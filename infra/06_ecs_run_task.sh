#!/bin/bash
set -e
source .env

ACCOUNT=$AWS_ACCOUNT_ID
REGION=$AWS_REGION
PROJECT=$PROJECT_NAME

# Stop existing tasks first - Just one should be running
./stop_all_tasks.sh

# read APP image URI from earlier run (or build again)
if [ -f image_app.env ]; then
  source image_app.env
else
  echo "image_app.env missing. Run push_app_to_ecr.sh first."
  exit 1
fi

# Ensure CloudWatch Logs group exists for ecs logs (exec role lacks CreateLogGroup)
aws logs create-log-group --log-group-name "/ecs/${PROJECT}" --region "$REGION" >/dev/null 2>&1 || true

# render taskdef (inject ARNs and logging config)
cat ecs_taskdef.json \
  | sed "s|__ACCOUNT_ID__|$ACCOUNT|g" \
  | sed "s|__PROJECT__|$PROJECT|g" \
  | sed "s|__ECR_APP_IMAGE__|$IMAGE_URI|g" \
  | sed "s|__S3_BUCKET__|$S3_BUCKET|g" \
  | sed "s|__LAMBDA_NAME__|$LAMBDA_NAME|g" \
  | sed "s|__AWS_REGION__|$REGION|g" \
  | sed "s|__ECS_TASK_FAMILY__|$ECS_TASK_FAMILY|g" > tmp_taskdef.json

aws ecs register-task-definition --cli-input-json file://tmp_taskdef.json

# create cluster if not exists
aws ecs create-cluster --cluster-name $ECS_CLUSTER || true

# Create or re-use a security group that allows port 8080 from anywhere (demo only)
VPC_ID=$(aws ec2 describe-vpcs --filters Name=isDefault,Values=true --query "Vpcs[0].VpcId" --output text)
SG_NAME="${PROJECT}-sg"
# Try to find existing SG by name in this VPC
SG_ID=$(aws ec2 describe-security-groups \
  --filters Name=group-name,Values=${SG_NAME} Name=vpc-id,Values=${VPC_ID} \
  --query "SecurityGroups[0].GroupId" --output text 2>/dev/null || true)
if [ -z "$SG_ID" ] || [ "$SG_ID" = "None" ]; then
  SG_ID=$(aws ec2 create-security-group \
    --group-name ${SG_NAME} \
    --description "tunesugar demo sg" \
    --vpc-id $VPC_ID \
    --query GroupId --output text)
fi
# Authorize ingress (idempotent)
aws ec2 authorize-security-group-ingress --group-id $SG_ID --protocol tcp --port 8080 --cidr 0.0.0.0/0 >/dev/null 2>&1 || true

# pick default subnets
SUBNETS=$(aws ec2 describe-subnets --filters "Name=defaultForAz,Values=true" --query "Subnets[*].SubnetId" --output text | tr '\t' ',')

# run the task
TASK_ARN=$(aws ecs run-task \
  --cluster $ECS_CLUSTER \
  --launch-type FARGATE \
  --task-definition $ECS_TASK_FAMILY \
  --network-configuration "awsvpcConfiguration={subnets=[$SUBNETS],securityGroups=[$SG_ID],assignPublicIp=ENABLED}" \
  --query "tasks[0].taskArn" --output text)

echo "Task ARN: $TASK_ARN"

# wait for task to attach network interface
sleep 8

# get public IP
ENI_ID=$(aws ecs describe-tasks --cluster $ECS_CLUSTER --tasks $TASK_ARN --query "tasks[0].attachments[0].details[?name=='networkInterfaceId'].value" --output text)
PUBLIC_IP=$(aws ec2 describe-network-interfaces --network-interface-ids $ENI_ID --query "NetworkInterfaces[0].Association.PublicIp" --output text)
echo "Public IP: $PUBLIC_IP"
echo "Test upload: curl -F \"file=@/path/to/your.wav\" http://$PUBLIC_IP:8080/upload"
