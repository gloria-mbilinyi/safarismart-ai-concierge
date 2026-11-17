# SafariSmart Hackathon Demo Runbook

This runbook is for the November 2026 hackathon demonstration. Use synthetic customer details and the synthetic operator only. Never show `.env`, terminal history containing credentials, a real phone number, an access token, or private booking detail on a public screen.

## Pre-demo checklist

Complete these before the judging slot:

1. Confirm PostgreSQL is running and the ignored `.env` still contains the working local `DATABASE_URL` and `AUTH_SECRET_KEY`.
2. Choose a known local demo password for `demo.operator@example.test`. Do not paste it into slides, chat, source, or this document.
3. Close any unrelated service using ports `8001` or `5173`.
4. Put the browser at 100% zoom and keep the window at a comfortable desktop width.
5. Keep the Africa's Talking Simulator evidence in a separate tab; do not depend on live outbound TLS during the judging slot.

## Single Windows CMD sequence

Open **Windows Command Prompt**, replace only `<YOUR-LOCAL-DEMO-PASSWORD>`, and paste the following block. It uses port `8001` to avoid common local port `8000` conflicts.

```cmd
cd /d C:\Users\Public\hackathon_projects\safarismart-ai-concierge
call .venv\Scripts\activate.bat
cd backend
python -m alembic upgrade head
python -m app.seed.destinations
set "SAFARISMART_BOOTSTRAP_PASSWORD=<YOUR-LOCAL-DEMO-PASSWORD>"
python -m app.cli.bootstrap_operator --operator-name "SafariSmart Synthetic Safaris" --operator-slug "safarismart-synthetic-safaris" --email "demo.operator@example.test" --full-name "Demo Operator" --assign-demo-destinations
set "SAFARISMART_BOOTSTRAP_PASSWORD="
cd ..\frontend
call npm ci
cd ..
start "SafariSmart API" cmd /k "cd /d C:\Users\Public\hackathon_projects\safarismart-ai-concierge\backend && ..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8001"
start "SafariSmart Web" cmd /k "cd /d C:\Users\Public\hackathon_projects\safarismart-ai-concierge\frontend && set VITE_API_BASE_URL=http://127.0.0.1:8001/api/v1&& npm run dev -- --host 127.0.0.1"
timeout /t 5
start http://127.0.0.1:5173
```

Expected startup checks:

```cmd
curl.exe --fail http://127.0.0.1:8001/api/health
curl.exe --fail http://127.0.0.1:8001/api/v1/destinations
```

Health must return `{"status":"ok"}`. The seed and bootstrap commands are repeatable; existing matching rows are reused instead of duplicated. A password mismatch deliberately fails rather than resetting the account.

## Three-minute story

### 0:00–0:25 — Problem and channels

Open the landing page. Say:

> SafariSmart makes Tanzanian tourism discovery accessible across a modern web experience, SMS, and USSD. It connects discovery to a safe booking-request workflow while keeping operator decisions human-controlled.

Point to the channel cards and the visible synthetic/demo wording.

### 0:25–0:55 — Trusted catalog

Open **Explore** and search for `Zanzibar` or filter the catalog. Explain that all five records are curated reference content from the database, not scraped live inventory, prices, or partnership claims.

### 0:55–1:35 — Grounded planner

Open **Trip planner**. Choose 5 days, 2 travellers, wildlife + beach, and a TZS budget such as `2500000`. Generate the plan.

Point to:

- `Rule-based fallback` when no local model is configured
- Named destinations that exist in the catalog
- The day-by-day high-level itinerary
- The disclaimer that budget is context and the result is not price, availability, or reservation

Say that an optional local Ollama model may reorder only known destination slugs; it cannot invent catalog facts or take booking actions.

### 1:35–2:10 — Consent-aware request

Open **Request a booking** from a destination. Use obviously synthetic details, future travel dates, phone preference, and explicit consent. Submit once and show the returned `pending_availability` reference.

Explain that replay protection uses an idempotency key and the public response omits contact data. Do not read the synthetic phone number aloud.

### 2:10–2:50 — Protected operator workflow

Open **Operator login** and use `demo.operator@example.test` plus the local password. Open the new request in the organization-scoped queue. Show its audit history and create a clearly labelled synthetic quote, or reject the request with a demo reason.

Explain that direct confirmation from `pending_availability` is impossible and cross-organization requests resolve as not found. Do not show an authorization token or real PII.

### 2:50–3:00 — Africa's Talking evidence

Show the prepared Simulator screenshots/tabs for the previously demonstrated SMS receipt and bilingual USSD `CON`/`END` flow. State clearly that these are Sandbox interactions, not real handset delivery or a live reservation.

## Optional live local SMS evidence

This uses the PII-safe provider, performs no network call, and prints only counts. Run it in a separate CMD window after creating a consented phone-preference booking:

```cmd
cd /d C:\Users\Public\hackathon_projects\safarismart-ai-concierge\backend
set "SMS_ENABLED=true"
set "SMS_PROVIDER=local"
..\.venv\Scripts\python.exe -m app.cli.notification_worker --drain
set "SMS_ENABLED="
set "SMS_PROVIDER="
```

The summary should show processed state without printing the recipient or message. This local mode is rejected in staging and production.

## Optional local USSD check

```cmd
curl.exe -X POST http://127.0.0.1:8001/api/v1/ussd --data-urlencode "sessionId=demo-session-1" --data-urlencode "serviceCode=*384*34763#" --data-urlencode "phoneNumber=+255700000001" --data-urlencode "text="
curl.exe -X POST http://127.0.0.1:8001/api/v1/ussd --data-urlencode "sessionId=demo-session-2" --data-urlencode "serviceCode=*384*34763#" --data-urlencode "phoneNumber=+255700000001" --data-urlencode "text=2*1"
```

The first response begins `CON Welcome`; the second is the Kiswahili destination list. These values are synthetic local callback data.

## Temporary Sandbox tunnel

Only if a live callback is essential, run a trusted temporary HTTPS tunnel while the API is active:

```cmd
cloudflared tunnel --url http://127.0.0.1:8001
```

Temporarily set the Sandbox callback to:

```text
https://<temporary-host>/api/v1/ussd
```

Do not commit, document as permanent, or place this transient URL in `.env` or Marketplace configuration. Remove it from the Sandbox dashboard when the demo ends. The laptop and tunnel are not production hosting.

## Docker alternative

Docker was not available on the development machine during final local verification. GitHub Actions is configured to build and smoke-test this path. On a machine with Docker, interactive CMD can generate ephemeral values and launch the stack without writing them to source:

```cmd
cd /d C:\Users\Public\hackathon_projects\safarismart-ai-concierge
for /f %i in ('python -c "import secrets; print(secrets.token_urlsafe(36))"') do set "POSTGRES_PASSWORD=%i"
for /f %i in ('python -c "import secrets; print(secrets.token_urlsafe(48))"') do set "AUTH_SECRET_KEY=%i"
set "WEB_PORT=8080"
docker compose up --build --detach db api frontend
docker compose ps
start http://127.0.0.1:8080
```

Stop without deleting the database volume:

```cmd
docker compose down
```

## Evidence capture

Capture these before submission, preferably at 1440×900 or a similar readable resolution:

1. Landing page with SafariSmart branding and channel summary
2. Five-card destination explorer
3. Planner response with generation-mode badge and disclaimer
4. Successful booking reference with no contact data visible
5. Operator queue/detail with synthetic label and audit history; redact PII
6. Africa's Talking Sandbox SMS inbox showing only a designated test number
7. English and Kiswahili USSD Simulator screens showing `CON`/`END`
8. GitHub Actions run summary after the final commit

Redact API keys, database URLs, access tokens, real phone numbers, real email addresses, and customer names. Do not edit screenshots to imply provider approval, production deployment, payment, or real booking confirmation.

## Recovery during judging

- If the planner's optional model is unavailable, keep `AI_PROVIDER=fallback`; that is a tested product mode, not a failure.
- If external SMS TLS fails, show the prior Simulator evidence and run the local outbox drain.
- If the temporary tunnel fails, use the local USSD `curl.exe` check and prior Simulator evidence.
- If a demo quote already exists, create a fresh booking request instead of editing database state.
- If the browser cannot reach the API, verify `http://127.0.0.1:8001/api/health` and that the web terminal set `VITE_API_BASE_URL` to port `8001`.
