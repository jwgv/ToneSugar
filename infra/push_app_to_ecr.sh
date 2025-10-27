#!/bin/bash
source .env

echo "Building and pushing ${PROJECT_NAME} app to ECR..."

# Login to ECR
aws ecr get-login-password --region ${AWS_REGION} | \
    docker login --username AWS --password-stdin ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com

# Build the image for AMD64 platform (required for ECS Fargate)
echo "Building Docker image for linux/amd64..."
cd ../
docker buildx build \
    --platform linux/amd64 \
    -t ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO_APP}:latest \
    -f app/Dockerfile \
    app/ \
    --push

echo "Image pushed successfully!"