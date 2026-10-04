---
title: Dataset comparison example
---

# Dataset comparison

Compare original source DICOM files with the candidate DICOM copies produced by
external de-identification. This checks whether processing preserved file
coverage and assigned patient pseudonyms consistently. It does **not** compare
two dicomqc runs. Privacy checks also run on readable paired candidate files.

## Run the synthetic example

1. In **Setup**, select **Dataset comparison**.
2. Open **Load example data** and select **Dataset comparison**.
3. Select the resulting run and open **Reports**.

[![Comparison setup with source, candidate, and pairing manifest inputs.](/img/desktop-comparison-setup.png)](/img/desktop-comparison-setup.png)

The example generates three source files for two fictional patients, a flawed
candidate dataset, a corrected dataset, and a pairing manifest. It writes
before and after reports within the example run. The corrected files are
generated fixtures, not files repaired by dicomqc.

## Compare the results

Select the **before** HTML report. Expect **three errors**: one missing candidate
file and two findings for a source patient assigned different pseudonyms across
visits. Only two of the three pairs are readable.

[![Comparison report summary showing three errors in two issue groups.](/img/desktop-comparison-report.png)](/img/desktop-comparison-report.png)

The existing candidate files pass individual privacy checks. These problems
become visible only through comparison with the source and manifest.

Select the **after** HTML report: all three pairs are readable with no findings.
This illustrates the expected correction, not a guarantee of anonymity.
Use **File > Save Project** to retain the run and reports.

[![Corrected comparison report with no findings.](/img/desktop-comparison-after.png)](/img/desktop-comparison-after.png)

## Compare your own datasets

| Input | Select |
| --- | --- |
| **Source folder** | Original DICOM files, under restricted access |
| **Candidate folder** | Output produced by an external de-identification tool |
| **Pairing manifest** | CSV with `source,candidate` columns and relative file paths |

Have the external processing workflow record file pairs; dicomqc cannot infer
them from renamed files. See [manifest requirements](compare.md#prepare-a-pairing-manifest).

Select all three inputs, then **Run comparison**. An optional [project
policy](desktop-checks.md) applies only to candidate metadata. UID checks,
scanner inventory, and MultiQC output are not available in this mode.

References such as `pair-000003/candidate` identify manifest data rows, not
patient IDs. Use the restricted manifest to locate files.

:::caution Sensitive inputs

Source data and pairing manifests can identify patients. Keep them under
restricted access. Saved projects include a copy of the selected manifest;
review project contents before sharing.

:::
