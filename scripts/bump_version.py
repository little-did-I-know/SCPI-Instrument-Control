#!/usr/bin/env python3
"""Version bumping script for Siglent-Oscilloscope package.

This script handles version bumping across the codebase:
- Updates pyproject.toml
- Updates siglent/__init__.py
- Updates CHANGELOG.md with new version header

Usage:
    python scripts/bump_version.py [--major | --minor | --patch]
    make version-bump  # Interactive mode
    make bump-major    # Bump major version
    make bump-minor    # Bump minor version
    make bump-patch    # Bump patch version
"""

import re
import sys
from datetime import date
from pathlib import Path
from typing import Optional, Tuple


def get_current_version(file_path: Path, pattern: str) -> Optional[str]:
    """Extract version string from a file using regex pattern."""
    try:
        content = file_path.read_text(encoding='utf-8')
        match = re.search(pattern, content, re.MULTILINE)
        if match:
            return match.group(1)
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
    return None


def parse_version(version_str: str) -> Tuple[int, int, int]:
    """Parse version string into (major, minor, patch) tuple."""
    match = re.match(r'^(\d+)\.(\d+)\.(\d+)$', version_str)
    if not match:
        raise ValueError(f"Invalid version format: {version_str}")
    return tuple(map(int, match.groups()))


def format_version(major: int, minor: int, patch: int) -> str:
    """Format version tuple as string."""
    return f"{major}.{minor}.{patch}"


def check_version_consistency() -> Optional[str]:
    """Check that all version numbers in the codebase match."""
    root_dir = Path(__file__).parent.parent

    # Check pyproject.toml
    pyproject_version = get_current_version(
        root_dir / "pyproject.toml",
        r'^version\s*=\s*"([^"]+)"'
    )

    # Check siglent/__init__.py
    init_version = get_current_version(
        root_dir / "siglent" / "__init__.py",
        r'^__version__\s*=\s*"([^"]+)"'
    )

    if not pyproject_version or not init_version:
        print("ERROR: Could not find version in required files")
        return None

    if pyproject_version != init_version:
        print(f"ERROR: Version mismatch detected!")
        print(f"  pyproject.toml: {pyproject_version}")
        print(f"  siglent/__init__.py: {init_version}")
        return None

    return pyproject_version


def validate_version_bump(old_ver: str, new_ver: str) -> bool:
    """Validate that version bump follows semantic versioning rules."""
    try:
        old_major, old_minor, old_patch = parse_version(old_ver)
        new_major, new_minor, new_patch = parse_version(new_ver)
    except ValueError as e:
        print(f"ERROR: {e}")
        return False

    # Count how many numbers changed
    changes = 0
    if new_major != old_major:
        changes += 1
    if new_minor != old_minor:
        changes += 1
    if new_patch != old_patch:
        changes += 1

    # Validate only one number changed
    if changes != 1:
        print(f"ERROR: You must increment exactly one version number")
        print(f"  Current: {old_ver}")
        print(f"  New: {new_ver}")
        print(f"  Changes: {changes} numbers changed")
        return False

    # Validate increment is forward
    if new_major < old_major:
        print(f"ERROR: Major version cannot decrease ({old_major} -> {new_major})")
        return False
    if new_major == old_major and new_minor < old_minor:
        print(f"ERROR: Minor version cannot decrease ({old_minor} -> {new_minor})")
        return False
    if new_major == old_major and new_minor == old_minor and new_patch < old_patch:
        print(f"ERROR: Patch version cannot decrease ({old_patch} -> {new_patch})")
        return False

    # Warn about unusual jumps
    if new_major > old_major:
        if new_major - old_major > 1:
            print(f"WARNING: Skipping major versions ({old_major} -> {new_major})")
            response = input("Continue anyway? (y/N): ").strip().lower()
            if response != 'y':
                return False
        # When bumping major, minor and patch should reset to 0
        if new_minor != 0 or new_patch != 0:
            print(f"WARNING: When bumping major version, minor and patch should be 0")
            print(f"  Suggested: {new_major}.0.0")
            response = input("Continue anyway? (y/N): ").strip().lower()
            if response != 'y':
                return False

    if new_minor > old_minor:
        if new_major != old_major:
            print(f"ERROR: Cannot bump both major and minor version")
            return False
        if new_minor - old_minor > 1:
            print(f"WARNING: Skipping minor versions ({old_minor} -> {new_minor})")
            response = input("Continue anyway? (y/N): ").strip().lower()
            if response != 'y':
                return False
        # When bumping minor, patch should reset to 0
        if new_patch != 0:
            print(f"WARNING: When bumping minor version, patch should be 0")
            print(f"  Suggested: {new_major}.{new_minor}.0")
            response = input("Continue anyway? (y/N): ").strip().lower()
            if response != 'y':
                return False

    if new_patch > old_patch:
        if new_major != old_major or new_minor != old_minor:
            print(f"ERROR: Cannot bump patch with major or minor changes")
            return False
        if new_patch - old_patch > 1:
            print(f"WARNING: Skipping patch versions ({old_patch} -> {new_patch})")
            response = input("Continue anyway? (y/N): ").strip().lower()
            if response != 'y':
                return False

    return True


def run_tests() -> bool:
    """Run test suite to ensure code quality before version bump."""
    import subprocess

    print("\nRunning test suite (excluding codecov)...")
    try:
        # Run pytest without codecov
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/", "-v"],
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )

        if result.returncode == 0:
            print("✓ All tests passed")
            return True
        else:
            print("✗ Tests failed:")
            print(result.stdout)
            print(result.stderr)
            return False
    except subprocess.TimeoutExpired:
        print("✗ Tests timed out after 5 minutes")
        return False
    except Exception as e:
        print(f"✗ Error running tests: {e}")
        return False


def update_file(file_path: Path, pattern: str, new_version: str) -> bool:
    """Update version in a file using regex pattern."""
    try:
        content = file_path.read_text(encoding='utf-8')

        # Replace version
        new_content = re.sub(
            pattern,
            lambda m: m.group(0).replace(m.group(1), new_version),
            content,
            flags=re.MULTILINE
        )

        if new_content == content:
            print(f"WARNING: No changes made to {file_path}")
            return False

        file_path.write_text(new_content, encoding='utf-8')
        print(f"✓ Updated {file_path}")
        return True
    except Exception as e:
        print(f"ERROR: Failed to update {file_path}: {e}")
        return False


def update_changelog(new_version: str) -> bool:
    """Add new version header to CHANGELOG.md."""
    root_dir = Path(__file__).parent.parent
    changelog_path = root_dir / "CHANGELOG.md"

    try:
        content = changelog_path.read_text(encoding='utf-8')

        # Find the [Unreleased] section
        unreleased_pattern = r'(## \[Unreleased\]\s*\n)'

        if not re.search(unreleased_pattern, content):
            print("ERROR: Could not find [Unreleased] section in CHANGELOG.md")
            return False

        # Create new version section
        today = date.today().isoformat()
        new_section = f"\n## [{new_version}] - {today}\n\n### Added\n\n### Changed\n\n### Fixed\n\n"

        # Insert new section after [Unreleased]
        new_content = re.sub(
            unreleased_pattern,
            r'\1' + new_section,
            content
        )

        changelog_path.write_text(new_content, encoding='utf-8')
        print(f"✓ Updated CHANGELOG.md with version {new_version}")
        return True
    except Exception as e:
        print(f"ERROR: Failed to update CHANGELOG.md: {e}")
        return False


def interactive_version_bump() -> Optional[str]:
    """Interactive mode to determine new version."""
    current_version = check_version_consistency()
    if not current_version:
        return None

    print(f"\nCurrent version: {current_version}")
    major, minor, patch = parse_version(current_version)

    # Ask about major version bump
    print(f"\nIs this a MAJOR release ({major}.X.X -> {major+1}.0.0)?")
    print("  (Breaking changes, incompatible API changes)")
    response = input("Bump major version? (y/N): ").strip().lower()
    if response == 'y':
        return format_version(major + 1, 0, 0)

    # Ask about minor version bump
    print(f"\nIs this a MINOR release ({major}.{minor}.X -> {major}.{minor+1}.0)?")
    print("  (New features, backward compatible)")
    response = input("Bump minor version? (y/N): ").strip().lower()
    if response == 'y':
        return format_version(major, minor + 1, 0)

    # Ask about patch version bump
    print(f"\nIs this a PATCH release ({major}.{minor}.{patch} -> {major}.{minor}.{patch+1})?")
    print("  (Bug fixes, backward compatible)")
    response = input("Bump patch version? (y/N): ").strip().lower()
    if response == 'y':
        return format_version(major, minor, patch + 1)

    # Ask for manual version input
    print(f"\nNo automatic bump selected.")
    print(f"Current version: {current_version}")
    while True:
        response = input("Enter new version (or 'q' to quit): ").strip()
        if response.lower() == 'q':
            return None

        # Validate format
        try:
            parse_version(response)
            return response
        except ValueError:
            print(f"Invalid version format: {response}")
            print("Version must be in format: MAJOR.MINOR.PATCH (e.g., 0.5.2)")


def main():
    """Main entry point for version bumping script."""
    root_dir = Path(__file__).parent.parent

    print("=" * 60)
    print("Siglent-Oscilloscope Version Bump Script")
    print("=" * 60)

    # Check for command-line arguments
    bump_type = None
    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()
        if arg in ['--major', '-M']:
            bump_type = 'major'
        elif arg in ['--minor', '-m']:
            bump_type = 'minor'
        elif arg in ['--patch', '-p']:
            bump_type = 'patch'
        else:
            print(f"Unknown argument: {sys.argv[1]}")
            print("Usage: bump_version.py [--major | --minor | --patch]")
            return 1

    # Step 1: Check version consistency
    print("\n[1/5] Checking version consistency...")
    current_version = check_version_consistency()
    if not current_version:
        return 1
    print(f"✓ All version numbers match: {current_version}")

    # Step 2: Run tests
    print("\n[2/5] Running test suite...")
    if not run_tests():
        print("\nERROR: Tests must pass before bumping version")
        response = input("Skip tests and continue anyway? (y/N): ").strip().lower()
        if response != 'y':
            return 1

    # Step 3: Determine new version
    print("\n[3/5] Determining new version...")
    if bump_type:
        major, minor, patch = parse_version(current_version)
        if bump_type == 'major':
            new_version = format_version(major + 1, 0, 0)
        elif bump_type == 'minor':
            new_version = format_version(major, minor + 1, 0)
        else:  # patch
            new_version = format_version(major, minor, patch + 1)
        print(f"Auto-bumping {bump_type} version: {current_version} -> {new_version}")
    else:
        new_version = interactive_version_bump()
        if not new_version:
            print("\nVersion bump cancelled.")
            return 0

    # Step 4: Validate version bump
    print("\n[4/5] Validating version bump...")
    if not validate_version_bump(current_version, new_version):
        return 1
    print(f"✓ Version bump validated: {current_version} -> {new_version}")

    # Step 5: Update files
    print("\n[5/5] Updating files...")

    # Confirm before making changes
    print(f"\nReady to bump version from {current_version} to {new_version}")
    print("This will update:")
    print("  - pyproject.toml")
    print("  - siglent/__init__.py")
    print("  - CHANGELOG.md")
    response = input("\nProceed with version bump? (y/N): ").strip().lower()
    if response != 'y':
        print("\nVersion bump cancelled.")
        return 0

    # Update pyproject.toml
    success = update_file(
        root_dir / "pyproject.toml",
        r'^version\s*=\s*"([^"]+)"',
        new_version
    )
    if not success:
        return 1

    # Update siglent/__init__.py
    success = update_file(
        root_dir / "siglent" / "__init__.py",
        r'^__version__\s*=\s*"([^"]+)"',
        new_version
    )
    if not success:
        return 1

    # Update CHANGELOG.md
    success = update_changelog(new_version)
    if not success:
        return 1

    print("\n" + "=" * 60)
    print(f"✓ Successfully bumped version to {new_version}")
    print("=" * 60)
    print("\nNext steps:")
    print(f"  1. Edit CHANGELOG.md to document changes for v{new_version}")
    print(f"  2. Review the changes: git diff")
    print(f"  3. Commit: git add -A && git commit -m 'Bump version to v{new_version}'")
    print(f"  4. Tag: git tag v{new_version}")
    print(f"  5. Push: git push origin <branch> --tags")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
