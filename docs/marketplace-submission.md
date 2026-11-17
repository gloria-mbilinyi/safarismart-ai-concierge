# Africa's Talking Marketplace Submission Draft

> **Status: DRAFT — not published, reviewed, approved, or live.** Registry credentials, final pricing, support contact, policies, screenshots, and the explicit owner decision to submit are still required. Do not interpret this file as an Africa's Talking endorsement.

## Listing copy

- **Product name:** SafariSmart AI Concierge
- **Suggested slug:** `safarismart-ai-concierge`
- **Developer:** Gloria Beneth Mbilinyi
- **Industry:** Hospitality & Tourism
- **Africa's Talking products:** SMS and USSD
- **Source repository:** `https://github.com/gloria-mbilinyi/safarismart-ai-concierge`
- **Logo asset:** [`docs/assets/safarismart-marketplace-logo.svg`](assets/safarismart-marketplace-logo.svg)

### Short description

Bilingual Tanzania trip discovery, grounded planning, booking requests, operator review, SMS updates, and USSD access in one safe tourism MVP.

### Long description

SafariSmart AI Concierge helps travellers discover curated Tanzanian destinations through a responsive web app and low-bandwidth Africa's Talking channels. Travellers can search destination reference content, ask bounded English or Kiswahili questions, generate a grounded multi-day trip idea, and submit a consent-aware booking request. An authenticated, organization-scoped operator workspace supports audited review, synthetic quotes, rejection, and safe status progression.

The concierge works at zero model cost in deterministic fallback mode. An optional locally managed Ollama model can rank only known catalog destinations; it cannot invent inventory, prices, partnerships, or bookings. Consent-aware SMS events are written to a transactional outbox and submitted by a bounded-retry worker. The bilingual USSD menu provides fast, read-only discovery without calling an LLM or exposing customer records.

SafariSmart is packaged as a per-customer application instance backed by PostgreSQL. The current hackathon version is a demonstration: catalog entries are reference content, operator data and quotes are synthetic, and no live availability, payment, or real reservation provider is connected.

## Submission assets to prepare

- Square logo exported from the repository SVG to the dimensions/formats accepted by the submission form
- Landing page, destination explorer, planner disclaimer, booking result, and operator dashboard screenshots
- Africa's Talking Sandbox SMS and USSD evidence with credentials and personal data redacted
- Public privacy notice and terms URL approved by the owner
- Support email or support URL owned and monitored by the owner
- Final image URL in the Africa's Talking Container Registry
- Final pricing approved by the owner

Evidence capture guidance is in [DEMO.md](DEMO.md).

## Single-image build

The Marketplace artifact builds the React app and serves it with FastAPI from one non-root Python 3.12 runtime. It runs Alembic migrations and the repeatable destination seed before starting on the platform-provided `PORT`.

```bash
docker build --file marketplace/Dockerfile --tag safarismart-ai-concierge:0.1.0 .
```

For an external PostgreSQL test, create an ignored local environment file such as `.env.marketplace.local` containing strong, non-production test values:

```dotenv
APP_ENV=production
DATABASE_URL=postgresql+psycopg://<user>:<url-encoded-password>@<host>:5432/<database>
AUTH_SECRET_KEY=<at-least-32-random-characters>
FRONTEND_ORIGINS=http://127.0.0.1:8000
SMS_ENABLED=false
AI_PROVIDER=fallback
```

Then run:

```bash
docker run --rm --env-file .env.marketplace.local -p 8000:8000 safarismart-ai-concierge:0.1.0
```

Check `http://127.0.0.1:8000/` and `http://127.0.0.1:8000/api/health`. `.env.*` is ignored by Git except for the safe `.env.example`.

## Registry publishing procedure

Obtain the registry hostname, namespace, username, and password from the Marketplace submission workflow. Do not place the password in a command argument, source file, issue, screenshot, or shell script.

```bash
docker login <AT_REGISTRY_HOST> --username <AT_REGISTRY_USERNAME>
docker tag safarismart-ai-concierge:0.1.0 <AT_REGISTRY_HOST>/<AT_NAMESPACE>/safarismart-ai-concierge:0.1.0
docker push <AT_REGISTRY_HOST>/<AT_NAMESPACE>/safarismart-ai-concierge:0.1.0
```

Paste the resulting immutable, versioned image URL into the Marketplace technical section. Keep `0.1.0` for the submitted build and publish later versions under new tags. Do not publish from this repository until the owner has reviewed the image, supplied credentials, and explicitly approved the external action.

## Runtime configuration

Each installation should have an isolated database and signing secret. Secrets must use the platform's protected environment configuration rather than the image or frontend bundle.

| Variable | Required | Safe listing guidance |
| --- | --- | --- |
| `APP_ENV` | Yes | Set `production` for a Marketplace instance |
| `DATABASE_URL` | Yes | Private PostgreSQL SQLAlchemy URL; use URL-encoded credentials |
| `AUTH_SECRET_KEY` | Yes | Unique random secret, at least 32 characters; never display after entry |
| `PORT` | Platform | HTTP listen port; defaults to `8000` if absent |
| `FRONTEND_ORIGINS` | Yes | Explicit public HTTP(S) origin; wildcards are rejected |
| `AUTH_ACCESS_TOKEN_EXPIRE_MINUTES` | No | `30` by default; allowed range 5–1,440 |
| `AUTH_ISSUER` | No | Default `safarismart-api` |
| `AUTH_AUDIENCE` | No | Default `safarismart-operator` |
| `EMAIL_ENABLED` | No | Default `false`; enable only after Resend sender verification |
| `RESEND_API_KEY` | If email enabled | Protected restricted key; never expose to the browser |
| `RESEND_FROM_EMAIL` | If email enabled | Sender on a verified domain |
| `RESEND_FROM_NAME` | No | Default `SafariSmart AI Concierge` |
| `SMS_ENABLED` | No | Default `false`; enable only after provider setup |
| `SMS_PROVIDER` | If SMS enabled | Use `africastalking` in production; `local` is rejected |
| `AFRICASTALKING_ENVIRONMENT` | If SMS enabled | `sandbox` for testing or `production` for live credentials |
| `AFRICASTALKING_USERNAME` | If SMS enabled | Sandbox must be exactly `sandbox`; otherwise live app username |
| `AFRICASTALKING_API_KEY` | If SMS enabled | Protected secret; never expose to the browser |
| `AFRICASTALKING_SENDER_ID` | No | Only an approved sender identity where applicable |
| `AI_PROVIDER` | No | `fallback` (default) or `ollama` |
| `OLLAMA_BASE_URL` | If Ollama | Reachable private HTTP(S) endpoint |
| `OLLAMA_MODEL` | If Ollama | Default `qwen2.5:3b`; model must be provisioned separately |
| `OLLAMA_TIMEOUT_SECONDS` | No | Default `5`, bounded to 0.5–30 seconds |
| `BOOKING_RATE_LIMIT_PER_MINUTE` | No | Default `5` per client on one process |
| `BOOKING_RATE_LIMIT_MAX_CLIENTS` | No | Default `10000` in-memory client keys |
| `USSD_RATE_LIMIT_PER_MINUTE` | No | Default `30` per opaque session on one process |
| `USSD_RATE_LIMIT_MAX_SESSIONS` | No | Default `10000` in-memory session hashes |

`FRONTEND_DIST_PATH` is set inside the image and should not be overridden. `SMS_PROVIDER=local`, missing signing keys, the implicit local database URL, incomplete Resend configuration, and debug mode are rejected in production.

### PostgreSQL requirement

The application requires a PostgreSQL database reachable from its container. The provided image does not bundle a database. The instance identity must have permission to run the included Alembic migrations and read/write only its own SafariSmart schema/database. Use backups, TLS, connection limits, and credential rotation appropriate to the selected database service.

### Dispatcher requirement

The web image serves the API and frontend. It performs bounded post-commit, startup, and periodic notification drains while active; pending work remains durable in PostgreSQL when the instance sleeps. The same image can run a continuously supervised dispatcher when the platform supports a separate worker process:

```bash
python -m app.cli.notification_worker
```

If the Marketplace supports only one process per plugin instance, bounded best-effort dispatch is available while that process is active. Clearly disclose this limitation; leave each provider disabled until its credentials and sender are valid, and do not claim notification delivery merely because the web image is running.

## Privacy, consent, and security stance

- Booking submission requires explicit customer consent and validates the selected contact channel.
- Public responses omit names, phone numbers, email addresses, consent details, special requests, and audit history.
- Email/SMS scheduling and sending recheck consent, selected channel, and matching recipient; fixed bilingual templates minimize content and never fall back to another channel.
- Routine dispatcher and USSD paths do not log recipients, message bodies, session identifiers, or credentials.
- Operator users are provisioned out of band; there is no public self-registration.
- Operator resources are isolated by organization, with uniform not-found behavior for missing/cross-organization records.
- A booking reference, email, or phone number is not accepted as customer authentication. Customer lookup and actions are intentionally absent.
- USSD is read-only and never exposes booking status, accepts payments, or invokes the LLM.
- Deployment secrets remain server-side and must be unique per application instance.

The owner must publish a reviewed privacy notice and terms before submission. This repository document is technical guidance, not legal advice.

## Proposed pricing — owner approval required

These are **DRAFT positioning values only**. They have not been configured, offered, charged, validated with customers, or approved by Africa's Talking. Provider usage, taxes, support workload, and Marketplace billing capabilities must be reviewed first.

| Draft plan | Draft price | Frequency | Intended scope |
| --- | ---: | --- | --- |
| Explorer Sandbox | TZS 0 | Monthly | Time-limited evaluation with fallback concierge and Sandbox-only channels |
| Lodge Starter | TZS 35,000 | Monthly | One isolated instance, operator workspace, usage billed separately by provider |
| Operator Plus | TZS 95,000 | Monthly | One isolated instance plus assisted configuration; usage billed separately |

Suggested listing disclaimer: “Africa's Talking messaging/USSD usage, database/hosting, taxes, and any third-party model costs are not included unless explicitly stated.” A free plan may not satisfy the Marketplace form's commercial requirements; if at least one paid entry is mandatory, submit only an owner-approved paid plan.

## Marketplace form checklist

The current official Open Hackathon guidance describes this sequence:

1. Sign in to the Marketplace.
2. Build the application image and push it to the Africa's Talking Container Registry using the supplied credentials.
3. Choose **Create Your Own Plugin**.
4. Complete registry credentials, basic information, image URL/technical details, environment variables, Africa's Talking product and industry categorization, at least one pricing entry, and the terms/privacy confirmations.
5. Submit for review and monitor status under **Manage Plugins**.

Before pressing submit, verify:

- [ ] Owner approved listing copy, logo, screenshots, support contact, privacy URL, and terms URL
- [ ] Final image was built from the intended commit and scanned/tested
- [ ] Registry login and image push succeeded; exact immutable tag recorded
- [ ] PostgreSQL and optional worker capabilities are supported by the chosen runtime
- [ ] Production callback URLs are durable HTTPS URLs, not a Quick Tunnel
- [ ] Production Africa's Talking credentials/sender/service code are authorized for the target country
- [ ] Prices and billing description are owner-approved and accurately include/exclude usage
- [ ] No secret appears in screenshots, Git history, image layers, frontend bundle, or form prose
- [ ] Listing says “booking request” and “synthetic demo” where relevant; it does not claim live reservations

Official references checked for this draft:

- [Africa's Talking Open & WIT Hackathon Marketplace submission steps](https://community.africastalking.com/events/details/africas-talking-africas-talking-open-community-east-africa-presents-africas-talking-open-and-wit-hackathon-build-anything-nairobi-kenya/cohost-africas-talking-women-in-tech-community/)
- [Africa's Talking Marketplace Beta overview](https://blog.africastalking.com/at-marketplace-beta-early-access-for-builders-e09d2e6a7ba1)
- [Africa's Talking Sandbox setup](https://help.africastalking.com/en/articles/1170660-how-do-i-get-started-on-the-africa-s-talking-sandbox)
- [Official Africa's Talking Python SDK](https://github.com/AfricasTalkingLtd/africastalking-python)

Marketplace fields and policies can change. Recheck the live form immediately before submission.

## Manual actions that remain

1. Owner supplies/approves support contact, privacy URL, terms URL, screenshots, and final pricing.
2. Owner obtains Marketplace and registry credentials.
3. Build and test the image where Docker is available.
4. Owner explicitly approves the external registry push and Marketplace submission.
5. Configure an isolated PostgreSQL database and, if supported, a continuously supervised dispatcher process.
6. Configure a verified Resend sender and restricted key, or leave email disabled.
7. Configure durable production HTTPS callbacks and authorized Africa's Talking live products only after provider approval.

Until those actions occur, the accurate status is: **source and submission package prepared; not published or production-hosted**.
