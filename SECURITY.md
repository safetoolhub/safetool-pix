# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.9-beta | ✅ Active |
| < 0.9 | ❌ Not supported |

## Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub issues.**

Send a private email to **safetoolhub@protonmail.com** with:

1. A description of the vulnerability and its potential impact
2. Steps to reproduce the issue
3. Your OS and SafeTool Pix version
4. Any suggested fix (optional)

### What to Expect

- **Acknowledgement** within 48 hours
- **Status update** within 7 days (confirmed, rejected, or needs more info)
- **Fix timeline** communicated once the vulnerability is confirmed
- **Credit** in the release notes if you wish (please indicate your preference)

We ask that you give us reasonable time to address the issue before any public disclosure.

## Scope

SafeTool Pix is a **100% offline, local desktop application**. It makes no network connections and stores no data outside your machine. As a result:

- Network-based vulnerabilities (SSRF, XXE with remote endpoints, etc.) are out of scope
- Cloud data exposure is out of scope (there is no cloud)
- Vulnerabilities in the build pipeline or release artifacts are **in scope**
- Local privilege escalation or malicious file parsing vulnerabilities are **in scope**
- Dependency vulnerabilities (in bundled packages) are **in scope**

Thank you for helping keep SafeTool Pix and its users safe.
