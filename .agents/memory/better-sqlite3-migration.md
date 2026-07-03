---
name: better-sqlite3 migration
description: API server was migrated from SQLite (better-sqlite3) to Replit PostgreSQL during import migration.
---

The API server's routes (`artifacts/api-server/src/routes/villas.ts` and `requests.ts`) originally used `better-sqlite3` to read from `bot/bot.db`. The native module was compiled for a different Node.js version and could not be rebuilt easily in Replit.

**What was done:** Migrated both route files to use `drizzle-orm` + `pg` via `@workspace/db`. Defined the `villas` and `visit_requests` tables in `lib/db/src/schema/index.ts`. Pushed schema to Replit PostgreSQL with `drizzle-kit push --force`. Removed `better-sqlite3` and `@types/better-sqlite3` from `artifacts/api-server/package.json`.

**Why:** Replit's Node 20 runtime could not load the pre-compiled better-sqlite3 binary (compiled for Node 24). Rebuilding from source failed due to missing node-gyp. Replit PostgreSQL is the correct data store for this environment.

**How to apply:** All future DB access in the API server should use `@workspace/db` (drizzle + pg). The bot still uses its own SQLite DB (`bot/bot.db`) via Python — that's fine and separate from the API layer.
