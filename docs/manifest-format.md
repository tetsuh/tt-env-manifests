# Manifest format

## Stack release manifests

Stack manifests live at `releases/<version>.json`. The filename stem must equal
the top-level `release` field and must be a stable semantic version without a
leading `v`.

Required top-level objects:

- `components`: logical stack component versions
- `system_packages`: virtual system-package version pins
- `python_packages`: Python package version pins
- `git_components`: repositories pinned to a tag or commit
- `container_components`: image aliases or images pinned by digest

A component is either a version string or an object containing `version`,
`download_url`, and a 64-character hexadecimal `sha256`. A container entry is
either `{ "ref": "other-name" }` or an `image_url` paired with an immutable
`sha256:<64 lowercase hex>` `image_tag`.

Unknown fields are rejected by the catalog validator even if an older tt-env
client would ignore them.

## OS manifests

OS manifests live at `manifests/<os_id>-<os_version>.env`. They are parsed as
data and are never sourced.

Accepted lines are limited to:

```text
KEY="safe-value"
KEY=()
KEY=("value" "other-value")
KEY=(
  "value"
)
```

Blank lines and comments beginning with `#` are allowed. Variable expansion,
command substitution, semicolons, backticks, backslashes, redirects, and other
shell syntax are rejected.

Every OS manifest must define:

- `PKG_MANAGER`
- `USE_SYSTEM_PACKAGES`
- `REQUIRED_REPOS`
- `WORKAROUNDS`
- virtual mappings for `CMAKE`, `NINJA`, `ZLIB`, `KMD`, `SMI`, `FLASH`,
  `TOPOLOGY`, and `METALIUM`
