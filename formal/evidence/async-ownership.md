# Async ownership and repair correspondence

Seven finite companion models cover six repair groups. These are application
contracts plus reviewed source/test correspondence, not compiled refinement or
proofs of SQLite, keyring, Windows input, CPAL, network transport or GPU inference.
The original detailed models and their negative mutation anchors remain intact.

| Model | Positive distinct states | Concrete bounded contract |
| --- | ---: | --- |
| AssistantCredentialOwnership | 11,583 | Two edits, two provider switches, two independent success/failure reads, serialized saves and one failed-write retry per edit. Captured provider and dirty/read/edit ownership survive awaits. Only a matching successful save clears a draft. |
| MicrophoneAsyncOwnership | 1,684 | Two independent test owners, out-of-order completion, active/enabled/mounted/recording intent, generation and late-start compensation. |
| MicrophoneEffectOwners | 25 | Two effect instances; a shared native-operation queue orders old-start compensation before replacement, and retired test completion cannot stop the new owner. |
| HistoryLeaseInterleavings | 339 | Two independent tasks and two audio identities; source deletion, release transaction and GC. Lease count equals live holders outside the transaction. |
| OutputDrainOwnership | 36 | Dictation A processing overlaps assistant B starting/recording; success, error, start-cancel and start-error schedule eligible drains; session/target/text remain distinct. Changed target routes to recovery. |
| IpcCommandDeadline | 21 | Write, flush and read share three ticks. Timeout or partial-frame cancellation invalidates the process and releases the command lock. |
| ModelIntegrityRepair | 13 | A present invalid completion manifest is authoritative; absent metadata retains legacy compatibility. Missing/corrupt caches can be explicitly repaired and reinspected as ready. |

HistoryRecords retains its separate five-row, three-audio-class, single
reprocessor/count-one bound. The lease companion focuses on release after source
row removal. Its transaction is DELETE `count = 1`, UPDATE `count > 1`, commit;
the old UPDATE-then-DELETE order violates `LeaseCountMatchesHolders` with two
holders. Atomic SQL microsteps are replayed at their actual public commit call;
the driver does not substitute a second lease implementation.

Output deduplication covers currently pending session IDs. It assumes one
production finalizer per unique recording session and deliberately permits
re-enqueue after draining; there is no global exactly-once ledger. The model
checks eligible terminal scheduling, while exact function-body source guards
bind success, error, cancelled startup and failed startup to the shared scheduler.
The runtime replay calls the actual `drain_pending_pastes` controller and AppState
mutexes. Only foreground/native-paste primitives are injected. Acknowledged OS
input does not prove a foreign application consumed it, and focus is sampled.

`scripts/generate_async_ownership_traces.py` runs the pinned TLC 1.7.4 jar, checks
its SHA-256, and extracts genuine counterexample `State` blocks into
`formal/traces/*.tlc.txt`. Each JSON binds model/config/jar/counterexample hashes
and the exact `lastEvent` sequence. Initial credential hydration is outside the companion model. Each provider
switch starts its read before a subsequent edit or successful save can change
the captured draft, matching the actual callback boundary. The stale-read
witness establishes a nonempty latest key before the old failure; replacement
monitor witnesses resolve the retired promise after the new native start.
All 48 new byte-hashed model/config/counterexample inputs use LF. Git
attributes pin these formats to LF, and the generator explicitly writes LF on
Windows. Two portability regressions check UTF-8 bytes and actual `git check-attr`
results independently of the index. Before repair they exposed 34 CRLF failures
without fixture errors; the full provenance/portability slice now passes eight
tests. No existing model was arbitrarily normalized.
The normal formal gate and frontend/native
replay helpers reject stale source/config, modified logs, edited schedules and
unmapped events. These hashes establish checked-in correspondence and drift
detection, not an authenticated signature from a theorem prover.

The registered wrong configurations expose captured-provider misrouting,
stale/saved-draft read publication, missing late-start compensation, stale test
ownership, per-effect native queues, retired test cleanup, missing success/cancel/
start-error drains, blind paste after target change, per-phase deadline reset,
unbounded stdin write, reusable cancelled frames and invalid-manifest fallback.
Each must return Java exit 12 with its named violated invariant. The separate
`ModelIntegrityRepairTrace.cfg` uses the deliberately false `RepairPathNotReached`
only to generate a positive repair-path witness; it is neither a wrong
implementation variant nor a safety proof.

Runtime replay entry points:

- `SettingsPageProviderDiscovery.test.tsx`: actual SettingsPage key edits,
  provider callbacks, debounced setter promises and read effects.
- `useMicrophoneSettings.test.tsx`: actual hook test/start promises, intent
  retirement and replacement mount, with separately controlled native primitives.
- `history_service.rs::async_ownership_replay_tests`: actual public
  get-for-reprocess/delete/release/cleanup calls, SQLite and WAV files in an
  isolated child data directory.
- `output_tests.rs::async_ownership_replay_tests`: actual AppState/controller,
  occupied and released slots, target recovery, exact failed-paste text and
  dispatch mutex exclusion.
- `ipc_recovery_tests.rs::async_ownership_replay_tests`: actual command timeout
  helper, live child stdin/flush/read, cancellation, process invalidation and a
  fresh server acquiring the released lock.
- `test_async_ownership_replay.py`: actual cache lookup and explicit
  `download_model` verification/atomic completion publication on temporary local
  bytes. Network calls are rejected; this is not a GPU smoke test.

The baseline IPC replay compiled and failed semantically because its private
timeout delegate ignored the requested budget (`Elapsed(())` at the outer
deadline). The corrected native replay filter passed six tests, with one child
fixture ignored. The startup source regression separately failed on the missing
`emit_start_error` drain call, then passed all three wiring checks after repair.
Existing dedicated regression slices supply the other baseline RED evidence;
their implementation owners record full corrected-suite results separately.
Formal wrong configurations are deliberate model variants. Four additional
isolated source mutations remove the stale-failure guard, captured-draft guard,
retired-effect owner guards or shared operation queue. Each corrected snapshot
passes exactly one selected replay; each wrong source fails exactly that replay
with an assertion failure. The live checkout is never mutated. Exact source
hashes and measured counts are in [async ownership results](async-ownership-results.json).

Reproduce the bounded evidence:

```sh
python scripts/generate_async_ownership_traces.py --tlc-jar /path/to/tla2tools.jar
python scripts/generate_async_ownership_traces.py --check
python scripts/test_async_ownership_traces.py
python scripts/test_async_output_wiring.py
python scripts/run_async_replay_mutations.py --workspace /explicit/local/scratch
python scripts/check_formal.py --inventory-only
pnpm exec vitest run src/pages/__tests__/SettingsPageProviderDiscovery.test.tsx src/hooks/__tests__/useMicrophoneSettings.test.tsx -t TLC
cargo test --manifest-path src-tauri/Cargo.toml --lib async_ownership_replay_tests -- --nocapture
uv run --no-sync python -m unittest discover -s src-tauri/resources -p test_async_ownership_replay.py
```

## Final Windows working-tree validation

Validated locally on 2026-10-14, against the repairs based on main `81b6da0`:

| Gate | Result |
| --- | --- |
| `pnpm check` | 563 frontend tests and one JSDOM animation/performance test passed; whitespace, lint, TypeScript, build and bundle budget passed. |
| Rust all-target tests, locked | 684 passed, 11 ignored fixtures/integration cases; one hotword performance test excluded using the CI command. |
| Rust formatting and Clippy all targets | Passed, including `-D warnings`. |
| Python resource discovery | 123 passed; source compilation passed. |
| Build atomicity / release CI / fail-fast regressions | 20 / 5 / 2 passed. |
| Formal verifier / provenance and LF portability / output wiring regressions | 11 / 8 / 3 passed. |
| Full formal gate | 53 positive configurations validated; 63 fault controls produced their expected violations; one separate repair reachability witness; Lean passed. All 65 AppWorkflow actions reached. |

The first full formal run executed 22 positive configurations and reused 31
unchanged proof logs only after matching source/config hashes and successful TLC
completion. The final LF-byte verification reran five configurations whose hashes
changed and reused 48 matching logs from the validated runs. All 64 negative/witness
cases and Lean ran again. This is not a claim that all unchanged configurations
were freshly explored in this round.

After LF provenance regeneration, the actual frontend/native/cache replay slices
passed again (7 / 6 / 1 tests). All four isolated source mutations were also rerun:
each corrected baseline passed and each wrong variant failed one semantic
assertion. No mutation was applied to the live working tree.

The initial source-validation run rejected the stale engine archive. A subsequent
local packaging check rebuilt the engine, passed source and 7-Zip integrity
verification, and completed `pnpm tauri build`. The NSIS installer passed its
archive test; its embedded engine matched the rebuilt archive byte for byte by
size and SHA-256. The installer was neither published nor installed. Live WebView
focus/input, physical microphones and GPU inference were not exercised. JSDOM
measurements do not establish Windows 60fps.
