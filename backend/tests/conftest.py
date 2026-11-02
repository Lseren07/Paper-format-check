"""测试公共配置：引擎鉴权与固定测试密钥。

`FORMAT_ENGINE_KEY` 必须在导入 app 之前设置，否则 `require_engine_key` 会
把所有请求判成 401。已有用例不带 header，因此默认用 dependency_overrides
绕过鉴权；401 分支由 `test_engine_key.py` 单独覆盖。
"""

import os

os.environ.setdefault("FORMAT_ENGINE_KEY", "test-key")

import pytest  # noqa: E402

from backend.app.main import app  # noqa: E402
from backend.app.security import require_engine_key  # noqa: E402


@pytest.fixture(autouse=True)
def _bypass_engine_key():
    app.dependency_overrides[require_engine_key] = lambda: None
    try:
        yield
    finally:
        app.dependency_overrides.pop(require_engine_key, None)
