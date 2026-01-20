# scripts

## github_raw_ingest_closedat.py

GitHub API(REST + GraphQL)를 호출해서 **closedAt 기준 기간 내 PR/Issue의 raw 응답만** `raw/` 아래에 저장합니다.  
정규화/RDB 적재/요약/벡터화 등 데이터 처리는 수행하지 않습니다.

### Prereq

- 전체(Discovery + Hydration) 수집: `GITHUB_TOKEN` 또는 `GH_TOKEN` 환경변수에 GitHub 토큰 설정
- Discovery-only(검색 결과 raw 저장만): 토큰 없이도 가능(`--no-hydrate`)
  - 참고: 토큰은 raw 저장 시 기록하지 않으며, `curl` 호출 시에도 argv에 토큰이 노출되지 않도록 `-H @file` 방식으로 전달합니다.

### Example

```bash
python3 scripts/github_raw_ingest_closedat.py --start 2026-01-06 --end 2026-01-20
```
