# SafariSmart AI Concierge Architecture

## Implemented scope

SafariSmart is a modular-monolith hackathon MVP. One FastAPI application owns validation, catalog grounding, booking rules, operator authorization, SMS scheduling, and USSD menus; PostgreSQL is the system of record. React is deployed either behind Nginx in the local Compose stack or as static files served by FastAPI in the single-image Marketplace build.

The product intentionally submits **booking requests**, not real reservations. It has no live inventory, payments, provider booking API, or verified customer account. All operator quotes and confirmations available in the demo are visibly synthetic.

## Runtime view

```mermaid
flowchart LR
    Traveller[Traveller browser] --> Web[React web app]
    Operator[Operator browser] --> Web
    Web --> API[FastAPI API]
    ATSMS[Africa's Talking SMS] <--> Dispatcher[Notification dispatcher]
    Resend[Resend HTTPS email] <--> Dispatcher
    ATUSSD[Africa's Talking USSD] --> API

    API --> Catalog[Destination catalog]
    API --> Concierge[Grounded concierge]
    API --> Booking[Booking service]
    API --> Auth[Operator security]
    API --> USSD[Deterministic USSD menus]
    Concierge --> OptionalLLM[Optional local Ollama ranking]
    Catalog --> DB[(PostgreSQL)]
    Booking --> DB
    Auth --> DB
    USSD --> DB
    Dispatcher --> DB

    subgraph Deployment choices
        Compose[Nginx + API + PostgreSQL]
        Marketplace[One frontend/API image + external PostgreSQL]
    end
```

## Component boundaries

- **React client:** landing page, catalog, planner/chat, booking form, operator login, and protected dashboard. It never stores operator passwords; the short-lived access token is kept in per-tab `sessionStorage`, removed on sign-out, and never placed in URLs or long-lived `localStorage`.
- **FastAPI transport:** Pydantic validation, route-level dependencies, CORS allowlist, form parsing, and response serialization.
- **Catalog service:** active destinations, search/filter/pagination, repeatable seed data, and public reference content.
- **Concierge service:** deterministic intent handling, bounded recent context, explicit destination selection, and optional prose/ranking through narrow provider interfaces. It cannot invoke booking actions.
- **Booking service:** idempotent public submission and the authoritative state machine. It writes state and history atomically.
- **Operator security:** Argon2 password verification, signed short-lived tokens with issuer/audience/expiry checks, active-account checks, token-version revocation, and organization-scoped resource lookup.
- **Notification service:** consent-aware bilingual email/SMS templates and a transactional selected-channel outbox. Provider calls happen after the booking transaction commits; no channel fallback is allowed.
- **USSD service:** synchronous, deterministic English/Kiswahili menus derived from cumulative input. It performs no LLM or booking lookup.
- **Provider adapters:** Resend HTTPS email, Africa's Talking Sandbox/production SDK, PII-safe local SMS provider, and optional Ollama JSON ranking/prose.
- **Persistence:** SQLAlchemy 2.x sessions and explicit Alembic migrations; application startup never creates schema implicitly.

## Data model

The implemented schema contains:

- `operators`: organizations, active flag, and a synthetic-demo marker
- `operator_users`: organization identity, Argon2 password hash, active flag, token version, and timestamps
- `destinations`: curated public content, category, region, featured/active state, and optional operator assignment
- `booking_requests`: reference, destination, assigned organization, travel data, minimized customer/contact data, notification language, consent, idempotency fingerprint, current status, and timestamps
- `booking_status_history`: old/new status, actor type/reference, reason, and timestamp
- `booking_quotes`: one synthetic quote per booking, amount/currency/expiry/terms, and explicit demo disclaimer
- `booking_notifications`: selected email/SMS channel, deduplicated event, safe template metadata, acceptance/delivery state, attempt/lease fields, controlled error code, provider identifier, and timestamps

`DATABASE_URL` must use PostgreSQL in deployed environments. Tests use isolated temporary SQLite files for speed plus a destructive PostgreSQL integration test only when `TEST_DATABASE_URL` points to a disposable database.

## Public and protected API boundaries

| Method | Path | Boundary |
| --- | --- | --- |
| `GET` | `/api/health` | Public process health |
| `GET` | `/api/v1/destinations` | Public active catalog search/filter |
| `GET` | `/api/v1/destinations/{id}` | Public active destination detail |
| `POST` | `/api/v1/concierge/plan` | Public, validated, catalog-grounded plan |
| `POST` | `/api/v1/concierge/chat` | Public, bounded catalog question |
| `POST` | `/api/v1/bookings` | Rate-limited public submission; idempotency header required |
| `POST` | `/api/v1/ussd` | Public Africa's Talking form callback; read-only |
| `POST` | `/api/v1/auth/token` | Existing operator login; no registration |
| `GET` | `/api/v1/operator/me` | Authenticated active operator identity |
| `GET` | `/api/v1/operator/bookings` | Organization-scoped PII-minimized queue |
| `GET` | `/api/v1/operator/bookings/{reference}` | Owning organization only |
| `POST` | `/api/v1/operator/bookings/{reference}/quote` | Synthetic organization only; audited |
| `POST` | `/api/v1/operator/bookings/{reference}/reject` | Valid operator state only; audited |
| `POST` | `/api/v1/operator/bookings/{reference}/confirm` | Only from `pending_confirmation`; audited |

Missing and cross-organization booking references both return `404`, preventing resource-existence leaks. There is no public booking list/detail, arbitrary SMS endpoint, customer status lookup, operator self-registration, or customer action endpoint.

## Booking workflow

```mermaid
stateDiagram-v2
    [*] --> PendingAvailability: public request
    PendingAvailability --> Quoted: synthetic operator quote
    PendingAvailability --> Rejected: operator decision
    Quoted --> PendingConfirmation: verified customer action (internal only)
    Quoted --> Expired: quote deadline
    PendingConfirmation --> Confirmed: operator decision
    PendingConfirmation --> Rejected: operator decision
    Confirmed --> Cancelled: authorized cancellation (internal only)
```

The public endpoint creates `pending_availability`, never `confirmed`. Direct operator confirmation from `pending_availability` or `quoted` is rejected. A verified-customer context is required for the internal `quoted → pending_confirmation` edge; no HTTP route exposes that edge in this MVP because a booking reference or contact detail is not identity proof.

Every accepted state transition locks the request, validates the actor/resource/state, updates the current value, writes a history row, and schedules the selected-channel notification in the same transaction. Quote expiry and rejection reasons are validated. The LLM has no path to this service.

## Grounded concierge boundary

The fallback planner is the default and works offline. It:

1. Loads active destinations from the catalog.
2. Enforces one of `single_destination`, `multiple_destinations`, or `explore_tanzania`; explicit modes cannot introduce an unselected destination.
3. Returns at most four known destinations and 1–14 itinerary days.
4. Treats TZS budget as planning context, never as a source of price estimates.
5. Emits a disclaimer that the result is not price, availability, or reservation.

Chat recognizes supported recommendation, overview, activity, duration, comparison, budget, booking-guidance, unsupported-fact, and clarification intents. The browser retains at most 20 redacted messages in per-tab `sessionStorage`; only the latest eight are returned as bounded context. The server trusts destination names only when they resolve to active catalog rows and never treats prior assistant prose as authority.

When `AI_PROVIDER=ollama`, the provider receives only allowed destination facts and a safe deterministic draft. Descriptions, safety wording, prices, availability, and booking authority remain in the application. Unknown entities, invented numbers, malformed output, timeout, or provider failure fall back to the deterministic response and report `rule_based_fallback`.

## Notification delivery architecture

```mermaid
sequenceDiagram
    participant API as Booking transaction
    participant DB as PostgreSQL outbox
    participant D as Bounded dispatcher
    participant P as Selected provider
    API->>DB: Save state + deduplicated event
    API->>DB: Commit
    D->>DB: Claim due row for configured channel with lease
    D->>DB: Commit claim
    D->>P: Submit fixed template outside transaction
    P-->>D: Provider acceptance or safe failure
    D->>DB: accepted / retry / failed
```

Scheduling and sending both require explicit consent, the matching selected channel, and a valid recipient. Fixed English/Kiswahili templates contain the booking reference and safe status but omit names, special requests, and trip details. Dispatchers use `FOR UPDATE SKIP LOCKED` on PostgreSQL, claim tokens, leases, bounded exponential retry, and PII-free result logs.

Resend receives SafariSmart's deterministic event key as its provider `Idempotency-Key`. Africa's Talking's SDK send operation has no equivalent key, leaving a rare at-least-once crash window after acceptance. In both channels, `accepted` is distinct from `delivered`.

`SMS_PROVIDER=local` performs validation without a network call and is rejected in staging/production. `SMS_PROVIDER=africastalking` uses the official SDK and requires an internally consistent Sandbox or production credential set. Resend uses a verified sender and secret API key over HTTPS; SMTP is not used.

The web response reports `queued` only when the selected provider is configured and otherwise reports `unavailable`. It never waits on the external API. A post-commit trigger and a small in-process loop drain bounded batches while the web instance is awake and immediately after restart; jobs remain durable while Render Free sleeps. A dedicated supervised worker and authenticated delivery webhooks remain future production upgrades.

## USSD boundary

Africa's Talking sends `sessionId`, `serviceCode`, `phoneNumber`, and cumulative `text` as form fields to `/api/v1/ussd`. SafariSmart validates lengths/formats, hashes the session identifier for a process-local sliding-window limit, stores none of the submitted subscriber data, and returns an Africa's Talking-compatible `CON` or `END` body.

Destination rows are loaded only when the current menu needs them. A database error produces a generic terminal response. The endpoint never invokes the LLM, exposes customer/booking data, accepts payment, or claims availability/prices. A production edge should add a shared limiter and the strongest callback/source controls supported by the provider.

## Deployment models

### Local Compose

`compose.yaml` runs PostgreSQL 16, a FastAPI image, and an Nginx-served frontend. It uses a persistent named database volume, health checks, migrations and destination seed on API startup, and an optional `sms-worker` profile. Credentials are supplied from the ignored local environment.

### Single-image Marketplace package

`marketplace/Dockerfile` uses a Node build stage and a non-root Python 3.12 runtime. FastAPI validates and serves the compiled Vite distribution, preserves API `404` responses, applies migrations, loads repeatable seed data, respects the platform `PORT`, and exposes `/api/health`. PostgreSQL remains an external per-instance dependency.

### Render Free + Neon

The root `render.yaml` provisions one Free Docker web service using `marketplace/Dockerfile`, `/api/health`, generated signing material, and dashboard-supplied Neon/Resend secrets. The process binds Render's `PORT`. Neon production URLs must use `postgresql+psycopg`, a pooled hostname, and TLS. Migrations and repeatable destination seeding run before the server starts. React and API share one HTTPS origin.

### Configuration safety

Production rejects missing/weak `AUTH_SECRET_KEY`, the implicit local database URL, debug mode, the local SMS provider, the wrong PostgreSQL driver, Neon without TLS, and incomplete Resend credentials. Secrets belong in the runtime's secret store, not the image, repository, callback URL, logs, or frontend bundle. Database URLs are excluded from settings representations. Each instance should receive separate database and provider credentials.

## Verification

Two GitHub Actions workflows cover the project:

- Backend CI: Python 3.12, PostgreSQL service, Alembic upgrade, and the full test suite including PostgreSQL integration.
- Frontend and Container CI: Node.js 24 install/test/build/audit, Compose validation and smoke test, and single-image build.

Local verification includes the isolated backend suite, frontend tests/typecheck/build, dependency audit, migration checks, and browser smoke tests. Container execution depends on Docker availability and must not be reported as locally verified when Docker is absent.

## Deliberate limitations

- No live inventory, real operator partnership, accommodation/restaurant/transport data, payment, or external reservation API
- No customer authentication, lookup, quote acceptance, cancellation, or status history API
- No server-side durable chat history or cross-channel customer identity; browser chat history is per tab only
- No production operator administration, password reset, MFA, or automated signing-key rotation
- No authenticated delivery-report or inbound SMS callback
- Best-effort in-process notification dispatch on sleeping free hosting; no dedicated worker monitoring
- Process-local rather than distributed booking/USSD rate limiting
- Ollama is optional ranking assistance, not a source of tourism facts or booking authority

The customer-access threat decision is in [customer-booking-access.md](customer-booking-access.md); channel operations are in [sms-notifications.md](sms-notifications.md) and [ussd-tourism.md](ussd-tourism.md).
