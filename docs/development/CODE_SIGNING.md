# Code Signing for Executables

This guide explains how to set up code signing for the Siglent Oscilloscope GUI executables.

## Why Code Signing?

Code signing provides:

- **User trust**: Users know the software comes from you
- **Security**: Prevents "Unknown developer" warnings
- **macOS Gatekeeper**: Required for easy installation on macOS
- **Windows SmartScreen**: Reduces security warnings

## Current Status

**Code signing is NOT currently enabled.** Users will see warnings when running executables:

- **Windows**: "Windows protected your PC" SmartScreen warning
- **macOS**: "App is from an unidentified developer"
- **Linux**: No warnings (Linux doesn't require code signing)

## Workarounds for Users

### macOS

Right-click app → "Open" → Confirm opening unsigned app

### Windows

Click "More info" → "Run anyway"

## Setting Up Code Signing (Optional)

### macOS Code Signing

**Requirements:**

- Apple Developer Account ($99/year)
- Developer ID Application certificate

**Steps:**

1. **Get Certificate:**
   - Join Apple Developer Program
   - Request "Developer ID Application" certificate
   - Download and install in Keychain

2. **Update PyInstaller spec:**

```python
# siglent-gui.spec
exe = EXE(
    # ... existing options ...
    codesign_identity='Developer ID Application: Your Name (TEAMID)',
)
```

3. **Add to GitHub Secrets:**
   - `MACOS_CERTIFICATE`: Base64-encoded .p12 certificate
   - `MACOS_CERTIFICATE_PASSWORD`: Certificate password

4. **Update Workflow:**

```yaml
- name: Import Code Signing Certificate
  env:
    CERTIFICATE_BASE64: ${{ secrets.MACOS_CERTIFICATE }}
    CERTIFICATE_PASSWORD: ${{ secrets.MACOS_CERTIFICATE_PASSWORD }}
  run: |
    echo $CERTIFICATE_BASE64 | base64 --decode > certificate.p12
    security create-keychain -p actions build.keychain
    security default-keychain -s build.keychain
    security unlock-keychain -p actions build.keychain
    security import certificate.p12 -k build.keychain -P $CERTIFICATE_PASSWORD -T /usr/bin/codesign
    security set-key-partition-list -S apple-tool:,apple:,codesign: -s -k actions build.keychain

- name: Build and Sign
  run: pyinstaller --clean siglent-gui.spec

- name: Notarize (Optional but recommended)
  env:
    APPLE_ID: ${{ secrets.APPLE_ID }}
    APPLE_PASSWORD: ${{ secrets.APPLE_APP_PASSWORD }}
  run: |
    xcrun notarytool submit dist/SiglentGUI.app --apple-id $APPLE_ID --password $APPLE_PASSWORD --wait
    xcrun stapler staple dist/SiglentGUI.app
```

### Windows Code Signing

**Requirements:**

- Code signing certificate from a trusted CA (DigiCert, Sectigo, etc.)
- Costs $100-400/year

**Steps:**

1. **Get Certificate:**
   - Purchase from CA (DigiCert, Sectigo, SSL.com)
   - Obtain .pfx file and password

2. **Add to GitHub Secrets:**
   - `WINDOWS_CERTIFICATE`: Base64-encoded .pfx
   - `WINDOWS_CERTIFICATE_PASSWORD`: Certificate password

3. **Update Workflow:**

```yaml
- name: Sign Windows Executable
  env:
    CERTIFICATE_BASE64: ${{ secrets.WINDOWS_CERTIFICATE }}
    CERTIFICATE_PASSWORD: ${{ secrets.WINDOWS_CERTIFICATE_PASSWORD }}
  shell: powershell
  run: |
    $cert_path = "certificate.pfx"
    $bytes = [Convert]::FromBase64String($env:CERTIFICATE_BASE64)
    [IO.File]::WriteAllBytes($cert_path, $bytes)

    & "C:\Program Files (x86)\Windows Kits\10\bin\10.0.19041.0\x64\signtool.exe" sign `
      /f $cert_path `
      /p $env:CERTIFICATE_PASSWORD `
      /tr http://timestamp.digicert.com `
      /td sha256 `
      /fd sha256 `
      dist\SiglentGUI.exe

    Remove-Item $cert_path
```

### Linux

Linux doesn't require code signing. Package signing is done at the repository level (for .deb, .rpm, etc.).

## Free Alternatives

### Self-Signed Certificates (Development Only)

Not recommended for distribution - users will still see warnings.

### Open Source Certificate (Limited)

- SignPath.io offers free signing for open source projects
- Application required, not instant

## Recommendations

**For Open Source Projects:**

1. **Start without signing** - Document the warnings in README
2. **Build reputation** - Users will trust after a while
3. **Consider signing later** - When project is established

**For Commercial Use:**

- Invest in proper certificates from day one
- Professional appearance matters

## Cost Summary

- **macOS**: $99/year (Apple Developer Program)
- **Windows**: $100-400/year (Code signing certificate)
- **Total**: ~$200-500/year for both platforms

## Documentation for Users

Include this in your README:

```markdown
## Security Warnings

The executables are not code-signed. You may see security warnings:

### macOS

Right-click the app → "Open" → Confirm opening

### Windows

Click "More info" → "Run anyway"

This is expected for unsigned applications. The source code is open and builds are automated via GitHub Actions.
```

## Resources

- [Apple Code Signing Guide](https://developer.apple.com/documentation/security/notarizing_macos_software_before_distribution)
- [Microsoft Authenticode](https://docs.microsoft.com/en-us/windows-hardware/drivers/install/authenticode)
- [PyInstaller Signing](https://pyinstaller.org/en/stable/feature-notes.html#code-signing)

## Future Considerations

When ready to implement code signing:

1. Open issue to track progress
2. Obtain necessary certificates
3. Set up GitHub secrets securely
4. Update workflows (examples above)
5. Test signed builds
6. Update documentation
