# Testing the Executable Build Workflow

This guide walks you through testing the executable build system both locally and via GitHub Actions.

## Pre-Flight Checklist

Before testing, run the automated test script:

```bash
python scripts/test_build_system.py
```

This checks:
- ✅ All required files exist
- ✅ Icons are present (optional but recommended)
- ✅ Dependencies are installed
- ✅ PyInstaller spec file is valid
- ✅ GitHub Actions workflow is configured
- ✅ Git repository is clean

Fix any issues reported before proceeding.

## Test Plan Overview

1. **Local Build Test** - Build on your machine first
2. **Test Tag Release** - Test GitHub Actions with a test tag
3. **Verify Artifacts** - Check that executables work
4. **Official Release** - Create real release if tests pass

---

## 1️⃣ Local Build Test

### Step 1: Install Build Dependencies

```bash
# Install PyInstaller
pip install ".[build-exe]"

# Or install everything
pip install ".[all,build-exe]"
```

### Step 2: Run Pre-Flight Test

```bash
python scripts/test_build_system.py
```

Expected output:
```
✓ Project Structure: PASS
✓ Icons: PASS
✓ Spec File: PASS
✓ Dependencies: PASS
✓ Entry Point: PASS
✓ Workflow: PASS
✓ Version: PASS
✓ Git Status: PASS

Results: 8/8 checks passed
```

### Step 3: Build Locally

```bash
# Clean and build
make build-exe
```

This will:
1. Clean previous builds
2. Install PyInstaller if needed
3. Run PyInstaller with `siglent-gui.spec`
4. Create executable in `dist/`

**Expected time:** 2-5 minutes

**Expected output:**
```
Building standalone executable for current platform...
Target: SiglentGUI.exe (or .app on macOS, binary on Linux)

Running: python -m PyInstaller --clean siglent-gui.spec
...
✓ Build complete!
  Executable location: dist/
```

### Step 4: Verify the Executable

**Check the file exists:**

```bash
# Windows
ls dist/SiglentGUI.exe

# macOS
ls -la dist/SiglentGUI.app

# Linux
ls -la dist/SiglentGUI
```

**Check file size:**

Typical sizes: 100-300 MB

```bash
# Windows (PowerShell)
(Get-Item dist/SiglentGUI.exe).length / 1MB

# macOS/Linux
du -h dist/SiglentGUI*
```

### Step 5: Test the Executable

**Run the executable:**

```bash
# Windows (Command Prompt)
dist\SiglentGUI.exe

# Windows (PowerShell)
.\dist\SiglentGUI.exe

# macOS
open dist/SiglentGUI.app

# Linux
./dist/SiglentGUI
```

**What to test:**
- [ ] Application launches without errors
- [ ] GUI window appears
- [ ] Main window UI loads correctly
- [ ] Can attempt connection (even without scope connected)
- [ ] Menus and tabs are accessible
- [ ] Application closes cleanly

**Check the console output** for any errors or warnings.

### Step 6: Test Icon Display

**Windows:**
- Right-click `SiglentGUI.exe` → Properties
- Check if custom icon appears in file properties
- Check taskbar icon when running

**macOS:**
- Check Finder icon
- Check Dock icon when running

**Linux:**
- Icons typically not embedded in binary
- Check if it runs without icon-related errors

---

## 2️⃣ GitHub Actions Test

Once local build works, test the automated workflow.

### Step 1: Commit Icon Files

```bash
# Make sure your icons are in place
ls resources/siglent-icon.*

# Add them to git
git add resources/siglent-icon.ico
git add resources/siglent-icon.icns
git commit -m "Add application icons for executables"
```

### Step 2: Create a Test Tag

Use a `-test` suffix to distinguish from real releases:

```bash
# Create test tag (matching your current version)
git tag v0.3.1-test

# Push the tag
git push origin v0.3.1-test
```

⚠️ **Note:** The workflow triggers on `v*.*.*` tags, so `v0.3.1-test` will work.

### Step 3: Monitor GitHub Actions

1. Go to your GitHub repository
2. Click the **Actions** tab
3. You should see a new workflow run: "Build Standalone Executables"
4. Click on it to watch progress

**Expected jobs:**
- `build-windows` (~5-10 min)
- `build-macos` (~5-10 min)
- `build-linux` (~5-10 min)
- `create-release-notes` (~1 min)

**Total time:** ~10-15 minutes

### Step 4: Check Build Logs

Click on each job to see the build logs:

**What to look for:**
- ✅ Dependencies install successfully
- ✅ PyInstaller runs without errors
- ✅ Executable is created
- ✅ Archive is created (ZIP or tar.gz)
- ✅ Upload to release succeeds

**Common issues:**
- Missing dependencies → Check `pyproject.toml`
- PyInstaller errors → Check `siglent-gui.spec`
- Upload fails → Check repository permissions

### Step 5: Download Artifacts

Once builds complete:

1. Go to the workflow run page
2. Scroll to **Artifacts** section
3. Download each artifact:
   - `windows-executable`
   - `macos-executable`
   - `linux-executable`

**Or download from Releases:**

1. Go to **Releases** tab
2. Find your test release (`v0.3.1-test`)
3. Download the attachments:
   - `SiglentGUI-v0.3.1-test-Windows-x64.zip`
   - `SiglentGUI-v0.3.1-test-macOS-arm64.zip`
   - `SiglentGUI-v0.3.1-test-Linux-x86_64.tar.gz`

---

## 3️⃣ Verify Downloaded Executables

### Windows Testing

```powershell
# Extract ZIP
Expand-Archive -Path SiglentGUI-v0.3.1-test-Windows-x64.zip -DestinationPath test-windows

# Run executable
cd test-windows
.\SiglentGUI.exe
```

**Test checklist:**
- [ ] Extracts without errors
- [ ] Executable runs
- [ ] No Python installation required
- [ ] Custom icon displays
- [ ] GUI loads completely

### macOS Testing

```bash
# Extract ZIP
unzip SiglentGUI-v0.3.1-test-macOS-arm64.zip

# Try to open (may get security warning)
open SiglentGUI.app
```

**If you get "App can't be opened" error:**
1. Right-click → Open
2. Click "Open" in the dialog
3. macOS will remember this choice

**Test checklist:**
- [ ] Extracts without errors
- [ ] Can open .app bundle
- [ ] No Python installation required
- [ ] Custom icon displays
- [ ] GUI loads completely

### Linux Testing

```bash
# Extract tar.gz
tar -xzf SiglentGUI-v0.3.1-test-Linux-x86_64.tar.gz

# Make executable (if needed)
chmod +x SiglentGUI

# Run
./SiglentGUI
```

**Test checklist:**
- [ ] Extracts without errors
- [ ] Executable runs
- [ ] No Python installation required
- [ ] GUI loads completely

---

## 4️⃣ Clean Up Test Release

After testing, you can delete the test release:

1. Go to **Releases** tab
2. Find `v0.3.1-test`
3. Click **Delete** (trash icon)

**Delete the test tag:**

```bash
# Delete local tag
git tag -d v0.3.1-test

# Delete remote tag
git push origin :refs/tags/v0.3.1-test
```

---

## 5️⃣ Create Official Release

Once everything works:

### Step 1: Update Version (if needed)

Edit `pyproject.toml`:
```toml
version = "0.3.2"  # or whatever your next version is
```

Commit:
```bash
git add pyproject.toml
git commit -m "Bump version to 0.3.2"
git push origin main
```

### Step 2: Create Release Tag

```bash
# Create official tag (no -test suffix)
git tag v0.3.2

# Push tag
git push origin v0.3.2
```

### Step 3: Monitor and Verify

Same as test release, but this time:
- Release will be public
- Users can download immediately
- Consider making release notes more detailed

---

## Troubleshooting

### Build Fails Locally

**Error:** `PyInstaller: command not found`

**Fix:**
```bash
pip install pyinstaller
```

---

**Error:** `No module named 'PyQt6'`

**Fix:**
```bash
pip install ".[all]"
```

---

**Error:** `Icon file not found`

**Fix:**
- Icons are optional
- If you have icons, verify paths in `siglent-gui.spec`
- If not, remove icon references from spec file

---

### GitHub Actions Fails

**Error:** Workflow doesn't trigger

**Check:**
- Tag format must match `v*.*.*` (e.g., `v0.3.1`, not `0.3.1`)
- Workflow file is in `.github/workflows/`
- You pushed the tag: `git push origin v0.3.1`

---

**Error:** `Permission denied` when uploading to release

**Fix:**
- Check repository settings → Actions → General
- Enable "Read and write permissions" for GITHUB_TOKEN

---

**Error:** PyInstaller fails in workflow

**Check:**
- Compare local build to CI build logs
- Ensure all dependencies are in `pyproject.toml`
- Check `hiddenimports` in `siglent-gui.spec`

---

### Executable Won't Run

**Error:** Windows: "Missing DLL" or crashes silently

**Fix:**
- Run from Command Prompt to see error messages
- Check if antivirus is blocking (common with PyInstaller)
- Rebuild with `--debug all` flag for verbose output

---

**Error:** macOS: "App is damaged"

**Fix:**
- This is normal for unsigned apps
- Tell users to: Right-click → Open (first time only)
- For production, consider code signing

---

**Error:** Linux: "Permission denied"

**Fix:**
```bash
chmod +x SiglentGUI
```

---

## Testing Checklist

Use this checklist for each release:

### Pre-Release Testing
- [ ] Run `python scripts/test_build_system.py` - all checks pass
- [ ] Icons are in `resources/` directory
- [ ] Local build succeeds (`make build-exe`)
- [ ] Local executable runs and GUI works
- [ ] Git repository is clean (or changes committed)
- [ ] Version number updated in `pyproject.toml`

### Test Release
- [ ] Create test tag (e.g., `v0.3.1-test`)
- [ ] GitHub Actions workflow triggers
- [ ] All three platform builds succeed
- [ ] Executables uploaded to release
- [ ] Download and test each platform
- [ ] Delete test release when done

### Official Release
- [ ] Create official tag (e.g., `v0.3.2`)
- [ ] Monitor workflow completion
- [ ] Download and quick-test each platform
- [ ] Release notes are clear and helpful
- [ ] Update README with download links

### Post-Release
- [ ] Test downloads from public release page
- [ ] Verify file sizes are reasonable (100-300 MB)
- [ ] Check that custom icons display
- [ ] Consider announcing release

---

## Additional Testing Ideas

### Test on Clean VM

For thorough testing, use a clean virtual machine:

**Windows:**
- VirtualBox with fresh Windows 10/11 install
- Download and run executable
- Verify no Python needed

**macOS:**
- Fresh macOS VM (requires macOS host)
- Test with and without Homebrew
- Verify no Python needed

**Linux:**
- Ubuntu/Debian/Fedora VM
- Test on minimal installation
- Verify dependencies are bundled

### Test with Real Oscilloscope

If you have hardware:
- [ ] Connect to actual SDS5000X oscilloscope
- [ ] Test waveform capture
- [ ] Test all GUI features
- [ ] Verify measurements work
- [ ] Test protocol decoding

### Performance Testing

- [ ] Measure startup time (should be 2-5 seconds)
- [ ] Check memory usage
- [ ] Verify GUI responsiveness
- [ ] Test with large waveform captures

---

## Getting Help

If you encounter issues during testing:

1. Check the build logs in GitHub Actions
2. Review `docs/development/BUILDING_EXECUTABLES.md`
3. Search [PyInstaller documentation](https://pyinstaller.org/)
4. Create an issue with:
   - Your OS and Python version
   - Full error message
   - Build logs (if from GitHub Actions)
   - Steps to reproduce

---

## Success Criteria

Your build system is working correctly if:

✅ Local build creates working executable
✅ GitHub Actions builds all three platforms
✅ Executables run without Python installed
✅ Custom icons display correctly
✅ GUI launches and all features work
✅ File sizes are reasonable (100-300 MB)
✅ Users can download and run immediately

Congratulations! Your build system is ready for production releases! 🎉
