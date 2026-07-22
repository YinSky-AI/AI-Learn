"""Server-authoritative daily challenge lifecycle and score helpers."""

from datetime import date, datetime, timezone
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content import Question
from app.models.daily_challenge import DailyChallenge, DailyChallengeAnswer, DailyChallengeAttempt, DailyChallengeQuestion
from app.models.user import User


def server_elapsed_seconds(started_at: datetime, time_limit_seconds: int, now: datetime | None = None) -> int:
    now = now or datetime.now(timezone.utc)
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=timezone.utc)
    return min(max(0, int((now - started_at).total_seconds())), time_limit_seconds)


def calculate_challenge_score(
    *,
    correct_count: int,
    total_count: int,
    elapsed_seconds: int,
    time_limit_seconds: int,
    streak_days: int = 0,
) -> dict:
    base_score = correct_count * 100
    speed_bonus = int(correct_count * 50 * max(0, time_limit_seconds - elapsed_seconds) / max(1, time_limit_seconds))
    streak_bonus = min(max(streak_days, 0), 7) * 10 if correct_count else 0
    return {
        "score": base_score + speed_bonus + streak_bonus,
        "base_score": base_score,
        "speed_bonus": speed_bonus,
        "streak_bonus": streak_bonus,
        "accuracy": round(correct_count / total_count, 4) if total_count else 0,
    }


def is_answer_correct(question_type: str, expected: str, submitted: str) -> bool:
    if question_type == "MULTIPLE_CHOICE":
        normalize = lambda value: {
            part.strip().casefold() for part in value.split(",") if part.strip()
        }
        return normalize(expected) == normalize(submitted)
    return submitted.strip().casefold() == expected.strip().casefold()


class DailyChallengeService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _today(self) -> DailyChallenge:
        challenge = (await self.db.execute(select(DailyChallenge).where(DailyChallenge.challenge_date == date.today()))).scalar_one_or_none()
        if challenge:
            return challenge
        questions = (await self.db.execute(select(Question).order_by(func.random()).limit(5))).scalars().all()
        if not questions:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail={"code": "CHALLENGE_001", "message": "今日挑战题目正在准备中，请稍后再试"})
        challenge = DailyChallenge(challenge_date=date.today(), question_count=len(questions))
        self.db.add(challenge)
        await self.db.flush()
        for position, question in enumerate(questions, 1):
            self.db.add(DailyChallengeQuestion(challenge_id=challenge.id, question_id=question.id, position=position))
        await self.db.flush()
        return challenge

    async def _questions(self, challenge_id: UUID):
        return list((await self.db.execute(select(DailyChallengeQuestion, Question).join(Question, Question.id == DailyChallengeQuestion.question_id).where(DailyChallengeQuestion.challenge_id == challenge_id).order_by(DailyChallengeQuestion.position))).all())

    @staticmethod
    def _question_payload(mapping, question) -> dict:
        options = [
            {"key": str(option.get("key", "")), "value": str(option.get("value", ""))}
            for option in (question.options or [])
            if isinstance(option, dict)
        ]
        return {"id": str(question.id), "position": mapping.position, "question_body": question.question_body, "question_type": question.question_type, "options": options, "difficulty": question.difficulty_level}

    @staticmethod
    def _attempt_payload(challenge, attempt, *, replayed=False, score=None, rank=None, expired=False) -> dict:
        remaining_seconds = 0 if attempt.completed else max(
            0,
            challenge.time_limit_seconds
            - server_elapsed_seconds(attempt.started_at, challenge.time_limit_seconds),
        )
        payload = {"challenge_id": str(challenge.id), "date": challenge.challenge_date.isoformat(), "subject": challenge.subject, "question_count": challenge.question_count, "time_limit_seconds": challenge.time_limit_seconds, "remaining_seconds": remaining_seconds, "started_at": attempt.started_at.isoformat(), "completed": attempt.completed, "replayed": replayed}
        if attempt.completed:
            base_score = attempt.correct_count * 100
            payload.update({"score": attempt.score, "base_score": base_score, "bonus_score": max(0, attempt.score - base_score), "correct_count": attempt.correct_count, "total_count": attempt.total_count, "time_spent_seconds": attempt.time_spent_seconds})
        if score:
            payload.update(score)
            payload["bonus_score"] = max(0, payload.get("score", 0) - payload.get("base_score", 0))
        if rank is not None:
            payload["rank"] = rank
        if expired:
            payload["expired"] = True
        return payload

    async def _rank(self, attempt: DailyChallengeAttempt) -> int:
        ahead = or_(
            DailyChallengeAttempt.score > attempt.score,
            and_(
                DailyChallengeAttempt.score == attempt.score,
                DailyChallengeAttempt.time_spent_seconds < attempt.time_spent_seconds,
            ),
            and_(
                DailyChallengeAttempt.score == attempt.score,
                DailyChallengeAttempt.time_spent_seconds == attempt.time_spent_seconds,
                DailyChallengeAttempt.completed_at < attempt.completed_at,
            ),
        )
        count = (
            await self.db.execute(
                select(func.count())
                .select_from(DailyChallengeAttempt)
                .where(
                    DailyChallengeAttempt.challenge_id == attempt.challenge_id,
                    DailyChallengeAttempt.completed.is_(True),
                    ahead,
                )
            )
        ).scalar_one()
        return int(count) + 1

    async def _user_rank(self, kind: str, user: User) -> int:
        if kind == "streak":
            ahead = or_(
                User.streak_days > (user.streak_days or 0),
                and_(
                    User.streak_days == (user.streak_days or 0),
                    User.total_score > (user.total_score or 0),
                ),
                and_(
                    User.streak_days == (user.streak_days or 0),
                    User.total_score == (user.total_score or 0),
                    User.created_at < user.created_at,
                ),
            )
        else:
            ahead = or_(
                User.total_score > (user.total_score or 0),
                and_(
                    User.total_score == (user.total_score or 0),
                    User.created_at < user.created_at,
                ),
            )
        count = (
            await self.db.execute(
                select(func.count())
                .select_from(User)
                .where(User.deleted_at.is_(None), ahead)
            )
        ).scalar_one()
        return int(count) + 1

    async def start(self, user_id: UUID) -> dict:
        challenge = await self._today()
        attempt = (await self.db.execute(select(DailyChallengeAttempt).where(DailyChallengeAttempt.challenge_id == challenge.id, DailyChallengeAttempt.user_id == user_id))).scalar_one_or_none()
        if attempt and attempt.completed:
            return self._attempt_payload(challenge, attempt, replayed=True, rank=await self._rank(attempt))
        if not attempt:
            attempt = DailyChallengeAttempt(challenge_id=challenge.id, user_id=user_id)
            self.db.add(attempt)
            await self.db.flush()
        payload = self._attempt_payload(challenge, attempt)
        payload["questions"] = [self._question_payload(mapping, question) for mapping, question in await self._questions(challenge.id)]
        return payload

    async def submit(self, user: User, event_id: UUID, answers: list[dict]) -> dict:
        challenge = await self._today()
        attempt = (
            await self.db.execute(
                select(DailyChallengeAttempt)
                .where(
                    DailyChallengeAttempt.challenge_id == challenge.id,
                    DailyChallengeAttempt.user_id == user.id,
                )
                .with_for_update()
            )
        ).scalar_one_or_none()
        if not attempt:
            raise HTTPException(status_code=409, detail={"code": "CHALLENGE_002", "message": "请先开始今日挑战"})
        if attempt.completed:
            return self._attempt_payload(challenge, attempt, replayed=True, rank=await self._rank(attempt))
        if (await self.db.execute(select(DailyChallengeAnswer).where(DailyChallengeAnswer.event_id == event_id))).scalar_one_or_none():
            return self._attempt_payload(challenge, attempt, replayed=True)
        elapsed = server_elapsed_seconds(attempt.started_at, challenge.time_limit_seconds)
        if elapsed >= challenge.time_limit_seconds:
            attempt.score = 0
            attempt.correct_count = 0
            attempt.total_count = challenge.question_count
            attempt.time_spent_seconds = challenge.time_limit_seconds
            attempt.completed = True
            attempt.completed_at = datetime.now(timezone.utc)
            await self.db.flush()
            score = {"base_score": 0, "speed_bonus": 0, "streak_bonus": 0, "accuracy": 0}
            return self._attempt_payload(
                challenge,
                attempt,
                score=score,
                rank=await self._rank(attempt),
                expired=True,
            )
        rows = await self._questions(challenge.id)
        expected = {str(question.id): question for _, question in rows}
        submitted = {str(item["question_id"]): item["selected_answer"].strip() for item in answers}
        if len(submitted) != len(answers) or set(submitted) != set(expected):
            raise HTTPException(status_code=422, detail={"code": "CHALLENGE_004", "message": "请完整且仅提交本次挑战的每一道题"})
        correct_count = 0
        for index, (_, question) in enumerate(rows):
            selected = submitted[str(question.id)]
            is_correct = is_answer_correct(
                question.question_type,
                question.correct_answer,
                selected,
            )
            correct_count += int(is_correct)
            self.db.add(DailyChallengeAnswer(attempt_id=attempt.id, question_id=question.id, selected_answer=selected, event_id=event_id if index == 0 else uuid4(), is_correct=is_correct))
        score = calculate_challenge_score(
            correct_count=correct_count,
            total_count=len(rows),
            elapsed_seconds=elapsed,
            time_limit_seconds=challenge.time_limit_seconds,
            streak_days=user.streak_days or 0,
        )
        attempt.score, attempt.correct_count, attempt.total_count = score["score"], correct_count, len(rows)
        attempt.time_spent_seconds, attempt.completed, attempt.completed_at = elapsed, True, datetime.now(timezone.utc)
        user.total_score = (user.total_score or 0) + attempt.score
        await self.db.flush()
        return self._attempt_payload(challenge, attempt, score=score, rank=await self._rank(attempt))

    async def leaderboard(self, kind: str, user_id: UUID, limit: int = 50) -> dict:
        if kind == "daily":
            challenge = await self._today()
            rows = (await self.db.execute(select(DailyChallengeAttempt, User).join(User, User.id == DailyChallengeAttempt.user_id).where(DailyChallengeAttempt.challenge_id == challenge.id, DailyChallengeAttempt.completed.is_(True), User.deleted_at.is_(None)).order_by(desc(DailyChallengeAttempt.score), DailyChallengeAttempt.time_spent_seconds, DailyChallengeAttempt.completed_at).limit(limit))).all()
            items = [{"rank": rank, "user_id": str(user.id), "nickname": user.nickname, "avatar_url": user.avatar_url, "value": attempt.score, "correct_count": attempt.correct_count, "time_spent_seconds": attempt.time_spent_seconds, "is_me": user.id == user_id} for rank, (attempt, user) in enumerate(rows, 1)]
            me = next((item for item in items if item["is_me"]), None)
            if me is None:
                current = (
                    await self.db.execute(
                        select(DailyChallengeAttempt, User)
                        .join(User, User.id == DailyChallengeAttempt.user_id)
                        .where(
                            DailyChallengeAttempt.challenge_id == challenge.id,
                            DailyChallengeAttempt.user_id == user_id,
                            DailyChallengeAttempt.completed.is_(True),
                            User.deleted_at.is_(None),
                        )
                    )
                ).first()
                if current:
                    attempt, user = current
                    me = {"rank": await self._rank(attempt), "user_id": str(user.id), "nickname": user.nickname, "avatar_url": user.avatar_url, "value": attempt.score, "correct_count": attempt.correct_count, "time_spent_seconds": attempt.time_spent_seconds, "is_me": True}
        else:
            order = desc(User.streak_days) if kind == "streak" else desc(User.total_score)
            users = (await self.db.execute(select(User).where(User.deleted_at.is_(None)).order_by(order, desc(User.total_score), User.created_at).limit(limit))).scalars().all()
            field = "streak_days" if kind == "streak" else "total_score"
            items = [{"rank": rank, "user_id": str(user.id), "nickname": user.nickname, "avatar_url": user.avatar_url, "value": getattr(user, field) or 0, "is_me": user.id == user_id} for rank, user in enumerate(users, 1)]
            me = next((item for item in items if item["is_me"]), None)
            if me is None:
                user = (
                    await self.db.execute(
                        select(User).where(User.id == user_id, User.deleted_at.is_(None))
                    )
                ).scalar_one_or_none()
                if user:
                    me = {"rank": await self._user_rank(kind, user), "user_id": str(user.id), "nickname": user.nickname, "avatar_url": user.avatar_url, "value": getattr(user, field) or 0, "is_me": True}
        return {"kind": kind, "items": items, "me": me, "message": "暂无上榜记录，快来成为第一位挑战者吧" if not items else ""}
