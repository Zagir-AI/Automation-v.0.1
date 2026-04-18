"""
data/breakers/breaker_tables.py — выбор автоматических выключателей.

Алгоритм выбора по ПУЭ 3.1.4 / ГОСТ Р 50345:
  I_ном ≥ I_расч × 1.1 (коэффициент перегрузки)
  Затем ближайший больший стандартный номинал.

Для двигателей учитывается пусковой ток:
  I_ном ≥ I_пуск / (k_от × k_возв)  — характеристика D
"""

# ── Стандартные номиналы (ГОСТ Р 50345) ─────────────────────────────
STANDARD_RATINGS = [
    6, 10, 13, 16, 20, 25, 32, 40, 50, 63,
    80, 100, 125, 160, 200, 250, 315, 400, 500, 630
]

# ── Характеристики расцепителей ──────────────────────────────────────
# {char: {"trip_factor_min": k, "trip_factor_max": k, "description": str}}
TRIP_CHARACTERISTICS = {
    "B": {
        "trip_factor_min": 3,
        "trip_factor_max": 5,
        "description": "Освещение, кабели с малым пусковым током",
    },
    "C": {
        "trip_factor_min": 5,
        "trip_factor_max": 10,
        "description": "Смешанная нагрузка, розетки, освещение",
    },
    "D": {
        "trip_factor_min": 10,
        "trip_factor_max": 20,
        "description": "Двигатели, трансформаторы, большой пусковой ток",
    },
}

# Маппинг типов потребителей → характеристика расцепителя
_TYPE_TO_CHAR = {
    "lighting":     "C",
    "sockets":      "C",
    "hvac":         "D",
    "motor":        "D",
    "elevator":     "D",
    "pump":         "D",
    "it_equipment": "C",
    "kitchen":      "C",
    "welding":      "D",
    "default":      "C",
}

# Количество полюсов по числу фаз
_PHASES_TO_POLES = {1: 2, 3: 3}


def _next_rating(i_min: float) -> int:
    """Ближайший стандартный номинал ≥ i_min."""
    for r in STANDARD_RATINGS:
        if r >= i_min:
            return r
    return STANDARD_RATINGS[-1]


def select_breaker(i_calc: float, char: str = "C", phases: int = 3) -> dict:
    """
    Подбор автомата по расчётному току.
    I_ном ≥ I_расч × 1.1 → ближайший стандартный номинал.
    """
    i_min = i_calc * 1.1
    rating = _next_rating(i_min)
    poles = _PHASES_TO_POLES.get(phases, 3)
    return {
        "rating": rating,
        "char": char,
        "poles": poles,
        "type": f"АВ {rating}А хар.{char} {poles}П",
        "i_calc": round(i_calc, 2),
    }


def select_breaker_for_consumer(consumer: dict, i_calc: float) -> dict:
    """
    Подбор автомата для потребителя с учётом типа нагрузки и пускового тока.
    """
    c_type = consumer.get("type", "default")
    char = _TYPE_TO_CHAR.get(c_type, "C")
    phases = consumer.get("phases", 3)
    start_factor = consumer.get("start_factor", 1.0)

    if start_factor > 3.0:
        # Двигатель с большим пусковым током — характеристика D
        char = "D"

    return select_breaker(i_calc, char=char, phases=phases)


def select_panel_breaker(i_calc: float, phases: int = 3) -> dict:
    """
    Подбор вводного автомата щита / ВРУ.
    Всегда характеристика C, 3 полюса.
    """
    return select_breaker(i_calc, char="C", phases=phases)
