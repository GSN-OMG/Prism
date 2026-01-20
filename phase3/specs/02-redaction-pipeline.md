# 레댁션(민감정보 마스킹) 파이프라인 스펙

목표: `ContextBundle` 및 모든 저장/모델입력 데이터에서 민감정보를 마스킹한다. DB에는 **마스킹된 원문만 저장**한다.

## 입력/출력

- 입력: 임의의 JSON 오브젝트(주로 `ContextBundle`) + `RedactionPolicy` JSON (`redaction-policy.schema.json`)
- 출력:
  - redacted JSON(원본 구조 유지)
  - (선택) 레포트: 적용된 규칙 이름/횟수, policy version

## 정책

- 디폴트 정책 파일: `redaction-policy.default.json`
- 정책 업데이트(MVP): 파일 수정 후 재시작

## 마스킹 대상(필수)

- `events[].content`, `events[].meta`, `events[].usage`
- `agents[].prompt.content`
- `result.*`, `feedback.*`
- `court_runs.artifacts`(저장 시)

## 처리 액션

- `mask`: `***REDACTED:<category>***`로 치환
- `partial`: 앞/뒤 일부만 남기고 치환(디폴트 `keep_start=4`, `keep_end=4`)
- `drop`: 저장/전달 금지(치환 문자열로 대체하거나 필드 제거 중 하나를 선택)
- `hash`: 가능하나 MVP에서는 권장하지 않음(복원 불가/충돌/운영 복잡성)

## 구현 가이드(권장)

- JSON 트리 전체를 순회하며 **문자열 값**에 regex 룰을 적용한다.
- 룰 적용 순서는 정책의 `rules[]` 순서를 따른다(결정론적).
- 레댁션 과정에서 원문을 로그로 남기지 않는다.

## 테스트(권장)

- 최소 테스트:
  - OpenAI 키 형태(`sk-...`, `sk-proj-...`) 마스킹
  - GitHub 토큰(`gh*_...`) 마스킹
  - 이메일/전화번호 마스킹
  - “drop” 룰이 제대로 제거/치환되는지

## 완료 조건(MVP)

- `ContextBundle`을 입력하면 redacted 버전을 반환한다.
- redacted 데이터만 DB에 적재되도록 파이프라인이 강제된다.
