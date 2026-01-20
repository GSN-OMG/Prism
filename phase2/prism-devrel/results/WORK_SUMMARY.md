# Phase 2 DevRel Agents - 작업 요약

**작업 일시**: 2026-01-20
**브랜치**: `phase2-agents-scaffold`

---

## 1. 수행 작업 개요

### 1.1 LLM 클라이언트 개선 및 에이전트 프롬프트 수정
- LLM 클라이언트 robustness 향상
- 에이전트 프롬프트 개선
- 커밋: `fix(phase2-llm): improve LLM client robustness and agent prompts`

### 1.2 Raw Data 통합 및 테스트
- CSV 파일(`repo_user.csv`, `repo_user_activity.csv`) 파싱 로직 구현
- `raw_data_loader.py` 생성 - CSV를 내부 타입으로 변환
- 에이전트 테스트 파일 생성
- 커밋: `feat(phase2-agents): add raw_data loader and tests`

### 1.3 봇 계정 필터링
- GitHub Actions, Copilot, Dependabot 등 봇 계정 제외 로직 추가
- `is_bot_account()` 함수 및 `BOT_PATTERNS` 정의
- 커밋: `feat(phase2-agents): add bot filtering and full agent pipeline results`

### 1.4 Tavily API 통합
- 외부 레포 인사이트 수집을 위한 Tavily 클라이언트 구현
- Issue Analysis, Docs Gap 에이전트에 Tavily 연동
- 커밋: `feat(phase2-agents): add Tavily API integration for external insights`

---

## 2. 생성/수정된 주요 파일

### 2.1 새로 생성된 파일

| 파일 | 설명 |
|------|------|
| `tests/helpers/raw_data_loader.py` | CSV 파싱 및 Contributor 변환 |
| `src/devrel/search/tavily_client.py` | Tavily API 클라이언트 |
| `results/agents/1_issue_analysis.md` | 이슈 분석 에이전트 결과 |
| `results/agents/2_assignment.md` | 담당자 할당 에이전트 결과 |
| `results/agents/3_promotion.md` | 승격 평가 에이전트 결과 |
| `results/agents/4_docs_gap.md` | 문서 갭 탐지 에이전트 결과 |

### 2.2 수정된 파일

| 파일 | 변경 내용 |
|------|----------|
| `src/devrel/agents/types.py` | ExternalInsight, EnhancedIssueAnalysis 등 새 타입 추가 |
| `src/devrel/agents/assignment.py` | `analyze_issue_with_tavily()` 함수 추가 |
| `src/devrel/agents/docs.py` | `detect_doc_gaps_with_tavily()` 함수 추가 |
| `.env.example` | TAVILY_API_KEY 설정 추가 |

---

## 3. 에이전트 파이프라인

```
Issue Analysis → Assignment → Response → Docs Gap → Promotion
      ↓              ↓                        ↓
  (Tavily)      (Contributor         (Tavily 외부
   외부 인사이트)    봇 필터링)           레포 비교)
```

### 3.1 테스트된 에이전트

| 에이전트 | 기능 | Tavily 연동 |
|----------|------|-------------|
| Issue Analysis | 이슈 분석 (유형, 우선순위, 필요 기술) | ✅ |
| Assignment | 담당자 추천 | - |
| Promotion | 기여자 승격 평가 | - |
| Docs Gap | 문서 갭 탐지 | ✅ |
| Response | 이슈 응답 초안 생성 | - |

---

## 4. 봇 필터링 패턴

```python
BOT_PATTERNS = (
    "[bot]", "github-actions", "dependabot", "renovate",
    "copilot", "chatgpt-codex-connector", "codecov",
    "stale", "mergify", "semantic-release",
)
```

필터링 결과:
- **제외됨**: github-actions[bot], copilot, chatgpt-codex-connector
- **포함됨**: AnkanMisra, HemanthIITJ, gustavz, habema, ihower

---

## 5. Tavily API 활용

### 5.1 Issue Analysis 향상

**기본 분석**:
- 이슈 유형, 우선순위
- 필요 기술, 키워드
- 추가 정보 필요 여부

**Tavily 보강**:
- AI 요약 (문제 해결 인사이트)
- 관련 레포 목록
- 외부 참조 링크 (관련도 점수 포함)

### 5.2 Docs Gap 향상

**기본 분석**:
- 문서 갭 존재 여부
- 갭 주제, 제안 문서 경로
- 문서 목차 제안

**Tavily 보강**:
- 유사 레포 비교
- 외부 문서 참조
- Best Practices 요약

---

## 6. 테스트 결과

```
pytest tests/ -v
================================
29 passed
================================
```

---

## 7. 커밋 히스토리

```
a13922b docs(phase2): add worklog summary
60f240f test(phase2-llm): run live openai tests when key present
27a50b0 docs(phase2): add USE_LLM fixture runner mode
fc7834e test(phase2-agents): cover llm paths with fake client
d25307c feat(phase2-agents): add llm structured output paths
```

---

## 8. 다음 단계 (권장)

1. **Response Agent 완성**: 이슈 응답 초안 생성 기능 테스트
2. **End-to-End 데모**: 전체 파이프라인 실행 스크립트 작성
3. **CI/CD 연동**: GitHub Actions로 자동 테스트 실행
4. **pgvector 연동**: 벡터 DB 기반 유사 이슈 검색

---

## 9. 환경 설정

```bash
# .env 파일 설정 (예시)
OPENAI_API_KEY=sk-...
TAVILY_API_KEY=tvly-...
OPENAI_JUDGE_MODEL=gpt-4.1-mini
RUN_LLM_JUDGE=0
```

```bash
# 테스트 실행
cd phase2/prism-devrel
PYTHONPATH=src:tests pytest tests/ -v
```
