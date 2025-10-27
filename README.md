# 🎵 TuneSugar

**TuneSugar** is a lightweight, cloud-native audio metadata analyzer built with FastAPI and AWS.

It features event-driven, serverless architecture using:

* **ECS Fargate** - containerized FastAPI API.
* **Lambda (Container Image)** - performs waveform analysis (tempo, duration).
* **S3** - stores uploaded audio and generated analysis.
* **DynamoDB** - keeps structured metadata records.
* **IAM** - minimal roles for least privilege.


## Architecture Overview

```text
User → FastAPI (ECS) → S3 (Upload)
                       ↳ Lambda (Analysis)
                             ↳ writes JSON to S3 + metadata to DynamoDB
```


## Prerequisites

* AWS account with `aws-cli` configured.
* Docker installed.
* Python 3.13 (for local testing).
* IAM user/role with permission to create ECS, Lambda, S3, ECR, and DynamoDB.


## Deployment Steps

All commands below run from the `infra/` directory.

1. **Configure Environment**

   ```bash
   cp env.example .env
   vi .env    # fill in the AWS_ACCOUNT_ID, region, etc.
   ```

2. **Create AWS Resources**

   ```bash
   ./01_create_s3_and_ecr.sh
   ./02_deploy_dynamodb.sh
   ./03_create_roles_and_policies.sh
   ```

3. **Deploy Services**

   ```bash
   ./04_push_lambda_to_ecr_and_deploy.sh
   ./05_push_app_to_ecr.sh
   ./06_ecs_run_task.sh
   ```

4. **Test the API**

   ```bash
   curl -F "file=@demo.wav" http://<PUBLIC_IP>:8080/upload
   curl http://<PUBLIC_IP>:8080/samples
   ```


## Audio Analysis

TuneSugar extracts lightweight audio metadata and stores it alongside your file.

- What it extracts:
  - duration (seconds)
  - tempo (BPM, optional) and detected beats count
- How it's computed:
  - Duration: tries fast header reads first (MP3 via Mutagen), then SoundFile info for PCM (e.g., WAV), then librosa.get_duration, with a minimal load fallback as last resort.
  - Tempo: uses librosa on a short excerpt for speed, resampling to TEMPO_SR and processing up to TEMPO_MAX_SECONDS; falls back to an aggregate tempo() estimate if beat tracking is unstable. Can be disabled entirely.
- Environment variables (defaults in parentheses):
  - ENABLE_TEMPO: enable/disable tempo analysis (true)
  - TEMPO_MAX_SECONDS: max audio seconds analyzed for tempo (30)
  - TEMPO_SR: resample rate used for tempo analysis (22050)
  - ANALYSIS_PREFIX: S3 key prefix for JSON analysis output (analysis/)
- Output targets:
  - S3: JSON written to `${ANALYSIS_PREFIX}<basename>.json`
  - DynamoDB: updates `duration` and `tempo` on the item for the uploaded file (if a `file_id` is provided)

Example analysis JSON saved to S3:

```json
{
  "duration": 123.45,
  "tempo": 128.0,
  "beats": 256,
  "duration_method": "soundfile.info",
  "timings": {
    "download_s": 0.21,
    "duration_s": 0.01,
    "tempo_s": 0.35
  },
  "tempo_enabled": true,
  "tempo_max_seconds": 30.0,
  "tempo_sr": 22050
}
```

Notes:
- Tempo is an estimate and can vary for complex or non-percussive audio.
- Short excerpts are used to keep Lambda fast and inexpensive; increase accuracy by raising TEMPO_MAX_SECONDS (costs more time/memory) or disable via ENABLE_TEMPO=false.

## DynamoDB Table Schema

| Attribute     | Type | Description              |
| ------------- | ---- | ------------------------ |
| `file_id`     | S    | Unique ID for audio file |
| `filename`    | S    | Original file name       |
| `s3_key`      | S    | Path in S3 bucket        |
| `duration`    | N    | Audio length in seconds  |
| `tempo`       | N    | Estimated BPM            |
| `analyzed_at` | S    | ISO UTC timestamp        |


## Cleanup

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


## Extending TuneSugar

* Add a UI for uploading audio files and viewing results.
* Add OpenAI’s Whisper API in Lambda to generate **audio descriptions**.
* Use API Gateway in front of ECS for HTTPS endpoints.
* Add TTL (Time To Live) on DynamoDB for automatic cleanup.
