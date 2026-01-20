# Vector DB: pgvector

이 프로젝트의 벡터 저장소는 Chroma 대신 **Postgres + pgvector**를 사용합니다.

## 권장 환경 변수 (초안)

- `DATABASE_URL`: Postgres 접속 문자열 (예: `postgresql+psycopg://user:pass@host:5432/db`)
- `PGVECTOR_TABLE_PREFIX`: 테이블 접두어(여러 프로젝트 공존 시)

## 메모

- 임베딩/검색 스키마 및 인덱스(HNSW/IVFFLAT)는 Phase 1/3에서 확정합니다.
- Phase 2(Agents)는 Vector 조회 결과를 입력으로 받는 형태로 유지합니다.

