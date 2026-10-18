# Shared Qwen3-ASR and R2T2 native backend

Qwen 0.6B and R2T2 share a resident audio.cpp C ABI runtime and the same capture, session and caption protocol. Model selection remains independent. Qwen and R2T2 support NVIDIA CUDA and CPU. No WSL, vLLM or PyTorch is required. The retired transcribe.cpp loader and provider packages are excluded from the engine. Saved Qwen 1.7B selections migrate to R2T2; existing model caches are preserved.

Qwen 0.6B now uses `audio-cpp/audio.cpp-gguf`, revision `f861648c0c1f4da9f18e9a0ce5e217b0679bb2f5`, file `Qwen3-ASR-0.6B-GGUF/qwen3-asr-0.6b-q8_0.gguf` (1,151,272,416 bytes, SHA-256 `6c44ec2fb4cee513892d7863c1fcc3ea6b699ffa4d899b0ef4ab19956d9544f7`). This download is separate from the former transcribe.cpp model; the original cache is preserved.

Qwen capture forwards 40-ms blocks. Its first nonempty preview is attempted at 120-ms audio intervals, then previews use 200-ms intervals and at most the latest 12 seconds. Hypotheses remain revisable. Finish recognizes the entire captured recording, including residual samples; it never substitutes the latest window for the full recording. The shared protocol rejects stale session IDs and discontinuous sample offsets.

When a successful preview already processed the complete unchanged capture, finish reuses that result. Reuse requires the exact same captured sample count and a recording no longer than the preview window. Even one additional sample, or any earlier audio outside that window, requires the complete final decode. Reset and failed decoding discard the reusable result.

Captures longer than 115 seconds use native automatic 30-second chunking for final recognition. This stays within the pinned encoder's 1,500-position limit and applies the generation limit to each chunk, keeping the final partial chunk. Shorter captures keep the unsplit path.

## Fixed model

- Repository: `davidxifeng/Confucius4-R2T2-gguf`
- Revision: `a8e6b385d7df7eae9519363e07034a209004797a`
- File: `r2t2-q8_0.gguf` (Q8_0, 2,477,512,064 bytes)
- SHA-256: `19f5ccd624484bcb5d44301437de41560b0ecc40c430e8850dfeefefbe82ccf5`

The loader verifies the pinned file before loading it. Weights download
separately; old model caches are not deleted by migration. Model terms are
in [R2T2-MODEL-LICENSE.txt](../src-tauri/resources/R2T2-MODEL-LICENSE.txt).

## Streaming

- Capture resamples once and polls every 40 ms, sending complete 160-ms blocks instead of partial requests or merged 320-ms updates. CUDA decodes 160-ms chunks; CPU uses 320 ms. Finish flushes all real samples and the resampler tail; cancellation resets the session.
- CUDA initialization decodes one silent chunk and resets the session before reporting ready. With native ABI 0.4+, the first aligned VAD prefix (at most one second) is decoded once instead of replaying each chunk. Later audio keeps normal chunk boundaries; ABI 0.3 and CPU retain chunk-by-chunk feeds.
- A 16-second rolling window advances by 8 seconds. Committed text is append-only; the visible preview can change. There is no fixed 30-second recording reset.
- The encoder recomputes the current window. This is not an incremental encoder/KV-cache implementation.
- On CUDA, startup previews can add 320 ms of zero-valued right context after 640 ms of real audio. There are at most three attempts, ending when normal decoding produces text. Padded results never enter commits, language state, continuation prompts or final output.
- Language, topic hints and hotwords are fixed for each recording. They are separate from AI polish.
- Profiles retain at most 300 hotwords; ASR selects at most 100 by weight and usage. The Python request boundary also keeps at most 100 unique hotwords, normalizes whitespace and ignores case when deduplicating. Empty entries and entries longer than 80 Unicode characters are skipped without shortening words. Streaming and offline requests use the same normalization.
- VAD retains its trailing audio window but skips inference while an active segment is too short to end. Native captions render directly, without running an unused character-reveal animation.
- Stop flushes 320 ms of acoustic silence inside the native decoder before collecting the final result. This is inference input, with no timer or extra microphone recording. Paired CUDA checks recovered the missing Chinese tails “带” and “喝” and English sentence tails; 80/160 ms remained insufficient on the Chinese clips. Captured sample counts and the live-feed schedule are unchanged; ending a segment adds bounded decoder work. The opt-in Rust test `real_native_stop_before_caption_refresh_keeps_sentence_tail` covers immediate Stop through the actual server and checks sample accounting.
- With native ABI 0.5+, CUDA rolling sessions append that complete context to the pending audio and decode it once in the final flush. The adapter enables `confucius4_r2t2.coalesced_finish` before session creation; the native option defaults to false. ABI 0.3/0.4, CPU, Qwen and nonrolling sessions retain their previous finish path. Empty recordings add no context.

## Build and packaging

Follow [Development](development.md) to build the two native packages and the installer. Native builds require Visual Studio 2022 C++ tools, CMake and Ninja; CUDA builds were validated with CUDA 12.9 and MSVC 14.44.

The build pins audio.cpp revision `6c70f32d0d90a29a9863e556bd9712ce622f868b` and requires an exact match to `scripts/patches/audio-cpp-r2t2-windows-streaming.patch`. Build `light-whisper-asr-9` writes libraries, licenses and SHA-256 manifests to ignored `src-tauri/resources/r2t2-native/{cpu,cuda}/`. CUDA targets architectures 75, 80, 86, 89 and 90.

The engine builder validates both manifests and shares byte-identical CUDA/CRT DLLs in `_internal` when a root copy exists. Otherwise, dependencies stay beside the native library. Shared files are listed in each copied manifest. Standalone native packages retain their dependencies. Only CPU/CUDA native directories enter the engine; copied legacy Vulkan DLLs are removed before compression, and reused archives containing Vulkan libraries or retired transcribe.cpp packages are rejected. Model weights are not bundled.

The shared greedy decoder retains KV data on the device and reuses bounded prefill/decode graphs. Qwen uses 1,024-token prefill blocks and attention views over existing KV storage; R2T2 retains its validated 64-token blocks. CPU/CUDA greedy generation reads one 4-byte token ID per step. The opt-in argmax retains generation's first-maximum tie rule; classification retains its existing backend tie behavior.

## Validation and limits

Q8 was tested on an RTX 4070 SUPER 12 GB. Checks covered five public clips, five short truncations, silence, a 126.6-second recording, exact final audio accounting, cancellation and restart. The packaged R2T2 process passed 31 requests; packaged Qwen CUDA and R2T2 CPU also passed smoke tests. This is limited regression coverage, not a broad accuracy benchmark or AMD validation.

Paired paced server playback for build `light-whisper-r2t2-5` measured:

| First caption after model readiness | Runtime 4 | Runtime 5 |
|:--|--:|--:|
| Chinese, first recording | 1.17 s | 0.92 s |
| English, first recording | 1.02 s | 0.90 s |
| Chinese, later recordings | 1.01 s | 0.91 s |
| English, later recordings | 0.87 s | 0.87 s |

Each version ran three repetitions in separate Chinese-first and English-first processes. Later-recording values are medians. Warmup itself took about 0.19 seconds before readiness; total initialization varied from 4.8 to 5.5 seconds across these runs. First-prefix coalescing removes repeated decoding of queued audio. Committed traces and final transcripts matched on the regression clips. These are two latency fixtures, not microphone-to-screen guarantees or a broad accuracy benchmark. The former Qwen 1.7B repeated-recognition strategy still produced its first caption sooner on these clips.

Capture scheduling was also simulated with real inference and 0, 20 and 150 ms of already-captured audio. At 150 ms of offset, two-run median first-caption time improved from 1.06 to 0.94 seconds in Chinese and 1.02 to 0.89 seconds in English; aligned inputs were effectively unchanged. These measurements isolate polling alignment, not the full desktop path. On the same full clips, redundant VAD calls fell from 43 to 5 and from 88 to 23 without changing committed traces or final text.

### Incremental frontend

Build `light-whisper-r2t2-6` reuses raw STFT magnitudes whose input samples remain unchanged. Appended audio recomputes the right-reflected boundary and new frames. The full mel transform and global log-mel floor still run on every window, so a louder append can change earlier normalized features. Rewritten, shortened, shifted or peak-renormalized audio invalidates reuse. Each frontend retains only its latest normalized PCM and magnitude window; shared copies synchronize cache access.

On the same i5-13600KF, a 36-second PCM replay with 160 ms appends and 16-second rolling windows reduced cumulative frontend median time from 1,053.4 to 323.6 ms (69.3%). Per-extraction p95 fell from 7.78 to 2.32 ms. Each variant had 12 measured replays and 2,700 measured extractions, following warmups in separate ABBA process blocks. These are CPU frontend timings, not equal full-model or microphone-to-screen speedups.

Separate CUDA process blocks compared complete native feeds on Chinese, English and repeated 36-second Chinese audio. Median feed time improved by 1.0%, 1.0% and 1.2%; p95 changed from 86.89 to 83.98 ms, 93.00 to 92.28 ms and 98.60 to 98.41 ms. These small full-model differences are close to runtime noise; the repeatable result is the frontend reduction. Encoder and autoregressive decoder work still dominate.

Regression checks compare every feature value with a fresh full extraction: 47 cases and 294 assertions cover reflected tails, non-hop endings, loud appends, normalization, sliding windows and independent owners. CUDA streaming checks cover 13 scenarios and 508 audio pushes, including a 36-second rolling recording, reset, silence and final speech appends. Committed, preview and final text and captured sample counts matched the baseline. The existing 320 ms finish context remains unchanged. This is fixture-based regression coverage, not a broad accuracy guarantee.

### Chunked prefill output work

Build `light-whisper-r2t2-7` executes only the decoder stack and KV writes on intermediate prefill blocks. The final block retains the original normalization, output projection and readback. Both graphs share the full graph's tensor allocation and use separate CUDA capture keys. Model weights, precision, attention, streaming windows and the 320 ms finish context are unchanged.

Warmed CUDA comparisons on the same RTX 4070 SUPER used ABBA and BAAB process blocks. Each of four processes per variant warmed all three clips, then ran two measured sweeps: eight runs per clip and variant. The table reports medians of summed stream start, feed and finish calls, excluding model loading, microphone capture and desktop rendering.

| Public audio | Runtime 6 | Runtime 7 | Reduction |
|:--|--:|--:|--:|
| Chinese, 4.20 s | 1,339.2 ms | 1,332.3 ms | 0.5%, within noise |
| English, 10.56 s | 3,642.2 ms | 3,553.7 ms | 2.4% |
| Chinese rolling, 36 s | 14,577.6 ms | 14,033.1 ms | 3.7% |

The rolling case improved by 4.5% and 3.5% in the two rounds. Its feed p95 fell from 96.63 to 92.69 ms. GPU clocks ranged from 2,910 to 2,925 MHz. These are fixture-based stream-call timings, not an isolated native prefill timer or a microphone-to-screen guarantee; Chinese short-clip improvement was not established.

Native CPU tests execute real ggml graphs with deterministic synthetic weights: 39 cases and 156 continuation steps preserve the frozen runtime's logits, hidden outputs and greedy-token traces bit-for-bit. They count actual graph operations and check that only the final block executes the output head and final normalization, including hidden-only mode, partial blocks, cache growth and graph rebuilds. Separate real-model CUDA checks retain all committed, preview and final outputs and sample counts across 13 scenarios and 508 pushes. Every benchmark replay also matches that reference. This is regression coverage, not a broad accuracy benchmark.


### Shared runtime and Qwen measurements

Build `light-whisper-asr-8` was compared with the preceding local installer engine on the same RTX 4070 SUPER. Each process warmed once and measured three repeated requests with identical PCM and the product VAD. These are server inference and wall times; they exclude model startup, microphone capture and desktop rendering.

| Chinese recording | Previous inference median | Shared inference median | Reduction |
|:--|--:|--:|--:|
| Natural speech, 31.12 s | 344.9 ms | 206.8 ms | 40.0% |
| Repeated speech, 32 s | 272.7 ms | 228.5 ms | 16.2% |

The natural-speech transcript matched exactly. The repeated clip retained seven complete repetitions and its partial final phrase; the older process omitted one complete repetition. A separate seven-fixture raw-native comparison preserved text and language across the KV-view optimization. The new GGUF package has different input-embedding storage and encoder behavior from the older provider; these checks do not establish broad CER/WER parity.

Three paced 16-second replays plus a 13-sample tail measured median first nonempty caption at 783.9 → 757.0 ms. Median per-run changed-caption gap p95 was 947.2 → 767.5 ms. All three new streams accepted exactly 256,013 samples and the original PCM hash. This Python stdio driver reproduces the scheduling policy; it does not execute the Rust capture loop or measure microphone-to-screen latency.

CPU synthetic checks retain 48 generation and 24 classification cases, 68 guards, and 8,736 bytes of frozen trace; resident generation performs zero host KV exports. A separate 57-case greedy readback check preserves 1,344 trace bytes, with 210 full-vocabulary reads replaced by 210 four-byte token reads. Actual CUDA argmax checks cover 39 finite-value tie/stride cases. R2T2 keeps its previous committed, preview, final and sample-count traces across 13 real-model scenarios and 508 pushes. The CPU Qwen DLL was also exercised on the packaged public Chinese clip.

### Qwen complete-preview finish reuse

A follow-up compares two previous and two updated packaged Qwen processes in old/new/new/old order. Each process runs all eight cases once for warmup and three times for measurement. The table pools six measured `stream_finish` requests per case; audio feed, microphone capture and desktop rendering are outside this interval.

| Complete unchanged preview | Previous finish median | Reused finish median |
|:--|--:|--:|
| Public Chinese clip, 4.20 s | 52.49 ms | 0.196 ms |
| Public English clip, 10.56 s | 127.45 ms | 0.204 ms |

The same clips with an additional one or thirteen samples, and repeated 16-second captures exceeding the preview window, still execute the full final callback. All 128 results across the four processes preserve exact text, language and captured sample counts against the reference. Existing VAD counters show zero final callback runs on eligible reuse and one on every fallback. Fallback median changes range from 17.3% lower to 2.34% higher; no fallback acceleration is claimed. An earlier source-versus-package run had a 26% higher Chinese one-sample-tail median, retained in the local evidence; the controlled packaged comparison did not reproduce it. Reuse eligibility frequency in real microphone recordings has not been measured.

### Bounded VAD feature reuse

Both servers reuse the current FireRedVAD owner's fbank and CMVN features only when normalized PCM is an unchanged prefix of the next input. Complete frames remain identical with `snip_edges=True` and zero dither; partial final frames retain their samples. Changed, shorter or shifted inputs rebuild. Each owner retains one prefix up to the Qwen preview limit of 12 seconds; longer final recordings clear the cache and use full extraction. Returned features own their storage, and extraction failures discard partial state. Full ONNX inference and speech segmentation still run on every call.

A local CPU comparison used the same frozen Chinese and English recordings, two warmups and eight alternating paired measurements against the original source. The table reports cumulative medians across 32 growing inputs ending at 12 seconds, excluding VAD construction/model loading.

| Recording | Feature extraction before/after | Complete VAD before/after |
|:--|--:|--:|
| Chinese | 156.5 / 15.4 ms | 448.6 / 305.4 ms |
| English | 159.1 / 14.6 ms | 450.7 / 303.3 ms |

Paired median feature reductions were 90.2% and 90.8%; complete VAD reductions were 32.1% and 32.8%. A 36-second replay with 12-second rolling windows reduced complete VAD time by 6.5% in both languages. All feature/probability bytes and speech regions matched. Complete VAD median/p95 ratios stayed below 1.05 across six workloads per language; no single-pass or whole-ASR speedup follows from these figures. Dedicated tests cover changed input, ownership, the cache bound, partial failures, silence/loud appends and one/thirteen-sample tails.

Qwen also caches optional GPU name/memory metadata for each loaded runtime, including failed probes. Runtime loads invalidate it, CPU fallback omits stale CUDA fields, and caller mutation cannot change cached metadata. This removes repeated status subprocess work; it does not accelerate the decoder.

Two Qwen encoder reuse experiments were discarded. Padded-token capacity graphs changed CPU softmax rounding; exact-shape reuse preserved all synthetic outputs and reduced graph rebuilds from 20 to 14, but four paired CUDA blocks showed only -0.98% to +0.23% changes across growing, repeated, complete and thirteen-sample-tail inputs. It did not reach the declared 3% retention threshold. The original native build and cuBLAS/Lt remain unchanged.

The final rebuilt engines were compared in old/new/new/old process order with one offline warmup and three paced 16-second replays per process. All twelve measured replays accepted the same 256,013 samples and PCM hash, preserving exact final text and language. First-caption median was 764.5 / 762.7 ms; finish-request median was 225.4 / 224.7 ms. The median of per-run changed-caption-gap p95 was 772.8 / 783.9 ms. All median/p95 guard ratios remained below 1.05. These small differences do not establish a whole-subtitle speedup; this Python stdio driver does not measure Rust microphone capture or desktop rendering.

### R2T2 final acoustic context

Build `light-whisper-asr-9` combines the pending real tail and the complete 320 ms acoustic context in one final decode for CUDA rolling sessions. Models, precision, rolling windows and live feed boundaries are unchanged.

On the same RTX 4070 SUPER, separate resident-model processes ran two rounds in ABBA/BAAB order, with one warmup per case and three measured sweeps per process. Each variant has twelve measured recordings per case. The interval below is `NativeRuntime.finish`; model loading, microphone capture, VAD, IPC and AI polish are outside it.

| Recording | Previous finish median | Combined finish median | Reduction |
|:--|--:|--:|--:|
| Chinese, 4.20 s | 85.90 ms | 30.42 ms | 64.6% |
| English, 10.56 s | 82.04 ms | 38.64 ms | 52.9% |
| Repeated Chinese, 36 s | 139.50 ms | 67.74 ms | 51.4% |

Both rounds and the aggregate passed the declared 10% finish target for the two original clips, with no greater-than-5% regression in first-caption compute time, feed p95 or finish p95. All 96 warmup/measured streams preserved exact committed, preview and final text, language and sample traces, and all eight processes closed normally. The final DLL also passes the thirteen-case, 508-feed base regression. A separate eight-case comparison preserves 729 feed responses across forced languages, context hints, mixed speech, rolling tails and real product VAD segmentation. Additional natural 31.12-second and FLEURS 10.38-second Chinese clips retain exact live/final text, language and sample traces across 260 feeds. CPU R2T2 output, cancellation, reset and captured counts match the preceding CPU package; CPU Qwen text and language also match. These public-fixture checks are limited regression evidence, not a broad CER/WER evaluation.

Rebuilt packaged engines were then replayed in old/new/new/old process order, with one offline warmup and three paced 16-second streams plus a thirteen-sample tail per process. All twelve measured streams retained exact final text, language, 256,013 captured samples and the accepted PCM hash, and every child exited normally. Median finish-request latency including VAD and stdio IPC fell from 201.95 to 73.29 ms; simulated audio-stop-to-final latency fell from 269.59 to 138.63 ms (48.6%). First-caption median was 1,023.64 / 1,029.34 ms. This driver exercises the packaged Python server and scheduling policy; it does not measure Rust microphone capture, desktop rendering or AI polish.

## Reproduce checks

`scripts/benchmark_r2t2_startup.py` takes explicit model, library, dependency-directory and PCM16 WAV paths. Save a baseline with `--output baseline.json`, then test a candidate with `--baseline baseline.json`. It compares committed traces and final text, including silence, resets and short recordings. `--max-first-audio-seconds` checks audio position, excluding compute time.

Native frontend regression (MSVC required; no model or CUDA):

```powershell
python scripts/test_r2t2_frontend_cache.py --source build/r2t2/source --build-dir build/native-tests/r2t2-frontend
```

`scripts/benchmark_r2t2_frontend.py` builds the real frontend without FFT mocks. Pass `--source`, `--build-dir` and a mono 16 kHz `--wav`. Build baseline and candidate separately with `--build-only`, then measure preserved executables with `--no-build` in ABBA order while other compilation and inference are idle.

`scripts/test_r2t2_native_cache.py` captures or checks complete CUDA streaming traces. Pass `--model`, `--library`, `--dependencies`, `--zh-wav`, `--en-wav` and a fresh `--output`; use `--reference baseline.json` to compare a candidate. It keeps the original finish padding and verifies exact audio accounting, including non-hop final appends.

`scripts/benchmark_r2t2_finish.py` compares preserved baseline and candidate wrapper directories and DLLs in separate sequential workers. Pass `--baseline-source-dir`, `--candidate-source-dir`, `--baseline-library`, `--candidate-library`, `--model`, `--dependencies`, `--reference`, `--zh-wav`, `--en-wav` and a fresh `--output-dir`. Defaults run two ABBA/BAAB rounds, one warmup per case and three measured sweeps per process. Exact live/final text, language and sample traces must match before timing is considered; native cleanup failures reject the worker. Keep other compilation and inference idle. `--self-test` checks the measurement guards without loading a model.

After building the native CPU runtime, extract the unmodified pinned runtime from its Git history and run the chunked-prefill unit check (MSVC required; no model or GPU):

```powershell
python -c "from pathlib import Path; import subprocess; Path('build/r2t2/prefill-baseline.cpp').write_bytes(subprocess.check_output(['git', '-C', 'build/r2t2/source', 'show', 'HEAD:src/framework/modules/transformers/qwen_causal_decode_runtime.cpp']))"
python scripts/test_r2t2_prefill.py --source build/r2t2/source --libraries build/r2t2/cpu --baseline build/r2t2/prefill-baseline.cpp --build-dir build/native-tests/r2t2-prefill
```

For real-model timing, `scripts/benchmark_r2t2_prefill.py` takes `--baseline-library`, `--candidate-library`, `--model`, `--dependencies`, `--reference`, `--zh-wav`, `--en-wav` and a new `--output-dir`. Use the frozen 13-scenario/508-push reference from `test_r2t2_native_cache.py`, `--rounds 2 --repeats 2 --order ABBA`, and idle other compilation/inference. It preloads the same CUDA dependencies in separate resident-model workers, alternates ABBA/BAAB order, checks every replay against the reference and saves raw timings, hashes and GPU snapshots. Independent process blocks and complete recordings are the repeated measurements; individual feeds are correlated.

The ignored Rust integration tests require these environment variables:

- `LIGHT_WHISPER_R2T2_TEST_PYTHON`: Python executable
- `LIGHT_WHISPER_R2T2_TEST_RESOURCES`: resource directory
- `LIGHT_WHISPER_R2T2_TEST_CACHE`: isolated model cache
- `LIGHT_WHISPER_R2T2_TEST_AUDIO`: mono 16-kHz PCM16 Chinese fixture matching the assertions in `native_integration_tests.rs`
- `LIGHT_WHISPER_R2T2_TEST_DATA`: writable test-data directory

Run sequentially with CUDA available; model downloads are disabled:

```powershell
cargo test --manifest-path src-tauri/Cargo.toml --lib native_integration_tests -- --ignored --test-threads=1
```
