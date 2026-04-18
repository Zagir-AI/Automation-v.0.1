"""
data/cables/pue_tables.py — таблицы допустимых длительных токов (ПУЭ 7-е изд., табл.1.3.6).

Поддерживаемые марки кабелей:
  ВВГнг-LS, ВВГнг, ВВГ  — медь, установочный
  АВВГнг-LS, АВВГнг      — алюминий
  NYM                     — медь (аналог ВВГ)
  ПВС, ШВВП               — медь, гибкий
"""

# ── Стандартные сечения ──────────────────────────────────────────────
STANDARD_SECTIONS = [1.5, 2.5, 4, 6, 10, 16, 25, 35, 50, 70, 95, 120, 150, 185, 240]

# ── Маппинг марок → материал и базовая таблица ───────────────────────
# {марка_нижний_регистр: {"material": "copper"|"aluminium", "table": "cu_vvg"|"al_avvg"|...}}
CABLE_MARK_MAP = {
    "ввгнг-ls":   {"material": "copper",    "table": "cu_vvg"},
    "ввгнг":      {"material": "copper",    "table": "cu_vvg"},
    "ввг":        {"material": "copper",    "table": "cu_vvg"},
    "авввгнг-ls": {"material": "aluminium", "table": "al_avvg"},
    "авввгнг":    {"material": "aluminium", "table": "al_avvg"},
    "авввг":      {"material": "aluminium", "table": "al_avvg"},
    "nym":        {"material": "copper",    "table": "cu_vvg"},
    "пвс":        {"material": "copper",    "table": "cu_flex"},
    "шввп":       {"material": "copper",    "table": "cu_flex"},
}

# Ключи способов прокладки
# "air"    — открыто на воздухе (лотки открытые, скобы)
# "tray"   — в кабельном лотке (закрытый, пучок)
# "pipe"   — в трубе / коробе
# "ground" — в земле

# ── Таблица токов: медные кабели ВВГнг-LS (ПУЭ 7, табл.1.3.6) ────────
# {сечение_мм2: {"air": A, "tray": A, "pipe": A, "ground": A}}
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

# Гибкие кабели ПВС/ШВВП (приближённо, снижение 10%)
_CU_FLEX = {s: {k: round(v * 0.9) for k, v in d.items()} for s, d in _CU_VVG.items()}

# Алюминиевые кабели АВВГнг-LS (ПУЭ 7, табл.1.3.6 — алюминий)
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

_TABLES = {
    "cu_vvg":  _CU_VVG,
    "cu_flex": _CU_FLEX,
    "al_avvg": _AL_AVVG,
}

# ── Удельное сопротивление кабелей, Ом/км ────────────────────────────
# {("copper"|"aluminium", сечение_мм2): (r0_active, x0_reactive)}
# r0 — активное (при 70°С), x0 — индуктивное (приближённо для LV кабелей)
CABLE_RESISTANCE = {
    # Медь (ρ=0.0175 Ом·мм²/м при 20°C, +15% на нагрев до 70°C → 0.02)
    ("copper", 1.5):  (13.3,  0.10),
    ("copper", 2.5):  (7.98,  0.10),
    ("copper", 4):    (4.99,  0.09),
    ("copper", 6):    (3.30,  0.09),
    ("copper", 10):   (1.91,  0.08),
    ("copper", 16):   (1.21,  0.08),
    ("copper", 25):   (0.780, 0.08),
    ("copper", 35):   (0.554, 0.08),
    ("copper", 50):   (0.393, 0.07),
    ("copper", 70):   (0.272, 0.07),
    ("copper", 95):   (0.206, 0.07),
    ("copper", 120):  (0.161, 0.07),
    ("copper", 150):  (0.129, 0.07),
    ("copper", 185):  (0.106, 0.06),
    ("copper", 240):  (0.0801,0.06),
    # Алюминий (ρ=0.028 Ом·мм²/м при 20°C, +15% → 0.032)
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
# Базовая температура: воздух 25°C, земля 15°C
# {install_key: {температура_С: коэффициент}}
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

# Маппинг строковых описаний прокладки → install_key
_INSTALL_STR_MAP = {
    "открыто":    "air",
    "воздух":     "air",
    "air":        "air",
    "лоток":      "tray",
    "лотке":      "tray",
    "tray":       "tray",
    "труба":      "pipe",
    "трубе":      "pipe",
    "короб":      "pipe",
    "pipe":       "pipe",
    "conduit":    "pipe",
    "земля":      "ground",
    "земле":      "ground",
    "грунт":      "ground",
    "ground":     "ground",
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
        # Пробуем найти по частичному совпадению
        for k, v in CABLE_MARK_MAP.items():
            if k in key or key in k:
                info = v
                break
    if info is None:
        # По умолчанию — медный ВВГ
        return _CU_VVG
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
    # Точное совпадение
    if s in _INSTALL_STR_MAP:
        return _INSTALL_STR_MAP[s]
    # Частичное совпадение
    for k, v in _INSTALL_STR_MAP.items():
        if k in s:
            return v
    return "tray"  # по умолчанию — лоток


def get_temp_correction(install_key: str, ambient_t: float) -> float:
    """
    Поправочный коэффициент на температуру окружающей среды.
    Если точная температура не найдена — интерполяция.
    """
    table = _TEMP_CORRECTION.get(install_key, _TEMP_CORRECTION["air"])
    temps = sorted(table.keys())

    if ambient_t <= temps[0]:
        return table[temps[0]]
    if ambient_t >= temps[-1]:
        return table[temps[-1]]

    # Линейная интерполяция
    for i in range(len(temps) - 1):
        t1, t2 = temps[i], temps[i + 1]
        if t1 <= ambient_t <= t2:
            k1, k2 = table[t1], table[t2]
            return round(k1 + (k2 - k1) * (ambient_t - t1) / (t2 - t1), 4)

    return 1.0
