#!/bin/bash
# cleanup_all_resources.sh
# Tear down all AWS resources related to the TuneSugar project.
# Run this when you're done to avoid unexpected AWS billing.

set -e

# ----------------------------
# CONFIGURATION
# ----------------------------
REGION="us-west-2"                      # Change if needed
ECR_REPO="tunesugar-app"                # ECR repository name
LAMBDA_FUNCTION="TuneSugarAnalyzer"     # Lambda function name
ECS_CLUSTER="tunesugar-cluster"         # ECS cluster name
ECS_SERVICE="tunesugar-service"         # ECS service name
S3_BUCKET="tunesugar-audio"             # S3 bucket for uploads
DDB_TABLE_PREFIX="tunesugar"            # DynamoDB table name prefix
IAM_ROLE="tunesugar-task-role"          # Optional: ECS Task Role name
IAM_POLICY="tunesugar-policy"           # Optional: custom policy name

# ----------------------------
# SAFETY PROMPT
# ----------------------------
echo "⚠️  WARNING: This will permanently delete AWS resources for TuneSugar."
read -p "Type 'DELETE TUNESUGAR' to confirm: " CONFIRM

if [ "$CONFIRM" != "DELETE TUNESUGAR" ]; then
  echo "Aborted. No resources were deleted."
  exit 1
fi

echo "✅ Proceeding with cleanup..."

# ----------------------------
# STEP 1: Delete ECS Service & Cluster
# ----------------------------
echo "Deleting ECS service..."
aws ecs update-service \
  --cluster "$ECS_CLUSTER" \
  --service "$ECS_SERVICE" \
  --desired-count 0 \
  --region "$REGION" >/dev/null 2>&1 || true

aws ecs delete-service \
  --cluster "$ECS_CLUSTER" \
  --service "$ECS_SERVICE" \
  --force \
  --region "$REGION" >/dev/null 2>&1 || true

aws ecs delete-cluster \
  --cluster "$ECS_CLUSTER" \
  --region "$REGION" >/dev/null 2>&1 || true

# ----------------------------
# STEP 2: Delete ECR Repository
# ----------------------------
echo "Deleting ECR repository..."
aws ecr delete-repository \
  --repository-name "$ECR_REPO" \
  --force \
  --region "$REGION" >/dev/null 2>&1 || true

# ----------------------------
# STEP 3: Delete Lambda Function
# ----------------------------
echo "Deleting Lambda function..."
aws lambda delete-function \
  --function-name "$LAMBDA_FUNCTION" \
  --region "$REGION" >/dev/null 2>&1 || true

# ----------------------------
# STEP 4: Empty and Delete S3 Bucket
# ----------------------------
echo "Deleting S3 bucket and contents..."
aws s3 rm "s3://$S3_BUCKET" --recursive >/dev/null 2>&1 || true
aws s3api delete-bucket \
  --bucket "$S3_BUCKET" \
  --region "$REGION" >/dev/null 2>&1 || true

# ----------------------------
# STEP 5: Delete DynamoDB Tables (if any)
# ----------------------------
echo "Checking for DynamoDB tables with prefix '$DDB_TABLE_PREFIX'..."

DDB_TABLES=$(aws dynamodb list-tables --region "$REGION" --output text --query "TableNames[]" | tr '\t' '\n' | grep "^${DDB_TABLE_PREFIX}" || true)

if [ -n "$DDB_TABLES" ]; then
  echo "Found the following DynamoDB tables to delete:"
  echo "$DDB_TABLES"
  for TABLE in $DDB_TABLES; do
    echo "   ➜ Deleting table: $TABLE"
    aws dynamodb delete-table --table-name "$TABLE" --region "$REGION" >/dev/null 2>&1 || true
  done
else
  echo "✅ No DynamoDB tables found with prefix '$DDB_TABLE_PREFIX'."
fi

# ----------------------------
# STEP 6: Delete IAM roles and policies
# ----------------------------
echo "Deleting IAM role and policy (if exist)..."
aws iam detach-role-policy \
  --role-name "$IAM_ROLE" \
  --policy-arn "arn:aws:iam::aws:policy/$IAM_POLICY" >/dev/null 2>&1 || true

aws iam delete-role --role-name "$IAM_ROLE" >/dev/null 2>&1 || true
aws iam delete-policy --policy-arn "arn:aws:iam::aws:policy/$IAM_POLICY" >/dev/null 2>&1 || true

# ----------------------------
# STEP 7: Cleanup confirmation
# ----------------------------
echo "✅ Cleanup complete. All TuneSugar-related AWS resources have been removed."
echo "Double-check the AWS Console to ensure nothing remains."
