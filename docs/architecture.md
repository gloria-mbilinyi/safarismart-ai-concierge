# SafariSmart AI Concierge Architecture

## Status and scope

This document describes both the implemented Phase 2 backend and the proposed target architecture. Phase 2 implements the FastAPI foundation, SQLAlchemy persistence, Alembic migrations, a public destination catalog, idempotent booking request submission, and an internal booking workflow. Components marked as planned should guide later phases rather than be treated as deployed functionality.

The architecture favors a modular monolith for the hackathon: one deployable backend with explicit internal boundaries. This keeps deployment and operations simple while allowing high-volume or integration-heavy modules to be extracted later if needed.

## Design goals

- Make tourism discovery accessible through web, SMS, and USSD channels.
- Keep booking decisions deterministic and auditable; the LLM may assist but cannot confirm a booking by itself.
- Isolate external providers behind adapters so sandbox and production implementations can be exchanged safely.
- Protect credentials and minimize stored personal data.
- Make inbound callbacks idempotent and outbound notifications observable.
- Keep USSD interactions short and responsive while allowing longer-running AI work on web and SMS channels.

## System components

The API, booking service, PostgreSQL persistence boundary, destination catalog, and internal workflow are implemented. The web clients, concierge, notifications, provider adapters, and Africa's Talking paths in the following target diagram remain planned.

```mermaid
flowchart LR
    Web[Traveller web app] --> API[FastAPI transport layer]
    Dashboard[Operator dashboard] --> API
    SMS[SMS user] <--> AT[Africa's Talking]
    USSD[USSD user] <--> AT
    AT --> Webhooks[SMS and USSD callbacks]
    Webhooks --> API

    API --> Concierge[Concierge service]
    API --> Booking[Booking service]
    API --> Conversation[Conversation service]
    Booking --> Notification[Notification service]

    Concierge --> LLM[LLM adapter]
    Booking --> Provider[Tour operator or inventory adapter]
    Notification --> AT

    Concierge --> DB[(PostgreSQL)]
    Booking --> DB
    Conversation --> DB
    Notification --> DB
```

### Client channels

- **Traveller web app:** destination discovery, concierge chat, and booking-request tracking.
- **Operator dashboard:** review requests, publish availability or offers, and update booking states.
- **SMS:** asynchronous, low-bandwidth concierge messages and booking notifications.
- **USSD:** short, menu-based discovery and booking-request capture on basic phones.

### Backend modules

- **Transport layer:** FastAPI routes, request validation, authentication, rate limits, and response serialization.
- **Concierge service:** conversation orchestration, retrieval of trusted tourism content, and controlled LLM calls.
- **Conversation service:** channel-neutral sessions and messages so a traveller can be assisted consistently.
- **Booking service:** booking commands, state transitions, validation, availability checks, and audit history.
- **Notification service:** message templates, delivery attempts, retry policy, and provider status updates.
- **Provider adapters:** narrow interfaces for the LLM, Africa's Talking, and tour-operator or inventory systems.
- **Persistence layer:** repositories and transactions backed by PostgreSQL.

### Initial data domains

- **Implemented:** operators, curated destinations, booking requests, traveller contact preferences and consent, booking status history, and idempotency keys.
- **Planned:** activities, accommodation inventory, offers, conversations, messages, notifications, provider identifiers, and general integration events.

## Persistence and migrations

SQLAlchemy 2.x models define operators, destinations, booking requests, and booking status history. Production configuration uses a PostgreSQL URL supplied through `DATABASE_URL`; FastAPI creates request-scoped sessions and disposes its connection pool during shutdown.

Alembic owns schema changes. The initial revision creates relationships, uniqueness rules, check constraints, indexes, and timestamps. Application startup does not create tables implicitly. Operators must run `alembic upgrade head` before serving traffic.

The explicit destination seed operation inserts Serengeti National Park, Ngorongoro Conservation Area, Mount Kilimanjaro, Zanzibar, and Tarangire National Park. It is idempotent by destination slug and contains no live availability, pricing, or partnership data.

## API boundaries

All JSON responses will use documented schemas. Business rules belong in services rather than route handlers, and database models must not be returned directly.

| Boundary | Proposed endpoint | Responsibility | Access |
| --- | --- | --- | --- |
| Platform health | `GET /api/health` | Report that the API process is available | Public; implemented |
| Destination catalog | `GET /api/v1/destinations` | Search, filter, and paginate active curated destinations | Public; implemented |
| Destination detail | `GET /api/v1/destinations/{id}` | Return one active curated destination | Public; implemented |
| Booking submission | `POST /api/v1/bookings` | Validate and create an idempotent pending request | Public submission; implemented |
| Concierge | `POST /api/v1/conversations/{id}/messages` | Accept a traveller message and return or queue an assistant response | Authenticated session; planned |
| Booking queries | `GET /api/v1/bookings/{id}` | Return the request and its permitted status history | Traveller or operator authorization; planned |
| Operator actions | `POST /api/v1/bookings/{id}/offers` | Record availability and an operator offer | Operator authorization; planned |
| SMS callback | `POST /api/webhooks/africas-talking/sms` | Normalize an inbound SMS or delivery update | Provider callback controls; planned |
| USSD callback | `POST /api/ussd` | Advance a short-lived USSD menu session | Provider callback controls; planned |

External callbacks must be rate-limited, validated against provider-supported controls, assigned an internal correlation ID, and processed idempotently. The API must acknowledge callbacks quickly; work that does not affect the immediate response should run outside the request path.

## Booking workflow

The booking service, not the LLM, owns the workflow and allowed transitions.

Public submission creates a request directly in `pending_availability`; it never creates a confirmed booking. The internal workflow implements the remaining state edges shown below.

```mermaid
stateDiagram-v2
    [*] --> Draft
    Draft --> PendingAvailability: traveller submits request
    PendingAvailability --> Quoted: operator confirms an offer
    PendingAvailability --> Rejected: unavailable or invalid
    Quoted --> PendingConfirmation: traveller selects offer
    PendingConfirmation --> Confirmed: operator/provider confirms
    Quoted --> Expired: quote deadline passes
    PendingConfirmation --> Rejected: confirmation fails
    Confirmed --> Cancelled: permitted cancellation
    Rejected --> [*]
    Expired --> [*]
    Cancelled --> [*]
```

1. The concierge or form collects destination, dates, party size, preferences, contact channel, and consent.
2. The booking service validates required data and creates a draft using a client-provided idempotency key.
3. Submission moves the request to `pending_availability` and asks an operator or inventory adapter for availability.
4. An available option becomes a time-limited quote; unavailable or invalid requests are rejected with a reason.
5. The traveller selects a quote. Any payment workflow introduced later must use a dedicated payment provider and must never expose payment credentials to the LLM.
6. The operator or booking provider confirms the reservation before the state becomes `confirmed`.
7. The notification service sends an SMS or web update and records the provider message ID and delivery state.
8. Every transition records the actor, timestamp, correlation ID, and reason for auditability.

Commands must reject invalid state changes, duplicate callbacks, expired quotes, and unauthorized access. PostgreSQL transactions should update the booking and its status history atomically.

Phase 2 implements these rules as an internal workflow service with row locking and resource-scoped authorization facts. Booking detail and status-management endpoints remain intentionally unavailable until authenticated customer and operator identities can be securely bound to the corresponding booking or operator. Public callers can submit a request, but they cannot inspect it or advance its status.

## Phase 2 security and privacy boundaries

- Booking submission responses omit names, email addresses, phone numbers, consent records, and special requests.
- The public API exposes no booking list, detail, audit-history, operator-decision, or status-change endpoint.
- A client-supplied idempotency key can replay only the same normalized booking input; conflicting reuse is rejected.
- Destination identifiers must resolve to active catalog records before a booking is accepted.
- Customer and operator workflow actors must carry resource-scoped authorization facts established by a future authentication layer.
- Operator-only transitions include quoting, rejection, and confirmation. The LLM and unauthenticated callers cannot confirm bookings.

Phase 3's customer-access threat model and deferral decision are documented in [customer-booking-access.md](customer-booking-access.md). Booking references and contact details are not authentication factors, so customer lookup and action endpoints remain absent until a verified account or out-of-band challenge channel exists.

## Africa's Talking integration

### SMS flow

```mermaid
sequenceDiagram
    participant T as Traveller
    participant AT as Africa's Talking
    participant API as FastAPI callback
    participant C as Conversation service
    participant N as Notification service

    T->>AT: Send SMS
    AT->>API: Inbound message callback
    API->>C: Normalize and deduplicate message
    API-->>AT: Prompt acknowledgement
    C->>N: Queue channel-appropriate reply
    N->>AT: Send outbound SMS
    AT-->>API: Delivery status callback
    API->>N: Record delivery outcome
```

- Convert provider fields into a channel-neutral message model and retain the provider ID for deduplication.
- Normalize phone numbers to an agreed format before lookup, and store only the data required for the service.
- Keep SMS replies concise and split messages deliberately to control cost and readability.
- Retry only transient failures with bounded backoff; permanent failures should be visible to operators.
- Use separate sandbox and production settings, sender configuration, and callback URLs.

### USSD flow

USSD is synchronous. Africa's Talking sends the session identifier, service code, phone number, and accumulated user input to the callback. The application will load the short-lived session, apply a deterministic menu transition, and return either `CON` to continue or `END` to close the session.

The callback path must not wait for an LLM response. Initial menus should support destination browsing and booking-request capture with small, numbered choices. Session state can begin in PostgreSQL with an expiry timestamp; a dedicated low-latency store can be introduced if traffic or response-time measurements justify it.

### Integration security and operations

- Load credentials only from runtime secrets or environment variables; never store them in source control.
- Use HTTPS callback URLs and the strongest callback authentication or source validation supported by the provider configuration.
- Redact API keys, phone numbers, and message content from routine logs.
- Track callback latency, send success, delivery status, retry count, and cost-related metrics.
- Correlate inbound events, booking commands, LLM calls, and outbound messages without exposing secrets.

## LLM boundary

The LLM adapter receives the minimum context needed for a response. It may suggest destinations, summarize verified content, and identify booking details, but all tool inputs must be schema-validated. The booking service revalidates extracted values and enforces authorization and state transitions.

Prompts and retrieved content are untrusted input. The system should resist prompt injection, avoid placing secrets in model context, label uncertain information, and provide a human handoff when confidence or safety requirements are not met.

## Deployment direction

Docker will package the frontend and backend, with PostgreSQL provided as a managed service or separate container. Deployments should expose only the web/API entry points, run database migrations as a controlled release step, and include liveness and readiness checks. Production secrets must come from the deployment platform rather than committed files.
