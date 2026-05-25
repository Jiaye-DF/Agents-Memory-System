"""``app.storage.s3_storage`` 單元測試（v1.5.0 Phase 8-1）。

涵蓋：
- ``build_key`` 正常 / 接受 ``uuid.UUID``
- ``_sanitize_filename`` 路徑字元 / 控制字元 / Unicode 保留 / 純非法 → ``ValueError``
- ``put_object`` + ``get_object`` round trip（bytes 一致 + ContentType）
- ``mark_deleted`` 後 ``get_object_tagging`` 驗 ``status=deleted``
- ``exists`` true / false
- lazy init 缺憑證 raise ``RuntimeError``

WHY moto：避免真實 AWS / 憑證依賴；``mock_aws`` 提供 in-process S3。
WHY 每個 test 重置 ``_client``：模組層 cache 跨測試會殘留, 導致先前 monkeypatch
的 settings 與新 mock context 不一致。
"""
from __future__ import annotations

import uuid

import pytest

boto3 = pytest.importorskip("boto3")
moto = pytest.importorskip("moto")

from botocore.exceptions import ClientError  # noqa: E402
from moto import mock_aws  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.storage import s3_storage  # noqa: E402


_TEST_BUCKET = "test-bucket"
_TEST_REGION = "ap-northeast-1"


@pytest.fixture
def s3_env(monkeypatch: pytest.MonkeyPatch):
    """提供 moto 假 S3 + 對齊 settings + 重置 module client cache。"""
    monkeypatch.setattr(settings, "AWS_ACCESS_KEY_ID", "test-key", raising=False)
    monkeypatch.setattr(
        settings, "AWS_SECRET_ACCESS_KEY", "test-secret", raising=False
    )
    monkeypatch.setattr(settings, "AWS_REGION", _TEST_REGION, raising=False)
    monkeypatch.setattr(settings, "S3_BUCKET", _TEST_BUCKET, raising=False)
    s3_storage._client = None
    with mock_aws():
        client = boto3.client("s3", region_name=_TEST_REGION)
        client.create_bucket(
            Bucket=_TEST_BUCKET,
            CreateBucketConfiguration={"LocationConstraint": _TEST_REGION},
        )
        yield client
    s3_storage._client = None


# ---------------------------------------------------------------------------
# build_key
# ---------------------------------------------------------------------------


def test_build_key_basic():
    key = s3_storage.build_key("skills", "abc-123", "foo.zip")
    assert key == "skills/abc-123/foo.zip"


def test_build_key_accepts_uuid():
    uid = uuid.UUID("12345678-1234-5678-1234-567812345678")
    key = s3_storage.build_key("attachments", uid, "report.pdf")
    assert key == f"attachments/{uid}/report.pdf"


def test_build_key_sanitizes_filename():
    key = s3_storage.build_key("scripts", "uid-1", "../etc/passwd")
    # `..` 與 `/` 都會被替換為 `_`
    assert key == "scripts/uid-1/__etc_passwd"


# ---------------------------------------------------------------------------
# _sanitize_filename
# ---------------------------------------------------------------------------


def test_sanitize_replaces_path_chars():
    assert s3_storage._sanitize_filename("a/b") == "a_b"
    assert s3_storage._sanitize_filename("a\\b") == "a_b"
    assert s3_storage._sanitize_filename("..foo") == "_foo"


def test_sanitize_strips_control_chars():
    raw = "hello\x00world\x1fend"
    assert s3_storage._sanitize_filename(raw) == "helloworldend"


def test_sanitize_preserves_unicode_and_spaces():
    raw = "報告 final v2.pdf"
    assert s3_storage._sanitize_filename(raw) == "報告 final v2.pdf"


def test_sanitize_raises_when_all_chars_illegal():
    with pytest.raises(ValueError):
        s3_storage._sanitize_filename("\x00\x01\x02")


# ---------------------------------------------------------------------------
# put_object + get_object round trip
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_put_and_get_round_trip(s3_env):
    key = "skills/uid-1/payload.zip"
    body = b"hello-bytes-\x00\x01"
    await s3_storage.put_object(key, body, "application/zip")

    fetched = await s3_storage.get_object(key)
    assert fetched == body

    head = s3_env.head_object(Bucket=_TEST_BUCKET, Key=key)
    assert head["ContentType"] == "application/zip"


# ---------------------------------------------------------------------------
# mark_deleted
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mark_deleted_sets_status_tag(s3_env):
    key = "attachments/uid-2/report.pdf"
    await s3_storage.put_object(key, b"data", "application/pdf")
    await s3_storage.mark_deleted(key)

    resp = s3_env.get_object_tagging(Bucket=_TEST_BUCKET, Key=key)
    tags = {t["Key"]: t["Value"] for t in resp["TagSet"]}
    assert tags == {"status": "deleted"}


# ---------------------------------------------------------------------------
# exists
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_exists_true_when_object_present(s3_env):
    key = "scripts/uid-3/a.zip"
    await s3_storage.put_object(key, b"x", "application/zip")
    assert await s3_storage.exists(key) is True


@pytest.mark.asyncio
async def test_exists_false_when_object_absent(s3_env):
    assert await s3_storage.exists("scripts/uid-3/missing.zip") is False


# ---------------------------------------------------------------------------
# lazy init / missing credentials
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_client_raises_when_credentials_missing(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(settings, "AWS_ACCESS_KEY_ID", "", raising=False)
    monkeypatch.setattr(settings, "AWS_SECRET_ACCESS_KEY", "", raising=False)
    monkeypatch.setattr(settings, "S3_BUCKET", "", raising=False)
    s3_storage._client = None
    try:
        with pytest.raises(RuntimeError):
            await s3_storage.put_object("k", b"x", "text/plain")
    finally:
        s3_storage._client = None


@pytest.mark.asyncio
async def test_get_client_raises_when_only_bucket_missing(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(settings, "AWS_ACCESS_KEY_ID", "k", raising=False)
    monkeypatch.setattr(settings, "AWS_SECRET_ACCESS_KEY", "s", raising=False)
    monkeypatch.setattr(settings, "S3_BUCKET", "", raising=False)
    s3_storage._client = None
    try:
        with pytest.raises(RuntimeError):
            await s3_storage.put_object("k", b"x", "text/plain")
    finally:
        s3_storage._client = None


# ---------------------------------------------------------------------------
# 互動：exists 對非 404 ClientError 應 raise
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_exists_propagates_non_404_client_error(
    monkeypatch: pytest.MonkeyPatch, s3_env
):
    def boom(*args, **kwargs):
        raise ClientError(
            {"Error": {"Code": "500", "Message": "boom"}}, "HeadObject"
        )

    client = s3_storage._get_client()
    monkeypatch.setattr(client, "head_object", boom)
    with pytest.raises(ClientError):
        await s3_storage.exists("any/key")
