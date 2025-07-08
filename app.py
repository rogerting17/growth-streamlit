import streamlit as st
import pandas as pd
import io
import requests
from bs4 import BeautifulSoup
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import twstock
# pip install streamlit pandas numpy plotly requests beautifulsoup4 twstock(套件安裝程式碼)

# CSV 路徑
csv_path = "data.csv"

# 初始化 session staate
if "data_updated" not in st.session_state:
    st.session_state["data_updated"] = False
if "last_update_time" not in st.session_state:
    st.session_state["last_update_time"] = "尚未更新"

# 更新資料：爬 Goodinfo 年增率
def update_data():
    import time
    import os
    import re
    import pandas as pd
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait, Select
    from selenium.webdriver.support import expected_conditions as EC
    import streamlit as st

    if os.path.exists(csv_path):
        try:
            old_df = pd.read_csv(csv_path, encoding="utf-8-sig")
            old_df.columns = old_df.columns.map(lambda x: str(x).replace("\xa0", " ").replace("\u3000", " ").strip())
            old_df["代號"] = old_df["代號"].astype(str)
        except Exception as e:
            st.warning(f"⚠️ 無法讀取本地檔案：{e}")
            return False
    else:
        old_df = pd.DataFrame()

    chrome_options = Options()
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--lang=zh-TW")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)

    driver = webdriver.Chrome(options=chrome_options)
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {
            "source": "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
                      "Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });"
                      "Object.defineProperty(navigator, 'languages', { get: () => ['zh-TW', 'zh'] });"
        }
    )
    wait = WebDriverWait(driver, 30)

    rpt_time = "最新資料"
    rank_ranges = ["1~300", "301~600", "601~900", "901~1200", "1201~1500", "1501~1800", "1801~1895"]
    all_rows = []
    first_load = True

    progress = st.progress(0)
    status_text = st.empty()

    for idx, rank_range in enumerate(rank_ranges):
        driver.get("https://goodinfo.tw/tw2/StockList.asp?MARKET_CAT=熱門排行&INDUSTRY_CAT=年度稅後淨利最高")
        time.sleep(5)

        try:
            Select(wait.until(EC.presence_of_element_located((By.ID, "selSHEET")))).select_by_visible_text("月營收–近12個月營收一覽")
            time.sleep(10 if first_load else 5)
            wait.until(lambda d: d.find_element(By.ID, "divStockList").get_attribute("innerHTML") != "")
            Select(wait.until(EC.presence_of_element_located((By.ID, "selSHEET2")))).select_by_visible_text("月累計年增率")
            time.sleep(8 if first_load else 6)
            Select(wait.until(EC.presence_of_element_located((By.ID, "selRPT_TIME")))).select_by_visible_text(rpt_time)
            time.sleep(8 if first_load else 6)
            Select(wait.until(EC.presence_of_element_located((By.ID, "selRANK")))).select_by_visible_text(rank_range)
            time.sleep(10 if first_load else 8)
        except:
            continue

        first_load = False
        temp_rows = []

        while True:
            try:
                wait.until(EC.presence_of_element_located((By.ID, "tblStockList")))
                table_html = driver.find_element(By.ID, "tblStockList").get_attribute("outerHTML")

                if "查無資料" in table_html or "<tbody></tbody>" in table_html:
                    break

                df = pd.read_html(table_html)[0]
                df.columns = df.columns.map(lambda x: str(x).replace("\xa0", " ").replace("\u3000", " ").strip())
                if "代號" not in df.columns or "名稱" not in df.columns:
                    if df.columns.str.contains("代號名稱").any():
                        df[["代號", "名稱"]] = df[df.columns[1]].str.extract(r'(\d{4})(.+)')
                df = df[df["代號"].astype(str).str.match(r"\d{4}")]
                df["代號"] = df["代號"].astype(str)
                df = df.reset_index(drop=True)

                keep_cols = [col for col in df.columns if col in ["代號", "名稱"]]
                dynamic_cols = [col for col in df.columns if "年增率" in col][-3:]
                df = df[keep_cols + dynamic_cols]
                temp_rows.append(df)

                next_btn = driver.find_elements(By.LINK_TEXT, "下一頁")
                if next_btn:
                    driver.execute_script("arguments[0].click();", next_btn[0])
                    time.sleep(3)
                else:
                    break
            except:
                break

        if temp_rows:
            combined = pd.concat(temp_rows, ignore_index=True)
            st.write(f"📌 {rank_range} 前兩列：")
            st.dataframe(combined.head(2), use_container_width=True)
            all_rows.append(combined)

        pct = int(((idx + 1) / len(rank_ranges)) * 100)
        progress.progress(pct, text=f"進度：{pct}%")
        status_text.text(f"完成 {pct}%：{rank_range}")

    driver.quit()

    if not all_rows or all(len(df) == 0 for df in all_rows):
        st.error("❌ 沒有抓到任何資料")
        return False

    final_df = pd.concat(all_rows, ignore_index=True)

    if not old_df.empty:
        main_cols = ["代號", "名稱"]
        old_df = old_df.drop_duplicates(subset=main_cols)
        final_df = final_df.drop_duplicates(subset=main_cols)
        final_df.set_index(main_cols, inplace=True)
        old_df.set_index(main_cols, inplace=True)

        for col in final_df.columns:
            if col not in old_df.columns:
                old_df[col] = pd.NA
        old_df.update(final_df)
        old_df.reset_index(inplace=True)
        final_df = old_df

        def sort_monthly_cols(cols):
            def extract_key(c):
                match = re.search(r'(\d{2})M(\d{2})', c)
                return (int(match.group(1)), int(match.group(2))) if match else (999, 999)
            return sorted(cols, key=extract_key)

        dynamic_cols = sort_monthly_cols([c for c in final_df.columns if "年增率" in c])
        base_cols = [c for c in final_df.columns if c not in dynamic_cols]
        final_df = final_df[base_cols + dynamic_cols]

        # 🔧 將「平均 年增率」取代「平均年增率」
        if "平均 年增率" in final_df.columns:
            final_df["平均年增率"] = final_df["平均 年增率"]
            final_df.drop(columns=["平均 年增率"], inplace=True)

    final_df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    st.success(f"✅ 資料已寫入：{csv_path}")
    return True


# 取得 K 線資料 (最近 100 日)
def get_kline_data(code):
    sid = str(code).strip()
    stock = twstock.Stock(sid)
    df = pd.DataFrame({
        'date': stock.date,
        'open': stock.open,
        'high': stock.high,
        'low': stock.low,
        'close': stock.close,
        'volume': stock.capacity
    })
    for w in [5, 10, 20]:
        df[f'{w}MA'] = df['close'].rolling(w).mean()
    return df.tail(100)

# 取得 TWSE 歷史日線 (過去5年)
def get_twse_history_data(code):
    # 使用 TWSE API 按月下載，從今天往前5年
    today = datetime.now()
    start = today - timedelta(days=5*365)
    # 將起始日調整到當月1日
    start = start.replace(day=1)
    dfs = []
    current = start
    while current <= today:
        date_str = f"{current.year}{current.month:02d}01"
        url = f"https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=json&date={date_str}&stockNo={code}"
        res = requests.get(url)
        if res.status_code == 200:
            js = res.json()
            if js.get('stat') == 'OK':
                tmp = pd.DataFrame(js['data'], columns=js['fields'])
                # 數值清洗
                for col in ['成交股數','成交金額','開盤價','最高價','最低價','收盤價']:
                    tmp[col] = tmp[col].str.replace(',', '').astype(float)
                tmp['日期'] = pd.to_datetime(tmp['日期'], format='%Y/%m/%d')
                tmp = tmp[['日期','開盤價','最高價','最低價','收盤價','成交股數']]
                dfs.append(tmp)
        # 下一月
        if current.month == 12:
            current = current.replace(year=current.year+1, month=1)
        else:
            current = current.replace(month=current.month+1)
    if dfs:
        df_all = pd.concat(dfs).reset_index(drop=True)
        # 篩選最後5年
        df_all = df_all[df_all['日期'] >= start]
        return df_all.sort_values('日期')
    return pd.DataFrame()
@st.cache_data
def fetch_history_from_2019(symbol: str) -> pd.DataFrame:
    import time
    from requests.exceptions import HTTPError

    start_dt = int(datetime(2019, 1, 1).timestamp())
    end_dt = int(time.time())
    headers = {"User-Agent": "Mozilla/5.0"}

    def fetch_with_suffix(suffix):
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}{suffix}"
        params = {
            "period1": start_dt,
            "period2": end_dt,
            "interval": "1d",
            "includePrePost": "false",
            "events": "div,splits"
        }
        resp = requests.get(url, params=params, headers=headers)
        resp.raise_for_status()
        return resp.json()

    try:
        data = fetch_with_suffix(".TW")
    except HTTPError:
        try:
            data = fetch_with_suffix(".TWO")
        except HTTPError:
            return pd.DataFrame()  # 兩個都失敗，回傳空表格

    result = data["chart"]["result"][0]
    ts = result["timestamp"]
    quote = result["indicators"]["quote"][0]
    adjclose = result["indicators"].get("adjclose", [{}])[0].get("adjclose", [None] * len(ts))

    df = pd.DataFrame({
        "Open": quote["open"],
        "High": quote["high"],
        "Low": quote["low"],
        "Close": quote["close"],
        "Volume": quote["volume"],
        "AdjClose": adjclose
    }, index=pd.to_datetime(ts, unit="s"))

    df = df.dropna(subset=["Open", "Close"])
    for w in (5, 10, 20):
        df[f"MA{w}"] = df["Close"].rolling(window=w).mean()
    return df
# 畫面與側邊欄
st.set_page_config(page_title="年增率與K線圖", layout="wide")
st.sidebar.title("📂 查詢條件")

# 更新按鈕
if st.sidebar.button("🔄 更新資料（重新爬蟲並載入）"):
    with st.spinner("更新中..."):
        if update_data():
            st.session_state['data_updated'] = True
            st.session_state['last_update_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            st.success(f"✅ 上次更新：{st.session_state['last_update_time']}")
        else:
            st.error("❌ 年增率抓取失敗，請稍後再試！")

# 載入年增率與產業分類
@st.cache_data
def load_data():
    import re
    df = pd.read_csv(csv_path, encoding='utf-8-sig')
    df.columns = df.columns.map(lambda x: str(x).replace("\xa0", " ").replace("\u3000", " ").strip())

    # 處理「平均 年增率」欄位：用它覆蓋「平均年增率」，再刪掉原欄位
    if "平均 年增率" in df.columns:
        df["平均年增率"] = df["平均 年增率"]
        df.drop(columns=["平均 年增率"], inplace=True)

    # 統一新產業分類欄位名稱
    if '新產業分類' in df.columns:
        df.rename(columns={'新產業分類': '產業分類'}, inplace=True)

    # 抓所有月年增率欄位（排除平均）
    yoy_cols = [c for c in df.columns if '年增率' in c and not c.strip().startswith('平均')]
    df[yoy_cols] = df[yoy_cols].apply(pd.to_numeric, errors='coerce')

    # 長表結構轉換
    df_m = df.melt(id_vars=['代號', '名稱', '產業分類'], value_vars=yoy_cols,
                   var_name='月份', value_name='年增率')

    # 容錯解析 '25M06 年增率' → Timestamp(2025, 6, 1)
    def parse_month_to_date(month_str):
        match = re.search(r'(\d{2})M(\d{2})', month_str)
        if match:
            y, m = int(match.group(1)), int(match.group(2))
            return pd.Timestamp(year=2000 + y, month=m, day=1)
        return pd.NaT

    df_m['日期'] = df_m['月份'].apply(parse_month_to_date)
    return df_m

# 主程式

df_melted = load_data()
inds = sorted(df_melted['產業分類'].dropna().unique())
sel_inds = st.sidebar.multiselect("選擇產業分類（可多選）", inds)
manual_input = st.sidebar.text_input("或輸入股票代號（逗號分隔）", placeholder="2330,1101")
manual_codes = [c.strip() for c in manual_input.split(',') if c.strip()]
filtered = df_melted.copy()
if sel_inds:
    filtered = filtered[filtered['產業分類'].isin(sel_inds)]
if manual_codes:
    filtered = pd.concat([filtered, df_melted[df_melted['代號'].isin(manual_codes)]])
stocks = filtered[['代號','名稱']].drop_duplicates()
opts = {f"{r['代號']} {r['名稱']}":r['代號'] for _,r in stocks.iterrows()}
selected = st.sidebar.multiselect("選擇股票", list(opts.keys()), default=list(opts.keys())[:1])
show_k = st.sidebar.checkbox("📉 顯示 K 線+年增率")
show_hist = st.sidebar.checkbox("📆 顯示過去5年日 K 線")

# 繪製 K 線+年增率
if show_k and len(selected) == 1:
    code = opts[selected[0]]
    df_s = df_melted[df_melted['代號'] == code]
    ind = df_s['產業分類'].iloc[0]
    ind_avg = df_melted[df_melted['產業分類'] == ind].groupby('日期')['年增率'].mean().reset_index()

    df_yf = fetch_history_from_2019(code)
    if df_yf.empty:
        st.warning(f"{code}.TW 無法從 Yahoo Finance 取得資料")
    else:
        import numpy as np
        vol_colors = np.where(df_yf["Close"] >= df_yf["Open"], "red", "green")

        fig = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.02,
            row_heights=[0.8, 0.2],
            specs=[[{"secondary_y": True}], [{}]]
        )

        # K 線圖
        fig.add_trace(
            go.Candlestick(
                x=df_yf.index,
                open=df_yf["Open"],
                high=df_yf["High"],
                low=df_yf["Low"],
                close=df_yf["Close"],
                name="K 線",
                increasing_line_color='red',
                decreasing_line_color='green'
            ),
            row=1, col=1, secondary_y=False
        )

        # 移動平均線
        for w in (5, 10, 20):
            fig.add_trace(
                go.Scatter(
                    x=df_yf.index,
                    y=df_yf[f"MA{w}"],
                    mode="lines",
                    name=f"MA{w}"
                ),
                row=1, col=1, secondary_y=False
            )

        # 年增率曲線
        fig.add_trace(
            go.Scatter(
                x=df_s['日期'],
                y=df_s['年增率'],
                mode='lines+markers',
                name=f"{code} 年增率",
                line=dict(color='purple')
            ),
            row=1, col=1, secondary_y=True
        )

        # 產業平均年增率
        fig.add_trace(
            go.Scatter(
                x=ind_avg['日期'],
                y=ind_avg['年增率'],
                mode='lines+markers',
                name=f"{ind} 平均年增率",
                line=dict(color='darkorange', dash='dot')
            ),
            row=1, col=1, secondary_y=True
        )

        # 成交量柱狀圖
        fig.add_trace(
            go.Bar(
                x=df_yf.index,
                y=df_yf["Volume"],
                marker_color=vol_colors,
                name="成交量",
                showlegend=False
            ),
            row=2, col=1
        )

        # Layout 設定
        fig.update_layout(
            uirevision=None,
            title=dict(
                text=f"{code}.TW 5 年日 K 線 + 月營收年增率 + 成交量",
                font=dict(size=22),
                x=0.005,
                xanchor="left"
            ),
            dragmode='pan',
            hovermode='x unified',
            height=850,
            margin=dict(l=40, r=40, t=80, b=40),
            xaxis=dict(
                type="date",
                fixedrange=False,
                rangeslider=dict(visible=False),
                rangeselector=dict(
                    buttons=[
                        dict(count=1, label="1 日", step="day", stepmode="backward"),
                        dict(count=7, label="1 週", step="day", stepmode="backward"),
                        dict(count=3, label="3 個月", step="month", stepmode="backward"),
                        dict(count=6, label="6 個月", step="month", stepmode="backward"),
                        dict(count=1, label="1 年", step="year", stepmode="backward"),
                        dict(step="year", stepmode="todate", label="YTD"),
                        dict(step="all", label="全部")
                    ]
                )
            ),
            yaxis=dict(title="價格", fixedrange=False, domain=[0.3, 1]),
            yaxis2=dict(title="年增率 (%)", overlaying='y', side='right', fixedrange=False, domain=[0.3, 1]),
            xaxis2=dict(fixedrange=False),
            yaxis3=dict(title="成交量", fixedrange=False, domain=[0, 0.2])
        )

        # ✅ 預設顯示最近 6 個月
        fig.update_xaxes(
            range=[
                (datetime.today() - timedelta(days=180)).strftime('%Y-%m-%d'),
                datetime.today().strftime('%Y-%m-%d')
            ]
        )

        # 顯示圖表（啟用滑鼠滾輪縮放）
        st.plotly_chart(fig, use_container_width=True, config={"scrollZoom": True})






elif show_k:
    st.warning("請僅選擇一檔股票以顯示 K 線圖。")


# 平均年增率排行榜 Top 10
if '平均年增率' in pd.read_csv(csv_path, encoding='utf-8-sig').columns:
    df_avg = pd.read_csv(csv_path, encoding='utf-8-sig')[['代號','名稱','平均年增率']].dropna()
    df_avg['平均年增率'] = pd.to_numeric(df_avg['平均年增率'], errors='coerce')
    df_rank = df_avg.sort_values('平均年增率', ascending=False).head(10).reset_index(drop=True)
    st.subheader("🏆 平均年增率排行榜 Top 10")
    st.dataframe(df_rank.style.format({'平均年增率':'{:.2f}%'}))

# 多檔股票 vs 多產業年增率趨勢
all_years = sorted(df_melted['日期'].dt.year.unique())
start_y = st.sidebar.selectbox("聚焦起始年", all_years, index=0)
end_y = st.sidebar.selectbox("聚焦結束年", all_years, index=len(all_years)-1)
sel_multi = st.sidebar.multiselect("多檔股票趨勢", list(opts.keys()), default=list(opts.keys())[:2])
if sel_multi:
    fig1, fig3 = go.Figure(), go.Figure()
    for sel in sel_multi:
        code = opts[sel]
        df_s = df_melted[df_melted['代號']==code]
        ind = df_s['產業分類'].iloc[0]
        df_i = df_melted[df_melted['產業分類']==ind]
        df_i_avg = df_i.groupby('日期')['年增率'].mean().reset_index()
        merged = pd.merge(df_s[['日期','年增率']], df_i_avg, on='日期', suffixes=(f'_{code}', f'_{ind}'))
        fig1.add_trace(go.Scatter(x=merged['日期'], y=merged[f'年增率_{code}'], mode='lines+markers', name=code))
        fig1.add_trace(go.Scatter(x=merged['日期'], y=merged[f'年增率_{ind}'], mode='lines+markers', name=f'{ind} 平均', line=dict(dash='dot')))
        focus = merged[(merged['日期'].dt.year>=start_y)&(merged['日期'].dt.year<=end_y)]
        fig3.add_trace(go.Scatter(x=focus['日期'], y=focus[f'年增率_{code}'], mode='lines+markers', name=code))
        fig3.add_trace(go.Scatter(x=focus['日期'], y=focus[f'年增率_{ind}'], mode='lines+markers', name=f'{ind} 平均', line=dict(dash='dot')))
    fig1.update_layout(title='📊 全期年增率趨勢', xaxis_title='日期', yaxis_title='年增率 (%)', hovermode='x unified', height=600)
    fig3.update_layout(title=f'🔍 {start_y}~{end_y} 年趨勢', xaxis_title='日期', yaxis_title='年增率 (%)', hovermode='x unified', height=600)
    st.plotly_chart(fig1, use_container_width=True)
    st.plotly_chart(fig3, use_container_width=True)
# 此為簡化展示，用於部署需替換為完整內容
# 請將上述完整 Streamlit 程式碼貼入這裡做部署
