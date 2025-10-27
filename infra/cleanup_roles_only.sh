#!/bin/bash
# cleanup_roles_only.sh
# Deletes only IAM roles and inline policies created for the TuneSugar project.

set -e
source .env

PROJECT=$PROJECT_NAME

echo "⚠️  This will permanently delete IAM roles and policies for project '$PROJECT'."
read -p "Type 'DELETE IAM' to confirm: " CONFIRM

if [ "$CONFIRM" != "DELETE IAM" ]; then
  echo "Aborted."
  exit 0
fi

echo "Deleting IAM roles and policies..."

# Delete ECS exec role (no inline policies)
aws iam detach-role-policy \
  --role-name ${PROJECT}-ecs-exec-role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy >/dev/null 2>&1 || true
aws iam delete-role --role-name ${PROJECT}-ecs-exec-role >/dev/null 2>&1 || true

# Delete ECS task role (inline)
aws iam delete-role-policy \
  --role-name ${PROJECT}-ecs-task-role \
  --policy-name ${PROJECT}-ecs-task-policy >/dev/null 2>&1 || true
aws iam delete-role --role-name ${PROJECT}-ecs-task-role >/dev/null 2>&1 || true

# Delete Lambda role (inline)
aws iam delete-role-policy \
  --role-name ${PROJECT}-lambda-role \
  --policy-name ${PROJECT}-lambda-exec-policy >/dev/null 2>&1 || true
aws iam delete-role --role-name ${PROJECT}-lambda-role >/dev/null 2>&1 || true

echo "✅ IAM roles and policies deleted for project '$PROJECT'."
