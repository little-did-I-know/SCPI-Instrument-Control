#!/usr/bin/env python3
"""Generate example documentation from Python example files.

This script parses all example files in the examples/ directory, extracts their
docstrings and source code, categorizes them by difficulty level, and generates
structured markdown documentation for MkDocs.

Usage:
    python scripts/docs/generate_examples_docs.py

Output:
    - docs/examples/beginner.md
    - docs/examples/intermediate.md
    - docs/examples/advanced.md
"""

import ast
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import yaml


@dataclass
class ExampleMetadata:
    """Metadata extracted from an example file."""

    filename: str
    filepath: Path
    title: str
    description: str
    module_docstring: str
    source_code: str
    scope_ip: str
    category: str
    requirements: List[str]
    no_hardware: bool
    mock_by_default: bool


# Phrases examples actually use in their docstrings to say they need no real
# instrument (mock-only, synthetic data, etc.). Matched case-insensitively
# against the module docstring so examples that document themselves as
# hardware-free don't get an oscilloscope requirement or SCOPE_IP
# configuration block stamped on them.
NO_HARDWARE_PATTERN = re.compile(
    r"no hardware|mock connection|fully synthetic|without hardware|hardware-free|no instrument needed",
    re.IGNORECASE,
)

# The mock-first examples refresh (2026-08) gave every network-facing example
# a `--host` flag defaulting to "mock": no hardware is required to run them,
# but a real instrument remains one flag away. Their docstrings all share the
# phrasing "Requirements: none by default -- runs against the built-in mock
# ...". This is a *third* state distinct from NO_HARDWARE_PATTERN's "no real
# instrument path exists at all" (e.g. synthetic_signals.py) -- these examples
# DO have a real-hardware path, it's just not the default.
MOCK_BY_DEFAULT_PATTERN = re.compile(
    r"none by default\s*--\s*runs against (?:the|a) built-in mock",
    re.IGNORECASE,
)


def is_no_hardware_example(docstring: str) -> bool:
    """Detect whether an example's docstring declares it needs no real hardware.

    Args:
        docstring: Module docstring.

    Returns:
        True if the docstring indicates the example runs without hardware.
    """
    return bool(NO_HARDWARE_PATTERN.search(docstring))


def is_mock_by_default_example(docstring: str) -> bool:
    """Detect whether an example defaults to a mock but also supports real hardware.

    Args:
        docstring: Module docstring.

    Returns:
        True if the docstring uses the mock-first-examples-refresh phrasing
        ("Requirements: none by default -- runs against the built-in mock ...").
    """
    return bool(MOCK_BY_DEFAULT_PATTERN.search(docstring))


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


def extract_module_docstring(filepath: Path) -> str:
    """Extract the module-level docstring from a Python file.

    Args:
        filepath: Path to Python file.

    Returns:
        Module docstring or empty string if none found.
    """
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        tree = ast.parse(content, filename=str(filepath))
        return ast.get_docstring(tree) or ""
    except Exception as e:
        print(f"Warning: Could not parse {filepath}: {e}")
        return ""


def extract_scope_ip(filepath: Path) -> str:
    """Extract SCOPE_IP configuration from example file.

    Args:
        filepath: Path to Python file.

    Returns:
        SCOPE_IP value or default placeholder.
    """
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        # Match: SCOPE_IP = "..."
        match = re.search(r'SCOPE_IP\s*=\s*["\']([^"\']+)["\']', content)
        if match:
            return match.group(1)
    except Exception:
        pass

    return "192.168.1.100"


def extract_requirements(filepath: Path, docstring: str) -> List[str]:
    """Extract requirements from docstring or imports.

    Args:
        filepath: Path to Python file.
        docstring: Module docstring.

    Returns:
        List of requirements.
    """
    requirements = []

    # Check for special dependencies in imports
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        if "from scpi_control.vector_graphics import" in content and "VectorDisplay" in content:
            requirements.append("scpi_control[fun] - Vector graphics extras")
        elif "matplotlib" in content:
            requirements.append("matplotlib - For plotting")

        if "PyQt" in content:
            requirements.append("PyQt6 - For GUI")

    except Exception:
        pass

    # Default requirements
    if not requirements:
        requirements = ["scpi_control - Core library"]

    if is_mock_by_default_example(docstring):
        requirements.append("None -- runs on the built-in mock; `--host <ip>` for real hardware")
    elif is_no_hardware_example(docstring):
        requirements.append("No hardware required")
    else:
        requirements.append("Oscilloscope connected to network")

    return requirements


def get_example_title(filename: str, docstring: str) -> str:
    """Generate a human-readable title from filename or docstring.

    Args:
        filename: Example filename (e.g., "simple_capture.py").
        docstring: Module docstring.

    Returns:
        Human-readable title.
    """
    # Try to extract title from docstring first line
    if docstring:
        first_line = docstring.split("\n")[0].strip()
        if first_line and not first_line.startswith("This"):
            return first_line.rstrip(".")

    # Generate from filename
    name = filename.replace(".py", "").replace("_", " ").title()
    return name


def slugify_heading(title: str) -> str:
    """Slugify a heading the same way Python-Markdown's ``toc`` extension does.

    MkDocs (via Python-Markdown's ``toc`` extension, as configured with
    ``permalink: true`` and no custom slugify function) generates heading
    anchors with ``markdown.extensions.toc.slugify(value, '-')``. That
    function: NFKD-normalizes and drops non-ASCII characters, strips
    everything that isn't a word character, whitespace, or hyphen, lowercases
    the result, then collapses runs of whitespace into a single separator.
    Reimplemented here (rather than importing ``markdown``) so the TOC links
    generated in this script always match the anchors MkDocs actually emits.

    Args:
        title: Heading text (e.g. an example's title).

    Returns:
        URL anchor fragment (without the leading '#').
    """
    value = unicodedata.normalize("NFKD", title)
    value = value.encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^\w\s-]", "", value).strip().lower()
    return re.sub(r"[-\s]+", "-", value)


def categorize_example(filename: str, config: dict) -> str:
    """Determine the category (beginner/intermediate/advanced) for an example.

    Args:
        filename: Example filename.
        config: Configuration dictionary.

    Returns:
        Category name (beginner, intermediate, or advanced).
    """
    categories = config["examples"]["categories"]

    for category, files in categories.items():
        if filename in files:
            return category

    return "intermediate"  # Default


def parse_example_file(filepath: Path, config: dict) -> ExampleMetadata:
    """Parse an example file and extract metadata.

    Args:
        filepath: Path to example file.
        config: Configuration dictionary.

    Returns:
        ExampleMetadata object.
    """
    filename = filepath.name
    docstring = extract_module_docstring(filepath)
    scope_ip = extract_scope_ip(filepath)
    requirements = extract_requirements(filepath, docstring)
    category = categorize_example(filename, config)
    title = get_example_title(filename, docstring)

    # Read full source code
    with open(filepath, "r", encoding="utf-8") as f:
        source_code = f.read()

    return ExampleMetadata(
        filename=filename,
        filepath=filepath,
        title=title,
        description=docstring.split("\n\n")[0] if docstring else "",
        module_docstring=docstring,
        source_code=source_code,
        scope_ip=scope_ip,
        category=category,
        requirements=requirements,
        no_hardware=is_no_hardware_example(docstring),
        mock_by_default=is_mock_by_default_example(docstring),
    )


def generate_example_section(example: ExampleMetadata) -> str:
    """Generate markdown section for a single example.

    Args:
        example: ExampleMetadata object.

    Returns:
        Markdown formatted string.
    """
    lines = []

    # Title
    lines.append(f"## {example.title}")
    lines.append("")

    # Description
    if example.description:
        lines.append(example.description)
        lines.append("")

    # Requirements
    if example.requirements:
        lines.append("### Requirements")
        lines.append("")
        for req in example.requirements:
            lines.append(f"- {req}")
        lines.append("")

    # Configuration
    lines.append("### Configuration")
    lines.append("")
    if example.mock_by_default:
        lines.append("None -- runs on the built-in mock with no setup. Pass `--host <ip>` to drive real hardware instead.")
    elif example.no_hardware:
        lines.append("No hardware required.")
    else:
        lines.append(f"Update `SCOPE_IP` to match your oscilloscope's IP address (default: `{example.scope_ip}`).")
    lines.append("")

    # Usage
    lines.append("### Usage")
    lines.append("")
    lines.append("```bash")
    lines.append(f"python examples/{example.filename}")
    lines.append("```")
    lines.append("")

    # Full source code
    lines.append("### Source Code")
    lines.append("")
    lines.append("```python")
    lines.append(example.source_code.rstrip())
    lines.append("```")
    lines.append("")

    # Separator
    lines.append("---")
    lines.append("")

    return "\n".join(lines)


def generate_category_page(category: str, examples: List[ExampleMetadata], config: dict) -> str:
    """Generate a complete markdown page for a category of examples.

    Args:
        category: Category name (beginner, intermediate, advanced).
        examples: List of ExampleMetadata for this category.
        config: Configuration dictionary.

    Returns:
        Complete markdown page content.
    """
    lines = []

    # Page header
    title = category.title()
    lines.append(f"# {title} Examples")
    lines.append("")

    # Description based on category
    descriptions = {
        "beginner": "Complete examples for getting started with the Siglent Oscilloscope library. These examples demonstrate core functionality and common use cases.",
        "intermediate": "Intermediate examples showing automation patterns, real-time data capture, and batch operations for more advanced use cases.",
        "advanced": "Advanced examples demonstrating signal analysis, FFT processing, and specialized features like vector graphics for XY mode display.",
    }

    lines.append(descriptions.get(category, f"{title} examples for the Siglent Oscilloscope library."))
    lines.append("")

    # Quick reference table
    lines.append("## Quick Reference")
    lines.append("")
    lines.append("| Example | Description |")
    lines.append("|---------|-------------|")
    for example in examples:
        anchor = slugify_heading(example.title)
        lines.append(f"| [{example.title}](#{anchor}) | {example.description} |")
    lines.append("")

    lines.append("---")
    lines.append("")

    # Examples
    for example in examples:
        section = generate_example_section(example)
        lines.append(section)

    # Footer with navigation
    lines.append("## Next Steps")
    lines.append("")

    if category == "beginner":
        lines.append("Ready to learn more? Check out the [Intermediate Examples](intermediate.md) for automation and real-time capture patterns.")
    elif category == "intermediate":
        lines.append("Explore [Advanced Examples](advanced.md) for signal analysis and specialized features, or review [Beginner Examples](beginner.md) for fundamentals.")
    else:  # advanced
        lines.append("Review the [API Reference](../api/oscilloscope.md) for detailed documentation of all available methods and properties.")

    lines.append("")
    lines.append("See also:")
    lines.append("")
    lines.append("- [User Guide](../user-guide/basic-usage.md) - Conceptual documentation")
    lines.append("- [API Reference](../api/oscilloscope.md) - Detailed API documentation")
    lines.append("- [Getting Started](../getting-started/quickstart.md) - Quick start guide")
    lines.append("")

    return "\n".join(lines)


def main():
    """Generate all example documentation."""
    print("Generating example documentation...")

    # Load configuration
    config = load_config()
    examples_config = config["examples"]

    # Paths
    root_dir = Path(__file__).parent.parent.parent
    source_dir = root_dir / examples_config["source_dir"]
    output_dir = root_dir / examples_config["output_dir"]

    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    # Parse all examples
    examples_by_category: Dict[str, List[ExampleMetadata]] = {
        "beginner": [],
        "intermediate": [],
        "advanced": [],
    }

    categories = examples_config["categories"]
    all_example_files = set()
    for category_files in categories.values():
        all_example_files.update(category_files)

    for example_file in sorted(all_example_files):
        filepath = source_dir / example_file

        if not filepath.exists():
            print(f"Warning: Example file not found: {filepath}")
            continue

        print(f"  Parsing {example_file}...")
        metadata = parse_example_file(filepath, config)
        examples_by_category[metadata.category].append(metadata)

    # Generate documentation pages
    for category, examples in examples_by_category.items():
        if not examples:
            continue

        print(f"  Generating {category}.md ({len(examples)} examples)...")
        content = generate_category_page(category, examples, config)

        output_file = output_dir / f"{category}.md"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(content)

        print(f"    Created {output_file}")

    print("Example documentation generated successfully!")
    print(f"  Output: {output_dir}")


if __name__ == "__main__":
    main()
