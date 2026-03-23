# 22B Assistant BMVP Backend — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the BMVP backend for 22B Assistant: BaseAgent ABC + Pipeline Executor, 4-Gate Security Auditor, and Administrative Agent wrapping P1 공문닥터 — all test-driven.

**Architecture:** A `PipelineExecutor` drives a fixed sequence: Gate 1 (classify) → agent.process() → Gate 2 (mask) → Gate 3 (verify) → Gate 4 (log). Each gate is a standalone module owned by `SecurityAuditor`. `AdministrativeAgent` wraps P1's `correct_text()` without modifying P1. `AgentRegistry` loads agents from `manifest.json` files — adding a new agent requires only `agent.py + manifest.json`.

**Tech Stack:** Python 3.12, pytest 8+, cryptography (Fernet), sqlite3, gongmun_doctor (P1, local editable install)

**Spec:** `docs/superpowers/specs/2026-03-23-22b-assistant-bmvp-backend-design.md`

---

## File Map

```
22B-Assistant/
├── pyproject.toml
├── .gitignore
├── README.md
├── src/
│   └── assistant_22b/
│       ├── __init__.py
│       ├── pipeline/
│       │   ├── __init__.py
│       │   ├── context.py          # GateRecord, AgentResult, PipelineContext
│       │   └── executor.py         # PipelineExecutor
│       ├── agents/
│       │   ├── __init__.py
│       │   ├── base.py             # BaseAgent ABC, AgentManifest
│       │   ├── registry.py         # AgentRegistry
│       │   └── administrative/
│       │       ├── __init__.py
│       │       ├── manifest.json
│       │       ├── role_prompt.txt
│       │       └── agent.py        # AdministrativeAgent(BaseAgent)
│       └── security/
│           ├── __init__.py
│           ├── auditor.py          # SecurityAuditor (orchestrates gates)
│           ├── gate1_classifier.py # PII detection → sensitivity tag
│           ├── gate2_masker.py     # PIIMasker wrapper (pass-through in BMVP)
│           ├── gate3_verifier.py   # Output PII check + citation integrity
│           └── gate4_logger.py     # Fernet-encrypted SQLite audit log
└── tests/
    ├── conftest.py
    ├── test_pipeline_context.py
    ├── test_base_agent.py
    ├── test_gate1_classifier.py
    ├── test_gate2_masker.py
    ├── test_gate3_verifier.py
    ├── test_gate4_logger.py
    ├── test_security_auditor.py
    ├── test_administrative_agent.py
    ├── test_agent_registry.py
    └── test_pipeline_executor.py
```

---

## Task 1: Project Setup

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `src/assistant_22b/__init__.py`
- Create: `src/assistant_22b/pipeline/__init__.py`
- Create: `src/assistant_22b/agents/__init__.py`
- Create: `src/assistant_22b/agents/administrative/__init__.py`
- Create: `src/assistant_22b/security/__init__.py`
- Create: `tests/__init__.py` (empty — makes tests a package)

- [ ] **Step 1: Create pyproject.toml**

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.backends.legacy:build"

[project]
name = "assistant-22b"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "gongmun_doctor",      # install separately: pip install -e ../DDC/gongmun-doctor
    "cryptography>=42.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "pytest-cov>=5.0"]

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 2: Create .gitignore**

```gitignore
__pycache__/
*.py[cod]
*.egg-info/
.eggs/
dist/
build/
.env
*.key
*.pem
.venv/
venv/

# 22B Assistant runtime data (never commit)
# Note: ~/.22b-assistant/ lives in the home directory and is outside this repo.
# It cannot be excluded via .gitignore — never manually copy it into the repo.
.22b-assistant/
```

- [ ] **Step 3: Create all empty `__init__.py` files**

```bash
# Run from 22B-Assistant directory
touch src/assistant_22b/__init__.py
touch src/assistant_22b/pipeline/__init__.py
touch src/assistant_22b/agents/__init__.py
touch src/assistant_22b/agents/administrative/__init__.py
touch src/assistant_22b/security/__init__.py
touch tests/__init__.py
```

- [ ] **Step 4: Install P1 and this package**

```bash
# From 22B-Assistant directory
pip install -e ../DDC/gongmun-doctor
pip install -e ".[dev]"
```

Expected: both install without errors. Verify:
```bash
python -c "import gongmun_doctor; import assistant_22b; print('OK')"
```
Expected output: `OK`

- [ ] **Step 5: Initialize git and make first commit**

```bash
git init
git add pyproject.toml .gitignore src/ tests/
git commit -m "chore: project setup — 22B Assistant BMVP backend"
```

---

## Task 2: Shared Data Types (GateRecord, AgentResult, PipelineContext)

**Files:**
- Create: `src/assistant_22b/pipeline/context.py`
- Create: `tests/conftest.py`
- Create: `tests/test_pipeline_context.py`

- [ ] **Step 1: Write conftest.py (shared fixtures)**

```python
# tests/conftest.py
import json
import pytest
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime
from assistant_22b.pipeline.context import AgentResult, GateRecord, PipelineContext


@pytest.fixture
def clean_text():
    return "이 문서는 교정이 필요한 내용을 담고 있습니다."


@pytest.fixture
def pii_text():
    return "담당자 김철수(010-1234-5678)에게 연락 바랍니다."


@pytest.fixture
def rrn_text():
    return "주민등록번호: 850101-1234567"


@pytest.fixture
def sample_context(clean_text):
    return PipelineContext(
        request_id="test-req-001",
        input_text=clean_text,
    )


@pytest.fixture
def pii_context(pii_text):
    return PipelineContext(
        request_id="test-req-002",
        input_text=pii_text,
    )


@pytest.fixture
def sample_agent_result():
    return AgentResult(
        agent_id="test-agent",
        output="교정된 텍스트입니다.",
        citations=["L1-TEST-001"],
        raw=[],
    )


@pytest.fixture
def tmp_rules_dir(tmp_path):
    """Temp directory with a single known correction rule for deterministic tests."""
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    rule_data = {
        "meta": {"layer": "L1_test"},
        "rules": [
            {
                "id": "L1-TEST-001",
                "type": "exact_replace",
                "search": "테스트오류",
                "replace": "테스트정상",
                "desc": "테스트 규칙",
                "source": "테스트 출처",
            }
        ],
    }
    (rules_dir / "L1_test.json").write_text(
        json.dumps(rule_data, ensure_ascii=False), encoding="utf-8"
    )
    return rules_dir


# P1 CorrectionItem has fields: rule_id, rule_desc, rule_source, layer,
# original_text, corrected_text, paragraph_index.
# FakeCorrectionItem mirrors this for Gate 3 tests that inspect _format_output.
@dataclass
class FakeCorrectionItem:
    """Stub matching gongmun_doctor.report.markdown.CorrectionItem interface."""
    rule_id: str
    rule_desc: str = "테스트 규칙 설명"
    rule_source: str = "테스트 출처"
    layer: str = "L1_test"
    original_text: str = "오류"
    corrected_text: str = "정상"
    paragraph_index: int = 0


@pytest.fixture
def tmp_manifest_dir(tmp_path, tmp_rules_dir):
    """Temp agent directory with manifest.json and agent.py stub."""
    manifest = {
        "id": "test-agent",
        "name": "테스트 에이전트",
        "icon": "🧪",
        "version": "0.0.1",
        "triggers": ["테스트"],
        "llm_preference": "local",
        "sensitivity": "internal",
        "fallback": False,
    }
    (tmp_path / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
    )
    return tmp_path
```

- [ ] **Step 2: Write failing test for PipelineContext**

```python
# tests/test_pipeline_context.py
from datetime import datetime
from assistant_22b.pipeline.context import AgentResult, GateRecord, PipelineContext


def test_pipeline_context_default_sensitivity():
    ctx = PipelineContext(request_id="r1", input_text="hello")
    assert ctx.sensitivity == "public"


def test_pipeline_context_empty_gate_log_by_default():
    ctx = PipelineContext(request_id="r1", input_text="hello")
    assert ctx.gate_log == []


def test_pipeline_context_empty_agent_results_by_default():
    ctx = PipelineContext(request_id="r1", input_text="hello")
    assert ctx.agent_results == []


def test_pipeline_context_has_created_at():
    before = datetime.now()
    ctx = PipelineContext(request_id="r1", input_text="hello")
    after = datetime.now()
    assert before <= ctx.created_at <= after


def test_gate_record_stores_all_fields():
    ts = datetime.now()
    record = GateRecord(gate=1, passed=True, timestamp=ts, notes="test note")
    assert record.gate == 1
    assert record.passed is True
    assert record.timestamp == ts
    assert record.notes == "test note"


def test_gate_record_default_notes_empty():
    record = GateRecord(gate=2, passed=False, timestamp=datetime.now())
    assert record.notes == ""


def test_agent_result_default_verified_true():
    result = AgentResult(
        agent_id="a1", output="out", citations=[], raw=[]
    )
    assert result.verified is True


def test_agent_result_default_error_none():
    result = AgentResult(
        agent_id="a1", output="out", citations=[], raw=[]
    )
    assert result.error is None
```

- [ ] **Step 3: Run test — verify it fails**

```bash
pytest tests/test_pipeline_context.py -v
```
Expected: `ModuleNotFoundError: No module named 'assistant_22b.pipeline.context'`

- [ ] **Step 4: Implement `context.py`**

```python
# src/assistant_22b/pipeline/context.py
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class GateRecord:
    gate: int        # 1 | 2 | 3 | 4
    passed: bool
    timestamp: datetime
    notes: str = ""  # human-readable summary


@dataclass
class AgentResult:
    agent_id: str
    output: str                # formatted text shown to user
    citations: list[str]       # rule_ids cited
    raw: list                  # list[CorrectionItem] from P1, kept as list[Any]
    verified: bool = True      # set False by Gate 3 if issues found
    error: str | None = None   # set if agent.process() raised


@dataclass
class PipelineContext:
    request_id: str
    input_text: str
    sensitivity: str = "public"  # Gate 1 overwrites; public|internal|confidential|secret
    gate_log: list[GateRecord] = field(default_factory=list)
    agent_results: list[AgentResult] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: datetime | None = None
```

- [ ] **Step 5: Run test — verify it passes**

```bash
pytest tests/test_pipeline_context.py -v
```
Expected: all 8 tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/assistant_22b/pipeline/context.py tests/conftest.py tests/test_pipeline_context.py
git commit -m "feat: PipelineContext, GateRecord, AgentResult dataclasses"
```

---

## Task 3: BaseAgent ABC + AgentManifest

**Files:**
- Create: `src/assistant_22b/agents/base.py`
- Create: `tests/test_base_agent.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_base_agent.py
import json
import pytest
from pathlib import Path
from assistant_22b.agents.base import AgentManifest, BaseAgent
from assistant_22b.pipeline.context import AgentResult, PipelineContext


class ConcreteAgent(BaseAgent):
    """Minimal concrete implementation for testing the ABC."""
    def process(self, context: PipelineContext) -> AgentResult:
        return AgentResult(
            agent_id=self.agent_id,
            output="test output",
            citations=[],
            raw=[],
        )


def test_agent_manifest_loads_from_json(tmp_manifest_dir):
    manifest = AgentManifest.from_json(tmp_manifest_dir / "manifest.json")
    assert manifest.id == "test-agent"
    assert manifest.name == "테스트 에이전트"
    assert "테스트" in manifest.triggers
    assert manifest.fallback is False


def test_base_agent_exposes_agent_id(tmp_manifest_dir):
    agent = ConcreteAgent(tmp_manifest_dir)
    assert agent.agent_id == "test-agent"


def test_base_agent_exposes_triggers(tmp_manifest_dir):
    agent = ConcreteAgent(tmp_manifest_dir)
    assert "테스트" in agent.triggers


def test_base_agent_from_manifest_dir(tmp_manifest_dir):
    agent = ConcreteAgent.from_manifest_dir(tmp_manifest_dir)
    assert agent.agent_id == "test-agent"


def test_base_agent_cannot_instantiate_without_process():
    """BaseAgent is abstract — instantiating it directly must fail."""
    with pytest.raises(TypeError):
        BaseAgent(Path("."))  # type: ignore
```

- [ ] **Step 2: Run test — verify it fails**

```bash
pytest tests/test_base_agent.py -v
```
Expected: `ModuleNotFoundError: No module named 'assistant_22b.agents.base'`

- [ ] **Step 3: Implement `base.py`**

```python
# src/assistant_22b/agents/base.py
from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Self

from assistant_22b.pipeline.context import AgentResult, PipelineContext


@dataclass
class AgentManifest:
    id: str
    name: str
    icon: str
    version: str
    triggers: list[str]
    llm_preference: str  # "local" | "hybrid" | "external"
    sensitivity: str     # "public" | "internal" | "confidential" | "secret"
    fallback: bool = False

    @classmethod
    def from_json(cls, path: Path) -> AgentManifest:
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            id=data["id"],
            name=data["name"],
            icon=data.get("icon", ""),
            version=data["version"],
            triggers=data.get("triggers", []),
            llm_preference=data.get("llm_preference", "local"),
            sensitivity=data.get("sensitivity", "internal"),
            fallback=data.get("fallback", False),
        )


class BaseAgent(ABC):
    def __init__(self, manifest_dir: Path) -> None:
        self.manifest = AgentManifest.from_json(manifest_dir / "manifest.json")
        self._manifest_dir = manifest_dir

    @classmethod
    def from_manifest_dir(cls, path: Path) -> Self:
        return cls(path)

    @property
    def agent_id(self) -> str:
        return self.manifest.id

    @property
    def triggers(self) -> list[str]:
        return self.manifest.triggers

    @abstractmethod
    def process(self, context: PipelineContext) -> AgentResult: ...
```

- [ ] **Step 4: Run test — verify it passes**

```bash
pytest tests/test_base_agent.py -v
```
Expected: all 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/assistant_22b/agents/base.py tests/test_base_agent.py
git commit -m "feat: BaseAgent ABC and AgentManifest"
```

---

## Task 4: Gate 1 — Input Classifier

**Files:**
- Create: `src/assistant_22b/security/gate1_classifier.py`
- Create: `tests/test_gate1_classifier.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_gate1_classifier.py
from assistant_22b.security.gate1_classifier import Gate1Classifier


def test_clean_text_is_public():
    clf = Gate1Classifier()
    result = clf.classify("이 문서는 교정이 필요합니다.")
    assert result.sensitivity == "public"
    assert result.detected_pii == []


def test_phone_number_is_internal(pii_text):
    clf = Gate1Classifier()
    result = clf.classify(pii_text)
    assert result.sensitivity == "internal"
    assert "전화번호" in result.detected_pii


def test_email_is_internal():
    clf = Gate1Classifier()
    result = clf.classify("담당자 이메일: kim@example.go.kr")
    assert result.sensitivity == "internal"
    assert "이메일" in result.detected_pii


def test_rrn_is_confidential(rrn_text):
    clf = Gate1Classifier()
    result = clf.classify(rrn_text)
    assert result.sensitivity == "confidential"
    assert "주민번호" in result.detected_pii


def test_rrn_overrides_phone():
    """When both RRN and phone are present, confidential wins."""
    clf = Gate1Classifier()
    text = "주민번호: 850101-1234567, 전화: 010-9999-0000"
    result = clf.classify(text)
    assert result.sensitivity == "confidential"
    assert "주민번호" in result.detected_pii
    assert "전화번호" in result.detected_pii


def test_bank_account_is_internal():
    clf = Gate1Classifier()
    result = clf.classify("계좌번호: 110-123456-78901")
    assert result.sensitivity == "internal"
    assert "계좌번호" in result.detected_pii
```

- [ ] **Step 2: Run test — verify it fails**

```bash
pytest tests/test_gate1_classifier.py -v
```
Expected: `ModuleNotFoundError: No module named 'assistant_22b.security.gate1_classifier'`

- [ ] **Step 3: Implement `gate1_classifier.py`**

```python
# src/assistant_22b/security/gate1_classifier.py
from __future__ import annotations

import re
from dataclasses import dataclass, field

_SEVERITY_ORDER = {"public": 0, "internal": 1, "confidential": 2, "secret": 3}

_PATTERNS: list[tuple[str, str, re.Pattern]] = [
    # (sensitivity, pii_type, compiled_pattern)
    # Confidential — highest priority
    ("confidential", "주민번호", re.compile(r"\d{6}-[1-4]\d{6}")),
    # Internal
    ("internal", "전화번호", re.compile(r"\b01[016789]-\d{3,4}-\d{4}\b")),
    ("internal", "전화번호", re.compile(r"\b02-\d{3,4}-\d{4}\b")),
    ("internal", "전화번호", re.compile(r"\b0[3-9]\d-\d{3,4}-\d{4}\b")),
    ("internal", "이메일", re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")),
    ("internal", "계좌번호", re.compile(r"(?<!\d)\d{3,6}-\d{2,6}-\d{4,8}(?!\d)")),
]


@dataclass
class ClassificationResult:
    sensitivity: str
    detected_pii: list[str] = field(default_factory=list)


class Gate1Classifier:
    def classify(self, text: str) -> ClassificationResult:
        detected: list[str] = []
        max_sensitivity = "public"

        for sensitivity, pii_type, pattern in _PATTERNS:
            if pattern.search(text) and pii_type not in detected:
                detected.append(pii_type)
                if _SEVERITY_ORDER[sensitivity] > _SEVERITY_ORDER[max_sensitivity]:
                    max_sensitivity = sensitivity

        return ClassificationResult(sensitivity=max_sensitivity, detected_pii=detected)
```

- [ ] **Step 4: Run test — verify it passes**

```bash
pytest tests/test_gate1_classifier.py -v
```
Expected: all 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/assistant_22b/security/gate1_classifier.py tests/test_gate1_classifier.py
git commit -m "feat: Gate 1 — input PII classifier"
```

---

## Task 5: Gate 2 — PII Masker

**Files:**
- Create: `src/assistant_22b/security/gate2_masker.py`
- Create: `tests/test_gate2_masker.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_gate2_masker.py
from assistant_22b.security.gate2_masker import Gate2Masker


def test_masks_phone_number(pii_text):
    masker = Gate2Masker()
    result = masker.process(pii_text)
    assert "[전화번호]" in result.masked_text
    assert "010-1234-5678" not in result.masked_text
    assert result.was_masked is True


def test_clean_text_not_masked(clean_text):
    masker = Gate2Masker()
    result = masker.process(clean_text)
    assert result.masked_text == clean_text
    assert result.was_masked is False


def test_masked_text_returned_unchanged_when_no_pii():
    masker = Gate2Masker()
    text = "보조금 지급 현황을 보고드립니다."
    result = masker.process(text)
    assert result.was_masked is False


def test_masks_rrn(rrn_text):
    masker = Gate2Masker()
    result = masker.process(rrn_text)
    assert "[주민번호]" in result.masked_text
    assert result.was_masked is True
```

- [ ] **Step 2: Run test — verify it fails**

```bash
pytest tests/test_gate2_masker.py -v
```
Expected: `ModuleNotFoundError: No module named 'assistant_22b.security.gate2_masker'`

- [ ] **Step 3: Implement `gate2_masker.py`**

```python
# src/assistant_22b/security/gate2_masker.py
from __future__ import annotations

from dataclasses import dataclass

from gongmun_doctor.llm.pii_masker import PIIMasker


@dataclass
class MaskResult:
    masked_text: str
    was_masked: bool


class Gate2Masker:
    """Wraps P1's PIIMasker. In BMVP: runs masking but does not block.
    External LLM calls are not yet wired, so masked_text is computed
    but not transmitted anywhere — recorded for audit purposes only.
    """

    def __init__(self) -> None:
        self._masker = PIIMasker()

    def process(self, text: str) -> MaskResult:
        masked = self._masker.mask(text)
        return MaskResult(masked_text=masked, was_masked=(masked != text))
```

- [ ] **Step 4: Run test — verify it passes**

```bash
pytest tests/test_gate2_masker.py -v
```
Expected: all 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/assistant_22b/security/gate2_masker.py tests/test_gate2_masker.py
git commit -m "feat: Gate 2 — PII masker (wraps P1 PIIMasker)"
```

---

## Task 6: Gate 3 — Result Verifier

**Files:**
- Create: `src/assistant_22b/security/gate3_verifier.py`
- Create: `tests/test_gate3_verifier.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_gate3_verifier.py
import pytest
from dataclasses import dataclass
from assistant_22b.security.gate3_verifier import Gate3Verifier
from assistant_22b.pipeline.context import AgentResult


@dataclass
class FakeCorrectionItem:
    """Mimics gongmun_doctor.report.markdown.CorrectionItem for testing."""
    rule_id: str
    rule_desc: str = "테스트 규칙 설명"
    rule_source: str = "테스트 출처"
    layer: str = "L1_test"
    original_text: str = "오류"
    corrected_text: str = "정상"
    paragraph_index: int = 0


def test_clean_result_passes_verification():
    verifier = Gate3Verifier()
    result = AgentResult(
        agent_id="a1",
        output="이 문서는 교정이 완료되었습니다.",
        citations=["L1-001"],
        raw=[FakeCorrectionItem(rule_id="L1-001")],
    )
    issues = verifier.verify(result)
    assert issues == []


def test_pii_in_output_is_flagged():
    verifier = Gate3Verifier()
    result = AgentResult(
        agent_id="a1",
        output="담당자 전화: 010-9999-0000",
        citations=[],
        raw=[],
    )
    issues = verifier.verify(result)
    assert any("PII" in issue for issue in issues)


def test_missing_citation_is_flagged():
    verifier = Gate3Verifier()
    result = AgentResult(
        agent_id="a1",
        output="교정 완료",
        citations=["L1-GHOST"],  # not in raw
        raw=[FakeCorrectionItem(rule_id="L1-001")],
    )
    issues = verifier.verify(result)
    assert any("L1-GHOST" in issue for issue in issues)


def test_all_citations_matched_passes():
    verifier = Gate3Verifier()
    result = AgentResult(
        agent_id="a1",
        output="교정 완료",
        citations=["L1-001", "L2-003"],
        raw=[
            FakeCorrectionItem(rule_id="L1-001"),
            FakeCorrectionItem(rule_id="L2-003"),
        ],
    )
    issues = verifier.verify(result)
    assert issues == []


def test_empty_citations_and_raw_passes():
    verifier = Gate3Verifier()
    result = AgentResult(
        agent_id="a1",
        output="교정 사항 없음",
        citations=[],
        raw=[],
    )
    issues = verifier.verify(result)
    assert issues == []
```

- [ ] **Step 2: Run test — verify it fails**

```bash
pytest tests/test_gate3_verifier.py -v
```
Expected: `ModuleNotFoundError: No module named 'assistant_22b.security.gate3_verifier'`

- [ ] **Step 3: Implement `gate3_verifier.py`**

```python
# src/assistant_22b/security/gate3_verifier.py
from __future__ import annotations

from assistant_22b.pipeline.context import AgentResult
from assistant_22b.security.gate1_classifier import Gate1Classifier


class Gate3Verifier:
    """Verifies agent results:
    (a) output does not leak PII
    (b) every cited rule_id exists in the raw CorrectionItems
    """

    def __init__(self) -> None:
        self._classifier = Gate1Classifier()

    def verify(self, result: AgentResult) -> list[str]:
        """Returns list of issue strings. Empty list = passed."""
        issues: list[str] = []

        # (a) PII leak check
        pii_check = self._classifier.classify(result.output)
        if pii_check.detected_pii:
            issues.append(f"PII in output: {pii_check.detected_pii}")

        # (b) Citation integrity
        raw_rule_ids = {
            getattr(item, "rule_id", None) for item in result.raw
        } - {None}
        for citation in result.citations:
            if citation not in raw_rule_ids:
                issues.append(f"Citation '{citation}' not found in raw results")

        return issues
```

- [ ] **Step 4: Run test — verify it passes**

```bash
pytest tests/test_gate3_verifier.py -v
```
Expected: all 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/assistant_22b/security/gate3_verifier.py tests/test_gate3_verifier.py
git commit -m "feat: Gate 3 — result verifier (PII leak + citation integrity)"
```

---

## Task 7: Gate 4 — Audit Logger

**Files:**
- Create: `src/assistant_22b/security/gate4_logger.py`
- Create: `tests/test_gate4_logger.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_gate4_logger.py
import hashlib
import json
import sqlite3
from pathlib import Path
from assistant_22b.security.gate4_logger import Gate4Logger
from assistant_22b.pipeline.context import AgentResult, GateRecord, PipelineContext
from datetime import datetime


def make_context(tmp_path: Path) -> PipelineContext:
    ctx = PipelineContext(request_id="test-req-audit", input_text="테스트 공문")
    ctx.sensitivity = "internal"
    ctx.gate_log.append(GateRecord(gate=1, passed=True, timestamp=datetime.now()))
    ctx.agent_results.append(
        AgentResult(agent_id="administrative", output="교정 완료", citations=[], raw=[])
    )
    return ctx


def test_gate4_creates_db_file(tmp_path):
    db = tmp_path / "audit.db"
    key = tmp_path / ".audit_key"
    logger = Gate4Logger(db_path=db, key_path=key)
    ctx = make_context(tmp_path)
    logger.log(ctx)
    assert db.exists()


def test_gate4_creates_key_file(tmp_path):
    db = tmp_path / "audit.db"
    key = tmp_path / ".audit_key"
    logger = Gate4Logger(db_path=db, key_path=key)
    ctx = make_context(tmp_path)
    logger.log(ctx)
    assert key.exists()


def test_gate4_log_is_readable(tmp_path):
    db = tmp_path / "audit.db"
    key = tmp_path / ".audit_key"
    logger = Gate4Logger(db_path=db, key_path=key)
    ctx = make_context(tmp_path)
    logger.log(ctx)
    records = logger.read_all()
    assert len(records) == 1
    assert records[0]["request_id"] == "test-req-audit"


def test_gate4_input_is_hashed_not_stored_raw(tmp_path):
    db = tmp_path / "audit.db"
    key = tmp_path / ".audit_key"
    logger = Gate4Logger(db_path=db, key_path=key)
    ctx = make_context(tmp_path)
    logger.log(ctx)
    records = logger.read_all()
    expected_hash = hashlib.sha256("테스트 공문".encode()).hexdigest()
    assert records[0]["input_hash"] == expected_hash
    assert "테스트 공문" not in json.dumps(records[0])


def test_gate4_failure_does_not_raise(tmp_path, monkeypatch):
    """Gate 4 must not crash the pipeline even if sqlite3.connect fails."""
    import sqlite3 as _sqlite3
    db = tmp_path / "audit.db"
    key = tmp_path / ".audit_key"
    logger = Gate4Logger(db_path=db, key_path=key)
    ctx = make_context(tmp_path)

    # Force every sqlite3.connect call to raise OperationalError
    def broken_connect(*args, **kwargs):
        raise _sqlite3.OperationalError("simulated disk failure")

    monkeypatch.setattr("assistant_22b.security.gate4_logger.sqlite3.connect", broken_connect)
    # Must not raise despite the forced failure
    logger.log(ctx)  # should silently swallow and print to stderr
```

- [ ] **Step 2: Run test — verify it fails**

```bash
pytest tests/test_gate4_logger.py -v
```
Expected: `ModuleNotFoundError: No module named 'assistant_22b.security.gate4_logger'`

- [ ] **Step 3: Implement `gate4_logger.py`**

```python
# src/assistant_22b/security/gate4_logger.py
from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

from cryptography.fernet import Fernet

from assistant_22b.pipeline.context import PipelineContext


class Gate4Logger:
    """Appends encrypted audit records to a local SQLite database.

    Schema: audit_log(id INTEGER PK, created_at TEXT, blob BLOB)
    Each blob is a Fernet-encrypted JSON payload containing the full audit record.
    created_at is stored as plaintext for time-based filtering.
    """

    def __init__(self, db_path: Path, key_path: Path) -> None:
        self._db_path = db_path
        self._key_path = key_path
        self._fernet = self._load_or_create_key()
        self._init_db()

    def _load_or_create_key(self) -> Fernet:
        if self._key_path.exists():
            key = self._key_path.read_bytes()
        else:
            key = Fernet.generate_key()
            self._key_path.parent.mkdir(parents=True, exist_ok=True)
            self._key_path.write_bytes(key)
        return Fernet(key)

    def _init_db(self) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_log (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT    NOT NULL,
                    blob       BLOB    NOT NULL
                )
                """
            )

    def log(self, context: PipelineContext) -> None:
        """Encrypt and persist the audit record. Never raises."""
        try:
            record = {
                "request_id": context.request_id,
                "input_hash": hashlib.sha256(
                    context.input_text.encode("utf-8")
                ).hexdigest(),
                "sensitivity": context.sensitivity,
                "agents_used": [r.agent_id for r in context.agent_results],
                "gate_log": [
                    {
                        "gate": g.gate,
                        "passed": g.passed,
                        "timestamp": g.timestamp.isoformat(),
                        "notes": g.notes,
                    }
                    for g in context.gate_log
                ],
                "result_summaries": [
                    {
                        "agent_id": r.agent_id,
                        "citations": r.citations,
                        "verified": r.verified,
                        "error": r.error,
                    }
                    for r in context.agent_results
                ],
                "external_sent": False,
            }
            payload = json.dumps(record, ensure_ascii=False, default=str).encode("utf-8")
            encrypted = self._fernet.encrypt(payload)
            now = datetime.now().isoformat()
            with sqlite3.connect(self._db_path) as conn:
                conn.execute(
                    "INSERT INTO audit_log (created_at, blob) VALUES (?, ?)",
                    (now, encrypted),
                )
        except Exception as exc:
            print(f"[Gate4] Audit log failed: {exc}", file=sys.stderr)

    def read_all(self) -> list[dict]:
        """Decrypt and return all audit records. For testing and audit review."""
        results = []
        with sqlite3.connect(self._db_path) as conn:
            rows = conn.execute(
                "SELECT blob FROM audit_log ORDER BY id"
            ).fetchall()
        for (blob,) in rows:
            try:
                payload = self._fernet.decrypt(blob)
                results.append(json.loads(payload.decode("utf-8")))
            except Exception:
                results.append({"error": "decryption_failed"})
        return results
```

- [ ] **Step 4: Run test — verify it passes**

```bash
pytest tests/test_gate4_logger.py -v
```
Expected: all 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/assistant_22b/security/gate4_logger.py tests/test_gate4_logger.py
git commit -m "feat: Gate 4 — Fernet-encrypted SQLite audit logger"
```

---

## Task 8: SecurityAuditor (orchestrates all gates)

**Files:**
- Create: `src/assistant_22b/security/auditor.py`
- Create: `tests/test_security_auditor.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_security_auditor.py
from pathlib import Path
from assistant_22b.security.auditor import SecurityAuditor
from assistant_22b.pipeline.context import AgentResult, PipelineContext


def make_auditor(tmp_path: Path) -> SecurityAuditor:
    return SecurityAuditor(
        db_path=tmp_path / "audit.db",
        key_path=tmp_path / ".audit_key",
    )


def test_gate1_sets_sensitivity_on_context(pii_context, tmp_path):
    auditor = make_auditor(tmp_path)
    auditor.gate1(pii_context)
    assert pii_context.sensitivity == "internal"


def test_gate1_appends_to_gate_log(sample_context, tmp_path):
    auditor = make_auditor(tmp_path)
    auditor.gate1(sample_context)
    assert len(sample_context.gate_log) == 1
    assert sample_context.gate_log[0].gate == 1


def test_gate2_appends_gate_record(sample_context, tmp_path):
    auditor = make_auditor(tmp_path)
    auditor.gate2(sample_context)
    assert any(g.gate == 2 for g in sample_context.gate_log)


def test_gate3_marks_result_unverified_on_pii(tmp_path):
    auditor = make_auditor(tmp_path)
    ctx = PipelineContext(request_id="x", input_text="ok")
    ctx.agent_results.append(
        AgentResult(
            agent_id="a",
            output="전화: 010-9999-0000",  # PII in output
            citations=[],
            raw=[],
        )
    )
    auditor.gate3(ctx)
    assert ctx.agent_results[0].verified is False


def test_gate3_passes_clean_result(tmp_path):
    """Agent result with no PII in output and no citations passes Gate 3."""
    auditor = make_auditor(tmp_path)
    ctx = PipelineContext(request_id="y", input_text="clean")
    clean_result = AgentResult(
        agent_id="b", output="교정 사항이 없습니다.", citations=[], raw=[]
    )
    ctx.agent_results.append(clean_result)
    auditor.gate3(ctx)
    assert ctx.agent_results[0].verified is True


def test_gate4_writes_audit_log(sample_context, tmp_path):
    auditor = make_auditor(tmp_path)
    auditor.gate4(sample_context)
    db_path = tmp_path / "audit.db"
    assert db_path.exists()
```

- [ ] **Step 2: Run test — verify it fails**

```bash
pytest tests/test_security_auditor.py -v
```
Expected: `ModuleNotFoundError: No module named 'assistant_22b.security.auditor'`

- [ ] **Step 3: Implement `auditor.py`**

```python
# src/assistant_22b/security/auditor.py
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

from assistant_22b.pipeline.context import GateRecord, PipelineContext
from assistant_22b.security.gate1_classifier import Gate1Classifier
from assistant_22b.security.gate2_masker import Gate2Masker
from assistant_22b.security.gate3_verifier import Gate3Verifier
from assistant_22b.security.gate4_logger import Gate4Logger


class SecurityAuditor:
    def __init__(self, db_path: Path, key_path: Path) -> None:
        self._classifier = Gate1Classifier()
        self._masker = Gate2Masker()
        self._verifier = Gate3Verifier()
        self._logger = Gate4Logger(db_path=db_path, key_path=key_path)

    def gate1(self, context: PipelineContext) -> GateRecord:
        result = self._classifier.classify(context.input_text)
        context.sensitivity = result.sensitivity
        record = GateRecord(
            gate=1,
            passed=True,
            timestamp=datetime.now(),
            notes=f"sensitivity={result.sensitivity}; pii={result.detected_pii}",
        )
        context.gate_log.append(record)
        return record

    def gate2(self, context: PipelineContext) -> GateRecord:
        result = self._masker.process(context.input_text)
        record = GateRecord(
            gate=2,
            passed=True,
            timestamp=datetime.now(),
            notes=f"was_masked={result.was_masked}; external_sent=False",
        )
        context.gate_log.append(record)
        return record

    def gate3(self, context: PipelineContext) -> GateRecord:
        all_issues: list[str] = []
        for agent_result in context.agent_results:
            issues = self._verifier.verify(agent_result)
            if issues:
                agent_result.verified = False
                all_issues.extend(issues)
        passed = len(all_issues) == 0
        record = GateRecord(
            gate=3,
            passed=passed,
            timestamp=datetime.now(),
            notes="; ".join(all_issues) if all_issues else "ok",
        )
        context.gate_log.append(record)
        return record

    def gate4(self, context: PipelineContext) -> GateRecord:
        """Logs audit record. Never raises — pipeline safety gate."""
        try:
            self._logger.log(context)
            record = GateRecord(
                gate=4,
                passed=True,
                timestamp=datetime.now(),
                notes="logged",
            )
        except Exception as exc:  # pragma: no cover
            print(f"[SecurityAuditor] Gate 4 failed: {exc}", file=sys.stderr)
            record = GateRecord(
                gate=4,
                passed=False,
                timestamp=datetime.now(),
                notes=str(exc),
            )
        context.gate_log.append(record)
        return record
```

- [ ] **Step 4: Run test — verify it passes**

```bash
pytest tests/test_security_auditor.py -v
```
Expected: all 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/assistant_22b/security/auditor.py tests/test_security_auditor.py
git commit -m "feat: SecurityAuditor orchestrating Gates 1-4"
```

---

## Task 9: Administrative Agent (P1 wrapper)

**Files:**
- Create: `src/assistant_22b/agents/administrative/manifest.json`
- Create: `src/assistant_22b/agents/administrative/role_prompt.txt`
- Create: `src/assistant_22b/agents/administrative/agent.py`
- Create: `tests/test_administrative_agent.py`

- [ ] **Step 1: Create manifest.json and role_prompt.txt**

```json
// src/assistant_22b/agents/administrative/manifest.json
{
  "id": "administrative",
  "name": "행정 에이전트",
  "icon": "📝",
  "version": "1.0.0",
  "triggers": ["공문", "교정", "공문서", "기안", "보고서", "행정", "문서", "맞춤법", "띄어쓰기"],
  "llm_preference": "local",
  "sensitivity": "internal",
  "fallback": true
}
```

```text
// src/assistant_22b/agents/administrative/role_prompt.txt
당신은 대한민국 공공기관 공문서 교정 전문가입니다.
행정업무운영편람, 공문서 작성 요령, 한글 맞춤법에 근거하여 문서를 교정합니다.
모든 교정에는 반드시 근거 규칙 ID와 출처를 명시합니다.
```

- [ ] **Step 2: Write failing test**

```python
# tests/test_administrative_agent.py
from pathlib import Path
from assistant_22b.agents.administrative.agent import AdministrativeAgent
from assistant_22b.pipeline.context import AgentResult, PipelineContext


ADMIN_MANIFEST_DIR = (
    Path(__file__).parent.parent
    / "src" / "assistant_22b" / "agents" / "administrative"
)


def test_administrative_agent_returns_agent_result(sample_context):
    agent = AdministrativeAgent(ADMIN_MANIFEST_DIR)
    result = agent.process(sample_context)
    assert isinstance(result, AgentResult)
    assert result.agent_id == "administrative"


def test_administrative_agent_citations_match_raw(sample_context):
    agent = AdministrativeAgent(ADMIN_MANIFEST_DIR)
    result = agent.process(sample_context)
    raw_rule_ids = [getattr(item, "rule_id", None) for item in result.raw]
    assert result.citations == raw_rule_ids


def test_administrative_agent_with_known_rule(tmp_rules_dir):
    """Uses a controlled tmp rule: 테스트오류 → 테스트정상."""
    manifest_dir = Path(__file__).parent.parent / "src/assistant_22b/agents/administrative"
    agent = AdministrativeAgent(manifest_dir, rules_dir=tmp_rules_dir)
    ctx = PipelineContext(request_id="r-rule", input_text="이 문서에 테스트오류가 있습니다.")
    result = agent.process(ctx)
    assert "L1-TEST-001" in result.citations
    assert "테스트정상" in result.output


def test_administrative_agent_clean_text_has_empty_citations(tmp_rules_dir):
    manifest_dir = Path(__file__).parent.parent / "src/assistant_22b/agents/administrative"
    agent = AdministrativeAgent(manifest_dir, rules_dir=tmp_rules_dir)
    ctx = PipelineContext(request_id="r-clean", input_text="오류가 없는 문장입니다.")
    result = agent.process(ctx)
    assert result.citations == []
    assert result.raw == []
```

- [ ] **Step 3: Run test — verify it fails**

```bash
pytest tests/test_administrative_agent.py -v
```
Expected: `ModuleNotFoundError: No module named 'assistant_22b.agents.administrative.agent'`

- [ ] **Step 4: Implement `agent.py`**

```python
# src/assistant_22b/agents/administrative/agent.py
from __future__ import annotations

from pathlib import Path

from gongmun_doctor.engine import correct_text
from gongmun_doctor.rules.loader import load_rules

from assistant_22b.agents.base import BaseAgent
from assistant_22b.pipeline.context import AgentResult, PipelineContext


class AdministrativeAgent(BaseAgent):
    """Wraps P1 공문닥터 engine as a BaseAgent.

    rules_dir=None  → use P1 bundled rules (L1/L2/L3, default)
    rules_dir=Path  → use custom rules directory (for testing or overrides)
    """

    def __init__(self, manifest_dir: Path, rules_dir: Path | None = None) -> None:
        super().__init__(manifest_dir)
        self._rules_dir = rules_dir

    def process(self, context: PipelineContext) -> AgentResult:
        rules = load_rules(self._rules_dir)
        items = correct_text(context.input_text, rules)
        return AgentResult(
            agent_id=self.agent_id,
            output=self._format_output(items),
            citations=[item.rule_id for item in items],
            raw=items,
        )

    def _format_output(self, items: list) -> str:
        if not items:
            return "교정 사항이 없습니다."
        lines = ["## 교정 결과\n"]
        for item in items:
            lines.append(
                f"- **[{item.rule_id}]** {item.rule_desc}\n"
                f"  - 원문: `{item.original_text}`\n"
                f"  - 교정: `{item.corrected_text}`\n"
                f"  - 근거: {item.rule_source}"
            )
        return "\n".join(lines)
```

- [ ] **Step 5: Run test — verify it passes**

```bash
pytest tests/test_administrative_agent.py -v
```
Expected: all 4 tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/assistant_22b/agents/administrative/ tests/test_administrative_agent.py
git commit -m "feat: AdministrativeAgent — wraps P1 공문닥터 engine"
```

---

## Task 10: Agent Registry

**Files:**
- Create: `src/assistant_22b/agents/registry.py`
- Create: `tests/test_agent_registry.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_agent_registry.py
import json
from pathlib import Path
from assistant_22b.agents.registry import AgentRegistry


AGENTS_DIR = (
    Path(__file__).parent.parent / "src" / "assistant_22b" / "agents"
)


def test_registry_loads_administrative_agent():
    registry = AgentRegistry(AGENTS_DIR)
    agents = registry.all_agents()
    ids = [a.agent_id for a in agents]
    assert "administrative" in ids


def test_registry_routes_by_keyword():
    registry = AgentRegistry(AGENTS_DIR)
    agents = registry.route("이 공문을 교정해줘")
    ids = [a.agent_id for a in agents]
    assert "administrative" in ids


def test_registry_falls_back_to_fallback_agent():
    """Unknown domain text → fallback agent (administrative, fallback=true)."""
    registry = AgentRegistry(AGENTS_DIR)
    agents = registry.route("오늘 날씨가 좋네요")  # no trigger match
    assert len(agents) == 1
    assert agents[0].agent_id == "administrative"


def test_registry_keyword_match_is_case_insensitive():
    registry = AgentRegistry(AGENTS_DIR)
    agents = registry.route("문서 교정 부탁합니다")
    ids = [a.agent_id for a in agents]
    assert "administrative" in ids


def test_registry_no_duplicate_agents_for_multiple_trigger_matches():
    registry = AgentRegistry(AGENTS_DIR)
    # "공문서 맞춤법" contains TWO triggers for administrative → still one result
    agents = registry.route("공문서 맞춤법 교정")
    admin_hits = [a for a in agents if a.agent_id == "administrative"]
    assert len(admin_hits) == 1
```

- [ ] **Step 2: Run test — verify it fails**

```bash
pytest tests/test_agent_registry.py -v
```
Expected: `ModuleNotFoundError: No module named 'assistant_22b.agents.registry'`

- [ ] **Step 3: Implement `registry.py`**

```python
# src/assistant_22b/agents/registry.py
from __future__ import annotations

import importlib
import json
from pathlib import Path

from assistant_22b.agents.base import AgentManifest, BaseAgent


class AgentRegistry:
    """Scans agents/*/manifest.json, loads agents, routes requests by trigger keyword."""

    def __init__(self, agents_dir: Path) -> None:
        self._agents: list[BaseAgent] = []
        self._fallback: BaseAgent | None = None
        self._load(agents_dir)

    def _load(self, agents_dir: Path) -> None:
        for manifest_path in sorted(agents_dir.glob("*/manifest.json")):
            agent_dir = manifest_path.parent
            subpackage = agent_dir.name  # e.g., "administrative"

            try:
                module = importlib.import_module(
                    f"assistant_22b.agents.{subpackage}.agent"
                )
            except ImportError:
                continue

            # Find the first BaseAgent subclass in the module
            for name in dir(module):
                obj = getattr(module, name)
                if (
                    isinstance(obj, type)
                    and issubclass(obj, BaseAgent)
                    and obj is not BaseAgent
                ):
                    agent = obj.from_manifest_dir(agent_dir)
                    self._agents.append(agent)
                    if agent.manifest.fallback:
                        self._fallback = agent
                    break

    def all_agents(self) -> list[BaseAgent]:
        return list(self._agents)

    def route(self, text: str) -> list[BaseAgent]:
        """Return agents whose triggers appear in text. Deduplicated, preserves order."""
        text_lower = text.lower()
        seen: set[str] = set()
        matched: list[BaseAgent] = []

        for agent in self._agents:
            if agent.agent_id in seen:
                continue
            if any(trigger.lower() in text_lower for trigger in agent.triggers):
                matched.append(agent)
                seen.add(agent.agent_id)

        if not matched and self._fallback:
            return [self._fallback]
        return matched
```

- [ ] **Step 4: Run test — verify it passes**

```bash
pytest tests/test_agent_registry.py -v
```
Expected: all 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/assistant_22b/agents/registry.py tests/test_agent_registry.py
git commit -m "feat: AgentRegistry — manifest-driven agent loading and routing"
```

---

## Task 11: Pipeline Executor (end-to-end)

**Files:**
- Create: `src/assistant_22b/pipeline/executor.py`
- Create: `tests/test_pipeline_executor.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_pipeline_executor.py
from pathlib import Path
from assistant_22b.pipeline.executor import PipelineExecutor
from assistant_22b.security.auditor import SecurityAuditor
from assistant_22b.agents.registry import AgentRegistry


AGENTS_DIR = (
    Path(__file__).parent.parent / "src" / "assistant_22b" / "agents"
)


def make_executor(tmp_path: Path) -> PipelineExecutor:
    auditor = SecurityAuditor(
        db_path=tmp_path / "audit.db",
        key_path=tmp_path / ".audit_key",
    )
    registry = AgentRegistry(AGENTS_DIR)
    return PipelineExecutor(auditor=auditor, registry=registry)


def test_pipeline_returns_context(tmp_path):
    executor = make_executor(tmp_path)
    ctx = executor.run("이 공문을 교정해줘")
    assert ctx.request_id is not None
    assert ctx.completed_at is not None


def test_pipeline_has_all_four_gate_records(tmp_path):
    executor = make_executor(tmp_path)
    ctx = executor.run("공문서 교정 요청")
    gates = [g.gate for g in ctx.gate_log]
    assert 1 in gates
    assert 2 in gates
    assert 3 in gates
    assert 4 in gates


def test_pipeline_assigns_sensitivity(tmp_path):
    executor = make_executor(tmp_path)
    ctx = executor.run("보조금 지급 현황 보고서를 교정해줘")
    assert ctx.sensitivity in ("public", "internal", "confidential", "secret")


def test_pipeline_with_pii_text_sets_internal_or_higher(tmp_path, pii_text):
    executor = make_executor(tmp_path)
    ctx = executor.run(pii_text)
    assert ctx.sensitivity in ("internal", "confidential", "secret")


def test_pipeline_produces_agent_result(tmp_path):
    executor = make_executor(tmp_path)
    ctx = executor.run("공문 교정해줘")
    assert len(ctx.agent_results) >= 1
    result = ctx.agent_results[0]
    assert result.agent_id == "administrative"
    assert isinstance(result.output, str)


def test_pipeline_agent_exception_does_not_crash(tmp_path, monkeypatch):
    """If an agent raises, pipeline still completes and records the error."""
    from assistant_22b.agents.administrative.agent import AdministrativeAgent

    def boom(self, ctx):
        raise RuntimeError("simulated agent crash")

    monkeypatch.setattr(AdministrativeAgent, "process", boom)
    executor = make_executor(tmp_path)
    ctx = executor.run("공문 교정")
    assert ctx.completed_at is not None
    error_results = [r for r in ctx.agent_results if r.error is not None]
    assert len(error_results) == 1
```

- [ ] **Step 2: Run test — verify it fails**

```bash
pytest tests/test_pipeline_executor.py -v
```
Expected: `ModuleNotFoundError: No module named 'assistant_22b.pipeline.executor'`

- [ ] **Step 3: Implement `executor.py`**

```python
# src/assistant_22b/pipeline/executor.py
from __future__ import annotations

import uuid
from datetime import datetime

from assistant_22b.agents.registry import AgentRegistry
from assistant_22b.pipeline.context import AgentResult, PipelineContext
from assistant_22b.security.auditor import SecurityAuditor


class PipelineExecutor:
    """Orchestrates the full request→response pipeline.

    Sequence: Gate1 → route → agent.process (×N) → Gate2 → Gate3 → Gate4
    All gates always run. Agent exceptions are caught and recorded.
    """

    def __init__(self, auditor: SecurityAuditor, registry: AgentRegistry) -> None:
        self._auditor = auditor
        self._registry = registry

    def run(self, text: str) -> PipelineContext:
        context = PipelineContext(
            request_id=str(uuid.uuid4()),
            input_text=text,
        )

        # Gate 1 — classify sensitivity
        self._auditor.gate1(context)

        # Route to agents
        agents = self._registry.route(text)

        # Execute agents (sequential in BMVP)
        for agent in agents:
            try:
                result = agent.process(context)
            except Exception as exc:
                result = AgentResult(
                    agent_id=agent.agent_id,
                    output="",
                    citations=[],
                    raw=[],
                    error=str(exc),
                )
            context.agent_results.append(result)

        # Gate 2 — PII mask check (BMVP: pass-through, no external LLM)
        self._auditor.gate2(context)

        # Gate 3 — verify results
        self._auditor.gate3(context)

        # Gate 4 — audit log
        self._auditor.gate4(context)

        context.completed_at = datetime.now()
        return context
```

- [ ] **Step 4: Run test — verify it passes**

```bash
pytest tests/test_pipeline_executor.py -v
```
Expected: all 6 tests PASS

- [ ] **Step 5: Run full test suite — all green**

```bash
pytest --tb=short -q
```
Expected: all tests PASS, no warnings

- [ ] **Step 6: Commit**

```bash
git add src/assistant_22b/pipeline/executor.py tests/test_pipeline_executor.py
git commit -m "feat: PipelineExecutor — end-to-end pipeline orchestration"
```

---

## Task 12: README + GitHub Upload

**Files:**
- Create: `README.md`

- [ ] **Step 1: Write README.md**

```markdown
# 22B Assistant — BMVP Backend

A local-first AI assistant backend with a team of specialized agents.
Each agent is an expert in a specific domain. They don't chat — they work and report.

## Architecture

```
User Request
    │
    ▼
PipelineExecutor
    ├── Gate 1: Input classification (sensitivity tagging)
    ├── AgentRegistry → Agent.process()
    ├── Gate 2: PII masking (before any external LLM call)
    ├── Gate 3: Result verification (PII leak + citation check)
    └── Gate 4: Encrypted audit log (SQLite)
```

## Core Principles

- **Local-only by default** — all data stays on your PC
- **Agent = specialist** — each agent wraps a domain engine
- **Pipeline, not conversation** — agents work and report, no inter-agent chat
- **Security-first** — 4-Gate auditor monitors every request

## Setup

### Prerequisites
- Python 3.12+
- P1 공문닥터 (`gongmun-doctor`) — must be cloned separately

### Install

```bash
# 1. Clone and install P1 공문닥터
git clone <gongmun-doctor-repo>
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

## Adding a New Agent

Each domain agent requires only two files in `src/assistant_22b/agents/<domain>/`:

1. **`manifest.json`** — declares triggers, sensitivity, fallback flag
2. **`agent.py`** — a class extending `BaseAgent` with a `process()` method

The `AgentRegistry` discovers it automatically on startup.

### Example manifest.json

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

## Project Structure

```
src/assistant_22b/
├── pipeline/          # PipelineContext, PipelineExecutor
├── security/          # SecurityAuditor, Gate 1-4
└── agents/
    ├── base.py        # BaseAgent ABC
    ├── registry.py    # Manifest-driven agent loading
    └── administrative/ # P1 공문닥터 wrapper
```

## Data Privacy

- No server. No cloud sync. All data stays on your PC.
- Audit logs are Fernet-encrypted at rest (`~/.22b-assistant/audit.db`).
- Input text is never stored — only its SHA-256 hash is logged.
- PII is detected and masked before any external LLM call.

## Roadmap

- **Phase A (current):** Administrative Agent (공문닥터), 4-Gate Security
- **Phase B:** Legal Agent (규정레이다), Task Agent, Personalization
- **Phase C:** Local LLM integration (civil-ai-ko.gguf)
- **Phase D:** Civil Engineering, Architecture, Permit, Accounting, Audit agents

## License

MIT
```

- [ ] **Step 2: Run full test suite one final time**

```bash
pytest --tb=short -q
```
Expected: all tests PASS

- [ ] **Step 3: Add remote and push to GitHub**

```bash
git add README.md
git commit -m "docs: add README with setup, architecture, and agent extension guide"

git remote add origin https://github.com/sinmb79/00-assistant.git
git branch -M main
git push -u origin main
```

Expected: push succeeds. Verify at https://github.com/sinmb79/00-assistant

---

## Verification Checklist

Before marking complete:

- [ ] All tests written before implementation
- [ ] Watched each test fail before implementing
- [ ] `pytest --tb=short -q` shows all PASS
- [ ] No API keys, personal data, or raw text in git history
- [ ] README explains setup, architecture, and how to add an agent
- [ ] GitHub push succeeded
