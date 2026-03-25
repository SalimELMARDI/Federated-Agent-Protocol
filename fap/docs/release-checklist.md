# Release Checklist

Use this checklist before cutting the first public alpha release.

## Repo And Packaging

- [ ] `pyproject.toml` reflects the alpha release version and current dependency surface
- [ ] misleading or unused runtime dependency claims are removed
- [ ] root `README.md` is updated and matches the actual runtime
- [ ] `CHANGELOG.md` exists and includes the first alpha entry
- [ ] `LICENSE` exists
- [ ] release note draft exists

## Runtime And Docs

- [ ] demo scenario docs point to the current scripts and endpoints
- [ ] `spec/` docs do not obviously contradict the active runtime
- [ ] alpha limitations are stated explicitly
- [ ] no misleading production-stable language remains
- [ ] no misleading Flower/runtime substrate claims remain

## Verification

- [ ] `python -m pytest`
- [ ] `python -m ruff check .`
- [ ] `python -m mypy apps packages tests`
- [ ] package imports work for:
  - `fap_core`
  - `fap_client`
  - `fap_mcp`
- [ ] demo artifacts are present and readable

## Suggested Extra Validation

- [ ] install with `python -m pip install -e .`
- [ ] contributor install with `python -m pip install -e ".[dev]"`
- [ ] demo scenario works from a clean local setup
- [ ] `/ask`, `fap_client`, and `fap_mcp` example paths still behave as documented

## Public Positioning Check

Before release, confirm the project is presented as:

- protocol alpha
- reference runtime
- developer preview
- not yet production stable
