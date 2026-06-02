#!/bin/bash
set -euo pipefail

# Only run in remote (Claude Code on the web) environments
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

REPO_DIR="/home/user/TasksDia"

if [ -d "$REPO_DIR/.git" ]; then
  echo "[session-start] Repositório já existe, atualizando..."
  git -C "$REPO_DIR" pull --ff-only origin main
else
  echo "[session-start] Clonando hiabreu/TasksDia..."
  git clone "https://x-access-token:${GH_TOKEN}@github.com/hiabreu/TasksDia.git" "$REPO_DIR"
fi

echo "[session-start] Pronto — $REPO_DIR disponível."
