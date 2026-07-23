"""Run one durable GenerationJob worker loop against the primary database."""

import asyncio
import os
import socket

from app.ai.provider import get_ai_provider
from app.ai.question_pipeline import QuestionPipeline
from app.core.database import AsyncSessionLocal
from app.services.question_generation_service import claim_next_generation_job, process_claimed_generation_job


async def main() -> None:
    worker_id = os.getenv("GENERATION_WORKER_ID", socket.gethostname())
    while True:
        async with AsyncSessionLocal() as db:
            async with db.begin():
                job = await claim_next_generation_job(db, worker_id)
                if job is None:
                    await asyncio.sleep(2)
                    continue
                await process_claimed_generation_job(db, job, QuestionPipeline(get_ai_provider()))


if __name__ == "__main__":
    asyncio.run(main())
