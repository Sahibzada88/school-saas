"""CSV generation: always in memory / streamed per request, never written to disk."""
import csv
import io
import re
from collections.abc import Iterable

from django.http import StreamingHttpResponse

from apps.core.exceptions import ExportTooLarge

MAX_CSV_ROWS = 20_000  # serverless budget: bigger exports must be narrowed (class, section, dates)
_FORMULA_START = ("=", "+", "-", "@", "\t", "\r")


def safe_cell(value):
    """CSV/Excel formula injection guard: a cell starting with = + - @ would be executed by spreadsheet apps."""
    if value is None:
        return ""
    if isinstance(value, str) and value.startswith(_FORMULA_START):
        return "'" + value
    return value


def safe_filename(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("_.") or "export"


class _Echo:
    def write(self, value):
        return value


class CSVExportService:
    @staticmethod
    def respond(filename: str, header: list[str], rows: Iterable, *, count: int | None = None) -> StreamingHttpResponse:
        if count is not None and count > MAX_CSV_ROWS:
            raise ExportTooLarge()
        writer = csv.writer(_Echo())

        def stream():
            yield "\ufeff"  # BOM so Excel reads UTF-8 names correctly
            yield writer.writerow(header)
            for index, row in enumerate(rows):
                if index >= MAX_CSV_ROWS:
                    break
                yield writer.writerow([safe_cell(cell) for cell in row])

        response = StreamingHttpResponse(stream(), content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="{safe_filename(filename)}.csv"'
        response["Cache-Control"] = "no-store"
        return response

    @staticmethod
    def to_string(header: list[str], rows: Iterable) -> str:
        """For tests and small payloads."""
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(header)
        for row in rows:
            writer.writerow([safe_cell(cell) for cell in row])
        return buffer.getvalue()
