"""
docs/gen_spec.py — генерация спецификации оборудования, изделий и материалов.

Формат: ГОСТ 21.110-2013, форма 3 (А4, альбомная).
Разделы: Щиты и шкафы управления | Аппараты защиты | Кабели и провода
"""

from pathlib import Path
from collections import defaultdict


def _build_spec_items(project: dict) -> dict:
    """
    Обходит _results и собирает позиции спецификации по разделам.
    Возвращает: {"panels": [...], "breakers": {...}, "cables": {...}}
    """
    vru = project["_results"]["vru"]
    proj = project["project"]

    panels = []
    breaker_counts = defaultdict(int)   # {(rating, char, poles): count}
    cable_lengths  = defaultdict(float) # {(mark, cores, section): meters}

    def add_breaker(br: dict, count: int = 1):
        if not br or not br.get("rating"):
            return
        key = (br["rating"], br.get("char", "C"), br.get("poles", 3))
        breaker_counts[key] += count

    def add_cable(cb: dict, count: int = 1):
        if not cb or not cb.get("section_mm2"):
            return
        mark = cb.get("mark", "ВВГнг-LS")
        cores = cb.get("cores", 4)
        section = cb.get("section_mm2")
        length = cb.get("length_m", 0) * count
        cable_lengths[(mark, cores, section)] += length

    # ВРУ как щит
    vru_br = vru.get("breaker", {})
    vru_cb = vru.get("incoming_cable", {})
    panels.append({
        "id": vru["id"],
        "name": f"ВРУ-1-22-УХЛ4",
        "note": f"Iн={vru_br.get('rating','?')}А, Iкз={project['vru'].get('isc_ka',10)}кА",
    })
    add_breaker(vru_br)
    add_cable(vru_cb)

    # Щиты
    for feeder in vru.get("feeders", []):
        for panel in feeder.get("panels", []):
            pb = panel.get("breaker", {})
            pc = panel.get("cable", {})
            bus_a = pb.get("rating", 63)
            pname = panel["name"]
            if not pname.lower().startswith("щит"):
                pname = f"Щит {pname}"
            panels.append({
                "id": panel["id"],
                "name": pname,
                "note": f"Iн шины={bus_a}А,",
            })
            add_breaker(pb)
            add_cable(pc)

            # Потребители
            for c in panel.get("consumers", []):
                add_breaker(c.get("breaker", {}))
                add_cable(c.get("cable", {}))

    return {
        "panels": panels,
        "breakers": breaker_counts,
        "cables": cable_lengths,
    }


def generate_spec(project: dict, docs_dir: Path) -> Path:
    """
    Генерирует спецификацию в формате DOCX.
    Возвращает путь к созданному файлу.
    """
    try:
        from docx import Document
        from docx.shared import Pt, Cm, RGBColor
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
        from docx.oxml.ns import qn
        from docx.oxml import OxmlElement
        _has_docx = True
    except ImportError:
        _has_docx = False

    proj = project["project"]
    code = proj.get("code", "")
    name = proj.get("name", "")
    stage = proj.get("stage", "Р")
    rev = proj.get("revision", 0)
    date = proj.get("date", "")
    designer = proj.get("designer", "")
    checker = proj.get("checker", "")
    norm_head = proj.get("norm_head", "")

    items = _build_spec_items(project)
    out_path = docs_dir / f"{code}_spec.docx"

    if not _has_docx:
        # Fallback: текстовый файл
        txt_path = docs_dir / f"{code}_spec.txt"
        _write_spec_txt(project, items, txt_path, proj)
        return txt_path

    doc = Document()

    # ── Поля страницы ──
    section = doc.sections[0]
    section.page_width  = Cm(29.7)
    section.page_height = Cm(21.0)
    section.left_margin   = Cm(2.0)
    section.right_margin  = Cm(1.0)
    section.top_margin    = Cm(1.5)
    section.bottom_margin = Cm(1.5)

    # ── Заголовок ──
    def add_centered(text, size=12, bold=False):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(text)
        run.font.size = Pt(size)
        run.font.bold = bold
        run.font.name = "Times New Roman"
        return p

    add_centered("Спецификация оборудования, изделий и материалов", size=13, bold=True)
    add_centered(f"Электроснабжение {name.lower()}", size=11)
    add_centered(
        f"Раздел: ЭС и ЭО | Стадия: {stage} | Код: {code} | Ред.: {rev} | Дата: {date}",
        size=10
    )
    doc.add_paragraph()

    # ── Таблица ──
    col_widths = [Cm(1.3), Cm(4.5), Cm(8.0), Cm(1.5), Cm(1.2), Cm(5.0)]
    headers = ["Поз.", "Марка/Обозначение", "Наименование", "Кол.", "Ед.", "Примечание"]

    table = doc.add_table(rows=1, cols=6)
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER

    # Шапка таблицы
    hdr_row = table.rows[0]
    for i, (cell, h, w) in enumerate(zip(hdr_row.cells, headers, col_widths)):
        cell.width = w
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(h)
        run.font.bold = True
        run.font.size = Pt(10)
        run.font.name = "Times New Roman"
        cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER

    pos = 1

    def add_section_row(title: str):
        row = table.add_row()
        merged = row.cells[0].merge(row.cells[5])
        p = merged.paragraphs[0]
        run = p.add_run(title)
        run.font.bold = True
        run.font.size = Pt(10)
        run.font.name = "Times New Roman"

    def add_item_row(mark: str, name: str, qty, unit: str, note: str = ""):
        nonlocal pos
        row = table.add_row()
        data = [str(pos), mark, name, str(qty), unit, note]
        for cell, val, w in zip(row.cells, data, col_widths):
            cell.width = w
            p = cell.paragraphs[0]
            align = WD_ALIGN_PARAGRAPH.CENTER if val in (str(pos), str(qty), unit) else WD_ALIGN_PARAGRAPH.LEFT
            p.alignment = align
            run = p.add_run(val)
            run.font.size = Pt(10)
            run.font.name = "Times New Roman"
        pos += 1

    # ── Раздел 1: Щиты ──
    add_section_row("Щиты и шкафы управления")
    for panel in items["panels"]:
        add_item_row(panel["id"], panel["name"], 1, "шт.", panel.get("note", ""))

    # ── Раздел 2: Автоматы ──
    add_section_row("Аппараты защиты")
    for (rating, char, poles), count in sorted(items["breakers"].items()):
        pole_str = "2 полюса" if poles == 2 else "3 полюса"
        mark = f"АВ {rating}А {char}"
        name_str = f"Выключатель автоматический {poles}П {rating}А хар.{char}"
        add_item_row(mark, name_str, count, "шт.", f"МСВ, {pole_str}")

    # ── Раздел 3: Кабели ──
    add_section_row("Кабели и провода")
    for (mark, cores, section), length_m in sorted(items["cables"].items()):
        length_with_reserve = round(length_m * 1.05)  # +5% запас
        name_str = f"Кабель {mark} {cores}×{section}"
        add_item_row(f"{mark} {cores}×{section}", name_str,
                     length_with_reserve, "М", "с запасом 5%")

    doc.add_paragraph()

    # ── Подписи ──
    p_sign = doc.add_paragraph()
    p_sign.alignment = WD_ALIGN_PARAGRAPH.LEFT
    tab_str = "\t\t\t"
    run = p_sign.add_run(
        f"Разработал: {designer}{tab_str}Проверил: {checker}{tab_str}Н.контроль: {norm_head}"
    )
    run.font.size = Pt(10)
    run.font.name = "Times New Roman"

    doc.save(str(out_path))
    return out_path


def _write_spec_txt(project, items, path: Path, proj: dict):
    """Запасной вариант — текстовый файл без python-docx."""
    lines = [
        "СПЕЦИФИКАЦИЯ ОБОРУДОВАНИЯ, ИЗДЕЛИЙ И МАТЕРИАЛОВ",
        f"Объект: {proj.get('name','')}",
        f"Код: {proj.get('code','')} | Стадия: {proj.get('stage','')} | Ред.: {proj.get('revision',0)}",
        "",
        f"{'Поз.':<5} {'Марка':<20} {'Наименование':<45} {'Кол.':<6} {'Ед.':<4} Примечание",
        "-" * 100,
    ]
    pos = 1

    lines.append("--- Щиты и шкафы управления ---")
    for panel in items["panels"]:
        lines.append(f"{pos:<5} {panel['id']:<20} {panel['name']:<45} {'1':<6} {'шт.':<4} {panel.get('note','')}")
        pos += 1

    lines.append("--- Аппараты защиты ---")
    for (rating, char, poles), count in sorted(items["breakers"].items()):
        mark = f"АВ {rating}А {char}"
        name_str = f"Выключатель автоматический {poles}П {rating}А хар.{char}"
        lines.append(f"{pos:<5} {mark:<20} {name_str:<45} {count:<6} {'шт.':<4}")
        pos += 1

    lines.append("--- Кабели и провода ---")
    for (mark, cores, section), length_m in sorted(items["cables"].items()):
        length_r = round(length_m * 1.05)
        name_str = f"Кабель {mark} {cores}×{section}"
        m = f"{mark} {cores}×{section}"
        lines.append(f"{pos:<5} {m:<20} {name_str:<45} {length_r:<6} {'М':<4} с запасом 5%")
        pos += 1

    path.write_text("\n".join(lines), encoding="utf-8")
