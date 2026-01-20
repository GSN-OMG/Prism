# Prism

Codex CLI를 활용해 빠르게 구현/검증/데모까지 가져가기 위한 해커톤용 워크스페이스입니다.

## 빠른 시작

- Codex 실행: `codex`
- 변경사항 리뷰: `codex review --uncommitted`
- 재사용 프롬프트 실행: `codex exec - < .codex/prompts/plan.md`
- (선택) 공통 커맨드: `make help`

## 추천 워크플로우 (해커톤)

1) 계획: `.codex/prompts/plan.md`
2) 구현: `.codex/prompts/implement.md`
3) 리뷰: `.codex/prompts/review.md` / `.codex/prompts/code-review.md`
4) 보안 점검(필요 시): `.codex/prompts/security-review.md`
5) 빌드 깨짐/타입 에러: `.codex/prompts/build-fix.md`
6) 데모 준비: `.codex/prompts/demo-script.md`

## 문서/템플릿

- Codex 작업 규칙(프로젝트용): `CODEX.md`
- 해커톤 플레이북: `docs/hackathon-playbook.md`
- ADR 템플릿(설계 결정 기록): `docs/adr-template.md`

## 참고

이 레포의 Codex 템플릿/체크리스트 구성은 `affaan-m/everything-claude-code`의 아이디어를 Codex CLI 워크플로우에 맞게 재구성한 것입니다.
