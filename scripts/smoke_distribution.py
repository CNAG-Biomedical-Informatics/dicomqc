"""Exercise an installed distribution from a directory outside the checkout."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from importlib.metadata import version
from pathlib import Path

import dicomqc


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-version", required=True)
    expected = parser.parse_args().expected_version
    assert dicomqc.__version__ == version("dicomqc") == expected
    checkout = Path(__file__).resolve().parents[1]
    assert checkout not in Path(dicomqc.__file__).resolve().parents, "Smoke test imported checkout code"
    with tempfile.TemporaryDirectory(prefix="dicomqc-package-smoke-") as temporary:
        root = Path(temporary)

        def cli(*args: str, expected_exit: int = 0) -> str:
            result = subprocess.run(
                [sys.executable, "-m", "dicomqc.cli", *args], cwd=root,
                capture_output=True, text=True, check=False,
            )
            assert result.returncode == expected_exit, (args, result.stdout, result.stderr)
            return result.stdout

        assert cli("--version").strip() == f"dicomqc {expected}"
        cli("demo", "--output-dir", "scan-demo")
        assert (root / "scan-demo/dicomqc/dicomqc_mqc/dicomqc_summary_mqc.yaml").is_file()
        assert "DICOM metadata audit" in (root / "scan-demo/dicomqc/report.html").read_text()
        cli("demo", "--compare", "--output-dir", "comparison-demo")
        for name, errors in (("before", 3), ("after", 0)):
            report = root / f"comparison-demo/{name}.json"
            assert json.loads(report.read_text())["summary"]["errors"] == errors
            assert report.with_suffix(".csv").is_file()
            assert "Dataset comparison" in report.with_suffix(".html").read_text()
        for directory, code in (("candidate", 2), ("corrected", 0)):
            cli("compare", "comparison-demo/source", f"comparison-demo/{directory}",
                "--manifest", "comparison-demo/pairs.csv", "--json", f"{directory}.json",
                "--csv", f"{directory}.csv", "--html", f"{directory}.html", expected_exit=code)
            assert (root / f"{directory}.html").is_file()
        cli("demo", "--compare", "--output-dir", "comparison-demo", "--force")
    print(f"Installed dicomqc {expected}: scan demo, comparison demo, and comparisons passed.")


if __name__ == "__main__":
    main()
