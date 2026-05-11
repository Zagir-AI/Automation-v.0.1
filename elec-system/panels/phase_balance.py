"""
panels/phase_balance.py — автоматическая балансировка фаз для однофазных потребителей.

Функции:
  - auto_assign_phases() — назначает фазы A/B/C однофазным потребителям (жадный алгоритм)
  - calc_phase_balance() — рассчитывает токи по фазам и дисбаланс
"""

import copy
from math import sqrt


def _estimate_current(c: dict) -> float:
    """
    Оценочный ток однофазного потребителя для алгоритма балансировки.
    
    I = P × kс / (U × cos φ)
    где U = 220В (фазное напряжение)
    """
    p_kw = c.get("power_kw", 0.0)
    ks = c.get("demand_factor", 0.8)
    cos = c.get("cos_phi", 0.85) or 0.85
    return p_kw * ks / (0.22 * cos)  # 220В однофазная сеть


def auto_assign_phases(consumers: list[dict]) -> list[dict]:
    """
    Назначает фазы однофазным потребителям внутри одного щита.
    
    Алгоритм:
      1. Трёхфазные (phases=3) пропускаются — не получают поле phase
      2. Уже назначенные (phase уже есть и не пустое) — не перезаписываются
      3. Жадный алгоритм: сортируем по оценочному току DESC,
         каждый следующий потребитель идёт на фазу с наименьшей суммой токов
    
    Args:
        consumers: список потребителей щита
    
    Returns:
        КОПИЯ списка с добавленным полем phase (входной список не мутируется)
    """
    result = copy.deepcopy(consumers)
    
    # Разделяем на однофазные без назначения и остальные
    to_assign = []
    for i, c in enumerate(result):
        phases = c.get("phases", 3)
        existing_phase = c.get("phase", "").strip()
        
        if phases == 1 and not existing_phase:
            # Оценочный ток для сортировки
            i_est = _estimate_current(c)
            to_assign.append((i, i_est))
    
    # Сортируем по убыванию тока (самые мощные первыми)
    to_assign.sort(key=lambda x: x[1], reverse=True)
    
    # Счётчики нагрузки по фазам
    phase_loads = {"A": 0.0, "B": 0.0, "C": 0.0}
    
    # Учитываем уже назначенные однофазные потребители
    for c in result:
        if c.get("phases", 3) == 1 and c.get("phase", "").strip():
            phase = c["phase"].strip().upper()
            if phase in phase_loads:
                phase_loads[phase] += _estimate_current(c)
    
    # Назначаем фазы
    for idx, i_est in to_assign:
        # Находим фазу с минимальной нагрузкой
        min_phase = min(phase_loads, key=phase_loads.get)
        result[idx]["phase"] = min_phase
        phase_loads[min_phase] += i_est
    
    return result


def calc_phase_balance(consumers_results: list[dict]) -> dict:
    """
    Считает токи по фазам и дисбаланс по результатам потребителей (_results).
    
    Правила:
      - Однофазный потребитель (phases=1): его i_calc_a идёт в phase (A/B/C)
      - Трёхфазный (phases=3): его i_calc_a добавляется в каждую фазу
        (i_calc_a — это линейный ток, уже трёхфазный, не делим на sqrt(3))
    
    Args:
        consumers_results: список результатов потребителей из calc_panel()["consumers"]
    
    Returns:
        {
          "A": {"p_kw": float, "i_a": float},
          "B": {"p_kw": float, "i_a": float},
          "C": {"p_kw": float, "i_a": float},
          "imbalance_pct": float,   # (max-min)/avg*100, 0 если avg==0
          "imbalance_a":  float,    # max_i - min_i
        }
    """
    phase_data = {
        "A": {"p_kw": 0.0, "i_a": 0.0},
        "B": {"p_kw": 0.0, "i_a": 0.0},
        "C": {"p_kw": 0.0, "i_a": 0.0},
    }
    
    for c in consumers_results:
        phases = c.get("phases", 3)
        i_calc = c.get("i_calc_a", 0.0)
        p_calc = c.get("p_calc_kw", 0.0)
        
        if phases == 1:
            # Однофазный — добавляем в назначенную фазу
            phase = c.get("phase", "").strip().upper()
            if phase in phase_data:
                phase_data[phase]["i_a"] += i_calc
                phase_data[phase]["p_kw"] += p_calc
        elif phases == 3:
            # Трёхфазный — добавляем в каждую фазу
            # i_calc_a — это линейный ток, нагружает все три фазы одинаково
            for ph in ("A", "B", "C"):
                phase_data[ph]["i_a"] += i_calc
                phase_data[ph]["p_kw"] += p_calc / 3  # мощность делим на 3 фазы
    
    # Округляем значения
    for ph in ("A", "B", "C"):
        phase_data[ph]["i_a"] = round(phase_data[ph]["i_a"], 2)
        phase_data[ph]["p_kw"] = round(phase_data[ph]["p_kw"], 3)
    
    # Расчёт дисбаланса
    currents = [phase_data[ph]["i_a"] for ph in ("A", "B", "C")]
    i_max = max(currents)
    i_min = min(currents)
    i_avg = sum(currents) / 3
    
    imbalance_pct = ((i_max - i_min) / i_avg * 100) if i_avg > 0 else 0.0
    imbalance_a = i_max - i_min
    
    return {
        **phase_data,
        "imbalance_pct": round(imbalance_pct, 1),
        "imbalance_a": round(imbalance_a, 2),
    }
