# Hackathon Playbook (Codex)

이 문서는 “Codex와 함께 해커톤을 끝까지(데모/발표까지) 가져가는” 최소 플레이북입니다.

## 1) 킥오프 체크리스트 (15–30분)

- 문제 정의(1문장):
- 타겟 사용자:
- MVP(반드시 되는 것 3개):
- Nice-to-have(있으면 좋은 것 3개):
- 데모 시나리오(2분짜리):
- 리스크 Top 3(예: API 불안정, 로그인 지연, 배포 실패):
- 플랜 B(배포 실패 시 로컬/녹화/스크린샷 등):

권장: 위 내용을 `CODEX.md`의 “프로젝트 컨텍스트” 섹션에 바로 채워 넣기.

## 2) Codex 사용 루프 (반복)

1. 계획 세우기: `codex exec - < .codex/prompts/plan.md`
2. 작은 변경으로 구현: `codex exec - < .codex/prompts/implement.md`
3. 리뷰로 위험 줄이기: `codex exec - < .codex/prompts/review.md`
4. 필요 시 보안/빌드 픽스:
   - 보안: `codex exec - < .codex/prompts/security-review.md`
   - 빌드/타입: `codex exec - < .codex/prompts/build-fix.md`

## 3) “필요하면 문서/결정부터” 패턴

구현 전에 아래 중 하나라도 해당하면, 먼저 짧은 문서/결정을 남기는 게 더 빠를 때가 많습니다.

- 팀원이 2명 이상이고 동시에 다른 부분을 작업해야 함
- 데이터 모델/API 계약이 핵심임
- 인증/권한/결제/파일 업로드 등 보안 민감 영역이 있음

템플릿: `docs/adr-template.md`

## 4) 데모 준비 체크리스트 (발표 1–2시간 전)

- [ ] “시작 URL/커맨드” 1개로 데모 시작 가능
- [ ] 네트워크/API 실패 시 플랜 B 준비(스위치/목업/녹화)
- [ ] 주요 화면 3개만 고정(기능 욕심 금지)
- [ ] 데모 경로를 사람 기준으로 작성(코드 설명 X)

프롬프트: `codex exec - < .codex/prompts/demo-script.md`

