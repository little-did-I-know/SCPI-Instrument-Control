# Quick Icon Setup Guide

## Where to Place Your Icons

Copy your icon files to these exact locations:

```
Siglent/
└── resources/
    ├── siglent-icon.ico     ← Your Windows icon (.ico format)
    └── siglent-icon.icns    ← Your macOS icon (.icns format)
```

## Commands to Copy Icons

### On Windows (Command Prompt)

```cmd
copy C:\path\to\your\windows-icon.ico resources\siglent-icon.ico
copy C:\path\to\your\macos-icon.icns resources\siglent-icon.icns
```

### On Windows (PowerShell)

```powershell
Copy-Item "C:\path\to\your\windows-icon.ico" -Destination "resources\siglent-icon.ico"
Copy-Item "C:\path\to\your\macos-icon.icns" -Destination "resources\siglent-icon.icns"
```

### On macOS/Linux

```bash
cp /path/to/your/windows-icon.ico resources/siglent-icon.ico
cp /path/to/your/macos-icon.icns resources/siglent-icon.icns
```

## Verify Icons Are in Place

```bash
# List files in resources directory
ls -la resources/

# Should show:
# siglent-icon.ico
# siglent-icon.icns
# README.md
```

## Then Commit to Git

```bash
git add resources/siglent-icon.ico
git add resources/siglent-icon.icns
git commit -m "Add application icons for executables"
git push
```

## That's It!

The build system will automatically use these icons when creating executables.

---

**Need help?** See `docs/development/BUILDING_EXECUTABLES.md` for more details.
