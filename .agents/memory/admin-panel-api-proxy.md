---
name: Admin panel API proxy
description: Vite dev server must proxy /api to the API server's actual dev port or the dashboard shows all zeros.
---

The admin panel (Vite) and the API server (Express) are separate workflows/processes. The generated API client uses relative paths like `/api/...`, which Vite resolves against its own port — not the API server — unless a proxy is configured.

**Why:** Without the proxy, all fetch calls silently 404/500 against the Vite dev server, causing React Query to return undefined/error data (rendered as 0s in the UI).

**How to apply:** The proxy is set in `artifacts/admin-panel/vite.config.ts` under `server.proxy`, pointing `/api` at `http://localhost:<api-server-dev-port>`. Do not remove this. The API server's actual dev port is not fixed — once both services are artifact-managed, it's whatever `localPort` is set in `artifacts/api-server/.replit-artifact/artifact.toml` (the artifact runtime injects that as `PORT` for the dev process, overriding any port a legacy `.replit` workflow used to pass). Always check that file's `localPort` and match the proxy target to it — don't assume a fixed number like 3000.
