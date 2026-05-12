"""
data/cables/pue_tables.py — таблицы допустимых длительных токов (ПУЭ 7-е изд.).

Поддерживаемые марки кабелей:
  ВВГнг-LS, ВВГнг, ВВГ      — медь, ПВХ (табл.1.3.6)
  ВВГнг-FRLS                  — медь, огнестойкий (≈ВВГнг-LS)
  АВВГнг-LS, АВВГнг           — алюминий, ПВХ (табл.1.3.6)
  ААШв, ААБ2л, АВБШв          — алюминий, бронированный (табл.1.3.5)
  ПвВнг-LS                    — медь, XLPE (~+15% к ПВХ)
  КВВГнг-LS                   — контрольный, медь (≈ВВГнг-LS)
  NYM                          — медь (аналог ВВГ)
  ПВС, ШВВП                   — медь, гибкий
"""

# ── Стандартные сечения ──────────────────────────────────────────────
STANDARD_SECTIONS = [1.5, 2.5, 4, 6, 10, 16, 25, 35, 50, 70, 95, 120, 150, 185, 240]

# ── Маппинг марок → материал и базовая таблица ───────────────────────
# {марка_нижний_регистр: {"material": "copper"|"aluminium", "table": ключ}}
CABLE_MARK_MAP = {
    # Медь, ПВХ
    "ввгнг-ls":   {"material": "copper",    "table": "cu_vvg"},
    "ввгнг-frls": {"material": "copper",    "table": "cu_vvg"},  # огнестойкий ≈ тот же ток
    "ввгнг":      {"material": "copper",    "table": "cu_vvg"},
    "ввг":        {"material": "copper",    "table": "cu_vvg"},
    "nym":        {"material": "copper",    "table": "cu_vvg"},
    "пвс":        {"material": "copper",    "table": "cu_flex"},
    "шввп":       {"material": "copper",    "table": "cu_flex"},
    # Медь, XLPE (сшитый полиэтилен — допустимый ток ~+15% к ПВХ)
    "пввнг-ls":   {"material": "copper",    "table": "cu_xlpe"},
    "пввнг":      {"material": "copper",    "table": "cu_xlpe"},
    # Медь, контрольный (≈ВВГнг-LS по нагреву)
    "кввгнг-ls":  {"material": "copper",    "table": "cu_vvg"},
    "кввгнг":     {"material": "copper",    "table": "cu_vvg"},
    # Алюминий, ПВХ (АВВГнг-LS: А+В+В+Г = аввг, два 'в')
    "аввгнг-ls":  {"material": "aluminium", "table": "al_avvg"},
    "аввгнг":     {"material": "aluminium", "table": "al_avvg"},
    "аввг":       {"material": "aluminium", "table": "al_avvg"},
    # Алюминий, бронированный (ПУЭ табл.1.3.5)
    "аашв":       {"material": "aluminium", "table": "al_armor"},
    "ааб2л":      {"material": "aluminium", "table": "al_armor"},
    "аабл":       {"material": "aluminium", "table": "al_armor"},
    "авбшв":      {"material": "aluminium", "table": "al_armor"},
    "авб2л":      {"material": "aluminium", "table": "al_armor"},
}

# Ключи способов прокладки:
# "air"    — открыто на воздухе (лотки открытые, скобы)
# "tray"   — в кабельном лотке (закрытый, пучок)
# "pipe"   — в трубе / коробе
# "ground" — в земле (траншея)

# ── Таблица токов: медь ВВГнг-LS (ПУЭ 7, табл.1.3.6) ────────────────
_CU_VVG = {
    1.5:  {"air": 19,  "tray": 17,  "pipe": 15,  "ground": 22},
    2.5:  {"air": 26,  "tray": 24,  "pipe": 21,  "ground": 30},
    4:    {"air": 35,  "tray": 32,  "pipe": 29,  "ground": 37},
    6:    {"air": 45,  "tray": 40,  "pipe": 36,  "ground": 46},
    10:   {"air": 60,  "tray": 55,  "pipe": 50,  "ground": 60},
    16:   {"air": 80,  "tray": 70,  "pipe": 65,  "ground": 75},
    25:   {"air": 100, "tray": 85,  "pipe": 80,  "ground": 90},
    35:   {"air": 125, "tray": 105, "pipe": 95,  "ground": 110},
    50:   {"air": 155, "tray": 130, "pipe": 120, "ground": 135},
    70:   {"air": 190, "tray": 165, "pipe": 150, "ground": 165},
    95:   {"air": 225, "tray": 200, "pipe": 175, "ground": 195},
    120:  {"air": 260, "tray": 230, "pipe": 200, "ground": 220},
    150:  {"air": 295, "tray": 255, "pipe": 230, "ground": 250},
    185:  {"air": 330, "tray": 285, "pipe": 255, "ground": 275},
    240:  {"air": 385, "tray": 335, "pipe": 295, "ground": 315},
}

# Гибкие кабели ПВС/ШВВП (снижение 10% от ВВГнг-LS)
_CU_FLEX = {s: {k: round(v * 0.9) for k, v in d.items()} for s, d in _CU_VVG.items()}

# Медь XLPE (ПвВнг-LS) — допустимый ток ~+15% к ПВХ (70°C→90°C)
_CU_XLPE = {s: {k: round(v * 1.15) for k, v in d.items()} for s, d in _CU_VVG.items()}

# ── Алюминий ПВХ АВВГнг-LS (ПУЭ 7, табл.1.3.6, алюминий) ───────────
_AL_AVVG = {
    2.5:  {"air": 20,  "tray": 18,  "pipe": 16,  "ground": 23},
    4:    {"air": 28,  "tray": 25,  "pipe": 22,  "ground": 29},
    6:    {"air": 36,  "tray": 32,  "pipe": 28,  "ground": 36},
    10:   {"air": 47,  "tray": 43,  "pipe": 39,  "ground": 47},
    16:   {"air": 62,  "tray": 55,  "pipe": 50,  "ground": 58},
    25:   {"air": 80,  "tray": 68,  "pipe": 63,  "ground": 70},
    35:   {"air": 98,  "tray": 82,  "pipe": 74,  "ground": 85},
    50:   {"air": 120, "tray": 100, "pipe": 92,  "ground": 105},
    70:   {"air": 148, "tray": 128, "pipe": 116, "ground": 128},
    95:   {"air": 174, "tray": 155, "pipe": 135, "ground": 150},
    120:  {"air": 200, "tray": 178, "pipe": 155, "ground": 170},
    150:  {"air": 230, "tray": 200, "pipe": 178, "ground": 192},
    185:  {"air": 255, "tray": 222, "pipe": 198, "ground": 212},
    240:  {"air": 295, "tray": 258, "pipe": 228, "ground": 245},
}

# ── Алюминий бронированный ААШв/ААБ2л/АВБШв (ПУЭ 7, табл.1.3.5) ────
# Данные для 3-жильных кабелей с алюминиевыми жилами
_AL_ARMOR = {
    16:   {"air": 60,  "tray": 55,  "pipe": 50,  "ground": 75},
    25:   {"air": 75,  "tray": 65,  "pipe": 60,  "ground": 90},
    35:   {"air": 90,  "tray": 80,  "pipe": 72,  "ground": 110},
    50:   {"air": 110, "tray": 95,  "pipe": 87,  "ground": 135},
    70:   {"air": 140, "tray": 120, "pipe": 109, "ground": 165},
    95:   {"air": 170, "tray": 148, "pipe": 132, "ground": 200},
    120:  {"air": 200, "tray": 173, "pipe": 154, "ground": 230},
    150:  {"air": 230, "tray": 195, "pipe": 174, "ground": 260},
    185:  {"air": 255, "tray": 218, "pipe": 196, "ground": 295},
    240:  {"air": 295, "tray": 253, "pipe": 228, "ground": 340},
}

_TABLES = {
    "cu_vvg":   _CU_VVG,
    "cu_flex":  _CU_FLEX,
    "cu_xlpe":  _CU_XLPE,
    "al_avvg":  _AL_AVVG,
    "al_armor": _AL_ARMOR,
}

# ── Удельное сопротивление кабелей, Ом/км ────────────────────────────
# {("copper"|"aluminium", сечение_мм2): (r0_active, x0_reactive)}
CABLE_RESISTANCE = {
    # Медь (при 70°C)
    ("copper", 1.5):  (13.3,   0.10),
    ("copper", 2.5):  (7.98,   0.10),
    ("copper", 4):    (4.99,   0.09),
    ("copper", 6):    (3.30,   0.09),
    ("copper", 10):   (1.91,   0.08),
    ("copper", 16):   (1.21,   0.08),
    ("copper", 25):   (0.780,  0.08),
    ("copper", 35):   (0.554,  0.08),
    ("copper", 50):   (0.393,  0.07),
    ("copper", 70):   (0.272,  0.07),
    ("copper", 95):   (0.206,  0.07),
    ("copper", 120):  (0.161,  0.07),
    ("copper", 150):  (0.129,  0.07),
    ("copper", 185):  (0.106,  0.06),
    ("copper", 240):  (0.0801, 0.06),
    # Алюминий (при 70°C)
    ("aluminium", 2.5):  (12.8,  0.10),
    ("aluminium", 4):    (8.00,  0.09),
    ("aluminium", 6):    (5.29,  0.09),
    ("aluminium", 10):   (3.08,  0.08),
    ("aluminium", 16):   (1.91,  0.08),
    ("aluminium", 25):   (1.20,  0.08),
    ("aluminium", 35):   (0.868, 0.08),
    ("aluminium", 50):   (0.641, 0.07),
    ("aluminium", 70):   (0.443, 0.07),
    ("aluminium", 95):   (0.320, 0.07),
    ("aluminium", 120):  (0.253, 0.07),
    ("aluminium", 150):  (0.206, 0.07),
    ("aluminium", 185):  (0.164, 0.06),
    ("aluminium", 240):  (0.125, 0.06),
}

# ── Поправочные коэффициенты на температуру (ПУЭ 7, табл.1.3.3) ─────
_TEMP_CORRECTION = {
    "air": {
        10: 1.29, 15: 1.15, 20: 1.08, 25: 1.00,
        30: 0.91, 35: 0.82, 40: 0.71, 45: 0.58, 50: 0.45,
    },
    "tray": {
        10: 1.29, 15: 1.15, 20: 1.08, 25: 1.00,
        30: 0.91, 35: 0.82, 40: 0.71, 45: 0.58, 50: 0.45,
    },
    "pipe": {
        10: 1.29, 15: 1.15, 20: 1.08, 25: 1.00,
        30: 0.91, 35: 0.82, 40: 0.71, 45: 0.58, 50: 0.45,
    },
    "ground": {
        0: 1.25, 5: 1.18, 10: 1.13, 15: 1.00,
        20: 0.94, 25: 0.87, 30: 0.80, 35: 0.72,
    },
}

# ── Маппинг строкового описания прокладки → install_key ──────────────
_INSTALL_STR_MAP = {
    "открыто": "air",
    "воздух":  "air",
    "air":     "air",
    "лоток":   "tray",
    "лотке":   "tray",
    "tray":    "tray",
    "труба":   "pipe",
    "трубе":   "pipe",
    "короб":   "pipe",
    "pipe":    "pipe",
    "conduit": "pipe",
    "земля":   "ground",
    "земле":   "ground",
    "грунт":   "ground",
    "ground":  "ground",
}

# ── Таблица автовыбора марки кабеля по условию прокладки ─────────────
# (install_key, material, category_pue) → марка
# Используется когда cable_mark_override не задан
_MARK_BY_INSTALL = {
    # Медь
    ("air",    "copper", 1): "ВВГнг-FRLS",
    ("air",    "copper", 2): "ВВГнг-LS",
    ("air",    "copper", 3): "ВВГнг-LS",
    ("tray",   "copper", 1): "ВВГнг-FRLS",
    ("tray",   "copper", 2): "ВВГнг-LS",
    ("tray",   "copper", 3): "ВВГнг-LS",
    ("pipe",   "copper", 1): "ВВГнг-FRLS",
    ("pipe",   "copper", 2): "ВВГнг-LS",
    ("pipe",   "copper", 3): "ВВГнг-LS",
    ("ground", "copper", 1): "ВВГнг-LS",
    ("ground", "copper", 2): "ВВГнг-LS",
    ("ground", "copper", 3): "ВВГнг-LS",
    # Алюминий
    ("air",    "aluminium", 1): "АВБШв",
    ("air",    "aluminium", 2): "АВВГнг-LS",
    ("air",    "aluminium", 3): "АВВГнг-LS",
    ("tray",   "aluminium", 1): "АВБШв",
    ("tray",   "aluminium", 2): "АВВГнг-LS",
    ("tray",   "aluminium", 3): "АВВГнг-LS",
    ("pipe",   "aluminium", 1): "АВБШв",
    ("pipe",   "aluminium", 2): "АВВГнг-LS",
    ("pipe",   "aluminium", 3): "АВВГнг-LS",
    ("ground", "aluminium", 1): "АВБШв",
    ("ground", "aluminium", 2): "ААШв",
    ("ground", "aluminium", 3): "ААШв",
}


# ── Публичные функции ─────────────────────────────────────────────────

def get_ampacity_table(mark: str) -> dict:
    """
    Возвращает таблицу допустимых токов для марки кабеля.
    {сечение: {"air": А, "tray": А, "pipe": А, "ground": А}}
    """
    key = mark.strip().lower()
    info = CABLE_MARK_MAP.get(key)
    if info is None:
        for k, v in CABLE_MARK_MAP.items():
            if k in key or key in k:
                info = v
                break
    if info is None:
        return _CU_VVG  # fallback — медный ВВГ
    return _TABLES[info["table"]]


def get_conductor_material(mark: str) -> str:
    """Возвращает 'copper' или 'aluminium' для марки кабеля."""
    key = mark.strip().lower()
    info = CABLE_MARK_MAP.get(key)
    if info is None:
        for k, v in CABLE_MARK_MAP.items():
            if k in key or key in k:
                return v["material"]
        return "copper"
    return info["material"]


def get_install_key(install_str: str) -> str:
    """Преобразует текстовое описание прокладки в ключ ("air"/"tray"/"pipe"/"ground")."""
    s = install_str.strip().lower()
    if s in _INSTALL_STR_MAP:
        return _INSTALL_STR_MAP[s]
    for k, v in _INSTALL_STR_MAP.items():
        if k in s:
            return v
    return "tray"


def get_temp_correction(install_key: str, ambient_t: float) -> float:
    """Поправочный коэффициент на температуру (ПУЭ 7, табл.1.3.3)."""
    table = _TEMP_CORRECTION.get(install_key, _TEMP_CORRECTION["air"])
    temps = sorted(table.keys())

    if ambient_t <= temps[0]:
        return table[temps[0]]
    if ambient_t >= temps[-1]:
        return table[temps[-1]]

    for i in range(len(temps) - 1):
        t1, t2 = temps[i], temps[i + 1]
        if t1 <= ambient_t <= t2:
            k1, k2 = table[t1], table[t2]
            return round(k1 + (k2 - k1) * (ambient_t - t1) / (t2 - t1), 4)

    return 1.0


# ── Поправочный коэффициент на число кабелей в пучке ─────────────────
# ПУЭ 7, табл. 1.3.7 / РТМ 36.18.32.4-92, разд. 2.4
# Применяется при прокладке в лотке (tray) и трубе (pipe)
_K_GROUP = {
    1: 1.00, 2: 0.90, 3: 0.85, 4: 0.80, 5: 0.80,
    6: 0.75, 7: 0.75, 8: 0.70, 9: 0.70, 10: 0.70,
}
_K_GROUP_GT10 = 0.65  # более 10 кабелей в пучке


def get_grouping_factor(n_cables_in_group: int) -> float:
    """
    Поправочный коэффициент на число кабелей в одном лотке или трубе.
    ПУЭ 7, табл. 1.3.7 / РТМ 36.18.32.4-92.
    Для прокладки открыто (air) не применяется — возвращает 1.0.
    """
    if n_cables_in_group <= 1:
        return 1.0
    return _K_GROUP.get(n_cables_in_group, _K_GROUP_GT10)


# ── Минимальные сечения медных проводников ───────────────────────────
# СП 256.1325800.2016 п.6.2.4 / ПУЭ 7.1.34
MIN_SECTION_MM2 = {
    "lighting":           1.5,
    "emergency_lighting": 1.5,
    "sockets":            2.5,
    "power":              1.5,
    "hvac":               1.5,
    "ventilation_unit":   1.5,
    "smoke_fan":          1.5,
    "smoke_exhaust":      1.5,
    "fire_pump":          2.5,
    "motor":              1.5,
    "pump":               1.5,
    "elevator":           1.5,
    "it_equipment":       1.5,
    "kitchen":            2.5,
    "heating":            1.5,
    "ahu":                1.5,
    "panel":              2.5,
    "default":            1.5,
}


def get_min_section(consumer_type: str, is_aluminum: bool = False) -> float:
    """
    Минимальное допустимое сечение проводника (мм²).
    СП 256.1325800.2016 п.6.2.4; ПУЭ 7.1.34.
    Для алюминия минимум 16 мм² (ПУЭ 7.1.34, алюминий запрещён < 16 мм²).
    """
    if is_aluminum:
        return 16.0
    return MIN_SECTION_MM2.get(consumer_type, MIN_SECTION_MM2["default"])


def get_cable_mark_by_install(install_key: str, material: str = "copper",
                               category_pue: int = 3) -> str:
    """
    Автовыбор марки кабеля по условию прокладки, материалу и категории ПУЭ.

    Args:
        install_key:   "air" / "tray" / "pipe" / "ground"
        material:      "copper" / "aluminium"
        category_pue:  1, 2 или 3

    Returns:
        Марка кабеля (строка)
    """
    cat = min(max(int(category_pue), 1), 3)
    key = (install_key, material, cat)
    return _MARK_BY_INSTALL.get(key, "ВВГнг-LS")
