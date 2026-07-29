import streamlit as st
import pandas as pd
import requests
import json
import os
from datetime import datetime, timedelta
import base64
import plotly.express as px

try:
    from pypdf import PdfReader
except:
    PdfReader = None

try:
    from icalendar import Calendar, Event
except:
    Calendar = None
    Event = None

st.set_page_config(page_title="DDL管理", layout="wide")

DATA_FILE = "deadlines.csv"

if "df" not in st.session_state:
    if os.path.exists(DATA_FILE):
        st.session_state.df = pd.read_csv(DATA_FILE)
        for col in ["重复", "状态"]:
            if col not in st.session_state.df.columns:
                st.session_state.df[col] = "无" if col == "重复" else "未完成"
    else:
        st.session_state.df = pd.DataFrame(columns=[
            "课程/科目", "截止日期", "描述", "标签", "重复", "状态", "添加时间"
        ])

def save_data():
    st.session_state.df.to_csv(DATA_FILE, index=False, encoding="utf-8-sig")

st.title("📚 DDL管理")

with st.sidebar:
    api_key = st.text_input("DeepSeek API Key", type="password")
    st.metric("总任务", len(st.session_state.df))

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "添加", "管理", "图表", "导出", "上传", "月历"
])

with tab1:
    with st.form("add"):
        col1, col2 = st.columns(2)
        with col1:
            course = st.text_input("课程")
            deadline = st.text_input("截止日期 (YYYY-MM-DD)")
        with col2:
            desc = st.text_input("描述")
            tag = st.text_input("标签")
            repeat = st.selectbox("重复", ["无", "每周", "每月"])
        submitted = st.form_submit_button("保存")
        if submitted:
            if course and deadline:
                try:
                    dt = datetime.strptime(deadline, "%Y-%m-%d")
                    dates = [dt]
                    if repeat == "每周":
                        dates = [dt + timedelta(weeks=i) for i in range(4)]
                    elif repeat == "每月":
                        dates = []
                        for i in range(3):
                            m = dt.month + i
                            y = dt.year + (m-1)//12
                            m = (m-1)%12 + 1
                            try:
                                dates.append(datetime(y, m, dt.day))
                            except:
                                dates.append(datetime(y, m, 1))
                    new_rows = []
                    for d in dates:
                        new_rows.append({
                            "课程/科目": course,
                            "截止日期": d.strftime("%Y-%m-%d"),
                            "描述": desc,
                            "标签": tag if tag else "未分类",
                            "重复": repeat,
                            "状态": "未完成",
                            "添加时间": datetime.now().strftime("%Y-%m-%d %H:%M")
                        })
                    st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame(new_rows)], ignore_index=True)
                    save_data()
                    st.success(f"添加了 {len(new_rows)} 条")
                    st.rerun()
                except:
                    st.error("日期格式错误，请使用 YYYY-MM-DD")

with tab2:
    keyword = st.text_input("搜索")
    status_filter = st.selectbox("状态", ["全部", "未完成", "已完成"])
    df2 = st.session_state.df.copy()
    if keyword:
        df2 = df2[df2["课程/科目"].str.contains(keyword, na=False) | df2["描述"].str.contains(keyword, na=False)]
    if status_filter != "全部":
        df2 = df2[df2["状态"] == status_filter]
    if not df2.empty:
        df2["截止日期"] = pd.to_datetime(df2["截止日期"])
        df2["剩余天数"] = (df2["截止日期"].dt.date - datetime.now().date()).dt.days
        edited = st.data_editor(
            df2[["课程/科目", "截止日期", "描述", "标签", "状态", "剩余天数"]],
            column_config={
                "状态": st.column_config.SelectboxColumn("状态", options=["未完成", "已完成"])
            },
            hide_index=True,
            key="edit"
        )
        if not edited.equals(df2[["课程/科目", "截止日期", "描述", "标签", "状态", "剩余天数"]]):
            for _, row in edited.iterrows():
                mask = (st.session_state.df["课程/科目"] == row["课程/科目"]) & (st.session_state.df["截止日期"] == str(row["截止日期"]))
                if mask.any():
                    st.session_state.df.loc[mask, "状态"] = row["状态"]
            save_data()
            st.success("状态已更新")
            st.rerun()
    else:
        st.info("无数据")

with tab3:
    df3 = st.session_state.df[st.session_state.df["状态"] != "已完成"]
    if not df3.empty:
        df3["截止日期"] = pd.to_datetime(df3["截止日期"])
        df3 = df3[df3["截止日期"] >= datetime.now()]
        if not df3.empty:
            df3["星期"] = df3["截止日期"].dt.day_name()
            count = df3.groupby("星期").size().reset_index(name="数量")
            fig = px.bar(count, x="星期", y="数量")
            st.plotly_chart(fig)
        else:
            st.info("未来无任务")
    else:
        st.info("暂无")

with tab4:
    if st.button("导出CSV"):
        csv = st.session_state.df.to_csv(index=False)
        b64 = base64.b64encode(csv.encode()).decode()
        st.markdown(f'<a href="data:file/csv;base64,{b64}" download="data.csv">下载</a>', unsafe_allow_html=True)

with tab5:
    uploaded = st.file_uploader("上传文件", type=["txt", "pdf"])
    if uploaded:
        text = ""
        if uploaded.type == "application/pdf" and PdfReader:
            reader = PdfReader(uploaded)
            for page in reader.pages:
                text += page.extract_text()
        else:
            text = uploaded.read().decode("utf-8")
        st.text_area("内容", text, height=200)

with tab6:
    st.subheader("月历")
    if "year" not in st.session_state:
        st.session_state.year = datetime.now().year
        st.session_state.month = datetime.now().month
    c1, c2, c3 = st.columns([1,2,1])
    with c1:
        if st.button("◀"):
            if st.session_state.month == 1:
                st.session_state.month = 12
                st.session_state.year -= 1
            else:
                st.session_state.month -= 1
            st.rerun()
    with c2:
        st.write(f"{st.session_state.year}年{st.session_state.month}月")
    with c3:
        if st.button("▶"):
            if st.session_state.month == 12:
                st.session_state.month = 1
                st.session_state.year += 1
            else:
                st.session_state.month += 1
            st.rerun()
    year = st.session_state.year
    month = st.session_state.month
    first = datetime(year, month, 1)
    if month == 12:
        last = datetime(year+1, 1, 1) - timedelta(days=1)
    else:
        last = datetime(year, month+1, 1) - timedelta(days=1)
    start = first.weekday()
    days = last.day
    df6 = st.session_state.df[st.session_state.df["状态"] != "已完成"]
    tasks = {}
    if not df6.empty:
        df6["截止日期"] = pd.to_datetime(df6["截止日期"])
        for _, row in df6.iterrows():
            if row["截止日期"].year == year and row["截止日期"].month == month:
                key = row["截止日期"].strftime("%Y-%m-%d")
                tasks.setdefault(key, []).append(row["课程/科目"])
    cal = [None]*start + [datetime(year, month, d) for d in range(1, days+1)]
    while len(cal) < 42:
        cal.append(None)
    html = "<div style='display:grid;grid-template-columns:repeat(7,1fr);gap:2px;'>"
    for w in ["一","二","三","四","五","六","日"]:
        html += f"<div style='text-align:center;font-weight:bold;'>{w}</div>"
    for d in cal:
        if d is None:
            html += "<div style='min-height:60px;'></div>"
        else:
            key = d.strftime("%Y-%m-%d")
            t = tasks.get(key, [])
            color = "red" if len(t)>=3 else "orange" if len(t)>=1 else "green"
            html += f"<div style='border-top:3px solid {color};min-height:60px;background:#f9f9f9;padding:2px;'><div>{d.day}</div>"
            for task in t[:3]:
                html += f"<div style='font-size:10px;'>{task[:4]}</div>"
            if len(t)>3:
                html += f"<div>+{len(t)-3}</div>"
            html += "</div>"
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)

st.caption("功能: 添加/管理/图表/导出/月历")
