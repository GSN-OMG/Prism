# 에이전트 테스트 결과

**생성일시**: 2026-01-20T14:45:20
**대상 저장소**: openai/openai-agents-python
**전체 기여자 수**: 58명
**테스트에 사용된 활성 기여자**: 5명

---

## 입력 데이터

### 이슈 #2314
- **제목**: OAuth token refresh not working with custom providers
- **본문**: When using a custom OAuth provider, the token refresh fails with 401 errors.
- **라벨**: `bug`, `auth`

### 기여자 목록 (raw_data에서 추출)

| 로그인 | 활동 영역 | 병합된 PR | 리뷰 수 | 활동 점수 |
|--------|----------|----------|---------|----------|
| HemanthIITJ | 커뮤니티, 개발 | 9 | 0 | 1.0 |
| chatgpt-codex-connector | 코드리뷰, 커뮤니티 | 0 | 53 | 5.9 |
| github-actions | 커뮤니티, 개발 | 11 | 0 | 5.8 |
| github-actions[bot] | 개발 | 11 | 0 | 1.1 |
| gustavz | 코드리뷰, 개발 | 2 | 9 | 1.3 |

---

## 결과 비교

### 1. 이슈 분석 (Issue Analysis)

| 항목 | 규칙 기반 | LLM 기반 |
|------|----------|----------|
| 이슈 유형 | bug | bug |
| **우선순위** | medium | **high** |
| 필요 기술 | debugging, auth | OAuth, authentication, API, security |
| 키워드 | oauth, auth | OAuth, token refresh, custom provider, 401 error |
| **추가 정보 필요** | false | **true** |
| **권장 조치** | direct_answer | **request_info** |

### 2. 담당자 추천 (Assignee Recommendation)

| 항목 | 규칙 기반 | LLM 기반 |
|------|----------|----------|
| **추천 담당자** | github-actions | **HemanthIITJ** |
| **신뢰도** | 0.54 | **0.75** |
| 대안 담당자 | chatgpt-codex-connector, github-actions[bot] | gustavz, github-actions |

#### 규칙 기반 추천 이유
| 요소 | 설명 | 점수 |
|------|------|------|
| 최근 활동 | recent_activity_score=5.8 | 1.00 |
| 병합된 PR | merged_prs=11 | 0.55 |

#### LLM 기반 추천 이유
| 요소 | 설명 | 점수 |
|------|------|------|
| 관련 기술/영역 | HemanthIITJ의 커뮤니티 및 개발 전문성이 OAuth 버그 처리에 적합 | 0.30 |
| 최근 활동 | 실제 인간 기여자 중 최고 활동 점수 | 0.20 |
| 병합된 PR | 9개의 병합된 PR로 검증된 기여자 | 0.25 |

### 3. 승진 평가 (Promotion Evaluation) - HemanthIITJ

| 항목 | 규칙 기반 | LLM 기반 |
|------|----------|----------|
| 현재 단계 | REGULAR | Contributor |
| 제안 단계 | REGULAR | Contributor |
| 승진 후보 여부 | false | false |
| **신뢰도** | 0.40 | **0.58** |

#### 규칙 기반 증거
| 기준 | 상태 | 상세 |
|------|------|------|
| 최근 활동 | 미충족 | recent_activity_score=1.0 |
| 병합된 PR | 충족 | merged_prs=9 |
| 리뷰 | 미충족 | reviews=0 |

#### LLM 기반 증거
| 기준 | 상태 | 상세 |
|------|------|------|
| 최근 활동 점수 | 우수 | 매우 높은 현재 참여도 |
| 병합된 PR | 양호 | 9개의 병합된 PR, 일관된 기여 |
| 리뷰 | 부족 | 0개의 리뷰, 동료 리뷰 활동 없음 |
| 활동 영역 | 광범위 | 커뮤니티와 개발 영역에서 활동 |

#### LLM 권장사항
> 아직 승진 후보가 아닙니다. 리뷰어/메인테이너 경로로 성장하려면 코드 리뷰 수행 및 문서화를 시작하고, 이슈 분류에 참여하며, 품질 높은 PR을 계속 제출하세요.

---

## 주요 관찰 사항

### 1. LLM이 더 맥락적인 분석 제공
- 401 에러의 심각성을 고려하여 우선순위를 `high`로 상향
- 본문이 있음에도 추가 정보가 필요하다고 판단

### 2. 담당자 선택 방식의 차이
- **규칙 기반**: 높은 활동 점수 우선 (봇 포함)
- **LLM 기반**: 관련 경험을 가진 실제 인간 기여자 우선

### 3. 승진 평가의 차이
- **규칙 기반**: 단순 임계값 기반 판단
- **LLM 기반**: 다차원적 분석 및 성장을 위한 실행 가능한 피드백 제공

---

## 결론

| 측면 | 규칙 기반 | LLM 기반 |
|------|----------|----------|
| 속도 | 빠름 (즉시) | 느림 (API 호출) |
| 비용 | 무료 | 토큰 비용 발생 |
| 정확도 | 기계적 | 맥락 인식 |
| 설명 | 제한적 | 상세함 |
| 추천 | 적합: 초기 분류 | 적합: 최종 결정 |
