# VPS Setup (No Docker)

Deploy on Ubuntu 22.04+ with at least **8 GB RAM** (for Qwen 7B + app).

## 1. System packages

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git
```

## 2. Install Ollama

```bash
curl -fsSL https://ollama.com/install.sh | sh
sudo systemctl enable ollama
sudo systemctl start ollama
ollama pull qwen2.5:7b-instruct
```

## 3. Deploy app

```bash
sudo useradd -r -m -d /opt/email-agent emailagent || true
sudo mkdir -p /opt/email-agent
sudo chown emailagent:emailagent /opt/email-agent

# Copy project files to /opt/email-agent (git clone or rsync)
cd /opt/email-agent
sudo -u emailagent ./scripts/install.sh
sudo -u emailagent nano .env   # set OAuth, sheet ID, APP_BASE_URL
```

Set in `.env` for production:

```
APP_BASE_URL=https://your-domain.com
GOOGLE_REDIRECT_URI=https://your-domain.com/auth/google/callback
REPLY_MODE=draft
```

Update the same redirect URI in Google Cloud Console.

## 4. systemd service

```bash
sudo cp scripts/email-agent.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable email-agent
sudo systemctl start email-agent
sudo systemctl status email-agent
```

## 5. HTTPS (recommended)

Use nginx + Let's Encrypt so OAuth works reliably:

```nginx
server {
    listen 80;
    server_name your-domain.com;
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## 6. Connect Gmail

1. Open `https://your-domain.com/dashboard`
2. Click **Connect Gmail**
3. Approve permissions

## 7. Verify

```bash
curl http://127.0.0.1:8000/health
curl -X POST http://127.0.0.1:8000/api/poll
```

Check `/dashboard` for logged drafts and extractions.

## Operating costs

| Item | Cost |
|------|------|
| VPS (8GB) | ~$20–40/mo |
| Ollama / Qwen | $0 per email |
| Google APIs | Free at typical volume |
| Twilio etc. | N/A for email agent |

## Troubleshooting

**Ollama connection refused** — ensure `ollama serve` is running: `systemctl status ollama`

**OAuth redirect mismatch** — `GOOGLE_REDIRECT_URI` must exactly match Google Cloud credentials

**Empty pricing** — check sheet tab name `Pricing`, share sheet with connected Google account

**Extraction errors** — try `ollama pull qwen2.5:14b` on a 16GB+ VPS, or retry via `/api/threads/{id}/process?force=true`
