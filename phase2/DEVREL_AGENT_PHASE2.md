# Phase 2 작업 노트 (Agents)

이 문서는 Phase 2(Agents) 구현을 위한 작업 노트입니다. 전체 설계는 루트의
`DEVREL_AGENT_IMPLEMENTATION.md`를 기준으로 합니다.

## 목표

- Agents 레이어의 순수 로직(입력 → 출력)을 먼저 스캐폴딩
- 외부 의존성(GitHub/LLM/Vector)은 이후 Phase에서 주입/연결
- 파일 단위 커밋으로 협업 충돌 최소화

## 전제 (Vector DB)

- Vector DB는 Chroma 대신 **Postgres + pgvector**를 사용합니다.
- Phase 2에서는 Vector 연동 코드는 작성하지 않고, 이후 Phase에서 주입/연결합니다.

## 디렉토리

- `phase2/prism-devrel/src/devrel/agents/`

## 산출물

- `assignment.py`: 이슈/기여자 매칭 및 할당 추천 데이터 생성
- `response.py`: 이슈 답변 초안 생성 (또는 추가 정보 요청)
- `docs.py`: 반복 질문/패턴 기반 문서 갭 후보 생성
- `promotion.py`: 기여자 활동 기반 승격 추천 데이터 생성

