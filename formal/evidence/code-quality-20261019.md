# Code quality and verification, 2026-10-19

Base: `507ed50`. Changes and verification are local to the working tree.

Follow-up: the two KaTeX findings recorded below are now resolved. The
[KaTeX security verification](katex-security-20261019.md) records the dependency
upgrade, reproduced regressions and subsequent complete verification. The
latest production dependency audit has zero findings at every severity.

## Changes

| Area | Problem and resulting behavior |
| --- | --- |
| Polish credentials | Reads, provider changes, startup and translation auto-enable could write the displayed credential into the currently active provider. Reads and enabled-only configuration no longer write credentials. Actual edits capture their provider/version, serialize saves and retain failed drafts. Omitted IPC arguments retain legacy behavior; an explicit empty key still deletes only its target. |
| Runtime credential state | Removed two write-only secret caches, their setters and redundant synchronization paths. Requests continue loading the key for their captured provider. |
| Engine settings | Separate read/modify/atomic-replace operations could lose another writer's fields. One mutex now covers the complete mutation, including GPU settings and model-directory updates. Unknown fields survive and failed writes release ownership. |
| Theme | Mounted hook consumers could disagree, stale OS/storage callbacks could override manual choices, and late mounts could reset a choice when persistence failed. Consumers now share the accepted choice, ignore stale OS ownership and read the latest stored preference on storage delivery. Full teardown permits a fresh storage read. |
| Engine archive | Verification previously omitted most declared native/shared dependencies. Every declared dependency now has size/hash validation, bounded streaming reads and flat-name validation. Windows case-insensitive lookup accepts a single valid casing while duplicate/colliding paths remain rejected. |
| Hotword correction | Reused the existing candidate application function. Exact matches and cheap rejection rules precede edit-distance work; an absent alias match bypasses unnecessary target validation. Original ranking, the 100-alias limit, inflection rules and distance thresholds remain intact. |
| Test entry points | Added four existing packaging/backend test scripts to CI and the local release gate. Vitest defaults to one worker. |

The actual bundled archive contains `_internal/VCOMP140.DLL`; its size/hash
exactly match both manifests' lowercase `vcomp140.dll` declarations. The
case-insensitive lookup fixes a reproduced verifier rejection of this valid
Windows archive. The archive itself was not rebuilt or modified.

## Regression coverage

| Area | Concrete boundaries checked |
| --- | --- |
| Credentials | Initial non-default provider, rapid provider changes, deferred reads, dirty edits, failed saves, stale read after save completion, explicit deletion, enabled-only startup, translation with a pending read/edit, optional/legacy IPC payloads and actual keyring-plugin IPC backed by an isolated in-memory store. |
| Engine settings | Paused real transactions interleaved with engine/model/GPU/directory set/reset writers; preservation of unknown fields; write-error recovery. Subprocess isolation protects real user configuration. The unfixed implementation reproduced five lost updates. |
| Theme | All mounted consumers, manual light/dark under OS changes, cross-window storage delivery, stale queued notifications, invalid/removed/cleared storage, unrelated/session storage, unavailable storage, late mounts, complete teardown/remount, delayed transition callbacks, reduced motion and cleanup. Late-mount dark/light cases reproduced the original failure. |
| Archive | Missing/corrupt local and shared dependencies, malformed tables/types/sizes/digests, unsafe names, duplicates before/after directories, nonregular entries, Windows case collisions, valid single case variants, bounded reads and the actual 640,384,716-byte engine archive. |
| Hotwords | Existing Chinese/ASCII and real-profile replay cases, plus 42 concrete ASCII boundary cases. Alias regressions preserve the ranked 100-entry limit, target membership and empty-original handling. The original ten functional cases passed before the optimization and remain passing afterward. |

The unchanged performance test uses 100 hotwords, a populated alias profile,
100 warmups and 1,000 measured corrections. In this resource-limited run its
p95 changed from **2,233 us** to **501 us**, retaining four required replacements
and the existing **less than 1,000 us** assertion. This is a measured workload,
not a latency guarantee for every profile or machine.

## Verification results

| Gate | Result |
| --- | --- |
| `pnpm check` | Passed: 614 functional tests, one fluidity test, whitespace, ESLint, TypeScript, Vite build and bundle budgets. |
| Rust format / Clippy | Passed with all targets, locked/offline dependencies and `-D warnings`. |
| Rust all targets | Passed: 762 tests, zero failures, 12 pre-existing ignored entries; includes the hotword performance test. |
| Python | Passed: lockfile check, source compilation, 224 resource tests and 99 script tests. |
| Actual engine archive | Passed via `node scripts/verify_engine_archive.mjs`. |
| Full formal verification | Passed: 41 models, 55 positive configurations, all 66 counterexample/witness checks and Lean StateContracts; all 65 declared AppWorkflow actions reached across ten workloads. Twenty unchanged successful positive runs were reused only after matching source/config hashes; inventory, bindings, provenance, Lean and all negative/witness checks ran again. |
| Production dependency audit | Existing `--prod --audit-level high` gate passed: zero moderate/high/critical findings; two low findings are recorded below. |

The 12 Rust ignored entries comprise five microphone/CUDA integration tests,
two live search endpoint tests, three subprocess fixtures invoked by their
parent tests/replays, one explicit IPC-artifact regeneration test and one
intentional legacy-race RED demonstration. They were not enabled wholesale.

The dependency audit reports [GHSA-238p-pmpm-9mq7](https://github.com/advisories/GHSA-238p-pmpm-9mq7)
for the unchanged direct KaTeX 0.17.0 and transitive
`rehype-katex > katex` 0.16.47 paths. These are two low-severity dependency
findings for one advisory, not two newly reproduced application vulnerabilities.
Dependency upgrading is outside this patch; the package manifest/lockfile were
not changed. The diagnostic JSON audit retains these findings separately from
the successful existing CI severity-threshold command.

## Formal correspondence and limits

Added `EngineConfigurationWrites` and `ThemeSynchronization` with positive
configurations and negative controls. Registry and coverage documents include
their implementation/evidence paths. Existing credential ownership contracts
apply independently to assistant and polish editors, with additional actual
polish IPC and production-page regressions.

Engine mutation modeling covers four writers within one application process,
atomic replacement success/failure, unknown fields and transaction settlement.
Theme modeling covers two windows with two mounted consumers each, manual/system
modes and delivery of the latest persisted value. Mount lifecycles and browser
transitions are checked by implementation tests, outside that abstract model.

Passing these checks does not establish every possible source input,
cross-editor combination, external-process filesystem writer, native browser,
microphone/GPU/network implementation or OS durability property. Hotword text
matching and archive bytes have concrete regressions, not source-level
refinement proofs. Wider retirement of interim-ASR/WAV helper paths was left
outside this patch because it would cross packaged-runtime boundaries.

## Resource limits and evidence

All resumed verification jobs ran sequentially. Child processes inherited
BelowNormal priority and affinity for two logical processors. Rust build/test
workers and numerical thread pools were limited to one; Node heap to 768 MiB;
Java heap to 1,024 MiB with two active processors. The actual compiler processes
were checked for inherited priority/affinity. No additional test jobs ran in
the test-authoring agents.

Logs and model-checker results are in the ignored local directory
`tmp/code-quality-20261019/`:

- `frontend-final.log`, `rust-lint-final.log`, `rust-tests-final.log`
- `python-final.log`, `python-scripts-final.log`, `engine-archive-final.log`
- `theme-late-mount-red.log`, `theme-final.log`, `hotword-boundaries-before.log`
- `rust-perf-final.log` (the original 2,233 us failure), `hotword-after.log`
- `archive-case-positive-red.log`, `archive-vcomp-inspection.log`
- `formal-final.log`, `formal-results/summary.json`, per-configuration logs/hashes
- `dependency-audit-final.log`, `dependency-audit-final.json`

No commit, push, release or installed-app replacement was performed.
