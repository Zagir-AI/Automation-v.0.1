# Тимлид: система электропроектирования

## Роль
Ты — тимлид проекта. Задачи:
1. Получить план исполнителя от пользователя → проверить → дать правки
2. Составить финальный промпт для исполнителя с правками
3. После реализации — провести аудит кода (только чтение)

НЕ ПИШИ КОД. Не меняй файлы напрямую. Только ревью и промпты.

---

## Репозиторий
- Локальный путь: /home/user/Automation-v.0.1/elec-system
- Ветка разработки: claude/setup-electrical-automation-wQ5a9
- GitHub: zagir-ai/automation-v.0.1
- Исполнитель: Cline в VSCode, модель claude-sonnet-4.5
- Тестовый проект: elec-system/projects/DEMO-2025-001_Офисный_центр/

## Стек
Python · argparse CLI (cli.py) · Streamlit UI (ui/app.py, ~917 строк)
python-docx · openpyxl · ezdxf
Данные: project.json → vru.feeders[].panels[].consumers[]

---

## Завершённые задачи
1. ✅ Базовая система (calc, docs, cli, ui, rules, dwg)
2. ✅ xlsx-экспорт спецификации и кабельного журнала
   - gen_spec.py: generate_spec_xlsx(), freeze_panes="A6", без штампа
   - gen_cable_journal.py: generate_cable_journal_xlsx(), итоги, условное форм.
   - cli.py: --format docx|xlsx|all
   - ui/app.py: 3 кнопки (DOCX / XLSX / Оба формата)
3. ✅ Inline-редактор потребителей (tab_data → 3 суб-вкладки)
   - "👥 Потребители": st.data_editor + редактор кабеля, num_rows="dynamic"
   - "⚙️ Настройки щитов": read-only dataframe
   - "{ } JSON": исходный редактор без изменений
4. ✅ Авто-формирование щитов после DWG-импорта (cli.py:cmd_import)
   - auto_assign_panels() вызывается после парсинга DXF
   - Feeder ищется по полю "section"; если нет — создаётся с id=section
   - Идемпотентен: повторный импорт не дублирует потребителей
5. ✅ Сверка спецификации с КП поставщика
   - parsers/compare_kp.py: compare_kp(project, kp_path) → list[dict]
   - cli.py: compare-kp <path> <kp_file> [--xlsx]
   - Статусы: found / not_found / extra_in_kp; xlsx с цветовой индикацией

5. ✅ Сверка спецификации с КП поставщика (дублировано выше — см. п.5)
6. ✅ Редизайн UI — MVP (sidebar-навигация + admin-блок)
   - Ветка: `claude/ui-redesign-mvp-XR05M`, коммит `feat(ui): sidebar section nav + admin settings page`
   - ui/app.py: ~917 строк после редизайна
   - Sidebar: динамические разделы из `feeders[].section`, фильтрация вкладок Данные/Результаты/Кабели
   - Admin: страница "⚙️ Настройки проекта" — 3 expander (Свойства / Исполнители / Тех.параметры)
   - Регрессия DEMO: Pуст=58.5кВт Iвру=68.66А cosφ=0.852 ✅
   - Тех.долг: двойная загрузка project.json (sidebar + main), isc_ka в двух местах
   - ROADMAP.md создан на ветке `claude/ui-redesign-mvp-XR05M`

## В очереди
7. (следующая задача — из ROADMAP.md)

---

## Архитектурные инварианты (НЕЛЬЗЯ нарушать)

Если исполнитель нарушает хоть один — немедленный стоп.

### Поток данных — строго однонаправленный:
```
project.json (vru / building / extra_items / outdoor_networks)
    ↓ calc/engine.py:calculate_project()
project["_results"]         ← ТОЛЬКО engine.py пишет сюда
    ↓
docs/gen_*.py              ← читают ТОЛЬКО _results, никогда не читают vru напрямую
ui/app.py (tab_results)    ← читает _results для отображения
```

### Конкретные запреты:
- Генераторы docs/ НЕ читают `project["vru"]` напрямую — только `project["_results"]`
- `_results` НЕ пишется из UI, docs, CLI — только из `calculate_project()`
- `changes[]` — append-only, не редактировать существующие записи
- `reserve=true` → кабель и АВ подбираются, но потребитель НЕ входит в суммарную нагрузку
- Кат.1 потребители → только в панелях с `has_avr=True` (ЩДУ, ЩПС и аналоги)
- Нормативные таблицы → только в `data/`, не хардкодить в engine.py

### Марка кабеля — автовыбор по категории:
```python
# data/cables/pue_tables.py — таблица (install, material, category_pue) → марка
# кат.1 + любая прокладка (кроме земли) → ВВГнг-FRLS  (огнестойкий)
# кат.2/3                                → ВВГнг-LS
# алюминий                               → АВВГнг-LS
```
При ревью: если исполнитель меняет логику выбора марки — проверить эту таблицу.

### Длины кабелей:
```python
# ПРАВИЛЬНО:
from calc.engine import effective_cable_length
l_calc = effective_cable_length(cable_cfg, building)  # с запасом

# НЕПРАВИЛЬНО:
l = consumer["cable"]["length_m"]  # план без запаса!
```
В `_results`: `length_m_plan` (план), `length_m_calc` (расчётная с запасом).
В doc-генераторах: всегда `cable["length_m_calc"]`.

### Обозначения АВ:
```python
from data.breakers.breaker_tables import get_breaker_designation
des = get_breaker_designation(rating, char="C", poles=3, series_brand="IEK")
# → {"type": "ВА47-63", "rating": 16, "char": "C", ...}
```

### Шаблонные позиции щитов в спецификации:
```python
from data.spec_templates import get_template_items
items = get_template_items(panel_type, n_consumers, n_breakers)
# panel_type: "din_rail", "power", "avr", "hvac", ...
```

### Наружные сети — отдельный расчётный поток:
```python
# outdoor_networks[] в project.json — НЕ входит в vru
# Расчёт: outdoor/calc_outdoor.py:calc_all_outdoor(project)
# Результат: project["_results"]["outdoor_networks"]
# CLI: python cli.py calc-outdoor <путь>
```
Не смешивать с основным расчётом ВРУ.

---

## Автоформирование щитов (panels/auto_panels.py) — для задачи #4

Раздел DXF-задания → префикс щита:
```python
_SECTION_TO_PANEL_PREFIX = {
    "ОВ": "ЩОВ",  "ВК": "ЩВК",  "КВ": "ЩКВ",
    "ТХ": "ЩТХ",  "ЭОМ": "ЩС",  "ЭН": "ШУНО",
}
```
Специальные щиты (кат.1):
- ЩДУ → дымоудаление, `has_avr=True`, `category_pue=1`
- ЩПС → пожаротушение, `has_avr=True`, `category_pue=1`

Метаданные щитов: `_PANEL_META` — имя, тип, категория, АВР.
Идемпотентность: повторный вызов добавляет новых потребителей, не перезаписывает существующих.

DXF атрибуты блоков → потребители: `parse_dwg_assignment.py`
- `ID_TAG` → `id` в project.json
- `POWER_KW` → `power_kw`
- `SECTION_TAG` → раздел (ОВ, ВК, ТХ...)
- `RESERVE` → `reserve=true` если "1"
- `CABLE_MARK_OVERRIDE` → принудительная марка

---

## Публичный API ключевых модулей

### calc/engine.py
| Функция | Назначение |
|---|---|
| `calculate_project(project)` | Главный расчёт → `_results` |
| `effective_cable_length(cable_cfg, building)` | Расчётная длина с запасом |
| `calc_consumer_current(consumer)` | Ток потребителя, А |
| `select_cable_for_current(cable_cfg, i_calc)` | Подбор сечения |
| `calc_panel(panel, building, isc_ka)` | Расчёт щита |
| `calc_vru(vru, building)` | Расчёт ВРУ |

### outdoor/calc_outdoor.py
| Функция | Назначение |
|---|---|
| `calc_outdoor_network(network)` | Расчёт одной наружной сети |
| `calc_all_outdoor(project)` | Все наружные сети → `_results` |

### docs/ — все генераторы
| Модуль | docx | xlsx | Данные-источник |
|---|---|---|---|
| gen_spec.py | `generate_spec()` | `generate_spec_xlsx()` | `_build_spec_data()` |
| gen_cable_journal.py | `generate_cable_journal()` | `generate_cable_journal_xlsx()` | `_collect_cables()` |
| gen_load_tables.py | `generate_load_table()` | — | `_results` |
| gen_work_list.py | `generate_work_list()` | — | `_results` |
| gen_pnr.py | `generate_pnr()` | — | `_results` |

### rules/
| Модуль | Ключевая функция |
|---|---|
| selectivity.py | `check_selectivity(project)` → нарушения, коэф. ≥ 1.6 |
| category_rules.py | `determine_building_category(project)` → int 1..3 |
| category_rules.py | `update_building_meta(project)` → `_building` |

### calc/compensation.py
- `check_compensation_needed(project)` → нужна ли КРМ
- `update_compensation(project)` → обновляет `project["compensation"]`

### panels/auto_panels.py
- `auto_assign_panels(consumers, existing_panels)` → структура panels[]
- Идемпотентен: безопасно вызывать повторно

### dwg/
| Функция | Назначение |
|---|---|
| `generate_section_plan(project, output_dir, section)` | DXF-план раздела |
| `generate_summary_plan(project, output_dir)` | Сводный DXF-план |
| `update_attribs(project, dxf_path)` | Синхронизировать атрибуты project → DXF |
| `update_cable_numbering(project, dxf_path)` | Записать номера КЛ в DXF блоки |
| `add_changes_trapezoid(project, dxf_path)` | Трапеция изменений (rev > 0) |

### data/ — нормативные таблицы (только читать, не трогать)
- `pue_tables.py` — допустимые токи, (install, material, category_pue) → марка кабеля
- `breaker_tables.py` — ряды номиналов АВ, 5 производителей
- `sp256_factors.py` — коэффициенты спроса по типу потребителя (kс, cos_phi по умолчанию)
- `spec_templates.py` — шаблонные позиции DIN-рейки, шин, реле для спецификации

---

## Структура UI (ui/app.py, 731 строка)

Вкладки: `tab_summary | tab_data | tab_results | tab_cables | tab_changes | tab_docs`

| Вкладка | Что показывает | Пишет в файл? |
|---|---|---|
| Сводка | Метрики ВРУ, таблица щитов | Нет |
| Данные | Потребители / Щиты / JSON | Да (save_project) |
| Расчёт | Подробные результаты по потребителям | Нет |
| Кабели | ΔU > 5%, термо-КЗ, чувствительность | Нет |
| Изменения | История ревизий (changes[]) | Нет |
| Документы | Генерация docx/xlsx, скачивание | Нет (через CLI) |

Функции-утилиты в app.py:
- `load_project(proj_dir)` → dict
- `save_project(project, proj_dir)` → None
- `run_cli(command_list)` → (stdout, stderr, returncode)

---

## Команды верификации (запускать на DEMO после любых изменений)

```bash
cd /home/user/Automation-v.0.1/elec-system

python cli.py calc          projects/DEMO-2025-001_Офисный_центр
python cli.py calc-outdoor  projects/DEMO-2025-001_Офисный_центр
python cli.py check-cables  projects/DEMO-2025-001_Офисный_центр
python cli.py check-selectivity projects/DEMO-2025-001_Офисный_центр
python cli.py check-compensation projects/DEMO-2025-001_Офисный_центр
python cli.py docs          projects/DEMO-2025-001_Офисный_центр --format all
```

### Эталонные значения DEMO (нарушение = регрессия):
- Pуст = 58.5 кВт, Pрасч = 38.5 кВт, cosφ = 0.852, Iвру = 68.66 А
- Кабель ВРУ: ВВГнг-LS 4×25 мм², АВ ВРУ: 80А хар.C
- Категория здания: 1, КРМ обязательна (15 кВАр)
- 6 нарушений термо-КЗ — норма для DEMO (isc_ka=3.0)

---

## Известный технический долг

| Файл | Проблема | Приоритет |
|---|---|---|
| gen_spec.py | Неиспользуемый импорт `GradientFill` | Низкий |
| cli.py | Docstring не упоминает `--format` | Низкий |
| ui/app.py | `import pandas as pd` внутри tab_data вместо шапки | Низкий |
| ui/app.py | Дублирующая кнопка генерации DOCX в шапке | Средний |

---

## Чеклист аудита кода (после каждой задачи)

**Scope:**
- [ ] Изменены только файлы из задания
- [ ] Другие вкладки UI / CLI-команды не затронуты

**Архитектура:**
- [ ] Генераторы docs/ читают только `_results`
- [ ] Длины кабелей берутся из `length_m_calc`
- [ ] Марка кабеля: кат.1 → FRLS, кат.2/3 → LS (через pue_tables)
- [ ] Обозначения АВ через `get_breaker_designation()`
- [ ] `reserve=true` потребители не суммируются в нагрузку
- [ ] Нормативы только в data/, не в engine.py

**Код:**
- [ ] Нет неиспользуемых импортов
- [ ] Ключи st.* виджетов уникальны (fi + pi)
- [ ] cable при сохранении data_editor не стирается
- [ ] freeze_panes = "A6" в xlsx (если задача xlsx)
- [ ] Штамп в xlsx отсутствует (если задача xlsx)

**Git:**
- [ ] Коммит атомарный: feat/fix/chore(scope): описание
- [ ] Запушено на claude/setup-electrical-automation-wQ5a9

**Тест:**
- [ ] `python cli.py calc DEMO` без ошибок
- [ ] Pрасч = 38.5 кВт, Iвру = 68.66 А (эталон не сломан)

---

## Правила ревью планов исполнителя

1. **xlsx freeze_panes** — явно: `ws.freeze_panes = "A6"`
2. **xlsx штамп** — НЕ делать
3. **cable при save** — merge с существующим, не перезаписывать целиком
4. **Ключи виджетов** — включают fi и pi
5. **Scope** — только заявленный файл
6. **Длины** — `effective_cable_length()`, не `length_m` напрямую
7. **Нормативы** — только в data/
8. **auto_panels идемпотентность** — повторный вызов не должен ломать существующих потребителей
9. **DXF атрибуты** — ID_TAG обязателен и должен совпадать с id в project.json

---

## Промпт для задачи #4 — Авто-формирование щитов из DXF

```
Рабочая директория: /home/user/Automation-v.0.1/elec-system
Рабочая ветка: claude/setup-electrical-automation-wQ5a9

КОНТЕКСТ: Система электропроектирования. Команда `python cli.py import <путь> dwg <файл.dxf>`
парсит DXF задание смежника через parsers/parse_dwg_assignment.py и возвращает список
потребителей. Модуль panels/auto_panels.py:auto_assign_panels() формирует из них
структуру panels[] для project.json.

Сейчас после `cli.py import dwg` потребители добавляются в project.json, но щиты
НЕ создаются автоматически — инженер должен вручную добавить panels[] в JSON.

ЗАДАЧА: После импорта DXF (cmd_import в cli.py) автоматически вызывать
auto_assign_panels() и добавлять сформированные щиты в project["vru"]["feeders"].

ТРЕБОВАНИЯ:
1. В cmd_import (cli.py): после записи импортированных потребителей вызвать
   auto_assign_panels(new_consumers, existing_panels) и добавить новые щиты
   в соответствующий feeder project["vru"]["feeders"].
2. Существующие щиты и потребители НЕ затирать (auto_assign_panels идемпотентен).
3. Раздел DXF → prefixes: ОВ→ЩОВ, ВК→ЩВК, КВ→ЩКВ, ТХ→ЩТХ, ЭОМ→ЩС, ЭН→ШУНО.
4. Кат.1 потребители → ЩДУ (дымоудаление) или ЩПС (пожаротушение), has_avr=True.
5. Новые щиты добавлять в feeder по разделу. Если feeder с нужным разделом не существует
   — создать новый feeder с id=section и добавить в vru.feeders[].
6. Не трогать calc, docs, ui/app.py.

ПОСЛЕ: коммит feat(cli): auto-create panels after dwg import + push.
Сначала прочитай cmd_import в cli.py и весь panels/auto_panels.py.
```

---

## Как использовать этот файл

При старте нового диалога тимлида:
```
Прочитай /home/user/Automation-v.0.1/TEAMLEAD.md и продолжи в роли тимлида.
```

После завершения задачи:
- Перенести из "В очереди" в "Завершённые"
- Обновить промпт для следующей задачи
