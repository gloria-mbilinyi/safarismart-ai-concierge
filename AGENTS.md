# SafariSmart AI Concierge Engineering Guide

## Project context

SafariSmart AI Concierge is an AI-powered tourism and hospitality platform created by Gloria Beneth Mbilinyi for the Africa's Talking Open Hackathon 2026.

The intended stack is:

- Python 3.12 and FastAPI for the backend
- React and TypeScript for the frontend
- PostgreSQL for persistent data
- An LLM integration for concierge conversations
- Africa's Talking SMS and USSD APIs for accessible communication
- Docker for local and production deployment

Keep changes appropriate to the current development phase. Do not implement unrelated future functionality without an explicit request.

## Repository layout

- `backend/`: FastAPI application and backend tests
- `frontend/`: React and TypeScript application
- `database/`: database migrations, seeds, and database documentation
- `docs/`: architecture and engineering documentation

Prefer small, cohesive modules with clear boundaries. Keep API transport logic separate from business logic and external-service adapters. Add tests for new behavior and regressions.

## Security and configuration

- Read deployment-specific configuration from environment variables.
- Keep `.env.example` limited to safe placeholders and non-secret defaults.
- Never commit `.env` files, credentials, access tokens, API keys, private customer data, or generated secret material.
- Validate external input and avoid logging secrets or sensitive personal data.
- Treat Africa's Talking, LLM, payment, and booking-provider integrations as external boundaries with explicit adapters and error handling.

## Git workflow

1. Inspect `git status`, the active branch, and relevant existing files before changing anything.
2. Preserve existing history, repository configuration, and all unrelated user changes.
3. Complete work in small, logical milestones and create one atomic commit for each meaningful completed milestone.
4. Use Conventional Commits with an appropriate prefix: `feat:`, `fix:`, `docs:`, `test:`, `refactor:`, `chore:`, or `ci:`.
5. Run relevant automated tests and quality checks before each commit. Do not claim a check passed unless it was executed.
6. Stage only files that belong to the current milestone. Never include unrelated or pre-existing changes.
7. Do not create empty, fake, or unnecessary commits for contribution activity.
8. Never force-push, rewrite published history, delete existing work, or bypass branch protections.
9. Push completed commits to `origin/main` when the task requests it and the environment permits it.
10. At handoff, report every created commit hash and message, the checks executed and their results, and the push status.

Before committing, review both `git diff` and `git diff --staged`, and confirm no secrets or unrelated files are included.
