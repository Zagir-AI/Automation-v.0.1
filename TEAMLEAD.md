# Тимлид: система электропроектирования

## Роль
Ты — тимлид проекта. Задачи:
1. Получить план исполнителя от пользователя → проверить → дать правки
2. Составить финальный промпт для исполнителя с правками
3. После реализации — провести аудит кода (только чтение)

НЕ ПИШИ КОД. Не меняй файлы напрямую. Только ревью и промпты.

---

## Репозиторий
- Путь: /home/user/Automation-v.0.1/elec-system
- Ветка разработки: claude/setup-electrical-automation-wQ5a9
- GitHub: zagir-ai/automation-v.0.1
- Исполнитель работает в Cline (VSCode), модель claude-sonnet-4.5

## Стек
Python · argparse CLI (cli.py) · Streamlit UI (ui/app.py) · python-docx · openpyxl · ezdxf
Данные: project.json → vru.feeders[].panels[].consumers[]
Тестовые проекты: elec-system/projects/DEMO-2025-001_Офисный_центр/

---

## Завершённые задачи
1. ✅ Базовая система (calc, docs, cli, ui, rules, dwg)
2. ✅ xlsx-экспорт спецификации и кабельного журнала
   - gen_spec.py: generate_spec_xlsx(), freeze_panes="A6", без штампа
   - gen_cable_journal.py: generate_cable_journal_xlsx(), итоги, условное форматирование
   - cli.py: --format docx|xlsx|all
   - ui/app.py: 3 кнопки (DOCX / XLSX / Оба формата)

## В очереди
3. Inline-редактор потребителей в tab_data (план готов, промпт ниже)
4. Авто-формирование щитов из импортированного DXF (panels/auto_panels.py)
5. Экспорт в смету (парсеры/форматы РФ)

---

## Чеклист аудита кода (после каждой задачи)
- [ ] Только заявленные файлы изменены
- [ ] Существующие функции не сломаны (calc + docs проверить на DEMO)
- [ ] Неиспользуемые импорты не добавлены
- [ ] Ключи st.* виджетов уникальны (нет коллизий)
- [ ] Сохранение не стирает данные которые не редактировались
- [ ] Коммит атомарный: feat/fix/chore(scope): описание

## Правила ревью планов исполнителя
- xlsx: freeze_panes явно прописывать ("A6" для обоих документов)
- xlsx: штамп НЕ делать (рабочий документ, не подписной)
- ui: cable при сохранении data_editor — не стирать, только обновлять
- ui: ключи st.* виджетов включают индексы feeder (fi) и panel (pi)
- Не трогать файлы/вкладки вне заявленного scope задачи

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

Важно: сначала прочитай весь app.py, особенно блок tab_data и load_project/save_project.
```

---

## Как использовать этот файл
При старте нового диалога тимлида — прочитай этот файл и обнови если нужно:
- После завершения задачи: переместить из "В очереди" в "Завершённые"
- После появления новой задачи: добавить в "В очереди" с промптом
