"""Shared CSV upload parsing for bulk imports. Strict on purpose: size/row caps, UTF-8 only, header check, and the
caller validates every row BEFORE anything is written (dry run), so a bad file never half-imports."""
import csv
import io
from dataclasses import dataclass, field

from rest_framework.exceptions import ValidationError

MAX_IMPORT_BYTES = 1_000_000
MAX_IMPORT_ROWS = 500


@dataclass
class ImportReport:
    total: int = 0
    created: int = 0
    dry_run: bool = True
    errors: list = field(default_factory=list)  # [{"row": 3, "errors": ["..."]}]

    def add_error(self, row: int, message: str) -> None:
        for entry in self.errors:
            if entry["row"] == row:
                entry["errors"].append(message)
                return
        self.errors.append({"row": row, "errors": [message]})

    def as_dict(self) -> dict:
        return {"total": self.total, "created": self.created, "dry_run": self.dry_run, "ok": not self.errors, "errors": sorted(self.errors, key=lambda e: e["row"])}


def read_csv_rows(uploaded, required: list[str]) -> list[tuple[int, dict]]:
    """Returns [(spreadsheet_row_number, {column: value})]. Row 1 is the header, so data starts at row 2."""
    if uploaded is None:
        raise ValidationError({"file": ["Upload a CSV file."]})
    raw = uploaded.read(MAX_IMPORT_BYTES + 1)
    if len(raw) > MAX_IMPORT_BYTES:
        raise ValidationError({"file": [f"The file is too large (max {MAX_IMPORT_BYTES // 1000} KB). Split it into smaller files."]})
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValidationError({"file": ["Save the file as CSV (UTF-8) and try again."]}) from exc
    reader = csv.DictReader(io.StringIO(text))
    headers = [(h or "").strip().lower() for h in (reader.fieldnames or [])]
    missing = [c for c in required if c not in headers]
    if missing:
        raise ValidationError({"file": [f"Missing column(s): {', '.join(missing)}. Download the template to see the expected columns."]})
    rows = []
    for index, record in enumerate(reader, start=2):
        row = {(k or "").strip().lower(): (v or "").strip() for k, v in record.items() if k is not None}
        if not any(row.values()):
            continue  # blank line
        rows.append((index, row))
        if len(rows) > MAX_IMPORT_ROWS:
            raise ValidationError({"file": [f"Too many rows (max {MAX_IMPORT_ROWS} per file). Split the file."]})
    if not rows:
        raise ValidationError({"file": ["The file has no data rows."]})
    return rows
