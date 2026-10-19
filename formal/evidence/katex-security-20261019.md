# KaTeX security verification, 2026-10-19

Follow-up to [the code quality verification](code-quality-20261019.md), on the
same local working tree based on `507ed50`.

## Change and regression evidence

The two low-severity dependency findings were two paths to
[GHSA-238p-pmpm-9mq7](https://github.com/KaTeX/KaTeX/security/advisories/GHSA-238p-pmpm-9mq7).
Direct KaTeX 0.17.0 and transitive KaTeX 0.16.47 are replaced with patched
0.18.2. The root dependency is the single version source; the pnpm workspace
override refers to `$katex`, covering both `rehype-katex` and
`remark-math > micromark-extension-math`. This override is necessary because
`rehype-katex` 7.0.1 still declares the vulnerable 0.16 series. No other package
version changed. The Markdown implementation and its styles were unchanged.

The dedicated regression file is
`src/components/MarkdownContentSecurity.test.tsx`. With the original installed
dependencies, two tests reproduced inherited `Object.prototype.trust` enabling
otherwise forbidden links. With the upgrade, all three tests pass:

- Direct rendering ignores inherited trust when options are omitted.
- The actual Markdown component blocks inherited trust and still renders
  inline and display math.
- An explicit own `trust: true` option continues to enable trusted commands.

The test restores the original prototype descriptor in a `finally` block.
It uses inert `.invalid` URLs and does not fetch remote content.

## Final verification

| Gate | Result |
| --- | --- |
| Offline frozen install | Passed, with dependency lifecycle scripts disabled. |
| Production dependency audit | Passed, exit 0: zero info, low, moderate, high or critical findings. |
| `pnpm check` | Passed: 617 functional tests in 60 files, one fluidity test, whitespace, ESLint, TypeScript, Vite build and bundle budgets. |
| Rust format / Clippy | Passed, all targets, locked/offline dependencies and `-D warnings`. |
| Rust all targets | Passed: 762 tests, zero failures, 12 pre-existing ignored entries. |
| Python | Passed: lockfile check, source compilation, 224 resource tests and 99 script tests. |
| Actual engine archive | Passed: `node scripts/verify_engine_archive.mjs`, 640,384,716 bytes; archive unchanged. |
| Formal gate | Passed: 41 models, 55 positive configurations, 66 expected counterexample/witness checks, Lean StateContracts and 17 provenance fixtures. All 65 declared AppWorkflow actions reached across ten workloads. |

The first Rust run failed only its existing timing assertion (hotword p95
1,634 us, limit less than 1,000 us). Under the same resource limits, an isolated
rerun measured 751 us, then the entire all-target suite passed with 529 us.
The first failure log is retained. No production code, timing threshold or test
selection was changed to obtain that result. This timing check remains sensitive
to runtime scheduling. The 12 existing ignored entries are accounted for in the
preceding report; they are not counted as passed tests.

The formal runner rechecked inventory, implementation bindings, trace provenance
and action coverage. All 55 positive results were reused only after matching
current TLA+/CFG hashes and confirming successful checker logs. Lean and all
66 counterexample/witness checks ran again, producing 121 result records.
The models and their bounds are unchanged. They do not prove the external KaTeX
parser; the concrete security regressions exercise that implementation.

## Resource limits and logs

Verification jobs ran sequentially. Processes inherited BelowNormal priority
and affinity for two logical processors. Build/test and numerical workers were
limited to one, Node heap to 768 MiB and Java heap to 1,024 MiB with two active
processors. Actual Node, Rust linker and Java process limits were inspected.
Test authoring did not run another local verification job.

Ignored local evidence: `tmp/katex-security-20261019/`:

- `security-red.log`, `security-green.log`, `katex-resolution.log`
- `install.log`, `frozen-install.log`, `audit-final.json`
- `frontend-final.log`, `rust-lint-final.log`, `rust-tests-final.log`
- `rust-tests-initial.log`, `rust-perf-isolated.log`
- `python-lock-and-compile-final.log`, `python-resources-final.log`, `python-scripts-final.log`
- `engine-archive-final.log`, `formal-final.log`, `formal-results/summary.json`

No commit, push, release or installed-app replacement was performed.
