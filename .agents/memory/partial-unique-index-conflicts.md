---
name: Partial unique index + ON CONFLICT in Drizzle
description: Why idempotent upserts against a partial unique index (e.g. nullable FK/dedupe key) need raw SQL instead of the query builder.
---

Drizzle's `.onConflictDoNothing({ target: col })` / `.onConflictDoUpdate()` emits
`ON CONFLICT (col)` with no `WHERE` predicate. Postgres requires the ON CONFLICT
target to exactly match an existing unique index, including its partial
predicate — so against a **partial** unique index (e.g.
`UNIQUE (telegram_message_id) WHERE telegram_message_id IS NOT NULL`, used to
dedupe nullable foreign keys like external message IDs) the query builder's
version does not match and the insert throws.

**Why:** discovered while building an idempotent upsert-by-external-id endpoint;
`onConflictDoNothing({ target: villasTable.telegram_message_id })` returned a
bundled 500 with no useful stack (pino-http only logs the HTTP-level error, not
the underlying pg error after esbuild bundling swallows details).

**How to apply:** when the unique constraint is partial, drop to a raw
`db.execute(sql`...`)` INSERT with the full `ON CONFLICT (col) WHERE col IS NOT
NULL DO NOTHING RETURNING *`, then do a follow-up SELECT if 0 rows returned
(conflict occurred) to fetch and return the existing row. Don't rely on
catching `err.code === '23505'` and inspecting `err.constraint`/`err.detail` —
those properties are not reliably preserved through the bundled/minified error
path in this stack.
