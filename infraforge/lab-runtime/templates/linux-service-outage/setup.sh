#!/usr/bin/env bash
# Lab setup script: runs at container start to create the broken state.
# This is NOT visible to the user.

set -euo pipefail

# ── Touch marker file so the grader can detect changes made by user ───────────
touch /tmp/.lab_start

# ── Create the webapp service ─────────────────────────────────────────────────
mkdir -p /etc/webapp /var/log/webapp /opt/webapp

cat > /opt/webapp/server.py <<'PYEOF'
#!/usr/bin/env python3
import http.server
import json
import os

class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"status":"ok"}')
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, fmt, *args):
        pass  # suppress access logs to stderr

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    httpd = http.server.HTTPServer(("", port), Handler)
    httpd.serve_forever()
PYEOF

chmod +x /opt/webapp/server.py

# ── Broken config: wrong ExecStart path ──────────────────────────────────────
cat > /etc/webapp/config.env <<'EOF'
PORT=8080
ENVIRONMENT=production
EOF

cat > /etc/systemd/system/webapp.service <<'EOF'
[Unit]
Description=InfraForge Webapp
After=network.target

[Service]
Type=simple
EnvironmentFile=/etc/webapp/config.env
# BUG: wrong path — intentional break
ExecStart=/usr/bin/python3 /opt/webappp/server.py
Restart=on-failure
RestartSec=5s
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable webapp

# Try to start it (it will fail — that's the point)
systemctl start webapp || true

# ── Fill up /var/log with rotated logs to simulate disk pressure ──────────────
mkdir -p /var/log/webapp
for i in $(seq 1 20); do
    dd if=/dev/urandom bs=1M count=40 2>/dev/null | base64 > /var/log/webapp/app.log.$i
done

# Current log (must be preserved)
echo "[$(date -Iseconds)] webapp service log" > /var/log/webapp/app.log

echo "[lab-setup] Done. webapp.service is broken and disk is under pressure."
