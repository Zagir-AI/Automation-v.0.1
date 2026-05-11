"""
outdoor/calc_earthwork.py — расчёт объёмов земляных работ для кабельных траншей.

Нормативы: СНиП 3.05.06-85, ПУЭ 2.3.83, ГЭСН 81-02-01.

Опциональный блок "trench" в outdoor_networks[]:
  {
    "n_cables":   1,           # кабелей в одной траншее
    "depth_m":    0.7,         # глубина траншеи, м
    "soil_type":  "суглинок",  # тип грунта (см. SOIL_LOOSEN)
    "protection": "кирпич"     # "кирпич" или "плита"
  }
Если блок отсутствует — используются дефолты.
"""
from __future__ import annotations

import math

# Коэффициенты разрыхления по типу грунта (ГЭСН 81-02-01)
SOIL_LOOSEN: dict[str, float] = {
    "песок":         1.10,
    "суглинок":      1.20,
    "глина":         1.28,
    "тяжёлая глина": 1.35,
    "скальный":      1.45,
}


def calc_trench(
    length_m:   float,
    n_cables:   int   = 1,
    depth_m:    float = 0.7,
    soil_type:  str   = "суглинок",
    protection: str   = "кирпич",
    voltage_kv: float = 0.4,
) -> dict:
    """
    Рассчитывает объёмы земляных работ для одной кабельной траншеи.

    Ширина по СНиП 3.05.06-85:
      1 кабель  → 0.30 м
      2 кабеля  → 0.50 м
      3+ кабеля → 0.50 + (n-2) × 0.15 м

    Глубина по ПУЭ 2.3.83:
      ≤ 1 кВ: не менее 0.70 м
      1–10 кВ: не менее 1.00 м
      (depth_m применяется как переданное значение, мин. значение ПУЭ — справочно)

    Подсыпка: 100 мм снизу + 100 мм сверху = 0.20 м × ширину траншеи.

    Защита:
      "кирпич" → кирпич 250×120×65 мм, укладка плашмя поперёк траншеи:
                 n_bricks = ceil(width_m / 0.25 + 1) × ceil(length_m) шт
      "плита"  → ПК 1000×800×40 мм:
                 n_slabs = ceil(length_m / 1.0) × ceil(width_m / 0.8) шт

    Возвращает dict:
      length_m, n_cables, width_m, depth_m, soil_type, protection,
      v_excavation_m3  — объём выемки грунта
      v_loose_m3       — с коэффициентом разрыхления (для вывоза)
      v_sand_m3        — объём песчаной подсыпки
      v_backfill_m3    — объём обратной засыпки
      n_bricks         — шт (protection="кирпич", иначе 0)
      n_slabs          — шт (protection="плита",  иначе 0)
      depth_min_pue_m  — минимальная глубина по ПУЭ 2.3.83 (справочно)
    """
    # Ширина траншеи
    if n_cables <= 1:
        width_m = 0.30
    elif n_cables == 2:
        width_m = 0.50
    else:
        width_m = 0.50 + (n_cables - 2) * 0.15

    # Минимальная глубина по ПУЭ 2.3.83
    depth_min_pue_m = 1.00 if voltage_kv > 1.0 else 0.70

    # Объём выемки (прямоугольное сечение)
    v_excavation_m3 = length_m * width_m * depth_m

    # Объём с разрыхлением (для транспортировки)
    k_loosen = SOIL_LOOSEN.get(soil_type, 1.20)
    v_loose_m3 = v_excavation_m3 * k_loosen

    # Песчаная подсыпка: 100 мм снизу + 100 мм сверху
    v_sand_m3 = length_m * width_m * 0.20

    # Обратная засыпка = выемка − подсыпка
    v_backfill_m3 = max(v_excavation_m3 - v_sand_m3, 0.0)

    # Защитное покрытие
    if protection == "кирпич":
        bricks_per_m = math.ceil(width_m / 0.25) + 1
        n_bricks = bricks_per_m * math.ceil(length_m)
        n_slabs  = 0
    else:  # "плита"
        n_bricks = 0
        n_slabs  = math.ceil(length_m / 1.0) * math.ceil(width_m / 0.8)

    return {
        "length_m":        length_m,
        "n_cables":        n_cables,
        "width_m":         round(width_m, 2),
        "depth_m":         depth_m,
        "soil_type":       soil_type,
        "protection":      protection,
        "v_excavation_m3": round(v_excavation_m3, 3),
        "v_loose_m3":      round(v_loose_m3, 3),
        "v_sand_m3":       round(v_sand_m3, 3),
        "v_backfill_m3":   round(v_backfill_m3, 3),
        "n_bricks":        n_bricks,
        "n_slabs":         n_slabs,
        "depth_min_pue_m": depth_min_pue_m,
    }


def calc_all_earthwork(project: dict) -> list[dict]:
    """
    Считает земляные работы для всех outdoor_networks с install="земля".
    Читает параметры из network.get("trench", {}).
    Сохраняет результат в project["_results"]["earthwork"].
    Возвращает список результатов.
    """
    results = []

    for net in project.get("outdoor_networks", []):
        cable = net.get("cable", {})
        if cable.get("install", "") != "земля":
            continue

        trench_cfg = net.get("trench", {})
        res = calc_trench(
            length_m   = float(cable.get("length_m", 0)),
            n_cables   = int(trench_cfg.get("n_cables", 1)),
            depth_m    = float(trench_cfg.get("depth_m", 0.7)),
            soil_type  = trench_cfg.get("soil_type", "суглинок"),
            protection = trench_cfg.get("protection", "кирпич"),
            voltage_kv = float(net.get("voltage_kv", 0.4)),
        )
        res["network_id"]   = net["id"]
        res["network_name"] = net.get("name", net["id"])
        results.append(res)

    project.setdefault("_results", {})["earthwork"] = results
    return results
