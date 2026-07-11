# Email Agent

Self-hosted AI email agent for moving companies: reads full Gmail threads, classifies booked vs inquiry, extracts structured job data with a local LLM (Ollama/Qwen), pulls pricing + stock replies from Google Sheets, drafts replies for inquiries only, labels mail in Gmail, and logs everything.

**No Docker** — runs as a Python app on your VPS with systemd.

## Features

- Full Gmail thread read via Gmail API (not snippets)
- Classify: **booked** / **inquiry** / **unclear** / **ignore**
- Booked jobs (Moving Helper etc.): **extract only** — no sales draft
- Structured extraction into your job categories (title + booking entry + Y/N + pricing)
- Live pricing from Google Sheet (`Pricing` tab)
- Stock replies from Google Sheet (`StockResponses` tab) with keyword triggers
- Gmail drafts for inquiries (`REPLY_MODE=draft`) — never auto-send unless you set send
- Gmail labels: `Agent/Drafted`, `Agent/Extracted`, `Agent/Needs-Human`, `Agent/Ignored`
- Safety: only Drafted is marked read; Needs-Human / Ignored / Extracted stay unread
- Writes rows to `ExtractedJobs` sheet tab (copyable title + booking blocks)
- Confirmation emails 3 days + 1 day before (from `Jobs` tab)
- Lead follow-up if no reply (awaiting_reply after draft)
- Web dashboard: message log, job fields, send button, Connect Gmail
- Admin guide: [docs/admin-guide.md](docs/admin-guide.md)

## Quick start (development)

```bash
chmod +x scripts/install.sh scripts/run_dev.sh
./scripts/install.sh
# Edit .env with Google OAuth credentials and PRICING_SHEET_ID
./scripts/run_dev.sh
```

Open http://localhost:8000/dashboard → **Connect Gmail**.

## Google Cloud setup

1. Create a project at [Google Cloud Console](https://console.google.com)
2. Enable **Gmail API**, **Google Sheets API**, **Google Calendar API**
3. Create OAuth 2.0 credentials (Web application)
4. Authorized redirect URI: `http://YOUR_HOST:8000/auth/google/callback`
5. Copy Client ID and Secret into `.env`

Scopes used: Gmail modify/send, Sheets read/write, Calendar readonly.

## Sheet tabs

**`Pricing`**

| day_of_week | num_movers | truck_type | price |
|-------------|------------|------------|-------|
| monday      | 2          | 16ft       | 450   |

**`StockResponses`** (optional)

| trigger | body |
|---------|------|
| insurance | Hi {customer_name}, … |

**`Jobs`** (confirmations)

| job_id | customer_email | customer_name | move_date | description | load_address |
|--------|----------------|---------------|-----------|-------------|--------------|

**`ExtractedJobs`** — auto-created; agent appends extracted jobs.

Share the sheet with the Google account you connect.

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/poll` | Process unread threads |
| POST | `/api/threads/{id}/process` | Process one thread |
| POST | `/api/threads/{id}/awaiting-reply` | Enable follow-up if no reply |
| GET | `/health` | Health check |

## VPS production (no Docker)

See [docs/setup.md](docs/setup.md). Operator guide: [docs/admin-guide.md](docs/admin-guide.md).

## Configuration

Copy `.env.example` to `.env`. Key variables:

- `OLLAMA_MODEL` — default `qwen2.5:3b-instruct`
- `REPLY_MODE` — `draft` (recommended) or `send`
- `FOLLOWUP_WAIT_DAYS` / `FOLLOWUP_MAX_ATTEMPTS`
- `REMINDER_DAYS` — default `3,1`

## Project structure

```
app/
  auth/         Google OAuth
  gmail/        Thread read, drafts, send, labels
  extraction/   Classify + schema + Ollama
  pricing/      Sheets pricing, stock, ExtractedJobs write
  replies/      Templates + stock matching
  scheduler/    Poll, reminders, follow-ups
  services/     Pipeline
config/
  rules.yaml    Fallback reply templates
docs/
  setup.md
  admin-guide.md
web/            Next.js dashboard
```
