"""skill_repository.search_similar 單測（v1.6.0 Phase 10-1）。

測試環境無 pgvector PostgreSQL（conftest 無真 DB fixture），故不整合驗證
cosine 距離運算本身；改以假 DB 驗證：

- raw SQL 條款正確（is_deleted / embedding IS NOT NULL / visibility / min_score / ORDER BY）
- 綁定參數正確（vector literal / user_uid / min_score / top_k）
- raw SQL 回傳順序保序（cosine 排序由 DB 端 ORDER BY 保證）
- 空結果 early-return，不再發第二段 ORM 查詢
"""
from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

# 跳過測試若 pgvector 未裝（import 鏈經過 app.models.skill → pgvector）
pgvector = pytest.importorskip("pgvector")  # noqa: F841

from app.repositories import skill_repository  # noqa: E402


class _FakeResult:
    def __init__(self, mapping_rows=None, scalar_items=None):
        self._mapping_rows = mapping_rows or []
        self._scalar_items = scalar_items or []

    def mappings(self):
        return SimpleNamespace(all=lambda: self._mapping_rows)

    def scalars(self):
        return SimpleNamespace(all=lambda: self._scalar_items)


class _FakeDB:
    """假 AsyncSession：第一次 execute 回 raw rows，第二次回 ORM skills。"""

    def __init__(self, raw_rows, orm_skills):
        self._raw_rows = raw_rows
        self._orm_skills = orm_skills
        self.calls: list[tuple] = []

    async def execute(self, stmt, params=None):
        self.calls.append((stmt, params))
        if len(self.calls) == 1:
            return _FakeResult(mapping_rows=self._raw_rows)
        return _FakeResult(scalar_items=self._orm_skills)


def _mk_skill(skill_uid: uuid.UUID):
    return SimpleNamespace(skill_uid=skill_uid)


@pytest.mark.asyncio
async def test_search_similar_sql_clauses_and_params():
    """raw SQL 含全部過濾條款，且綁定參數（vector / user_uid / min_score / top_k）正確。"""
    user_uid = str(uuid.uuid4())
    uid = uuid.uuid4()
    db = _FakeDB(
        raw_rows=[{"skill_uid": uid, "score": 0.9}],
        orm_skills=[_mk_skill(uid)],
    )

    await skill_repository.search_similar([0.25, 0.5], 8, 0.5, user_uid, db)

    stmt, params = db.calls[0]
    sql = str(stmt)
    assert "is_deleted = FALSE" in sql
    assert "embedding IS NOT NULL" in sql
    assert "owner_user_uid = CAST(:user_uid AS uuid) OR visibility = 'public'" in sql
    assert "1 - (embedding <=> CAST(:query AS vector)) >= :min_score" in sql
    assert "ORDER BY embedding <=> CAST(:query AS vector)" in sql
    assert "LIMIT :top_k" in sql

    assert params["query"] == "[0.25,0.5]"
    assert params["user_uid"] == user_uid
    assert params["min_score"] == 0.5
    assert params["top_k"] == 8


@pytest.mark.asyncio
async def test_search_similar_preserves_raw_row_order_and_scores():
    """回傳順序沿用 raw SQL（DB 端 cosine 排序），ORM 補回順序不影響結果。"""
    uid_a, uid_b, uid_c = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    skill_a, skill_b, skill_c = _mk_skill(uid_a), _mk_skill(uid_b), _mk_skill(uid_c)
    db = _FakeDB(
        raw_rows=[
            {"skill_uid": uid_b, "score": 0.95},
            {"skill_uid": uid_a, "score": 0.80},
            {"skill_uid": uid_c, "score": 0.60},
        ],
        # ORM 第二段查詢刻意亂序
        orm_skills=[skill_a, skill_c, skill_b],
    )

    out = await skill_repository.search_similar(
        [0.1], 8, 0.5, str(uuid.uuid4()), db
    )

    assert [s.skill_uid for s, _ in out] == [uid_b, uid_a, uid_c]
    assert [score for _, score in out] == [0.95, 0.80, 0.60]


@pytest.mark.asyncio
async def test_search_similar_empty_rows_returns_empty_without_orm_query():
    """raw SQL 無命中時回空 list，且不再發第二段 ORM 查詢。"""
    db = _FakeDB(raw_rows=[], orm_skills=[])
    out = await skill_repository.search_similar(
        [0.1], 8, 0.5, str(uuid.uuid4()), db
    )
    assert out == []
    assert len(db.calls) == 1


@pytest.mark.asyncio
async def test_search_similar_skips_uid_missing_in_orm_load():
    """ORM 補查缺漏的 skill_uid（如並發軟刪）自動跳過，不 KeyError。"""
    uid_a, uid_b = uuid.uuid4(), uuid.uuid4()
    db = _FakeDB(
        raw_rows=[
            {"skill_uid": uid_a, "score": 0.9},
            {"skill_uid": uid_b, "score": 0.8},
        ],
        orm_skills=[_mk_skill(uid_b)],
    )

    out = await skill_repository.search_similar(
        [0.1], 8, 0.5, str(uuid.uuid4()), db
    )

    assert len(out) == 1
    assert out[0][0].skill_uid == uid_b
    assert out[0][1] == 0.8


@pytest.mark.asyncio
async def test_search_similar_normalizes_user_uid():
    """user_uid 以 uuid 正規化後綁定（無連字號輸入轉為標準格式）。"""
    raw = uuid.uuid4()
    compact = raw.hex  # 無連字號格式
    db = _FakeDB(raw_rows=[], orm_skills=[])

    await skill_repository.search_similar([0.1], 8, 0.5, compact, db)

    _, params = db.calls[0]
    assert params["user_uid"] == str(raw)
