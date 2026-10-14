"""Check three replay sensitivities in isolated local snapshots; never edit live sources."""

import argparse
import hashlib
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASES = {
    "assistant-saved-read": {
        "source": "src/pages/SettingsPage.tsx",
        "changes": [("&& provider === assistantProviderRef.current && !draft && !assistantKeyDraftsRef.current[provider];",
                     "&& provider === assistantProviderRef.current && !assistantKeyDraftsRef.current[provider];")],
        "test": "src/pages/__tests__/SettingsPageProviderDiscovery.test.tsx",
        "pattern": "replays a read captured while dirty after the matching save clears its draft",
        "failure": "to have value",
    },
    "assistant-read": {
        "source": "src/pages/SettingsPage.tsx",
        "changes": [("if (current()) setAssistantApiKeyState(\"\");", "setAssistantApiKeyState(\"\");")],
        "test": "src/pages/__tests__/SettingsPageProviderDiscovery.test.tsx",
        "pattern": "replays a stale provider read outcome",
        "failure": "to have value",
    },
    "microphone-retired-test": {
        "source": "src/hooks/useMicrophoneSettings.ts",
        "changes": [
            ("    if (monitorOwner !== ownerRef.current) return Promise.resolve();\n", ""),
            ("if (monitorOwner !== ownerRef.current || generation !== monitorGenerationRef.current) return;",
             "if (generation !== monitorGenerationRef.current) return;"),
        ],
        "test": "src/hooks/__tests__/useMicrophoneSettings.test.tsx",
        "pattern": "replays microphone-retired-test through two hook instances",
        "failure": "replacement",
    },
    "microphone-effect-owner": {
        "source": "src/hooks/useMicrophoneSettings.ts",
        "changes": [
            ("  const ownerRef = useRef(Symbol(\"microphone-settings\"));",
             "  const ownerRef = useRef(Symbol(\"microphone-settings\"));\n  const localQueue = useRef(Promise.resolve());"),
            ("const operation = monitorQueue.then(", "const operation = localQueue.current.then("),
            ("    monitorQueue = operation;", "    localQueue.current = operation;"),
        ],
        "test": "src/hooks/__tests__/useMicrophoneSettings.test.tsx",
        "pattern": "replays microphone-effect-owner through two hook instances",
        "failure": "replacement",
    },
}


def run(snapshot: Path, case: dict, label: str) -> tuple[int, dict]:
    report = snapshot / f"{label}.json"
    result = subprocess.run([
        "node", str(ROOT / "node_modules/vitest/vitest.mjs"), "run", case["test"],
        "-t", case["pattern"], "--reporter=json", f"--outputFile={report}",
    ], cwd=snapshot, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    (snapshot / f"{label}.txt").write_text(result.stdout + result.stderr, encoding="utf-8")
    if not report.exists():
        raise ValueError(f"test collection failed without JSON report: {snapshot / f'{label}.txt'}")
    return result.returncode, json.loads(report.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True, help="Explicit local scratch parent")
    parser.add_argument("--case", choices=CASES)
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    records = []
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    for name in [args.case] if args.case else CASES:
        case = CASES[name]
        snapshot = workspace / f"mutation-{name}-{stamp}"
        if snapshot.resolve().parent != workspace:
            raise ValueError("snapshot escaped explicit scratch parent")
        snapshot.mkdir()
        for folder in ["src", "formal"]:
            shutil.copytree(ROOT / folder, snapshot / folder)
        for filename in ["package.json", "tsconfig.json", "vitest.config.ts"]:
            shutil.copyfile(ROOT / filename, snapshot / filename)
        config = snapshot / "vitest.config.ts"
        config.write_text(config.read_text(encoding="utf-8").replace(
            "  plugins:", '  cacheDir: path.resolve(import.meta.dirname, ".vite-cache"),\n  plugins:'), encoding="utf-8")
        dependencies = snapshot / "node_modules"
        if __import__("os").name == "nt":
            subprocess.run(["cmd", "/c", "mklink", "/J", str(dependencies), str(ROOT / "node_modules")],
                           check=True, capture_output=True, text=True)
        else:
            dependencies.symlink_to(ROOT / "node_modules", target_is_directory=True)
        baseline_code, baseline = run(snapshot, case, "baseline")
        if baseline_code or baseline["numPassedTests"] != 1 or baseline["numFailedTests"]:
            raise ValueError(f"baseline must collect and pass exactly one replay: {snapshot}")
        path = snapshot / case["source"]
        source = path.read_text(encoding="utf-8")
        original_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        for old, new in case["changes"]:
            if source.count(old) != 1:
                raise ValueError(f"mutation anchor drift in {case['source']}: {old}")
            source = source.replace(old, new)
        path.write_text(source, encoding="utf-8")
        wrong_code, wrong = run(snapshot, case, "wrong")
        messages = [message for suite in wrong["testResults"] for test in suite["assertionResults"]
                    if test["status"] == "failed" for message in test["failureMessages"]]
        if wrong_code != 1 or wrong["numFailedTests"] != 1 or not any(case["failure"] in message for message in messages):
            raise ValueError(f"mutation must fail semantically in the selected replay: {snapshot}")
        record = {"case": name, "snapshot": str(snapshot), "source": case["source"],
                  "baseline_sha256": original_hash, "wrong_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                  "baseline_exit": baseline_code, "wrong_exit": wrong_code,
                  "test": case["pattern"], "failed_assertions": wrong["numFailedTests"]}
        records.append(record)
        print(f"PASS sensitivity {name}: baseline 1 GREEN, wrong source 1 semantic RED")
    (workspace / "async-replay-mutations.json").write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
