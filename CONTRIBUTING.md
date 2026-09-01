# Contributing

Development conventions for `chk-a`.

---

## Environment

```bash
make dev-install      # venv + pip install -e ".[dev]"
make test             # pytest
make lint             # black --check + flake8
make build            # sdist/wheel
```

Python 3.11+ (tested on 3.14). The project deliberately avoids heavy ML/monitoring
dependencies — online learning uses a custom EMA + entropy implementation. **Do not add
`torch`/`sklearn`/`river`/`prometheus_client`/`python-systemd`** unless a loop
spec explicitly requires it.

---

## Layout

- `src/chk_a/agents/` — the four agents (resolver, consensus, ml, alert).
- `src/chk_a/config/loader.py` — YAML + `${ENV}` config loader.
- `src/chk_a/models/schemas.py` — pydantic contracts shared between agents.
- `src/chk_a/storage/` — atomic JSON baseline store.
- `src/chk_a/utils/` — logger, telegram, systemd_notify, context.
- `src/chk_a/orchestrator.py` — scheduler + agent wiring.
- `src/chk_a/main.py` — CLI entry point.
- `tests/` — pytest suite (mirrors `src/chk_a` structure).

---

## Conventions

- **Async**: agents that do I/O are `async`; `ConsensusAgent.aggregate()` is sync
  (pure computation).
- **Structured logging**: use `setup_logger` (JSONL). Per-cycle `correlation_id`
  is attached automatically via `utils/context`.
- **Tests**: every agent has a co-located `tests/test_*_agent.py`. Prefer offline
  tests (mock network/Telegram). When a test fails because of a spec
  misinterpretation, **fix the test to match the authoritative `md` spec**, not
  the agent code, unless the agent is genuinely wrong.
- **Config**: secrets come from `${ENV}`; never commit tokens.
- **No new heavy deps** without updating `pyproject.toml` and this doc.

---

## Adding a loop

1. Read `md/loop_engineering_prompt.md` — it is the authoritative spec.
2. Implement the feature under `src/chk_a/`.
3. Add/extend tests; ensure `make test` and `make lint` pass.
4. Update docs (README / ARCHITECTURE / RUNBOOK) as needed.
5. Report the loop as done with the test count and any regressions.

---

## Releasing

```bash
make lint && make build
# review dist/, then install via install.sh on target hosts
```
