# dicomqc development — 2026-10-03

## Current direction

### Desktop update check - 2026-10-05

- Added Help > Check for Updates, following Convert-Pheno's on-demand native
  dialog pattern. Queries GitHub's latest published stable release rather than
  tags, so a tag with draft installers is not announced as available.
- Uses a separate HTTPS client with a 15-second timeout and semantic version
  comparison. No audit data or local API credentials are sent. Open Downloads
  opens the fixed GitHub releases page; installation remains manual.
- Existing 0.2.0 installer candidates predate this change and must be rebuilt
  before release to include the new menu item.
- macOS now places About, Settings, and Quit under the dicomqc application
  menu, with Services and Hide actions. Quit still uses the existing unsaved
  project/active-audit confirmation. Windows and Linux retain their menu layout.
- Fixed the development logo by allowing its shared image through Vite's file
  restrictions. The user confirmed the logo displays after relaunch.

### Installer candidate verified - 2026-10-04

- Unified installer run `37217534293` passed all five targets from commit
  `0b915258ebda595ee38e4f2f6daaaec4aa92f09b`: macOS Intel/Apple Silicon,
  Windows x64, Linux x64/ARM64.
  https://github.com/CNAG-Biomedical-Informatics/dicomqc/actions/runs/37217534293
- Python results: Windows 630 passed/9 skipped, 97.62% coverage; other targets
  631 passed/8 skipped, 97.96% coverage. Frontend, frozen-engine, native-bridge,
  installer inspection and platform startup checks also passed.
- Windows CI installs and launches the actual package and checks for a window.
  macOS checks packaged startup. Linux checks the native GUI under Xvfb and
  extracted/packaged AppImage startup. These are not full manual UI reviews.
- Downloaded all five installers and verified their SHA-256 checksums in ignored
  `build/desktop-0.2.0-0b91525/`, with one subdirectory per platform.
  Workflow installer artifacts are retained for 30 days.
- Fixes uncovered by cross-platform testing include Windows atomic progress-file
  replacement conflicts, workspace path aliases, read-only SQLite URI encoding,
  run ownership checks after reopening, and comparison reference/count handling.
  macOS workspace identities use canonical paths. Platform-specific test fixtures
  were corrected; the native 10,000-file example has a bounded 120-second timeout.
- Keep one authoritative installer workflow. Platform-selected diagnostic runs
  are useful during development; a complete same-revision matrix is required
  before release. C-P and DGW received local handoff notes about this approach;
  their workflows were not changed or dispatched.
- Next gate: user installation tests on at least two real machines. Check example
  privacy/comparison audits, report previews/export, project save/reopen after
  quitting, run rename/delete, cancellation and clean exit. These installers do
  not establish performance or audit validity on the forthcoming real DICOM data.
- Windows builds are unsigned; macOS builds are not Apple-notarized. Successful
  CI does not remove platform trust prompts or replace clean-machine testing.
- At the user's request, prepared an unpublished draft in Convert-Pheno's release
  style with all five installers and five checksums:
  https://github.com/CNAG-Biomedical-Informatics/dicomqc/releases/tag/untagged-c48f612f84200a0abee5
- The draft has intended tag name `v0.2.0`, but no corresponding Git tag exists;
  verified remote tags still contain only `v0.1.0`. No new PyPI workflow ran.
  Draft target and installer source are `0b915258ebda595ee38e4f2f6daaaec4aa92f09b`.
  Version 0.2.0 remains unreleased. After manual approval, finalize release
  metadata and create/push the annotated tag before publishing the draft. Rebuild
  and replace draft assets if the tagged source changes. Do not publish the draft
  early and let GitHub create a tag automatically.
- Untracked root files `README` and `project` were left untouched.

### Portable project sessions

The user explicitly wants a DAW-style session: one `.dicomqc` file containing
multiple runs (examples and external datasets together), settings, report artifacts,
findings, logs, policy copies and the selected pairing manifest. Original DICOM
files remain external. There is no user-selected database/output folder in the
desktop UI anymore. Individual report export remains **Save copy**.

Project files are now version-2 ZIP containers, not the earlier JSON references.
The Python API has privileged save/open routes, called only by the native shell;
the renderer cannot invoke these filesystem operations through `api_request`.
Opening extracts into a private app-managed session and reconstructs its SQLite
database with fresh directory identities. Saving is atomic and requires no active
audits. Save As creates an independent snapshot. Run changes contribute to the
unsaved indicator. Reports and policy/manifest content can be sensitive; packages
are not anonymized data exports.

Existing working folders were not deleted. Earlier JSON `.dicomqc` documents are
not portable archives; save the existing working session using Save As to create
the new format. Internal recovery storage remains between launches; explicit Save
updates the portable file. Automatic cleanup of old recovery sessions is not yet
implemented, so do not describe the internal storage as automatically reclaimed.

Convert-Pheno was checked: it uses a JSON `.cpheno` plus `.cpheno.data` companion,
and references external result history. dicomqc intentionally goes further by
including reports in one movable project file, as confirmed by the user.

Verification includes synthetic fixture runs, moving the archive, removing the
original workspace and DICOM directory, reopening all findings/artifacts, retaining
policy copies, and Rust-to-Python API integration. Focused Playwright desktop and
narrow-window checks cover Advanced setup and removal of output-folder controls.


The user confirmed that Python remains the authoritative audit engine and CLI.
The native Tauri shell talks to the local authenticated FastAPI service. It does
not run or parse the CLI for desktop operations. The sibling Rust port remains
an earlier experiment; do not resume that rewrite.

The user's latest priority is **UI and desktop workflow**, before packaging or
release. Use Convert-Pheno and digital-genome-workstation as design references:
persistent navigation, sources and runs, a working toolbar, distinct setup,
findings and report views, and a desktop status/task area. Do not publish anything.

The user explicitly declined resumable jobs and a preflight/dry-run summary.
Do not add either without a new request. Performance measurements belong in the
existing run log.

Audit Setup now presents two modes: Privacy audit (default) and Dataset
comparison. Policies and UID/scanner options extend audits; synthetic scenarios
are separate example runs. Comparison hides scan-only controls. The next-audit
summary names the selected policy; completed runs retain its ID and digest in
the Log and exported job record. Generated policy YAML and pairing CSV are
grouped as Example inputs within the selected run's Reports view.

## Testing guidance

The user explicitly requested proportionate testing, not the full suite after
every change. Avoid repeating broad checks for small About/navigation edits.

- Text or styling: targeted build or visual check as appropriate.
- UI behavior: relevant component tests; browser/native checks where needed.
- Audit logic or API changes: broader tests covering the affected behavior.
- Before commits or releases: full validation as appropriate to the accumulated
  changes; retain the greater-than-95% Python coverage requirement.
- Notes-only edits: no tests needed.

## Current implementation

- `app/src-tauri/` now contains the native Rust shell, authenticated API bridge,
  service lifecycle, native menus/dialogs, `.dicomqc` project lifecycle, isolated
  report previews, exports that never overwrite existing files, and run deletion.
- Python API reliability work covers readiness, stdin-parent supervision, worker
  lifecycle, queue resilience, input/workspace identity checks, progress, and
  deletion of finished runs. Real workers call the shared Python engine directly.
- Frontend redesigned as a desktop workspace: persistent Sources/Runs sidebar,
  searchable history, Setup/Findings/Reports tabs, split report preview, native
  menu events and enabled states, light/dark/system themes, and task/status bars.
  Component/bridge tests: 45 passed. Playwright checks three widths (390, 760,
  1440) in all three themes, including long paths and multiline history rows.
- Project policies have a first-class Policy workspace based on Convert-Pheno's
  CodeMirror interaction: YAML highlighting, line numbers, search, undo, strict
  Python-engine validation, and line diagnostics. **Save as and use** validates
  and creates a private, no-clobber YAML copy outside inputs and outputs; it
  never overwrites the selected source. Unsaved edits block audits and project
  saving. The project continues to reference the durable external YAML file.
- The job log derives a compact Performance section from existing provenance:
  threads, files read, and average end-to-end files/second. No extra worker
  telemetry or DICOM values are captured.
- Project files and output folders are deliberately separate. A `.dicomqc` JSON
  file stores audit settings and references to external inputs and the selected
  output folder. The output folder owns SQLite run history, immutable run
  directories, and reports. Save As writes a new project document without moving
  outputs. Open requires a trust confirmation and reconnects to the recorded output.
  Treat project files as private because paths can disclose study or site names.
- The visible **Load example data** control uses the same fixture-backed scenarios
  as API, CLI, and integration tests; there is no UI-only data. It is filtered by
  workflow: scan shows Privacy scan, Project policy, UID integrity, Scanner
  inventory, and Large cohort; compare shows only Dataset comparison.
- Runs have immutable IDs and mutable, searchable display names. Rename updates
  only persisted job metadata; it never changes run directories or report paths.
- Setup changes are tracked as dirty. The title marks them with `*`; New/Open and
  Quit/Exit require confirmation before discarding them. Active audits continue to
  block project changes and require confirmation before application exit.
- `native-smoke` is an explicit Linux-only verification feature, excluded from
  ordinary builds. `app/tests/native-smoke.js` drives real UI/API workflows and
  captures WebKit screenshots into the chosen `DICOMQC_SMOKE_DIR`.
- Native Linux ARM64 smoke passes all five synthetic demos, HTML preview,
  native menu event navigation, history search, light/dark themes and resizing
  to 760 px. Current evidence is `build/native-workspace-checked/`; earlier
  verification folders capture superseded layouts. Native WebKit needed explicit
  nonshrinking flex history rows to prevent overlapping text after resizing.
- Desktop engine packaging scripts and a manually dispatched five-platform
  workflow exist, but packaging work is now deferred. A local installer attempt
  stopped at a Tauri minor-version mismatch: Rust is locked to 2.11.6 for the
  installed Rust 1.86 compiler; npm API resolved to 2.12.1. Align these versions
  before installer builds. Do not confuse this with a native dev build failure.
- Python wheel/sdist build, Twine checks, and installed-wheel synthetic CLI demos
  passed. Desktop files and these session notes are excluded from the CLI sdist.
- Latest complete Python suite including run deletion: 523 passed, 2 skipped,
  99.14% coverage. Backend source is frozen. The coverage gate is 95.01%.
- Native API bridge integration passes all five demos, exports, restart, deletion,
  input transfer and an audit writing into the new output folder. Deletion uses
  the native credential after confirmation; the renderer proxy rejects DELETE.
  Rust tests: 4 passed including the real-engine integration test.
- Built-in examples generate synthetic DICOM data and immediately run an audit.
  They do not yet preload Setup inputs for an editable, pre-run demo workflow.

## Workspace and tools

All current source is in this permanent repository. Do not use `/tmp` as a source
checkout. The previous Rust port's temporary checkout is missing; its deletion
mechanism was not established. `/tmp` was inspected and no dicomqc leftovers
existed before this session. Remove disposable task-generated temp files after
verification, as the user requested.

This host is Linux ARM64, Python 3.12.3, Rust 1.86, WebKitGTK 4.1 available.
The repository `.venv` has been updated with API, test and desktop-build extras;
it is usable on this host. `app/node_modules` and the npm lockfile exist. Source
edits have been approved for a development commit. The separate untracked
`README` user-notes file must remain outside that commit. No push or release is
authorized by this commit request. The final pre-commit Python suite passed
523 tests with 2 skips and 99.14% coverage (`build/coverage-commit.xml`).

Read the history below for feature details and the earlier authorized Git history
correction. Statements below about a missing Tauri shell or unusable `.venv` are
historical and superseded by the current notes above.

---

# Historical handoff — 2026-10-02

## Resume here

The user asked to implement a native desktop application following Convert-Pheno,
then paused to move to another machine. **Implementation is incomplete.**
The API foundation and frontend source exist; there is no native Tauri shell yet.
Do not describe the desktop app, installers, or coordinated release as finished.

Read this file, inspect `git status`, and preserve all existing changes before
continuing. At the user's subsequent request, implementation, documentation, tests,
screenshots, and these notes are being staged for handoff; none is committed yet.
Confirm the index with `git diff --cached --stat`. Before staging, many important
files were untracked, including source, tests, and screenshots.
The untracked file named `README` (without `.md`) contains user notes: do not edit,
delete, or accidentally include it in a commit or release.

## Moving to another machine

- These notes explain the work; they are not an export of the work.
- If the same SSD/repository directory is used, everything under the repository
  is already there. Recreate development environments on the new machine.
- For a different checkout, transfer the complete working directory including
  untracked files and `.git`, or make an explicitly approved WIP branch/commit
  and push it first. A normal `git diff` does not include untracked files.
- Do not copy `.venv`, `node_modules`, compiled native outputs, or Python caches
  as usable environments; rebuild them. `/tmp` paths below are machine-local.
- The newest GitHub main does not contain the uncommitted feature/API/UI work.

Repository on this machine:
`/media/mrueda/2TBS/CNAG/Project_DICOMqc/dicomqc`

Reference Convert-Pheno repository:
`/media/mrueda/2TBS/CNAG/Project_ConvertPheno/convert-pheno`

## Agreed architecture and release decisions

1. Preserve `pip install dicomqc` as an independent CLI installation.
2. CLI and local API use the same Python audit engine. No audit rules in Rust or
   React; no bridge that parses CLI output.
3. Tauri 2 + React + TypeScript desktop, with embedded Vite-built assets. Native
   development only, not a browser application or frontend development server.
4. Desktop starts a bundled, authenticated local Python API. A standalone API
   is independently usable by local scripts through optional Python dependencies.
5. The first API is **local only**: no remote hosting, uploads, cloud service,
   or multi-user server deployment.
6. Release the CLI to PyPI and desktop installers **together as v0.2.0** after
   validation. The user explicitly selected “Release together.”
7. Target the Convert-Pheno platform matrix: macOS Intel and Apple Silicon DMGs,
   Windows x86-64 installer, Linux x86-64 and ARM64 AppImages.
8. Bundle Python and dependencies so desktop users need no separate Python or
   Node installation. Proposed packaging: PyInstaller directory bundle in Tauri.
9. First release: one active audit and a FIFO queue, isolated Python worker per
   job, SQLite run history, progress, cancellation, and interrupted-run recovery.
   No Redis, RabbitMQ, Celery, or RQ. Concurrency is currently hardcoded to one;
   user was told this and did not request configurable concurrency yet.
10. No plugin system. User explicitly discarded the plugin roadmap.
11. No publication, new release tag, or installer upload has been authorized.

Desktop workflows: Scan, Compare, all existing synthetic demos; project policies,
UID checks, scanner inventory, reports. Respect current CLI capability differences:
UID checks, vendor inventory, and MultiQC are scan-only; policy also works in Compare.

Planned layout: New audit / Runs / Settings. Large readable controls, advanced
options folded, native dialogs/menus, theme preferences, grouped findings, export
and isolated report preview. No raw DICOM/pixel viewer or portable project format.

## GitHub corrections already completed

At explicit user request:

- Deleted `v0.2.0` locally and remotely. Keep `v0.1.0` unchanged.
- Queried GitHub: no GitHub release entry existed for `v0.2.0`.
- Reworded the old “Release v0.2.0…” commit to
  `Prepare v0.2.0: dataset comparisons and offline HTML reports`.
- Recreated its descendant with identical file trees and pushed main using an
  explicit force-with-lease. Working-tree and staged diffs were verified unchanged.
- Current main: `422607617bfb67f076da5d33c7ea1f9208acd076`.
- Reworded preparation commit: `9e51372`.
- Old main: `d6dee0d7ba2ea80ca0ccb10bb40bf097f6a01959`.
- Recovery reference: `refs/backup/pre-release-message-rewrite` points at old main.
  It is local only; keep it if copying `.git`.
- GitHub About description is now: `Audit DICOM metadata for privacy risks.`

An older clone may have divergent history after this authorized rewrite. Do not
force-push its old main back, or discard uncommitted work to synchronize it.

The prior tag-triggered publication failed before publishing: checkout peeled the
annotated tag, and validation expected a tag object. The release workflow still
needs to restore/verify the remote annotated tag object before checking it.
Convert-Pheno's installer workflow already demonstrates this fix. Do not recreate
the release tag until the coordinated release is ready.

## Existing feature work to preserve

All of this predates desktop implementation and is still uncommitted:

- YAML project policies: `rules/policy.py`, scan/compare `--policy`, demo,
  strict bounded YAML validation, redacted configured/observed values.
- Scanner/software and dataset-local private creator inventory:
  `vendor.py`, `scan --vendor-summary`, demo. Raw labels are explicitly opt-in;
  private payloads remain excluded.
- UID integrity: `rules/uid.py`, `scan --uid-checks`, `demo --uid-demo`.
  Checks top-level study/series/instance UID syntax, role reuse, series/study
  conflicts, and instance-context conflicts. Missing fields are coverage gaps,
  not IOD-required-attribute errors. No global uniqueness or full compliance claim.
- UID-enabled scan JSON omits legacy raw record-context fields. HTML/MultiQC
  include value-free UID coverage. The UID demo has 7 errors in 4 groups before
  correction and no findings afterward, using four synthetic files per side.
- Shared HTML/MultiQC vocabulary and folded supporting panels.
- Documentation restructuring, real report screenshots, compact architecture
  SVGs, and concise changelog under `0.2.0 — Unreleased`.

Documentation preferences:

- Preserve the beloved `dicomqc-audit.svg` home/README illustration.
- No Reports tab/page: it was removed deliberately. Reports and screenshots
  belong beside the relevant data walkthrough.
- JSON examples are collapsed code; CSV examples are collapsed actual tables.
- Do not add “Implemented” labels or “included in v0.2.0” notices.
- Keep text direct, reports uncluttered, and screenshots real rendered reports.

## Desktop/API implementation so far

### Shared execution and progress

- `execution.py`: moved `_load_requested_policy` and `_validate_multiqc_output`
  out of CLI; CLI imports them. Remaining CLI preflight checks have **not** all
  been extracted/shared yet.
- `progress.py`: optional value-free progress events.
- `scan_paths(..., progress=None)` and `compare_datasets(..., progress=None)`
  emit discovery, reading, and relationship phases.
- Current reading count is emitted before processing a file/pair. Review this:
  the displayed `completed` count should describe completed work accurately.
- `pyproject.toml` adds optional extras `api`, `api-test`, and `desktop-build`.
  Base runtime dependencies remain pydicom and PyYAML.
- CLI routes `dicomqc serve` lazily to the optional API launcher.

### Local API files (`src/dicomqc/api/`)

- `app.py`: FastAPI, strict request models, versioned `/api/v1` endpoints.
  Includes health, capabilities, authenticated OpenAPI, privileged local-input
  registration, submit/list/status/cancel jobs, paginated findings, indexed
  report downloads, privileged shutdown.
- `server.py`: loopback-only Uvicorn launch, `--state-dir`, `--port`, token-file
  options; also reads `DICOMQC_API_TOKEN` and `DICOMQC_LOCAL_TOKEN`. Distinct
  tokens must each contain at least 32 characters. Private readiness-file support
  is intended for the future Rust launcher.
- `storage.py`: private atomic JSON writes and selected-input identity checks.
- `jobs.py`: SQLite state, workspace ownership lock, in-memory opaque input
  handles, single active worker, FIFO scheduling, cancellation, interrupted-run
  recovery, artifact lookup restricted to the run's artifact list.
- `worker.py`: directly invokes core scans/comparisons and existing demos;
  writes reports to a pending directory then renames it; publishes completion
  separately. Live review JSON omits `records`; downloadable report JSON retains
  documented CLI semantics.
- `runner.py`: private loopback watchdog handshake; worker exits if its
  supervisor connection disappears. No external queue service.

Important distinction: a completed audit with errors has job status `completed`
and audit exit code 2. A worker failure has job status `failed`, with no published
artifact list. Never conflate findings with process failure.

### Frontend source (`app/`)

Added `package.json`, `tsconfig.json`, `vite.config.ts`, `index.html`, and:

- `src/desktop.ts`: typed Rust invocation boundary, job/result types, audit labels.
- `src/main.tsx`: initial Scan/Compare forms, native-selection calls, folded
  options, all five synthetic examples, job polling/history/cancellation,
  paginated grouped findings, report preview/export, workspace and theme settings.
- `src/style.css`: initial desktop layout and light/dark/system styling.

**Not installed, compiled, tested, or visually inspected yet.** There is no
`app/package-lock.json`, no `app/src-tauri`, no Rust code, no native configuration,
no native icons, no desktop screenshots, and no packaging workflow yet.

Frontend currently expects these Rust commands, all still to implement:
`api_request`, `select_input`, `workspace`, `choose_workspace`, `read_report`,
`save_report`, and `reveal_run`.

The intended Rust layer retains both API tokens; renderer uses restricted Rust
commands rather than receiving credentials. Native input dialogs register paths
with the privileged API endpoint. Workspace switching must reject active jobs,
stop the old service, start the new one, persist settings, and invalidate handles.
Report preview is a sandboxed iframe without script/native permissions; exported
HTML retains its existing standalone controls.

## Tests actually run

Before desktop changes:

- Full Python suite: **407 passed, 1 skipped**, coverage **99.86%**.
- Skip: optional DCMTK interoperability test.
- Docs production build and documentation browser checks passed, including 11
  real report snapshots beside walkthroughs at desktop/mobile widths.
- UID HTML browser tests passed: groups, folded details, coverage, filters,
  mobile, print, no-JS, redaction, offline behavior, and MultiQC alignment.
- Wheel + sdist built and passed Twine metadata checks. A clean installed-wheel
  environment passed scan/comparison/policy/vendor/UID demos.

After shared validation/progress/API changes:

- Existing suite before adding API tests: **407 passed, 1 skipped**, `--no-cov`.
- New `tests/test_api.py`: **19 passed**, `--no-cov`, with optional dependencies.
  Covers authentication/host/origin/privileged routes, real subprocess UID scan
  parity and read-only behavior, comparisons, policies/MultiQC, five demos,
  invalid requests, changed inputs, queued cancellation, workspace locking,
  restart recovery, generic worker failure, and atomic storage.
- These API tests required execution outside this tool's network sandbox:
  inside it, Starlette's asynchronous test client hung and loopback connections
  were restricted. The two hung test sessions were stopped with Ctrl-C.
- Warning: current Starlette TestClient says httpx is deprecated in favor of
  httpx2. Resolve/pin compatible optional test dependencies before release.
- No combined full-suite coverage run since adding the API files/tests.
- No native or frontend tests/build have been run.
- Last `git diff --check` passed.

## Development environments and machine limitations

This host is Linux Mint 20.3 (Ubuntu focal baseline), Node 20.20.2, GTK 3.24.20.
Rust/cargo were not on PATH or in `/home/mrueda/.cargo/bin`. WebKitGTK 4.1
development files were unavailable through pkg-config.

An approved attempt at `sudo -n apt-get ...` stopped immediately because sudo
requires a password. No host system packages were installed. Never request or
store the user's password.

Docker was discussed as a **build-only fallback** for a newer Linux baseline.
Only `docker image ls` was executed. No Docker image/container/Dockerfile was
created. The user asked why Docker was needed; it is not an application runtime
requirement. Prefer native setup if the next machine supports Tauri prerequisites.

Working temporary Python environment on this machine:

```bash
/tmp/dicomqc-test-env/bin/python -m pytest
/tmp/dicomqc-test-env/bin/python -m pytest tests/test_api.py --no-cov
PYTHONPATH=src /tmp/dicomqc-test-env/bin/python -m dicomqc.cli --help
```

The checked-in-directory `.venv` is stale from another machine. Do not reuse it.
System Python here is 3.8; the temporary test environment uses Python 3.12.15.
For a fresh machine, create a new Python >=3.10 environment (prefer 3.12) and use:

```bash
python -m pip install -e '.[test,release,api,api-test,desktop-build]'
python -m pytest
```

Optional API tools installed only into `/tmp/dicomqc-test-env`:
FastAPI 0.142.2, Uvicorn 0.54.0, httpx 0.28.1, PyInstaller 6.22.3,
Starlette 1.7.0, anyio 4.15.1. Native/frontend dependencies were not installed.

Existing report preview base: `/tmp/dicomqc-workspace-design`.
Contains scan/comparison/policy/vendor/UID examples. Always use a subdirectory
for a new demo; do not force-replace the root and delete other examples.
Documentation screenshots are already copied into `docs-site/static/img` and
will transfer with the working tree. The temporary previews will not.

Playwright/browser assets: `/tmp/dicomqc-playwright`.
Docs preview previously ran at `http://127.0.0.1:3017/dicomqc/`.
Latest pre-API distribution smoke environment:
`/tmp/dicomqc-uid-package-UnfES6` (not a build of the new API).

## Next steps and review priorities

1. Inspect the new API code before extending it. Harden path ownership and
   lifecycle behavior: existing workspace database/lock symlinks, input changes
   after queueing, output/input overlap, worker handshake failure, cancellation
   during startup/report publication, supervisor crash, and real running-job
   cancellation. Tests currently cover only some of these paths.
2. Complete shared execution validation. Preserve CLI behavior while applying
   consistent manifest/policy/report protections to API jobs.
3. Review API error redaction (including validation errors), token comparisons,
   bounded request/result handling, and startup readiness. `ready-file` currently
   records the bound port before lifespan startup; native code must still poll
   authenticated health and check engine/API versions.
4. Ensure large-result handling is genuinely bounded. HTTP findings are paginated,
   but current `review()` loads the whole JSON; this is not yet scalable streaming.
5. Add run deletion with ownership checks and confirmation, secure native report
   export/reveal, graceful close prompts, settings persistence, and robust
   service cleanup. These agreed behaviors are not fully implemented.
6. Implement native Tauri shell and launcher, then install frontend dependencies,
   generate its lockfile, run typecheck/build/component tests, and prove a real
   synthetic scan inside the native app. Do not substitute a browser-only preview.
7. Fix style/code issues surfaced by first build; the UI was written but not
   compiled or visually verified. Capture real native screenshots only afterward.
8. Build the frozen Python engine and test it away from the checkout, including
   watchdog subprocess startup. Then implement five-target installer CI and
   installed-app smoke tests. No release publication without authorization.
9. Keep API/desktop dependencies optional and GUI/runtime artifacts out of wheel
   and sdist. Ensure internal session notes/user notes are excluded as needed.
10. Run the full test suite with coverage after installing API test dependencies.
    Update CI to exercise optional API tests without making them base CLI runtime
    dependencies. Preserve the 95% coverage gate.
11. Add API/Desktop docs and real screenshots beside synthetic workflows; concise
    changelog update. Current docs do not yet describe the new API/Desktop work.
12. Prepare both CLI and desktop artifacts from the same candidate revision;
    validate all target platforms before the coordinated v0.2.0 release.

## Convert-Pheno reference files

Read its `AGENTS.md` before working there; this task only needs reference reads.
Useful references:

- `SESSION_NOTES.md`: Desktop Direction and later release/platform lessons.
- `app/src-tauri/src/main.rs`: managed local engine, two tokens, native dialogs,
  menus, shutdown, workspace/resource settings, platform-specific startup.
- `api/perl/README.md`, `api/perl/main.pl`, `lib/Convert/Pheno/HTTP/Jobs.pm`:
  shared API and job execution patterns.
- `scripts/stage-desktop-engine.pl`, `scripts/test-desktop-engine.pl`:
  relocatable runtime staging and packaged-engine smoke tests.
- `.github/workflows/desktop-installers.yml`: five-target builds, real installed
  startup checks, artifact checksums, annotated-tag validation.
- `docs-site/docs/graphical-interface.md`: workflow documentation and actual
  desktop screenshots.

Use its architecture as a reference, not a wholesale copy of Perl infrastructure
or unrelated features. Review licensing before copying code/assets.

## 2026-10-03: single-audit parallel metadata processing

- The queue still permits exactly one running audit. Additional submissions are
  queued FIFO; the Desktop primary action says **Queue audit** while work exists.
- Scan and comparison now accept `-t` / `--threads` (from `1` through the
  logical processors available to the process; default `min(4, available)`). The
  same setting is available under **Settings > Processing** and is saved in
  `.dicomqc` projects. Version-1 project files without the field load as four,
  capped to available hardware.
- Production scan and comparison work is split into bounded batches (256 files
  or 128 manifest pairs) and dispatched to worker processes with at most twice
  the configured worker count in flight. Results merge in deterministic input
  order. Custom injected backends retain the thread mapper used by tests.
  If the entire audit fits within the initial bounded lookahead, it runs serially
  to avoid process startup and IPC overhead.
  Dataset-wide UID/mapping aggregation remains serial. Directory traversal sorts
  one directory at a time instead of retaining a globally sorted file tree.
- During iterative UI work, run focused tests and compile checks. Run the broad
  Python coverage suite and frontend/native suites after core or release-facing
  changes; do not rerun every suite for each small visual edit.
- A sixth **Large cohort** scenario generates metadata-only DICOM files
  inside its run workspace. A Desktop slider spans 1,000 to 100,000 files in
  1,000-file increments and defaults to 10,000. The first 150 files contain an
  invented direct-PHI marker and the first 50 also produce two pseudonym-format
  warnings, yielding 250 deterministic findings for pagination and report review.
  It is a stress/regression example, not a committed binary artifact or a
  performance claim. On this six-logical-CPU host, the same cached 50,000-file
  scan took 12.04 seconds with one worker and 5.08 seconds with four process
  workers after batching. The earlier per-file thread implementation took 40.03
  seconds with four workers and was removed.
- Runs have a dedicated **Log** tab with a durable job record: sanitized input-role
  counts, options, worker count, synthetic cohort size when applicable, timing,
  outcome, and a bounded timeline of predefined events. **Download job record**
  writes the same provenance as JSON through a native save dialog. Records never
  include DICOM values, source paths, input handles, parser diagnostics, or worker
  stdout/stderr. Existing runs recover parameters from their private request when
  available.
- Embedded JSON, CSV, and HTML previews are capped at 8 MiB to protect the desktop
  webview on large cohorts. The report panel explains the limit and keeps **Save
  copy** available for opening the complete artifact externally.
- Active-run feedback uses determinate progress for known totals (including
  large-example generation and reading), a spinner for genuinely indeterminate
  phases, and phase/count/elapsed-time text. Queued jobs do not animate.

## Documentation and citation follow-up (2026-10-03)

- Documentation navigation separates Desktop App and CLI. Audit modes explains
  Privacy audit versus Dataset comparison before optional checks and outputs.
- Desktop worked examples use fixture-backed Playwright captures generated by
  `npm --prefix docs-site run screenshots:desktop`; the native bridge is mocked,
  while report contents come from the real Python demo generators.
- Later: add root `CITATION.cff` for version 0.2.0, using the GitHub About simple
  description as the software title. Confirm release metadata when doing this.
  The manuscript working title is now "dicomqc: Auditing privacy risks in
  de-identified DICOM metadata"; CITATION.cff exists for software version 0.2.0.
- Docs prose should be plain and specific: name the controls, inputs, checks,
  and expected results. Avoid promotional language and unnecessary rewrites.

## Release preparation (2026-10-03)

- The user approved replacing the former tag-only distribution policy with
  tag-triggered draft GitHub Releases for Desktop installers. PyPI still runs
  separately from the same annotated stable tag. Manual installer builds remain
  artifact-only, with a platform selector. No tag or Release was created locally.
- Build-desktop now inspects installed/extracted Python engines, collects named
  installers with SHA-256 files, and refuses to replace published Release assets.
  Actual five-platform execution and manual GUI checks remain release gates.
- Release is planned for tomorrow; do not date the changelog or tag yet.
- Next: a separate private ../dicomqc-videos repository following convert-pheno,
  COHORTome, and digital-genome-workstation video production conventions.
