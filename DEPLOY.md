# Deployment Guide

This guide walks you through deploying AIcruit to Google Cloud Platform (GCP) and Vercel. It assumes no prior GCP experience.

## What you are deploying and why GCP

AIcruit's backend is a gateway plus six FastAPI microservices, all containerized. We deploy them to **Cloud Run** (serverless containers, scales to zero), with **Cloud SQL** for Postgres, **Cloud Storage (GCS)** for uploaded files (resumes, snapshots), **Secret Manager** for API keys, and **Artifact Registry** for the built images. The frontend (Next.js) ships to **Vercel** since that is the cheapest, fastest path for a Next.js App Router site. Co-locating everything in one GCP region keeps egress cheap and latency low.

## Prerequisites

1. Install the [gcloud CLI](https://cloud.google.com/sdk/docs/install).
2. Authenticate:
   ```sh
   gcloud auth login
   gcloud auth application-default login
   ```
3. Create a GCP project at [console.cloud.google.com](https://console.cloud.google.com), enable billing on it, and note the project ID.
4. Pick a region. **Use `us-central1`** - Cloud Run, Cloud SQL, and Cloud TTS are all available there at the lowest tier.

## One-time setup

### 1. Set environment variables

```sh
export GCP_PROJECT_ID=your-project-id
export GCP_REGION=us-central1
export GCS_BUCKET=${GCP_PROJECT_ID}-aicruit-files
export CLOUD_SQL_INSTANCE=${GCP_PROJECT_ID}:${GCP_REGION}:aicruit-db
```

### 2. Run the bootstrap script

```sh
bash scripts/gcp/setup.sh
```

This enables required APIs (Cloud Run, Cloud SQL, Secret Manager, Artifact Registry, Cloud TTS, Cloud Build), creates the Artifact Registry repo, the GCS bucket, and the Cloud SQL instance (`db-f1-micro`).

### 3. Bootstrap the database schema

The Cloud SQL instance is empty. Apply `database/schema.sql` once:

```sh
# Option A: gcloud sql connect (simplest)
gcloud sql connect aicruit-db --user=postgres --database=aicruit < database/schema.sql

# Option B: Cloud SQL Auth Proxy (preferred for repeat use)
# Download proxy: https://cloud.google.com/sql/docs/postgres/sql-proxy
./cloud-sql-proxy $CLOUD_SQL_INSTANCE &
psql "host=127.0.0.1 port=5432 user=postgres dbname=aicruit" -f database/schema.sql
```

### 4. Seed secrets

```sh
cp scripts/gcp/.gcp-secrets.env.example scripts/gcp/.gcp-secrets.env
# Edit .gcp-secrets.env and fill in real values for:
#   GEMINI_API_KEY, GROQ_API_KEY, OPENROUTER_API_KEY,
#   COGNITO_CLIENT_ID, COGNITO_CLIENT_SECRET, COGNITO_USER_POOL_ID,
#   COGNITO_REGION, DATABASE_URL, FRONTEND_ORIGINS

bash scripts/gcp/seed-secrets.sh
```

This pushes each value into Secret Manager. The file `.gcp-secrets.env` is gitignored - keep it local.

### 5. Create the Cloud Run service account

```sh
gcloud iam service-accounts create aicruit-runtime \
  --display-name="AIcruit Cloud Run runtime"

SA="aicruit-runtime@${GCP_PROJECT_ID}.iam.gserviceaccount.com"

# Read secrets at runtime
gcloud projects add-iam-policy-binding $GCP_PROJECT_ID \
  --member="serviceAccount:$SA" --role="roles/secretmanager.secretAccessor"

# Connect to Cloud SQL
gcloud projects add-iam-policy-binding $GCP_PROJECT_ID \
  --member="serviceAccount:$SA" --role="roles/cloudsql.client"

# Read/write the GCS bucket
gcloud storage buckets add-iam-policy-binding gs://$GCS_BUCKET \
  --member="serviceAccount:$SA" --role="roles/storage.objectAdmin"

# Use Cloud TTS
gcloud projects add-iam-policy-binding $GCP_PROJECT_ID \
  --member="serviceAccount:$SA" --role="roles/cloudtts.user"
```

## First deploy

```sh
bash scripts/gcp/deploy-all.sh
```

This builds each Docker image, pushes to Artifact Registry, and deploys each service to Cloud Run with the correct secrets, Cloud SQL connection, and service account. Expect **10-15 minutes** total on a first run (subsequent builds are cached).

When it finishes, the script prints each service URL. Save the **gateway URL** - you will need it for the frontend.

## Subsequent deploys

### Deploy one service

```sh
bash scripts/gcp/deploy.sh question-generation
```

About **2 minutes**. Cloud Run does a rolling update - zero downtime, traffic shifts to the new revision once it is healthy.

### Deploy all services

```sh
bash scripts/gcp/deploy-all.sh
```

### Rollback

List revisions, then pin traffic to a previous one:

```sh
gcloud run revisions list --service=gateway --region=$GCP_REGION
gcloud run services update-traffic gateway \
  --to-revisions=gateway-00007-abc=100 --region=$GCP_REGION
```

### Logs

```sh
gcloud run services logs tail gateway --region=$GCP_REGION
```

### Optional: auto-deploy on git push

Add a `cloudbuild.yaml` and a Cloud Build trigger pointed at your GitHub repo to deploy on every push to `main`. See [Cloud Build triggers docs](https://cloud.google.com/build/docs/automating-builds/create-manage-triggers). Out of scope here.

## Local testing

Nothing about local dev changed. From the repo root:

```sh
docker compose -f infra/docker/docker-compose.yml up --build
cd frontend && npm run dev
```

### What you need locally

- A `.env` file per service under `services/<name>/.env`. Each service has a `.env.example` showing the required keys (mostly `GEMINI_API_KEY`, `GROQ_API_KEY`, `OPENROUTER_API_KEY`).
- `STORAGE_BACKEND=local` (default) keeps file-service writing to a local volume - no GCS needed.

### Google Cloud TTS locally

text-to-speech now uses the Cloud TTS API. Download a service account JSON key from the GCP console (the `aicruit-runtime` SA works) and save it to:

- **Linux / macOS**: `~/.config/aicruit/gcp-sa.json`
- **Windows**: `%USERPROFILE%\.config\aicruit\gcp-sa.json`

`docker-compose.yml` mounts that path into the text-to-speech container and sets `GOOGLE_APPLICATION_CREDENTIALS` for you.

### Point local frontend at deployed backend

Skip running the backend locally - just edit `frontend/.env.local`:

```
NEXT_PUBLIC_API_URL=https://gateway-xxxxx.a.run.app
```

Then `npm run dev`. Useful for frontend-only iterations.

## Frontend - Vercel deploy

1. Go to [vercel.com](https://vercel.com), import your GitHub repo.
2. Set **Root Directory** to `frontend/`.
3. Add environment variable: `NEXT_PUBLIC_API_URL` = your gateway Cloud Run URL.
4. Deploy. Push to `main` -> auto-redeploys. Custom domains under the Vercel project settings.

### Important: update CORS after first Vercel deploy

Vercel will give you a URL like `https://aicruit-abc.vercel.app`. Add it to the gateway's `FRONTEND_ORIGINS` secret (comma-separated if multiple), then redeploy the gateway:

```sh
echo -n "https://aicruit-abc.vercel.app,https://your-custom-domain.com" | \
  gcloud secrets versions add FRONTEND_ORIGINS --data-file=-
bash scripts/gcp/deploy.sh gateway
```

Without this step, the browser blocks every request with a CORS error.

## Cost expectations

| Component | Idle | Light traffic |
|---|---|---|
| Cloud Run (7 services) | $0 (scales to zero) | $0-5/mo |
| Cloud SQL (db-f1-micro) | ~$10/mo | ~$10/mo |
| GCS | $0 | <$1/mo |
| Secret Manager | $0 | <$1/mo |
| Cloud TTS | $0 (4M chars free/mo) | $0 |
| Artifact Registry | $0 | <$1/mo |
| Vercel (frontend) | $0 | $0 |
| **Total** | **~$10/mo** | **~$10-20/mo** |

The fixed cost is essentially Cloud SQL. Everything else scales to zero.

## Common troubleshooting

- **"Permission denied on secret"** - the runtime service account is missing `roles/secretmanager.secretAccessor`. Re-run the IAM binding from setup step 5.
- **"Cloud SQL connection failed"** - the service was deployed without `--add-cloudsql-instances`. Check `scripts/gcp/deploy.sh` and redeploy.
- **CORS error in browser** - `FRONTEND_ORIGINS` does not include your frontend URL. Update the secret and redeploy the gateway.
- **TTS returns 403** - service account missing `roles/cloudtts.user`. Add it.
- **First request takes 5-10s (503 / cold start)** - Cloud Run scaled to zero. Set `--min-instances=1` on the gateway if this matters; adds ~$5/mo.

## Migrating off AWS Cognito (optional, future)

Cognito is the only remaining AWS dependency. If you want to consolidate on GCP, swap `gateway/app/routes/auth.py` to use **Firebase Auth** or **Identity Platform** (same product, different SKU). Out of scope for this guide, but flagged so you know it is the last cord to cut.
