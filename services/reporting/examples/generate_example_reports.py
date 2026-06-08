from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.reporting import (
    build_report_document,
    render_clinical_report_html,
    render_technical_report_html,
)


def main() -> None:
    root = Path(__file__).resolve().parent
    contract_path = root / "sample_reporting_contract.json"
    payload = json.loads(contract_path.read_text())
    document = build_report_document(payload)

    (root / "sample_report_document.json").write_text(json.dumps(document, indent=2))
    (root / "sample_clinical_report.html").write_text(render_clinical_report_html(document))
    (root / "sample_technical_report.html").write_text(render_technical_report_html(document))


if __name__ == "__main__":
    main()
