---
name: Admin panel API proxy
description: Vite dev server (port 5000) must proxy /api to the API server (port 3000) or the dashboard shows all zeros.
---

The admin panel (Vite, port 5000) and the API server (Express, port 3000) are separate workflows. The generated API client uses relative paths like `/api/...`, which Vite resolves against its own port — not the API server — unless a proxy is configured.

**Why:** Without the proxy, all fetch calls silently 404 against the Vite dev server, causing React Query to return undefined data (rendered as 0s in the UI).

**How to apply:** The proxy is set in `artifacts/admin-panel/vite.config.ts` under `server.proxy`:
```ts
proxy: {
  "/api": {
    target: "http://localhost:3000",
    changeOrigin: true,
  },
},
```
Do not remove this. If the API server port ever changes, update the target here too.
