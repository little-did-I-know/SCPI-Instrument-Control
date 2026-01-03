# Resources Directory

This directory contains application resources for building standalone executables.

## Required Files for Executable Builds

### Application Icons

To add custom icons to your executables, create the following files:

- **`siglent-icon.ico`** - Windows application icon
  - Format: ICO (multi-resolution)
  - Recommended sizes: 16x16, 32x32, 48x48, 256x256

- **`siglent-icon.icns`** - macOS application icon
  - Format: ICNS (multi-resolution)
  - Recommended sizes: 16x16 to 1024x1024

### Creating Icons

See the full guide in `docs/development/BUILDING_EXECUTABLES.md` for detailed instructions.

**Quick method using online tools:**

1. Create a 1024x1024 PNG image with your icon design
2. Convert to .ico: https://convertio.co/png-ico/
3. Convert to .icns: https://cloudconvert.com/png-to-icns
4. Place the files in this directory

**The build will work without icons**, but the executable will use a generic Python icon instead.

## Current Status

This directory is currently empty. Icons are optional but recommended for professional appearance.

When you add icon files, the PyInstaller build will automatically include them in the executables.
