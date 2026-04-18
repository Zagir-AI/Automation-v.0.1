"""
docs/gen_cable_journal.py — кабельный журнал по ГОСТ 21.613.

Таблица: № | Марка | Сечение | Кол.жил | Откуда | Куда | Длина,м | Масса | Примечание
"""

from pathlib import Path


def _collect_cables(project: dict) -> list:
    """Собирает все кабельные линии из результатов расчёта."""
    vru = project["_results"]["vru"]
    cables = []
    n = 1

    # Вводной кабель ВРУ
    ic = vru.get("incoming_cable", {})
    if ic.get("section_mm2"):
        cables.append({
            "n": n,
            "mark": ic.get("mark", "ВВГнг-LS"),
            "section": ic.get("section_mm2"),
            "cores": ic.get("cores", 4),
            "from": "ТП-1",
            "to": vru["id"],
            "length_m": ic.get("length_m", 0),
            "install": ic.get("install", "лоток"),
            "note": f"Iдоп={ic.get('i_allowed',0):.0f}А",
        })
        n += 1

    # Кабели питания щитов
    for feeder in vru.get("feeders", []):
        for panel in feeder.get("panels", []):
            pc = panel.get("cable", {})
            if pc.get("section_mm2"):
                cables.append({
                    "n": n,
                    "mark": pc.get("mark", "ВВГнг-LS"),
                    "section": pc.get("section_mm2"),
                    "cores": pc.get("cores", 4),
                    "from": vru["id"],
                    "to": panel["id"],
                    "length_m": pc.get("length_m", 0),
                    "install": pc.get("install", "лоток"),
                    "note": f"ΔU={pc.get('voltage_drop_pct',0)}%",
                })
                n += 1

            # Кабели потребителей
            for c in panel.get("consumers", []):
                cc = c.get("cable", {})
                if cc.get("section_mm2"):
                    cables.append({
                        "n": n,
                        "mark": cc.get("mark", "ВВГнг-LS"),
                        "section": cc.get("section_mm2"),
                        "cores": cc.get("cores", 3),
                        "from": panel["id"],
                        "to": c["id"],
                        "length_m": cc.get("length_m", 0),
                        "install": cc.get("install", "лоток"),
                        "note": c["name"][:30],
                    })
                    n += 1

    return cables


def generate_cable_journal(project: dict, docs_dir: Path) -> Path:
    """Генерирует кабельный журнал ГОСТ 21.613 в формате DOCX."""
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
    cables = _collect_cables(project)
    out_path = docs_dir / f"{code}_cable_journal.docx"

    if not _has_docx:
        txt_path = docs_dir / f"{code}_cable_journal.txt"
        _write_txt(cables, proj, txt_path)
        return txt_path

    doc = Document()
    sec = doc.sections[0]
    sec.page_width    = Cm(42.0)   # A3 альбом
    sec.page_height   = Cm(29.7)
    sec.left_margin   = Cm(2.0)
    sec.right_margin  = Cm(1.0)
    sec.top_margin    = Cm(1.5)
    sec.bottom_margin = Cm(1.5)

    # Заголовок
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run("Кабельный журнал")
    run.font.bold = True
    run.font.size = Pt(13)
    run.font.name = "Times New Roman"

    p2 = doc.add_paragraph()
    p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r2 = p2.add_run(
        f"{proj.get('name','')} | Код: {code} | Стадия: {proj.get('stage','')} | "
        f"Ред.: {proj.get('revision',0)} | Дата: {proj.get('date','')}"
    )
    r2.font.size = Pt(10)
    r2.font.name = "Times New Roman"
    doc.add_paragraph()

    # Таблица
    headers = ["№", "Марка кабеля", "Сечение, мм²", "Жил", "Откуда", "Куда",
               "Длина, м", "Способ прокладки", "Примечание"]
    col_w = [Cm(0.8), Cm(3.5), Cm(2.5), Cm(1.2), Cm(3.0), Cm(3.0),
             Cm(2.0), Cm(3.5), Cm(5.0)]

    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"

    for i, (cell, h, w) in enumerate(zip(table.rows[0].cells, headers, col_w)):
        cell.width = w
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(h)
        run.font.bold = True
        run.font.size = Pt(9)
        run.font.name = "Times New Roman"
        cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER

    for cable in cables:
        row = table.add_row()
        values = [
            str(cable["n"]),
            cable["mark"],
            str(cable["section"]),
            str(cable["cores"]),
            cable["from"],
            cable["to"],
            str(cable["length_m"]),
            cable["install"],
            cable["note"],
        ]
        for cell, val, w in zip(row.cells, values, col_w):
            cell.width = w
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = p.add_run(val)
            run.font.size = Pt(9)
            run.font.name = "Times New Roman"

    doc.add_paragraph()
    p_sign = doc.add_paragraph()
    r = p_sign.add_run(
        f"Разработал: {proj.get('designer','')}"
        f"\t\t\tПроверил: {proj.get('checker','')}"
        f"\t\t\tН.контроль: {proj.get('norm_head','')}"
    )
    r.font.size = Pt(10)
    r.font.name = "Times New Roman"

    doc.save(str(out_path))
    return out_path


def _write_txt(cables, proj, path: Path):
    lines = [
        "КАБЕЛЬНЫЙ ЖУРНАЛ (ГОСТ 21.613)",
        f"Объект: {proj.get('name','')} | Код: {proj.get('code','')}",
        "",
        f"{'№':<4} {'Марка':<15} {'Сеч.':<6} {'Жил':<4} {'Откуда':<10} {'Куда':<10} {'L,м':<6} {'Прокладка':<12} Примечание",
        "-" * 90,
    ]
    for c in cables:
        lines.append(
            f"{c['n']:<4} {c['mark']:<15} {c['section']:<6} {c['cores']:<4} "
            f"{c['from']:<10} {c['to']:<10} {c['length_m']:<6} {c['install']:<12} {c['note']}"
        )
    path.write_text("\n".join(lines), encoding="utf-8")
