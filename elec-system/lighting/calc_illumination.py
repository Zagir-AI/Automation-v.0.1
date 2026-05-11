"""
lighting/calc_illumination.py — расчёт освещённости методом КИ (коэффициент использования).

Норматив: СП 52.13330.2016 (актуализированная редакция СНиП 23-05-95*).

Блок "rooms" в project.json (верхний уровень):
  [
    {
      "id":           "ПМ-101",
      "name":         "Переговорная",
      "type":         "офис",        # тип помещения — ключ SP52_NORMS
      "length_m":     8.0,
      "width_m":      6.0,
      "height_m":     3.0,
      "h_work_m":     0.8,           # высота рабочей поверхности, м (дефолт 0.8)
      "n_luminaires": 6,             # фактическое число светильников
      "luminous_flux_lm": 3200,      # световой поток одного светильника, лм
      "rho_ceil":     0.7,           # коэф. отражения потолка (дефолт 0.7)
      "rho_wall":     0.5,           # коэф. отражения стен (дефолт 0.5)
      "kz":           1.5,           # коэф. запаса (дефолт 1.5)
      "z":            1.1            # коэф. неравномерности (дефолт 1.1)
    }
  ]
"""
from __future__ import annotations


# ── СП 52.13330.2016 Таблица 2 — нормируемая освещённость, лк ──────────────
SP52_NORMS: dict[str, int] = {
    "офис":           300,
    "переговорная":   300,
    "кабинет":        300,
    "коридор":        100,
    "лестница":       100,
    "склад":          200,
    "производство":   300,
    "торговый зал":   400,
    "читальный зал":  400,
    "учебный класс":  300,
    "архив":          200,
}

# ── UF-таблица (коэф. использования светового потока) по индексу помещения i ─
# Источник: МГСН 2.06-99, приложение к методике КИ (ЛПО-4×18 Вт, типовой офис)
_UF_RAW: list[tuple[float, float]] = [
    (0.60, 0.30),
    (0.80, 0.37),
    (1.00, 0.42),
    (1.25, 0.47),
    (1.50, 0.51),
    (2.00, 0.56),
    (2.50, 0.59),
    (3.00, 0.62),
    (4.00, 0.65),
    (5.00, 0.67),
]


def _uf(i: float) -> float:
    """Линейная интерполяция КИ по индексу помещения."""
    if i <= _UF_RAW[0][0]:
        return _UF_RAW[0][1]
    if i >= _UF_RAW[-1][0]:
        return _UF_RAW[-1][1]
    for (x0, y0), (x1, y1) in zip(_UF_RAW, _UF_RAW[1:]):
        if x0 <= i <= x1:
            return y0 + (y1 - y0) * (i - x0) / (x1 - x0)
    return _UF_RAW[-1][1]


# ── Поправки на коэф. отражения ──────────────────────────────────────────────
def _rho_factor(rho_ceil: float, rho_wall: float) -> float:
    """Поправочный коэффициент на отражение (упрощённая билинейная таблица)."""
    # Потолок: 0.7 → 1.0, 0.5 → 0.93, 0.3 → 0.85
    if rho_ceil >= 0.65:
        fc = 1.00
    elif rho_ceil >= 0.40:
        fc = 0.93
    else:
        fc = 0.85

    # Стены: 0.7 → 1.06, 0.5 → 1.00, 0.3 → 0.92
    if rho_wall >= 0.65:
        fw = 1.06
    elif rho_wall >= 0.40:
        fw = 1.00
    else:
        fw = 0.92

    return (fc + fw) / 2.0


def calc_room(room: dict) -> dict:
    """
    Рассчитывает фактическую и нормируемую освещённость одного помещения.

    Формула КИ (метод коэффициента использования):
      Eфакт = (N × Фл × UF × Крхо) / (S × Кз × z)

    Индекс помещения:
      i = S / (h_светильника × (a + b))
      h_светильника = height_m - h_work_m

    Результат:
      room_index     — индекс помещения i
      uf             — коэффициент использования
      e_fact_lx      — фактическая освещённость, лк
      e_norm_lx      — нормируемая освещённость, лк
      ok             — True если Eфакт ≥ Eнорм
      deficit_pct    — дефицит, % (>0 если не соответствует)
      n_required     — минимальное число светильников для выполнения нормы
    """
    length_m = float(room["length_m"])
    width_m  = float(room["width_m"])
    height_m = float(room["height_m"])
    h_work_m = float(room.get("h_work_m", 0.8))
    n_lum    = int(room["n_luminaires"])
    flux_lm  = float(room["luminous_flux_lm"])
    rho_ceil = float(room.get("rho_ceil", 0.7))
    rho_wall = float(room.get("rho_wall", 0.5))
    kz       = float(room.get("kz", 1.5))
    z        = float(room.get("z", 1.1))

    room_type = room.get("type", "офис").lower()
    e_norm = SP52_NORMS.get(room_type, 300)

    s_m2 = length_m * width_m
    h_mount = max(height_m - h_work_m, 0.1)
    room_index = s_m2 / (h_mount * (length_m + width_m))
    uf = _uf(room_index)
    rho_corr = _rho_factor(rho_ceil, rho_wall)

    e_fact = (n_lum * flux_lm * uf * rho_corr) / (s_m2 * kz * z)
    e_fact = round(e_fact, 1)

    ok = e_fact >= e_norm
    deficit_pct = round(max((e_norm - e_fact) / e_norm * 100, 0), 1)

    # Минимальное число светильников для нормы
    n_req_raw = (e_norm * s_m2 * kz * z) / (flux_lm * uf * rho_corr)
    import math
    n_required = math.ceil(n_req_raw)

    return {
        "id":            room.get("id", ""),
        "name":          room.get("name", room.get("id", "")),
        "type":          room_type,
        "length_m":      length_m,
        "width_m":       width_m,
        "height_m":      height_m,
        "s_m2":          round(s_m2, 2),
        "room_index":    round(room_index, 3),
        "uf":            round(uf, 3),
        "rho_corr":      round(rho_corr, 3),
        "n_luminaires":  n_lum,
        "flux_lm":       flux_lm,
        "e_fact_lx":     e_fact,
        "e_norm_lx":     e_norm,
        "ok":            ok,
        "deficit_pct":   deficit_pct,
        "n_required":    n_required,
    }


def calc_all_illumination(project: dict) -> list[dict]:
    """
    Считает освещённость для всех помещений из project["rooms"].
    Сохраняет результат в project["_results"]["illumination"].
    Возвращает список результатов.
    """
    results = []
    for room in project.get("rooms", []):
        results.append(calc_room(room))

    project.setdefault("_results", {})["illumination"] = results
    return results
