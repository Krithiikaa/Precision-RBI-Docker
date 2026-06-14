# Precision-RBI

A Remote Browser Isolation (RBI) system. Browsers run on **your server**; the
user's device only receives sanitized DOM or a pixel stream. Every site the
user visits transits the **Precision-RBI** server first, automatically — no
manual `?url=` entry, no untrusted code on the user's machine.

## Components

| Service       | Role                                                            | Port |
|---------------|-----------------------------------------------------------------|------|
| `gateway`     | Auth (login once), WebSocket control channel, serves thin client| 8000 |
| `browser-host`| Disposable isolated Chromium pool (Playwright), DOM+pixel render | 9000 |
| `redis`       | Session store                                                   | 6379 |
| `clickhouse`  | Audit log store (captures ALL user activity)                    | 8123 |

## How your requirements map

- **Runs on server first, then loads into website** → `browser-host` fetches and
  renders every page server-side; only the result streams to the browser.
- **No manual `?url=`** → the thin client captures the address bar / clicks and
  sends them over the `/ws` channel; the URL resolves only on the server.
- **Capture all user logs** → `services/audit.py` emits every navigation, result,
  and user action into ClickHouse (`rbi.audit`).
- **Auth once per user** → short access token + long refresh token (HttpOnly
  cookies); `/auth/refresh` silently re-mints access with no re-prompt.
- **Hybrid DOM + pixel fallback** → DOM is sanitized and mirrored; complex/heavy
  pages auto-switch to a pixel screenshot stream.

## Run it (one command)

```bash
cp .env.example .env        # edit JWT_SECRET / ADMIN_PASSWORD
docker compose up --build
```

Open http://localhost:8000 → log in with `admin` / `admin123` (or your
`ADMIN_PASSWORD`) → type any URL in the bar.

## View captured logs

```bash
curl "http://localhost:8123/?query=SELECT * FROM rbi.audit ORDER BY ts DESC LIMIT 50 FORMAT Pretty"
```

## Local dev without Docker

```bash
# terminal 1 - browser host
cd browser-host && pip install -r requirements.txt && playwright install chromium
uvicorn app.main:app --port 9000

# terminal 2 - gateway (needs redis + clickhouse running)
cd gateway && pip install -r requirements.txt
REDIS_URL=redis://localhost:6379/0 BROWSER_HOST_URL=http://localhost:9000 \
  uvicorn app.main:app --port 8000
```

## Production hardening (next steps)

- Put Nginx/Envoy in front of `gateway`, terminate TLS, set `COOKIE_SECURE=true`.
- Run `browser-host` containers under **gVisor** (`runtime: runsc`) and apply an
  egress-only firewall (allow 80/443 out, drop inbound).
- Replace `DEMO_USERS` with a real IdP/OIDC and a user database.
- Add download scanning (ClamAV/CDR) before releasing files to the user.
- Recycle browser contexts per session (already done on release).
