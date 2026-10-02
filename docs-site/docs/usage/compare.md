---
title: Compare datasets
---

# Compare source and de-identified files

The source checkout includes `dicomqc compare`. It checks that a de-identification
run accounts for every input file and uses patient pseudonyms consistently.
This command is not included in the published v0.1.0 package.

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
  --csv comparison-findings.csv
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
