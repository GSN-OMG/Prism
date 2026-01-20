# 임베딩/유사도/검색 스펙 (model2vec + pgvector)

목표: 교훈/권고안을 임베딩하여 검색과 중복 후보 탐지에 사용한다.

## 범위

- 임베딩 생성: model2vec 다국어 모델(고정된 dim/버전 권장)
- 저장: `lessons.embedding` (pgvector)
- 검색: `search_lessons(role, query, k)` 제공

## 입력/출력

- 입력: 텍스트(예: `title + content + rationale`)
- 출력: float 벡터 + 메타(`embedding_model`, `embedding_dim`)

## 중복/승계 후보 탐지(권장)

- 신규 lesson 저장 전:
  - 같은 `role`에서 Top-K 유사 lesson 조회
  - 유사도 임계값을 넘는 후보를 Judge 입력에 포함(병합/승계 판단)

## 인덱싱(권장)

- pgvector 인덱스(HNSW 또는 IVFFlat) 사용
- dim은 운영에서 고정(모델 변경 시 재임베딩 마이그레이션)

## 완료 조건(MVP)

- 임베딩 생성 함수 1개 + pgvector 저장
- `search_lessons`로 Top-K 조회 가능

