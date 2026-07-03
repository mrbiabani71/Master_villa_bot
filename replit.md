# Master Villa (مستر ویلا)

A Telegram bot + admin panel for an Iranian villa real estate business: users browse/search villa listings and FAQs via the bot, while admins manage villa listings (create/edit/publish/archive) through a web admin panel backed by a shared API.

## Run & Operate

- `pnpm --filter @workspace/api-server run dev` — run the API server (port 3000)
- `pnpm --filter @workspace/admin-panel run dev` — run the admin panel (port 5000)
- `python3 bot/main.py` — run the Telegram bot
- `pnpm run typecheck` — full typecheck across all packages
- `pnpm run build` — typecheck + build all packages
- `pnpm --filter @workspace/api-spec run codegen` — regenerate API hooks and Zod schemas from the OpenAPI spec
- `pnpm --filter @workspace/db run push` — push DB schema changes (dev only)
- Required env: `DATABASE_URL` — Postgres connection string
- Bot secrets: `TELEGRAM_BOT_TOKEN`, `ADMIN_ID` (and `CHANNEL_ID`, not yet configured)

## Stack

- pnpm workspaces, Node.js 24, TypeScript 5.9
- API: Express 5
- DB: PostgreSQL + Drizzle ORM
- Validation: Zod (`zod/v4`), `drizzle-zod`
- API codegen: Orval (from OpenAPI spec)
- Build: esbuild (CJS bundle)
- Bot: Python (python-telegram-bot), separate SQLite store (`bot/bot.db`)

## Where things live

- `bot/` — Telegram bot (Python). `bot/Bot.py` entry/routing, `bot/user/faq.py` FAQ content, `bot/admin/panel.py` admin menu routing + state, `bot/keyboards.py` all reply keyboards.
- `artifacts/api-server/src/routes/villas.ts` — villa CRUD + status endpoints
- `artifacts/admin-panel/src/pages/villas/` — villa management UI (admin panel)
- `lib/api-spec/openapi.yaml` — source of truth for API contracts (villa endpoints, etc.)

## Architecture decisions

- Villas use a 4-status lifecycle: draft → published → sold / archived, enforced at the API layer.
- Bot and admin panel are separate apps talking to the same API server; bot keeps its own local SQLite (`bot/bot.db`) rather than the Postgres DB used by the API/admin panel.
- Admin panel Vite dev server proxies `/api` to the API server (port 3000) so the dashboard shows real data instead of zeros.

## Product

- Bot: users browse villa listings, read FAQs (documents, in-person visits, coverage areas), contact admin.
- Admin panel: staff manage villa listings (create, edit, publish, archive) with status tracking.
- Bot admin menu also has a Settings submenu with placeholders for future city/region management (not yet implemented).

## User preferences

- Strict scope discipline: only implement exactly what's requested per sprint. Do not proactively add adjacent features (e.g. filtering/search, city/region CRUD) even if they seem like natural next steps — log them as future enhancements instead and wait for explicit instruction.
- Current sprint focus (Sprint 1/2): Villa Management (CRUD, listing, status system) + UX stability. Villa Management's core structure is not yet finalized, so avoid adding filtering/search or other extensions until it stabilizes (future sprint item).
- Settings menu "مدیریت شهرها" / "مدیریت مناطق" entries should stay as visible placeholders ("این بخش در حال توسعه است") — do not wire up real CRUD/data-editing flows or schema changes until a dedicated future sprint.
- After implementing a task: test, then commit. Note: the main agent cannot run `git push` (blocked as a destructive op) — user must run `git push` manually from the Shell after each checkpoint.

## Gotchas

- `git commit` / `git push` are blocked for the main agent. Checkpoints auto-commit locally after each loop, but pushing to GitHub requires the user to run `git push` manually in the Shell.
- Admin panel Vite dev server needs a proxy for `/api` → `localhost:3000`, or the dashboard will show all zeros.
- `better-sqlite3`'s pre-built binary targets Node 24 — must run Node 24 or rebuild on a version mismatch.

## Pointers

- See the `pnpm-workspace` skill for workspace structure, TypeScript setup, and package details
