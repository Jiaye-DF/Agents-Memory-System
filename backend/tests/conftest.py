"""pytest 共用設定（v1.3.4 起）。

測試從 ``backend/`` 子目錄跑時無法直接載入專案根目錄的 ``.env``；
此處在 ``Settings()`` 初始化前注入測試用 fallback，讓 import 鏈不會
卡在 pydantic-settings 的必填欄位驗證。
"""
from __future__ import annotations

import os

# 必須在 import app.core.config 之前設定（pydantic-settings 在
# 模組載入時即時驗證）。pytest collection 階段已會 import 任何
# 含 from app... 的檔案，所以放 conftest.py 頂層即可。
os.environ.setdefault("POSTGRES_USER", "test")
os.environ.setdefault("POSTGRES_PASSWORD", "test")
os.environ.setdefault("POSTGRES_DB", "test")
os.environ.setdefault("SECRET_KEY", "test-secret-not-used-in-unit-tests")
