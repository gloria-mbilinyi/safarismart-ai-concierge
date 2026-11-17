# SafariSmart MVP Release Checklist

Status date: 17 November 2026

Target: Africa's Talking Open Hackathon demo on 18 November 2026

The labels below deliberately separate code/configuration from executed evidence.

## Verification summary

| Area | Status | Evidence or remaining action |
| --- | --- | --- |
| Backend automated suite | Verified locally | `193 passed, 1 skipped`; skip is the opt-in PostgreSQL integration test without `TEST_DATABASE_URL` |
| Frontend unit tests | Verified locally | 3 Vitest files, 13 tests passed |
| TypeScript and production bundle | Verified locally | `npm run build` completed; Vite transformed 2,143 modules |
| Frontend dependency audit | Verified locally | `npm audit --omit=dev --audit-level=high` reported 0 vulnerabilities during final MVP work |
| Browser desktop flow | Verified locally | Built single-image UI exercised: five-row catalog, two-turn Zanzibar chat, Zanzibar-only five-day plan, invalid-email validation, and localized booking acknowledgement with actual reference/unavailable channel state |
| Browser mobile flow | Verified locally | 390px catalog rendered all five destination cards |
| API health/catalog/planner | Verified locally | Health, five-row catalog, and a five-day grounded planner response exercised |
| Alembic chain | Verified locally | Migration head checks and isolated migration tests pass in the backend suite |
| Local SMS provider/worker | Verified locally | Bounded worker drained an empty migrated SQLite database without credentials/network; automated worker/provider tests pass |
| Africa's Talking SMS Sandbox | Previously demonstrated by owner | Remote GitHub Actions send reached the Sandbox Simulator; preserve a redacted screenshot/log as submission evidence |
| Africa's Talking USSD Sandbox | Previously demonstrated by owner | English/Kiswahili `CON`/`END` navigation worked on Sandbox code `*384*34763#`; preserve redacted screenshots |
| Compose model | YAML verified locally | Compose and workflow YAML parse; Docker executable was unavailable locally |
| Compose build/smoke | Verified in GitHub Actions; not locally executed | Commit `2340cc7` built/started PostgreSQL, API, and frontend, then passed web and proxied-health checks; Docker remains unavailable locally |
| Single Marketplace image | Verified in GitHub Actions; not locally executed | Commit `2340cc7` successfully built `marketplace/Dockerfile` |
| PostgreSQL integration | Verified in GitHub Actions | Commit `2340cc7` supplied isolated PostgreSQL, applied Alembic, and passed the complete suite with `TEST_DATABASE_URL` |
| Render + Neon public deployment | Prepared, not performed | Blueprint and runbook are committed; owner account authorization, Neon credentials, sender verification, and public checks remain required |
| Marketplace publication | Not done | Requires owner approval, registry credentials, image push, listing data, pricing, policies, and form submission |
| Durable production hosting | Not done | Quick Tunnel/laptop is explicitly temporary and must not be presented as production |

## Functional release checklist

- [x] Five curated destinations seed repeatably by slug
- [x] Catalog search/filter/detail works without live availability or pricing claims
- [x] Planner constrains days, party size, interests, optional region, and TZS budget context
- [x] Planner and chat are grounded in active catalog rows
- [x] Single-destination planning cannot introduce a second destination; chat uses bounded per-tab context with an explicit reset
- [x] Fallback is visibly labelled; Ollama failure falls back safely
- [x] Booking requires active destination, future dates, party size, contact validation, consent, and idempotency key
- [x] Public booking response excludes customer contact data
- [x] Operator login validates signature, issuer, audience, expiration, active account, and token version
- [x] Operator queue is organization-scoped; cross-organization resources do not leak existence
- [x] Direct confirmation from `pending_availability` is rejected
- [x] Synthetic quote and confirmation wording does not claim a real reservation
- [x] Booking transitions and notifications are written atomically with audit/outbox records
- [x] Email preference queues only Resend email; phone preference queues only Africa's Talking SMS; there is no channel fallback
- [x] Resend email and SMS use fixed bilingual templates with the actual booking reference and truthful pending/demo wording
- [x] Notification dispatcher has bounded drain, continuous mode, row leases, retries, provider identifiers, safe errors, and PII-free summaries
- [x] Provider acceptance remains distinct from delivery; the public response reports only `queued` or `unavailable`
- [x] Active web instances perform safe bounded post-commit/startup/periodic dispatch without fake keep-alive traffic
- [x] Local SMS mode performs no network call and is rejected outside development/test
- [x] USSD validates form input, limits abuse, avoids PII storage/logging, and makes no LLM call
- [x] Customer booking lookup/actions remain absent without identity verification
- [x] Responsive traveller and operator screens have loading, empty, error, and demo states
- [x] Single-image artifact serves SPA routes without hiding API `404` responses

## Security and privacy review

- [x] `.env` is ignored and was not staged
- [x] `.env.example` contains placeholders/non-secret defaults only
- [x] No hardcoded API key, signing key, token, database password, or real customer record was intentionally added
- [x] Deployment requires environment configuration and rejects insecure production defaults
- [x] Neon production URLs require the psycopg driver and TLS; database URLs are excluded from settings representations
- [x] Passwords use Argon2 through a maintained library
- [x] CORS is an explicit origin allowlist; wildcards are rejected
- [x] Public inputs have lengths, ranges, patterns, and Pydantic schemas
- [x] Public booking submission has a bounded per-client process-local rate limit
- [x] Routine SMS/USSD logs avoid phone numbers, message bodies, and session identifiers
- [x] Docker runtime uses a non-root user in the backend and Marketplace images
- [x] Frontend production audit has no known high-severity dependency finding
- [ ] Review the final GitHub Actions logs for accidental secret echo before sharing screenshots
- [ ] Rotate any credential ever exposed outside an approved secret store
- [ ] Publish reviewed privacy and terms URLs before Marketplace submission
- [ ] Add provider-supported delivery callback authenticity controls before enabling callback ingestion
- [ ] Add shared/edge rate limiting before multi-instance public booking or USSD deployment

## Final local commands

Run from the repository root:

```powershell
.\.venv\Scripts\python.exe -m pytest backend -q
.\.venv\Scripts\python.exe -m compileall -q backend\app backend\tests
Set-Location frontend
npm test
npm run build
npm audit --omit=dev --audit-level=high
Set-Location ..
git diff --check
git status --short
```

With a disposable PostgreSQL database only:

```powershell
$env:DATABASE_URL = 'postgresql+psycopg://<user>:<password>@127.0.0.1:5432/safarismart_test'
$env:TEST_DATABASE_URL = $env:DATABASE_URL
Set-Location backend
python -m alembic upgrade head
python -m pytest -q
Remove-Item Env:TEST_DATABASE_URL
Remove-Item Env:DATABASE_URL
```

The PostgreSQL integration test clears application-domain tables. Never point it at a valuable or production database.

## GitHub and CI checks

After the final push:

1. Open the repository **Actions** tab.
2. Select the workflow runs for the final commit SHA, not an earlier commit.
3. Confirm **Backend CI** completed successfully, including migrations and PostgreSQL integration.
4. Confirm **Frontend and Container CI** completed successfully, including tests, build, audit, Compose smoke, and Marketplace image build.
5. If a run is queued, record it as queued—not passed—and wait when time permits.
6. If a job fails, inspect the first failing step, fix the defect, rerun locally where possible, commit, push, and verify the new SHA.

## Demo evidence checklist

- [ ] Landing page branding and accessibility/channel summary
- [ ] Destination explorer with all five cards
- [ ] Context-aware Zanzibar chat plus single-destination planner result showing its generation-mode badge and non-booking disclaimer
- [ ] Bilingual booking success state showing the actual reference and truthful selected-channel state but no customer contact data
- [ ] Operator synthetic queue/quote/audit state with PII redacted
- [ ] Africa's Talking SMS Sandbox inbox with test recipient redacted
- [ ] English USSD Simulator menu
- [ ] Kiswahili USSD Simulator destination menu
- [ ] Final GitHub Actions workflow summary
- [ ] Final commit SHA and repository URL

Do not include `.env`, browser developer storage, access tokens, real contact data, registry passwords, dashboard API keys, or a temporary tunnel URL in evidence.

## Submission blockers and owner-only actions

These are not code defects and require external access or an irreversible decision:

1. Approve draft pricing and billing wording.
2. Supply a monitored support contact and approved public privacy/terms URLs.
3. Obtain Africa's Talking Marketplace Container Registry credentials.
4. Review the exact built image, then explicitly approve and perform the registry push.
5. Create the Marketplace plugin, enter configuration metadata, and submit for review.
6. Create the Render Free service from `render.yaml`, provision Neon, and place the TLS-enforced pooled URL only in Render's secret store.
7. Verify a Resend sender domain and set a restricted API key, or explicitly leave email disabled.
8. Configure durable HTTPS callbacks and authorized live SMS/USSD products; never use a Quick Tunnel as production hosting.
9. Confirm live product pricing, sender/service code, country compliance, balances, and provider approval.

Until these are complete, describe SafariSmart as a **tested local/Sandbox hackathon MVP with prepared Render and Marketplace deployment artifacts**, not a live public or Marketplace product.

## Go/no-go statement

The MVP is suitable for a local hackathon demonstration when the native startup checks pass and synthetic credentials are ready. Backend/PostgreSQL, frontend, audit, Compose smoke, and single-image CI completed successfully for implementation/documentation commit `2340cc7` on 17 November 2026. Public launch, provider-delivery claims, and Marketplace publication remain **no-go** until the owner-only account/configuration steps above are complete.
