# Implementation correspondence and repair evidence

Current optimization correspondence: [2026-10-11 verification](optimization-20261011.md).
The earlier PR #9/PR #10 baselines and results below remain historical evidence.

Baseline: d29cd45db8876bd7bcfa915ae642af3b0fcc4bbe, PR #9.

| Boundary | Before | Repair/evidence |
| --- | --- | --- |
| OAuth ownership | Source interleaving and legacy model resurrected logout/overrode a new login | Shared epoch/mutex coordinator, refresh serialization and stale commit/fatal-failure rejection; frozen coordinator tests. |
| Device challenge | Completion allocated a fresh owner after logout | Start reserves owner; server binds actual ID/code; completion claims before polling; challenge tests. |
| OAuth storage | Malformed metadata defaulted to logged-in; token written before metadata | Atomic metadata, intent/tombstone first, committed metadata last, invalid/orphan refresh rejection; storage tests and OAuthStorage. |
| Provider credentials | A key before auth await, B endpoint afterward; raw caches lacked provider identity | Four LLM paths freeze config/endpoint and load captured provider slot; cloud ASR additionally owns its engine and snapshots region/key/endpoint, and Alibaba catalog uses its own region slot. Snapshot source guard fails against baseline and passes current code; ProviderRequestsLegacy fails wrong-recipient invariant. |
| Keyring failures | Compiled write/delete regression failed intended assertions | All callers propagate errors before cache publication; NoEntry delete is idempotent; two tests pass without exposing payload. |
| Monitor ownership | No reservation while driver startup waited; legacy seam failed stop/recording assertion | Monitor generations reserved/invalidated under lock; publication checks recording then monitor lock; stale workers stop/join; monitor regression and negative model. |
| Monitor unmount | Actual hook test observed start after delayed subscription resolved post-unmount | Disposal checks before/after stop await; test passes and listener is cleaned up. |
| Model-status unmount | Actual hook regression found late status-listener registration was never cleaned up | Per-effect disposal guard suppresses old events and immediately cleans a late listener; two tests pass. |
| ASR settings | Actual tests exposed initial selection/catalog overwriting newer values | Selection/catalog/context/unmount versions; thirteen hook tests pass. |
| Engine reply identity | Production predicate accepted untagged response; intended regression assertion failed | Require exact Some(request_id); bundled servers echo IDs; current test passes. Older incompatible engines require updating. |
| Hotkey pending start | Release before async slot reservation was lost; compiled legacy scaffold failed four of five owner tests | Per-gate intent, bind under recording mutex, exact-session release/failure/retirement; five frozen owner tests pass. |
| Hotkey cleanup | Old error reset looked up the new registered gate | Preserve original Arc, serialize gate transitions, reject retired registrations and release on mode switches without backend migration. |
| Hotkey registration identity | Same-backend mode switch retained a gate; native registrations reused fixed IDs | Mode changes always replace gates; configuration/dispatch serialize; native IDs never reuse. Actual allocator RED, static mode guard RED, two new TLA counterexamples and exhaustion test. |
| Hotkey rollback | Lifecycle failure republished a retired gate and could leak a new native registration; errors were ignored | Clear new registrations, rebuild old specs with fresh gate/ID, clear affected slots on restoration failure and return errors; setup-failure model and two static source RED/GREEN guards. |
| Subtitle final | Earlier assertion passed with late-interim guard removed | Independent final-seen state; same mutation now violates SubtitleFinalStaysFinal; production guard/regression retained. |
| Formal binding gate | Seven verifier regressions failed because predicate reachability and negated/comment/string references counted as proof | Ten regressions now pass; safety/liveness must be asserted, and only explicitly declared state-changing actions can use reachability. |
| Web search cache publication | Compiled legacy operation seam gave settled disk/cache pairs (second, first) and (new, old) | Real operation mutex covers setter, lazy getter and startup storage/cache publication; three frozen tests pass. WebSearchKeys separates I/O and publication, and two legacy controls violate settled equality/stale-load rejection. |
| Model catalog auth | Actual catalog helper RED returned account B's bearer for a resolved account A key | Config captured before auth; resolver returns key and catalog token from the same session. Account-switch regression plus derived-key/bearer pairing tests pass; ProviderAuthSnapshot includes account change/logout. |
| Auxiliary LLM auth | Extended source guard found correction validation lacked OAuth resolution and selection/vision lacked captured auth modes | Correction validation, selection, vision and catalog join the four original LLM snapshot paths; resolver no longer rereads live profile preferences. Guard covers eight LLM/catalog plus three cloud paths. |
| Download cancel/retry | Four actual hook tests failed: initial/retry timers survived cancellation, late rejection retried, retired listener restarted the engine | Owned timer plus generation invalidation on cancel/retry/unmount; promise and effect guards. All four frozen regressions pass; DownloadUiLifecycle includes pending completion and StrictMode replay with two failing legacy controls. |
| Recording listener disposal | Two actual hook regressions showed a post-unmount/retired listener could display a toast | Shared event callback checks its owning effect's disposal before running; both tests pass and delayed listener cleanup is checked. |
| Final model correspondence review | Recording was bound to a download listener model, and stale completion used only a guard-derived flag | Separate EventSubscriptionLifecycle models pending/late registration and recording effects. Download completion records before/after publication counts; an independent legacy control fails OldRequestCannotPublish. |
| Release CI gate | The real wait_for_ci function accepted a successful workflow with a missing/skipped/failed formal job in three mocked regressions | Require all four named jobs for the exact candidate SHA. Five regressions pass on Windows/Linux and run in Python CI; formal CI uses the project's Python version. No publication path is invoked by these tests. |

OAuth declaration-scaffold RED is interface evidence, not original-service race
reproduction. Hotkey/monitor pure-seam RED has the same limit; actual source
interleavings and negative models separately establish the baseline mismatch.
Source guards are static checks, not Rust execution proofs. Final commands/results
are in results.json and the exact-head CI run on the PR.

The web-search operation seam RED is also interface evidence: its body initially
ran the closure without ownership, matching the source interleaving. The three
production callers were then wired to the tested mutex and independently reviewed.
The download/recording listener and catalog-helper RED cases execute the actual
production hook/helper. Static source-guard failures are kept separate from these
runtime regressions. Frozen new test hashes are recorded in results.json.

Profile updates retain version ordering; normalization and provenance have actual
unit tests. App rules retain first-match/captured context. Cloud key saves serialize disk/cache publication with configuration changes. Directory migration
copies before commit and rechecks before cleanup. History uses SQLite transactions
and actual references/leases before GC. Selection replacement rechecks context
around blocking text capture. Window generations are separate from session IDs.
Autostart confirms plugin state before success, and theme follows media changes
only in system mode. All concrete paths/tests and assumptions are in the registry.

No live user OAuth credentials, microphone recordings or provider charges are
needed. Driver/native behavior, platform storage, availability and linguistic
quality remain environment assumptions/test targets. Arbitrary power-loss or
filesystem corruption is not proved. If every marker/deletion write fails,
durable logout is impossible: memory clears and the command returns an error.
Root independently reviews/tests the combined patch before commit/push/PR update.
