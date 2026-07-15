"""skill_repository.search_similar 單測（v1.6.2 多向量 1:N）。

測試環境無 pgvector PostgreSQL（conftest 無真 DB fixture），故不整合驗證
cosine 距離運算本身；改以假 DB 驗證兩層 SQL：

- 內層條款：FROM skill_embedding 純 HNSW 近鄰（ORDER BY <=> / LIMIT :candidate_k）
- 外層條款：JOIN skill 過濾（is_deleted / visibility）+ GROUP BY + HAVING MAX + ORDER BY score DESC / LIMIT :top_k
- 綁定參數正確（vector literal / user_uid / min_score / candidate_k = top_k * 6 / top_k）
- raw SQL 回傳順序保序（分數排序由 DB 端 ORDER BY 保證）
- 空結果 early-return，不再發第二段 ORM 查詢
- scope 切換可見性條款（v1.6.1：public 僅 visibility 條款；未知值防呆落回 visible）
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
async def test_search_similar_two_layer_sql_clauses_and_params():
    """兩層 SQL 條款齊全，且綁定參數（vector / user_uid / min_score / candidate_k / top_k）正確。"""
    user_uid = str(uuid.uuid4())
    uid = uuid.uuid4()
    db = _FakeDB(
        raw_rows=[{"skill_uid": uid, "score": 0.9}],
        orm_skills=[_mk_skill(uid)],
    )

    await skill_repository.search_similar([0.25, 0.5], 8, 0.5, user_uid, db)

    stmt, params = db.calls[0]
    sql = str(stmt)
    # 內層：對 skill_embedding 純 HNSW 近鄰取候選
    assert "FROM skill_embedding" in sql
    assert "ORDER BY se.embedding <=> CAST(:query AS vector)" in sql
    assert "LIMIT :candidate_k" in sql
    # 外層：join skill 過濾 + per-skill 取 MAX
    assert "JOIN skill s ON s.skill_uid = t.skill_uid" in sql
    assert "s.is_deleted = FALSE" in sql
    assert (
        "s.owner_user_uid = CAST(:user_uid AS uuid) OR s.visibility = 'public'"
        in sql
    )
    assert "GROUP BY t.skill_uid" in sql
    assert "HAVING MAX(t.score) >= :min_score" in sql
    assert "ORDER BY score DESC" in sql
    assert "LIMIT :top_k" in sql

    assert params["query"] == "[0.25,0.5]"
    assert params["user_uid"] == user_uid
    assert params["min_score"] == 0.5
    assert params["candidate_k"] == 8 * skill_repository.CANDIDATE_MULTIPLIER
    assert params["candidate_k"] == 48
    assert params["top_k"] == 8


@pytest.mark.asyncio
async def test_search_similar_preserves_raw_row_order_and_scores():
    """回傳順序沿用 raw SQL（DB 端 MAX 分數排序），ORM 補回順序不影響結果。"""
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
async def test_search_similar_public_scope_excludes_owner_clause():
    """scope="public" 時可見性條款僅 visibility，不含 owner 條件，也不綁 user_uid。"""
    db = _FakeDB(raw_rows=[], orm_skills=[])

    await skill_repository.search_similar(
        [0.1], 8, 0.5, str(uuid.uuid4()), db, scope="public"
    )

    stmt, params = db.calls[0]
    sql = str(stmt)
    assert "s.visibility = 'public'" in sql
    assert "owner_user_uid" not in sql
    assert "user_uid" not in params
    # 其餘條款不受 scope 影響
    assert "FROM skill_embedding" in sql
    assert "LIMIT :candidate_k" in sql
    assert "s.is_deleted = FALSE" in sql
    assert "GROUP BY t.skill_uid" in sql
    assert "HAVING MAX(t.score) >= :min_score" in sql
    assert "LIMIT :top_k" in sql


@pytest.mark.asyncio
async def test_search_similar_unknown_scope_falls_back_to_visible():
    """未知 scope 值防呆：一律當 "visible"（條款與預設 scope 一致）。"""
    user_uid = str(uuid.uuid4())
    db = _FakeDB(raw_rows=[], orm_skills=[])

    await skill_repository.search_similar(
        [0.1], 8, 0.5, user_uid, db, scope="not-a-scope"
    )

    stmt, params = db.calls[0]
    sql = str(stmt)
    assert (
        "s.owner_user_uid = CAST(:user_uid AS uuid) OR s.visibility = 'public'"
        in sql
    )
    assert params["user_uid"] == user_uid


@pytest.mark.asyncio
async def test_search_similar_normalizes_user_uid():
    """user_uid 以 uuid 正規化後綁定（無連字號輸入轉為標準格式）。"""
    raw = uuid.uuid4()
    compact = raw.hex  # 無連字號格式
    db = _FakeDB(raw_rows=[], orm_skills=[])

    await skill_repository.search_similar([0.1], 8, 0.5, compact, db)

    _, params = db.calls[0]
    assert params["user_uid"] == str(raw)
