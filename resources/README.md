# Application Icons

This directory contains icons for the Siglent Oscilloscope GUI application.

## Icon Files

The build process expects the following icon files:

- **Windows**: `siglent-icon.ico` (256x256 pixels, .ico format)
- **macOS**: `siglent-icon.icns` (multiple resolutions, .icns format)
- **Linux**: No specific icon file required (uses desktop integration)

## Creating Icons

### From Source Image

Start with a high-resolution square image (at least 1024x1024 px).

### Windows (.ico)

```bash
# Using ImageMagick
convert icon-source.png -define icon:auto-resize=256,128,64,48,32,16 siglent-icon.ico
```

### macOS (.icns)

```bash
# Create iconset and convert
mkdir siglent.iconset
sips -z 512 512 icon-source.png --out siglent.iconset/icon_512x512.png
iconutil -c icns siglent.iconset
mv siglent.icns siglent-icon.icns
```

## Current Status

Icons are currently missing. The build will work without them but executables will have default icons.
