# Contributing

Manifest changes use GitHub Issues and pull requests.

## Release manifests

1. Start from an upstream stable tt-metal GitHub Release.
2. Use its version without the leading `v`, for example `releases/0.75.0.json`.
3. Pin every artifact checksum and container digest to immutable values.
4. Add the upstream release URL and evidence to `docs/compatibility.md`.
5. State which validation was performed. Do not describe schema-only validation
   as installation or hardware validation.

## OS manifests

OS manifests are data in a deliberately restricted shell-like grammar. They
must never contain or execute shell expansions, commands, redirects, or
substitutions. See `docs/manifest-format.md` for accepted syntax.

## Checks

```bash
python3 scripts/validate.py
python3 -m unittest discover -s tests -v
```
