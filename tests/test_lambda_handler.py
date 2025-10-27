import importlib

import pytest


@pytest.mark.usefixtures("set_basic_env", "stub_soundfile_and_mutagen")
def test_handler_success_updates_ddb_and_s3(monkeypatch):
    import analyzer.handler as handler

    importlib.reload(handler)

    # Make duration and tempo deterministic
    monkeypatch.setattr(handler, "_fast_duration", lambda path, ext: (3.5, "stub"))
    monkeypatch.setattr(handler, "_bounded_tempo", lambda path: (120.0, 42, 0.01))

    event = {"bucket": "test-bucket", "key": "uploads/abc.wav", "file_id": "fid-1"}
    result = handler.handler(event)

    assert "error" not in result
    assert result["bucket"] == "test-bucket"
    assert result["key"] == "uploads/abc.wav"
    analysis = result["analysis"]
    assert analysis["duration"] == 3.5
    assert analysis["tempo"] == 120.0
    assert analysis["beats"] == 42

    # S3 JSON written
    assert len(handler.s3.puts) == 1
    put = handler.s3.puts[0]
    assert put["Bucket"] == "test-bucket"
    assert put["Key"].startswith("analysis/")
    assert put["ContentType"] == "application/json"

    # DDB update called
    assert len(handler.table.updated) == 1
    upd = handler.table.updated[0]
    assert upd["Key"] == {"file_id": "fid-1"}


@pytest.mark.usefixtures("set_basic_env", "stub_soundfile_and_mutagen")
def test_handler_inserts_when_no_file_id(monkeypatch):
    import analyzer.handler as handler

    importlib.reload(handler)

    monkeypatch.setattr(handler, "_fast_duration", lambda path, ext: (2.0, "stub"))
    monkeypatch.setattr(handler, "_bounded_tempo", lambda path: (0.0, 0, 0.0))

    event = {"bucket": "test-bucket", "key": "uploads/foo.mp3"}
    result = handler.handler(event)

    assert "error" not in result
    # Put item called
    assert len(handler.table.put_items) == 1
    item = handler.table.put_items[0]["Item"]
    assert item["file_id"] == "foo.mp3"
    assert item["s3_key"] == "uploads/foo.mp3"


@pytest.mark.usefixtures("set_basic_env")
def test_handler_missing_params(monkeypatch):
    import analyzer.handler as handler

    importlib.reload(handler)

    res = handler.handler({})
    assert res == {"error": "Missing bucket or key"}
