# SafariSmart AI Concierge

SafariSmart AI Concierge is an AI-powered tourism and hospitality platform created by Gloria Beneth Mbilinyi for the Africa's Talking Open Hackathon 2026 in Dar es Salaam, Tanzania.

The platform is being designed to help travellers discover destinations, request bookings, and receive assistance through the web, SMS, and USSD. Tour operators will be able to manage requests from a React dashboard.

## Project status

Phase 4 Step 2 adds consent-aware booking SMS notifications and an Africa's Talking Sandbox integration to the database-backed catalog, booking, and secure operator-management platform. Concierge AI, the frontend, live inventory, payments, verified customer access, inbound SMS, and USSD remain planned work.

The current API provides:

- A modular FastAPI application with environment-based settings
- `GET /api/health` for service health checks
- A searchable catalog of curated Tanzanian destinations
- Idempotent booking request submission with consent and contact validation
- Argon2 password hashing and short-lived signed operator access tokens
- Organization-scoped operator queues, booking detail, and audited decisions
- Clearly labelled synthetic quote and confirmation demonstrations
- PostgreSQL models and Alembic migrations
- An authorized booking status workflow with audit history
- English and Swahili booking SMS templates with consent and phone-preference checks
- A transactional SMS outbox with idempotency, worker leases, retries, and delivery states
- A sandbox-first Africa's Talking adapter and explicit Simulator test command
- Isolated unit tests and PostgreSQL integration testing in GitHub Actions

## Technology stack

- Python 3.12 and FastAPI
- React and TypeScript
- PostgreSQL
- LLM integration
- Africa's Talking SMS and USSD APIs
- Docker

## Repository layout

```text
.
|-- backend/       FastAPI application and tests
|-- database/      Database migrations and seeds
|-- docs/          Architecture and engineering documentation
|-- frontend/      React and TypeScript application
|-- .env.example   Safe configuration template
`-- AGENTS.md      Engineering and Git workflow standards
```

## Local backend setup

### Prerequisites

- Python 3.12
- Git
- PostgreSQL 14 or newer for local application and integration-test use

Node.js and Docker are not required for the current backend. Most automated tests create isolated SQLite databases; the PostgreSQL integration test runs when `TEST_DATABASE_URL` is supplied and otherwise reports a skip.

### Install

From the repository root, create and activate a virtual environment:

```bash
python -m venv .venv
```

On macOS or Linux:

```bash
source .venv/bin/activate
```

On Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Install the backend and development dependencies:

```bash
python -m pip install --upgrade pip
python -m pip install -e "backend[dev]"
```

Create a local environment file from the safe template:

```bash
cp .env.example .env
```

On Windows PowerShell, use `Copy-Item .env.example .env` instead. Set `DATABASE_URL` to a local PostgreSQL database, for example:

```dotenv
DATABASE_URL=postgresql+psycopg://safarismart:<password>@localhost:5432/safarismart
```

Leave other external-service credentials as placeholders until those integrations are configured. The `.env` file is ignored by Git.

Generate an unpredictable local signing key and place it in `.env` as `AUTH_SECRET_KEY`. This command prints a suitable value without storing one in the repository:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Authentication is unavailable when this value is blank in development. Staging and production refuse to start without a strong signing key and an explicitly configured database URL; debug mode is also rejected there.

Apply the database migration from the backend directory:

```bash
cd backend
python -m alembic upgrade head
```

Seed the five curated destinations. The command is repeatable and inserts only missing records:

```bash
python -m app.seed.destinations
```

Create a local synthetic operator only after setting an explicit development password. Never use this account or password in production.

On macOS or Linux:

```bash
export SAFARISMART_BOOTSTRAP_PASSWORD='<generated-local-password>'
python -m app.cli.bootstrap_operator \
  --operator-name "SafariSmart Synthetic Safaris" \
  --operator-slug "safarismart-synthetic-safaris" \
  --email "demo.operator@example.test" \
  --full-name "Demo Operator" \
  --assign-demo-destinations
unset SAFARISMART_BOOTSTRAP_PASSWORD
```

On Windows PowerShell:

```powershell
$env:SAFARISMART_BOOTSTRAP_PASSWORD = '<generated-local-password>'
python -m app.cli.bootstrap_operator `
  --operator-name "SafariSmart Synthetic Safaris" `
  --operator-slug "safarismart-synthetic-safaris" `
  --email "demo.operator@example.test" `
  --full-name "Demo Operator" `
  --assign-demo-destinations
Remove-Item Env:SAFARISMART_BOOTSTRAP_PASSWORD
```

The command is development-only, requires the password through an environment variable instead of a command-line argument, and refuses to attach demo credentials to a non-demo operator.

Return to the repository root with `cd ..` before running the API command below.

### Run the API

```bash
python -m uvicorn app.main:app --app-dir backend --reload
```

The service is available at `http://127.0.0.1:8000`. Useful endpoints are:

- Health check: `http://127.0.0.1:8000/api/health`
- OpenAPI documentation: `http://127.0.0.1:8000/docs`
- Alternative API documentation: `http://127.0.0.1:8000/redoc`

Expected health response:

```json
{"status": "ok"}
```

### Run the tests

```bash
python -m pytest backend
```

The default suite uses separate temporary database files and verifies migrations, authentication, authorization, workflow rules, privacy boundaries, and repeatable seed behavior.

To include the PostgreSQL integration path, create a disposable test database, apply migrations, and expose the same URL under both settings:

```bash
cd backend
export DATABASE_URL='postgresql+psycopg://postgres:<password>@localhost:5432/safarismart_test'
export TEST_DATABASE_URL="$DATABASE_URL"
python -m alembic upgrade head
python -m pytest -v
```

Do not point `TEST_DATABASE_URL` at a database containing valuable data: the integration test clears application-domain tables before and after its run. The `Backend CI` GitHub Actions workflow performs these steps with an isolated PostgreSQL service and Python 3.12.

## SMS notifications and Sandbox testing

SMS is disabled by default. There is no public arbitrary-message endpoint. Booking creation and valid status transitions enqueue fixed, PII-minimized templates only when the customer consented and selected phone contact. Database transactions never call Africa's Talking directly; a worker claims committed outbox rows before submitting them.

For a Sandbox check, set `SMS_ENABLED=true`, keep `AFRICASTALKING_ENVIRONMENT=sandbox`, use the required `sandbox` username and your Sandbox API key, then register the designated test number in the [Africa's Talking Simulator](https://simulator.africastalking.com:1517/). From `backend/`, run:

```bash
python -m app.cli.send_sandbox_sms --simulator-number +2557XXXXXXXX
```

The command sends one fixed test message, refuses production configuration, and does not print credentials or the recipient. An accepted API response is not proof of delivery; verify the message in the Simulator inbox. See [docs/sms-notifications.md](docs/sms-notifications.md) for worker behavior, state definitions, full setup, and production requirements.

## Available API endpoints

| Method | Path | Purpose | Access |
| --- | --- | --- | --- |
| `GET` | `/api/health` | Process health check | Public |
| `GET` | `/api/v1/destinations` | Search, filter, and paginate active destinations | Public |
| `GET` | `/api/v1/destinations/{id}` | Retrieve one active destination | Public |
| `POST` | `/api/v1/bookings` | Submit a pending booking request | Public submission |
| `POST` | `/api/v1/auth/token` | Exchange operator credentials for a bearer token | Public login form |
| `GET` | `/api/v1/operator/me` | Resolve the authenticated operator identity | Operator bearer token |
| `GET` | `/api/v1/operator/bookings` | List assigned requests without customer PII | Operator bearer token |
| `GET` | `/api/v1/operator/bookings/{reference}` | View assigned request detail and audit history | Assigned operator only |
| `POST` | `/api/v1/operator/bookings/{reference}/quote` | Create a synthetic demo quote | Assigned demo operator only |
| `POST` | `/api/v1/operator/bookings/{reference}/reject` | Reject from a permitted state with a reason | Assigned operator only |
| `POST` | `/api/v1/operator/bookings/{reference}/confirm` | Confirm only after verified customer acceptance | Assigned operator only |

Destination list query parameters are `q`, `region`, `category`, `featured`, `limit`, and `offset`. Supported categories are `beach`, `conservation_area`, `mountain`, and `national_park`.

Booking submissions require an `Idempotency-Key` header between 8 and 128 characters. Repeating the same key and normalized request returns the original booking reference; reusing it for different input returns `409 Conflict`.

Example request using future travel dates:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/bookings \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: traveller-request-0001" \
  -d '{
    "destination_id": "<destination-uuid>",
    "travel_start_date": "2027-07-10",
    "travel_end_date": "2027-07-15",
    "party_size": 2,
    "customer_name": "Amina Traveller",
    "customer_phone": "+255712345678",
    "customer_contact_preference": "phone",
    "customer_consent": true
  }'
```

The response contains the booking reference, pending status, destination, travel dates, party size, and creation timestamp. It never returns customer contact information. A booking reference is not proof of customer identity, so public lookup and customer action endpoints remain unavailable.

### Operator authentication and requests

There is no public operator registration endpoint. After a development account has been bootstrapped, exchange its email and local password using the OAuth2 password form:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/auth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  --data-urlencode "username=<operator-email>" \
  --data-urlencode "password=<local-password>"
```

Use the returned short-lived token as a bearer credential:

```bash
curl http://127.0.0.1:8000/api/v1/operator/me \
  -H "Authorization: Bearer <access-token>"

curl http://127.0.0.1:8000/api/v1/operator/bookings \
  -H "Authorization: Bearer <access-token>"
```

The queue response intentionally omits customer contact data. Assigned booking detail is available only to the owning operator organization; missing and cross-organization references both return `404`.

Synthetic demo operators can exercise quote and decision actions:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/operator/bookings/<reference>/quote \
  -H "Authorization: Bearer <access-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "amount_minor": 250000,
    "currency": "TZS",
    "expires_at": "<future-ISO-8601-timestamp>",
    "terms": "Synthetic demonstration terms only."
  }'
```

Quotes and confirmation states are demonstrations only: they do not represent live availability, a real operator offer, payment, or a real-world reservation. Direct confirmation from `pending_availability` is rejected. Because verified customer access is deferred, there is currently no public HTTP path for a customer to accept a quote and move it to `pending_confirmation`.

## Configuration

Runtime settings are read from environment variables and, for local development, the root `.env` file.

| Variable | Purpose | Current default |
| --- | --- | --- |
| `APP_NAME` | Name shown in generated API metadata | `SafariSmart AI Concierge` |
| `APP_ENV` | Runtime environment: development, test, staging, or production | `development` |
| `APP_DEBUG` | FastAPI debug mode | `false` |
| `API_V1_PREFIX` | Prefix for the current API router | `/api` |
| `DATABASE_URL` | SQLAlchemy PostgreSQL connection string | `postgresql+psycopg://localhost/safarismart` |
| `AUTH_SECRET_KEY` | Strong secret used to sign operator access tokens | Blank in development; required in staging/production |
| `AUTH_ACCESS_TOKEN_EXPIRE_MINUTES` | Operator token lifetime from 5 to 1,440 minutes | `30` |
| `AUTH_ISSUER` | Required access-token issuer | `safarismart-api` |
| `AUTH_AUDIENCE` | Required access-token audience | `safarismart-operator` |
| `SMS_ENABLED` | Explicitly enable provider-backed SMS sending | `false` |
| `AFRICASTALKING_ENVIRONMENT` | Provider environment: sandbox or production | `sandbox` |
| `AFRICASTALKING_USERNAME` | `sandbox` in test; live app username in production | Blank |
| `AFRICASTALKING_API_KEY` | Secret API credential loaded as a redacted value | Blank |
| `AFRICASTALKING_SENDER_ID` | Optional registered sender ID | Blank |
| `LLM_API_KEY` | Future language-model provider credential | Not connected yet |

Never commit a populated `.env` file or any credential.

## Current limitations

- Catalog entries are curated reference content; they do not claim live availability, prices, or operator partnerships.
- Operator accounts are provisioned out of band; the included bootstrap is development-only and creates synthetic data.
- Customer lookup, quote acceptance, and cancellation remain deferred until a verified account or out-of-band challenge channel exists. See [docs/customer-booking-access.md](docs/customer-booking-access.md).
- Operator quote data is synthetic and does not integrate with inventory, payment, or reservation providers.
- Access tokens are stateless; per-user `token_version` supports revocation, but password reset, MFA, key rotation, and a production identity administration flow are not implemented.
- The outbox worker service still needs deployment scheduling or a dedicated worker process.
- Delivery-report persistence is internal; a provider-authenticated callback endpoint is deferred until callback controls are designed.
- Sandbox acceptance must be verified manually in the Simulator and is not real handset delivery.
- Payments, AI concierge behavior, frontend screens, inbound SMS, and USSD remain outside the current phase.

## Architecture

See [docs/architecture.md](docs/architecture.md) for the proposed components, API boundaries, booking workflow, and Africa's Talking integration design.

## Author

Gloria Beneth Mbilinyi
