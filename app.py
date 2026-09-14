import streamlit as st
import pandas as pd
from io import BytesIO

# Настройки страницы
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

# Боковая панель для ввода логинов и паролей
st.sidebar.header("🔐 Авторизация у поставщиков")
with st.sidebar.expander("Армтек", expanded=False):
    armtek_login = st.text_input("Логин Армтек", key="arm_l")
    armtek_pass = st.text_input("Пароль Армтек", type="password", key="arm_p")

with st.sidebar.expander("Шате-М", expanded=False):
    shate_login = st.text_input("Логин Шате-М", key="sh_l")
    shate_pass = st.text_input("Пароль Шате-М", type="password", key="sh_p")

with st.sidebar.expander("Эмикс", expanded=False):
    emex_login = st.text_input("Логин Эмикс", key="em_l")
    emex_pass = st.text_input("Пароль Эмикс", type="password", key="em_p")

with st.sidebar.expander("Сфера", expanded=False):
    sfera_login = st.text_input("Логин Сфера", key="sf_l")
    sfera_pass = st.text_input("Пароль Сфера", type="password", key="sf_p")

# Поле поиска
query = st.text_input("Номер позиции для поиска", placeholder="Введите артикул детали...")

def fetch_raw_data_from_suppliers(part_number):
    # Тестовые данные для проверки логики (2 строки на оригинал, 2 на аналог)
    return [
        {"supplier": "Армтек", "part_number": part_number, "brand": "Original", "price": 1020, "delivery_days": 2, "is_analog": False, "search_query": part_number},
        {"supplier": "Армтек", "part_number": part_number, "brand": "Original", "price": 950, "delivery_days": 5, "is_analog": False, "search_query": part_number},
        {"supplier": "Армтек", "part_number": "AN-11", "brand": "Bosch", "price": 700, "delivery_days": 3, "is_analog": True, "search_query": part_number},
        {"supplier": "Армтек", "part_number": "AN-22", "brand": "Brembo", "price": 850, "delivery_days": 1, "is_analog": True, "search_query": part_number},
        
        {"supplier": "Шате-М", "part_number": part_number, "brand": "Original", "price": 980, "delivery_days": 1, "is_analog": False, "search_query": part_number},
        {"supplier": "Шате-М", "part_number": "AN-33", "brand": "LPR", "price": 600, "delivery_days": 4, "is_analog": True, "search_query": part_number},
        {"supplier": "Шате-М", "part_number": "AN-44", "brand": "Patron", "price": 650, "delivery_days": 2, "is_analog": True, "search_query": part_number},
        
        {"supplier": "Эмикс", "part_number": part_number, "brand": "Original", "price": 1100, "delivery_days": 0, "is_analog": False, "search_query": part_number},
        {"supplier": "Эмикс", "part_number": part_number, "brand": "Original", "price": 1050, "delivery_days": 3, "is_analog": False, "search_query": part_number},
        
        {"supplier": "Сфера", "part_number": part_number, "brand": "Original", "price": 1200, "delivery_days": 1, "is_analog": False, "search_query": part_number},
        {"supplier": "Сфера", "part_number": "AN-55", "brand": "Febi", "price": 500, "delivery_days": 7, "is_analog": True, "search_query": part_number},
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
            analog_rows.append(analog_group.loc[idx_min_time_an].copy())

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
