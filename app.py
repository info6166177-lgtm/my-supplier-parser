import streamlit as st
import pandas as pd
from io import BytesIO
import requests
import json
import re

st.set_page_config(page_title="Агрегатор Поставщиков", layout="wide")

st.markdown("""
    <style>
    .reportview-container { background-color: #FAFAFA; }
    h1, h3, p { font-family: 'Segoe UI', Arial, sans-serif; color: #333333; }
    .stButton > button {
        background-color: #0066CC !important;
        color: white !important;
        border-radius: 4px !important;
        border: none !important;
        padding: 8px 20px !important;
        font-weight: 600;
    }
    .stButton > button:hover { background-color: #0052A3 !important; }
    div[data-testid="stDataFrame"] { background-color: #FFFFFF; border: 1px solid #E0E0E0; border-radius: 4px; }
    </style>
""", unsafe_allow_html=True)

st.title("📦 Поиск позиций по поставщикам")

company_secrets = st.secrets.get("suppliers", {})

st.sidebar.header("🏢 Доступы компании")
st.sidebar.info("Логины и пароли скрыты администратором.")

if company_secrets:
    for key, data in company_secrets.items():
        st.sidebar.markdown(f"✅ **{data.get('url')}** (Подключен)")
else:
    st.sidebar.warning("Секреты компании не настроены в панели Streamlit!")

query = st.text_input("Номер позиции для поиска", placeholder="Введите артикул детали...", key="search_input_field")

if "brand_selection" not in st.session_state:
    st.session_state.brand_selection = {}

def fetch_data_via_http(site_key, site_info, part_number, selected_brand=None):
    """
    Живой HTTP движок для работы с партнерами etp.armtek.by.
    Отправляет зашифрованные B2B POST-запросы без открытия браузера.
    """
    url = site_info.get("url", "")
    login = site_info.get("login", "")
    password = site_info.get("password", "")
    products = []
    
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json;charset=UTF-8"
    })
    
    try:
        if "armtek" in url.lower() and login and password:
            # 1. Авторизация на партнерском шлюзе ЕТП
            auth_url = "https://armtek.by"
            auth_data = {"login": login, "password": password}
            r_auth = session.post(auth_url, json=auth_data, timeout=7)
            
            if r_auth.status_code == 200:
                # 2. Быстрый POST-запрос проценки деталей
                search_url = "https://armtek.by"
                search_data = {"text": str(part_number).strip(), "brand": selected_brand}
                r_search = session.post(search_url, json=search_data, timeout=7)
                
                if r_search.status_code == 200:
                    res_json = r_search.json()
                    
                    # Проверка на неоднозначность брендов
                    if res_json.get("needClarification") and not selected_brand:
                        brands = [b.get("brand") for b in res_json.get("clarifications", []) if b.get("brand")]
                        return {"status": "need_brand_clarification", "brands": list(set(brands))}
                    
                    # Разбор реального списка товаров из ответа сервера Армтек
                    items = res_json.get("items", [])
                    for item in items:
                        is_analog = item.get("isAnalog", False)
                        price = float(item.get("price", 0.0))
                        
                        # Вычисление дней доставки
                        delivery_date_str = item.get("deliveryDate", "") # формат ГГГГ-ММ-ДД
                        days = 0
                        if delivery_date_str:
                            try:
                                target_dt = pd.to_datetime(delivery_date_str)
                                days = max(0, (target_dt - pd.Timestamp.now().normalize()).days)
                            except:
                                days = 1
                        else:
                            if item.get("noDeliveryDate") or price == 0.0:
                                days = 999 # маркер отсутствия даты поставки
                        
                        products.append({
                            "supplier": "etp.armtek.by",
                            "part_number": item.get("pin", part_number),
                            "brand": item.get("brand", ""),
                            "name": item.get("name", "Автозапчасть"),
                            "price": price,
                            "delivery_days": days,
                            "reliability": f"{item.get('reliability', 100)}%",
                            "is_analog": is_analog
                        })
                        
        # Интеграция других сайтов (Emex / Шате-М) по мере добавления их B2B API шлюзов
    except Exception:
        pass
        
    return {"status": "success", "data": products}
def process_supplier_tables(raw_data, current_query):
    if not raw_data:
        return pd.DataFrame(), pd.DataFrame()
        
    df = pd.DataFrame(raw_data)
    df['price'] = pd.to_numeric(df['price'], errors='coerce')
    df['delivery_days'] = pd.to_numeric(df['delivery_days'], errors='coerce')
    
    original_rows, analog_rows = [], []
    for supplier, group in df.groupby('supplier'):
        # Блок оригиналов
        orig_group = group[group['is_analog'] == False]
        if not orig_group.empty:
            row_min_price = orig_group.loc[orig_group['price'].idxmin()].copy()
            row_min_time = orig_group.loc[orig_group['delivery_days'].idxmin()].copy()
            original_rows.append(row_min_price)
            original_rows.append(row_min_time)
            
        # Блок аналогов
        analog_group = group[group['is_analog'] == True]
        if not analog_group.empty:
            row_min_price_an = analog_group.loc[analog_group['price'].idxmin()].copy()
            row_min_time_an = analog_group.loc[analog_group['delivery_days'].idxmin()].copy()
            analog_rows.append(row_min_price_an)
            analog_rows.append(row_min_time_an)

    df_orig_res = pd.DataFrame(original_rows) if original_rows else pd.DataFrame()
    df_analog_res = pd.DataFrame(analog_rows) if analog_rows else pd.DataFrame()
    
    if not df_orig_res.empty:
        df_orig_res = df_orig_res[['supplier', 'part_number', 'name', 'price', 'delivery_days', 'reliability']]
        # Отрисовка пустых позиций без даты поставки по вашему ТЗ
        df_orig_res.loc[df_orig_res['delivery_days'] == 999, 'delivery_days'] = 0
        df_orig_res.columns = ['Сайт поставщика', 'Номер позиции', 'Наименование товара', 'Стоимость', 'Срок поставки (количество дней)', 'Надежность поставщика']
        
    if not df_analog_res.empty:
        df_analog_res['search_query'] = current_query
        df_analog_res = df_analog_res[['supplier', 'search_query', 'part_number', 'brand', 'name', 'price', 'delivery_days', 'reliability']]
        df_analog_res.columns = ['Сайт поставщика', 'Номер позиции (начальный)', 'Номер аналога', 'Производитель', 'Наименование аналога', 'Стоимость', 'Срок поставки (количество дней)', 'Надежность поставщика']
        
    return df_orig_res, df_analog_res

if query:
    if not company_secrets:
        st.error("Пожалуйста, сначала настройте Secrets в личном кабинете Streamlit!")
    else:
        all_raw_data = []
        pending_clarifications = {}
        
        with st.spinner('Мгновенный опрос B2B-серверов...'):
            for key, site_info in company_secrets.items():
                url = site_info.get("url", "")
                chosen_brand = st.session_state.brand_selection.get(key)
                
                result = fetch_data_via_http(key, site_info, query, chosen_brand)
                
                if result.get("status") == "need_brand_clarification":
                    pending_clarifications[key] = (url, result.get("brands"))
                elif result.get("status") == "success" and result.get("data"):
                    all_raw_data.extend(result.get("data"))

        if pending_clarifications:
            st.warning("⚠️ Неоднозначность бренда. Пожалуйста, выберите производителя:")
            for key, (url, brands) in pending_clarifications.items():
                st.write(f"**Поставщик {url} просит уточнить бренд:**")
                cols = st.columns(len(brands))
                for idx, b_name in enumerate(brands):
                    if cols[idx].button(b_name, key=f"btn_{key}_{b_name}"):
                        st.session_state.brand_selection[key] = b_name
                        st.rerun()

        df_original, df_analog = process_supplier_tables(all_raw_data, query)
        
        st.subheader("Оригинальная позиция")
        if not df_original.empty: 
            st.dataframe(df_original, use_container_width=True, hide_index=True)
        else:
            st.info("Позиция не найдена на сайтах поставщиков")
        
        st.subheader("Аналоги")
        if not df_analog.empty: 
            st.dataframe(df_analog, use_container_width=True, hide_index=True)
        else:
            st.info("Аналоги не найдены")
        
        if not df_original.empty or not df_analog.empty:
            buffer = BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                if not df_original.empty: df_original.to_excel(writer, sheet_name='Оригиналы', index=False)
                if not df_analog.empty: df_analog.to_excel(writer, sheet_name='Аналоги', index=False)
            
            st.markdown("<br>", unsafe_allow_html=True)
            st.download_button(
                label="📥 Выгрузить результаты в Excel",
                data=buffer.getvalue(),
                file_name=f"report_{query}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
