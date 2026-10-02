---
title: CLI Reference
---

# CLI Reference

## Global options

| Option | Description |
| --- | --- |
| `--version` | Print the installed dicomqc version and exit. |
| `-h`, `--help` | Show command help and exit. |

## `dicomqc scan`

```bash
dicomqc scan PATH [PATH ...] [--json FILE] [--csv FILE] [--html FILE] [--multiqc [DIR]] [--profile PROFILE] [--quiet]
```

### Arguments

| Argument | Description |
| --- | --- |
| `PATH` | DICOM file or directory. Multiple paths are accepted. |

### Options

| Option | Description |
| --- | --- |
| `--json FILE` | Write a JSON report without raw DICOM tag values. |
| `--csv FILE` | Write a CSV findings report. |
| `--html FILE` | Write a standalone HTML report with search and severity filters. Works offline. |
| `--multiqc [DIR]` | Write a MultiQC custom-content directory. Defaults to `dicomqc_mqc/`. |
| `--profile PROFILE` | Select a rule profile. v0.2 supports `research-release-v0.1`. |
| `--quiet` | Suppress the text summary. |

### Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Clean scan |
| `1` | Warnings only |
| `2` | Errors or fatal scan failures |

## `dicomqc compare`

Available since v0.2.0; see [Compare datasets](../usage/compare.md):

```bash
dicomqc compare SOURCE CANDIDATE --manifest FILE [--json FILE] [--csv FILE] [--html FILE] [--quiet]
```

This checks file completeness and patient pseudonym consistency using an explicit
CSV pairing manifest. It also audits candidate metadata. Comparison reports use
manifest row references and omit original paths and raw metadata. Exit codes are
the same as `scan`. `--html FILE` writes an offline report including pairing
coverage and searchable findings. Reports must use distinct output paths outside
the input directories and must not overwrite the manifest.

## `dicomqc demo`

```bash
dicomqc demo [--compare] [--output-dir DIR] [--force]
```

Generate a synthetic DICOM dataset and a complete dicomqc report bundle.

### Options

| Option | Description |
| --- | --- |
| `--output-dir DIR` | Write demo files under `DIR` instead of `dicomqc-demo/`. |
| `--force` | Replace an existing marked demo directory created by v0.2.0 or later. Unmarked directories are refused. |
| `--compare` | Generate source, failing candidate, and corrected datasets, a pairing manifest, and JSON/CSV/HTML reports for both comparisons. Available since v0.2.0. |

The demo command exits `0` when generation succeeds, even though the synthetic
scan result contains intentional findings. The reported scan exit code is shown
in the command output.

With `--compare`, the two comparison exit codes are `2` (intentional failures)
and `0` (corrected dataset). The demo command still exits `0` on successful
generation. Both demo modes exit `2` if their audit results differ from the
expected results. See the [comparison demo](../usage/compare.md#try-the-comparison-demo).
