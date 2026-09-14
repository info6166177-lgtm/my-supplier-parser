import streamlit as st
import pandas as pd
from io import BytesIO

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

# Боковая панель для ввода данных (Адрес, Логин, Пароль строго по вашему ТЗ)
st.sidebar.header("🔐 Авторизация у поставщиков")

with st.sidebar.expander("Армтек", expanded=False):
    armtek_url = st.text_input("Адрес сайта / API Армтек", value="https://armtek.by", key="arm_u")
    armtek_login = st.text_input("Логин Армтек", key="arm_l")
    armtek_pass = st.text_input("Пароль Армтек", type="password", key="arm_p")

with st.sidebar.expander("Шате-М", expanded=False):
    shate_url = st.text_input("Адрес сайта / API Шате-М", value="https://shate-m.by", key="sh_u")
    shate_login = st.text_input("Логин Шате-М", key="sh_l")
    shate_pass = st.text_input("Пароль Шате-М", type="password", key="sh_p")

with st.sidebar.expander("Эмикс", expanded=False):
    emex_url = st.text_input("Адрес сайта / API Эмикс", value="https://emex.ru", key="em_u")
    emex_login = st.text_input("Логин Эмикс", key="em_l")
    emex_pass = st.text_input("Пароль Эмикс", type="password", key="em_p")

with st.sidebar.expander("Сфера", expanded=False):
    sfera_url = st.text_input("Адрес сайта / API Сфера", key="sf_u")
    sfera_login = st.text_input("Логин Сфера", key="sf_l")
    sfera_pass = st.text_input("Пароль Сфера", type="password", key="sf_p")

query = st.text_input("Номер позиции для поиска", placeholder="Введите артикул детали...")

def fetch_raw_data_from_suppliers(part_number):
    # Модель реальных данных на основе присланного вами поиска Armtek.by по артикулу 01020045b
    return [
        # Оригиналы CORTECO
        {"supplier": "Армтек", "part_number": "01020045B", "brand": "CORTECO", "price": 31.50, "delivery_days": 3, "is_analog": False, "search_query": part_number},
        {"supplier": "Армтек", "part_number": "01020045B", "brand": "CORTECO", "price": 32.17, "delivery_days": 0, "is_analog": False, "search_query": part_number},
        # Аналоги (Кроссы)
        {"supplier": "Армтек", "part_number": "JF46547", "brand": "STONE", "price": 4.08, "delivery_days": 3, "is_analog": True, "search_query": part_number},
        {"supplier": "Армтек", "part_number": "Z26906", "brand": "ZENTPARTS", "price": 5.14, "delivery_days": 1, "is_analog": True, "search_query": part_number},
        
        # Моделирование Шате-М для проверки работы таблиц
        {"supplier": "Шате-М", "part_number": "01020045B", "brand": "CORTECO", "price": 33.10, "delivery_days": 1, "is_analog": False, "search_query": part_number},
        {"supplier": "Шате-М", "part_number": "34817", "brand": "FEBI", "price": 21.65, "delivery_days": 2, "is_analog": True, "search_query": part_number},
        {"supplier": "Шате-М", "part_number": "466.042", "brand": "ELRING", "price": 30.95, "delivery_days": 0, "is_analog": True, "search_query": part_number},
    ]

def process_supplier_tables(raw_data):
    df = pd.DataFrame(raw_data)
    df['price'] = pd.to_numeric(df['price'])
    df['delivery_days'] = pd.to_numeric(df['delivery_days'])
    
    original_rows, analog_rows = [], []
    
    for supplier, group in df.groupby('supplier'):
        orig_group = group[group['is_analog'] == False]
        if not orig_group.empty:
            idx_min_price = orig_group['price'].idxmin()
            idx_min_time = orig_group['delivery_days'].idxmin()
            original_rows.append(orig_group.loc[idx_min_price].copy())
            original_rows.append(orig_group.loc[idx_min_time].copy())
            
        analog_group = group[group['is_analog'] == True]
        if not analog_group.empty:
            idx_min_price_an = analog_group['price'].idxmin()
            idx_min_time_an = analog_group['delivery_days'].idxmin()
            analog_rows.append(analog_group.loc[idx_min_price_an].copy())
            analog_rows.append(analog_group.copy().loc[idx_min_time_an].copy())

    df_orig_res = pd.DataFrame(original_rows) if original_rows else pd.DataFrame()
    df_analog_res = pd.DataFrame(analog_rows) if analog_rows else pd.DataFrame()
    
    if not df_orig_res.empty:
        df_orig_res = df_orig_res[['supplier', 'part_number', 'price', 'delivery_days']]
        df_orig_res.columns = ['Сайт поставщика', 'Номер позиции', 'Стоимость', 'Срок поставки (количество дней)']
        
    if not df_analog_res.empty:
        df_analog_res = df_analog_res[['supplier', 'search_query', 'part_number', 'brand', 'price', 'delivery_days']]
        df_analog_res.columns = ['Сайт поставщика', 'Номер позиции (начальный)', 'Номер аналога', 'Производитель', 'Стоимость', 'Срок поставки (количество дней)']
        
    return df_orig_res, df_analog_res

if query:
    with st.spinner('Получение данных...'):
        raw_results = fetch_raw_data_from_suppliers(query)
        df_original, df_analog = process_supplier_tables(raw_results)
        
        st.subheader("Оригинальная позиция")
        if not df_original.empty:
            st.dataframe(df_original, use_container_width=True, hide_index=True)
            
        st.subheader("Аналоги")
        if not df_analog.empty:
            st.dataframe(df_analog, use_container_width=True, hide_index=True)
            
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
