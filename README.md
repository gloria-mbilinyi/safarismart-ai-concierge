# SafariSmart AI Concierge

SafariSmart AI Concierge is an AI-powered tourism and hospitality platform created by Gloria Beneth Mbilinyi for the Africa's Talking Open Hackathon 2026 in Dar es Salaam, Tanzania.

The platform is being designed to help travellers discover destinations, request bookings, and receive assistance through the web, SMS, and USSD. Tour operators will be able to manage requests from a React dashboard.

## Project status

Phase 1 establishes the repository standards, backend application foundation, health monitoring, and system architecture. The full concierge, booking, frontend, database, and Africa's Talking integrations are planned but are not implemented yet.

The current API provides:

- A modular FastAPI application with environment-based settings
- `GET /api/health` for service health checks
- Automated endpoint tests

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

PostgreSQL, Node.js, and Docker are not required for the current health endpoint. They will be required as their respective components are implemented.

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

On Windows PowerShell, use `Copy-Item .env.example .env` instead. Leave external-service credentials as placeholders until those integrations are configured. The `.env` file is ignored by Git.

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

## Configuration

Runtime settings are read from environment variables and, for local development, the root `.env` file.

| Variable | Purpose | Current default |
| --- | --- | --- |
| `APP_NAME` | Name shown in generated API metadata | `SafariSmart AI Concierge` |
| `APP_ENV` | Runtime environment: development, test, staging, or production | `development` |
| `APP_DEBUG` | FastAPI debug mode | `false` |
| `API_V1_PREFIX` | Prefix for the current API router | `/api` |
| `DATABASE_URL` | Future PostgreSQL connection string | Not connected yet |
| `AFRICASTALKING_USERNAME` | Future Africa's Talking account or sandbox username | Not connected yet |
| `AFRICASTALKING_API_KEY` | Future Africa's Talking API credential | Not connected yet |
| `LLM_API_KEY` | Future language-model provider credential | Not connected yet |

Never commit a populated `.env` file or any credential.

## Architecture

See [docs/architecture.md](docs/architecture.md) for the proposed components, API boundaries, booking workflow, and Africa's Talking integration design.

## Author

Gloria Beneth Mbilinyi
