from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from .models import CreateSessionRequest, ResumePatch, ResumeProfile, SessionState


class SessionNotFoundError(KeyError):
    pass


class InMemorySessionStore:
    """带 JSON 持久化的会话存储：数据在重启后仍然保留"""

    def __init__(self, data_dir: str = "data") -> None:
        self._sessions: dict[str, SessionState] = {}
        self._lock = asyncio.Lock()
        self._data_file = Path(data_dir) / "sessions.json"
        self._data_file.parent.mkdir(parents=True, exist_ok=True)
        self._load_from_disk()

    def _load_from_disk(self) -> None:
        """启动时从磁盘加载会话"""
        if not self._data_file.exists():
            return
        try:
            raw = json.loads(self._data_file.read_text(encoding="utf-8"))
            for item in raw:
                session = SessionState.model_validate(item)
                self._sessions[session.id] = session
        except Exception:
            # 数据损坏时不影响启动
            pass

    def _save_to_disk(self) -> None:
        """保存所有会话到磁盘"""
        try:
            data = [
                session.model_dump(mode="json")
                for session in self._sessions.values()
            ]
            self._data_file.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            # 保存失败不影响内存操作
            pass

    async def create(self, request: CreateSessionRequest) -> SessionState:
        state = SessionState(
            id=f"sess_{uuid4().hex[:12]}",
            resume=request.resume,
            preferred_locations=request.preferred_locations,
            remote_preference=request.remote_preference,
        )
        async with self._lock:
            self._sessions[state.id] = state
            self._save_to_disk()
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
            self._save_to_disk()
            return state.model_copy(deep=True)