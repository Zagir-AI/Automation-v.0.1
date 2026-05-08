"""
parsers/parse_estimate.py — парсинг сметы или КП поставщика из Excel/CSV.

Поддерживаемые форматы:
  - Excel (.xlsx, .xls) — стандартная смета или КП поставщика
  - CSV — любой разделитель (, ; \t)

Возвращает список позиций:
  [{"name": str, "mark": str, "qty": float, "unit": str, "price": float, "note": str}]
"""

import re
from pathlib import Path


# ── Ключевые слова для распознавания колонок ─────────────────────────
_COL_NAME_KEYS   = ["наименование", "name", "номенклатура", "позиция", "description"]
_COL_MARK_KEYS   = ["марка", "обозначение", "артикул", "mark", "code", "шифр"]
_COL_QTY_KEYS    = ["кол", "количество", "qty", "count", "объем", "объём"]
_COL_UNIT_KEYS   = ["ед", "единица", "unit", "мер"]
_COL_PRICE_KEYS  = ["цена", "стоимость", "price", "cost", "руб"]
_COL_NOTE_KEYS   = ["примечание", "note", "комментарий", "comment"]


def _detect_column(header: str, key_list: list) -> bool:
    h = header.strip().lower()
    return any(k in h for k in key_list)


def _find_columns(headers: list) -> dict:
    """Находит индексы нужных колонок по заголовкам."""
    cols = {"name": None, "mark": None, "qty": None,
            "unit": None, "price": None, "note": None}
    for i, h in enumerate(headers):
        if h is None:
            continue
        h_str = str(h)
        if cols["name"]  is None and _detect_column(h_str, _COL_NAME_KEYS):
            cols["name"] = i
        elif cols["mark"] is None and _detect_column(h_str, _COL_MARK_KEYS):
            cols["mark"] = i
        elif cols["qty"]  is None and _detect_column(h_str, _COL_QTY_KEYS):
            cols["qty"] = i
        elif cols["unit"] is None and _detect_column(h_str, _COL_UNIT_KEYS):
            cols["unit"] = i
        elif cols["price"] is None and _detect_column(h_str, _COL_PRICE_KEYS):
            cols["price"] = i
        elif cols["note"] is None and _detect_column(h_str, _COL_NOTE_KEYS):
            cols["note"] = i
    return cols


def _row_to_item(row: list, cols: dict) -> dict | None:
    """Преобразует строку таблицы в словарь позиции."""
    def get(idx):
        if idx is None or idx >= len(row):
            return ""
        val = row[idx]
        return "" if val is None else str(val).strip()

    name = get(cols["name"])
    if not name or len(name) < 2:
        return None

    # Пропускаем строки-заголовки и разделители
    if any(k in name.lower() for k in ["наименование", "итого", "всего", "name", "итог"]):
        return None

    qty_str = get(cols["qty"])
    price_str = get(cols["price"])

    def parse_float(s: str) -> float:
        s = re.sub(r"[^\d.,]", "", s).replace(",", ".")
        try:
            return float(s)
        except ValueError:
            return 0.0

    return {
        "name":  name,
        "mark":  get(cols["mark"]),
        "qty":   parse_float(qty_str),
        "unit":  get(cols["unit"]) or "шт.",
        "price": parse_float(price_str),
        "note":  get(cols["note"]),
    }


def _parse_excel(path: str) -> list:
    """Парсит Excel-файл (.xlsx/.xls)."""
    try:
        import openpyxl
        wb = openpyxl.load_workbook(path, data_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
    except ImportError:
        try:
            import xlrd
            wb = xlrd.open_workbook(path)
            ws = wb.sheet_by_index(0)
            rows = [tuple(ws.row_values(i)) for i in range(ws.nrows)]
        except ImportError:
            return []

    if not rows:
        return []

    # Ищем строку заголовков (первые 10 строк)
    header_row_idx = 0
    for i, row in enumerate(rows[:10]):
        row_str = [str(c).lower() if c else "" for c in row]
        if any(k in " ".join(row_str) for k in ["наименование", "name", "марка"]):
            header_row_idx = i
            break

    headers = [str(c) if c else "" for c in rows[header_row_idx]]
    cols = _find_columns(headers)

    items = []
    for row in rows[header_row_idx + 1:]:
        item = _row_to_item(list(row), cols)
        if item:
            items.append(item)

    return items


def _parse_csv(path: str) -> list:
    """Парсит CSV-файл с автоопределением разделителя."""
    import csv
    content = Path(path).read_text(encoding="utf-8-sig", errors="ignore")

    # Определяем разделитель
    sep = ","
    for s in [";", "\t", ","]:
        if content.count(s) > content.count(sep):
            sep = s

    reader = csv.reader(content.splitlines(), delimiter=sep)
    rows = list(reader)

    if not rows:
        return []

    # Ищем заголовок
    header_idx = 0
    for i, row in enumerate(rows[:10]):
        row_str = " ".join(row).lower()
        if any(k in row_str for k in ["наименование", "name", "марка"]):
            header_idx = i
            break

    cols = _find_columns(rows[header_idx])
    items = []
    for row in rows[header_idx + 1:]:
        item = _row_to_item(row, cols)
        if item:
            items.append(item)

    return items


def parse_file(path: str) -> list:
    """
    Универсальный парсер сметы/КП.
    Поддерживает .xlsx, .xls, .csv
    Возвращает список позиций: [{"name", "mark", "qty", "unit", "price", "note"}]
    """
    p = Path(path)
    suffix = p.suffix.lower()

    if suffix in (".xlsx", ".xls"):
        items = _parse_excel(path)
    elif suffix == ".csv":
        items = _parse_csv(path)
    else:
        # Пробуем как CSV
        items = _parse_csv(path)

    return items


def print_parsed_items(items: list) -> None:
    """Вывод распарсенных позиций в консоль."""
    if not items:
        print("Позиции не найдены")
        return
    print(f"\nНайдено позиций: {len(items)}\n")
    fmt = f"{'№':<4} {'Наименование':<40} {'Марка':<20} {'Кол.':<8} {'Ед.':<5} {'Цена':<10}"
    print(fmt)
    print("-" * 90)
    for i, item in enumerate(items, 1):
        print(
            f"{i:<4} {item['name'][:40]:<40} {item['mark'][:20]:<20} "
            f"{item['qty']:<8} {item['unit']:<5} {item['price']:<10.2f}"
        )
