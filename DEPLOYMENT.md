# Fantasy Premier League MCP Server - Google Cloud Run Deployment

This guide will help you deploy the Fantasy Premier League MCP server to Google Cloud Run for remote access.

## Prerequisites

1. **Google Cloud SDK**: Install from https://cloud.google.com/sdk/docs/install
2. **Authentication**: Run `gcloud auth login`
3. **Project Setup**: 
   ```bash
   gcloud config set project YOUR_PROJECT_ID
   ```
4. **Enable Required APIs**:
   ```bash
   gcloud services enable run.googleapis.com
   gcloud services enable artifactregistry.googleapis.com
   gcloud services enable cloudbuild.googleapis.com
   ```

## Deployment Options

### Option 1: Automated Deployment Script

Run the deployment script:

```bash
chmod +x deploy.sh
./deploy.sh
```

### Option 2: Manual Deployment

#### Step 1: Create Artifact Registry Repository

```bash
gcloud artifacts repositories create remote-mcp-servers \
  --repository-format=docker \
  --location=us-central1 \
  --description="Remote MCP servers"
```

#### Step 2: Build and Push Container

```bash
# Build and push using Cloud Build
gcloud builds submit --region=us-central1 \
  --tag us-central1-docker.pkg.dev/$PROJECT_ID/remote-mcp-servers/fpl-mcp-server:latest
```

#### Step 3: Deploy to Cloud Run

```bash
gcloud run deploy fpl-mcp-server \
  --image us-central1-docker.pkg.dev/$PROJECT_ID/remote-mcp-servers/fpl-mcp-server:latest \
  --region=us-central1 \
  --allow-unauthenticated \
  --memory=1Gi \
  --cpu=1 \
  --max-instances=10
```

### Option 3: Deploy from Source (Simplest)

```bash
gcloud run deploy fpl-mcp-server \
  --allow-unauthenticated \
  --region=us-central1 \
  --source .
```

## Configuration

### Environment Variables

The server supports these environment variables:

- `PORT`: Port number (set automatically by Cloud Run)
- `ENVIRONMENT`: Set to "production" for Cloud Run
- `FPL_EMAIL`: Fantasy Premier League account email (if using authenticated features)
- `FPL_PASSWORD`: Fantasy Premier League account password (if using authenticated features)
- `CACHE_TTL`: Cache time-to-live in seconds (default: 300)

To set environment variables during deployment:

```bash
gcloud run deploy fpl-mcp-server \
  --image us-central1-docker.pkg.dev/$PROJECT_ID/remote-mcp-servers/fpl-mcp-server:latest \
  --region=us-central1 \
  --allow-unauthenticated \
  --set-env-vars="ENVIRONMENT=production,CACHE_TTL=600"
```

### Public Access Configuration

The server is deployed with `--allow-unauthenticated` for easy integration. This means:

- ✅ **Simple Integration**: Direct URL access without authentication setup
- ✅ **Claude Desktop Ready**: Works immediately with MCP clients
- ⚠️ **Public Access**: Anyone on the internet can access the service

**Optional**: If you prefer restricted access, you can update the service later:

```bash
# Remove public access (requires authentication)
gcloud run services remove-iam-policy-binding fpl-mcp-server \
  --region=us-central1 \
  --member='allUsers' \
  --role='roles/run.invoker'

# Grant access to specific users
gcloud run services add-iam-policy-binding fpl-mcp-server \
  --region=us-central1 \
  --member='user:example@gmail.com' \
  --role='roles/run.invoker'
```

## Get Service Information

### Get the Service URL

```bash
gcloud run services describe fpl-mcp-server \
  --region=us-central1 \
  --format='value(status.url)'
```

### View Logs

```bash
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=fpl-mcp-server" \
  --limit=50 \
  --format="table(timestamp, jsonPayload.message)"
```

## Claude Desktop Integration

To use the deployed remote MCP server with Claude Desktop, add this configuration to your `claude_desktop_config.json`:

### Option 1: Using MCP Proxy (Recommended)

```json
{
  "mcpServers": {
    "fpl-mcp": {
      "command": "npx",
      "args": [
        "@modelcontextprotocol/server-everything",
        "proxy",
        "https://YOUR-SERVICE-URL-HERE/mcp"
      ]
    }
  }
}
```

### Option 2: Using Remote HTTP Transport

```json
{
  "mcpServers": {
    "fpl-mcp": {
      "type": "http",
      "url": "https://YOUR-SERVICE-URL-HERE/mcp"
    }
  }
}
```

### Option 3: Using MCP Remote Package

```bash
npm install -g @modelcontextprotocol/mcp-remote
```

```json
{
  "mcpServers": {
    "fpl-mcp": {
      "command": "mcp-remote",
      "args": [
        "https://YOUR-SERVICE-URL-HERE/mcp"
      ]
    }
  }
}
```

Replace `YOUR-SERVICE-URL-HERE` with your actual Cloud Run service URL (e.g., `https://fpl-mcp-server-123456789-uc.a.run.app`).

**Note**: The server implements proper MCP HTTP transport with both SSE and HTTP JSON-RPC endpoints at `/mcp`.

## Monitoring and Troubleshooting

### View Service Status

```bash
gcloud run services describe fpl-mcp-server --region=us-central1
```

### Update Service

To update the service with a new image:

```bash
gcloud run services update fpl-mcp-server \
  --region=us-central1 \
  --image us-central1-docker.pkg.dev/$PROJECT_ID/remote-mcp-servers/fpl-mcp-server:latest
```

### Scale Configuration

Adjust scaling settings:

```bash
gcloud run services update fpl-mcp-server \
  --region=us-central1 \
  --min-instances=0 \
  --max-instances=10 \
  --concurrency=80
```

## Cost Analysis & Controls

### Timeout & Resource Controls

The deployment includes built-in cost controls:

```bash
--memory=512Mi          # Reduced memory allocation
--cpu=1                 # Single CPU allocation
--min-instances=0       # Scales to ZERO when not in use (no cost!)
--max-instances=5       # Limits maximum concurrent instances
--concurrency=80        # Max requests per instance
--timeout=300          # 5-minute request timeout
--cpu-throttling       # Enables CPU throttling for cost savings
```

### Cost Breakdown (US pricing)

**When NOT in use (most of the time):**
- **$0.00/hour** - Scales to zero instances

**When actively handling requests:**
- **CPU**: ~$0.000024/vCPU-second ($0.086/hour per vCPU)
- **Memory**: ~$0.0000025/GiB-second ($0.009/hour per GiB)
- **Requests**: $0.40 per million requests

**Typical hourly costs when active:**
- **Light usage** (few requests): ~$0.05-0.10/hour
- **Moderate usage** (100+ requests): ~$0.10-0.20/hour
- **Heavy usage** (1000+ requests): ~$0.20-0.50/hour

### Monthly Cost Estimates

**Cloud Run Free Tier (first 2M requests, 360K GB-seconds):**
- Most personal usage: **$0-5/month**
- Moderate usage: **$5-20/month**
- Heavy usage: **$20-50/month**

### Cost Optimization Features

✅ **Auto Scale-to-Zero**: No cost when idle (99% of the time)  
✅ **Request Timeout**: 5-minute limit prevents runaway costs  
✅ **Instance Limits**: Max 5 concurrent instances  
✅ **CPU Throttling**: Reduces CPU costs when possible  
✅ **Memory Optimized**: 512Mi instead of 1Gi saves ~45%  

### Free Tier Limits

Google Cloud Run free tier includes:
- **2 million requests** per month
- **360,000 GB-seconds** of compute time per month
- **1 GB network egress** per month from North America

**For typical MCP usage, you'll likely stay within free tier limits.**

### Set Up Billing Alerts

Automatically monitor costs and get notified:

```bash
chmod +x setup-billing-alerts.sh
./setup-billing-alerts.sh
```

This sets up alerts at 50%, 80%, and 100% of your budget ($10 default).

### Manual Cost Monitoring

```bash
# View current month's costs
gcloud billing budgets list --billing-account=YOUR_BILLING_ACCOUNT

# Check service usage
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=fpl-mcp-server" --limit=50

# Monitor request volume
gcloud monitoring metrics list --filter="resource.type=cloud_run_revision"
```

## Security Considerations

### Public Deployment Security

Since this deployment allows unauthenticated access (`--allow-unauthenticated`), consider these security aspects:

**✅ What's Protected:**
- FPL credentials are only accessible via environment variables (not exposed via API)
- HTTPS is enforced by default on Cloud Run
- No sensitive data is stored in the application itself
- Rate limiting is built into the FPL API integration

**⚠️ Potential Risks:**
- **Public Access**: Anyone can discover and use your MCP server
- **API Costs**: Unrestricted usage may increase Google Cloud costs
- **Rate Limiting**: Heavy usage might trigger FPL API rate limits

**🛡️ Mitigation Strategies:**

1. **Monitor Usage**: Set up Cloud Console monitoring and billing alerts
2. **Resource Limits**: Configure appropriate CPU/memory limits and max instances
3. **Optional Authentication**: Switch to authenticated access if needed:
   ```bash
   gcloud run services remove-iam-policy-binding fpl-mcp-server \
     --region=us-central1 \
     --member='allUsers' \
     --role='roles/run.invoker'
   ```
4. **Audit Logging**: Enable Cloud Audit Logs to monitor access
5. **Network Security**: Consider VPC ingress controls for enterprise deployments

### Best Practices

1. **Store credentials securely** (use environment variables, not hardcoded values)
2. **Monitor costs** via Google Cloud Console billing alerts  
3. **Enable audit logging** for monitoring access patterns
4. **Use HTTPS only** (enforced by default on Cloud Run)
5. **Regular updates** to keep dependencies secure

## Support

For issues with:
- **Cloud Run deployment**: Check [Cloud Run documentation](https://cloud.google.com/run/docs)
- **FPL MCP functionality**: Check the project's GitHub issues
- **Authentication**: Verify IAM permissions and service account keys