"""
rules/category_rules.py — категорийность здания и схема ВРУ (ПУЭ гл.1.2).

Алгоритм:
  - Есть потребители кат.1 → здание кат.1 → ВРУ с АВР
  - Есть потребители кат.2 → здание кат.2 → ВРУ с резервным вводом
  - Только кат.3           → здание кат.3 → ВРУ с одним вводом
"""

from datetime import date


# ── Схемы ВРУ по категории ────────────────────────────────────────────────────
_VRU_SCHEMES = {
    1: {
        "scheme":      "avr",
        "description": "Два независимых ввода + АВР",
        "inputs":      2,
        "has_avr":     True,
        "has_section_switch": False,
        "note":        "ПУЭ 1.2.19: потребители 1-й категории — бесперебойное питание",
    },
    2: {
        "scheme":      "reserve_input",
        "description": "Основной ввод + резервный ввод + секционный выключатель",
        "inputs":      2,
        "has_avr":     False,
        "has_section_switch": True,
        "note":        "ПУЭ 1.2.20: потребители 2-й категории — резервирование",
    },
    3: {
        "scheme":      "single_input",
        "description": "Один ввод",
        "inputs":      1,
        "has_avr":     False,
        "has_section_switch": False,
        "note":        "ПУЭ 1.2.21: потребители 3-й категории — допустим перерыв до 1 суток",
    },
}


def _collect_consumers(project: dict) -> list[dict]:
    """Собирает всех потребителей из project.json (vru + outdoor_networks)."""
    consumers = []

    vru = project.get("vru", {})
    for feeder in vru.get("feeders", []):
        for panel in feeder.get("panels", []):
            consumers.extend(panel.get("consumers", []))

    for line in project.get("outdoor_networks", []):
        consumers.extend(line.get("consumers", []))

    return consumers


def determine_building_category(project: dict) -> int:
    """
    Определяет категорию здания по ПУЭ гл.1.2.

    Анализирует всех потребителей в project.json (включая outdoor_networks).
    Возвращает 1, 2 или 3.
    """
    consumers = _collect_consumers(project)

    if not consumers:
        return 3

    categories = [c.get("category_pue", 3) for c in consumers]
    min_cat = min(categories)

    # Особый случай: котельная с category_auto
    boiler = project.get("boiler_room", {})
    if boiler.get("category_auto", False):
        # Если нет резервного источника тепла — кат.1
        has_backup = boiler.get("has_backup_source", False)
        boiler_cat = 2 if has_backup else 1
        min_cat = min(min_cat, boiler_cat)

    return min_cat


def get_vru_scheme(category: int) -> dict:
    """
    Возвращает схему ВРУ для заданной категории здания.

    Returns:
        dict с ключами: scheme, description, inputs, has_avr,
                        has_section_switch, note
    """
    return dict(_VRU_SCHEMES.get(category, _VRU_SCHEMES[3]))


def check_category_compliance(consumer: dict, panel: dict) -> bool:
    """
    Проверяет соответствие категории потребителя и его щита.

    Нарушение: потребитель кат.1 в щите кат.2 или кат.3 без АВР.

    Returns:
        True — всё в порядке, False — нарушение
    """
    consumer_cat = consumer.get("category_pue", 3)
    panel_cat    = panel.get("category_pue", 3)
    panel_avr    = panel.get("has_avr", False)

    if consumer_cat == 1 and not panel_avr:
        return False
    if consumer_cat < panel_cat:
        return False
    return True


def check_all_compliance(project: dict) -> list[dict]:
    """
    Проверяет соответствие категорий всех потребителей их щитам.

    Returns:
        list[dict] — список нарушений:
        {"severity": "error"|"warning", "consumer_id", "consumer_name",
         "consumer_cat", "panel_id", "panel_cat", "panel_avr", "message"}
    """
    violations = []

    vru = project.get("vru", {})
    for feeder in vru.get("feeders", []):
        for panel in feeder.get("panels", []):
            panel_id  = panel.get("id", "?")
            panel_cat = panel.get("category_pue", 3)
            has_avr   = panel.get("has_avr", False)
            for consumer in panel.get("consumers", []):
                c_id  = consumer.get("id", "?")
                c_cat = consumer.get("category_pue", 3)
                if c_cat == 1 and not has_avr:
                    violations.append({
                        "severity":      "error",
                        "consumer_id":   c_id,
                        "consumer_name": consumer.get("name"),
                        "consumer_cat":  c_cat,
                        "panel_id":      panel_id,
                        "panel_cat":     panel_cat,
                        "panel_avr":     has_avr,
                        "message": (
                            f"Потребитель {c_id} (кат.1) в щите {panel_id} "
                            f"без АВР — нарушение ПУЭ 1.2.19"
                        ),
                    })
                elif c_cat < panel_cat:
                    violations.append({
                        "severity":      "warning",
                        "consumer_id":   c_id,
                        "consumer_name": consumer.get("name"),
                        "consumer_cat":  c_cat,
                        "panel_id":      panel_id,
                        "panel_cat":     panel_cat,
                        "panel_avr":     has_avr,
                        "message": (
                            f"Потребитель {c_id} (кат.{c_cat}) в щите {panel_id} "
                            f"кат.{panel_cat} — рекомендуется выделить в отдельный щит"
                        ),
                    })

    return violations


def update_building_meta(project: dict) -> dict:
    """
    Обновляет блок _building в project.json:
    category_pue, vru_scheme, compliance_ok, last_check.

    Не изменяет исходные данные — только _building.
    """
    category = determine_building_category(project)
    scheme   = get_vru_scheme(category)
    violations = check_all_compliance(project)

    project.setdefault("_building", {})
    project["_building"].update({
        "category_pue":   category,
        "vru_scheme":     scheme["scheme"],
        "vru_description":scheme["description"],
        "has_avr":        scheme["has_avr"],
        "compliance_ok":  len(violations) == 0,
        "violations":     len(violations),
        "last_check":     str(date.today()),
    })
    return project


def print_building_summary(project: dict) -> None:
    """Выводит сводку по категорийности здания."""
    category = determine_building_category(project)
    scheme   = get_vru_scheme(category)
    violations = check_all_compliance(project)

    name = project.get("project", {}).get("name", "Объект")
    print(f"\nКатегорийность здания: {name}")
    print(f"  Категория ПУЭ:  {category}")
    print(f"  Схема ВРУ:      {scheme['description']}")
    print(f"  {scheme['note']}")
    if violations:
        print(f"\n  ⚠ Нарушений соответствия: {len(violations)}")
        for v in violations:
            print(f"    • {v['message']}")
    else:
        print(f"\n  ✓ Нарушений соответствия не найдено")
