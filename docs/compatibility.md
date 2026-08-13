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

## Stack releases

The upstream tt-metal release table at commit
[`d92d211`](https://github.com/tenstorrent/tt-metal/blob/d92d2113baeb140ed4e6b7a6665aaf8756f95df2/README.md#latest-releases)
records firmware `19.2.0`, KMD `2.5.0`, and TT-SMI `3.0.38` for `v0.67.0`,
`v0.67.4`, and `v0.68.0`. The release manifests preserve those component
versions. GitHub's official release and package APIs were queried on 2026-08-13
to verify stable release status, archive checksums, image tags, and immutable
image digests.

These historical entries intentionally leave `system_packages` and
`python_packages` empty because the cited upstream sources do not establish the
complete package pins required by tt-env-go. Consequently, tt-env-go's normal
pinned Ubuntu `USE_SYSTEM_PACKAGES=true` installation plan currently rejects
these entries before installation; their catalog and immutable container
metadata remain available. This is a known consumer limitation, not merely
missing install or hardware test evidence. Package pins must not be inferred
from component compatibility versions.

### tt-metal v0.67.0 (`releases/0.67.0.json`)

- **Upstream release:** [GitHub Release](https://github.com/tenstorrent/tt-metal/releases/tag/v0.67.0),
  published 2026-03-21. The official
  [release API](https://api.github.com/repos/tenstorrent/tt-metal/releases/tags/v0.67.0)
  reports `tt-metalium.tar.gz` SHA-256
  `5c3ef352c6fab65576144fbf00893a846e009b553fc35d99c977e0c680477919`.
- **Container provenance:** Official GHCR package versions pin tag `v0.67.0`
  for the [Ubuntu 24.04 runtime](https://github.com/orgs/tenstorrent/packages/container/tt-metal%2Ftt-metalium-ubuntu-24.04-release-amd64/749903197)
  at digest `sha256:39f92aa795c28b1836947300d6556c7e3a7ccdba12e9aa60b3ad3be05df2e5c8`
  and the [Ubuntu 22.04 models image](https://github.com/orgs/tenstorrent/packages/container/tt-metal%2Ftt-metalium-ubuntu-22.04-release-models-amd64/749925506)
  at digest `sha256:df7c675f80c4adc8bfd97d9a0da18b2ea86542c903bade2d71f7a9e8f9092fd8`.
- **Validation:** Catalog/schema validated. No installation or hardware
  validation was performed in this repository.

### tt-metal v0.67.4 (`releases/0.67.4.json`)

- **Upstream release:** [GitHub Release](https://github.com/tenstorrent/tt-metal/releases/tag/v0.67.4),
  published 2026-03-28. The official
  [release API](https://api.github.com/repos/tenstorrent/tt-metal/releases/tags/v0.67.4)
  reports `tt-metalium.tar.gz` SHA-256
  `ae3964dfd1c454fb7cfcd52bd521e703b7b6083ca363d748a3d5d74eb1123408`.
- **Container provenance:** Official GHCR package versions pin tag `v0.67.4`
  for the [Ubuntu 24.04 runtime](https://github.com/orgs/tenstorrent/packages/container/tt-metal%2Ftt-metalium-ubuntu-24.04-release-amd64/763862109)
  at digest `sha256:2cc5bcf40755597bde650980be6d15fa6898f2f19ce712fd1074e6d2c5201581`
  and the [Ubuntu 22.04 models image](https://github.com/orgs/tenstorrent/packages/container/tt-metal%2Ftt-metalium-ubuntu-22.04-release-models-amd64/763883651)
  at digest `sha256:05c568161f72bd4b64e77ab6fb0ea51110ef12b2d1b6df557c698bc1fb54ed3e`.
- **Validation:** Catalog/schema validated. No installation or hardware
  validation was performed in this repository.

### tt-metal v0.68.0 (`releases/0.68.0.json`)

- **Upstream release:** [GitHub Release](https://github.com/tenstorrent/tt-metal/releases/tag/v0.68.0),
  published 2026-04-11. The official
  [release API](https://api.github.com/repos/tenstorrent/tt-metal/releases/tags/v0.68.0)
  reports `tt-metalium.tar.gz` SHA-256
  `ae9d041fec2acc4be7de455f57873047772f06624f18f6074bf7e3a5e429a67b`.
- **Container provenance:** Official GHCR package versions pin tag `v0.68.0`
  for the [Ubuntu 24.04 runtime](https://github.com/orgs/tenstorrent/packages/container/tt-metal%2Ftt-metalium-ubuntu-24.04-release-amd64/789552822)
  at digest `sha256:1d811ad04e5d212ebe6436edfbfde979d43c5fa7600880baad8b2059b9c1510b`
  and the [Ubuntu 22.04 models image](https://github.com/orgs/tenstorrent/packages/container/tt-metal%2Ftt-metalium-ubuntu-22.04-release-models-amd64/789610716)
  at digest `sha256:be2275a89d4209be0f42d91081b851acfd3ac0938fe5ce035997da0eda8ba2f4`.
- **Validation:** Catalog/schema validated. No installation or hardware
  validation was performed in this repository.

For the following releases, the exact tagged source's `INSTALLING.md` pins the
same installer arguments: KMD `2.5.0`, firmware `19.2.0`, and TT-SMI
`v3.0.38`. GitHub's official release and package APIs were queried on
2026-08-13 to verify release status, archive checksums, image tags, and image
digests. Releases `v0.70.0` and `v0.71.1` are explicitly marked prerelease by
the upstream API and are excluded from this stable catalog.

### tt-metal v0.69.0 (`releases/0.69.0.json`)

- **Upstream release:** [GitHub Release](https://github.com/tenstorrent/tt-metal/releases/tag/v0.69.0),
  published 2026-05-04. The official
  [release API](https://api.github.com/repos/tenstorrent/tt-metal/releases/tags/v0.69.0)
  reports `tt-metalium.tar.gz` SHA-256
  `83a930938b2e532fff494f5981adc9133fb40abd107819f7e739d4c48548feef`.
- **Compatibility provenance:** The exact release commit's
  [`INSTALLING.md`](https://github.com/tenstorrent/tt-metal/blob/cf7232ab47227167f091c3c3cf6fdbed63c8b51c/INSTALLING.md#option-1-tt-installer-script-recommended)
  supplies the recorded KMD, firmware, and TT-SMI installer versions.
- **Container provenance:** Official GHCR versions pin tag `v0.69.0` for the
  [Ubuntu 24.04 runtime](https://github.com/orgs/tenstorrent/packages/container/tt-metal%2Ftt-metalium-ubuntu-24.04-release-amd64/839471194)
  at `sha256:7598666e0b099e5a2cd77f5e579c2ed2f2c6f514cf3013eb25c2c5ff1b3f7b19`
  and the [Ubuntu 22.04 models image](https://github.com/orgs/tenstorrent/packages/container/tt-metal%2Ftt-metalium-ubuntu-22.04-release-models-amd64/839504506)
  at `sha256:48d938159be63b73cffe16f0cef116ff7dff1334e956f288ea8b55d38bf96c8d`.
- **Validation:** Catalog/schema validated. No installation or hardware
  validation was performed; the package-pin limitation above applies.

### tt-metal v0.70.1 (`releases/0.70.1.json`)

- **Upstream release:** [GitHub Release](https://github.com/tenstorrent/tt-metal/releases/tag/v0.70.1),
  published 2026-05-15. The official
  [release API](https://api.github.com/repos/tenstorrent/tt-metal/releases/tags/v0.70.1)
  reports `tt-metalium.tar.gz` SHA-256
  `07d60a7a4b48eb2f46540a2a15941adcd07ac91e337cfdb762bbb019baa11a4e`.
- **Compatibility provenance:** The exact release commit's
  [`INSTALLING.md`](https://github.com/tenstorrent/tt-metal/blob/80180b9d7d07ea9fcc99f723d4d46fe7a0b233bd/INSTALLING.md#option-1-tt-installer-script-recommended)
  supplies the recorded KMD, firmware, and TT-SMI installer versions.
- **Container provenance:** Official GHCR versions pin tag `v0.70.1` for the
  [Ubuntu 24.04 runtime](https://github.com/orgs/tenstorrent/packages/container/tt-metal%2Ftt-metalium-ubuntu-24.04-release-amd64/867005919)
  at `sha256:ead7b800bdb6bebb9425c377222314447c5b2052f6e8b1e3c9caa1818cb7d8c4`
  and the [Ubuntu 22.04 models image](https://github.com/orgs/tenstorrent/packages/container/tt-metal%2Ftt-metalium-ubuntu-22.04-release-models-amd64/867061499)
  at `sha256:02151bea82bc345afe6171b72d9232332d90699f550e6c5b35a645fa19569b3e`.
- **Validation:** Catalog/schema validated. No installation or hardware
  validation was performed; the package-pin limitation above applies.

### tt-metal v0.71.2 (`releases/0.71.2.json`)

- **Upstream release:** [GitHub Release](https://github.com/tenstorrent/tt-metal/releases/tag/v0.71.2),
  published 2026-05-28. The official
  [release API](https://api.github.com/repos/tenstorrent/tt-metal/releases/tags/v0.71.2)
  reports `tt-metalium.tar.gz` SHA-256
  `5c88b0ca14cb68bcb2e458bb8ad16aa83d6357f41f12f4b65026bf342dd755a1`.
- **Compatibility provenance:** The exact release commit's
  [`INSTALLING.md`](https://github.com/tenstorrent/tt-metal/blob/25891d3d9b7350752f18189ea1fe5620de2cf518/INSTALLING.md#option-1-tt-installer-script-recommended)
  supplies the recorded KMD, firmware, and TT-SMI installer versions.
- **Container provenance:** Official GHCR versions pin tag `v0.71.2` for the
  [Ubuntu 24.04 runtime](https://github.com/orgs/tenstorrent/packages/container/tt-metal%2Ftt-metalium-ubuntu-24.04-release-amd64/899769548)
  at `sha256:8e32440a458bcff3b804916ddd917d22532594b72696b5bc1618bf0eec7a9274`
  and the [Ubuntu 22.04 models image](https://github.com/orgs/tenstorrent/packages/container/tt-metal%2Ftt-metalium-ubuntu-22.04-release-models-amd64/899844130)
  at `sha256:788e877ae073bb7dd933d997e9ae5dc0bddd7227f7ebb14baf4f4b44709d14ee`.
- **Validation:** Catalog/schema validated. No installation or hardware
  validation was performed; the package-pin limitation above applies.

### tt-metal v0.72.0 (`releases/0.72.0.json`)

- **Upstream release:** [GitHub Release](https://github.com/tenstorrent/tt-metal/releases/tag/v0.72.0),
  published 2026-06-09. The official
  [release API](https://api.github.com/repos/tenstorrent/tt-metal/releases/tags/v0.72.0)
  reports `tt-metalium.tar.gz` SHA-256
  `b1537186de0184f6701233ec7ea3ed3e6ea3390f1b37fe37b8c6f728c89a8c20`.
- **Compatibility provenance:** The exact release commit's
  [`INSTALLING.md`](https://github.com/tenstorrent/tt-metal/blob/ba9340e3a45ac5ba51c752a49341f2def28d0514/INSTALLING.md#option-1-tt-installer-script-recommended)
  supplies the recorded KMD, firmware, and TT-SMI installer versions.
- **Container provenance:** Official GHCR versions pin tag `v0.72.0` for the
  [Ubuntu 24.04 runtime](https://github.com/orgs/tenstorrent/packages/container/tt-metal%2Ftt-metalium-ubuntu-24.04-release-amd64/927646942)
  at `sha256:44d92ec1ce77b9ba7f11a76630b3a2a046879565f5f9fb1a185b70a3e86010bb`
  and the [Ubuntu 22.04 models image](https://github.com/orgs/tenstorrent/packages/container/tt-metal%2Ftt-metalium-ubuntu-22.04-release-models-amd64/927669495)
  at `sha256:39f400743f061ba29a43e2cfee7f0b5b6ed7345da6b55f7f04ff16f7430fd5c5`.
- **Validation:** Catalog/schema validated. No installation or hardware
  validation was performed; the package-pin limitation above applies.

The initial catalog will continue through stable upstream tt-metal `v0.75.0`.
Release-specific provenance and validation results are added with each entry.
