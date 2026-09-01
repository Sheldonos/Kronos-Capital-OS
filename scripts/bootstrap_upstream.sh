#!/usr/bin/env bash
set -euo pipefail
REPO="https://github.com/shiyu-coder/Kronos.git"
COMMIT="67b630e67f6a18c9e9be918d9b4337c960db1e9a"
TARGET="upstream/Kronos"
mkdir -p upstream
if [[ -d "$TARGET/.git" ]]; then
  git -C "$TARGET" fetch --all --tags
else
  rm -rf "$TARGET"
  git clone "$REPO" "$TARGET"
fi
git -C "$TARGET" checkout "$COMMIT"
test "$(git -C "$TARGET" rev-parse HEAD)" = "$COMMIT"
echo "Kronos locked at $COMMIT"
