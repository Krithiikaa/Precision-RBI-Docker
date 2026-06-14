"""
Precision-RBI mitmproxy addon.

Behaviour per request:
  1. Log EVERY request to the gateway (full URL capture, per device/user).
  2. If the request is a top-level DOCUMENT navigation:
       - device not authenticated  -> redirect to captive portal (login once)
       - device authenticated       -> return the streaming BOOTSTRAP page
         (the real site is rendered in the isolated browser, never here)
  3. Non-document requests for the real site are never made by the user's
     browser, because the document response is replaced by the viewer.

Infra domains (gateway/portal/viewer) are exempted in the PAC file so they
bypass the proxy and load normally.
"""
import json
import httpx
from mitmproxy import http

GATEWAY = "http://gateway:8000"          # internal name on the compose network
GATEWAY_PUBLIC = "http://rbi.local:8000" # what the user's browser can reach
INFRA_HOSTS = {"rbi.local", "gateway"}

_client = httpx.Client(timeout=5)


def _is_document(flow: http.HTTPFlow) -> bool:
    dest = flow.request.headers.get("sec-fetch-dest", "")
    if dest:
        return dest == "document"
    accept = flow.request.headers.get("accept", "")
    return "text/html" in accept and flow.request.method == "GET"


def _client_ip(flow: http.HTTPFlow) -> str:
    return flow.client_conn.peername[0] if flow.client_conn.peername else "unknown"


def _device(ip: str) -> dict | None:
    try:
        r = _client.get(f"{GATEWAY}/portal/check", params={"ip": ip})
        data = r.json()
        return data if data.get("authenticated") else None
    except Exception:
        return None


def _log(ip: str, user: str, url: str, etype: str):
    try:
        _client.post(f"{GATEWAY}/log", json={
            "ip": ip, "user_id": user, "url": url, "event_type": etype,
        })
    except Exception:
        pass


def request(flow: http.HTTPFlow):
    host = flow.request.pretty_host
    if host in INFRA_HOSTS:
        return  # let our own infra through untouched

    ip = _client_ip(flow)
    dev = _device(ip)
    user = dev["user_id"] if dev else "unauthenticated"
    url = flow.request.pretty_url

    # capture EVERY request
    _log(ip, user, url, "proxy_request")

    if not _is_document(flow):
        # sub-resources: if the device is browsing via the viewer, the real
        # site's assets are fetched by the isolated browser, not here. Block
        # direct fetches of non-infra resources to enforce isolation.
        if not dev:
            flow.response = http.Response.make(
                302, b"", {"Location": f"{GATEWAY_PUBLIC}/portal"})
        else:
            flow.response = http.Response.make(
                204, b"", {"Content-Type": "text/plain"})
        return

    # top-level navigation
    if not dev:
        # one-time captive portal login
        flow.response = http.Response.make(
            302, b"",
            {"Location": f"{GATEWAY_PUBLIC}/portal?next={url}"})
        return

    # authenticated -> return streaming bootstrap pointing at the isolated view
    _log(ip, user, url, "navigate")
    boot = f"""<!doctype html><html><head><meta charset=utf-8>
<title>Precision-RBI</title></head><body style="margin:0">
<script>
  window.RBI_TARGET = {json.dumps(url)};
  window.RBI_GATEWAY = {json.dumps(GATEWAY_PUBLIC)};
  location.replace(window.RBI_GATEWAY + "/viewer?target=" +
                   encodeURIComponent(window.RBI_TARGET));
</script>
Loading securely&hellip;</body></html>"""
    flow.response = http.Response.make(
        200, boot.encode(), {"Content-Type": "text/html"})
