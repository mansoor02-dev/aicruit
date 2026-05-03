#!/usr/bin/env bash
# scripts/gcp/seed-secrets.sh
# Reads scripts/gcp/.gcp-secrets.env (KEY=VALUE per line, gitignored) and
# upserts each entry into Google Secret Manager.
#
# Prereqs:
#   - bash scripts/gcp/setup.sh has been run (Secret Manager API enabled)
#   - GCP_PROJECT_ID env var set
#   - The file scripts/gcp/.gcp-secrets.env exists (copy from the .example)

set -euo pipefail

: "${GCP_PROJECT_ID:?Set GCP_PROJECT_ID}"
gcloud config set project "$GCP_PROJECT_ID" >/dev/null

ENV_FILE="$(dirname "$0")/.gcp-secrets.env"
if [[ ! -f "$ENV_FILE" ]]; then
  echo "ERROR: $ENV_FILE not found."
  echo "  cp scripts/gcp/.gcp-secrets.env.example scripts/gcp/.gcp-secrets.env"
  echo "  # then fill in real values"
  exit 1
fi

echo ">> Seeding secrets from $ENV_FILE ..."
while IFS= read -r line || [[ -n "$line" ]]; do
  # skip blanks + comments
  [[ -z "${line// }" ]] && continue
  [[ "$line" =~ ^[[:space:]]*# ]] && continue

  KEY="${line%%=*}"
  VALUE="${line#*=}"
  KEY="${KEY// /}"

  if [[ -z "$KEY" || -z "$VALUE" ]]; then
    echo "  skipping malformed line: $line"
    continue
  fi

  echo "  - $KEY"
  if gcloud secrets describe "$KEY" >/dev/null 2>&1; then
    printf '%s' "$VALUE" | gcloud secrets versions add "$KEY" --data-file=-
  else
    printf '%s' "$VALUE" | gcloud secrets create "$KEY" \
      --replication-policy=automatic \
      --data-file=-
  fi
done < "$ENV_FILE"

echo ">> Done. List with:  gcloud secrets list"
