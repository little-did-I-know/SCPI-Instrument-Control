# Branding and Visual Assets

This document describes how the project's visual assets (logos, icons) are used across different platforms.

## Assets

- **Logo (PNG)**: `resources/Test Equipment.png` - Main project logo (795 KB)
- **Icon (ICO)**: `resources/Test Equipment.ico` - Windows icon format (17 KB)
- **Icon (ICNS)**: `resources/siglent-icon.icns` - macOS icon format (1.3 MB)

## Usage Across Platforms

### 📦 PyPI Package Page

The logo is automatically displayed on the PyPI project page through the README.md file.

**Location in README.md:**
```markdown
<div align="center">
  <img src="resources/Test Equipment.png" alt="Siglent Test Equipment Control" width="400">
</div>
```

When you publish to PyPI, this image will appear at the top of your project page.

**Verification:**
- Visit https://pypi.org/project/Siglent-Oscilloscope/
- The logo should appear at the top of the page

---

### 🐙 GitHub Repository

#### Social Preview Image (Repository Card)

The social preview image is what appears when your repository is shared on social media, GitHub search results, and repository lists.

**How to set it up:**

1. Go to your repository: https://github.com/little-did-I-know/SCPI-Instrument-Control
2. Click on **Settings** (⚙️ gear icon in the top menu)
3. Scroll down to the **Social preview** section
4. Click **Edit**
5. Click **Upload an image**
6. Upload `docs/images/social-preview.png`
7. Click **Save**

**Image Requirements:**
- ✅ Minimum size: 640×320px
- ✅ Maximum size: 2MB
- ✅ Recommended: 1280×640px (2:1 aspect ratio)
- ✅ `docs/images/social-preview.png`: 1280×640, 44 KB (purpose-built for this slot)

> Use `docs/images/social-preview.png`, not `resources/Test Equipment.png` — the
> latter is 1024×1024, so GitHub crops it to 2:1 and loses most of the image.
> The waveform on the card is a real capture from the built-in mock scope.
> Regenerate it with `python scripts/media/make_social_preview.py`.

**What it looks like:**
When someone shares your repo link, they'll see:
```
┌─────────────────────────────────────┐
│  [Your Test Equipment Logo Image]  │
├─────────────────────────────────────┤
│ Siglent-Oscilloscope                │
│ Python library for controlling...   │
└─────────────────────────────────────┘
```

#### README.md Display

The logo already appears at the top of your GitHub README automatically since we added it to the README.md file.

---

### 📚 Documentation (MkDocs)

The logo and favicon are configured in `mkdocs.yml`:

```yaml
theme:
  name: material
  logo: ../resources/Test Equipment.png
  favicon: ../resources/Test Equipment.ico
```

**Appears as:**
- **Logo**: In the navigation sidebar (top-left)
- **Favicon**: In browser tabs

**Build and preview:**
```bash
make docs
# Opens in browser at http://127.0.0.1:8000
```

The logo will appear in the sidebar, and the favicon will show in the browser tab.

---

### 🖥️ GUI Application

To use the icon in the PyQt6 GUI application, you can set it in the main window initialization.

**Example usage:**
```python
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication
import os

app = QApplication([])

# Set application icon
icon_path = os.path.join(os.path.dirname(__file__), '..', 'resources', 'Test Equipment.ico')
app.setWindowIcon(QIcon(icon_path))

# Or for a specific window
window.setWindowIcon(QIcon(icon_path))
```

This will make the icon appear:
- In the window title bar
- In the taskbar
- In the Alt+Tab switcher (Windows)
- In the Dock (macOS with .icns file)

---

## Distribution

The resources directory is automatically included in package distributions via `MANIFEST.in`:

```
# Include resources (logos, icons)
recursive-include resources *.png *.ico *.icns
```

This means when users install via `pip install Siglent-Oscilloscope`, they get the resources folder.

---

## Checklist

After updating branding assets:

- [x] ✅ Updated README.md with logo
- [x] ✅ Updated MANIFEST.in to include resources
- [x] ✅ Updated mkdocs.yml with logo and favicon
- [ ] ⏳ Set GitHub social preview image (requires manual web UI action)
- [ ] ⏳ (Optional) Update GUI application to use icon
- [ ] ⏳ Verify PyPI page displays logo after next release

---

## Notes

- **GitHub Social Preview**: Must be set manually through GitHub web UI (cannot be automated via git)
- **PyPI Logo**: Automatically sourced from README.md
- **Docs Logo**: Automatically built from mkdocs.yml
- **File Formats**:
  - PNG for web/documentation
  - ICO for Windows
  - ICNS for macOS
