# SafariSmart USSD Tourism Discovery

## Contract

Africa's Talking POSTs `application/x-www-form-urlencoded` to the public USSD callback:

- `POST /api/v1/ussd`
- Fields: `sessionId`, `serviceCode`, `phoneNumber`, `text`
- Response: `text/plain`, beginning with `CON ` (more input) or `END ` (terminate)
- `text` is cumulative and `*`-delimited: `""`, `"1"`, `"1*1"`, `"1*1*1"`.

The first screen selects English or Kiswahili. Users can browse the first five active curated destinations from the existing public catalog, read booking information, or view help. The callback does **not** look up customers, expose private booking records, create bookings, make payments, or claim availability or prices. Language and screen progression are derived from the cumulative `text`; no subscriber identifiers are stored. A bounded in-memory limiter retains only a hash of the opaque session ID and recent timestamps; it never retains the phone number, service code, or menu input.

## Local development

From the project root with a configured local database:

```cmd
python -m uvicorn app.main:app --app-dir backend --reload
```

From a second Windows CMD terminal, send a test callback:

```cmd
curl.exe -X POST http://127.0.0.1:8000/api/v1/ussd --data-urlencode "sessionId=local-test-1" --data-urlencode "serviceCode=*384*123#" --data-urlencode "phoneNumber=+255700000001" --data-urlencode "text="
```

The response should begin with `CON Welcome to SafariSmart`.

Try `text=2` for Kiswahili. Once the five curated destinations have been seeded, try `text=2*1` to list them and `text=2*1*1` for the first destination.

Run automated tests:

```cmd
python -m pytest backend/tests/test_ussd.py -v
python -m pytest backend -q
```

## Simulator callback setup

GitHub Actions can **send outbound sandbox SMS**, but a USSD callback requires a publicly reachable HTTPS URL for this running FastAPI service. GitHub Actions is not a permanent web host. For sandbox-only manual tests, deploy a development instance or expose a running local instance through a trusted HTTPS tunnel. Never put database passwords, auth tokens or Africa's Talking API keys in the callback URL.

In the Africa's Talking Sandbox dashboard, create a USSD channel/service code, set its callback to `https://YOUR-PUBLIC-HOST/api/v1/ussd`, connect a virtual phone in the Sandbox Simulator, then dial the assigned *sandbox* USSD code. Do not assume the documentation's example code is your allocated code.

A production callback needs additional operational controls: review webhook authentication options with the provider, apply shared edge rate limiting and abuse protection, monitor failures without logging phone numbers or session identifiers, and configure a stable HTTPS deployment. The implemented process-local sliding-window limiter is defense in depth for the single-process MVP, not a distributed edge control. Avoid customer-sensitive USSD functionality until identity verification is designed.

## Scope limits

The catalog is a curated educational/demo dataset; no live tour inventory or verified operator pricing is connected. A booking status lookup is deliberately unavailable over unauthenticated USSD. The simple menu recomputes the first five active destinations on each request; adding dynamic ordering or a larger catalog should introduce stable session snapshots or pagination to avoid index changes mid-session.
