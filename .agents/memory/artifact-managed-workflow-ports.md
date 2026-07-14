---
name: Artifact-managed workflow ports
description: Why editing artifact-backed workflow commands/ports fails, and how their ports are actually configured.
---

Once a service under `artifacts/*` has a `.replit-artifact/artifact.toml`, its workflow is "managed by an artifact" — `removeWorkflow`/`configureWorkflow` on it fail with "managed by an artifact and cannot be overridden". The dev port/command come from `[[services]]` (`localPort`) and `[services.development].run` / `[services.env]` in that `artifact.toml`, not from `.replit`.

**Why:** the artifact runtime injects `PORT` from `artifact.toml` for the dev process regardless of what a legacy `.replit` workflow used to pass; a stale hardcoded port elsewhere (e.g. another service's proxy target) will silently break after artifact-ification.

**How to apply:** when a project gets auto-converted to artifacts (e.g. after import) and a proxy/client hardcodes a port for another local service, check that service's `artifact.toml` `localPort` and update the proxy target to match instead of trying to change the workflow's env/port directly.
