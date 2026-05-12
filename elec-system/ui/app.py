"""
ui/app.py — веб-интерфейс системы.

Запуск:
  cd elec-system
  streamlit run ui/app.py

Функции:
  - Список всех объектов с кратким статусом
  - Открытие проекта: просмотр и редактирование данных
  - Кнопка "Пересчитать всё" — запускает calc + docs
  - Просмотр результатов расчёта
  - Загрузка и парсинг сметы / КП
"""

import re
import sys
import json
import subprocess
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

PROJECTS_DIR = ROOT / "projects"

# ── Конфигурация страницы ────────────────────────────────────────────

st.set_page_config(
    page_title="ЭлектроПроект",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Проверяем доступность папки проектов сразу при старте
try:
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    _test_file = PROJECTS_DIR / ".write_test"
    _test_file.touch()
    _test_file.unlink()
except Exception as _dir_err:
    st.error(
        f"Нет доступа к папке проектов: `{PROJECTS_DIR}`\n\n"
        f"Ошибка: {_dir_err}\n\n"
        "Убедись, что у текущего пользователя есть права на запись в эту папку."
    )
    st.stop()

# ── Вспомогательные функции ──────────────────────────────────────────

def load_project(proj_dir: Path) -> dict:
    jf = proj_dir / "project.json"
    if jf.exists():
        return json.loads(jf.read_text(encoding="utf-8"))
    return {}

def save_project(project: dict, proj_dir: Path):
    jf = proj_dir / "project.json"
    jf.write_text(json.dumps(project, ensure_ascii=False, indent=2), encoding="utf-8")

def get_all_projects() -> list:
    result = []
    if not PROJECTS_DIR.exists():
        return result
    for d in sorted(PROJECTS_DIR.iterdir()):
        if not d.is_dir():
            continue
        p = load_project(d)
        if p:
            result.append((d, p))
    return result

def run_cli(command: list) -> tuple[str, str, int]:
    """Запустить CLI-команду, вернуть stdout, stderr, returncode."""
    proc = subprocess.run(
        [sys.executable, str(ROOT / "cli.py")] + command,
        capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(ROOT)
    )
    # Убираем ANSI-коды
    import re
    ansi = re.compile(r"\033\[[0-9;]*m")
    return ansi.sub("", proc.stdout), ansi.sub("", proc.stderr), proc.returncode


# ── Сайдбар ──────────────────────────────────────────────────────────

projects = get_all_projects()


def _filter_feeders(feeders: list, section: str | None) -> list:
    """Фильтрует фидеры по разделу; None / 'Все' — возвращает все."""
    if not section or section == "Все":
        return feeders
    return [f for f in feeders if f.get("section") == section]


with st.sidebar:
    st.title("⚡ ЭлектроПроект")
    st.divider()

    _sb_active = st.session_state.get("active_project")

    if _sb_active:
        # Проект открыт — навигация по разделам
        _sb_proj = load_project(Path(_sb_active))
        _sb_info = _sb_proj.get("project", {})
        st.markdown(f"**{_sb_info.get('code', '')}**")
        st.caption(_sb_info.get("name", "")[:45])
        st.divider()

        _sections = ["Все"]
        for _f in _sb_proj.get("vru", {}).get("feeders", []):
            _sec = _f.get("section", "")
            if _sec and _sec not in _sections:
                _sections.append(_sec)

        _cur_sec = st.session_state.get("active_section", "Все")
        if _cur_sec not in _sections:
            _cur_sec = "Все"

        st.caption("Раздел проекта")
        for _sec_opt in _sections:
            _is_active = _cur_sec == _sec_opt
            if st.button(
                f"{'▶ ' if _is_active else ''}{_sec_opt}",
                key=f"sec_btn_{_sec_opt}",
                type="primary" if _is_active else "secondary",
                use_container_width=True,
            ):
                if not _is_active:
                    st.session_state["active_section"] = _sec_opt
                    st.rerun()
    else:
        # Дашборд — список проектов
        st.subheader(f"Объекты ({len(projects)})")
        for d, p in projects:
            proj_info = p.get("project", {})
            _calc = p.get("_meta", {}).get("calc_done", False)
            icon = "✅" if _calc else "🔲"
            label = f"{icon} **{proj_info.get('code','?')}** {proj_info.get('name','')[:25]}"
            if st.button(label, key=str(d), use_container_width=True):
                st.session_state["active_project"] = str(d)
                st.session_state["active_section"] = "Все"
                st.rerun()

        st.divider()
        if st.button("➕ Новый объект", use_container_width=True):
            st.session_state["show_new_form"] = True


# ── Новый проект ────────────────────────────────────────────────────

if st.session_state.get("show_new_form"):
    st.header("Новый объект")
    col1, col2 = st.columns(2)
    with col1:
        new_code = st.text_input("Код объекта", placeholder="ОБЪ-2025-001")
    with col2:
        new_name = st.text_input("Название", placeholder="Офисное здание по ул. Ленина")

    btn_col1, btn_col2 = st.columns([1, 4])
    with btn_col1:
        if st.button("← Назад", use_container_width=True):
            st.session_state["show_new_form"] = False
            st.rerun()
    with btn_col2:
        if st.button("Создать", type="primary", use_container_width=True):
            if new_code and new_name:
                if not re.match(r'^[А-ЯA-Z0-9\-]{3,20}$', new_code.strip()):
                    st.error("Код объекта: только буквы (А-Я, A-Z), цифры и «-», от 3 до 20 символов.")
                else:
                    out, err, rc = run_cli(["new", new_code.strip(), new_name.strip()])
                    if rc == 0:
                        st.success(f"Создан: {new_code}")
                        st.session_state["show_new_form"] = False
                        st.rerun()
                    else:
                        st.error(f"Ошибка: {err}")
            else:
                st.warning("Заполни код и название")
    st.stop()


# ── Главный экран ───────────────────────────────────────────────────

active_path = st.session_state.get("active_project")

if not active_path:
    st.title("⚡ ЭлектроПроект")
    st.caption("Система автоматизации проектной документации по электроснабжению")
    st.divider()

    if not projects:
        st.info("Нет объектов. Создай первый через кнопку в сайдбаре.")
        st.stop()

    # ── Верхние метрики ──────────────────────────────────────────────────
    total = len(projects)
    calc  = sum(1 for _, p in projects if p.get("_results"))
    p_sum = sum(
        p.get("_results", {}).get("summary", {}).get("p_installed_kw", 0)
        for _, p in projects if p.get("_results")
    )
    def _safe_len(val) -> int:
        return len(val) if isinstance(val, list) else 0

    warns = sum(
        _safe_len(p.get("_results", {}).get("cable_checks", {}).get("du_violations")) +
        _safe_len(p.get("_results", {}).get("cable_checks", {}).get("kz_thermal_violations"))
        for _, p in projects if p.get("_results")
    )

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("📁 Проектов",      total)
    col2.metric("✅ Рассчитано",    f"{calc} / {total}")
    col3.metric("⚡ Суммарно, кВт", f"{p_sum:.1f}")
    col4.metric(
        "⚠️ Нарушений", warns,
        delta=None if warns == 0 else "требует проверки",
        delta_color="inverse",
    )

    st.divider()
    st.subheader("Объекты")

    # ── Карточки по 2 в строку ───────────────────────────────────────────
    from itertools import zip_longest
    pairs = [projects[i:i + 2] for i in range(0, len(projects), 2)]
    for pair in pairs:
        cols = st.columns(2)
        for col, item in zip_longest(cols, pair):
            if item is None:
                continue
            d, p = item
            if col is None:
                continue
            with col:
                with st.container(border=True):
                    proj    = p.get("project", {})
                    res     = p.get("_results", {})
                    summary = res.get("summary", {})
                    bld     = p.get("_building", {})
                    calc_ok = bool(res)

                    code    = proj.get("code", "?")
                    name    = proj.get("name", "?")
                    stage   = proj.get("stage", "")
                    cat     = bld.get("category_pue", "—")
                    p_inst  = summary.get("p_installed_kw")
                    p_calc  = summary.get("p_calc_kw")
                    i_vru   = summary.get("i_vru_a")
                    cos_phi = summary.get("cos_phi")
                    calc_at = res.get("calculated_at", "")[:10]

                    # Заголовок карточки
                    hdr_col, stage_col = st.columns([4, 1])
                    hdr_col.markdown(f"**{code}** — {name[:35]}")
                    stage_col.markdown(f"`{stage}`" if stage else "")

                    st.divider()

                    if calc_ok:
                        r1c1, r1c2 = st.columns(2)
                        r1c1.write(f"⚡ Pуст: **{p_inst:.1f} кВт**" if p_inst is not None else "⚡ Pуст: —")
                        r1c2.write(f"Pрасч: **{p_calc:.1f} кВт**"   if p_calc is not None else "Pрасч: —")

                        r2c1, r2c2 = st.columns(2)
                        r2c1.write(f"🔌 Iвру: **{i_vru:.1f} А**"    if i_vru   is not None else "🔌 Iвру: —")
                        r2c2.write(f"cos φ: **{cos_phi:.3f}**"       if cos_phi is not None else "cos φ: —")

                        r3c1, r3c2 = st.columns(2)
                        r3c1.write(f"🏢 Кат. ПУЭ: **{cat}**")
                        r3c2.write(f"Дата: {calc_at}" if calc_at else "")
                    else:
                        st.warning("Расчёт не выполнен")

                    if st.button("→ Открыть", key=f"open_{code}"):
                        st.session_state["active_project"] = str(d)
                        st.rerun()

    st.stop()


# ── Активный проект ─────────────────────────────────────────────────

proj_dir = Path(active_path)
project = load_project(proj_dir)

if not project:
    st.error(f"Не найден project.json в {proj_dir}")
    st.stop()

proj = project.get("project", {})
results = project.get("_results")
calc_done = project.get("_meta", {}).get("calc_done", False)
active_section = st.session_state.get("active_section", "Все")

# Шапка
col_back, col_title, col_btns = st.columns([1, 3, 1])
with col_back:
    st.write("")
    if st.button("← К проектам", width="stretch"):
        st.session_state["active_project"] = None
        st.session_state.pop("active_section", None)
        st.rerun()
with col_title:
    _sec_badge = f" — **{active_section}**" if active_section != "Все" else ""
    st.title(f"⚡ {proj.get('name','')}")
    st.caption(f"Код: {proj.get('code','')} | Стадия: {proj.get('stage','')} | "
               f"Ред. {proj.get('revision',0)} | {proj.get('date','')}"
               + (f" | Раздел: {active_section}" if active_section != "Все" else ""))

with col_btns:
    st.write("")
    if st.button("🔄 Пересчитать всё", type="primary", width="stretch"):
        with st.spinner("Расчёт..."):
            out, err, rc = run_cli(["calc", str(proj_dir)])
        if rc == 0:
            st.success("Расчёт завершён")
            project = load_project(proj_dir)
            results = project.get("_results")
            calc_done = True
            st.rerun()
        else:
            st.error(f"Ошибка расчёта:\n{err}")

    if st.button("📄 Сгенерировать документы", width="stretch"):
        with st.spinner("Генерация..."):
            out, err, rc = run_cli(["docs", str(proj_dir)])
        if rc == 0:
            st.success(out.strip().split("\n")[-1] if out else "Готово")
        else:
            st.error(err)


# Вкладки
tab_summary, tab_data, tab_results, tab_cables, tab_changes, tab_docs = st.tabs([
    "📊 Сводка", "✏️ Данные", "🔢 Расчёт", "⚡ Кабели", "📝 Изменения", "📁 Документы"
])


# ── Вкладка: Сводка ─────────────────────────────────────────────────

with tab_summary:
    if calc_done and results:
        s = results.get("summary", {})
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Pустан, кВт", f"{s.get('p_installed_kw', 0):.1f}")
        c2.metric("Pрасч, кВт",  f"{s.get('p_calc_kw', 0):.1f}")
        c3.metric("cos φ",        f"{s.get('cos_phi', 0):.3f}")
        c4.metric("Iвру, А",      f"{s.get('i_vru_a', 0):.1f}")

        st.divider()
        cable = s.get("incoming_cable", {})
        vru_r = results.get("vru", {})
        br = vru_r.get("breaker", {})
        col_a, col_b = st.columns(2)
        with col_a:
            if cable.get("section_mm2"):
                st.info(f"**Вводной кабель:** {cable['mark']} "
                        f"{cable['cores']}×{cable['section_mm2']} мм² · "
                        f"L={cable.get('length_m',0)} м · "
                        f"ΔU={cable.get('voltage_drop_pct',0)}%")
        with col_b:
            if br.get("rating"):
                st.info(f"**Вводной автомат:** АВ {br['rating']}А хар.{br.get('char','C')} "
                        f"({br.get('type','')})")

        # Категория здания (ПУЭ гл.1.2)
        bld = project.get("_building", {})
        if bld:
            cat = bld.get("category_pue", "?")
            vru_desc = bld.get("vru_description", "—")
            compliance = bld.get("compliance_ok", True)
            n_viol = bld.get("violations", 0)
            c_cat, c_scheme, c_comp = st.columns(3)
            c_cat.metric("Категория здания (ПУЭ)", cat)
            c_scheme.metric("Схема ВРУ", vru_desc)
            if compliance:
                c_comp.success("✓ Категорийность OK")
            else:
                c_comp.error(f"⚠ Нарушений кат.: {n_viol}")

        # Таблица щитов
        st.subheader("Щиты")
        for feeder in vru_r.get("feeders", []):
            st.markdown(f"**{feeder['id']} — {feeder['name']}** "
                        f"(Pр={feeder['p_calc_kw']:.1f} кВт, Iр={feeder['i_calc_a']:.1f} А)")
            data = []
            for panel in feeder.get("panels", []):
                pc = panel.get("cable", {})
                pb = panel.get("breaker", {})
                du = pc.get("voltage_drop_pct", 0)
                data.append({
                    "ID": panel["id"],
                    "Наименование": panel["name"],
                    "Этаж": panel.get("floor", ""),
                    "Iр, А": f"{panel['i_calc_a']:.1f}",
                    "Кабель": f"{pc.get('mark','')} {pc.get('cores','')}×{pc.get('section_mm2','')}",
                    "L, м": pc.get("length_m", ""),
                    "ΔU, %": f"{'⚠️ ' if du > 5 else ''}{du}",
                    "Автомат": f"{pb.get('rating','')}А {pb.get('char','')}",
                })
            st.dataframe(data, width="stretch", hide_index=True)
            
            # Фазовый баланс фидера
            pb = feeder.get("phase_balance")
            if pb:
                with st.expander("⚖️ Фазовый баланс", expanded=False):
                    imb = pb.get("imbalance_pct", 0)
                    col_a, col_b, col_c, col_d = st.columns(4)
                    col_a.metric("Iа, А", f"{pb['A']['i_a']:.1f}")
                    col_b.metric("Iб, А", f"{pb['B']['i_a']:.1f}")
                    col_c.metric("Iс, А", f"{pb['C']['i_a']:.1f}")
                    color = "🟢" if imb < 10 else ("🟡" if imb < 20 else "🔴")
                    col_d.metric(f"{color} Дисбаланс", f"{imb:.1f}%")
    else:
        st.warning("Проект ещё не рассчитан. Нажми **Пересчитать всё**.")


# ── Вкладка: Данные ──────────────────────────────────────────────────

with tab_data:
    sub_consumers, sub_settings, sub_kz, sub_json = st.tabs([
        "👥 Потребители", "⚙️ Настройки щитов", "⚡ Ток КЗ", "{ } JSON"
    ])

    # ── Суб-вкладка: Потребители ──────────────────────────────────────
    with sub_consumers:
        import pandas as pd

        CONSUMER_TYPES  = ["lighting", "power", "hvac", "it", "other"]
        INSTALL_OPTIONS = ["лоток", "труба", "открыто", "земля"]

        # Список щитов, отфильтрованных по разделу
        _all_feeders = project.get("vru", {}).get("feeders", [])
        panel_options = []
        for _fi, _feeder in enumerate(_all_feeders):
            if active_section != "Все" and _feeder.get("section") != active_section:
                continue
            for _pi, _panel in enumerate(_feeder.get("panels", [])):
                _label = (f"{_feeder.get('id','?')} / {_panel.get('id','?')}"
                          f" — {_panel.get('name','')}")
                panel_options.append((_label, _fi, _pi))

        if not panel_options:
            _hint = (f" раздела «{active_section}»" if active_section != "Все" else "")
            st.warning(f"Щиты{_hint} не найдены. "
                       + ("Выбери другой раздел в сайдбаре или заполни JSON." if active_section != "Все"
                          else "Заполни структуру проекта во вкладке «{ } JSON»."))
        else:
            selected_label = st.selectbox(
                "Щит", [o[0] for o in panel_options], key="panel_sel"
            )
            fi, pi = next((o[1], o[2]) for o in panel_options if o[0] == selected_label)
            panel     = project["vru"]["feeders"][fi]["panels"][pi]
            consumers = panel.setdefault("consumers", [])

            # Плоская таблица потребителей
            rows = [{
                "id":            c.get("id", ""),
                "name":          c.get("name", ""),
                "type":          c.get("type", "power"),
                "power_kw":      float(c.get("power_kw", 0.0)),
                "demand_factor": float(c.get("demand_factor", 0.85)),
                "cos_phi":       float(c.get("cos_phi", 0.85)),
                "phases":        int(c.get("phases", 3)),
                "start_factor":  float(c.get("start_factor", 1.0)),
            } for c in consumers]

            df = pd.DataFrame(
                rows,
                columns=["id","name","type","power_kw",
                         "demand_factor","cos_phi","phases","start_factor"]
            )

            st.caption("Нажми + внизу таблицы чтобы добавить потребителя; выдели строку и Del — чтобы удалить.")
            edited_df = st.data_editor(
                df,
                num_rows="dynamic",
                use_container_width=True,
                column_config={
                    "id":   st.column_config.TextColumn("ID", required=True),
                    "name": st.column_config.TextColumn("Наименование"),
                    "type": st.column_config.SelectboxColumn(
                        "Тип", options=CONSUMER_TYPES, required=True
                    ),
                    "power_kw":      st.column_config.NumberColumn(
                        "Pуст, кВт", min_value=0.0, step=0.1, format="%.2f"),
                    "demand_factor": st.column_config.NumberColumn(
                        "kс", min_value=0.0, max_value=1.0, step=0.01, format="%.2f"),
                    "cos_phi":       st.column_config.NumberColumn(
                        "cos φ", min_value=0.01, max_value=1.0, step=0.01, format="%.2f"),
                    "phases":        st.column_config.NumberColumn(
                        "Фазы", min_value=1, max_value=3, step=1),
                    "start_factor":  st.column_config.NumberColumn(
                        "kп", min_value=1.0, step=0.1, format="%.1f"),
                },
                hide_index=True,
                key=f"consumer_editor_{fi}_{pi}",
            )

            # Редактор кабеля выбранного потребителя
            st.divider()
            st.caption("Кабель потребителя")

            consumer_ids = [
                str(r["id"]) for _, r in edited_df.iterrows()
                if str(r.get("id", "")).strip() not in ("", "nan")
            ]
            c_idx    = None
            new_mark = new_cores = new_sec = new_len = new_install = new_amb = None

            if consumer_ids:
                selected_consumer_id = st.selectbox(
                    "Потребитель", consumer_ids, key=f"cable_sel_{fi}_{pi}"
                )
                c_idx = next(
                    (i for i, c in enumerate(consumers)
                     if c.get("id") == selected_consumer_id),
                    None
                )
                cable = consumers[c_idx].get("cable", {}) if c_idx is not None else {}
            else:
                st.caption("Добавь потребителей в таблицу выше, затем сохрани — и здесь появится редактор кабеля.")
                col1, col2, col3 = st.columns(3)
                with col1:
                    new_mark  = st.text_input(
                        "Марка кабеля", value=cable.get("mark", "ВВГнг-LS"),
                        key=f"cm_{fi}_{pi}_{c_idx}")
                    new_cores = st.number_input(
                        "Жилы", value=int(cable.get("cores", 3)),
                        min_value=1, max_value=5, key=f"cc_{fi}_{pi}_{c_idx}")
                with col2:
                    new_sec = st.number_input(
                        "Сечение, мм²", value=float(cable.get("section_mm2") or 0),
                        min_value=0.0, step=0.5, key=f"cs_{fi}_{pi}_{c_idx}")
                    new_len = st.number_input(
                        "Длина, м", value=float(cable.get("length_m", 10)),
                        min_value=0.0, step=1.0, key=f"cl_{fi}_{pi}_{c_idx}")
                with col3:
                    install_val = cable.get("install", "лоток")
                    install_idx = (INSTALL_OPTIONS.index(install_val)
                                   if install_val in INSTALL_OPTIONS else 0)
                    new_install = st.selectbox(
                        "Прокладка", INSTALL_OPTIONS,
                        index=install_idx, key=f"ci_{fi}_{pi}_{c_idx}")
                    new_amb = st.number_input(
                        "Темп. среды, °C", value=int(cable.get("ambient_t", 25)),
                        min_value=-40, max_value=50, key=f"ca_{fi}_{pi}_{c_idx}")

            # Сохранение
            if st.button("💾 Сохранить потребителей", type="primary",
                         key=f"save_cons_{fi}_{pi}"):
                new_consumers = []
                save_error = False
                for _, row in edited_df.iterrows():
                    cid = str(row.get("id", "")).strip()
                    if not cid or cid == "nan":
                        continue
                    old = next((c for c in consumers if c.get("id") == cid), {})
                    try:
                        new_consumers.append({
                            "id":            cid,
                            "name":          str(row.get("name", "")),
                            "type":          str(row.get("type", "power")),
                            "power_kw":      float(row.get("power_kw", 0.0)),
                            "demand_factor": float(row.get("demand_factor", 0.85)),
                            "cos_phi":       float(row.get("cos_phi", 0.85)),
                            "phases":        int(row.get("phases", 3)),
                            "start_factor":  float(row.get("start_factor", 1.0)),
                        "cable":         old.get("cable", {
                            "mark": "ВВГнг-LS", "cores": 3, "section_mm2": None,
                            "length_m": 10, "install": "лоток",
                            "ambient_t": 25, "parallel": 1,
                        }),
                        })
                    except (ValueError, TypeError) as _e:
                        st.error(f"Ошибка в строке потребителя «{cid}»: {_e}")
                        save_error = True
                        break
                if save_error:
                    st.stop()
                # Обновить cable выбранного потребителя
                if c_idx is not None and new_mark is not None:
                    target_id = consumers[c_idx].get("id")
                    target = next(
                        (nc for nc in new_consumers if nc["id"] == target_id), None
                    )
                    if target is None:
                        st.error(f"Потребитель «{target_id}» не найден в списке — cable не обновлён. "
                                 "Убедись, что ID не был изменён при редактировании таблицы.")
                    if target is not None:
                        target["cable"] = {
                            "mark":        new_mark,
                            "cores":       int(new_cores),
                            "section_mm2": float(new_sec) if new_sec > 0 else None,
                            "length_m":    float(new_len),
                            "install":     new_install,
                            "ambient_t":   int(new_amb),
                            "parallel":    (consumers[c_idx].get("cable", {})
                                            .get("parallel", 1)),
                        }
                project["vru"]["feeders"][fi]["panels"][pi]["consumers"] = new_consumers
                save_project(project, proj_dir)
                st.success("Сохранено. Нажми **Пересчитать всё**.")
                st.rerun()

    # ── Суб-вкладка: Настройки щитов ─────────────────────────────────
    with sub_settings:
        vru = project.get("vru", {})
        
        # ── Выбор щита (с фильтром по разделу) ─────────────────────────
        panel_options_s = []
        for _fi, _feeder in enumerate(vru.get("feeders", [])):
            if active_section != "Все" and _feeder.get("section") != active_section:
                continue
            for _pi, _panel in enumerate(_feeder.get("panels", [])):
                _label = f"{_feeder.get('id','?')} / {_panel.get('id','?')} — {_panel.get('name','')}"
                panel_options_s.append((_label, _fi, _pi))

        col_sel, col_add = st.columns([4, 1])
        with col_sel:
            if not panel_options_s:
                _hint_s = f" раздела «{active_section}»" if active_section != "Все" else ""
                st.info(f"Нет щитов{_hint_s}. Добавьте через кнопку →")
                selected_panel_s = None
            else:
                selected_label_s = st.selectbox(
                    "Выберите щит",
                    [o[0] for o in panel_options_s],
                    key="settings_panel_select",
                )
                _match = next((o for o in panel_options_s if o[0] == selected_label_s), None)
                if _match is None:
                    st.error("Щит не найден. Обнови страницу.")
                    st.stop()
                fi_s, pi_s = _match[1], _match[2]
                selected_panel_s = project["vru"]["feeders"][fi_s]["panels"][pi_s]

        with col_add:
            st.write("")
            st.write("")
            if st.button("➕ Добавить щит", key="add_panel_btn"):
                st.session_state["show_add_panel"] = True

        # ── Форма добавления нового щита ────────────────────────────────
        if st.session_state.get("show_add_panel"):
            from panels.auto_panels import make_blank_panel, _PANEL_META
            with st.form("new_panel_form"):
                st.markdown("**Новый щит**")
                np_feeder_ids = [f.get("id", f"feeder_{i}") for i, f in enumerate(vru.get("feeders", []))]
                np_feeder = st.selectbox("Фидер", np_feeder_ids, key="np_feeder")
                np_id = st.text_input("ID щита (напр. ЩО-2)", key="np_id")
                np_type = st.selectbox("Тип щита", list(_PANEL_META.keys()), key="np_type")
                np_submitted = st.form_submit_button("Создать")
                if np_submitted:
                    if np_id:
                        new_panel = make_blank_panel(np_id, np_type)
                        fi_new = next(
                            (i for i, f in enumerate(vru.get("feeders", [])) if f.get("id") == np_feeder),
                            None,
                        )
                        if fi_new is None:
                            st.error(f"Фидер «{np_feeder}» не найден. Обнови страницу.")
                            st.stop()
                        vru["feeders"][fi_new].setdefault("panels", []).append(new_panel)
                        save_project(project, proj_dir)
                        st.session_state["show_add_panel"] = False
                        st.success(f"Щит {np_id} добавлен")
                        st.rerun()
                    else:
                        st.warning("Укажите ID щита")

        if selected_panel_s is None:
            st.stop()

        panel_s = selected_panel_s

        # ── Параметры щита ──────────────────────────────────────────────
        st.divider()
        col_meta, col_cable = st.columns(2)

        with col_meta:
            st.markdown("**📋 Параметры щита**")
            panel_name_s = st.text_input(
                "Название", value=panel_s.get("name", ""), key=f"pname_{fi_s}_{pi_s}"
            )
            panel_floor_s = st.text_input(
                "Этаж", value=str(panel_s.get("floor", "")), key=f"pfloor_{fi_s}_{pi_s}"
            )
            PANEL_TYPES = {
                "lighting": "Освещение", "power": "Силовой",
                "heating": "Отопление", "ventilation": "Вентиляция",
                "hvac": "Кондиционирование", "technology": "Технологический",
                "smoke_exhaust": "Дымоудаление", "firefighting": "Пожаротушение",
                "outdoor_lighting": "Наружное освещение",
            }
            ptype_keys = list(PANEL_TYPES.keys())
            ptype_labels = list(PANEL_TYPES.values())
            cur_type = panel_s.get("type", "power")
            ptype_idx = ptype_keys.index(cur_type) if cur_type in ptype_keys else 0
            panel_type_s = st.selectbox(
                "Тип", ptype_labels, index=ptype_idx, key=f"ptype_{fi_s}_{pi_s}"
            )
            panel_cat_s = st.selectbox(
                "Категория ПУЭ", [1, 2, 3],
                index=[1, 2, 3].index(panel_s.get("category_pue", 3)),
                key=f"pcat_{fi_s}_{pi_s}",
            )
            panel_avr_s = st.checkbox(
                "Есть АВР", value=bool(panel_s.get("has_avr", False)),
                key=f"pavr_{fi_s}_{pi_s}",
            )

        with col_cable:
            st.markdown("**🔌 Ввод (кабель питания щита)**")
            cable_s = panel_s.setdefault("cable", {})
            INSTALL_OPTIONS = ["лоток", "труба", "открыто", "земля"]
            cur_install = cable_s.get("install", "лоток")
            install_idx = INSTALL_OPTIONS.index(cur_install) if cur_install in INSTALL_OPTIONS else 0

            pc_mark = st.text_input(
                "Марка", value=cable_s.get("mark", "ВВГнг-LS"), key=f"pcmark_{fi_s}_{pi_s}"
            )
            pc_cores = st.number_input(
                "Жил", min_value=1, max_value=5,
                value=int(cable_s.get("cores", 4)), step=1, key=f"pccores_{fi_s}_{pi_s}"
            )
            pc_section = st.number_input(
                "Сечение, мм² (0 = авто)", min_value=0.0, max_value=500.0,
                value=float(cable_s.get("section_mm2") or 0.0), step=1.0,
                key=f"pcsec_{fi_s}_{pi_s}",
            )
            pc_length = st.number_input(
                "Длина план, м", min_value=0.0, max_value=2000.0,
                value=float(cable_s.get("length_m", 20)), step=1.0,
                key=f"pclen_{fi_s}_{pi_s}",
            )
            pc_install = st.selectbox(
                "Прокладка", INSTALL_OPTIONS, index=install_idx, key=f"pcinst_{fi_s}_{pi_s}"
            )
            pc_temp = st.number_input(
                "Темп. окр., °C", min_value=-40, max_value=50,
                value=int(cable_s.get("ambient_t", 25)), step=1, key=f"pctemp_{fi_s}_{pi_s}"
            )
            pc_parallel = st.number_input(
                "Параллельных кабелей", min_value=1, max_value=10,
                value=int(cable_s.get("parallel", 1)), step=1, key=f"pcpar_{fi_s}_{pi_s}"
            )

        # ── Кнопка сохранения мета + кабеля щита ───────────────────────
        col_save, col_del = st.columns([3, 1])
        with col_save:
            if st.button("💾 Сохранить параметры щита", key=f"save_panel_{fi_s}_{pi_s}"):
                panel_s["name"] = panel_name_s
                panel_s["floor"] = panel_floor_s
                panel_s["type"] = ptype_keys[ptype_labels.index(panel_type_s)]
                panel_s["category_pue"] = panel_cat_s
                panel_s["has_avr"] = panel_avr_s
                # Merge кабеля — НЕ перезаписывать целиком
                panel_s["cable"].update({
                    "mark": pc_mark,
                    "cores": int(pc_cores),
                    "section_mm2": float(pc_section) if pc_section > 0 else None,
                    "length_m": float(pc_length),
                    "install": pc_install,
                    "ambient_t": int(pc_temp),
                    "parallel": int(pc_parallel),
                })
                save_project(project, proj_dir)
                st.success("Параметры щита сохранены")
                st.rerun()
        with col_del:
            if st.button("🗑️ Удалить щит", key=f"del_panel_{fi_s}_{pi_s}", type="secondary"):
                st.session_state[f"confirm_del_{fi_s}_{pi_s}"] = True

        # Кнопка автобаланса фаз
        if st.button("⚖️ Авто-баланс фаз этого щита", key=f"balance_ph_{fi_s}_{pi_s}"):
            out, err, rc = run_cli(["balance-phases", str(proj_dir)])
            if rc == 0:
                st.success("Фазы назначены. Нажми Пересчитать всё.")
                st.rerun()
            else:
                st.error(err)

        if st.session_state.get(f"confirm_del_{fi_s}_{pi_s}"):
            _n_cons = len(panel_s.get("consumers", []))
            _cons_info = f" и {_n_cons} потребител{'ем' if _n_cons == 1 else 'ями' if 2 <= _n_cons <= 4 else 'ями'}" if _n_cons else ""
            st.warning(f"Удалить щит **{panel_s.get('id')}**{_cons_info}? Это действие необратимо.")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("Да, удалить", key=f"confirm_yes_{fi_s}_{pi_s}"):
                    vru["feeders"][fi_s]["panels"].pop(pi_s)
                    save_project(project, proj_dir)
                    st.session_state.pop(f"confirm_del_{fi_s}_{pi_s}", None)
                    st.success("Щит удалён")
                    st.rerun()
            with c2:
                if st.button("Отмена", key=f"confirm_no_{fi_s}_{pi_s}"):
                    st.session_state.pop(f"confirm_del_{fi_s}_{pi_s}", None)
                    st.rerun()

        # ── Потребители щита ────────────────────────────────────────────
        st.divider()
        st.markdown("**👥 Потребители щита**")

        consumers_s = panel_s.setdefault("consumers", [])

        if not consumers_s:
            st.info("Нет потребителей. Добавьте строку в таблицу ниже.")

        CON_TYPES = ["lighting", "power", "hvac", "pump", "it", "other"]

        df_consumers_s = []
        for c in consumers_s:
            df_consumers_s.append({
                "id":            c.get("id", ""),
                "name":          c.get("name", ""),
                "type":          c.get("type", "power"),
                "power_kw":      c.get("power_kw", 0.0),
                "demand_factor": c.get("demand_factor", 0.8),
                "cos_phi":       c.get("cos_phi", 0.85),
                "phases":        c.get("phases", 3),
                "phase":         c.get("phase", "") if c.get("phases", 3) == 1 else "",
                "start_factor":  c.get("start_factor", 1.0),
                "reserve":       c.get("reserve", False),
            })

        import pandas as pd
        df_s = pd.DataFrame(df_consumers_s) if df_consumers_s else pd.DataFrame(columns=[
            "id", "name", "type", "power_kw", "demand_factor", "cos_phi",
            "phases", "phase", "start_factor", "reserve"
        ])

        edited_df_s = st.data_editor(
            df_s,
            num_rows="dynamic",
            use_container_width=True,
            key=f"consumers_editor_{fi_s}_{pi_s}",
            column_config={
                "id":            st.column_config.TextColumn("ID", width="small"),
                "name":          st.column_config.TextColumn("Название"),
                "type":          st.column_config.SelectboxColumn("Тип", options=CON_TYPES),
                "power_kw":      st.column_config.NumberColumn("P, кВт", min_value=0.0, step=0.1),
                "demand_factor": st.column_config.NumberColumn("kс", min_value=0.0, max_value=1.0, step=0.01),
                "cos_phi":       st.column_config.NumberColumn("cosφ", min_value=0.01, max_value=1.0, step=0.01),
                "phases":        st.column_config.SelectboxColumn("Фаз", options=[1, 3]),
                "phase":         st.column_config.SelectboxColumn(
                    "Фаза", options=["", "A", "B", "C"],
                    help="Только для однофазных (phases=1). Пустое = авто."
                ),
                "start_factor":  st.column_config.NumberColumn("Iпуск/Iн", min_value=1.0, step=0.1),
                "reserve":       st.column_config.CheckboxColumn("Резерв"),
            },
        )

        if st.button("💾 Сохранить потребителей", key=f"save_consumers_{fi_s}_{pi_s}"):
            new_rows = edited_df_s.to_dict("records")
            # Merge: сохранить cable каждого потребителя
            old_by_id = {c.get("id"): c for c in consumers_s}
            merged = []
            for row in new_rows:
                cid = str(row.get("id", "")).strip()
                if not cid:
                    continue
                old_c = old_by_id.get(cid, {})
                new_item = {
                    "id":            cid,
                    "name":          str(row.get("name", cid)),
                    "type":          str(row.get("type", "power")),
                    "power_kw":      float(row.get("power_kw", 0.0)),
                    "demand_factor": float(row.get("demand_factor", 0.8)),
                    "cos_phi":       float(row.get("cos_phi", 0.85)),
                    "phases":        int(row.get("phases", 3)),
                    "start_factor":  float(row.get("start_factor", 1.0)),
                    "reserve":       bool(row.get("reserve", False)),
                    # Сохранить cable из оригинала, если есть
                    "cable": old_c.get("cable", {
                        "mark": "ВВГнг-LS", "cores": 3 if int(row.get("phases", 3)) == 3 else 2,
                        "section_mm2": None, "length_m": 15,
                        "install": "лоток", "ambient_t": 25, "parallel": 1,
                    }),
                }
                # Добавить phase только для однофазных
                if int(row.get("phases", 3)) == 1:
                    phase_val = str(row.get("phase", "")).strip()
                    if phase_val in ("A", "B", "C"):
                        new_item["phase"] = phase_val
                merged.append(new_item)
            panel_s["consumers"] = merged
            save_project(project, proj_dir)
            st.success(f"Сохранено {len(merged)} потребителей")
            st.rerun()

    # ── Суб-вкладка: Ток КЗ ───────────────────────────────────────────
    with sub_kz:
        vru = project.get("vru", {})
        st.subheader("Расчёт тока КЗ от параметров ТП")

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**🏭 Параметры трансформатора**")
            tp_s_nom = st.number_input(
                "S_ном, кВА", min_value=25.0, max_value=10000.0,
                value=float(vru.get("tp_s_nom_kva", 630)), step=25.0,
                key="tp_s_nom"
            )
            tp_u_k = st.number_input(
                "u_к, %", min_value=1.0, max_value=10.0,
                value=float(vru.get("tp_u_k_pct", 5.5)), step=0.1,
                key="tp_u_k"
            )
            tp_u_nom_lv = st.number_input(
                "U_ном (вторич.), кВ", min_value=0.1, max_value=1.0,
                value=float(vru.get("tp_u_nom_lv_kv", 0.4)), step=0.05,
                key="tp_u_nom_lv"
            )
        with col2:
            st.markdown("**🔌 Кабель ТП → ВРУ**")
            tp_cable_mark = st.text_input(
                "Марка кабеля", value=vru.get("tp_cable_mark", "ВВГнг-LS"),
                key="tp_cable_mark"
            )
            tp_cable_section = st.number_input(
                "Сечение, мм²", min_value=0.0, max_value=1000.0,
                value=float(vru.get("tp_cable_section_mm2", 0.0)), step=1.0,
                key="tp_cable_section"
            )
            tp_cable_length = st.number_input(
                "Длина, м", min_value=0.0, max_value=2000.0,
                value=float(vru.get("tp_cable_length_m", 0.0)), step=1.0,
                key="tp_cable_length"
            )
            tp_parallel = st.number_input(
                "Параллельных кабелей", min_value=1, max_value=10,
                value=int(vru.get("tp_parallel_cables", 1)), step=1,
                key="tp_parallel"
            )

        from calc.engine import calc_isc_from_tp
        try:
            kz_result = calc_isc_from_tp(
                tp_s_nom, tp_u_k, tp_u_nom_lv,
                tp_cable_mark, tp_cable_section, tp_cable_length, tp_parallel
            )
        except Exception as _e:
            st.error(f"Ошибка расчёта тока КЗ: {_e}")
            st.stop()

        st.divider()
        m1, m2, m3 = st.columns(3)
        m1.metric("Z_тр", f"{kz_result['z_tr_ohm'] * 1000:.2f} мОм")
        m2.metric("Z_каб", f"{kz_result['z_cable_ohm'] * 1000:.2f} мОм")
        m3.metric("Iкз на шинах ТП", f"{kz_result['isc_at_tr_ka']:.2f} кА")

        isc_vru = kz_result["isc_at_vru_ka"]
        color = "🟢" if isc_vru >= 3.0 else "🟡"
        st.markdown(f"### {color} Iкз на шинах ВРУ: **{isc_vru:.2f} кА**")
        st.caption(f"Текущее значение в проекте: isc_ka = {vru.get('isc_ka', 10.0)} кА")

        if kz_result.get("notes"):
            st.warning(kz_result["notes"])

        if st.button("✅ Применить к проекту", key="apply_isc_ka"):
            vru["isc_ka"] = round(isc_vru, 3)
            vru["tp_s_nom_kva"] = tp_s_nom
            vru["tp_u_k_pct"] = tp_u_k
            vru["tp_u_nom_lv_kv"] = tp_u_nom_lv
            vru["tp_cable_mark"] = tp_cable_mark
            vru["tp_cable_section_mm2"] = tp_cable_section
            vru["tp_cable_length_m"] = tp_cable_length
            vru["tp_parallel_cables"] = tp_parallel
            save_project(project, proj_dir)
            st.success(f"isc_ka = {vru['isc_ka']} кА сохранено в проект")
            st.rerun()

    # ── Суб-вкладка: JSON ─────────────────────────────────────────────
    with sub_json:
        st.subheader("Редактор project.json")
        st.caption("Прямое редактирование JSON. После изменений нажми Сохранить, затем Пересчитать.")

        json_text = st.text_area(
            "project.json",
            value=json.dumps(project, ensure_ascii=False, indent=2),
            height=600,
            key="json_editor"
        )

        col_save, col_validate = st.columns(2)
        with col_save:
            if st.button("💾 Сохранить", type="primary"):
                try:
                    new_project = json.loads(json_text)
                    save_project(new_project, proj_dir)
                    st.success("Сохранено")
                    st.rerun()
                except json.JSONDecodeError as e:
                    st.error(f"Ошибка JSON: {e}")
        with col_validate:
            if st.button("✔️ Проверить"):
                out, err, rc = run_cli(["validate", str(proj_dir)])
                if rc == 0:
                    st.success(out.strip())
                else:
                    st.error(out.strip())


# ── Вкладка: Расчёт ─────────────────────────────────────────────────

with tab_results:
    if not calc_done or not results:
        st.warning("Нет результатов расчёта.")
    else:
        sub_panels, sub_illum = st.tabs(["Щиты и потребители", "💡 Освещённость"])

        with sub_panels:
            vru_r = results.get("vru", {})
            _feeders_r = _filter_feeders(vru_r.get("feeders", []), active_section)
            if not _feeders_r:
                st.info("Щиты не найдены в результатах расчёта. "
                        + (f"Раздел «{active_section}» пуст или не рассчитан." if active_section != "Все"
                           else "Нажми «Пересчитать всё»."))
            for feeder in _feeders_r:
                with st.expander(f"{feeder['id']} — {feeder['name']} "
                                 f"| Pр={feeder['p_calc_kw']:.1f} кВт | Iр={feeder['i_calc_a']:.1f} А",
                                 expanded=True):
                    for panel in feeder.get("panels", []):
                        st.markdown(f"**{panel['id']} {panel['name']}** "
                                    f"(Iр={panel['i_calc_a']:.1f} А, n={panel['n_consumers']} потр.)")
                        data = []
                        for c in panel.get("consumers", []):
                            cc = c.get("cable", {})
                            cb = c.get("breaker", {})
                            du = cc.get("voltage_drop_pct", 0)
                            data.append({
                                "ID": c["id"],
                                "Потребитель": c["name"],
                                "Pн, кВт": c["power_kw"],
                                "Кд": c["demand_factor"],
                                "Iр, А": c["i_calc_a"],
                                "Кабель": f"{cc.get('mark','')} {cc.get('cores','')}×{cc.get('section_mm2','')}",
                                "L, м": cc.get("length_m",""),
                                "ΔU, %": f"{'⚠️' if du>5 else ''}{du}",
                                "Автомат": f"{cb.get('rating','')}А {cb.get('char','')}",
                            })
                        st.dataframe(data, width="stretch", hide_index=True)

        with sub_illum:
            illum = results.get("illumination", [])
            if illum_err := results.get("illumination_error"):
                st.error(f"Ошибка расчёта освещённости: {illum_err}")
                with st.expander("Пример структуры rooms[] в project.json"):
                    st.code(
                        '{\n'
                        '  "rooms": [\n'
                        '    {\n'
                        '      "id": "П-01",\n'
                        '      "name": "Офис 101",\n'
                        '      "type": "office",\n'
                        '      "s_m2": 40.0,\n'
                        '      "height_m": 3.0,\n'
                        '      "n_luminaires": 8,\n'
                        '      "luminous_flux_lm": 3200\n'
                        '    }\n'
                        '  ]\n'
                        '}',
                        language="json",
                    )
            elif not illum:
                st.info("Нет данных об освещённости. Добавьте блок 'rooms' в project.json.")
            else:
                n_ok   = sum(1 for r in illum if r["ok"])
                n_fail = len(illum) - n_ok
                c1, c2, c3 = st.columns(3)
                c1.metric("Помещений", len(illum))
                c2.metric("Соответствует норме", n_ok)
                c3.metric("Дефицит освещённости", n_fail, delta=f"-{n_fail}" if n_fail else None,
                          delta_color="inverse")

                rows = []
                for r in illum:
                    rows.append({
                        "ID":          r["id"],
                        "Помещение":   r["name"],
                        "Тип":         r["type"],
                        "S, м²":       r["s_m2"],
                        "Индекс i":    r["room_index"],
                        "КИ":          r["uf"],
                        "Eфакт, лк":   r["e_fact_lx"],
                        "Eнорм, лк":   r["e_norm_lx"],
                        "Статус":      "OK" if r["ok"] else f"−{r['deficit_pct']:.0f}% (нужно {r['n_required']} св.)",
                    })
                st.dataframe(rows, hide_index=True, use_container_width=True)


# ── Вкладка: Кабели ─────────────────────────────────────────────────

with tab_cables:
    if not calc_done or not results:
        st.warning("Нет результатов расчёта.")
    else:
        vru_r = results.get("vru", {})
        du_err, kzt_err, kzs_err = [], [], []

        for feeder in _filter_feeders(vru_r.get("feeders", []), active_section):
            for panel in feeder.get("panels", []):
                for obj_id, obj_name, cb in (
                    [(panel["id"], panel["name"], panel.get("cable", {}))]
                    + [(c["id"], c["name"], c.get("cable", {}))
                       for c in panel.get("consumers", [])]
                ):
                    if not cb.get("du_ok", True):
                        du_err.append({
                            "ID": obj_id, "Наименование": obj_name,
                            "ΔU, %": cb.get("voltage_drop_pct"),
                            "Лимит, %": cb.get("du_limit_pct"),
                            "Кабель": f"{cb.get('mark','')} {cb.get('cores','')}×{cb.get('section_mm2','')}мм²",
                            "L расч, м": cb.get("length_m_calc", cb.get("length_m", "")),
                        })
                    if not cb.get("kz_thermal_ok", True):
                        kzt_err.append({
                            "ID": obj_id, "Наименование": obj_name,
                            "Sфакт, мм²": cb.get("section_mm2", "—"),
                            "Sмин, мм²": cb.get("kz_thermal_s_min_mm2", "—"),
                            "Iкз_ист, кА": cb.get("isc_ka_source", "—"),
                        })
                    if not cb.get("kz_sens_ok", True):
                        kzs_err.append({
                            "ID": obj_id, "Наименование": obj_name,
                            "Iкз_конец, А": cb.get("kz_sens_i_end_a"),
                            "Iоткл_мин, А": cb.get("kz_sens_i_trip_min_a"),
                        })

        c1, c2, c3 = st.columns(3)
        c1.metric("Нарушения ΔU",        len(du_err))
        c2.metric("Термо-КЗ",            len(kzt_err))
        c3.metric("Чувствит. защиты",    len(kzs_err))

        with st.expander("Что это значит?"):
            st.markdown(
                "**Нарушения ΔU** — падение напряжения на линии превышает допустимое (обычно 5%). "
                "Решение: увеличить сечение кабеля или уменьшить длину.\n\n"
                "**Термо-КЗ** — сечение кабеля меньше минимального, рассчитанного по термической "
                "стойкости при токе КЗ. Решение: увеличить сечение или проверить isc_ka проекта.\n\n"
                "**Чувствительность защиты** — ток КЗ в конце линии недостаточен для срабатывания "
                "автоматического выключателя. Решение: уменьшить длину линии, увеличить сечение "
                "или выбрать АВ с меньшим током отсечки."
            )
        st.divider()

        if du_err:
            st.error(f"Превышение ΔU — {len(du_err)} линий")
            st.dataframe(du_err, width="stretch", hide_index=True)
        if kzt_err:
            st.warning(f"Термостойкость при КЗ — {len(kzt_err)} линий")
            st.dataframe(kzt_err, width="stretch", hide_index=True)
        if kzs_err:
            st.warning(f"Чувствительность защиты — {len(kzs_err)} линий")
            st.dataframe(kzs_err, width="stretch", hide_index=True)
        if not du_err and not kzt_err and not kzs_err:
            st.success("Нарушений нет")


# ── Вкладка: Изменения ───────────────────────────────────────────────

with tab_changes:
    changes = project.get("changes", [])
    if not changes:
        st.info("Изменений нет (ревизия 0).")
    else:
        st.subheader(f"Журнал изменений (всего: {len(changes)})")
        for ch in reversed(changes):
            with st.expander(
                f"Ред. {ch.get('rev',0)} | {ch.get('date','')} | {ch.get('description','')[:60]}"
            ):
                st.write(f"**Дата:** {ch.get('date','')}")
                st.write(f"**Автор:** {ch.get('author','')}")
                st.write(f"**Описание:** {ch.get('description','')}")
                st.write(f"**Затронуто:** {', '.join(ch.get('affected_docs',[]))}")
                if ch.get("items"):
                    st.json(ch["items"])

    st.divider()
    st.subheader("Зарегистрировать ручное изменение")
    man_desc = st.text_input("Описание изменения")
    man_reason = st.selectbox("Код причины", ["01 — Ошибка", "02 — Замечание экспертизы",
                                               "03 — Изменение задания", "04 — Иное"])
    if st.button("Зарегистрировать изменение", type="secondary"):
        if man_desc:
            from changes.detector import register_change
            updated = register_change(project, description=man_desc,
                                       reason_code=man_reason[:2])
            save_project(updated, proj_dir)
            st.success(f"Зарегистрирована ревизия {updated['project']['revision']}")
            st.rerun()
        else:
            st.warning("Введи описание")


# ── Вкладка: Документы ───────────────────────────────────────────────

with tab_docs:
    docs_dir = proj_dir / "docs"

    # Загрузка сметы/КП
    st.subheader("Импорт из сметы или КП поставщика")
    uploaded = st.file_uploader("Excel-файл сметы или КП", type=["xlsx","xls","csv"])
    if uploaded:
        import tempfile
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=Path(uploaded.name).suffix) as tmp:
                tmp.write(uploaded.read())
                tmp_path = Path(tmp.name)

            from parsers.parse_estimate import parse_file
            items = parse_file(str(tmp_path))

            if items:
                st.success(f"Найдено позиций: {len(items)}")
                st.dataframe(items, use_container_width=True, hide_index=True)
                st.caption("Данные распарсены. Используй их для заполнения спецификации.")
            else:
                st.warning("Позиции не найдены. Проверь формат файла.")
        except Exception as _e:
            st.error(f"Ошибка при чтении файла: {_e}")
        finally:
            if tmp_path and tmp_path.exists():
                tmp_path.unlink(missing_ok=True)

    st.divider()

    # ── Кнопки генерации ─────────────────────────────────────────────
    st.subheader("Генерация документов")
    col_d, col_x, col_a = st.columns(3)

    with col_d:
        if st.button("📄 Сгенерировать DOCX", width="stretch"):
            with st.spinner("Генерация DOCX..."):
                out, err_txt, rc = run_cli(["docs", str(proj_dir), "--format", "docx"])
            if rc == 0:
                st.success("DOCX сгенерированы")
            else:
                st.error(err_txt or out)

    with col_x:
        if st.button("📊 Сгенерировать XLSX", width="stretch"):
            with st.spinner("Генерация XLSX..."):
                out, err_txt, rc = run_cli(["docs", str(proj_dir), "--format", "xlsx"])
            if rc == 0:
                st.success("XLSX сгенерированы")
            else:
                st.error(err_txt or out)

    with col_a:
        if st.button("📦 Оба формата", width="stretch"):
            with st.spinner("Генерация DOCX + XLSX..."):
                out, err_txt, rc = run_cli(["docs", str(proj_dir), "--format", "all"])
            if rc == 0:
                st.success("Все форматы сгенерированы")
            else:
                st.error(err_txt or out)

    st.divider()

    # ── Однолинейные схемы щитов (DXF) ───────────────────────────────
    st.subheader("📐 Однолинейные схемы щитов (DXF)")
    col_sld1, col_sld2 = st.columns(2)
    with col_sld1:
        if st.button("📐 Сгенерировать все схемы (DXF)", key="sld_all"):
            with st.spinner("Генерация DXF..."):
                out, err_txt, rc = run_cli(["sld", str(proj_dir)])
            if rc == 0:
                st.success("Схемы созданы в папке dwg/")
            else:
                st.error(err_txt or out)
    with col_sld2:
        dwg_dir_ui = proj_dir / "dwg"
        dxf_files = sorted(dwg_dir_ui.glob("*_sld.dxf")) if dwg_dir_ui.exists() else []
        if dxf_files:
            sel_name = st.selectbox("Скачать файл", [f.name for f in dxf_files],
                                    key="sld_dl_sel")
            chosen = next((f for f in dxf_files if f.name == sel_name), None)
            if chosen:
                st.download_button("⬇ Скачать DXF", chosen.read_bytes(),
                                   file_name=chosen.name, mime="application/dxf",
                                   key="sld_dl_btn")
        else:
            st.caption("Нажми кнопку генерации — затем здесь появятся файлы для скачивания.")

    st.divider()

    # ── Листинг файлов ───────────────────────────────────────────────
    st.subheader("Сгенерированные документы")

    def _file_row(f: Path, mime: str, icon: str):
        size_kb = f.stat().st_size // 1024
        col_name, col_size, col_dl = st.columns([4, 1, 1])
        col_name.write(f"{icon} {f.name}")
        col_size.write(f"{size_kb} КБ")
        with open(f, "rb") as fh:
            col_dl.download_button(
                "⬇️",
                data=fh.read(),
                file_name=f.name,
                mime=mime,
                key=f"dl_{f.name}",
            )

    if docs_dir.exists():
        docx_files = sorted(docs_dir.glob("*.docx"))
        xlsx_files = sorted(docs_dir.glob("*.xlsx"))

        if docx_files:
            st.markdown("**Word (DOCX)**")
            for f in docx_files:
                _file_row(
                    f,
                    mime="application/vnd.openxmlformats-officedocument"
                         ".wordprocessingml.document",
                    icon="📄",
                )

        if xlsx_files:
            if docx_files:
                st.markdown("")
            st.markdown("**Excel (XLSX)**")
            for f in xlsx_files:
                _file_row(
                    f,
                    mime="application/vnd.openxmlformats-officedocument"
                         ".spreadsheetml.sheet",
                    icon="📊",
                )

        if not docx_files and not xlsx_files:
            st.info("Документов пока нет. Нажми одну из кнопок генерации выше.")
    else:
        st.info("Папка docs/ не создана. Нажми одну из кнопок генерации выше.")
