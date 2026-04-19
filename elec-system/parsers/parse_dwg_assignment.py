"""
parsers/parse_dwg_assignment.py — импорт потребителей из DXF-плана смежников.

Читает блоки оборудования на плане (планы ТХ, ОВ, ВК и др.) и возвращает
список потребителей в формате project.json для добавления в consumers[].

Поддерживаемые атрибуты блоков (любой регистр):
  Обозначение: TAG, ID, POS, ПОЗИЦИЯ, ОБОЗНАЧЕНИЕ
  Наименование: NAME, НАИМЕНОВАНИЕ, DESC
  Тип:         TYPE, ТИП, EQUIP_TYPE
  Мощность:    POWER, P_KW, МОЩНОСТЬ, P_INST
  cosφ:        COS_PHI, COSPHI, КПД (fallback — по типу)
  КПД:         ETA, КПД_ДВ
  Фазность:    PHASES, ФАЗЫ
  Напряжение:  VOLTAGE, VOLTAGE_CLASS, НАПРЯЖЕНИЕ

Зависимость: ezdxf (pip install ezdxf)
"""

from pathlib import Path


# ── Типы оборудования → параметры по умолчанию ──────────────────────────────
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

# Ключевые слова для определения типа по имени/тегу блока
_TYPE_KEYWORDS = {
    "motor":    ["насос", "pump", "двигател", "motor", "электродвиг"],
    "fan":      ["вентилят", "fan", "дутьев", "exhaust"],
    "hvac":     ["кондицион", "чиллер", "вру", "ahu", "hvac", "fan coil"],
    "lighting": ["светильн", "light", "люстр", "прожект"],
    "socket":   ["розетк", "socket", "outlet"],
    "welder":   ["сварк", "weld"],
}


def _detect_type(name: str, block_name: str) -> str:
    text = (name + " " + block_name).lower()
    for eq_type, keywords in _TYPE_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return eq_type
    return "other"


# ── Сопоставление имён атрибутов ─────────────────────────────────────────────
_ATTR_ID      = {"TAG", "ID", "POS", "ПОЗИЦИЯ", "ОБОЗНАЧЕНИЕ", "ID_TAG"}
_ATTR_NAME    = {"NAME", "НАИМЕНОВАНИЕ", "DESC", "DESCR", "TITLE"}
_ATTR_TYPE    = {"TYPE", "ТИП", "EQUIP_TYPE", "EQUIPMENT_TYPE"}
_ATTR_POWER   = {"POWER", "P_KW", "МОЩНОСТЬ", "P_INST", "P_UST", "KW"}
_ATTR_COS     = {"COS_PHI", "COSPHI", "COS", "COSFI", "PF"}
_ATTR_ETA     = {"ETA", "КПД_ДВ", "EFFICIENCY"}
_ATTR_PHASES  = {"PHASES", "ФАЗЫ", "PHASE"}
_ATTR_VOLTAGE = {"VOLTAGE", "VOLTAGE_CLASS", "НАПРЯЖЕНИЕ", "UN", "U_NOM"}


def _get_attr(attribs: dict, keys: set) -> str | None:
    for key in keys:
        if key in attribs:
            return attribs[key].strip()
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
                        position: tuple) -> dict | None:
    """Преобразует атрибуты блока в словарь потребителя."""
    # Мощность обязательна
    power_raw = _get_attr(attribs, _ATTR_POWER)
    power_kw = _parse_float(power_raw)
    if power_kw is None or power_kw <= 0:
        return None

    # Обозначение
    tag = _get_attr(attribs, _ATTR_ID) or ""
    name = _get_attr(attribs, _ATTR_NAME) or tag or block_name

    # Тип оборудования
    type_raw = _get_attr(attribs, _ATTR_TYPE) or ""
    eq_type = type_raw.lower() if type_raw.lower() in _TYPE_DEFAULTS else _detect_type(name, block_name)

    defaults = _TYPE_DEFAULTS.get(eq_type, _TYPE_DEFAULTS["other"])

    cos_phi = _parse_float(_get_attr(attribs, _ATTR_COS)) or defaults["cos_phi"]
    eta     = _parse_float(_get_attr(attribs, _ATTR_ETA))  or defaults["eta"]
    phases  = int(_parse_float(_get_attr(attribs, _ATTR_PHASES)) or defaults["phases"])

    voltage_raw = _get_attr(attribs, _ATTR_VOLTAGE) or "0.4kV"
    voltage_class = voltage_raw if voltage_raw else "0.4kV"

    consumer = {
        "id":            tag or f"{block_name}-{int(position[0])}",
        "name":          name,
        "type":          eq_type,
        "power_kw":      round(power_kw, 2),
        "demand_factor": defaults["demand_factor"],
        "cos_phi":       round(cos_phi, 3),
        "eta":           round(eta, 3),
        "phases":        phases,
        "voltage_class": voltage_class,
        "source":        "dwg",
        "source_file":   source_file,
        "position":      {"x": round(position[0], 2), "y": round(position[1], 2)},
        "cable": {
            "mark":       "ВВГнг-LS",
            "install":    "лоток",
            "length_m":   10,
            "section_mm2": None
        },
        "breaker": {}
    }
    return consumer


def parse_dwg_assignment(dxf_path: str) -> list[dict]:
    """
    Читает DXF-план смежников и возвращает список потребителей
    в формате project.json (consumers[]).

    Извлекает только блоки с атрибутом мощности (POWER/P_KW/МОЩНОСТЬ).
    Блоки без мощности пропускаются.

    Args:
        dxf_path: путь к DXF-файлу

    Returns:
        list[dict] — потребители, готовые для вставки в consumers[]
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
    seen_ids = set()

    for insert in msp.query("INSERT"):
        if not insert.attribs_follow:
            continue

        # Собираем атрибуты в словарь {TAG.upper(): text}
        raw_attribs = {a.dxf.tag.upper(): a.dxf.text for a in insert.attribs}
        if not raw_attribs:
            continue

        block_name = insert.dxf.name or ""
        pos = insert.dxf.insert  # Vec3
        position = (float(pos.x), float(pos.y))

        consumer = _block_to_consumer(block_name, raw_attribs, path.name, position)
        if consumer is None:
            continue

        # Уникальность по id
        base_id = consumer["id"]
        uid = base_id
        counter = 1
        while uid in seen_ids:
            uid = f"{base_id}-{counter}"
            counter += 1
        consumer["id"] = uid
        seen_ids.add(uid)

        consumers.append(consumer)

    return consumers


def print_parsed_consumers(consumers: list) -> None:
    """Вывод извлечённых потребителей в консоль."""
    if not consumers:
        print("Потребители не найдены (нет блоков с атрибутом мощности)")
        return
    print(f"\nНайдено потребителей: {len(consumers)}\n")
    fmt = f"{'ID':<12} {'Наименование':<30} {'Тип':<10} {'P,кВт':<8} {'cosφ':<6} {'фаз':<4}"
    print(fmt)
    print("-" * 75)
    for c in consumers:
        print(
            f"{c['id']:<12} {c['name'][:30]:<30} {c['type']:<10} "
            f"{c['power_kw']:<8.2f} {c['cos_phi']:<6.3f} {c['phases']:<4}"
        )
