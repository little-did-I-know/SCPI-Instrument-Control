#!/usr/bin/env python3
"""Build standalone executable for Siglent Oscilloscope GUI application.

This script builds platform-specific executables using PyInstaller.
Supports Windows (.exe), macOS (.app), and Linux (binary).

Usage:
    python scripts/build_executable.py              # Build for current platform
    python scripts/build_executable.py --clean      # Clean before building
    python scripts/build_executable.py --test       # Build and test executable
"""

import argparse
import platform
import shutil
import subprocess
import sys
from pathlib import Path


def get_platform_info():
    """Get current platform information."""
    system = platform.system().lower()

    if system == "windows":
        return {"name": "Windows", "executable": "SiglentGUI.exe", "archive_ext": ".zip", "platform_suffix": "Windows-x64"}
    elif system == "darwin":
        return {"name": "macOS", "executable": "SiglentGUI.app", "archive_ext": ".zip", "platform_suffix": "macOS-arm64"}
    elif system == "linux":
        return {"name": "Linux", "executable": "SiglentGUI", "archive_ext": ".tar.gz", "platform_suffix": "Linux-x86_64"}
    else:
        return {"name": system, "executable": "SiglentGUI", "archive_ext": ".tar.gz", "platform_suffix": system}


def clean_build_artifacts():
    """Remove previous build artifacts."""
    print("Cleaning build artifacts...")

    paths_to_remove = [
        Path("build"),
        Path("dist"),
        Path("siglent-gui.spec~"),
    ]

    for path in paths_to_remove:
        if path.exists():
            if path.is_dir():
                shutil.rmtree(path)
                print(f"  Removed: {path}/")
            else:
                path.unlink()
                print(f"  Removed: {path}")

    print("✓ Clean complete\n")


def check_dependencies():
    """Check if required dependencies are installed."""
    print("Checking dependencies...")

    try:
        import PyInstaller

        print(f"  ✓ PyInstaller {PyInstaller.__version__}")
    except ImportError:
        print("  ✗ PyInstaller not found")
        print("\nInstalling PyInstaller...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)
        print("  ✓ PyInstaller installed")

    # Check if spec file exists
    spec_file = Path("siglent-gui.spec")
    if not spec_file.exists():
        print(f"  ✗ Spec file not found: {spec_file}")
        sys.exit(1)
    else:
        print(f"  ✓ Spec file found: {spec_file}")

    print("✓ All dependencies ready\n")


def build_executable():
    """Build the executable using PyInstaller."""
    platform_info = get_platform_info()

    print(f"Building executable for {platform_info['name']}...")
    print(f"Target: {platform_info['executable']}\n")

    # Run PyInstaller
    cmd = [sys.executable, "-m", "PyInstaller", "--clean", "--noconfirm", "siglent-gui.spec"]

    print(f"Running: {' '.join(cmd)}\n")
    print("=" * 70)

    result = subprocess.run(cmd)

    print("=" * 70)

    if result.returncode != 0:
        print("\n✗ Build failed!")
        sys.exit(1)

    # Check if executable was created
    dist_path = Path("dist") / platform_info["executable"]

    if not dist_path.exists():
        print(f"\n✗ Executable not found: {dist_path}")
        sys.exit(1)

    print(f"\n✓ Build successful!")
    print(f"\nExecutable location:")
    print(f"  {dist_path.absolute()}")

    # Show file size
    if dist_path.is_file():
        size_mb = dist_path.stat().st_size / (1024 * 1024)
        print(f"\nFile size: {size_mb:.1f} MB")
    elif dist_path.is_dir():
        # Calculate size of .app bundle
        total_size = sum(f.stat().st_size for f in dist_path.rglob("*") if f.is_file())
        size_mb = total_size / (1024 * 1024)
        print(f"\nBundle size: {size_mb:.1f} MB")

    return dist_path


def test_executable(executable_path):
    """Test the built executable."""
    platform_info = get_platform_info()

    print("\n" + "=" * 70)
    print("Testing executable...")
    print("=" * 70)

    if not executable_path.exists():
        print(f"✗ Executable not found: {executable_path}")
        return False

    print(f"\nExecutable: {executable_path}")
    print("\nNOTE: This will attempt to launch the GUI application.")
    print("      Close the application window to continue.")

    input("\nPress Enter to launch the executable (or Ctrl+C to skip)...")

    try:
        if platform_info["name"] == "macOS":
            # Open .app bundle on macOS
            subprocess.run(["open", str(executable_path)])
        elif platform_info["name"] == "Windows":
            subprocess.run([str(executable_path)])
        else:
            # Linux
            subprocess.run([str(executable_path)])

        print("\n✓ Executable launched successfully")
        return True

    except Exception as e:
        print(f"\n✗ Failed to launch executable: {e}")
        return False


def create_archive(executable_path):
    """Create a distributable archive."""
    platform_info = get_platform_info()

    print("\n" + "=" * 70)
    print("Creating distribution archive...")
    print("=" * 70)

    # Get version from pyproject.toml or use 'dev'
    version = get_version()

    archive_name = f"SiglentGUI-{version}-{platform_info['platform_suffix']}"

    print(f"\nArchive: {archive_name}{platform_info['archive_ext']}")

    dist_dir = Path("dist")

    if platform_info["archive_ext"] == ".zip":
        import zipfile

        archive_path = dist_dir / f"{archive_name}.zip"

        with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            # Add executable
            if executable_path.is_file():
                zipf.write(executable_path, executable_path.name)
            elif executable_path.is_dir():
                # Add .app bundle recursively
                for file in executable_path.rglob("*"):
                    if file.is_file():
                        arcname = str(file.relative_to(dist_dir))
                        zipf.write(file, arcname)

            # Add README and LICENSE if they exist
            for doc_file in ["README.md", "LICENSE"]:
                if Path(doc_file).exists():
                    zipf.write(doc_file, doc_file)

        print(f"✓ Created: {archive_path}")

    else:  # .tar.gz for Linux
        import tarfile

        archive_path = dist_dir / f"{archive_name}.tar.gz"

        with tarfile.open(archive_path, "w:gz") as tar:
            tar.add(executable_path, arcname=executable_path.name)

            for doc_file in ["README.md", "LICENSE"]:
                if Path(doc_file).exists():
                    tar.add(doc_file, arcname=doc_file)

        print(f"✓ Created: {archive_path}")

    size_mb = archive_path.stat().st_size / (1024 * 1024)
    print(f"  Size: {size_mb:.1f} MB")

    return archive_path


def get_version():
    """Extract version from pyproject.toml."""
    try:
        import tomli
    except ImportError:
        # Python 3.11+ has tomllib built-in
        try:
            import tomllib as tomli
        except ImportError:
            # Fallback: parse manually
            return parse_version_manual()

    try:
        with open("pyproject.toml", "rb") as f:
            data = tomli.load(f)
            return data.get("project", {}).get("version", "dev")
    except Exception:
        return parse_version_manual()


def parse_version_manual():
    """Manually parse version from pyproject.toml."""
    try:
        with open("pyproject.toml", "r") as f:
            for line in f:
                if line.strip().startswith("version"):
                    # Extract version from: version = "0.3.1"
                    return line.split("=")[1].strip().strip('"').strip("'")
    except Exception:
        pass
    return "dev"


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Build standalone executable for Siglent GUI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/build_executable.py              # Build for current platform
  python scripts/build_executable.py --clean      # Clean before building
  python scripts/build_executable.py --test       # Build and test
  python scripts/build_executable.py --archive    # Build and create archive
        """,
    )

    parser.add_argument("--clean", action="store_true", help="Clean build artifacts before building")

    parser.add_argument("--test", action="store_true", help="Test the executable after building")

    parser.add_argument("--archive", action="store_true", help="Create a distributable archive after building")

    args = parser.parse_args()

    print("=" * 70)
    print("Siglent Oscilloscope GUI - Executable Builder")
    print("=" * 70)
    print()

    # Clean if requested
    if args.clean:
        clean_build_artifacts()

    # Check dependencies
    check_dependencies()

    # Build
    executable_path = build_executable()

    # Test if requested
    if args.test:
        test_executable(executable_path)

    # Create archive if requested
    if args.archive:
        create_archive(executable_path)

    print("\n" + "=" * 70)
    print("Build complete!")
    print("=" * 70)

    return 0


if __name__ == "__main__":
    sys.exit(main())
