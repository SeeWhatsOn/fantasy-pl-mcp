#!/bin/bash

# Fantasy Premier League MCP Server - Billing Alerts Setup
# This script sets up billing alerts to monitor Cloud Run costs

set -e

PROJECT_ID=${PROJECT_ID:-$(gcloud config get-value project)}
BUDGET_NAME=${BUDGET_NAME:-"fpl-mcp-server-budget"}
BUDGET_AMOUNT=${BUDGET_AMOUNT:-10}  # $10 USD default
EMAIL=${NOTIFICATION_EMAIL:-""}

echo "🔔 Setting up billing alerts for Fantasy Premier League MCP Server"
echo "Project: $PROJECT_ID"
echo "Budget: \$${BUDGET_AMOUNT} USD"
echo ""

# Check if project is set
if [ -z "$PROJECT_ID" ]; then
    echo "❌ Error: PROJECT_ID is not set. Please run:"
    echo "   gcloud config set project YOUR_PROJECT_ID"
    exit 1
fi

# Check for notification email
if [ -z "$EMAIL" ]; then
    echo "📧 Enter email address for billing notifications:"
    read EMAIL
fi

if [ -z "$EMAIL" ]; then
    echo "❌ Error: Email address is required for billing notifications"
    exit 1
fi

echo "📋 Setting up billing budget and alerts..."

# Get billing account ID
BILLING_ACCOUNT=$(gcloud billing projects describe $PROJECT_ID --format="value(billingAccountName)" | sed 's/.*\///')

if [ -z "$BILLING_ACCOUNT" ]; then
    echo "❌ Error: No billing account found for project $PROJECT_ID"
    echo "Please ensure billing is enabled for your project"
    exit 1
fi

# Create budget configuration
cat > budget-config.json << EOF
{
  "displayName": "$BUDGET_NAME",
  "budgetFilter": {
    "projects": ["projects/$PROJECT_ID"],
    "services": ["services/Cloud Run"]
  },
  "amount": {
    "specifiedAmount": {
      "currencyCode": "USD",
      "units": "$BUDGET_AMOUNT"
    }
  },
  "thresholdRules": [
    {
      "thresholdPercent": 0.5,
      "spendBasis": "CURRENT_SPEND"
    },
    {
      "thresholdPercent": 0.8,
      "spendBasis": "CURRENT_SPEND"
    },
    {
      "thresholdPercent": 1.0,
      "spendBasis": "CURRENT_SPEND"
    }
  ],
  "notificationsRule": {
    "pubsubTopic": "projects/$PROJECT_ID/topics/budget-alerts",
    "schemaVersion": "1.0",
    "monitoringNotificationChannels": []
  }
}
EOF

# Create Pub/Sub topic for budget alerts
gcloud pubsub topics create budget-alerts --project=$PROJECT_ID 2>/dev/null || echo "Topic already exists"

# Create notification channel
CHANNEL_ID=$(gcloud alpha monitoring channels create \
    --display-name="Email notification for $EMAIL" \
    --type=email \
    --channel-labels=email_address=$EMAIL \
    --project=$PROJECT_ID \
    --format="value(name)" | sed 's/.*\///')

# Add notification channel to budget config
jq --arg channel "projects/$PROJECT_ID/notificationChannels/$CHANNEL_ID" \
   '.notificationsRule.monitoringNotificationChannels = [$channel]' \
   budget-config.json > budget-config-updated.json

# Create the budget
gcloud billing budgets create \
    --billing-account=$BILLING_ACCOUNT \
    --budget-from-file=budget-config-updated.json \
    --project=$PROJECT_ID

# Clean up temporary files
rm budget-config.json budget-config-updated.json

echo "✅ Billing alerts configured successfully!"
echo ""
echo "📊 What you'll be notified about:"
echo "   - 50% of budget reached (\$$(($BUDGET_AMOUNT / 2)))"
echo "   - 80% of budget reached (\$$(echo "$BUDGET_AMOUNT * 0.8" | bc))"
echo "   - 100% of budget reached (\$$BUDGET_AMOUNT)"
echo ""
echo "🔗 View your budgets: https://console.cloud.google.com/billing/budgets"
echo "📈 View Cloud Run metrics: https://console.cloud.google.com/run"