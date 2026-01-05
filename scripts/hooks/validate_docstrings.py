#!/usr/bin/env python3
"""Validate Python docstrings in modified files.

This pre-commit hook validates that:
- All public functions, classes, and modules have docstrings
- Docstrings follow Google style format
- Required sections (Args, Returns, Raises) are present
- Docstrings meet minimum length requirements

Usage:
    python scripts/hooks/validate_docstrings.py file1.py file2.py ...

Exit codes:
    0 - All validations passed
    1 - Validation failures found
"""

import ast
import re
import sys
from pathlib import Path
from typing import List, Tuple

import yaml


def load_config(config_path: Path = None) -> dict:
    """Load docstring validation configuration.

    Args:
        config_path: Path to .docstring-validation.yaml. If None, uses default.

    Returns:
        Configuration dictionary.
    """
    if config_path is None:
        config_path = Path(".docstring-validation.yaml")

    if not config_path.exists():
        # Return default config
        return {
            "strict_mode": False,
            "require_module_docstrings": True,
            "require_class_docstrings": True,
            "require_function_docstrings": True,
            "min_module_docstring_length": 10,
            "min_class_docstring_length": 20,
            "min_function_docstring_length": 15,
            "style": "google",
            "sections": {
                "require_args": True,
                "require_returns": True,
                "require_raises": False,
            },
        }

    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def is_public(name: str) -> bool:
    """Check if a name is public (doesn't start with _).

    Args:
        name: Function, class, or module name.

    Returns:
        True if public, False otherwise.
    """
    return not name.startswith("_")


def has_parameters(func: ast.FunctionDef) -> bool:
    """Check if a function has parameters (excluding self/cls).

    Args:
        func: AST FunctionDef node.

    Returns:
        True if function has parameters.
    """
    args = func.args.args
    if not args:
        return False

    # Exclude self/cls
    param_names = [arg.arg for arg in args]
    if param_names[0] in ("self", "cls"):
        param_names = param_names[1:]

    return len(param_names) > 0


def has_return_value(func: ast.FunctionDef) -> bool:
    """Check if a function has a return statement with a value.

    Args:
        func: AST FunctionDef node.

    Returns:
        True if function returns a value.
    """
    for node in ast.walk(func):
        if isinstance(node, ast.Return) and node.value is not None:
            return True
    return False


def check_google_style_sections(docstring: str, func: ast.FunctionDef, config: dict) -> List[str]:
    """Check for required Google-style docstring sections.

    Args:
        docstring: Docstring text.
        func: AST FunctionDef node.
        config: Configuration dictionary.

    Returns:
        List of error messages.
    """
    errors = []
    sections_config = config.get("sections", {})

    # Check for Args section
    if sections_config.get("require_args") and has_parameters(func):
        if not re.search(r"\n\s*Args:", docstring):
            errors.append("Missing 'Args:' section (function has parameters)")

    # Check for Returns section
    if sections_config.get("require_returns") and has_return_value(func):
        if not re.search(r"\n\s*Returns:", docstring):
            errors.append("Missing 'Returns:' section (function returns a value)")

    return errors


class DocstringValidator:
    """Validates docstrings in Python files."""

    def __init__(self, filepath: Path, config: dict):
        """Initialize validator.

        Args:
            filepath: Path to Python file.
            config: Configuration dictionary.
        """
        self.filepath = filepath
        self.config = config
        self.errors = []
        self.warnings = []

    def validate(self) -> Tuple[bool, List[str], List[str]]:
        """Validate all docstrings in file.

        Returns:
            Tuple of (success, errors, warnings).
        """
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                content = f.read()

            tree = ast.parse(content, filename=str(self.filepath))

            # Check module docstring
            self.check_module_docstring(tree)

            # Walk AST and check functions and classes
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    self.check_class_docstring(node)
                elif isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
                    self.check_function_docstring(node)

            success = len(self.errors) == 0
            return success, self.errors, self.warnings

        except SyntaxError as e:
            self.errors.append(f"Syntax error: {e}")
            return False, self.errors, self.warnings
        except Exception as e:
            self.errors.append(f"Validation error: {e}")
            return False, self.errors, self.warnings

    def check_module_docstring(self, module: ast.Module) -> None:
        """Check if module has a docstring.

        Args:
            module: AST Module node.
        """
        if not self.config.get("require_module_docstrings"):
            return

        docstring = ast.get_docstring(module)
        if not docstring:
            self.errors.append("Missing module-level docstring")
            return

        min_length = self.config.get("min_module_docstring_length", 10)
        if len(docstring) < min_length:
            self.warnings.append(f"Module docstring too short ({len(docstring)} chars, minimum {min_length})")

    def check_class_docstring(self, node: ast.ClassDef) -> None:
        """Check if class has a docstring.

        Args:
            node: AST ClassDef node.
        """
        if not is_public(node.name):
            return  # Skip private classes

        if not self.config.get("require_class_docstrings"):
            return

        docstring = ast.get_docstring(node)
        if not docstring:
            self.errors.append(f"Class '{node.name}' missing docstring (line {node.lineno})")
            return

        min_length = self.config.get("min_class_docstring_length", 20)
        if len(docstring) < min_length:
            self.warnings.append(f"Class '{node.name}' docstring too short " f"({len(docstring)} chars, minimum {min_length}, line {node.lineno})")

    def check_function_docstring(self, node: ast.FunctionDef) -> None:
        """Check if function has a docstring.

        Args:
            node: AST FunctionDef node.
        """
        if not is_public(node.name):
            return  # Skip private functions

        if not self.config.get("require_function_docstrings"):
            return

        docstring = ast.get_docstring(node)
        if not docstring:
            self.errors.append(f"Function '{node.name}' missing docstring (line {node.lineno})")
            return

        min_length = self.config.get("min_function_docstring_length", 15)
        if len(docstring) < min_length:
            self.warnings.append(f"Function '{node.name}' docstring too short " f"({len(docstring)} chars, minimum {min_length}, line {node.lineno})")

        # Check Google-style sections
        section_errors = check_google_style_sections(docstring, node, self.config)
        for error in section_errors:
            self.warnings.append(f"Function '{node.name}' (line {node.lineno}): {error}")


def should_skip_file(filepath: Path, config: dict) -> bool:
    """Check if file should be skipped based on exclude patterns.

    Args:
        filepath: Path to file.
        config: Configuration dictionary.

    Returns:
        True if file should be skipped.
    """
    exclude_patterns = config.get("exclude_patterns", [])

    for pattern in exclude_patterns:
        # Simple glob-like matching
        if pattern.endswith("/*"):
            if str(filepath).startswith(pattern[:-2]):
                return True
        elif pattern.startswith("*"):
            if str(filepath).endswith(pattern[1:]):
                return True
        elif pattern in str(filepath):
            return True

    return False


def main(args: List[str] = None) -> int:
    """Main entry point for docstring validation.

    Args:
        args: Command-line arguments (file paths).

    Returns:
        Exit code (0 = success, 1 = validation failures).
    """
    if args is None:
        args = sys.argv[1:]

    if not args:
        print("Usage: validate_docstrings.py file1.py file2.py ...")
        return 0

    # Load configuration
    config = load_config()

    # Validate each file
    all_success = True
    total_errors = 0
    total_warnings = 0

    for filepath_str in args:
        filepath = Path(filepath_str)

        if not filepath.exists():
            print(f"File not found: {filepath}")
            continue

        if should_skip_file(filepath, config):
            continue

        validator = DocstringValidator(filepath, config)
        success, errors, warnings = validator.validate()

        if errors:
            all_success = False
            total_errors += len(errors)
            print(f"\n{filepath}:")
            for error in errors:
                print(f"  ERROR: {error}")

        if warnings:
            total_warnings += len(warnings)
            if not config.get("strict_mode"):
                print(f"\n{filepath}:")
            for warning in warnings:
                if config.get("strict_mode"):
                    print(f"  ERROR: {warning}")
                    all_success = False
                else:
                    print(f"  WARNING: {warning}")

    # Summary
    if total_errors > 0 or (config.get("strict_mode") and total_warnings > 0):
        print(f"\nDocstring validation failed: {total_errors} errors, {total_warnings} warnings")
        return 1
    elif total_warnings > 0:
        print(f"\nDocstring validation passed with {total_warnings} warnings")
        return 0
    else:
        print("\nAll docstring validations passed!")
        return 0


if __name__ == "__main__":
    sys.exit(main())
