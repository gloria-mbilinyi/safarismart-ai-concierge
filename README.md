# SafariSmart AI Concierge

SafariSmart AI Concierge is an AI-powered tourism and hospitality platform created by Gloria Beneth Mbilinyi for the Africa's Talking Open Hackathon 2026 in Dar es Salaam, Tanzania.

The platform is being designed to help travellers discover destinations, request bookings, and receive assistance through the web, SMS, and USSD. Tour operators will be able to manage requests from a React dashboard.

## Project status

Phase 2 provides a database-backed destination catalog and booking request submission workflow. Concierge AI, the frontend, authenticated booking management, live inventory, payments, SMS, and USSD remain planned work.

The current API provides:

- A modular FastAPI application with environment-based settings
- `GET /api/health` for service health checks
- A searchable catalog of curated Tanzanian destinations
- Idempotent booking request submission with consent and contact validation
- PostgreSQL models and Alembic migrations
- An internal, authorized booking status workflow with audit history
- Isolated database, migration, seed, validation, and endpoint tests

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
- PostgreSQL 14 or newer for local application use

Node.js and Docker are not required for the current backend. The automated test suite creates isolated SQLite databases and does not require a running PostgreSQL server.

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

Apply the database migration from the backend directory:

```bash
cd backend
python -m alembic upgrade head
```

Seed the five curated destinations. The command is repeatable and inserts only missing records:

```bash
python -m app.seed.destinations
cd ..
```

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

The suite uses a separate temporary database file for each test and verifies the Alembic upgrade, schema parity, downgrade, and repeatable seed behavior.

## Available API endpoints

| Method | Path | Purpose | Access |
| --- | --- | --- | --- |
| `GET` | `/api/health` | Process health check | Public |
| `GET` | `/api/v1/destinations` | Search, filter, and paginate active destinations | Public |
| `GET` | `/api/v1/destinations/{id}` | Retrieve one active destination | Public |
| `POST` | `/api/v1/bookings` | Submit a pending booking request | Public submission |

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

The response contains the booking reference, pending status, destination, travel dates, party size, and creation timestamp. It never returns customer contact information. Booking lookup and status-management endpoints are intentionally unavailable until secure customer and operator authentication is implemented.

## Configuration

Runtime settings are read from environment variables and, for local development, the root `.env` file.

| Variable | Purpose | Current default |
| --- | --- | --- |
| `APP_NAME` | Name shown in generated API metadata | `SafariSmart AI Concierge` |
| `APP_ENV` | Runtime environment: development, test, staging, or production | `development` |
| `APP_DEBUG` | FastAPI debug mode | `false` |
| `API_V1_PREFIX` | Prefix for the current API router | `/api` |
| `DATABASE_URL` | SQLAlchemy PostgreSQL connection string | `postgresql+psycopg://localhost/safarismart` |
| `AFRICASTALKING_USERNAME` | Future Africa's Talking account or sandbox username | Not connected yet |
| `AFRICASTALKING_API_KEY` | Future Africa's Talking API credential | Not connected yet |
| `LLM_API_KEY` | Future language-model provider credential | Not connected yet |

Never commit a populated `.env` file or any credential.

## Current limitations

- Catalog entries are curated reference content; they do not claim live availability, prices, or operator partnerships.
- A submitted booking remains `pending_availability` until an authorized operator workflow is available.
- Booking detail and status-management APIs are deferred because customer and operator authentication is not implemented.
- The workflow service enforces state and authorization rules internally, but it is not exposed over HTTP.
- The automated suite verifies migrations on isolated SQLite databases; PostgreSQL integration testing should be added to CI when a disposable PostgreSQL service is available.
- Payments, AI concierge behavior, frontend screens, SMS, and USSD are outside Phase 2.

## Architecture

See [docs/architecture.md](docs/architecture.md) for the proposed components, API boundaries, booking workflow, and Africa's Talking integration design.

## Author

Gloria Beneth Mbilinyi
