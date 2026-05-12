"""
outdoor/calc_outdoor.py — расчёт наружных сетей освещения (ПУЭ гл.2.1, 6.5).

Схема сети: ШУНО → кабельные линии → опоры (светильники).

Структура outdoor_networks[] в project.json:
  {
    "id":        "ОН-1",
    "name":      "Наружное освещение паркинга",
    "voltage_kv": 0.4,
    "cable": {"mark":"ВВГнг-LS", "cores":4, "length_m":120, "section_mm2":null},
    "consumers": [
      {"id":"СВ-01", "name":"Светильник LED", "power_kw":0.15, "cos_phi":0.95,
       "n_units":10, "demand_factor":1.0, "category_pue":3}
    ]
  }

Результат записывается в project["_results"]["outdoor_networks"].
"""

from __future__ import annotations
import math

from data.cables.pue_tables import (
    get_ampacity_table, get_install_key, get_conductor_material,
    get_temp_correction, STANDARD_SECTIONS,
)
from data.breakers.breaker_tables import select_breaker


# ── Расчёт линии ─────────────────────────────────────────────────────────────

def _calc_line_current(p_kw: float, cos_phi: float, voltage_kv: float,
                        phases: int = 3) -> float:
    """Расчётный ток линии, А."""
    if p_kw <= 0 or cos_phi <= 0:
        return 0.0
    u_v = voltage_kv * 1000
    if phases == 3:
        return p_kw * 1000 / (math.sqrt(3) * u_v * cos_phi)
    else:
        return p_kw * 1000 / (u_v * cos_phi)


def _select_cable_section(i_calc: float, cable_mark: str,
                           install_key: str, ambient_t: float = 25) -> float | None:
    """Подбирает минимальное сечение кабеля по допустимому току."""
    k_temp = get_temp_correction(install_key, ambient_t)
    table = get_ampacity_table(cable_mark)
    for section in STANDARD_SECTIONS:
        i_allow_base = table.get(section, {}).get(install_key, 0)
        i_allow = i_allow_base * k_temp
        if i_allow >= i_calc:
            return section
    return STANDARD_SECTIONS[-1]


def _calc_voltage_drop(p_kw: float, cos_phi: float, i_calc: float,
                        section_mm2: float, length_m: float,
                        cable_mark: str, phases: int = 3,
                        voltage_kv: float = 0.4) -> float:
    """Потеря напряжения в процентах (ПУЭ формула)."""
    from data.cables.pue_tables import CABLE_RESISTANCE
    material = get_conductor_material(cable_mark)
    r0, x0 = CABLE_RESISTANCE.get((material, section_mm2), (0.0, 0.0))

    sin_phi = math.sqrt(max(0, 1 - cos_phi ** 2))
    l_km = length_m / 1000

    if phases == 3:
        u_v = voltage_kv * 1000
        dU = math.sqrt(3) * i_calc * l_km * (r0 * cos_phi + x0 * sin_phi)
        return round(dU / u_v * 100, 2)
    else:
        u_v = voltage_kv * 1000
        dU = 2 * i_calc * l_km * (r0 * cos_phi + x0 * sin_phi)
        return round(dU / u_v * 100, 2)


# ── Расчёт одной наружной сети ────────────────────────────────────────────────

def calc_outdoor_network(network: dict) -> dict:
    """
    Рассчитывает одну наружную сеть освещения.

    Args:
        network: элемент из project["outdoor_networks"]

    Returns:
        dict с расчётными результатами (p_calc_kw, i_calc_a, cable, breaker, consumers)
    """
    voltage_kv = network.get("voltage_kv", 0.4)
    phases     = network.get("phases", 3)
    cable_cfg  = network.get("cable", {})
    mark       = cable_cfg.get("mark", "ВВГнг-LS")
    cores      = cable_cfg.get("cores", 4)
    length_m   = cable_cfg.get("length_m", 50)
    fixed_sec  = cable_cfg.get("section_mm2")
    install    = cable_cfg.get("install", "земля")
    ambient_t  = cable_cfg.get("ambient_t", 15)  # для земли обычно 15°C

    install_key = get_install_key(install)

    # 1. Суммарная нагрузка
    consumers_result = []
    p_total = 0.0
    q_total = 0.0

    for c in network.get("consumers", []):
        p_unit    = c.get("power_kw", 0)
        cos_phi_c = c.get("cos_phi", 0.95)
        n_units   = c.get("n_units", 1)
        kd        = c.get("demand_factor", 1.0)
        cat       = c.get("category_pue", 3)

        p_calc_c = p_unit * n_units * kd
        q_calc_c = p_calc_c * math.sqrt(max(0, 1 - cos_phi_c**2)) / cos_phi_c if cos_phi_c > 0 else 0
        i_calc_c = _calc_line_current(p_calc_c, cos_phi_c, voltage_kv, phases)

        # Автомат для группы потребителей
        br_c = select_breaker(i_calc_c * 1.1)

        consumers_result.append({
            "id":           c.get("id"),
            "name":         c.get("name", ""),
            "power_kw":     p_unit,
            "n_units":      n_units,
            "demand_factor":kd,
            "cos_phi":      cos_phi_c,
            "p_calc_kw":    round(p_calc_c, 3),
            "i_calc_a":     round(i_calc_c, 3),
            "category_pue": cat,
            "breaker":      br_c,
        })

        if not c.get("reserve", False):
            p_total += p_calc_c
            q_total += q_calc_c

    # 2. Суммарный ток
    s_total = math.sqrt(p_total**2 + q_total**2)
    cos_phi_net = p_total / s_total if s_total > 0 else 1.0
    i_calc = _calc_line_current(p_total, cos_phi_net, voltage_kv, phases)

    # 3. Кабель
    k_temp   = get_temp_correction(install_key, ambient_t)
    section  = fixed_sec if fixed_sec else _select_cable_section(
        i_calc * 1.25,  # запас 25% для наружного освещения
        mark, install_key, ambient_t
    )
    table_    = get_ampacity_table(mark)
    i_allow_base = table_.get(section, {}).get(install_key, 0)
    i_allow   = i_allow_base * k_temp
    cable_ok  = i_allow >= i_calc

    dU = _calc_voltage_drop(p_total, cos_phi_net, i_calc, section, length_m,
                            mark, phases, voltage_kv)
    # ПУЭ 7.1.68: ΔU ≤ 5% для наружного освещения
    du_limit  = 5.0
    du_ok     = dU <= du_limit

    cable_result = {
        "mark":         mark,
        "cores":        cores,
        "section_mm2":  section,
        "length_m":     length_m,
        "install":      install,
        "install_key":  install_key,
        "i_calc":       round(i_calc, 2),
        "i_allowed":    round(i_allow, 1),
        "ambient_t":    ambient_t,
        "k_temp":       round(k_temp, 3),
        "voltage_drop_pct": dU,
        "du_limit_pct": du_limit,
        "ok":           cable_ok and du_ok,
        "auto_selected": fixed_sec is None,
    }

    # 4. Автомат линии (ШУНО → кабель)
    breaker = select_breaker(i_calc * 1.1)

    return {
        "id":             network.get("id"),
        "name":           network.get("name", ""),
        "voltage_kv":     voltage_kv,
        "p_installed_kw": round(sum(c.get("power_kw",0)*c.get("n_units",1)
                                    for c in network.get("consumers",[])), 3),
        "p_calc_kw":      round(p_total, 3),
        "cos_phi":        round(cos_phi_net, 3),
        "i_calc_a":       round(i_calc, 3),
        "cable":          cable_result,
        "breaker":        breaker,
        "consumers":      consumers_result,
    }


# ── Публичный API ─────────────────────────────────────────────────────────────

def calc_all_outdoor(project: dict) -> dict:
    """
    Рассчитывает все наружные сети из project["outdoor_networks"].

    Записывает результат в project["_results"]["outdoor_networks"].
    Возвращает обновлённый project.
    """
    networks = project.get("outdoor_networks", [])

    results = []
    for net in networks:
        results.append(calc_outdoor_network(net))

    project.setdefault("_results", {})
    project["_results"]["outdoor_networks"] = results
    return project


def print_outdoor_report(project: dict) -> None:
    """Выводит отчёт по наружным сетям."""
    results = project.get("_results", {}).get("outdoor_networks", [])
    if not results:
        print("Наружные сети не заданы")
        return

    print(f"\nНаружные сети освещения: {len(results)} линий")
    for net in results:
        cable = net.get("cable", {})
        br    = net.get("breaker", {})
        ok    = cable.get("ok", True)
        flag  = "✓" if ok else "✗"

        print(f"\n  {flag} {net['id']} — {net['name']}")
        print(f"    Pуст={net['p_installed_kw']:.2f} кВт  "
              f"Pрасч={net['p_calc_kw']:.3f} кВт  "
              f"I={net['i_calc_a']:.2f} А")
        if cable:
            print(f"    Кабель: {cable['mark']} {cable['cores']}×{cable['section_mm2']}мм²  "
                  f"L={cable['length_m']}м  "
                  f"ΔU={cable['voltage_drop_pct']}% (≤{cable['du_limit_pct']}%)")
        if br:
            print(f"    АВ: {br.get('type','')}")
        if not ok:
            if not cable.get("ok"):
                print(f"    ⚠ Кабель перегружен или превышено ΔU")
