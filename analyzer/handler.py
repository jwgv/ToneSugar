# analyzer/handler.py
# Import librosa lazily when needed (tempo)
import importlib
import json
import os
import tempfile
import time
import traceback
from datetime import datetime, timezone
from decimal import Decimal

import boto3
import soundfile as sf
from mutagen.mp3 import MP3 as MutagenMP3

# Environment vars set by ECS/Lambda
REGION = os.getenv("AWS_REGION", "us-west-2")
DDB_TABLE = os.getenv("DDB_TABLE_NAME", "tunesugar-metadata")
OUT_PREFIX = os.getenv("ANALYSIS_PREFIX", "analysis/")

# Performance/feature toggles
ENABLE_TEMPO = os.getenv("ENABLE_TEMPO", "true").lower() in ("1", "true", "yes", "on")
TEMPO_MAX_SECONDS = float(os.getenv("TEMPO_MAX_SECONDS", "30"))
TEMPO_SR = int(os.getenv("TEMPO_SR", "22050"))

s3 = boto3.client("s3", region_name=REGION)
dynamodb = boto3.resource("dynamodb", region_name=REGION)
table = dynamodb.Table(DDB_TABLE)


def _fast_duration(path: str, ext: str) -> tuple[float, str]:
    """Return duration in seconds using the fastest available method
    and a label for method used."""
    ext = ext.lower()
    # MP3: use mutagen header parsing (no decode)
    if ext == ".mp3":
        try:
            d = float(MutagenMP3(path).info.length)
            return d, "mutagen"
        except Exception:
            pass
    # WAV (and many other PCM) via soundfile.info
    try:
        info = sf.info(path)
        if info.duration is not None and info.duration > 0:
            return float(info.duration), "soundfile.info"
    except Exception:
        pass
    # Fallback: librosa header-based duration if available, else load minimal
    try:
        librosa = importlib.import_module("librosa")
        d = float(librosa.get_duration(path=path))
        if d > 0:
            return d, "librosa.get_duration"
    except Exception:
        pass
    # Last resort: load a tiny chunk to estimate total duration if possible
    try:
        librosa = importlib.import_module("librosa")
        y, sr = librosa.load(path, sr=None, mono=True, duration=5.0)
        if sr and len(y) > 0:
            # Not accurate for full file; return chunk length as lower bound
            return float(len(y) / sr), "librosa.partial"
    except Exception:
        pass
    return 0.0, "unknown"


def _bounded_tempo(path: str) -> tuple[float, int, float]:
    """Compute tempo on a bounded excerpt for speed.
    Returns (tempo, beats_count, seconds_processed)."""
    if not ENABLE_TEMPO:
        return 0.0, 0, 0.0
    try:
        librosa = importlib.import_module("librosa")
        start = time.time()
        # Use fast resampler; with resampy installed, "kaiser_fast" is both fast and robust
        y, sr = librosa.load(
            path,
            sr=TEMPO_SR,
            mono=True,
            duration=TEMPO_MAX_SECONDS,
            res_type="kaiser_fast",
        )
        if y is None or len(y) == 0 or sr is None or sr == 0:
            return 0.0, 0, 0.0
        tempo, beats = librosa.beat.beat_track(y=y, sr=sr)
        # Fallback: if beat tracker fails to find a stable tempo, try onset‑based tempo estimate
        if not tempo or tempo <= 0 or (hasattr(beats, "__len__") and len(beats) == 0):
            try:
                t_alt = librosa.beat.tempo(y=y, sr=sr, aggregate="mean")
                # tempo() can return array-like; take scalar mean
                import numpy as _np

                tempo = (
                    float(_np.mean(t_alt))
                    if getattr(t_alt, "shape", ())
                    else float(t_alt)
                )
            except Exception as _e:
                print(f"Tempo fallback failed: {_e}")
        elapsed = time.time() - start
        return (
            float(tempo or 0.0),
            int(len(beats) if hasattr(beats, "__len__") else 0),
            float(elapsed),
        )
    except Exception:
        # Log a short message to surface the root cause in CW logs (keeps tracebacks concise)
        import traceback as _tb

        print("Tempo computation error:", _tb.format_exc(limit=1))
        return 0.0, 0, 0.0


def handler(event, context=None):
    """
    Lambda handler to analyze audio and update DynamoDB.
    Event payload example:
      {"bucket": "tunesugar-audio", "key": "uploads/abc.wav", "file_id": "uuid-1234"}
    """
    print("Received event:", event)
    bucket = event.get("bucket")
    key = event.get("key")
    file_id = event.get("file_id")  # optional, if ECS passed it along

    if not bucket or not key:
        return {"error": "Missing bucket or key"}

    try:
        timings = {}
        t0 = time.time()
        with tempfile.NamedTemporaryFile(suffix=os.path.splitext(key)[1]) as tmp:
            s3.download_file(bucket, key, tmp.name)
            timings["download_s"] = time.time() - t0

            ext = os.path.splitext(key)[1].lower()
            t1 = time.time()
            duration, duration_method = _fast_duration(tmp.name, ext)
            timings["duration_s"] = time.time() - t1

            t2 = time.time()
            tempo, beats_count, tempo_elapsed = _bounded_tempo(tmp.name)
            timings["tempo_s"] = tempo_elapsed if tempo_elapsed else (time.time() - t2)

            analysis = {
                "duration": float(duration),
                "tempo": float(tempo),
                "beats": int(beats_count),
                "duration_method": duration_method,
                "timings": timings,
                "tempo_enabled": ENABLE_TEMPO,
                "tempo_max_seconds": TEMPO_MAX_SECONDS,
                "tempo_sr": TEMPO_SR,
            }

            # Save analysis JSON to S3
            out_key = f"{OUT_PREFIX}{os.path.basename(key)}.json"
            s3.put_object(
                Bucket=bucket,
                Key=out_key,
                Body=json.dumps(analysis).encode("utf-8"),
                ContentType="application/json",
            )

            # Update DynamoDB (if record exists)
            if file_id:
                print(f"Updating DynamoDB record for file_id={file_id}")
                update_expr = "SET #duration = :d, #tempo = :t, #analyzed_at = :a"
                expr_names = {
                    "#duration": "duration",
                    "#tempo": "tempo",
                    "#analyzed_at": "analyzed_at",
                }
                expr_values = {
                    ":d": Decimal(str(float(duration))),
                    ":t": Decimal(str(float(tempo))),
                    ":a": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                }
                # Log the expression (redacting values) for debugging deployment drift
                print(
                    f"DDB UpdateExpression: {update_expr}, Names: {list(expr_names.keys())}"
                )
                try:
                    table.update_item(
                        Key={"file_id": file_id},
                        UpdateExpression=update_expr,
                        ExpressionAttributeNames=expr_names,
                        ExpressionAttributeValues=expr_values,
                    )
                except Exception as e:
                    # As a defensive fallback, attempt a retry and surface clearer context
                    if "ValidationException" in str(e) or "reserved keyword" in str(e):
                        print(
                            "Retrying DDB update with defensive attribute name mapping..."
                        )
                        table.update_item(
                            Key={"file_id": file_id},
                            UpdateExpression=update_expr,
                            ExpressionAttributeNames=expr_names,
                            ExpressionAttributeValues=expr_values,
                        )
                    else:
                        raise
            else:
                # Fallback: insert new record if no file_id provided
                table.put_item(
                    Item={
                        "file_id": os.path.basename(key),
                        "s3_key": key,
                        "duration": Decimal(str(float(duration))),
                        "tempo": Decimal(str(float(tempo))),
                    }
                )

            return {"bucket": bucket, "key": key, "analysis": analysis}

    except Exception as e:
        traceback.print_exc()
        return {"error": str(e)}
