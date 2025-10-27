import json
import os
import uuid

import boto3

try:
    from .db_dynamo import (
        delete_metadata,
        list_metadata,
        list_metadata_by_file_id,
        save_metadata,
        update_metadata,
    )
except ImportError:  # when running as a top-level module (e.g., uvicorn main:app)
    from db_dynamo import (
        list_metadata,
        list_metadata_by_file_id,
        save_metadata,
        update_metadata,
        delete_metadata,
    )

from fastapi import Body, FastAPI, File, HTTPException, Path, UploadFile

app = FastAPI(title="TuneSugar API")

S3_BUCKET = os.getenv("S3_BUCKET")
LAMBDA_NAME = os.getenv("LAMBDA_NAME")
AWS_REGION = os.getenv("AWS_REGION", "us-west-2")

s3 = boto3.client("s3", region_name=AWS_REGION)
lambda_client = boto3.client("lambda", region_name=AWS_REGION)


@app.get("/")
def root():
    return {"message": "TuneSugar API running"}


@app.post("/upload")
async def upload_audio(file: UploadFile = File(...)):
    """Upload an audio file, save to S3, store metadata in DynamoDB, and trigger Lambda analysis."""
    ext = "." + file.filename.rsplit(".", 1)[-1].lower()
    if ext not in [".wav", ".mp3"]:
        raise HTTPException(status_code=400, detail="Only WAV/MP3 supported")

    # Generate file_id once here
    file_id = str(uuid.uuid4())
    s3_key = f"uploads/{file_id}{ext}"

    # Step 1: Upload file to S3
    try:
        s3.upload_fileobj(file.file, S3_BUCKET, s3_key)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"S3 upload failed: {e}")

    # Step 2: Save initial metadata to DynamoDB (preserve same file_id)
    save_metadata(filename=file.filename, s3_key=s3_key, file_id=file_id)

    # Step 3: Trigger Lambda with file_id (so it updates the same record)
    payload = {"bucket": S3_BUCKET, "key": s3_key, "file_id": file_id}
    try:
        lambda_client.invoke(
            FunctionName=LAMBDA_NAME,
            InvocationType="Event",  # async
            Payload=json.dumps(payload),
        )
    except Exception as e:
        return {
            "file_id": file_id,
            "s3_key": s3_key,
            "lambda_invoked": False,
            "error": str(e),
        }

    return {"file_id": file_id, "s3_key": s3_key, "lambda_invoked": True}


@app.get("/samples")
def get_samples(limit: int = 20):
    """Return recent samples stored in DynamoDB."""
    items = list_metadata(limit)
    return {"items": items}


@app.get("/samples/{file_id}")
@app.get("/sample/{file_id}")
def get_sample(file_id: str):
    """Return a single sample by file_id."""
    if not file_id:
        return {"error": "Missing file_id"}
    item = list_metadata_by_file_id(file_id=file_id)
    if not item:
        return {"error": "No sample found"}
    return {"items": item[0]}


@app.patch("/update/{file_id}")
def update_sample(file_id: str = Path(...), fields: dict = Body(...)):
    """
    Update metadata for a specific file_id in DynamoDB.
    Example:
      PATCH /update/<file_id>
      Body: {"tempo": 125.0, "duration": 3.74}
    """
    updated = update_metadata(file_id, **fields)
    if "error" in updated:
        raise HTTPException(status_code=500, detail=updated["error"])
    return {"file_id": file_id, "updated_fields": updated}


@app.delete("/samples/{file_id}")
@app.delete("/sample/{file_id}")
def delete_sample(file_id: str = Path(...)):
    """
    Delete a sample (metadata) by file_id from DynamoDB.
    Auth can be added later.
    """
    if not file_id:
        raise HTTPException(status_code=400, detail="Missing file_id")
    result = delete_metadata(file_id)
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    return {"file_id": file_id, "deleted": True}
