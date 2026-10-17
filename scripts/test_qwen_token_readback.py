"""Real tiny CPU greedy traces and observed full-vocabulary readback regression.

Compare candidate shared decoder TUs with pinned pre-token-readback copies.
The C++ test uses only existing generate APIs, checks finite ties/near ties,
and observes actual backend tensor reads and ARGMAX graph operations.
Cached native libraries are read-only; no CMake invocation or GPU use.
"""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

from build_r2t2_runtime import ROOT, build_environment
from test_qwen_shared_decoder import sha256
from test_r2t2_prefill import LIBRARIES


RUNTIMES = {
    "src/framework/runtime/greedy_qwen_decoder.cpp": "daa7e5aa946eaa17e166388871372b2d50de09e4fc8286fa19bbb17860feb371",
    "src/framework/modules/transformers/qwen_causal_decode_runtime.cpp": "c6e12ab2f6f3dd12c07f64051358773a5763611277610ad912082292c99e4357",
    "src/models/qwen3_asr/thinker.cpp": "335d31312f785e3f8b3acb52f9c4337651fbf72725200bfa073ec360edd0d992",
}
TEST = ROOT / "scripts/native_tests/qwen_token_readback_test.cpp"
INTERPOSE = ROOT / "scripts/native_tests/qwen_token_readback_interpose.h"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--libraries", required=True, type=Path)
    parser.add_argument("--baseline-dir", type=Path, default=ROOT / "tmp/shared-native-20261017/token-tests/frozen")
    parser.add_argument("--build-dir", type=Path, default=ROOT / "tmp/shared-native-20261017/token-tests")
    parser.add_argument("--mode", choices=("all", "equivalence", "work"), default="all")
    parser.add_argument("--no-build", action="store_true")
    args = parser.parse_args()
    source, libraries, baseline, build = (path.resolve() for path in
                                        (args.source, args.libraries, args.baseline_dir, args.build_dir))
    if build in (source, libraries) or (build / "CMakeCache.txt").exists():
        parser.error("test build directory must be separate from native/CMake builds")
    build.mkdir(parents=True, exist_ok=True)
    paths = [TEST, INTERPOSE, Path(__file__).resolve(), ROOT / "scripts/test_qwen_shared_decoder.py",
             ROOT / "scripts/test_r2t2_prefill.py", ROOT / "scripts/build_r2t2_runtime.py",
             *[source / name for name in RUNTIMES], *[baseline / Path(name).name for name in RUNTIMES],
             *[libraries / name for name in LIBRARIES], *sorted((source / "include").rglob("*.h")),
             *sorted((source / "external/ggml/include").glob("*.h"))]
    for path in paths:
        if not path.is_file():
            parser.error(f"required native test input missing: {path}")
    for name, digest in RUNTIMES.items():
        if sha256(baseline / Path(name).name) != digest:
            parser.error(f"frozen full-logits baseline raw SHA256 mismatch: {name}")
    fingerprint = {str(path): sha256(path) for path in paths}
    env, _ = build_environment()
    env = {key.upper(): value for key, value in env.items()}
    compiler, linker = (shutil.which(name, path=env["PATH"]) for name in ("cl.exe", "link.exe"))
    if not compiler or not linker:
        parser.error("MSVC cl.exe/link.exe unavailable")
    commands = []

    def execute(command, log):
        command = list(map(str, command))
        commands.append(command)
        result = subprocess.run(command, cwd=build, env=env, capture_output=True, text=True, errors="replace")
        with (build / log).open("a", encoding="utf-8") as output:
            output.write(subprocess.list2cmdline(command) + "\n" + result.stdout + result.stderr)
        return result

    executables = {name: build / f"qwen_token_{name}.exe" for name in ("baseline", "candidate")}
    manifest = build / "compiled-source.json"
    if not args.no_build:
        (build / "build.log").write_text("", encoding="utf-8")
        common = [compiler, "/nologo", "/c", "/std:c++17", "/EHsc", "/O2", "/Gy", "/MD", "/DNDEBUG",
                  "/DNOMINMAX", "/D_CRT_SECURE_NO_WARNINGS", f"/I{source / 'include'}",
                  f"/I{source / 'external/ggml/include'}"]
        build_commands = [[*common, f"/Fo{build / 'test.obj'}", TEST]]
        for name in executables:
            objects = []
            for index, runtime in enumerate(RUNTIMES):
                path = baseline / Path(runtime).name if name == "baseline" else source / runtime
                obj = build / f"{name}-{index}.obj"
                objects.append(obj)
                build_commands.append([*common, f"/FI{INTERPOSE}", f"/Fo{obj}", path])
            build_commands.append([linker, "/nologo", "/OPT:REF", f"/OUT:{executables[name]}",
                                   build / "test.obj", *objects, *[libraries / item for item in LIBRARIES],
                                   "kernel32.lib", "advapi32.lib"])
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
            parser.error("compiled inputs changed; rerun without --no-build")
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
            before, after = ((build / f"{name}.bin").read_bytes() for name in executables)
            evidence["exact_trace_equal"] = before == after
            evidence["trace_sha256"] = {name: sha256(build / f"{name}.bin") for name in executables}
            print(f"{'PASS' if before == after else 'FAIL'} exact frozen token trace bytes={len(after)}")
            returncode = 0 if before == after else 1
    if not returncode and args.mode != "equivalence":
        (build / "work.log").write_text("", encoding="utf-8")
        result = execute([executables["candidate"], "work", build / "work.bin"], "work.log")
        evidence["results"]["work"] = result.returncode
        lines = result.stdout.splitlines()
        reds = [line for line in lines if line.startswith("WORK_RED ")]
        print("\n".join(reds[:3] + lines[-1:]))
        print(result.stderr, end="")
        returncode = result.returncode
    evidence["returncode"] = returncode
    (build / f"{args.mode}.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    return returncode


if __name__ == "__main__":
    raise SystemExit(main())
