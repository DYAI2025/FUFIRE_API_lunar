# Cloud Run Setup — One-Time Commands

## Voraussetzungen
- `gcloud` CLI installiert und eingeloggt (`gcloud auth login`)

```bash
export PROJECT_ID=bazodiac
export REGION=europe-west1
export SERVICE=fufireapi
```

## 1. APIs aktivieren

```bash
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  iam.googleapis.com \
  --project=$PROJECT_ID
```

## 2. Artifact Registry Repo anlegen

```bash
gcloud artifacts repositories create fufire \
  --project=$PROJECT_ID \
  --location=$REGION \
  --repository-format=docker \
  --description="FuFirE API images"
```

## 3. Service Account für Deployments

```bash
gcloud iam service-accounts create fufire-deployer \
  --project=$PROJECT_ID \
  --display-name="FuFirE Deployer"

SA_EMAIL="fufire-deployer@$PROJECT_ID.iam.gserviceaccount.com"

# Nötige Rollen
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SA_EMAIL" \
  --role="roles/run.admin"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SA_EMAIL" \
  --role="roles/artifactregistry.writer"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SA_EMAIL" \
  --role="roles/iam.serviceAccountUser"
```

## 4a. Option A: GitHub Actions via Workload Identity Federation (empfohlen, kein Key)

```bash
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')

# WIF Pool anlegen
gcloud iam workload-identity-pools create "github" \
  --project=$PROJECT_ID \
  --location="global" \
  --display-name="GitHub Actions"

# OIDC Provider
gcloud iam workload-identity-pools providers create-oidc "github-provider" \
  --project=$PROJECT_ID \
  --location="global" \
  --workload-identity-pool="github" \
  --issuer-uri="https://token.actions.githubusercontent.com" \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository" \
  --attribute-condition="assertion.repository=='DYAI2025/FuFirE'"

# SA erlauben, von GitHub Actions zu impersonieren
gcloud iam service-accounts add-iam-policy-binding $SA_EMAIL \
  --project=$PROJECT_ID \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/\$PROJECT_NUMBER/locations/global/workloadIdentityPools/github/attribute.repository/DYAI2025/FuFirE"

# WIF Provider URL (als GitHub Secret setzen)
echo "GCP_WIF_PROVIDER:"
echo "projects/$PROJECT_NUMBER/locations/global/workloadIdentityPools/github/providers/github-provider"
```

### GitHub Secrets setzen

Unter https://github.com/DYAI2025/FuFirE/settings/secrets/actions:

| Secret | Wert |
|--------|------|
| `GCP_WIF_PROVIDER` | `projects/58392391307/locations/global/workloadIdentityPools/github/providers/github-provider` |
| `GCP_SA_EMAIL` | `fufire-deployer@bazodiac.iam.gserviceaccount.com` |

## 4b. Option B: Service Account Key (einfacher, aber weniger sicher)

```bash
gcloud iam service-accounts keys create /tmp/fufire-sa-key.json \
  --iam-account=$SA_EMAIL \
  --project=$PROJECT_ID

# Inhalt als GitHub Secret GCP_SA_KEY setzen
cat /tmp/fufire-sa-key.json
rm /tmp/fufire-sa-key.json  # lokal löschen!
```

Im Workflow dann ersetzen:
```yaml
with:
  credentials_json: ${{ secrets.GCP_SA_KEY }}
  # statt workload_identity_provider + service_account
```

## 5. Cloud Run Service initial anlegen (ersetzt Placeholder)

```bash
IMAGE="$REGION-docker.pkg.dev/$PROJECT_ID/fufire/fufire-api:latest"

# Erst lokal bauen und pushen:
gcloud auth configure-docker $REGION-docker.pkg.dev
docker build -t $IMAGE .
docker push $IMAGE

# Service deployen (ersetzt Placeholder):
gcloud run deploy $SERVICE \
  --image=$IMAGE \
  --region=$REGION \
  --platform=managed \
  --allow-unauthenticated \
  --port=8080 \
  --memory=512Mi \
  --cpu=1 \
  --min-instances=0 \
  --max-instances=10 \
  --set-env-vars=FUFIRE_REQUIRE_API_KEYS=true,WEBHOOK_HMAC_ONLY=true \
  --project=$PROJECT_ID
```

## 6. Überprüfen

```bash
gcloud run services describe $SERVICE \
  --region=$REGION \
  --project=$PROJECT_ID \
  --format='value(status.url)'

# Health check
curl "$(gcloud run services describe $SERVICE --region=$REGION --project=$PROJECT_ID --format='value(status.url)')/health"
```

## Deployment Flow danach

Nach diesem Setup deployed GitHub Actions automatisch bei jedem Push auf `main`:
1. Docker-Image bauen (mit Ephemeris-Cache ~3 min, cold ~8 min)
2. Image nach Artifact Registry pushen
3. Cloud Run aktualisieren
4. Health check
