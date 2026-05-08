"""
dwg/gen_plans.py — генерация DXF-планов электроснабжения.

Создаёт два типа планов:
  section_plan  — план одного раздела (расстановка щитов и потребителей)
  summary_plan  — сводный план (только щиты с нагрузками)

Координаты:
  - Берутся из project["layout"] если есть
  - Иначе — автоматическая расстановка в строки

Слои DXF:
  PANELS    — щиты (блок прямоугольник 600×400)
  CONSUMERS — потребители (блок круг ⌀200)
  CABLES    — кабельные трассы (линии)
  LABELS    — текстовые подписи
  DIMS      — размеры
  CHANGES   — трапеция изменений (только при rev > 0)
"""

from __future__ import annotations
from pathlib import Path
import math

import ezdxf
from ezdxf import colors
from ezdxf.enums import TextEntityAlignment


# ── Константы чертежа ─────────────────────────────────────────────────────────

PANEL_W     = 600    # ширина блока щита, мм
PANEL_H     = 400    # высота блока щита, мм
PANEL_COLS  = 4      # щитов в ряду при автоматической расстановке
PANEL_GAP_X = 1200   # шаг по X между щитами
PANEL_GAP_Y = 1000   # шаг по Y между рядами
CONSUMER_R  = 100    # радиус блока потребителя, мм
CONSUMER_COLS = 6    # потребителей в ряду
CONSUMER_GAP  = 500  # шаг между потребителями

TEXT_H_LARGE  = 200  # высота заголовочного текста
TEXT_H_NORMAL = 150  # высота обычного текста
TEXT_H_SMALL  = 100  # высота мелкого текста

# Слои
LAYER_PANELS    = "PANELS"
LAYER_CONSUMERS = "CONSUMERS"
LAYER_CABLES    = "CABLES"
LAYER_LABELS    = "LABELS"
LAYER_DIMS      = "DIMS"
LAYER_CHANGES   = "CHANGES"


# ── Вспомогательные функции ───────────────────────────────────────────────────

def _setup_layers(doc: ezdxf.document.Drawing):
    """Создаёт стандартные слои чертежа."""
    layers = [
        (LAYER_PANELS,    colors.CYAN),
        (LAYER_CONSUMERS, colors.GREEN),
        (LAYER_CABLES,    colors.YELLOW),
        (LAYER_LABELS,    colors.WHITE),
        (LAYER_DIMS,      colors.RED),
        (LAYER_CHANGES,   colors.MAGENTA),
    ]
    for name, color in layers:
        if name not in doc.layers:
            layer = doc.layers.add(name)
            layer.color = color


def _add_panel_block(doc: ezdxf.document.Drawing):
    """Создаёт блок 'PANEL_BOX' — прямоугольник щита с атрибутами."""
    if "PANEL_BOX" in doc.blocks:
        return

    blk = doc.blocks.new("PANEL_BOX")
    # Прямоугольник
    blk.add_lwpolyline(
        [(0, 0), (PANEL_W, 0), (PANEL_W, PANEL_H), (0, PANEL_H), (0, 0)],
        dxfattribs={"layer": LAYER_PANELS}
    )
    # Диагональ
    blk.add_line((0, 0), (PANEL_W, PANEL_H),
                 dxfattribs={"layer": LAYER_PANELS})
    # Атрибуты
    blk.add_attdef("PANEL_ID",    insert=(PANEL_W/2, PANEL_H + 50),
                   dxfattribs={"height": TEXT_H_NORMAL, "layer": LAYER_LABELS,
                                "halign": 1, "valign": 0})
    blk.add_attdef("PANEL_NAME",  insert=(PANEL_W/2, -150),
                   dxfattribs={"height": TEXT_H_SMALL, "layer": LAYER_LABELS,
                                "halign": 1, "valign": 0})
    blk.add_attdef("PANEL_LOAD",  insert=(PANEL_W/2, -280),
                   dxfattribs={"height": TEXT_H_SMALL, "layer": LAYER_LABELS,
                                "halign": 1, "valign": 0})


def _add_consumer_block(doc: ezdxf.document.Drawing):
    """Создаёт блок 'CONSUMER_CIRCLE' — окружность потребителя."""
    if "CONSUMER_CIRCLE" in doc.blocks:
        return

    blk = doc.blocks.new("CONSUMER_CIRCLE")
    blk.add_circle((0, 0), CONSUMER_R,
                   dxfattribs={"layer": LAYER_CONSUMERS})
    blk.add_attdef("ID_TAG",    insert=(0, CONSUMER_R + 30),
                   dxfattribs={"height": TEXT_H_SMALL, "layer": LAYER_LABELS,
                                "halign": 4, "valign": 0})
    blk.add_attdef("POWER_KW",  insert=(0, -CONSUMER_R - 30),
                   dxfattribs={"height": TEXT_H_SMALL, "layer": LAYER_LABELS,
                                "halign": 4, "valign": 0})


def _place_panel(msp, panel_id: str, panel_name: str, load_str: str,
                 x: float, y: float):
    """Вставляет блок щита в MSP."""
    ref = msp.add_blockref("PANEL_BOX", (x, y))
    ref.add_attrib("PANEL_ID",   panel_id,   insert=(x + PANEL_W/2, y + PANEL_H + 50))
    ref.add_attrib("PANEL_NAME", panel_name[:24], insert=(x + PANEL_W/2, y - 150))
    ref.add_attrib("PANEL_LOAD", load_str,   insert=(x + PANEL_W/2, y - 280))


def _place_consumer(msp, c_id: str, p_kw: float, x: float, y: float):
    """Вставляет блок потребителя в MSP."""
    ref = msp.add_blockref("CONSUMER_CIRCLE", (x, y))
    ref.add_attrib("ID_TAG",   c_id,           insert=(x, y + CONSUMER_R + 30))
    ref.add_attrib("POWER_KW", f"{p_kw:.2f}кВт", insert=(x, y - CONSUMER_R - 30))


def _draw_cable_line(msp, x1: float, y1: float, x2: float, y2: float,
                     label: str = ""):
    """Рисует кабельную трассу."""
    msp.add_line((x1, y1), (x2, y2), dxfattribs={"layer": LAYER_CABLES})
    if label:
        mx = (x1 + x2) / 2
        my = (y1 + y2) / 2
        msp.add_text(label,
                     dxfattribs={"insert": (mx, my + 60),
                                 "height": TEXT_H_SMALL,
                                 "layer": LAYER_LABELS})


def _add_title_block(msp, title: str, subtitle: str, date_str: str,
                     x: float = 0, y: float = -1500):
    """Добавляет упрощённый штамп чертежа."""
    msp.add_text(title,
                 dxfattribs={"insert": (x, y),
                             "height": TEXT_H_LARGE,
                             "layer": LAYER_LABELS})
    msp.add_text(subtitle,
                 dxfattribs={"insert": (x, y - 300),
                             "height": TEXT_H_NORMAL,
                             "layer": LAYER_LABELS})
    msp.add_text(f"Дата: {date_str}",
                 dxfattribs={"insert": (x, y - 500),
                             "height": TEXT_H_SMALL,
                             "layer": LAYER_LABELS})


def _add_changes_trapezoid(msp, revision: int, change_note: str,
                            x: float, y: float):
    """Трапеция изменений (ГОСТ). Только при rev > 0."""
    if revision <= 0:
        return
    # Простая рамка изменений
    msp.add_lwpolyline(
        [(x, y), (x + 3000, y), (x + 3000, y + 400), (x, y + 400), (x, y)],
        dxfattribs={"layer": LAYER_CHANGES}
    )
    msp.add_text(f"Изм.{revision}: {change_note[:40]}",
                 dxfattribs={"insert": (x + 50, y + 150),
                             "height": TEXT_H_SMALL,
                             "layer": LAYER_CHANGES})


# ── Генератор планов ──────────────────────────────────────────────────────────

def _iter_panels(vru_results: dict):
    for feeder in vru_results.get("feeders", []):
        for panel in feeder.get("panels", []):
            yield panel


def generate_section_plan(project: dict, output_dir: Path | str,
                           section: str | None = None) -> Path:
    """
    Генерирует план раздела — расстановка щитов и потребителей.

    Args:
        project:    project.json (с _results)
        output_dir: папка для DXF
        section:    код раздела ("ОВ", "ВК", ...) или None = все

    Returns:
        Path к DXF-файлу
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    proj_info = project.get("project", {})
    proj_name = proj_info.get("name", "Объект")
    proj_code = proj_info.get("code", "")
    revision  = proj_info.get("revision", 0)
    from datetime import date
    date_str  = str(date.today())

    vru = project.get("_results", {}).get("vru", {})

    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4  # мм
    _setup_layers(doc)
    _add_panel_block(doc)
    _add_consumer_block(doc)
    msp = doc.modelspace()

    # Фильтрация по разделу
    panels = list(_iter_panels(vru))
    if section:
        _sect_types = {
            "ОВ": "heating", "ВК": "ventilation", "КВ": "hvac",
            "ТХ": "technology", "ДУ": "smoke_exhaust", "ПС": "firefighting",
            "ЭОМ": "lighting", "ЭН": "outdoor_lighting",
        }
        ftype = _sect_types.get(section)
        if ftype:
            panels = [p for p in panels if p.get("type") == ftype]

    # Расстановка щитов
    for idx, panel in enumerate(panels):
        col = idx % PANEL_COLS
        row = idx // PANEL_COLS
        px = col * PANEL_GAP_X
        py = row * PANEL_GAP_Y * (-1)  # вниз

        p_kw = panel.get("p_calc_kw", 0)
        load_str = f"P={p_kw:.1f}кВт I={panel.get('i_calc_a',0):.1f}А"
        _place_panel(msp, panel["id"], panel.get("name",""), load_str, px, py)

        # Потребители данного щита
        consumers = [c for c in panel.get("consumers", [])
                     if not c.get("reserve", False)]
        base_y = py - 800
        for cidx, c in enumerate(consumers):
            ccol = cidx % CONSUMER_COLS
            crow = cidx // CONSUMER_COLS
            cx = ccol * CONSUMER_GAP
            cy = base_y - crow * CONSUMER_GAP

            _place_consumer(msp, c.get("id",""), c.get("power_kw", 0), cx, cy)

            # Линия к щиту
            panel_cx = px + PANEL_W / 2
            panel_bottom = py
            cable = c.get("cable", {})
            cable_label = (f"{cable.get('mark','')} "
                           f"{cable.get('cores','')}×{cable.get('section_mm2','')}") if cable else ""
            _draw_cable_line(msp, cx, cy + CONSUMER_R, panel_cx, panel_bottom, cable_label)

    # Заголовок
    title_y = -(len(panels) // PANEL_COLS + 1) * PANEL_GAP_Y - 1200
    plan_title = f"ПЛАН {'РАЗДЕЛА ' + section if section else 'ЭЛЕКТРОСНАБЖЕНИЯ'}"
    _add_title_block(msp, plan_title,
                     f"{proj_code} {proj_name}", date_str,
                     0, title_y)

    # Трапеция изменений
    if revision > 0:
        changes = project.get("changes", [])
        last_change = changes[-1].get("description", "") if changes else ""
        _add_changes_trapezoid(msp, revision, last_change, 0, title_y - 800)

    fname = f"plan_{'section_' + section if section else 'electrical'}.dxf"
    out = output_dir / fname
    doc.saveas(str(out))
    return out


def generate_summary_plan(project: dict, output_dir: Path | str) -> Path:
    """
    Генерирует сводный план — только щиты с нагрузками и ВРУ.

    Returns:
        Path к DXF-файлу
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    proj_info = project.get("project", {})
    proj_name = proj_info.get("name", "Объект")
    proj_code = proj_info.get("code", "")
    revision  = proj_info.get("revision", 0)
    from datetime import date
    date_str  = str(date.today())

    vru = project.get("_results", {}).get("vru", {})

    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4
    _setup_layers(doc)
    _add_panel_block(doc)
    msp = doc.modelspace()

    panels = list(_iter_panels(vru))

    # ВРУ в центре сверху
    vru_x = (PANEL_COLS // 2) * PANEL_GAP_X
    vru_y = PANEL_GAP_Y
    vru_load = (f"P={vru.get('p_calc_kw',0):.1f}кВт  "
                f"I={vru.get('i_calc_a',0):.1f}А")
    _place_panel(msp, "ВРУ-1", "Вводно-распределительное устройство",
                 vru_load, vru_x, vru_y)

    # Щиты в ряд
    for idx, panel in enumerate(panels):
        col = idx % PANEL_COLS
        row = idx // PANEL_COLS
        px = col * PANEL_GAP_X
        py = -(row * PANEL_GAP_Y)

        p_kw = panel.get("p_calc_kw", 0)
        load_str = f"P={p_kw:.1f}кВт I={panel.get('i_calc_a',0):.1f}А"
        _place_panel(msp, panel["id"], panel.get("name",""), load_str, px, py)

        # Линия ВРУ → Щит
        panel_cx = px + PANEL_W / 2
        panel_top = py + PANEL_H
        vru_cx = vru_x + PANEL_W / 2
        vru_bottom = vru_y

        cable = panel.get("cable", {}) if "cable" in panel else \
                panel.get("incoming_cable", {})
        cable_label = ""
        if cable:
            cable_label = (f"{cable.get('mark','')} "
                           f"{cable.get('cores','')}×{cable.get('section_mm2','')}")
        _draw_cable_line(msp, panel_cx, panel_top, vru_cx, vru_bottom, cable_label)

    # Заголовок
    title_y = -(len(panels) // PANEL_COLS + 1) * PANEL_GAP_Y - 1200
    _add_title_block(msp, "СВОДНЫЙ ПЛАН ЭЛЕКТРОСНАБЖЕНИЯ",
                     f"{proj_code} {proj_name}", date_str,
                     0, title_y)

    if revision > 0:
        changes = project.get("changes", [])
        last_change = changes[-1].get("description", "") if changes else ""
        _add_changes_trapezoid(msp, revision, last_change, 0, title_y - 800)

    out = output_dir / "plan_summary.dxf"
    doc.saveas(str(out))
    return out
