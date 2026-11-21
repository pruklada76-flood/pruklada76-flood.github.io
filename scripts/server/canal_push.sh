#!/usr/bin/env bash
# Run from cron on the village server: fetch canal WL.RJK.01 and rain RF.TKU.01 from the BMA site and push
# data/canal-rjk.json and data/rain-tku.json.
# Needs: git, python3, a clone of this repo made with a write-enabled deploy key (see scripts/server/README.md).
# Settings via environment (all optional):
#   CANAL_REPO   path of the clone              (default: the repo this script lives in, else ~/canal-bot)
#   CANAL_KEY    SSH private key for the deploy key (default: ~/.ssh/pruklada_deploy)
#   CANAL_CA     extra CA/intermediate PEM for the BMA site, only if TLS verification fails
# The whole body is inside main() so bash parses it before `git reset` can replace this file.
main() {
  set -euo pipefail
  # bma_canal.py is run from the folder this script is in, not from the clone. Copy both files to a folder
  # outside the clone (see README, "hardening") so a push to the repo can never run new code on the server.
  local here; here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  local repo="${CANAL_REPO:-}"
  if [ -z "$repo" ]; then
    if [ -d "$here/../../.git" ]; then repo="$(cd "$here/../.." && pwd)"; else repo="$HOME/canal-bot"; fi
  fi
  local key="${CANAL_KEY:-$HOME/.ssh/pruklada_deploy}"
  export GIT_SSH_COMMAND="ssh -i $key -o IdentitiesOnly=yes -o BatchMode=yes"
  tmp="$(mktemp -d)"; trap 'rm -rf "${tmp:?}"' EXIT   # global, not local: the EXIT trap runs after main() returns
  exec 9>"${TMPDIR:-/tmp}/canal_push.lock"
  flock -n 9 || { echo "$(date '+%F %T') another run is still going"; return 0; }
  cd "$repo"
  git fetch -q origin main && git reset -q --hard origin/main     # this clone is only for the bot

  local ca=(); [ -n "${CANAL_CA:-}" ] && ca=(--ca-file "$CANAL_CA")
  local kinds="" k
  # canal -> data/canal-rjk.json, rain -> data/rain-tku.json; one failing does not stop the other
  for k in canal rain; do
    if python3 -I "$here/bma_canal.py" fetch --kind "$k" ${ca[@]+"${ca[@]}"} > "$tmp/$k.json"; then kinds="$kinds $k"
    else echo "$(date '+%F %T') $k fetch failed"; fi
  done
  [ -n "$kinds" ] || return 1

  for attempt in 1 2 3 4; do
    local msg="" n
    for k in $kinds; do
      local f=data/canal-rjk.json; [ "$k" = rain ] && f=data/rain-tku.json
      n="$(python3 -I "$here/bma_canal.py" merge --kind "$k" "$tmp/$k.json" "$f")"
      if [ "$n" != "0" ]; then git add "$f"; msg="$msg $k +$n"; fi
    done
    if [ -z "$msg" ]; then echo "$(date '+%F %T') no new readings"; return 0; fi
    git -c user.name="village-canal-bot" -c user.email="canal-bot@users.noreply.github.com" \
      commit -q -m "data: BMA from village server:$msg"
    if git push -q origin HEAD:main; then echo "$(date '+%F %T') pushed:$msg"; return 0; fi
    echo "push rejected (attempt $attempt), retrying"; sleep $((attempt * 10))
    git fetch -q origin main && git reset -q --hard origin/main
  done
  echo "$(date '+%F %T') push failed"; return 1
}
main "$@"; exit $?
