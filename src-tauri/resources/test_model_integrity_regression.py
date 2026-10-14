import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(__file__))

import hf_cache_utils
import qwen3_asr_server


class ModelIntegrityRegressionTests(unittest.TestCase):
    invalid_manifests = (
        "malformed",
        "size-mismatch",
        "hash-mismatch",
        "missing-listed-file",
    )

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.cache_root = Path(directory.name)
        root = mock.patch.object(hf_cache_utils, "get_hf_cache_root", return_value=str(self.cache_root))
        root.start()
        self.addCleanup(root.stop)

    def cached_model(self, case):
        config = {"repo_id": f"test/{case}", "filename": "model.gguf"}
        snapshot = self.cache_root / ("models--" + config["repo_id"].replace("/", "--")) / "snapshots" / "revision"
        snapshot.mkdir(parents=True)
        weight = b"x" * 1_000_001
        path = snapshot / config["filename"]
        path.write_bytes(weight)
        item = {"path": config["filename"], "size": len(weight), "sha256": hashlib.sha256(weight).hexdigest()}
        manifest = {"files": [item]}
        if case == "legacy":
            return config, snapshot, path
        if case == "malformed":
            (snapshot / hf_cache_utils.COMPLETE_MANIFEST_NAME).write_text("{", encoding="utf-8")
            return config, snapshot, path
        if case == "size-mismatch":
            item["size"] += 1
        elif case == "hash-mismatch":
            item["sha256"] = "0" * 64
        elif case == "missing-listed-file":
            manifest["files"].append({"path": "config.json", "size": 2})
        elif case == "unlisted-required-file":
            (snapshot / "other.gguf").write_bytes(weight)
            item["path"] = "other.gguf"
        (snapshot / hf_cache_utils.COMPLETE_MANIFEST_NAME).write_text(json.dumps(manifest), encoding="utf-8")
        return config, snapshot, path

    def test_present_invalid_manifest_cannot_fall_back_to_legacy_readiness(self):
        for case in self.invalid_manifests:
            with self.subTest(case=case):
                config, snapshot, _ = self.cached_model(case)
                self.assertFalse(hf_cache_utils._snapshot_matches_completion_manifest(snapshot))
                self.assertFalse(
                    hf_cache_utils.is_hf_repo_ready(config["repo_id"]),
                    "a large weight cannot override a present invalid completion manifest",
                )

    def test_exact_model_resolver_rejects_invalid_or_unlisted_manifest_files(self):
        for case in (*self.invalid_manifests, "unlisted-required-file"):
            with self.subTest(case=case):
                config, _, _ = self.cached_model(case)
                self.assertIsNone(hf_cache_utils.find_hf_snapshot_file(config["repo_id"], config["filename"]))
                server = qwen3_asr_server.Qwen3ASRServer.__new__(qwen3_asr_server.Qwen3ASRServer)
                server.model_config = config
                self.assertIsNone(server._resolve_model_path())

    def test_qwen_initialization_refuses_corrupt_cache_before_loading_runtime(self):
        for case in self.invalid_manifests:
            with (
                self.subTest(case=case),
                mock.patch.object(qwen3_asr_server.Qwen3ASRServer, "_detect_device", return_value="cpu"),
                mock.patch.object(qwen3_asr_server.Qwen3ASRServer, "_load_runtime") as load,
                mock.patch.object(qwen3_asr_server.Qwen3ASRServer, "_warmup_inference"),
                mock.patch.object(qwen3_asr_server.Qwen3ASRServer, "_get_gpu_device_info", return_value={"device": "cpu"}),
                mock.patch.object(qwen3_asr_server, "FireRedVad"),
            ):
                config, _, _ = self.cached_model(case)
                server = qwen3_asr_server.Qwen3ASRServer(engine="qwen3-asr-0.6b")
                server.model_config = config
                response = server.initialize()
                self.assertFalse(response["success"])
                self.assertFalse(server.initialized)
                load.assert_not_called()

    def test_valid_manifest_and_no_manifest_legacy_cache_remain_usable(self):
        for case in ("valid", "legacy"):
            with self.subTest(case=case):
                config, _, path = self.cached_model(case)
                self.assertTrue(hf_cache_utils.is_hf_repo_ready(config["repo_id"]))
                self.assertEqual(hf_cache_utils.find_hf_snapshot_file(config["repo_id"], config["filename"]), str(path))

    def test_missing_cache_is_unavailable_to_readiness_and_loader(self):
        self.assertFalse(hf_cache_utils.is_hf_repo_ready("test/missing"))
        self.assertIsNone(hf_cache_utils.find_hf_snapshot_file("test/missing", "model.gguf"))


if __name__ == "__main__":
    unittest.main()
