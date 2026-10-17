from __future__ import annotations

import sys

import pytest

from studio import teardown_adapter as ta


@pytest.mark.parametrize("url", [
    "https://v.douyin.com/abcd/", "https://www.douyin.com/video/7604889380867588283",
    "v.douyin.com/abcd/", "https://www.iesdouyin.com/share/video/1",
])
def test_validate_url_accepts_douyin(url):
    assert "douyin.com" in ta.validate_url(url)


@pytest.mark.parametrize("url", [
    "https://example.com/v", "https://douyin.com.evil.io/x", "https://notdouyin.com/x",
    "ftp://x", "", "javascript:alert(1)", "https://www.xiaohongshu.com/explore/1",
])
def test_validate_url_rejects_others(url):
    with pytest.raises(ta.TeardownError):
        ta.validate_url(url)


def test_missing_engine_gives_actionable_message(monkeypatch):
    for name in [m for m in sys.modules if m.startswith("douyin_teardown")]:
        monkeypatch.delitem(sys.modules, name)
    monkeypatch.setitem(sys.modules, "douyin_teardown", None)  # 让 import 失败
    with pytest.raises(ta.TeardownError, match="setup.sh"):
        ta.run_teardown("https://v.douyin.com/abcd/", lambda _s: None)
    env = ta.check_environment()
    assert any(c["key"] == "engine" and not c["ok"] for c in env)
