---
title: Compare datasets
---

# Compare source and de-identified files

Available since v0.2.0, `dicomqc compare` checks that a de-identification
run accounts for every input file and uses patient pseudonyms consistently.

## Try the comparison demo

Run:

```bash
dicomqc demo --compare --output-dir comparison-demo
```

The demo creates three synthetic source files for two patients. The first
candidate dataset is missing one file and assigns different pseudonyms to two
visits from the same patient. Its comparison exits `2`. Each existing candidate
file passes the individual metadata checks, so this shows problems that require
comparing the datasets.

The demo also creates a separate corrected dataset with all three files and
consistent pseudonyms. Its comparison exits `0`. The generator creates both
examples; the audit itself never edits DICOM files.

```text
comparison-demo/
  source/                 # three synthetic source files
  candidate/              # two files; inconsistent pseudonyms
  corrected/              # three files; consistent pseudonyms
  pairs.csv               # same pairing manifest for both runs
  before.html             # failing comparison
  before.json
  before.csv
  after.html              # corrected comparison
  after.json
  after.csv
```

Rerun either comparison yourself:

```bash
dicomqc compare comparison-demo/source comparison-demo/candidate --manifest comparison-demo/pairs.csv
dicomqc compare comparison-demo/source comparison-demo/corrected --manifest comparison-demo/pairs.csv
```

The `demo` command exits `0` when generation succeeds, even though the first
comparison intentionally fails. Unexpected audit results make the demo exit `2`.
Use `--force` to replace a demo directory created by v0.2.0 or later. It refuses
unmarked directories, including old demos; choose a new output path for those.
Without `--output-dir`, it writes to `dicomqc-demo/`, just like the
regular demo. Comparison demos write HTML, JSON, and CSV reports. Open either
`before.html` or `after.html` directly in a browser; MultiQC is not needed.

## Prepare a pairing manifest

Create a CSV file outside both DICOM directories:

```csv
source,candidate
patient-a/visit-1/image.dcm,sub-001/visit-1/renamed.dcm
patient-a/visit-2/image.dcm,sub-001/visit-2/renamed.dcm
```

Paths are relative to the source and candidate directories respectively. Each
file must appear exactly once on its side of the manifest. The directories
must be separate, contain only the files being audited, and have no symbolic
links. Files do not need a `.dcm` extension. Keep the manifest restricted: its
paths may identify patients.

Have the de-identification process record these pairs as it writes output files.
dicomqc trusts that pairing; it cannot prove that two listed files correspond.
It does not guess from filenames or UIDs, which may change during de-identification.

## Run the comparison

```bash
dicomqc compare raw_mri/ candidate_mri/ \
  --manifest pairs.csv \
  --json comparison.json \
  --csv comparison-findings.csv \
  --html comparison.html
```

Save reports outside both input directories. The command reads metadata and
does not modify the DICOM files or the manifest.

It checks for:

- missing files listed in the manifest;
- source or candidate files omitted from the manifest;
- listed files that cannot be read as DICOM;
- missing or unchanged `PatientID` values;
- one source patient receiving different output IDs;
- different source patients receiving the same output ID.

It also runs the existing `research-release-v0.1` privacy checks on each readable,
listed candidate file. Original source files are not expected to pass those checks.

Source patients are grouped by `IssuerOfPatientID` and `PatientID`. If the issuer
is absent, equal source IDs are treated as the same patient. Use a single source
ID namespace or populate issuers before comparing data from multiple sites.
Output `PatientID` values must be unique across source patients in this comparison.
Patient name consistency is not checked; output names still receive the ordinary
pseudonym-format check.

## Read the results

Exit codes match `scan`: `0` means no findings, `1` means warnings, and `2` means
errors, unreadable files, or invalid inputs. Empty manifests and duplicate pairings
are rejected instead of producing a clean result.
Parser warnings also stop a file from passing. Their original text is suppressed
because it may contain identifiers; inspect affected files in a restricted environment.

Comparison reports omit original paths, identifiers, UIDs, and other raw metadata.
A reference such as `pair-000002/candidate` points to the second data row of the
manifest (excluding its header). Use the restricted manifest to locate that file.
For files omitted from the manifest, `unpaired-source-000001` or
`unpaired-candidate-000001` identifies the first omitted relative path in sorted
order on that side. These references are local to this comparison, not stable
identifiers across different manifests or inventories.

The JSON `comparison` section counts source files, candidate files, manifest pairs,
readable pairs, and pairs checked for identity consistency. The usual scan counts
refer to readable, listed **candidate** files. Dataset errors can therefore exist
even when all scanned candidates pass their individual checks.

## Limits of this first implementation

This comparison expects one output file for every source file. It does not yet
support intentional exclusions, splitting or merging files, date-shift checks,
UID-reference checks, pixel comparisons, or MultiQC output for comparisons.
Equal file counts alone do not establish completeness: the manifest must cover
both inventories and every listed file must be readable.

A consistent pseudonym is not proof of anonymity. Review the findings and the
remaining privacy risks before sharing data.
