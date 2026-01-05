"""
Application settings for persistent user preferences.

Stores user preferences across sessions including last used template,
LLM provider, and report options.
"""

import json
import os
import platform
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from siglent.report_generator.models.report_options import ReportOptions


@dataclass
class AppSettings:
    """Application-level settings (persisted across sessions)."""

    last_used_template: Optional[str] = None
    last_llm_provider: Optional[str] = None
    last_options: Optional[ReportOptions] = None

    @staticmethod
    def get_settings_file() -> Path:
        """
        Get path to settings file.

        Returns platform-appropriate configuration directory:
        - Windows: %APPDATA%/SiglentReportGenerator/settings.json
        - macOS: ~/Library/Application Support/SiglentReportGenerator/settings.json
        - Linux: ~/.config/SiglentReportGenerator/settings.json

        Returns:
            Path to settings file
        """
        if platform.system() == "Windows":
            base = Path(os.environ.get("APPDATA", Path.home()))
        elif platform.system() == "Darwin":  # macOS
            base = Path.home() / "Library" / "Application Support"
        else:  # Linux and others
            base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))

        settings_dir = base / "SiglentReportGenerator"
        settings_dir.mkdir(parents=True, exist_ok=True)
        return settings_dir / "settings.json"

    def save(self) -> None:
        """Save settings to file."""
        data = {
            "last_used_template": self.last_used_template,
            "last_llm_provider": self.last_llm_provider,
            "last_options": self.last_options.to_dict() if self.last_options else None,
        }

        settings_file = self.get_settings_file()
        with open(settings_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    @classmethod
    def load(cls) -> "AppSettings":
        """
        Load settings from file.

        Returns:
            AppSettings instance (defaults if file doesn't exist)
        """
        settings_file = cls.get_settings_file()
        if not settings_file.exists():
            return cls()

        try:
            with open(settings_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            return cls(
                last_used_template=data.get("last_used_template"),
                last_llm_provider=data.get("last_llm_provider"),
                last_options=ReportOptions.from_dict(data["last_options"]) if data.get("last_options") else None,
            )
        except (json.JSONDecodeError, KeyError, Exception):
            # If loading fails, return defaults
            return cls()
