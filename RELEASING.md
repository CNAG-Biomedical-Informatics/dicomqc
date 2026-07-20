# Releasing dicomqc

Git tags are the canonical release records for dicomqc. Stable Python package
publication is automated from annotated tags; GitHub Release objects are not
part of the release process.

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
   python3 -m pip install -e ".[release,test]"
   pytest
   ```

4. Commit the release state and push `main`.
5. Create and push an annotated tag on that exact commit:

   ```bash
   git tag -a vX.Y.Z -m "Tagging version X.Y.Z" <commit>
   git push origin vX.Y.Z
   ```

6. Confirm that the **Publish to PyPI** workflow succeeds.
7. If a Docker image is published, dispatch that build manually from the same
   stable tag so both distributions use the identical source revision.

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
