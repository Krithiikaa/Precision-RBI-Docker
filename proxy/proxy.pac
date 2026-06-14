// Precision-RBI proxy auto-config.
// Push this via MDM as the browser/OS proxy PAC URL.
// Everything goes through the RBI proxy EXCEPT our own infra and local addrs.
function FindProxyForURL(url, host) {
  // RBI infrastructure must bypass the proxy (portal, viewer, stream)
  if (shExpMatch(host, "rbi.local") ||
      shExpMatch(host, "*.rbi.local")) {
    return "DIRECT";
  }
  // never proxy localhost / private ranges used by the infra
  if (isPlainHostName(host) ||
      shExpMatch(host, "*.local") ||
      isInNet(dnsResolve(host), "127.0.0.0", "255.0.0.0") ||
      isInNet(dnsResolve(host), "10.0.0.0", "255.0.0.0") ||
      isInNet(dnsResolve(host), "192.168.0.0", "255.255.0.0")) {
    return "DIRECT";
  }
  // everything else -> Precision-RBI proxy
  return "PROXY rbi.local:8080";
}
