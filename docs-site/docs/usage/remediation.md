---
title: Remediation
---

# Remediation

DICOMQC is a validator for DICOM de-identification policies. Like a schema
validator, it reports non-compliance but does not rewrite the source files.

When DICOMQC finds a problem, fix the candidate release dataset with an
anonymization or pseudonymization tool, then run DICOMQC again.

```text
raw DICOMs
    |
    v
anonymizer / pseudonymizer
    |
    v
candidate release DICOMs
    |
    v
DICOMQC audit
    |
    v
pass/fail report + recommendations
```

## Safe working pattern

Never modify the only copy of a DICOM dataset. Work on a copy or on the output
of a controlled anonymization pipeline.

```bash
cp -a raw_study anonymized_study
```

Run the audit:

```bash
dicomqc scan anonymized_study/ --json report.json --csv findings.csv --multiqc
```

Apply fixes with your chosen tool, then rerun the audit:

```bash
dicomqc scan anonymized_study/ --json report-after-fix.json --csv findings-after-fix.csv --multiqc
```

## DCMTK `dcmodify`

DCMTK is a common command-line toolkit for DICOM operations. Its `dcmodify`
command can remove or replace metadata tags.

Example: remove direct PHI fields from all `.dcm` files in a working copy:

```bash
find anonymized_study -name '*.dcm' -print0 \
  | xargs -0 dcmodify \
      -e PatientBirthDate \
      -e PatientAddress \
      -e PatientTelephoneNumbers \
      -e InstitutionAddress \
      -e ReferringPhysicianName \
      -e OperatorsName \
      -e AccessionNumber
```

Example: replace pseudonym fields:

```bash
dcmodify \
  -i PatientName=SUBJ001 \
  -i PatientID=SUBJ001 \
  anonymized_study/image.dcm
```

Private tags require project-specific judgment. Removing all private tags may be
appropriate for some releases but may also remove scanner- or research-relevant
metadata.

```bash
dcmodify -e "(0029,0010)" anonymized_study/image.dcm
```

Use your installed DCMTK version's documented options for broad private-tag
removal, or enumerate the private tags that your release policy says must be
removed. Check the exact `dcmodify` syntax before using these commands in
production.

## Orthanc

Orthanc can anonymize DICOM instances through its REST API and configuration.
This is useful when DICOM ingestion and de-identification already happen inside
an Orthanc workflow.

Recommended pattern:

1. Import or route data into Orthanc.
2. Use Orthanc anonymization to create a derived dataset.
3. Export the derived dataset.
4. Run DICOMQC on the exported result.

DICOMQC should audit the exported candidate release, not the original Orthanc
store.

## XNAT and site pipelines

For XNAT-based workflows, apply XNAT anonymization scripts or containerized
pipeline steps first, then run DICOMQC on the resulting DICOM export.

This keeps DICOMQC independent of the site platform while still making it useful
as a release gate.

## Custom `pydicom` scripts

Small projects sometimes use custom `pydicom` scripts to remediate metadata.
Keep those scripts separate from DICOMQC and make them explicit pipeline steps.

The DICOMQC role is to validate the output and produce redaction-safe evidence.

## Future remediation plans

A future DICOMQC release may emit a machine-readable remediation plan such as:

```yaml
required_changes:
  - tag: PatientBirthDate
    action: remove
  - tag: PatientName
    action: replace_with_pseudonym
  - tag: PrivateTags
    action: review_or_remove
```

The plan would still be applied by external tools. DICOMQC remains read-only.
