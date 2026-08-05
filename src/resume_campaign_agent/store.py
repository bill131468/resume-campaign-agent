from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from uuid import uuid4

from .models import CreateSessionRequest, ResumePatch, ResumeProfile, SessionState


class SessionNotFoundError(KeyError):
    pass


class InMemorySessionStore:
    """PII-minimizing prototype store: data is discarded when the process exits."""

    def __init__(self) -> None:
        self._sessions: dict[str, SessionState] = {}
        self._lock = asyncio.Lock()

    async def create(self, request: CreateSessionRequest) -> SessionState:
        state = SessionState(
            id=f"sess_{uuid4().hex[:12]}",
            resume=request.resume,
            preferred_locations=request.preferred_locations,
            remote_preference=request.remote_preference,
        )
        async with self._lock:
            self._sessions[state.id] = state
        return state.model_copy(deep=True)

    async def get(self, session_id: str) -> SessionState:
        async with self._lock:
            state = self._sessions.get(session_id)
            if state is None:
                raise SessionNotFoundError(session_id)
            return state.model_copy(deep=True)

    async def list(self) -> list[SessionState]:
        async with self._lock:
            return [
                state.model_copy(deep=True)
                for state in sorted(
                    self._sessions.values(), key=lambda item: item.updated_at, reverse=True
                )
            ]

    async def update_resume(self, session_id: str, patch: ResumePatch) -> SessionState:
        async with self._lock:
            state = self._sessions.get(session_id)
            if state is None:
                raise SessionNotFoundError(session_id)
            update = patch.model_dump(exclude_unset=True)
            resume_data = state.resume.model_dump()
            resume_data.update(update)
            state.resume = ResumeProfile.model_validate(resume_data)
            state.updated_at = datetime.now(timezone.utc)
            return state.model_copy(deep=True)
