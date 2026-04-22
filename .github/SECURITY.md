# Security Policy

## Reporting Security Issues

If you discover a security vulnerability, **do not open a public issue**. Instead:

1. **Email:** carlostorresada@gmail.com with subject `[SECURITY] <brief description>`
2. **Include:** Description of the vulnerability (no exploit code), affected component, severity estimate
3. **Do not disclose:** Full exploit details, proof-of-concept code, or 0-day specifics in public discussion

We'll:
- Acknowledge your report within 7 days
- Provide an estimated timeline for fix
- Credit you in the release notes (if desired)
- Notify you when the fix is released

## Supported Versions

We release security patches for the current version and one prior release:

| Version | Supported |
|---------|-----------|
| 0.1.x   | ✅ Yes    |
| 0.0.x   | ❌ No     |

## Security Practices

px4-sitl-doctor implements security best practices:

- ✅ Bundles compatibility matrix (offline-first; no external API dependencies)
- ✅ Reads environment variables (does not store or log them)
- ✅ Spawns subprocesses safely (no `shell=True`; arguments passed as lists)
- ✅ Uses PyYAML safely (only `safe_load`, never `unsafe_load`)
- ✅ Validates upstream version data (fetches from GitHub releases API, not arbitrary URLs)
- ✅ No hardcoded credentials or secrets in code or configs
