# 22B Assistant — BMVP

A local-first AI assistant for Korean government officials, with a team of specialized domain agents.
Each agent wraps a domain engine. They don't chat — they work and report.

## Quick Start

```bash
# Launch the assistant (system tray + chat window)
python -m assistant_22b
# or, after pip install:
assistant-22b
```

Hotkey: **Ctrl+Shift+G** — toggles the chat window at any time.

## Architecture

```
User Input (chat window)
    │
    ▼
AssistantApp.process_message()
    │
    ▼
PipelineExecutor
    ├── Gate 1: Input classification (sensitivity tagging)
    ├── AgentRegistry → Agent.process()
    ├── Gate 2: PII masking (before any external LLM call)
    ├── Gate 3: Result verification (PII leak + citation check)
    └── Gate 4: Encrypted audit log (SQLite + Fernet)
    │
    ▼
ConversationStore (encrypted SQLite)
```

## Core Principles

- **Local-only by default** — all data stays on your PC
- **Agent = specialist** — each agent wraps a domain engine
- **Pipeline, not conversation** — agents work and report, no inter-agent chat
- **Security-first** — 4-Gate auditor monitors every request

## Setup

### Prerequisites

- Python 3.12+
- [공문닥터 (gongmun-doctor)](https://github.com/sinmb79/gongmun-doctor) — P1, must be installed separately

### Install

```bash
# 1. Clone and install P1 공문닥터
git clone <gongmun-doctor-repo-url>
pip install -e ./gongmun-doctor

# 2. Clone and install 22B Assistant
git clone https://github.com/sinmb79/00-assistant.git
cd 00-assistant
pip install -e ".[dev]"
```

### Run tests

```bash
pytest --tb=short -q
```

Expected output: 86 passed

## Adding a New Agent

Each domain agent needs only two files in `src/assistant_22b/agents/<domain>/`:

1. **`manifest.json`** — declares id, name, triggers, sensitivity, fallback flag
2. **`agent.py`** — a class extending `BaseAgent` with a `process()` method

The `AgentRegistry` discovers and loads it automatically on startup.

### Example `manifest.json`

```json
{
  "id": "legal",
  "name": "법무 에이전트",
  "icon": "⚖️",
  "version": "1.0.0",
  "triggers": ["법령", "조문", "규정", "법"],
  "llm_preference": "hybrid",
  "sensitivity": "internal",
  "fallback": false
}
```

### Example `agent.py`

```python
from pathlib import Path
from assistant_22b.agents.base import BaseAgent
from assistant_22b.pipeline.context import AgentResult, PipelineContext

class LegalAgent(BaseAgent):
    def process(self, context: PipelineContext) -> AgentResult:
        # wrap your domain engine here
        return AgentResult(
            agent_id=self.agent_id,
            output="법령 검색 결과...",
            citations=["법령ID-001"],
            raw=[],
        )
```

## Project Structure

```
src/assistant_22b/
├── __main__.py         # Entry point: python -m assistant_22b
├── config.py           # AssistantConfig + ConfigManager
├── pipeline/
│   ├── context.py      # GateRecord, AgentResult, PipelineContext
│   └── executor.py     # PipelineExecutor — orchestrates the full pipeline
├── security/
│   ├── auditor.py      # SecurityAuditor — owns Gate 1-4
│   ├── gate1_classifier.py  # PII detection → sensitivity tag
│   ├── gate2_masker.py      # PII masking (wraps P1 PIIMasker)
│   ├── gate3_verifier.py    # Output PII check + citation integrity
│   └── gate4_logger.py      # Fernet-encrypted SQLite audit log
├── agents/
│   ├── base.py         # BaseAgent ABC + AgentManifest
│   ├── registry.py     # Manifest-driven agent discovery and routing
│   └── administrative/ # 행정 에이전트 — wraps P1 공문닥터
├── llm/
│   └── router.py       # LLMRouter — none / external (CloudLLMRuntime) / local (llama-cpp)
├── storage/
│   └── conversations.py # ConversationStore — encrypted SQLite chat history
├── hwp/
│   └── adapter.py      # HwpAdapter — wraps P1 HwpController + HwpCorrectionBridge
└── ui/
    ├── app.py          # AssistantApp — wires everything together
    ├── chat_window.py  # Tkinter chat UI
    └── tray.py         # pystray system tray icon
```

## Security & Privacy

- No server. No cloud sync. All data stays on your PC.
- Audit logs are Fernet-encrypted at rest (`~/.22b-assistant/audit.db`).
- Input text is **never stored** — only its SHA-256 hash is logged.
- PII is detected and masked before any external LLM call (Gate 2).
- `~/.22b-assistant/` is outside this repository and must never be committed.

## Roadmap

| Phase | Status | Content |
|-------|--------|---------|
| BMVP | ✅ Done | Administrative Agent, 4-Gate Security, Pipeline, LLM Router, Chat UI, Tray |
| B | Planned | Legal Agent (규정레이다), Task Agent, Personalization |
| C | Planned | Local LLM (civil-ai-ko.gguf) integration |
| D | Planned | Civil Engineering, Architecture, Permit, Accounting, Audit agents |
| E | Planned | Domain pack marketplace, team sync |

## License

MIT
