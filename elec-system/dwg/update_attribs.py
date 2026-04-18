"""
dwg/update_attribs.py — синхронизация атрибутов блоков AutoCAD с project.json.

Обновляет атрибуты блоков в DXF-файле на основе результатов расчёта.
ID_TAG атрибут блока должен совпадать с id потребителя/щита в project.json.

Зависимость: ezdxf (pip install ezdxf)
"""

from pathlib import Path


def _build_attrib_map(project: dict) -> dict:
    """
    Строит словарь {id: {ATTRIB_NAME: value}} для всех элементов проекта.
    """
    attribs = {}
    results = project.get("_results", {})
    vru = results.get("vru", {})

    # ВРУ
    ic = vru.get("incoming_cable", {})
    br = vru.get("breaker", {})
    attribs[vru.get("id", "ВРУ-1")] = {
        "I_CALC":   str(round(vru.get("i_calc_a", 0), 1)),
        "P_CALC":   str(round(vru.get("p_calc_kw", 0), 1)),
        "CABLE":    f"{ic.get('mark','')} {ic.get('cores','')}×{ic.get('section_mm2','')}",
        "BREAKER":  f"АВ {br.get('rating','')}А хар.{br.get('char','')}",
        "COS_PHI":  str(round(vru.get("cos_phi", 0), 3)),
    }

    for feeder in vru.get("feeders", []):
        for panel in feeder.get("panels", []):
            pc = panel.get("cable", {})
            pb = panel.get("breaker", {})
            attribs[panel["id"]] = {
                "I_CALC":  str(panel.get("i_calc_a", 0)),
                "P_CALC":  str(panel.get("p_calc_kw", 0)),
                "CABLE":   f"{pc.get('mark','')} {pc.get('cores','')}×{pc.get('section_mm2','')}",
                "BREAKER": f"АВ {pb.get('rating','')}А хар.{pb.get('char','')}",
                "DU":      str(pc.get("voltage_drop_pct", 0)),
            }
            for c in panel.get("consumers", []):
                cc = c.get("cable", {})
                cb = c.get("breaker", {})
                attribs[c["id"]] = {
                    "I_CALC":  str(c.get("i_calc_a", 0)),
                    "P_CALC":  str(c.get("p_calc_kw", 0)),
                    "CABLE":   f"{cc.get('mark','')} {cc.get('cores','')}×{cc.get('section_mm2','')}",
                    "BREAKER": f"АВ {cb.get('rating','')}А хар.{cb.get('char','')}",
                    "DU":      str(cc.get("voltage_drop_pct", 0)),
                    "NAME":    c.get("name", ""),
                }

    return attribs


def update_attribs(project: dict, dxf_path: str) -> int:
    """
    Обновляет атрибуты блоков в DXF-файле.
    Ищет блоки с атрибутом ID_TAG, сопоставляет с project._results.

    Возвращает количество обновлённых блоков.
    """
    try:
        import ezdxf
    except ImportError:
        print("Установи ezdxf: pip install ezdxf")
        return 0

    attrib_map = _build_attrib_map(project)
    path = Path(dxf_path)

    if not path.exists():
        print(f"DXF-файл не найден: {path}")
        return 0

    doc = ezdxf.readfile(str(path))
    msp = doc.modelspace()
    updated = 0

    for insert in msp.query("INSERT"):
        if not insert.is_attrib_block:
            continue
        attribs = {a.dxf.tag.upper(): a for a in insert.attribs}
        block_id = attribs.get("ID_TAG")
        if block_id is None:
            continue

        id_val = block_id.dxf.text.strip()
        if id_val not in attrib_map:
            continue

        updates = attrib_map[id_val]
        for tag, value in updates.items():
            if tag in attribs:
                attribs[tag].dxf.text = str(value)

        updated += 1

    if updated > 0:
        doc.saveas(str(path))
        print(f"Обновлено блоков: {updated} в {path.name}")

    return updated


def add_changes_trapezoid(project: dict, dxf_path: str) -> bool:
    """
    Добавляет трапецию изменений ГОСТ на слой CHANGES (только при rev > 0).
    """
    rev = project["project"].get("revision", 0)
    if rev == 0:
        return False

    try:
        import ezdxf
    except ImportError:
        return False

    path = Path(dxf_path)
    if not path.exists():
        return False

    doc = ezdxf.readfile(str(path))
    msp = doc.modelspace()

    # Создаём слой CHANGES если не существует
    if "CHANGES" not in doc.layers:
        doc.layers.new("CHANGES", dxfattribs={"color": 1})  # красный

    changes = project.get("changes", [])
    last_change = changes[-1] if changes else {}

    # Добавляем текстовую аннотацию в штамп
    x0, y0 = 0, -10 * rev  # смещение по Y для каждой ревизии
    msp.add_text(
        f"Рев.{rev} от {last_change.get('date','?')}: {last_change.get('description','')[:40]}",
        dxfattribs={
            "layer": "CHANGES",
            "height": 3.5,
            "insert": (x0, y0),
        }
    )

    doc.saveas(str(path))
    return True
