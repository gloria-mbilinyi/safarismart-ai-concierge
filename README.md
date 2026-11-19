# SafariSmart AI Concierge

![SafariSmart AI Concierge logo](docs/assets/safarismart-marketplace-logo.svg)

SafariSmart is a bilingual tourism discovery and booking-request MVP built by Gloria Beneth Mbilinyi for the Africa's Talking Open Hackathon 2026. Travellers can explore five curated Tanzanian destinations, generate a grounded trip idea, submit a consent-aware request, and receive status notifications. A synthetic operator dashboard demonstrates the protected review workflow without claiming live inventory, partnerships, prices, payments, or real reservations.

## MVP status

The complete local demo is implemented:

- Responsive React and TypeScript traveller and operator experiences
- Searchable destination catalog for Serengeti, Ngorongoro, Kilimanjaro, Zanzibar, and Tarangire with responsive, locally served licensed photography
- Context-aware English/Kiswahili concierge chat that recognizes all 31 Tanzanian regions while keeping regional discovery separate from the five bookable catalog destinations
- Optional zero-cost local Ollama ranking with a deterministic fallback and developer-only mode diagnostics
- TZS budget context that never invents or estimates prices
- Idempotent public booking requests with consent and contact validation
- Argon2 operator authentication, signed short-lived tokens, organization isolation, and audited workflow decisions
- Transactional selected-channel outbox with Resend email, Africa's Talking SMS, provider idempotency where supported, retries, and truthful availability states
- Fast, read-only bilingual USSD destination discovery with input validation and per-session rate limiting
- PostgreSQL, SQLAlchemy 2.x, Alembic, Docker Compose, a single-image Marketplace package, and GitHub Actions

This remains a hackathon prototype. Catalog content is curated reference data. A synthetic quote or confirmation in the demo is not a real-world offer or reservation.

## Architecture and layout

```text
backend/                 FastAPI app, migrations, workers, CLIs, and tests
frontend/                React/TypeScript/Vite web app and tests
  public/images/         Optimized local destination photography
database/                Database notes and seed guidance
docs/                    Architecture, demo, channel, and release runbooks
marketplace/Dockerfile   Single-image Marketplace build
render.yaml              Render Free Docker Blueprint (secrets stay dashboard-supplied)
compose.yaml             Local web/API/PostgreSQL stack
.env.example             Safe configuration template
```

See [architecture.md](docs/architecture.md), [tanzania-regional-knowledge.md](docs/tanzania-regional-knowledge.md), [render-deployment.md](docs/render-deployment.md), [DEMO.md](docs/DEMO.md), and [RELEASE_CHECKLIST.md](docs/RELEASE_CHECKLIST.md) for the implementation, regional sources, deployment, exact demo flow, and evidence status.

The destination catalog uses ten local WebP derivatives: 640px and 1280px variants for each curated place. Cards choose an appropriate source with `srcset`, lazy-load offscreen images, preserve a 16:9 layout, and show an accessible fallback if an asset fails. Photographer, source, transformation, and Creative Commons details are recorded in [image-credits.md](docs/image-credits.md) and displayed with each photograph.

## Native local setup

Prerequisites: Python 3.12, Node.js 24, npm, Git, and PostgreSQL 14 or newer.

From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e "backend[dev]"
Copy-Item .env.example .env
```

Edit the ignored `.env` and set a local PostgreSQL `DATABASE_URL` and a random `AUTH_SECRET_KEY` of at least 32 characters. Generate a signing value without storing it in source control:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Apply migrations and load the repeatable catalog seed:

```powershell
Set-Location backend
python -m alembic upgrade head
python -m app.seed.destinations
Set-Location ..
```

Create the explicitly synthetic development operator. The command is repeatable only when the same identity and password are supplied; it never silently resets a password.

```powershell
$env:SAFARISMART_BOOTSTRAP_PASSWORD = '<generated-local-password>'
Set-Location backend
python -m app.cli.bootstrap_operator --operator-name "SafariSmart Synthetic Safaris" --operator-slug "safarismart-synthetic-safaris" --email "demo.operator@example.test" --full-name "Demo Operator" --assign-demo-destinations
Remove-Item Env:SAFARISMART_BOOTSTRAP_PASSWORD
Set-Location ..
```

Start the API and web app in separate terminals:

```powershell
python -m uvicorn app.main:app --app-dir backend --reload
```

```powershell
Set-Location frontend
npm ci
npm run dev
```

Open `http://127.0.0.1:5173`. API docs are at `http://127.0.0.1:8000/docs`, and health is at `http://127.0.0.1:8000/api/health`.

## Docker Compose demo

Docker is optional for native development. Put URL-safe random values in the ignored `.env` for `POSTGRES_PASSWORD` and `AUTH_SECRET_KEY`, then run:

```powershell
docker compose up --build --detach db api frontend
docker compose ps
```

Open `http://127.0.0.1:8080`. Stop the stack with `docker compose down`; add `--volumes` only when intentionally deleting the disposable local database. The optional notification dispatcher starts with `docker compose --profile sms up --build sms-worker` after its provider settings are configured; the service name remains `sms-worker` for Compose compatibility.

The Marketplace/Render-oriented single image serves the compiled frontend and FastAPI from one process:

```powershell
docker build --file marketplace/Dockerfile --tag safarismart-ai-concierge:0.1.0 .
```

It requires an external PostgreSQL `DATABASE_URL` and strong `AUTH_SECRET_KEY`. For the public hackathon path, follow the exact [Render Free + Neon runbook](docs/render-deployment.md). Full registry steps and draft listing copy are in [marketplace-submission.md](docs/marketplace-submission.md).

## Concierge modes

`AI_PROVIDER=fallback` is the default and needs no model, API key, paid API, or network access. It deterministically handles greetings, recognizes the official 31-region set, answers from source-attributed regional highlights, and ranks active catalog rows. The API retains `rule_based_fallback` as developer diagnostics, but the traveller UI does not expose implementation labels.

For an optional local Ollama service:

```dotenv
AI_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:3b
```

Ollama may rank or rephrase only known catalog destination facts. Regional facts remain deterministic and source-attributed. All descriptions, itinerary fields, safety wording, and booking boundaries still come from validated application data. Invalid or unavailable model output falls back safely.

## Email, SMS, and USSD

Every consented booking atomically creates exactly one notification job matching the selected channel. Email uses the Resend HTTPS API; SMS uses the existing Africa's Talking adapter. An idempotent booking replay returns the original reference and never creates a second job. Provider calls happen only after commit, and API acceptance is stored separately from confirmed delivery.

When a provider is not configured, the booking still succeeds and the bilingual success page says that external notification is unavailable. While a web instance is active, bounded drains process due jobs; jobs remain durable in PostgreSQL while a Render Free instance sleeps. Configuration and limitations are in [render-deployment.md](docs/render-deployment.md).

SMS is disabled by default. `SMS_PROVIDER=local` validates messages without contacting a provider and is accepted only in development or test. To drain locally queued notifications without revealing phone numbers or message bodies:

```powershell
Set-Location backend
python -m app.cli.notification_worker --drain
```

Use `python -m app.cli.notification_worker` for continuous polling when dedicated worker compute is available. Africa's Talking Sandbox configuration and the fixed-message Simulator check are documented in [sms-notifications.md](docs/sms-notifications.md).

Africa's Talking posts form-encoded USSD requests to `POST /api/v1/ussd`. The read-only menu supports English and Kiswahili and does not store the subscriber number or expose booking details. See [ussd-tourism.md](docs/ussd-tourism.md).

## API surface

| Method | Path | Purpose | Access |
| --- | --- | --- | --- |
| `GET` | `/api/health` | Process health | Public |
| `GET` | `/api/v1/destinations` | Search/filter active catalog | Public |
| `GET` | `/api/v1/destinations/{id}` | Destination detail | Public |
| `POST` | `/api/v1/concierge/plan` | Grounded 1–14 day trip idea | Public |
| `POST` | `/api/v1/concierge/chat` | Bounded catalog and Tanzania-region concierge | Public |
| `POST` | `/api/v1/bookings` | Idempotent pending request | Public submission |
| `POST` | `/api/v1/ussd` | Africa's Talking read-only menu callback | Public callback |
| `POST` | `/api/v1/auth/token` | Operator login | Existing users only |
| `GET` | `/api/v1/operator/me` | Current operator identity | Bearer token |
| `GET` | `/api/v1/operator/bookings` | Organization queue, PII-minimized | Bearer token |
| `GET` | `/api/v1/operator/bookings/{reference}` | Assigned request and audit detail | Owning organization |
| `POST` | `/api/v1/operator/bookings/{reference}/quote` | Synthetic demo quote | Synthetic operator |
| `POST` | `/api/v1/operator/bookings/{reference}/reject` | Valid audited rejection | Owning organization |
| `POST` | `/api/v1/operator/bookings/{reference}/confirm` | Confirm only from `pending_confirmation` | Owning organization |

Booking submission requires a unique `Idempotency-Key` header and is protected by a per-client, in-process burst limit. The public response omits customer contact information and reports only the selected notification channel plus `queued` or `unavailable`; it never claims delivery. There is deliberately no unauthenticated booking lookup, customer quote acceptance, arbitrary notification sending, operator registration, or direct confirmation from `pending_availability`.

## Tests and CI

Run backend and frontend checks:

```powershell
.\.venv\Scripts\python.exe -m pytest backend -q
Set-Location frontend
npm test
npm run build
npm audit --omit=dev --audit-level=high
```

Most backend tests use isolated SQLite databases. Set `TEST_DATABASE_URL` only to a disposable migrated PostgreSQL database to enable the destructive PostgreSQL integration case. GitHub Actions provides its own isolated PostgreSQL service, runs Alembic, executes the backend and frontend suites, audits production frontend dependencies, and smoke-tests the Compose and single-image builds.

## Security and known limits

- Never commit `.env`, credentials, customer data, tokens, or generated signing material.
- Staging and production reject missing/weak signing keys, implicit database defaults, debug mode, the local SMS provider, the wrong PostgreSQL driver, and Neon URLs without TLS.
- Customer booking lookup and actions remain deferred until a verified account or one-time out-of-band challenge is implemented; a reference, email, or phone number is not proof of identity.
- Regional recognition is travel discovery, not inventory: only the five active catalog records can produce a booking-form target.
- Regional profiles intentionally omit live hotel prices, availability, opening hours, transport times, and any attraction detail that has not been source-checked.
- The demo has no live inventory, accommodation/transport catalog, payments, real operator integrations, durable customer sessions, MFA, password reset, or verified delivery-report callback.
- Public booking and USSD limiters are per API process; multi-instance production should add trusted edge controls and a shared limiter.
- Render Free notification dispatch is best-effort while the web instance is awake; PostgreSQL retains due jobs during sleep, but a dedicated worker remains the production upgrade.
- A provider API acceptance is not proof of handset delivery, payment, operator acceptance, or reservation.

## Hackathon handoff

- [3-minute demo and exact Windows commands](docs/DEMO.md)
- [Release and evidence checklist](docs/RELEASE_CHECKLIST.md)
- [Marketplace submission draft](docs/marketplace-submission.md)
- [Render Free + Neon deployment runbook](docs/render-deployment.md)
- [Customer-access security decision](docs/customer-booking-access.md)

## Author

Gloria Beneth Mbilinyi
