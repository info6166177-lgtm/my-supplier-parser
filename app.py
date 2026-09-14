import streamlit as st
import pandas as pd
from io import BytesIO
import asyncio
import os
import re

st.set_page_config(page_title="Агрегатор Поставщиков", layout="wide")
st.title("📦 Поиск позиций по поставщикам")

company_secrets = st.secrets.get("suppliers", {})
st.sidebar.header("🏢 Доступы компании")
if company_secrets:
    for key, data in company_secrets.items():
        st.sidebar.markdown(f"✅ **{data.get('url')}** (Подключен)")
else:
    st.sidebar.warning("Секреты компании не настроены в панели Streamlit!")

query = st.text_input("Номер позиции для поиска", placeholder="Введите артикул детали...", key="search_input_field")

if "brand_selection" not in st.session_state:
    st.session_state.brand_selection = {}

async def fetch_live_playwright_data(site_info, part_number, selected_brand=None):
    from playwright.async_api import async_playwright
    url = site_info.get("url", "")
    login = site_info.get("login", "")
    password = site_info.get("password", "")
    products = []
    os.system("playwright install chromium")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-gpu"])
        context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
        page = await context.new_page()
        
        try:
            if "armtek" in url.lower() and login and password:
                await page.goto("https://armtek.by", timeout=15000)
                if await page.query_selector("input[type='text']"):
                    await page.fill("input[type='text']", login)
                    await page.fill("input[type='password']", password)
                    await page.click("button[type='submit']")
                    await page.wait_for_load_state("networkidle", timeout=15000)
                
                search_url = f"https://armtek.by{str(part_number).strip()}"
                if selected_brand:
                    search_url += f"&brand={selected_brand}"
                    
                await page.goto(search_url, timeout=15000)
                await page.wait_for_selector("tr, .search-result-row", timeout=10000)
                html = await page.content()
                
                if "Возможно вы искали" in html and not selected_brand:
                    found_brands = re.findall(r'brand=([^"\'&>]+)', html)
                    if found_brands:
                        unique_brands = list(set([b.upper().strip() for b in found_brands if len(b) < 20]))
                        await browser.close()
                        return {"status": "need_brand_clarification", "brands": unique_brands}
                
                rows = await page.query_selector_all("tr")
                is_analog_block = False
                for row in rows:
                    text = await row.inner_text()
                    if not text: continue
                    if "Возможные замены" in text:
                        is_analog_block = True
                        continue
                    if any(k in text for k in ["Дроздово", "Москва", "СК51", "Нет даты поставки"]):
                        price_match = re.search(r"(\d+[\.,]\d+)", text)
                        price = float(price_match.group(1).replace(",", ".")) if price_match else 0.0
                        days = 3
                        if "сегодня" in text.lower(): days = 0
                        elif "завтра" in text.lower(): days = 1
                        elif "Нет даты поставки" in text: days, price = 999, 0.0
                        
                        products.append({
                            "supplier": "etp.armtek.by", "part_number": part_number if not is_analog_block else "Кросс-номер",
                            "brand": selected_brand or "COB-WEB", "name": "Фильтр" if is_analog_block else "Оригинал",
                            "price": price, "delivery_days": days, "reliability": "100%", "is_analog": is_analog_block
                        })
        except Exception: pass
        finally: await browser.close()
    return {"status": "success", "data": products}

def process_supplier_tables(raw_data, current_query):
    if not raw_data: return pd.DataFrame(), pd.DataFrame()
    df = pd.DataFrame(raw_data)
    df['price'] = pd.to_numeric(df['price'], errors='coerce')
    df['delivery_days'] = pd.to_numeric(df['delivery_days'], errors='coerce')
    
    original_rows, analog_rows = [], []
    for supplier, group in df.groupby('supplier'):
        orig_group = group[group['is_analog'] == False]
        if not orig_group.empty:
            original_rows.append(orig_group.loc[orig_group['price'].idxmin()].copy())
            original_rows.append(orig_group.loc[orig_group['delivery_days'].idxmin()].copy())
        analog_group = group[group['is_analog'] == True]
        if not analog_group.empty:
            analog_rows.append(analog_group.loc[analog_group['price'].idxmin()].copy())
            analog_rows.append(analog_group.loc[analog_group['delivery_days'].idxmin()].copy())

    df_orig = pd.DataFrame(original_rows) if original_rows else pd.DataFrame()
    df_anal = pd.DataFrame(analog_rows) if analog_rows else pd.DataFrame()
    
    if not df_orig.empty:
        df_orig = df_orig[['supplier', 'part_number', 'name', 'price', 'delivery_days', 'reliability']]
        df_orig.loc[df_orig['delivery_days'] == 999, 'delivery_days'] = "Нет даты"
        df_orig.columns = ['Сайт поставщика', 'Номер позиции', 'Наименование товара', 'Стоимость', 'Срок поставки (дней)', 'Надежность']
    if not df_anal.empty:
        df_anal['search_query'] = current_query
        df_anal = df_anal[['supplier', 'search_query', 'part_number', 'brand', 'name', 'price', 'delivery_days', 'reliability']]
        df_anal.columns = ['Сайт поставщика', 'Номер позиции (нач)', 'Номер аналога', 'Производитель', 'Наименование аналога', 'Стоимость', 'Срок поставки (дней)', 'Надежность']
    return df_orig, df_anal

if query:
    if not company_secrets:
        st.error("Пожалуйста, настройте Secrets в личном кабинете Streamlit!")
    else:
        all_raw_data, pending_clarifications = [], {}
        with st.spinner('Запуск защищенного браузерного ядра и сбор цен...'):
            for key, site_info in company_secrets.items():
                url = site_info.get("url", "")
                chosen_brand = st.session_state.brand_selection.get(key)
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    result = loop.run_until_complete(fetch_live_playwright_data(site_info, query, chosen_brand))
                    if result.get("status") == "need_brand_clarification":
                        pending_clarifications[key] = (url, result.get("brands"))
                    elif result.get("status") == "success" and result.get("data"):
                        all_raw_data.extend(result.get("data"))
                except Exception: pass

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
            st.info("Позиция не найдена")
            
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
            st.download_button(label="📥 Выгрузить результаты в Excel", data=buffer.getvalue(), file_name=f"report_{query}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
