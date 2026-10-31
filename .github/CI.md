# CI Support and Reference Alignment

These workflows assume this package is its own repository root. GitHub does not
discover them while nested in the parent workspace. Reference workflow/action
files in `reference-pookiepy`, not its potentially stale README, define the
comparison. This note records the original differences, implemented changes
and intentional deviations.

## Original Differences

- Local `test.yml` covered Python 3.10-3.14 on three desktop runners, with raw
  unittest discovery, no coverage report, ARM jobs or floating-Python probes.
  Reference `ci.yml` also has examples, integration and latest-Python jobs.
- Local `lint.yml` ran Python 3.14 Pylint directly, without a shared action or
  local rcfile. Development requirements used `pylint>=4,<5` alongside runtime
  requirements and coverage; reference mandatory lint pins `pylint==3.2.6`.
- Local jobs repeated setup/install commands and disabled uv caching; reference
  shares setup, dependency probing and check dispatch with CI caches enabled.
- Weekly latest-Python checks and actionlint/zizmor audits were absent. Reference
  additionally has weekly gRPC compatibility and installed CLI skeleton smoke.
- Local `build.yml` already ran tests, built and Twine-checked wheel/sdist,
  smoke-tested both installations and uploaded artifacts. Reference has no
  equivalent build workflow, but does have its framework CLI smoke workflow.
- Local publishing already separated read-only build validation from OIDC
  publication, retaining the package environment URL. Originally the workflow
  used a GitHub Release trigger, without skip-existing, hash controls or
  post-publish tagging, as its README described. Reference
  `pypi_publish.yml` uses one privileged job, master pushes and post-publish tags.
- Checkout, setup-python and setup-uv SHA pins already matched the reference.
  Standalone artifact upload/download actions were already SHA-pinned; the
  reference has no artifact handoff. PyPI already used exact release `v1.14.2`.
- Local publication used fixed Python 3.14; reference publishing uses `3.x`.
  Release build and tag setup now use `3.x`, without optional-probe failure policy.
- Dynamic, file-based PDM version metadata already matched the reference model;
  the standalone package has no framework protobuf build hook to preserve.

## Implemented Configuration and CI Contract

- `test.yml`: push/PR mandatory Python 3.10, 3.11, 3.12, 3.13 and 3.14 on
  `ubuntu-latest`, `windows-latest`, `macos-latest`, `ubuntu-22.04-arm` and
  `ubuntu-24.04-arm`. This core OS/Python matrix exactly matches the reference.
  Nonblocking `3.x` probes use the same five runners. Dependency-resolution
  failures warn and skip probe checks; actual check failures are reported.
- Core checks use `coverage run -m unittest discover -s tests -p "test_*.py"`
  followed by `coverage report -m`, exactly the reference gate, with no minimum.
  `coverage>=7.10,<8` is development tooling, not runtime metadata.
- `lint.yml`: Ubuntu / Python 3.14 runs `pylint --jobs=1 jacl4py tests`, using
  `pylint==4.0.10` from `requirements-dev.txt`, which includes runtime requirements.
  No diagnostics are disabled; default fail-under is 10, with no custom threshold.
- The compact `.pylintrc` preserves every effective reference setting, without
  comments. Only domain-specific entries are removed: the custom integration
  path in `init-hook`, generated protobuf ignore patterns/modules, grpc ignored
  classes, and `grpc`/`google` third-party classifications. The root import hook,
  `source-roots`, `ignore=third_party,interface`, optparse/thread ignored classes,
  empty settings and all other reference values remain. Configured `jobs=4`
  remains; the CI command overrides it to 1, just like the reference.
- `weekly-latest-python.yml`: Monday 12:00 UTC (`0 12 * * 1`) and manual runs,
  nonblocking `3.x` unit jobs on the same five runners, plus Ubuntu lint with
  latest Pylint, not the mandatory development pin, matching reference weekly.
- `verify-workflows.yml`: reference syntax/expression checks with actionlint and
  security audit with zizmor, on workflow/action/script changes and manual runs.
- Shared `setup-python`, `install-dependencies` and `python-check` actions use
  adapted `install_dependencies.py`, `run_checks.py` and `report_probe.py` helpers.
  Callers own matrices/policy; helpers omit grpc/proto/examples handling. The
  selected interpreter is passed through `UV_PYTHON`; the local project
  is installed for distribution-metadata tests. CI uv caches are enabled and
  keyed by suite, Python, OS and architecture; release caches stay disabled.
- Action pins follow the reference. PyPI publishing intentionally uses exact
  `pypa/gh-action-pypi-publish@v1.14.2`, with the same narrow zizmor unpinned-use
  suppression because its published container is tag-based. No API token is stored.

## Publication and Justified Deviations

`pypi_publish.yml` matches the configured PyPI trusted publisher identity. Pushes
to `master`, not GitHub Releases, start a read-only build job: preflight unit
tests, wheel/sdist build, Twine validation, isolated installed-artifact smoke
checks and validated artifact upload. Only its dependent publish job receives
OIDC and tag-write permissions, under environment `pypi-release` with URL
`https://pypi.org/project/jacl4py/`. It downloads the validated artifacts and uses
`verify-metadata: true`, `skip-existing: true`, `print-hash: false` and
`attestations: true`. Publication success precedes an annotated `v<version>` tag;
same-commit tags are no-ops, different-commit tags cause failure and are never moved.

- Two publication jobs deliberately retain least privilege and validated
  artifacts, instead of copying the reference's single privileged job.
- Pylint is pinned to 4.0.10, not reference 3.2.6, because Python 3.14 support
  was added in Pylint 4.0. See the [upstream release notes](https://pylint.readthedocs.io/en/latest/whatsnew/4/4.0/index.html).
  Applicable reference configuration and failure policy remain unchanged;
  diagnostic results can differ between Pylint major versions.
- `build.yml` remains an additional Ubuntu / Python 3.14 gate. Reference CLI
  skeleton smoke covers 3.10/3.14/3.x on three desktop OSes, but tests installed
  pookiepy skeleton generation, which this package does not provide. Package
  wheel/sdist smoke checks are retained, not claimed as literal CLI matrix parity.
- Weekly gRPC, protobuf generation, examples, framework integration and CLI
  suites/dependencies are excluded because they are absent here. No fake suites
  or dependencies are added. Core supported-version matrix parity is unchanged.
- Existing `test.yml`, `lint.yml` and `build.yml` identities remain
  instead of merging into reference `ci.yml`, reducing branch-protection
  migration. Check job display names may change; review required status contexts.
- Publication has no full-matrix CI `needs` barrier, matching the reference;
  only its own validated build is a dependency. Configure external controls below.
- `jacl4py/__init__.py` remains the authoritative manually edited version source.
  PDM dynamic metadata needs no backend change or version bump. Tags are outputs;
  there is no automatic bump or semantic-version inference from commit messages.
- Source distributions retain their existing CI-source inclusion policy, now
  including all of `.github/` and `.pylintrc`, so workflows do not ship without
  their new helpers. Unlike the reference, CI sources were already included here.
- Tag extraction uses uv and the selected interpreter, rather than bare Python,
  consistent with the standalone tooling; version parsing and tag policy match.

## External Settings and Validation

Configure the PyPI publisher with the actual GitHub owner/repository,
`pypi_publish.yml` and `pypi-release`; verify project availability and use unpublished
versions. Skipping existing files supports retries, not artifact replacement.
Protect `master` with mandatory supported-version test, lint and build checks.
The path-filtered workflow audit should not be universally required unless your
ruleset handles skipped workflows, or unrelated PRs can wait indefinitely.
Configure environment reviewers, allowed release branches,
and tag rules that allow the release bot to create, but not move, release tags.
Grant repository Actions the tag-write permission required by publication.
Floating-Python and weekly probes should not be required checks.

Some editor/actionlint versions cannot resolve the reference's `$/...` local
action syntax, especially in this nested workspace. Paths are relative to each
standalone repository root. The audit workflow retains the reference's narrow
actionlint compatibility filter; no security findings are filtered out.

No tests or linters were run for these configuration/documentation changes.
Reference-setting comparison is not evidence that package code passes Pylint.
Local verification parsed all nine workflow/action YAML files, Python helpers,
embedded shell commands, TOML and INI configuration. Reference matrices, release
options and permissions were compared structurally. `uv build` successfully
built the sdist and a wheel from it; the sdist includes CI helpers and `.pylintrc`.
Actual runner behavior, installed-artifact smoke checks, actionlint, zizmor and
PyPI/OIDC publication still require GitHub Actions validation.

## Patch Summary

| File | Change |
| --- | --- |
| `.github/workflows/test.yml` | Add ARM, coverage dispatch and nonblocking latest-Python probes. |
| `.github/workflows/lint.yml` | Shared pinned-Python lint action and development requirements. |
| `.github/workflows/build.yml` | Shared setup; preserve preflight, build, metadata and artifact smoke gates. |
| `.github/workflows/pypi_publish.yml` | Master pushes, latest stable Python, reference publish options, tag after publish. |
| `.github/workflows/weekly-latest-python.yml` | Add reference weekly/manual latest-Python unit and lint probes. |
| `.github/workflows/verify-workflows.yml` | Add reference syntax and security audits. |
| `.github/actions/setup-python/action.yml` | Shared pinned tooling, interpreter output and cache policy. |
| `.github/actions/install-dependencies/action.yml` | Shared installation and nonblocking dependency probe. |
| `.github/actions/python-check/action.yml` | Shared setup, local package installation and check dispatch. |
| `.github/scripts/install_dependencies.py` | One dependency command for installation and dry-run probes. |
| `.github/scripts/run_checks.py` | Coverage/unit and serial Pylint execution. |
| `.github/scripts/report_probe.py` | Warnings and job summaries for skipped/failed probes. |
| `.github/scripts/tag_release.sh` | Annotated version tags; same-commit retry; refuse tag movement. |
| `.github/CI.md` | Differences, deviations, validation, external setup and this inventory. |
| `.pylintrc` | Applicable reference lint configuration without framework exclusions. |
| `requirements-dev.txt` | Supported, fixed Pylint pin; retain coverage and runtime requirements. |
| `pyproject.toml` | Include complete CI sources and lint configuration in sdists. |
| `README.md` | Correct release lifecycle, quality checks and version-management instructions. |