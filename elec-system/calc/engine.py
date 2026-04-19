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


def select_cable(cable_cfg: dict) -> dict:
    """
    Подбор сечения кабеля по расчётному току.

    cable_cfg: {"mark": "ВВГнг-LS", "cores": 4, "section_mm2": null или число,
                "length_m": 25, "install": "лоток", "ambient_t": 25, "parallel": 1}
    i_calc: расчётный ток линии
    i_calc_start: пусковой ток (для проверки)

    Возвращает обогащённый словарь с результатом.
    """
    result = dict(cable_cfg)  # копируем, не меняем оригинал
    return result


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
    cos_phi = cable_result.get("cos_phi", 0.85)
    sin_phi = math.sqrt(1 - cos_phi**2)

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

def calc_panel(panel: dict) -> dict:
    """
    Расчёт щита: нагрузки, кабели, автоматы всех потребителей.
    Возвращает dict с результатами.
    """
    consumers = panel.get("consumers", [])
    results_consumers = []

    p_calc_total = 0.0
    q_calc_total = 0.0

    for c in consumers:
        i_calc = calc_consumer_current(c)
        i_start = i_calc * c.get("start_factor", 1.0)

        # Кабель потребителя
        cable_cfg = dict(c.get("cable", {}))
        cable_cfg["cos_phi"] = c.get("cos_phi", 0.85)
        cable_result = select_cable_for_current(cable_cfg, i_calc, i_start)

        # Потеря напряжения
        du = calc_voltage_drop(cable_result, i_calc, c.get("phases", 3))
        cable_result["voltage_drop_pct"] = du

        # Автомат потребителя
        breaker_result = select_breaker_for_consumer(c, i_calc)

        # Вклад в суммарную мощность щита
        p_kw = c["power_kw"] * c.get("demand_factor",
               DEFAULT_DEMAND_FACTORS.get(c.get("type","default"), 0.70))
        cos_phi = c.get("cos_phi", 0.85)
        sin_phi = math.sqrt(1 - cos_phi**2)
        p_calc_total += p_kw
        q_calc_total += p_kw * sin_phi / cos_phi  # Q = P × tg φ

        results_consumers.append({
            "id": c["id"],
            "name": c["name"],
            "type": c.get("type", ""),
            "power_kw": c["power_kw"],
            "demand_factor": c.get("demand_factor",
                DEFAULT_DEMAND_FACTORS.get(c.get("type","default"), 0.70)),
            "p_calc_kw": round(p_kw, 3),
            "phases": c.get("phases", 3),
            "i_calc_a": i_calc,
            "i_start_a": round(i_calc * c.get("start_factor", 1.0), 2),
            "cable": cable_result,
            "breaker": breaker_result,
        })

    # Суммарный расчётный ток щита
    n = len(consumers)
    ku = get_simultaneous_factor(n)
    p_ku = p_calc_total * ku
    q_ku = q_calc_total * ku
    s_calc = math.sqrt(p_ku**2 + q_ku**2)
    cos_phi_panel = p_ku / s_calc if s_calc > 0 else 0.85
    cos_phi_panel = min(max(cos_phi_panel, 0.5), 1.0)

    i_panel = s_calc * 1000 / (math.sqrt(3) * U_LINE) if n > 0 else 0
    i_panel = round(i_panel, 2)

    # Питающий кабель щита
    panel_cable_cfg = dict(panel.get("cable", {}))
    panel_cable_cfg.setdefault("cos_phi", cos_phi_panel)
    panel_cable_result = select_cable_for_current(panel_cable_cfg, i_panel)
    du_panel = calc_voltage_drop(panel_cable_result, i_panel, 3)
    panel_cable_result["voltage_drop_pct"] = du_panel

    # Вводной автомат щита
    panel_breaker = select_panel_breaker(i_panel)

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

def calc_feeder(feeder: dict) -> dict:
    """Расчёт фидера: суммирует щиты."""
    panels_results = []
    p_total = 0.0
    q_total = 0.0

    for panel in feeder.get("panels", []):
        pr = calc_panel(panel)
        panels_results.append(pr)
        cos_phi = pr["cos_phi"]
        sin_phi = math.sqrt(max(0, 1 - cos_phi**2))
        p_total += pr["p_calc_kw"]
        q_total += pr["p_calc_kw"] * (sin_phi / cos_phi) if cos_phi > 0 else 0

    n_panels = len(panels_results)
    ku = get_simultaneous_factor(n_panels) if n_panels > 1 else 1.0
    s_total = math.sqrt(p_total**2 + q_total**2) * ku
    cos_phi_f = p_total / s_total if s_total > 0 else 0.85
    cos_phi_f = min(max(cos_phi_f, 0.5), 1.0)
    i_feeder = s_total * 1000 / (math.sqrt(3) * U_LINE) if s_total > 0 else 0

    return {
        "id": feeder["id"],
        "name": feeder["name"],
        "section": feeder.get("section", ""),
        "panels": panels_results,
        "p_calc_kw": round(p_total * ku, 3),
        "s_calc_kva": round(s_total, 3),
        "cos_phi": round(cos_phi_f, 3),
        "ku": round(ku, 3),
        "i_calc_a": round(i_feeder, 2),
    }


# ─────────────────────────────────────────────
#  УРОВЕНЬ 4: ВРУ
# ─────────────────────────────────────────────

def calc_vru(vru: dict) -> dict:
    """Расчёт ВРУ: суммирует фидеры."""
    feeders_results = []
    p_total = 0.0
    q_total = 0.0

    for feeder in vru.get("feeders", []):
        fr = calc_feeder(feeder)
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

    vru_result = calc_vru(project["vru"])

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
    result["_meta"]["calc_done"] = True
    result["_meta"]["last_modified"] = datetime.date.today().isoformat()

    return result
