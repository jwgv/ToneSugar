#!/bin/bash
source .env

echo "Creating IAM roles and policies for ${PROJECT_NAME}..."

# Create ECS Task Execution Role
cat > /tmp/ecs-task-execution-trust-policy.json << EOF
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {
                "Service": "ecs-tasks.amazonaws.com"
            },
            "Action": "sts:AssumeRole"
        }
    ]
}
EOF

aws iam create-role \
    --role-name ${PROJECT_NAME}-ecs-execution-role \
    --assume-role-policy-document file:///tmp/ecs-task-execution-trust-policy.json

# Attach the managed ECS execution role policy
aws iam attach-role-policy \
    --role-name ${PROJECT_NAME}-ecs-execution-role \
    --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy

# Create ECS Task Role (for the application to access AWS services)
aws iam create-role \
    --role-name ${PROJECT_NAME}-ecs-task-role \
    --assume-role-policy-document file:///tmp/ecs-task-execution-trust-policy.json

# Create CloudWatch Logs policy
cat > /tmp/cloudwatch-logs-policy.json << EOF
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
                "logs:PutLogEvents"
            ],
            "Resource": "arn:aws:logs:${AWS_REGION}:${AWS_ACCOUNT_ID}:log-group:/ecs/${PROJECT_NAME}*"
        }
    ]
}
EOF

aws iam create-policy \
    --policy-name ${PROJECT_NAME}-cloudwatch-logs-policy \
    --policy-document file:///tmp/cloudwatch-logs-policy.json

# Attach CloudWatch Logs policy to execution role
aws iam attach-role-policy \
    --role-name ${PROJECT_NAME}-ecs-execution-role \
    --policy-arn arn:aws:iam::${AWS_ACCOUNT_ID}:policy/${PROJECT_NAME}-cloudwatch-logs-policy

# Create DynamoDB access policy for the task role
cat > /tmp/dynamodb-policy.json << EOF
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "dynamodb:GetItem",
                "dynamodb:PutItem",
                "dynamodb:Query",
                "dynamodb:Scan",
                "dynamodb:UpdateItem",
                "dynamodb:DeleteItem"
            ],
            "Resource": "arn:aws:dynamodb:${AWS_REGION}:${AWS_ACCOUNT_ID}:table/${DDB_TABLE_NAME}"
        }
    ]
}
EOF

aws iam create-policy \
    --policy-name ${PROJECT_NAME}-dynamodb-policy \
    --policy-document file:///tmp/dynamodb-policy.json

# Attach DynamoDB policy to task role
aws iam attach-role-policy \
    --role-name ${PROJECT_NAME}-ecs-task-role \
    --policy-arn arn:aws:iam::${AWS_ACCOUNT_ID}:policy/${PROJECT_NAME}-dynamodb-policy

# Clean up temp files
rm -f /tmp/ecs-task-execution-trust-policy.json
rm -f /tmp/cloudwatch-logs-policy.json
rm -f /tmp/dynamodb-policy.json

echo "IAM roles and policies created successfully!"
echo "Execution Role: ${PROJECT_NAME}-ecs-execution-role"
echo "Task Role: ${PROJECT_NAME}-ecs-task-role"