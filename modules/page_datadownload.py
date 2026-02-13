def render_db_update():
    # --- HEADER & NAVIGACE ---
    col_back, col_title, _ = st.columns([1, 4, 1])
    with col_back:
        # Tlačítko pro návrat do menu
        if st.button("⬅️ Menu", key="db_menu_btn"):
            st.session_state.current_app = "main_menu"
            st.rerun()
    with col_title:
        st.markdown("<h2 style='text-align: center; margin-top: -10px;'>📊 Daktela Export Dat</h2>", unsafe_allow_html=True)
    st.divider()

    # --- INPUTY ---
    
    # 1. Datum
    c1, c2 = st.columns(2)
    d_from = c1.date_input("Datum od (včetně 00:00)", value=date.today() - timedelta(days=7), key="exp_d_from")
    d_to = c2.date_input("Datum do (včetně 23:59)", value=date.today(), key="exp_d_to")

    # 2. Sloupce
    available_fields = ["name", "title", "created", "last_activity", "category", "user"]
    default_fields = ["name", "title", "created", "last_activity"]
    selected_fields = st.multiselect("Vyberte sloupce k exportu", options=available_fields, default=default_fields, key="exp_fields")

    # 3. Kategorie (Načtení a výběr)
    cat_options = {"VŠE (bez filtru)": None}
    
    # Cache pro kategorie, aby se nenačítaly při každém překreslení
    if 'categories_cache' not in st.session_state:
        try:
            cat_res = requests.get(f"{INSTANCE_URL}/api/v6/ticketsCategories.json", headers={'x-auth-token': ACCESS_TOKEN})
            if cat_res.status_code == 200:
                st.session_state['categories_cache'] = {c['title']: c['name'] for c in cat_res.json().get('result', {}).get('data', [])}
        except: pass
    
    if 'categories_cache' in st.session_state:
        cat_options.update(st.session_state['categories_cache'])
    
    selected_cat_label = st.selectbox("Filtr kategorie", options=list(cat_options.keys()), key="exp_cat")
    selected_cat_id = cat_options[selected_cat_label]

    st.divider()

    # --- LOGIKA STAHOVÁNÍ ---
    if st.button("🚀 Načíst data a připravit export", type="primary", use_container_width=True, key="exp_start_btn"):
        if not ACCESS_TOKEN or not INSTANCE_URL:
            st.error("Chybí konfigurace URL nebo Tokenu.")
            st.stop()
            
        status_box = st.status("Zahajuji komunikaci s API...", expanded=True)
        
        all_data = []
        skip = 0
        take = 1000 # Daktela limit
        
        # Sestavení filtrů
        params = {
            "filter[logic]": "and",
            # Filtr 0: Datum OD
            "filter[filters][0][field]": "created",
            "filter[filters][0][operator]": "gte",
            "filter[filters][0][value]": f"{d_from} 00:00:00",
            # Filtr 1: Datum DO
            "filter[filters][1][field]": "created",
            "filter[filters][1][operator]": "lte",
            "filter[filters][1][value]": f"{d_to} 23:59:59",
            "take": take,
            "skip": skip
        }

        # Filtr 2: Kategorie (pokud je vybrána)
        filter_index = 2
        if selected_cat_id:
            params[f"filter[filters][{filter_index}][field]"] = "category"
            params[f"filter[filters][{filter_index}][operator]"] = "eq"
            params[f"filter[filters][{filter_index}][value]"] = selected_cat_id

        # Fields parametry (co chceme za sloupce)
        # Vždy přidáme 'name' pro identifikaci, i kdyby ho uživatel nevybral (ale ve finále ho můžeme skrýt)
        fields_to_request = list(set(selected_fields + ["name"])) 
        for i, field in enumerate(fields_to_request):
            params[f"fields[{i}]"] = field

        # SMYČKA PRO STRÁNKOVÁNÍ
        start_time = time.time()
        while True:
            params['skip'] = skip
            try:
                # Volání API
                resp = requests.get(f"{INSTANCE_URL}/api/v6/tickets.json", params=params, headers={"X-AUTH-TOKEN": ACCESS_TOKEN})
                resp.raise_for_status()
                
                json_data = resp.json()
                result = json_data.get('result', {})
                data_batch = result.get('data', [])
                total_records = result.get('total', 0)
                
                if not data_batch:
                    break
                
                all_data.extend(data_batch)
                
                status_box.write(f"📥 Staženo {len(all_data)} / {total_records} záznamů...")
                
                # Pokud jsme stáhli vše, končíme
                if len(all_data) >= total_records:
                    break
                
                # Jinak posuneme skip o 1000
                skip += take
                time.sleep(0.1) # Malá pauza
                
            except Exception as e:
                status_box.update(label="❌ Chyba při stahování", state="error")
                st.error(f"Chyba API: {str(e)}")
                st.stop()

        status_box.update(label="✅ Data úspěšně stažena", state="complete", expanded=False)
        
        if not all_data:
            st.warning("V daném období nebyla nalezena žádná data.")
        else:
            # Zpracování do DataFrame
            df = pd.DataFrame(all_data)
            
            # Filtrování sloupců podle výběru uživatele
            # (Ošetříme, pokud API vrátilo něco navíc, nebo pokud nějaký sloupec chybí)
            final_cols = [c for c in selected_fields if c in df.columns]
            df = df[final_cols]

            st.success(f"Nalezeno celkem {len(df)} záznamů.")
            
            # Náhled
            with st.expander("👀 Náhled dat (prvních 10 řádků)", expanded=True):
                st.dataframe(df.head(10))
            
            # Export do Excelu (in-memory)
            # Používáme io.BytesIO, abychom neukládali soubor na disk serveru
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False, sheet_name='Report')
            
            file_data = buffer.getvalue()
            
            # Tlačítko pro stažení
            st.download_button(
                label=f"📥 Stáhnout XLSX ({len(df)} řádků)",
                data=file_data,
                file_name=f"daktela_export_{d_from}_{d_to}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary"
            )