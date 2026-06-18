# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
npm start        # Start the Express server on port 3000 (node server.js)
```

No test runner, linter, or build step is configured.

## Architecture

Single-file Node.js backend (`server.js`) with plain HTML/JS frontend (`public/`). The app lets employees send WhatsApp messages through a web dashboard backed by a persistent WhatsApp Web session.

### Two-phase usage model

1. **Admin phase** (`/admin`): An admin opens the admin page, scans the QR code with WhatsApp, and establishes a session. The session is persisted via `LocalAuth` in `./session/`.
2. **Employee phase** (`/`): Employees enter a password (`EMPLOYEE_PASSWORD` hardcoded in `server.js`) and send messages to phone numbers.

### Key state in `server.js`

| Variable | Purpose |
|---|---|
| `client` | The `whatsapp-web.js` Client instance (singleton) |
| `isReady` | Boolean — true once `client.on('ready')` fires |
| `qrCodeData` | Data URL of current QR image, cleared on `ready` |
| `statusMessage` | Arabic string shown in the UI |

### Phone number normalization

Egyptian-specific: strips non-digits → if starts with `0`, replaces it with `2` → if result is 10 digits not starting with `20`, prepends `20` → appends `@c.us` to form the WhatsApp chat ID.

### API endpoints

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/login` | Validates `password` field against `EMPLOYEE_PASSWORD` |
| `GET` | `/api/status` | Returns `{ isReady, hasQR, message }` — polled every 3–5 s by both UIs |
| `GET` | `/api/qr` | Returns `{ qrCode }` data URL for admin page |
| `POST` | `/api/send` | Sends message; requires `password`, `phone`, `message` |

### Deployment

Designed for **Railway.app** (`railway.toml`). The `Dockerfile` uses `node:20-slim` with system Chromium (`PUPPETEER_SKIP_CHROMIUM_DOWNLOAD=true`) to keep image size down. The `./session/` directory must be on a persistent volume in production.

## Important constraints

- **Multi-step tasks**: include a verification plan before executing.
- **Do not fabricate information** — especially phone numbers, WhatsApp chat IDs, or session state.
- **Do not modify `./session/`** — it holds the live WhatsApp authentication data.
- The `whatsapp-web.js` library drives a real Chromium browser under the hood; changes to `clientOptions` (e.g., `puppeteer` flags) can break startup in Docker.
