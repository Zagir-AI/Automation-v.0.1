"""
docs/gen_pnr.py — программа пусконаладочных работ (ПНР).
"""

from pathlib import Path


def _build_pnr_stages(project: dict) -> list:
    """Формирует этапы ПНР."""
    vru = project["_results"]["vru"]
    consumer_count = sum(
        len(panel.get("consumers", []))
        for feeder in vru.get("feeders", [])
        for panel in feeder.get("panels", [])
    )
    panel_count = sum(
        len(feeder.get("panels", []))
        for feeder in vru.get("feeders", [])
    )

    stages = [
        # (этап, наименование работы, норматив, ед., кол., срок_дней)
        (1, "Визуальный осмотр электрооборудования и кабельных линий",
         "ПУЭ гл.1.8", "компл.", 1, 1),
        (2, "Проверка соответствия выполненного монтажа проектной документации",
         "РД 34.20.501", "компл.", 1, 1),
        (3, "Измерение сопротивления изоляции кабелей (Uиспыт=1000В)",
         "ПУЭ 1.8.37", "линия", consumer_count + panel_count, 1),
        (4, "Проверка правильности подключения фаз (чередование фаз)",
         "ПУЭ 1.8.20", "точка", panel_count + 1, 1),
        (5, "Измерение сопротивления петли фаза-нуль",
         "ПУЭ 1.8.36", "точка", consumer_count, 1),
        (6, "Проверка срабатывания автоматических выключателей",
         "ГОСТ Р 50345", "шт.", consumer_count + panel_count + 1, 1),
        (7, "Проверка защитного заземления (Rзащ ≤ 0.1 Ом)",
         "ПУЭ 1.8.39", "точка", panel_count + 1, 1),
        (8, "Рабочее включение под нагрузку и проверка токов",
         "РД 34.20.501", "компл.", 1, 1),
        (9, "Наладка и регулировка уставок автоматов (при необходимости)",
         "ГОСТ Р 50345", "шт.", panel_count + 1, 1),
        (10, "Оформление протоколов испытаний и измерений",
         "ГОСТ Р 50571", "компл.", 1, 1),
        (11, "Оформление акта технической готовности",
         "РД 34.20.501", "акт", 1, 1),
    ]
    return [
        {"n": s[0], "name": s[1], "norm": s[2], "unit": s[3], "qty": s[4], "days": s[5]}
        for s in stages
    ]


def generate_pnr(project: dict, docs_dir: Path) -> Path:
    """Генерирует программу ПНР в DOCX."""
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
    stages = _build_pnr_stages(project)
    out_path = docs_dir / f"{code}_pnr.docx"

    if not _has_docx:
        txt_path = docs_dir / f"{code}_pnr.txt"
        _write_txt(stages, proj, txt_path)
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
    r = p.add_run("Программа пусконаладочных работ (ПНР)")
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

    headers = ["№", "Наименование работы", "Норматив", "Ед.", "Кол.", "Срок, дн."]
    col_w   = [Cm(1.0), Cm(10.0), Cm(3.5), Cm(1.8), Cm(1.8), Cm(2.5)]

    table = doc.add_table(rows=1, cols=6)
    table.style = "Table Grid"

    for cell, h, w in zip(table.rows[0].cells, headers, col_w):
        cell.width = w
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(h)
        run.font.bold = True; run.font.size = Pt(10); run.font.name = "Times New Roman"
        cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER

    for stage in stages:
        row = table.add_row()
        values = [str(stage["n"]), stage["name"], stage["norm"],
                  stage["unit"], str(stage["qty"]), str(stage["days"])]
        aligns = [WD_ALIGN_PARAGRAPH.CENTER, WD_ALIGN_PARAGRAPH.LEFT,
                  WD_ALIGN_PARAGRAPH.LEFT,   WD_ALIGN_PARAGRAPH.CENTER,
                  WD_ALIGN_PARAGRAPH.CENTER, WD_ALIGN_PARAGRAPH.CENTER]
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
        f"Проверил: {proj.get('checker','')}\t\t\t"
        f"Согласовано: _______________"
    )
    r_s.font.size = Pt(10); r_s.font.name = "Times New Roman"

    doc.save(str(out_path))
    return out_path


def _write_txt(stages, proj, path: Path):
    lines = [
        "ПРОГРАММА ПУСКОНАЛАДОЧНЫХ РАБОТ",
        f"Объект: {proj.get('name','')} | Код: {proj.get('code','')}",
        "",
        f"{'№':<4} {'Наименование':<45} {'Норматив':<15} {'Ед.':<6} {'Кол.':<5} Дней",
        "-" * 85,
    ]
    for s in stages:
        lines.append(
            f"{s['n']:<4} {s['name']:<45} {s['norm']:<15} "
            f"{s['unit']:<6} {s['qty']:<5} {s['days']}"
        )
    path.write_text("\n".join(lines), encoding="utf-8")
