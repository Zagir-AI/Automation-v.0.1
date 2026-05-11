"""
data/spec_templates.py — типовые позиции спецификации по типу щита.

Используется в docs/gen_spec.py для добавления стандартных материалов
(DIN-рейки, шины, клеммы) которые не рассчитываются автоматически.

Структура:
  PANEL_TEMPLATE_ITEMS["all"]        — позиции для любого щита
  PANEL_TEMPLATE_ITEMS["<type>"]     — дополнительные позиции по типу щита

Поля позиции:
  name      — наименование
  mark      — марка/обозначение (можно оставить пустым)
  unit      — единица измерения
  qty_expr  — выражение для расчёта количества:
               "1"              — 1 шт. на щит
               "breakers"       — по числу автоматов
               "consumers"      — по числу потребителей
               float            — фиксированное число
  note      — примечание (необязательно)
  section   — раздел спецификации (default: "hardware")
"""

PANEL_TEMPLATE_ITEMS: dict[str, list[dict]] = {

    # ── Позиции для ЛЮБОГО щита ──────────────────────────────────────────
    "all": [
        {
            "name":     "Рейка монтажная DIN (TS-35)",
            "mark":     "TDM SQ0804-0022",
            "unit":     "м",
            "qty_expr": "1.0",
            "note":     "L=1м, по факту",
            "section":  "hardware",
        },
        {
            "name":     "Шина нулевая N в корпусе (на DIN)",
            "mark":     "ШНИ-6×9-12-D-C",
            "unit":     "шт.",
            "qty_expr": "1",
            "note":     "",
            "section":  "hardware",
        },
        {
            "name":     "Шина заземления PE в корпусе (на DIN)",
            "mark":     "ШНИ-6×9-12-D-J",
            "unit":     "шт.",
            "qty_expr": "1",
            "note":     "",
            "section":  "hardware",
        },
        {
            "name":     "Клеммная колодка вводная",
            "mark":     "ЗВИ-20 нг LS",
            "unit":     "шт.",
            "qty_expr": "4",
            "note":     "на ввод (L1, L2, L3, N)",
            "section":  "hardware",
        },
    ],

    # ── Щит освещения ────────────────────────────────────────────────────
    "lighting": [
        {
            "name":     "Выключатель нагрузки (рубильник) 3P",
            "mark":     "ВН-32 3P 40А IEK",
            "unit":     "шт.",
            "qty_expr": "1",
            "note":     "ввод щита",
            "section":  "breakers",
        },
    ],

    # ── Щит силовой (розеточный) ─────────────────────────────────────────
    "power": [
        {
            "name":     "Выключатель нагрузки (рубильник) 3P",
            "mark":     "ВН-32 3P 63А IEK",
            "unit":     "шт.",
            "qty_expr": "1",
            "note":     "ввод щита",
            "section":  "breakers",
        },
        {
            "name":     "УЗО 2P 25А 30мА тип AC",
            "mark":     "АВДТ32 IEK",
            "unit":     "шт.",
            "qty_expr": "consumers",
            "note":     "для розеточных групп",
            "section":  "breakers",
        },
    ],

    # ── Щит отопления ────────────────────────────────────────────────────
    "heating": [
        {
            "name":     "Контактор 3P",
            "mark":     "КМИ-32210 IEK",
            "unit":     "шт.",
            "qty_expr": "consumers",
            "note":     "управление насосами",
            "section":  "hardware",
        },
        {
            "name":     "Реле тепловое",
            "mark":     "РТИ-1316 IEK",
            "unit":     "шт.",
            "qty_expr": "consumers",
            "note":     "защита насосов",
            "section":  "hardware",
        },
    ],

    # ── Щит вентиляции ───────────────────────────────────────────────────
    "ventilation": [
        {
            "name":     "Контактор 3P",
            "mark":     "КМИ-32210 IEK",
            "unit":     "шт.",
            "qty_expr": "consumers",
            "note":     "управление вентиляцией",
            "section":  "hardware",
        },
        {
            "name":     "Реле тепловое",
            "mark":     "РТИ-1316 IEK",
            "unit":     "шт.",
            "qty_expr": "consumers",
            "note":     "",
            "section":  "hardware",
        },
    ],

    # ── Щит дымоудаления (кат.1, FRLS) ──────────────────────────────────
    "smoke_exhaust": [
        {
            "name":     "Контактор 3P (для вентилятора ДУ)",
            "mark":     "КМИ-32210 IEK",
            "unit":     "шт.",
            "qty_expr": "consumers",
            "note":     "пожаробезопасное исполнение",
            "section":  "hardware",
        },
        {
            "name":     "Реле времени (задержка пуска ДУ)",
            "mark":     "РВО-П2 IEK",
            "unit":     "шт.",
            "qty_expr": "1",
            "note":     "",
            "section":  "hardware",
        },
        {
            "name":     "Источник питания (ИБП) 24В для цепей управления",
            "mark":     "БП-24В/5А",
            "unit":     "шт.",
            "qty_expr": "1",
            "note":     "уточнить мощность",
            "section":  "hardware",
        },
    ],

    # ── Щит пожарной сигнализации (кат.1) ───────────────────────────────
    "firefighting": [
        {
            "name":     "Контактор 3P",
            "mark":     "КМИ-32210 IEK",
            "unit":     "шт.",
            "qty_expr": "consumers",
            "note":     "",
            "section":  "hardware",
        },
        {
            "name":     "Источник питания (ИБП) 24В",
            "mark":     "БП-24В/5А",
            "unit":     "шт.",
            "qty_expr": "1",
            "note":     "уточнить мощность",
            "section":  "hardware",
        },
    ],

    # ── Щит наружного освещения (ШУНО) ──────────────────────────────────
    "outdoor_lighting": [
        {
            "name":     "Астрономическое реле времени",
            "mark":     "РВА-01 IEK",
            "unit":     "шт.",
            "qty_expr": "1",
            "note":     "управление НО",
            "section":  "hardware",
        },
        {
            "name":     "Фотореле",
            "mark":     "ФР-601 IEK",
            "unit":     "шт.",
            "qty_expr": "1",
            "note":     "резерв / дублирование",
            "section":  "hardware",
        },
    ],
}


def get_template_items(panel_type: str, n_consumers: int, n_breakers: int) -> list[dict]:
    """
    Возвращает список позиций шаблона для щита заданного типа.

    Args:
        panel_type:   тип щита (lighting, power, heating, ...)
        n_consumers:  число потребителей (без резервных)
        n_breakers:   число автоматических выключателей

    Returns:
        list[dict] с полями: name, mark, unit, qty, note, section
    """
    base  = PANEL_TEMPLATE_ITEMS.get("all", [])
    extra = PANEL_TEMPLATE_ITEMS.get(panel_type, [])

    result = []
    for item in base + extra:
        qty_expr = item.get("qty_expr", "1")
        if qty_expr == "consumers":
            qty = n_consumers
        elif qty_expr == "breakers":
            qty = n_breakers
        else:
            try:
                qty = float(qty_expr)
            except (ValueError, TypeError):
                qty = 1

        if qty <= 0:
            continue

        result.append({
            "name":    item["name"],
            "mark":    item.get("mark", ""),
            "unit":    item["unit"],
            "qty":     qty,
            "note":    item.get("note", ""),
            "section": item.get("section", "hardware"),
        })

    return result
