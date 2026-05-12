"""
dwg/gen_sld.py — детальная однолинейная схема щита (DXF, ГОСТ 21.608-84).

Генерирует на каждый щит:
  - Вертикальная шина питания
  - Вводной АВ с кабелем
  - Ответвления к потребителям: АВ + маркировка кабеля + прямоугольник нагрузки
  - Таблица групп (9 колонок) под схемой
  - Упрощённый штамп
"""

from pathlib import Path

try:
    import ezdxf
    _HAS_EZDXF = True
except ImportError:
    _HAS_EZDXF = False

# ── Геометрия ────────────────────────────────────────────────────────
_BUS_X       = 20      # X шины питания
_BUS_Y_TOP   = 160     # Y верхней точки шины
_BUS_Y_BOT   = 10      # Y нижней точки шины (до первого потребителя)
_CONSUMER_X0 = 55      # X первого потребителя
_CONSUMER_DX = 30      # шаг между потребителями по X
_BRANCH_Y    = 120     # Y точки ответвления от шины
_LOAD_Y      = 60      # Y центра прямоугольника нагрузки
_LOAD_W      = 20      # ширина прямоугольника нагрузки
_LOAD_H      = 12      # высота прямоугольника нагрузки

# ── Таблица групп ─────────────────────────────────────────────────────
_COL_HEADERS = ["№", "Наименование", "Фаз", "Pн,кВт", "Iрасч,А",
                "Кабель", "L,м", "АВ", "Прим."]
_COL_W = [8, 55, 8, 12, 10, 28, 8, 18, 10]   # ширины колонок, мм; сумма=157
_ROW_H    = 8    # высота строки данных, мм
_HEADER_H = 10   # высота строки шапки, мм
_TABLE_Y0 = -15  # Y верхней границы таблицы


def _add_layers(doc):
    doc.layers.new("BUS",     dxfattribs={"color": 5,  "lineweight": 70})
    doc.layers.new("WIRE",    dxfattribs={"color": 7,  "lineweight": 25})
    doc.layers.new("BREAKER", dxfattribs={"color": 2,  "lineweight": 25})
    doc.layers.new("EQUIP",   dxfattribs={"color": 3,  "lineweight": 18})
    doc.layers.new("TEXT",    dxfattribs={"color": 7,  "lineweight": 13})
    doc.layers.new("TABLE",   dxfattribs={"color": 7,  "lineweight": 13})


def _line(msp, x1, y1, x2, y2, layer="WIRE"):
    msp.add_line((x1, y1), (x2, y2), dxfattribs={"layer": layer})


def _text(msp, txt, x, y, h=2.5, layer="TEXT"):
    msp.add_text(str(txt), dxfattribs={"layer": layer, "height": h,
                                        "insert": (x, y)})


def _rect(msp, x, y, w, h, layer="EQUIP"):
    msp.add_lwpolyline(
        [(x, y), (x+w, y), (x+w, y+h), (x, y+h)],
        dxfattribs={"layer": layer, "closed": True},
    )


def _draw_breaker(msp, x, y, poles=3):
    """Символ АВ: прямоугольник 4×6 мм + диагональ (IEC 60617 упрощённый)."""
    _rect(msp, x-2, y-3, 4, 6, layer="BREAKER")
    _line(msp, x-2, y-3, x+2, y+3, layer="BREAKER")
    _text(msp, f"{poles}P", x+3, y-1, h=2.0)


def _draw_table(msp, consumers_data: list[dict], panel_r: dict):
    """Рисует таблицу групп ГОСТ 21.608-84."""
    x0 = _BUS_X - 10
    y0 = _TABLE_Y0

    # Шапка
    cx = x0
    for i, (header, w) in enumerate(zip(_COL_HEADERS, _COL_W)):
        _rect(msp, cx, y0 - _HEADER_H, w, _HEADER_H, layer="TABLE")
        _text(msp, header, cx + 1, y0 - _HEADER_H + 3, h=2.5, layer="TABLE")
        cx += w

    # Строки данных
    for row_i, c in enumerate(consumers_data):
        y_row = y0 - _HEADER_H - (row_i + 1) * _ROW_H
        cx = x0
        cable = c.get("cable", {})
        breaker = c.get("breaker", {})
        cable_str = (f"{cable.get('mark','?')} "
                     f"{cable.get('cores','?')}×{cable.get('section_mm2','?')}")
        l_calc = cable.get("length_m_calc") or cable.get("length_m", "?")
        note = "РЕЗ" if c.get("reserve") else ""

        cells = [
            str(row_i + 1),
            c.get("name", "")[:20],
            str(c.get("phases", 3)),
            f"{c.get('power_kw', 0):.1f}",
            f"{c.get('i_calc_a', 0):.1f}",
            cable_str,
            f"{float(l_calc):.0f}" if l_calc != "?" else "?",
            breaker.get("type", "?")[:14],
            note,
        ]
        for cell, w in zip(cells, _COL_W):
            _rect(msp, cx, y_row, w, _ROW_H, layer="TABLE")
            _text(msp, cell, cx + 1, y_row + 2, h=2.0, layer="TABLE")
            cx += w

    # Итоговая строка
    n_rows = len(consumers_data)
    y_total = y0 - _HEADER_H - (n_rows + 1) * _ROW_H
    panel_cable = panel_r.get("cable", {})
    panel_br    = panel_r.get("breaker", {})
    p_total = sum(c.get("power_kw", 0) for c in consumers_data
                  if not c.get("reserve"))
    total_cable = (f"{panel_cable.get('mark','?')} "
                   f"{panel_cable.get('cores','?')}×"
                   f"{panel_cable.get('section_mm2','?')}")

    total_cells = [
        "", "Итого", "",
        f"{p_total:.1f}",
        f"{panel_r.get('i_calc_a', 0):.1f}",
        total_cable, "",
        panel_br.get("type", "?")[:14], "",
    ]
    cx = x0
    for cell, w in zip(total_cells, _COL_W):
        _rect(msp, cx, y_total, w, _ROW_H, layer="TABLE")
        _text(msp, cell, cx + 1, y_total + 2, h=2.0, layer="TABLE")
        cx += w


def _draw_stamp(msp, project: dict, panel_id: str):
    """Упрощённый штамп в правом нижнем углу."""
    proj = project.get("project", {})
    sx, sy = 180, -80
    w, h = 185, 55
    _rect(msp, sx, sy, w, h, layer="TABLE")
    _text(msp, f"Однолинейная схема: {panel_id}", sx+3, sy+44, h=4.0)
    _text(msp, f"Объект: {proj.get('name', '')}", sx+3, sy+34, h=3.5)
    _text(msp, f"Код: {proj.get('code','')}  Стадия: {proj.get('stage','')}",
           sx+3, sy+25, h=3.0)
    _text(msp, f"Разработал: {proj.get('designer', '')}", sx+3, sy+16, h=3.0)
    _text(msp, f"Проверил:   {proj.get('checker', '')}", sx+3, sy+8, h=3.0)
    _text(msp, f"ГИП:        {proj.get('gip', '')}", sx+3, sy+1, h=3.0)


def _find_panel(project: dict, panel_id: str):
    """Ищет панель в _results по panel_id. Возвращает (panel_r, feeder_r) или (None, None)."""
    results = project.get("_results", {})
    for feeder in results.get("vru", {}).get("feeders", []):
        for panel in feeder.get("panels", []):
            if panel.get("id") == panel_id:
                return panel, feeder
    return None, None


def _find_source_consumers(project: dict, panel_id: str) -> list[dict]:
    """Возвращает исходных consumers из vru (с полем power_kw) по panel_id."""
    for feeder in project.get("vru", {}).get("feeders", []):
        for panel in feeder.get("panels", []):
            if panel.get("id") == panel_id:
                return panel.get("consumers", [])
    return []


def generate_panel_sld(project: dict, panel_id: str, output_dir: Path) -> Path | None:
    """
    Генерирует однолинейную схему одного щита.
    Читает из project["_results"]. Не изменяет project.
    Возвращает путь к созданному .dxf или None если ezdxf не установлен.
    """
    if not _HAS_EZDXF:
        return None

    panel_r, _ = _find_panel(project, panel_id)
    if panel_r is None:
        raise ValueError(f"Щит '{panel_id}' не найден в _results")

    # Объединяем данные _results и исходных consumers (нужен power_kw)
    src_consumers = {c.get("id"): c for c in _find_source_consumers(project, panel_id)}
    consumers_data = []
    for c in panel_r.get("consumers", []):
        merged = dict(c)
        src = src_consumers.get(c.get("id"), {})
        merged.setdefault("power_kw", src.get("power_kw", 0.0))
        merged.setdefault("reserve",  src.get("reserve", False))
        consumers_data.append(merged)

    code = project.get("project", {}).get("code", "PROJ")
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"{code}_{panel_id}_sld.dxf"

    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4   # мм
    msp = doc.modelspace()
    _add_layers(doc)

    # ── Заголовок ──────────────────────────────────────────────────────
    panel_name = panel_r.get("name", panel_id)
    _text(msp, f"{panel_id} — {panel_name}", _BUS_X, _BUS_Y_TOP + 5, h=5.0)

    # ── Вводной кабель ─────────────────────────────────────────────────
    in_cable = panel_r.get("cable", {})
    cable_lbl = (f"{in_cable.get('mark','?')} "
                 f"{in_cable.get('cores','?')}×{in_cable.get('section_mm2','?')}")
    _text(msp, cable_lbl, _BUS_X + 5, _BUS_Y_TOP - 5, h=2.5)
    _line(msp, _BUS_X, _BUS_Y_TOP, _BUS_X, _BUS_Y_TOP - 12, layer="WIRE")

    # ── Вводной АВ ─────────────────────────────────────────────────────
    in_br = panel_r.get("breaker", {})
    in_poles = in_br.get("poles", 3)
    _draw_breaker(msp, _BUS_X, _BUS_Y_TOP - 18, poles=in_poles)
    _text(msp, in_br.get("type", "?")[:20], _BUS_X + 5, _BUS_Y_TOP - 20, h=2.5)
    _line(msp, _BUS_X, _BUS_Y_TOP - 24, _BUS_X, _BUS_Y_TOP - 30, layer="WIRE")

    # ── Вертикальная шина ──────────────────────────────────────────────
    bus_y_top = _BUS_Y_TOP - 30
    bus_y_bot = _BUS_Y_BOT + 20
    n = len(consumers_data)
    bus_x_right = _CONSUMER_X0 + max(n - 1, 0) * _CONSUMER_DX + _LOAD_W
    _line(msp, _BUS_X, bus_y_top, bus_x_right, bus_y_top, layer="BUS")  # горизонтальная шина

    # ── Потребители ────────────────────────────────────────────────────
    for ci, c in enumerate(consumers_data):
        cx = _CONSUMER_X0 + ci * _CONSUMER_DX
        br = c.get("breaker", {})
        cb = c.get("cable", {})
        poles = br.get("poles", c.get("phases", 3))

        # Вертикаль от шины вниз
        _line(msp, cx, bus_y_top, cx, bus_y_top - 8, layer="WIRE")

        # Символ АВ
        br_y = bus_y_top - 14
        _draw_breaker(msp, cx, br_y, poles=poles)
        _text(msp, f"{br.get('rating','?')}А", cx - 6, br_y - 7, h=2.0)

        # Вертикаль после АВ
        _line(msp, cx, br_y - 3, cx, _LOAD_Y + _LOAD_H // 2, layer="WIRE")

        # Прямоугольник нагрузки
        _rect(msp, cx - _LOAD_W//2, _LOAD_Y, _LOAD_W, _LOAD_H, layer="EQUIP")
        _text(msp, c.get("id", ""), cx - 8, _LOAD_Y + 7, h=2.5)
        _text(msp, f"{c.get('i_calc_a', 0):.1f}А", cx - 7, _LOAD_Y + 2, h=2.0)

        # Маркировка кабеля
        cb_str = (f"{cb.get('mark','?')} "
                  f"{cb.get('cores','?')}×{cb.get('section_mm2','?')}")
        _text(msp, cb_str, cx - 8, _LOAD_Y - 5, h=1.8)

        # Пометка резервного
        if c.get("reserve"):
            _text(msp, "(рез)", cx - 5, _LOAD_Y - 9, h=2.0)

    # ── Таблица групп ──────────────────────────────────────────────────
    _draw_table(msp, consumers_data, panel_r)

    # ── Штамп ──────────────────────────────────────────────────────────
    _draw_stamp(msp, project, panel_id)

    doc.saveas(str(out_path))
    return out_path


def generate_all_sld(project: dict, output_dir: Path) -> list[Path]:
    """Генерирует схемы для всех щитов проекта. Возвращает список путей."""
    if not _HAS_EZDXF:
        return []

    paths = []
    results = project.get("_results", {})
    for feeder in results.get("vru", {}).get("feeders", []):
        for panel in feeder.get("panels", []):
            panel_id = panel.get("id")
            if panel_id:
                p = generate_panel_sld(project, panel_id, output_dir)
                if p:
                    paths.append(p)
    return paths
