#!/usr/bin/env bash
# Extract the Precision-RBI root CA so you can push it to devices via MDM.
# Run AFTER the proxy container has started once (it generates the CA on first run).
set -e
echo "Pulling CA from the proxy container..."
docker compose cp proxy:/root/.mitmproxy/mitmproxy-ca-cert.pem ./precision-rbi-ca.pem
docker compose cp proxy:/root/.mitmproxy/mitmproxy-ca-cert.cer ./precision-rbi-ca.cer 2>/dev/null || true
echo
echo "CA written to ./precision-rbi-ca.pem (and .cer for Windows)."
echo "Push this as a TRUSTED ROOT CA to all managed devices via your MDM."
echo "Without it, HTTPS sites will show certificate warnings."
