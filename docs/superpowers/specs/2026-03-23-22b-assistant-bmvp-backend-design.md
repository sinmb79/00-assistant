# 22B Assistant BMVP Backend — Design Spec

**Date:** 2026-03-23
**Status:** Approved
**Scope:** Backend only — BaseAgent ABC + Pipeline Executor, Security Auditor (4-Gate), Administrative Agent (P1 wrapper)

---

## 1. Context

22B Assistant is a local-first AI assistant with a team of specialized domain agents. Each agent receives input, processes it, and reports a result — no inter-agent conversation. A Security Auditor monitors every pipeline at four gates.

P1 공문닥터 (`gongmun_doctor` package at `../DDC/gongmun-doctor`) is already implemented and must not be modified. The Administrative Agent wraps it via `pip install -e`.

---

## 2. Scope (This Spec)

| Component | Description |
|-----------|-------------|
| `BaseAgent` ABC | Abstract base class all domain agents implement |
| `PipelineExecutor` | Orchestrates the 4-gate + agent execution flow |
| `PipelineContext` | Immutable-ish dataclass carrying request→response state |
| `SecurityAuditor` | Owns Gate 1–4; each gate is a separate module |
| `AdministrativeAgent` | Wraps `gongmun_doctor.engine.correct_text` |
| `AgentRegistry` | Scans `agents/` for `manifest.json`, loads agents |

**Out of scope:** UI, LLM Router, Coordinator (next phase).

---

## 3. Architecture

```
User Request (text)
       │
       ▼
PipelineExecutor.run(request)
       │
       ├─► Gate 1 (SecurityAuditor): classify sensitivity → tag + route decision
       │
       ├─► AgentRegistry.route(request) → [AdministrativeAgent, ...]
       │
       ├─► agent.process(context) for each agent (sequential, BMVP)
       │
       ├─► Gate 2 (SecurityAuditor): PII masking before any external call
       │                             (BMVP: no external LLM → gate is a pass-through
       │                              that still logs the check)
       │
       ├─► Gate 3 (SecurityAuditor): verify result (citation check, PII leak check)
       │
       ├─► Gate 4 (SecurityAuditor): write audit log to encrypted SQLite
       │
       └─► return AgentResult
```

---

## 4. Components

### 4.0 Shared Data Types

```python
# pipeline/context.py
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class GateRecord:
    gate: int                  # 1 | 2 | 3 | 4
    passed: bool
    timestamp: datetime
    notes: str = ""            # human-readable summary (e.g. "PII detected: 전화번호")

@dataclass
class AgentResult:
    agent_id: str
    output: str                # formatted text shown to user
    citations: list[str]       # rule_ids cited (from CorrectionItem.rule_id)
    raw: list                  # list[CorrectionItem] from P1 — kept as list[Any] to avoid hard coupling
    verified: bool = True      # set False by Gate 3 if issues found
    error: str | None = None   # set if agent.process() raised an exception
```

### 4.1 PipelineContext

```python
@dataclass
class PipelineContext:
    request_id: str              # str(uuid4())
    input_text: str
    sensitivity: str = "public"  # initial value; Gate 1 overwrites
                                 # values: "public" | "internal" | "confidential" | "secret"
    gate_log: list[GateRecord] = field(default_factory=list)
    agent_results: list[AgentResult] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: datetime | None = None
```

### 4.2 BaseAgent ABC

```python
from __future__ import annotations   # enables Self on Python 3.12
from typing import Self

class BaseAgent(ABC):
    manifest: AgentManifest      # loaded from manifest.json at init

    @classmethod
    def from_manifest_dir(cls, path: Path) -> Self: ...

    @abstractmethod
    def process(self, context: PipelineContext) -> AgentResult: ...

    @property
    def triggers(self) -> list[str]: ...    # from manifest

    @property
    def agent_id(self) -> str: ...          # from manifest
```

`AgentManifest` is a dataclass parsed from `manifest.json`:
- `id`, `name`, `icon`, `version`
- `triggers: list[str]` — keywords for routing
- `llm_preference: str` — `"local"` | `"hybrid"` | `"external"`
- `sensitivity: str` — default sensitivity level for this agent's data
- `fallback: bool = False` — if `true`, Registry uses this agent when no trigger matches

### 4.3 SecurityAuditor (4 Gates)

**Gate 1 — Input Classifier** (`gate1_classifier.py`)
- Regex patterns for: 주민번호, 전화번호, 이메일, 계좌번호, 주소
- Does NOT depend on `gongmun_doctor` — standalone regex (no circular dependency)
- Returns: sensitivity tag + list of detected PII types
- Does NOT block — classifies and tags only

**Gate 2 — External Transmission Guard** (`gate2_masker.py`)
- Exact import: `from gongmun_doctor.llm.pii_masker import PIIMasker`
- BMVP: no external LLM → gate runs masking on `context.input_text` but does NOT block
- Stores masked text + mask map in `GateRecord.notes` for future de-masking
- Gate 2 runs AFTER agents in BMVP (no external LLM to intercept).
  In future phases (external LLM), Gate 2 will move BEFORE agent.process().
  This known asymmetry is acceptable in BMVP; documented here for future implementers.

**Gate 3 — Result Verifier** (`gate3_verifier.py`)
- (a) PII leak check: runs Gate 1 classifier on `AgentResult.output`; fail if PII detected
- (b) Citation check: verifies each `AgentResult.citations` rule_id appears in `AgentResult.raw`
  Note: `correct_text()` applies rules sequentially (cumulative correction);
  `raw` contains one CorrectionItem per rule that matched, in application order.
  Gate 3 checks that every citation in `citations` has a matching `CorrectionItem.rule_id`.
- Sets `AgentResult.verified = False` on failure; does NOT block pipeline

**Gate 4 — Audit Logger** (`gate4_logger.py`)
- SQLite database: `~/.22b-assistant/audit.db`
- Encryption strategy: serialize entire audit record as JSON → encrypt with Fernet → store as
  single `blob` column. Schema: `audit_log(id INTEGER PK, created_at TEXT, blob BLOB)`.
  Trade-off: no SQL queries on encrypted fields; acceptable for BMVP (read = decrypt all).
  Plaintext `created_at` retained for time-based filtering without decryption.
- Fernet key: stored at `~/.22b-assistant/.audit_key` (generated on first run)
- Decrypted record JSON structure:
  `{request_id, input_hash (SHA-256), sensitivity, agents_used, gate_log, result_summaries, external_sent: false}`
- Gate 4 failure (disk error, key error): logs to stderr, does NOT raise — pipeline never aborts

### 4.4 AdministrativeAgent

Exact imports used (P1 public API):
```python
from gongmun_doctor.engine import correct_text
from gongmun_doctor.rules.loader import load_rules
from gongmun_doctor.report.markdown import CorrectionItem  # for type hints only
```

Rule loading strategy: **use P1 bundled rules directly** (Option B).
`load_rules()` called with no argument → defaults to `gongmun_doctor/rules/` inside the installed package.
Rationale: avoids duplication; P1 rules are the authoritative source.
Future: pass custom `rules_dir` when administrative agent gains its own rule overrides.

```python
class AdministrativeAgent(BaseAgent):
    def process(self, context: PipelineContext) -> AgentResult:
        rules = load_rules()          # uses P1 bundled rules
        items = correct_text(context.input_text, rules)
        return AgentResult(
            agent_id=self.agent_id,
            output=self._format_output(items),
            citations=[item.rule_id for item in items],
            raw=items,
        )
```

- Text-only interface (BMVP chat). `correct_document()` (HWPX path) is NOT used.
- `python-hwpx` is still a transitive dependency (imported by `gongmun_doctor.engine` at module
  level). Install via `pip install -e ../DDC/gongmun-doctor` — `pyproject.toml` of P1 declares
  `python-hwpx` as a required dependency, so it is installed automatically.

### 4.5 AgentRegistry

- Scans `agents/*/manifest.json` at startup
- Instantiates one agent per manifest
- `route(text) -> list[BaseAgent]`: matches keywords from `triggers` (case-insensitive substring)
- Fallback: manifest with `"fallback": true` is used when no triggers match
  (AdministrativeAgent's manifest sets `"fallback": true` — Registry is decoupled from the class name)
- BMVP: only one agent active; sequential execution in `PipelineExecutor`

---

## 5. Data Flow (Sequence)

```
PipelineExecutor.run(text)
  → context = PipelineContext(request_id=uuid4(), input_text=text, ...)
  → gate1_result = auditor.gate1(context)      # classify
  → context.sensitivity = gate1_result.sensitivity
  → agents = registry.route(context.input_text)
  → for agent in agents:
      result = agent.process(context)
      context.agent_results.append(result)
  → gate2_result = auditor.gate2(context)      # mask (BMVP: pass-through)
  → gate3_result = auditor.gate3(context)      # verify
  → gate4_result = auditor.gate4(context)      # log
  → context.completed_at = now()
  → return context
```

---

## 6. Package Layout

```
22B-Assistant/
├── pyproject.toml           # depends on gongmun_doctor, cryptography
├── src/
│   └── assistant_22b/
│       ├── __init__.py
│       ├── agents/
│       │   ├── __init__.py
│       │   ├── base.py
│       │   ├── registry.py
│       │   └── administrative/
│       │       ├── manifest.json
│       │       ├── role_prompt.txt
│       │       ├── rules/           # L1/L2/L3 JSON (same format as P1)
│       │       └── agent.py
│       ├── pipeline/
│       │   ├── __init__.py
│       │   ├── context.py
│       │   └── executor.py
│       └── security/
│           ├── __init__.py
│           ├── auditor.py
│           ├── gate1_classifier.py
│           ├── gate2_masker.py
│           ├── gate3_verifier.py
│           └── gate4_logger.py
└── tests/
    ├── conftest.py
    ├── test_base_agent.py
    ├── test_pipeline_context.py
    ├── test_pipeline_executor.py
    ├── test_gate1_classifier.py
    ├── test_gate2_masker.py
    ├── test_gate3_verifier.py
    ├── test_gate4_logger.py
    ├── test_administrative_agent.py
    └── test_agent_registry.py
```

---

## 7. Dependencies

```toml
[project]
dependencies = [
    # P1 공문닥터 — local editable install.
    # Path is relative to pyproject.toml location; adjust for your setup.
    # gongmun_doctor pulls in python-hwpx as a required dep (auto-installed).
    "gongmun_doctor",            # installed via: pip install -e ../DDC/gongmun-doctor
    "cryptography>=42.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "pytest-cov"]
```

**Setup instructions (for README and contributors):**
```bash
# 1. Install P1 (editable)
pip install -e ../DDC/gongmun-doctor

# 2. Install 22B Assistant (editable)
pip install -e ".[dev]"
```

Cross-platform note: `file:///` URI in pyproject.toml is not portable across machines.
Use the two-step install above instead of embedding the path in `pyproject.toml`.
`python-hwpx` requires no native compilation on Windows (pure Python). Linux compatibility
should be verified before CI setup in a future phase.

---

## 8. Error Handling

- Gate 3 failure → `AgentResult.verified = False`, still returned (not blocked)
- Gate 4 failure → logged to stderr, does NOT abort pipeline (audit should never crash the user)
- Agent exception → `AgentResult.error = str(e)`, pipeline continues with empty output for that agent

---

## 9. Testing Strategy (TDD)

Test order mirrors build order:
1. `PipelineContext` — construction, GateRecord appending
2. `BaseAgent` — manifest loading, abstract enforcement
3. `Gate1Classifier` — PII detection patterns
4. `Gate2Masker` — masking + pass-through behavior
5. `Gate3Verifier` — citation check, PII leak detection
6. `Gate4Logger` — write/read encrypted audit log
7. `AdministrativeAgent` — correction output, citation list
8. `AgentRegistry` — manifest scan, keyword routing
9. `PipelineExecutor` — end-to-end flow

All tests use real code. Mocks only for file I/O in Gate 4 tests (temp dir).

---

## 10. GitHub Upload

Repository: `https://github.com/sinmb79/00-assistant.git`

Exclusions (`.gitignore`):
- `~/.22b-assistant/` (runtime data, audit DB, key file)
- `.env`, `*.key`, `*.pem`
- `__pycache__/`, `*.egg-info/`
- No API keys, no personal documents

README includes: project overview, setup instructions (pip install -e), architecture diagram, agent pack structure for contributors.
