---
name: better-sqlite3 Node version
description: The pre-built better-sqlite3 binary in this project targets Node.js 24 (MODULE_VERSION 137).
---

The `better-sqlite3` pre-built binary shipped in the pnpm lockfile was compiled for Node.js 24 (MODULE_VERSION 137). Running it under Node 20 (115) or Node 22 (127) causes an `ERR_DLOPEN_FAILED` crash.

**Why:** The lockfile was generated on a system running Node 24, so pnpm downloaded the Node-24 pre-built binary.

**How to apply:** Always run this project with `nodejs-24`. If the version ever changes, run `pnpm rebuild better-sqlite3` from the workspace root and restart the API Server workflow.
