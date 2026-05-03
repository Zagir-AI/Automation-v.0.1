# CLAUDE.md — инструкции для Claude Code
Это система автоматизации электропроектирования.
При работе с этим проектом следуй правилам ниже.

## Структура проекта
```
elec-system/
  cli.py                  ← главная точка входа
  projects/               ← каждый объект — отдельная папка
    КОД_Название/
      project.json        ← единственный источник истины (schema v1.1)
      docs/               ← сгенерированные Word-документы
      dwg/                ← DXF-чертежи для AutoCAD
  calc/
    engine.py             ← расчётный движок (нагрузки, кабели, автоматы)
    compensation.py       ← расчёт КРМ (компенсация реактивной мощности)
  docs/
    gen_spec.py           ← спецификация ГОСТ 21.110 (5 разделов, IEK-серии)
    gen_cable_journal.py  ← кабельный журнал ГОСТ 21.613 (№КЛ, L план/расч)
    gen_load_tables.py    ← ведомость нагрузок (by_panel / by_section / summary)
    gen_work_list.py      ← ведомость объёмов работ (6 разделов)
    gen_pnr.py            ← программа ПНР (6 фаз, нормативы, исполнитель)
  parsers/
    parse_dwg_assignment.py ← парсинг DXF-заданий смежников (ezdxf)
    parse_load_table.py   ← парсинг таблиц нагрузок Excel/CSV
    parse_estimate.py     ← парсинг сметы и КП в Excel
  panels/
    auto_panels.py        ← автоформирование щитов из списка потребителей
  rules/
    category_rules.py     ← категорийность здания ПУЭ гл.1.2, схема ВРУ
    selectivity.py        ← проверка селективности АВ (коэф. ≥ 1.6)
  outdoor/
    calc_outdoor.py       ← расчёт наружных сетей освещения
  changes/
    detector.py           ← механизм изменений, трапеция ГОСТ
  dwg/
    update_attribs.py     ← синхронизация атрибутов в AutoCAD
    create_test_sld.py    ← создание тестовой однолинейки
    gen_plans.py          ← генерация DXF-планов (section + summary)
    number_cables.py      ← автонумерация кабелей КЛ-{ЩИТ}-{NN}
  data/
    cables/pue_tables.py        ← таблицы допустимых токов ПУЭ
    breakers/breaker_tables.py  ← ряды номиналов, серии АВ, get_breaker_designation()
    demand_factors/sp256_factors.py ← коэффициенты спроса СП 256
    spec_templates.py           ← шаблонные позиции щитов по типу (DIN, шины, реле)
  ui/app.py               ← Streamlit веб-интерфейс
```

## Главный файл данных — project.json (schema v1.1)
Структура: project → vru → feeders[] → panels[] → consumers[]

Дополнительные блоки верхнего уровня:
- `building{}`         — параметры здания: floor_height_m, floors
- `extra_items[]`      — ручные позиции спецификации (mark, name, unit, qty, note)
- `outdoor_networks[]` — наружные сети освещения
- `imports[]`          — история импортов из DXF/Excel
- `cable_numbering{}`  — нумерация кабелей {id → "КЛ-ЩИТ-NN"}
- `compensation{}`     — результат расчёта КРМ
- `_building{}`        — категория здания, схема ВРУ (из rules/category_rules.py)

Результаты расчёта хранятся в `_results` — исходные данные никогда не меняются.
История изменений — в `changes[]`.

### Поля project.project:
- `breaker_series`  — производитель АВ: "IEK" | "Schneider" | "ABB" | "DEKraft" | "TDM"
- `gip`, `gap`, `org`, `city`, `stage` — для штампа документов
- `designer`, `checker`, `norm_head` — подписанты

### Поля кабеля (cable_routing):
```json
"cable_routing": {
  "mode": "reserve_only",   // reserve_only | floor_height | manual
  "reserve_pct": 20,        // запас, %
  "floors_up": 2,           // этажей вверх (только для floor_height)
  "floors_down": 0,
  "extra_m": 2.0,           // дополнительный запас на разделку, м
  "manual_length_m": 45.0   // только для mode=manual
}
```
- `mode=reserve_only` — L = length_m × 1.20 (по умолчанию)
- `mode=floor_height` — L = (length_m + этажи × floor_height_m + extra_m) × 1.20
- `mode=manual`       — L = manual_length_m (запас не добавляется)

## Правила при изменении кода

### Расчётный движок (calc/engine.py):
- Не менять алгоритм без проверки на тестовом объекте
- Нормативные таблицы только в data/ — не хардкодить в engine.py
- Все токи в Амперах, мощности в кВт, длины в метрах
- `effective_cable_length(cable_cfg, building)` — всегда использовать для расчётной длины
- Результат кабеля содержит `length_m_plan`, `length_m_calc`, `routing_note`

### Генераторы документов (docs/):
- Все документы читают из `project["_results"]`
- Никогда не читать из `project["vru"]` напрямую в генераторах
- Длины кабелей брать из `cable["length_m_calc"]` (уже с запасом)
- Обозначения АВ через `get_breaker_designation()` из breaker_tables.py
- Шаблонные позиции щитов через `get_template_items()` из spec_templates.py
- Штамп — единый формат: таблица 5 строк (заголовок + 4 подписанта)
- Формат: ГОСТ 21.110, 21.613, А3/А4

### project.json:
- `section_mm2: null` = автоподбор, число = фиксированное
- `demand_factor` берётся из потребителя; если нет — из data/demand_factors
- `reserve: true` — кабель и АВ подбираются, в нагрузку НЕ включается
- `cable_mark_override` — принудительная марка кабеля
- Кат.1 потребители обязательно в щитах с `has_avr=True` (ЩДУ, ЩПС)
- Новые поля добавлять с дефолтным значением

### DXF/AutoCAD:
- ID_TAG атрибут блока должен совпадать с id в project.json
- Трапеция изменений: layer "CHANGES", только при rev > 0

## Атрибуты DXF блоков (стандарт)
- `ID_TAG`              — id потребителя (= id в project.json)
- `POWER_KW`            — мощность кВт
- `SECTION_TAG`         — раздел (ОВ, ВК, ТХ, ...)
- `RESERVE`             — "1" если резервный агрегат
- `CABLE_MARK_OVERRIDE` — марка кабеля (необязательно)
- `CABLE_NO`            — номер кабеля (заполняет number_cables.py)

## Серии автоматических выключателей (IEK по умолчанию)
| Диапазон | Серия IEK | ГОСТ |
|---|---|---|
| 6–63А   | ВА47-63  | ГОСТ IEC 60898-1 |
| 80–125А | ВА57-35  | ГОСТ Р 50030.2   |
| 160–250А| ВА88-35  | ГОСТ Р 50030.2   |
| 315–630А| ВА88-43  | ГОСТ Р 50030.2   |

Изменить производителя: `project["project"]["breaker_series"] = "Schneider"`

## Тестирование
Тестовый объект: `projects/DEMO-2025-001_Офисный_центр/`

Состав DEMO:
- ЭОМ: ЩО-1 (освещение), ЩС-1 (силовые, ИТ), ЩК-1 (климат)
- ОВ:  ЩОВ-1 (насосы отопления, кат.2; НО-02 — резерв)
- ВК:  ЩВК-1 (вентустановки), ЩДУ-1 (дымоудаление, кат.1, FRLS, АВР)
- НО:  наружное освещение паркинга (ОН-1, L=80м)

После любых изменений в calc/engine.py запускать:
```bash
python cli.py calc projects/DEMO-2025-001_Офисный_центр
python cli.py docs projects/DEMO-2025-001_Офисный_центр
```

### Ожидаемые значения для DEMO (актуальные):
- Pуст = 58.5 кВт  (ЭОМ 28 + ОВ 3 + ВК 9.5 + ЩДУ 7.5 + ВВ 4 резерв не входит)
- Pрасч = 38.5 кВт  (НО-02 и ВДУ-02 — reserve=true, не суммируются)
- cosφ = 0.852
- Iвру = 68.66 А
- Кабель ВРУ: ВВГнг-LS 4×25 мм²
- АВ ВРУ: 80А хар.C
- ЩДУ-1: ВВГнг-FRLS 4×1.5 (кат.1 — огнестойкий)
- КРМ: обязательна, tgφ=0.614, батарея КРМ-0.4-15 (15 кВАр)
- Категория здания: 1 (есть кат.1 потребители в ЩДУ-1)
- НО-1: ВВГнг-LS 4×1.5, L=80м, ΔU=0.8%

### Ожидаемые нарушения селективности (норма для DEMO):
- ЩОВ-1 → НО-01/НО-02: отношение 1.0 (рекомендация: ЩОВ-1 АВ 10А)
- ЩДУ-1 → ВДУ-01/ВДУ-02: отношение 1.0 (рекомендация: ЩДУ-1 АВ 32А)
- ЩК-1  → КД-01: предупреждение (рекомендация: ЩК-1 АВ 32А)

## Команды разработки
```bash
# Расчёт ВРУ
python cli.py calc projects/DEMO-2025-001_Офисный_центр

# Расчёт наружных сетей
python cli.py calc-outdoor projects/DEMO-2025-001_Офисный_центр

# Проверки
python cli.py check-selectivity projects/DEMO-2025-001_Офисный_центр
python cli.py check-compensation projects/DEMO-2025-001_Офисный_центр
python cli.py check-cables projects/DEMO-2025-001_Офисный_центр

# Документы (все / по типу)
python cli.py docs projects/DEMO-2025-001_Офисный_центр
python cli.py docs projects/DEMO-2025-001_Офисный_центр --type spec
python cli.py docs projects/DEMO-2025-001_Офисный_центр --type cable
python cli.py docs projects/DEMO-2025-001_Офисный_центр --type load
python cli.py docs projects/DEMO-2025-001_Офисный_центр --type work
python cli.py docs projects/DEMO-2025-001_Офисный_центр --type pnr

# Штамп (редактирование подписантов)
python cli.py stamp projects/DEMO-2025-001_Офисный_центр
python cli.py stamp projects/DEMO-2025-001_Офисный_центр --field designer --value "Смирнов А.А."

# DXF план
python cli.py plan projects/DEMO-2025-001_Офисный_центр
python cli.py plan projects/DEMO-2025-001_Офисный_центр --section ВК

# Импорт из смежников
python cli.py import projects/DEMO-2025-001_Офисный_центр dwg задание_ОВ.dxf --section ОВ
python cli.py import projects/DEMO-2025-001_Офисный_центр table нагрузки_ВК.xlsx --section ВК

# Новый объект (интерактивный режим — в реальном терминале)
python cli.py new ОБЪ-2025-002 "Школа на ул. Садовой"

# Новый объект неинтерактивно (CI/скрипты, не-TTY) — штамп через флаги
python cli.py new ОБЪ-2025-002 "Школа на ул. Садовой" \
  --designer "Иванов И.И." --checker "Сидоров С.С." \
  --gip "Петров П.П." --org "ООО Электропроект" --city "Москва"

# Список проектов
python cli.py list

# Веб-интерфейс
streamlit run ui/app.py
```
