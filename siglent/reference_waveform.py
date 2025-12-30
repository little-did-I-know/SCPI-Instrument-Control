"""Reference waveform storage and management for comparison."""

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)


class ReferenceWaveform:
    """Manages reference waveforms for comparison with live data.

    Reference waveforms are stored as NPZ files in a user directory,
    allowing users to capture and compare against known-good signals.
    """

    def __init__(self, storage_dir: Optional[str] = None):
        """Initialize reference waveform manager.

        Args:
            storage_dir: Directory to store reference waveforms.
                        Defaults to ~/.siglent/references/
        """
        if storage_dir is None:
            # Use default directory in user's home
            home_dir = Path.home()
            storage_dir = home_dir / ".siglent" / "references"
        else:
            storage_dir = Path(storage_dir)

        self.storage_dir = Path(storage_dir)

        # Create directory if it doesn't exist
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Reference waveform storage initialized at: {self.storage_dir}")

    def save_reference(self, waveform, name: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Save a waveform as a reference.

        Args:
            waveform: WaveformData object
            name: Reference name (will be sanitized)
            metadata: Optional metadata dictionary

        Returns:
            Path to saved reference file

        Raises:
            ValueError: If waveform is None or name is empty
            IOError: If save fails
        """
        if waveform is None:
            raise ValueError("Cannot save None waveform as reference")

        if not name or not name.strip():
            raise ValueError("Reference name cannot be empty")

        # Sanitize name (remove special characters)
        safe_name = self._sanitize_name(name)

        # Create filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{safe_name}_{timestamp}.npz"
        filepath = self.storage_dir / filename

        # Prepare metadata
        if metadata is None:
            metadata = {}

        metadata["name"] = name
        metadata["timestamp"] = datetime.now().isoformat()
        metadata["channel"] = getattr(waveform, "channel", "Unknown")

        # Add waveform statistics
        metadata["min_voltage"] = float(np.min(waveform.voltage))
        metadata["max_voltage"] = float(np.max(waveform.voltage))
        metadata["mean_voltage"] = float(np.mean(waveform.voltage))
        metadata["std_voltage"] = float(np.std(waveform.voltage))
        metadata["num_samples"] = len(waveform.voltage)
        metadata["time_span"] = float(waveform.time[-1] - waveform.time[0]) if len(waveform.time) > 1 else 0.0

        try:
            # Save as NPZ with compression
            np.savez_compressed(filepath, time=waveform.time, voltage=waveform.voltage, metadata=metadata)

            logger.info(f"Reference waveform saved: {filepath}")
            return str(filepath)

        except Exception as e:
            logger.error(f"Failed to save reference waveform: {e}")
            raise IOError(f"Failed to save reference: {e}")

    def load_reference(self, name: str) -> Optional[Dict[str, Any]]:
        """Load a reference waveform by name.

        Args:
            name: Reference name or filename

        Returns:
            Dictionary with 'time', 'voltage', and 'metadata' keys, or None if not found
        """
        # Try to find the file
        filepath = self._find_reference_file(name)

        if filepath is None:
            logger.warning(f"Reference waveform not found: {name}")
            return None

        try:
            # Load NPZ file
            data = np.load(filepath, allow_pickle=True)

            result = {
                "time": data["time"],
                "voltage": data["voltage"],
                "metadata": data["metadata"].item() if "metadata" in data else {},
                "filepath": str(filepath),
            }

            logger.info(f"Reference waveform loaded: {filepath}")
            return result

        except Exception as e:
            logger.error(f"Failed to load reference waveform: {e}")
            return None

    def list_references(self) -> List[Dict[str, Any]]:
        """List all available reference waveforms.

        Returns:
            List of dictionaries with reference information
        """
        references = []

        try:
            # Find all NPZ files in storage directory
            for filepath in self.storage_dir.glob("*.npz"):
                try:
                    # Load metadata without loading full data
                    data = np.load(filepath, allow_pickle=True)
                    metadata = data["metadata"].item() if "metadata" in data else {}

                    ref_info = {
                        "filename": filepath.name,
                        "filepath": str(filepath),
                        "name": metadata.get("name", filepath.stem),
                        "timestamp": metadata.get("timestamp", ""),
                        "channel": metadata.get("channel", "Unknown"),
                        "num_samples": metadata.get("num_samples", 0),
                        "time_span": metadata.get("time_span", 0.0),
                        "min_voltage": metadata.get("min_voltage", 0.0),
                        "max_voltage": metadata.get("max_voltage", 0.0),
                        "file_size": filepath.stat().st_size,
                        "modified_time": datetime.fromtimestamp(filepath.stat().st_mtime).isoformat(),
                    }

                    references.append(ref_info)

                except Exception as e:
                    logger.warning(f"Failed to read reference {filepath.name}: {e}")

            # Sort by timestamp (most recent first)
            references.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

            logger.info(f"Found {len(references)} reference waveform(s)")
            return references

        except Exception as e:
            logger.error(f"Failed to list references: {e}")
            return []

    def delete_reference(self, name: str) -> bool:
        """Delete a reference waveform.

        Args:
            name: Reference name or filename

        Returns:
            True if deleted successfully, False otherwise
        """
        filepath = self._find_reference_file(name)

        if filepath is None:
            logger.warning(f"Reference waveform not found: {name}")
            return False

        try:
            filepath.unlink()
            logger.info(f"Reference waveform deleted: {filepath}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete reference: {e}")
            return False

    def rename_reference(self, old_name: str, new_name: str) -> bool:
        """Rename a reference waveform.

        Args:
            old_name: Current reference name
            new_name: New reference name

        Returns:
            True if renamed successfully, False otherwise
        """
        old_filepath = self._find_reference_file(old_name)

        if old_filepath is None:
            logger.warning(f"Reference waveform not found: {old_name}")
            return False

        try:
            # Load and update metadata
            data = np.load(old_filepath, allow_pickle=True)
            time = data["time"]
            voltage = data["voltage"]
            metadata = data["metadata"].item() if "metadata" in data else {}

            # Update name in metadata
            metadata["name"] = new_name

            # Create new filename
            safe_name = self._sanitize_name(new_name)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            new_filename = f"{safe_name}_{timestamp}.npz"
            new_filepath = self.storage_dir / new_filename

            # Save with new name
            np.savez_compressed(new_filepath, time=time, voltage=voltage, metadata=metadata)

            # Delete old file
            old_filepath.unlink()

            logger.info(f"Reference waveform renamed: {old_name} -> {new_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to rename reference: {e}")
            return False

    def calculate_difference(self, waveform, reference_data: Dict[str, Any]) -> Optional[np.ndarray]:
        """Calculate difference between a waveform and reference.

        Args:
            waveform: WaveformData object
            reference_data: Reference data dictionary from load_reference()

        Returns:
            Difference array (waveform - reference) or None if incompatible
        """
        if waveform is None or reference_data is None:
            return None

        try:
            ref_voltage = reference_data["voltage"]

            # Check if lengths match
            if len(waveform.voltage) != len(ref_voltage):
                logger.warning("Waveform and reference have different lengths, interpolating...")
                # Interpolate reference to match waveform time base
                ref_time = reference_data["time"]
                ref_voltage_interp = np.interp(waveform.time, ref_time, ref_voltage)
                return waveform.voltage - ref_voltage_interp
            else:
                return waveform.voltage - ref_voltage

        except Exception as e:
            logger.error(f"Failed to calculate difference: {e}")
            return None

    def calculate_correlation(self, waveform, reference_data: Dict[str, Any]) -> Optional[float]:
        """Calculate correlation coefficient between waveform and reference.

        Args:
            waveform: WaveformData object
            reference_data: Reference data dictionary from load_reference()

        Returns:
            Correlation coefficient (0.0 to 1.0) or None if incompatible
        """
        if waveform is None or reference_data is None:
            return None

        try:
            ref_voltage = reference_data["voltage"]

            # Interpolate if needed
            if len(waveform.voltage) != len(ref_voltage):
                ref_time = reference_data["time"]
                ref_voltage = np.interp(waveform.time, ref_time, ref_voltage)

            # Calculate correlation coefficient
            correlation = np.corrcoef(waveform.voltage, ref_voltage)[0, 1]

            return float(correlation)

        except Exception as e:
            logger.error(f"Failed to calculate correlation: {e}")
            return None

    def _sanitize_name(self, name: str) -> str:
        """Sanitize reference name for filesystem.

        Args:
            name: Original name

        Returns:
            Sanitized name safe for filesystem
        """
        # Replace spaces with underscores
        safe_name = name.strip().replace(" ", "_")

        # Remove special characters
        safe_chars = []
        for char in safe_name:
            if char.isalnum() or char in ("_", "-"):
                safe_chars.append(char)

        safe_name = "".join(safe_chars)

        # Limit length
        if len(safe_name) > 50:
            safe_name = safe_name[:50]

        return safe_name if safe_name else "reference"

    def _find_reference_file(self, name: str) -> Optional[Path]:
        """Find reference file by name.

        Args:
            name: Reference name or filename

        Returns:
            Path to reference file or None if not found
        """
        # If name is already a full path, use it
        if os.path.isabs(name):
            filepath = Path(name)
            if filepath.exists():
                return filepath
            return None

        # Try as filename directly
        filepath = self.storage_dir / name
        if filepath.exists():
            return filepath

        # Try with .npz extension
        if not name.endswith(".npz"):
            filepath = self.storage_dir / f"{name}.npz"
            if filepath.exists():
                return filepath

        # Search for files containing the name
        for filepath in self.storage_dir.glob("*.npz"):
            try:
                data = np.load(filepath, allow_pickle=True)
                metadata = data["metadata"].item() if "metadata" in data else {}
                if metadata.get("name", "") == name:
                    return filepath
            except:
                continue

        return None

    def get_storage_size(self) -> int:
        """Get total size of reference storage in bytes.

        Returns:
            Total size in bytes
        """
        total_size = 0
        try:
            for filepath in self.storage_dir.glob("*.npz"):
                total_size += filepath.stat().st_size
        except Exception as e:
            logger.error(f"Failed to calculate storage size: {e}")

        return total_size

    def clear_all_references(self) -> int:
        """Delete all reference waveforms.

        Returns:
            Number of references deleted
        """
        count = 0
        try:
            for filepath in self.storage_dir.glob("*.npz"):
                try:
                    filepath.unlink()
                    count += 1
                except Exception as e:
                    logger.warning(f"Failed to delete {filepath.name}: {e}")

            logger.info(f"Cleared {count} reference waveform(s)")
            return count

        except Exception as e:
            logger.error(f"Failed to clear references: {e}")
            return count

    def __repr__(self) -> str:
        """String representation."""
        num_refs = len(self.list_references())
        size_mb = self.get_storage_size() / (1024 * 1024)
        return f"ReferenceWaveform(storage={self.storage_dir}, refs={num_refs}, size={size_mb:.2f}MB)"
