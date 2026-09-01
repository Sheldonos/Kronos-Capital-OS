# Security

- Never commit `.env.runtime`, API private keys, bank credentials, OAuth refresh tokens, or certificates.
- Use provider keys dedicated to KCOS and restrict them by IP and portfolio/account where supported.
- Trading keys should not have transfer/withdrawal permission by default.
- Move production secrets from env files to a secrets manager/HSM/KMS-backed system.
- Keep PostgreSQL and Redis private to the deployment network.
- Treat a stale risk/data state as fail-closed for new exposure.
- Rotate compromised credentials immediately and trip the emergency stop before restoring execution.

## Operator token (remote dashboard access)

The KCOS dashboard stores the operator admin token in `sessionStorage`, which is cleared when the
browser tab is closed. This is intentional: no cross-session persistence on the client. Mitigations
operators must apply:

- **Do not expose port 8080 to the public internet.** Bind the API behind an authenticated reverse
  proxy (nginx + mTLS, Cloudflare Access, Tailscale, or similar) for any remote access.
- `sessionStorage` is visible in browser devtools to anyone with physical or remote access to the
  browser session. Use a dedicated, locked-down browser profile for dashboard access.
- The admin token should be rotated with `kcos admin-token` after any session compromise.
- For zero-trust deployments, run the runtime on the same host as the browser (loopback access
  bypasses token auth entirely) or enforce mTLS at the proxy layer.

## Rate limiting

The `/api/*` admin endpoints do not implement per-IP rate limiting inside the application. Deploy
a rate-limiting reverse proxy (nginx `limit_req`, Caddy `rate_limit`, AWS WAF, etc.) in front of
port 8080 before any internet-facing deployment. Without this, a remote attacker who obtains the
admin token can replay it at high frequency.
