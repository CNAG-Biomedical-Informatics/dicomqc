# Releasing dicomqc

Annotated Git tags identify release source revisions. Pushing a stable tag
publishes the CLI to PyPI and separately builds Desktop installers into a
**draft GitHub Release**. Review the draft before making downloads public.

## Release invariants

- Stable tags use the exact form `vX.Y.Z` and are annotated.
- The tag version, `dicomqc.__version__`, and installed distribution metadata
  must match.
- A published version is never reused, and a published tag is never moved.
- The source distribution and wheel are built, validated, and smoke-tested
  before the publication job receives an OpenID Connect token.
- Deleting a GitHub Release object must preserve its Git tag. Never use
  `--cleanup-tag` when deleting a release.

## PyPI Trusted Publisher

Configure the production publisher with these exact values:

```text
Project: dicomqc
Owner: CNAG-Biomedical-Informatics
Repository: dicomqc
Workflow: publish-pypi.yml
Environment: pypi
```

The workflow remains at `.github/workflows/publish-pypi.yml`. Its build job has
read-only repository access. Only the separate `pypi` environment job receives
`id-token: write` for publication.

## Stable release procedure

1. Update `pyproject.toml` and `src/dicomqc/__init__.py` to the same Python
   version.
2. Move the release changes from `Unreleased` to a dated version section in
   `CHANGELOG.md`.
3. Install the release and test dependencies and run the complete test suite:

   ```bash
   python3 -m pip install -e ".[release,test,api,api-test]"
   pytest
   ```

4. Build the wheel and source distribution and validate their metadata:

   ```bash
   python -m build
   python -m twine check dist/*
   ```

   Install each distribution into its own fresh virtual environment. From a
   directory outside the checkout, run this script with that environment's Python:

   ```bash
   python /path/to/dicomqc/scripts/smoke_distribution.py --expected-version X.Y.Z
   ```

   It checks version metadata, both demo modes, failing and passing comparisons,
   and generated reports. The PyPI workflow runs it against both package formats.
   Update the docs for the release and run `npm run build` in `docs-site/`.

5. Commit the release state and push `main`.
6. Create and push an annotated tag on that exact commit:

   ```bash
   git tag -a vX.Y.Z -m "Tagging version X.Y.Z" <commit>
   git push origin vX.Y.Z
   ```

7. Confirm that **Publish to PyPI** and **Build desktop installers** succeed.
   The two workflows are independent: a Desktop failure does not roll back PyPI.
8. Review the draft GitHub Release, test its installers on supported systems,
   and complete the release notes before publishing it. Do not move the tag.
9. If a Docker image is published, dispatch that build manually from the same
   stable tag so both distributions use the identical source revision.

## Desktop installers

`.github/workflows/build-desktop.yml` builds DMG installers for macOS Intel and
Apple Silicon, an NSIS installer for Windows x64, and AppImages for Linux x64
and ARM64. Python and the audit engine are bundled.

- **Manual testing:** use **Build desktop installers > Run workflow** and select
  one platform or `all`. Download installer/checksum artifacts from the run;
  they are retained for 30 days. Manual runs do not create a GitHub Release.
- **Stable tags:** every platform must succeed before the workflow creates a
  draft Release containing five installers and five SHA-256 files. The tag must
  be annotated and match the Python, frontend, and native package versions.
- **Package checks:** extract AppImages, verify and mount DMGs, or silently
  install NSIS packages; verify the executable architecture; then run the
  frozen-engine tests against the packaged copy. These cover relocation,
  authentication, examples, workers, and shutdown. The packaged application is
  also launched on every platform; Linux additionally runs the full native GUI
  smoke test before packaging.
- **Reruns:** failed jobs can be retried; assets may be replaced only while the
  Release remains a draft. Published Release assets are not overwritten.

macOS builds are not Apple-notarized and Windows installers are unsigned.
Installer checks do not replace manual GUI testing on each platform. The macOS
ad-hoc signature check is not notarization. The Linux x64 build uses Ubuntu
22.04; ARM64 uses Ubuntu 24.04, so their system requirements differ.

For 0.2.0, finish the dated changelog and update all version files (including
`CITATION.cff`) before tagging. Run a manual all-platform build first. This
workflow does not create or push release tags on your behalf.

## TestPyPI prereleases

TestPyPI publication remains a manual `workflow_dispatch` operation from
`main`. Use a unique PEP 440 prerelease version such as `0.2.0rc1`; TestPyPI,
like PyPI, does not permit replacing an existing distribution file.

TestPyPI does not require a Git tag and never triggers the production PyPI
workflow.

## Failed publication

Fix the configuration or workflow error and rerun the failed GitHub Actions
jobs. Do not recreate or move the tag, and do not increment the package version
unless PyPI accepted one or more files for that version.
