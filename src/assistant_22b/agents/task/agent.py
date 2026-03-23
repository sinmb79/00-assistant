"""Task Agent — rule-based todo/schedule management."""
from __future__ import annotations

import re
from pathlib import Path

from assistant_22b.agents.base import BaseAgent
from assistant_22b.pipeline.context import AgentResult, PipelineContext
from assistant_22b.storage.tasks import TaskStore

_DATA_DIR = Path.home() / ".22b-assistant"

_DONE_KW = ["완료", "다 했어", "끝났어", "했어"]
_DELETE_KW = ["삭제", "취소", "지워"]
_UPDATE_KW = ["수정", "바꿔", "변경"]
_LIST_KW = ["오늘", "이번 주", "목록", "뭐 해야", "알려줘"]
_ADD_KW = ["추가", "등록", "할일", "해야", "만들어"]

_PRIORITY = {1: "높음", 2: "보통", 3: "낮음"}


class TaskAgent(BaseAgent):
    """Rule-based task management agent."""

    def __init__(self, manifest_dir: Path, store: TaskStore | None = None) -> None:
        super().__init__(manifest_dir)
        if store is not None:
            self._store = store
        else:
            data = _DATA_DIR
            db_dir = data / "db"
            db_dir.mkdir(parents=True, exist_ok=True)
            self._store = TaskStore(
                db_path=db_dir / "tasks.db",
                key_path=data / ".tasks_key",
            )

    def process(self, context: PipelineContext) -> AgentResult:
        try:
            return self._dispatch(context.input_text)
        except Exception as exc:
            return AgentResult(
                agent_id=self.agent_id,
                output="",
                citations=[],
                raw=[],
                error=f"TaskStore 접근 오류: {exc}",
            )

    def _dispatch(self, text: str) -> AgentResult:
        t = text.lower()
        intent = self._classify(t)
        if intent == "ADD":
            return self._handle_add(text)
        if intent == "LIST":
            return self._handle_list(t)
        if intent == "DONE":
            return self._handle_done(text)
        if intent == "DELETE":
            return self._handle_delete(text)
        if intent == "UPDATE":
            return self._handle_update(text)
        return AgentResult(
            agent_id=self.agent_id,
            output="무슨 일정 작업을 원하시나요? (추가/조회/완료/삭제)",
            citations=[],
            raw=[],
        )

    def _classify(self, text_lower: str) -> str:
        # Check higher-priority intents first to avoid keyword collisions
        # DONE > DELETE > UPDATE > LIST > ADD > UNKNOWN
        # LIST is checked before ADD because "할일 목록" and "오늘 뭐 해야" should be LIST
        for kw in _DONE_KW:
            if kw in text_lower:
                return "DONE"
        for kw in _DELETE_KW:
            if kw in text_lower:
                return "DELETE"
        for kw in _UPDATE_KW:
            if kw in text_lower:
                return "UPDATE"
        for kw in _LIST_KW:
            if kw in text_lower:
                return "LIST"
        for kw in _ADD_KW:
            if kw in text_lower:
                return "ADD"
        return "UNKNOWN"

    def _handle_add(self, text: str) -> AgentResult:
        # Remove intent keyword(s) to extract title
        title = re.sub(
            r"(추가|등록|할일|해야|만들어)(해줘|해|줘|요|하기)?[:\s]*",
            "", text, flags=re.IGNORECASE
        ).strip()
        if not title:
            title = text.strip()

        # Extract ISO date if present
        due_match = re.search(r"\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2})?", text)
        due_date = due_match.group() if due_match else None
        # Remove the date from title if it was extracted
        if due_date:
            title = title.replace(due_date, "").strip()

        # Remove trailing "마감" keyword if present after stripping
        title = re.sub(r"\s*마감\s*$", "", title).strip()

        self._store.add(title=title, due_date=due_date)
        msg = f"✅ 할일 추가됨: {title}"
        if due_date:
            msg += f" (마감: {due_date})"
        return AgentResult(agent_id=self.agent_id, output=msg, citations=[], raw=[])

    def _handle_list(self, text_lower: str) -> AgentResult:
        filter_ = None
        if "오늘" in text_lower:
            filter_ = "today"
        elif "이번 주" in text_lower:
            filter_ = "week"
        tasks = self._store.list_open(filter=filter_)
        if not tasks:
            label = {"today": "오늘", "week": "이번 주"}.get(filter_ or "", "")
            return AgentResult(
                agent_id=self.agent_id,
                output=f"{label + ' ' if label else ''}할일이 없습니다.",
                citations=[],
                raw=[],
            )
        lines = ["## 할일 목록\n"]
        for t in tasks:
            due = f" (마감: {t['due_date']})" if t.get("due_date") else ""
            pri = _PRIORITY.get(t.get("priority", 2), "보통")
            lines.append(f"- [{pri}] {t['title']}{due}")
        return AgentResult(
            agent_id=self.agent_id,
            output="\n".join(lines),
            citations=[],
            raw=[],
        )

    def _handle_done(self, text: str) -> AgentResult:
        matched = self._find_task_in_text(text, self._store.list_open())
        if not matched:
            return AgentResult(
                agent_id=self.agent_id,
                output="완료할 할일을 찾지 못했습니다. 할일 이름을 포함해서 말씀해 주세요.",
                citations=[],
                raw=[],
            )
        self._store.mark_done(matched["task_id"])
        return AgentResult(
            agent_id=self.agent_id,
            output=f"✅ 완료: {matched['title']}",
            citations=[],
            raw=[],
        )

    def _handle_delete(self, text: str) -> AgentResult:
        matched = self._find_task_in_text(text, self._store.list_open())
        if not matched:
            return AgentResult(
                agent_id=self.agent_id,
                output="삭제할 할일을 찾지 못했습니다. 할일 이름을 포함해서 말씀해 주세요.",
                citations=[],
                raw=[],
            )
        self._store.delete(matched["task_id"])
        return AgentResult(
            agent_id=self.agent_id,
            output=f"🗑️ 삭제됨: {matched['title']}",
            citations=[],
            raw=[],
        )

    def _handle_update(self, text: str) -> AgentResult:
        matched = self._find_task_in_text(text, self._store.list_open())
        if not matched:
            return AgentResult(
                agent_id=self.agent_id,
                output="수정할 할일을 찾지 못했습니다. 할일 이름을 포함해서 말씀해 주세요.",
                citations=[],
                raw=[],
            )
        due_match = re.search(r"\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2})?", text)
        if due_match:
            self._store.update(matched["task_id"], due_date=due_match.group())
            return AgentResult(
                agent_id=self.agent_id,
                output=f"✏️ 수정됨: {matched['title']}",
                citations=[],
                raw=[],
            )
        return AgentResult(
            agent_id=self.agent_id,
            output="수정할 내용을 인식하지 못했습니다. 날짜 형식(YYYY-MM-DD)을 포함해서 말씀해 주세요.",
            citations=[],
            raw=[],
        )

    @staticmethod
    def _find_task_in_text(text: str, tasks: list[dict]) -> dict | None:
        text_lower = text.lower()
        # First pass: exact title match (title is substring of input)
        for task in tasks:
            if task["title"].lower() in text_lower:
                return task
        # Second pass: keyword match — any significant word from title in input
        for task in tasks:
            title_words = [
                w for w in task["title"].lower().split()
                if len(w) >= 2
            ]
            if title_words and any(w in text_lower for w in title_words):
                return task
        return None
