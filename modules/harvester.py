import streamlit as st
import requests
import json
import time
import re
from datetime import datetime, timedelta, date
from config import NOISE_PATTERNS, CUT_OFF_PATTERNS, HISTORY_PATTERNS
from utils.helpers import slugify, clean_html, format_date_split, identify_side

# --- CALLBACKY (FUNKCE PRO TLAČÍTKA) ---
def set_date_range(d_from, d_to): st.session_state.filter_date_from = d_from; st.session_state.filter_date_to = d_to
def cb_this_year(): set_date_range(date(date.today().year, 1, 1), date.today())
def cb_last_year(): today = date.today(); last_year = today.year - 1; set_date_range(date(last_year, 1, 1), date(last_year, 12, 31))
def cb_last_half_year():
    today = date.today(); first_of_this_month = today.replace(day=1); last_of_prev_month = first_of_this_month - timedelta(days=1)
    start_month = first_of_this_month.month - 6; start_year = first_of_this_month.year
    if start_month <= 0: start_month += 12; start_year -= 1
    set_date_range(date(start_year, start_month, 1), last_of_prev_month)
def cb_last_3_months():
    today = date.today(); first_of_this_month = today.replace(day=1); last_of_prev_month = first_of_this_month - timedelta(days=1)
    start_month = first_of_this_month.month - 3; start_year = first_of_this_month.year
    if start_month <= 0: start_month += 12; start_year -= 1
    set_date_range(date(start_year, start_month, 1), last_of_prev_month)
def cb_last_month():
    today = date.today(); first_of_this_month = today.replace(day=1); last_of_prev_month = first_of_this_month - timedelta(days=1); first_of_prev_month = last_of_prev_month.replace(day=1)
    set_date_range(first_of_prev_month, last_of_prev_month)
def cb_this_month(): set_date_range(date.today().replace(day=1), date.today())
def cb_last_week():
    today = date.today(); start_of_this_week = today - timedelta(days=today.weekday()); start_of_last_week = start_of_this_week - timedelta(weeks=1); end_of_last_week = start_of_last_week + timedelta(days=6)
    set_date_range(start_of_last_week, end_of_last_week)
def cb_this_week(): today = date.today(); start_of_this_week = today - timedelta(days=today.weekday()); set_date_range(start_of_this_week, today)
def cb_yesterday(): yesterday = date.today() - timedelta(days=1); set_date_range(yesterday, yesterday)

def reset_cat_callback(): st.session_state.sb_category = "VŠE (bez filtru)"; st.session_state.selected_cat_key = "ALL"
def reset_stat_callback(): st.session_state.sb_status = "VŠE (bez filtru)"; st.session_state.selected_stat_key = "ALL"
def get_index(options_dict, current_val_key):
    found_key = next((k for k, v in options_dict.items() if v == current_val_key), "VŠE (bez filtru)")
    try: return list(options_dict.keys()).index(found_key)
    except ValueError: return 0

# --- HLAVNÍ FUNKCE MODULU ---
def render_harvester():
    # Načtení Secrets
    INSTANCE_URL = st.secrets["DAKTELA_URL"]
    ACCESS_TOKEN = st.secrets["DAKTELA_TOKEN"]

    # --- Header ---
    col_back, col_title, col_void = st.columns([1, 4, 1])
    with col_back:
        if st.button("⬅️ Menu"):
            st.session_state.current_app = "dashboard"
            st.session_state.harvester_phase = "filter"
            st.rerun()
    with col_title:
        st.markdown("<h2 style='text-align: center; margin-top: -10px;'>🔎 Analýza ticketů</h2>", unsafe_allow_html=True)
    st.divider()

    # --- Inicializace proměnných ---
    if 'harvester_phase' not in st.session_state: st.session_state.harvester_phase = "filter"
    if 'stop_requested' not in st.session_state: st.session_state.stop_requested = False
    if 'export_data' not in st.session_state: st.session_state.export_data = []
    if 'id_list_txt' not in st.session_state: st.session_state.id_list_txt = ""
    if 'stats' not in st.session_state: st.session_state.stats = {}
    if 'found_tickets' not in st.session_state: st.session_state.found_tickets = [] 
    if 'filter_date_from' not in st.session_state: st.session_state.filter_date_from = date.today()
    if 'filter_date_to' not in st.session_state: st.session_state.filter_date_to = date.today()
    if 'selected_cat_key' not in st.session_state: st.session_state.selected_cat_key = "ALL"
    if 'selected_stat_key' not in st.session_state: st.session_state.selected_stat_key = "ALL"

    # Načtení číselníků
    if 'categories' not in st.session_state:
        try:
            res_cat = requests.get(f"{INSTANCE_URL}/api/v6/ticketsCategories.json", headers={'x-auth-token': ACCESS_TOKEN})
            cat_data = res_cat.json().get('result', {}).get('data', [])
            st.session_state['categories'] = sorted(cat_data, key=lambda x: x.get('title', '').lower())
            res_stat = requests.get(f"{INSTANCE_URL}/api/v6/statuses.json", headers={'x-auth-token': ACCESS_TOKEN})
            stat_data = res_stat.json().get('result', {}).get('data', [])
            st.session_state['statuses'] = sorted(stat_data, key=lambda x: x.get('title', '').lower())
        except: st.error("Chyba číselníků."); st.stop()

    cat_options_map = {"VŠE (bez filtru)": "ALL"}; cat_options_map.update({c['title']: c['name'] for c in st.session_state['categories']})
    stat_options_map = {"VŠE (bez filtru)": "ALL"}; stat_options_map.update({s['title']: s['name'] for s in st.session_state['statuses']})

    # ========================== LOGIKA FÁZÍ ==========================

    # --- FÁZE 3: PROCESSING ---
    if st.session_state.harvester_phase == "processing":
        with st.container(border=True):
            st.info(f"**Právě zpracovávám data pro:**\n\n"
                    f"📅 **Období:** {st.session_state.filter_date_from.strftime('%d.%m.%Y')} - {st.session_state.filter_date_to.strftime('%d.%m.%Y')}\n\n"
                    f"📂 **Kategorie:** {next((k for k,v in cat_options_map.items() if v == st.session_state.selected_cat_key), 'VŠE')}\n\n"
                    f"🏷️ **Status:** {next((k for k,v in stat_options_map.items() if v == st.session_state.selected_stat_key), 'VŠE')}")
        
        st.write(""); st.subheader("3. Probíhá těžba dat..."); st.write("")
        col_stop1, col_stop2, col_stop3 = st.columns([1, 2, 1])
        with col_stop2:
            if st.button("🛑 ZASTAVIT PROCES", use_container_width=True):
                st.session_state.stop_requested = True; st.session_state.harvester_phase = "selection"; st.rerun()

        progress_bar = st.progress(0); status_text = st.empty(); eta_text = st.empty()
        
        combined_cut_regex = re.compile("|".join(CUT_OFF_PATTERNS + HISTORY_PATTERNS), re.IGNORECASE | re.MULTILINE)
        tickets_to_process = st.session_state.found_tickets
        if st.session_state.final_limit > 0: tickets_to_process = tickets_to_process[:st.session_state.final_limit]

        full_export_data = []; start_time = time.time(); total_count = len(tickets_to_process)

        for idx, t_obj in enumerate(tickets_to_process):
            if st.session_state.stop_requested: break
            t_num = t_obj.get('name')
            status_text.markdown(f"📥 Zpracovávám ticket **{idx + 1}/{total_count}**: `{t_num}`")
            try:
                acts = []
                for attempt in range(3):
                    try:
                        res_act = requests.get(f"{INSTANCE_URL}/api/v6/tickets/{t_num}/activities.json", headers={'X-AUTH-TOKEN': ACCESS_TOKEN}, timeout=30)
                        res_act.raise_for_status()
                        acts = res_act.json().get('result', {}).get('data', [])
                        break
                    except: time.sleep(1)
                
                t_date, t_time = format_date_split(t_obj.get('created'))
                t_status = t_obj.get('statuses', [{}])[0].get('title', 'N/A') if isinstance(t_obj.get('statuses'), list) and t_obj.get('statuses') else "N/A"
                custom_fields = t_obj.get('customFields', {})
                vip_list = custom_fields.get('vip', [])
                ticket_clientType = "VIP" if "→ VIP KLIENT ←" in vip_list else "Standard"
                
                ticket_entry = {"ticket_number": t_num, "ticket_name": t_obj.get('title', 'Bez předmětu'), "ticket_clientType": ticket_clientType, "ticket_category": t_obj.get('category', {}).get('title', 'N/A') if t_obj.get('category') else "N/A", "ticket_status": t_status, "ticket_creationDate": t_date, "ticket_creationTime": t_time, "activities": []}

                for a_idx, act in enumerate(sorted(acts, key=lambda x: x.get('time', '')), 1):
                    item = act.get('item') or {}; address = item.get('address', '')
                    cleaned = clean_html(item.get('text') or act.get('description'))
                    if not cleaned: continue
                    if any(re.search(p, cleaned, re.IGNORECASE) for p in NOISE_PATTERNS): cleaned = "[AUTOMATICKÝ EMAIL BALÍKOBOTU]"
                    else:
                        match = combined_cut_regex.search(cleaned)
                        if match: cleaned = cleaned[:match.start()].strip() + "\n\n[PODPIS]"
                    u_title = (act.get('user') or {}).get('title'); c_title = (act.get('contact') or {}).get('title'); direction = item.get('direction', 'out')
                    if direction == "in": sender = identify_side(c_title, address, is_user=False); recipient = "Balíkobot"
                    else: sender = identify_side(u_title, "", is_user=True); recipient = identify_side(c_title, address, is_user=False)
                    a_date, a_time = format_date_split(act.get('time')); act_type = act.get('type') or "COMMENT"
                    act_data = {"activity_number": a_idx, "activity_type": act_type, "activity_sender": sender}
                    if act_type != "COMMENT": act_data["activity_recipient"] = recipient
                    act_data.update({"activity_creationDate": a_date, "activity_creationTime": a_time, "activity_text": cleaned})
                    ticket_entry["activities"].append(act_data)
                full_export_data.append(ticket_entry)
            except Exception: pass
            
            progress_bar.progress((idx + 1) / total_count)
            elapsed = time.time() - start_time
            if idx > 0:
                avg_per_item = elapsed / (idx + 1); remaining_sec = (total_count - (idx + 1)) * avg_per_item
                eta_text.caption(f"⏱️ Zbývá cca: {int(remaining_sec)} sekund")

        final_ids_list = "SEZNAM ZPRACOVANÝCH ID\nDatum těžby: {}\n------------------------------\n".format(datetime.now().strftime('%d.%m.%Y %H:%M'))
        final_ids_list += "\n".join([str(t['ticket_number']) for t in full_export_data])
        st.session_state.stats = {"tickets": len(full_export_data), "activities": sum(len(t['activities']) for t in full_export_data), "size": f"{len(json.dumps(full_export_data).encode('utf-8')) / 1024:.1f} KB"}
        st.session_state.export_data = full_export_data; st.session_state.id_list_txt = final_ids_list
        st.session_state.harvester_phase = "results"; st.rerun()

    # --- FÁZE 4: RESULTS ---
    elif st.session_state.harvester_phase == "results":
        st.success("🎉 Těžba dokončena!")
        st.info(f"**Použitý filtr:**\n\n"
                f"📅 **Období:** {st.session_state.filter_date_from.strftime('%d.%m.%Y')} - {st.session_state.filter_date_to.strftime('%d.%m.%Y')}\n\n"
                f"📂 **Kategorie:** {next((k for k,v in cat_options_map.items() if v == st.session_state.selected_cat_key), 'VŠE')}\n\n"
                f"🏷️ **Status:** {next((k for k,v in stat_options_map.items() if v == st.session_state.selected_stat_key), 'VŠE')}")
        s = st.session_state.stats
        c1, c2, c3 = st.columns(3)
        c1.metric("Zpracováno ticketů", s["tickets"]); c2.metric("Nalezeno aktivit", s["activities"]); c3.metric("Velikost dat", s["size"])
        st.write("")
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        c_name = "VSE" if st.session_state.selected_cat_key == "ALL" else slugify(next((k for k,v in cat_options_map.items() if v == st.session_state.selected_cat_key), "cat"))
        s_name = "VSE" if st.session_state.selected_stat_key == "ALL" else slugify(next((k for k,v in stat_options_map.items() if v == st.session_state.selected_stat_key), "stat"))
        json_data = json.dumps(st.session_state.export_data, ensure_ascii=False, indent=2)
        col_dl1, col_dl2 = st.columns(2)
        with col_dl1: st.download_button(label="💾 STÁHNOUT JSON DATA", data=json_data, file_name=f"data_{c_name}_{s_name}_{ts}.json", mime="application/json", use_container_width=True)
        with col_dl2: st.download_button(label="🆔 STÁHNOUT SEZNAM ID", data=st.session_state.id_list_txt, file_name=f"tickets_{c_name}_{s_name}_{ts}.txt", mime="text/plain", use_container_width=True)
        st.write("")
        if st.button("🔄 Začít znovu / Nová analýza", type="primary", use_container_width=True):
            st.session_state.harvester_phase = "filter"; st.rerun()
        st.markdown("**Náhled dat (první ticket):**")
        st.code(json.dumps(st.session_state.export_data[0] if st.session_state.export_data else {}, ensure_ascii=False, indent=2), language="json")

    # --- FÁZE 2: SELECTION ---
    elif st.session_state.harvester_phase == "selection":
        col_x1, col_x2, col_x3 = st.columns([1, 2, 1])
        with col_x2:
            if st.button("❌ Zavřít výsledky a upravit zadání", use_container_width=True):
                st.session_state.harvester_phase = "filter"; st.rerun()
        st.subheader("2. Výsledek hledání")
        count = len(st.session_state.found_tickets)
        if count == 0: st.warning("⚠️ V zadaném období a nastavení nebyly nalezeny žádné tickety.")
        else:
            st.success(f"✅ Nalezeno **{count}** ticketů.")
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            c_name = "VSE" if st.session_state.selected_cat_key == "ALL" else slugify(next((k for k,v in cat_options_map.items() if v == st.session_state.selected_cat_key), "cat"))
            s_name = "VSE" if st.session_state.selected_stat_key == "ALL" else slugify(next((k for k,v in stat_options_map.items() if v == st.session_state.selected_stat_key), "stat"))
            found_ids = "\n".join([str(t.get('name', '')) for t in st.session_state.found_tickets])
            col_d1, col_d2, col_d3 = st.columns([1, 2, 1])
            with col_d2: st.download_button(label="⬇️ Stáhnout nalezená ID (TXT)", data=found_ids, file_name=f"tickets_{c_name}_{s_name}_{ts}.txt", mime="text/plain", use_container_width=True)
            st.write(""); st.write("Kolik ticketů chcete hloubkově zpracovat?")
            limit_val = st.number_input("Limit (0 = zpracovat všechny nalezené)", min_value=0, max_value=count, value=min(count, 50))
            st.write("")
            if st.button("⛏️ SPUSTIT ZPRACOVÁNÍ DAT", type="primary", use_container_width=True):
                st.session_state.final_limit = limit_val; st.session_state.stop_requested = False; st.session_state.harvester_phase = "processing"; st.rerun()

    # --- FÁZE 1: FILTER (DEFAULT) ---
    else:
        with st.container():
            st.subheader("1. Nastavení filtru")
            st.markdown("<h2 style='text-align: center; margin-top: -10px; font-size: 16px;'>📅 Datum</h3>", unsafe_allow_html=True)
            c_date1, c_date2 = st.columns(2)
            with c_date1: d_from = st.date_input("Od", key="filter_date_from", format="DD.MM.YYYY")
            with c_date2: d_to = st.date_input("Do", key="filter_date_to", format="DD.MM.YYYY")
            st.caption("Rychlý výběr období:")
            b_r1 = st.columns(3); b_r1[0].button("Tento rok", use_container_width=True, on_click=cb_this_year); b_r1[1].button("Minulý rok", use_container_width=True, on_click=cb_last_year); b_r1[2].button("Poslední půl rok", use_container_width=True, on_click=cb_last_half_year)
            b_r2 = st.columns(3); b_r2[0].button("Poslední 3 měsíce", use_container_width=True, on_click=cb_last_3_months); b_r2[1].button("Minulý měsíc", use_container_width=True, on_click=cb_last_month); b_r2[2].button("Tento měsíc", use_container_width=True, on_click=cb_this_month)
            b_r3 = st.columns(3); b_r3[0].button("Minulý týden", use_container_width=True, on_click=cb_last_week); b_r3[1].button("Tento týden", use_container_width=True, on_click=cb_this_week); b_r3[2].button("Včerejšek", use_container_width=True, on_click=cb_yesterday)
            st.divider()
            st.markdown("<h2 style='text-align: center; margin-top: -10px; font-size: 16px;'>Kategorie & Status</h3>", unsafe_allow_html=True)
            c_filt1, c_filt2 = st.columns(2)
            with c_filt1:
                cat_idx = get_index(cat_options_map, st.session_state.selected_cat_key)
                sel_cat_label = st.selectbox("📂 Kategorie", options=list(cat_options_map.keys()), index=cat_idx, key="sb_category")
                st.session_state.selected_cat_key = cat_options_map[sel_cat_label]
                st.button("Vybrat vše (Kategorie)", use_container_width=True, on_click=reset_cat_callback)
            with c_filt2:
                stat_idx = get_index(stat_options_map, st.session_state.selected_stat_key)
                sel_stat_label = st.selectbox("🏷️ Status", options=list(stat_options_map.keys()), index=stat_idx, key="sb_status")
                st.session_state.selected_stat_key = stat_options_map[sel_stat_label]
                st.button("Vybrat vše (Status)", use_container_width=True, on_click=reset_stat_callback)
            st.write("")
            if st.button("🔍 VYHLEDAT TICKETY", type="primary", use_container_width=True):
                params = {"filter[logic]": "and", "filter[filters][0][field]": "created", "filter[filters][0][operator]": "gte", "filter[filters][0][value]": f"{st.session_state.filter_date_from} 00:00:00", "filter[filters][1][field]": "created", "filter[filters][1][operator]": "lte", "filter[filters][1][value]": f"{st.session_state.filter_date_to} 23:59:59", "fields[0]": "name", "fields[1]": "title", "fields[2]": "created", "fields[3]": "customFields", "fields[4]": "category", "fields[5]": "statuses"}
                filter_idx = 2
                if st.session_state.selected_cat_key != "ALL": params[f"filter[filters][{filter_idx}][field]"] = "category"; params[f"filter[filters][{filter_idx}][operator]"] = "eq"; params[f"filter[filters][{filter_idx}][value]"] = st.session_state.selected_cat_key; filter_idx += 1
                if st.session_state.selected_stat_key != "ALL": params[f"filter[filters][{filter_idx}][field]"] = "statuses"; params[f"filter[filters][{filter_idx}][operator]"] = "eq"; params[f"filter[filters][{filter_idx}][value]"] = st.session_state.selected_stat_key; filter_idx += 1
                
                with st.spinner("Prohledávám databázi..."):
                    try:
                        all_tickets = []; params["take"] = 1000; params["skip"] = 0
                        while True:
                            res = requests.get(f"{INSTANCE_URL}/api/v6/tickets.json", params=params, headers={'X-AUTH-TOKEN': ACCESS_TOKEN})
                            data = res.json().get('result', {}).get('data', [])
                            if not data: break
                            all_tickets.extend(data)
                            if len(data) < 1000: break
                            params["skip"] += 1000
                        st.session_state.found_tickets = all_tickets
                        st.session_state.harvester_phase = "selection"
                        st.rerun()
                    except Exception as e: st.error(f"Chyba: {e}")