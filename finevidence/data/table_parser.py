"""Parse HTML filing tables into table chunks and simple metric candidates."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from io import StringIO
from pathlib import Path
from typing import Iterable

from finevidence.data.sec_filing_parser import RAW_FILINGS_ROOT, PROCESSED_ROOT, infer_ticker_and_year, iter_filing_paths
from finevidence.data.text_utils import write_jsonl


METRIC_ALIASES = {
    "revenue": (
        r"\bnet sales\b",
        r"\btotal net sales\b",
        r"\brevenue\b",
        r"\brevenues\b",
        r"\btotal revenues\b",
        r"\bnet revenue\b",
        r"\btotal net revenue\b",
    ),
    "gross_profit": (
        r"\bgross profit\b",
        r"\bgross margin\b",
    ),
}


def _require_pandas():
    try:
        import pandas as pd
    except ImportError as exc:
        raise ImportError("table_parser requires pandas. Install pandas to parse HTML tables.") from exc
    return pd


def _clean_cell(value: object) -> str:
    if value is None:
        return ""
    text = str(value).replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text)
    if text.lower() in {"nan", "none"}:
        return ""
    return text.strip()


def _flatten_columns(columns: object) -> list[str]:
    flattened: list[str] = []
    for column in columns:
        if isinstance(column, tuple):
            parts = [_clean_cell(part) for part in column if _clean_cell(part) and not str(part).startswith("Unnamed")]
            flattened.append(" | ".join(parts) if parts else "")
        else:
            text = _clean_cell(column)
            flattened.append("" if text.startswith("Unnamed") else text)
    return flattened


def _dataframe_to_record(df, table_id: str, table_index: int, source_path: Path) -> dict:
    ticker, fiscal_year = infer_ticker_and_year(source_path)
    normalized = df.copy()
    normalized.columns = _flatten_columns(normalized.columns)
    rows = [
        [_clean_cell(value) for value in row]
        for row in normalized.astype(object).itertuples(index=False, name=None)
    ]
    return {
        "table_id": table_id,
        "ticker": ticker,
        "fiscal_year": fiscal_year,
        "filing_type": "10-K",
        "table_index": table_index,
        "columns": list(normalized.columns),
        "rows": rows,
        "source_path": source_path.as_posix(),
    }


def parse_tables_in_file(path: str | Path) -> list[dict]:
    """Parse all HTML tables from one filing into JSON-serializable records."""

    pd = _require_pandas()
    source_path = Path(path)
    html = source_path.read_text(encoding="utf-8", errors="ignore")
    try:
        dataframes = pd.read_html(StringIO(html))
    except ValueError:
        dataframes = []

    ticker, fiscal_year = infer_ticker_and_year(source_path)
    records: list[dict] = []
    for table_index, dataframe in enumerate(dataframes):
        if dataframe.empty:
            continue
        table_id = f"{ticker}_{fiscal_year}_10K_table_{table_index:04d}"
        records.append(_dataframe_to_record(dataframe, table_id, table_index, source_path))
    return records


def parse_all_tables(raw_root: str | Path = RAW_FILINGS_ROOT) -> list[dict]:
    """Parse tables from every downloaded filing."""

    records: list[dict] = []
    for path in iter_filing_paths(raw_root):
        records.extend(parse_tables_in_file(path))
    return records


def parse_number(value: str) -> Decimal | None:
    """Parse common SEC table number formats."""

    text = _clean_cell(value)
    if not text or "%" in text:
        return None
    if text in {"-", "--", "—", "–"}:
        return None

    negative = text.startswith("(") and text.endswith(")")
    text = text.strip("()")
    text = text.replace("$", "").replace(",", "").replace(" ", "")
    text = re.sub(r"[^0-9.\-]", "", text)
    if not text or text in {"-", ".", "-."}:
        return None

    try:
        number = Decimal(text)
    except InvalidOperation:
        return None
    return -number if negative else number


def _json_value(number: Decimal) -> int | float | str:
    if number == number.to_integral_value():
        return int(number)
    return float(number)


def _extract_year(text: str) -> str | None:
    match = re.search(r"\b(20[0-9]{2})\b", text)
    return match.group(1) if match else None


def _is_change_column(column_name: str) -> bool:
    lowered = column_name.lower()
    return any(token in lowered for token in ("change", "percent", "percentage", "%"))


def _column_years(table: dict, header_scan_rows: int = 5) -> dict[int, str]:
    years: dict[int, str] = {}

    for column_index, column_name in enumerate(table.get("columns", [])):
        if _is_change_column(column_name):
            continue
        year = _extract_year(column_name)
        if year:
            years[column_index] = year

    for row in table.get("rows", [])[:header_scan_rows]:
        for column_index, cell in enumerate(row):
            if _is_change_column(cell):
                continue
            year = _extract_year(cell)
            if year:
                years.setdefault(column_index, year)

    return years


def _match_metric(label: str) -> str | None:
    lowered = label.lower()
    if any(token in lowered for token in ("percentage", "percent", "%", "ratio", "rate")):
        return None
    for metric, patterns in METRIC_ALIASES.items():
        for pattern in patterns:
            if re.search(pattern, lowered):
                return metric
    return None


def extract_metric_records(table_records: Iterable[dict]) -> list[dict]:
    """Extract simple revenue and gross profit candidate records from tables."""

    metric_records: list[dict] = []
    for table in table_records:
        columns = table.get("columns", [])
        rows = table.get("rows", [])
        column_years = _column_years(table)
        for row_index, row in enumerate(rows):
            if not row:
                continue

            label_parts = [cell for cell in row[:2] if cell and not parse_number(cell)]
            label = " ".join(label_parts) if label_parts else row[0]
            metric = _match_metric(label)
            if not metric:
                continue

            for column_index, cell in enumerate(row[1:], start=1):
                number = parse_number(cell)
                if number is None:
                    continue

                column_name = columns[column_index] if column_index < len(columns) else ""
                if _is_change_column(column_name):
                    continue

                period = column_years.get(column_index)
                if period is None:
                    continue

                metric_records.append(
                    {
                        "ticker": table["ticker"],
                        "fiscal_year": table["fiscal_year"],
                        "period": period,
                        "metric": metric,
                        "value": _json_value(number),
                        "unit": "as_reported",
                        "source_table_id": table["table_id"],
                        "source_row_index": row_index,
                        "source_column_index": column_index,
                        "source_path": table["source_path"],
                    }
                )

    return metric_records


def parse_tables(
    raw_root: str | Path = RAW_FILINGS_ROOT,
    processed_root: str | Path = PROCESSED_ROOT,
) -> tuple[list[dict], list[dict]]:
    """Parse all tables and write table chunks plus metric candidate records."""

    table_records = parse_all_tables(raw_root)
    metric_records = extract_metric_records(table_records)
    processed_path = Path(processed_root)
    write_jsonl(table_records, processed_path / "table_chunks.jsonl")
    write_jsonl(metric_records, processed_path / "metric_records.jsonl")
    return table_records, metric_records


def main() -> None:
    tables, metrics = parse_tables()
    print(f"parsed_tables={len(tables)} metric_records={len(metrics)}")


if __name__ == "__main__":
    main()
