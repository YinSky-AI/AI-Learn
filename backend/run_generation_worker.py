"""Run one durable GenerationJob worker loop against the primary database."""

import asyncio
import os
import socket

from app.ai.provider import get_ai_provider
from app.ai.question_pipeline import QuestionPipeline
from app.core.database import AsyncSessionLocal
from app.services.question_generation_service import claim_next_generation_job, process_claimed_generation_job


async def run_worker_once(session_factory, pipeline, worker_id: str) -> bool:
    async with session_factory() as db:
        async with db.begin():
            claimed = await claim_next_generation_job(db, worker_id)
    if claimed is None:
        return False
    await process_claimed_generation_job(session_factory, claimed, pipeline)
    return True


async def main() -> None:
    worker_id = os.getenv("GENERATION_WORKER_ID", socket.gethostname())
    pipeline = QuestionPipeline(get_ai_provider())
    while True:
        worked = await run_worker_once(AsyncSessionLocal, pipeline, worker_id)
        if not worked:
            await asyncio.sleep(2)


if __name__ == "__main__":
    asyncio.run(main())
