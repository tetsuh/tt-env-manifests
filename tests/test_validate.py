import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "catalog_validate", Path(__file__).parents[1] / "scripts" / "validate.py"
)
validate = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(validate)


class CatalogValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "releases").mkdir()
        (self.root / "manifests").mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def valid_release(self):
        return {
            "release": "0.75.0",
            "description": "test release",
            "components": {"tt-metal": "v0.75.0"},
            "system_packages": {},
            "python_packages": {},
            "git_components": {},
            "container_components": {
                "image": {
                    "image_url": "ghcr.io/example/image",
                    "image_tag": "sha256:" + "a" * 64,
                },
                "default": {"ref": "image"},
            },
        }

    def valid_os_manifest(self):
        return """PKG_MANAGER="apt"
USE_SYSTEM_PACKAGES="true"
REQUIRED_REPOS=("https://example.com/repo/")
VIRT_PKG_CMAKE="cmake"
VIRT_PKG_NINJA="ninja-build"
VIRT_PKG_ZLIB="zlib1g-dev"
VIRT_PKG_KMD="tenstorrent-dkms"
VIRT_PKG_SMI="tt-smi"
VIRT_PKG_FLASH="tt-flash"
VIRT_PKG_TOPOLOGY="tt-topology"
VIRT_PKG_METALIUM="tt-metalium"
WORKAROUNDS=()
"""

    def write_release(self, name="0.75.0.json", value=None):
        path = self.root / "releases" / name
        path.write_text(json.dumps(value or self.valid_release()), encoding="utf-8")
        return path

    def write_os_manifest(self, value=None, name="ubuntu-24.04.env"):
        path = self.root / "manifests" / name
        path.write_text(value or self.valid_os_manifest(), encoding="utf-8")
        return path

    def test_valid_catalog(self):
        self.write_release()
        self.write_os_manifest()
        self.assertEqual(validate.validate_catalog(self.root), [])

    def test_release_filename_must_match(self):
        self.write_release("0.74.0.json")
        errors = validate.validate_catalog(self.root)
        self.assertTrue(any("does not match release" in error for error in errors))

    def test_tt_metal_version_must_match_release(self):
        value = self.valid_release()
        value["components"]["tt-metal"] = "v0.74.0"
        self.write_release(value=value)
        errors = validate.validate_catalog(self.root)
        self.assertTrue(any("tt-metal component" in error for error in errors))

    def test_release_rejects_leading_zero_version(self):
        value = self.valid_release()
        value["release"] = "00.75.0"
        value["components"]["tt-metal"] = "v00.75.0"
        self.write_release("00.75.0.json", value)
        errors = validate.validate_catalog(self.root)
        self.assertTrue(any("stable semantic version" in error for error in errors))

    def test_release_rejects_consumer_incompatible_name(self):
        value = self.valid_release()
        value["git_components"]["bad+name"] = {
            "url": "https://example.com/repo.git",
            "version": "abc123",
        }
        self.write_release(value=value)
        errors = validate.validate_catalog(self.root)
        self.assertTrue(any("invalid git component name" in error for error in errors))

    def test_release_rejects_mutable_container_tag(self):
        value = self.valid_release()
        value["container_components"]["image"]["image_tag"] = "latest"
        self.write_release(value=value)
        errors = validate.validate_catalog(self.root)
        self.assertTrue(any("immutable sha256 digest" in error for error in errors))

    def test_release_rejects_unknown_field(self):
        value = self.valid_release()
        value["unexpected"] = True
        self.write_release(value=value)
        errors = validate.validate_catalog(self.root)
        self.assertTrue(any("unknown field" in error for error in errors))

    def test_release_rejects_strict_url_syntax(self):
        invalid_urls = (
            "https://example.com/file with-space",
            "https://example.com/file%ZZ",
            "https://example.com:bad/file",
            "https://example.com:/file",
            "https://example.com:99999/file",
            "https://user:pass@example.com/file",
            "https://example.com/file#fragment",
        )
        for url in invalid_urls:
            with self.subTest(url=url):
                value = self.valid_release()
                value["components"]["download"] = {
                    "version": "1.0.0",
                    "download_url": url,
                    "sha256": "a" * 64,
                }
                self.write_release(value=value)
                errors = validate.validate_catalog(self.root)
                self.assertTrue(errors, url)

    def test_release_rejects_invalid_utf8(self):
        path = self.root / "releases" / "0.75.0.json"
        path.write_bytes(b"\xff")
        errors = validate.validate_catalog(self.root)
        self.assertTrue(any("invalid JSON" in error for error in errors))

    def test_os_manifest_filename_must_match_contract(self):
        for name in (
            "Ubuntu-24.04.env",
            "-24.04.env",
            "ubuntu-version.env",
            "ubuntu-24@04.env",
            "ubuntu--24.04.env",
            "ubuntu-24.04-.env",
        ):
            with self.subTest(name=name):
                self.write_os_manifest(name=name)
                errors = validate.validate_catalog(self.root, allow_empty=True)
                self.assertTrue(any("filename must match" in error for error in errors))

    def test_os_manifest_accepts_planned_filenames(self):
        for name in ("ubuntu-22.04.env", "ubuntu-24.04.env", "linuxmint-22.1.env", "rocky__linux-9.env"):
            with self.subTest(name=name):
                self.write_os_manifest(name=name)
                self.assertEqual(validate.validate_catalog(self.root, allow_empty=True), [])

    def test_os_manifest_rejects_unquoted_inline_array_item(self):
        value = self.valid_os_manifest().replace(
            'REQUIRED_REPOS=("https://example.com/repo/")',
            "REQUIRED_REPOS=(https://example.com/repo/)",
        )
        self.write_os_manifest(value)
        errors = validate.validate_catalog(self.root)
        self.assertTrue(any("invalid array item" in error for error in errors))

    def test_os_manifest_rejects_unquoted_multiline_array_item(self):
        value = self.valid_os_manifest().replace(
            'REQUIRED_REPOS=("https://example.com/repo/")',
            'REQUIRED_REPOS=(\n  https://example.com/repo/\n)',
        )
        self.write_os_manifest(value)
        errors = validate.validate_catalog(self.root)
        self.assertTrue(any("invalid array item" in error for error in errors))

    def test_release_rejects_duplicate_json_key(self):
        path = self.root / "releases" / "0.75.0.json"
        path.write_text('{"release":"0.75.0","release":"0.74.0"}', encoding="utf-8")
        errors = validate.validate_catalog(self.root)
        self.assertTrue(any("duplicate JSON key" in error for error in errors))

    def test_release_rejects_container_reference_cycle(self):
        value = self.valid_release()
        value["container_components"] = {"a": {"ref": "b"}, "b": {"ref": "a"}}
        self.write_release(value=value)
        errors = validate.validate_catalog(self.root)
        self.assertTrue(any("reference cycle" in error for error in errors))

    def test_os_manifest_rejects_command_substitution(self):
        value = self.valid_os_manifest() + 'EVIL="$(id)"\n'
        self.write_os_manifest(value)
        errors = validate.validate_catalog(self.root)
        self.assertTrue(any("unsafe shell character" in error for error in errors))

    def test_os_manifest_requires_virtual_mappings(self):
        value = self.valid_os_manifest().replace('VIRT_PKG_KMD="tenstorrent-dkms"\n', "")
        self.write_os_manifest(value)
        errors = validate.validate_catalog(self.root)
        self.assertTrue(any("VIRT_PKG_KMD" in error for error in errors))

    def test_os_manifest_rejects_unicode_whitespace(self):
        self.write_os_manifest("\u00a0" + self.valid_os_manifest())
        errors = validate.validate_catalog(self.root)
        self.assertTrue(any("ASCII text only" in error for error in errors))

    def test_empty_catalog_requires_explicit_bootstrap_mode(self):
        self.assertTrue(validate.validate_catalog(self.root))
        self.assertEqual(validate.validate_catalog(self.root, allow_empty=True), [])

    def test_catalog_rejects_symlink(self):
        target = self.root / "outside.json"
        target.write_text("{}", encoding="utf-8")
        (self.root / "releases" / "0.75.0.json").symlink_to(target)
        errors = validate.validate_catalog(self.root, allow_empty=True)
        self.assertTrue(any("symlinks are not allowed" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
