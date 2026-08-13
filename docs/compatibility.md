# Compatibility and provenance

This document records where each catalog entry came from and how it was
validated.

## Validation levels

- **Catalog validated**: filename, schema, restricted OS grammar, and immutable
  pins pass automated checks.
- **Install validated**: `tt-env install` completed on the listed OS and
  architecture.
- **Hardware validated**: representative workloads completed on the listed
  Tenstorrent hardware.

Catalog validation does not imply install or hardware validation.

## OS manifests

### Ubuntu 22.04 (`manifests/ubuntu-22.04.env`)

- **Provenance:** Official Tenstorrent APT repository documentation at
  <https://ppa.tenstorrent.com/> states the signed source
  `https://ppa.tenstorrent.com/ubuntu/` with a `jammy` source line and lists
  Ubuntu 22.04 compatibility. The manifest supplies the base URL unchanged to
  tt-env-go's native repository adapter; actual consumer repository
  configuration and installation remain unvalidated here.
- **Repository metadata:** The jammy `Release` index was fetched on 2026-08-12
  (date `Wed, 12 Aug 2026 12:32:22 UTC`, SHA-256
  `12d8efac93eb95fa875795ca13c087108cb59e8a1abe08782c87841e3baddd3d`); its
  `Packages.gz` SHA-256 is
  `d7712087618331412aa45afaf9a50079d598e47b789db171cbf2c60bf3632de9`.
  Decoded amd64 metadata contains `tenstorrent-dkms`, `tt-smi`, `tt-flash`,
  `tt-topology`, and `tt-metalium`.
- **Validation:** Catalog/schema validated. No installation or hardware
  validation was performed in this repository.

### Ubuntu 24.04 (`manifests/ubuntu-24.04.env`)

- **Provenance:** The same official source documentation describes a `noble`
  source line and states Ubuntu 24.04 compatibility. The manifest supplies the
  base URL unchanged to tt-env-go's native repository adapter; actual consumer
  repository configuration and installation remain unvalidated here.
- **Repository metadata:** The noble `Release` index was fetched on 2026-08-12
  (date `Wed, 12 Aug 2026 12:31:40 UTC`, SHA-256
  `7f677f1e2638f9d7a3b5509d7ca2103607762c212e5c7934071729c6f5c9690d`); its
  `Packages.gz` SHA-256 is
  `8792e615fe8783bb27f0a9a0191d5f3f1f50f01fa9c48f83e1028238cb49a843`.
  Decoded amd64 metadata contains the same five Tenstorrent package names.
- **Validation:** Catalog/schema validated. No installation or hardware
  validation was performed in this repository.

The generic mappings `cmake`, `ninja-build`, and `zlib1g-dev` use the Ubuntu
package names documented for jammy and noble at <https://packages.ubuntu.com/>.
The manifest values are consumer mappings only; repository signing, package
installation, and hardware compatibility remain separate validation stages.
The signed jammy/noble source-line behavior is upstream documentation, not
codename construction or resolution currently implemented by tt-env-go.

## Initial release range

The initial catalog will cover stable upstream tt-metal releases from `v0.67.0`
through `v0.75.0`. Release-specific provenance and validation results will be
added with each release manifest.
