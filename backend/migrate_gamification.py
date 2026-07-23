# -*- coding: utf-8 -*-
"""旧入口保留为无副作用提示；Schema 只允许由 Alembic revision 演进。"""

import sys


def main() -> int:
    print(
        "此脚本已停用且未执行数据库操作；请使用经目标核验的 "
        "python schema_admin.py upgrade 命令。",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
