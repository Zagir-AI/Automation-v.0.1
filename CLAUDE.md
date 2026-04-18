# CLAUDE.md — инструкции для Claude Code
Это система автоматизации электропроектирования.
При работе с этим проектом следуй правилам ниже.
## Структура проекта
```
elec-system/
  cli.py                  ← главная точка входа
  projects/               ← каждый объект — отдельная папка
    КОД_Название/
      project.json        ← единственный источник истины
      docs/               ← сгенерированные Word-документы
      dwg/                ← DXF-чертежи для AutoCAD
  calc/
    engine.py             ← расчётный движок (нагрузки, кабели, автоматы)
  docs/
    gen_spec.py           ← спецификация ГОСТ 21.110
    gen_cable_journal.py  ← кабельный журнал ГОСТ 21.613
    gen_work_list.py      ← ведомость работ + программа ПНР
  parsers/
    parse_estimate.py     ← парсинг сметы и КП в Excel
  changes/
    detector.py           ← механизм изменений, трапеция ГОСТ
  dwg/
    update_attribs.py     ← синхронизация атрибутов в AutoCAD
    create_test_sld.py    ← создание тестовой однолинейки
  data/
    cables/pue_tables.py  ← таблицы допустимых токов ПУЭ
    breakers/breaker_tables.py ← ряды номиналов автоматов
    demand_factors/sp256_factors.py ← коэффициенты спроса СП 256
  ui/app.py               ← Streamlit веб-интерфейс
```
## Главный файл данных — project.json
Структура: project → vru → feeders[] → panels[] → consumers[]
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

## Тестирование
Тестовый объект: projects/DEMO-2025-001_Офисный_центр/
После любых изменений в calc/engine.py запускать:
```bash
python cli.py calc projects/DEMO-2025-001_Офисный_центр
python cli.py docs projects/DEMO-2025-001_Офисный_центр
```
Ожидаемые значения для DEMO:
- Pуст ≈ 28 кВт
- Iвру ≈ 37 А
- кабель ВВГнг-LS 4×10

## Команды разработки
```bash
# Расчёт
python cli.py calc projects/DEMO-2025-001_Офисный_центр

# Документы
python cli.py docs projects/DEMO-2025-001_Офисный_центр

# Новый объект
python cli.py new ОБЪ-2025-002 "Школа на ул. Садовой"

# Веб-интерфейс
streamlit run ui/app.py

# Тестовая однолинейка
python dwg/create_test_sld.py projects/DEMO-2025-001_Офисный_центр
```
