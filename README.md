# tt-env-manifests

Official public manifest catalog for
[`tt-env`](https://github.com/tetsuh/tt-env-go), an environment manager for the
Tenstorrent software stack.

## Layout

- `releases/<version>.json` — version-pinned stack manifests
- `manifests/<os_id>-<os_version>.env` — OS package mappings
- `docs/manifest-format.md` — manifest contracts
- `docs/compatibility.md` — release provenance and validation status

The initial catalog targets stable tt-metal releases from `v0.67.0` (March
2026) onward. The leading `v` is omitted from catalog release identifiers and
filenames.

## Validation

```bash
python3 scripts/validate.py
python3 -m unittest discover -s tests -v
```

Validation checks data shape, immutable pins, filename consistency, and the
restricted OS manifest grammar. It does not prove that a release installs or
runs successfully on Tenstorrent hardware; those results are tracked separately
in [`docs/compatibility.md`](docs/compatibility.md).

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md) and [`AGENTS.md`](AGENTS.md).

## License

Apache License 2.0 — see [`LICENSE`](LICENSE).
