---
title: Install
---

# Install

The desktop app is the recommended **dicomqc** interface. The CLI supports
automation and scripted workflows; both use the same
Python audit engine.

## Desktop App

:::info Desktop availability

Installers have not been published. Testers with access to a draft Release or
workflow artifact can use those packages. Alternatively, follow the
[desktop source-build instructions](desktop.md#build-from-source), which require
Python, Node.js, Rust, and the operating system's Tauri prerequisites.

:::

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

Once it is running, try the [Desktop privacy audit example](desktop-privacy.md).

The app maintains a local working folder for settings and audit results. See
[Storage and removal](desktop.md#storage-and-removal) for its location on each
operating system and how to remove application data when uninstalling.

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

## External DICOM tools

DCMTK, Orthanc, and other pseudonymization or remediation tools are not dicomqc
dependencies. Install them separately only when they are part of the local
DICOM transformation workflow. dicomqc itself remains read-only.

Continue with the [Desktop example](desktop-privacy.md) or
[CLI walkthrough](quickstart.md) to run your first audit with synthetic data.
