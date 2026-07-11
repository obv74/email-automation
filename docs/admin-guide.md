# Email Agent — Admin Guide

For DC Top Choice Movers (and any company on this install).

## What the agent does

1. Reads **full** Gmail threads (not snippets).
2. Classifies each unread inbox email:
   - **booked** — already booked (Moving Helper / payment code / JB-) → extract only
   - **inquiry** — new lead / question → extract + stock/price draft
   - **unclear** → Needs-Human (no guess)
   - **ignore** → not moving-related
3. Applies Gmail labels (visible on phone):
   - `Agent/Drafted` — draft ready (marked **read**)
   - `Agent/Extracted` — booked job summarized (stays **unread**)
   - `Agent/Needs-Human` — unsure (stays **unread**)
   - `Agent/Ignored` — skipped (stays **unread**)
4. Writes structured jobs to your Google Sheet tab **`ExtractedJobs`**.
5. Sends confirmation emails from the **`Jobs`** tab **3 days** and **1 day** before the move.

**Nothing sends a customer email without your click** when Reply mode is `draft` (recommended).

---

## Turn the agent off / on

**Settings → AI summarize & reply**

- **Off** = inbox is not touched at all.
- **On** = polling resumes.

Or use **Disconnect Gmail** to revoke access.

---

## Google Sheet setup

One spreadsheet, three tabs (share with the connected Gmail account).

### Tab `Pricing`

| day_of_week | num_movers | truck_type | price |
|-------------|------------|------------|-------|
| monday      | 2          | 15ft       | 318   |

### Tab `StockResponses` (optional but recommended)

| trigger | body |
|---------|------|
| insurance | Hi {customer_name}, Yes we carry liability insurance… |
| protective covers | Hi {customer_name}, Our movers wear… |
| I want to book | Hi {customer_name}, Great — here is the deposit… |

Triggers are matched against the email + summary (case-insensitive). Longer triggers win.

Placeholders you can use: `{customer_name}`, `{summary}`, `{quote}`, `{load_address}`, `{unload_address}`, `{move_date}`, `{move_time}`, `{inventory}`, …

### Tab `Jobs` (confirmations)

| job_id | customer_email | customer_name | move_date | description | load_address |
|--------|----------------|---------------|-----------|-------------|--------------|

Confirmations run on days listed in `REMINDER_DAYS` (default `3,1`).

### Tab `ExtractedJobs` (auto-created)

The agent creates this tab and appends every extracted job (booked + inquiry) with title/booking blocks ready to copy into your schedule Doc.

---

## Daily workflow

1. Open Gmail (phone or desktop).
2. Check label folders:
   - **Agent/Drafted** → review draft → Send (or use dashboard **Send reply**).
   - **Agent/Extracted** → open dashboard → **Copy all** job categories → paste into schedule Doc / movers text.
   - **Agent/Needs-Human** → handle yourself (stays unread).
3. Keep the **Jobs** tab updated for booked moves so confirmations fire.

---

## Re-connect Gmail (required once after upgrade)

We upgraded Sheets access so the agent can **write** `ExtractedJobs`.

1. Settings → Disconnect Gmail  
2. Connect Gmail again and accept the new permissions  

---

## Dashboard

- Message log with direction badges: draft / extracted / needs human / skipped  
- Structured **Job categories** + **Copy all**  
- Connect Gmail, pricing sheet ID, AI on/off, reply mode  

---

## VPS / AI model

The AI runs on your Contabo VPS via Ollama (no per-email AI fee).  
Frontend may be on Vercel; the API + Ollama stay on the VPS 24/7.

See [setup.md](setup.md) for install / systemd / nginx.

---

## Ownership

On milestone release you own the full source code for what was delivered.  
Running costs: VPS only (plus free Gmail/Sheets at your volume).
