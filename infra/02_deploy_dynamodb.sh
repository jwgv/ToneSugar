#!/bin/bash
# 02_deploy_dynamodb.sh
# Creates a DynamoDB table for TuneSugar to store audio metadata.

set -e

# ----------------------------
# CONFIGURATION
# ----------------------------
REGION="us-west-2"                   # Adjust if needed
TABLE_NAME="tunesugar-metadata"      # DynamoDB table name
READ_CAPACITY=1                      # Low-cost for demo
WRITE_CAPACITY=1                     # Low-cost for demo

# ----------------------------
# CREATE TABLE
# ----------------------------
echo "Creating DynamoDB table: $TABLE_NAME"

# Define table schema:
# Primary key: file_id (string)
aws dynamodb create-table \
  --table-name "$TABLE_NAME" \
  --attribute-definitions AttributeName=file_id,AttributeType=S \
  --key-schema AttributeName=file_id,KeyType=HASH \
  --provisioned-throughput ReadCapacityUnits=$READ_CAPACITY,WriteCapacityUnits=$WRITE_CAPACITY \
  --region "$REGION" \
  >/dev/null

echo "Waiting for table to become ACTIVE..."
aws dynamodb wait table-exists --table-name "$TABLE_NAME" --region "$REGION"

echo "✅ DynamoDB table '$TABLE_NAME' created successfully in region $REGION."

# ----------------------------
# (Optional) Enable TTL for auto-cleanup
# ----------------------------
# Uncomment this if you want items to expire automatically after a time.
# Replace 'expires_at' with a TTL attribute (UNIX timestamp in seconds).
#
# aws dynamodb update-time-to-live \
#   --table-name "$TABLE_NAME" \
#   --time-to-live-specification "Enabled=true, AttributeName=expires_at" \
#   --region "$REGION"

echo "Example schema:"
echo "{
  \"file_id\": \"uuid-1234\",
  \"filename\": \"demo.wav\",
  \"duration\": 3.5,
  \"tempo\": 120.0,
  \"key\": \"uploads/uuid-1234.wav\",
  \"analyzed_at\": \"2025-10-26T13:00:00Z\"
}"
