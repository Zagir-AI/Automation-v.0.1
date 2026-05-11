"""
dwg/number_cables.py — автонумерация кабелей из DXF-чертежа.

Принцип:
  1. Читает DXF-файл плана
  2. Находит блоки с атрибутом ID_TAG (потребители)
  3. Присваивает каждому номер кабеля по схеме: КЛ-{щит}-{номер}
  4. Обновляет атрибуты блоков в DXF (если read_only=False)
  5. Возвращает таблицу нумерации для вставки в project.json

Формат номера кабеля: КЛ-{PANEL_ID}-{NN}
  Пример: КЛ-ЩО1-01, КЛ-ЩС1-02, КЛ-ВРУ-01

Результат записывается в project["cable_numbering"].
"""

from __future__ import annotations
from pathlib import Path
from collections import defaultdict

import ezdxf


# ── Формат номеров ────────────────────────────────────────────────────────────

def _make_cable_no(panel_id: str, seq: int) -> str:
    """КЛ-ЩО1-01, КЛ-ЩС1-02 и т.д."""
    clean = panel_id.replace("-", "").replace(" ", "")
    return f"КЛ-{clean}-{seq:02d}"


def _normalize_panel_id(raw: str) -> str:
    """'ЩО-1' → 'ЩО1', 'ВРУ-1' → 'ВРУ1'"""
    return raw.replace("-", "").strip()


# ── Чтение DXF ────────────────────────────────────────────────────────────────

def _get_attrib_value(ref, tag: str) -> str | None:
    """Читает значение атрибута блока по тегу."""
    for attrib in ref.attribs:
        if attrib.dxf.tag.upper() == tag.upper():
            return attrib.dxf.text
    return None


def _set_attrib_value(ref, tag: str, value: str) -> bool:
    """Устанавливает значение атрибута блока."""
    for attrib in ref.attribs:
        if attrib.dxf.tag.upper() == tag.upper():
            attrib.dxf.text = value
            return True
    return False


def extract_consumers_from_dxf(dxf_path: Path | str) -> list[dict]:
    """
    Извлекает потребителей из DXF-файла плана.

    Returns:
        list[dict] с ключами: id, panel_id, cable_no (или None), x, y
    """
    dxf_path = Path(dxf_path)
    if not dxf_path.exists():
        return []

    doc  = ezdxf.readfile(str(dxf_path))
    msp  = doc.modelspace()
    consumers = []

    for entity in msp:
        if entity.dxftype() != "INSERT":
            continue
        if not entity.attribs_follow:
            continue

        id_tag    = _get_attrib_value(entity, "ID_TAG")
        panel_tag = _get_attrib_value(entity, "PANEL_ID")
        cable_no  = _get_attrib_value(entity, "CABLE_NO")

        if not id_tag:
            continue

        pos = entity.dxf.insert
        consumers.append({
            "id":       id_tag,
            "panel_id": panel_tag or "",
            "cable_no": cable_no or None,
            "x":        round(float(pos.x), 1),
            "y":        round(float(pos.y), 1),
        })

    return consumers


# ── Нумерация ─────────────────────────────────────────────────────────────────

def number_cables_from_project(project: dict) -> dict[str, str]:
    """
    Нумерует кабели по данным project["_results"].

    Порядок нумерации: по щитам в порядке feeders → panels → consumers.
    Каждый щит начинает нумерацию с 01.

    Returns:
        dict: {consumer_id → cable_no}
    """
    vru = project.get("_results", {}).get("vru", {})
    numbering: dict[str, str] = {}

    for feeder in vru.get("feeders", []):
        for panel in feeder.get("panels", []):
            panel_id = panel.get("id", "ВРУ")
            seq = 1
            for c in panel.get("consumers", []):
                c_id = c.get("id")
                if not c_id:
                    continue
                cable_no = _make_cable_no(panel_id, seq)
                numbering[c_id] = cable_no
                seq += 1

    return numbering


def number_cables_from_dxf(dxf_path: Path | str,
                            project: dict | None = None) -> dict[str, str]:
    """
    Нумерует кабели по данным из DXF (по координатам — слева-направо, сверху-вниз).

    Если передан project — сначала использует project для получения panel_id,
    затем дополняет данными из DXF.

    Returns:
        dict: {consumer_id → cable_no}
    """
    consumers = extract_consumers_from_dxf(dxf_path)
    if not consumers:
        return {}

    # Если panel_id неизвестен — пробуем из project
    if project:
        panel_map: dict[str, str] = {}
        vru = project.get("_results", {}).get("vru", {})
        for feeder in vru.get("feeders", []):
            for panel in feeder.get("panels", []):
                for c in panel.get("consumers", []):
                    if c.get("id"):
                        panel_map[c["id"]] = panel["id"]
        for c in consumers:
            if not c["panel_id"] and c["id"] in panel_map:
                c["panel_id"] = panel_map[c["id"]]

    # Группируем по щитам
    by_panel: dict[str, list] = defaultdict(list)
    for c in consumers:
        by_panel[c["panel_id"] or "UNKNOWN"].append(c)

    # Сортируем внутри щита: слева-направо, сверху-вниз
    numbering: dict[str, str] = {}
    for panel_id, panel_consumers in sorted(by_panel.items()):
        sorted_c = sorted(panel_consumers, key=lambda c: (-c["y"], c["x"]))
        for seq, c in enumerate(sorted_c, start=1):
            numbering[c["id"]] = _make_cable_no(panel_id, seq)

    return numbering


def write_cable_numbers_to_dxf(dxf_path: Path | str,
                                numbering: dict[str, str],
                                out_path: Path | str | None = None) -> Path:
    """
    Записывает номера кабелей в атрибут CABLE_NO блоков DXF.

    Args:
        dxf_path:  входной DXF
        numbering: {consumer_id → cable_no}
        out_path:  выходной DXF (если None — перезаписывает входной)

    Returns:
        Path к обновлённому DXF
    """
    dxf_path = Path(dxf_path)
    doc = ezdxf.readfile(str(dxf_path))
    msp = doc.modelspace()

    updated = 0
    for entity in msp:
        if entity.dxftype() != "INSERT":
            continue
        if not entity.attribs_follow:
            continue

        id_tag = _get_attrib_value(entity, "ID_TAG")
        if not id_tag or id_tag not in numbering:
            continue

        cable_no = numbering[id_tag]
        if not _set_attrib_value(entity, "CABLE_NO", cable_no):
            # Добавляем атрибут если его нет
            entity.add_attrib("CABLE_NO", cable_no)
        updated += 1

    save_path = Path(out_path) if out_path else dxf_path
    doc.saveas(str(save_path))
    return save_path


# ── Публичный API ─────────────────────────────────────────────────────────────

def update_cable_numbering(project: dict,
                            dxf_path: Path | str | None = None) -> dict:
    """
    Нумерует кабели и записывает результат в project["cable_numbering"].

    Если dxf_path передан — нумерует по DXF (порядок по координатам).
    Иначе — по порядку в project["_results"] (feeders → panels → consumers).

    Returns:
        Обновлённый project
    """
    if dxf_path and Path(dxf_path).exists():
        numbering = number_cables_from_dxf(dxf_path, project)
    else:
        numbering = number_cables_from_project(project)

    project["cable_numbering"] = numbering
    return project


def print_cable_numbering(project: dict) -> None:
    """Выводит таблицу нумерации кабелей."""
    numbering = project.get("cable_numbering", {})
    if not numbering:
        print("Нумерация кабелей не выполнена")
        return

    vru = project.get("_results", {}).get("vru", {})

    print(f"\nНумерация кабелей: {len(numbering)} линий")
    print(f"{'Потребитель':<12} {'Наименование':<35} {'Кабель №':<18} {'Марка и сечение'}")
    print("-" * 90)

    # Берём порядок из _results для красивого вывода
    for feeder in vru.get("feeders", []):
        for panel in feeder.get("panels", []):
            for c in panel.get("consumers", []):
                c_id = c.get("id", "")
                cable_no = numbering.get(c_id, "—")
                cable = c.get("cable", {})
                cable_str = ""
                if cable:
                    cable_str = (f"{cable.get('mark','')} "
                                 f"{cable.get('cores','')}×"
                                 f"{cable.get('section_mm2','')}мм²")
                print(f"{c_id:<12} {c.get('name','')[:35]:<35} {cable_no:<18} {cable_str}")
