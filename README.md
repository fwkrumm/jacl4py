# jacl4py

Just another custom logger for Python.

`jacl4py` is a standalone package containing the custom Python logger previously
used by pookiepy.

## Installation

Install from PyPI:

```powershell
pip install jacl4py
```

Or install the local package with uv:

```powershell
uv pip install .
```

## Usage

```python
from jacl4py.logger import INTERNAL_INFO, get_logger

logger = get_logger("service")
logger.iinfo("framework lifecycle event")
logger.log(INTERNAL_INFO, "another internal event")
logger.info("service started")
```

Only `get_logger()` is needed to configure a logger. Package loggers use their
own registry, so importing the module does not replace Python's global logger
class. `logging.getLogger("service")` and `get_logger("service")` are separate
objects and do not change each other's handlers. The `INTERNAL_DEBUG` and
`INTERNAL_INFO` level names are registered with `logging`.

The console handler defaults to `INFO`; the file handler defaults to
`INTERNAL_DEBUG`. The default `log_dir=LogDir.DEFAULT` writes log files under the
system temporary directory in `<safe-name><uuid8>/<safe-name>.log`. For example,
`get_logger("test")` might write to `test12345678/test.log` under the temporary
directory. The suffix is the first eight hexadecimal characters of UUID4;
existing paths are never reused on a collision. Names are restricted to ASCII
letters, digits, dots, underscores, and hyphens for filesystem use, with other
characters replaced by underscores and the name component limited to 64
characters. The original logger name is preserved in log records.

Each writer has one stable active filename. Files rotate daily and retain up to
30 backups for that writer, not necessarily 30 calendar days. Reinitialization
and new processes receive fresh paths. Old run directories and file families
are preserved, not automatically pruned. The custom `iinfo()` and `idebug()`
methods emit at levels 7 and 5 respectively.

Pass `log_dir=None` to disable file logging, or a string or `Path` for a custom
directory. An explicit directory is used as given, with a unique filename
`<safe-name><uuid8>.log` inside it. Pass `None` for `console_log_level` or
`file_log_level` to disable that handler. Use an application-owned directory
when file permissions or durable retention matter.

```python
from jacl4py.logger import LogDir, get_logger

logger = get_logger("service", log_dir=LogDir.DEFAULT)
console_only = get_logger("console", log_dir=None)
```

`JacLogger.setLevel()` follows standard logging behavior: it changes only the
logger threshold, preserving independent console and file handler levels.
Reusing a configured name returns the cached logger, emits a warning, and
ignores new configuration arguments. Initialization and deletion are serialized
across threads; ordinary log calls do not acquire the package lifecycle lock.

Pass `reinit_if_exists=True` to replace an existing logger and apply new settings
without the cached-logger warning:

```python
from jacl4py.logger import delete_logger, get_logger

log = get_logger("my_test11", reinit_if_exists=True)
delete_logger("my_test11")
```

`delete_logger(name)` closes and removes the package logger's handlers and
unregisters it without touching standard loggers. It returns `True` if a package
logger was deleted, otherwise `False`. Existing log
files are preserved. Logging through a deleted `JacLogger` reference raises
`ResourceNotInitializedError`, a subclass of `RuntimeError`, even for messages
below the configured level. Import it from `jacl4py.logger` or
`jacl4py.exceptions`. Use the new object returned by `get_logger()` after
reinitialization. Package child loggers remain usable and reconnect when the
named logger is recreated. Use `get_logger()` for child names too.

In each worker process, call `get_logger()` to obtain a separate writer. After
`fork`, inherited package logger references are invalidated automatically; do
not continue logging through an inherited reference. No queue or listener is
required. Logging is synchronous, including disk writes and rollover, so it can
block application threads or an async event loop. Configure or replace loggers
before starting work rather than while other threads are emitting records.

The version is available from the imported logger module:

```python
from jacl4py import logger

print(logger.__version__)
```

For a release, edit only `__version__` in `jacl4py/__init__.py`. PDM reads that
constant for wheel and source-distribution metadata; `jacl4py.__version__` and
`jacl4py.logger.__version__` expose the same value.

## Development

This standalone repository targets Python 3.10 or newer. It is authored by
Fabian Krumm and distributed under the BSD 3-Clause License from the original
project.

Run the unit tests with uv:

```powershell
uv pip install -r requirements.txt
uv run --with-requirements requirements.txt python -m unittest discover -s tests -p "test_*.py"
```

Install development tools, including Pylint and coverage:

```powershell
uv pip install -r requirements-dev.txt
```

Run the same Pylint check as the push and pull request workflow:

```powershell
uv run --with-requirements requirements-dev.txt python -m pylint --jobs=1 jacl4py tests
```

Check test coverage, including branches and missing lines:

```powershell
uv run --with-requirements requirements-dev.txt python -m coverage run --branch --source=jacl4py -m unittest discover -s tests -p "test_*.py"
uv run --with-requirements requirements-dev.txt python -m coverage report -m
```

Build with:

```powershell
uv build
```

`requirements.txt` contains runtime-only dependencies and mirrors
`pyproject.toml` project dependencies. The workflows use it before tests, build,
and publication preflight; the requirements guard test detects drift, so update
both files together. PDM's declared build backend supplies `uv build` build
dependencies, while the generated wheel and source-distribution metadata causes
pip installs to resolve runtime dependencies automatically. The requirements
files are included in source distributions. `requirements-dev.txt` includes
the runtime requirements and adds development-only tools. PDM includes the package source and
test/workflow sources directly, so a `MANIFEST.in` file is unnecessary.

## Publishing

GitHub Actions discovers workflows only from the repository root's
`.github/workflows` directory; workflows nested under `logger-package` are not
run automatically in this monorepo. When this package is published from its own
repository, keep these workflow files at that repository root.

`pypi_publish.yml` runs on pushes to `master`, not GitHub Release publication. A
read-only build job runs preflight unit tests, builds wheel and sdist, checks
them with Twine, smoke-tests each installed artifact, and uploads the validated
distributions. Only then does the `pypi-release` environment job publish those
artifacts through PyPI Trusted Publishing (OIDC, no stored API token), with
`skip-existing: true`, `print-hash: false`, and `attestations: true`.

After successful publication, it creates an annotated `v<version>` tag from
`jacl4py/__init__.py`. An existing tag on the same commit is an idempotent no-op;
a tag on another commit is never moved and causes failure. Edit the local
version constant manually before a new release: neither tags nor commit messages
infer or automatically bump the version. PDM reads that constant for metadata.

Configure the PyPI trusted publisher for project `jacl4py`, your GitHub
owner/repository, workflow filename `pypi_publish.yml`, and environment `pypi-release`.
Keep that filename to preserve the trusted publisher identity and retain the
environment URL `https://pypi.org/project/jacl4py/`. Confirm project availability
and choose an unpublished version before pushing. Skipping existing files allows
retries; it does not permit replacing a published version.

Publication depends on its own build job, not a mandatory CI `needs` barrier.
Protect `master` with required supported-version tests, lint, build and workflow
audit checks; protect the environment with reviewers and branch restrictions.
Floating `3.x` probes are nonblocking, not support guarantees. CI runs Python
3.10-3.14 on five runners, reports coverage without a minimum, and uses Pylint
3.2.6 with the default fail-under of 10 and no disabled messages or custom
threshold. See [.github/CI.md](.github/CI.md) for the matrix, weekly
checks, reference differences, and repository settings.

# todos

## ai findings

- [ ] Medium (#6): Benchmark synchronous logging under representative load.
	Document an optional bounded queue/listener recipe only if needed, including
	overflow behavior and flushing at shutdown. UUID paths isolate writers but do
	not remove I/O latency.
- [ ] Medium (#7): Make intentionally disabled outputs silent with a
	`NullHandler`; track configuration independently of handler presence so
	Python's `lastResort` handler cannot unexpectedly emit to stderr.
- [ ] Medium (#8): Validate replacement settings and build handlers before
	invalidating the working logger. Finish cleanup if one handler fails to close,
	and consider an opt-in strict policy for required file logging.
- [ ] Medium (#9): Increment `stacklevel` in `iinfo()` and `idebug()` so caller
	metadata identifies application code rather than the wrapper.
- [ ] Medium (#10): Extend regression coverage for output silence, caller
	attribution, custom global logger factories, and file open/write/close
	failures; add branch coverage reporting in CI. High-severity regression tests
	have been added but still need execution.
- [ ] Medium (#11): Pin the PyPI publishing action to a reviewed commit; lock
	release tooling, automate dependency updates and vulnerability audits, and
	verify the release tag against built metadata. Keep consumer dependency ranges
	separate from release-tool reproducibility.
- [ ] Low (#12): Add real project/support URLs, tested Python classifiers,
	contribution and private security-reporting guidance, and a compatibility and
	deprecation policy. Expand privacy, permissions, and application integration
	guidance as the public API settles.
- [ ] Retention follow-up: Define opt-in cleanup of completed runs if total
	disk usage must be bounded. Per-writer rotation does not delete older UUID
	directories or file families; do not delete other writers' files implicitly.