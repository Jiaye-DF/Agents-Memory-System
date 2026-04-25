"""rrf_fuse 單測（v1.3.5 Phase 8 驗收）。

純算術，不依賴 DB / Redis；目的：
- 三層輸入產出長度與排序正確
- k=60 公式驗證（rank=1 → 1/61；rank=2 → 1/62）
- 邊界：某層為空 → 不報錯、其他層仍融合
- final_top_k 截斷正確

WHY 直接 SimpleNamespace mock：rrf_fuse 只讀 mem 物件的 attribute（getattr），
不需建構真正的 ORM；省掉 pgvector / DB 依賴。
"""

from types import SimpleNamespace

import pytest

# 跳過測試若 pgvector 未裝（CI 環境保護；rrf_fuse 本身不依賴 pgvector，但 import path 會經過）
pgvector = pytest.importorskip("pgvector")  # noqa: F841

from app.services.rag_service import rrf_fuse  # noqa: E402


def _mk_session_mem(uid: str, topic: str = "t", keywords=None):
    return SimpleNamespace(
        chat_memory_uid=uid,
        topic=topic,
        keywords=keywords or [],
        entities=[],
    )


def _mk_project_mem(uid: str, topic: str = "p", keywords=None):
    return SimpleNamespace(
        project_memory_uid=uid,
        topic=topic,
        keywords=keywords or [],
        entities=[],
    )


def _mk_user_mem(uid: str, topic: str = "u", keywords=None):
    return SimpleNamespace(
        user_memory_uid=uid,
        topic=topic,
        keywords=keywords or [],
        entities=[],
    )


def test_rrf_fuse_three_layers_basic_top_k():
    layers = {
        "session": [(_mk_session_mem(f"s{i}"), 0.9 - i * 0.05) for i in range(5)],
        "project": [(_mk_project_mem(f"p{i}"), 0.8 - i * 0.05) for i in range(5)],
        "user": [(_mk_user_mem(f"u{i}"), 0.7 - i * 0.05) for i in range(5)],
    }
    out = rrf_fuse(layers, k=60, final_top_k=8)
    # 三層各 5 筆 → 共 15；final_top_k=8 截斷
    assert len(out) == 8
    # 降序
    scores = [item.rrf_score for item in out]
    assert scores == sorted(scores, reverse=True)


def test_rrf_fuse_k60_formula():
    layers = {
        "session": [(_mk_session_mem("s0"), 0.9)],
        "project": [],
        "user": [],
    }
    out = rrf_fuse(layers, k=60, final_top_k=8)
    assert len(out) == 1
    # rank=1 → score = 1/(60+1) = 1/61
    assert out[0].rrf_score == pytest.approx(1.0 / 61)
    assert out[0].source_rank == 1


def test_rrf_fuse_rank_2():
    layers = {
        "session": [
            (_mk_session_mem("s0"), 0.9),
            (_mk_session_mem("s1"), 0.5),
        ],
        "project": [],
        "user": [],
    }
    out = rrf_fuse(layers, k=60, final_top_k=8)
    assert len(out) == 2
    # rank=1 → 1/61；rank=2 → 1/62
    assert out[0].rrf_score == pytest.approx(1.0 / 61)
    assert out[1].rrf_score == pytest.approx(1.0 / 62)


def test_rrf_fuse_empty_layer_does_not_break():
    """某層為空時其他層仍融合。"""
    layers = {
        "session": [(_mk_session_mem("s0"), 0.9)],
        "project": [],
        "user": [(_mk_user_mem("u0"), 0.7)],
    }
    out = rrf_fuse(layers, k=60, final_top_k=8)
    assert len(out) == 2
    scopes = {item.scope for item in out}
    assert scopes == {"session", "user"}


def test_rrf_fuse_higher_rank_ranks_higher():
    """rank=1 的 item 永遠贏 rank=2，不管原始分數。"""
    layers = {
        "session": [(_mk_session_mem("s0"), 0.5)],  # rank=1 in session
        "project": [
            (_mk_project_mem("p0"), 0.99),  # rank=1 in project
            (_mk_project_mem("p1"), 0.98),  # rank=2 in project
        ],
        "user": [],
    }
    out = rrf_fuse(layers, k=60, final_top_k=8)
    # 同 rank=1 兩筆；其中一筆 rank=2
    assert len(out) == 3
    # rank=1 的兩筆排前面、rank=2 的最後
    assert out[-1].source_rank == 2


def test_rrf_fuse_unknown_scope_skipped():
    layers = {
        "session": [(_mk_session_mem("s0"), 0.9)],
        "garbage": [(SimpleNamespace(some_uid="x"), 0.9)],
    }
    out = rrf_fuse(layers, k=60, final_top_k=8)
    assert len(out) == 1
    assert out[0].scope == "session"
