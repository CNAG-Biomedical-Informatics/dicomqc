---
title: Audit modes
---

# Two audit modes

Start with **Privacy audit** to inspect a dataset. Use **Dataset comparison**
when you also have its source files and want to check the de-identification
process. Choose the mode based on the data you have.
Desktop and CLI use the same engine and checks.

:::info What Dataset comparison compares

It compares **original source DICOM files** with **processed candidate DICOM
files**, using a private pairing CSV. It does not compare two completed dicomqc
runs, reports, or projects.

:::

| Mode | Inputs | Checks | Desktop | CLI |
| --- | --- | --- | --- | --- |
| **Privacy audit** | DICOM files or folders | Identifying metadata, pseudonym formats, private tags, unreadable files | [Example](desktop-privacy.md) | [scan](quickstart.md) |
| **Dataset comparison** | Source folder, candidate folder, pairing CSV | File coverage and patient pseudonym consistency, plus privacy checks on readable paired candidate files | [Example](desktop-comparison.md) | [compare](compare.md) |

A candidate is the DICOM output of an external de-identification tool.
Comparison does not create it. If you receive only the candidate dataset, run
a privacy audit. Comparison requires source access and a pairing manifest in a
restricted environment.

## Optional checks within a mode

These extend an audit; they are **not additional modes**.

| Option | Privacy audit | Dataset comparison |
| --- | --- | --- |
| Project policy (YAML) | Additional metadata rules on scanned files | Additional rules on candidate files only |
| UID integrity | Optional syntax and study/series relationship checks | Not supported |
| Scanner inventory | Optional equipment and private-creator inventory | Not supported |
| HTML, JSON, CSV | Available | Available |
| MultiQC custom content | Optional output | Not supported |

A policy adds to built-in checks rather than replacing them. Scanner inventory
describes observed labels, not a separate privacy verdict. MultiQC displays
results and does not perform another audit.

Configure [Desktop options](desktop-checks.md), or use the CLI guides for
[policies](policies.md), [UID integrity](uid-integrity.md), and
[scanner inventory](vendor-summary.md).

## Examples and projects

Each Desktop example generates synthetic DICOM files and starts **a separate run
in the current project**. The policy, UID, and
inventory examples demonstrate Privacy audit options, not new modes.

:::caution Scope

Neither mode modifies DICOM, examines pixels, or certifies that data can be
shared. Passing means the enabled checks found no problems. Apply changes with
an external tool, rerun the audit, and review remaining risks.

:::
