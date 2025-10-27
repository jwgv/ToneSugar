#!/bin/bash
set -e
source .env

aws configure set region $AWS_REGION

echo "Creating S3 bucket: $S3_BUCKET"
aws s3api create-bucket \
  --bucket "$S3_BUCKET" \
  --region "$AWS_REGION" \
  --create-bucket-configuration LocationConstraint="$AWS_REGION" || true

echo "Creating ECR repo: $ECR_REPO_APP"
aws ecr create-repository --repository-name "$ECR_REPO_APP" --region "$AWS_REGION" || true

echo "Creating ECR repo: $ECR_REPO_ANALYZER"
aws ecr create-repository --repository-name "$ECR_REPO_ANALYZER" --region "$AWS_REGION" || true

echo "Done. Edit roles and deploy images next."
