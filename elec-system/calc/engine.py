"""
calc/engine.py — расчётный движок системы.

Алгоритм:
  1. Для каждого потребителя → расчётный ток Iр
  2. Подбор кабеля потребителя
  3. Подбор автомата потребителя
  4. Для щита → суммарная нагрузка (метод коэфф. спроса + участия в максимуме)
  5. Подбор питающего кабеля щита
  6. Подбор вводного автомата щита
  7. Для ВРУ → суммарная нагрузка всех фидеров
  8. Запись результатов обратно в project dict

Всё записывается в project["_results"] — исходные данные не меняются.
"""

import math
import sys
import os

# Добавляем корень проекта в path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from data.cables.pue_tables import (
    get_ampacity_table, get_conductor_material, get_install_key,
    get_temp_correction, STANDARD_SECTIONS, CABLE_RESISTANCE, CABLE_MARK_MAP
)
from data.breakers.breaker_tables import (
    select_breaker_for_consumer, select_panel_breaker, select_breaker
)
from data.demand_factors.sp256_factors import (
    DEFAULT_DEMAND_FACTORS, get_simultaneous_factor, MAX_VOLTAGE_DROP
)

U_PHASE = 220.0   # В — фазное напряжение
U_LINE  = 380.0   # В — линейное напряжение

# Запасы по умолчанию (%)
CABLE_RESERVE_INDOOR  = 20.0
CABLE_RESERVE_OUTDOOR = 20.0

# ── Критерии выбора кабеля ────────────────────────────────────────────────────

# Допустимые потери напряжения по типу потребителя, % (ПУЭ 7.1.67, 7.1.60)
_DU_LIMITS: dict[str, float] = {
    "lighting":         2.5,
    "outdoor_lighting": 5.0,
    "sockets":          5.0,
    "it_equipment":     5.0,
    "hvac":             5.0,
    "motor":            5.0,
    "pump":             5.0,
    "elevator":         5.0,
    "kitchen":          5.0,
    "welding":          5.0,
    "ventilation_unit": 5.0,
    "smoke_fan":        5.0,
    "panel":            5.0,   # питающий кабель щита
    "default":          5.0,
}

# Коэффициент термической стойкости (ГОСТ 28249-93, ПУЭ 1.4.17)
# S_мин = I_кз(А) × √(t_откл(с)) / C
_KZ_C = {"copper": 115, "aluminium": 74}
_KZ_T_TRIP_S = 0.02   # время отключения, с (мгновенный расцепитель АВ)

# Минимальный кратность тока мгновенного расцепителя по характеристике
_TRIP_K_MIN = {"B": 3, "C": 5, "D": 10}


def _du_limit(consumer_type: str) -> float:
    """Допустимая потеря напряжения для типа потребителя, %."""
    return _DU_LIMITS.get(consumer_type, _DU_LIMITS["default"])


def _calc_isc_end(isc_ka_source: float, mark: str, section: float,
                   length_m: float) -> float:
    """
    Ток однофазного КЗ (фаза–ноль) в конце кабельной линии, А.

    Z_ист = U_ф / I_кз_ист
    I_кз_кон = U_ф / (Z_ист + 2 × r_каб)
    (реактивная составляющая кабеля пренебрежимо мала до 240мм²)
    """
    material = get_conductor_material(mark)
    r0, _   = CABLE_RESISTANCE.get((material, section), (0.5, 0.0))
    z_src   = U_PHASE / max(isc_ka_source * 1000, 1)
    r_cable = 2 * r0 * length_m / 1000          # туда + обратно (ф+0)
    z_total = z_src + r_cable
    return round(U_PHASE / z_total, 1) if z_total > 0 else 0.0


def _upgrade_section_for_du(cable_result: dict, i_calc: float,
                             phases: int, du_max: float) -> dict:
    """
    Проверяет ΔU для выбранного сечения и при необходимости увеличивает его.

    Перебирает стандартные сечения начиная с текущего вверх.
    Возвращает обновлённый cable_result с полями:
      voltage_drop_pct, du_limit_pct, du_ok, section_upgraded_for_du
    """
    section = cable_result.get("section_mm2")
    if not section:
        return cable_result

    mark     = cable_result.get("mark", "ВВГнг-LS")
    install  = cable_result.get("install_key", "tray")
    k_temp   = cable_result.get("k_temp", 1.0)
    parallel = cable_result.get("parallel", 1)
    cos_phi  = cable_result.get("cos_phi", 0.85)
    length_m = cable_result.get("length_m", 0)
    sin_phi  = math.sqrt(max(0.0, 1.0 - cos_phi ** 2))
    material = get_conductor_material(mark)
    amp_tab  = get_ampacity_table(mark)

    start = STANDARD_SECTIONS.index(section) if section in STANDARD_SECTIONS else 0

    for s in STANDARD_SECTIONS[start:]:
        if s not in amp_tab:
            continue
        i_base = amp_tab[s].get(install)
        if not i_base:
            continue
        i_allowed = i_base * k_temp * parallel
        if i_allowed < i_calc:
            continue

        r0, x0   = CABLE_RESISTANCE.get((material, s), (0.5, 0.08))
        z_eff    = r0 * cos_phi + x0 * sin_phi
        length_km = length_m / 1000.0

        if phases == 3:
            du = math.sqrt(3) * i_calc * length_km * z_eff / U_LINE * 100
        else:
            du = 2.0 * i_calc * length_km * z_eff / U_PHASE * 100
        du = round(du, 2)

        if du <= du_max:
            upgraded = (s != section)
            upd = dict(cable_result)
            upd.update({
                "section_mm2":             s,
                "i_allowed":               round(i_allowed, 2),
                "ok":                      True,
                "voltage_drop_pct":        du,
                "du_limit_pct":            du_max,
                "du_ok":                   True,
                "section_upgraded_for_du": upgraded,
            })
            return upd

    # Ни одно сечение не укладывается в ΔU — возвращаем с флагом предупреждения
    upd = dict(cable_result)
    upd.update({"du_limit_pct": du_max, "du_ok": False,
                "section_upgraded_for_du": False})
    return upd


def _add_kz_checks(cable_result: dict, i_calc: float, phases: int,
                    breaker_rating: int, breaker_char: str,
                    isc_ka_source: float) -> dict:
    """
    Добавляет в cable_result результаты двух проверок по токам КЗ:

    1. Термическая стойкость (ПУЭ 1.4.17 / ГОСТ 28249-93):
       S_мин = I_кз_ист(А) × √(t_откл) / C

    2. Чувствительность защиты (ПУЭ 3.1.8):
       I_кз_конец ≥ k_мин × I_ном_АВ
       (ПУЭ — автомат должен отключить КЗ в мгновенной зоне)
    """
    section  = cable_result.get("section_mm2")
    mark     = cable_result.get("mark", "ВВГнг-LS")
    length_m = cable_result.get("length_m", 0)

    if not section or not isc_ka_source:
        return cable_result

    material = get_conductor_material(mark)
    C        = _KZ_C.get(material, 115)

    # 1. Термическая стойкость
    i_kz_src_a   = isc_ka_source * 1000
    s_min_thermal = i_kz_src_a * math.sqrt(_KZ_T_TRIP_S) / C
    # Ближайший стандартный номинал ≥ s_min_thermal
    s_std_thermal = STANDARD_SECTIONS[-1]
    for s in STANDARD_SECTIONS:
        if s >= s_min_thermal:
            s_std_thermal = s
            break
    kz_thermal_ok = (section >= s_std_thermal)

    # 2. Чувствительность защиты
    i_kz_end    = _calc_isc_end(isc_ka_source, mark, section, length_m)
    k_min       = _TRIP_K_MIN.get(breaker_char, 5)
    i_trip_min  = k_min * breaker_rating
    kz_sens_ok  = (i_kz_end >= i_trip_min)

    upd = dict(cable_result)
    upd.update({
        "kz_thermal_ok":        kz_thermal_ok,
        "kz_thermal_s_min_mm2": s_std_thermal,
        "kz_sens_ok":           kz_sens_ok,
        "kz_sens_i_end_a":      int(i_kz_end),
        "kz_sens_i_trip_min_a": i_trip_min,
        "isc_ka_source":        isc_ka_source,
    })
    return upd


def effective_cable_length(cable_cfg: dict, building: dict | None = None) -> float:
    """
    Расчётная длина кабеля с учётом cable_routing.

    Три режима (cable_routing.mode):
      reserve_only  — L = length_m × (1 + reserve_pct/100)
      floor_height  — L = (length_m + этажи × H_этажа + extra_m) × (1 + reserve_pct/100)
      manual        — L = manual_length_m (запас не добавляется)

    building: {"floor_height_m": 3.0, ...}  — берётся из project["building"]
    """
    routing     = cable_cfg.get("cable_routing") or {}
    mode        = routing.get("mode", "reserve_only")
    reserve_pct = routing.get("reserve_pct", CABLE_RESERVE_INDOOR)

    if mode == "manual":
        return float(routing.get("manual_length_m", cable_cfg.get("length_m", 0)))

    base = float(cable_cfg.get("length_m", 0))

    if mode == "floor_height":
        fh      = (building or {}).get("floor_height_m", 3.0)
        up      = routing.get("floors_up",   0)
        down    = routing.get("floors_down",  0)
        extra   = routing.get("extra_m",      2.0)
        base   += (up + down) * fh + extra

    return round(base * (1 + reserve_pct / 100), 1)


def routing_note(cable_cfg: dict, building: dict | None = None) -> str:
    """Текстовое пояснение как посчитана длина (для примечания в спецификации)."""
    routing = cable_cfg.get("cable_routing") or {}
    mode    = routing.get("mode", "reserve_only")
    l_plan  = cable_cfg.get("length_m", 0)

    if mode == "manual":
        return "ручной ввод"
    if mode == "floor_height":
        fh   = (building or {}).get("floor_height_m", 3.0)
        up   = routing.get("floors_up",  0)
        down = routing.get("floors_down", 0)
        ex   = routing.get("extra_m",    2.0)
        pct  = routing.get("reserve_pct", CABLE_RESERVE_INDOOR)
        return (f"план {l_plan}м + стояк {up+down}эт.×{fh}м + "
                f"запас {ex}м + {pct:.0f}%")
    pct = routing.get("reserve_pct", CABLE_RESERVE_INDOOR)
    return f"план {l_plan}м + запас {pct:.0f}%"


# ─────────────────────────────────────────────
#  УРОВЕНЬ 1: ПОТРЕБИТЕЛЬ
# ─────────────────────────────────────────────

def calc_consumer_current(consumer: dict) -> float:
    """Расчётный ток потребителя, А."""
    p = consumer["power_kw"] * 1000  # Вт
    cos_phi = consumer.get("cos_phi", 0.85)
    eta = consumer.get("eta", 1.0)
    kd = consumer.get("demand_factor",
                       DEFAULT_DEMAND_FACTORS.get(consumer.get("type","default"), 0.70))
    phases = consumer.get("phases", 3)

    # Расчётная мощность с учётом коэфф. спроса
    p_calc = p * kd

    if phases == 3:
        i = p_calc / (math.sqrt(3) * U_LINE * cos_phi * eta)
    else:
        i = p_calc / (U_PHASE * cos_phi * eta)

    return round(i, 3)



def select_cable_for_current(cable_cfg: dict, i_calc: float, i_start: float = 0) -> dict:
    """Полный подбор кабеля с проверкой по допустимому току."""
    mark = cable_cfg.get("mark", "ВВГнг-LS")
    install_str = cable_cfg.get("install", "лоток")
    ambient_t = cable_cfg.get("ambient_t", 25)
    parallel = cable_cfg.get("parallel", 1)

    install_key = get_install_key(install_str)
    k_temp = get_temp_correction(install_key, ambient_t)

    amp_table = get_ampacity_table(mark)

    # Если сечение задано явно — только проверяем
    forced_section = cable_cfg.get("section_mm2")
    if forced_section:
        i_allowed = amp_table.get(forced_section, {}).get(install_key, 0)
        i_allowed_corr = i_allowed * k_temp * parallel
        return {
            **cable_cfg,
            "section_mm2": forced_section,
            "i_calc": round(i_calc, 2),
            "i_allowed": round(i_allowed_corr, 2),
            "ok": i_allowed_corr >= i_calc,
            "install_key": install_key,
            "k_temp": round(k_temp, 3),
            "auto_selected": False,
        }

    # Автоподбор сечения
    selected_section = None
    selected_i_allowed = 0

    for section in STANDARD_SECTIONS:
        if section not in amp_table:
            continue
        i_base = amp_table[section].get(install_key)
        if i_base is None:
            continue
        i_allowed = i_base * k_temp * parallel
        if i_allowed >= i_calc:
            selected_section = section
            selected_i_allowed = i_allowed
            break

    if selected_section is None:
        return {
            **cable_cfg,
            "section_mm2": None,
            "i_calc": round(i_calc, 2),
            "i_allowed": 0,
            "ok": False,
            "error": f"Не найдено сечение для Iр={i_calc:.1f}А, марка {mark}, прокладка: {install_str}",
            "install_key": install_key,
            "k_temp": round(k_temp, 3),
            "auto_selected": True,
        }

    return {
        **cable_cfg,
        "section_mm2": selected_section,
        "i_calc": round(i_calc, 2),
        "i_allowed": round(selected_i_allowed, 2),
        "ok": True,
        "install_key": install_key,
        "k_temp": round(k_temp, 3),
        "auto_selected": True,
    }


def calc_voltage_drop(cable_result: dict, i_calc: float, phases: int) -> float:
    """
    Расчёт потери напряжения, %.
    ΔU% = (√3 × Iр × L × (r₀×cosφ + x₀×sinφ)) / Uн  — для 3ф
    ΔU% = (2 × Iр × L × (r₀×cosφ + x₀×sinφ)) / Uн    — для 1ф
    L — длина в км
    """
    section = cable_result.get("section_mm2")
    if not section:
        return 0.0

    mark = cable_result.get("mark", "ВВГнг-LS")
    material = get_conductor_material(mark)
    length_km = cable_result.get("length_m", 0) / 1000.0
    cos_phi = min(max(cable_result.get("cos_phi", 0.85), 0.01), 1.0)
    sin_phi = math.sqrt(max(0.0, 1 - cos_phi**2))

    r0, x0 = CABLE_RESISTANCE.get((material, section), (0.5, 0.08))

    z_eff = r0 * cos_phi + x0 * sin_phi  # Ом/км

    if phases == 3:
        du = math.sqrt(3) * i_calc * length_km * z_eff / U_LINE * 100
    else:
        du = 2 * i_calc * length_km * z_eff / U_PHASE * 100

    return round(du, 2)


# ─────────────────────────────────────────────
#  УРОВЕНЬ 2: ЩИТ
# ─────────────────────────────────────────────

def calc_panel(panel: dict, building: dict | None = None, isc_ka: float = 10.0) -> dict:
    """
    Расчёт щита: нагрузки, кабели, автоматы всех потребителей.

    building: project["building"] — для расчёта длин кабелей по floor_height.
    isc_ka: ток КЗ на шинах ПИТАНИЯ (ВРУ/фидер), кА. Для потребителей
            используется пониженный Iкз на шинах самого щита, вычисленный
            через импеданс питающего кабеля (_calc_isc_end).
    reserve=True потребители: кабель и автомат подбираются, но НЕ суммируются в нагрузку.
    """
    consumers = panel.get("consumers", [])
    p_calc_total = 0.0
    q_calc_total = 0.0

    # ── ПРОХОД 1: кабели и автоматы потребителей (без КЗ-проверок) ──────
    # КЗ-проверки добавим позже — после того как узнаем Iкз на шинах щита.
    pass1 = []
    for c in consumers:
        is_reserve = c.get("reserve", False)
        i_calc  = calc_consumer_current(c)
        i_start = i_calc * c.get("start_factor", 1.0)

        breaker_result = select_breaker_for_consumer(c, i_calc)

        cable_cfg = dict(c.get("cable", {}))
        cable_cfg["cos_phi"] = c.get("cos_phi", 0.85)
        eff_len = effective_cable_length(cable_cfg, building)
        cable_cfg_calc = {**cable_cfg, "length_m": eff_len}
        i_cable_min = max(i_calc, breaker_result.get("rating", i_calc))
        cable_result = select_cable_for_current(cable_cfg_calc, i_cable_min, i_start)
        cable_result["length_m_plan"] = cable_cfg.get("length_m", 0)
        cable_result["length_m_calc"] = eff_len
        cable_result["routing_note"]  = routing_note(cable_cfg, building)

        du_max = _du_limit(c.get("type", "default"))
        cable_result = _upgrade_section_for_du(cable_result, i_calc, c.get("phases", 3), du_max)

        if not is_reserve:
            p_kw    = c["power_kw"] * c.get("demand_factor",
                      DEFAULT_DEMAND_FACTORS.get(c.get("type","default"), 0.70))
            cos_phi = c.get("cos_phi", 0.85)
            sin_phi = math.sqrt(max(0, 1 - cos_phi**2))
            p_calc_total += p_kw
            q_calc_total += p_kw * sin_phi / cos_phi
        else:
            p_kw = 0.0

        pass1.append((c, is_reserve, i_calc, i_start, breaker_result, cable_result, p_kw))

    # ── Питающий кабель щита ─────────────────────────────────────────────
    n = len(consumers)
    ku = get_simultaneous_factor(n)
    p_ku = p_calc_total * ku
    q_ku = q_calc_total * ku
    s_calc = math.sqrt(p_ku**2 + q_ku**2)
    cos_phi_panel = p_ku / s_calc if s_calc > 0 else 0.85
    cos_phi_panel = min(max(cos_phi_panel, 0.5), 1.0)

    i_panel = s_calc * 1000 / (math.sqrt(3) * U_LINE) if n > 0 else 0
    i_panel = round(i_panel, 2)

    panel_breaker = select_panel_breaker(i_panel)
    # Enforce engineer-specified minimum (e.g. for selectivity compliance)
    br_min = int(panel.get("breaker_min_rating", 0))
    if br_min and panel_breaker["rating"] < br_min:
        panel_breaker = select_panel_breaker(br_min / 1.1)

    panel_cable_cfg = dict(panel.get("cable", {}))
    panel_cable_cfg.setdefault("cos_phi", cos_phi_panel)
    p_eff_len = effective_cable_length(panel_cable_cfg, building)
    panel_cable_cfg_calc = {**panel_cable_cfg, "length_m": p_eff_len}
    i_cable_min = max(i_panel, panel_breaker.get("rating", i_panel))
    panel_cable_result = select_cable_for_current(panel_cable_cfg_calc, i_cable_min)
    panel_cable_result["length_m_plan"] = panel_cable_cfg.get("length_m", 0)
    panel_cable_result["length_m_calc"] = p_eff_len
    panel_cable_result["routing_note"]  = routing_note(panel_cable_cfg, building)
    panel_cable_result = _upgrade_section_for_du(panel_cable_result, i_panel, 3, _du_limit("panel"))
    # Питающий кабель щита проверяется при Iкз источника (ВРУ/фидер)
    panel_cable_result = _add_kz_checks(panel_cable_result, i_panel, 3,
                                        panel_breaker.get("rating", 6),
                                        panel_breaker.get("char", "C"),
                                        isc_ka)

    # Iкз на шинах щита: ниже, чем на шинах ВРУ, из-за импеданса питающего кабеля
    isc_ka_panel = _calc_isc_end(
        isc_ka,
        panel_cable_result.get("mark", "ВВГнг-LS"),
        panel_cable_result.get("section_mm2", 1.5),
        p_eff_len,
    ) / 1000  # А → кА
    isc_ka_consumers = max(isc_ka_panel, 0.01)

    # ── ПРОХОД 2: КЗ-проверки потребителей с Iкз на шинах щита ─────────
    results_consumers = []
    for c, is_reserve, i_calc, i_start, breaker_result, cable_result, p_kw in pass1:
        cable_result = _add_kz_checks(cable_result, i_calc, c.get("phases", 3),
                                      breaker_result.get("rating", 6),
                                      breaker_result.get("char", "C"),
                                      isc_ka_consumers)
        results_consumers.append({
            "id":           c["id"],
            "name":         c["name"],
            "type":         c.get("type", ""),
            "section":      c.get("section", ""),
            "power_kw":     c["power_kw"],
            "reserve":      is_reserve,
            "demand_factor":c.get("demand_factor",
                            DEFAULT_DEMAND_FACTORS.get(c.get("type","default"), 0.70)),
            "p_calc_kw":    round(p_kw, 3),
            "phases":       c.get("phases", 3),
            "cos_phi":      c.get("cos_phi", 0.85),
            "i_calc_a":     i_calc,
            "i_start_a":    round(i_start, 2),
            "cable":        cable_result,
            "breaker":      breaker_result,
            "category_pue": c.get("category_pue", panel.get("category_pue", 3)),
        })

    return {
        "id": panel["id"],
        "name": panel["name"],
        "floor": panel.get("floor", ""),
        "consumers": results_consumers,
        "n_consumers": n,
        "p_installed_kw": round(sum(c["power_kw"] for c in consumers), 2),
        "p_calc_kw": round(p_calc_total * ku, 3),
        "s_calc_kva": round(s_calc, 3),
        "cos_phi": round(cos_phi_panel, 3),
        "ku": round(ku, 3),
        "i_calc_a": i_panel,
        "cable": panel_cable_result,
        "breaker": panel_breaker,
    }


# ─────────────────────────────────────────────
#  УРОВЕНЬ 3: ФИДЕР
# ─────────────────────────────────────────────

def calc_feeder(feeder: dict, building: dict | None = None, isc_ka: float = 10.0) -> dict:
    """Расчёт фидера: суммирует щиты."""
    panels_results = []
    p_total = 0.0
    q_total = 0.0

    for panel in feeder.get("panels", []):
        pr = calc_panel(panel, building, isc_ka)
        panels_results.append(pr)
        cos_phi = pr["cos_phi"]
        sin_phi = math.sqrt(max(0, 1 - cos_phi**2))
        p_total += pr["p_calc_kw"]
        q_total += pr["p_calc_kw"] * (sin_phi / cos_phi) if cos_phi > 0 else 0

    n_panels = len(panels_results)
    ku = get_simultaneous_factor(n_panels) if n_panels > 1 else 1.0
    p_ku = p_total * ku
    q_ku = q_total * ku
    s_total = math.sqrt(p_ku**2 + q_ku**2)
    cos_phi_f = p_ku / s_total if s_total > 0 else 0.85
    cos_phi_f = min(max(cos_phi_f, 0.5), 1.0)
    i_feeder = s_total * 1000 / (math.sqrt(3) * U_LINE) if s_total > 0 else 0

    return {
        "id": feeder["id"],
        "name": feeder["name"],
        "section": feeder.get("section", ""),
        "panels": panels_results,
        "p_calc_kw": round(p_ku, 3),
        "s_calc_kva": round(s_total, 3),
        "cos_phi": round(cos_phi_f, 3),
        "ku": round(ku, 3),
        "i_calc_a": round(i_feeder, 2),
    }


# ─────────────────────────────────────────────
#  УРОВЕНЬ 4: ВРУ
# ─────────────────────────────────────────────

def calc_vru(vru: dict, building: dict | None = None) -> dict:
    """Расчёт ВРУ: суммирует фидеры."""
    isc_ka = float(vru.get("isc_ka", 10.0))
    feeders_results = []
    p_total = 0.0
    q_total = 0.0

    for feeder in vru.get("feeders", []):
        fr = calc_feeder(feeder, building, isc_ka)
        feeders_results.append(fr)
        cos_phi = fr["cos_phi"]
        sin_phi = math.sqrt(max(0, 1 - cos_phi**2))
        p_total += fr["p_calc_kw"]
        q_total += fr["p_calc_kw"] * (sin_phi / cos_phi) if cos_phi > 0 else 0

    n_feeders = len(feeders_results)
    ku = get_simultaneous_factor(n_feeders) if n_feeders > 1 else 1.0
    s_total = math.sqrt(p_total**2 + q_total**2) * ku
    # Взвешенный cos φ через компоненты P и Q
    p_ku = p_total * ku
    q_ku = q_total * ku
    cos_phi_v = p_ku / math.sqrt(p_ku**2 + q_ku**2) if (p_ku**2 + q_ku**2) > 0 else 0.85
    cos_phi_v = min(max(cos_phi_v, 0.5), 1.0)
    i_vru = s_total * 1000 / (math.sqrt(3) * U_LINE) if s_total > 0 else 0

    # Сумма установленных мощностей (из исходных данных)
    p_installed = sum(
        c.get("power_kw", 0)
        for f in vru.get("feeders", [])
        for panel in f.get("panels", [])
        for c in panel.get("consumers", [])
    )

    # Вводной автомат ВРУ (сначала автомат — потом кабель под него)
    vru_breaker = select_panel_breaker(i_vru)

    # Вводной кабель ВРУ: I_доп ≥ I_ном_автомата (ПУЭ 3.1.4)
    vru_cable_cfg = dict(vru.get("incoming_cable", {}))
    vru_cable_cfg.setdefault("cos_phi", cos_phi_v)
    if i_vru > 0:
        i_cable_min = max(i_vru, vru_breaker.get("rating", i_vru))
        vru_cable_result = select_cable_for_current(vru_cable_cfg, i_cable_min)
        vru_cable_result = _upgrade_section_for_du(vru_cable_result, i_vru, 3, _du_limit("panel"))
        vru_cable_result = _add_kz_checks(vru_cable_result, i_vru, 3,
                                          vru_breaker.get("rating", 6),
                                          vru_breaker.get("char", "C"),
                                          isc_ka)
    else:
        vru_cable_result = {**vru_cable_cfg, "section_mm2": None, "i_calc": 0,
                            "i_allowed": 0, "ok": False, "auto_selected": True}

    return {
        "id": vru["id"],
        "name": vru["name"],
        "feeders": feeders_results,
        "p_installed_kw": round(p_installed, 2),
        "p_calc_kw": round(p_total, 3),
        "s_calc_kva": round(s_total, 3),
        "cos_phi": round(cos_phi_v, 3),
        "ku": round(ku, 3),
        "i_calc_a": round(i_vru, 2),
        "incoming_cable": vru_cable_result,
        "breaker": vru_breaker,
    }


# ─────────────────────────────────────────────
#  ГЛАВНАЯ ФУНКЦИЯ: РАСЧЁТ ВСЕГО ПРОЕКТА
# ─────────────────────────────────────────────

def calculate_project(project: dict) -> dict:
    """
    Входит: dict из project.json
    Выходит: тот же dict с добавленным ключом "_results"
    Исходные данные НЕ меняются.
    """
    import copy
    import datetime

    result = copy.deepcopy(project)

    building   = project.get("building", {})
    vru_result = calc_vru(project["vru"], building)

    result["_results"] = {
        "calculated_at": datetime.datetime.now().isoformat(),
        "vru": vru_result,
        "summary": {
            "p_installed_kw": vru_result["p_installed_kw"],
            "p_calc_kw": vru_result["p_calc_kw"],
            "s_calc_kva": vru_result["s_calc_kva"],
            "cos_phi": vru_result["cos_phi"],
            "i_vru_a": vru_result["i_calc_a"],
            "incoming_cable": vru_result["incoming_cable"],
        }
    }

    if project.get("outdoor_networks"):
        try:
            from outdoor.calc_outdoor import calc_all_outdoor
            result = calc_all_outdoor(result)
        except Exception as e:
            result["_results"]["outdoor_error"] = str(e)

    # Категорийность здания и схема ВРУ (ПУЭ гл.1.2)
    try:
        from rules.category_rules import update_building_meta
        result = update_building_meta(result)
    except Exception:
        pass

    result["_meta"]["calc_done"] = True
    result["_meta"]["last_modified"] = datetime.date.today().isoformat()

    return result
