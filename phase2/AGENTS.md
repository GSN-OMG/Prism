# Repository Guidelines

## Project Structure & Module Organization
This repository currently documents the DevRel Agent design in `phase2/DEVREL_AGENT_IMPLEMENTATION.md`. If you implement code, follow the planned layout in that document: a top-level `prism-devrel/` project with `src/devrel/` and subpackages like `core/`, `github/`, `llm/`, `vector/`, and `agents/`. Keep the plan updated whenever you add, rename, or remove modules so the diagram and examples stay accurate.

## Build, Test, and Development Commands
There is no runnable build in this repo yet. When code lands, the CLI is expected to expose commands like:

```bash
prism-devrel analyze
prism-devrel assign <issue>
prism-devrel respond <issue>
prism-devrel docs
prism-devrel promotions
prism-devrel run
```

If you add scripts, list them here and in `phase2/DEVREL_AGENT_IMPLEMENTATION.md` with a one-line purpose.

## Coding Style & Naming Conventions
Use Python 3.11+ with type hints, 4-space indentation, and `snake_case` for functions/variables, `PascalCase` for classes. Keep file names aligned with responsibilities (for example, `agents/assignment.py`, `llm/schemas.py`). Prefer small, focused modules and keep comments minimal and explanatory.

## Testing Guidelines
No tests exist yet. When adding tests, use `pytest`, place them under `tests/`, and name files `test_*.py`. Mock GitHub and OpenAI calls by default, and keep integration tests opt-in with environment flags.

## Commit & Pull Request Guidelines
This directory is not a Git repo, so no commit history is available. Use clear, imperative messages with a short scope (for example, `docs: update architecture diagram` or `feat: add GitHub client scaffold`). PRs should include a concise description, any linked issue, and a note about updates required in `phase2/DEVREL_AGENT_IMPLEMENTATION.md`.

## Security & Configuration Tips
Secrets should live in `.env` and never be committed. Expected keys include `OPENAI_API_KEY`, `GITHUB_TOKEN`, and `GITHUB_REPO`; update `.env.example` when adding configuration. If you add new environment variables, document them here and in the plan.
