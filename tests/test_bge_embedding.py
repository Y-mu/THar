from __future__ import annotations

import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from langHar.infrastructure.rag.embedding import BGEEmbeddingManager


class BGEModelDownloadTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.model_dir = (Path(directory.name) / "model").resolve()
        environment = patch.dict(os.environ, {"RAG_EMBEDDING_MODEL_PATH": str(self.model_dir)})
        environment.start()
        self.addCleanup(environment.stop)
        downloader = patch("langHar.infrastructure.rag.embedding.snapshot_download")
        self.download = downloader.start()
        self.addCleanup(downloader.stop)

    def make_model_files(self, **kwargs: object) -> None:
        self.model_dir.mkdir(parents=True, exist_ok=True)
        for filename in ("config.json", "tokenizer_config.json", "vocab.txt", "model.safetensors"):
            (self.model_dir / filename).write_text("fixture", encoding="utf-8")

    def test_missing_model_is_downloaded(self) -> None:
        self.download.side_effect = self.make_model_files

        self.assertEqual(BGEEmbeddingManager._ensure_model_available(), self.model_dir)
        self.assertEqual(self.download.call_args.kwargs["repo_id"], BGEEmbeddingManager.MODEL_NAME)
        self.assertEqual(self.download.call_args.kwargs["local_dir"], str(self.model_dir))

    def test_complete_model_does_not_use_network(self) -> None:
        self.make_model_files()

        self.assertEqual(BGEEmbeddingManager._ensure_model_available(), self.model_dir)
        self.download.assert_not_called()

    def test_partial_directory_triggers_download(self) -> None:
        self.model_dir.mkdir()
        (self.model_dir / "config.json").write_text("{}")
        self.download.side_effect = self.make_model_files

        BGEEmbeddingManager._ensure_model_available()
        self.download.assert_called_once()

    def test_empty_weights_trigger_download(self) -> None:
        self.make_model_files()
        (self.model_dir / "model.safetensors").write_bytes(b"")
        self.download.side_effect = self.make_model_files

        BGEEmbeddingManager._ensure_model_available()
        self.download.assert_called_once()

    def test_embedding_is_loaded_only_from_local_files(self) -> None:
        self.make_model_files()
        with (
            patch.object(BGEEmbeddingManager, "_detect_device", return_value="cpu"),
            patch("langHar.infrastructure.rag.embedding.HuggingFaceEmbeddings") as embedding,
        ):
            BGEEmbeddingManager._build_embedding()
            self.assertEqual(
                embedding.call_args.kwargs["model_kwargs"],
                {"device": "cpu", "local_files_only": True},
            )
            self.assertEqual(
                embedding.call_args.kwargs["query_encode_kwargs"],
                {
                    "batch_size": 32,
                    "normalize_embeddings": True,
                    "prompt": BGEEmbeddingManager.QUERY_INSTRUCTION,
                },
            )
            self.assertNotIn("prompt", embedding.call_args.kwargs["encode_kwargs"])
            self.download.assert_not_called()

    def test_download_failure_can_be_retried(self) -> None:
        self.download.side_effect = ConnectionError("offline")
        with self.assertRaisesRegex(FileNotFoundError, "自动下载.*失败"):
            BGEEmbeddingManager._ensure_model_available()

        self.download.side_effect = self.make_model_files
        self.assertEqual(BGEEmbeddingManager._ensure_model_available(), self.model_dir)

    def test_incomplete_download_is_not_accepted(self) -> None:
        self.download.return_value = str(self.model_dir)
        with self.assertRaisesRegex(FileNotFoundError, "下载不完整"):
            BGEEmbeddingManager._ensure_model_available()

    def test_concurrent_initialization_builds_one_instance(self) -> None:
        with (
            patch.object(BGEEmbeddingManager, "_instance", None),
            patch.object(BGEEmbeddingManager, "_build_embedding", return_value=object()) as build,
            ThreadPoolExecutor(max_workers=4) as executor,
        ):
            instances = list(executor.map(lambda _: BGEEmbeddingManager.get_embeddings(), range(8)))
            build.assert_called_once()
            self.assertTrue(all(instance is instances[0] for instance in instances))


class BGEDeviceTests(unittest.TestCase):
    def test_mps_is_selected_when_available(self) -> None:
        with (
            patch("torch.cuda.is_available", return_value=False),
            patch("torch.backends.mps.is_available", return_value=True),
            patch("builtins.print"),
        ):
            self.assertEqual(BGEEmbeddingManager._detect_device(), "mps")

    def test_mps_runtime_reason_is_reported_when_unavailable(self) -> None:
        with (
            patch("torch.cuda.is_available", return_value=False),
            patch("torch.backends.mps.is_available", return_value=False),
            patch("torch.backends.mps.is_built", return_value=True),
            patch("torch.empty", side_effect=RuntimeError("MPS requires macOS 14.0+")),
            patch("builtins.print") as output,
        ):
            self.assertEqual(BGEEmbeddingManager._detect_device(), "cpu")
            self.assertIn("macOS 14.0+", output.call_args.args[0])

    def test_missing_mps_build_is_reported(self) -> None:
        with (
            patch("torch.cuda.is_available", return_value=False),
            patch("torch.backends.mps.is_available", return_value=False),
            patch("torch.backends.mps.is_built", return_value=False),
            patch("torch.empty") as allocate,
            patch("builtins.print") as output,
        ):
            self.assertEqual(BGEEmbeddingManager._detect_device(), "cpu")
            self.assertIn("未编译 MPS 支持", output.call_args.args[0])
            allocate.assert_not_called()
