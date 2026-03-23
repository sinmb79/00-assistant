# Claude Code Task: 22B Assistant BMVP

## 선행 필독
`22b_assistant_project_tree_v5_final.md` 를 먼저 읽어라. 전체 아키텍처가 거기 있다.

## 현재 상태
- P1 공문닥터: Phase 3 완료 (또는 진행 중)
- 이 코드를 **행정 에이전트**로 감싸서 22B Assistant에 통합

## BMVP 범위 (이것만 만들어라)

1. **시스템 트레이 앱 + 채팅 창** (PyWebView)
2. **코디네이터** — 키워드 기반 라우터. 사용자 입력 → 적절한 에이전트 분배
3. **행정 에이전트** — 기존 공문닥터 엔진을 BaseAgent로 래핑
4. **보안감사관** — 4-Gate 파이프라인 감시
   - Gate 1: 입력 민감도 분류 (정규식 PII 탐지)
   - Gate 2: 외부 전송 시 마스킹 + 사용자 확인
   - Gate 3: 결과물 검증 (인용 조문 DB 대조, 민감정보 노출 체크)
   - Gate 4: 전 과정 감사 로그 (암호화 SQLite)
5. **LLM Router** — 로컬(llama-cpp) or 외부(LiteLLM, 사용자 API key) 선택
6. **로컬 데이터 저장** — 암호화 SQLite (대화, 설정, 감사로그)
7. **한글 COM 연동** — 기존 hwp_com 모듈 통합

## 핵심 설계 원칙

- 에이전트는 대화하지 않는다. 파이프라인(단방향): 입력→처리→결과
- 보안감사관은 모든 파이프라인에 걸쳐 있다. 우회 불가
- 물리적 LLM 인스턴스는 1개. 에이전트별로 다른 프롬프트
- 규칙 기반 작업은 LLM을 거치지 않는다
- 서버 없음. 전부 로컬
- BaseAgent 추상 클래스 만들고, 이후 도메인 에이전트(법무, 토목, 건축 등)는 같은 구조로 추가 가능하게

## 에이전트 팩 구조 (확장 표준)

```
agents/
├── base.py              # BaseAgent ABC
├── administrative/      # 행정 에이전트
│   ├── manifest.json
│   ├── role_prompt.txt
│   ├── rules/
│   ├── corpus/
│   └── agent.py         # AdministrativeAgent(BaseAgent)
└── registry.py          # 에이전트 폴더 자동 탐색 + 로딩
```

manifest.json 에 triggers(키워드), llm_preference(local/hybrid), sensitivity(등급) 포함.
코디네이터가 manifest의 triggers를 보고 라우팅.

## 순서

1. BaseAgent ABC + 파이프라인 실행기
2. 보안감사관 (4-Gate)
3. 코디네이터 (키워드 라우터)
4. 행정 에이전트 (공문닥터 래핑)
5. LLM Router (로컬/외부 선택)
6. UI (트레이 + 채팅 창)
7. 스토리지 (암호화 SQLite)
8. 통합 테스트

기존 공문닥터 코드를 깨지 마라. 래핑만 해라.
