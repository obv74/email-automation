# Email Agent

Self-hosted AI email agent for moving companies: reads full Gmail threads, extracts structured job data with a local LLM (Ollama/Qwen), pulls pricing from Google Sheets, generates rule-based replies, and logs everything.

**No Docker** — runs as a Python app on your VPS with systemd.

## Features

- Full Gmail thread read via Gmail API (not snippets)
- Structured extraction: name, phone, addresses, inventory, requests, promises, summary
- Live pricing from Google Sheet (day of week, movers, truck type)
- Stock/custom replies from `config/rules.yaml`
- Gmail drafts by default (`REPLY_MODE=draft`) or auto-send
- Message log dashboard at `/dashboard`
- Scheduled job reminders (2-day / 1-day) from Sheet `Jobs` tab
- Lead follow-up if no reply (mark thread with API)
- Background polling via APScheduler

## Quick start (development)

```bash
chmod +x scripts/install.sh scripts/run_dev.sh
./scripts/install.sh
# Edit .env with Google OAuth credentials and PRICING_SHEET_ID
./scripts/run_dev.sh
```

Open http://localhost:8000/dashboard → **Connect Gmail**.

## Google Cloud setup

1. Create a project at [Google Cloud Console](https://console.cloud.google.com)
2. Enable **Gmail API**, **Google Sheets API**, **Google Calendar API**
3. Create OAuth 2.0 credentials (Web application)
4. Authorized redirect URI: `http://YOUR_HOST:8000/auth/google/callback`
5. Copy Client ID and Secret into `.env`

## Pricing sheet format

**Tab `Pricing`** (header row):

| day_of_week | num_movers | truck_type | price |
|-------------|------------|------------|-------|
| monday      | 2          | 16ft       | 450   |

**Tab `Jobs`** (for confirmation reminders):

| job_id | customer_email | customer_name | move_date | description | load_address |
|--------|----------------|---------------|-----------|-------------|--------------|

Share the sheet with the Google account you connect, or use a service account (`GOOGLE_SERVICE_ACCOUNT_FILE`).

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/poll` | Process unread threads |
| POST | `/api/threads/{id}/process` | Process one thread |
| POST | `/api/threads/{id}/awaiting-reply` | Enable follow-up if no reply |
| GET | `/health` | Health check |

## VPS production (no Docker)

See [docs/setup.md](docs/setup.md).

## Configuration

Copy `.env.example` to `.env`. Key variables:

- `OLLAMA_MODEL` — default `qwen2.5:7b-instruct`
- `REPLY_MODE` — `draft` (recommended) or `send`
- `FOLLOWUP_WAIT_DAYS` / `FOLLOWUP_MAX_ATTEMPTS`
- `REMINDER_DAYS` — e.g. `2,1`

## Project structure

```
app/
  auth/         Google OAuth
  gmail/        Thread read, drafts, send
  extraction/   Ollama + Pydantic schema
  pricing/      Sheets + quote logic
  replies/      YAML rules + templates
  scheduler/    Poll, reminders, follow-ups
  dashboard/    Message log UI
config/
  rules.yaml    Reply templates
scripts/
  install.sh    One-time setup
  email-agent.service
```

## License

Proprietary — delivered to client with full source ownership per project agreement.
