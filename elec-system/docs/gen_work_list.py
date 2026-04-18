"""
docs/gen_work_list.py — ведомость объёмов работ (монтажные работы).
"""

from pathlib import Path


def _build_work_items(project: dict) -> list:
    """Формирует перечень работ на основе результатов проекта."""
    vru = project["_results"]["vru"]
    items = []
    n = 1

    cable_total_m = 0
    panel_count = 0
    consumer_count = 0
    breaker_count = 0

    for feeder in vru.get("feeders", []):
        for panel in feeder.get("panels", []):
            panel_count += 1
            pc = panel.get("cable", {})
            cable_total_m += pc.get("length_m", 0)

            for c in panel.get("consumers", []):
                consumer_count += 1
                breaker_count += 1
                cc = c.get("cable", {})
                cable_total_m += cc.get("length_m", 0)

    # ВРУ
    ic = vru.get("incoming_cable", {})
    cable_total_m += ic.get("length_m", 0)

    cable_with_reserve = round(cable_total_m * 1.05)

    works = [
        # (наименование, ед.изм., кол-во, примечание)
        ("Монтаж ВРУ (ВРУ-1-22-УХЛ4)", "шт.", 1, "Установка, подключение"),
        ("Монтаж щитов распределительных", "шт.", panel_count, "Установка на стену/рейку"),
        ("Прокладка кабельного лотка", "м", round(cable_total_m * 0.6), "Перфолоток 200×60"),
        ("Прокладка кабелей ВВГнг-LS в лотке", "м", cable_with_reserve, "С укладкой и закреплением"),
        ("Разделка и подключение кабелей", "конц.", consumer_count + panel_count + 1, "С двух сторон"),
        ("Монтаж автоматических выключателей", "шт.", breaker_count + panel_count + 1, "На DIN-рейку"),
        ("Маркировка кабелей и шин", "компл.", 1, "Бирки, маркеры"),
        ("Заземление оборудования (PE-шина)", "точка", panel_count + 1, ""),
        ("Испытания и измерения изоляции", "линия", consumer_count + panel_count, "Мегаомметр 1000В"),
        ("Проверка УЗО и автоматов (расцепление)", "шт.", breaker_count, ""),
        ("Замер сопротивления петли фаза-нуль", "точка", consumer_count, ""),
        ("Сдача-приёмка исполнительной документации", "компл.", 1, ""),
    ]

    return [{"n": i+1, "name": w[0], "unit": w[1], "qty": w[2], "note": w[3]}
            for i, w in enumerate(works)]


def generate_work_list(project: dict, docs_dir: Path) -> Path:
    """Генерирует ведомость объёмов работ в DOCX."""
    try:
        from docx import Document
        from docx.shared import Pt, Cm
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
        _has_docx = True
    except ImportError:
        _has_docx = False

    proj = project["project"]
    code = proj.get("code", "")
    works = _build_work_items(project)
    out_path = docs_dir / f"{code}_work_list.docx"

    if not _has_docx:
        txt_path = docs_dir / f"{code}_work_list.txt"
        _write_txt(works, proj, txt_path)
        return txt_path

    doc = Document()
    sec = doc.sections[0]
    sec.page_width    = Cm(29.7)
    sec.page_height   = Cm(21.0)
    sec.left_margin   = Cm(2.0)
    sec.right_margin  = Cm(1.0)
    sec.top_margin    = Cm(1.5)
    sec.bottom_margin = Cm(1.5)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("Ведомость объёмов работ")
    r.font.bold = True; r.font.size = Pt(13); r.font.name = "Times New Roman"

    p2 = doc.add_paragraph()
    p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r2 = p2.add_run(
        f"Электроснабжение {proj.get('name','').lower()} | "
        f"Код: {code} | Стадия: {proj.get('stage','')} | "
        f"Ред.: {proj.get('revision',0)} | Дата: {proj.get('date','')}"
    )
    r2.font.size = Pt(10); r2.font.name = "Times New Roman"
    doc.add_paragraph()

    headers = ["№", "Наименование работы", "Ед.изм.", "Кол-во", "Примечание"]
    col_w = [Cm(1.0), Cm(10.0), Cm(2.5), Cm(2.5), Cm(6.0)]

    table = doc.add_table(rows=1, cols=5)
    table.style = "Table Grid"

    for cell, h, w in zip(table.rows[0].cells, headers, col_w):
        cell.width = w
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(h)
        run.font.bold = True; run.font.size = Pt(10); run.font.name = "Times New Roman"
        cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER

    for work in works:
        row = table.add_row()
        values = [str(work["n"]), work["name"], work["unit"], str(work["qty"]), work["note"]]
        aligns = [WD_ALIGN_PARAGRAPH.CENTER, WD_ALIGN_PARAGRAPH.LEFT,
                  WD_ALIGN_PARAGRAPH.CENTER, WD_ALIGN_PARAGRAPH.CENTER, WD_ALIGN_PARAGRAPH.LEFT]
        for cell, val, w, align in zip(row.cells, values, col_w, aligns):
            cell.width = w
            p = cell.paragraphs[0]
            p.alignment = align
            run = p.add_run(val)
            run.font.size = Pt(10); run.font.name = "Times New Roman"

    doc.add_paragraph()
    p_s = doc.add_paragraph()
    r_s = p_s.add_run(
        f"Разработал: {proj.get('designer','')}\t\t\t"
        f"Проверил: {proj.get('checker','')}"
    )
    r_s.font.size = Pt(10); r_s.font.name = "Times New Roman"

    doc.save(str(out_path))
    return out_path


def _write_txt(works, proj, path: Path):
    lines = [
        "ВЕДОМОСТЬ ОБЪЁМОВ РАБОТ",
        f"Объект: {proj.get('name','')} | Код: {proj.get('code','')}",
        "",
        f"{'№':<4} {'Наименование работы':<45} {'Ед.':<6} {'Кол.':<6} Примечание",
        "-" * 80,
    ]
    for w in works:
        lines.append(f"{w['n']:<4} {w['name']:<45} {w['unit']:<6} {w['qty']:<6} {w['note']}")
    path.write_text("\n".join(lines), encoding="utf-8")
