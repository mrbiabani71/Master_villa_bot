---
    name: Orval-generated zod request schemas silently drop undeclared fields
    description: A field present in a request body but missing from the OpenAPI spec is silently stripped by zod .object() before the route handler ever sees it — no error, just null in the DB.
    ---

    In this project, `lib/api-zod/src/generated/api.ts` (zod schemas) is generated from `lib/api-spec/openapi.yaml` via orval (`pnpm run codegen` in `lib/api-spec`). Route handlers call `SomeBody.safeParse(req.body)` and use `parsed.data` — a plain `zod.object()`, not `.passthrough()`, so any request field not declared in the OpenAPI schema is dropped with no error, no warning, no zod validation failure.

    **Why this matters:** we spent a full debugging cycle chasing a Python-bot "identifier lost during edit" bug that turned out to be entirely server-side: `CreateVillaRequest`/`UpdateVillaRequest` in openapi.yaml didn't declare `telegram_message_id`/`telegram_media_group_id`/`original_caption`, so every create/update silently wrote NULL for those columns regardless of what the client sent. The client-side value was correct end-to-end; only the schema was missing fields.

    **How to apply:** when a field a client sends doesn't appear to persist (comes back null, or an idempotency/lookup key never matches), check the OpenAPI spec + generated zod schema for that field before assuming the client, DB write, or business logic is at fault. After editing openapi.yaml, must run `pnpm run codegen` in `lib/api-spec` to regenerate lib/api-zod and lib/api-client-react, then restart the API server.
    