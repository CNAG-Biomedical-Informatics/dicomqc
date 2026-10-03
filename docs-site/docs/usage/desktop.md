---
title: Desktop app
---

# Desktop app

The desktop app provides file and folder selection, dataset comparison,
searchable run history, findings, and report previews.
It uses the same Python audit engine as the `dicomqc` command. Desktop builds
are currently for testing; installers have not been published.

![dicomqc desktop workspace showing synthetic run history and an HTML report preview.](/img/desktop-workspace.png)

## Run an audit

1. Open **New audit** and choose **Scan a dataset** or **Compare datasets**.
2. Select DICOM files or folders. A comparison also needs a
   [pairing manifest](compare.md#prepare-a-pairing-manifest).
3. Under **Advanced checks and outputs**, optionally select a project policy.
   Scans also support UID checks, scanner inventory, and MultiQC custom content.
4. Review **Output folder**, or select **Choose output folder** to change it.
   Choose an empty folder or an existing dicomqc workspace, separate from inputs.
   Each audit writes to its own subfolder; your input selections are retained.
5. Select **Run audit**. Select a run in the sidebar, then use **Findings** to
   review checks or **Reports** to inspect its output files.

The sidebar keeps selected sources and searchable run history visible while
you switch views. **Setup** returns to the audit inputs; the bottom task strip
shows active work.

One audit runs at a time; additional audits wait in a queue. Cancellation stops
the worker without publishing a complete report. An audit that completes with
errors still has reports to review: findings are different from a worker failure.

**Explore with synthetic data** provides scan, comparison, policy, UID, and scanner
inventory examples. These examples need no patient data and contain deliberate
findings. Selecting an example generates synthetic DICOM files in its run folder
and starts the audit immediately; it does not preload the Setup input fields.

## Reports and workspace

Each run has its own folder in the workspace. **Reports** provides a file list,
HTML previews, and **Save copy**. Exports require a new filename and never replace
an existing file. HTML previews disable scripts; the saved standalone report
retains its interactive controls.

**Settings** controls appearance and also provides the output-folder selector.
The app remembers this folder between sessions. Finish or cancel active audits
before switching. Existing runs stay in their original output folder; selecting
that folder again restores its history.
**Delete run** removes a finished run and its reports after native confirmation;
it leaves the original inputs in place.

The app inspects metadata only. It does not alter DICOM files, inspect pixels,
or perform pseudonymization. See [Remediation](remediation.mdx) for the surrounding
workflow. Review report contents before sharing them.

## Local service

The native shell starts an authenticated FastAPI service on the local machine.
Requests and responses stay on loopback; no remote server is required. Credentials
remain in the native shell. The service calls the Python audit functions directly
and runs each audit in a separate worker process.

Closing the app stops its service and workers. Completed run history is stored
locally in SQLite. A run interrupted by an unexpected shutdown is marked as
interrupted when its workspace is reopened.

## Build from source

Developers need Python, Node.js, Rust, and the operating system's
[Tauri prerequisites](https://v2.tauri.app/start/prerequisites/). From the repository
root, create and activate a virtual environment, then run:

```bash
python -m pip install -e ".[api]"
npm --prefix app ci
npm --prefix app run desktop
```

The development launcher uses `.venv/bin/python` on Unix or
`.venv/Scripts/python.exe` on Windows. Set `DICOMQC_DESKTOP_PYTHON` to use a different
interpreter. The frontend is built and embedded in the native app.

Packaged builds bundle Python and dependencies. Their intended users do not need
a separate Python installation. The repository's **Build desktop test artifacts**
workflow is manually dispatched and targets macOS Intel and Apple Silicon,
Windows x64, and Linux x64 and ARM64. Each platform still needs installer and
workflow testing before a public desktop release.
