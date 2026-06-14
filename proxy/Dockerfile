FROM python:3.12-slim
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY addon.py .
EXPOSE 8080
# --mode regular = explicit forward proxy (what the PAC/MDM points browsers at)
# certs persist in /root/.mitmproxy (mounted volume) so the CA is stable
CMD ["mitmdump", "--mode", "regular", "--listen-port", "8080", \
     "--set", "block_global=false", "-s", "addon.py"]
