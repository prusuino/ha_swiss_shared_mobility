# Security Policy

## Supported Versions

Only the latest release is supported. Please update to the latest version before reporting an issue.

## Reporting a Vulnerability

This integration only reads publicly published data from sharedmobility.ch over HTTPS (`https://api.sharedmobility.ch/v1/sharedmobility/identify` for the vehicles around a point, `…/find` for the station search; no key, no account) — it does not handle credentials, personal data, or write access to any external system. If you still believe you have found a security issue (e.g. in how data is parsed or how entities are exposed), please report it privately via [GitHub Security Advisories](../../security/advisories/new) rather than opening a public issue.

For anything that is not security-sensitive (bugs, feature requests), please use the regular [Issues](../../issues) tab instead.
