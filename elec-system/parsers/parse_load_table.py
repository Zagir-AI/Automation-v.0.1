"""
parsers/parse_load_table.py — импорт таблицы нагрузок Excel от смежника.

Типовые заголовки (по ТЗ):
  Наименование | Pуст, кВт | Ки | cosφ | Категория | Марка кабеля | Примечание

Нестандартные заголовки — через parsers/column_map.json.
Поддерживает .xlsx, .xls, .csv.

Возвращает список потребителей в формате project.json (consumers[]).
"""

import json
import re
from pathlib import Path


# ── Загрузка маппинга колонок ────────────────────────────────────────────────
def _load_column_map() -> dict:
    map_path = Path(__file__).parent / "column_map.json"
    if map_path.exists():
        with open(map_path, encoding="utf-8") as f:
            data = json.load(f)
        return {k: v for k, v in data.items() if not k.startswith("_")}
    # Дефолтный маппинг если файл не найден
    return {
        "name":          ["наименование"],
        "power_kw":      ["pуст", "мощность"],
        "demand_factor": ["ки", "кс"],
        "cos_phi":       ["cos"],
        "category":      ["категория", "кат"],
        "cable_mark":    ["марка"],
        "note":          ["примечание"],
        "quantity":      ["кол"],
        "section":       ["раздел"],
        "phases":        ["фазы"],
    }


def _detect_col(header: str, keywords: list[str]) -> bool:
    h = str(header).strip().lower()
    return any(kw in h for kw in keywords)


def _find_columns(headers: list, col_map: dict) -> dict:
    """Находит индексы колонок по заголовкам."""
    result = {key: None for key in col_map}
    for i, h in enumerate(headers):
        if h is None:
            continue
        for key, keywords in col_map.items():
            if result[key] is None and _detect_col(str(h), keywords):
                result[key] = i
    return result


def _parse_float(s) -> float | None:
    if s is None:
        return None
    cleaned = re.sub(r"[^\d.,]", "", str(s)).replace(",", ".")
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _parse_int(s) -> int | None:
    v = _parse_float(s)
    return int(v) if v is not None else None


def _is_skip_row(name: str) -> bool:
    """Пропускаем строки-заголовки, итоги, разделители."""
    n = name.strip().lower()
    if len(n) < 2:
        return True
    skip_words = ["итого", "всего", "итог", "total", "наименование",
                  "name", "№", "п/п", "примечание"]
    return any(w in n for w in skip_words)


def _row_to_consumer(row: list, cols: dict, row_idx: int,
                      default_section: str) -> dict | None:
    """Преобразует строку таблицы в потребителя."""
    def get(key):
        idx = cols.get(key)
        if idx is None or idx >= len(row):
            return None
        val = row[idx]
        return str(val).strip() if val is not None else None

    name = get("name")
    if not name or _is_skip_row(name):
        return None

    power_kw = _parse_float(get("power_kw"))
    if power_kw is None or power_kw <= 0:
        return None

    # Количество единиц (по умолчанию 1)
    qty = _parse_int(get("quantity")) or 1

    demand_factor = _parse_float(get("demand_factor"))
    if demand_factor is None or not (0 < demand_factor <= 1.0):
        demand_factor = 0.75  # fallback

    cos_phi = _parse_float(get("cos_phi"))
    if cos_phi is None or not (0 < cos_phi <= 1.0):
        cos_phi = 0.85  # fallback

    category_raw = _parse_int(get("category"))
    category = category_raw if category_raw in (1, 2, 3) else 3

    cable_mark = get("cable_mark") or None
    note       = get("note") or ""
    section    = get("section") or default_section
    phases_raw = _parse_int(get("phases"))
    phases     = phases_raw if phases_raw in (1, 3) else 3

    consumer_id = f"ТН-{row_idx:03d}"

    consumer = {
        "id":                  consumer_id,
        "name":                name,
        "type":                "other",
        "section":             section,
        "power_kw":            round(power_kw * qty, 2),
        "demand_factor":       demand_factor,
        "cos_phi":             cos_phi,
        "eta":                 1.0,
        "phases":              phases,
        "voltage_class":       "0.4kV",
        "category_pue":        category,
        "reserve":             False,
        "reserve_scheme":      None,
        "panel_id":            None,
        "cable_mark_override": cable_mark,
        "source":              "table",
        "note":                note,
        "cable": {
            "mark":        cable_mark or "ВВГнг-LS",
            "install":     "лоток",
            "length_m":    10,
            "section_mm2": None,
        },
        "breaker": {},
    }
    return consumer


def _read_excel_rows(path: str) -> list[list]:
    """Читает строки из Excel-файла."""
    import openpyxl
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb.active
    return [list(row) for row in ws.iter_rows(values_only=True)]


def _read_csv_rows(path: str) -> list[list]:
    """Читает строки из CSV с автоопределением разделителя."""
    import csv
    content = Path(path).read_text(encoding="utf-8-sig", errors="ignore")
    sep = max([";", "\t", ","], key=content.count)
    reader = csv.reader(content.splitlines(), delimiter=sep)
    return [row for row in reader]


def _find_header_row(rows: list[list], col_map: dict) -> int:
    """Ищет строку с заголовками в первых 15 строках.
    Требует совпадения хотя бы по 2 ключам, одним из которых должен быть 'name'.
    """
    name_keywords = col_map.get("name", ["наименование"])
    for i, row in enumerate(rows[:15]):
        row_text = " ".join(str(c).lower() for c in row if c)
        # Обязательно: колонка с наименованием
        if not any(kw in row_text for kw in name_keywords):
            continue
        # Дополнительно: хотя бы ещё одна колонка
        other_keywords = [kw for key, kws in col_map.items()
                          if key != "name" for kw in kws]
        if any(kw in row_text for kw in other_keywords):
            return i
    return 0


def parse_load_table(xlsx_path: str,
                     section_code: str = "ТХ") -> list[dict]:
    """
    Парсит таблицу нагрузок Excel/CSV от смежника.

    Распознаёт заголовки через column_map.json (поддержка нестандартных форм).
    Строки без наименования или мощности пропускаются.
    Итоговые строки ("Итого", "Всего") пропускаются автоматически.

    Args:
        xlsx_path:    путь к файлу (.xlsx, .xls, .csv)
        section_code: код раздела по умолчанию (если колонки "Раздел" нет)

    Returns:
        list[dict] — потребители в формате consumers[]
    """
    path = Path(xlsx_path)
    if not path.exists():
        raise FileNotFoundError(f"Файл не найден: {path}")

    suffix = path.suffix.lower()
    try:
        if suffix in (".xlsx", ".xls"):
            rows = _read_excel_rows(str(path))
        else:
            rows = _read_csv_rows(str(path))
    except ImportError:
        raise ImportError("Установи openpyxl: pip install openpyxl")

    if not rows:
        return []

    col_map = _load_column_map()
    header_idx = _find_header_row(rows, col_map)
    headers = rows[header_idx]
    cols = _find_columns(headers, col_map)

    if cols.get("name") is None and cols.get("power_kw") is None:
        raise ValueError(
            f"Не найдены обязательные колонки (Наименование, Pуст). "
            f"Проверьте заголовки или добавьте маппинг в column_map.json.\n"
            f"Найденные заголовки: {[str(h) for h in headers if h]}"
        )

    consumers = []
    for row_idx, row in enumerate(rows[header_idx + 1:], start=1):
        row = [c for c in row]  # копия
        consumer = _row_to_consumer(row, cols, row_idx, section_code)
        if consumer:
            consumers.append(consumer)

    return consumers


def print_parsed_consumers(consumers: list) -> None:
    """Вывод потребителей в консоль."""
    if not consumers:
        print("Потребители не найдены")
        return
    print(f"\nНайдено потребителей: {len(consumers)}\n")
    header = f"{'ID':<10} {'Наименование':<32} {'P,кВт':<8} {'Ки':<6} {'cosφ':<6} {'Кат':<4} {'Кабель'}"
    print(header)
    print("-" * 80)
    for c in consumers:
        print(
            f"{c['id']:<10} {c['name'][:32]:<32} {c['power_kw']:<8.2f} "
            f"{c['demand_factor']:<6.2f} {c['cos_phi']:<6.3f} "
            f"{c['category_pue']:<4} {c['cable_mark_override'] or '-'}"
        )
