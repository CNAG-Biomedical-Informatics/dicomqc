#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT_DIR="${OUT_DIR:-$ROOT_DIR/examples/multiqc/output}"
DICOM_DIR="$OUT_DIR/dicom"
REPORT_DIR="$OUT_DIR/dicomqc"
if [ -n "${PYTHON:-}" ]; then
  PYTHON_BIN="$PYTHON"
elif [ -x "$ROOT_DIR/.venv/bin/python" ]; then
  PYTHON_BIN="$ROOT_DIR/.venv/bin/python"
else
  PYTHON_BIN="python3"
fi

if [ -n "${DICOMQC:-}" ]; then
  DICOMQC_BIN="$DICOMQC"
elif [ -x "$ROOT_DIR/.venv/bin/dicomqc" ]; then
  DICOMQC_BIN="$ROOT_DIR/.venv/bin/dicomqc"
else
  DICOMQC_BIN="dicomqc"
fi

rm -rf "$OUT_DIR"
mkdir -p "$DICOM_DIR" "$REPORT_DIR"

"$PYTHON_BIN" "$ROOT_DIR/scripts/make_dicom_fixtures.py" --output-dir "$DICOM_DIR"

set +e
"$DICOMQC_BIN" scan "$DICOM_DIR" \
  --json "$REPORT_DIR/report.json" \
  --csv "$REPORT_DIR/findings.csv" \
  --multiqc "$REPORT_DIR/dicomqc_mqc"
status=$?
set -e

if command -v multiqc >/dev/null 2>&1; then
  (
    cd "$OUT_DIR"
    multiqc dicomqc --outdir . --force --config "$ROOT_DIR/examples/multiqc/multiqc_config.yaml"
  )
  echo "MultiQC report: $OUT_DIR/multiqc_report.html"
else
  echo "MultiQC is not installed; custom-content files are in $REPORT_DIR/dicomqc_mqc"
fi

echo "dicomqc exit code: $status"
exit 0
