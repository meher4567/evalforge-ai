# Authentication and tenant isolation

EvalForge uses organization-scoped principals. Every persisted app, evaluator configuration, gate
rule, run, and comparison carries an organization ID, and every API query includes that ID. Child
resources are resolved through their tenant-owned parent. Cross-tenant identifiers return `404`
rather than revealing that a resource exists.

## First owner

Set a high-entropy `EVALFORGE_BOOTSTRAP_TOKEN`, migrate the database, then call the one-time
bootstrap endpoint:

```bash
curl -X POST https://api.example.com/api/auth/bootstrap \
  -H 'Content-Type: application/json' \
  -H 'X-EvalForge-Bootstrap-Token: <bootstrap-secret>' \
  -d '{
    "email": "owner@example.com",
    "password": "a-long-unique-password",
    "display_name": "Project Owner",
    "organization_name": "Example",
    "organization_slug": "example"
  }'
```

The endpoint is permanently closed after the first user exists. Rotate or remove the bootstrap
secret after initial setup.

## Credentials

- Passwords are salted and hashed with scrypt; plaintext passwords are never stored.
- Login sessions and personal API keys are opaque random values. Only keyed BLAKE2b fingerprints
  are stored. The plaintext API key is returned once.
- Send a session or API key as `Authorization: Bearer <token>` or
  `X-EvalForge-API-Key: <token>`.
- Browser credentials are memory-only and are never written to local or session storage. Refreshing
  or closing the page removes the credential.
- Password changes revoke the user's other active login sessions.
- Five failed password attempts lock the account for 15 minutes. Invalid-user checks still execute
  the password hash path to reduce account-enumeration timing differences.
- Set a unique `EVALFORGE_AUTH_TOKEN_PEPPER`; rotating it invalidates all sessions and personal
  API keys.

## Roles

| Role | Read | Run/evaluate | Manage members | Grant owner |
|---|---:|---:|---:|---:|
| viewer | yes | no | no | no |
| evaluator | yes | yes | no | no |
| admin | yes | yes | yes | no |
| owner | yes | yes | yes | yes |

An organization cannot lose its last owner. Removed or disabled users immediately fail credential
validation because membership and user status are checked on every authenticated request.

## OIDC readiness

The schema supports passwordless users and immutable `(issuer, subject)` identity links in
`oidc_identities`. No external bearer token is trusted by default. Enabling an OIDC provider still
requires an issuer-specific authorization-code flow, JWKS signature and claim validation, explicit
account-linking rules, and redirect URI configuration. This boundary is intentional: merely trusting
proxy headers or decoding an unsigned JWT would weaken the authentication model.
