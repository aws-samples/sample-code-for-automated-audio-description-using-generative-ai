#!/bin/bash
# Deploy the DVI Narration sample to your AWS account.
# Prerequisites: AWS CLI v2.27.42+ configured, Node.js 18+, Python 3.12+, curl
set -e

echo "============================================"
echo "  DVI Narration Pipeline - Deployment"
echo "============================================"
echo ""

# Check prerequisites
command -v aws >/dev/null 2>&1 || { echo "ERROR: AWS CLI not found. Install it first."; exit 1; }
command -v node >/dev/null 2>&1 || { echo "ERROR: Node.js not found. Install Node.js 18+."; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "ERROR: Python 3 not found. Install Python 3.12+."; exit 1; }
command -v curl >/dev/null 2>&1 || { echo "ERROR: curl not found. Install curl."; exit 1; }

# Verify AWS credentials
echo "Verifying AWS credentials..."
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text 2>/dev/null)
REGION=$(aws configure get region 2>/dev/null || echo "us-east-1")
echo "  Account: $ACCOUNT_ID"
echo "  Region:  $REGION"
echo ""

# ---------------------------------------------------------------------------
# Ensure Amazon Bedrock model access (Twelve Labs Pegasus + Anthropic Claude)
# ---------------------------------------------------------------------------
# Both models are served via AWS Marketplace and must be subscribed once per
# account before the pipeline can invoke them. We check availability and, if
# needed, request the subscription (including the one-time First Time Use form
# that Anthropic models require). This is best-effort: if it can't complete
# (e.g. missing aws-marketplace:Subscribe permission, or an older AWS CLI), it
# warns and lets the deploy continue so you can enable access in the console.
# Requires AWS CLI v2.27.42+. Override the Anthropic FTU form values with the
# BEDROCK_FTU_COMPANY / _WEBSITE / _INDUSTRY / _USECASE env vars if you like.
PEGASUS_BASE_MODEL_ID="twelvelabs.pegasus-1-2-v1:0"
CLAUDE_BASE_MODEL_ID="anthropic.claude-sonnet-4-5-20250929-v1:0"

model_agreement_status() {
    aws bedrock get-foundation-model-availability \
        --model-id "$1" --region "$REGION" \
        --query 'agreementAvailability.status' --output text 2>/dev/null || echo "UNKNOWN"
}

ensure_model_access() {
    local model_id="$1" label="$2" is_anthropic="$3" status offer i form
    status=$(model_agreement_status "$model_id")
    if [ "$status" = "AVAILABLE" ]; then
        echo "  OK: $label already enabled."
        return 0
    fi
    echo "  $label not enabled (agreement status: $status). Requesting access..."

    # Anthropic models require a one-time First Time Use form per account.
    if [ "$is_anthropic" = "yes" ]; then
        form=$(python3 -c "import base64,json;print(base64.b64encode(json.dumps({'companyName':'${BEDROCK_FTU_COMPANY:-DVI Sample}','companyWebsite':'${BEDROCK_FTU_WEBSITE:-https://example.com}','intendedUsers':'0','industryOption':'${BEDROCK_FTU_INDUSTRY:-Technology}','otherIndustryOption':'','useCases':'${BEDROCK_FTU_USECASE:-Automated audio description (DVI) sample pipeline.}'}).encode()).decode())" 2>/dev/null || echo "")
        if [ -n "$form" ]; then
            aws bedrock put-use-case-for-model-access --form-data "$form" --region "$REGION" >/dev/null 2>&1 \
                && echo "    Submitted Anthropic first-time-use form." \
                || echo "    First-time-use form already on file or not required."
        fi
    fi

    offer=$(aws bedrock list-foundation-model-agreement-offers \
        --model-id "$model_id" --offer-type ALL --region "$REGION" \
        --query 'offers[0].offerToken' --output text 2>/dev/null || echo "")
    if [ -z "$offer" ] || [ "$offer" = "None" ]; then
        echo "    WARN: no offer token returned for $label."
        echo "    Enable it manually: Bedrock console -> Model catalog -> $label -> Subscribe/Request access."
        return 0
    fi

    aws bedrock create-foundation-model-agreement \
        --model-id "$model_id" --offer-token "$offer" --region "$REGION" >/dev/null 2>&1 \
        && echo "    Subscription requested." \
        || echo "    WARN: subscription request failed (do you have aws-marketplace:Subscribe?)."

    # Subscription can take up to ~2 minutes to finalize.
    for i in 1 2 3 4 5 6; do
        status=$(model_agreement_status "$model_id")
        if [ "$status" = "AVAILABLE" ]; then
            echo "  OK: $label enabled."
            return 0
        fi
        sleep 20
    done

    echo "  WARN: $label still not AVAILABLE (agreement status: $status)."
    echo "    Deployment will continue, but the pipeline will fail until access is granted."
    echo "    Enable it manually: Bedrock console -> Model catalog -> $label -> Subscribe/Request access."
    return 0
}

echo "Checking Amazon Bedrock model access..."
if aws bedrock help >/dev/null 2>&1; then
    ensure_model_access "$PEGASUS_BASE_MODEL_ID" "Twelve Labs Pegasus 1.2" "no"
    ensure_model_access "$CLAUDE_BASE_MODEL_ID" "Anthropic Claude Sonnet 4.5" "yes"
else
    echo "  WARN: this AWS CLI doesn't support the 'aws bedrock' model-access commands (need v2.27.42+)."
    echo "  Skipping automatic enablement. Enable Pegasus and Claude in the Bedrock console before running the pipeline."
fi
echo ""

# Step 1: Collect admin email
echo "[1/6] Configuring admin user..."
read -p "  Enter admin email for dashboard access: " ADMIN_EMAIL
if [ -z "$ADMIN_EMAIL" ]; then
    echo "ERROR: Admin email is required."
    exit 1
fi
echo ""

# Step 2: Set up Python virtual environment and install dependencies
echo "[2/6] Installing Python CDK dependencies..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
source .venv/bin/activate
pip install -r requirements.txt -q

# Step 3: Bootstrap CDK (if needed)
echo "[3/6] Bootstrapping CDK..."
npx cdk bootstrap aws://$ACCOUNT_ID/$REGION --quiet 2>/dev/null || true

# Step 3: Build the FFmpeg Lambda layer
echo "[3/6] Building FFmpeg Lambda layer..."
bash backend/layers/ffmpeg/build-layer.sh

# Step 4: Build the React frontend
echo "[4/6] Building React frontend..."
cd dashboard/frontend
npm ci --silent
npm run build
cd ../..

# Step 5: Deploy all stacks
echo "[5/6] Deploying CDK stacks (this may take 10-15 minutes)..."
npx cdk deploy --all --require-approval never --outputs-file cdk-outputs.json --context adminEmail="$ADMIN_EMAIL"

# Step 6: Print outputs
echo ""
echo "[6/6] Deployment complete!"
echo ""
echo "============================================"
echo "  Deployment Outputs"
echo "============================================"
if [ -f cdk-outputs.json ]; then
    cat cdk-outputs.json | python3 -c "
import json, sys
data = json.load(sys.stdin)
for stack, outputs in data.items():
    print(f'\n  {stack}:')
    for key, value in outputs.items():
        print(f'    {key}: {value}')
"
fi
echo ""
echo "============================================"
echo "  Next Steps"
echo "============================================"
echo ""
echo "1. Check your email ($ADMIN_EMAIL) for a temporary password from Cognito."
echo ""
echo "2. Upload a test video:"
echo "   aws s3 cp your-video.mp4 s3://\$(cat cdk-outputs.json | python3 -c \"import json,sys; print(json.load(sys.stdin)['DviPipelineStack']['BucketName'])\")/input/your-video.mp4"
echo ""
echo "3. Open the Dashboard URL above, sign in with your email and temporary password,"
echo "   set a new password, then trigger a pipeline run."
