---
title: Install
hide_table_of_contents: true
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

# Install

The desktop app is the recommended **dicomqc** interface. The CLI supports
automation and scripted workflows; both use the same
Python audit engine.

<Tabs defaultValue="desktop" queryString="interface">
<TabItem value="desktop" label="Desktop App">

## Desktop App

Download the Desktop package for your operating system from
[GitHub Releases](https://github.com/CNAG-Biomedical-Informatics/dicomqc/releases).
You do not need to build the app from source.

### Choose a download

Expand **Assets** on the release page. Download the package for your
computer, not the automatically generated **Source code** archives.

| Computer | Package for 0.2.0 |
| --- | --- |
| Mac, Apple Silicon (M-series) | `dicomqc-0.2.0-macos-arm64.dmg` |
| Mac, Intel | `dicomqc-0.2.0-macos-x64.dmg` |
| Windows, Intel/AMD 64-bit | `dicomqc-0.2.0-windows-x64-setup.exe` |
| Linux, Intel/AMD 64-bit | `dicomqc-0.2.0-linux-x64.AppImage` |
| Linux, ARM64 | `dicomqc-0.2.0-linux-arm64.AppImage` |

Each package has a matching `.sha256` checksum file. **Desktop bundles its Python
engine**; you do not need to install Python, Node.js, or Rust separately.
The Windows package is x64; there is no native Windows ARM64 package.

<Tabs defaultValue="macos">
<TabItem value="macos" label="macOS">

### macOS

1. Check **About This Mac** and choose the Apple Silicon or Intel download.
2. Open the `.dmg` and drag **dicomqc** into **Applications**.
3. Eject the disk image, then open dicomqc from Applications.

There is no installer wizard on macOS: copying the app into Applications is the
installation step. Use the ARM64 build on an M-series Mac.

:::warning First launch on macOS

These builds are not Apple-notarized. If macOS blocks the app, review
[Apple's guidance](https://support.apple.com/en-us/102445). After attempting to
open it, macOS may offer **Open Anyway** under **System Settings > Privacy &
Security**. Approve only the app you intentionally downloaded from this repository.
Do not disable Gatekeeper; report unexpected security or damaged-app warnings.

:::

</TabItem>
<TabItem value="windows" label="Windows">

### Windows

1. Download and run `dicomqc-0.2.0-windows-x64-setup.exe`.
2. Follow the installation wizard. The package is configured to install for
   your current user.
3. Open **dicomqc** from the Start menu when setup finishes.

:::warning First launch on Windows

The installer is not code-signed, so Windows may display an unknown-publisher or
SmartScreen warning. Check the download source and follow your institution's
software policy. Do not disable Windows security protections to install it.
See [Microsoft's SmartScreen explanation](https://learn.microsoft.com/en-us/windows/security/operating-system-security/virus-and-threat-protection/microsoft-defender-smartscreen/).

:::

</TabItem>
<TabItem value="linux" label="Linux">

### Linux AppImage

Choose `linux-x64` for Intel/AMD or `linux-arm64` for ARM64. The AppImage runs
directly; it does not install itself into system folders or require a separate
Python installation.

Browser downloads may not retain executable permission. From the folder where
you downloaded the file, enable execution once and launch it:

```bash
chmod +x dicomqc-0.2.0-linux-x64.AppImage
./dicomqc-0.2.0-linux-x64.AppImage
```

For ARM64, use `dicomqc-0.2.0-linux-arm64.AppImage` in both commands.
Neither command needs `sudo`. Keep the AppImage wherever you want to run it;
settings and working data are stored separately, as described below.

Linux builds use Ubuntu 22.04 for x64 and Ubuntu 24.04 for ARM64 as build
baselines. An AppImage still needs compatible system libraries. If it fails with
a FUSE or `GLIBC` error, report the message and your distribution/version; do not
replace system libraries manually.

</TabItem>
</Tabs>

### First audit

Once it is running, try the [Desktop privacy audit example](desktop-privacy.md).
Use **Load example data** beside **DICOM inputs** to try a synthetic dataset
before selecting your own files. Finish the audit and use **File > Save Project**
to save a `.dicomqc` project wherever you choose.

### Storage and removal

:::info Where dicomqc stores application data

Settings, run history, reports, and working project data are stored separately
from the application:

- **Linux:** `~/.local/share/org.cnag.dicomqc/` (or `$XDG_DATA_HOME/org.cnag.dicomqc/` if configured).
- **macOS:** `~/Library/Application Support/org.cnag.dicomqc/`.
- **Windows:** `%LOCALAPPDATA%\org.cnag.dicomqc\`.

This folder keeps your settings and audit results between sessions, along with
example data and working copies of projects. These files are not automatically
deleted when you close the app.

You choose where to save `.dicomqc` project files. Your original DICOM files
stay where they are and are never modified by dicomqc.

Save your project and quit the app before removing working data.

:::

#### Update Desktop

Save your project and quit dicomqc before updating:

- **macOS:** replace the app in Applications with the copy from the new DMG.
- **Windows:** run the newer setup executable and follow its wizard.
- **Linux:** replace the AppImage and enable executable permission again if needed.

#### Uninstall or reset

1. Save projects and export any reports you want to keep **outside application
   storage**. Unsaved results may exist only in the working folder.
2. Quit dicomqc. If you previously used a different working folder, its location
   is recorded in `workspace.json` inside the application data folder.
3. To uninstall, delete the AppImage on Linux, remove the app from Applications
   on macOS, or use Installed apps on Windows.
4. To remove saved settings and local history too, delete the application data
   folder listed above, if it remains. Review and separately remove any external
   dicomqc working folder recorded in step 2. Do not delete your input datasets.

Deleting application data without uninstalling resets the local working state;
dicomqc recreates it on the next launch. Separately saved `.dicomqc` projects,
exported reports, and original DICOM datasets are not removed by this cleanup.

:::caution Save before cleaning up

Deleting working storage removes its run history and reports, including unsaved
work. Save the project first; a saved project contains reports and settings but
does not embed the original DICOM inputs.

:::

</TabItem>
<TabItem value="cli" label="CLI">

## CLI

Install from [PyPI](https://pypi.org/project/dicomqc/) with Python 3.10 or newer.
The PyPI package installs **the CLI, not the desktop app**.

### Install from PyPI

Create an isolated environment so dicomqc and its dependencies do not alter the
system Python installation:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install dicomqc
```

Verify the installed command and version:

```bash
dicomqc --version
```

Upgrade an existing installation with:

```bash
python -m pip install --upgrade dicomqc
```

### Optional MultiQC installation

dicomqc writes standalone HTML reports without extra packages. Install MultiQC
only if you want to combine dicomqc results with other QC reports:

```bash
python -m pip install multiqc
```

See the [scan walkthrough](quickstart.md#view-the-same-scan-in-multiqc)
for the rendering command and its matching report screenshots.

### Install from source

From a repository checkout, install dicomqc and its runtime dependencies in
editable mode:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

Contributors who need pytest and coverage tooling can install the `test`
optional dependency group:

```bash
python -m pip install -e ".[test]"
```

The `test` extra is not needed for normal use.

For the complete suite, including the optional local API, install
`".[test,api,api-test]"`. The [desktop app](desktop.md) has separate native build
requirements; installing the PyPI package provides the CLI.

</TabItem>
</Tabs>

## External DICOM tools

DCMTK, Orthanc, and other pseudonymization or remediation tools are not dicomqc
dependencies. Install them separately only when they are part of the local
DICOM transformation workflow. dicomqc itself remains read-only.

Continue with the [Desktop example](desktop-privacy.md) or
[CLI walkthrough](quickstart.md) to run your first audit with synthetic data.
