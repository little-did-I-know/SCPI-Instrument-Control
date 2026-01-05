"""
Plot style configuration for matplotlib plots.

Allows customization of waveform plot appearance including colors,
line styles, fonts, and grid settings.
"""

from dataclasses import asdict, dataclass
from typing import Any, Dict


@dataclass
class PlotStyle:
    """Matplotlib plot style configuration."""

    # Colors
    waveform_color: str = "#1f77b4"
    fft_color: str = "#ff7f0e"
    grid_color: str = "#cccccc"
    background_color: str = "#ffffff"

    # Line styles
    waveform_linewidth: float = 0.8
    grid_alpha: float = 0.3
    grid_enabled: bool = True

    # Font sizes
    title_fontsize: int = 11
    label_fontsize: int = 10
    tick_fontsize: int = 9

    # Matplotlib style preset
    matplotlib_style: str = "default"  # "default", "seaborn", "ggplot", etc.

    def apply_to_axes(self, ax):
        """
        Apply this style to a matplotlib axes object.

        Args:
            ax: Matplotlib axes object to apply style to
        """
        # Apply grid
        if self.grid_enabled:
            ax.grid(True, alpha=self.grid_alpha, color=self.grid_color)
        else:
            ax.grid(False)

        # Apply background color
        ax.set_facecolor(self.background_color)

        # Apply font sizes
        if hasattr(ax, "title"):
            ax.title.set_fontsize(self.title_fontsize)
        if hasattr(ax, "xaxis"):
            ax.xaxis.label.set_fontsize(self.label_fontsize)
        if hasattr(ax, "yaxis"):
            ax.yaxis.label.set_fontsize(self.label_fontsize)

        # Apply tick font size
        ax.tick_params(labelsize=self.tick_fontsize)

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary.

        Returns:
            Dictionary representation of plot style
        """
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlotStyle":
        """
        Create from dictionary.

        Args:
            data: Dictionary with plot style settings

        Returns:
            PlotStyle instance
        """
        return cls(**data)
