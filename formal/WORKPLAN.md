# Whole-application contract verification

Acceptance is defined at the application's owned state and command boundaries.
Every registered IPC command, asynchronous event family, and bundled engine
protocol must have a reviewed contract, a formal obligation, implementation
evidence, and an explicit environment assumption. A group label or a passing
action-count check is not evidence for an unexamined member of that group.

The trusted boundary includes Windows/Tauri/CPAL/keyring/SQLite primitives,
network transport, and the learned ASR/LLM model internals. Their failures are
inputs to application contracts; their own implementations are not proved.
Visual appearance and linguistic output quality require different acceptance
criteria. This work must never be presented as a Rust/TypeScript compiler-to-
machine-code refinement proof.

## Required gates

1. Inventory all commands, event families, lifecycle hooks, and engine protocols.
2. Map each to modeled state transitions and safety properties. Check conditional
   liveness only under stated timeout/scheduler/storage fairness assumptions.
3. Prove parameter-independent ownership and decision contracts in Lean; retain
   finite TLA+ checks for interleavings and product-state interactions.
4. Connect each obligation to actual production-path tests or a reviewed pure
   implementation seam. A model passing alone does not close an obligation.
5. Exercise intentional negative mutations or legacy counterexamples for each
   important property, so a vacuous assertion cannot masquerade as a check.
6. Independently review security, privacy, persistence, and destructive paths.
7. Run the final formal, Rust, frontend, Python, lint/build gates and update PR #9.

## Completed model slices

| Slice | Formal target | Implementation target |
| --- | --- | --- |
| OAuth | Login/refresh/logout generations, atomic publication, error invalidation | Both provider services and session coordinator |
| Capture | Native acceptance/fallback, sample ownership and cap, monitor/device lifecycle | Native/CPAL capture, monitor, engine input |
| Hotkeys | Registration conflicts, hold/toggle, duplicate/stale input | Hotkey dispatcher and recording entry |
| Engine setup | Four engines, directories, endpoints, key slots, restart/start ownership | Engine lifecycle, migration and settings hooks |
| Personalization | Import/normalization/export, hotwords, correction provenance, app rules | Profile services and commands |
| Context/routing | Independent Off/On/Auto settings, explicit choices, Jev fail-open, source constraints | Jev, AI polish, assistant, selection context |
| History | Multiple rows/shared audio, retention, leases, reprocessing, exports | SQLite history and command paths |
| Presentation | Window generations, stale events, hide/show, terminal UI state | Windows, subtitle/selection overlay, tray/startup |
| Async settings | Context and request versions, discovery, debounce/unmount, failure retention | Provider/model/device/settings hooks |
| Request protocols | Request/response identity, retries, cancellation, terminal/partial output | Rust/Python engine and LLM transports |
| Validation | URL/length/path partitions, import errors, update version rules | IPC and external-data validation |
| Credential publication | Phased storage/cache ownership, captured auth choices and account pairing | Web key setters/getters/startup, all LLM/catalog auth callers |
| UI disposal/cancellation | Revoked timers, stale promise completion and retired listeners | Model download and recording hooks |
| Async ownership and repair | Captured/dirty credentials, two test/effect owners, two lease holders, overlapping output, total IPC deadline, authoritative corrupt cache and repair | SettingsPage, useMicrophoneSettings, SQLite history, actual output controller, child-process IPC and cache/downloader trace replays |

The verifier itself has eleven regression cases, including the CI/verifier TLC
checksum pin comparison: a reachable predicate is not an
asserted property, and references under negation/implication, strings or comments
cannot establish an obligation. Only explicit state-changing actions may use
reachability evidence.

The model/implementation slices are recorded in verification.json, README.md,
COVERAGE.md and evidence/source-contracts.md. Final gate status and measured
results are recorded in evidence/results.json; the exact-head PR CI is the
authoritative remote check. Proof boundaries remain explicit in README.md.
