import importlib.util
import json
import os
import tempfile
import unittest
from unittest import mock
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

    def test_release_rejects_invalid_ghcr_repository_segments(self):
        for image_url in (
            "ghcr.io/example/",
            "ghcr.io/example//image",
            "ghcr.io/-example/image",
            "ghcr.io/example/image-",
            "ghcr.io/example/a..b",
            "ghcr.io/example/a___b",
            "ghcr.io/example/a.-b",
        ):
            with self.subTest(image_url=image_url):
                value = self.valid_release()
                value["container_components"]["image"]["image_url"] = image_url
                self.write_release(value=value)
                errors = validate.validate_catalog(self.root, allow_empty=True)
                self.assertTrue(any("image_url" in error for error in errors))

    def test_release_accepts_valid_ghcr_repository_segments(self):
        value = self.valid_release()
        value["container_components"]["image"]["image_url"] = "ghcr.io/example/a_b/a__b/a---b/team.v2_image-1"
        self.write_release(value=value)
        self.assertEqual(validate.validate_catalog(self.root, allow_empty=True), [])

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
            "https://example.com/file\u0080name",
            "https://example.com/file\u009fname",
            "https://example<.com/file",
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
                errors = validate.validate_catalog(self.root, allow_empty=True)
                self.assertTrue(any("download_url" in error for error in errors), url)

    def test_release_accepts_valid_url_hosts(self):
        value = self.valid_release()
        value["components"]["download"] = {
            "version": "1.0.0",
            "download_url": "https://[2001:db8::1]/file",
            "sha256": "a" * 64,
        }
        value["git_components"]["source"] = {
            "url": "https://example~host/path",
            "version": "main",
        }
        self.write_release(value=value)
        self.assertEqual(validate.validate_catalog(self.root, allow_empty=True), [])

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

    def test_os_manifest_rejects_empty_virtual_mapping(self):
        value = self.valid_os_manifest().replace('VIRT_PKG_KMD="tenstorrent-dkms"', 'VIRT_PKG_KMD=""')
        self.write_os_manifest(value)
        errors = validate.validate_catalog(self.root)
        self.assertTrue(any("VIRT_PKG_KMD must be a non-empty string" in error for error in errors))

    def test_os_manifest_rejects_invalid_repository_url(self):
        value = self.valid_os_manifest().replace(
            'REQUIRED_REPOS=("https://example.com/repo/")',
            'REQUIRED_REPOS=("http://example.com/repo/")',
        )
        self.write_os_manifest(value)
        errors = validate.validate_catalog(self.root)
        self.assertTrue(any("REQUIRED_REPOS[0]" in error for error in errors))

    def test_os_manifest_rejects_duplicate_repositories(self):
        value = self.valid_os_manifest().replace(
            'REQUIRED_REPOS=("https://example.com/repo/")',
            'REQUIRED_REPOS=("https://example.com/repo/" "https://example.com/repo/")',
        )
        self.write_os_manifest(value)
        errors = validate.validate_catalog(self.root)
        self.assertTrue(any("must not contain duplicate entries" in error for error in errors))

    def test_os_manifest_allows_empty_repositories(self):
        value = self.valid_os_manifest().replace(
            'REQUIRED_REPOS=("https://example.com/repo/")',
            "REQUIRED_REPOS=()",
        )
        self.write_os_manifest(value)
        self.assertEqual(validate.validate_catalog(self.root, allow_empty=True), [])

    def test_committed_release_manifests_have_verified_pins(self):
        expected = {
            "0.67.0": {
                "runtime": "39f92aa795c28b1836947300d6556c7e3a7ccdba12e9aa60b3ad3be05df2e5c8",
                "models": "df7c675f80c4adc8bfd97d9a0da18b2ea86542c903bade2d71f7a9e8f9092fd8",
            },
            "0.67.4": {
                "runtime": "2cc5bcf40755597bde650980be6d15fa6898f2f19ce712fd1074e6d2c5201581",
                "models": "05c568161f72bd4b64e77ab6fb0ea51110ef12b2d1b6df557c698bc1fb54ed3e",
            },
            "0.68.0": {
                "runtime": "1d811ad04e5d212ebe6436edfbfde979d43c5fa7600880baad8b2059b9c1510b",
                "models": "be2275a89d4209be0f42d91081b851acfd3ac0938fe5ce035997da0eda8ba2f4",
            },
            "0.69.0": {
                "runtime": "7598666e0b099e5a2cd77f5e579c2ed2f2c6f514cf3013eb25c2c5ff1b3f7b19",
                "models": "48d938159be63b73cffe16f0cef116ff7dff1334e956f288ea8b55d38bf96c8d",
            },
            "0.70.1": {
                "runtime": "ead7b800bdb6bebb9425c377222314447c5b2052f6e8b1e3c9caa1818cb7d8c4",
                "models": "02151bea82bc345afe6171b72d9232332d90699f550e6c5b35a645fa19569b3e",
            },
            "0.71.2": {
                "runtime": "8e32440a458bcff3b804916ddd917d22532594b72696b5bc1618bf0eec7a9274",
                "models": "788e877ae073bb7dd933d997e9ae5dc0bddd7227f7ebb14baf4f4b44709d14ee",
            },
            "0.72.0": {
                "runtime": "44d92ec1ce77b9ba7f11a76630b3a2a046879565f5f9fb1a185b70a3e86010bb",
                "models": "39f400743f061ba29a43e2cfee7f0b5b6ed7345da6b55f7f04ff16f7430fd5c5",
            },
        }
        root = Path(__file__).parents[1]
        for release, digests in expected.items():
            with self.subTest(release=release):
                path = root / "releases" / f"{release}.json"
                value = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(value["release"], release)
                self.assertEqual(
                    value["components"],
                    {
                        "tt-metal": f"v{release}",
                        "tt-kmd": "2.5.0",
                        "firmware": "19.2.0",
                        "tt-smi": "3.0.38",
                    },
                )
                containers = value["container_components"]
                self.assertEqual(containers["tt-metalium"], {"ref": "tt-metalium-ubuntu24"})
                self.assertEqual(
                    containers["tt-metalium-ubuntu24"],
                    {
                        "image_url": "ghcr.io/tenstorrent/tt-metal/tt-metalium-ubuntu-24.04-release-amd64",
                        "image_tag": "sha256:" + digests["runtime"],
                    },
                )
                self.assertEqual(
                    containers["tt-metalium-models"],
                    {
                        "image_url": "ghcr.io/tenstorrent/tt-metal/tt-metalium-ubuntu-22.04-release-models-amd64",
                        "image_tag": "sha256:" + digests["models"],
                    },
                )

    def test_prerelease_only_versions_are_not_catalog_entries(self):
        root = Path(__file__).parents[1]
        for release in ("0.70.0", "0.71.1"):
            with self.subTest(release=release):
                self.assertFalse((root / "releases" / f"{release}.json").exists())

    def test_committed_ubuntu_manifests_have_exact_consumer_values(self):
        expected_scalars = {
            "PKG_MANAGER": "apt",
            "USE_SYSTEM_PACKAGES": "true",
            "VIRT_PKG_CMAKE": "cmake",
            "VIRT_PKG_NINJA": "ninja-build",
            "VIRT_PKG_ZLIB": "zlib1g-dev",
            "VIRT_PKG_KMD": "tenstorrent-dkms",
            "VIRT_PKG_SMI": "tt-smi",
            "VIRT_PKG_FLASH": "tt-flash",
            "VIRT_PKG_TOPOLOGY": "tt-topology",
            "VIRT_PKG_METALIUM": "tt-metalium",
        }
        expected_arrays = {"REQUIRED_REPOS": ["https://ppa.tenstorrent.com/ubuntu/"], "WORKAROUNDS": []}
        root = Path(__file__).parents[1]
        for name in ("ubuntu-22.04.env", "ubuntu-24.04.env"):
            with self.subTest(name=name):
                scalars, arrays = validate.validate_os_manifest(root / "manifests" / name)
                self.assertEqual(scalars, expected_scalars)
                self.assertEqual(arrays, expected_arrays)

    def test_os_manifest_rejects_unicode_whitespace(self):
        self.write_os_manifest("\u00a0" + self.valid_os_manifest())
        errors = validate.validate_catalog(self.root)
        self.assertTrue(any("ASCII text only" in error for error in errors))

    def test_os_manifest_rejects_non_lf_record_separators(self):
        for separator in ("\x0b", "\x0c", "\r"):
            with self.subTest(separator=repr(separator)):
                self.write_os_manifest(self.valid_os_manifest().replace("\n", separator, 1))
                errors = validate.validate_catalog(self.root)
                self.assertTrue(any("control characters" in error for error in errors))

    def test_os_manifest_accepts_crlf(self):
        self.write_os_manifest(self.valid_os_manifest().replace("\n", "\r\n"))
        self.assertEqual(validate.validate_catalog(self.root, allow_empty=True), [])

    def test_catalog_rejects_replaced_release_entry(self):
        path = self.write_release()
        directory_fd, entries = validate.catalog_paths(self.root / "releases", ".json", self.root, [])
        self.assertIsNotNone(directory_fd)
        try:
            replacement = path.with_name(path.name + ".replacement")
            replacement.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
            os.replace(replacement, path)
            with self.assertRaises(validate.ValidationError):
                validate.validate_release_content(path, validate.read_catalog_entry(entries[0]))
        finally:
            os.close(directory_fd)

    def test_catalog_rejects_replaced_os_entry(self):
        path = self.write_os_manifest()
        directory_fd, entries = validate.catalog_paths(self.root / "manifests", ".env", self.root, [])
        self.assertIsNotNone(directory_fd)
        try:
            replacement = path.with_name(path.name + ".replacement")
            replacement.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
            os.replace(replacement, path)
            with self.assertRaises(validate.ValidationError):
                validate.validate_os_manifest_content(path, validate.read_catalog_entry(entries[0]))
        finally:
            os.close(directory_fd)

    def test_os_manifest_accepts_exact_aggregate_limit(self):
        base = self.valid_os_manifest().encode("ascii")
        target = validate.MAX_OS_TOTAL_BYTES
        content = bytearray(base)
        remaining = target - len(content)
        while remaining:
            line_length = min(65535, remaining)
            if line_length == 1:
                content.extend(b"\n")
            else:
                content.extend(b"#" + b"x" * (line_length - 2) + b"\n")
            remaining -= line_length
        self.write_os_manifest(content.decode("ascii"))
        self.assertEqual(validate.validate_catalog(self.root, allow_empty=True), [])

    def test_os_manifest_rejects_over_aggregate_limit(self):
        base = self.valid_os_manifest().encode("ascii")
        content = base + b"#x\n" * ((validate.MAX_OS_TOTAL_BYTES - len(base)) // 3 + 1)
        self.assertGreater(len(content), validate.MAX_OS_TOTAL_BYTES)
        self.write_os_manifest(content.decode("ascii"))
        errors = validate.validate_catalog(self.root, allow_empty=True)
        self.assertTrue(any("aggregate limit" in error for error in errors))

    def test_direct_os_manifest_accepts_exact_aggregate_limit(self):
        base = self.valid_os_manifest().encode("ascii")
        padding = validate.MAX_OS_TOTAL_BYTES - len(base)
        content = bytearray(base)
        while padding >= 2:
            chunk = min(65535, padding)
            content.extend(b"#" + b"x" * (chunk - 2) + b"\n")
            padding -= chunk
        if padding:
            content.extend(b"\n")
        self.assertEqual(len(content), validate.MAX_OS_TOTAL_BYTES)
        path = self.write_os_manifest(content.decode("ascii"))
        validate.validate_os_manifest(path)

    def test_direct_os_manifest_rejects_over_aggregate_limit(self):
        base = self.valid_os_manifest().encode("ascii")
        content = base + b"#x\n" * ((validate.MAX_OS_TOTAL_BYTES - len(base)) // 3 + 1)
        self.assertGreater(len(content), validate.MAX_OS_TOTAL_BYTES)
        path = self.write_os_manifest(content.decode("ascii"))
        with self.assertRaisesRegex(validate.ValidationError, "aggregate limit"):
            validate.validate_os_manifest(path)

    def test_os_manifest_rejects_oversized_records(self):
        for record in (
            "#" + "x" * (validate.MAX_OS_RECORD_BYTES - 1),
            "PKG_MANAGER=\"" + "a" * (validate.MAX_OS_RECORD_BYTES - 14) + "\"",
        ):
            with self.subTest(record_prefix=record[:10]):
                self.write_os_manifest(record + "\n" + self.valid_os_manifest())
                errors = validate.validate_catalog(self.root, allow_empty=True)
                self.assertTrue(any("record must be shorter" in error for error in errors))

    def test_os_manifest_accepts_maximum_record_boundary(self):
        record = "#" + "x" * (validate.MAX_OS_RECORD_BYTES - 2)
        self.write_os_manifest(record + "\n" + self.valid_os_manifest())
        self.assertEqual(validate.validate_catalog(self.root, allow_empty=True), [])

    def test_os_manifest_rejects_lone_cr(self):
        self.write_os_manifest(self.valid_os_manifest().replace("\n", "\r"))
        errors = validate.validate_catalog(self.root)
        self.assertTrue(any("control characters" in error for error in errors))

    def test_catalog_closes_descriptors_when_manifest_discovery_fails(self):
        real_close = validate.os.close
        closed: list[int] = []

        def close(file_fd):
            closed.append(file_fd)
            real_close(file_fd)

        with mock.patch.object(validate.os, "close", side_effect=close), mock.patch.object(
            validate.os, "listdir", side_effect=[[".gitkeep"], OSError("injected failure")]
        ):
            with self.assertRaises(OSError):
                validate.validate_catalog(self.root, allow_empty=True)
        self.assertEqual(len(closed), 2)
        self.assertEqual(len(set(closed)), 2)

    def test_catalog_rejects_symlinked_catalog_directories(self):
        for name in ("manifests", "releases"):
            with self.subTest(name=name):
                target = self.root / f"outside-{name}"
                target.mkdir()
                original = self.root / name
                original.rmdir()
                original.symlink_to(target, target_is_directory=True)
                errors = validate.validate_catalog(self.root, allow_empty=True)
                self.assertTrue(any(f"{name}: symlinks are not allowed" in error for error in errors))
                original.unlink()
                original.mkdir()

    def test_empty_catalog_is_rejected_by_default(self):
        self.assertTrue(validate.validate_catalog(self.root))
        self.assertEqual(validate.validate_catalog(self.root, allow_empty=True), [])

    def test_catalog_accepts_regular_gitkeep(self):
        (self.root / "releases" / ".gitkeep").write_text("", encoding="utf-8")
        (self.root / "manifests" / ".gitkeep").write_text("", encoding="utf-8")
        self.assertEqual(validate.validate_catalog(self.root, allow_empty=True), [])

    def test_catalog_rejects_unsafe_gitkeep_entries(self):
        for kind in ("symlink", "directory"):
            with self.subTest(kind=kind):
                target = self.root / f"outside-{kind}"
                if kind == "symlink":
                    target.write_text("", encoding="utf-8")
                    (self.root / "manifests" / ".gitkeep").symlink_to(target)
                else:
                    (self.root / "manifests" / ".gitkeep").mkdir()
                errors = validate.validate_catalog(self.root, allow_empty=True)
                self.assertTrue(any("manifests/.gitkeep" in error for error in errors))
                gitkeep = self.root / "manifests" / ".gitkeep"
                if gitkeep.is_symlink() or gitkeep.is_file():
                    gitkeep.unlink()
                else:
                    gitkeep.rmdir()

    def test_catalog_rejects_symlink(self):
        target = self.root / "outside.json"
        target.write_text("{}", encoding="utf-8")
        (self.root / "releases" / "0.75.0.json").symlink_to(target)
        errors = validate.validate_catalog(self.root, allow_empty=True)
        self.assertTrue(any("symlinks are not allowed" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
