"""
changes/detector.py — регистрация изменений проекта (трапеция ГОСТ).

При регистрации изменения:
  - увеличивается номер ревизии в project["project"]["revision"]
  - добавляется запись в project["changes"]
  - обновляется _meta["last_modified"]
"""

import copy
import datetime
from typing import Optional


# Коды причин изменений (ГОСТ 21.1101)
REASON_CODES = {
    "01": "Ошибка в документации",
    "02": "Замечание органов экспертизы",
    "03": "Изменение задания на проектирование",
    "04": "Иное",
}

# Документы, которые затрагивает каждый тип изменения
_AFFECTED_BY_CATEGORY = {
    "cable":    ["Кабельный журнал", "Спецификация", "Чертежи"],
    "panel":    ["Спецификация", "Чертежи", "Ведомость работ"],
    "load":     ["Расчёты", "Спецификация", "Кабельный журнал"],
    "general":  ["Все разделы"],
    "calc":     ["Расчёты", "Спецификация"],
    "drawing":  ["Чертежи"],
}


def register_change(
    project: dict,
    description: str,
    reason_code: str = "04",
    author: str = "",
    category: str = "general",
    items: Optional[list] = None,
    date: Optional[str] = None,
) -> dict:
    """
    Регистрирует изменение в проекте.

    Параметры:
        project      — dict проекта (не изменяется, возвращается копия)
        description  — текстовое описание изменения
        reason_code  — код причины ("01"–"04")
        author       — ФИО исполнителя
        category     — категория изменения (cable/panel/load/general/...)
        items        — список изменённых позиций [{"id":..., "field":..., "old":..., "new":...}]
        date         — дата изменения (ISO, по умолч. сегодня)

    Возвращает: копию проекта с обновлёнными полями.
    """
    result = copy.deepcopy(project)

    if date is None:
        date = datetime.date.today().isoformat()

    # Увеличиваем ревизию
    old_rev = result["project"].get("revision", 0)
    new_rev = old_rev + 1
    result["project"]["revision"] = new_rev
    result["project"]["date"] = date

    # Сбрасываем calc_done — нужен пересчёт
    if "_meta" in result:
        result["_meta"]["last_modified"] = date
        result["_meta"]["calc_done"] = False

    # Формируем запись изменения
    change_record = {
        "rev": new_rev,
        "date": date,
        "author": author or result["project"].get("designer", ""),
        "description": description,
        "reason_code": reason_code,
        "reason_text": REASON_CODES.get(reason_code, reason_code),
        "category": category,
        "affected_docs": _AFFECTED_BY_CATEGORY.get(category, ["Все разделы"]),
        "items": items or [],
    }

    if "changes" not in result:
        result["changes"] = []
    result["changes"].append(change_record)

    return result


def get_change_summary(project: dict) -> str:
    """Возвращает краткую строку о последнем изменении."""
    changes = project.get("changes", [])
    if not changes:
        return "Ред. 0 — изменений нет"
    last = changes[-1]
    return (
        f"Ред. {last['rev']} от {last['date']} — "
        f"{last['description'][:60]} "
        f"(прич.: {last['reason_text']})"
    )


def detect_changes(old_project: dict, new_project: dict) -> list:
    """
    Автоматически находит изменения между двумя версиями проекта.
    Сравнивает данные в vru.feeders → panels → consumers.
    Возвращает список изменённых позиций.
    """
    changes = []

    def compare_consumer(old_c: dict, new_c: dict):
        fields = ["power_kw", "demand_factor", "cos_phi", "phases",
                  "cable.section_mm2", "cable.length_m", "cable.mark"]
        for field in fields:
            if "." in field:
                key1, key2 = field.split(".")
                old_val = old_c.get(key1, {}).get(key2)
                new_val = new_c.get(key1, {}).get(key2)
            else:
                old_val = old_c.get(field)
                new_val = new_c.get(field)
            if old_val != new_val:
                changes.append({
                    "id": new_c.get("id", "?"),
                    "field": field,
                    "old": old_val,
                    "new": new_val,
                })

    old_feeders = old_project.get("vru", {}).get("feeders", [])
    new_feeders = new_project.get("vru", {}).get("feeders", [])

    old_consumers = {
        c["id"]: c
        for f in old_feeders
        for p in f.get("panels", [])
        for c in p.get("consumers", [])
    }
    new_consumers = {
        c["id"]: c
        for f in new_feeders
        for p in f.get("panels", [])
        for c in p.get("consumers", [])
    }

    for cid, new_c in new_consumers.items():
        if cid in old_consumers:
            compare_consumer(old_consumers[cid], new_c)
        else:
            changes.append({"id": cid, "field": "new_consumer", "old": None, "new": new_c.get("name")})

    for cid in old_consumers:
        if cid not in new_consumers:
            changes.append({"id": cid, "field": "deleted_consumer", "old": old_consumers[cid].get("name"), "new": None})

    return changes
