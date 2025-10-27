# 🎵 TuneSugar

**TuneSugar** is a lightweight, cloud-native audio metadata analyzer built with FastAPI and AWS.
It features event-driven, serverless architecture using:

* **ECS Fargate** – containerized FastAPI API.
* **Lambda (Container Image)** – performs waveform analysis (tempo, duration).
* **S3** – stores uploaded audio and generated analysis.
* **DynamoDB** – keeps structured metadata records.
* **IAM** – minimal roles for least privilege.


## ⚙️ Architecture Overview

```text
User → FastAPI (ECS) → S3 (Upload)
                       ↳ Lambda (Analysis)
                             ↳ writes JSON to S3 + metadata to DynamoDB
```


## 🧩 Prerequisites

* AWS account with `aws-cli` configured.
* Docker installed.
* Python 3.13 (for local testing).
* IAM user/role with permission to create ECS, Lambda, S3, ECR, and DynamoDB.


## 📁 Project Structure


tunesugar/
├── app/               # FastAPI container (ECS)
│   ├── main.py
│   ├── db_dynamo.py
│   ├── requirements.txt
│   └── Dockerfile
│
├── analyzer/          # Lambda function (container image)
│   ├── handler.py
│   ├── requirements.txt
│   └── Dockerfile
│
├── infra/             # Deployment and cleanup scripts
│   ├── deploy_dynamodb.sh
│   ├── push_app_to_ecr.sh
│   ├── push_lambda_to_ecr_and_deploy.sh
│   ├── ecs_run_task.sh
│   ├── cleanup_all_resources.sh
│   ├── env.example
│   └── ecs_taskdef.json
└── README.md
```


## 🚀 Deployment Steps

All commands below run from the `infra/` directory.

1. **Configure Environment**

   ```bash
   cp env.example .env
   vi .env    # fill in the AWS_ACCOUNT_ID, region, etc.
   ```

2. **Create AWS Resources**

   ```bash
   ./01_create_s3_and_ecr.sh
   ./deploy_dynamodb.sh
   ./02_create_roles_and_policies.sh
   ```

3. **Deploy Services**

   ```bash
   ./push_lambda_to_ecr_and_deploy.sh
   ./push_app_to_ecr.sh
   ./ecs_run_task.sh
   ```

4. **Test the API**

   ```bash
   curl -F "file=@demo.wav" http://<PUBLIC_IP>:8080/upload
   curl http://<PUBLIC_IP>:8080/samples
   ```


## 🧠 DynamoDB Table Schema

| Attribute     | Type | Description              |
| ------------- | ---- | ------------------------ |
| `file_id`     | S    | Unique ID for audio file |
| `filename`    | S    | Original file name       |
| `s3_key`      | S    | Path in S3 bucket        |
| `duration`    | N    | Audio length in seconds  |
| `tempo`       | N    | Estimated BPM            |
| `analyzed_at` | S    | ISO UTC timestamp        |


## 🧹 Cleanup

To delete all billable AWS resources after testing:

```bash
./cleanup_all_resources.sh
```

Type `DELETE TUNESUGAR` when prompted.
This removes:

* ECS Cluster / Service
* Lambda function
* ECR repositories
* S3 bucket
* DynamoDB tables
* IAM roles


## 🧰 Extending TuneSugar

* Add OpenAI’s Whisper API in Lambda to generate **audio descriptions**.
* Store analysis output in DynamoDB for UI display.
* Use API Gateway in front of ECS for HTTPS endpoints.
* Add TTL (Time To Live) on DynamoDB for automatic cleanup.
