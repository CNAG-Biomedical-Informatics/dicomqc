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
dicomqc scan PATH [PATH ...] [--json FILE] [--csv FILE] [--multiqc [DIR]] [--profile PROFILE] [--quiet]
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
| `--multiqc [DIR]` | Write a MultiQC custom-content directory. Defaults to `dicomqc_mqc/`. |
| `--profile PROFILE` | Select a rule profile. v0.1 supports `research-release-v0.1`. |
| `--quiet` | Suppress the text summary. |

### Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Clean scan |
| `1` | Warnings only |
| `2` | Errors or fatal scan failures |

## `dicomqc compare`

Available in the source checkout; see [Compare datasets](../usage/compare.md):

```bash
dicomqc compare SOURCE CANDIDATE --manifest FILE [--json FILE] [--csv FILE] [--quiet]
```

This checks file completeness and patient pseudonym consistency using an explicit
CSV pairing manifest. It also audits candidate metadata. Comparison reports use
manifest row references and omit original paths and raw metadata. Exit codes are
the same as `scan`. The published v0.1.0 package does not include this command.

## `dicomqc demo`

```bash
dicomqc demo [--output-dir DIR] [--force]
```

Generate a synthetic DICOM dataset and a complete dicomqc report bundle.

### Options

| Option | Description |
| --- | --- |
| `--output-dir DIR` | Write demo files under `DIR` instead of `dicomqc-demo/`. |
| `--force` | Replace the output directory if it already exists. |

The demo command exits `0` when generation succeeds, even though the synthetic
scan result contains intentional findings. The reported scan exit code is shown
in the command output.
