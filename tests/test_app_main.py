import importlib
import uuid as _uuid

from fastapi.testclient import TestClient


def test_root_returns_message(set_basic_env):
    import app.main as main

    importlib.reload(main)

    with TestClient(main.app) as client:
        r = client.get("/")
    assert r.status_code == 200
    assert r.json() == {"message": "TuneSugar API running"}


def test_upload_success(monkeypatch, set_basic_env):
    import app.main as main

    importlib.reload(main)

    # Stub DB save to capture call
    saved = {}

    def fake_save_metadata(filename, s3_key, file_id=None, **kwargs):
        saved.update({"filename": filename, "s3_key": s3_key, "file_id": file_id})
        return saved

    monkeypatch.setattr(main, "save_metadata", fake_save_metadata)

    # Fix UUID for deterministic s3_key
    fixed = _uuid.UUID("12345678-1234-5678-1234-567812345678")
    monkeypatch.setattr(main.uuid, "uuid4", lambda: fixed)

    with TestClient(main.app) as client:
        files = {"file": ("test.wav", b"abc", "audio/wav")}
        r = client.post("/upload", files=files)

    data = r.json()
    assert r.status_code == 200
    assert data["file_id"] == str(fixed)
    assert data["s3_key"] == f"uploads/{fixed}.wav"
    assert data["lambda_invoked"] is True
    # lambda invoked
    assert len(main.lambda_client.invokes) == 1
    # S3 upload happened
    assert len(main.s3.uploads) == 1
    assert main.s3.uploads[0][0] == "test-bucket"
    assert main.s3.uploads[0][1] == f"uploads/{fixed}.wav"


def test_upload_invalid_extension(set_basic_env):
    import app.main as main

    importlib.reload(main)

    with TestClient(main.app) as client:
        files = {"file": ("test.txt", b"abc", "text/plain")}
        r = client.post("/upload", files=files)
    assert r.status_code == 400
    assert r.json()["detail"] == "Only WAV/MP3 supported"


def test_upload_lambda_invoke_error(monkeypatch, set_basic_env):
    import app.main as main

    importlib.reload(main)

    # Cause lambda invocation to raise
    main.lambda_client.error = Exception("kaboom")

    # Stub DB save (no-op)
    monkeypatch.setattr(main, "save_metadata", lambda **kwargs: kwargs)

    # Fix UUID for deterministic value
    fixed = _uuid.UUID("12345678-1234-5678-1234-567812345678")
    monkeypatch.setattr(main.uuid, "uuid4", lambda: fixed)

    with TestClient(main.app) as client:
        files = {"file": ("test.mp3", b"abc", "audio/mpeg")}
        r = client.post("/upload", files=files)

    data = r.json()
    assert r.status_code == 200
    assert data["file_id"] == str(fixed)
    assert data["lambda_invoked"] is False
    assert "kaboom" in data["error"]


def test_get_samples(monkeypatch, set_basic_env):
    import app.main as main

    importlib.reload(main)

    items = [{"file_id": "a"}, {"file_id": "b"}]
    monkeypatch.setattr(main, "list_metadata", lambda limit=20: items)

    with TestClient(main.app) as client:
        r = client.get("/samples", params={"limit": 2})
    assert r.status_code == 200
    assert r.json() == {"items": items}


def test_get_sample_found(monkeypatch, set_basic_env):
    import app.main as main

    importlib.reload(main)

    item = {"file_id": "abc"}
    monkeypatch.setattr(main, "list_metadata_by_file_id", lambda file_id: [item])

    with TestClient(main.app) as client:
        r = client.get("/samples/abc")
    assert r.status_code == 200
    assert r.json() == {"items": item}


def test_get_sample_not_found(monkeypatch, set_basic_env):
    import app.main as main

    importlib.reload(main)

    monkeypatch.setattr(main, "list_metadata_by_file_id", lambda file_id: [])

    with TestClient(main.app) as client:
        r = client.get("/samples/zzz")
    assert r.status_code == 200
    assert r.json() == {"error": "No sample found"}


def test_patch_update_success(monkeypatch, set_basic_env):
    import app.main as main

    importlib.reload(main)

    monkeypatch.setattr(main, "update_metadata", lambda fid, **f: {"tempo": 120})

    with TestClient(main.app) as client:
        r = client.patch("/update/abc", json={"tempo": 120})
    assert r.status_code == 200
    assert r.json() == {"file_id": "abc", "updated_fields": {"tempo": 120}}


def test_patch_update_error(monkeypatch, set_basic_env):
    import app.main as main

    importlib.reload(main)

    monkeypatch.setattr(main, "update_metadata", lambda fid, **f: {"error": "bad"})

    with TestClient(main.app) as client:
        r = client.patch("/update/abc", json={"tempo": 120})
    assert r.status_code == 500
    assert r.json()["detail"] == "bad"


def test_delete_success(monkeypatch, set_basic_env):
    import app.main as main

    importlib.reload(main)

    monkeypatch.setattr(main, "delete_metadata", lambda fid: {"status": "success"})

    with TestClient(main.app) as client:
        r = client.delete("/samples/abc")
    assert r.status_code == 200
    assert r.json() == {"file_id": "abc", "deleted": True}


def test_delete_error(monkeypatch, set_basic_env):
    import app.main as main

    importlib.reload(main)

    monkeypatch.setattr(main, "delete_metadata", lambda fid: {"error": "oops"})

    with TestClient(main.app) as client:
        r = client.delete("/samples/abc")
    assert r.status_code == 500
    assert r.json()["detail"] == "oops"
