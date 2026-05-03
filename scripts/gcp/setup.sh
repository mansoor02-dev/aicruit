#!/usr/bin/env bash
# scripts/gcp/setup.sh
# One-time GCP bootstrap for AIcruit. Idempotent - safe to re-run.
#
# What this does:
#   - Sets gcloud project, enables required APIs
#   - Creates Artifact Registry repo "aicruit"
#   - Creates GCS bucket for uploads
#   - Creates Cloud SQL Postgres 15 instance + database + user
#
# Prereqs:
#   - gcloud CLI installed + `gcloud auth login` done
#   - Billing enabled on the GCP project
#   - Run from any shell with bash (Git Bash on Windows works)
#
# Required env vars:
#   GCP_PROJECT_ID   (REQUIRED)
#   DB_PASSWORD      (REQUIRED, used to create the Cloud SQL user)
# Optional:
#   GCP_REGION         default us-central1
#   GCS_BUCKET         default ${GCP_PROJECT_ID}-aicruit-uploads
#   CLOUDSQL_INSTANCE  default aicruit-db
#   DB_NAME            default aicruit
#   DB_USER            default aicruit

set -euo pipefail

: "${GCP_PROJECT_ID:?Set GCP_PROJECT_ID}"
: "${DB_PASSWORD:?Set DB_PASSWORD (the Cloud SQL user password to create)}"

GCP_REGION="${GCP_REGION:-us-central1}"
GCS_BUCKET="${GCS_BUCKET:-${GCP_PROJECT_ID}-aicruit-uploads}"
CLOUDSQL_INSTANCE="${CLOUDSQL_INSTANCE:-aicruit-db}"
DB_NAME="${DB_NAME:-aicruit}"
DB_USER="${DB_USER:-aicruit}"

echo "=== Resolved configuration ==="
echo "  Project:           $GCP_PROJECT_ID"
echo "  Region:            $GCP_REGION"
echo "  GCS bucket:        gs://$GCS_BUCKET"
echo "  Cloud SQL:         $CLOUDSQL_INSTANCE"
echo "  DB name / user:    $DB_NAME / $DB_USER"
echo "==============================="

echo ">> Setting active project..."
gcloud config set project "$GCP_PROJECT_ID"

echo ">> Enabling APIs (this can take a minute)..."
gcloud services enable \
  run.googleapis.com \
  sqladmin.googleapis.com \
  secretmanager.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  texttospeech.googleapis.com \
  storage.googleapis.com

echo ">> Creating Artifact Registry repo 'aicruit' (Docker, $GCP_REGION)..."
gcloud artifacts repositories create aicruit \
  --repository-format=docker \
  --location="$GCP_REGION" \
  --description="AIcruit container images" 2>/dev/null || echo "   (already exists)"

echo ">> Creating GCS bucket gs://$GCS_BUCKET ..."
gcloud storage buckets create "gs://$GCS_BUCKET" \
  --location="$GCP_REGION" \
  --uniform-bucket-level-access 2>/dev/null || echo "   (already exists)"

echo ">> Creating Cloud SQL instance $CLOUDSQL_INSTANCE (db-f1-micro, postgres 15)..."
# NOTE: Using public IP for simplicity. For production, prefer --no-assign-ip plus
# a Serverless VPC connector + private IP. Cloud Run can reach Cloud SQL over the
# Cloud SQL Auth Proxy regardless of public/private IP via --add-cloudsql-instances.
if ! gcloud sql instances describe "$CLOUDSQL_INSTANCE" >/dev/null 2>&1; then
  gcloud sql instances create "$CLOUDSQL_INSTANCE" \
    --database-version=POSTGRES_15 \
    --tier=db-f1-micro \
    --region="$GCP_REGION" \
    --storage-size=10GB \
    --storage-type=SSD \
    --backup
else
  echo "   (already exists)"
fi

echo ">> Creating database $DB_NAME ..."
gcloud sql databases create "$DB_NAME" --instance="$CLOUDSQL_INSTANCE" 2>/dev/null \
  || echo "   (already exists)"

echo ">> Creating DB user $DB_USER ..."
if gcloud sql users list --instance="$CLOUDSQL_INSTANCE" --format='value(name)' | grep -qx "$DB_USER"; then
  echo "   (user exists - updating password)"
  gcloud sql users set-password "$DB_USER" --instance="$CLOUDSQL_INSTANCE" --password="$DB_PASSWORD"
else
  gcloud sql users create "$DB_USER" --instance="$CLOUDSQL_INSTANCE" --password="$DB_PASSWORD"
fi

CONNECTION_NAME="$(gcloud sql instances describe "$CLOUDSQL_INSTANCE" --format='value(connectionName)')"

cat <<DONE

=================================================================
SETUP COMPLETE.

Cloud SQL connection name:  $CONNECTION_NAME
Suggested DATABASE_URL (for Cloud Run via Cloud SQL Auth Proxy unix socket):
  postgresql+psycopg2://${DB_USER}:${DB_PASSWORD}@/${DB_NAME}?host=/cloudsql/${CONNECTION_NAME}

Next steps:
  1. cp scripts/gcp/.gcp-secrets.env.example scripts/gcp/.gcp-secrets.env
     # then fill in real values (Gemini, Groq, OpenRouter, Cognito, DATABASE_URL above)
  2. bash scripts/gcp/seed-secrets.sh
  3. bash scripts/gcp/deploy-all.sh

Manual steps you may still need:
  - Apply database/schema.sql against the new Cloud SQL DB (run init_db.py
    from a Cloud Shell or via the Cloud SQL Auth Proxy locally).
  - Grant the Cloud Run runtime service account access to GCS + Secret Manager:
      roles/secretmanager.secretAccessor
      roles/storage.objectAdmin (only on the uploads bucket)
      roles/cloudsql.client
  - Set FRONTEND_ORIGINS on each deployed service to your Vercel URL.
=================================================================
DONE
