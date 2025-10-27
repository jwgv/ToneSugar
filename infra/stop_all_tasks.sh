#!/bin/bash
set -e

# Load environment variables
source .env

echo "Checking for running tasks in cluster: $ECS_CLUSTER"

# Get all running task ARNs
RUNNING_TASKS=$(aws ecs list-tasks \
  --cluster "$ECS_CLUSTER" \
  --desired-status RUNNING \
  --query 'taskArns[]' \
  --output text \
  --region "$AWS_REGION")

# Check if there are any running tasks
if [ -z "$RUNNING_TASKS" ]; then
    echo "No running tasks found in cluster $ECS_CLUSTER"
    exit 0
fi

echo "Found running tasks:"
echo "$RUNNING_TASKS"
echo ""

# Convert to array and count tasks
TASK_ARRAY=($RUNNING_TASKS)
TASK_COUNT=${#TASK_ARRAY[@]}

echo "Found $TASK_COUNT running task(s). Stopping them..."
echo ""

# Stop each task
for task_arn in $RUNNING_TASKS; do
    echo "Stopping task: $task_arn"
    aws ecs stop-task \
      --cluster "$ECS_CLUSTER" \
      --task "$task_arn" \
      --region "$AWS_REGION" \
      --reason "Stopped by stop_all_tasks.sh script"

    if [ $? -eq 0 ]; then
        echo "✓ Successfully stopped task: $task_arn"
    else
        echo "✗ Failed to stop task: $task_arn"
    fi
    echo ""
done

echo "Done! Stopped $TASK_COUNT task(s)."
echo ""
echo "Note: It may take a few moments for tasks to fully terminate."
echo "You can verify with: aws ecs list-tasks --cluster $ECS_CLUSTER --desired-status RUNNING"