---
title: CLI Reference
---

# CLI Reference

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
| `--json FILE` | Write a redaction-safe JSON report. |
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
