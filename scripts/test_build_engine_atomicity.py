import importlib.metadata
import importlib.util
import hashlib
import io
import json
import tarfile
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock
import build_r2t2_runtime as native_builder


BUILD_SCRIPT = Path(__file__).with_name("build_engine.py")
OLD_ARCHIVE = b"known-good-engine-archive"


def load_build_engine_module():
    spec = importlib.util.spec_from_file_location("build_engine_under_test", BUILD_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {BUILD_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class EngineArchiveSourceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.archive = self.root / "engine.tar.xz"
        self.module = load_build_engine_module()
        self.module.RESOURCES_DIR = self.root
        self.module.ADD_DATA_FILES = ["engine.py", "server_common.py", "gpu_idle.py"]
        self.sources = {name: f"# {name}\nVALUE = 180\n".encode() for name in self.module.ADD_DATA_FILES}
        for name, source in self.sources.items():
            (self.root / name).write_bytes(source)
        shared = b"synthetic shared CRT"
        self.native_members = {"_internal/msvcp140.dll": shared}
        for backend in ("cpu", "cuda"):
            library = f"synthetic {backend} native library".encode()
            prefix = f"_internal/r2t2-native/{backend}"
            manifest = {
                "build_id": self.module.R2T2_BUILD_ID,
                "revision": self.module.R2T2_REVISION,
                "patch_sha256": hashlib.sha256(self.module.R2T2_PATCH.read_bytes()).hexdigest(),
                "backend": backend,
                "files": {"audiocpp.dll": {
                    "size": len(library), "sha256": hashlib.sha256(library).hexdigest(),
                }},
                "shared_files": {"msvcp140.dll": {
                    "size": len(shared), "sha256": hashlib.sha256(shared).hexdigest(),
                }},
            }
            self.native_members[f"{prefix}/audiocpp.dll"] = library
            self.native_members[f"{prefix}/runtime-manifest.json"] = json.dumps(manifest).encode()

    def package(self, sources, *, native_members=None, extra_members=()):
        members = {f"_internal/{name}": source for name, source in sources.items()}
        members.update(self.native_members if native_members is None else native_members)
        with tarfile.open(self.archive, "w:xz") as archive:
            for name, source in members.items():
                member = tarfile.TarInfo(name)
                member.size = len(source)
                archive.addfile(member, io.BytesIO(source))
            for member, source in extra_members:
                archive.addfile(member, None if source is None else io.BytesIO(source))

    def test_current_sources_pass_even_across_checkout_line_endings(self):
        self.package({name: source.replace(b"\n", b"\r\n") for name, source in self.sources.items()})
        self.module.verify_archive_sources(self.archive)

    def test_old_gpu_idle_dispatch_is_rejected(self):
        self.package({**self.sources, "server_common.py": b"# legacy dispatcher\nVALUE = 180\n"})
        with self.assertRaisesRegex(RuntimeError, "Stale bundled source: _internal/server_common.py"):
            self.module.verify_archive_sources(self.archive)

    def test_changed_checkout_requires_a_rebuilt_engine(self):
        self.package(self.sources)
        (self.root / "gpu_idle.py").write_bytes(b"VALUE = 0\n")
        with self.assertRaisesRegex(RuntimeError, "bundled source: _internal/gpu_idle.py"):
            self.module.verify_archive_sources(self.archive)

    def test_missing_idle_module_is_rejected(self):
        self.package({name: source for name, source in self.sources.items() if name != "gpu_idle.py"})
        with self.assertRaisesRegex(RuntimeError, "Missing bundled sources: _internal/gpu_idle.py"):
            self.module.verify_archive_sources(self.archive)

    def test_xz_header_without_an_archive_is_rejected(self):
        self.archive.write_bytes(b"\xfd7zXZ\x00")
        with self.assertRaises((tarfile.TarError, EOFError)):
            self.module.verify_archive_sources(self.archive)

    def test_source_symlink_is_rejected(self):
        member = tarfile.TarInfo("_internal/gpu_idle.py")
        member.type = tarfile.SYMTYPE
        member.linkname = "../../outside.py"
        self.package(
            {name: source for name, source in self.sources.items() if name != "gpu_idle.py"},
            extra_members=[(member, None)],
        )
        with self.assertRaisesRegex(RuntimeError, "Invalid bundled source: _internal/gpu_idle.py"):
            self.module.verify_archive_sources(self.archive)

    def test_duplicate_source_cannot_override_a_verified_file(self):
        source = b"VALUE = 0\n"
        member = tarfile.TarInfo("_internal/gpu_idle.py")
        member.size = len(source)
        self.package(self.sources, extra_members=[(member, source)])
        with self.assertRaisesRegex(RuntimeError, "Invalid bundled source: _internal/gpu_idle.py"):
            self.module.verify_archive_sources(self.archive)

    def test_current_native_runtimes_and_shared_files_pass(self):
        self.package(self.sources)
        self.module.verify_archive_sources(self.archive)

    def test_wrong_native_provenance_or_backend_is_rejected(self):
        for backend in ("cpu", "cuda"):
            for field, stale in (
                ("build_id", "light-whisper-r2t2-5"),
                ("revision", "0" * 40),
                ("patch_sha256", "0" * 64),
                ("backend", "cuda" if backend == "cpu" else "cpu"),
            ):
                with self.subTest(backend=backend, field=field):
                    name = f"_internal/r2t2-native/{backend}/runtime-manifest.json"
                    manifest = json.loads(self.native_members[name])
                    manifest[field] = stale
                    self.package(self.sources, native_members={
                        **self.native_members, name: json.dumps(manifest).encode(),
                    })
                    with self.assertRaises(RuntimeError):
                        self.module.verify_archive_sources(self.archive)

    def test_missing_native_manifest_or_library_is_rejected(self):
        for backend in ("cpu", "cuda"):
            for filename in ("runtime-manifest.json", "audiocpp.dll"):
                with self.subTest(backend=backend, filename=filename):
                    missing = f"_internal/r2t2-native/{backend}/{filename}"
                    self.package(self.sources, native_members={
                        name: source for name, source in self.native_members.items() if name != missing
                    })
                    with self.assertRaises(RuntimeError):
                        self.module.verify_archive_sources(self.archive)

    def test_same_size_modified_native_library_is_rejected(self):
        for backend in ("cpu", "cuda"):
            with self.subTest(backend=backend):
                name = f"_internal/r2t2-native/{backend}/audiocpp.dll"
                self.package(self.sources, native_members={
                    **self.native_members, name: b"X" * len(self.native_members[name]),
                })
                with self.assertRaises(RuntimeError):
                    self.module.verify_archive_sources(self.archive)

    def test_duplicate_native_manifest_or_library_is_rejected(self):
        for backend in ("cpu", "cuda"):
            for filename in ("runtime-manifest.json", "audiocpp.dll"):
                with self.subTest(backend=backend, filename=filename):
                    name = f"_internal/r2t2-native/{backend}/{filename}"
                    source = self.native_members[name]
                    member = tarfile.TarInfo(name)
                    member.size = len(source)
                    self.package(self.sources, extra_members=[(member, source)])
                    with self.assertRaises(RuntimeError):
                        self.module.verify_archive_sources(self.archive)

    def test_symlinked_native_manifest_or_library_is_rejected(self):
        for backend in ("cpu", "cuda"):
            for filename in ("runtime-manifest.json", "audiocpp.dll"):
                with self.subTest(backend=backend, filename=filename):
                    name = f"_internal/r2t2-native/{backend}/{filename}"
                    member = tarfile.TarInfo(name)
                    member.type = tarfile.SYMTYPE
                    member.linkname = "../../../outside"
                    self.package(
                        self.sources,
                        native_members={key: source for key, source in self.native_members.items() if key != name},
                        extra_members=[(member, None)],
                    )
                    with self.assertRaises(RuntimeError):
                        self.module.verify_archive_sources(self.archive)


class BuildEngineArchiveAtomicityTests(unittest.TestCase):
    def test_packaging_shares_only_identical_runtime_dlls_and_updates_manifest(self):
        def fake_pyinstaller(_cmd):
            internal = self.dist_dir / "engine/_internal"
            backend = internal / "r2t2-native/cuda"
            backend.mkdir(parents=True)
            payloads = {"cublasLt64_12.dll": b"same cuda", "cublas64_12.dll": b"version A",
                        "cudart64_12.dll": b"no shared copy", "audiocpp.dll": b"model library"}
            for name, data in payloads.items():
                (backend / name).write_bytes(data)
            (internal / "cublasLt64_12.dll").write_bytes(payloads["cublasLt64_12.dll"])
            (internal / "cublas64_12.dll").write_bytes(b"version B")
            (internal / "audiocpp.dll").write_bytes(payloads["audiocpp.dll"])
            manifest = {"backend": "cuda", "files": {
                name: {"size": len(data), "sha256": hashlib.sha256(data).hexdigest()}
                for name, data in payloads.items()}}
            (backend / "runtime-manifest.json").write_text(json.dumps(manifest))
            return types.SimpleNamespace(returncode=0)

        def inspect_archive_input(engine_dir, output):
            internal = engine_dir / "_internal"
            backend = internal / "r2t2-native/cuda"
            self.assertFalse((backend / "cublasLt64_12.dll").exists())
            self.assertEqual((internal / "cublasLt64_12.dll").read_bytes(), b"same cuda")
            for name in ("cublas64_12.dll", "cudart64_12.dll", "audiocpp.dll"):
                self.assertTrue((backend / name).is_file(), name)
            manifest = json.loads((backend / "runtime-manifest.json").read_text())
            self.assertEqual(set(manifest["shared_files"]), {"cublasLt64_12.dll"})
            self.assertNotIn("cublasLt64_12.dll", manifest["files"])
            for name, metadata in manifest["shared_files"].items():
                self.assertEqual(metadata["sha256"], hashlib.sha256((internal / name).read_bytes()).hexdigest())
            output.write_bytes(b"new verified archive")
            return 1.0

        with mock.patch.object(self.module.subprocess, "run", side_effect=fake_pyinstaller), \
             mock.patch.object(self.module, "create_tar_xz", side_effect=inspect_archive_input):
            self.module.main()
        self.assertEqual(self.output_archive.read_bytes(), b"new verified archive")
        self.assertNotIn("shared_files", json.loads((self.resources_dir / "r2t2-native/cuda/runtime-manifest.json").read_text()))

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)

        self.root = Path(self.temp_dir.name)
        self.resources_dir = self.root / "resources"
        self.resources_dir.mkdir()
        self.entry_script = self.resources_dir / "engine.py"
        self.entry_script.write_text("print('synthetic engine')\n", encoding="utf-8")
        self.output_archive = self.resources_dir / "engine.tar.xz"
        self.output_archive.write_bytes(OLD_ARCHIVE)
        self.dist_dir = self.resources_dir / "python-dist"
        self.module = load_build_engine_module()
        self.module.PROJECT_ROOT = self.root
        self.module.RESOURCES_DIR = self.resources_dir
        self.module.DIST_DIR = self.dist_dir
        self.module.ENTRY_SCRIPT = self.entry_script
        self.module.OUTPUT_ARCHIVE = self.output_archive
        self.module.WINDOWS_MANIFEST = self.root / "missing-manifest.xml"
        for backend in ("cpu", "cuda"):
            directory = self.resources_dir / "r2t2-native" / backend
            directory.mkdir(parents=True)
            library = b"synthetic native library"
            (directory / "audiocpp.dll").write_bytes(library)
            (directory / "runtime-manifest.json").write_text(json.dumps({
                "backend": backend, "build_id": self.module.R2T2_BUILD_ID,
                "revision": self.module.R2T2_REVISION,
                "patch_sha256": hashlib.sha256(self.module.R2T2_PATCH.read_bytes()).hexdigest(),
                "files": {"audiocpp.dll": {"size": len(library), "sha256": hashlib.sha256(library).hexdigest()}},
            }), encoding="utf-8")
        # Freeze installed metadata without depending on a retired helper API.
        self.enterContext(mock.patch.object(importlib.metadata, "version", return_value="0.1.3"))

    def test_remove_file_retries_transient_windows_lock(self):
        locked_path = mock.Mock(spec=Path)
        locked_path.exists.return_value = True
        locked_path.unlink.side_effect = [PermissionError("file is busy"), None]

        with mock.patch.object(self.module.time, "sleep") as sleep:
            self.module.remove_file(locked_path, warn_only=False, retries=2, delay=0.25)

        self.assertEqual(locked_path.unlink.call_count, 2)
        sleep.assert_called_once_with(0.25)

    def test_stale_native_runtime_is_rejected_before_destroying_old_build(self):
        self.dist_dir.mkdir()
        sentinel = self.dist_dir / "keep.txt"
        sentinel.write_text("previous build")
        manifest_path = self.resources_dir / "r2t2-native/cpu/runtime-manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["patch_sha256"] = "old patch"
        manifest_path.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(RuntimeError, "Stale R2T2"):
            self.module.main()
        self.assertTrue(sentinel.is_file())
        self.assertEqual(self.output_archive.read_bytes(), OLD_ARCHIVE)

    def test_modified_native_library_is_rejected(self):
        library = self.resources_dir / "r2t2-native/cuda/audiocpp.dll"
        library.write_bytes(b"X" * library.stat().st_size)
        with self.assertRaisesRegex(RuntimeError, "checksum mismatch"):
            self.module.validate_r2t2_runtime()

    def test_unlisted_native_file_is_rejected(self):
        (self.resources_dir / "r2t2-native/cpu/stale.dll").write_bytes(b"old")
        with self.assertRaisesRegex(RuntimeError, "Unexpected native"):
            self.module.validate_r2t2_runtime()

    def _native_build_fixture(self):
        source, build, redist = (self.root / name for name in ("source", "build", "redist"))
        for relative in ("LICENSE", "external/ggml/LICENSE", "external/sentencepiece/LICENSE"):
            path = source / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("synthetic license")
        (build / "bin").mkdir(parents=True)
        (build / "bin/audiocpp.dll").write_bytes(b"new native library")
        for name in ("msvcp140.dll", "vcruntime140.dll", "vcruntime140_1.dll", "vcomp140.dll"):
            path = redist / "x64/CRT" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"synthetic runtime")
        return source, build, {"VCToolsRedistDir": str(redist)}

    def test_native_rebuild_does_not_absorb_old_package_files(self):
        source, build, env = self._native_build_fixture()
        output = self.resources_dir / "r2t2-native/cpu"
        (output / "stale.dll").write_bytes(b"old")
        native_builder.copy_runtime(source, build, output, "cpu", None, env, "")
        self.assertFalse((output / "stale.dll").exists())
        manifest = json.loads((output / "runtime-manifest.json").read_text())
        self.assertEqual(set(manifest["files"]), {p.name for p in output.iterdir()} - {"runtime-manifest.json"})
        self.assertEqual((output / "audiocpp.dll").read_bytes(), b"new native library")

    def test_native_assembly_failure_preserves_previous_package(self):
        source, build, env = self._native_build_fixture()
        (source / "LICENSE").unlink()
        output = self.resources_dir / "r2t2-native/cpu"
        previous = {p.name: p.read_bytes() for p in output.iterdir()}
        with self.assertRaises(FileNotFoundError):
            native_builder.copy_runtime(source, build, output, "cpu", None, env, "")
        self.assertEqual({p.name: p.read_bytes() for p in output.iterdir()}, previous)

    def test_native_publish_failure_restores_previous_package(self):
        source, build, env = self._native_build_fixture()
        output = self.resources_dir / "r2t2-native/cpu"
        previous = {p.name: p.read_bytes() for p in output.iterdir()}
        rename = Path.rename
        def fail_publish(path, target):
            if path.name == "new":
                raise PermissionError("synthetic publish failure")
            return rename(path, target)
        with mock.patch.object(Path, "rename", fail_publish):
            with self.assertRaisesRegex(PermissionError, "synthetic publish failure"):
                native_builder.copy_runtime(source, build, output, "cpu", None, env, "")
        self.assertEqual({p.name: p.read_bytes() for p in output.iterdir()}, previous)

    def test_native_publish_refuses_unmanaged_output_directory(self):
        source, build, env = self._native_build_fixture()
        output = self.root / "unmanaged"
        output.mkdir()
        (output / "keep.txt").write_text("user file")
        with self.assertRaisesRegex(RuntimeError, "unmanaged"):
            native_builder.copy_runtime(source, build, output, "cpu", None, env, "")
        self.assertEqual((output / "keep.txt").read_text(), "user file")

    def test_native_failed_rollback_keeps_recoverable_backup(self):
        source, build, env = self._native_build_fixture()
        output = self.resources_dir / "r2t2-native/cpu"
        previous = {p.name: p.read_bytes() for p in output.iterdir()}
        rename = Path.rename
        def fail_publish_and_restore(path, target):
            if path.name in ("new", "previous"):
                raise PermissionError("synthetic locked target")
            return rename(path, target)
        with mock.patch.object(Path, "rename", fail_publish_and_restore):
            with self.assertRaisesRegex(RuntimeError, "Previous native package retained"):
                native_builder.copy_runtime(source, build, output, "cpu", None, env, "")
        backups = list(output.parent.glob(".r2t2-runtime-*/previous"))
        self.assertEqual(len(backups), 1)
        self.assertEqual({p.name: p.read_bytes() for p in backups[0].iterdir()}, previous)

    def test_remove_file_exhausted_lock_is_nonfatal_for_temporary_artifact(self):
        locked_path = mock.Mock(spec=Path)
        locked_path.exists.return_value = True
        locked_path.unlink.side_effect = PermissionError("file is busy")

        with mock.patch.object(self.module.time, "sleep") as sleep:
            self.module.remove_file(locked_path, warn_only=True, retries=2, delay=0.25)

        self.assertEqual(locked_path.unlink.call_count, 2)
        sleep.assert_called_once_with(0.25)

    def test_pyinstaller_failure_preserves_last_known_good_archive(self):
        failed_process = types.SimpleNamespace(returncode=23)

        with (
            mock.patch.object(self.module.subprocess, "run", return_value=failed_process),
            self.assertRaises(SystemExit) as exit_context,
        ):
            self.module.main()

        self.assertEqual(exit_context.exception.code, 23)
        self.assertTrue(
            self.output_archive.exists(),
            "A failed rebuild must not delete the last known-good engine archive",
        )
        self.assertEqual(self.output_archive.read_bytes(), OLD_ARCHIVE)

    def test_compression_failure_uses_staging_and_preserves_published_archive(self):
        attempted_outputs = []

        def fake_pyinstaller(_cmd):
            engine_dir = self.dist_dir / "engine"
            engine_dir.mkdir(parents=True)
            (engine_dir / "engine.exe").write_bytes(b"synthetic executable")
            return types.SimpleNamespace(returncode=0)

        def fail_compression(_engine_dir, output):
            attempted_outputs.append(Path(output))
            Path(output).write_bytes(b"partial-new-archive")
            raise RuntimeError("synthetic compression failure")

        with (
            mock.patch.object(self.module.subprocess, "run", side_effect=fake_pyinstaller),
            mock.patch.object(self.module, "strip_dev_artifacts", return_value=0.0),
            mock.patch.object(self.module, "create_tar_xz", side_effect=fail_compression),
            self.assertRaisesRegex(RuntimeError, "synthetic compression failure"),
        ):
            self.module.main()

        used_staging_path = bool(attempted_outputs) and attempted_outputs[0] != self.output_archive
        preserved_archive = (
            self.output_archive.exists()
            and self.output_archive.read_bytes() == OLD_ARCHIVE
        )
        self.assertTrue(
            used_staging_path and preserved_archive,
            "Compression must target a staging path and atomically replace the published "
            f"archive only after success; attempted={attempted_outputs}, "
            f"published_bytes={self.output_archive.read_bytes() if self.output_archive.exists() else None!r}",
        )


if __name__ == "__main__":
    unittest.main()
