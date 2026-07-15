#!/usr/bin/env python3
"""Generate API reference documentation stubs using mkdocstrings.

This script scans the scpi_control package, generates markdown stub pages that use
mkdocstrings autodoc syntax, and creates cross-references between related modules.

Usage:
    python scripts/docs/generate_api_stubs.py

Output:
    Updates all files in docs/api/ with mkdocstrings syntax
"""

import ast
import importlib.util
from pathlib import Path
from typing import Dict, List, Optional

import yaml


def load_config(config_path: Path = None) -> dict:
    """Load documentation generation configuration.

    Args:
        config_path: Path to docs_config.yaml. If None, uses default location.

    Returns:
        Configuration dictionary.
    """
    if config_path is None:
        config_path = Path(__file__).parent / "docs_config.yaml"

    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_module_docstring(module_path: Path) -> str:
    """Extract module-level docstring from a Python file.

    Args:
        module_path: Path to Python module file.

    Returns:
        Module docstring or empty string.
    """
    try:
        with open(module_path, "r", encoding="utf-8") as f:
            content = f.read()

        tree = ast.parse(content, filename=str(module_path))
        return ast.get_docstring(tree) or ""
    except Exception as e:
        print(f"  Warning: Could not parse {module_path}: {e}")
        return ""


def find_module_file(package_dir: Path, module_name: str) -> Optional[Path]:
    """Find the Python file for a given module name.

    Args:
        package_dir: Root package directory (scpi_control/).
        module_name: Module name (e.g., "oscilloscope" or "connection.socket").

    Returns:
        Path to module file or None if not found.
    """
    # Handle dotted module names (e.g., "connection.socket")
    parts = module_name.split(".")

    if len(parts) == 1:
        # Top-level module (e.g., "oscilloscope.py")
        module_file = package_dir / f"{module_name}.py"
        if module_file.exists():
            return module_file
    else:
        # Submodule (e.g., "connection/socket.py")
        submodule_path = package_dir / "/".join(parts[:-1]) / f"{parts[-1]}.py"
        if submodule_path.exists():
            return submodule_path

        # Try as subpackage __init__.py
        subpackage_init = package_dir / "/".join(parts) / "__init__.py"
        if subpackage_init.exists():
            return subpackage_init

    return None


def get_related_modules(module_name: str, all_modules: List[Dict]) -> List[Dict]:
    """Find related modules based on functionality.

    Args:
        module_name: Current module name.
        all_modules: List of all module configurations.

    Returns:
        List of related module dicts.
    """
    relationships = {
        "oscilloscope": ["channel", "trigger", "waveform", "measurement", "exceptions"],
        "channel": ["oscilloscope", "trigger"],
        "trigger": ["oscilloscope", "channel"],
        "waveform": ["oscilloscope", "channel", "analysis"],
        "measurement": ["oscilloscope", "waveform"],
        "analysis": ["waveform"],
        "automation": ["oscilloscope", "waveform", "measurement"],
        "connection.socket": ["oscilloscope", "exceptions"],
        "exceptions": ["oscilloscope", "connection.socket"],
        "models": ["oscilloscope"],
        "vector_graphics": ["oscilloscope", "waveform"],
        "screen_capture": ["oscilloscope"],
        "reference_waveform": ["oscilloscope", "waveform"],
        "math_channel": ["oscilloscope", "waveform"],
    }

    related_names = relationships.get(module_name, [])

    # Find module dicts for related names
    related = []
    for mod in all_modules:
        if mod["name"] in related_names:
            related.append(mod)

    return related


def generate_api_stub(module_info: Dict, related_modules: List[Dict]) -> str:
    """Generate markdown stub for an API module using mkdocstrings.

    Args:
        module_info: Module configuration dict.
        related_modules: List of related module dicts.

    Returns:
        Markdown content.
    """
    lines = []

    # Title
    title = module_info["title"]
    lines.append(f"# {title}")
    lines.append("")

    # Description
    description = module_info.get("description", "")
    if description:
        lines.append(description)
        lines.append("")

    # Mkdocstrings autodoc section
    module_path = f"scpi_control.{module_info['name']}"
    lines.append(f"::: {module_path}")
    lines.append("    options:")
    lines.append("      show_root_heading: false")
    lines.append("      show_source: true")
    lines.append("      heading_level: 2")
    lines.append("      members_order: source")
    lines.append("      group_by_category: true")
    lines.append("      show_signature_annotations: true")
    lines.append("      separate_signature: true")
    lines.append("      merge_init_into_class: true")
    lines.append("      filters:")
    lines.append('        - "!^_"  # Exclude private members')
    lines.append("")

    # Related modules section
    if related_modules:
        lines.append("## See Also")
        lines.append("")
        for related in related_modules:
            related_title = related["title"]
            # Replace dots with underscores for file names
            related_file = related["name"].replace(".", "_")
            lines.append(f"- [{related_title}]({related_file}.md) - {related.get('description', '')}")
        lines.append("")

    return "\n".join(lines)


def main():
    """Generate all API reference stubs."""
    print("Generating API reference documentation...")

    # Load configuration
    config = load_config()
    api_config = config["api"]

    # Paths
    root_dir = Path(__file__).parent.parent.parent
    package_dir = root_dir / api_config["package_dir"]
    output_dir = root_dir / api_config["output_dir"]

    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    # Get all modules from config
    modules = api_config["modules"]

    # Sort by priority
    modules_sorted = sorted(modules, key=lambda m: m.get("priority", 999))

    # Generate stub for each module
    for module_info in modules_sorted:
        module_name = module_info["name"]
        print(f"  Generating {module_name}.md...")

        # Find module file
        module_file = find_module_file(package_dir, module_name)
        if not module_file:
            print(f"    Warning: Module file not found for {module_name}, skipping")
            continue

        # Get related modules
        related_modules = get_related_modules(module_name, modules)

        # Generate stub content
        content = generate_api_stub(module_info, related_modules)

        # Write to output file
        output_filename = module_name.replace(".", "_") + ".md"
        output_file = output_dir / output_filename
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(content)

        print(f"    Created {output_file}")

    print("API reference documentation generated successfully!")
    print(f"  Output: {output_dir}")


if __name__ == "__main__":
    main()
