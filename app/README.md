# Native Desktop Build

The desktop workspace runs from source. Installer validation is deferred:
the current lockfiles resolve Rust Tauri to 2.11.6 and the JavaScript API to
2.12.1, which the installer build rejects as a minor-version mismatch. Align
these dependencies before running the installer workflow. This does not block
the tested native development build described in the [desktop guide](../docs-site/docs/usage/desktop.md).

Build on the target OS and CPU architecture; PyInstaller does not cross-compile.
Use Python 3.12, Node.js 24, Rust stable and the platform's
[Tauri 2 prerequisites](https://v2.tauri.app/start/prerequisites/).
Run from the repository root in a dedicated Python virtual environment:

```sh
python -m pip install ".[api,desktop-build,test,api-test]"
python scripts/build_desktop_engine.py --check-versions
python -m pytest
npm --prefix app ci
npm --prefix app test
python scripts/build_desktop_engine.py
npm --prefix app run build
cargo test --manifest-path app/src-tauri/Cargo.toml --locked
npm --prefix app run tauri -- build
```

The version check compares Python project/runtime, npm package/lockfile, Tauri
configuration and Cargo package versions. It never changes version files.
The build stages `app/src-tauri/engine/dicomqc-api` (`dicomqc-api.exe` on Windows)
beside `_internal/`. Keep the entire directory together. Tauri must bundle it
as `engine/` under its resource directory, preserving that layout. The launcher
uses `resource_dir()/engine/dicomqc-api[.exe]`; the frozen binary also handles
`--worker` subprocesses. Neither Python nor a pip install is needed by end users.
Build intermediates live in `build/desktop-engine/`; rebuilding replaces only
the generated engine directory, never Rust sources or configuration.

Smoke test a frozen build, including relocation, all five synthetic audits,
authenticated shutdown and `--parent-stdin` parent-pipe closure:

```sh
DICOMQC_DESKTOP_ENGINE=app/src-tauri/engine python -m pytest tests/test_desktop_build.py -k frozen --no-cov
```

In PowerShell, first set `$env:DICOMQC_DESKTOP_ENGINE = 'app/src-tauri/engine'`,
then run the same pytest command without the environment assignment prefix.
Ordinary test runs skip this test unless that variable is set.

`build-desktop.yml` runs only through manual dispatch. It builds native macOS
Intel/ARM DMGs, Windows x64 NSIS installers, and Linux x64/ARM64 AppImages,
retained as CI artifacts for seven days. No tags, releases, PyPI uploads,
signing credentials or notarization are configured. These are compatibility
test builds, not published releases; OS trust prompts are expected. Linux
builds require compatible glibc/WebKitGTK on the destination (x64 builds use
Ubuntu 22.04; ARM64 uses 24.04). Installer/GUI acceptance on real target machines
is still required. The stable PyPI workflow is independent and unchanged.
