from __future__ import annotations

import base64
import fcntl
import hashlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

import pyarrow as pa
import pyarrow.parquet as pq

from asterion.dci.cli import main as cli_main
from asterion.dci.export import (
    CANARY,
    DciExportError,
    _decrypt,
    _derive_key,
    _pick_col,
    build_filename,
    export_bcplus,
    export_bcplus_qa,
    export_bright,
    export_subset,
    extract_title,
    get_domain,
    safe_relative_path,
    sanitize_name,
    unique_path,
)


ROOT = Path(__file__).resolve().parents[1]


def _encrypt(value: str) -> str:
    raw = value.encode("utf-8")
    key = _derive_key(CANARY, len(raw))
    return base64.b64encode(bytes(a ^ b for a, b in zip(raw, key))).decode()


def _parquet(path: Path, rows: list[dict[str, object]], *, row_group_size: int = 1) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist(rows), path, row_group_size=row_group_size)


class AsterionDciExportTests(unittest.TestCase):
    def test_scripts_bcplus_eval_extract_bcplus_qa_py_function_derive_key(self) -> None:
        self.assertEqual(_derive_key("x", 65), hashlib.sha256(b"x").digest() * 2 + hashlib.sha256(b"x").digest()[:1])

    def test_scripts_bcplus_eval_extract_bcplus_qa_py_function_decrypt(self) -> None:
        self.assertEqual(_decrypt(_encrypt("问题")), "问题")
        for value in ("%%%", base64.b64encode(b"\xff").decode()):
            with self.assertRaises(DciExportError):
                _decrypt(value)

    def test_scripts_bcplus_eval_extract_bcplus_qa_py_function_pick_col(self) -> None:
        self.assertEqual(_pick_col(["QID", "Question", "Target"], ["qid", "id"]), "QID")
        with self.assertRaises(DciExportError):
            _pick_col(["other"], ["qid"])

    def test_scripts_bcplus_eval_extract_bcplus_qa_py_durable_output_output_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve(); source = root / "source"; output = root / "qa.jsonl"
            _parquet(source / "b10.parquet", [{"QID": "3", "Question": _encrypt("q3"), "Target": _encrypt("a3")}])
            _parquet(source / "b2.parquet", [{"QID": "1", "Question": _encrypt("q1"), "Target": _encrypt("a1")}, {"QID": "2", "Question": _encrypt("q2"), "Target": _encrypt("a2")}], row_group_size=1)
            self.assertEqual(export_bcplus_qa(source, output), 3)
            rows = [json.loads(line) for line in output.read_text().splitlines()]
            self.assertEqual([row["query_id"] for row in rows], ["1", "2", "3"])
            before = output.stat().st_ino
            self.assertEqual(export_bcplus_qa(source, output), 3)
            self.assertEqual(output.stat().st_ino, before)

    def test_scripts_bcplus_eval_extract_bcplus_qa_py_function_main(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve(); source = root / "s"; output = root / "o.jsonl"
            _parquet(source / "x.parquet", [{"id": 7, "problem": "raw", "solution": "answer"}])
            self.assertEqual(cli_main(["export", "bcplus-qa", "--parquet-dir", str(source), "--output", str(output), "--no-decrypt"], repo_root=ROOT, stdout=io.StringIO(), stderr=io.StringIO()), 0)
            self.assertEqual(json.loads(output.read_text())["query"], "raw")

    def test_scripts_bcplus_eval_extract_bcplus_qa_py_cli_flag_no_decrypt(self) -> None:
        self.assertIn("--no-decrypt", cli_main_help("export", "bcplus-qa"))

    def test_scripts_bcplus_eval_extract_bcplus_qa_py_cli_flag_output(self) -> None:
        self.assertIn("--output", cli_main_help("export", "bcplus-qa"))

    def test_scripts_bcplus_eval_extract_bcplus_qa_py_cli_flag_parquet_dir(self) -> None:
        self.assertIn("--parquet-dir", cli_main_help("export", "bcplus-qa"))

    def test_src_dci_benchmark_export_bc_plus_docs_py_function_extract_title(self) -> None:
        self.assertEqual(extract_title("x\nTitle:  Example  \ny"), "Example")
        self.assertIsNone(extract_title("none"))

    def test_src_dci_benchmark_export_bc_plus_docs_py_function_sanitize_name(self) -> None:
        self.assertEqual(sanitize_name(' a<>:"/\\|?*  b. ', "fallback"), "a b")
        self.assertEqual(sanitize_name("...", "fallback"), "fallback")
        self.assertEqual(sanitize_name("CON", "fallback"), "fallback")

    def test_src_dci_benchmark_export_bc_plus_docs_py_function_get_domain(self) -> None:
        self.assertEqual(get_domain("https://EXAMPLE.com/a"), "example.com")
        self.assertEqual(get_domain("not a url"), "unknown-domain")

    def test_src_dci_benchmark_export_bc_plus_docs_py_function_build_filename(self) -> None:
        self.assertEqual(build_filename(None, "https://x.test/a.txt", "9"), "a.txt.txt")
        self.assertLessEqual(len(Path(build_filename("x" * 300, "", "9")).stem), 140)

    def test_src_dci_benchmark_export_bc_plus_docs_py_function_unique_path(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve(); path = root / "Name.txt"; path.write_text("one")
            self.assertEqual(unique_path(path, "7", "one"), path)
            self.assertEqual(unique_path(path, "7", "two").name, "Name__docid_7.txt")
            (root / "Name__docid_7.txt").write_text("three")
            self.assertEqual(unique_path(path, "7", "two").name, "Name__docid_7_2.txt")

    def test_src_dci_benchmark_export_bc_plus_docs_py_durable_output_domain_title_txt(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve(); source = root / "source"; output = root / "output"
            _parquet(source / "part.parquet", [
                {"docid": "2", "text": "Title: Same\nsecond", "url": "https://Example.com/b"},
                {"docid": "1", "text": "Title: Same\nfirst", "url": "https://example.com/a"},
                {"docid": "3", "text": "Title: SAME\nthird", "url": "https://example.com/c"},
            ])
            self.assertEqual(export_bcplus(source, output), 3)
            names = sorted(path.name for path in (output / "example.com").glob("*.txt"))
            self.assertEqual(names, ["SAME__docid_3.txt", "Same.txt", "Same__docid_1.txt"])
            self.assertEqual(export_bcplus(source, output), 3)

    def test_src_dci_benchmark_export_bc_plus_docs_py_function_main(self) -> None:
        self.assertIn("bcplus", cli_main_help("export"))

    def test_src_dci_benchmark_export_bc_plus_docs_py_function_parse_args(self) -> None:
        self.assertIn("export", cli_main_help())

    def test_src_dci_benchmark_export_bc_plus_docs_py_cli_flag_output_dir(self) -> None:
        self.assertIn("--output-dir", cli_main_help("export", "bcplus"))

    def test_src_dci_benchmark_export_bc_plus_docs_py_cli_flag_source_dir(self) -> None:
        self.assertIn("--source-dir", cli_main_help("export", "bcplus"))

    def test_src_dci_benchmark_export_bright_docs_py_function_safe_relative_path(self) -> None:
        self.assertEqual(safe_relative_path("a/b.txt"), Path("a/b.txt"))
        for value in ("", "/a", "../a", "a/../b", "a\\b", "C:/x", "CON", "a./b"):
            with self.assertRaises(DciExportError, msg=value):
                safe_relative_path(value)

    def test_src_dci_benchmark_export_bright_docs_py_function_export_subset(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve(); source = root / "source"; output = root / "output"
            _parquet(source / "p.parquet", [{"id": "nested/a.txt", "content": "A"}, {"id": "nested/b.txt", "content": None}])
            self.assertEqual(export_subset(source, output), 2)
            self.assertEqual((output / "nested/a.txt").read_text(), "A")
            self.assertEqual((output / "nested/b.txt").read_text(), "")
            self.assertEqual((output / ".dci_export_complete").read_text(), "2\n")

    def test_src_dci_benchmark_export_bright_docs_py_durable_output_dci_export_complete(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve(); source = root / "source"; output = root / "output"
            _parquet(source / "p.parquet", [{"id": "ok", "content": "A"}, {"id": "../bad", "content": "B"}])
            with self.assertRaises(DciExportError):
                export_subset(source, output)
            self.assertFalse((output / ".dci_export_complete").exists())
            _parquet(source / "p.parquet", [{"id": "ok", "content": "A"}])
            self.assertEqual(export_subset(source, output), 1)
            self.assertTrue((output / ".dci_export_complete").is_file())

    def test_src_dci_benchmark_export_bright_docs_py_durable_output_subset_id(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve(); source = root / "source"; output = root / "output"
            for subset in ("biology", "earth_science", "economics", "robotics"):
                _parquet(source / subset / "p.parquet", [{"id": f"{subset}.txt", "content": subset}])
            self.assertEqual(export_bright(source, output, ("robotics",)), 1)
            self.assertFalse((output / "biology").exists())
            self.assertEqual(export_bright(source, output), 4)

    def test_src_dci_benchmark_export_bright_docs_py_function_main(self) -> None:
        self.assertIn("bright", cli_main_help("export"))

    def test_src_dci_benchmark_export_bright_docs_py_function_parse_args(self) -> None:
        self.assertIn("--subset", cli_main_help("export", "bright"))

    def test_src_dci_benchmark_export_bright_docs_py_cli_flag_output_root(self) -> None:
        self.assertIn("--output-root", cli_main_help("export", "bright"))

    def test_src_dci_benchmark_export_bright_docs_py_cli_flag_source_root(self) -> None:
        self.assertIn("--source-root", cli_main_help("export", "bright"))

    def test_src_dci_benchmark_export_bright_docs_py_cli_flag_subset(self) -> None:
        self.assertIn("--subset", cli_main_help("export", "bright"))

    def test_exporters_reject_schema_symlink_overlap_and_portable_collisions(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve(); source = root / "source"; output = root / "output"
            _parquet(source / "bad.parquet", [{"other": "x"}])
            with self.assertRaises(DciExportError): export_bcplus(source, output)
            with self.assertRaises(DciExportError): export_bcplus_qa(source, root / "q.jsonl")
            with self.assertRaises(DciExportError): export_bcplus(source, source / "nested")
            link = root / "link"; link.symlink_to(source, target_is_directory=True)
            with self.assertRaises(DciExportError): export_bcplus(link, output)
            _parquet(source / "bad.parquet", [{"id": "Café", "content": "one"}, {"id": "Café", "content": "two"}])
            with self.assertRaises(DciExportError): export_subset(source, output)

    def test_exclusive_lock_and_interrupted_rerun(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve(); source = root / "source"; output = root / "output"
            _parquet(source / "p.parquet", [{"id": "a", "content": "A"}])
            output.mkdir(); (output / ".asterion-dci-export.lock").write_text("held")
            self.assertEqual(export_subset(source, output), 1)
            lock = (output / ".asterion-dci-export.lock").open("a+")
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaises(DciExportError): export_subset(source, output)
            fcntl.flock(lock, fcntl.LOCK_UN); lock.close()
            self.assertEqual(export_subset(source, output), 1)

    def test_qa_overlap_nested_symlink_nulls_and_natural_collision_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve(); source = root / "source"; output = root / "output"
            _parquet(source / "qa.parquet", [{"id": "1", "query": "q", "answer": "a"}])
            with self.assertRaises(DciExportError):
                export_bcplus_qa(source, source / "qa.jsonl", decrypt=False)
            nested = root / "nested"; nested.mkdir(); (nested / "link").symlink_to(source, target_is_directory=True)
            with self.assertRaises(DciExportError):
                export_bcplus(nested / "link", output)
            _parquet(source / "qa.parquet", [{"docid": "1", "text": None, "url": "https://x"}])
            with self.assertRaises(DciExportError): export_bcplus(source, output)
            _parquet(source / "qa.parquet", [{"id": "file02", "content": "one"}, {"id": "file2", "content": "two"}])
            with self.assertRaises(DciExportError): export_subset(source, output)

    def test_cli_failures_are_body_free_and_module_has_no_baseline_import(self) -> None:
        err = io.StringIO(); out = io.StringIO()
        self.assertEqual(cli_main(["export", "bcplus", "--source-dir", "/missing", "--output-dir", "/tmp/out"], repo_root=ROOT, stdout=out, stderr=err), 2)
        self.assertEqual(out.getvalue(), "")
        self.assertEqual(err.getvalue(), "DCI export failed\n")
        source = (ROOT / "packages/python/asterion-core/src/asterion/dci/export.py").read_text()
        self.assertNotIn("src.dci", source)
        self.assertNotIn("import pandas", source)
        self.assertNotIn("concat(", source)

    def test_installed_wheel_exports_without_repository_baseline(self) -> None:
        source = (ROOT / "packages/python/asterion-core/pyproject.toml").read_text()
        self.assertIn("pyarrow", source)
        self.assertTrue(importlib.util.find_spec("asterion.dci.export"))


def cli_main_help(*args: str) -> str:
    stdout = io.StringIO()
    status = cli_main([*args, "--help"], repo_root=ROOT, stdout=stdout, stderr=io.StringIO())
    if status != 0:
        raise AssertionError(f"help exited {status}")
    return stdout.getvalue()


if __name__ == "__main__":
    unittest.main()
