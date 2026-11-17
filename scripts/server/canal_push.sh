#!/usr/bin/env bash
# Run from cron on the village server: fetch WL.RJK.01 from the BMA site and push data/canal-rjk.json.
# Needs: git, python3, a clone of this repo made with a write-enabled deploy key (see scripts/server/README.md).
# Settings via environment (all optional):
#   CANAL_REPO   path of the clone              (default: the repo this script lives in)
#   CANAL_KEY    SSH private key for the deploy key (default: ~/.ssh/pruklada_deploy)
#   CANAL_CA     extra CA/intermediate PEM for the BMA site, only if TLS verification fails
# The whole body is inside main() so bash parses it before `git reset` can replace this file.
main() {
  set -euo pipefail
  local repo="${CANAL_REPO:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
  local key="${CANAL_KEY:-$HOME/.ssh/pruklada_deploy}"
  export GIT_SSH_COMMAND="ssh -i $key -o IdentitiesOnly=yes -o BatchMode=yes"
  local tmp; tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT
  exec 9>"${TMPDIR:-/tmp}/canal_push.lock"
  flock -n 9 || { echo "$(date '+%F %T') another run is still going"; return 0; }
  cd "$repo"
  git fetch -q origin main && git reset -q --hard origin/main     # this clone is only for the bot

  local ca=(); [ -n "${CANAL_CA:-}" ] && ca=(--ca-file "$CANAL_CA")
  python3 -I scripts/server/bma_canal.py fetch "${ca[@]}" > "$tmp/rows.json"

  for attempt in 1 2 3 4; do
    local n; n="$(python3 -I scripts/server/bma_canal.py merge "$tmp/rows.json" data/canal-rjk.json)"
    if [ "$n" = "0" ]; then echo "$(date '+%F %T') no new readings"; return 0; fi
    git add data/canal-rjk.json
    git -c user.name="village-canal-bot" -c user.email="canal-bot@users.noreply.github.com" \
      commit -q -m "data: canal WL.RJK.01 from village server ($n new)"
    if git push -q origin HEAD:main; then echo "$(date '+%F %T') pushed $n new readings"; return 0; fi
    echo "push rejected (attempt $attempt), retrying"; sleep $((attempt * 10))
    git fetch -q origin main && git reset -q --hard origin/main
  done
  echo "$(date '+%F %T') push failed"; return 1
}
main "$@"; exit $?
