"""Build/run real ggml argmax guards from cached libraries; no model or engine.

Use --backend cuda --build-only when another process owns GPU execution.
Only this test executable and logs are written; cached native builds stay read-only.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

from build_r2t2_runtime import ROOT, build_environment


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument("--source", type=Path, default=ROOT / "tmp/asr-engine-20261017/r2t2-upstream")
    parser.add_argument("--libraries", type=Path)
    parser.add_argument("--cuda-root", type=Path, default=ROOT / "tmp/asr-engine-20261017/cuda-sdk/root")
    parser.add_argument("--build-dir", type=Path, default=ROOT / "tmp/shared-native-20261017/argmax-guards")
    parser.add_argument("--build-only", action="store_true")
    parser.add_argument("--no-build", action="store_true")
    args = parser.parse_args()
    source, build, cuda = (path.resolve() for path in (args.source, args.build_dir, args.cuda_root))
    libraries = (args.libraries or ROOT / ("tmp/shared-native-20261017/cpu-build" if args.backend == "cpu"
                                        else "tmp/asr-engine-20261017/r2t2-cuda-build")).resolve()
    ggml = source / "external/ggml"
    test = ROOT / "scripts/native_tests/native_argmax_test.cpp"
    libs = [libraries / f"ggml/src/{name}.lib" for name in ("ggml", "ggml-cpu", "ggml-base")]
    if args.backend == "cuda":
        libs += [libraries / "ggml/src/ggml-cuda/ggml-cuda.lib"]
        libs += [cuda / f"lib/x64/{name}.lib" for name in ("cublas", "cublasLt", "cuda", "cudart")]
    inputs = [test, Path(__file__).resolve(), *libs, *sorted((ggml / "include").glob("*.h")),
              ggml / "src/ggml-cpu/ops.cpp", ggml / "src/ggml-cpu/vec.h", ggml / "src/ggml-cuda/argmax.cu"]
    for path in inputs:
        if not path.is_file():
            parser.error(f"required native test input missing: {path}")
    fingerprints = {str(path): sha256(path) for path in inputs}
    build.mkdir(parents=True, exist_ok=True)
    exe = build / f"native_argmax_{args.backend}.exe"
    manifest = build / f"{args.backend}-compiled.json"
    env, _ = build_environment()
    env = {key.upper(): value for key, value in env.items()}
    if args.backend == "cuda":
        env["PATH"] = str(cuda / "bin") + os.pathsep + env["PATH"]
    if not args.no_build:
        compiler = shutil.which("cl.exe", path=env["PATH"])
        if not compiler:
            parser.error("Visual Studio cl.exe unavailable after vcvars")
        command = [compiler, "/nologo", "/std:c++17", "/EHsc", "/O2", "/MD", "/DNOMINMAX",
                   f"/I{ggml / 'include'}", f"/Fo{build / (args.backend + '.obj')}", f"/Fe{exe}"]
        if args.backend == "cuda":
            command += ["/DTEST_CUDA"]
        command += [str(test), "/link", "/OPT:REF", *map(str, libs), "kernel32.lib", "advapi32.lib"]
        result = subprocess.run(command, cwd=build, env=env, capture_output=True, text=True, errors="replace")
        (build / f"{args.backend}-build.log").write_text(
            subprocess.list2cmdline(command) + "\n" + result.stdout + result.stderr, encoding="utf-8")
        if result.returncode:
            print(result.stdout + result.stderr, end="")
            return result.returncode
        manifest.write_text(json.dumps({"inputs": fingerprints, "executable": sha256(exe),
                                        "command": command}, indent=2) + "\n", encoding="utf-8")
    else:
        previous = json.loads(manifest.read_text(encoding="utf-8"))
        if previous["inputs"] != fingerprints or previous["executable"] != sha256(exe):
            parser.error("compiled native test inputs changed; rerun without --no-build")
    if args.build_only:
        print(json.dumps({"executable": str(exe), "sha256": sha256(exe), "executed": False}))
        return 0
    result = subprocess.run([str(exe), "--backend", args.backend, "--output", str(build / f"{args.backend}.json")],
                            cwd=build, env=env, capture_output=True, text=True, errors="replace")
    (build / f"{args.backend}-run.log").write_text(result.stdout + result.stderr, encoding="utf-8")
    print(result.stdout, end="")
    if result.returncode:
        print(result.stderr, end="")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
