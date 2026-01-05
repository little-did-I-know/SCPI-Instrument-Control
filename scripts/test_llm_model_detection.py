#!/usr/bin/env python3
"""
Test script for LLM settings dialog model detection feature.

This script tests the new "Detect Models" functionality for Ollama and LM Studio.
"""

import sys
from PyQt6.QtWidgets import QApplication

from siglent.report_generator.llm.client import LLMConfig
from siglent.report_generator.widgets.llm_settings_dialog import LLMSettingsDialog


def main():
    """Test the LLM settings dialog."""
    print("LLM Settings Dialog - Model Detection Test")
    print("=" * 60)

    app = QApplication(sys.argv)

    # Create a default config
    config = LLMConfig.create_ollama_config(
        model="llama3.2",
        hostname="localhost",
        port=11434
    )

    print("\nOpening LLM Settings Dialog...")
    print("\nFeatures to test:")
    print("  1. Ollama tab has 'Detect Models' button")
    print("  2. LM Studio tab has 'Detect Models' button")
    print("  3. Model field is now a combo box (editable)")
    print("  4. Clicking 'Detect Models' queries the server")
    print("  5. Available models populate the combo box")
    print("  6. Manual entry still works (combo is editable)")
    print("\nTest procedure:")
    print("  - Go to Ollama tab")
    print("  - Click 'Detect Models' button")
    print("  - Verify models are listed (if Ollama is running)")
    print("  - Select a model from dropdown")
    print("  - Repeat for LM Studio tab (if LM Studio is running)")
    print("  - Try manual entry by typing a model name")
    print("\nNote: You need Ollama or LM Studio running to test detection.")
    print("=" * 60)

    # Create and show dialog
    dialog = LLMSettingsDialog(current_config=config)

    # Show the dialog
    result = dialog.exec()

    if result:
        new_config = dialog.get_config()
        print("\n[PASS] Dialog accepted")
        print(f"\nNew configuration:")
        print(f"  Endpoint: {new_config.endpoint}")
        print(f"  Model: {new_config.model}")
        print(f"  Temperature: {new_config.temperature}")
        print(f"  Max Tokens: {new_config.max_tokens}")
        print(f"  Timeout: {new_config.timeout}")
    else:
        print("\n[INFO] Dialog cancelled")

    print("\nManual verification checklist:")
    print("  [  ] Ollama tab has 'Detect Models' button next to model field")
    print("  [  ] LM Studio tab has 'Detect Models' button next to model field")
    print("  [  ] Model combo box is editable (allows manual typing)")
    print("  [  ] Detect button queries server and populates models")
    print("  [  ] Error message shown if server unreachable")
    print("  [  ] Previously selected model is preserved after detection")
    print("  [  ] Model selection persists when switching tabs")

    return 0


if __name__ == "__main__":
    sys.exit(main())
