import sys
from types import ModuleType

import pytest


class _FakeBoto3Module(ModuleType):
    class _FakeS3:
        def __init__(self):
            self.uploads = []
            self.puts = []

        def upload_fileobj(self, fileobj, bucket, key):
            # Read without consuming for caller
            pos = fileobj.tell()
            data = fileobj.read()
            fileobj.seek(pos)
            self.uploads.append((bucket, key, len(data)))

        def download_file(self, bucket, key, filename):
            # Write a few bytes to the target file to simulate download
            with open(filename, "wb") as f:
                f.write(b"FAKE")

        def put_object(self, **kwargs):
            self.puts.append(kwargs)

    class _FakeLambda:
        def __init__(self, error: Exception | None = None):
            self.error = error
            self.invokes = []

        def invoke(self, **kwargs):
            if self.error:
                raise self.error
            self.invokes.append(kwargs)
            return {"StatusCode": 202}

    class _FakeTable:
        def __init__(self):
            self.updated = []
            self.deleted = []
            self.scanned = []
            self.gotten = {}
            self.put_items = []

        def update_item(self, **kwargs):
            self.updated.append(kwargs)
            return {"Attributes": kwargs.get("ExpressionAttributeValues", {})}

        def delete_item(self, **kwargs):
            self.deleted.append(kwargs)
            return {"ResponseMetadata": {"HTTPStatusCode": 200}}

        def scan(self, **kwargs):
            self.scanned.append(kwargs)
            return {"Items": []}

        def get_item(self, **kwargs):
            return {"Item": self.gotten.get(kwargs.get("Key", {}).get("file_id"))}

        def put_item(self, **kwargs):
            self.put_items.append(kwargs)
            return {"ResponseMetadata": {"HTTPStatusCode": 200}}

    class _FakeDynamoResource:
        def __init__(self):
            self.tables = {}

        def Table(self, name):
            t = self.tables.get(name)
            if not t:
                t = _FakeBoto3Module._FakeTable()
                self.tables[name] = t
            return t

    def __init__(self):
        super().__init__("boto3")
        self._s3 = _FakeBoto3Module._FakeS3()
        self._lambda = _FakeBoto3Module._FakeLambda()
        self._ddb = _FakeBoto3Module._FakeDynamoResource()

    def client(self, service_name, region_name=None):
        if service_name == "s3":
            return self._s3
        if service_name == "lambda":
            return self._lambda
        raise NotImplementedError(service_name)

    def resource(self, service_name, region_name=None):
        if service_name == "dynamodb":
            return self._ddb
        raise NotImplementedError(service_name)


@pytest.fixture(autouse=True)
def stub_boto3_module(monkeypatch):
    """Ensure a stub boto3 is available during tests so importing modules doesn't fail.
    Individual tests can still monkeypatch app/analyzer module attributes with their own fakes.
    """
    # Ensure project root is on sys.path for absolute imports like "analyzer" and "app"
    import os

    repo_root = os.path.dirname(os.path.dirname(__file__))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    fake = _FakeBoto3Module()
    sys.modules.setdefault("boto3", fake)

    # Provide a minimal botocore.exceptions.ClientError so app code can import without real botocore
    botocore_mod = ModuleType("botocore")
    exceptions_mod = ModuleType("botocore.exceptions")

    class ClientError(Exception):
        pass

    exceptions_mod.ClientError = ClientError
    sys.modules.setdefault("botocore", botocore_mod)
    sys.modules.setdefault("botocore.exceptions", exceptions_mod)

    yield
    # do not remove to avoid interfering with other tests in same session


@pytest.fixture(autouse=True)
def stub_soundfile_and_mutagen(monkeypatch):
    """Autouse: Provide minimal stubs for soundfile and mutagen so analyzer.handler can import
    without requiring heavyweight native audio libraries during tests and CI.
    """
    # soundfile
    sf_mod = ModuleType("soundfile")

    class _Info:
        def __init__(self, duration=None):
            self.duration = duration

    def info(path):
        return _Info(duration=0.0)

    sf_mod.info = info
    sys.modules.setdefault("soundfile", sf_mod)

    # mutagen.mp3
    mutagen_mod = ModuleType("mutagen")
    mp3_mod = ModuleType("mutagen.mp3")

    class MP3:
        class _Info:
            length = 0.0

        info = _Info()

        def __init__(self, path):
            pass

    mp3_mod.MP3 = MP3
    sys.modules.setdefault("mutagen", mutagen_mod)
    sys.modules.setdefault("mutagen.mp3", mp3_mod)
    yield


@pytest.fixture()
def set_basic_env(monkeypatch):
    monkeypatch.setenv("S3_BUCKET", "test-bucket")
    monkeypatch.setenv("LAMBDA_NAME", "test-lambda")
    monkeypatch.setenv("AWS_REGION", "us-west-2")
    monkeypatch.setenv("DDB_TABLE_NAME", "tunesugar-metadata")
    yield
