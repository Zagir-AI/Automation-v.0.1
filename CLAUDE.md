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
    gen_spec.py           ← спецификация ГОСТ 21.110
    gen_cable_journal.py  ← кабельный журнал ГОСТ 21.613
    gen_load_tables.py    ← ведомость нагрузок (by_panel / by_section / summary)
    gen_work_list.py      ← ведомость работ + программа ПНР
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
    cables/pue_tables.py  ← таблицы допустимых токов ПУЭ
    breakers/breaker_tables.py ← ряды номиналов автоматов
    demand_factors/sp256_factors.py ← коэффициенты спроса СП 256
  ui/app.py               ← Streamlit веб-интерфейс
```
## Главный файл данных — project.json (schema v1.1)
Структура: project → vru → feeders[] → panels[] → consumers[]
Дополнительные блоки верхнего уровня:
- outdoor_networks[]  — наружные сети освещения
- imports[]           — история импортов из DXF/Excel
- cable_numbering{}   — нумерация кабелей {id → "КЛ-ЩИТ-NN"}
- compensation{}      — результат расчёта КРМ
- _building{}         — категория здания, схема ВРУ (из rules/category_rules.py)
Результаты расчёта хранятся в _results — исходные данные никогда не меняются.
История изменений — в changes[].
## Правила при изменении кода

### Расчётный движок (calc/engine.py):
- Не менять алгоритм без проверки на тестовом объекте
- Нормативные таблицы только в data/ — не хардкодить в engine.py
- Все токи в Амперах, мощности в кВт, длины в метрах

### Генераторы документов (docs/):
- Все документы читают из project["_results"]
- Никогда не читать из project["vru"] напрямую в генераторах
- Формат: ГОСТ 21.110, 21.613, А3/А4

### project.json:
- section_mm2: null = автоподбор, число = фиксированное
- demand_factor берётся из потребителя; если нет — из data/demand_factors
- Новые поля добавлять с дефолтным значением

### DXF/AutoCAD:
- ID_TAG атрибут блока должен совпадать с id в project.json
- Трапеция изменений: layer "CHANGES", только при rev > 0

## Правила — reserve, cable_mark_override
- consumer.reserve=True: потребитель входит в щит, кабель и АВ подбираются,
  но в сумму нагрузки НЕ включается
- consumer.cable_mark_override: принудительная марка кабеля (переопределяет автоподбор)
- Кат.1 потребители обязательно в щитах с has_avr=True (ЩДУ, ЩПС)

## Атрибуты DXF блоков (стандарт)
- ID_TAG:              id потребителя (= id в project.json)
- POWER_KW:            мощность кВт
- SECTION_TAG:         раздел (ОВ, ВК, ТХ, ...)
- RESERVE:             "1" если резервный агрегат
- CABLE_MARK_OVERRIDE: марка кабеля (необязательно)
- CABLE_NO:            номер кабеля (заполняет number_cables.py)

## Тестирование
Тестовый объект: projects/DEMO-2025-001_Офисный_центр/
Состав DEMO: ЭОМ (освещение, силовые, климат) + ОВ (насосы) + ВК (вентиляция, ЩДУ) + наружное освещение

После любых изменений в calc/engine.py запускать:
```bash
python cli.py calc projects/DEMO-2025-001_Офисный_центр
python cli.py docs projects/DEMO-2025-001_Офисный_центр
```

Ожидаемые значения для DEMO (полный состав с ОВ+ВК+ЩДУ):
- Pуст ≈ 58.5 кВт  (ЭОМ 28 + ОВ 3 + ВК 9.5 + ЩДУ 7.5 + ВВ 4 резерв)
- Pрасч ≈ 48.4 кВт
- cosφ ≈ 0.852
- Iвру ≈ 86 А
- Кабель: ВВГнг-LS 4×35
- АВ ВРУ: 100А
- ЩДУ-1: ВВГнг-FRLS (кат.1 — огнестойкий)
- КРМ: обязательна, tgφ=0.614, батарея КРМ-0.4-15
- Категория здания: 1 (есть кат.1 потребители в ЩДУ-1)

## Команды разработки
```bash
# Расчёт ВРУ
python cli.py calc projects/DEMO-2025-001_Офисный_центр

# Расчёт наружных сетей
python cli.py calc-outdoor projects/DEMO-2025-001_Офисный_центр

# Проверки
python cli.py check-selectivity projects/DEMO-2025-001_Офисный_центр
python cli.py check-compensation projects/DEMO-2025-001_Офисный_центр

# Документы (все / только ведомость нагрузок)
python cli.py docs projects/DEMO-2025-001_Офисный_центр
python cli.py docs projects/DEMO-2025-001_Офисный_центр --type load

# DXF план
python cli.py plan projects/DEMO-2025-001_Офисный_центр
python cli.py plan projects/DEMO-2025-001_Офисный_центр --section ВК

# Импорт из смежников
python cli.py import projects/DEMO-2025-001_Офисный_центр dwg задание_ОВ.dxf --section ОВ
python cli.py import projects/DEMO-2025-001_Офисный_центр table нагрузки_ВК.xlsx --section ВК

# Новый объект
python cli.py new ОБЪ-2025-002 "Школа на ул. Садовой"

# Веб-интерфейс
streamlit run ui/app.py
```
