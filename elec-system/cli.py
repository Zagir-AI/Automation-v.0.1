#!/usr/bin/env python3
"""
cli.py — главная точка входа в систему.

Использование:
  python cli.py new <код_объекта> "<название>"     — создать новый проект
  python cli.py calc <путь_к_папке_проекта>        — рассчитать
  python cli.py calc .                             — рассчитать текущую папку
  python cli.py summary <путь>                    — краткая сводка результатов
  python cli.py docs <путь>                       — сгенерировать все документы
  python cli.py validate <путь>                   — проверить корректность JSON
  python cli.py list                              — список всех проектов
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
    # Поиск по коду в папке projects
    for d in PROJECTS_DIR.iterdir():
        if d.is_dir() and arg.upper() in d.name.upper():
            return d
    print(err(f"Проект не найден: {arg}"))
    sys.exit(1)


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


def cmd_new(args):
    """Создать новый проект из шаблона."""
    import shutil
    code = args.code.upper()
    name = args.name

    # Транслитерация для имени папки
    folder_name = f"{code}_{name[:30].replace(' ','_').replace('/','_')}"
    target = PROJECTS_DIR / folder_name

    if target.exists():
        print(warn(f"Папка уже существует: {target}"))
        return

    target.mkdir()

    # Базовый project.json
    template = {
        "project": {
            "name": name,
            "code": code,
            "object_type": "Общественное здание",
            "stage": "Р",
            "voltage_kv": 0.4,
            "system": "TN-S",
            "frequency": 50,
            "city": "",
            "designer": "",
            "checker": "",
            "norm_head": "",
            "revision": 0,
            "date": str(__import__("datetime").date.today()),
            "notes": ""
        },
        "vru": {
            "id": "ВРУ-1",
            "name": "ВРУ-1",
            "bus_current_a": 250,
            "isc_ka": 10,
            "incoming_cable": {
                "mark": "ВВГнг-LS",
                "cores": 4,
                "section_mm2": None,
                "length_m": 30,
                "install": "лоток",
                "ambient_t": 25,
                "parallel": 1
            },
            "feeders": []
        },
        "changes": [],
        "_meta": {
            "schema_version": "1.0",
            "created": str(__import__("datetime").date.today()),
            "last_modified": str(__import__("datetime").date.today()),
            "calc_done": False
        }
    }

    with open(target / "project.json", "w", encoding="utf-8") as f:
        json.dump(template, f, ensure_ascii=False, indent=2)

    # Создаём подпапки
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

    # Обязательные поля
    for field in ["name", "code", "stage"]:
        if not project.get("project", {}).get(field):
            errors.append(f"project.{field} — не заполнено")

    # ВРУ
    vru = project.get("vru", {})
    if not vru.get("feeders"):
        warnings.append("vru.feeders — пустой список, добавь фидеры")

    # Проверяем потребителей
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
    """Полный расчёт проекта."""
    from calc.engine import calculate_project

    proj_dir = find_project_dir(args.path)
    project = load_project(proj_dir)

    p_name = project.get("project", {}).get("name", "")
    print(hdr(f"Расчёт: {p_name}"))

    result = calculate_project(project)
    save_project(result, proj_dir)

    # Вывод сводки
    s = result["_results"]["summary"]
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

    # Детализация по фидерам
    for feeder in vru.get("feeders", []):
        print(f"  {C.CYAN}{feeder['id']} {feeder['name']}{C.RESET}  "
              f"Pр={feeder['p_calc_kw']:.2f}кВт  Iр={feeder['i_calc_a']:.1f}А")
        for panel in feeder.get("panels", []):
            cb = panel.get("cable", {})
            br = panel.get("breaker", {})
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


def cmd_summary(args):
    """Краткая сводка по рассчитанному проекту."""
    proj_dir = find_project_dir(args.path)
    project = load_project(proj_dir)

    if not project.get("_results"):
        print(warn("Проект ещё не рассчитан. Запусти: python cli.py calc " + args.path))
        return

    s = project["_results"]["summary"]
    p = project["project"]
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

    # Предупреждения
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


def cmd_docs(args):
    """Генерация всех документов."""
    proj_dir = find_project_dir(args.path)
    project = load_project(proj_dir)

    if not project.get("_results"):
        print(warn("Нет результатов расчёта. Сначала запусти: python cli.py calc " + args.path))
        print(info("Запускаю расчёт автоматически..."))
        from calc.engine import calculate_project
        project = calculate_project(project)
        save_project(project, proj_dir)

    print(hdr(f"Генерация документов: {project['project']['name']}"))

    docs_dir = proj_dir / "docs"
    docs_dir.mkdir(exist_ok=True)

    # Импортируем генераторы
    try:
        from docs.gen_spec import generate_spec
        path = generate_spec(project, docs_dir)
        print(ok(f"Спецификация: {path.name}"))
    except ImportError:
        print(info("docs/gen_spec.py — будет создан на этапе 3"))

    try:
        from docs.gen_cable_journal import generate_cable_journal
        path = generate_cable_journal(project, docs_dir)
        print(ok(f"Кабельный журнал: {path.name}"))
    except ImportError:
        print(info("docs/gen_cable_journal.py — будет создан на этапе 3"))

    try:
        from docs.gen_work_list import generate_work_list
        path = generate_work_list(project, docs_dir)
        print(ok(f"Ведомость работ: {path.name}"))
    except ImportError:
        print(info("docs/gen_work_list.py — будет создан на этапе 3"))

    try:
        from docs.gen_pnr import generate_pnr
        path = generate_pnr(project, docs_dir)
        print(ok(f"Программа ПНР: {path.name}"))
    except ImportError:
        print(info("docs/gen_pnr.py — будет создан на этапе 3"))

    print()
    print(info(f"Документы: {docs_dir}"))


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
    p_calc = sub.add_parser("calc", help="Рассчитать проект")
    p_calc.add_argument("path", help="Путь к папке проекта или код")

    # summary
    p_sum = sub.add_parser("summary", help="Краткая сводка результатов")
    p_sum.add_argument("path", help="Путь к папке проекта или код")

    # validate
    p_val = sub.add_parser("validate", help="Проверить структуру JSON")
    p_val.add_argument("path", help="Путь к папке проекта или код")

    # docs
    p_docs = sub.add_parser("docs", help="Сгенерировать все документы")
    p_docs.add_argument("path", help="Путь к папке проекта или код")

    args = parser.parse_args()

    commands = {
        "list":     cmd_list,
        "new":      cmd_new,
        "calc":     cmd_calc,
        "summary":  cmd_summary,
        "validate": cmd_validate,
        "docs":     cmd_docs,
    }

    if args.command in commands:
        commands[args.command](args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
