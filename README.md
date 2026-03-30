# 22B Assistant

**한국 공무원을 위한 로컬 AI 비서 — 공문서 교정부터 법령 검색까지**

내 PC 안에서만 돌아갑니다. 서버 없음. 클라우드 동기화 없음. 민감한 업무 문서가 외부로 나가지 않습니다.

---

## 이 도구가 하는 일

공문서를 채팅창에 붙여넣으면, AI가 맞춤법·공문서체·형식을 교정하고 근거 규칙까지 알려줍니다.

```
Ctrl+Shift+G  →  채팅창 열기
                     ↓
            공문서 텍스트 붙여넣기
                     ↓
    🔒 Gate 1: 입력 민감도 판단 (주민번호·전화번호·이메일 감지)
                     ↓
    📝 행정 에이전트: 맞춤법·공문서체 교정 + 근거 규칙 ID 명시
                     ↓
    🔒 Gate 2: 외부 LLM 사용 시 → PII 마스킹 후 전송 여부 확인
                     ↓
    🔒 Gate 3: 결과물 검증 (인용 규칙이 실제 DB에 있는지 확인)
                     ↓
    🔒 Gate 4: 전 과정 감사 로그 (암호화 기록)
                     ↓
              교정 결과 + 근거 규칙 출력
```

지금 이 버전(BMVP)에 포함된 기능:

| 기능 | 상태 |
|------|------|
| 공문서 맞춤법·공문서체 교정 | ✅ |
| 4단계 보안 파이프라인 | ✅ |
| 시스템 트레이 앱 + 채팅 창 | ✅ |
| 암호화 대화 기록 저장 | ✅ |
| LLM 없이도 규칙 기반 교정 | ✅ |
| 로컬 LLM 연결 (GGUF 모델) | ✅ 선택 |
| 외부 LLM 연결 (Claude·OpenAI·Gemini) | ✅ 선택 |
| 법무·토목·건축·인허가·회계·감사 에이전트 | 🔜 업데이트 예정 |

---

## 준비물

**반드시 있어야 하는 것**

- Python **3.12 이상**
  터미널에서 `python --version`으로 확인합니다.
  없으면 [python.org](https://www.python.org/downloads/)에서 설치합니다. 설치 시 "Add Python to PATH" 체크박스를 반드시 체크하세요.

- **공문닥터(gongmun-doctor)**
  행정 에이전트의 핵심 교정 엔진입니다. 별도 저장소에서 먼저 설치해야 합니다.
  설치 방법은 아래 3단계를 참고하세요.

**없어도 처음엔 괜찮은 것**

- 로컬 LLM 모델 파일 (`.gguf`) — 없으면 규칙 기반 교정만 동작합니다.
- Claude·OpenAI·Gemini API 키 — 없으면 외부 LLM 없이 동작합니다.

---

## 설치 방법

### 1단계 — 공문닥터(gongmun-doctor) 설치

이 비서의 핵심 교정 엔진입니다. 먼저 설치해야 합니다.

```bash
git clone https://github.com/sinmb79/gongmun-doctor.git
cd gongmun-doctor
pip install -e .
cd ..
```

### 2단계 — 22B Assistant 설치

```bash
git clone https://github.com/sinmb79/00-assistant.git
cd 00-assistant
pip install -e ".[dev]"
```

`pip install -e ".[dev]"`는 이 프로젝트를 개발 모드로 설치하는 명령입니다.
`assistant-22b` 명령어가 터미널에서 바로 쓸 수 있게 등록됩니다.

### 3단계 — 설치 확인

```bash
pytest --tb=short -q
```

`86 passed` 메시지가 나오면 정상입니다.

---

## 실행 방법

```bash
# 방법 A: 모듈로 실행
python -m assistant_22b

# 방법 B: 설치된 명령어로 실행
assistant-22b
```

실행하면 시스템 트레이(작업표시줄 오른쪽 아래)에 22B 아이콘이 나타납니다.

**채팅 창 열기**: `Ctrl+Shift+G`

이후에도 `Ctrl+Shift+G`로 채팅 창을 열고 닫을 수 있습니다.
한글 프로그램 작업 중에도 단축키 하나로 바로 호출됩니다.

---

## 처음 써보기

1. `python -m assistant_22b` 실행
2. `Ctrl+Shift+G` 눌러서 채팅 창 열기
3. 교정이 필요한 공문서 텍스트를 채팅창에 붙여넣기
4. 전송 버튼 클릭 또는 Enter
5. 교정 결과와 근거 규칙 ID 확인

입력 예시:

```
아래와 같이 보고 드립니다. 이번 사업은 총 3개년에 걸처 시행할 계획이며...
```

출력 예시:

```
[교정 결과]
"걸처" → "걸쳐" (맞춤법 규칙 KS-013)
"보고 드립니다" → "보고합니다" (공문서체 규칙 ADM-021: 공문서에서 높임 표현 단순화)
```

---

## LLM 설정 (선택 사항)

기본값은 LLM 없이 규칙 기반 교정만 합니다. 충분히 쓸 수 있습니다.

더 자연스러운 윤문이 필요하면 아래 중 하나를 선택합니다.

### 옵션 A — 외부 LLM (Claude·OpenAI·Gemini)

설정 파일 `~/.22b-assistant/config.json`을 열어 아래처럼 수정합니다.

```json
{
  "llm_mode": "external",
  "llm_provider": "claude"
}
```

`llm_provider`에는 `"claude"`, `"openai"`, `"gemini"` 중 하나를 씁니다.
API 키는 각 서비스의 환경변수로 설정합니다.

```bash
# 예: Claude 사용 시
export ANTHROPIC_API_KEY="sk-ant-..."
```

> **외부 LLM을 사용할 때는 Gate 2가 동작합니다.**
> 전송 전에 "이 내용을 마스킹 처리해서 외부로 보내도 됩니까?" 확인 화면이 나타납니다.
> 본인이 OK 하기 전까지는 아무것도 외부로 나가지 않습니다.

### 옵션 B — 로컬 LLM (무료, 인터넷 불필요)

GGUF 형식의 로컬 모델 파일이 있으면 설정합니다.

```json
{
  "llm_mode": "local",
  "llm_model_path": "C:/models/civil-ai-ko-q4.gguf"
}
```

로컬 LLM은 인터넷이 없어도 동작합니다. 민감한 문서를 외부로 보낼 걱정이 없습니다.

---

## 보안 파이프라인 이해하기

이 도구는 모든 요청이 4단계 보안 검사를 거칩니다.

| 단계 | 이름 | 하는 일 |
|------|------|---------|
| Gate 1 | 입력 분류 | 주민번호·전화번호·이메일·계좌번호를 자동 감지해서 민감도 등급 부여 |
| Gate 2 | 외부 전송 차단 | 외부 LLM 사용 시 PII를 가린 후 "이대로 보낼까요?" 사용자 확인 |
| Gate 3 | 결과 검증 | 교정 근거로 인용된 규칙이 실제 DB에 있는지 확인. 가짜 근거 차단 |
| Gate 4 | 감사 로그 | 전 과정을 암호화 SQLite에 기록 (어떤 에이전트가 무엇을 처리했는지) |

민감도 등급이 **대외비·비밀**이면 외부 LLM은 자동으로 차단되고 로컬 처리만 허용됩니다.

---

## 데이터 저장 위치

모든 데이터는 내 PC에만 저장됩니다. 이 저장소 밖입니다.

```
~/.22b-assistant/        ← Windows 기준: C:\Users\사용자명\.22b-assistant\
├── config.json          ← 설정 파일 (LLM 모드, 단축키 등)
└── db/
    ├── conversations.db ← 대화 기록 (암호화)
    ├── tasks.db         ← 할일 목록 (암호화)
    └── audit.db         ← 감사 로그 (암호화)
```

이 폴더는 절대 GitHub에 올라가지 않습니다. `.gitignore`에 명시되어 있고, 이 저장소 밖에 있습니다.

---

## 자주 만나는 문제

### `assistant-22b` 명령을 못 찾는다

설치 단계가 빠진 경우입니다.

```bash
cd 00-assistant
pip install -e ".[dev]"
```

### `ModuleNotFoundError: gongmun_doctor` 오류

공문닥터를 먼저 설치해야 합니다.

```bash
cd gongmun-doctor
pip install -e .
```

### `Ctrl+Shift+G`가 반응하지 않는다

1. 다른 프로그램이 같은 단축키를 쓰고 있을 수 있습니다.
   `~/.22b-assistant/config.json`에서 `"hotkey"`를 다른 키로 바꿔보세요.

2. `keyboard` 패키지가 Windows에서 관리자 권한을 필요로 하는 경우가 있습니다.
   터미널을 **관리자 권한으로 실행** 후 다시 시도해보세요.

### 테스트 86개가 전부 통과하지 않는다

공문닥터 설치 후 재시도합니다.

```bash
pip install -e ../gongmun-doctor
pytest --tb=short -q
```

---

## 새 에이전트 추가하기 (개발자용)

에이전트를 하나 추가하는 데 파일 두 개면 충분합니다.

`src/assistant_22b/agents/<도메인>/` 폴더를 만들고 아래 두 파일을 넣습니다.

**manifest.json** — 에이전트 메타정보

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

`triggers`에 있는 키워드가 입력에 포함되면 이 에이전트가 자동으로 선택됩니다.

**agent.py** — 처리 로직

```python
from pathlib import Path
from assistant_22b.agents.base import BaseAgent
from assistant_22b.pipeline.context import AgentResult, PipelineContext

class LegalAgent(BaseAgent):
    def process(self, context: PipelineContext) -> AgentResult:
        return AgentResult(
            agent_id=self.agent_id,
            output="법령 검색 결과...",
            citations=["법령ID-001"],
            raw=[],
        )
```

저장하고 `assistant-22b`를 재시작하면 자동으로 등록됩니다.

---

## 프로젝트 구조

```
src/assistant_22b/
├── __main__.py          ← 진입점: python -m assistant_22b
├── config.py            ← 설정 관리 (~/.22b-assistant/config.json)
├── pipeline/
│   ├── context.py       ← 파이프라인 데이터 구조 (GateRecord, AgentResult)
│   └── executor.py      ← 파이프라인 실행기 (Gate 1→에이전트→Gate 2,3,4)
├── security/
│   ├── auditor.py       ← 보안감사관 (Gate 1~4 총괄)
│   ├── gate1_classifier.py ← PII 감지 + 민감도 등급 부여
│   ├── gate2_masker.py  ← PII 마스킹 (외부 전송 전)
│   ├── gate3_verifier.py   ← 결과 검증 (인용 규칙 + PII 노출 체크)
│   └── gate4_logger.py  ← 암호화 감사 로그 기록
├── agents/
│   ├── base.py          ← BaseAgent ABC (모든 에이전트가 상속)
│   ├── registry.py      ← manifest.json 자동 탐색 + 에이전트 로딩
│   └── administrative/  ← 행정 에이전트 (공문닥터 래핑)
├── llm/
│   └── router.py        ← LLM 라우터 (없음/로컬/외부 선택)
├── storage/
│   └── conversations.py ← 암호화 대화 기록 저장
├── hwp/
│   └── adapter.py       ← 한글(HWP) 연동
└── ui/
    ├── app.py           ← 전체 연결 (AssistantApp)
    ├── chat_window.py   ← Tkinter 채팅 UI
    └── tray.py          ← 시스템 트레이 아이콘
```

---

## 앞으로 추가될 기능

| 단계 | 내용 |
|------|------|
| Phase B | 법무 에이전트, 일정 에이전트, 개인화 학습 |
| Phase C | 로컬 LLM(civil-ai-ko.gguf) 통합, 하이브리드 자동 분기 |
| Phase D | 토목·건축·인허가·회계·감사 에이전트 |
| Phase E | 도메인 팩 마켓플레이스, 팀 내 연동 |

---

## 라이선스

MIT License
