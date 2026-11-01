# Developer Context

- This repository contains `jacl4py`, a standalone Python 3.10+ logger. Source is
  in `jacl4py/`; regression tests are in `tests/`. Preserve logger isolation and
  explicit handler lifecycle management.
- Use uv for Python commands. Run from this repository root; follow the setup
  in `README.md`.
- Validate changes with `uv run python .github/scripts/run_checks.py unit` and
  `uv run python .github/scripts/run_checks.py lint` after installing development
  requirements. Keep regression tests focused on changed behavior.
- Keep runtime dependencies in `pyproject.toml` and `requirements.txt` aligned.
  The version source is `jacl4py/__init__.py`; do not bump it unless requested.
- Read `.github/CI.md` for CI and release policy. The publishing workflow is
  `.github/workflows/pypi_publish.yml`; pushes to `master` publish to PyPI.
  Do not publish, push tags, or commit without explicit authorization.
- Pre-1.0.0 releases are testing versions; semantic versioning starts at 1.0.0.