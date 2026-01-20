# 시크릿/설정 스펙 (해커톤 운영 가이드)

목표: OpenAI/GitHub/DB 등 시크릿이 **코드/커밋/로그/DB**에 남지 않게 운영한다.

## 원칙

- API Key는 **환경변수** 또는 로컬 `.env`로만 관리(`.env`는 `.gitignore`에 의해 추적되지 않음).
- 키가 채팅/로그 등 외부로 노출된 경우 **즉시 폐기(rotate)** 하고 새 키로 교체한다.
- Court 입력/저장 데이터는 모두 레댁션을 통과한 뒤에만 사용/저장한다.
- 에러 로그/도구 호출 인자도 민감정보를 포함할 수 있으므로 동일하게 마스킹한다.

## 권장 환경변수(예시)

- 예시는 `phase3/.env.example` 참고.
- `OPENAI_API_KEY` (절대 커밋 금지)
- `GITHUB_TOKEN` (절대 커밋 금지)
- `DATABASE_URL`
- `REDACTION_POLICY_PATH=phase3/redaction-policy.default.json`

## 체크리스트

- [ ] `.env` 파일이 git에 올라가지 않는지 확인
- [ ] `case_events`에 원문 시크릿이 저장되지 않는지 샘플 케이스로 확인
- [ ] GUI/로그 출력이 redacted 데이터만 사용하는지 확인
