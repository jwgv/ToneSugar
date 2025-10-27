#!/bin/bash
# push_lambda_to_ecr_and_deploy.sh
# Builds the analyzer Lambda image, pushes it to ECR, and creates/updates the Lambda with env vars.

set -e
source .env

ACCOUNT=$AWS_ACCOUNT_ID
REGION=$AWS_REGION
REPO=$ECR_REPO_ANALYZER
IMAGE_URI=${ACCOUNT}.dkr.ecr.${REGION}.amazonaws.com/${REPO}:latest
LAMBDA_NAME=$LAMBDA_NAME
# Resolve the Lambda role ARN dynamically to avoid account/profile mismatches
CALLER_ARN=$(aws sts get-caller-identity --query Arn --output text 2>/dev/null || true)
CALLER_ACCOUNT=$(aws sts get-caller-identity --query Account --output text 2>/dev/null || true)

if [ -z "$CALLER_ACCOUNT" ]; then
  echo "❌ Unable to obtain AWS caller identity. Is your AWS CLI configured? Try setting AWS_PROFILE or running 'aws configure'."
  exit 1
fi

if [ "$CALLER_ACCOUNT" != "$ACCOUNT" ]; then
  echo "❌ Account mismatch."
  echo "   - CLI caller account: $CALLER_ACCOUNT ($CALLER_ARN)"
  echo "   - .env AWS_ACCOUNT_ID: $ACCOUNT"
  echo "   These must match. Set AWS_PROFILE to the correct account or update infra/.env."
  exit 1
fi

ROLE_NAME="${PROJECT_NAME}-lambda-role"
RESOLVED_ROLE_ARN=$(aws iam get-role --role-name "$ROLE_NAME" --query 'Role.Arn' --output text 2>/dev/null || true)

if [ -z "$RESOLVED_ROLE_ARN" ] || [ "$RESOLVED_ROLE_ARN" = "None" ]; then
  echo "❌ IAM role '$ROLE_NAME' not found in account $ACCOUNT ($CALLER_ARN)."
  echo "   Run 'infra/02_create_roles_and_policies.sh' with the same AWS profile/account and try again."
  exit 1
fi

LAMBDA_ROLE_ARN="$RESOLVED_ROLE_ARN"

echo "   Preflight:"
echo "   - Region: ${REGION}"
echo "   - Caller: ${CALLER_ARN}"
echo "   - Resolved Lambda role ARN: ${LAMBDA_ROLE_ARN}"

echo "..Waiting for IAM role propagation..."
sleep 10

# Environment variables for the Lambda
DDB_TABLE_NAME=${DDB_TABLE_NAME:-"tunesugar-metadata"}
ANALYSIS_PREFIX=${ANALYSIS_PREFIX:-"analysis/"}
# Analyzer behavior toggles
ENABLE_TEMPO=${ENABLE_TEMPO:-"true"}
TEMPO_MAX_SECONDS=${TEMPO_MAX_SECONDS:-30}
TEMPO_SR=${TEMPO_SR:-22050}
# Configurable compute settings (with safe defaults)
LAMBDA_TIMEOUT=${LAMBDA_TIMEOUT:-60}
LAMBDA_MEMORY=${LAMBDA_MEMORY:-1024}

echo "..Building and deploying Lambda container for TuneSugar..."
echo "Region: ${REGION}"
echo "Lambda: ${LAMBDA_NAME}"
echo "DynamoDB Table: ${DDB_TABLE_NAME}"
echo "ECR Repo: ${REPO}"

# Login to ECR
aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin ${ACCOUNT}.dkr.ecr.${REGION}.amazonaws.com

# Build and push Lambda container (ensure Lambda-compatible media types)
# Default to classic docker build/push to avoid manifest lists/attestations that Lambda may reject.
# Opt-in to buildx only if USE_BUILDX=true is set in the environment.
if [ "${USE_BUILDX}" = "true" ] && docker buildx version >/dev/null 2>&1; then
  echo "🛠 Using docker buildx to build and push (linux/amd64) per USE_BUILDX=true"
  # Note: Some buildx versions implicitly add attestations/provenance which produce an OCI index.
  # If your buildx supports it, you can disable with --provenance=false; otherwise prefer classic build.
  docker buildx build \
    --platform linux/amd64 \
    -t ${IMAGE_URI} \
    --push \
    --output oci-mediatypes=false,type=image,push=true
    ../analyzer
else
  echo "..Using classic docker build/push (linux/amd64)"
  # Ensure classic builder path without extra attestations
  export DOCKER_BUILDKIT=0
  docker build --platform linux/amd64 -t ${REPO} ../analyzer
  docker tag ${REPO}:latest ${IMAGE_URI}
  docker push ${IMAGE_URI}
fi

echo "✅ Pushed Lambda image: ${IMAGE_URI}"

# Check if Lambda exists
if aws lambda get-function --function-name ${LAMBDA_NAME} >/dev/null 2>&1; then
  echo "🔁 Updating existing Lambda function..."

  # Update function code first
  aws lambda update-function-code \
    --function-name ${LAMBDA_NAME} \
    --image-uri ${IMAGE_URI} \
    --region ${REGION}

  # Wait for the function to be in Active state before updating configuration
  echo "..Waiting for function code update to complete..."
  aws lambda wait function-updated --function-name ${LAMBDA_NAME} --region ${REGION}

  # Now update the configuration
  aws lambda update-function-configuration \
    --function-name ${LAMBDA_NAME} \
    --region ${REGION} \
    --timeout ${LAMBDA_TIMEOUT} \
    --memory-size ${LAMBDA_MEMORY} \
    --environment "Variables={DDB_TABLE_NAME=${DDB_TABLE_NAME},ANALYSIS_PREFIX=${ANALYSIS_PREFIX},ENABLE_TEMPO=${ENABLE_TEMPO},TEMPO_MAX_SECONDS=${TEMPO_MAX_SECONDS},TEMPO_SR=${TEMPO_SR},JOBLIB_MULTIPROCESSING=0}"

  # Wait for configuration update to complete
  echo "..Waiting for function configuration update to complete..."
  aws lambda wait function-updated --function-name ${LAMBDA_NAME} --region ${REGION}
else
  echo "..Creating new Lambda function..."
  aws lambda create-function \
    --function-name ${LAMBDA_NAME} \
    --package-type Image \
    --code ImageUri=${IMAGE_URI} \
    --role ${LAMBDA_ROLE_ARN} \
    --region ${REGION} \
    --timeout ${LAMBDA_TIMEOUT} \
    --memory-size ${LAMBDA_MEMORY} \
    --environment "Variables={DDB_TABLE_NAME=${DDB_TABLE_NAME},ANALYSIS_PREFIX=${ANALYSIS_PREFIX},ENABLE_TEMPO=${ENABLE_TEMPO},TEMPO_MAX_SECONDS=${TEMPO_MAX_SECONDS},TEMPO_SR=${TEMPO_SR},JOBLIB_MULTIPROCESSING=0}"
fi

echo "✅ Lambda '${LAMBDA_NAME}' deployed with environment variables:"
echo "   - AWS_REGION = ${REGION}"
echo "   - DDB_TABLE_NAME = ${DDB_TABLE_NAME}"
echo "   - ANALYSIS_PREFIX = ${ANALYSIS_PREFIX}"
echo "✅ Lambda compute settings:"
echo "   - TIMEOUT = ${LAMBDA_TIMEOUT}s"
echo "   - MEMORY_SIZE = ${LAMBDA_MEMORY} MB"