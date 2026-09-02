---
title: Prior Work
---

# Prior Work

dicomqc builds on existing work in DICOM metadata quality control. The projects
below address related problems but differ in scope or deployment model.

| Project | Focus | Relationship to dicomqc |
| --- | --- | --- |
| [`SPMIC-UoN/xnat-dicomqc`](https://github.com/SPMIC-UoN/xnat-dicomqc) | Configurable DICOM tag checks in an XNAT container. | dicomqc is a standalone command-line tool and does not require XNAT. It writes JSON, CSV, and MultiQC-compatible reports. |
| [`IUSCA/SQAN`](https://github.com/IUSCA/SQAN) | DICOM metadata extraction, logging, and web-based quality-control review for neuroimaging. | SQAN provides a broader data-management system. dicomqc has a narrower role: checking local DICOM metadata after de-identification. |

## Positioning

dicomqc does not replace site QC platforms, XNAT workflows, anonymizers, or BIDS
validators. It is a standalone, read-only check that answers:

- Did the files pass the selected metadata checks?
- Which files and tags need review?
- Which profile and rule produced each finding?
- Can the results be saved without copying raw DICOM values into the report?
