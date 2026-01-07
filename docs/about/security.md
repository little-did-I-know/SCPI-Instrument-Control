# Security Policy

## Supported Versions

We actively support the following versions of SCPI-Instrument-Control with security updates:

| Version | Supported          |
| ------- | ------------------ |
| 0.2.x   | :white_check_mark: |
| 0.1.x   | :x:                |

## Reporting a Vulnerability

We take the security of SCPI-Instrument-Control seriously. If you believe you have found a security vulnerability, please report it to us as described below.

### How to Report a Security Vulnerability

**Please do not report security vulnerabilities through public GitHub issues.**

Instead, please report them via one of the following methods:

1. **GitHub Security Advisories** (Preferred)
   - Go to the [Security tab](https://github.com/little-did-I-know/SCPI-Instrument-Control/security) of this repository
   - Click "Report a vulnerability"
   - Fill out the form with details about the vulnerability

2. **Email**
   - Contact the maintainers directly through GitHub
   - Include "SECURITY" in the subject line
   - Provide detailed information about the vulnerability

### What to Include in Your Report

Please include the following information to help us better understand and address the issue:

- Type of vulnerability (e.g., remote code execution, privilege escalation, etc.)
- Full paths of source file(s) related to the manifestation of the vulnerability
- The location of the affected source code (tag/branch/commit or direct URL)
- Any special configuration required to reproduce the issue
- Step-by-step instructions to reproduce the issue
- Proof-of-concept or exploit code (if possible)
- Impact of the vulnerability, including how an attacker might exploit it

### What to Expect

After you submit a vulnerability report, you can expect:

1. **Acknowledgment**: We will acknowledge receipt of your vulnerability report within 48 hours.

2. **Communication**: We will keep you informed about the progress of fixing the vulnerability.

3. **Timeline**: We aim to:
   - Confirm the vulnerability within 5 business days
   - Develop and test a fix within 30 days
   - Release a patched version as soon as possible

4. **Credit**: If you wish, we will credit you in the security advisory and release notes (unless you prefer to remain anonymous).

## Security Best Practices for Users

When using SCPI-Instrument-Control, we recommend the following security practices:

### Network Security

1. **Isolate Test Equipment**: Keep oscilloscopes on a separate network segment from critical systems
2. **Firewall Rules**: Restrict access to oscilloscope IP addresses
3. **VPN Access**: Use VPN when accessing oscilloscopes remotely
4. **No Public Internet**: Never expose oscilloscopes directly to the internet

### Credential Management

1. **Default Passwords**: Change default passwords on oscilloscopes if applicable
2. **Access Control**: Limit who can access oscilloscopes on your network
3. **Authentication**: Enable authentication features on your oscilloscope if available

### Code Security

1. **Input Validation**: Always validate IP addresses and network inputs
2. **Error Handling**: Handle connection errors gracefully
3. **Logging**: Monitor logs for unusual activity
4. **Dependencies**: Keep dependencies up to date (use Dependabot)

### Safe Usage Examples

```python
from scpi_control import Oscilloscope

# Good: Validate IP address before connecting
import ipaddress

def safe_connect(ip_str):
    try:
        # Validate IP address format
        ip = ipaddress.ip_address(ip_str)

        # Avoid public IPs - oscilloscopes should be on private networks
        if ip.is_global:
            raise ValueError("Oscilloscope should not be on public internet")

        # Connect with timeout
        scope = Oscilloscope(ip_str, timeout=5.0)
        scope.connect()
        return scope
    except ValueError as e:
        print(f"Invalid IP address: {e}")
        return None
```

## Known Security Considerations

### Network Communication

- This library communicates with oscilloscopes over **unencrypted TCP/IP** (SCPI protocol)
- SCPI protocol does not include authentication or encryption by default
- Network traffic can potentially be intercepted or modified

**Mitigation**: Use isolated/private networks for test equipment

### Command Injection

- The library sends SCPI commands to oscilloscopes
- Malicious SCPI commands could potentially affect oscilloscope operation
- User input should be validated before being used in SCPI commands

**Mitigation**: The library uses parameterized commands and validates inputs

### Resource Exhaustion

- Large waveform captures can consume significant memory
- Rapid acquisition loops could impact system performance

**Mitigation**: Implement appropriate timeouts and rate limiting in your code

## Dependency Security

We use automated tools to monitor dependencies for known vulnerabilities:

- **Dependabot**: Automatically creates PRs for dependency updates
- **Safety**: Checks Python dependencies for known security vulnerabilities
- **Bandit**: Static security analysis for Python code

## Disclosure Policy

When we receive a security bug report, we will:

1. Confirm the problem and determine affected versions
2. Audit code to find similar problems
3. Prepare fixes for all supported versions
4. Release new versions as soon as possible
5. Publish a security advisory on GitHub

We request that you:

- Give us reasonable time to fix the vulnerability before public disclosure
- Make a good faith effort to avoid privacy violations, destruction of data, or service interruption
- Do not exploit the vulnerability beyond what is necessary to demonstrate it

## Security Updates

Security updates will be released as patch versions (e.g., 0.2.5 → 0.2.6) and will be:

- Announced in the [GitHub Security Advisories](https://github.com/little-did-I-know/SCPI-Instrument-Control/security/advisories)
- Documented in the [Changelog](changelog.md)
- Tagged with `[SECURITY]` prefix in release notes

## Scope

This security policy applies to:

- The `siglent` Python package
- Official examples and documentation
- CI/CD workflows

This policy does **not** cover:

- Security of the oscilloscope hardware or firmware
- Third-party dependencies (report those to respective maintainers)
- Vulnerabilities in forks or unofficial versions

## Questions?

If you have questions about this security policy, please open a GitHub Discussion or contact the maintainers.

---

**Last Updated**: 2025-12-30
