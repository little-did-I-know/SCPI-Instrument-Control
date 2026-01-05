#!/usr/bin/env python3
"""
Pre-PR Validation Script for Siglent-Oscilloscope

Run this script before creating a pull request to ensure all quality checks pass.
This will save time by catching issues locally before CI runs.

Usage:
    python scripts/pre_pr_check.py
    python scripts/pre_pr_check.py --fast    # Skip slow tests
    python scripts/pre_pr_check.py --fix     # Auto-fix issues where possible
"""

import argparse
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple

# Fix Windows console encoding for Unicode characters
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        import io

        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")


# Colors for terminal output
class Colors:
    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKCYAN = "\033[96m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"


def print_header(msg: str):
    """Print a section header."""
    print(f"\n{Colors.BOLD}{Colors.HEADER}{'=' * 70}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.HEADER}{msg}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.HEADER}{'=' * 70}{Colors.ENDC}\n")


def print_step(msg: str):
    """Print a step message."""
    print(f"{Colors.OKCYAN}▶ {msg}{Colors.ENDC}")


def print_success(msg: str):
    """Print a success message."""
    print(f"{Colors.OKGREEN}✓ {msg}{Colors.ENDC}")


def print_error(msg: str):
    """Print an error message."""
    print(f"{Colors.FAIL}✗ {msg}{Colors.ENDC}")


def print_warning(msg: str):
    """Print a warning message."""
    print(f"{Colors.WARNING}⚠ {msg}{Colors.ENDC}")


def run_command(cmd: List[str], check: bool = True, capture: bool = False) -> Tuple[bool, str]:
    """
    Run a command and return success status and output.

    Args:
        cmd: Command to run as list of strings
        check: Whether to check return code
        capture: Whether to capture output

    Returns:
        Tuple of (success, output)
    """
    try:
        if capture:
            result = subprocess.run(cmd, capture_output=True, text=True, check=check)
            return True, result.stdout
        else:
            subprocess.run(cmd, check=check)
            return True, ""
    except subprocess.CalledProcessError as e:
        if capture:
            return False, e.stdout if e.stdout else str(e)
        return False, str(e)
    except FileNotFoundError:
        return False, f"Command not found: {cmd[0]}"


def check_git_status() -> bool:
    """Check if there are uncommitted changes."""
    print_step("Checking git status...")
    success, output = run_command(["git", "status", "--porcelain"], capture=True)

    if not success:
        print_warning("Could not check git status (not a git repo?)")
        return True  # Don't fail on this

    if output.strip():
        print_warning("You have uncommitted changes:")
        print(output[:500])  # Show first 500 chars
        response = input("\nContinue anyway? [y/N]: ").lower()
        if response != "y":
            print_error("Aborted by user")
            return False
    else:
        print_success("No uncommitted changes")

    return True


def check_formatting(auto_fix: bool = False) -> bool:
    """Check code formatting with Black."""
    print_step("Checking code formatting (Black)...")

    if auto_fix:
        print("  Auto-fixing formatting issues...")
        success, _ = run_command(["black", "--line-length", "200", "siglent/", "tests/", "examples/"])
        if success:
            print_success("Code formatted successfully")
            return True
        else:
            print_error("Failed to format code")
            return False
    else:
        success, output = run_command(["black", "--check", "--line-length", "200", "siglent/", "tests/", "examples/"], check=False, capture=True)

        if success:
            print_success("All files properly formatted")
            return True
        else:
            print_error("Code formatting issues found")
            print_warning("  Run: black --line-length 200 siglent/ tests/ examples/")
            print_warning("  Or: python scripts/pre_pr_check.py --fix")
            return False


def check_imports(auto_fix: bool = False) -> bool:
    """Check import sorting with isort."""
    print_step("Checking import sorting (isort)...")

    if auto_fix:
        print("  Auto-fixing import order...")
        success, _ = run_command(["isort", "--profile", "black", "--line-length", "200", "siglent/", "tests/", "examples/"])
        if success:
            print_success("Imports sorted successfully")
            return True
        else:
            print_warning("isort not installed (pip install isort)")
            return True  # Don't fail on this
    else:
        success, _ = run_command(["isort", "--check-only", "--profile", "black", "--line-length", "200", "siglent/", "tests/", "examples/"], check=False)

        if success:
            print_success("Import order correct")
            return True
        else:
            print_warning("Import order issues found (run with --fix to auto-correct)")
            return True  # Don't fail on this, it's not critical


def check_linting() -> bool:
    """Check code quality with flake8."""
    print_step("Running linter (flake8)...")

    success, output = run_command(["flake8", "siglent/", "--max-line-length=200", "--extend-ignore=E203,W503"], check=False, capture=True)

    if success:
        print_success("No linting issues found")
        return True
    else:
        print_error("Linting issues found:")
        print(output[:1000])  # Show first 1000 chars
        return False


def check_security() -> bool:
    """Run security checks with bandit."""
    print_step("Running security checks (bandit)...")

    success, output = run_command(["bandit", "-r", "siglent/", "-ll"], check=False, capture=True)  # Low-low severity

    if success or "No issues identified" in output:
        print_success("No security issues found")
        return True
    else:
        print_warning("Security issues found (review output):")
        print(output[:1000])
        return True  # Don't fail on warnings


def check_exception_imports() -> bool:
    """Validate exception imports and backward compatibility."""
    print_step("Validating exception imports...")

    try:
        # Ensure we're importing from local development version, not installed package
        import sys
        from pathlib import Path

        # Add current directory to Python path (at the beginning to prioritize local code)
        project_root = Path.cwd()
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))

        # Clear any cached imports to force reload from local version
        if "siglent.exceptions" in sys.modules:
            del sys.modules["siglent.exceptions"]
        if "siglent" in sys.modules:
            del sys.modules["siglent"]

        # Test new exception names
        # Test backward compatibility aliases
        from siglent.exceptions import CommandError, ConnectionError, SiglentConnectionError, SiglentError, SiglentTimeoutError, TimeoutError

        # Verify they are the same class (aliases work)
        if ConnectionError is not SiglentConnectionError:
            print_error("Backward compatibility alias 'ConnectionError' is not SiglentConnectionError")
            return False

        if TimeoutError is not SiglentTimeoutError:
            print_error("Backward compatibility alias 'TimeoutError' is not SiglentTimeoutError")
            return False

        # Test top-level package imports
        from siglent import SiglentConnectionError as TopLevelConn
        from siglent import SiglentTimeoutError as TopLevelTimeout

        if TopLevelConn is not SiglentConnectionError:
            print_error("Top-level import of SiglentConnectionError failed")
            return False

        if TopLevelTimeout is not SiglentTimeoutError:
            print_error("Top-level import of SiglentTimeoutError failed")
            return False

        # Test exception inheritance
        if not issubclass(SiglentConnectionError, SiglentError):
            print_error("SiglentConnectionError is not a subclass of SiglentError")
            return False

        if not issubclass(SiglentTimeoutError, SiglentError):
            print_error("SiglentTimeoutError is not a subclass of SiglentError")
            return False

        print_success("Exception imports valid (new names + backward compatibility)")
        return True

    except ImportError as e:
        print_error(f"Failed to import exceptions: {e}")
        return False
    except Exception as e:
        print_error(f"Unexpected error validating exceptions: {e}")
        return False


def run_tests(fast_mode: bool = False) -> bool:
    """Run test suite."""
    print_step("Running tests...")

    cmd = ["pytest", "tests/", "-v"]

    if fast_mode:
        print("  (Fast mode: skipping slow tests)")
        cmd.extend(["-m", "not slow", "-x"])  # Stop on first failure

    success, _ = run_command(cmd, check=False)

    if success:
        print_success("All tests passed")
        return True
    else:
        print_error("Some tests failed")
        return False


def check_coverage(fast_mode: bool = False) -> bool:
    """Check test coverage."""
    if fast_mode:
        print_warning("Skipping coverage check in fast mode")
        return True

    print_step("Checking test coverage...")

    success, output = run_command(["pytest", "tests/", "--cov=siglent", "--cov-report=term-missing", "--cov-report=html", "-q"], check=False, capture=True)

    if success:
        # Extract coverage percentage
        for line in output.split("\n"):
            if "TOTAL" in line:
                print_success(f"Coverage check passed: {line.strip()}")
                break
        print(f"  HTML report: file://{Path.cwd()}/htmlcov/index.html")
        return True
    else:
        print_error("Coverage check failed")
        return False


def validate_build() -> bool:
    """Validate package can be built."""
    print_step("Validating package build...")

    # Clean old builds
    import shutil

    for dir_name in ["build", "dist", "*.egg-info"]:
        for path in Path(".").glob(dir_name):
            if path.is_dir():
                shutil.rmtree(path)

    # Build
    success, _ = run_command(["python", "-m", "build"], check=False)
    if not success:
        print_error("Build failed")
        return False

    # Check with twine
    success, _ = run_command(["twine", "check", "dist/*"], check=False)
    if success:
        print_success("Package builds correctly")
        return True
    else:
        print_error("Package validation failed")
        return False


def main():
    """Run all pre-PR checks."""
    parser = argparse.ArgumentParser(
        description="Run all pre-PR validation checks",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/pre_pr_check.py              # Run all checks
  python scripts/pre_pr_check.py --fast       # Skip slow tests
  python scripts/pre_pr_check.py --fix        # Auto-fix formatting
  python scripts/pre_pr_check.py --fast --fix # Fast mode with auto-fix
        """,
    )
    parser.add_argument("--fast", action="store_true", help="Skip slow checks (coverage, full test suite)")
    parser.add_argument("--fix", action="store_true", help="Automatically fix issues where possible (formatting, imports)")
    parser.add_argument("--skip-tests", action="store_true", help="Skip running tests (useful for quick formatting checks)")
    parser.add_argument("--no-git-check", action="store_true", help="Skip git status check")

    args = parser.parse_args()

    print_header("Pre-PR Validation Check")
    print(f"Fast mode: {args.fast}")
    print(f"Auto-fix: {args.fix}")

    # Track results
    checks = []

    # Run checks in order
    if not args.no_git_check:
        checks.append(("Git Status", check_git_status()))
    checks.append(("Exception Imports", check_exception_imports()))
    checks.append(("Code Formatting", check_formatting(args.fix)))
    checks.append(("Import Sorting", check_imports(args.fix)))
    checks.append(("Linting", check_linting()))
    checks.append(("Security", check_security()))

    if not args.skip_tests:
        checks.append(("Tests", run_tests(args.fast)))
        checks.append(("Coverage", check_coverage(args.fast)))

    if not args.fast:
        checks.append(("Package Build", validate_build()))

    # Print summary
    print_header("Summary")

    all_passed = True
    for check_name, passed in checks:
        if passed:
            print_success(f"{check_name:.<40} PASSED")
        else:
            print_error(f"{check_name:.<40} FAILED")
            all_passed = False

    print()
    if all_passed:
        print_success("All checks passed! Ready to create PR.")
        return 0
    else:
        print_error("Some checks failed. Please fix issues before creating PR.")
        print_warning("\nTips:")
        print("  - Run with --fix to auto-fix formatting issues")
        print("  - Run with --fast for quicker iteration")
        print("  - Check the output above for specific errors")
        return 1


if __name__ == "__main__":
    sys.exit(main())
