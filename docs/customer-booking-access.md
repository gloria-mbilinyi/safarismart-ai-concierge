# Customer Booking Access Security Decision

## Current MVP decision

Customer booking lookup and acceptance endpoints are deferred. SafariSmart currently has no authenticated customer account and no verified email or SMS delivery path. A booking reference, email address, or phone number can be copied, guessed, forwarded, or exposed in logs and therefore cannot prove customer identity, alone or in combination.

The public API continues to support booking submission. Its response contains only the booking reference, pending status, destination identifier, dates, party size, and creation time. It does not return stored names, contact details, consent data, special requests, audit history, or operator decisions.

The following public capabilities intentionally do not exist:

- Booking lookup by reference, email address, or phone number
- Booking status history retrieval
- Quote acceptance or rejection
- Cancellation
- Customer-driven transition to `pending_confirmation`

This means an operator can create a synthetic quote, but cannot confirm it through the HTTP API until a customer has accepted it through a future verified channel. Internal workflow tests can establish `pending_confirmation` only with an explicitly trusted test authorization context.

## Required design before enabling access

A future customer-access implementation should use one of these approaches:

1. An authenticated customer account with verified email or phone ownership and booking ownership recorded at submission.
2. A short-lived, single-use challenge delivered out-of-band to a previously verified communication channel.

For a challenge flow, SafariSmart should:

- Generate a cryptographically random value that is never derived from the booking reference or contact data.
- Store only a hash of the challenge, scoped to one booking and one action.
- Deliver it through a verified SMS or email integration, never in the public booking response.
- Apply a short expiry, one-time use, attempt limits, rate limiting, and audit logging.
- Exchange successful verification for a short-lived booking-scoped session token.
- Recheck booking ownership and current workflow state on every action.
- Return uniform responses that do not reveal whether a booking or contact record exists.

Until those controls and a verified delivery channel are implemented, keeping customer booking endpoints absent is the safer behavior.
