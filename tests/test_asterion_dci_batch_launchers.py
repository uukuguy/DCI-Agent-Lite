from __future__ import annotations

import io
import json
import os
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from asterion.dci.cli import main


ROOT = Path(__file__).resolve().parents[1]
SOURCE_LAUNCHER_ROOT = ROOT / "scripts"
ASTERION_LAUNCHER_ROOT = SOURCE_LAUNCHER_ROOT / "asterion"
PROFILE_RESOURCE = (
    ROOT
    / "packages/python/asterion-core/src/asterion/dci/resources/batch-profiles.json"
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
}


class AsterionDciBatchLauncherTests(unittest.TestCase):
    def test_docs_superpowers_plans_2026_07_14_af_240_batch_evaluation_export_parity_md_target_feature_installed_batch_profiles(
        self,
    ) -> None:
        document = json.loads(PROFILE_RESOURCE.read_text(encoding="utf-8"))
        self.assertEqual(document["schema"], "asterion.dci.batch-profiles/v1")
        self.assertEqual(set(document["profiles"]), PROFILE_NAMES)
        for name, profile in document["profiles"].items():
            with self.subTest(profile=name):
                self.assertEqual(profile["provider"], "openai")
                self.assertEqual(profile["model"], "gpt-5.4-nano")
                self.assertEqual(profile["tools"], "read,bash")
                self.assertEqual(profile["node_max_old_space_size_mb"], 8192)
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
                self.assertIn('source "$REPO_ROOT/.env"', text)
                self.assertIn("asterion-dci benchmark", text)
                self.assertIn('"$@"', text)
                self.assertIn("--profile", text)
                self.assertIn("--limit", text)
                self.assertIn("[ -f", text)
                self.assertIn("[ -d", text)
                self.assertNotIn("src/dci", text)
                self.assertNotIn("scripts/bcplus_eval/run_bcplus_eval.py", text)
                self.assertNotIn("uv run python", text)

    def test_dynamic_launcher_preserves_positional_context_thinking_and_limit(self) -> None:
        text = (
            ASTERION_LAUNCHER_ROOT / "bcplus_eval/run_bcplus_eval_openai.sh"
        ).read_text(encoding="utf-8")
        self.assertIn('level=${1:-"level3"}', text)
        self.assertIn('thinking_level=${2:-""}', text)
        self.assertIn('--runtime-context-level "$level"', text)
        self.assertIn('command+=(--thinking-level "$thinking_level")', text)

    def test_dynamic_launcher_omits_unset_optionals_and_forwards_explicit_limit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            launcher_dir = root / "scripts/asterion/bcplus_eval"
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
            fake = bin_dir / "asterion-dci"
            fake.write_text(
                '#!/usr/bin/env bash\nprintf "%s\\n" "$@" > "$CAPTURE_ARGS"\n',
                encoding="utf-8",
            )
            fake.chmod(0o755)
            env = os.environ | {"PATH": f"{bin_dir}:{os.environ['PATH']}"}

            unset_log = root / "unset.log"
            result = subprocess.run(
                ["bash", str(launcher), "level2"],
                env=env | {"CAPTURE_ARGS": str(unset_log)},
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            unset_args = unset_log.read_text(encoding="utf-8").splitlines()
            self.assertNotIn("--thinking-level", unset_args)
            self.assertNotIn("--limit", unset_args)

            limit_log = root / "limit.log"
            result = subprocess.run(
                ["bash", str(launcher), "level5", "--limit", "9"],
                env=env | {"CAPTURE_ARGS": str(limit_log)},
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            limit_args = limit_log.read_text(encoding="utf-8").splitlines()
            self.assertNotIn("--thinking-level", limit_args)
            self.assertEqual(limit_args[-2:], ["--limit", "9"])

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
                    "from importlib.resources import files; import json; p=files('asterion.dci.resources').joinpath('batch-profiles.json'); assert len(json.loads(p.read_text())['profiles']) == 12",
                ],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)


for _relative, _profile in {
    "bcplus_eval/run_L3.sh": "bcplus_level3",
    "bcplus_eval/run_bcplus_eval_openai.sh": "bcplus_dynamic_level_thinking",
    "bright/run_bio.sh": "bright_biology",
    "bright/run_earth_science.sh": "bright_earth_science",
    "bright/run_economics.sh": "bright_economics",
    "bright/run_robotics.sh": "bright_robotics",
    "qa/run_2wikimultihopqa_dev_sample50.sh": "qa_2wikimultihopqa",
    "qa/run_bamboogle_test_sample50.sh": "qa_bamboogle",
    "qa/run_hotpotqa_dev_sample50.sh": "qa_hotpotqa",
    "qa/run_musique_dev_sample50.sh": "qa_musique",
    "qa/run_nq_test_sample50.sh": "qa_nq",
    "qa/run_triviaqa_test_sample50.sh": "qa_triviaqa",
}.items():
    def _test(self: AsterionDciBatchLauncherTests, relative: str = _relative) -> None:
        self.assertTrue((ASTERION_LAUNCHER_ROOT / relative).is_file())

    source_id = _relative.replace("/", "_").replace(".", "_").lower()
    setattr(
        AsterionDciBatchLauncherTests,
        f"test_scripts_{source_id}_launcher_{_profile}",
        _test,
    )


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
        stdout = io.StringIO()
        self.assertEqual(
            main(
                ["benchmark", "--help"],
                repo_root=ROOT,
                stdout=stdout,
                stderr=io.StringIO(),
            ),
            0,
        )
        self.assertIn(flag, stdout.getvalue())

    flag_id = _flag.removeprefix("--").replace("-", "_")
    setattr(
        AsterionDciBatchLauncherTests,
        f"test_scripts_bcplus_eval_run_bcplus_eval_py_cli_flag_{flag_id}",
        _flag_test,
    )
