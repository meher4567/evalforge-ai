# Security Policy

## Reporting a vulnerability

Do not open a public issue for a suspected vulnerability. Use GitHub’s private vulnerability reporting for this repository when available. Otherwise, contact the repository owner privately through their GitHub profile and include a minimal reproduction, affected commit, impact, and suggested remediation.

Please do not include live credentials, customer data, or destructive proof-of-concept payloads. You should receive an acknowledgement within seven days. Disclosure timing should be coordinated after a fix is available.

## Supported versions

Security fixes target the current `main` branch until versioned releases are published.

## Deployment baseline

- Set `EVALFORGE_ENVIRONMENT=production` and a strong `EVALFORGE_API_KEY` for any exposed deployment.
- Keep provider secrets in approved environment variables; inline secrets in version configs are rejected.
- Restrict allowed adapter modules and outbound provider hosts.
- Apply Alembic migrations before starting the API or worker. `/readyz` reports unhealthy when the database is not at the current migration head.
- Terminate TLS and enforce network-level access controls at the deployment edge.
