# Agent workflow guide

This file is the canonical workflow guide for coding agents working in this
repository.

## Workflow

- Use GitHub Flow and branch from the latest `main`.
- Name work branches `feature/<issue-number>-<short-slug>`.
- Keep each pull request scoped to one issue.
- Do not revert unrelated changes or delete untracked files.
- Use Conventional Commits for commits and pull request titles.
- Link pull requests with `Closes #<issue>` or `Refs #<issue>`.
- Use squash merge by default unless the operator requests another method.

## Manifest policy

- Publish stable upstream tt-metal releases only. Prereleases require an
  explicit policy decision and must not silently become the current release.
- Use the upstream version without its leading `v` as both the release filename
  and the manifest's `release` value.
- Pin downloadable artifacts by SHA-256 and container images by immutable
  `sha256:` digest. Never publish `latest` or another mutable tag.
- Record upstream provenance in `docs/compatibility.md`.
- Distinguish schema validation from installation and hardware validation.
- Never execute or source OS manifest files; validation must use the restricted
  parser in `scripts/validate.py`.

## Validation

Run before opening a pull request:

```bash
# Remove --allow-empty after the initial catalog entries are published.
python3 scripts/validate.py --allow-empty
python3 -m unittest discover -s tests -v
```

Do not add new validation dependencies unless the task requires them.
