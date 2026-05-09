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
        capture_output=True, text=True, cwd=str(ROOT)
    )
    # Убираем ANSI-коды
    import re
    ansi = re.compile(r"\033\[[0-9;]*m")
    return ansi.sub("", proc.stdout), ansi.sub("", proc.stderr), proc.returncode


# ── Сайдбар ──────────────────────────────────────────────────────────

with st.sidebar:
    st.title("⚡ ЭлектроПроект")
    st.caption("Система автоматизации")
    st.divider()

    projects = get_all_projects()
    st.subheader(f"Объекты ({len(projects)})")

    selected_dir = None
    for d, p in projects:
        proj_info = p.get("project", {})
        calc_done = p.get("_meta", {}).get("calc_done", False)
        icon = "✅" if calc_done else "🔲"
        label = f"{icon} **{proj_info.get('code','?')}** {proj_info.get('name','')[:25]}"
        if st.button(label, key=str(d), width="stretch"):
            st.session_state["active_project"] = str(d)

    st.divider()
    if st.button("➕ Новый объект", width="stretch"):
        st.session_state["show_new_form"] = True


# ── Новый проект ────────────────────────────────────────────────────

if st.session_state.get("show_new_form"):
    st.header("Новый объект")
    col1, col2 = st.columns(2)
    with col1:
        new_code = st.text_input("Код объекта", placeholder="ОБЪ-2025-001")
    with col2:
        new_name = st.text_input("Название", placeholder="Офисное здание по ул. Ленина")

    if st.button("Создать", type="primary"):
        if new_code and new_name:
            out, err, rc = run_cli(["new", new_code, new_name])
            if rc == 0:
                st.success(f"Создан: {new_code}")
                st.session_state["show_new_form"] = False
                st.rerun()
            else:
                st.error(f"Ошибка: {err}")
        else:
            st.warning("Заполни код и название")
    if st.button("Отмена"):
        st.session_state["show_new_form"] = False
        st.rerun()
    st.stop()


# ── Главный экран ───────────────────────────────────────────────────

active_path = st.session_state.get("active_project")

if not active_path:
    st.title("⚡ ЭлектроПроект")
    st.markdown("Система автоматизации проектной документации по электроснабжению")
    st.divider()

    # Сводная таблица всех объектов
    if projects:
        st.subheader("Все объекты")
        cols = st.columns([2, 3, 1, 1, 1, 1])
        cols[0].markdown("**Код**")
        cols[1].markdown("**Название**")
        cols[2].markdown("**Стадия**")
        cols[3].markdown("**Pуст, кВт**")
        cols[4].markdown("**Iвру, А**")
        cols[5].markdown("**Статус**")
        st.divider()

        for d, p in projects:
            proj = p.get("project", {})
            res = p.get("_results", {}).get("summary", {})
            calc_done = p.get("_meta", {}).get("calc_done", False)
            c = st.columns([2, 3, 1, 1, 1, 1])
            c[0].write(proj.get("code",""))
            c[1].write(proj.get("name","")[:35])
            c[2].write(proj.get("stage",""))
            c[3].write(f"{res.get('p_installed_kw','-')}" if calc_done else "—")
            c[4].write(f"{res.get('i_vru_a','-')}" if calc_done else "—")
            c[5].write("✅ Рассчитан" if calc_done else "🔲 Ожидает")
    else:
        st.info("Нет объектов. Создай первый через кнопку в сайдбаре.")
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

# Шапка
col_title, col_btns = st.columns([3, 1])
with col_title:
    st.title(f"⚡ {proj.get('name','')}")
    st.caption(f"Код: {proj.get('code','')} | Стадия: {proj.get('stage','')} | "
               f"Ред. {proj.get('revision',0)} | {proj.get('date','')}")

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
    else:
        st.warning("Проект ещё не рассчитан. Нажми **Пересчитать всё**.")


# ── Вкладка: Данные ──────────────────────────────────────────────────

with tab_data:
    sub_consumers, sub_settings, sub_json = st.tabs([
        "👥 Потребители", "⚙️ Настройки щитов", "{ } JSON"
    ])

    # ── Суб-вкладка: Потребители ──────────────────────────────────────
    with sub_consumers:
        import pandas as pd

        CONSUMER_TYPES  = ["lighting", "power", "hvac", "it", "other"]
        INSTALL_OPTIONS = ["лоток", "труба", "открыто", "земля"]

        # Список всех щитов из vru.feeders[].panels[]
        panel_options = []
        for _fi, _feeder in enumerate(project.get("vru", {}).get("feeders", [])):
            for _pi, _panel in enumerate(_feeder.get("panels", [])):
                _label = (f"{_feeder.get('id','?')} / {_panel.get('id','?')}"
                          f" — {_panel.get('name','')}")
                panel_options.append((_label, _fi, _pi))

        if not panel_options:
            st.warning("Щиты не найдены. Заполни структуру проекта во вкладке «{ } JSON».")
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
                for _, row in edited_df.iterrows():
                    cid = str(row.get("id", "")).strip()
                    if not cid or cid == "nan":
                        continue
                    old = next((c for c in consumers if c.get("id") == cid), {})
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
                # Обновить cable выбранного потребителя
                if c_idx is not None and new_mark is not None:
                    target_id = consumers[c_idx].get("id")
                    target = next(
                        (nc for nc in new_consumers if nc["id"] == target_id), None
                    )
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
        all_panels_data = []
        for _feeder in project.get("vru", {}).get("feeders", []):
            for _panel in _feeder.get("panels", []):
                _pc = _panel.get("cable", {})
                all_panels_data.append({
                    "Фидер":        _feeder.get("id", ""),
                    "ID щита":      _panel.get("id", ""),
                    "Название":     _panel.get("name", ""),
                    "Этаж":         _panel.get("floor", ""),
                    "Марка кабеля": _pc.get("mark", ""),
                    "L, м":         _pc.get("length_m", ""),
                    "Сечение, мм²": _pc.get("section_mm2", ""),
                    "Потребителей": len(_panel.get("consumers", [])),
                })
        if all_panels_data:
            st.subheader("Щиты проекта")
            st.caption("Только чтение. Для изменения параметров щита используй «{ } JSON».")
            st.dataframe(all_panels_data, use_container_width=True, hide_index=True)
        else:
            st.info("Щиты не найдены в project.json.")

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
        vru_r = results.get("vru", {})
        for feeder in vru_r.get("feeders", []):
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


# ── Вкладка: Кабели ─────────────────────────────────────────────────

with tab_cables:
    if not calc_done or not results:
        st.warning("Нет результатов расчёта.")
    else:
        vru_r = results.get("vru", {})
        du_err, kzt_err, kzs_err = [], [], []

        for feeder in vru_r.get("feeders", []):
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
                            "Sфакт, мм²": cb.get("section_mm2"),
                            "Sмин, мм²": cb.get("kz_thermal_s_min_mm2"),
                            "Iкз_ист, кА": cb.get("isc_ka_source"),
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
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(uploaded.name).suffix) as tmp:
            tmp.write(uploaded.read())
            tmp_path = Path(tmp.name)

        from parsers.parse_estimate import parse_file, print_parsed_items
        import io
        items = parse_file(str(tmp_path))

        if items:
            st.success(f"Найдено позиций: {len(items)}")
            st.dataframe(items, width="stretch", hide_index=True)
            st.caption("Данные распарсены. Используй их для заполнения спецификации.")
        else:
            st.warning("Позиции не найдены. Проверь формат файла.")

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
