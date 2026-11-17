# Render Free + Neon deployment

This runbook deploys SafariSmart as one public HTTPS web service. The image builds React and serves it from FastAPI, while Neon holds all durable data. Render Free can sleep and restart; the PostgreSQL outbox preserves notification jobs across both events.

No live deployment was created while writing this guide because no Render, Neon, Resend, DNS, or Africa's Talking account authorization was connected to this workspace. Do not invent a public URL or mark a provider configured until the corresponding dashboard confirms it.

## 1. Connect GitHub to Render

1. Sign in to Render and authorize access to `gloria-mbilinyi/safarismart-ai-concierge` with the narrowest repository access available.
2. Choose **New → Blueprint**, select the repository, and use the root [`render.yaml`](../render.yaml).
3. Confirm one **Free** Docker web service, branch `main`, build context `.`, and Dockerfile `marketplace/Dockerfile`.
4. Keep the health-check path `/api/health`.
5. After creation, set auto-deploy to **After CI Checks Pass** so a failing GitHub Actions run is not promoted.

The equivalent manual Web Service configuration is runtime **Docker**, plan **Free**, branch `main`, Dockerfile path `marketplace/Dockerfile`, context `.`, and health check `/api/health`. Render requires the process to bind `0.0.0.0:$PORT`; the existing image does this and defaults to port 8000 only when `PORT` is absent.

Official references: [Render Blueprint specification](https://render.com/docs/blueprint-spec), [web-service port binding](https://render.com/docs/web-services), and [health checks](https://render.com/docs/health-checks).

## 2. Create Neon PostgreSQL with TLS

1. Create a Neon Free project in a region reasonably close to the selected Render region.
2. In **Connection Details**, select the pooled connection string (`-pooler` hostname).
3. Require TLS with `sslmode=require`.
4. Change only the URL scheme for SQLAlchemy/psycopg:

   ```text
   Neon:      postgresql://USER:PASSWORD@HOST-pooler.REGION.neon.tech/neondb?sslmode=require
   SafariSmart: postgresql+psycopg://USER:PASSWORD@HOST-pooler.REGION.neon.tech/neondb?sslmode=require
   ```

5. Store the converted value as Render's secret `DATABASE_URL`. Never paste it into GitHub, logs, screenshots, or this document.

Production startup rejects the wrong driver and rejects a Neon hostname without a TLS-enforcing `sslmode`. The Docker command applies Alembic migrations and the repeatable five-destination seed before starting Uvicorn. A failed migration stops deployment instead of serving against an unknown schema.

Official references: [Neon connection pooling](https://neon.com/blog/postgres-support-case-recap) and [TLS connection guidance](https://neon.com/blog/oops-proof-your-vibe-code-with-neon-because-mistakes-happen).

## 3. Configure required application secrets

The Blueprint generates `AUTH_SECRET_KEY`. Do not replace it with a memorable password or reuse an operator password. Confirm these values in Render:

| Variable | Required value |
| --- | --- |
| `APP_ENV` | `production` |
| `APP_DEBUG` | `false` |
| `DATABASE_URL` | Secret Neon pooled URL using `postgresql+psycopg` and `sslmode=require` |
| `AUTH_SECRET_KEY` | Render-generated random secret (at least 32 characters) |
| `FRONTEND_ORIGINS` | The exact final `https://…onrender.com` origin, without a trailing slash |
| `AI_PROVIDER` | `fallback` unless a genuinely usable free model endpoint is separately proven |
| `FORWARDED_ALLOW_IPS` | `*` only because the Render service is reached through Render's trusted proxy; use a narrower proxy range elsewhere |

Do not put a demo operator password in Render environment values exposed to frontend builds. Bootstrap an operator only through an approved administrative process with an explicitly supplied secret; there is no public registration route or frontend default password.

## 4. Verify a Resend sender and enable email

1. In Resend, add a domain the owner controls.
2. Add the DNS records shown by Resend and wait until sending capability is **Verified**.
3. Create a restricted API key suitable for sending transactional email.
4. Choose a sender address on that verified domain, such as `bookings@your-domain.example`.
5. Set these Render secrets/settings:

   ```dotenv
   EMAIL_ENABLED=true
   RESEND_API_KEY=<secret Resend key>
   RESEND_FROM_EMAIL=bookings@your-verified-domain.example
   RESEND_FROM_NAME=SafariSmart AI Concierge
   ```

SafariSmart calls `POST https://api.resend.com/emails` and supplies its durable outbox key as Resend's `Idempotency-Key`. A successful response means provider acceptance, not inbox delivery. If domain verification or credentials are not ready, set `EMAIL_ENABLED=false`, remove the secret values, and redeploy; email jobs remain durable and the success screen truthfully says external email is unavailable.

Official references: [Resend HTTPS send example](https://resend.com/aws-lambda), [provider idempotency keys](https://resend.com/changelog/idempotency-keys), and [domain verification workflow](https://resend.com/changelog/domain-verification-events).

## 5. Choose Africa's Talking Sandbox or live SMS

Leave `SMS_ENABLED=false` until the chosen environment is fully configured.

Sandbox demonstration:

```dotenv
SMS_ENABLED=true
SMS_PROVIDER=africastalking
AFRICASTALKING_ENVIRONMENT=sandbox
AFRICASTALKING_USERNAME=sandbox
AFRICASTALKING_API_KEY=<secret Sandbox key>
AFRICASTALKING_SENDER_ID=
```

Sandbox acceptance and Simulator inbox evidence do **not** prove delivery to a real handset. For live SMS, create an approved production application, comply with country/sender requirements, fund the account, set `AFRICASTALKING_ENVIRONMENT=production`, use the production username/key, and configure an approved sender only when applicable. SafariSmart never falls back from SMS to email or from email to SMS.

See [sms-notifications.md](sms-notifications.md) for the fixed templates and Simulator procedure.

## 6. Understand notification dispatch on Render Free

The booking row, audit row, and one selected-channel notification row commit in one database transaction. The HTTP response never waits for Resend or Africa's Talking.

After commit, the active web process triggers a bounded drain. While the instance remains awake, it checks a small due batch every 30 seconds. On each restart or wake, it immediately drains another bounded batch. Row leases, `FOR UPDATE SKIP LOCKED`, attempt counts, controlled errors, and exponential retry remain in PostgreSQL.

Render Free can spin down after inactivity and provides no free background worker. Therefore notification delivery is best-effort: jobs remain safe while asleep but cannot be submitted until the web instance wakes. Do not add fake keep-alive requests. Dedicated supervised worker hosting and authenticated delivery webhooks remain the production upgrade path.

[Render's Free documentation](https://render.com/docs/free) describes spin-down, ephemeral filesystems, blocked SMTP ports, and the absence of free background-worker compute. SafariSmart uses the Resend HTTPS API, not SMTP.

## 7. Verify the public deployment

After Render reports **Live**, replace `APP_URL` below with the actual public HTTPS origin:

```bash
APP_URL=https://your-service.onrender.com
curl --fail --show-error "$APP_URL/api/health"
curl --fail --show-error "$APP_URL/api/v1/destinations?limit=5"
```

Then verify in a private browser window:

1. `/` and a direct refresh of `/planner` both load the React app.
2. The catalog shows exactly the five curated seeded destinations.
3. A Zanzibar-only five-day plan contains only Zanzibar.
4. The chat remembers recent turns within one tab and clears with **New chat**.
5. Submit one synthetic email-preference booking and confirm the returned reference appears on screen and in the fixed email template; verify only provider acceptance unless a delivery event is independently available.
6. Submit one synthetic phone-preference booking only if Sandbox/live SMS is configured; in Sandbox, inspect the Simulator and describe it as Sandbox evidence.
7. Log in with a privately bootstrapped synthetic operator, verify the organization-scoped queue, and log out. Never place the password in screenshots or browser source.
8. Confirm anonymous `GET /api/v1/operator/bookings` returns `401` and anonymous booking detail remains unavailable.

Do not use real customer contact details for hackathon verification.

## 8. Recovery and rollback

- **Build failure:** inspect the first failing Render build step; do not bypass GitHub checks. Fix, test, commit, and redeploy.
- **Startup/migration failure:** keep the failed instance offline, confirm the Neon URL and migration error, then deploy a corrected commit. Do not point tests at the production database.
- **Provider failure:** disable only the affected channel (`EMAIL_ENABLED=false` or `SMS_ENABLED=false`) and redeploy. Booking submissions remain available and visibly report external notifications as unavailable.
- **Bad application deploy:** in Render **Deploys**, choose a recent successful deploy and **Rollback to this deploy**. Dashboard rollback disables auto-deploys; re-enable them only after the defect is fixed. See [Render rollbacks](https://render.com/docs/rollbacks).
- **Database recovery:** prefer a Neon branch/restore procedure and a reviewed forward migration. Do not casually run `alembic downgrade`; this migration's downgrade intentionally removes queued email rows before restoring the SMS-only constraint.
- **Compromised secret:** rotate it in the provider and Render, redeploy, invalidate affected credentials, and review logs without copying secret values.

Record the deployed commit SHA and actual URL only after the public checks above pass.
