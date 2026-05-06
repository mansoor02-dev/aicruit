#!/usr/bin/env bash
# scripts/gcp/deploy.sh
# Build + deploy ONE AIcruit service to Cloud Run.
#
# Usage:    bash scripts/gcp/deploy.sh <service-name>
# Services: gateway | file-service | resume-parser | transcribe-audio
#           question-generation | text-to-speech | report-generation
#
# Per-service env wiring (declared in the case statement below):
#   gateway              -> public; uses DATABASE_URL + Cognito secrets + all *_URL upstreams
#   file-service         -> public; GCS_BUCKET, DATABASE_URL
#   resume-parser        -> internal; GEMINI_API_KEY
#   question-generation  -> internal; OPENROUTER_API_KEY
#   transcribe-audio     -> internal; GROQ_API_KEY
#   text-to-speech       -> internal; (uses Cloud TTS or local Piper)
#   report-generation    -> internal; OPENROUTER_API_KEY, DATABASE_URL
#
# Prereqs:
#   - setup.sh + seed-secrets.sh already run
#   - GCP_PROJECT_ID env var set
#   - For services that need to know upstream URLs, pass them as env vars:
#       FILE_SERVICE_URL, RESUME_PARSER_URL, QUESTION_GEN_URL, TRANSCRIBE_URL,
#       TTS_URL, REPORT_GEN_URL
#     deploy-all.sh discovers + injects these automatically.

set -euo pipefail

SERVICE="${1:-}"
if [[ -z "$SERVICE" ]]; then
  echo "Usage: bash scripts/gcp/deploy.sh <service-name>"
  exit 1
fi

: "${GCP_PROJECT_ID:?Set GCP_PROJECT_ID}"
GCP_REGION="${GCP_REGION:-us-central1}"
CLOUDSQL_INSTANCE="${CLOUDSQL_INSTANCE:-aicruit-db}"
GCS_BUCKET="${GCS_BUCKET:-${GCP_PROJECT_ID}-aicruit-uploads}"
FRONTEND_ORIGINS="${FRONTEND_ORIGINS:-*}"

CONNECTION_NAME="${GCP_PROJECT_ID}:${GCP_REGION}:${CLOUDSQL_INSTANCE}"
IMAGE_BASE="${GCP_REGION}-docker.pkg.dev/${GCP_PROJECT_ID}/aicruit"

# ---- service-name -> source-dir / cloud-run name / port / config ----
SRC_DIR=""
RUN_NAME=""
PORT=""
ENV_VARS=""        # comma-separated KEY=VAL
SECRETS=""         # comma-separated KEY=SECRET_NAME:latest
NEEDS_SQL="false"
PUBLIC="false"

_resolve() { gcloud run services describe "$1" --region="$GCP_REGION" --format='value(status.url)' 2>/dev/null || true; }

case "$SERVICE" in
  gateway)
    SRC_DIR="gateway"
    RUN_NAME="gateway"
    PORT="8000"
    PUBLIC="true"
    NEEDS_SQL="true"
    # Auto-resolve sibling service URLs from Cloud Run if not pre-exported.
    # Lets `bash deploy.sh gateway` work standalone (not just via deploy-all.sh).
    : "${FILE_SERVICE_URL:=$(_resolve file-service)}"
    : "${RESUME_PARSER_URL:=$(_resolve resume-parser)}"
    : "${QUESTION_GEN_URL:=$(_resolve question-generation)}"
    : "${TRANSCRIBE_URL:=$(_resolve transcribe-audio)}"
    : "${TTS_URL:=$(_resolve text-to-speech)}"
    : "${REPORT_GEN_URL:=$(_resolve report-generation)}"
    for v in FILE_SERVICE_URL RESUME_PARSER_URL QUESTION_GEN_URL TRANSCRIBE_URL TTS_URL REPORT_GEN_URL; do
      if [ -z "${!v}" ]; then
        echo "ERROR: $v is empty. Deploy that upstream service first, or export $v before running this." >&2
        exit 1
      fi
    done
    ENV_VARS="FRONTEND_ORIGINS=${FRONTEND_ORIGINS},FILE_SERVICE_URL=${FILE_SERVICE_URL},RESUME_PARSER_URL=${RESUME_PARSER_URL},QUESTION_GEN_URL=${QUESTION_GEN_URL},TRANSCRIBE_URL=${TRANSCRIBE_URL},TTS_URL=${TTS_URL},REPORT_GEN_URL=${REPORT_GEN_URL}"
    SECRETS="DATABASE_URL=DATABASE_URL:latest,COGNITO_CLIENT_ID=COGNITO_CLIENT_ID:latest,COGNITO_CLIENT_SECRET=COGNITO_CLIENT_SECRET:latest,COGNITO_USER_POOL_ID=COGNITO_USER_POOL_ID:latest,COGNITO_REGION=COGNITO_REGION:latest"
    ;;
  file-service)
    SRC_DIR="services/file-service"
    RUN_NAME="file-service"
    PORT="8005"
    PUBLIC="true"
    NEEDS_SQL="true"
    ENV_VARS="FRONTEND_ORIGINS=${FRONTEND_ORIGINS},GCS_BUCKET=${GCS_BUCKET},STORAGE_BACKEND=gcs"
    SECRETS="DATABASE_URL=DATABASE_URL:latest"
    ;;
  resume-parser)
    SRC_DIR="services/resume-parser"
    RUN_NAME="resume-parser"
    PORT="8006"
    NEEDS_SQL="true"
    : "${FILE_SERVICE_URL:=$(_resolve file-service)}"
    [ -z "$FILE_SERVICE_URL" ] && { echo "ERROR: FILE_SERVICE_URL empty (deploy file-service first)" >&2; exit 1; }
    ENV_VARS="FRONTEND_ORIGINS=${FRONTEND_ORIGINS},FILE_SERVICE_URL=${FILE_SERVICE_URL}"
    SECRETS="GEMINI_API_KEY=GEMINI_API_KEY:latest,DATABASE_URL=DATABASE_URL:latest"
    ;;
  transcribe-audio)
    SRC_DIR="services/transcribe-audio"
    RUN_NAME="transcribe-audio"
    PORT="8007"
    ENV_VARS="FRONTEND_ORIGINS=${FRONTEND_ORIGINS}"
    SECRETS="GROQ_API_KEY=GROQ_API_KEY:latest"
    ;;
  question-generation)
    SRC_DIR="services/question-generation"
    RUN_NAME="question-generation"
    PORT="8010"
    NEEDS_SQL="true"
    : "${FILE_SERVICE_URL:=$(_resolve file-service)}"
    [ -z "$FILE_SERVICE_URL" ] && { echo "ERROR: FILE_SERVICE_URL empty (deploy file-service first)" >&2; exit 1; }
    ENV_VARS="FRONTEND_ORIGINS=${FRONTEND_ORIGINS},EMBEDDING_MODEL=gemini-embedding-001,EMBEDDING_DIMS=768,FILE_SERVICE_URL=${FILE_SERVICE_URL}"
    SECRETS="GEMINI_API_KEY=GEMINI_API_KEY:latest,OPENROUTER_API_KEY=OPENROUTER_API_KEY:latest,DATABASE_URL=DATABASE_URL:latest"
    ;;
  text-to-speech)
    SRC_DIR="services/text-to-speech"
    RUN_NAME="text-to-speech"
    PORT="8011"
    ENV_VARS="FRONTEND_ORIGINS=${FRONTEND_ORIGINS}"
    SECRETS=""
    ;;
  report-generation)
    SRC_DIR="services/report-generation"
    RUN_NAME="report-generation"
    PORT="8012"
    NEEDS_SQL="true"
    : "${FILE_SERVICE_URL:=$(_resolve file-service)}"
    [ -z "$FILE_SERVICE_URL" ] && { echo "ERROR: FILE_SERVICE_URL empty (deploy file-service first)" >&2; exit 1; }
    ENV_VARS="FRONTEND_ORIGINS=${FRONTEND_ORIGINS},FILE_SERVICE_URL=${FILE_SERVICE_URL}"
    SECRETS="OPENROUTER_API_KEY=OPENROUTER_API_KEY:latest,DATABASE_URL=DATABASE_URL:latest"
    ;;
  *)
    echo "Unknown service: $SERVICE"
    exit 1
    ;;
esac

if [[ ! -d "$SRC_DIR" ]]; then
  echo "ERROR: source dir '$SRC_DIR' not found. Run from repo root."
  exit 1
fi

IMAGE="${IMAGE_BASE}/${RUN_NAME}:latest"

echo "=== Deploying $SERVICE ==="
echo "  Source dir:       $SRC_DIR"
echo "  Cloud Run name:   $RUN_NAME"
echo "  Image:            $IMAGE"
echo "  Port:             $PORT"
echo "  Public:           $PUBLIC"
echo "  Cloud SQL:        $([[ $NEEDS_SQL == true ]] && echo $CONNECTION_NAME || echo none)"
echo "  Env vars:         $ENV_VARS"
echo "  Secrets:          ${SECRETS:-(none)}"
echo "==========================="

# Services that import from the repo-root shared/ package need it copied
# into their build context, since `gcloud builds submit` only uploads SRC_DIR.
NEEDS_SHARED="false"
case "$SERVICE" in
  resume-parser|question-generation|report-generation)
    NEEDS_SHARED="true"
    ;;
esac

if [ "$NEEDS_SHARED" = "true" ]; then
  if [ ! -d "shared" ]; then
    echo "ERROR: shared/ directory not found at repo root. Run deploy.sh from repo root." >&2
    exit 1
  fi
  echo ">> Vendoring shared/ into $SRC_DIR/shared (pre-build)"
  rm -rf "$SRC_DIR/shared"
  cp -r shared "$SRC_DIR/shared"
  trap 'rm -rf "$SRC_DIR/shared"' EXIT
fi

echo ">> Building image with Cloud Build..."
gcloud builds submit --tag "$IMAGE" "$SRC_DIR"

echo ">> Deploying to Cloud Run..."
DEPLOY_ARGS=(
  run deploy "$RUN_NAME"
  --image="$IMAGE"
  --region="$GCP_REGION"
  --platform=managed
  --port="$PORT"
  --memory=1Gi
  --cpu=1
  --timeout=900
  --concurrency=20
)

if [[ "$PUBLIC" == "true" ]]; then
  DEPLOY_ARGS+=(--allow-unauthenticated)
else
  DEPLOY_ARGS+=(--no-allow-unauthenticated)
fi

if [[ "$NEEDS_SQL" == "true" ]]; then
  DEPLOY_ARGS+=(--add-cloudsql-instances="$CONNECTION_NAME")
fi

if [[ -n "$ENV_VARS" ]]; then
  DEPLOY_ARGS+=(--set-env-vars="$ENV_VARS")
fi

if [[ -n "$SECRETS" ]]; then
  DEPLOY_ARGS+=(--set-secrets="$SECRETS")
fi

gcloud "${DEPLOY_ARGS[@]}"

URL="$(gcloud run services describe "$RUN_NAME" --region="$GCP_REGION" --format='value(status.url)')"
echo ">> Deployed: $URL"
