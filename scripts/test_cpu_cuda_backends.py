"""Offline CPU/CUDA build, actual packager CLI, pruning and archive contracts."""

import importlib.metadata

import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import sys
import tarfile
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

import build_r2t2_runtime as builder
from test_build_engine_atomicity import load_build_engine_module


class CpuCudaNativeBuildTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source, self.build, self.output, self.cuda, self.vulkan, redist = (
            self.root / name for name in ("source", "build", "output", "cuda", "vulkan", "redist")
        )
        for relative in ("LICENSE", "external/ggml/LICENSE", "external/sentencepiece/LICENSE"):
            path = self.source / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("synthetic license", encoding="utf-8")
        (self.build / "bin").mkdir(parents=True)
        (self.build / "bin/audiocpp.dll").write_bytes(b"synthetic native library")
        for name in ("msvcp140.dll", "vcruntime140.dll", "vcruntime140_1.dll", "vcomp140.dll"):
            path = redist / "x64/CRT" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"synthetic redistributable")
        for relative in ("bin/nvcc.exe", "bin/cublas64_12.dll", "bin/cublasLt64_12.dll", "bin/cudart64_12.dll", "LICENSE"):
            path = self.cuda / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"synthetic CUDA build input")
        # A complete SDK prevents obsolete Vulkan support from failing by accident.
        for relative in ("Include/vulkan/vulkan.h", "Lib/vulkan-1.lib", "Bin/glslc.exe"):
            path = self.vulkan / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"synthetic retired build input")
        self.environment = {"PATH": "existing-build-path", "VULKAN_SDK": str(self.vulkan),
                            "VCToolsRedistDir": str(redist)}
        self.enterContext(mock.patch.dict(os.environ, {"VULKAN_SDK": str(self.vulkan)}))
        self.prepare = self.enterContext(mock.patch.object(builder, "prepare_source"))
        self.build_environment = self.enterContext(mock.patch.object(
            builder, "build_environment", side_effect=lambda: (self.environment.copy(), self.root / "ninja.exe")
        ))
        self.subprocess = self.enterContext(mock.patch.object(
            builder.subprocess, "run", return_value=SimpleNamespace(returncode=0)
        ))
        self.enterContext(contextlib.redirect_stdout(io.StringIO()))
        self.enterContext(contextlib.redirect_stderr(io.StringIO()))

    def invoke(self, backend, extra=()):
        arguments = ["build_r2t2_runtime.py", "--backend", backend,
                     "--source", str(self.source), "--build-dir", str(self.build),
                     "--output", str(self.output / backend), "--parallel", "2", *extra]
        if backend == "cuda":
            arguments += ["--cuda-root", str(self.cuda)]
        with mock.patch.object(sys, "argv", arguments):
            builder.main()

    def test_cpu_and_cuda_explicitly_disable_vulkan_and_keep_runtime_manifest_hashes(self):
        for backend in ("cpu", "cuda"):
            with self.subTest(backend=backend):
                self.subprocess.reset_mock()
                before = dict(os.environ)
                self.invoke(backend)
                configure, compile_call = self.subprocess.call_args_list
                command = configure.args[0]
                self.assertIn("-DENGINE_ENABLE_VULKAN=OFF", command)
                self.assertNotIn("-DENGINE_ENABLE_VULKAN=ON", command)
                self.assertIn(f"-DENGINE_ENABLE_CUDA={'ON' if backend == 'cuda' else 'OFF'}", command)
                self.assertEqual(compile_call.args[0], [
                    "cmake", "--build", str(self.build), "--target", "audiocpp", "--parallel", "2",
                ])
                self.assertEqual(dict(os.environ), before)
                self.assertEqual(configure.kwargs["env"]["VULKAN_SDK"], str(self.vulkan))
                self.assertNotIn(str(self.vulkan / "Bin"), configure.kwargs["env"]["PATH"].split(os.pathsep))
                directory = self.output / backend
                manifest = json.loads((directory / "runtime-manifest.json").read_text(encoding="utf-8"))
                self.assertEqual(manifest["backend"], backend)
                self.assertEqual(set(manifest["files"]), {path.name for path in directory.iterdir()} - {"runtime-manifest.json"})
                for name, metadata in manifest["files"].items():
                    data = (directory / name).read_bytes()
                    self.assertEqual(metadata, {"size": len(data), "sha256": hashlib.sha256(data).hexdigest()})

    def assert_cli_rejected(self, backend, extra=()):
        with self.assertRaises(SystemExit) as failure:
            self.invoke(backend, extra)
        self.assertNotEqual(failure.exception.code, 0)
        self.prepare.assert_not_called()
        self.build_environment.assert_not_called()
        self.subprocess.assert_not_called()
        self.assertFalse(self.output.exists())

    def test_vulkan_backend_rejects_before_source_or_build_work(self):
        self.assert_cli_rejected("vulkan")

    def test_auto_backend_rejects_before_source_or_build_work(self):
        self.assert_cli_rejected("auto")

    def test_retired_vulkan_root_cli_rejects_before_source_or_build_work(self):
        self.assert_cli_rejected("cpu", ("--vulkan-root", str(self.vulkan)))


class CpuCudaPackageTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.resources = self.root / "resources"
        self.resources.mkdir()
        self.module = load_build_engine_module()
        self.module.PROJECT_ROOT = self.root
        self.module.RESOURCES_DIR = self.resources
        self.module.ADD_DATA_FILES = ["engine.py"]
        self.module.ENTRY_SCRIPT = self.resources / "engine.py"
        self.module.ENTRY_SCRIPT.write_bytes(b"# synthetic engine\n")
        self.module.DIST_DIR = self.root / "dist"
        self.module.OUTPUT_ARCHIVE = self.resources / "engine.tar.xz"
        self.module.WINDOWS_MANIFEST = self.root / "missing-manifest.xml"
        self.archive = self.root / "reused.tar.xz"
        self.members = {"_internal/engine.py": self.module.ENTRY_SCRIPT.read_bytes()}
        for backend in ("cpu", "cuda"):
            self.members.update(self.native_members(backend, write_source=True))
        self.enterContext(mock.patch.object(importlib.metadata, "version", return_value="0.1.3"))
        self.enterContext(contextlib.redirect_stdout(io.StringIO()))
        self.enterContext(contextlib.redirect_stderr(io.StringIO()))

    def native_members(self, backend, *, write_source=False):
        library = f"synthetic {backend} library".encode()
        manifest = {
            "backend": backend, "build_id": self.module.R2T2_BUILD_ID,
            "revision": self.module.R2T2_REVISION,
            "patch_sha256": hashlib.sha256(self.module.R2T2_PATCH.read_bytes()).hexdigest(),
            "files": {"audiocpp.dll": {"size": len(library), "sha256": hashlib.sha256(library).hexdigest()}},
        }
        files = {"audiocpp.dll": library, "runtime-manifest.json": json.dumps(manifest).encode()}
        if write_source:
            directory = self.resources / "r2t2-native" / backend
            directory.mkdir(parents=True)
            for name, data in files.items():
                (directory / name).write_bytes(data)
        return {f"_internal/r2t2-native/{backend}/{name}": data for name, data in files.items()}

    def package(self, members=None):
        with tarfile.open(self.archive, "w:xz") as archive:
            for name, data in (self.members if members is None else members).items():
                member = tarfile.TarInfo(name)
                member.size = len(data)
                archive.addfile(member, io.BytesIO(data))

    def test_cpu_cuda_sources_validate_without_vulkan(self):
        try:
            actual = self.module.validate_r2t2_runtime()
        except RuntimeError as error:
            self.fail(f"Current CPU/CUDA-only source package rejected: {error}")
        self.assertEqual(actual, self.resources / "r2t2-native")

    def test_stale_extra_local_vulkan_directory_does_not_block_cpu_cuda_validation(self):
        directory = self.resources / "r2t2-native/vulkan"
        directory.mkdir()
        (directory / "runtime-manifest.json").write_text('{"backend":"retired"}', encoding="utf-8")
        (directory / "audiocpp.dll").write_bytes(b"old local native package")
        try:
            actual = self.module.validate_r2t2_runtime()
        except RuntimeError as error:
            self.fail(f"Unselected retired local package blocked CPU/CUDA: {error}")
        self.assertEqual(actual, directory.parent)

    def test_current_cpu_cuda_archive_passes_without_retired_backend(self):
        self.package()
        try:
            self.module.verify_archive_sources(self.archive)
        except RuntimeError as error:
            self.fail(f"Current CPU/CUDA-only archive rejected: {error}")

    def test_old_three_backend_archive_is_rejected_even_with_valid_vulkan_manifest(self):
        self.package({**self.members, **self.native_members("vulkan")})
        with self.assertRaises(RuntimeError):
            self.module.verify_archive_sources(self.archive)

    def test_retired_subtrees_and_dlls_are_rejected_with_normalized_slashes_and_case(self):
        self.package()
        try:
            self.module.verify_archive_sources(self.archive)
        except RuntimeError as error:
            self.fail(f"Valid CPU/CUDA archive must pass before forbidden-member probes: {error}")
        for name in (
            "_internal/r2t2-native/vulkan/retired.dat",
            r".\_INTERNAL\R2T2-NATIVE\VULKAN\retired.dat",
            r".\_INTERNAL\TRANSCRIBE_CPP_NATIVE_CU12\_NATIVE\GGML-VULKAN.DLL",
            "_internal/vulkan-1.dll",
            r"plugins\nested\VuLkAn-1.DlL",
        ):
            with self.subTest(member=name):
                self.package({**self.members, name: b"retired library"})
                with self.assertRaises(RuntimeError):
                    self.module.verify_archive_sources(self.archive)

    def test_main_selects_each_backend_directory_without_collecting_stale_vulkan_tree(self):
        # Valid old files let this test reach the real CLI seam before implementation.
        self.native_members("vulkan", write_source=True)
        with mock.patch.object(self.module.subprocess, "run", return_value=SimpleNamespace(returncode=23)) as run:
            with self.assertRaises(SystemExit) as stopped:
                self.module.main()
        self.assertEqual(stopped.exception.code, 23)
        command = run.call_args.args[0]
        selected = [command[index + 1] for index, arg in enumerate(command) if arg == "--add-data"]
        native = [(Path(source), destination.replace("\\", "/"))
                  for value in selected if "r2t2-native" in value
                  for source, destination in [value.rsplit(os.pathsep, 1)]]
        self.assertCountEqual(native, [
            (self.resources / "r2t2-native" / backend, f"r2t2-native/{backend}")
            for backend in ("cpu", "cuda")
        ])

    def test_main_prunes_only_retired_collected_dlls_before_compression_preserving_source_wheel(self):
        # Fake COLLECT copies a real fixture tree. Source wheel remains independent.
        self.native_members("vulkan", write_source=True)
        wheel = self.root / "source-wheel"
        retained = {
            "engine.exe": b"synthetic executable",
            "_internal/r2t2-native/cpu/audiocpp.dll": b"CPU library",
            "_internal/r2t2-native/cuda/audiocpp.dll": b"CUDA library",
            "_internal/onnxruntime/capi/onnxruntime_pybind11_state.pyd": b"ORT pybind",
            "_internal/onnxruntime/capi/onnxruntime_providers_shared.dll": b"ORT shared provider",
            "_internal/onnxruntime/capi/onnxruntime_providers_future.dll": b"future ORT provider",
            "_internal/kaldi_native_fbank/LICENSE": b"Kaldi license",
            "_internal/data/vulkan_settings.json": b"ordinary data",
        }
        retired = {
            "_internal/plugins/ggml-vulkan.dll": b"retired Vulkan",
            "_internal/plugins/VULKAN-1.DLL": b"retired Vulkan loader",
            "_internal/plugins/nested/GGML-VULKAN.DLL": b"nested retired copy",
            "_internal/vulkan-1.dll": b"root retired loader",
        }
        for relative, data in {**retained, **retired}.items():
            path = wheel / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)

        def snapshot(directory):
            return {path.relative_to(directory).as_posix(): path.read_bytes()
                    for path in directory.rglob("*") if path.is_file()}

        before = snapshot(wheel)
        captured = {}

        def fake_collect(_command):
            shutil.copytree(wheel, self.module.DIST_DIR / "engine")
            return SimpleNamespace(returncode=0)

        def capture_compression(directory, output):
            captured.update(snapshot(directory))
            output.write_bytes(b"synthetic nonempty archive")
            return 1.0

        with mock.patch.object(self.module.subprocess, "run", side_effect=fake_collect), \
             mock.patch.object(self.module, "create_tar_xz", side_effect=capture_compression):
            self.module.main()
        self.assertEqual(captured, retained)
        self.assertEqual(snapshot(wheel), before, "package pruning modified source wheel files")


if __name__ == "__main__":
    unittest.main()
