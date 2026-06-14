# Precision-RBI — Transparent Proxy Mode (Option B)

Users keep using normal Chrome/Edge/Firefox. Every site they type in the
normal address bar is silently routed through Precision-RBI, rendered in an
isolated server-side browser, and streamed back as pixels. Setup is pushed
once via MDM; users do nothing.

## How it works

```
Normal Chrome ──PAC (pushed by MDM)──► RBI proxy :8080
   proxy intercepts the navigation, checks the device is signed in,
   and returns a tiny BOOTSTRAP page → loads the stream viewer →
   the isolated browser renders the real site → pixels stream back.
   The real site's HTML/JS never reaches the user's machine.
```

Three things are pushed by MDM, all invisible to users:
1. **PAC file** (`proxy/proxy.pac`) — routes all traffic to the proxy.
2. **Root CA** (`precision-rbi-ca.pem`) — so HTTPS interception is trusted.
3. **Lock** these settings so users can't turn them off.

## First run

```bash
cp .env.example .env          # set JWT_SECRET / ADMIN_PASSWORD
docker compose up --build     # starts redis, clickhouse, browser-host, gateway, proxy
```

### Get the CA cert (after the proxy has started once)

```bash
cd proxy && bash extract-ca.sh
# -> produces precision-rbi-ca.pem  (push this to devices via MDM)
```

## MDM rollout (per platform)

**Host the PAC file** somewhere devices can reach (e.g. on the gateway, or any
internal web server). Point `rbi.local` at the host running this stack (DNS or
each device's hosts file for testing).

- **Windows (Intune/GPO):** push the CA to *Trusted Root Certification
  Authorities*; set the system proxy auto-config URL to the PAC; lock proxy
  settings via policy.
- **macOS (Jamf/MDM):** deploy CA via a configuration profile (System keychain,
  trusted); set network proxy via a Proxies profile.
- **Chrome/Edge policy:** `ProxyMode=pac_script`, `ProxyPacUrl=<pac url>`; the OS
  trust store covers the CA. Set `ProxySettings` as mandatory so users can't edit.
- **Firefox:** uses its own trust store — push the CA via
  `security.enterprise_roots.enabled=true` or an enterprise policy, and set the
  PAC under network settings policy.

## Test on your own machine (no MDM)

1. Add to `/etc/hosts`:  `127.0.0.1  rbi.local`
2. Configure your browser proxy manually → PAC URL or `rbi.local:8080`.
3. Import `precision-rbi-ca.pem` into your browser/OS as a trusted root.
4. Browse to any `https://` site → you get the portal once → sign in
   (`admin`/`admin123`) → thereafter sites stream through Precision-RBI.

## Verify logging (every URL captured)

```bash
docker compose exec clickhouse clickhouse-client \
  --query "SELECT ts,user_id,event_type,url FROM rbi.audit ORDER BY ts DESC LIMIT 50"
```

## Known limits of this MVP (read before production)

- **Streaming** uses CDP JPEG screencast, not WebRTC. Fine for a demo / low
  concurrency; for many users move to WebRTC and a browser-per-session pool with
  autoscaling.
- **Device auth is keyed by client IP.** On company devices (1 user/device) this
  is fine. Behind shared NAT, multiple users share one identity — use proxy-auth
  or per-device certs instead.
- **One shared isolated page per device** in this scaffold. Production needs a
  proper session/tab manager and lifecycle (idle eviction, recycling).
- **mitmproxy CA is the trust anchor.** Protect the `mitm_ca` volume; anyone with
  that key can impersonate sites to your fleet. In production use an HSM-backed CA.
- Sub-resource requests are returned 204 to enforce isolation; some edge cases
  (service workers, websockets to third parties) need explicit handling.
