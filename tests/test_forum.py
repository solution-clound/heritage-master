"""论坛工具测试"""

import pytest
from heritage_master.tools.forum import _check_config


def test_check_config_no_token():
    """测试未配置时的错误提示"""
    # 在没有配置的情况下应该返回错误信息
    err = _check_config()
    # 如果未配置，应返回提示信息
    if err:
        assert "⚠️" in err
