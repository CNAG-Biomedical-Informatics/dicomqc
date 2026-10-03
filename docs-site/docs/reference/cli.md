---
title: CLI Reference
---

# CLI Reference

The desktop app is the recommended interface for routine audits. Use the CLI
when you need scripting, batch execution, pipeline integration, or explicit
exit-code handling. Both interfaces run the same audit engine.

## Global options

| Option | Description |
| --- | --- |
| `--version` | Print the installed dicomqc version and exit. |
| `-h`, `--help` | Show command help and exit. |

## `dicomqc scan`

```bash
dicomqc scan PATH [PATH ...] [--json FILE] [--csv FILE] [--html FILE] [--multiqc [DIR]] [--profile PROFILE] [--policy FILE] [--vendor-summary] [--uid-checks] [-t THREADS] [--quiet]
```

### Arguments

| Argument | Description |
| --- | --- |
| `PATH` | DICOM file or directory. Multiple paths are accepted. |

### Options

| Option | Description |
| --- | --- |
| `--json FILE` | Write JSON findings and scan metadata. See [redaction details](../technical-details/architecture.mdx#what-stays-out-of-reports). |
| `--csv FILE` | Write a CSV findings report. |
| `--html FILE` | Write a standalone HTML report with search and severity filters. Works offline. |
| `--multiqc [DIR]` | Write a MultiQC custom-content directory. Defaults to `dicomqc_mqc/`. |
| `--profile PROFILE` | Select a rule profile. Supports `research-release-v0.1`. |
| `--policy FILE` | Add project-specific YAML checks without disabling built-in checks. See [Project policies](../usage/policies.md). |
| `--uid-checks` | Check top-level study, series, and instance UID syntax, role reuse, and hierarchy within this scan. See [UID integrity](../usage/uid-integrity.md). |
| `--vendor-summary` | Include declared scanner/software labels and private creator blocks. Exports metadata text that may identify people; see [Scanner inventory](../usage/vendor-summary.md). |
| `-t THREADS`, `--threads THREADS` | Process bounded batches of independent files with this many metadata threads. Default: `4` or fewer on smaller systems; maximum: logical processors available to dicomqc. Small audits run serially; results retain deterministic input order. |
| `--quiet` | Suppress the text summary. |

### Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Clean scan |
| `1` | Warnings only |
| `2` | Errors or fatal scan failures |

## `dicomqc compare`

See [Compare datasets](../usage/compare.md):

```bash
dicomqc compare SOURCE CANDIDATE --manifest FILE [--json FILE] [--csv FILE] [--html FILE] [--policy FILE] [-t THREADS] [--quiet]
```

This checks file completeness and patient pseudonym consistency using an explicit
CSV pairing manifest. It also audits candidate metadata. Comparison reports use
manifest row references and omit original paths and raw metadata. Exit codes are
the same as `scan`. `--html FILE` writes an offline report including pairing
coverage and searchable findings. Reports must use distinct output paths outside
the input directories and must not overwrite the manifest.

`--policy FILE` adds [project checks](../usage/policies.md)
to readable, listed candidate files only. Keep the policy outside the input
directories; reports must not overwrite it. The same policy option is available
for `scan`.

`-t` / `--threads` uses the same hardware-derived maximum as `scan` and sends
bounded batches of independent manifest pairs to worker processes within one
comparison audit.

## `dicomqc demo`

```bash
dicomqc demo [--compare | --policy-demo | --vendor-demo | --uid-demo | --large] [--output-dir DIR] [--force]
```

Generate a synthetic DICOM dataset and a complete dicomqc report bundle.

### Options

| Option | Description |
| --- | --- |
| `--output-dir DIR` | Write demo files under `DIR` instead of `dicomqc-demo/`. |
| `--force` | Replace an existing marked demo directory. Unmarked directories are refused. |
| `--compare` | Generate source, failing candidate, and corrected datasets, a pairing manifest, and JSON/CSV/HTML reports for both comparisons. |
| `--policy-demo` | Generate a policy file, failing and corrected synthetic datasets, and before/after JSON/CSV/HTML reports. |
| `--vendor-demo` | Generate three synthetic files and a scan with scanner/private-tag inventory in HTML, JSON, and MultiQC, plus CSV findings. |
| `--uid-demo` | Generate four failing and four corrected synthetic files, with before/after HTML, JSON, CSV, and MultiQC content. See [UID integrity](../usage/uid-integrity.md#try-the-uid-demo). |
| `--large` | Generate and audit 10,000 metadata-only DICOM files with 250 deterministic privacy findings. Use it to exercise scalability, pagination, and report review; it is not a performance guarantee for real storage. |

`--compare`, `--policy-demo`, `--vendor-demo`, `--uid-demo`, and `--large` are mutually exclusive.

The demo command exits `0` when generation succeeds, even though the synthetic
scan result contains intentional findings. The reported scan exit code is shown
in the command output.

With `--compare`, the two comparison exit codes are `2` (intentional failures)
and `0` (corrected dataset). The demo command still exits `0` on successful
generation. Demo generation exits `2` if its audit results differ from the
expected results. See the [comparison demo](../usage/compare.md#try-the-comparison-demo).

The `--policy-demo` mode has audit exit codes
`2` before correction and `0` afterward. It writes `before.html`, `after.html`,
their JSON/CSV equivalents, and `policy.yaml` under the output directory.
The demo command exits `0` on successful generation. See [Project policies](../usage/policies.md).

With `--vendor-demo`, the scan exits `1` for three private-tag warnings; the demo
command exits `0` on successful generation. See the
[inventory walkthrough](../usage/vendor-summary.md#try-the-inventory-demo).

With `--large`, the generated scan is clean and both the scan and demo command
exit `0`. Files are created under the selected demo output and are not stored in
the Python package or Git repository. Threading results depend on metadata size,
filesystem, cache state, and Python runtime; compare settings on the target
system instead of treating the example as a benchmark claim.

## Output formats

| Format | Use it for | Option |
| --- | --- | --- |
| HTML | Reviewing grouped findings in an offline browser report | `--html report.html` |
| JSON | Processing the full audit result in scripts | `--json report.json` |
| CSV | Working with individual findings in a spreadsheet | `--csv findings.csv` |
| MultiQC | Viewing scan results alongside other QC tools | `--multiqc dicomqc_mqc` |

Request several formats in one run:

```bash
dicomqc scan study/ --html report.html --json report.json --csv findings.csv --multiqc
```

Use distinct output paths outside the DICOM inputs; do not overwrite a policy
or manifest file. HTML, JSON, and CSV also work with `compare`; MultiQC export
is available for `scan`.

HTML embeds its styles and scripts, so no server or internet connection is
needed. See the [HTML review controls](../usage/quickstart.md#review-the-html-report).
`--multiqc` writes custom-content files, not a finished HTML report; run MultiQC
separately as shown in the [scan walkthrough](../usage/quickstart.md#view-the-same-scan-in-multiqc).

### JSON

JSON contains `tool`, `profile_id`, `summary`, `records`, `findings`, and
`skipped_files`. Comparisons add `comparison` pairing counts and use
manifest-row references instead of original paths. Policy audits add a
`policy` object containing `id` and the policy file's `sha256` digest, not its
configured values or patterns.

Ordinary scan JSON includes study/series UIDs, manufacturer, and modality;
policy-scan JSON, UID-enabled scan JSON, and comparison reports omit these record-context fields.
UID-enabled scans add `uid_checks` with the check profile and coverage counts;
see the [UID output examples](../usage/uid-integrity.md#json-and-csv-from-this-scan).
Explicitly adding `--vendor-summary` to a scan adds a separate `vendor_summary`
object with raw scanner/software labels and private creator labels, even when
`--policy` or `--uid-checks` is used. Those labels may contain identifying information; private
payload values are never exported. Review the
[redaction details](../technical-details/architecture.mdx#what-stays-out-of-reports)
before sharing reports.

### CSV

CSV has one row per finding, with columns `path`, `rule_id`, `profile_id`,
`severity`, `tag`, `keyword`, `value_state`, `message`, `recommendation`, and
`standard_refs`. A result without findings produces only the header. CSV does
not include audit summary counts, UID coverage, the policy digest, or the scanner inventory; keep JSON alongside it
for that context.

The [comparison walkthrough](../usage/compare.md#json-and-csv-from-this-comparison)
shows a JSON finding and the corresponding CSV rows as a table.
