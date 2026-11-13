# Reusable iOS graphics regression testing

The only manual graphics-testing entrypoint is
[`ios-graphics-devicefarm.yml`](../.github/workflows/ios-graphics-devicefarm.yml)
on **main**. Never create a new workflow for a new SDK version or hypothesis.

The older 7.2.2, 7.3.0 direct-ChildView, EAGL instrumentation, and
surface-change-latch runs remain available in GitHub Actions history. Existing
reports and source branches are retained. The separate `ios-devicefarm.yml`
covers SQLite and is **not** part of this graphics-workflow consolidation.

## Run a new experiment

Open **Actions → iOS graphics / reusable Device Farm → Run workflow**.
Keep the workflow branch set to **main**. Enter:

| Input | Meaning |
| --- | --- |
| `sdk_run_id` | GitHub Actions run in `TotalCross/totalcross` that built the SDK |
| `sdk_source_sha` | Exact 40-character source SHA of that upstream run |
| `sdk_version` | SDK package version, e.g. `7.2.2` or `7.3.0` |
| `sdk_artifact_id` | Optional ID if the run has multiple artifacts |
| `expected_sdk_digest` | Optional explicit outer artifact ZIP digest |
| `test_ref` | Branch or immutable commit containing the Java graphics test and Appium test module |
| `native_markers` | Optional comma-separated expected strings in the native executable |
| `execute` | **false:** build IPA and offline Appium package (no AWS). **true:** also schedule a billable physical iPhone test |
| `collect_run_arn` | Retrieve evidence from an existing Device Farm run (use with `execute=false`; no SDK inputs needed) |

A new experiment should normally use an **immutable `test_ref` commit** for
reproducibility. Only the Java source and Appium test Python file are copied
from the selected ref. The workflow, SDK verifier, deployment helper, Device
Farm launcher and test specification are always loaded from **main**.

### Examples (as of November 12, 2026)

**Working control — 7.2.2, August 24**

- `sdk_run_id: 32682363876`
- `sdk_source_sha: 452213ae7fdf483f443aa73153f0bdce6dcecf6f`
- `sdk_version: 7.2.2`
- `sdk_artifact_id: 9504578512`
- `test_ref: test/sqlite-plaintext-7.3.0`
- `execute: false` for a free package build

**Instrumented iOS 7.3.0 surface-latch experiment (PR #542)**

- `sdk_run_id: 43326093367`
- `sdk_source_sha: 791e8c465ccfb8c9e0d34588a5467ea9d033c762`
- `sdk_version: 7.3.0`
- `test_ref: test/sqlite-plaintext-7.3.0`
- `native_markers: screen-change-noop-release,screen-update-guard,screen-change-apply,vm-screen-update`
- `execute: false` first; select `true` only after checking IPA provenance

### Reproducibility and safety

The workflow validates the upstream `TotalCross/totalcross` run's source SHA
and successful **Build iOS** and **Package TotalCross** jobs, then resolves
exactly one non-expired SDK artifact and compares its downloaded SHA-256 with
the GitHub-reported digest. It does not require unrelated desktop smoke tests
to finish, but refuses an unsuccessful iOS/package build.

The SDK and application packaging run entirely on Ubuntu, without AWS
credentials. The build artifact contains the IPA, offline Appium test ZIP,
`sdk-run.json`, `sdk-artifact.json`, `provenance.json`,
`test-source.json`, `ios-graphics-ipa.json` and compilation logs.
The physical job checks out **main**, not unreviewed test scripts for AWS
administration, downloads the validated build artifact, validates the iPhone
pool and schedules at most the configured Device Farm run.

No push, scheduled job or pull request launches Device Farm. The physical
job is gated on a manual dispatch from `main` with `execute=true`.
A recovery operation uses `collect_run_arn` instead of creating an upload
or scheduling a new device.

The default `test_ref` continues to point to the existing graphics smoke
test, while future feature branches may supply other assertions. The reports
for prior experiments remain in `reports/` and the old workflow runs are
not modified.

### Workflow migrations

The generic workflow supersedes these experiment-specific YAMLs previously
maintained on the `test/sqlite-plaintext-7.3.0` branch:

- `ios-graphics-730-experiment.yml`
- `ios-graphics-730-native-diag.yml`
- `ios-graphics-730-surface-latch.yml`
- historical `ios-graphics-devicefarm.yml` (replaced on main)

The **SQLite** workflow `sqlite-plaintext-7.3.0.yml` is deliberately
not removed or modified.

If a bug is found in the runner, modify the single generic workflow and
its helpers in a normal PR. For a new experiment, change only the SDK run,
source SHA, test ref, and (if useful) native markers.
