# app/db_dynamo.py
import os
import uuid
from decimal import Decimal

import boto3
from botocore.exceptions import ClientError

REGION = os.getenv("AWS_REGION", "us-west-2")
TABLE_NAME = os.getenv("DDB_TABLE_NAME", "tunesugar-metadata")

dynamodb = boto3.resource("dynamodb", region_name=REGION)
table = dynamodb.Table(TABLE_NAME)


def _clean_ddb(value):
    """Recursively convert Python types to DynamoDB-friendly ones.
    - Convert float to Decimal (as string to preserve precision)
    - Recurse into dicts/lists/tuples
    """
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {k: _clean_ddb(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_clean_ddb(v) for v in value]
    if isinstance(value, tuple):
        return tuple(_clean_ddb(v) for v in value)
    return value


def save_metadata(
    filename: str,
    s3_key: str,
    duration: float = None,
    tempo: float = None,
    file_id: str | None = None,
):
    """Store a new audio file record in DynamoDB. If file_id is provided, use it; else generate one."""
    file_id = file_id or str(uuid.uuid4())
    item = {
        "file_id": file_id,
        "filename": filename,
        "s3_key": s3_key,
        "duration": (
            Decimal("0")
            if duration is None
            else Decimal(str(duration)) if isinstance(duration, float) else duration
        ),
        "tempo": (
            Decimal("0")
            if tempo is None
            else Decimal(str(tempo)) if isinstance(tempo, float) else tempo
        ),
        # analyzed_at intentionally omitted here
        # it will be set by the analyzer when real analysis completes
    }
    # Ensure nested structures (if any) are safe
    item = _clean_ddb(item)
    try:
        table.put_item(Item=item)
        return item
    except ClientError as e:
        print("DynamoDB put_item error:", e)
        return None


def update_metadata(file_id: str, **fields):
    """
    Update one or more attributes of an existing DynamoDB record.

    Example:
        update_metadata(file_id, tempo=128.4, duration=3.75)
    """
    if not file_id or not fields:
        return {"error": "Missing file_id or update fields"}

    # Clean values for DynamoDB (convert floats to Decimal, recurse if needed)
    cleaned_fields = {k: _clean_ddb(v) for k, v in fields.items()}

    # Use Expression Attribute Names to avoid reserved keyword collisions (e.g., duration, status)
    names = {f"#{k}": k for k in cleaned_fields.keys()}
    update_expr = "SET " + ", ".join([f"#{k} = :{k}" for k in cleaned_fields.keys()])
    expr_values = {f":{k}": v for k, v in cleaned_fields.items()}

    try:
        resp = table.update_item(
            Key={"file_id": file_id},
            UpdateExpression=update_expr,
            ExpressionAttributeNames=names,
            ExpressionAttributeValues=expr_values,
            ReturnValues="UPDATED_NEW",
        )
        return resp.get("Attributes", {})
    except ClientError as e:
        print("DynamoDB update_item error:", e)
        return {"error": str(e)}


def list_metadata(limit: int = 20):
    """Retrieve recent items (simple scan for demo purposes)."""
    try:
        resp = table.scan(Limit=limit)
        return resp.get("Items", [])
    except ClientError as e:
        print("DynamoDB scan failed:", e)
        return []


def list_metadata_by_file_id(file_id: str):
    """Retrieve a single item by its file_id primary key."""
    try:
        resp = table.get_item(Key={"file_id": file_id})
        item = resp.get("Item")
        return [item] if item else []
    except ClientError as e:
        print("DynamoDB get_item failed:", e)
        return []


def delete_metadata(file_id: str):
    """Delete a DynamoDB record."""
    try:
        table.delete_item(Key={"file_id": file_id})
        return {"status": "success"}
    except ClientError as e:
        print("DynamoDB delete_item error:", e)
        return {"error": str(e)}
