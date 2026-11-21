#!/usr/bin/env bash
# One-shot setup: loads .env into GitHub secrets, starts in dry-run mode, enables the workflow.
# Needs the GitHub CLI (https://cli.github.com). Usage: ./scripts/setup_github.sh [owner/repo]
set -euo pipefail

REPO="${1:-ahmad6143/claude}"
command -v gh >/dev/null || { echo "Install the GitHub CLI first: https://cli.github.com"; exit 1; }
gh auth status >/dev/null 2>&1 || gh auth login
[ -f .env ] || { echo "Copy .env.example to .env and fill it in first."; exit 1; }

while IFS='=' read -r key value; do
  [[ -z "$key" || "$key" =~ ^[[:space:]]*# ]] && continue
  [[ -z "$value" ]] && continue
  printf '%s' "$value" | gh secret set "$key" --repo "$REPO"
  echo "set secret $key"
done < .env

gh variable set REEL_DRY_RUN --body true --repo "$REPO"
gh workflow enable "Daily reel" --repo "$REPO" 2>/dev/null || true
echo
echo "Done. Test it:      gh workflow run 'Daily reel' -f dry_run=true --repo $REPO"
echo "Go live later with: gh variable set REEL_DRY_RUN --body false --repo $REPO"
