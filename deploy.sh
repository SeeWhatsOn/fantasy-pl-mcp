#!/bin/bash

# Fantasy Premier League MCP Server - Google Cloud Run Deployment Script
# 
# Prerequisites:
# 1. Install Google Cloud SDK: https://cloud.google.com/sdk/docs/install
# 2. Authenticate: gcloud auth login
# 3. Set project: gcloud config set project YOUR_PROJECT_ID
# 4. Enable required APIs:
#    - Cloud Run API: gcloud services enable run.googleapis.com
#    - Artifact Registry API: gcloud services enable artifactregistry.googleapis.com
#    - Cloud Build API: gcloud services enable cloudbuild.googleapis.com

set -e  # Exit on any error

# Configuration
PROJECT_ID=${PROJECT_ID:-$(gcloud config get-value project)}
REGION=${REGION:-"us-central1"}
SERVICE_NAME=${SERVICE_NAME:-"fpl-mcp-server"}
REGISTRY_NAME=${REGISTRY_NAME:-"remote-mcp-servers"}

echo "🚀 Deploying Fantasy Premier League MCP Server to Google Cloud Run"
echo "Project: $PROJECT_ID"
echo "Region: $REGION"
echo "Service: $SERVICE_NAME"
echo ""

# Check if project is set
if [ -z "$PROJECT_ID" ]; then
    echo "❌ Error: PROJECT_ID is not set. Please run:"
    echo "   gcloud config set project YOUR_PROJECT_ID"
    echo "   or set PROJECT_ID environment variable"
    exit 1
fi

echo "📋 Step 1: Creating Artifact Registry repository (if not exists)..."
gcloud artifacts repositories create $REGISTRY_NAME \
    --repository-format=docker \
    --location=$REGION \
    --description="Remote MCP servers" \
    --project=$PROJECT_ID 2>/dev/null || echo "Repository already exists, continuing..."

echo "🏗️  Step 2: Building and pushing container image..."
IMAGE_URL="$REGION-docker.pkg.dev/$PROJECT_ID/$REGISTRY_NAME/$SERVICE_NAME:latest"

gcloud builds submit \
    --region=$REGION \
    --tag $IMAGE_URL \
    --project=$PROJECT_ID

echo "🚀 Step 3: Deploying to Cloud Run..."
gcloud run deploy $SERVICE_NAME \
    --image $IMAGE_URL \
    --region=$REGION \
    --allow-unauthenticated \
    --memory=512Mi \
    --cpu=1 \
    --min-instances=0 \
    --max-instances=5 \
    --concurrency=80 \
    --timeout=300 \
    --cpu-throttling \
    --set-env-vars="ENVIRONMENT=production" \
    --project=$PROJECT_ID

echo "✅ Deployment complete!"
echo ""
echo "📋 Next steps:"
echo "1. Get the service URL:"
echo "   gcloud run services describe $SERVICE_NAME --region=$REGION --format='value(status.url)'"
echo ""
echo "2. Test the deployment:"
echo "   python test_server.py \$(gcloud run services describe $SERVICE_NAME --region=$REGION --format='value(status.url)')"
echo ""
echo "3. For Claude Desktop integration, use the service URL directly (no authentication required)"
echo ""
echo "⚠️  WARNING: This service is publicly accessible. Consider the following:"
echo "   - The service can be accessed by anyone on the internet"
echo "   - FPL credentials (if configured) are only accessible via environment variables"
echo "   - Monitor usage and costs via Cloud Console"