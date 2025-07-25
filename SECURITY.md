# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| latest  | :white_check_mark: |

## Known Security Considerations

### Direct Dependencies
Our direct Python dependencies have been updated to address known CVEs:
- **PyTorch 2.2.0+** - Patched for CVE-2024-31580 (heap buffer overflow)
- **Transformers 4.46.3+** - Patched for CVE-2024-11392/11393/11394 (RCE vulnerabilities)
- **NumPy 1.26.4** - No known direct vulnerabilities
- **urllib3 2.5.0** - Latest version, no known vulnerabilities

### Potential Vulnerability Sources
GitHub Dependabot may report vulnerabilities from:

1. **Base Docker Image** - The NVIDIA CUDA 11.8.0 base image includes Ubuntu 22.04 packages that may have vulnerabilities. Consider updating to a newer CUDA base image if compatible.

2. **Transitive Dependencies** - Dependencies installed by our direct dependencies that we don't control directly.

3. **System Packages** - apt packages installed during Docker build (python3.10, ffmpeg, git).

### Security Best Practices

1. **Environment Variables** - Never commit `.env` files. Use `.env.gpg` for encrypted configs.
2. **Audio Processing** - The service processes audio files in isolated containers with limited permissions.
3. **Email Credentials** - Store IMAP/SMTP credentials securely and rotate regularly.
4. **Network Security** - Run behind a firewall and limit SMTP relay access.

## Reporting a Vulnerability

Please report security vulnerabilities to the repository maintainer via GitHub issues.

Include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested remediation

## Update Schedule

We aim to update dependencies quarterly or when critical vulnerabilities are disclosed.