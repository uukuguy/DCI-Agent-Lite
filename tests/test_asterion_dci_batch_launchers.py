from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from asterion.dci.cli import main


ROOT = Path(__file__).resolve().parents[1]
_MODULE_ENVIRONMENT: dict[str, str] | None = None
SOURCE_LAUNCHER_ROOT = ROOT / "scripts"
ASTERION_LAUNCHER_ROOT = ROOT / "asterion/scripts"
PROFILE_RESOURCE = (
    ROOT
    / "asterion/src/asterion/dci/resources/batch-profiles.json"
)

SOURCE_LAUNCHERS = {
    path.relative_to(SOURCE_LAUNCHER_ROOT).as_posix()
    for family in ("bcplus_eval", "qa", "bright")
    for path in (SOURCE_LAUNCHER_ROOT / family).glob("run_*.sh")
}
TARGET_LAUNCHERS = {
    path.relative_to(ASTERION_LAUNCHER_ROOT).as_posix()
    for family in ("bcplus_eval", "qa", "bright")
    for path in (ASTERION_LAUNCHER_ROOT / family).glob("run_*.sh")
}

PROFILE_NAMES = {
    "bcplus.level3",
    "bcplus.openai",
    "qa.2wikimultihopqa",
    "qa.bamboogle",
    "qa.hotpotqa",
    "qa.musique",
    "qa.nq",
    "qa.triviaqa",
    "bright.biology",
    "bright.earth-science",
    "bright.economics",
    "bright.robotics",
    "beir.arguana",
    "beir.scifact",
}


def setUpModule() -> None:
    global _MODULE_ENVIRONMENT
    _MODULE_ENVIRONMENT = os.environ.copy()


def tearDownModule() -> None:
    assert _MODULE_ENVIRONMENT is not None
    os.environ.clear()
    os.environ.update(_MODULE_ENVIRONMENT)

PRIMARY_LAUNCHERS = {
    "bcplus_eval/run_bcplus_eval_openai.sh": (
        "bcplus.openai",
        "data/bcplus_qa.jsonl",
        "corpus/bc_plus_docs",
    ),
    "qa/run_2wikimultihopqa_dev_sample50.sh": (
        "qa.2wikimultihopqa",
        "data/dci-bench/data/2wikimultihopqa/test.jsonl",
        "corpus/wiki_corpus",
    ),
    "qa/run_bamboogle_test_sample50.sh": (
        "qa.bamboogle",
        "data/dci-bench/data/bamboogle/test.jsonl",
        "corpus/wiki_corpus",
    ),
    "qa/run_hotpotqa_dev_sample50.sh": (
        "qa.hotpotqa",
        "data/dci-bench/data/hotpotqa/test.jsonl",
        "corpus/wiki_corpus",
    ),
    "qa/run_musique_dev_sample50.sh": (
        "qa.musique",
        "data/dci-bench/data/musique/test.jsonl",
        "corpus/wiki_corpus",
    ),
    "qa/run_nq_test_sample50.sh": (
        "qa.nq",
        "data/dci-bench/data/nq/test.jsonl",
        "corpus/wiki_corpus",
    ),
    "qa/run_triviaqa_test_sample50.sh": (
        "qa.triviaqa",
        "data/dci-bench/data/triviaqa/test.jsonl",
        "corpus/wiki_corpus",
    ),
    "bright/run_bio.sh": (
        "bright.biology",
        "data/dci-bench/data/bright_biology/bright_biology.jsonl",
        "corpus/bright_corpus/biology",
    ),
    "bright/run_earth_science.sh": (
        "bright.earth-science",
        "data/dci-bench/data/bright_earth_science/bright_earth_science.jsonl",
        "corpus/bright_corpus/earth_science",
    ),
    "bright/run_economics.sh": (
        "bright.economics",
        "data/dci-bench/data/bright_economics/economics_full.jsonl",
        "corpus/bright_corpus/economics",
    ),
    "bright/run_robotics.sh": (
        "bright.robotics",
        "data/dci-bench/data/bright_robotics/bright_robotics.jsonl",
        "corpus/bright_corpus/robotics",
    ),
}
PRIMARY_PROFILE_NAMES = {profile for profile, _, _ in PRIMARY_LAUNCHERS.values()}


class AsterionDciBatchLauncherTests(unittest.TestCase):
    def test_docs_superpowers_plans_2026_07_14_af_240_batch_evaluation_export_parity_md_target_feature_installed_batch_profiles(
        self,
    ) -> None:
        document = json.loads(PROFILE_RESOURCE.read_text(encoding="utf-8"))
        self.assertEqual(document["schema"], "asterion.dci.batch-profiles/v1")
        self.assertEqual(set(document["profiles"]), PROFILE_NAMES)
        for name, profile in document["profiles"].items():
            with self.subTest(profile=name):
                if name in PRIMARY_PROFILE_NAMES:
                    self.assertNotIn("provider", profile)
                    self.assertNotIn("model", profile)
                else:
                    self.assertEqual(profile["provider"], "openai")
                    self.assertEqual(profile["model"], "gpt-5.4-nano")
                self.assertEqual(profile["tools"], "read,bash")
                self.assertEqual(profile["node_max_old_space_size_mb"], 8192)
                self.assertIn(
                    profile["runtime_context_level"],
                    {"level0", "level1", "level2", "level3", "level4"},
                )
                self.assertFalse(Path(profile["dataset"]).is_absolute())
                self.assertFalse(Path(profile["output_root"]).is_absolute())
                self.assertFalse(Path(profile["corpus"]).is_absolute())
                self.assertTrue(profile["output_root"].startswith("outputs/asterion/"))

    def test_profiles_match_every_source_launcher_mapping(self) -> None:
        profiles = json.loads(PROFILE_RESOURCE.read_text(encoding="utf-8"))["profiles"]
        expected = {
            "bcplus.level3": ("data/bcplus_qa.jsonl", "corpus/bc_plus_docs", "qa", 10, 300),
            "bcplus.openai": ("data/bcplus_qa.jsonl", "corpus/bc_plus_docs", "qa", 10, 100),
            "qa.2wikimultihopqa": ("data/dci-bench/data/2wikimultihopqa/test.jsonl", "corpus/wiki_corpus", "qa", 5, 300),
            "qa.bamboogle": ("data/dci-bench/data/bamboogle/test.jsonl", "corpus/wiki_corpus", "qa", 5, 300),
            "qa.hotpotqa": ("data/dci-bench/data/hotpotqa/test.jsonl", "corpus/wiki_corpus", "qa", 5, 300),
            "qa.musique": ("data/dci-bench/data/musique/test.jsonl", "corpus/wiki_corpus", "qa", 5, 300),
            "qa.nq": ("data/dci-bench/data/nq/test.jsonl", "corpus/wiki_corpus", "qa", 5, 300),
            "qa.triviaqa": ("data/dci-bench/data/triviaqa/test.jsonl", "corpus/wiki_corpus", "qa", 5, 300),
            "bright.biology": ("data/dci-bench/data/bright_biology/bright_biology.jsonl", "corpus/bright_corpus/biology", "ir", 20, 300),
            "bright.earth-science": ("data/dci-bench/data/bright_earth_science/bright_earth_science.jsonl", "corpus/bright_corpus/earth_science", "ir", 10, 300),
            "bright.economics": ("data/dci-bench/data/bright_economics/economics_full.jsonl", "corpus/bright_corpus/economics", "ir", 10, 300),
            "bright.robotics": ("data/dci-bench/data/bright_robotics/bright_robotics.jsonl", "corpus/bright_corpus/robotics", "ir", 20, 300),
            "beir.arguana": ("data/dci-bench/data/beir_arguana/test.jsonl", "corpus/beir/arguana", "ir", 10, 300),
            "beir.scifact": ("data/dci-bench/data/beir_scifact/test.jsonl", "corpus/beir/scifact", "ir", 10, 300),
        }
        for name, values in expected.items():
            with self.subTest(profile=name):
                profile = profiles[name]
                self.assertEqual(
                    (profile["dataset"], profile["corpus"], profile["mode"], profile["max_concurrency"], profile["max_turns"]),
                    values,
                )

    def test_launchers_have_exact_one_to_one_names_and_independent_commands(self) -> None:
        renamed_source = {
            path.replace("bcplus_eval/", "bcplus_eval/") for path in SOURCE_LAUNCHERS
        }
        self.assertEqual(TARGET_LAUNCHERS, renamed_source)
        for relative in sorted(TARGET_LAUNCHERS):
            text = (ASTERION_LAUNCHER_ROOT / relative).read_text(encoding="utf-8")
            with self.subTest(launcher=relative):
                self.assertIn("asterion-dci benchmark", text)
                self.assertIn('"$@"', text)
                self.assertIn("--profile", text)
                if relative not in PRIMARY_LAUNCHERS:
                    self.assertIn("--limit", text)
                self.assertIn("[ -f", text)
                self.assertIn("[ -d", text)
                self.assertNotIn("src/dci", text)
                self.assertNotIn("scripts/bcplus_eval/run_bcplus_eval.py", text)
                self.assertNotIn("uv run python", text)
                if relative in PRIMARY_LAUNCHERS:
                    self.assertIn(
                        'uv run --project "$PROJECT_ROOT" asterion-dci benchmark',
                        text,
                    )
                    self.assertNotIn("command=(asterion-dci", text)

    def test_all_primary_launchers_execute_repository_source_without_bare_cli(self) -> None:
        uv = shutil.which("uv")
        self.assertIsNotNone(uv)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            for _profile, dataset_relative, corpus_relative in PRIMARY_LAUNCHERS.values():
                dataset = root / dataset_relative
                dataset.parent.mkdir(parents=True, exist_ok=True)
                dataset.write_text("{}\n", encoding="utf-8")
                (root / corpus_relative).mkdir(parents=True, exist_ok=True)
            clean_bin = root / "bin"
            clean_bin.mkdir()
            uv_wrapper = clean_bin / "uv"
            uv_wrapper.write_text(
                f'#!/bin/sh\nexec "{uv}" "$@"\n', encoding="utf-8"
            )
            uv_wrapper.chmod(0o755)
            clean_path = os.pathsep.join((str(clean_bin), "/usr/bin", "/bin"))
            self.assertIsNone(shutil.which("asterion-dci", path=clean_path))
            environment = os.environ.copy()
            environment.pop("VIRTUAL_ENV", None)
            environment.update(
                {
                    "PATH": clean_path,
                    "ASTERION_DCI_RESOURCE_ROOT": str(root),
                }
            )

            for relative in sorted(PRIMARY_LAUNCHERS):
                launcher = ASTERION_LAUNCHER_ROOT / relative
                with self.subTest(relative=relative):
                    result = subprocess.run(
                        ["bash", str(launcher), "--help"],
                        cwd=ROOT,
                        env=environment,
                        capture_output=True,
                        text=True,
                        timeout=30,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn("usage: asterion-dci benchmark", result.stdout)

    def test_all_eleven_primary_pairs_are_thin_and_forward_literal_limit_once(self) -> None:
        self.assertEqual(len(PRIMARY_LAUNCHERS), 11)
        for relative, (profile, dataset_relative, corpus_relative) in PRIMARY_LAUNCHERS.items():
            for product in ("source", "asterion"):
                with self.subTest(relative=relative, product=product), tempfile.TemporaryDirectory() as td:
                    root = Path(td).resolve()
                    launcher_root = root / ("scripts" if product == "source" else "asterion/scripts")
                    launcher = launcher_root / relative
                    launcher.parent.mkdir(parents=True, exist_ok=True)
                    actual_root = SOURCE_LAUNCHER_ROOT if product == "source" else ASTERION_LAUNCHER_ROOT
                    launcher.write_text(
                        (actual_root / relative).read_text(encoding="utf-8"),
                        encoding="utf-8",
                    )
                    (root / ".env").write_text(
                        "DCI_PROVIDER=dotenv-provider\nDCI_MODEL=dotenv-model\n",
                        encoding="utf-8",
                    )
                    dataset = root / dataset_relative
                    dataset.parent.mkdir(parents=True, exist_ok=True)
                    dataset.write_text("{}\n", encoding="utf-8")
                    (root / corpus_relative).mkdir(parents=True, exist_ok=True)
                    bin_dir = root / "bin"
                    bin_dir.mkdir()
                    fake = bin_dir / "uv"
                    fake.write_text(
                        '#!/usr/bin/env bash\nprintf "%s\\n" "$DCI_PROVIDER" > "$CAPTURE_PROVIDER"\nprintf "%s\\n" "$@" > "$CAPTURE_ARGS"\n',
                        encoding="utf-8",
                    )
                    fake.chmod(0o755)
                    capture_args = root / f"{product}-args.txt"
                    capture_provider = root / f"{product}-provider.txt"
                    forwarded = ["--limit", "1", "--resume-policy", "fresh"]
                    result = subprocess.run(
                        ["bash", str(launcher), *forwarded],
                        env=os.environ
                        | {
                            "PATH": f"{bin_dir}:{os.environ['PATH']}",
                            "DCI_PROVIDER": "exported",
                            "ASTERION_DCI_RESOURCE_ROOT": str(root),
                            "ASTERION_DCI_BATCH_LIMIT": "9",
                            "CAPTURE_ARGS": str(capture_args),
                            "CAPTURE_PROVIDER": str(capture_provider),
                        },
                        capture_output=True,
                        text=True,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)
                    argv = capture_args.read_text(encoding="utf-8").splitlines()
                    self.assertEqual(capture_provider.read_text(encoding="utf-8").strip(), "exported")
                    self.assertEqual(argv.count("--limit"), 1)
                    self.assertEqual(argv.count("1"), 1)
                    self.assertEqual(argv.count("--resume-policy"), 1)
                    self.assertEqual(argv.count("fresh"), 1)
                    self.assertTrue(any(value.endswith(dataset_relative) for value in argv), argv)
                    corpus_flag = "--corpus-dir" if product == "source" else "--corpus"
                    self.assertIn(corpus_flag, argv)
                    self.assertTrue(any(value.endswith(corpus_relative) for value in argv), argv)
                    if product == "asterion":
                        self.assertEqual(
                            argv[:5],
                            [
                                "run",
                                "--project",
                                str(root / "asterion"),
                                "asterion-dci",
                                "benchmark",
                            ],
                        )
                        self.assertIn(profile, argv)
                    self.assertNotIn("--provider", argv)
                    self.assertNotIn("--model", argv)
                    if relative == "bcplus_eval/run_bcplus_eval_openai.sh":
                        context_index = argv.index("--runtime-context-level")
                        self.assertEqual(argv[context_index + 1], "level3")
                        self.assertNotIn("--thinking-level", argv)

                    text = launcher.read_text(encoding="utf-8")
                    self.assertEqual(text.count('"$@"'), 1)
                    self.assertNotIn('source "$REPO_ROOT/.env"', text)
                    self.assertNotIn("--provider openai", text)
                    self.assertNotIn("--model gpt-5.4-nano", text)

    def test_all_eleven_source_launchers_fail_closed_before_unbounded_work(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            dataset = root / "dataset.jsonl"
            dataset.write_text(
                json.dumps({"query_id": "q-1", "query": "q", "answer": "a"})
                + "\n",
                encoding="utf-8",
            )
            corpus = root / "corpus"
            corpus.mkdir()
            for index, relative in enumerate(sorted(PRIMARY_LAUNCHERS)):
                output = root / f"output-{index}"
                with self.subTest(relative=relative):
                    result = subprocess.run(
                        [
                            "bash",
                            str(SOURCE_LAUNCHER_ROOT / relative),
                            "--dataset",
                            str(dataset),
                            "--corpus-dir",
                            str(corpus),
                            "--output-root",
                            str(output),
                            "--max-concurrency",
                            "1",
                        ],
                        cwd=ROOT,
                        capture_output=True,
                        text=True,
                        timeout=30,
                    )
                    self.assertEqual(result.returncode, 2, result.stderr)
                    self.assertIn("coordinator-issued AF-340 authorization", result.stderr)
                    self.assertFalse(output.exists())

    def test_paper_beir_launchers_bind_exact_profiles_without_source_parity_claim(self) -> None:
        for relative, profile_name in (
            ("beir/benchmark_arguana.sh", "beir.arguana"),
            ("beir/benchmark_scifact.sh", "beir.scifact"),
        ):
            launcher = ASTERION_LAUNCHER_ROOT / relative
            text = launcher.read_text(encoding="utf-8")
            with self.subTest(relative=relative):
                self.assertIn(f"--profile {profile_name}", text)
                self.assertNotIn('source "$REPO_ROOT/.env"', text)
                self.assertEqual(
                    subprocess.run(
                        ["bash", "-n", str(launcher)], capture_output=True, text=True
                    ).returncode,
                    0,
                )

    def test_dynamic_launcher_preserves_positional_context_thinking_and_limit(self) -> None:
        text = (
            ASTERION_LAUNCHER_ROOT / "bcplus_eval/run_bcplus_eval_openai.sh"
        ).read_text(encoding="utf-8")
        self.assertIn('level="level3"', text)
        self.assertIn('if (($# > 0)) && [[ "$1" != --* ]]; then level=$1; shift; fi', text)
        self.assertIn('thinking_level=""', text)
        self.assertIn('[[ "$1" != --* ]]', text)
        self.assertIn('--runtime-context-level "$level"', text)
        self.assertIn('command+=(--thinking-level "$thinking_level")', text)

    def test_dynamic_launcher_omits_unset_optionals_and_forwards_explicit_limit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            launcher_dir = root / "asterion/scripts/bcplus_eval"
            launcher_dir.mkdir(parents=True)
            launcher = launcher_dir / "run_bcplus_eval_openai.sh"
            launcher.write_text(
                (ASTERION_LAUNCHER_ROOT / "bcplus_eval/run_bcplus_eval_openai.sh").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            (root / ".env").write_text("", encoding="utf-8")
            (root / "data").mkdir()
            (root / "data/bcplus_qa.jsonl").write_text("{}\n", encoding="utf-8")
            (root / "corpus/bc_plus_docs").mkdir(parents=True)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            fake = bin_dir / "uv"
            fake.write_text(
                '#!/usr/bin/env bash\nprintf "%s\\n" "$@" > "$CAPTURE_ARGS"\n',
                encoding="utf-8",
            )
            fake.chmod(0o755)
            env = os.environ | {
                "PATH": f"{bin_dir}:{os.environ['PATH']}",
                "ASTERION_DCI_RESOURCE_ROOT": str(root),
            }

            unset_log = root / "unset.log"
            result = subprocess.run(
                ["bash", str(launcher), "level2"],
                env=env | {"CAPTURE_ARGS": str(unset_log)},
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            unset_args = unset_log.read_text(encoding="utf-8").splitlines()
            self.assertEqual(
                unset_args[:5],
                [
                    "run",
                    "--project",
                    str(root / "asterion"),
                    "asterion-dci",
                    "benchmark",
                ],
            )
            self.assertNotIn("--thinking-level", unset_args)
            self.assertNotIn("--limit", unset_args)

            limit_log = root / "limit.log"
            result = subprocess.run(
                ["bash", str(launcher), "level5", "--limit", "9"],
                env=env | {"CAPTURE_ARGS": str(limit_log)},
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 2)
            self.assertFalse(limit_log.exists())

            explicit_log = root / "explicit.log"
            result = subprocess.run(
                [
                    "bash",
                    str(launcher),
                    "level4",
                    "high",
                    "--limit",
                    "7",
                    "--no-figures",
                ],
                env=env | {"CAPTURE_ARGS": str(explicit_log)},
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            explicit_args = explicit_log.read_text(encoding="utf-8").splitlines()
            self.assertEqual(
                explicit_args[-5:],
                ["--thinking-level", "high", "--limit", "7", "--no-figures"],
            )

            for invalid_args in (
                ("../../escape",),
                ("Level3",),
                ("legacy",),
                ("level3", "../../escape"),
            ):
                with self.subTest(invalid_args=invalid_args):
                    invalid_log = root / "invalid.log"
                    result = subprocess.run(
                        ["bash", str(launcher), *invalid_args],
                        env=env | {"CAPTURE_ARGS": str(invalid_log)},
                        capture_output=True,
                        text=True,
                    )
                    self.assertEqual(result.returncode, 2)
                    self.assertFalse(invalid_log.exists())
                    self.assertNotIn("../../escape", result.stderr)

    def test_all_launchers_are_valid_bash(self) -> None:
        for relative in sorted(TARGET_LAUNCHERS):
            with self.subTest(launcher=relative):
                result = subprocess.run(
                    ["bash", "-n", str(ASTERION_LAUNCHER_ROOT / relative)],
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_profile_only_cli_and_explicit_overrides_map_exact_request(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve() / "repo"
            invocation = Path(temporary_directory).resolve() / "invocation"
            invocation.mkdir()
            (root / "data/bcplus_qa.jsonl").parent.mkdir(parents=True)
            (root / "data/bcplus_qa.jsonl").write_text("{}\n", encoding="utf-8")
            (root / "corpus/bc_plus_docs").mkdir(parents=True)
            with patch("asterion.dci.cli.Path.cwd", return_value=invocation), patch(
                "asterion.dci.cli.run_benchmark"
            ) as run:
                run.return_value = type("Result", (), {"output_root": root / "out", "counts": {"total": 1}})()
                status = main(
                    [
                        "benchmark", "--profile", "bcplus.level3",
                        "--output-root", "custom-out", "--limit", "2",
                        "--max-concurrency", "3", "--pi-extra-arg=--custom value",
                    ],
                    repo_root=root,
                    stdout=io.StringIO(),
                    stderr=io.StringIO(),
                )
        self.assertEqual(status, 0)
        request = run.call_args.args[0]
        self.assertEqual(request.dataset, root / "data/bcplus_qa.jsonl")
        self.assertEqual(request.output_root, invocation / "custom-out")
        self.assertEqual(request.cwd, root / "corpus/bc_plus_docs")
        self.assertEqual(request.corpus, root / "corpus/bc_plus_docs")
        self.assertEqual(request.limit, 2)
        self.assertEqual(request.max_concurrency, 3)
        self.assertEqual(request.runtime_options.extra_args, ("--custom value",))
        self.assertEqual(request.runtime_options.provider, "openai")

    def test_primary_profile_preserves_exported_runtime_provider_and_model(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve() / "repo"
            invocation = Path(temporary_directory).resolve() / "invocation"
            invocation.mkdir()
            dataset = root / "data/dci-bench/data/hotpotqa/test.jsonl"
            dataset.parent.mkdir(parents=True)
            dataset.write_text("{}\n", encoding="utf-8")
            (root / "corpus/wiki_corpus").mkdir(parents=True)
            (root / ".env").write_text(
                "DCI_PROVIDER=dotenv-provider\nDCI_MODEL=dotenv-model\n",
                encoding="utf-8",
            )
            with patch.dict(
                os.environ,
                {
                    "DCI_PROVIDER": "exported-provider",
                    "DCI_MODEL": "exported-model",
                },
                clear=True,
            ), patch("asterion.dci.cli.Path.cwd", return_value=invocation), patch(
                "asterion.dci.cli.run_benchmark"
            ) as run:
                run.return_value = type(
                    "Result",
                    (),
                    {"output_root": root / "out", "counts": {"total": 1}},
                )()
                status = main(
                    ["benchmark", "--profile", "qa.hotpotqa", "--limit", "1"],
                    repo_root=root,
                    stdout=io.StringIO(),
                    stderr=io.StringIO(),
                )
        self.assertEqual(status, 0)
        options = run.call_args.args[0].runtime_options
        self.assertEqual(options.provider, "exported-provider")
        self.assertEqual(options.model, "exported-model")

    def test_unknown_profile_runner_only_paths_and_invalid_bounds_are_body_free(self) -> None:
        cases = (
            ["benchmark", "--profile", "unknown"],
            ["benchmark", "--profile", "bcplus.level3", "--package-dir", "secret-package"],
            ["benchmark", "--profile", "bcplus.level3", "--agent-dir", "secret-agent"],
            ["benchmark", "--profile", "bcplus.level3", "--limit", "0"],
            ["benchmark", "--profile", "bcplus.level3", "--max-concurrency", "0"],
        )
        for argv in cases:
            with self.subTest(argv=argv), patch("asterion.dci.cli.run_benchmark") as run:
                stdout = io.StringIO()
                stderr = io.StringIO()
                status = main(argv, repo_root=ROOT, stdout=stdout, stderr=stderr)
                self.assertEqual(status, 2)
                self.assertEqual(stdout.getvalue(), "")
                self.assertEqual(stderr.getvalue(), "DCI benchmark failed\n")
                self.assertNotIn("secret", stderr.getvalue())
                run.assert_not_called()

    def test_enable_ir_overrides_profile_but_conflicting_explicit_mode_fails(self) -> None:
        with patch("asterion.dci.cli.run_benchmark") as run:
            run.return_value = type(
                "Result", (), {"output_root": ROOT / "out", "counts": {"total": 1}}
            )()
            self.assertEqual(
                main(
                    ["benchmark", "--profile", "bcplus.level3", "--enable-ir"],
                    repo_root=ROOT,
                    stdout=io.StringIO(),
                    stderr=io.StringIO(),
                ),
                0,
            )
            self.assertEqual(run.call_args.args[0].mode, "ir")
        with patch("asterion.dci.cli.run_benchmark") as run:
            self.assertEqual(
                main(
                    [
                        "benchmark", "--profile", "bcplus.level3",
                        "--mode", "qa", "--enable-ir",
                    ],
                    repo_root=ROOT,
                    stdout=io.StringIO(),
                    stderr=io.StringIO(),
                ),
                2,
            )
            run.assert_not_called()

    def test_invalid_thinking_fails_before_batch_boundary_or_output(self) -> None:
        for option, value in (("--thinking-level", "invalid"),):
            with self.subTest(option=option), tempfile.TemporaryDirectory() as td:
                root = Path(td).resolve()
                dataset = root / "dataset.jsonl"
                output = root / "output"
                dataset.write_text(
                    '{"query_id":"q","query":"question","answer":"answer"}\n',
                    encoding="utf-8",
                )
                with patch("asterion.dci.cli.run_benchmark") as run:
                    stdout = io.StringIO()
                    stderr = io.StringIO()
                    status = main(
                        [
                            "benchmark", "--dataset", str(dataset),
                            "--output-root", str(output), option, value,
                        ],
                        repo_root=root,
                        stdout=stdout,
                        stderr=stderr,
                    )
                self.assertEqual(status, 2)
                self.assertEqual(stdout.getvalue(), "")
                self.assertEqual(stderr.getvalue(), "DCI benchmark failed\n")
                self.assertFalse(output.exists())
                run.assert_not_called()

    def test_empty_runtime_text_overrides_are_omitted_and_use_pi_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            dataset = root / "dataset.jsonl"
            dataset.write_text(
                '{"query_id":"q","query":"question","answer":"answer"}\n',
                encoding="utf-8",
            )
            with patch.dict(os.environ, {}, clear=True), patch(
                "asterion.dci.cli.run_benchmark"
            ) as run:
                run.return_value = type(
                    "Result",
                    (),
                    {"output_root": root / "output", "counts": {"total": 1}},
                )()
                status = main(
                    [
                        "benchmark",
                        "--dataset",
                        str(dataset),
                        "--output-root",
                        str(root / "output"),
                        "--provider",
                        "",
                        "--model",
                        "",
                        "--tools",
                        "",
                    ],
                    repo_root=root,
                    stdout=io.StringIO(),
                    stderr=io.StringIO(),
                )
            self.assertEqual(status, 0)
            options = run.call_args.args[0].runtime_options
            self.assertEqual(options.provider, "openai-codex")
            self.assertEqual(options.model, "gpt-5.6-luna")
            self.assertEqual(options.tools, "read,bash")

    def test_installed_wheel_loads_profiles_without_repository(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            dist = root / "dist"
            subprocess.run(
                ["uv", "build", "--package", "asterion", "--wheel", "--out-dir", str(dist)],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            wheel = next(dist.glob("*.whl"))
            with zipfile.ZipFile(wheel) as archive:
                resource = "asterion/dci/resources/batch-profiles.json"
                self.assertIn(resource, archive.namelist())
                document = json.loads(archive.read(resource))
                self.assertEqual(set(document["profiles"]), PROFILE_NAMES)
            env = os.environ.copy()
            env.pop("PYTHONPATH", None)
            result = subprocess.run(
                [
                    "uv", "run", "--isolated", "--no-project", "--with", str(wheel),
                    "python", "-I", "-c",
                    "from importlib.resources import files; import json; p=files('asterion.dci.resources').joinpath('batch-profiles.json'); assert len(json.loads(p.read_text())['profiles']) == 14",
                ],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)


for _relative, (_profile_slug, _profile_name) in {
    "bcplus_eval/run_L3.sh": ("bcplus_level3", "bcplus.level3"),
    "bcplus_eval/run_bcplus_eval_openai.sh": ("bcplus_dynamic_level_thinking", "bcplus.openai"),
    "bright/run_bio.sh": ("bright_biology", "bright.biology"),
    "bright/run_earth_science.sh": ("bright_earth_science", "bright.earth-science"),
    "bright/run_economics.sh": ("bright_economics", "bright.economics"),
    "bright/run_robotics.sh": ("bright_robotics", "bright.robotics"),
    "qa/run_2wikimultihopqa_dev_sample50.sh": ("qa_2wikimultihopqa", "qa.2wikimultihopqa"),
    "qa/run_bamboogle_test_sample50.sh": ("qa_bamboogle", "qa.bamboogle"),
    "qa/run_hotpotqa_dev_sample50.sh": ("qa_hotpotqa", "qa.hotpotqa"),
    "qa/run_musique_dev_sample50.sh": ("qa_musique", "qa.musique"),
    "qa/run_nq_test_sample50.sh": ("qa_nq", "qa.nq"),
    "qa/run_triviaqa_test_sample50.sh": ("qa_triviaqa", "qa.triviaqa"),
}.items():
    def _test(
        self: AsterionDciBatchLauncherTests,
        relative: str = _relative,
        profile_name: str = _profile_name,
    ) -> None:
        launcher = ASTERION_LAUNCHER_ROOT / relative
        profile = json.loads(PROFILE_RESOURCE.read_text(encoding="utf-8"))[
            "profiles"
        ][profile_name]
        text = launcher.read_text(encoding="utf-8")
        self.assertIn(f"--profile {profile_name}", text)
        self.assertIn(profile["dataset"], text)
        self.assertIn(profile["corpus"], text)
        self.assertIn("asterion-dci benchmark", text)
        if relative in PRIMARY_LAUNCHERS:
            self.assertNotIn('source "$REPO_ROOT/.env"', text)
        self.assertNotIn("run_bcplus_eval.py", text)
        syntax = subprocess.run(
            ["bash", "-n", str(launcher)], capture_output=True, text=True
        )
        self.assertEqual(syntax.returncode, 0, syntax.stderr)
        if profile_name == "bcplus.openai":
            self.test_dynamic_launcher_omits_unset_optionals_and_forwards_explicit_limit()

    source_id = _relative.replace("/", "_").replace(".", "_").lower()
    setattr(
        AsterionDciBatchLauncherTests,
        f"test_scripts_{source_id}_launcher_{_profile_slug}",
        _test,
    )


def _assert_cli_flag_mapping(
    case: AsterionDciBatchLauncherTests, flag: str
) -> None:
    with tempfile.TemporaryDirectory() as temporary_directory:
        root = Path(temporary_directory).resolve()
        dataset = root / "dataset.jsonl"
        alternate_dataset = root / "alternate.jsonl"
        corpus = root / "corpus"
        prompt = root / "prompt.md"
        dataset.write_text("{}\n", encoding="utf-8")
        alternate_dataset.write_text("{}\n", encoding="utf-8")
        corpus.mkdir()
        prompt.write_text("prompt", encoding="utf-8")
        arguments: dict[str, list[str]] = {
            "--agent-dir": [flag, str(root / "agent")],
            "--append-system-prompt-file": [flag, str(prompt)],
            "--corpus-dir": [flag, str(corpus)],
            "--corpus-hint": [flag, "sharded corpus"],
            "--dataset": [flag, str(alternate_dataset)],
            "--enable-ir": [flag],
            "--judge-api": [flag, "chat-completions"],
            "--judge-api-key-env": [flag, "TASK6_JUDGE_KEY"],
            "--judge-base-url": [flag, "https://judge.invalid/v1"],
            "--judge-cached-input-price-per-1m": [flag, "0.25"],
            "--judge-input-price-per-1m": [flag, "1.5"],
            "--judge-model": [flag, "judge-model"],
            "--judge-output-price-per-1m": [flag, "3.75"],
            "--judge-timeout-seconds": [flag, "17"],
            "--limit": [flag, "2"],
            "--max-concurrency": [flag, "3"],
            "--max-turns": [flag, "9"],
            "--model": [flag, "agent-model"],
            "--node-max-old-space-size-mb": [flag, "4096"],
            "--output-root": [flag, str(root / "alternate-output")],
            "--package-dir": [flag, str(root / "package")],
            "--pi-extra-arg": [f"{flag}=--custom value"],
            "--pi-thinking-level": [flag, "high"],
            "--provider": [flag, "agent-provider"],
            "--runtime-context-level": [flag, "level4"],
            "--system-prompt-file": [flag, str(prompt)],
            "--tools": [flag, "read"],
        }
        argv = [
            "benchmark",
            "--dataset",
            str(dataset),
            "--output-root",
            str(root / "output"),
            *arguments[flag],
        ]
        environment = {"TASK6_JUDGE_KEY": "synthetic-secret"}
        with patch.dict(os.environ, environment, clear=False), patch(
            "asterion.dci.cli.run_benchmark"
        ) as run:
            run.return_value = type(
                "Result", (), {"output_root": root / "output", "counts": {"total": 1}}
            )()
            stdout = io.StringIO()
            stderr = io.StringIO()
            status = main(argv, repo_root=root, stdout=stdout, stderr=stderr)
        if flag in {"--agent-dir", "--package-dir"}:
            case.assertEqual(status, 2)
            case.assertEqual(stderr.getvalue(), "DCI benchmark failed\n")
            run.assert_not_called()
            return
        case.assertEqual(status, 0, stderr.getvalue())
        request = run.call_args.args[0]
        expectations: dict[str, tuple[object, object]] = {
            "--append-system-prompt-file": (request.append_system_prompt_file, prompt),
            "--corpus-dir": (request.corpus, corpus),
            "--corpus-hint": (request.corpus_hint, "sharded corpus"),
            "--dataset": (request.dataset, alternate_dataset),
            "--enable-ir": (request.mode, "ir"),
            "--judge-api": (request.judge_config.api, "chat-completions"),
            "--judge-api-key-env": (request.judge_config.api_key_env, "TASK6_JUDGE_KEY"),
            "--judge-base-url": (request.judge_config.base_url, "https://judge.invalid/v1"),
            "--judge-cached-input-price-per-1m": (request.judge_config.cached_input_price_per_1m, 0.25),
            "--judge-input-price-per-1m": (request.judge_config.input_price_per_1m, 1.5),
            "--judge-model": (request.judge_config.model, "judge-model"),
            "--judge-output-price-per-1m": (request.judge_config.output_price_per_1m, 3.75),
            "--judge-timeout-seconds": (request.judge_config.timeout_seconds, 17),
            "--limit": (request.limit, 2),
            "--max-concurrency": (request.max_concurrency, 3),
            "--max-turns": (request.max_turns, 9),
            "--model": (request.runtime_options.model, "agent-model"),
            "--node-max-old-space-size-mb": (request.runtime_options.node_max_old_space_size_mb, 4096),
            "--output-root": (request.output_root, root / "alternate-output"),
            "--pi-extra-arg": (request.runtime_options.extra_args, ("--custom value",)),
            "--pi-thinking-level": (request.runtime_options.thinking_level, "high"),
            "--provider": (request.runtime_options.provider, "agent-provider"),
            "--runtime-context-level": (request.runtime_options.runtime_context_level, "level4"),
            "--system-prompt-file": (request.system_prompt_file, prompt),
            "--tools": (request.runtime_options.tools, "read"),
        }
        actual, expected = expectations[flag]
        case.assertEqual(actual, expected)


for _flag in (
    "--agent-dir",
    "--append-system-prompt-file",
    "--corpus-dir",
    "--corpus-hint",
    "--dataset",
    "--enable-ir",
    "--judge-api",
    "--judge-api-key-env",
    "--judge-base-url",
    "--judge-cached-input-price-per-1m",
    "--judge-input-price-per-1m",
    "--judge-model",
    "--judge-output-price-per-1m",
    "--judge-timeout-seconds",
    "--limit",
    "--max-concurrency",
    "--max-turns",
    "--model",
    "--node-max-old-space-size-mb",
    "--output-root",
    "--package-dir",
    "--pi-extra-arg",
    "--pi-thinking-level",
    "--provider",
    "--runtime-context-level",
    "--system-prompt-file",
    "--tools",
):
    def _flag_test(
        self: AsterionDciBatchLauncherTests, flag: str = _flag
    ) -> None:
        _assert_cli_flag_mapping(self, flag)

    flag_id = _flag.removeprefix("--").replace("-", "_")
    setattr(
        AsterionDciBatchLauncherTests,
        f"test_scripts_bcplus_eval_run_bcplus_eval_py_cli_flag_{flag_id}",
        _flag_test,
    )
