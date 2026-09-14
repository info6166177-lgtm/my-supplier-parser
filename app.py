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

# Инициализация списка поставщиков
if "suppliers" not in st.session_state:
    st.session_state.suppliers = [
        {"url": "armtek.by", "login": "", "password": ""},
        {"url": "shate-m.by", "login": "", "password": ""},
        {"url": "emex.ru", "login": "", "password": ""},
    ]

# ЛЕВОЕ МЕНЮ
st.sidebar.header("🔐 Настройки поставщиков")

# Кнопка "+" для добавления поставщика
with st.sidebar.expander("➕ Добавить поставщика", expanded=False):
    new_url = st.text_input("Адрес нового сайта (например, sferam.by)", key="new_u").strip()
    new_login = st.text_input("Логин", key="new_l")
    new_pass = st.text_input("Пароль", type="password", key="new_p")
    if st.button("Сохранить поставщика"):
        if new_url:
            if not any(s['url'] == new_url for s in st.session_state.suppliers):
                st.session_state.suppliers.append({"url": new_url, "login": new_login, "password": new_pass})
                st.success(f"Сайт {new_url} добавлен!")
                st.rerun()
            else:
                st.warning("Этот сайт уже есть в списке.")
        else:
            st.error("Адрес сайта не может быть пустым.")

st.sidebar.markdown("---")
st.sidebar.subheader("Список подключенных сайтов:")

for idx, supplier in enumerate(st.session_state.suppliers):
    with st.sidebar.expander(supplier["url"], expanded=False):
        supplier["url"] = st.text_input("Адрес сайта", value=supplier["url"], key=f"url_{idx}")
        supplier["login"] = st.text_input("Логин", value=supplier["login"], key=f"log_{idx}")
        supplier["password"] = st.text_input("Пароль", value=supplier["password"], type="password", key=f"pas_{idx}")

# ПОЛЕ ПОИСКА ПО ЦЕНТРУ
query = st.text_input("Номер позиции для поиска", placeholder="Введите артикул детали...")

def fetch_raw_data_from_suppliers(part_number, active_suppliers):
    """
    Модель данных на основе реального поиска Armtek.by по артикулу 01020045b 
    с новыми полями: наименование и надежность.
    """
    results = []
    for s in active_suppliers:
        site_name = s["url"]
        # Модель оригиналов (CORTECO)
        results.append({
            "supplier": site_name, "part_number": "01020045B", "brand": "CORTECO", 
            "name": "сальник КПП ! \\ 43x58x7 MB W126/W163/W140/W220", 
            "price": 31.50, "delivery_days": 3, "reliability": "95%", "is_analog": False, "search_query": part_number
        })
        results.append({
            "supplier": site_name, "part_number": "01020045B", "brand": "CORTECO", 
            "name": "сальник КПП ! \\ 43x58x7 MB W126/W163/W140/W220", 
            "price": 32.17, "delivery_days": 0, "reliability": "100%", "is_analog": False, "search_query": part_number
        })
        
        # Модель аналогов (ZENTPARTS и STONE)
        results.append({
            "supplier": site_name, "part_number": "JF46547", "brand": "STONE", 
            "name": "САЛЬНИК STONE JF46547", 
            "price": 4.08, "delivery_days": 3, "reliability": "81%", "is_analog": True, "search_query": part_number
        })
        results.append({
            "supplier": site_name, "part_number": "Z26906", "brand": "ZENTPARTS", 
            "name": "сальник КПП! 43x58x7\\ MB W126/W163/W140/W220", 
            "price": 5.14, "delivery_days": 1, "reliability": "98%", "is_analog": True, "search_query": part_number
        })
    return results

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
    
    # Форматируем колонки с новыми полями строго по ТЗ
    if not df_orig_res.empty:
        df_orig_res = df_orig_res[['supplier', 'part_number', 'name', 'price', 'delivery_days', 'reliability']]
        df_orig_res.columns = ['Сайт поставщика', 'Номер позиции', 'Наименование товара', 'Стоимость', 'Срок поставки (количество дней)', 'Надежность поставщика']
        
    if not df_analog_res.empty:
        df_analog_res = df_analog_res[['supplier', 'search_query', 'part_number', 'brand', 'name', 'price', 'delivery_days', 'reliability']]
        df_analog_res.columns = ['Сайт поставщика', 'Номер позиции (начальный)', 'Номер аналога', 'Производитель', 'Наименование аналога', 'Стоимость', 'Срок поставки (количество дней)', 'Надежность поставщика']
        
    return df_orig_res, df_analog_res

if query:
    with st.spinner('Получение данных...'):
        raw_results = fetch_raw_data_from_suppliers(query, st.session_state.suppliers)
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
