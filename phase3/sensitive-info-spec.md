# 민감정보 정의서 (v0.6)

목표: 회고 법정 모듈이 입력 컨텍스트를 수집/저장/모델에 전달하기 전에 **민감정보(Secrets/PII 등)** 를 일관되게 식별·마스킹하여 유출/재노출 위험을 낮춘다. 초기에는 **디폴트 정책**을 제공하고, 사용자가 **정책을 업데이트**할 수 있어야 한다.

## 1) 적용 범위

- `ContextBundle` 원문(대화/툴콜/로그/코드 조각/에러 메시지)
- `ContextBundle.agents[].prompt` (사건 입력에 포함되는 경우)
- `ContextBundle.result`, `ContextBundle.feedback` (사건 결과/피드백 원문)
- 이벤트 메타/운영 정보(`events[].meta`, `events[].usage`)에 포함된 도구 인자/결과/에러도 동일하게 마스킹
- DB 저장 데이터(`case_events.content`, `court_runs.artifacts`, `lessons.*`)
- 에이전트 입력(검사/변호사/배심원/판사에게 전달되는 컨텍스트)

## 2) 기본 원칙

- **모델 입력 전 선제 마스킹**: 민감정보는 LLM에게 보내지지 않도록 “에이전트 실행 전” 단계에서 마스킹한다.
- **최소 수집**: 분석에 필요하지 않은 원문(특히 자격증명/토큰)은 저장하지 않는다.
- **DB 저장은 마스킹된 원문만**: `case_events.content`, `court_runs.artifacts` 등 DB에 저장되는 텍스트/아티팩트는 **마스킹된 형태만** 저장한다(마스킹 전 원문은 저장하지 않는다).
- **프롬프트도 동일 적용**: 사건 입력/권고안에 포함되는 프롬프트 텍스트도 동일한 마스킹 규칙을 적용한다(원칙적으로 프롬프트에 secrets를 넣지 않는다).
- **버전/추적 가능성**: 어떤 사건이 어떤 정책 버전으로 마스킹됐는지 기록한다(`cases.redaction_policy_version` 등).
- **사용자 커스터마이즈**: 기본 정책은 시작점이며, 조직/프로젝트 특성에 맞게 확장 가능해야 한다.

## 3) 민감정보 범주(디폴트)

### A. 비밀(Secrets) — 기본: 마스킹
- API 키, 액세스 토큰, 리프레시 토큰, 세션 쿠키
- 비밀번호/패스프레이즈/OTP/개인키(SSH/PGP)/서명키
- 클라우드 크레덴셜(AWS/GCP/Azure 등) 및 연결 문자열

### B. 개인식별정보(PII) — 기본: 마스킹(필요 시 해시)
- 이메일, 전화번호
- 주민번호/여권번호 등 국가 식별자(가능하면 드롭 또는 강한 마스킹)
- 실명/주소/정확한 위치 정보(정책에 따라)

### C. 내부정보/민감 메타 — 기본: 부분 마스킹 또는 드롭(정책 선택)
- 내부 전용 도메인/호스트/사내 경로
- 고객명/계약명/내부 프로젝트 코드네임
- 장애 리포트의 고객 식별 단서

## 4) 기본 처리 규칙(디폴트)

- **마스킹(mask)**: 민감 토큰을 `***REDACTED:<type>***` 형태로 치환
- **부분 마스킹(partial)**: 앞/뒤 일부만 남김(예: `sk-...abcd`, 디폴트 `keep_start=4`, `keep_end=4`)
- **해시(hash)**: 동일 토큰 반복 여부만 추적하고 싶을 때(원문 복원 불가)
- **드롭(drop)**: 저장/전달 자체를 하지 않음(고위험 식별자에 권장)

권장 디폴트:
- Secrets: `partial` 또는 `mask`
- PII: `mask` (필요 시 `hash`)
- 국가 식별자/금융 정보: `drop` 또는 강한 `mask`

## 5) 정책 포맷/버전 관리(권장)

- 정책은 **JSON**을 1차 표준으로 두고(파일 기반 또는 DB 기반), 아래를 만족해야 한다.
  - 활성 정책(`is_active`) 1개
  - 정책 `version` 고정
  - 케이스에 적용된 정책 버전 기록
  - 구조 검증을 위해 JSON Schema 제공(예: `phase3/redaction-policy.schema.json`)
- 디폴트 정책 파일(초안): `phase3/redaction-policy.default.json`
- 업데이트 방식(MVP): 정책 파일을 수정하고 **재시작 시 반영**한다(DB 즉시 갱신/핫리로드는 추후).

### 예시(초안) — JSON
```json
{
  "version": "0.2",
  "rules": [
    {
      "name": "openai_api_key_like",
      "category": "secret",
      "action": "partial",
      "pattern": "\\bsk-[A-Za-z0-9]{20,}\\b"
    },
    {
      "name": "bearer_token",
      "category": "secret",
      "action": "mask",
      "pattern": "(?i)\\bBearer\\s+[A-Za-z0-9\\-\\._~\\+/]+=*\\b"
    },
    {
      "name": "email",
      "category": "pii",
      "action": "mask",
      "pattern": "\\b[^\\s@]+@[^\\s@]+\\.[^\\s@]+\\b"
    },
    {
      "name": "phone_like",
      "category": "pii",
      "action": "mask",
      "pattern": "\\b\\+?\\d[\\d\\s\\-()]{7,}\\b"
    }
  ]
}
```

## 6) 결정 사항 (현재)

- 원문 보관: **완전 미보관**. DB에는 마스킹된 원문만 저장한다.
