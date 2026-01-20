# prism-devrel (Phase 2)

Phase 2는 `agents/` 로직 스캐폴딩을 목표로 합니다.

## Dev

```bash
cd phase2/prism-devrel
python -m pytest
```

## Fixtures (터미널에서 결과 보기)

```bash
cd phase2/prism-devrel
python scripts/run_fixtures.py
```

LLM으로 실제 에이전트 출력 생성(과금 발생):

```bash
export USE_LLM=1
python scripts/run_fixtures.py
```

LLM-as-a-judge를 켜려면:

```bash
export RUN_LLM_JUDGE=1
export OPENAI_API_KEY=...
python scripts/run_fixtures.py
```
