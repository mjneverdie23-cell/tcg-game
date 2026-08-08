#!/usr/bin/env bash
# SessionStart hook: ensure a World Atlas web session can immediately run the
# app, tests and linters. Idempotent and safe to run on every session start.
set -euo pipefail
cd "$(dirname "$0")/../.."

# 1. Install dependencies if missing (postinstall runs `prisma generate`).
if [ ! -d node_modules ]; then
  echo "[session-start] installing dependencies…"
  npm install --no-audit --no-fund
fi

# 2. Ensure the Prisma client is generated.
if [ ! -e node_modules/.prisma/client/index.js ]; then
  echo "[session-start] generating Prisma client…"
  npx prisma generate >/dev/null
fi

# 3. Ensure the SQLite database exists.
if [ ! -f prisma/dev.db ]; then
  echo "[session-start] creating database…"
  npx prisma db push --skip-generate >/dev/null
fi

# 4. Populate the database if it's empty. `npm run pipeline` reuses the on-disk
#    download cache, so this is fast after the first run.
count=$(npx --yes tsx -e "import {PrismaClient} from '@prisma/client';const p=new PrismaClient();p.country.count().then(n=>{console.log(n);process.exit(0)}).catch(()=>{console.log(0);process.exit(0)})" 2>/dev/null || echo 0)
if [ "${count:-0}" -lt 100 ]; then
  echo "[session-start] running data pipeline (importing open datasets)…"
  npm run pipeline || echo "[session-start] pipeline failed (likely offline); existing data retained."
else
  echo "[session-start] database ready: ${count} countries."
fi

echo "[session-start] ready. dev: npm run dev · test: npm test · build: npm run build"
