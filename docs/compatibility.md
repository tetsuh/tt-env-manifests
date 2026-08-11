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

## Initial release range

The initial catalog will cover stable upstream tt-metal releases from `v0.67.0`
through `v0.75.0`. Release-specific provenance and validation results will be
added with each release manifest.
