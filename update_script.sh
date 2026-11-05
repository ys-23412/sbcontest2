#!/usr/bin/env bash
#
# Stop and start a GCP Compute Engine instance, record its external IP
# before and after, and save the new IP to a GitHub Actions variable.
#
# Requirements:
#   - gcloud CLI, authenticated (gcloud auth login, or a service account)
#   - gh CLI, authenticated (gh auth login, or GH_TOKEN set) with permission
#     to manage Actions variables on the target repo
#
# Usage:
#   ./restart-vm-update-ip.sh -p <gcp-project> -z <zone> -i <instance> \
#       -r <owner/repo> -v <VARIABLE_NAME> [-e <github-environment>]
#
# Each option can also be set with an environment variable:
#   GCP_PROJECT, GCP_ZONE, GCP_INSTANCE, GH_REPO, GH_VAR_NAME, GH_ENV
#
# Note: the IP only changes if the instance uses an *ephemeral* external IP.
# A reserved (static) IP stays the same after a restart.

set -euo pipefail

PROJECT="${GCP_PROJECT:-}"
ZONE="${GCP_ZONE:-}"
INSTANCE="${GCP_INSTANCE:-}"
REPO="${GH_REPO:-}"
VAR_NAME="${GH_VAR_NAME:-}"
GH_ENVIRONMENT="${GH_ENV:-}"
IP_WAIT_SECONDS=120

usage() {
  sed -n '3,19p' "$0" | sed 's/^# \{0,1\}//'
  exit 1
}

while getopts ":p:z:i:r:v:e:h" opt; do
  case "$opt" in
    p) PROJECT="$OPTARG" ;;
    z) ZONE="$OPTARG" ;;
    i) INSTANCE="$OPTARG" ;;
    r) REPO="$OPTARG" ;;
    v) VAR_NAME="$OPTARG" ;;
    e) GH_ENVIRONMENT="$OPTARG" ;;
    h|*) usage ;;
  esac
done

for name in PROJECT ZONE INSTANCE REPO VAR_NAME; do
  if [[ -z "${!name}" ]]; then
    echo "Error: $name is not set." >&2
    usage
  fi
done

for cmd in gcloud gh; do
  command -v "$cmd" >/dev/null || { echo "Error: '$cmd' is not installed." >&2; exit 1; }
done

log() { echo "[$(date '+%H:%M:%S')] $*"; }

get_external_ip() {
  gcloud compute instances describe "$INSTANCE" \
    --project "$PROJECT" --zone "$ZONE" \
    --format='get(networkInterfaces[0].accessConfigs[0].natIP)'
}

# 1. Record the current IP
OLD_IP="$(get_external_ip)"
log "Old IP for $INSTANCE: ${OLD_IP:-<none>}"

# 2. Stop the instance (gcloud waits until it reaches TERMINATED)
log "Stopping $INSTANCE..."
gcloud compute instances stop "$INSTANCE" --project "$PROJECT" --zone "$ZONE" --quiet

# 3. Start it again (waits until RUNNING)
log "Starting $INSTANCE..."
gcloud compute instances start "$INSTANCE" --project "$PROJECT" --zone "$ZONE" --quiet

# 4. Wait for the new external IP to be assigned
NEW_IP=""
deadline=$((SECONDS + IP_WAIT_SECONDS))
while [[ -z "$NEW_IP" && $SECONDS -lt $deadline ]]; do
  NEW_IP="$(get_external_ip)"
  [[ -z "$NEW_IP" ]] && sleep 5
done

if [[ -z "$NEW_IP" ]]; then
  echo "Error: no external IP assigned after ${IP_WAIT_SECONDS}s." >&2
  exit 1
fi
log "New IP for $INSTANCE: $NEW_IP"

# 5. Update the GitHub Actions variable
gh_args=(variable set "$VAR_NAME" --body "$NEW_IP" --repo "$REPO")
[[ -n "$GH_ENVIRONMENT" ]] && gh_args+=(--env "$GH_ENVIRONMENT")

log "Setting GitHub Actions variable $VAR_NAME on $REPO${GH_ENVIRONMENT:+ (env: $GH_ENVIRONMENT)}..."
gh "${gh_args[@]}"

echo
echo "Done."
echo "  Old IP: ${OLD_IP:-<none>}"
echo "  New IP: $NEW_IP"
if [[ "$OLD_IP" == "$NEW_IP" ]]; then
  echo "  (IP unchanged - the instance probably has a static external IP.)"
fi
