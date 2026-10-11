# Optimization verification correspondence

Baseline: `bbccaf9`. Scope: SettingsPage profile loading, history percentile rank
preservation, overlapping history audio I/O, and parallel assistant preparation.

| Requirement | Implementation and evidence |
| --- | --- |
| Loaded preferences precede editable controls; load failure supports retry | `SettingsPage.tsx::settingsReady` and `refreshProfileAndKeys`; `SettingsPageProfileLoad.test.tsx` executes pending-load and failure/retry behavior, saved history preference restoration, write suppression and OAuth status refresh after loading. Both tests fail semantically against baseline. `SettingsProfileLoad.cfg` checks two reads and one representative History preference; the full SettingsContracts field partition remains in its original workload. |
| Percentile behavior is unchanged | `history_service.rs::latency_stats`; `latency_percentiles_match_sorted_rank_for_empty_tied_and_large_inputs` compares p50/p95 with the previous sorted rounded ranks. This is a preservation regression designed to accept the previous definition; it does not measure baseline runtime, speed or allocation counts. |
| Fresh screen context is safe after the join | `assistant_service.rs::discard_stale_screen_context` is called by the actual post-join request path. Three Rust regressions cover changed process/title or unavailable foreground, matching foreground and reused pre-polish descriptions. The baseline lacks the helper (`INTERFACE_PENDING`); no baseline semantic Rust RED is claimed. AppWorkflow checks joined preparation and the sampled dispatch window; removing the check violates `FreshScreenIsCurrentAtDispatch`. |
| External search and fresh screen preparation finish before dispatch | AppWorkflow permits both preparation orders and foreground movement while either branch waits. Removing the join settlement conditions violates `AssistantPreparationSettlesBeforeDispatch`. Both futures remain owned by the existing cancellable assistant future. ModelNative tools execute during the LLM request and are outside the external preparation model. |
| Audio I/O overlaps processing while final result ordering remains intact | AppWorkflow starts `audioWrite` at recording stop and permits LLM work while it is pending. Success/failure settles before the history attempt, terminal transcription/subtitle results and paste authorization. Removing the settlement guard violates `HistorySettlesBeforePublication`. Assistant stream chunks/done may arrive earlier and are excluded. The model establishes bounded ordering, not a wall-clock speedup. |

Foreground identity is sampled after preparation. Windows may change focus after
that read and before or during HTTP dispatch; the model does not promise a focus
lock. Integrated screen preparation represents fresh payloads; reused pre-polish
descriptions retain prior semantics and are checked by the Rust tests.

No live microphone, OAuth credentials or charged provider requests are used.
Native APIs, network/LLM answers, SQLite and filesystem outcomes remain trusted
inputs. CI already discovers the tests, registry configurations and negative
controls; no workflow change is required.

Three temporary reachability witnesses independently refute serialized audio/LLM
work and each fixed preparation completion order. These are reachability traces,
not additional safety regressions or entries in the negative-control total.
The dedicated verification agent executes the checks; the root agent reviews
the changes and recorded evidence without executing tests.

Final local gates passed: 514 frontend tests plus one fluidity check; Rust
formatting/Clippy and 663 tests (10 ignored, one CI performance filter); 11 formal
verifier regressions; 32 TLA+ models across 46 positive configurations; 47 expected
counterexamples; 29 Lean theorems; all 65 integrated actions across ten workloads.
The final formal runner reuses only successful logs with matching source/config
hashes and reruns all negative controls.

Measured results, commands, tool versions and the verified source snapshot are
saved in [optimization-20261011.json](optimization-20261011.json). Raw local logs
and summaries remain outside the repository; the artifact records their filenames.
Machine-specific absolute paths are reported privately to the root agent.
