#!/usr/bin/env bash
# Fetches the Pokémon Showdown simulator (pinned commit) and stubs its one npm dependency
# so it runs straight from TypeScript under Bun, with no npm install.
set -euo pipefail
cd "$(dirname "$0")"
SHOWDOWN_COMMIT=3a766f2cfb5e51c1e428cfe87d0dba91a8f01640
if [ ! -d ps ]; then
  git clone https://github.com/smogon/pokemon-showdown.git ps
fi
git -C ps checkout -q "$SHOWDOWN_COMMIT"
# Array seeds use the Gen 5 RNG, so the ChaCha20 package is never called.
mkdir -p node_modules/ts-chacha20
echo 'export class Chacha20 { constructor() { throw new Error("ts-chacha20 stub: use array seeds"); } }' > node_modules/ts-chacha20/index.ts
echo '{"name": "ts-chacha20", "main": "index.ts"}' > node_modules/ts-chacha20/package.json
echo "Ready. Try: python3 run.py 400"
