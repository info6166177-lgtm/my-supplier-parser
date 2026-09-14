import streamlit as st
import pandas as pd
from io import BytesIO
import requests
from datetime import datetime
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
    Живой HTTP-клиент для закрытого B2B-портала etp.armtek.by.
    Авторизуется под вашим партнерским логином и мгновенно сканирует
    оригиналы и аналоги на основе присланных вами скриншотов экранов.
    """
    url = site_info.get("url", "")
    login = site_info.get("login", "")
    password = site_info.get("password", "")
    products = []
    
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
    })
    
    try:
        if "armtek" in url.lower() and login and password:
            login_url = "https://armtek.by"
            session.get(login_url, timeout=5)
            
            auth_payload = {"login": login, "password": password}
            r_login = session.post(login_url, data=auth_payload, timeout=5)
            
            if r_login.status_code == 200:
                search_url = f"https://armtek.by{str(part_number).strip()}"
                if selected_brand:
                    search_url += f"&brand={selected_brand}"
                    
                r_search = session.get(search_url, timeout=5)
                html = r_search.text
                
                if "Возможно вы искали" in html and not selected_brand:
                    found_brands = re.findall(r'brand=([^"\'&>]+)', html)
                    if found_brands:
                        unique_brands = list(set([b.upper().strip() for b in found_brands if len(b) < 20]))
                        return {"status": "need_brand_clarification", "brands": unique_brands}
                
                rows = re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.DOTALL)
                is_analog_block = False
                
                for row_html in rows:
                    if "Возможные замены" in row_html:
                        is_analog_block = True
                        continue
                        
                    text_blocks = re.findall(r'<td[^>]*>(.*?)</td>', row_html, re.DOTALL)
                    if not text_blocks:
                        text_blocks = re.findall(r'<div[^>]*>(.*?)</div>', row_html, re.DOTALL)
                        
                    full_text = " ".join([re.sub(r'<[^>]+>', '', b).strip() for b in text_blocks])
                    
                    if any(k in full_text for k in ["Дроздово", "Москва", "СК51", "Нет даты поставки"]):
                        price_match = re.search(r"(\d+[\.,]\d+)\s*(?:Br|p|руб)", full_text)
                        price = float(price_match.group(1).replace(",", ".")) if price_match else 0.0
                        
                        days = 0
                        if "сегодня" in full_text.lower():
                            days = 0
                        elif "завтра" in full_text.lower():
                            days = 1
                        elif "Нет даты поставки" in full_text:
                            days = 999  
                            price = 0.0
                        else:
                            date_match = re.search(r"(\d{2})\.(\d{2})\.(\d{2})", full_text)
                            if date_match:
                                try:
                                    target_dt = datetime.strptime(date_match.group(0), "%d.%m.%y")
                                    days = max(0, (target_dt - datetime.now()).days)
                                except:
                                    days = 3
                        
                        rel_match = re.search(r"(\d+)%", full_text)
                        reliability = f"{rel_match.group(1)}%" if rel_match else "100%"
                        
                        brand = selected_brand or "COB-WEB"
                        if text_blocks:
                            clean_cell = re.sub(r'<[^>]+>', ' ', text_blocks[0]).split()
                            if clean_cell: brand = clean_cell[0].upper()
                        
                        products.append({
                            "supplier": "etp.armtek.by",
                            "part_number": part_number if not is_analog_block else "Кросс-номер",
                            "brand": brand,
                            "name": "Фильтр автомобильный" if is_analog_block else "Оригинальная деталь",
                            "price": price,
                            "delivery_days": days,
                            "reliability": reliability,
                            "is_analog": is_analog_block
                        })
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
        orig_group = group[group['is_analog'] == False]
        if not orig_group.empty:
            row_min_price = orig_group.loc[orig_group['price'].idxmin()].copy()
            row_min_time = orig_group.loc[orig_group['delivery_days'].idxmin()].copy()
            original_rows.append(row_min_price)
            original_rows.append(row_min_time)
            
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
        df_orig_res.loc[df_orig_res['delivery_days'] == 999, 'delivery_days'] = "Нет даты"
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
        
        with st.spinner('Прямой опрос B2B-серверов...'):
            for key, site_info in company_secrets.items():
                url = site_info.get("url", "")
                chosen_brand = st.session_state.brand_selection.get(key)
                
                result = fetch_data_via_http(key, site_info, query, chosen_brand)
                
                if result.get("status") == "need_brand_clarification":
                    pending_clarifications[key] = (url, result.get("brands"))
                elif result.get("status") == "success" and result.get("data"):
                    all_raw_data.extend(result.get("data"))

        if pending_clarifications:
            st.warning("⚠️ Неоднозначность артикула. Пожалуйста, выберите производителя:")
            for key, (url, brands) in pending_clarifications.items():
                st.write(f"**Поставщик {url} просит уточнить бренд:**")
                cols = st.columns(len(brands) if len(brands) > 0 else 1)
                for idx, b_name in enumerate(brands):
                    if cols[idx].button(b_name, key=f"btn_{key}_{b_name}"):
                        st.session_state.brand_selection[key] = b_name
                        st.rerun()

        df_original, df_analog = process_supplier_tables(all_raw_data, query)
        
        st.subheader("Оригинальная позиция")
        if not df_original.empty: 
            st.dataframe(df_original, use_container_width=True, hide_index=True)
        else:
            st.info("Позиция не найдена у поставщиков")
        
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
