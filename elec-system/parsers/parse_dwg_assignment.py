"""
parsers/parse_dwg_assignment.py — импорт потребителей из DXF-плана смежников.

Читает блоки оборудования на плане (ТХ, ОВ, ВК, КВ и др.) и возвращает
список потребителей в формате project.json.

Поддерживаемые атрибуты блоков (любой регистр):
  TAG, ID, POS, ПОЗИЦИЯ, ОБОЗНАЧЕНИЕ  — позиционное обозначение
  NAME, НАИМЕНОВАНИЕ, DESC            — наименование
  TYPE, ТИП, EQUIP_TYPE              — тип оборудования
  POWER, P_KW, МОЩНОСТЬ, P_INST      — мощность, кВт
  COS_PHI, COSPHI, PF                — коэффициент мощности
  ETA, КПД_ДВ, EFFICIENCY            — КПД
  PHASES, ФАЗЫ                        — количество фаз
  VOLTAGE, VOLTAGE_CLASS, НАПРЯЖЕНИЕ  — класс напряжения
  CATEGORY, КАТ, КАТЕГОРИЯ           — категория ПУЭ (переопределение)

Зависимость: ezdxf
"""

from pathlib import Path


# ── Параметры по умолчанию для типов оборудования ────────────────────────────
_TYPE_DEFAULTS = {
    "motor":    {"cos_phi": 0.85, "eta": 0.92, "phases": 3, "demand_factor": 0.75},
    "pump":     {"cos_phi": 0.85, "eta": 0.92, "phases": 3, "demand_factor": 0.75},
    "fan":      {"cos_phi": 0.80, "eta": 0.90, "phases": 3, "demand_factor": 0.80},
    "hvac":     {"cos_phi": 0.80, "eta": 1.00, "phases": 3, "demand_factor": 0.80},
    "lighting": {"cos_phi": 0.95, "eta": 1.00, "phases": 3, "demand_factor": 0.90},
    "socket":   {"cos_phi": 0.80, "eta": 1.00, "phases": 3, "demand_factor": 0.50},
    "welder":   {"cos_phi": 0.60, "eta": 1.00, "phases": 3, "demand_factor": 0.35},
    "other":    {"cos_phi": 0.85, "eta": 1.00, "phases": 3, "demand_factor": 0.70},
}

# Ключевые слова для автоопределения типа оборудования
_TYPE_KEYWORDS = {
    "pump":     ["насос", "pump"],
    "motor":    ["двигател", "motor", "электродвиг", "станок", "конвейер"],
    "fan":      ["вентилят", "fan", "дутьев", "exhaust", "приточн", "вытяжн"],
    "hvac":     ["кондицион", "чиллер", "ahu", "hvac", "fan coil", "фанкойл"],
    "lighting": ["светильн", "light", "люстр", "прожект"],
    "socket":   ["розетк", "socket", "outlet"],
    "welder":   ["сварк", "weld"],
}

# ── Правила категории ПУЭ по разделу и типу/наименованию ─────────────────────
# Ключевые слова → категория 1
_CAT1_KEYWORDS = [
    "пожар", "пожаротуш", "пс", "пожарн",   # насосы пожаротушения
    "дымоудал", "дымовой", "противодым",      # системы дымоудаления
    "аварийн",                                # аварийные системы
]
# Ключевые слова → категория 2
_CAT2_KEYWORDS = [
    "отоплен", "теплоснабж", "подпитк",      # отопление
    "вентил", "приточн", "вытяжн",            # вентиляция (не аварийная)
]

# Щит по умолчанию для раздела
_SECTION_PANEL = {
    "ОВ":  "ЩОВ-1",
    "ВК":  "ЩВК-1",
    "КВ":  "ЩКВ-1",
    "ТХ":  "ЩТХ-1",
    "ЭОМ": "ЩС-1",
    "ЭН":  "ШУНО-1",
}

# Категория по умолчанию для раздела
_SECTION_DEFAULT_CATEGORY = {
    "ОВ": 2,
    "ВК": 2,
    "КВ": 3,
    "ТХ": 3,
    "ЭОМ": 3,
    "ЭН": 3,
}


def _detect_type(name: str, block_name: str) -> str:
    text = (name + " " + block_name).lower()
    for eq_type, keywords in _TYPE_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return eq_type
    return "other"


def _determine_category(name: str, eq_type: str, section: str,
                         attr_category: str | None) -> int:
    """Определяет категорию ПУЭ потребителя."""
    # Явное указание в атрибуте блока — приоритет
    if attr_category:
        try:
            return int(attr_category.strip())
        except ValueError:
            pass

    text = name.lower()

    # Категория 1 по ключевым словам
    if any(kw in text for kw in _CAT1_KEYWORDS):
        return 1

    # Котельное оборудование в ОВ → категория 1
    if section == "ОВ" and any(kw in text for kw in ["котёл", "котел", "boiler"]):
        return 1

    # Категория 2 по ключевым словам
    if any(kw in text for kw in _CAT2_KEYWORDS):
        return 2

    # Насосы в ОВ → категория 2
    if section == "ОВ" and eq_type == "pump":
        return 2

    # Вентиляторы в ВК → категория 2
    if section == "ВК" and eq_type == "fan":
        return 2

    # Кондиционеры → категория 3
    if eq_type == "hvac":
        return 3

    return _SECTION_DEFAULT_CATEGORY.get(section, 3)


def _determine_panel(name: str, eq_type: str, section: str, category: int) -> str:
    """Определяет щит для потребителя."""
    text = name.lower()

    # Системы дымоудаления → ЩДУ-1 (отдельный щит, кат.1)
    if any(kw in text for kw in ["дымоудал", "дымовой", "противодым"]):
        return "ЩДУ-1"

    # Насосы пожаротушения → ЩПС-1
    if any(kw in text for kw in ["пожар", "пожаротуш"]) and eq_type == "pump":
        return "ЩПС-1"

    # Прочие кат.1 в ВК → ЩПС-1
    if section == "ВК" and category == 1:
        return "ЩПС-1"

    return _SECTION_PANEL.get(section, "ЩТХ-1")


def _determine_reserve(name: str, eq_type: str, section: str, category: int) -> str | None:
    """Определяет схему резервирования."""
    text = name.lower()
    # Насосы с резервом: подпитка, пожаротушение, основные насосы ОВ/ВК
    if eq_type == "pump" and section in ("ОВ", "ВК"):
        return "1+1"
    if eq_type == "pump" and any(kw in text for kw in ["пожар", "подпитк", "рабоч", "резерв"]):
        return "1+1"
    return None


# ── Сопоставление имён атрибутов (новый стандарт + обратная совместимость) ───
# Порядок важен — первое совпадение побеждает
_ATTR_ID       = ["ID_TAG", "TAG", "ID", "POS", "ПОЗИЦИЯ", "ОБОЗНАЧЕНИЕ"]
_ATTR_NAME     = ["NAME", "НАИМЕНОВАНИЕ", "DESC", "DESCR", "TITLE"]
_ATTR_TYPE     = ["TYPE", "ТИП", "EQUIP_TYPE", "EQUIPMENT_TYPE"]
_ATTR_POWER    = ["POWER_KW", "POWER", "P_KW", "МОЩНОСТЬ", "P_INST", "P_UST", "KW"]
_ATTR_COS      = ["COS_PHI", "COSPHI", "COS", "COSFI", "PF"]
_ATTR_ETA      = ["ETA", "КПД_ДВ", "EFFICIENCY"]
_ATTR_PHASES   = ["PHASES", "ФАЗЫ", "PHASE"]
_ATTR_VOLTAGE  = ["VOLTAGE", "VOLTAGE_CLASS", "НАПРЯЖЕНИЕ", "UN", "U_NOM"]
_ATTR_CATEGORY = ["CATEGORY", "КАТ", "КАТЕГОРИЯ", "CAT"]
_ATTR_RESERVE  = ["RESERVE", "РЕЗЕРВ", "RESERVE_UNIT"]          # новый стандарт
_ATTR_SECTION  = ["SECTION_TAG", "SECTION", "РАЗДЕЛ"]           # новый стандарт
_ATTR_CABLE_OV = ["CABLE_MARK_OVERRIDE", "CABLE_MARK", "МАРКА"] # новый стандарт


def _get_attr(attribs: dict, keys: set) -> str | None:
    for key in keys:
        if key in attribs:
            val = attribs[key].strip()
            return val if val else None
    return None


def _parse_float(s: str | None) -> float | None:
    if not s:
        return None
    import re
    cleaned = re.sub(r"[^\d.,]", "", str(s)).replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def _block_to_consumer(block_name: str, attribs: dict, source_file: str,
                        position: tuple, section: str) -> dict | None:
    """Преобразует атрибуты блока в словарь потребителя."""
    power_kw = _parse_float(_get_attr(attribs, _ATTR_POWER))
    if power_kw is None or power_kw <= 0:
        return None

    tag  = _get_attr(attribs, _ATTR_ID) or ""
    name = _get_attr(attribs, _ATTR_NAME) or tag or block_name

    # SECTION_TAG в блоке переопределяет параметр section_code
    section_override = _get_attr(attribs, _ATTR_SECTION)
    if section_override:
        section = section_override.upper()

    type_raw = (_get_attr(attribs, _ATTR_TYPE) or "").lower()
    eq_type  = type_raw if type_raw in _TYPE_DEFAULTS else _detect_type(name, block_name)

    defaults = _TYPE_DEFAULTS.get(eq_type, _TYPE_DEFAULTS["other"])

    cos_phi = _parse_float(_get_attr(attribs, _ATTR_COS)) or defaults["cos_phi"]
    eta     = _parse_float(_get_attr(attribs, _ATTR_ETA)) or defaults["eta"]
    phases  = int(_parse_float(_get_attr(attribs, _ATTR_PHASES)) or defaults["phases"])
    voltage = _get_attr(attribs, _ATTR_VOLTAGE) or "0.4kV"

    category = _determine_category(name, eq_type, section,
                                    _get_attr(attribs, _ATTR_CATEGORY))
    panel_id = _determine_panel(name, eq_type, section, category)
    reserve_scheme = _determine_reserve(name, eq_type, section, category)

    # RESERVE="1" или "true" → резервный агрегат (не суммируется в нагрузку)
    reserve_raw = (_get_attr(attribs, _ATTR_RESERVE) or "").lower()
    is_reserve = reserve_raw in ("1", "true", "да", "yes", "резерв")

    # CABLE_MARK_OVERRIDE переопределяет автовыбор марки кабеля
    cable_mark_override = _get_attr(attribs, _ATTR_CABLE_OV)

    consumer_id = tag or f"{section}-{block_name}-{int(position[0])}"

    return {
        "id":                  consumer_id,
        "name":                name,
        "type":                eq_type,
        "section":             section,
        "power_kw":            round(power_kw, 2),
        "demand_factor":       defaults["demand_factor"],
        "cos_phi":             round(cos_phi, 3),
        "eta":                 round(eta, 3),
        "phases":              phases,
        "voltage_class":       voltage,
        "category_pue":        category,
        "reserve":             is_reserve,
        "reserve_scheme":      reserve_scheme,
        "panel_id":            panel_id,
        "cable_mark_override": cable_mark_override,
        "source":              "dwg",
        "source_file":         source_file,
        "position":            {"x": round(position[0], 2), "y": round(position[1], 2)},
        "cable": {
            "mark":        cable_mark_override or "ВВГнг-LS",
            "install":     "лоток",
            "length_m":    10,
            "section_mm2": None,
        },
        "breaker": {},
    }


def parse_dwg_assignment(dxf_path: str, section_code: str = "ТХ") -> list[dict]:
    """
    Читает DXF-план смежников и возвращает список потребителей.

    Args:
        dxf_path:     путь к DXF-файлу
        section_code: код раздела смежника (ОВ, ВК, КВ, ТХ и др.)

    Returns:
        list[dict] — потребители в формате consumers[] с полями
                     category_pue, reserve_scheme, panel_id, section
    """
    try:
        import ezdxf
    except ImportError:
        raise ImportError("Установи ezdxf: pip install ezdxf")

    path = Path(dxf_path)
    if not path.exists():
        raise FileNotFoundError(f"DXF-файл не найден: {path}")

    doc = ezdxf.readfile(str(path))
    msp = doc.modelspace()

    consumers = []
    seen_ids: set[str] = set()

    for insert in msp.query("INSERT"):
        if not insert.attribs_follow:
            continue

        raw_attribs = {a.dxf.tag.upper(): a.dxf.text for a in insert.attribs}
        if not raw_attribs:
            continue

        block_name = insert.dxf.name or ""
        pos = insert.dxf.insert
        position = (float(pos.x), float(pos.y))

        consumer = _block_to_consumer(block_name, raw_attribs, path.name,
                                       position, section_code)
        if consumer is None:
            continue

        # Гарантируем уникальность id
        base_id = consumer["id"]
        uid, counter = base_id, 1
        while uid in seen_ids:
            uid = f"{base_id}-{counter}"
            counter += 1
        consumer["id"] = uid
        seen_ids.add(uid)

        consumers.append(consumer)

    return consumers


def print_parsed_consumers(consumers: list) -> None:
    """Вывод потребителей в консоль."""
    if not consumers:
        print("Потребители не найдены (нет блоков с атрибутом мощности)")
        return
    print(f"\nНайдено потребителей: {len(consumers)}\n")
    header = f"{'ID':<12} {'Наименование':<28} {'Тип':<8} {'P,кВт':<7} {'cosφ':<6} {'Кат':<4} {'Щит':<10} {'Резерв'}"
    print(header)
    print("-" * 85)
    for c in consumers:
        print(
            f"{c['id']:<12} {c['name'][:28]:<28} {c['type']:<8} "
            f"{c['power_kw']:<7.2f} {c['cos_phi']:<6.3f} "
            f"{c['category_pue']:<4} {c['panel_id']:<10} "
            f"{c['reserve_scheme'] or '-'}"
        )
