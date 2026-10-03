# Security Policy

## Supported versions

Security fixes are applied to the current default branch. Historical commits, tags, forks, and unsupported dependency versions may not receive fixes.

## Required pre-main security gate

Every pull request is blocked from `main` unless the required `security-gate` succeeds. The gate covers the repository's first-party stack as follows:

- JavaScript/TypeScript: CodeQL `security-extended`;
- Python: CodeQL `security-extended`;
- repository-owned Go: CodeQL `security-extended` after compiling `docker/security-overrides`;
- GitHub Actions workflow code: CodeQL Actions analysis;
- any CodeQL code-scanning alert, at any severity, fails the pull-request gate from local SARIF before merge;
- Bash/shell: digest-verified ShellCheck;
- repository configuration and committed secret material: Trivy filesystem misconfiguration/secret scanning;
- the built k6 container and compiled dependency graph: Trivy image vulnerability scanning;
- pull-request dependency diffs: GitHub Dependency Review when the dependency graph is available.

The security workflow also runs `.github/scripts/validate_security_stack.py`, which fails closed if a recognized first-party code language appears without an assigned scanner. Scanner and workflow dependencies are immutable or digest-verified.

## Reporting a vulnerability

Do not disclose suspected vulnerabilities, credentials, tokens, exploit details, or sensitive test data in a public issue.

Use GitHub private vulnerability reporting if the repository presents that option. If private reporting is unavailable, open a minimal public issue requesting a private contact channel and do not include exploit or secret details.

Include:

- affected repository and commit SHA;
- impact and affected boundary;
- minimal reproduction steps;
- relevant dependency or tool versions;
- suggested mitigation, if known.

Reports will be validated against the current default branch. No bounty or response-time commitment is implied.

## Authorized testing

Do not use repository browser, API, DAST, or load-testing capabilities against systems you do not own or have explicit authorization to test. Keep credentials and production data out of committed fixtures and diagnostic artifacts.

## Disclosure

Coordinate disclosure after a fix or mitigation is available. Avoid publishing working exploit details before maintainers have had a reasonable opportunity to address the issue.
