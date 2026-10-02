---
title: Planned Features
---

# Planned Features

The features on this page are not available in dicomqc v0.1. They describe
ideas for later releases.

## Policy files

A policy file would let users define metadata checks. For example, it could require
`PatientBirthDate` to be absent or `PatientID` to match an approved pseudonym
format. The policy would define what dicomqc checks, not how files are modified.

## Plugins

Plugins would let separately installed packages add
checks, report formats, DICOM readers, standards profiles, or vendor-specific
metadata checks.

## Standards profiles

Planned DICOM PS3.15 and BIDS profiles would identify every check with a stable
rule ID and a reference to its source standard. The v0.1 result model already
contains `profile_id`, `rule_id`, and `standard_refs`, but the current built-in
profile does not claim compliance with either standard.

## Vendor metadata summaries

A vendor summary would list manufacturer, scanner
model, software version, and private creator blocks. Reviewers could use that
summary to identify private tags and protocol fields that need manual inspection.
