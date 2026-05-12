"""
calc/compensation.py — расчёт и подбор компенсации реактивной мощности (КРМ).

Условие применения (ПУЭ и тарифные требования):
  tgφ > 0.40 → предупреждение
  tgφ > 0.33 → КРМ обязательна (тарифное регулирование для 0.4кВ)

tgφ = Q / P = sinφ / cosφ

Данные читаются из project["_results"] — не из vru напрямую.
"""

import math

# ── Константы ─────────────────────────────────────────────────────────────────
TG_PHI_LIMIT   = 0.33   # порог тарифного регулирования (ПУЭ)
TG_PHI_WARNING = 0.40   # порог предупреждения
TG_PHI_TARGET  = 0.33   # целевое значение после компенсации

# Стандартный ряд батарей конденсаторов, кВАр
KRM_STANDARD_SERIES = [10, 15, 20, 25, 30, 40, 50, 75, 100, 150, 200]


def _tg_phi(cos_phi: float) -> float:
    """tgφ = sinφ / cosφ = √(1 - cos²φ) / cosφ"""
    cos_phi = max(0.01, min(cos_phi, 1.0))
    sin_phi = math.sqrt(1 - cos_phi ** 2)
    return sin_phi / cos_phi


def _select_krm_rating(q_kvar: float) -> int:
    """Подбирает ближайший больший номинал КРМ из стандартного ряда."""
    for rating in KRM_STANDARD_SERIES:
        if rating >= q_kvar:
            return rating
    return KRM_STANDARD_SERIES[-1]


def check_compensation_needed(project: dict) -> dict:
    """
    Проверяет необходимость КРМ по результатам расчёта ВРУ.

    Читает из project["_results"]["vru"].

    Returns dict с ключами:
      required      — bool, нужна ли КРМ
      warning       — bool, tgφ > 0.40 но < порога
      tg_phi_fact   — фактическое tgφ на шинах ВРУ
      tg_phi_target — целевое tgφ (0.33)
      p_kw          — активная мощность ВРУ
      q_kvar_fact   — реактивная мощность до компенсации
      q_comp_kvar   — требуемая компенсация, кВАр
      selected_krm  — подобранная батарея конденсаторов
      panels        — список щитов с tgφ > TG_PHI_WARNING
    """
    vru = project.get("_results", {}).get("vru", {})

    p_kw     = vru.get("p_calc_kw", 0)
    cos_phi  = vru.get("cos_phi", 1.0)
    s_kva    = vru.get("s_calc_kva", 0)

    if p_kw <= 0:
        return {"required": False, "warning": False,
                "tg_phi_fact": 0, "tg_phi_target": TG_PHI_TARGET,
                "p_kw": 0, "q_kvar_fact": 0, "q_comp_kvar": 0,
                "selected_krm": None, "panels": []}

    tg_fact  = _tg_phi(cos_phi)
    q_fact   = p_kw * tg_fact

    required = tg_fact > TG_PHI_LIMIT
    warning  = TG_PHI_WARNING >= tg_fact > TG_PHI_LIMIT

    q_comp   = 0.0
    krm      = None
    if required:
        q_target = p_kw * TG_PHI_TARGET
        q_comp   = max(0.0, round(q_fact - q_target, 2))
        krm_rating = _select_krm_rating(q_comp)
        krm = {
            "power_kvar": krm_rating,
            "model":      f"КРМ-0.4-{krm_rating}",
            "voltage_kv": 0.4,
            "note":       "Автоматическая батарея конденсаторов",
        }

    # Собираем щиты с повышенным tgφ для информации
    panels_info = []
    for feeder in vru.get("feeders", []):
        for panel in feeder.get("panels", []):
            p_cos = panel.get("cos_phi", 1.0)
            if p_cos and p_cos < 1.0:
                p_tg = _tg_phi(p_cos)
                if p_tg > TG_PHI_WARNING:
                    panels_info.append({
                        "id":      panel.get("id"),
                        "name":    panel.get("name", ""),
                        "cos_phi": round(p_cos, 3),
                        "tg_phi":  round(p_tg, 3),
                    })

    return {
        "required":      required,
        "warning":       warning,
        "tg_phi_fact":   round(tg_fact, 3),
        "tg_phi_target": TG_PHI_TARGET,
        "p_kw":          round(p_kw, 2),
        "q_kvar_fact":   round(q_fact, 2),
        "q_comp_kvar":   round(q_comp, 2),
        "selected_krm":  krm,
        "panels":        panels_info,
    }


def select_compensator(q_comp_kvar: float) -> dict:
    """
    Подбирает батарею конденсаторов по требуемой мощности компенсации.

    Args:
        q_comp_kvar: требуемая реактивная мощность компенсации, кВАр

    Returns:
        dict: {"power_kvar", "model", "voltage_kv", "note"}
    """
    rating = _select_krm_rating(q_comp_kvar)
    return {
        "power_kvar": rating,
        "model":      f"КРМ-0.4-{rating}",
        "voltage_kv": 0.4,
        "note":       "Автоматическая батарея конденсаторов",
    }


def update_compensation(project: dict) -> dict:
    """
    Считает КРМ и записывает результат в project["compensation"].
    Не изменяет исходные данные.
    """
    result = check_compensation_needed(project)
    project["compensation"] = {
        "required":      result["required"],
        "tg_phi_fact":   result["tg_phi_fact"],
        "tg_phi_target": result["tg_phi_target"],
        "q_comp_kvar":   result["q_comp_kvar"],
        "selected_krm":  result["selected_krm"],
    }
    return project


def print_compensation_report(result: dict) -> None:
    """Выводит отчёт по КРМ."""
    print(f"\nКомпенсация реактивной мощности:")
    print(f"  Активная мощность P    = {result['p_kw']:.2f} кВт")
    print(f"  Реактивная мощность Q  = {result['q_kvar_fact']:.2f} кВАр")
    print(f"  tgφ фактический        = {result['tg_phi_fact']:.3f}")
    print(f"  tgφ целевой (ПУЭ)      = {result['tg_phi_target']:.3f}")

    if result["required"]:
        krm = result["selected_krm"]
        print(f"\n  ⚠ КРМ ОБЯЗАТЕЛЬНА (tgφ={result['tg_phi_fact']} > {TG_PHI_LIMIT})")
        print(f"  Требуемая компенсация  = {result['q_comp_kvar']:.1f} кВАр")
        print(f"  Подобрана батарея:     {krm['model']} ({krm['power_kvar']} кВАр)")
    elif result["warning"]:
        print(f"\n  ⚡ Предупреждение: tgφ={result['tg_phi_fact']} > {TG_PHI_WARNING} — рекомендуется КРМ")
    else:
        print(f"\n  ✓ КРМ не требуется (tgφ={result['tg_phi_fact']} ≤ {TG_PHI_LIMIT})")

    if result["panels"]:
        print(f"\n  Щиты с повышенным tgφ:")
        for p in result["panels"]:
            print(f"    {p['id']}: cosφ={p['cos_phi']}, tgφ={p['tg_phi']}")
