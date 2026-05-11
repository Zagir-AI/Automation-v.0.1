"""
parsers/compare_kp.py — сверка спецификации проекта с КП поставщика.

Алгоритм:
  1. Получить плоский список позиций спецификации через _build_spec_data().
  2. Получить список позиций КП через parse_file().
  3. Сопоставить по нормализованной марке (strip + lower).
  4. Каждой позиции спецификации присвоить статус:
       - "found"     — найдена в КП  (берём цену оттуда)
       - "not_found" — отсутствует в КП
  5. Дополнительно вернуть позиции, которые есть в КП, но отсутствуют
     в спецификации:
       - "extra_in_kp"

Возвращает плоский список словарей с полями:
  pos, mark, name, qty, unit, price, amount, kp_mark, status

Сопоставление — строгое, по mark (без fuzzy-match).
"""

from __future__ import annotations

import math


# ── нормализация марки ────────────────────────────────────────────────────────

def _normalize(s: str | None) -> str:
    """strip + lower, пустая строка для None/пусто."""
    if not s:
        return ""
    return str(s).strip().lower()


# ── сборка плоской спецификации ───────────────────────────────────────────────

def _flatten_spec(spec: dict) -> list[dict]:
    """
    Преобразует структуру _build_spec_data() в плоский список позиций
    с полями mark/name/qty/unit.
    """
    items: list[dict] = []

    # 1. Автоматы
    for des in spec.get("breakers", {}).values():
        items.append({
            "mark": des.get("mark", ""),
            "name": des.get("name", ""),
            "qty":  float(des.get("count", 0)),
            "unit": "шт.",
        })

    # 2. Кабели
    for (mark, cores, section), info in spec.get("cables", {}).items():
        length = float(info.get("length_m", 0))
        items.append({
            "mark": f"{mark} {cores}×{section}",
            "name": f"Кабель {mark} {cores}×{section} мм²",
            "qty":  float(math.ceil(length)),
            "unit": "м",
        })

    # 3. Аппаратура / электроустановочные изделия
    for it in spec.get("hardware", []):
        items.append({
            "mark": it.get("mark", ""),
            "name": it.get("name", ""),
            "qty":  float(it.get("qty", 0)),
            "unit": it.get("unit", "шт."),
        })

    # 4. Прочие материалы (extra_items из project.json)
    for it in spec.get("extra", []):
        items.append({
            "mark": it.get("mark", ""),
            "name": it.get("name", ""),
            "qty":  float(it.get("qty", 0)),
            "unit": it.get("unit", "шт."),
        })

    return items


# ── публичная функция ────────────────────────────────────────────────────────

def compare_kp(project: dict, kp_path: str) -> list[dict]:
    """
    Сверка спецификации проекта с КП поставщика.

    Args:
        project: project.json как dict (с заполненным _results)
        kp_path: путь к Excel/CSV-файлу КП

    Returns:
        list[dict] — строки сверки. Поля каждой строки:
          pos       (int)   — порядковый номер
          mark      (str)   — марка позиции спецификации (или "" для extra_in_kp)
          name      (str)   — наименование
          qty       (float) — количество
          unit      (str)   — единица измерения
          price     (float) — цена за единицу (из КП, 0 если не найдено)
          amount    (float) — сумма qty * price
          kp_mark   (str)   — марка из КП (если найдено / для extra_in_kp)
          status    (str)   — "found" | "not_found" | "extra_in_kp"
    """
    # Импортируем строго локально, чтобы избежать циклических зависимостей
    from docs.gen_spec import _build_spec_data
    from parsers.parse_estimate import parse_file

    spec     = _build_spec_data(project)
    spec_items = _flatten_spec(spec)

    kp_items = parse_file(kp_path) or []
    kp_index: dict[str, dict] = {}
    for it in kp_items:
        key = _normalize(it.get("mark"))
        if not key:
            continue
        # При повторе марок берём первое вхождение
        kp_index.setdefault(key, it)

    matched_keys: set[str] = set()
    rows: list[dict] = []
    pos = 0

    for sp in spec_items:
        pos += 1
        key = _normalize(sp.get("mark"))
        kp_item = kp_index.get(key)

        if kp_item is not None and key:
            price = float(kp_item.get("price", 0) or 0)
            qty   = float(sp.get("qty", 0) or 0)
            rows.append({
                "pos":     pos,
                "mark":    sp.get("mark", ""),
                "name":    sp.get("name", ""),
                "qty":     qty,
                "unit":    sp.get("unit", ""),
                "price":   price,
                "amount":  round(qty * price, 2),
                "kp_mark": kp_item.get("mark", ""),
                "status":  "found",
            })
            matched_keys.add(key)
        else:
            rows.append({
                "pos":     pos,
                "mark":    sp.get("mark", ""),
                "name":    sp.get("name", ""),
                "qty":     float(sp.get("qty", 0) or 0),
                "unit":    sp.get("unit", ""),
                "price":   0.0,
                "amount":  0.0,
                "kp_mark": "",
                "status":  "not_found",
            })

    # Позиции, которые есть в КП, но не в спецификации
    for it in kp_items:
        key = _normalize(it.get("mark"))
        if not key or key in matched_keys:
            continue
        pos += 1
        qty   = float(it.get("qty", 0) or 0)
        price = float(it.get("price", 0) or 0)
        rows.append({
            "pos":     pos,
            "mark":    "",
            "name":    it.get("name", ""),
            "qty":     qty,
            "unit":    it.get("unit", ""),
            "price":   price,
            "amount":  round(qty * price, 2),
            "kp_mark": it.get("mark", ""),
            "status":  "extra_in_kp",
        })

    return rows
