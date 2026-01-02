# Documentation Deployment

This guide explains how the documentation is automatically deployed to multiple platforms and how to set them up.

## Documentation Platforms

The project documentation is deployed to **two platforms** for redundancy and accessibility:

1. **ReadTheDocs** (Primary): https://siglent-oscilloscope.readthedocs.io
2. **GitHub Pages** (Secondary): https://little-did-I-know.github.io/Siglent-Oscilloscope/

Both platforms automatically build and deploy documentation when changes are pushed to the `main` branch.

## Platform Comparison

| Feature | ReadTheDocs | GitHub Pages |
|---------|-------------|--------------|
| **Auto-build** | ✅ Yes | ✅ Yes (via Actions) |
| **PDF Export** | ✅ Yes | ❌ No |
| **EPUB Export** | ✅ Yes | ❌ No |
| **Version Switching** | ✅ Yes | ⚠️ Manual setup |
| **Search** | ✅ Yes | ✅ Yes |
| **Custom Domain** | ✅ Yes | ✅ Yes |
| **Build Time** | ~2-3 min | ~2-3 min |
| **Reliability** | Very High | Very High |

## Setup Instructions

### 1. ReadTheDocs Setup (One-Time)

**Initial Setup:**

1. **Go to ReadTheDocs.org**
   - Visit https://readthedocs.org/
   - Click "Sign Up" or "Log In with GitHub"

2. **Import the Repository**
   - Click "Import a Project"
   - Select "little-did-I-know/Siglent-Oscilloscope"
   - Click "Import"

3. **Configure Build**
   - ReadTheDocs will automatically detect `.readthedocs.yml`
   - No additional configuration needed!

4. **Trigger First Build**
   - Click "Build Version"
   - Wait 2-3 minutes for the build to complete
   - Docs will be live at: https://siglent-oscilloscope.readthedocs.io

**Webhook Configuration (Optional):**

ReadTheDocs automatically creates a webhook in your GitHub repository. If it doesn't:

1. Go to GitHub repository → Settings → Webhooks
2. Click "Add webhook"
3. Payload URL: `https://readthedocs.org/api/v2/webhook/siglent-oscilloscope/<your-key>/`
4. Content type: `application/json`
5. Events: "Just the push event"

### 2. GitHub Pages Setup (One-Time)

**Enable GitHub Pages:**

1. **Go to Repository Settings**
   - Visit: https://github.com/little-did-I-know/Siglent-Oscilloscope/settings/pages

2. **Configure Source**
   - Source: **Deploy from a branch**
   - Branch: **gh-pages**
   - Folder: **/ (root)**

3. **Click Save**

4. **Wait for Deployment**
   - Push to `main` branch triggers the workflow
   - Check Actions tab for deployment status
   - Docs will be live at: https://little-did-I-know.github.io/Siglent-Oscilloscope/

**Verify Workflow:**

```bash
# Check if the workflow exists
ls .github/workflows/docs.yml

# View workflow status
# Go to: https://github.com/little-did-I-know/Siglent-Oscilloscope/actions
```

### 3. GitHub Repository About Section

**Configure the About section** (top right of repository page):

1. **Go to Repository Home Page**
   - Visit: https://github.com/little-did-I-know/Siglent-Oscilloscope

2. **Click the Gear Icon** (⚙️) next to "About"

3. **Fill in Details:**
   - **Description**: `Python library for controlling Siglent oscilloscopes via SCPI - Real-time GUI, FFT analysis, protocol decoding`
   - **Website**: `https://siglent-oscilloscope.readthedocs.io`
   - **Topics**: `python`, `oscilloscope`, `scpi`, `siglent`, `test-equipment`, `instrumentation`, `pyqt6`, `gui`, `automation`, `data-acquisition`
   - **☑️ Releases**
   - **☑️ Packages**

4. **Click "Save changes"**

## Automatic Deployment

### ReadTheDocs Auto-Build

**Triggers:**
- Push to `main` branch
- Push to any branch (builds PR preview)
- Manual build from ReadTheDocs dashboard

**Build Process:**
1. ReadTheDocs webhook receives push notification
2. Clones repository
3. Runs `mkdocs build` using `.readthedocs.yml` config
4. Generates PDF and EPUB downloads
5. Deploys to https://siglent-oscilloscope.readthedocs.io

**Configuration File:** `.readthedocs.yml`

```yaml
version: 2
build:
  os: ubuntu-22.04
  tools:
    python: "3.11"
mkdocs:
  configuration: mkdocs.yml
python:
  install:
    - method: pip
      path: .
      extra_requirements:
        - docs
formats:
  - pdf
  - epub
```

### GitHub Pages Auto-Deploy

**Triggers:**
- Push to `main` branch
- Manual trigger via Actions tab

**Workflow:** `.github/workflows/docs.yml`

**Build Process:**
1. Checkout repository
2. Install Python 3.11
3. Install dependencies: `pip install -e ".[docs]"`
4. Generate API docs: `make docs-generate`
5. Build site: `mkdocs build --clean --strict`
6. Deploy to `gh-pages` branch using `peaceiris/actions-gh-pages@v4`

**View Deployment:**
- Actions tab: https://github.com/little-did-I-know/Siglent-Oscilloscope/actions
- Deployments: https://github.com/little-did-I-know/Siglent-Oscilloscope/deployments

## Manual Deployment

### Local Build and Preview

```bash
# Install documentation dependencies
pip install -e ".[docs]"

# Generate API documentation from docstrings
make docs-generate

# Build documentation
make docs

# Open built site
# Linux/macOS: open site/index.html
# Windows: start site/index.html

# Or serve with live reload
make docs-serve
# Visit http://127.0.0.1:8000
```

### Force Rebuild

**ReadTheDocs:**
1. Go to https://readthedocs.org/projects/siglent-oscilloscope/
2. Click "Build Version"
3. Select "latest" or specific version
4. Click "Build"

**GitHub Pages:**
1. Go to Actions tab
2. Select "Deploy Documentation" workflow
3. Click "Run workflow"
4. Select `main` branch
5. Click "Run workflow"

## Troubleshooting

### ReadTheDocs Build Fails

**Check Build Log:**
1. Go to https://readthedocs.org/projects/siglent-oscilloscope/builds/
2. Click on failed build
3. View detailed logs

**Common Issues:**

| Error | Solution |
|-------|----------|
| `ImportError: No module named X` | Add dependency to `docs/requirements.txt` or `pyproject.toml [docs]` |
| `Configuration file not found` | Verify `.readthedocs.yml` exists in repo root |
| `MkDocs build failed` | Run `make docs` locally to reproduce error |
| `griffe warnings` | Add missing docstrings to Python source code (warnings are OK, errors are not) |

### GitHub Pages Build Fails

**Check Workflow Log:**
1. Go to Actions tab
2. Click on failed "Deploy Documentation" workflow
3. Expand failed step to see error

**Common Issues:**

| Error | Solution |
|-------|----------|
| `mkdocs: command not found` | Dependencies not installed - check workflow file |
| `Documentation for X not found` | Run `make docs-generate` first |
| `Permission denied` | Check workflow has `permissions: contents: write` |
| `gh-pages branch not found` | First deployment creates it automatically |

### Missing Documentation Updates

**If docs don't update after push:**

1. **Check that push went to `main` branch:**
   ```bash
   git branch
   git log --oneline -5
   ```

2. **Verify workflows triggered:**
   - ReadTheDocs: Check email or dashboard
   - GitHub Pages: Check Actions tab

3. **Clear browser cache:**
   - Hard refresh: Ctrl+Shift+R (Windows/Linux) or Cmd+Shift+R (Mac)
   - Or open in private/incognito window

4. **Check DNS propagation:**
   - GitHub Pages can take 10-20 minutes for first deployment

## Documentation Links

All documentation links are configured in multiple places for maximum accessibility:

### In `pyproject.toml`
```toml
[project.urls]
Documentation = "https://siglent-oscilloscope.readthedocs.io"
"Documentation (GitHub Pages)" = "https://little-did-I-know.github.io/Siglent-Oscilloscope/"
```

This shows both links on the PyPI package page.

### In `README.md`
```markdown
[![Documentation](https://img.shields.io/badge/docs-GitHub%20Pages-blue?logo=github)](https://little-did-I-know.github.io/Siglent-Oscilloscope/)
[![Documentation](https://img.shields.io/badge/docs-ReadTheDocs-blue?logo=readthedocs)](https://siglent-oscilloscope.readthedocs.io)
```

Both badges are displayed at the top of the README.

### In GitHub About Section
- Website field points to ReadTheDocs (primary)
- GitHub Pages accessible via badges in README

## Updating Documentation

### For Content Changes

1. **Edit markdown files in `docs/` directory**
   ```bash
   # Example: Update user guide
   edit docs/user-guide/basic-usage.md
   ```

2. **Preview changes locally:**
   ```bash
   make docs-serve
   # Visit http://127.0.0.1:8000
   ```

3. **Commit and push:**
   ```bash
   git add docs/
   git commit -m "docs: Update basic usage guide"
   git push origin main
   ```

4. **Wait 2-3 minutes** for automatic deployment to both platforms

### For API Documentation Changes

API documentation is **auto-generated** from Python docstrings using mkdocstrings.

1. **Edit docstrings in Python source:**
   ```python
   # Example: siglent/oscilloscope.py
   def get_waveform(self, channel: int) -> WaveformData:
       """Capture waveform data from specified channel.

       Args:
           channel: Channel number (1-4)

       Returns:
           WaveformData object with time and voltage arrays
       """
   ```

2. **Regenerate API stubs:**
   ```bash
   make docs-generate
   ```

3. **Preview and commit:**
   ```bash
   make docs-serve  # Preview changes
   git add siglent/ docs/api/
   git commit -m "docs: Improve get_waveform docstring"
   git push origin main
   ```

## Version Management

### ReadTheDocs Versions

ReadTheDocs automatically tracks versions from git tags:

```bash
# Create a release tag
git tag v0.3.1
git push origin v0.3.1

# ReadTheDocs will automatically build docs for this version
# Accessible at: https://siglent-oscilloscope.readthedocs.io/en/v0.3.1/
```

### GitHub Pages Versions

GitHub Pages only shows latest `main` branch by default. For version management, use:

```bash
# Manual approach using mike (optional)
pip install mike
mike deploy --push 0.3.1 latest
mike set-default --push latest
```

## Monitoring

### Build Status

**ReadTheDocs:**
- Build status: https://readthedocs.org/projects/siglent-oscilloscope/builds/
- Email notifications on build failures

**GitHub Pages:**
- Actions tab: https://github.com/little-did-I-know/Siglent-Oscilloscope/actions
- Status badge in README shows deployment status

### Analytics

**ReadTheDocs:**
- Built-in analytics dashboard
- View page views, popular pages, search queries

**GitHub Pages:**
- Set up Google Analytics (optional)
- Or use GitHub Insights → Traffic

## Next Steps

- [Building Documentation](building.md#documentation) - Local build instructions
- [Contributing Documentation](contributing.md#updating-documentation) - Documentation style guide
- [Project Structure](structure.md) - Documentation file organization
