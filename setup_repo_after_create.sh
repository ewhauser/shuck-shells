#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "$0")" && pwd)"
cd "$repo_root"

if ! command -v gh >/dev/null 2>&1; then
  echo "error: gh is required" >&2
  exit 1
fi

if ! command -v git >/dev/null 2>&1; then
  echo "error: git is required" >&2
  exit 1
fi

bot_token="${SHUCK_SHELLS_BOT_TOKEN:-}"
if [[ -z "$bot_token" ]]; then
  if [[ -t 0 ]]; then
    read -r -s -p "Enter SHUCK_SHELLS_BOT_TOKEN: " bot_token
    echo
  fi
fi
if [[ -z "$bot_token" ]]; then
  echo "error: SHUCK_SHELLS_BOT_TOKEN is not set" >&2
  exit 1
fi

remote_url="$(git remote get-url origin)"
repo="${remote_url#git@github.com:}"
repo="${repo#https://github.com/}"
repo="${repo%.git}"

if [[ "$repo" != */* ]]; then
  echo "error: could not infer owner/name from origin: $remote_url" >&2
  exit 1
fi

echo "Using repo: $repo"

echo "Pushing local main to origin..."
git push -u origin main

echo "Enabling auto-merge and branch cleanup..."
gh api --method PATCH "repos/$repo" \
  -F allow_auto_merge=true \
  -F delete_branch_on_merge=true >/dev/null

echo "Configuring GitHub Pages for Actions..."
set +e
pages_output="$(gh api --method POST "repos/$repo/pages" -f build_type=workflow 2>&1)"
pages_status=$?
set -e
if [[ $pages_status -ne 0 ]]; then
  if [[ "$pages_output" == *"already exists"* ]] || [[ "$pages_output" == *"409"* ]]; then
    echo "Pages already configured; continuing."
  else
    echo "$pages_output" >&2
    exit $pages_status
  fi
fi

echo "Uploading repo secrets..."
gh secret set SHUCK_SHELLS_BOT_TOKEN \
  --repo "$repo" \
  --body "$bot_token"

echo "Applying branch protection to main..."
gh api \
  --method PUT \
  -H "Accept: application/vnd.github+json" \
  "repos/$repo/branches/main/protection" \
  --input - <<'JSON'
{
  "required_status_checks": {
    "strict": true,
    "contexts": ["validate"]
  },
  "enforce_admins": false,
  "required_pull_request_reviews": null,
  "restrictions": null,
  "required_conversation_resolution": true,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "block_creations": false,
  "required_linear_history": false,
  "lock_branch": false,
  "allow_fork_syncing": false
}
JSON

echo
echo "Done."
echo "Optional smoke test:"
echo "  gh workflow run refresh-index.yml --repo $repo"
echo "  gh run list --repo $repo --limit 10"
