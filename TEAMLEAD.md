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
Python · argparse CLI (cli.py) · Streamlit UI (ui/app.py)
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

## В очереди
3. Inline-редактор потребителей в tab_data (план готов, промпт ниже)
4. Авто-формирование щитов из DXF (panels/auto_panels.py)
5. Экспорт в смету (parsers/parse_estimate.py)

---

## Архитектурные инварианты (НЕЛЬЗЯ нарушать)

Это самое важное для ревью. Если исполнитель нарушает хоть один — стоп.

### Поток данных — строго однонаправленный:
```
project.json (vru/building/extra_items)
    ↓ calc/engine.py:calculate_project()
project["_results"]         ← ТОЛЬКО engine.py пишет сюда
    ↓
docs/gen_*.py              ← читают ТОЛЬКО _results, никогда не читают vru напрямую
ui/app.py                  ← читает _results для отображения
```

### Конкретные запреты:
- Генераторы docs/ НЕ читают `project["vru"]` напрямую — только `project["_results"]`
- `_results` НЕ пишется из UI, docs, CLI — только из `calculate_project()`
- `changes[]` — append-only, не редактировать существующие записи
- `reserve=true` → кабель и АВ подбираются, но потребитель НЕ входит в суммарную нагрузку
- Кат.1 потребители → только в панелях с `has_avr=True` (ЩДУ, ЩПС)

### Длины кабелей:
```python
# ПРАВИЛЬНО — всегда через effective_cable_length():
from calc.engine import effective_cable_length
l_calc = effective_cable_length(cable_cfg, building)  # с запасом

# НЕПРАВИЛЬНО — напрямую:
l = consumer["cable"]["length_m"]  # план без запаса — ошибка!
```
В _results: `length_m_plan` (план), `length_m_calc` (расчётная, с запасом).
В doc-генераторах брать `cable["length_m_calc"]`.

### Обозначения АВ:
```python
# Всегда через:
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

---

## Публичный API ключевых модулей

### calc/engine.py
| Функция | Назначение |
|---|---|
| `calculate_project(project)` | Главный расчёт → возвращает `_results` |
| `effective_cable_length(cable_cfg, building)` | Расчётная длина с запасом |
| `calc_consumer_current(consumer)` | Ток потребителя, А |
| `select_cable_for_current(cable_cfg, i_calc)` | Подбор сечения кабеля |
| `calc_panel(panel, building, isc_ka)` | Расчёт щита |
| `calc_vru(vru, building)` | Расчёт ВРУ |

### docs/gen_spec.py
| Функция | Назначение |
|---|---|
| `_build_spec_data(project)` | Сбор данных → переиспользовать в xlsx |
| `generate_spec(project, docs_dir)` | → .docx |
| `generate_spec_xlsx(project, docs_dir)` | → .xlsx |

### docs/gen_cable_journal.py
| Функция | Назначение |
|---|---|
| `_collect_cables(project)` | Сбор кабелей → переиспользовать в xlsx |
| `generate_cable_journal(project, docs_dir)` | → .docx |
| `generate_cable_journal_xlsx(project, docs_dir)` | → .xlsx |

### rules/selectivity.py
- `check_selectivity(project)` → список нарушений
- Коэффициент ≥ 1.6 (ПУЭ). При ревью: если исполнитель меняет логику выбора АВ — проверить `RATIO_REQUIRED = 1.6`.

### rules/category_rules.py
- `determine_building_category(project)` → int (1..3)
- `update_building_meta(project)` → обновляет `_building`

### calc/compensation.py
- `check_compensation_needed(project)` → нужна ли КРМ
- `update_compensation(project)` → обновляет `project["compensation"]`

---

## Команды верификации (запускать на DEMO после любых изменений)

```bash
cd /home/user/Automation-v.0.1/elec-system

# Базовый расчёт
python cli.py calc projects/DEMO-2025-001_Офисный_центр

# Проверки
python cli.py check-cables projects/DEMO-2025-001_Офисный_центр
python cli.py check-selectivity projects/DEMO-2025-001_Офисный_центр
python cli.py check-compensation projects/DEMO-2025-001_Офисный_центр

# Документы
python cli.py docs projects/DEMO-2025-001_Офисный_центр
python cli.py docs projects/DEMO-2025-001_Офисный_центр --format xlsx
```

### Эталонные значения DEMO (нарушение = регрессия):
- Pуст = 58.5 кВт, Pрасч = 38.5 кВт, cosφ = 0.852, Iвру = 68.66 А
- Кабель ВРУ: ВВГнг-LS 4×25 мм², АВ ВРУ: 80А хар.C
- Категория здания: 1, КРМ обязательна (15 кВАр)
- 6 нарушений термо-КЗ — это норма для DEMO (isc_ka=3.0)

---

## Известный технический долг

| Файл | Проблема | Приоритет |
|---|---|---|
| gen_spec.py | Неиспользуемый импорт `GradientFill` | Низкий |
| cli.py | Docstring не упоминает `--format` | Низкий |
| ui/app.py | Дублирующая кнопка генерации в шапке (docx) | Средний |

---

## Чеклист аудита кода (после каждой задачи)

**Scope:**
- [ ] Изменены только файлы из задания — не больше
- [ ] Другие вкладки UI / другие CLI-команды не затронуты

**Архитектура:**
- [ ] Генераторы docs/ читают только из `_results`
- [ ] Длины кабелей берутся из `length_m_calc` (не `length_m`)
- [ ] Обозначения АВ через `get_breaker_designation()`
- [ ] `reserve=true` потребители не суммируются в нагрузку

**Код:**
- [ ] Нет неиспользуемых импортов
- [ ] Ключи st.* виджетов уникальны (включают fi и pi)
- [ ] При сохранении data_editor: cable существующих потребителей не стирается
- [ ] freeze_panes явно прописан в xlsx ("A6")
- [ ] Штамп в xlsx — отсутствует

**Git:**
- [ ] Коммит атомарный: feat/fix/chore(scope): описание (ru)
- [ ] Запушено на claude/setup-electrical-automation-wQ5a9

**Тест:**
- [ ] `python cli.py calc DEMO` проходит без ошибок
- [ ] Эталонные значения DEMO совпадают (Pрасч=38.5 кВт, Iвру=68.66А)

---

## Правила ревью планов исполнителя

1. **xlsx freeze_panes** — обязательно явно: `ws.freeze_panes = "A6"`
2. **xlsx штамп** — НЕ делать (рабочий документ, не подписной)
3. **cable при save** — при сохранении data_editor кабель не стирать, merge с существующим
4. **Ключи виджетов** — включают fi (feeder idx) и pi (panel idx)
5. **Scope** — только заявленный файл, не "заодно почищу" остальное
6. **Длины** — всегда `effective_cable_length()`, не `length_m` напрямую
7. **Нормативы** — только в data/, не хардкодить в engine.py

---

## Промпт для задачи #3 — Inline-редактор потребителей

Готов к выдаче исполнителю:

```
Рабочая директория: /home/user/Automation-v.0.1/elec-system
Рабочая ветка: claude/setup-electrical-automation-wQ5a9 (переключись на неё)

КОНТЕКСТ: Система электропроектирования. UI — Streamlit, файл ui/app.py (~541 строк).
Данные: project.json → vru.feeders[].panels[].consumers[]

ЗАДАЧА: В ui/app.py внутри блока `with tab_data:` (строки ~279-309) заменить монолитный
st.text_area на три суб-вкладки через st.tabs([]):

1. "👥 Потребители" — st.data_editor таблица потребителей выбранного щита +
   редактор кабеля выбранного потребителя (st.columns(3)).
   Кнопка "💾 Сохранить потребителей" → project.json → st.rerun().

2. "⚙️ Настройки щитов" — st.dataframe список всех щитов (id, name, floor, длина кабеля).
   Только чтение, без кнопок.

3. "{ } JSON" — перенести сюда ТЕКУЩИЙ КОД без изменений (st.text_area + Сохранить + Проверить).

ТРЕБОВАНИЯ:
- Не трогать другие вкладки (tab_summary, tab_results, tab_cables, tab_changes, tab_docs).
- Не трогать cli.py, gen_spec.py, gen_cable_journal.py.
- st.data_editor с num_rows="dynamic" (строки добавлять и удалять).
- Ключи виджетов включают fi (индекс feeder) и pi (индекс panel).
- При сохранении из data_editor: cable существующих потребителей НЕ стирать.
- Поля потребителя: id, name, type (lighting/power/hvac/it/other),
  power_kw, demand_factor, cos_phi, phases (1-3), start_factor.
- Поля cable: mark, cores, section_mm2 (None если 0), length_m,
  install (лоток/труба/открыто/земля), ambient_t, parallel.

ПОСЛЕ: коммит feat(ui): add structured consumer editor in tab_data + push.
Сначала прочитай весь app.py, особенно блок tab_data и load_project/save_project.
```

---

## Как использовать этот файл

При старте нового диалога тимлида:
```
Прочитай /home/user/Automation-v.0.1/TEAMLEAD.md и продолжи в роли тимлида.
```

После завершения задачи — обновить:
- Переместить задачу из "В очереди" в "Завершённые"
- Добавить новый промпт для следующей задачи
