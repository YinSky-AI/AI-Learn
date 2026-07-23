# -*- coding: utf-8 -*-
"""先只读核验双库 revision，再启动 Uvicorn workers。"""

import asyncio
import sys

import uvicorn


from app.core.config import settings
from app.core.database import ai_learn_engine, engine
from app.core.schema_version import SchemaVersionError, verify_schema_targets


async def preflight_schema() -> None:
    await verify_schema_targets(
        {"primary": engine, "question-bank": ai_learn_engine},
        policy=settings.SCHEMA_VERSION_POLICY,
    )


def main() -> int:
    try:
        asyncio.run(preflight_schema())
    except SchemaVersionError as exc:
        print(f"应用启动失败：{exc}", file=sys.stderr)
        return 2
    except Exception:
        print("应用启动失败：Schema 版本检查不可用。", file=sys.stderr)
        return 1

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        workers=2,
        log_level="info",
        access_log=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
