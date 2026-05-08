"""
panels/auto_panels.py — автоформирование щитов по разделам смежников.

Принимает список потребителей (из parse_dwg_assignment или parse_load_table)
и формирует структуру panels[] для project.json.

Правила:
  - Каждый раздел получает свой щит: ОВ→ЩОВ-1, ВК→ЩВК-1 и т.д.
  - Потребители кат.1 с дымоудалением → ЩДУ-1 (has_avr=True)
  - Потребители кат.1 пожаротушения → ЩПС-1 (has_avr=True)
  - Прочие кат.1 → отдельный щит с АВР (has_avr=True)
  - Резервные агрегаты (reserve=True) входят в щит, но не суммируются в нагрузку
  - При повторном вызове: новые потребители добавляются, существующие не перезаписываются
"""

# ── Метаданные щитов по panel_id ─────────────────────────────────────────────
_PANEL_META = {
    "ЩОВ":  {"name": "Щит отопления",              "type": "heating",      "category_pue": 2, "has_avr": False},
    "ЩВК":  {"name": "Щит вентиляции",             "type": "ventilation",  "category_pue": 2, "has_avr": False},
    "ЩКВ":  {"name": "Щит кондиционирования",      "type": "hvac",         "category_pue": 3, "has_avr": False},
    "ЩТХ":  {"name": "Щит технологический",        "type": "technology",   "category_pue": 3, "has_avr": False},
    "ЩДУ":  {"name": "Щит дымоудаления",           "type": "smoke_exhaust","category_pue": 1, "has_avr": True},
    "ЩПС":  {"name": "Щит пожарной безопасности",  "type": "firefighting", "category_pue": 1, "has_avr": True},
    "ЩО":   {"name": "Щит освещения",              "type": "lighting",     "category_pue": 3, "has_avr": False},
    "ЩС":   {"name": "Щит силовой",                "type": "power",        "category_pue": 3, "has_avr": False},
    "ШУНО": {"name": "Шкаф управления наружным освещением", "type": "outdoor_lighting", "category_pue": 3, "has_avr": False},
}

# Раздел + категория → panel_id-префикс для нестандартных случаев
_SECTION_TO_PANEL_PREFIX = {
    "ОВ":  "ЩОВ",
    "ВК":  "ЩВК",
    "КВ":  "ЩКВ",
    "ТХ":  "ЩТХ",
    "ЭОМ": "ЩС",
    "ЭН":  "ШУНО",
}


def _get_panel_prefix(panel_id: str) -> str:
    """Извлекает префикс из panel_id. 'ЩОВ-1' → 'ЩОВ', 'ЩДУ-2' → 'ЩДУ'."""
    return panel_id.rsplit("-", 1)[0] if "-" in panel_id else panel_id


def _get_panel_number(panel_id: str) -> int:
    """Извлекает номер из panel_id. 'ЩОВ-1' → 1, 'ЩОВ-2' → 2."""
    parts = panel_id.rsplit("-", 1)
    try:
        return int(parts[-1]) if len(parts) > 1 else 1
    except ValueError:
        return 1


def _next_panel_id(prefix: str, existing_ids: set) -> str:
    """Генерирует следующий свободный id: ЩОВ-1, ЩОВ-2, ..."""
    n = 1
    while f"{prefix}-{n}" in existing_ids:
        n += 1
    return f"{prefix}-{n}"


def _make_panel(panel_id: str) -> dict:
    """Создаёт пустой объект щита."""
    prefix = _get_panel_prefix(panel_id)
    meta = _PANEL_META.get(prefix, {
        "name":         f"Щит {prefix}",
        "type":         "other",
        "category_pue": 3,
        "has_avr":      False,
    })
    num = _get_panel_number(panel_id)
    return {
        "id":           panel_id,
        "name":         f"{meta['name']} №{num}",
        "type":         meta["type"],
        "category_pue": meta["category_pue"],
        "has_avr":      meta["has_avr"],
        "cable": {
            "mark":        "ВВГнг-LS",
            "cores":       4,
            "install":     "лоток",
            "length_m":    20,
            "section_mm2": None,
        },
        "breaker": {},
        "consumers": [],
    }


def _resolve_panel_id(consumer: dict, existing_ids: set) -> str:
    """
    Определяет panel_id для потребителя.
    Приоритет: явный panel_id из потребителя → автогенерация по разделу.
    """
    panel_id = consumer.get("panel_id") or ""
    if panel_id:
        # Если щит с таким id ещё не существует — он будет создан
        return panel_id

    # Автогенерация по разделу
    section = consumer.get("section", "ТХ")
    prefix = _SECTION_TO_PANEL_PREFIX.get(section, "ЩТХ")
    return _next_panel_id(prefix, existing_ids)


def auto_assign_panels(consumers: list,
                        existing_panels: list | None = None) -> list[dict]:
    """
    Формирует список щитов из потребителей.

    Args:
        consumers:       список потребителей (из parse_dwg_assignment / parse_load_table)
        existing_panels: существующие щиты из project.json (для режима дополнения)

    Returns:
        list[dict] — щиты в формате panels[] для вставки в feeder или vru
    """
    # Индекс существующих щитов
    panels: dict[str, dict] = {}
    if existing_panels:
        for p in existing_panels:
            panels[p["id"]] = p

    existing_consumer_ids: set[str] = set()
    for p in panels.values():
        for c in p.get("consumers", []):
            existing_consumer_ids.add(c["id"])

    for consumer in consumers:
        # Пропускаем уже существующих потребителей (режим дополнения)
        if consumer["id"] in existing_consumer_ids:
            continue

        panel_id = _resolve_panel_id(consumer, set(panels.keys()))

        if panel_id not in panels:
            panels[panel_id] = _make_panel(panel_id)

        # Категория щита = минимум категорий его потребителей
        cat = consumer.get("category_pue", 3)
        if cat < panels[panel_id]["category_pue"]:
            panels[panel_id]["category_pue"] = cat
            # Кат.1 → включаем АВР
            if cat == 1:
                panels[panel_id]["has_avr"] = True

        panels[panel_id]["consumers"].append(consumer)
        existing_consumer_ids.add(consumer["id"])

    return list(panels.values())


def panels_summary(panels: list) -> None:
    """Выводит сводку щитов в консоль."""
    if not panels:
        print("Щиты не сформированы")
        return
    print(f"\nСформировано щитов: {len(panels)}\n")
    header = f"{'Щит':<12} {'Наименование':<35} {'Кат':<4} {'АВР':<5} {'Потребителей'}"
    print(header)
    print("-" * 70)
    for p in panels:
        avr = "Да" if p["has_avr"] else "-"
        n_consumers = len(p["consumers"])
        n_reserve = sum(1 for c in p["consumers"] if c.get("reserve"))
        note = f"{n_consumers} ({n_reserve} резерв)" if n_reserve else str(n_consumers)
        print(f"{p['id']:<12} {p['name'][:35]:<35} {p['category_pue']:<4} {avr:<5} {note}")
