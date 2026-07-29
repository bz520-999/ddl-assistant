import streamlit as st
import pandas as pd
import requests
import json
import os
from datetime import datetime, timedelta
from io import BytesIO, StringIO
import base64
import plotly.express as px

# ---------- 1. 可选依赖库（带容错） ----------
try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

try:
    from icalendar import Calendar, Event
except ImportError:
    Calendar = None
    Event = None

try:
    from dateutil import parser as date_parser
except ImportError:
    date_parser = None

# ---------- 2. 页面配置 ----------
st.set_page_config(page_title="学习DDL管理 Pro", layout="wide", initial_sidebar_state="expanded")

# ---------- 3. 万能日期解析函数 ----------
def parse_flexible_date(date_str):
    """支持 2026.7.30 / 7/30 / 30 July 等多种格式"""
    if not date_str:
        return None
    date_str = date_str.strip().replace("。", "").replace("，", ",")
    # 尝试常见格式
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.strftime("%Y-%m-%d")
    except:
        pass
    try:
        dt = datetime.strptime(date_str, "%Y/%m/%d")
        return dt.strftime("%Y-%m-%d")
    except:
        pass
    try:
        dt = datetime.strptime(date_str, "%m/%d")
        return dt.replace(year=datetime.now().year).strftime("%Y-%m-%d")
    except:
        pass
    if date_parser:
        try:
            dt = date_parser.parse(date_str, fuzzy=True)
            return dt.strftime("%Y-%m-%d")
        except:
            pass
    return None

# ---------- 4. 数据初始化 ----------
DATA_FILE = "deadlines.csv"

if "df" not in st.session_state:
    if os.path.exists(DATA_FILE):
        st.session_state.df = pd.read_csv(DATA_FILE)
        # 补全新列
        for col in ["重复", "状态"]:
            if col not in st.session_state.df.columns:
                st.session_state.df[col] = "无" if col == "重复" else "未完成"
    else:
        st.session_state.df = pd.DataFrame(columns=[
            "课程/科目", "截止日期", "描述", "标签", "重复", "状态", "添加时间"
        ])

def save_data():
    st.session_state.df.to_csv(DATA_FILE, index=False, encoding="utf-8-sig")

# ---------- 5. 顶部标题 & 倒计时英雄区 ----------
st.title("🚀 智能学习DDL管理 Pro")

# 倒计时横幅
if not st.session_state.df.empty:
    try:
        df_urgent = st.session_state.df[st.session_state.df["状态"] != "已完成"].copy()
        if not df_urgent.empty:
            df_urgent["截止日期_dt"] = pd.to_datetime(df_urgent["截止日期"])
            nearest = df_urgent["截止日期_dt"].min()
            diff = (nearest - datetime.now()).total_seconds()
            if diff > 0:
                days = int(diff // 86400)
                hours = int((diff % 86400) // 3600)
                color = "green" if days > 3 else "orange" if days > 1 else "red"
                st.markdown(f"<h2 style='text-align: center; color: {color};'>⏳ 距离最近DDL: {days} 天 {hours} 小时</h2>", unsafe_allow_html=True)
            else:
                st.markdown("<h2 style='text-align: center; color: red;'>🚨 有DDL已逾期！立刻处理！</h2>", unsafe_allow_html=True)
    except:
        pass

# 页面加载提醒
if not st.session_state.df.empty:
    try:
        df_alert = st.session_state.df[st.session_state.df["状态"] != "已完成"].copy()
        if not df_alert.empty:
            df_alert["截止日期"] = pd.to_datetime(df_alert["截止日期"])
            today = datetime.now().date()
            alert_df = df_alert[(df_alert["截止日期"].dt.date == today) | 
                                (df_alert["截止日期"].dt.date == today + timedelta(days=1))]
            for _, row in alert_df.iterrows():
                delta = (row["截止日期"].date() - today).days
                msg = "⏰ 今天截止" if delta == 0 else "⏰ 明天截止"
                st.toast(f"{msg}: {row['课程/科目']}", icon="🔔")
    except:
        pass
    # ---------- 6. 侧边栏 ----------
with st.sidebar:
    st.header("⚙️ 配置")
    api_key = st.text_input("DeepSeek API Key", type="password", help="platform.deepseek.com 获取")
    
    st.divider()
    st.subheader("🎨 界面主题")
    theme = st.radio("选择主题", ["🌞 明亮", "🌙 暗黑"], index=0, horizontal=True)
    if theme == "🌙 暗黑":
        st.markdown("""
        <style>
        .stApp { background-color: #1e1e1e; color: #ffffff; }
        .stApp * { color: #e0e0e0; }
        .stButton button { background-color: #333333; color: white; border: 1px solid #555; }
        .stDataFrame { background-color: #2a2a2a; }
        </style>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <style>
        .stApp { background-color: #ffffff; color: #000000; }
        </style>
        """, unsafe_allow_html=True)

    st.divider()
    st.subheader("📊 学习负荷")
    df = st.session_state.df
    total = len(df)
    if total > 0:
        done = len(df[df["状态"] == "已完成"])
        rate = int(done / total * 100) if total > 0 else 0
        st.metric("总任务数", total, delta=f"已完成 {done} 项")
        st.progress(rate / 100, text=f"完成进度 {rate}%")
        try:
            df_temp = df[df["状态"] != "已完成"].copy()
            if not df_temp.empty:
                df_temp["截止日期"] = pd.to_datetime(df_temp["截止日期"])
                urgent = df_temp[(df_temp["截止日期"] >= datetime.now()) & 
                                 (df_temp["截止日期"] <= datetime.now() + timedelta(days=3))]
                if not urgent.empty:
                    st.warning(f"⏰ 最近3天有 {len(urgent)} 个DDL即将截止！")
        except:
            pass
    else:
        st.info("暂无数据")

    st.divider()
    st.subheader("💾 数据保险箱")
    json_str = st.session_state.df.to_json(orient="records", force_ascii=False)
    st.download_button("📥 备份 (JSON)", data=json_str, file_name="backup.json", mime="application/json")
    uploaded_backup = st.file_uploader("📤 恢复备份", type=["json"], key="backup_uploader")
    if uploaded_backup is not None:
        import json as json_lib
        try:
            new_data = pd.DataFrame(json_lib.loads(uploaded_backup.read()))
            if not new_data.empty:
                st.session_state.df = new_data
                save_data()
                st.success("✅ 恢复成功！")
                st.rerun()
        except Exception as e:
            st.error(f"恢复失败：{e}")

# ---------- 7. 主界面 6个标签页 ----------
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📝 添加与解析", "🔍 管理与搜索", "📊 数据图表", 
    "📅 导出与分享", "📂 文件上传", "📆 月视图"
])

# ----- 7.1 添加与解析 (Form实现自动清空) -----
with tab1:
    col1, col2 = st.columns([2, 1])
    with col1:
        st.subheader("✍️ 一句话添加DDL")
        user_input = st.text_area("输入你的DDL", height=80)

        if st.button("🤖 AI 智能解析", use_container_width=True):
            if not api_key:
                st.error("❌ 请先在左侧输入API Key！")
            elif not user_input.strip():
                st.warning("⚠️ 请先输入内容")
            else:
                with st.spinner("AI解析中..."):
                    try:
                        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
                        prompt = f"""
                        提取学习任务信息。
                        规则：1.提取课程名称 2.提取截止日期(转为YYYY-MM-DD) 3.提取描述。
                        只返回JSON: {{"course": "", "deadline": "", "notes": ""}}
                        文本：{user_input}
                        """
                        payload = {
                            "model": "deepseek-chat",
                            "messages": [{"role": "user", "content": prompt}],
                            "temperature": 0.1
                        }
                        response = requests.post("https://api.deepseek.com/v1/chat/completions", 
                                                headers=headers, json=payload, timeout=30)
                        if response.status_code == 200:
                            result = response.json()
                            content = result["choices"][0]["message"]["content"].replace("```json", "").replace("```", "").strip()
                            parsed = json.loads(content)
                            st.session_state["parsed_course"] = parsed.get("course", "")
                            st.session_state["parsed_deadline"] = parsed.get("deadline", "")
                            st.session_state["parsed_notes"] = parsed.get("notes", "")
                            st.success("✅ 解析成功！请填写信息后保存")
                        else:
                            st.error(f"API失败：{response.text}")
                    except Exception as e:
                        st.error(f"解析出错：{e}")

        st.divider()
        st.subheader("🖊️ 手动录入")
        
        # 使用Form实现提交后自动清空
        with st.form(key="add_form", clear_on_submit=True):
            f_col1, f_col2 = st.columns(2)
            with f_col1:
                course = st.text_input("课程/科目", value=st.session_state.get("parsed_course", ""))
                deadline_raw = st.text_input("截止日期 (支持多种格式)", value=st.session_state.get("parsed_deadline", ""))
            with f_col2:
                notes = st.text_input("描述", value=st.session_state.get("parsed_notes", ""))
                tag = st.text_input("标签", placeholder="例如：作业")
                repeat = st.selectbox("重复周期", ["无", "每周", "每月"])
            
            submitted = st.form_submit_button("💾 保存到列表", type="primary", use_container_width=True)
            
            if submitted:
                # 解析日期
                deadline = parse_flexible_date(deadline_raw)
                if not course or not deadline:
                    st.error("⚠️ 课程和正确的截止日期必填", icon="🚨")
                else:
                    new_rows = []
                    try:
                        start_date = datetime.strptime(deadline, "%Y-%m-%d")
                        dates_to_add = []
                        if repeat == "无":
                            dates_to_add = [start_date]
                        elif repeat == "每周":
                            for i in range(4):
                                dates_to_add.append(start_date + timedelta(weeks=i))
                        elif repeat == "每月":
                            for i in range(3):
                                month = start_date.month + i
                                year = start_date.year + (month - 1) // 12
                                month = (month - 1) % 12 + 1
                                try:
                                    dates_to_add.append(datetime(year, month, start_date.day))
                                except ValueError:
                                    dates_to_add.append(datetime(year, month, 1))
                    except Exception as e:
                        st.error(f"日期处理出错：{e}")
                        st.stop()
                    
                    for dt in dates_to_add:
                        new_rows.append({
                            "课程/科目": course,
                            "截止日期": dt.strftime("%Y-%m-%d"),
                            "描述": notes,
                            "标签": tag if tag else "未分类",
                            "重复": repeat,
                            "状态": "未完成",
                            "添加时间": datetime.now().strftime("%Y-%m-%d %H:%M")
                        })
                    
                  
    # ----- 7.2 管理与搜索 (含批量删除) -----
with tab2:
    st.subheader("🔍 筛选与任务管理")
    search_col1, search_col2, search_col3 = st.columns(3)
    with search_col1:
        search_keyword = st.text_input("关键词", placeholder="搜索")
    with search_col2:
        filter_tag = st.selectbox("标签", ["全部"] + list(st.session_state.df["标签"].unique()))
    with search_col3:
        filter_status = st.selectbox("状态", ["全部", "未完成", "已完成"])

    df_display = st.session_state.df.copy()
    if search_keyword:
        df_display = df_display[
            df_display["课程/科目"].str.contains(search_keyword, na=False) |
            df_display["描述"].str.contains(search_keyword, na=False)
        ]
    if filter_tag != "全部":
        df_display = df_display[df_display["标签"] == filter_tag]
    if filter_status != "全部":
        df_display = df_display[df_display["状态"] == filter_status]

    if not df_display.empty:
        # 计算剩余天数（红绿灯）
        df_display["截止日期_dt"] = pd.to_datetime(df_display["截止日期"])
        today = datetime.now().date()
        df_display["剩余天数"] = (df_display["截止日期_dt"].dt.date - today).dt.days
        
        def get_icon(row):
            if row["状态"] == "已完成": return "✅ 已完成"
            days = row["剩余天数"]
            if days < 0: return "🔴 逾期" + str(days)
            elif days == 0: return "🔴 今天截止！"
            elif days <= 3: return "🟠 剩" + str(days) + "天"
            else: return "🟢 剩" + str(days) + "天"
        
        df_display["状态标识"] = df_display.apply(get_icon, axis=1)
        
        st.caption("💡 点击下方【状态】列，可直接切换 未完成/已完成")
        edited_df = st.data_editor(
            df_display[["课程/科目", "截止日期", "描述", "标签", "状态", "状态标识", "剩余天数"]],
            column_config={
                "状态": st.column_config.SelectboxColumn("状态", options=["未完成", "已完成"], required=True),
                "剩余天数": st.column_config.NumberColumn("剩余天数", disabled=True),
                "状态标识": st.column_config.TextColumn("状态标识", disabled=True),
            },
            use_container_width=True,
            hide_index=True,
            key="edit_status"
        )
        
        # 保存状态修改
        if not edited_df.equals(df_display[["课程/科目", "截止日期", "描述", "标签", "状态", "状态标识", "剩余天数"]]):
            for idx, row in edited_df.iterrows():
                mask = (st.session_state.df["课程/科目"] == row["课程/科目"]) & \
                       (st.session_state.df["截止日期"] == row["截止日期"])
                if mask.any():
                    st.session_state.df.loc[mask, "状态"] = row["状态"]
            save_data()
            st.success("✅ 状态已更新！")
            st.rerun()
        
        # 批量删除模块
        st.divider()
        st.subheader("🗑️ 批量删除")
        df_del = df_display.copy()
        df_del["选择删除"] = False
        edited_del = st.data_editor(
            df_del[["选择删除", "课程/科目", "截止日期", "状态"]],
            column_config={"选择删除": st.column_config.CheckboxColumn("勾选")},
            hide_index=True,
            key="del_editor"
        )
        
        col_del1, col_del2 = st.columns(2)
        with col_del1:
            if st.button("🗑️ 删除已勾选项", use_container_width=True):
                selected = edited_del[edited_del["选择删除"] == True]
                if not selected.empty:
                    for _, row in selected.iterrows():
                        mask = (st.session_state.df["课程/科目"] == row["课程/科目"]) & \
                               (st.session_state.df["截止日期"] == row["截止日期"])
                        if mask.any():
                            st.session_state.df = st.session_state.df.drop(st.session_state.df[mask].index)
                    save_data()
                    st.success(f"✅ 已删除 {len(selected)} 项")
                    st.rerun()
                else:
                    st.warning("请至少勾选一项")
        with col_del2:
            if st.button("🧹 一键清除已完成", use_container_width=True):
                before = len(st.session_state.df)
                st.session_state.df = st.session_state.df[st.session_state.df["状态"] != "已完成"]
                save_data()
                st.success(f"已清除 {before - len(st.session_state.df)} 项")
                st.rerun()
    else:
        st.info("没有匹配的任务")
# ----- 7.3 数据图表 -----
with tab3:
    st.subheader("📊 本周DDL分布 & 负荷分析")
    if st.session_state.df.empty:
        st.info("暂无数据")
    else:
        df_chart = st.session_state.df[st.session_state.df["状态"] != "已完成"].copy()
        if df_chart.empty:
            st.success("🎉 所有任务都已完成！")
        else:
            try:
                df_chart["截止日期"] = pd.to_datetime(df_chart["截止日期"])
                today = datetime.now()
                future_30 = today + timedelta(days=30)
                df_chart = df_chart[(df_chart["截止日期"] >= today) & (df_chart["截止日期"] <= future_30)]
                if not df_chart.empty:
                    day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
                    day_names_cn = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
                    df_chart["星期"] = pd.Categorical(df_chart["截止日期"].dt.day_name(), categories=day_order)
                    count_df = df_chart.groupby("星期").size().reset_index(name="任务数量")
                    count_df["星期"] = count_df["星期"].map(dict(zip(day_order, day_names_cn)))
                    fig = px.bar(count_df, x="星期", y="任务数量", title="未来30天 DDL 分布",
                                 color="任务数量", color_continuous_scale="Reds", text="任务数量")
                    fig.update_layout(height=400)
                    st.plotly_chart(fig, use_container_width=True)
                    
                    st.subheader("🏷️ 标签分布")
                    tag_df = df_chart["标签"].value_counts().reset_index()
                    tag_df.columns = ["标签", "数量"]
                    fig_pie = px.pie(tag_df, values="数量", names="标签", hole=0.3)
                    st.plotly_chart(fig_pie, use_container_width=True)
                else:
                    st.info("未来30天无任务")
            except Exception as e:
                st.warning(f"图表生成出错：{e}")

# ----- 7.4 导出与分享 -----
with tab4:
    st.subheader("📤 导出与协作")
    exp_col1, exp_col2 = st.columns(2)
    
    with exp_col1:
        if st.button("⬇️ 导出 CSV"):
            csv = st.session_state.df.to_csv(index=False, encoding="utf-8-sig")
            b64 = base64.b64encode(csv.encode()).decode()
            st.markdown(f'<a href="data:file/csv;base64,{b64}" download="deadlines.csv">点击下载 CSV</a>', unsafe_allow_html=True)
        
        if st.button("⬇️ 导出 日历(.ics)"):
            if Calendar is None:
                st.error("请安装 icalendar")
            elif st.session_state.df.empty:
                st.warning("暂无数据")
            else:
                try:
                    cal = Calendar()
                    cal.add('prodid', '-//DDL Pro//cn//')
                    cal.add('version', '2.0')
                    for _, row in st.session_state.df.iterrows():
                        if row["状态"] == "已完成": continue
                        event = Event()
                        event.add('summary', row["课程/科目"])
                        event.add('description', f"{row['描述']} | 标签: {row['标签']}")
                        date_obj = datetime.strptime(row["截止日期"], "%Y-%m-%d").date()
                        event.add('dtstart', date_obj)
                        event.add('dtend', date_obj)
                        cal.add_component(event)
                    ics_data = cal.to_ical()
                    b64 = base64.b64encode(ics_data).decode()
                    st.markdown(f'<a href="data:text/calendar;base64,{b64}" download="deadlines.ics">点击下载 .ics</a>', unsafe_allow_html=True)
                except Exception as e:
                    st.error(f"导出失败：{e}")
    
    with exp_col2:
        st.subheader("📱 分享卡片")
        if st.button("🔄 生成待办清单"):
            df_share = st.session_state.df[st.session_state.df["状态"] != "已完成"].copy()
            if df_share.empty:
                st.warning("所有任务都完成啦！")
            else:
                df_share = df_share.sort_values("截止日期")
                lines = ["# 📋 我的学习待办清单\n"]
                for _, row in df_share.iterrows():
                    lines.append(f"- **{row['课程/科目']}** 截止: {row['截止日期']} | {row['描述']} (标签: {row['标签']})")
                lines.append(f"\n> 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
                markdown_text = "\n".join(lines)
                st.text_area("📋 长按复制", markdown_text, height=250)
                st.download_button("📥 下载 .md", markdown_text, file_name="DDL_清单.md")
    
    # AI 复习规划
    st.divider()
    st.subheader("🧠 AI 智能复习规划")
    if st.button("📅 生成未来一周复习计划"):
        df_future = st.session_state.df[st.session_state.df["状态"] != "已完成"].copy()
        if df_future.empty or not api_key:
            st.warning("请确保有未完成任务且已配置API Key")
        else:
            with st.spinner("AI正在为你定制复习计划..."):
                try:
                    tasks = df_future[["课程/科目", "截止日期", "描述"]].head(10).to_string()
                    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
                    prompt = f"基于以下学习任务：\n{tasks}\n请生成一个未来一周的每日复习优先级清单，按紧急程度排序，用Markdown列表输出。"
                    payload = {"model": "deepseek-chat", "messages": [{"role": "user", "content": prompt}], "temperature": 0.7}
                    response = requests.post("https://api.deepseek.com/v1/chat/completions", headers=headers, json=payload, timeout=30)
                    if response.status_code == 200:
                        plan = response.json()["choices"][0]["message"]["content"]
                        st.markdown(plan)
                    else:
                        st.error("生成失败")
                except Exception as e:
                    st.error(f"报错：{e}")

# ----- 7.5 文件上传 (含图片OCR) -----
with tab5:
    st.subheader("📎 上传资料自动提取DDL")
    uploaded = st.file_uploader("支持 PDF / TXT / 图片", type=["pdf", "txt", "png", "jpg", "jpeg"])
    if uploaded:
        text = ""
        if uploaded.type == "application/pdf":
            if PdfReader:
                reader = PdfReader(uploaded)
                for page in reader.pages:
                    text += page.extract_text()
            else:
                st.error("请安装 pypdf")
        elif uploaded.type.startswith("image/"):
            try:
                import easyocr
                import tempfile
                reader = easyocr.Reader(['ch_sim', 'en'], gpu=False)
                with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
                    tmp.write(uploaded.read())
                    tmp_path = tmp.name
                result = reader.readtext(tmp_path, detail=0, paragraph=True)
                text = " ".join(result)
                st.success("✅ 图片OCR识别成功")
            except ImportError:
                st.error("请安装 easyocr 和 opencv-python-headless")
            except Exception as e:
                st.error(f"OCR失败：{e}")
        else:
            text = uploaded.read().decode("utf-8")
        
        if text:
            st.text_area("📝 提取的文本 (可编辑)", text, height=200)
            st.info("复制上方文本到【添加与解析】页，点击AI解析即可")
# ----- 7.6 月视图 (新增) -----
with tab6:
    st.subheader("📆 当月 DDL 日历")
    st.caption("🔴红色(≥3项)  🟠橙色(1-2项)  🟢绿色(无任务)  | 点击箭头切换月份")
    
    if "cal_year" not in st.session_state:
        st.session_state.cal_year = datetime.now().year
    if "cal_month" not in st.session_state:
        st.session_state.cal_month = datetime.now().month

    nav_col1, nav_col2, nav_col3 = st.columns([1, 2, 1])
    with nav_col1:
        if st.button("◀ 上月", use_container_width=True):
            if st.session_state.cal_month == 1:
                st.session_state.cal_month = 12; st.session_state.cal_year -= 1
            else:
                st.session_state.cal_month -= 1
            st.rerun()
    with nav_col2:
        st.markdown(f"<h3 style='text-align: center;'>{st.session_state.cal_year} 年 {st.session_state.cal_month} 月</h3>", unsafe_allow_html=True)
    with nav_col3:
        if st.button("下月 ▶", use_container_width=True):
            if st.session_state.cal_month == 12:
                st.session_state.cal_month = 1; st.session_state.cal_year += 1
            else:
                st.session_state.cal_month += 1
            st.rerun()

    year, month = st.session_state.cal_year, st.session_state.cal_month
    first_day = datetime(year, month, 1)
    if month == 12: last_day = datetime(year + 1, 1, 1) - timedelta(days=1)
    else: last_day = datetime(year, month + 1, 1) - timedelta(days=1)
    start_weekday = first_day.weekday()
    total_days = last_day.day

    df_cal = st.session_state.df[st.session_state.df["状态"] != "已完成"].copy()
    tasks_by_date = {}
    if not df_cal.empty:
        try:
            df_cal["截止日期_dt"] = pd.to_datetime(df_cal["截止日期"])
            month_mask = (df_cal["截止日期_dt"].dt.year == year) & (df_cal["截止日期_dt"].dt.month == month)
            for _, row in df_cal[month_mask].iterrows():
                key = row["截止日期_dt"].strftime("%Y-%m-%d")
                tasks_by_date.setdefault(key, []).append(row["课程/科目"])
        except: pass

    cal_dates = [None] * start_weekday + [datetime(year, month, d) for d in range(1, total_days + 1)]
    while len(cal_dates) < 42: cal_dates.append(None)

    html_cal = """
    <style>
    .cal-grid { display: grid; grid-template-columns: repeat(7, 1fr); gap: 4px; margin-top: 10px; }
    .cal-cell { min-height: 75px; background: #f9f9f9; border-radius: 8px; padding: 4px 2px; border-top: 3px solid #ddd; overflow: hidden; font-size: 12px; }
    .cal-cell .date { font-weight: bold; font-size: 14px; padding-left: 4px; color: #333; }
    .cal-cell .task-item { font-size: 10px; background: rgba(255,75,75,0.1); border-radius: 4px; padding: 1px 4px; margin: 2px 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; color: #333; }
    .cal-weekday { text-align: center; font-weight: bold; color: #888; font-size: 13px; padding: 6px 0; }
    .cal-empty { min-height: 75px; background: transparent; }
    .today-highlight { background: #ffeb3b30 !important; border: 1px solid #ffc107; }
    @media (max-width: 600px) { .cal-cell { min-height: 60px; font-size: 10px; } .cal-cell .date { font-size: 12px; } .cal-cell .task-item { font-size: 9px; } }
    </style>
    <div class="cal-grid">
    """
    weekdays = ["一", "二", "三", "四", "五", "六", "日"]
    for w in weekdays: html_cal += f'<div class="cal-weekday">{w}</div>'
    today_str = datetime.now().strftime("%Y-%m-%d")
    for dt in cal_dates:
        if dt is None:
            html_cal += '<div class="cal-empty"></div>'
        else:
            date_str = dt.strftime("%Y-%m-%d")
            tasks = tasks_by_date.get(date_str, [])
            is_today = (date_str == today_str)
            border_color = "#e74c3c" if len(tasks) >= 3 else "#f39c12" if len(tasks) >= 1 else "#2ecc71"
            cell_class = "cal-cell today-highlight" if is_today else "cal-cell"
            html_cal += f'<div class="{cell_class}" style="border-top-color: {border_color};"><div class="date">{dt.day}</div>'
            for task in tasks[:4]:
                task_display = task[:6] + "…" if len(task) > 6 else task
                html_cal += f'<div class="task-item">📌 {task_display}</div>'
            if len(tasks) > 4:
                html_cal += f'<div class="task-item" style="color:#888;">+{len(tasks)-4} 项</div>'
            html_cal += '</div>'
    html_cal += '</div><div style="display:flex; gap:16px; margin-top:16px; font-size:13px; flex-wrap:wrap; justify-content:center;"><span>🔴 ≥3项</span><span>🟠 1-2项</span><span>🟢 无任务</span><span>⭐ 今天</span></div>'
    st.markdown(html_cal, unsafe_allow_html=True)

    total_tasks_month = sum(len(v) for v in tasks_by_date.values())
    if total_tasks_month > 0:
        st.info(f"📊 本月共有 **{total_tasks_month}** 项未完成任务，分布在 **{len(tasks_by_date)}** 天里。")
    else:
        st.success("🎉 本月没有未完成的任务，继续保持！")
# ---------- 8. 底部 ----------
st.divider()
st.caption("💡 Pro 终极版：AI解析 | 红绿灯预警 | 月视图 | 图片OCR | 数据备份 | 暗黑主题")
