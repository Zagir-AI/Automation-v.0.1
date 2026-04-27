#!/usr/bin/env python3
"""
cli.py — главная точка входа в систему.

Использование:
  python cli.py new <код_объекта> "<название>"         — создать новый проект
  python cli.py calc <путь>                            — рассчитать нагрузки ВРУ
  python cli.py calc-outdoor <путь>                   — рассчитать наружные сети
  python cli.py summary <путь>                         — краткая сводка
  python cli.py docs <путь> [--type spec|cable|load|pnr]  — документы
  python cli.py plan <путь> [--section ОВ]            — DXF-план
  python cli.py check-selectivity <путь>              — проверить селективность
  python cli.py check-compensation <путь>             — проверить КРМ
  python cli.py import <путь> dwg|table <файл>        — импорт из DXF или Excel
  python cli.py validate <путь>                        — проверить JSON
  python cli.py list                                   — список проектов
"""

import sys
import os
import json
import argparse
import copy
from pathlib import Path

# ── пути ────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent
PROJECTS_DIR = ROOT / "projects"
PROJECTS_DIR.mkdir(exist_ok=True)
sys.path.insert(0, str(ROOT))

# ── ANSI цвета для терминала ──────────────────────────────────────────
class C:
    RESET  = "\033[0m"
    BOLD   = "\033[1m"
    GREEN  = "\033[92m"
    YELLOW = "\033[93m"
    RED    = "\033[91m"
    CYAN   = "\033[96m"
    GRAY   = "\033[90m"
    WHITE  = "\033[97m"

def ok(s):   return f"{C.GREEN}✓{C.RESET} {s}"
def warn(s): return f"{C.YELLOW}⚠{C.RESET} {s}"
def err(s):  return f"{C.RED}✗{C.RESET} {s}"
def info(s): return f"{C.CYAN}→{C.RESET} {s}"
def hdr(s):  return f"\n{C.BOLD}{C.WHITE}{s}{C.RESET}"


# ── УТИЛИТЫ ──────────────────────────────────────────────────────────

def load_project(path: Path) -> dict:
    json_file = path / "project.json" if path.is_dir() else path
    if not json_file.exists():
        print(err(f"Файл не найден: {json_file}"))
        sys.exit(1)
    with open(json_file, encoding="utf-8") as f:
        return json.load(f)

def save_project(project: dict, path: Path):
    json_file = path / "project.json" if path.is_dir() else path
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(project, f, ensure_ascii=False, indent=2)

def find_project_dir(arg: str) -> Path:
    """Найти папку проекта по аргументу (путь или код)."""
    p = Path(arg)
    if p.exists():
        return p
    for d in PROJECTS_DIR.iterdir():
        if d.is_dir() and arg.upper() in d.name.upper():
            return d
    print(err(f"Проект не найден: {arg}"))
    sys.exit(1)

def _ensure_calc(project: dict, proj_dir: Path) -> dict:
    """Если расчёт не выполнен — запускает автоматически."""
    if not project.get("_results"):
        print(info("Запускаю расчёт автоматически..."))
        from calc.engine import calculate_project
        project = calculate_project(project)
        save_project(project, proj_dir)
    return project


# ── КОМАНДЫ ───────────────────────────────────────────────────────────

def cmd_list(args):
    """Список всех проектов."""
    print(hdr("Проекты"))
    projects = sorted(PROJECTS_DIR.iterdir())
    if not projects:
        print(info("Нет проектов. Создай первый: python cli.py new КОД 'Название'"))
        return

    fmt = f"  {{:<30}} {{:<12}} {{:<8}} {{}}"
    print(C.GRAY + fmt.format("Папка", "Код", "Стадия", "Название") + C.RESET)
    print(C.GRAY + "  " + "─"*70 + C.RESET)

    for d in projects:
        if not d.is_dir():
            continue
        jf = d / "project.json"
        if not jf.exists():
            continue
        try:
            p = json.loads(jf.read_text(encoding="utf-8"))["project"]
            calc = " [✓расчёт]" if (d / "project.json").read_text().__contains__('"calc_done": true') else ""
            print(fmt.format(
                d.name[:30],
                p.get("code","")[:12],
                p.get("stage",""),
                p.get("name","")[:40] + calc
            ))
        except Exception:
            print(f"  {d.name} — ошибка чтения")


def _prompt(label: str, default: str = "", required: bool = False) -> str:
    """Интерактивный ввод одного поля штампа. Enter = оставить default."""
    suffix = f" [{default}]" if default else ""
    while True:
        val = input(f"  {label}{suffix}: ").strip()
        if not val:
            val = default
        if val or not required:
            return val
        print(f"  {C.RED}Обязательное поле — введи значение{C.RESET}")


def _input_stamp(current: dict | None = None) -> dict:
    """
    Интерактивный ввод штампа проекта.
    current — текущие значения (для режима редактирования).
    """
    c = current or {}
    print(f"\n{C.CYAN}Заполни штамп проекта (Enter — оставить текущее):{C.RESET}")
    return {
        "designer":   _prompt("Разработал (ФИО)",      c.get("designer", "")),
        "checker":    _prompt("Проверил (ФИО)",         c.get("checker", "")),
        "norm_head":  _prompt("Н.контроль (ФИО)",       c.get("norm_head", "")),
        "gip":        _prompt("ГИП (ФИО)",              c.get("gip", "")),
        "gap":        _prompt("ГАП (ФИО, необяз.)",     c.get("gap", "")),
        "org":        _prompt("Организация",             c.get("org", "")),
        "city":       _prompt("Город",                   c.get("city", "")),
        "stage":      _prompt("Стадия [Р]",              c.get("stage", "Р")) or "Р",
        "object_type":_prompt("Тип объекта",             c.get("object_type","Общественное здание")),
        "system":     _prompt("Система заземления [TN-S]",c.get("system","TN-S")) or "TN-S",
    }


def cmd_new(args):
    """Создать новый проект из шаблона (с интерактивным вводом штампа)."""
    code = args.code.upper()
    name = args.name

    folder_name = f"{code}_{name[:30].replace(' ','_').replace('/','_')}"
    target = PROJECTS_DIR / folder_name

    if target.exists():
        print(warn(f"Папка уже существует: {target}"))
        return

    target.mkdir()

    stamp = _input_stamp()
    today = str(__import__("datetime").date.today())

    template = {
        "project": {
            "name":        name,
            "code":        code,
            "object_type": stamp["object_type"],
            "stage":       stamp["stage"],
            "voltage_kv":  0.4,
            "system":      stamp["system"],
            "frequency":   50,
            "city":        stamp["city"],
            "designer":    stamp["designer"],
            "checker":     stamp["checker"],
            "norm_head":   stamp["norm_head"],
            "gip":         stamp["gip"],
            "gap":         stamp["gap"],
            "org":         stamp["org"],
            "revision":    0,
            "date":        today,
            "notes":       "",
            "breaker_series": "IEK",
        },
        "building": {
            "floor_height_m": 3.0,
            "floors":         1,
        },
        "vru": {
            "id":   "ВРУ-1",
            "name": "ВРУ-1",
            "bus_current_a": 250,
            "isc_ka": 10,
            "incoming_cable": {
                "mark":       "ВВГнг-LS",
                "cores":      4,
                "section_mm2":None,
                "length_m":   30,
                "install":    "лоток",
                "ambient_t":  25,
                "parallel":   1,
                "cable_routing": {"mode": "reserve_only", "reserve_pct": 20},
            },
            "feeders": [],
        },
        "outdoor_networks": [],
        "extra_items":      [],
        "changes":          [],
        "_meta": {
            "schema_version": "1.1",
            "created":        today,
            "last_modified":  today,
            "calc_done":      False,
        },
    }

    with open(target / "project.json", "w", encoding="utf-8") as f:
        json.dump(template, f, ensure_ascii=False, indent=2)

    for sub in ["docs", "dwg", "templates"]:
        (target / sub).mkdir()

    print(ok(f"Создан проект: {target}"))
    print(info(f"Редактируй: {target / 'project.json'}"))


def cmd_validate(args):
    """Проверка корректности project.json."""
    proj_dir = find_project_dir(args.path)
    project = load_project(proj_dir)

    errors = []
    warnings = []

    for field in ["name", "code", "stage"]:
        if not project.get("project", {}).get(field):
            errors.append(f"project.{field} — не заполнено")

    vru = project.get("vru", {})
    if not vru.get("feeders"):
        warnings.append("vru.feeders — пустой список, добавь группы")

    for feeder in vru.get("feeders", []):
        for panel in feeder.get("panels", []):
            for c in panel.get("consumers", []):
                if not c.get("power_kw"):
                    errors.append(f"  {c.get('id','?')} — нет мощности power_kw")
                if c.get("power_kw", 0) <= 0:
                    errors.append(f"  {c.get('id','?')} — power_kw должна быть > 0")
                if not c.get("cable"):
                    warnings.append(f"  {c.get('id','?')} — нет данных кабеля")

    p_name = project.get("project", {}).get("name", "")
    print(hdr(f"Проверка: {p_name}"))

    if errors:
        for e in errors:
            print(err(e))
    if warnings:
        for w in warnings:
            print(warn(w))
    if not errors and not warnings:
        print(ok("Структура корректна"))
    elif not errors:
        print(ok(f"Ошибок нет, предупреждений: {len(warnings)}"))
    else:
        print(err(f"Ошибок: {len(errors)}, предупреждений: {len(warnings)}"))
        sys.exit(1)


def cmd_calc(args):
    """Полный расчёт ВРУ."""
    from calc.engine import calculate_project

    proj_dir = find_project_dir(args.path)
    project = load_project(proj_dir)

    p_name = project.get("project", {}).get("name", "")
    print(hdr(f"Расчёт: {p_name}"))

    result = calculate_project(project)
    save_project(result, proj_dir)

    s   = result["_results"]["summary"]
    vru = result["_results"]["vru"]

    print(ok("Расчёт завершён"))
    print()
    print(f"  {'Установленная мощность':<30} {s['p_installed_kw']:>8.2f} кВт")
    print(f"  {'Расчётная мощность':<30} {s['p_calc_kw']:>8.2f} кВт")
    print(f"  {'Расчётная полная мощность':<30} {s['s_calc_kva']:>8.2f} кВА")
    print(f"  {'Расчётный cos φ':<30} {s['cos_phi']:>8.3f}")
    print(f"  {'Расчётный ток ВРУ':<30} {s['i_vru_a']:>8.2f} А")

    cable = s.get("incoming_cable", {})
    if cable.get("section_mm2"):
        print(f"  {'Вводной кабель':<30} {cable['mark']} {cable['cores']}×{cable['section_mm2']} мм²")

    breaker = vru.get("breaker", {})
    if breaker.get("rating"):
        print(f"  {'Вводной автомат':<30} АВ {breaker['rating']}А хар.{breaker['char']}")

    print()
    for feeder in vru.get("feeders", []):
        print(f"  {C.CYAN}{feeder['id']} {feeder['name']}{C.RESET}  "
              f"Pр={feeder['p_calc_kw']:.2f}кВт  Iр={feeder['i_calc_a']:.1f}А")
        for panel in feeder.get("panels", []):
            cb  = panel.get("cable", {})
            br  = panel.get("breaker", {})
            sec = cb.get("section_mm2", "?")
            rat = br.get("rating", "?")
            du  = cb.get("voltage_drop_pct", 0)
            du_warn = f" {C.YELLOW}⚠ΔU={du}%{C.RESET}" if du > 5 else f"  ΔU={du}%"
            print(f"    {panel['id']:<8} {panel['name']:<30}  "
                  f"Iр={panel['i_calc_a']:>6.1f}А  "
                  f"кабель {cb.get('mark','?')} {cb.get('cores','?')}×{sec}мм²  "
                  f"АВ {rat}А{du_warn}")

    print()
    print(info(f"Результаты сохранены: {proj_dir / 'project.json'}"))


def cmd_calc_outdoor(args):
    """Расчёт наружных сетей освещения."""
    from outdoor.calc_outdoor import calc_all_outdoor, print_outdoor_report

    proj_dir = find_project_dir(args.path)
    project  = load_project(proj_dir)

    p_name = project.get("project", {}).get("name", "")
    print(hdr(f"Расчёт наружных сетей: {p_name}"))

    if not project.get("outdoor_networks"):
        print(warn("outdoor_networks не заданы в project.json"))
        return

    result = calc_all_outdoor(project)
    save_project(result, proj_dir)

    print_outdoor_report(result)
    print()
    print(info(f"Результаты сохранены: {proj_dir / 'project.json'}"))


def cmd_summary(args):
    """Краткая сводка по рассчитанному проекту."""
    proj_dir = find_project_dir(args.path)
    project  = load_project(proj_dir)

    if not project.get("_results"):
        print(warn("Проект ещё не рассчитан. Запусти: python cli.py calc " + args.path))
        return

    s   = project["_results"]["summary"]
    p   = project["project"]
    vru = project["_results"]["vru"]

    print(hdr(f"{p['code']} — {p['name']}"))
    print(f"  Стадия: {p['stage']}   Ред. {p['revision']}   {p['date']}")
    print(f"  Система: {p['system']}  {p['voltage_kv']} кВ")
    print()
    print(f"  Мощность установленная:  {s['p_installed_kw']:>8.2f} кВт")
    print(f"  Мощность расчётная:      {s['p_calc_kw']:>8.2f} кВт")
    print(f"  Полная мощность:         {s['s_calc_kva']:>8.2f} кВА")
    print(f"  cos φ расчётный:         {s['cos_phi']:>8.3f}")
    print(f"  Ток ВРУ:                 {s['i_vru_a']:>8.2f} А")

    cable = s.get("incoming_cable", {})
    if cable.get("section_mm2"):
        print(f"  Вводной кабель:    {cable['mark']} {cable['cores']}×{cable['section_mm2']} мм²")

    print()
    warnings_found = 0
    for feeder in vru.get("feeders", []):
        for panel in feeder.get("panels", []):
            cb = panel.get("cable", {})
            if cb.get("voltage_drop_pct", 0) > 5.0:
                print(warn(f"  {panel['id']} — потеря напряжения {cb['voltage_drop_pct']}% > 5%"))
                warnings_found += 1
            if not cb.get("ok"):
                print(err(f"  {panel['id']} — {cb.get('error','ошибка подбора кабеля')}"))
            for c in panel.get("consumers", []):
                ccb = c.get("cable", {})
                if ccb.get("voltage_drop_pct", 0) > 5.0:
                    print(warn(f"    {c['id']} — ΔU={ccb['voltage_drop_pct']}%"))
                    warnings_found += 1

    if warnings_found == 0:
        print(ok("Предупреждений нет"))


def cmd_stamp(args):
    """Редактирование штампа проекта с автопересборкой документов."""
    proj_dir = find_project_dir(args.path)
    project  = load_project(proj_dir)
    proj     = project["project"]

    p_name = proj.get("name", "")
    print(hdr(f"Штамп: {p_name}"))

    if args.field and args.value:
        # Одно поле через флаги
        proj[args.field] = args.value
        print(ok(f"{args.field} = {args.value}"))
    else:
        # Интерактивный ввод — текущие значения как дефолт
        stamp = _input_stamp({
            "designer":    proj.get("designer", ""),
            "checker":     proj.get("checker", ""),
            "norm_head":   proj.get("norm_head", ""),
            "gip":         proj.get("gip", ""),
            "gap":         proj.get("gap", ""),
            "org":         proj.get("org", ""),
            "city":        proj.get("city", ""),
            "stage":       proj.get("stage", "Р"),
            "object_type": proj.get("object_type", ""),
            "system":      proj.get("system", "TN-S"),
        })
        for k, v in stamp.items():
            proj[k] = v

    project["project"] = proj
    save_project(project, proj_dir)
    print(ok("Штамп сохранён"))

    # Автоматически пересоздаём документы если они были сгенерированы ранее
    docs_dir = proj_dir / "docs"
    if docs_dir.exists() and any(docs_dir.iterdir()):
        print(info("Пересоздаю документы..."))
        project = _ensure_calc(project, proj_dir)
        fake_args = type("A", (), {"path": str(proj_dir), "type": None})()
        cmd_docs(fake_args)


def cmd_docs(args):
    """Генерация документов."""
    proj_dir = find_project_dir(args.path)
    project  = load_project(proj_dir)
    project  = _ensure_calc(project, proj_dir)

    doc_type = getattr(args, "type", None)
    p_name   = project["project"]["name"]
    print(hdr(f"Генерация документов: {p_name}"))

    docs_dir = proj_dir / "docs"
    docs_dir.mkdir(exist_ok=True)

    def _try_gen(import_path: str, func_name: str, label: str):
        try:
            mod = __import__(import_path, fromlist=[func_name])
            fn  = getattr(mod, func_name)
            path = fn(project, docs_dir)
            print(ok(f"{label}: {path.name}"))
        except ImportError as e:
            print(info(f"{label} — модуль не найден ({e})"))
        except Exception as e:
            print(err(f"{label} — ошибка: {e}"))

    if doc_type in (None, "spec"):
        _try_gen("docs.gen_spec",         "generate_spec",         "Спецификация")
    if doc_type in (None, "cable"):
        _try_gen("docs.gen_cable_journal","generate_cable_journal","Кабельный журнал")
    if doc_type in (None, "load"):
        from docs.gen_load_tables import generate_all_load_tables
        files = generate_all_load_tables(project, docs_dir)
        for f in files:
            print(ok(f"Ведомость нагрузок: {f.name}"))
    if doc_type in (None, "work"):
        _try_gen("docs.gen_work_list",    "generate_work_list",   "Ведомость работ")
    if doc_type in (None, "pnr"):
        _try_gen("docs.gen_pnr",          "generate_pnr",         "Программа ПНР")

    print()
    print(info(f"Документы: {docs_dir}"))


def cmd_plan(args):
    """Генерация DXF-плана."""
    from dwg.gen_plans import generate_section_plan, generate_summary_plan

    proj_dir = find_project_dir(args.path)
    project  = load_project(proj_dir)
    project  = _ensure_calc(project, proj_dir)

    section  = getattr(args, "section", None)
    p_name   = project["project"]["name"]
    print(hdr(f"Генерация плана: {p_name}"))

    dwg_dir  = proj_dir / "dwg"
    dwg_dir.mkdir(exist_ok=True)

    summary = generate_summary_plan(project, dwg_dir)
    print(ok(f"Сводный план: {summary.name}"))

    section_f = generate_section_plan(project, dwg_dir, section)
    label = f"Раздел {section}" if section else "Полный план"
    print(ok(f"{label}: {section_f.name}"))

    print()
    print(info(f"Чертежи: {dwg_dir}"))


def cmd_check_selectivity(args):
    """Проверка селективности автоматов."""
    from rules.selectivity import check_selectivity, print_selectivity_report

    proj_dir = find_project_dir(args.path)
    project  = load_project(proj_dir)
    project  = _ensure_calc(project, proj_dir)

    p_name = project["project"]["name"]
    print(hdr(f"Селективность: {p_name}"))

    results = check_selectivity(project)
    print_selectivity_report(results)

    violations = [r for r in results if not r["ok"]]
    errors_    = [r for r in violations if r["severity"] == "error"]
    if errors_:
        sys.exit(1)


def cmd_check_compensation(args):
    """Проверка необходимости КРМ."""
    from calc.compensation import check_compensation_needed, print_compensation_report, update_compensation

    proj_dir = find_project_dir(args.path)
    project  = load_project(proj_dir)
    project  = _ensure_calc(project, proj_dir)

    p_name = project["project"]["name"]
    print(hdr(f"КРМ: {p_name}"))

    result  = check_compensation_needed(project)
    print_compensation_report(result)

    # Сохраняем результат КРМ в project
    project = update_compensation(project)
    save_project(project, proj_dir)


def cmd_import(args):
    """Импорт потребителей из DXF или таблицы Excel."""
    proj_dir = find_project_dir(args.path)
    project  = load_project(proj_dir)

    source     = args.source       # "dwg" или "table"
    file_path  = Path(args.file)
    section    = getattr(args, "section", "ТХ")

    p_name = project["project"]["name"]
    print(hdr(f"Импорт ({source}): {p_name}"))

    if not file_path.exists():
        print(err(f"Файл не найден: {file_path}"))
        sys.exit(1)

    # 1. Парсинг
    if source == "dwg":
        from parsers.parse_dwg_assignment import parse_dwg_assignment
        new_consumers = parse_dwg_assignment(file_path, section_code=section)
    elif source == "table":
        from parsers.parse_load_table import parse_load_table
        new_consumers = parse_load_table(file_path, section_code=section)
    else:
        print(err(f"Неизвестный тип источника: {source}. Используй 'dwg' или 'table'"))
        sys.exit(1)

    if not new_consumers:
        print(warn("Потребители не найдены в файле"))
        return

    print(info(f"Найдено {len(new_consumers)} потребителей в разделе {section}"))

    # 2. Показываем что нашли
    for c in new_consumers[:10]:
        reserve_mark = " [резерв]" if c.get("reserve") else ""
        print(f"  {c['id']:<10} {c['name'][:35]:<35} "
              f"P={c.get('power_kw',0):.2f}кВт  кат.{c.get('category_pue',3)}{reserve_mark}")
    if len(new_consumers) > 10:
        print(f"  ... и ещё {len(new_consumers)-10} потребителей")

    # 3. Формируем щиты
    from panels.auto_panels import auto_assign_panels

    # Существующие щиты из первого фидера (или создаём фидер)
    vru = project.setdefault("vru", {})
    feeders = vru.setdefault("feeders", [])

    # Ищем фидер с нужным разделом или создаём
    target_feeder = None
    for f in feeders:
        if f.get("section") == section:
            target_feeder = f
            break
    if target_feeder is None:
        target_feeder = {
            "id":      f"Ф-{section}",
            "name":    f"Группа {section}",
            "section": section,
            "panels":  []
        }
        feeders.append(target_feeder)

    existing_panels = target_feeder.get("panels", [])
    updated_panels  = auto_assign_panels(new_consumers, existing_panels)

    # Подсчёт новых
    existing_ids = {c["id"] for p in existing_panels for c in p.get("consumers", [])}
    new_count    = sum(1 for p in updated_panels
                       for c in p.get("consumers", []) if c["id"] not in existing_ids)

    target_feeder["panels"] = updated_panels

    save_project(project, proj_dir)

    print()
    print(ok(f"Добавлено новых потребителей: {new_count}"))
    print(ok(f"Щитов сформировано: {len(updated_panels)}"))
    print(info(f"Запусти расчёт: python cli.py calc {args.path}"))


# ── ТОЧКА ВХОДА ───────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Система автоматизации электропроектирования",
        formatter_class=argparse.RawTextHelpFormatter
    )
    sub = parser.add_subparsers(dest="command")

    # list
    sub.add_parser("list", help="Список всех проектов")

    # new
    p_new = sub.add_parser("new", help="Создать новый проект")
    p_new.add_argument("code", help="Код объекта, напр. ОБЪ-2025-001")
    p_new.add_argument("name", help="Название объекта")

    # calc
    p_calc = sub.add_parser("calc", help="Рассчитать нагрузки ВРУ")
    p_calc.add_argument("path", help="Путь к папке проекта или код")

    # calc-outdoor
    p_co = sub.add_parser("calc-outdoor", help="Рассчитать наружные сети")
    p_co.add_argument("path", help="Путь к папке проекта или код")

    # summary
    p_sum = sub.add_parser("summary", help="Краткая сводка результатов")
    p_sum.add_argument("path", help="Путь к папке проекта или код")

    # validate
    p_val = sub.add_parser("validate", help="Проверить структуру JSON")
    p_val.add_argument("path", help="Путь к папке проекта или код")

    # docs
    p_docs = sub.add_parser("docs", help="Сгенерировать документы")
    p_docs.add_argument("path", help="Путь к папке проекта или код")
    p_docs.add_argument("--type", choices=["spec","cable","load","work","pnr"],
                         help="Тип документа (по умолчанию — все)")

    # plan
    p_plan = sub.add_parser("plan", help="Сгенерировать DXF-план")
    p_plan.add_argument("path", help="Путь к папке проекта или код")
    p_plan.add_argument("--section", help="Раздел: ОВ, ВК, ТХ, ДУ, ПС, ЭОМ, ЭН")

    # check-selectivity
    p_sel = sub.add_parser("check-selectivity", help="Проверить селективность АВ")
    p_sel.add_argument("path", help="Путь к папке проекта или код")

    # check-compensation
    p_comp = sub.add_parser("check-compensation", help="Проверить необходимость КРМ")
    p_comp.add_argument("path", help="Путь к папке проекта или код")

    # import
    p_imp = sub.add_parser("import", help="Импортировать потребителей из файла")
    p_imp.add_argument("path",    help="Путь к папке проекта или код")
    p_imp.add_argument("source",  choices=["dwg","table"],
                        help="Источник: dwg (DXF-чертёж) или table (Excel/CSV)")
    p_imp.add_argument("file",    help="Путь к файлу")
    p_imp.add_argument("--section", default="ТХ",
                        help="Код раздела (ОВ, ВК, ТХ, ...) [по умолчанию: ТХ]")

    # stamp
    p_stamp = sub.add_parser("stamp", help="Редактировать штамп проекта")
    p_stamp.add_argument("path",    help="Путь к папке проекта или код")
    p_stamp.add_argument("--field", help="Поле для изменения (designer, checker, ...)")
    p_stamp.add_argument("--value", help="Новое значение поля")

    args = parser.parse_args()

    commands = {
        "list":               cmd_list,
        "new":                cmd_new,
        "calc":               cmd_calc,
        "calc-outdoor":       cmd_calc_outdoor,
        "summary":            cmd_summary,
        "validate":           cmd_validate,
        "docs":               cmd_docs,
        "plan":               cmd_plan,
        "check-selectivity":  cmd_check_selectivity,
        "check-compensation": cmd_check_compensation,
        "import":             cmd_import,
        "stamp":              cmd_stamp,
    }

    if args.command in commands:
        commands[args.command](args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
