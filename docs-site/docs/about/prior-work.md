---
title: Prior Work
---

# Prior Work

All three tools check DICOM metadata. In particular, xnat-dicomqc and dicomqc
overlap in checking tags against rules. The useful differences are how they run,
how checks are defined, and what the results are used for.

| Aspect | dicomqc v0.2 | [xnat-dicomqc](https://github.com/SPMIC-UoN/xnat-dicomqc) | [SQAN](https://github.com/IUSCA/SQAN) |
| --- | --- | --- | --- |
| Main task | Audit metadata for privacy risks after de-identification. | Run project-defined DICOM tag QC on scans in XNAT. | Check imaging protocols and exams, and review results in a web portal. |
| Setup | Python CLI that scans local files and directories. | Docker container run through XNAT, with a plugin for QC data. | Services for data intake, QC, an API, and a web UI, backed by a database. |
| Checks | One built-in profile for direct identifiers, pseudonym formats, and private tags. | Tests defined in a project-level Excel configuration file. | Protocol and exam checks, with QC templates managed through the UI. |
| Results | JSON, CSV, and MultiQC-compatible files; exit codes for automated workflows. | QC data integrated into XNAT through its data-type plugin. | Stored metadata and QC results available through the API and portal. |
| Where they overlap | Tag checks and findings for review. | Tag checks and findings for review; overlap depends on the configured tests. | Metadata checks and review of QC results. |

xnat-dicomqc already provides configurable tag QC. dicomqc's difference is its
local command-line workflow and built-in privacy checks, not the idea of auditing
DICOM tags. User-defined policy files are still planned for dicomqc.

This comparison uses the [xnat-dicomqc README](https://github.com/SPMIC-UoN/xnat-dicomqc/blob/master/README.md)
and [SQAN README](https://github.com/IUSCA/SQAN/blob/master/README.md). It describes
their documented features, not a head-to-head test of which tool detects more problems.

## Where dicomqc fits

Use dicomqc after de-identification and alongside your site's QC tools and BIDS
validator. It answers:

- Did the files pass the selected metadata checks?
- Which files and tags need review?
- Which profile and rule produced each finding?
- Can the results be saved without copying raw DICOM values into the report?
