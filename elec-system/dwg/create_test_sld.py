"""
dwg/create_test_sld.py — создание тестовой однолинейной схемы (DXF).

Генерирует упрощённую однолинейку:
  - Ввод от ТП
  - ВРУ с вводным автоматом
  - Отходящие группы к щитам
  - Потребители с автоматами и кабелями

Зависимость: ezdxf (pip install ezdxf)
"""

import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def create_test_sld(project: dict, output_dir: Path) -> Path:
    """
    Создаёт однолинейную схему в DXF формате.
    Возвращает путь к созданному файлу.
    """
    try:
        import ezdxf
        from ezdxf.enums import TextEntityAlignment
        _has_ezdxf = True
    except ImportError:
        _has_ezdxf = False

    proj = project["project"]
    code = proj.get("code", "DEMO")
    out_path = output_dir / f"{code}_sld.dxf"

    if not _has_ezdxf:
        # Создаём простейший текстовый DXF вручную
        _write_minimal_dxf(project, out_path)
        return out_path

    results = project.get("_results", {})
    vru_r = results.get("vru", {}) if results else project.get("vru", {})

    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4  # мм
    msp = doc.modelspace()

    # Слои
    doc.layers.new("WIRES",   dxfattribs={"color": 7, "lineweight": 50})
    doc.layers.new("EQUIP",   dxfattribs={"color": 5, "lineweight": 25})
    doc.layers.new("TEXT",    dxfattribs={"color": 7, "lineweight": 13})
    doc.layers.new("BREAKER", dxfattribs={"color": 2, "lineweight": 25})

    def line(x1, y1, x2, y2, layer="WIRES"):
        msp.add_line((x1, y1), (x2, y2), dxfattribs={"layer": layer})

    def text(txt, x, y, h=3.5, layer="TEXT"):
        msp.add_text(txt, dxfattribs={"layer": layer, "height": h, "insert": (x, y)})

    def rect(x, y, w, h, layer="EQUIP"):
        msp.add_lwpolyline(
            [(x, y), (x+w, y), (x+w, y+h), (x, y+h), (x, y)],
            dxfattribs={"layer": layer, "closed": True}
        )

    def breaker_sym(x, y, layer="BREAKER"):
        """Символ автоматического выключателя (прямоугольник 4×6)."""
        rect(x-2, y-3, 4, 6, layer=layer)
        line(x, y+3, x, y+6, layer=layer)
        line(x, y-3, x, y-6, layer=layer)

    # ─── Ввод от ТП ───────────────────────────────────────
    x_vru = 100
    y_top = 250

    text("ТП-1", x_vru - 10, y_top + 10, h=4)
    line(x_vru, y_top + 5, x_vru, y_top - 10)  # линия ввода

    # ─── ВРУ ──────────────────────────────────────────────
    vru_w, vru_h = 40, 30
    x_vru_box = x_vru - vru_w // 2
    y_vru_box = y_top - 10 - vru_h
    rect(x_vru_box, y_vru_box, vru_w, vru_h, "EQUIP")

    vru_id = vru_r.get("id", "ВРУ-1")
    vru_br = vru_r.get("breaker", {})
    vru_ic = vru_r.get("incoming_cable", vru_r.get("incoming_cable", {}))
    ic_text = f"{vru_ic.get('mark','?')} {vru_ic.get('cores','?')}×{vru_ic.get('section_mm2','?')}"

    text(vru_id, x_vru_box + 2, y_vru_box + vru_h - 8, h=4, layer="TEXT")
    text(f"АВ {vru_br.get('rating','?')}А", x_vru_box + 2, y_vru_box + 4, h=3, layer="TEXT")
    text(ic_text, x_vru + 5, y_top - 5, h=2.5, layer="TEXT")

    # ─── Группы и щиты ────────────────────────────────────
    feeders = vru_r.get("feeders", [])
    n_feeders = len(feeders)
    if n_feeders == 0:
        doc.saveas(str(out_path))
        return out_path

    x_spacing = 80
    x_start = x_vru - (n_feeders - 1) * x_spacing // 2
    y_panel = y_vru_box - 80

    for fi, feeder in enumerate(feeders):
        x_f = x_start + fi * x_spacing
        y_bus = y_vru_box

        # Линия от ВРУ к щиту
        line(x_vru, y_bus, x_vru, y_bus - 10, "WIRES")    # вертикаль от ВРУ
        line(x_vru, y_bus - 10, x_f, y_bus - 10, "WIRES") # горизонталь
        line(x_f, y_bus - 10, x_f, y_panel + 30, "WIRES") # вертикаль к щиту

        for panel in feeder.get("panels", []):
            pb = panel.get("breaker", {})
            pc = panel.get("cable", {})

            # Автомат группы
            breaker_sym(x_f, y_panel + 25)
            text(f"АВ {pb.get('rating','?')}А", x_f + 4, y_panel + 22, h=2.5)

            # Щит
            pbox_w, pbox_h = 30, 20
            rect(x_f - pbox_w//2, y_panel - pbox_h, pbox_w, pbox_h, "EQUIP")
            text(panel["id"], x_f - 12, y_panel - 8, h=3.5)
            text(f"Iр={panel.get('i_calc_a',0):.0f}А", x_f - 12, y_panel - 15, h=2.5)

            # Кабель
            cable_str = f"{pc.get('mark','?')} {pc.get('cores','?')}×{pc.get('section_mm2','?')}"
            text(cable_str, x_f + 3, y_panel + 5, h=2, layer="TEXT")

            # Потребители
            consumers = panel.get("consumers", [])
            for ci, c in enumerate(consumers[:4]):  # макс 4 на схеме
                x_c = x_f - 15 + ci * 12
                y_c = y_panel - pbox_h - 30

                line(x_f, y_panel - pbox_h, x_f, y_panel - pbox_h - 10, "WIRES")
                line(x_f, y_panel - pbox_h - 10, x_c, y_panel - pbox_h - 10, "WIRES")
                line(x_c, y_panel - pbox_h - 10, x_c, y_c + 10, "WIRES")

                breaker_sym(x_c, y_c + 5, "BREAKER")
                cb = c.get("breaker", {})
                text(f"{cb.get('rating','?')}А", x_c - 5, y_c - 5, h=2.0)
                text(c["id"], x_c - 5, y_c - 9, h=2.0)

    # Штамп (упрощённый)
    stamp_x, stamp_y = 0, -50
    rect(stamp_x, stamp_y, 185, 55, "EQUIP")
    text("Однолинейная схема электроснабжения (тест)", stamp_x + 5, stamp_y + 40, h=4)
    text(f"Объект: {proj.get('name','')}", stamp_x + 5, stamp_y + 30, h=3.5)
    text(f"Код: {proj.get('code','')} | Стадия: {proj.get('stage','')} | Ред.: {proj.get('revision',0)}", stamp_x + 5, stamp_y + 22, h=3)
    text(f"Разработал: {proj.get('designer','')}", stamp_x + 5, stamp_y + 12, h=3)
    text(f"Проверил: {proj.get('checker','')}", stamp_x + 5, stamp_y + 4, h=3)

    doc.saveas(str(out_path))
    return out_path


def _write_minimal_dxf(project: dict, path: Path):
    """Создаёт минимальный DXF без ezdxf (только заголовок)."""
    proj = project["project"]
    content = f"""0
SECTION
2
HEADER
9
$ACADVER
1
AC1015
0
ENDSEC
0
SECTION
2
ENTITIES
0
TEXT
8
TEXT
10
10.0
20
10.0
30
0.0
40
5.0
1
{proj.get('name','')} - однолинейная схема (ezdxf не установлен)
0
ENDSEC
0
EOF
"""
    path.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    import json
    import sys

    if len(sys.argv) < 2:
        print("Использование: python create_test_sld.py <путь_к_проекту>")
        sys.exit(1)

    proj_dir = Path(sys.argv[1])
    with open(proj_dir / "project.json", encoding="utf-8") as f:
        project = json.load(f)

    if not project.get("_results"):
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from calc.engine import calculate_project
        project = calculate_project(project)

    out = create_test_sld(project, proj_dir / "dwg")
    print(f"Однолинейка создана: {out}")
