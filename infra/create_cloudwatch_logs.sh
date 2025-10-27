#!/bin/bash
source .env

echo "Creating CloudWatch log group for ${PROJECT_NAME}..."

# Create CloudWatch log group
aws logs create-log-group \
    --log-group-name "/ecs/${PROJECT_NAME}" \
    --region ${AWS_REGION}

echo "CloudWatch log group created: /ecs/${PROJECT_NAME}"

# Set retention policy (optional - 30 days)
aws logs put-retention-policy \
    --log-group-name "/ecs/${PROJECT_NAME}" \
    --retention-in-days 30 \
    --region ${AWS_REGION}

echo "Log retention set to 30 days"