from types import SimpleNamespace

import pytest
from fastapi import HTTPException


@pytest.mark.asyncio
async def test_error_log_rejects_non_admin_before_querying_database():
    from app.api.v1.ai import list_error_logs

    class DatabaseMustNotBeUsed:
        async def execute(self, _statement):
            raise AssertionError("非管理员请求不应查询错误日志")

    with pytest.raises(HTTPException, match="仅管理员可以查看错误日志") as error:
        await list_error_logs(
            error_type=None,
            severity=None,
            agent_name=None,
            page=1,
            page_size=20,
            user=SimpleNamespace(is_admin=False),
            db=DatabaseMustNotBeUsed(),
        )

    assert error.value.status_code == 403
