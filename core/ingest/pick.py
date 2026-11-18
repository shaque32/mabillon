"""Which importer reads a phone report file: by its suffix, and for .zip and .xlsx by content.

.pdf is a Cellebrite PDF report, .ufdr a Cellebrite UFDR package, .xml a Magnet AXIOM XML
report. A .zip is an iLEAPP or ALEAPP output folder when it holds a LEAPP manifest
(core.ingest.leapp.looks_like_leapp_zip), else a Cellebrite UFDR package. An .xlsx is a Magnet
AXIOM Excel report when it carries AXIOM's marks (core.ingest.axiom.looks_like_axiom_workbook),
else a Cellebrite Excel report.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

REPORT_SUFFIXES = (".xlsx", ".pdf", ".ufdr", ".zip", ".xml")


def report_importer(path: Path) -> Any:
    """The importer class for a report file (an EvidenceImporter, constructed with
    `source_id`, `now` and `date_order`)."""
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        from core.ingest.cellebrite_pdf import CellebritePdfImporter

        return CellebritePdfImporter
    if suffix == ".zip":
        from core.ingest.leapp import LeappImporter, looks_like_leapp_zip

        if looks_like_leapp_zip(path):
            return LeappImporter
    if suffix in (".ufdr", ".zip"):
        from core.ingest.ufdr import UfdrImporter

        return UfdrImporter
    from core.ingest.axiom import AxiomImporter, looks_like_axiom_workbook

    if suffix == ".xml" or (suffix == ".xlsx" and looks_like_axiom_workbook(path)):
        return AxiomImporter
    from core.ingest.cellebrite_excel import CellebriteExcelImporter

    return CellebriteExcelImporter
