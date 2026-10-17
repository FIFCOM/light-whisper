"""Compile tiny real CPU Qwen thinker tests; compare frozen output and observe KV work.

Cached static libraries are read-only. Only test, thinker, generic greedy and
causal-decode translation units are compiled in a separate test directory.
Every source that can read generation KV is interposed; a nonreuse generic
decoder control must show real host KV exports before zero-export can pass.
Synthetic weights establish numerical regression evidence, not ASR quality.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

from build_r2t2_runtime import ROOT, build_environment
from test_r2t2_prefill import LIBRARIES


THINKER = "src/models/qwen3_asr/thinker.cpp"
SHARED = ("src/framework/runtime/greedy_qwen_decoder.cpp",
          "src/framework/modules/transformers/qwen_causal_decode_runtime.cpp")
BASELINE_SHA256 = "429af9913ebdcba7a435732e53284614564e068a928a8b5a48b06bc0580fe57c"
TEST = ROOT / "scripts/native_tests/qwen_shared_decoder_test.cpp"
INTERPOSE = ROOT / "scripts/native_tests/qwen_shared_decoder_interpose.h"


def sha256(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--libraries", required=True, type=Path)
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--build-dir", type=Path, default=ROOT / "tmp/shared-native-20261017/decoder-tests")
    parser.add_argument("--mode", choices=("all", "equivalence", "work"), default="all")
    parser.add_argument("--no-build", action="store_true")
    args = parser.parse_args()
    source, libraries, baseline, build = (path.resolve() for path in
                                        (args.source, args.libraries, args.baseline, args.build_dir))
    if build == source or build == libraries or (build / "CMakeCache.txt").exists():
        parser.error("test build directory must be separate from native/CMake builds")
    build.mkdir(parents=True, exist_ok=True)
    paths = [source / THINKER, baseline, TEST, INTERPOSE, Path(__file__).resolve(),
             ROOT / "scripts/test_r2t2_prefill.py", ROOT / "scripts/build_r2t2_runtime.py",
             *[source / name for name in SHARED], *[libraries / name for name in LIBRARIES],
             *sorted((source / "include").rglob("*.h")),
             *sorted((source / "external/ggml/include").glob("*.h"))]
    for path in paths:
        if not path.is_file():
            parser.error(f"native test input missing: {path}")
    if sha256(baseline) != BASELINE_SHA256:
        parser.error("frozen Qwen thinker baseline raw SHA256 mismatch")
    fingerprint = {str(path): sha256(path) for path in paths}
    env, _ = build_environment()
    env = {key.upper(): value for key, value in env.items()}
    compiler, linker = (shutil.which(name, path=env["PATH"]) for name in ("cl.exe", "link.exe"))
    if not compiler or not linker:
        parser.error("MSVC cl.exe/link.exe unavailable")
    commands = []

    def execute(command, log_name):
        command = list(map(str, command))
        commands.append(command)
        result = subprocess.run(command, cwd=build, env=env, capture_output=True, text=True, errors="replace")
        with (build / log_name).open("a", encoding="utf-8") as log:
            log.write(subprocess.list2cmdline(command) + "\n" + result.stdout + result.stderr)
        return result

    executables = {name: build / f"qwen_shared_{name}.exe" for name in ("baseline", "candidate")}
    manifest = build / "compiled-source.json"
    if not args.no_build:
        (build / "build.log").write_text("", encoding="utf-8")
        common = [compiler, "/nologo", "/c", "/std:c++17", "/EHsc", "/O2", "/Gy", "/MD", "/DNDEBUG",
                  "/DNOMINMAX", "/D_CRT_SECURE_NO_WARNINGS", f"/I{source / 'include'}",
                  f"/I{source / 'external/ggml/include'}"]
        build_commands = [[*common, f"/Fo{build / 'test.obj'}", TEST]]
        shared_objects = []
        for index, name in enumerate(SHARED):
            obj = build / f"shared_{index}.obj"
            shared_objects.append(obj)
            build_commands.append([*common, f"/FI{INTERPOSE}", f"/Fo{obj}", source / name])
        for name, thinker in (("baseline", baseline), ("candidate", source / THINKER)):
            obj = build / f"{name}.obj"
            build_commands.extend([
                [*common, f"/FI{INTERPOSE}", f"/Fo{obj}", thinker],
                [linker, "/nologo", "/OPT:REF", f"/OUT:{executables[name]}", build / "test.obj", obj,
                 *shared_objects, *[libraries / path for path in LIBRARIES], "kernel32.lib", "advapi32.lib"],
            ])
        for command in build_commands:
            result = execute(command, "build.log")
            if result.returncode:
                print(result.stdout + result.stderr, end="")
                raise RuntimeError(f"INFRASTRUCTURE: compile/link failed; see {build / 'build.log'}")
        manifest.write_text(json.dumps({"inputs": fingerprint, "executables": {
            name: sha256(path) for name, path in executables.items()}}, indent=2) + "\n", encoding="utf-8")
    else:
        previous = json.loads(manifest.read_text(encoding="utf-8"))
        if previous["inputs"] != fingerprint or previous["executables"] != {
                name: sha256(path) for name, path in executables.items()}:
            parser.error("compiled test inputs changed; rerun without --no-build")
    evidence = {"inputs": fingerprint, "mode": args.mode, "commands": commands,
                "synthetic_weights_only": True, "results": {}}
    returncode = 0
    if args.mode != "work":
        for name, executable in executables.items():
            log = f"{name}-equivalence.log"
            (build / log).write_text("", encoding="utf-8")
            result = execute([executable, "equivalence", build / f"{name}.bin"], log)
            evidence["results"][name] = result.returncode
            print(name + ": " + (result.stdout.splitlines()[-1] if result.stdout else "no output"))
            if result.returncode:
                print(result.stderr, end="")
                returncode = result.returncode
                break
        if not returncode:
            expected, actual = ((build / f"{name}.bin").read_bytes() for name in executables)
            evidence["exact_trace_equal"] = expected == actual
            evidence["trace_sha256"] = {name: sha256(build / f"{name}.bin") for name in executables}
            print(f"{'PASS' if expected == actual else 'FAIL'} exact frozen token/classification trace bytes={len(actual)}")
            returncode = 0 if expected == actual else 1
    if not returncode and args.mode != "equivalence":
        (build / "work.log").write_text("", encoding="utf-8")
        result = execute([executables["candidate"], "work", build / "work.bin"], "work.log")
        evidence["results"]["work"] = result.returncode
        lines = result.stdout.splitlines()
        selected = [line for line in lines if line.startswith(("CONTROL_", "WORK_RED "))]
        print("\n".join(selected[:5] + lines[-1:]))
        print(result.stderr, end="")
        returncode = result.returncode
    evidence["returncode"] = returncode
    (build / f"{args.mode}.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    return returncode


if __name__ == "__main__":
    raise SystemExit(main())
