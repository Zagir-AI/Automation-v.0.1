"""
dwg/gen_sld.py — детальная однолинейная схема щита (ГОСТ 21.608-84).

Генерирует DXF для каждого щита:
  - горизонтальная шина питания (BUS)
  - вводной АВ с кабелем
  - ветви на каждого потребителя (автомат + прямоугольник)
  - таблица групп по ГОСТ 21.608-84
  - упрощённый штамп

Зависимость: ezdxf (pip install ezdxf)
"""
from __future__ import annotations

from pathlib import Path

# ── Геометрия схемы (мм) ────────────────────────────────────────────────────
_CONSUMER_STEP = 28        # шаг между ветвями потребителей
_CONSUMER_X0   = 20        # X центра первой ветви
_BUS_Y         = 172       # Y горизонтальной шины питания
_BRANCH_BR_Y   = 155       # Y центра АВ ветви
_BOX_TOP_Y     = 136       # Y верха прямоугольника потребителя
_BOX_H         = 14
_BOX_W         = 16

# ── Таблица групп ────────────────────────────────────────────────────────────
_COL_W = [10, 60, 8, 12, 10, 25, 8, 15, 10]   # сумма = 158 мм
_COL_HEADERS = [
    "№", "Наименование", "Фаз", "Pуст,кВт",
    "Iрасч,А", "Кабель", "L,м", "АВ", "Прим.",
]
_ROW_H  = 8
_HEAD_H = 10
_TABLE_TOP = -15   # Y верха шапки таблицы


def _all_panels(project: dict):
    """Перебирает все щиты из _results."""
    vru = project.get("_results", {}).get("vru", {})
    for feeder in vru.get("feeders", []):
        for panel in feeder.get("panels", []):
            yield panel


def generate_panel_sld(project: dict, panel_id: str, output_dir: Path):
    """
    Генерирует однолинейную схему одного щита.
    Читает из project["_results"]. Не изменяет project.
    Возвращает путь к созданному .dxf файлу или None при ошибке.
    """
    panel = next((p for p in _all_panels(project) if p["id"] == panel_id), None)
    if panel is None:
        return None
    return _draw_panel(project, panel, output_dir)


def generate_all_sld(project: dict, output_dir: Path) -> list:
    """Генерирует схемы для всех щитов. Возвращает список путей."""
    paths = []
    for panel in _all_panels(project):
        p = _draw_panel(project, panel, output_dir)
        if p:
            paths.append(p)
    return paths


def _draw_panel(project: dict, panel: dict, output_dir: Path):
    """Рисует DXF для одного щита, возвращает Path или None."""
    try:
        import ezdxf
    except ImportError:
        import warnings
        warnings.warn("ezdxf не установлен — установи: pip install ezdxf")
        return None

    proj      = project.get("project", {})
    code      = proj.get("code", "PROJ")
    panel_id  = panel["id"]
    consumers = panel.get("consumers", [])
    n         = len(consumers)

    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4   # мм
    msp = doc.modelspace()

    for lname, color, lw in [
        ("BUS",     5, 70),
        ("WIRE",    7, 25),
        ("BREAKER", 2, 25),
        ("EQUIP",   3, 18),
        ("TEXT",    7, 13),
        ("TABLE",   7, 13),
    ]:
        doc.layers.new(lname, dxfattribs={"color": color, "lineweight": lw})

    # ── Вспомогательные функции ──────────────────────────────────────────

    def _line(x1, y1, x2, y2, layer="WIRE"):
        msp.add_line((x1, y1), (x2, y2), dxfattribs={"layer": layer})

    def _txt(s, x, y, h=2.5, layer="TEXT"):
        msp.add_text(str(s), dxfattribs={"layer": layer, "height": h, "insert": (x, y)})

    def _rect(x, y, w, h, layer="EQUIP"):
        msp.add_lwpolyline(
            [(x, y), (x + w, y), (x + w, y + h), (x, y + h)],
            dxfattribs={"layer": layer, "closed": True},
        )

    def _breaker(x, y, poles=1, layer="BREAKER"):
        """Символ АВ: прямоугольник 4×6 мм + диагональ."""
        _rect(x - 2, y - 3, 4, 6, layer)
        _line(x - 2, y - 3, x + 2, y + 3, layer)
        _txt(f"{poles}P", x + 3, y - 1, h=2.0)

    # ── Заголовок ────────────────────────────────────────────────────────

    _txt(f"{panel_id} — {panel['name']}", 5, 205, h=4.5)
    _txt(
        f"Iрасч={panel['i_calc_a']:.1f} А  "
        f"Pуст={panel.get('p_installed_kw', 0):.1f} кВт  "
        f"ГОСТ 21.608-84",
        5, 198, h=3.0,
    )

    # ── Горизонтальная шина питания ──────────────────────────────────────

    bus_x0 = _CONSUMER_X0 - 12
    bus_x1 = _CONSUMER_X0 + max(n - 1, 0) * _CONSUMER_STEP + 14
    _line(bus_x0, _BUS_Y, bus_x1, _BUS_Y, "BUS")

    # ── Вводной кабель и АВ ──────────────────────────────────────────────

    x_in   = (bus_x0 + bus_x1) // 2
    in_br  = panel.get("breaker", {})
    in_cab = panel.get("cable", {})
    cab_in = (
        f"{in_cab.get('mark', '?')} "
        f"{in_cab.get('cores', '?')}×{in_cab.get('section_mm2', '?')}"
    )

    _line(x_in, 196, x_in, 192, "WIRE")           # провод сверху
    _breaker(x_in, 187, poles=in_br.get("poles", 3))
    _line(x_in, 181, x_in, _BUS_Y, "WIRE")         # провод к шине

    _txt(f"Ввод: {cab_in}", x_in + 6, 187, h=2.5)
    _txt(
        f"АВ {in_br.get('rating', '?')}А {in_br.get('char', 'C')} "
        f"{in_br.get('poles', 3)}П",
        x_in + 6, 182, h=2.5,
    )

    # ── Ветви потребителей ────────────────────────────────────────────────

    for ci, c in enumerate(consumers):
        xc = _CONSUMER_X0 + ci * _CONSUMER_STEP   # центр ветви

        # Вертикаль от шины к АВ
        _line(xc, _BUS_Y, xc, _BRANCH_BR_Y + 3, "WIRE")

        # АВ ветви
        cb = c.get("breaker", {})
        _breaker(xc, _BRANCH_BR_Y, poles=cb.get("poles", 1))

        # Провод к прямоугольнику
        _line(xc, _BRANCH_BR_Y - 3, xc, _BOX_TOP_Y + _BOX_H, "WIRE")

        # Прямоугольник потребителя
        _rect(xc - _BOX_W // 2, _BOX_TOP_Y, _BOX_W, _BOX_H, "EQUIP")

        # ID потребителя внутри
        _txt(c["id"], xc - _BOX_W // 2 + 1, _BOX_TOP_Y + 5, h=2.0)

        # Данные ниже прямоугольника
        cc   = c.get("cable", {})
        l_val = cc.get("length_m_calc", cc.get("length_m", "?"))
        cab_c = (f"{cc.get('mark', '?')} "
                 f"{cc.get('cores', '?')}×{cc.get('section_mm2', '?')}")
        _txt(cab_c,                    xc - _BOX_W // 2, _BOX_TOP_Y - 6,  h=2.0)
        _txt(f"L={l_val}м",            xc - _BOX_W // 2, _BOX_TOP_Y - 11, h=2.0)
        _txt(f"Iр={c.get('i_calc_a', 0):.1f}А", xc - _BOX_W // 2, _BOX_TOP_Y - 16, h=2.0)

        if c.get("reserve"):
            _txt("(рез)", xc - 4, _BOX_TOP_Y + _BOX_H + 1, h=2.0)

    # ── Таблица групп ─────────────────────────────────────────────────────

    table_bottom = _draw_table(panel, _line, _txt, _rect)

    # ── Штамп ────────────────────────────────────────────────────────────

    stamp_y = table_bottom - 65
    _rect(0, stamp_y, 185, 55, "EQUIP")
    _txt(f"Однолинейная схема: {panel_id} {panel['name']}", 5, stamp_y + 47, h=3.5)
    _txt(f"Объект: {proj.get('name', '')}",                  5, stamp_y + 38, h=3.0)
    _txt(f"Разработал: {proj.get('designer', '')}",          5, stamp_y + 28, h=3.0)
    _txt(f"Проверил:   {proj.get('checker', '')}",           5, stamp_y + 20, h=3.0)
    _txt(f"ГИП:        {proj.get('gip', '')}",               5, stamp_y + 12, h=3.0)
    _txt(
        f"Код: {proj.get('code', '')} | Стадия: {proj.get('stage', '')} | ГОСТ 21.608-84",
        5, stamp_y + 4, h=2.5,
    )

    # ── Сохранение ────────────────────────────────────────────────────────

    safe_id  = panel_id.replace("/", "-").replace("\\", "-")
    out_path = output_dir / f"{code}_{safe_id}_sld.dxf"
    doc.saveas(str(out_path))
    return out_path


def _draw_table(panel: dict, _line, _txt, _rect) -> int:
    """Рисует таблицу групп ГОСТ 21.608-84. Возвращает Y нижней границы."""
    col_x = [0]
    for w in _COL_W:
        col_x.append(col_x[-1] + w)
    total_w = col_x[-1]  # 158 мм

    consumers = panel.get("consumers", [])
    n_data    = len(consumers) + 1   # строки данных + итоговая

    table_top  = _TABLE_TOP                        # -15
    header_bot = table_top - _HEAD_H               # -25
    data_bot   = header_bot - n_data * _ROW_H      # нижняя граница

    # Внешний прямоугольник таблицы (целиком)
    _rect(0, data_bot, total_w, table_top - data_bot, "TABLE")

    # Горизонталь: шапка / данные
    _line(0, header_bot, total_w, header_bot, "TABLE")

    # Горизонтальные линии между строками данных
    for ri in range(1, n_data):
        ry = header_bot - ri * _ROW_H
        _line(0, ry, total_w, ry, "TABLE")

    # Вертикальные разделители (полная высота таблицы)
    for cx in col_x[1:-1]:
        _line(cx, data_bot, cx, table_top, "TABLE")

    # Текст шапки
    for ci, (header, cx0) in enumerate(zip(_COL_HEADERS, col_x)):
        _txt(header, cx0 + 1, header_bot + 2, h=2.5, layer="TABLE")

    # Строки потребителей
    for ri, c in enumerate(consumers):
        ty  = header_bot - ri * _ROW_H - _ROW_H + 2
        cc  = c.get("cable", {})
        cb  = c.get("breaker", {})
        cab = (f"{cc.get('mark', '?')} "
               f"{cc.get('cores', '?')}×{cc.get('section_mm2', '?')}")
        l_val = cc.get("length_m_calc", cc.get("length_m", "?"))
        name  = c["name"]
        if c.get("reserve"):
            name = "(рез) " + name

        row = [
            str(ri + 1),
            name[:28],
            str(c.get("phases", 3)),
            f"{c.get('power_kw', 0):.1f}",
            f"{c.get('i_calc_a', 0):.1f}",
            cab[:22],
            str(l_val),
            cb.get("type", f"АВ {cb.get('rating', '?')}А")[:20],
            "РЕЗ" if c.get("reserve") else "",
        ]
        for cell, cx0 in zip(row, col_x):
            if cell:
                _txt(cell, cx0 + 1, ty, h=2.0, layer="TABLE")

    # Итоговая строка
    p_total    = sum(c.get("power_kw", 0) for c in consumers if not c.get("reserve"))
    in_br      = panel.get("breaker", {})
    in_cab     = panel.get("cable", {})
    in_cab_str = (f"{in_cab.get('mark', '?')} "
                  f"{in_cab.get('cores', '?')}×{in_cab.get('section_mm2', '?')}")
    total_ty   = header_bot - len(consumers) * _ROW_H - _ROW_H + 2

    total_row = [
        "",
        "Итого",
        "",
        f"{p_total:.1f}",
        f"{panel.get('i_calc_a', 0):.1f}",
        in_cab_str[:22],
        "",
        in_br.get("type", f"АВ {in_br.get('rating', '?')}А")[:20],
        "",
    ]
    for cell, cx0 in zip(total_row, col_x):
        if cell:
            _txt(cell, cx0 + 1, total_ty, h=2.0, layer="TABLE")

    return data_bot
