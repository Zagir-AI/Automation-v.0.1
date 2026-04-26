"""
rules/selectivity.py — проверка селективности автоматических выключателей.

Принцип: I_ном(вышестоящего) >= I_ном(нижестоящего) × RATIO_REQUIRED

Обязательно для кат.1 и кат.2.
Для кат.3 — рекомендательно (severity="warning").

Данные читаются из project["_results"] — не из vru напрямую.
"""

from data.breakers.breaker_tables import STANDARD_RATINGS

RATIO_REQUIRED = 1.6   # ПУЭ, коэффициент селективности


def _next_rating(min_rating: float) -> int:
    """Возвращает следующий стандартный номинал >= min_rating."""
    for r in STANDARD_RATINGS:
        if r >= min_rating:
            return r
    return STANDARD_RATINGS[-1]


def _check_pair(upstream_id: str, upstream_rating: int,
                downstream_id: str, downstream_rating: int,
                category: int) -> dict:
    """Проверяет одну пару автоматов."""
    ratio = upstream_rating / downstream_rating if downstream_rating else 999
    ok = ratio >= RATIO_REQUIRED
    severity = "ok" if ok else ("error" if category <= 2 else "warning")

    result = {
        "upstream":          upstream_id,
        "upstream_rating":   upstream_rating,
        "downstream":        downstream_id,
        "downstream_rating": downstream_rating,
        "ratio":             round(ratio, 2),
        "required":          RATIO_REQUIRED,
        "category":          category,
        "ok":                ok,
        "severity":          severity,
    }

    if not ok:
        needed = downstream_rating * RATIO_REQUIRED
        fix_rating = _next_rating(needed)
        result["fix"] = (
            f"Заменить {upstream_id} с {upstream_rating}А на {fix_rating}А "
            f"(требуется ≥{needed:.0f}А для соотношения {RATIO_REQUIRED})"
        )
    else:
        result["fix"] = None

    return result


def check_selectivity(project: dict) -> list[dict]:
    """
    Проверяет селективность автоматов по всей иерархии.

    Цепочки: потребитель → щит → ВРУ
    (фидеры автоматов не имеют в текущей схеме)

    Читает из project["_results"]["vru"].

    Returns:
        list[dict] — все пары (и ok, и нарушения).
        Для фильтрации нарушений: [r for r in results if not r["ok"]]
    """
    results = []

    vru_results = project.get("_results", {}).get("vru", {})
    vru_breaker = vru_results.get("breaker", {})
    vru_rating  = vru_breaker.get("rating") if vru_breaker else None
    vru_id      = f"ВРУ АВ {vru_rating}А" if vru_rating else "ВРУ"

    for feeder in vru_results.get("feeders", []):
        for panel in feeder.get("panels", []):
            panel_id      = panel.get("id", "?")
            panel_breaker = panel.get("breaker", {})
            panel_rating  = panel_breaker.get("rating") if panel_breaker else None
            panel_cat     = panel.get("category_pue", 3)

            # ВРУ → щит
            if vru_rating and panel_rating:
                pair_id = f"{vru_id} → {panel_id} АВ {panel_rating}А"
                results.append(
                    _check_pair(vru_id, vru_rating,
                                f"{panel_id} АВ {panel_rating}А", panel_rating,
                                panel_cat)
                )

            # Щит → потребители
            for consumer in panel.get("consumers", []):
                # Резервные агрегаты тоже проверяем — у них свой кабель и автомат
                c_id      = consumer.get("id", "?")
                c_breaker = consumer.get("breaker", {})
                c_rating  = c_breaker.get("rating") if c_breaker else None
                c_cat     = consumer.get("category_pue", panel_cat)

                if panel_rating and c_rating:
                    results.append(
                        _check_pair(f"{panel_id} АВ {panel_rating}А", panel_rating,
                                    f"{c_id} АВ {c_rating}А",          c_rating,
                                    c_cat)
                    )

    return results


def print_selectivity_report(results: list) -> None:
    """Выводит отчёт по селективности."""
    if not results:
        print("Нет данных для проверки (нет рассчитанных автоматов)")
        return

    violations = [r for r in results if not r["ok"]]
    errors   = [r for r in violations if r["severity"] == "error"]
    warnings = [r for r in violations if r["severity"] == "warning"]

    print(f"\nПроверка селективности: {len(results)} пар автоматов")
    print(f"  Нарушений (кат.1-2, обязательно): {len(errors)}")
    print(f"  Предупреждений (кат.3, рекомендательно): {len(warnings)}")

    if not violations:
        print("  ✓ Все автоматы селективны")
        return

    if errors:
        print("\n  ОШИБКИ (требуется исправление):")
        for r in errors:
            print(f"    ✗ {r['upstream']} → {r['downstream']}")
            print(f"      Соотношение: {r['ratio']} (требуется ≥{r['required']})")
            print(f"      Рекомендация: {r['fix']}")

    if warnings:
        print("\n  ПРЕДУПРЕЖДЕНИЯ (желательно исправить):")
        for r in warnings:
            print(f"    ⚠ {r['upstream']} → {r['downstream']}")
            print(f"      Соотношение: {r['ratio']} (рекомендуется ≥{r['required']})")
            print(f"      Рекомендация: {r['fix']}")
