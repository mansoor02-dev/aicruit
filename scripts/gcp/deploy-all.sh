#!/usr/bin/env bash
# scripts/gcp/deploy-all.sh
# Deploys every AIcruit service to Cloud Run in dependency order, threading
# each upstream Cloud Run URL into the next deploy via env vars.
#
# Order:
#   1. file-service          (gateway needs FILE_SERVICE_URL)
#   2. resume-parser
#   3. question-generation
#   4. transcribe-audio
#   5. text-to-speech
#   6. report-generation
#   7. gateway               (last - needs every upstream URL)
#
# Prereqs:
#   - setup.sh + seed-secrets.sh have been run
#   - GCP_PROJECT_ID env var set

set -euo pipefail

: "${GCP_PROJECT_ID:?Set GCP_PROJECT_ID}"
GCP_REGION="${GCP_REGION:-us-central1}"
export GCP_PROJECT_ID GCP_REGION

HERE="$(cd "$(dirname "$0")" && pwd)"

get_url() {
  gcloud run services describe "$1" --region="$GCP_REGION" --format='value(status.url)' 2>/dev/null || true
}

echo "=== Deploying all AIcruit services to project $GCP_PROJECT_ID ($GCP_REGION) ==="

bash "$HERE/deploy.sh" file-service
export FILE_SERVICE_URL="$(get_url file-service)"
echo ">> FILE_SERVICE_URL=$FILE_SERVICE_URL"

bash "$HERE/deploy.sh" resume-parser
export RESUME_PARSER_URL="$(get_url resume-parser)"
echo ">> RESUME_PARSER_URL=$RESUME_PARSER_URL"

bash "$HERE/deploy.sh" question-generation
export QUESTION_GEN_URL="$(get_url question-generation)"
echo ">> QUESTION_GEN_URL=$QUESTION_GEN_URL"

bash "$HERE/deploy.sh" transcribe-audio
export TRANSCRIBE_URL="$(get_url transcribe-audio)"
echo ">> TRANSCRIBE_URL=$TRANSCRIBE_URL"

bash "$HERE/deploy.sh" text-to-speech
export TTS_URL="$(get_url text-to-speech)"
echo ">> TTS_URL=$TTS_URL"

bash "$HERE/deploy.sh" report-generation
export REPORT_GEN_URL="$(get_url report-generation)"
echo ">> REPORT_GEN_URL=$REPORT_GEN_URL"

bash "$HERE/deploy.sh" gateway
GATEWAY_URL="$(get_url gateway)"

cat <<DONE

=================================================================
ALL SERVICES DEPLOYED.

Gateway (point your frontend NEXT_PUBLIC_API_URL at this):
  $GATEWAY_URL

Internal service URLs:
  FILE_SERVICE_URL    = $FILE_SERVICE_URL
  RESUME_PARSER_URL   = $RESUME_PARSER_URL
  QUESTION_GEN_URL    = $QUESTION_GEN_URL
  TRANSCRIBE_URL      = $TRANSCRIBE_URL
  TTS_URL             = $TTS_URL
  REPORT_GEN_URL      = $REPORT_GEN_URL

Manual follow-ups:
  - Allow the gateway's runtime SA to invoke each internal service:
      gcloud run services add-iam-policy-binding <svc> \
        --region=$GCP_REGION --member=serviceAccount:<gateway-SA> \
        --role=roles/run.invoker
  - Set FRONTEND_ORIGINS on every service to your real Vercel URL.
  - Apply database/schema.sql against Cloud SQL (init_db.py via Cloud Shell
    or the Cloud SQL Auth Proxy).
=================================================================
DONE
