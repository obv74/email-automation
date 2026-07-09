# Email Agent Web (Vercel)

Next.js frontend for the Email Agent platform. Users register/login here; Gmail OAuth and AI processing run on the VPS API.

## Setup

```bash
cd web
npm install
cp .env.example .env.local
npm run dev
```

Open http://localhost:3000

## Environment

| Variable | Description |
|----------|-------------|
| `NEXT_PUBLIC_API_URL` | VPS FastAPI URL (e.g. `https://api.yourdomain.com`) |

## Deploy to Vercel

1. Push `web/` folder to GitHub (or deploy from monorepo with root directory `web`)
2. Set `NEXT_PUBLIC_API_URL` to your VPS API URL
3. On VPS `.env`, set:
   - `FRONTEND_URL=https://your-app.vercel.app`
   - `CORS_ORIGINS=https://your-app.vercel.app`
   - `GOOGLE_REDIRECT_URI=https://api.yourdomain.com/auth/google/callback` (VPS, not Vercel)

## OAuth flow (Option A)

1. User clicks **Connect Gmail** on Vercel
2. Browser → VPS `/auth/google/connect?tenant=slug&token=JWT`
3. Google → VPS `/auth/google/callback`
4. VPS saves token → redirects to `https://your-app.vercel.app/companies/{slug}?gmail=connected`
