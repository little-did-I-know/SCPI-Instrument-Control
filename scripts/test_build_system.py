#!/usr/bin/env python3
"""Test script to verify the executable build system.

This script performs pre-flight checks before attempting a build.
Run this before pushing a release tag to ensure everything is ready.

Usage:
    python scripts/test_build_system.py
"""

import sys
import os
from pathlib import Path

# Fix Windows console encoding for Unicode characters
if sys.platform == 'win32':
    try:
        import codecs
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass  # If it fails, we'll fall back to ASCII symbols


class Color:
    """ANSI color codes for terminal output."""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'


def print_header(text):
    """Print a section header."""
    print(f"\n{Color.BOLD}{Color.BLUE}{'='*70}{Color.END}")
    print(f"{Color.BOLD}{Color.BLUE}{text}{Color.END}")
    print(f"{Color.BOLD}{Color.BLUE}{'='*70}{Color.END}\n")


def print_success(text):
    """Print a success message."""
    try:
        print(f"{Color.GREEN}\u2713 {text}{Color.END}")
    except UnicodeEncodeError:
        print(f"{Color.GREEN}[OK] {text}{Color.END}")


def print_error(text):
    """Print an error message."""
    try:
        print(f"{Color.RED}\u2717 {text}{Color.END}")
    except UnicodeEncodeError:
        print(f"{Color.RED}[ERROR] {text}{Color.END}")


def print_warning(text):
    """Print a warning message."""
    try:
        print(f"{Color.YELLOW}\u26a0 {text}{Color.END}")
    except UnicodeEncodeError:
        print(f"{Color.YELLOW}[WARN] {text}{Color.END}")


def print_info(text):
    """Print an info message."""
    print(f"  {text}")


def check_project_structure():
    """Verify required files and directories exist."""
    print_header("Checking Project Structure")

    required_files = [
        "pyproject.toml",
        "siglent-gui.spec",
        ".github/workflows/build-executables.yml",
        "scripts/build_executable.py",
        "Makefile",
        "README.md",
        "LICENSE",
    ]

    required_dirs = [
        "siglent/gui",
        "resources",
        ".github/workflows",
    ]

    all_good = True

    for file_path in required_files:
        path = Path(file_path)
        if path.exists():
            print_success(f"Found: {file_path}")
        else:
            print_error(f"Missing: {file_path}")
            all_good = False

    for dir_path in required_dirs:
        path = Path(dir_path)
        if path.is_dir():
            print_success(f"Found: {dir_path}/")
        else:
            print_error(f"Missing: {dir_path}/")
            all_good = False

    return all_good


def check_icons():
    """Check if application icons are present."""
    print_header("Checking Application Icons")

    icons = {
        "resources/siglent-icon.ico": "Windows icon",
        "resources/siglent-icon.icns": "macOS icon",
    }

    has_icons = False

    for icon_path, description in icons.items():
        path = Path(icon_path)
        if path.exists():
            size_kb = path.stat().st_size / 1024
            print_success(f"{description}: {icon_path} ({size_kb:.1f} KB)")
            has_icons = True
        else:
            print_warning(f"{description}: {icon_path} (not found - will use default)")

    if not has_icons:
        print_warning("No custom icons found. Executables will use generic Python icon.")
        print_info("See docs/development/BUILDING_EXECUTABLES.md for icon creation guide")

    return True  # Icons are optional, so always return True


def check_spec_file():
    """Verify PyInstaller spec file is valid."""
    print_header("Checking PyInstaller Spec File")

    spec_file = Path("siglent-gui.spec")

    if not spec_file.exists():
        print_error("siglent-gui.spec not found!")
        return False

    content = spec_file.read_text(encoding='utf-8')

    # Check for key components
    checks = {
        "Analysis(": "Analysis configuration",
        "EXE(": "EXE configuration",
        "siglent/gui/app.py": "Entry point script",
        "hiddenimports": "Hidden imports list",
    }

    all_good = True

    for pattern, description in checks.items():
        if pattern in content:
            print_success(f"Contains {description}")
        else:
            print_error(f"Missing {description}")
            all_good = False

    # Check icon references
    if "resources/siglent-icon" in content:
        print_success("Icon configuration found")
    else:
        print_warning("No icon configuration (icons are optional)")

    return all_good


def check_dependencies():
    """Check if required Python packages are installed."""
    print_header("Checking Python Dependencies")

    required_packages = {
        "PyQt6": "GUI framework",
        "numpy": "Numerical computing",
        "matplotlib": "Plotting",
        "scipy": "Scientific computing",
        "pyqtgraph": "High-performance plotting",
    }

    build_packages = {
        "PyInstaller": "Executable builder (optional - can install on demand)",
    }

    all_good = True

    print_info("Runtime dependencies:")
    for package, description in required_packages.items():
        try:
            __import__(package)
            print_success(f"{package}: {description}")
        except ImportError:
            print_error(f"{package}: {description} - NOT INSTALLED")
            all_good = False

    print_info("\nBuild tools:")
    for package, description in build_packages.items():
        try:
            __import__(package)
            print_success(f"{package}: {description}")
        except ImportError:
            print_warning(f"{package}: {description} - NOT INSTALLED")
            print_info(f"  Install with: pip install {package.lower()}")

    return all_good


def check_entry_point():
    """Verify the GUI entry point exists and is importable."""
    print_header("Checking GUI Entry Point")

    entry_script = Path("siglent/gui/app.py")

    if not entry_script.exists():
        print_error(f"Entry point not found: {entry_script}")
        return False

    print_success(f"Entry point exists: {entry_script}")

    # Check if the main function exists
    content = entry_script.read_text(encoding='utf-8')

    if "def main(" in content:
        print_success("Found main() function")
    else:
        print_error("No main() function found in app.py")
        return False

    # Try to import (may fail without dependencies)
    try:
        sys.path.insert(0, str(Path.cwd()))
        from siglent.gui import app
        print_success("Successfully imported siglent.gui.app")

        if hasattr(app, 'main'):
            print_success("main() function is accessible")
        else:
            print_error("main() function not found in module")
            return False

    except ImportError as e:
        print_warning(f"Could not import (may need dependencies): {e}")
        print_info("This is OK if dependencies aren't installed yet")

    return True


def check_workflow_file():
    """Verify GitHub Actions workflow is valid."""
    print_header("Checking GitHub Actions Workflow")

    workflow_file = Path(".github/workflows/build-executables.yml")

    if not workflow_file.exists():
        print_error("Workflow file not found!")
        return False

    print_success(f"Workflow file exists: {workflow_file}")

    content = workflow_file.read_text(encoding='utf-8')

    # Check for required jobs
    required_jobs = [
        "build-windows",
        "build-macos",
        "build-linux",
    ]

    all_good = True

    for job in required_jobs:
        if f"job: {job}" in content or f"{job}:" in content:
            print_success(f"Found job: {job}")
        else:
            print_error(f"Missing job: {job}")
            all_good = False

    # Check for trigger configuration
    if "tags:" in content and "v*.*.*" in content:
        print_success("Configured to trigger on version tags (v*.*.*)")
    else:
        print_warning("Tag trigger may not be configured correctly")

    if "workflow_dispatch" in content:
        print_success("Manual trigger enabled")
    else:
        print_warning("Manual trigger not enabled")

    return all_good


def check_version():
    """Check version in pyproject.toml."""
    print_header("Checking Version Information")

    pyproject = Path("pyproject.toml")

    if not pyproject.exists():
        print_error("pyproject.toml not found!")
        return False

    content = pyproject.read_text(encoding='utf-8')

    # Extract version
    for line in content.split('\n'):
        if line.strip().startswith('version'):
            version = line.split('=')[1].strip().strip('"').strip("'")
            print_success(f"Current version: {version}")

            # Check if it looks like a valid version
            parts = version.split('.')
            if len(parts) >= 2 and all(p.isdigit() for p in parts[:2]):
                print_success("Version format looks valid")
            else:
                print_warning(f"Version format may be unusual: {version}")

            return True

    print_error("Could not find version in pyproject.toml")
    return False


def check_git_status():
    """Check git repository status."""
    print_header("Checking Git Repository")

    import subprocess

    # Check if we're in a git repo
    try:
        subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            check=True,
            capture_output=True,
            text=True
        )
        print_success("Git repository detected")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print_error("Not in a git repository!")
        return False

    # Check for uncommitted changes
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            check=True,
            capture_output=True,
            text=True
        )

        if result.stdout.strip():
            print_warning("Uncommitted changes detected:")
            for line in result.stdout.strip().split('\n')[:5]:
                print_info(f"  {line}")
            if len(result.stdout.strip().split('\n')) > 5:
                print_info("  ...")
            print_info("Consider committing before creating a release tag")
        else:
            print_success("No uncommitted changes")
    except subprocess.CalledProcessError:
        print_warning("Could not check git status")

    # Check current branch
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            check=True,
            capture_output=True,
            text=True
        )
        branch = result.stdout.strip()
        print_success(f"Current branch: {branch}")

        if branch != "main" and branch != "master":
            print_warning(f"Not on main/master branch. Currently on: {branch}")
    except subprocess.CalledProcessError:
        print_warning("Could not determine current branch")

    return True


def print_next_steps():
    """Print instructions for next steps."""
    print_header("Next Steps")

    print_info("To test the build system locally:")
    print(f"  {Color.BOLD}make build-exe{Color.END}")
    print()

    print_info("To create a test release:")
    print(f"  {Color.BOLD}git add .{Color.END}")
    print(f"  {Color.BOLD}git commit -m 'Test executable build'{Color.END}")
    print(f"  {Color.BOLD}git tag v0.3.2-test{Color.END}")
    print(f"  {Color.BOLD}git push origin main{Color.END}")
    print(f"  {Color.BOLD}git push origin v0.3.2-test{Color.END}")
    print()

    print_info("To create an official release:")
    print(f"  {Color.BOLD}git tag v0.3.2{Color.END}")
    print(f"  {Color.BOLD}git push origin v0.3.2{Color.END}")
    print()

    print_info("Monitor the build:")
    print(f"  Check GitHub Actions tab in your repository")
    print()


def main():
    """Run all checks."""
    print(f"\n{Color.BOLD}Siglent Oscilloscope - Build System Test{Color.END}")
    print(f"{Color.BOLD}{'='*70}{Color.END}\n")

    results = {
        "Project Structure": check_project_structure(),
        "Icons": check_icons(),
        "Spec File": check_spec_file(),
        "Dependencies": check_dependencies(),
        "Entry Point": check_entry_point(),
        "Workflow": check_workflow_file(),
        "Version": check_version(),
        "Git Status": check_git_status(),
    }

    # Summary
    print_header("Test Summary")

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for test_name, result in results.items():
        if result:
            print_success(f"{test_name}: PASS")
        else:
            print_error(f"{test_name}: FAIL")

    print(f"\n{Color.BOLD}Results: {passed}/{total} checks passed{Color.END}\n")

    if passed == total:
        print_success("All checks passed! Build system is ready.")
        print_next_steps()
        return 0
    else:
        print_error(f"{total - passed} check(s) failed. Fix issues before building.")
        print_info("\nSee docs/development/BUILDING_EXECUTABLES.md for help")
        return 1


if __name__ == "__main__":
    sys.exit(main())
