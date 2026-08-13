# Manifest format

## Stack release manifests

Stack manifests live at `releases/<version>.json`. Each release filename must
be `<release>.json`; its stem and top-level `release` value must be the same
stable semantic version without a leading `v` (for example, `0.75.0.json`).
Prerelease versions are not catalog entries. Release JSON files must be UTF-8
and must not contain duplicate object keys; duplicate keys are rejected rather
than silently overwritten.

A release object must contain exactly these seven top-level fields:

- `release`: the stable semantic version without `v`.
- `description`: a non-empty description string.
- `components`: component versions. Every component, including `tt-metal`, is
  either a non-empty version string or an object containing exactly `version`,
  `download_url`, and `sha256`. Object downloads use a 64-character
  hexadecimal SHA-256 digest. Regardless of representation, the effective
  version of the required `tt-metal` component must be exactly `v<release>`.
- `system_packages`: an object whose package names use lowercase letters,
  digits, `.`, `_`, and `-`, and whose versions are non-empty strings.
- `python_packages`: an object whose package names use letters, digits, `.`,
  `_`, and `-`, and whose versions are non-empty strings.
- `git_components`: an object of entries containing exactly `url` and
  `version`, with a non-empty version.
- `container_components`: an object of named image entries. An entry is either
  `{ "ref": "other-name" }`, referring to another entry, or an object
  containing exactly `image_url` and `image_tag`.

Unknown fields are rejected. Component, package, git-component, and container
component names must begin with a letter or digit and then contain only
letters, digits, `.`, `_`, and `-`.

### URLs and pins

Every artifact `download_url` and git-component `url` must be an absolute
HTTPS URL with a host. The validator rejects all Unicode `Cc` control
characters and whitespace, credentials, fragments, malformed percent
encoding, invalid authorities, and invalid ports (ports must be between 0 and
65535). Hostnames are RFC reg-name characters (with valid percent escapes) or
valid bracketed IPv6 addresses. No broader path restrictions are imposed.

Container images are immutable: `image_tag` must be exactly
`sha256:<64 lowercase hexadecimal digits>`. An `image_url` must begin with
`ghcr.io/` and contain one or more non-empty lowercase repository components,
using the Docker/OCI repository grammar.
Each component consists of lowercase alphanumeric runs separated only by a
single dot, one or two underscores, or one or more hyphens; every separator
must be followed by another alphanumeric run. A `{ "ref": ... }` target must
exist, cannot refer to itself, and all references must be acyclic.

## OS manifests

OS manifests live at `manifests/<os_id>-<os_version>.env`. The filename is
validated as follows: `<os_id>` is lowercase ASCII, starts and ends with an
alphanumeric character, and may contain lowercase letters, digits, `_`, and
`-` inside; `<os_version>` starts with a digit, ends with an alphanumeric
character, and may contain lowercase letters, digits, `.`, `_`, and `-` inside.
Interior adjacent separators are allowed. OS files must contain ASCII text, and each pre-LF record must be shorter than
65,536 bytes, matching the default record limit of tt-env-go's `bufio.Scanner`.
The total OS-manifest input is also limited to 1 MiB (1,048,576 bytes); the
validator reads at most one byte beyond that bound before decoding. CRLF is
accepted; other control separators are rejected. Files are parsed as
data and never sourced or executed.

Accepted lines are limited to:

```text
KEY="safe-value"
KEY=()
KEY=("value" "other-value")
KEY=(
  "value"
)
```

Every array element must be a double-quoted string. Blank lines and comments
beginning with `#` are allowed. Keys use uppercase ASCII letters, digits, and
underscores; scalar values are limited to letters, digits, `_`, `.`, `/`, `:`,
`+`, and `-`. Variable expansion, command substitution, semicolons,
backticks, backslashes, redirects, and other shell syntax are rejected.

Every OS manifest must define these scalar fields:

- `PKG_MANAGER`, whose value is `apt` or `dnf`;
- `USE_SYSTEM_PACKAGES`, whose value is `true` or `false`;
- `VIRT_PKG_CMAKE`, `VIRT_PKG_NINJA`, `VIRT_PKG_ZLIB`, `VIRT_PKG_KMD`,
  `VIRT_PKG_SMI`, `VIRT_PKG_FLASH`, `VIRT_PKG_TOPOLOGY`, and
  `VIRT_PKG_METALIUM`. Every virtual mapping must be non-empty. `tt-env-go`
  resolves these names in stack-policy order before installing system packages;
  the concrete values are package-manager package names.

It must also define the arrays `REQUIRED_REPOS` and `WORKAROUNDS`. Each
`REQUIRED_REPOS` entry is a non-empty absolute HTTPS URL validated with the
catalog's strict URL rules, and duplicate repository entries are rejected.
An empty `REQUIRED_REPOS=()` is valid for a distro-native catalog that needs no
additional repository. `tt-env-go` passes non-empty entries to its native
repository adapter before package metadata refresh; this catalog does not
execute that installation step. Duplicate keys, unterminated arrays, malformed
lines, missing required fields, and unsafe values are rejected. This parser
performs schema and manifest-semantic validation only; it does not install
packages or validate hardware compatibility.
