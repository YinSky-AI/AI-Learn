"""Run the durable diagnosis worker against the primary database."""

import asyncio
import os
import socket

from app.ai.provider import get_ai_provider
from app.core.database import AsyncSessionLocal
from app.services.diagnosis_job_service import claim_diagnosis_job, process_diagnosis_job


async def run_worker_once(session_factory, provider, worker_id: str) -> bool:
    async with session_factory() as db:
        async with db.begin():
            claimed = await claim_diagnosis_job(db, worker_id)
    if claimed is None:
        return False
    await process_diagnosis_job(session_factory, claimed, provider)
    return True


async def main() -> None:
    worker_id = os.getenv("DIAGNOSIS_WORKER_ID", socket.gethostname())
    provider = get_ai_provider()
    while True:
        worked = await run_worker_once(AsyncSessionLocal, provider, worker_id)
        if not worked:
            await asyncio.sleep(2)


if __name__ == "__main__":
    asyncio.run(main())
