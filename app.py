import streamlit as st
import pandas as pd
import requests
import json
import os
from datetime import datetime, timedelta
import base64
import plotly.express as px
import hashlib

# 可选依赖
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

# ---------- 页面配置（手机优化） ----------
st.set_page_config(
    page_title="学习助手 Pro",
    layout="centered",
    initial_sidebar_state="collapsed"  # 侧边栏默认收起
)

# 自定义CSS，优化手机显示
st.markdown("""
<style>
    /* 让卡片在手机上占满宽度 */
    .stApp {
        max-width: 100%;
        padding: 0.5rem;
    }
    /* 表格字体缩小 */
    .stDataFrame {
        font-size: 12px;
    }
    /* 按钮适应小屏 */
    .stButton button {
        width: 100%;
        margin: 0.2rem 0;
    }
    /* 移动端列间距 */
    @media (max-width: 600px) {
        .row-widget.stColumns {
            flex-direction: column !important;
        }
    }
</style>
""", unsafe_allow_html=True)

# ---------- 数据初始化 ----------
DATA_FILE = "deadlines.csv"
LIBRARY_FILE = "library.csv"

# DDL数据
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

# 资料库数据
if "library" not in st.session_state:
    if os.path.exists(LIBRARY_FILE):
        st.session_state.library = pd.read_csv(LIBRARY_FILE)
    else:
        st.session_state.library = pd.DataFrame(columns=[
            "文件名", "分类", "摘要", "上传时间", "文件内容"  # 可存储base64或文本
        ])

def save_data():
    st.session_state.df.to_csv(DATA_FILE, index=False, encoding="utf-8-sig")

def save_library():
    st.session_state.library.to_csv(LIBRARY_FILE, index=False, encoding="utf-8-sig")

# ---------- 辅助函数 ----------
def parse_flexible_date(date_str):
    if not date_str:
        return None
    date_str = date_str.strip().replace("。", "").replace("，", ",")
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d"):
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime("%Y-%m-%d")
        except:
            continue
    if date_parser:
        try:
            dt = date_parser.parse(date_str, fuzzy=True)
            return dt.strftime("%Y-%m-%d")
        except:
            pass
    return None

def extract_text_from_file(uploaded_file):
    """从上传的文件中提取文本"""
    text = ""
    if uploaded_file.type == "application/pdf":
        if PdfReader:
            reader = PdfReader(uploaded_file)
            for page in reader.pages:
                text += page.extract_text()
        else:
            st.error("请安装 pypdf")
    elif uploaded_file.type.startswith("image/"):
        try:
            import easyocr
            import tempfile
            reader = easyocr.Reader(['ch_sim', 'en'], gpu=False)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
                tmp.write(uploaded_file.read())
                tmp_path = tmp.name
            result = reader.readtext(tmp_path, detail=0, paragraph=True)
            text = " ".join(result)
            st.success("✅ 图片OCR识别成功")
        except ImportError:
            st.error("请安装 easyocr 和 opencv-python-headless")
        except Exception as e:
            st.error(f"OCR失败：{e}")
    else:  # txt等
        try:
            text = uploaded_file.read().decode("utf-8")
        except:
            text = uploaded_file.read().decode("gbk", errors="ignore")
    return text

# ---------- 标题 ----------
st.title("🎓 学习助手 Pro")

# ---------- 统一智能输入区 ----------
st.markdown("### ✨ 智能输入（文字 / 文件）")
with st.container():
    input_col, btn_col = st.columns([5, 1])
    with input_col:
        user_input = st.text_area("输入DDL或上传文件", placeholder="例如：下周一交高数作业，或上传课件PDF", height=80, key="smart_input")
    with btn_col:
        st.write("")  # 占位
        st.write("")
        send_btn = st.button("🚀 发送", use_container_width=True)

    uploaded_file = st.file_uploader("或点击上传文件 (PDF/图片/PPT等)", type=["pdf", "png", "jpg", "jpeg", "txt", "pptx"], key="smart_file", label_visibility="collapsed")

    if send_btn:
        # 处理输入
        if uploaded_file is not None:
            # 有文件上传，提取内容
            file_text = extract_text_from_file(uploaded_file)
            if file_text:
                # 合并用户输入的文字和文件内容
                combined_text = user_input + "\n" + file_text if user_input else file_text
                # 让AI判断是DDL还是资料
                with st.spinner("AI识别中..."):
                    try:
                        # 这里调用AI判断意图，并提取信息
                        # 为了简化，我们提供两种选项：手动选择类型
                        st.session_state["parsed_text"] = combined_text
                        st.session_state["uploaded_filename"] = uploaded_file.name
                        st.success("文件已读取，请到下方选择分类并保存")
                    except Exception as e:
                        st.error(f"处理失败：{e}")
            else:
                st.warning("未能提取文件内容，请确保文件可读")
        elif user_input.strip():
            # 纯文字，调用AI解析DDL
            if not api_key:
                st.error("请先在左侧设置 DeepSeek API Key")
            else:
                with st.spinner("AI解析中..."):
                    try:
                        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
                        prompt = f"""提取学习任务信息。规则：
1. 如果是DDL，提取课程名称、截止日期(转为YYYY-MM-DD)、描述。
2. 如果不是DDL，请返回 {{"type": "other", "content": "原文"}}。
只返回JSON。
文本：{user_input}"""
                        payload = {
                            "model": "deepseek-chat",
                            "messages": [{"role": "user", "content": prompt}],
                            "temperature": 0.1
                        }
                        response = requests.post("https://api.deepseek.com/v1/chat/completions",
                                                headers=headers, json=payload, timeout=30)
                        if response.status_code == 200:
                            content = response.json()["choices"][0]["message"]["content"]
                            content = content.replace("```json", "").replace("```", "").strip()
                            parsed = json.loads(content)
                            if parsed.get("course") and parsed.get("deadline"):
                                # 是DDL
                                st.session_state["parsed_course"] = parsed.get("course", "")
                                st.session_state["parsed_deadline"] = parsed.get("deadline", "")
                                st.session_state["parsed_notes"] = parsed.get("notes", "")
                                st.success("✅ 识别为DDL，已自动填入下方表单")
                            else:
                                st.info("识别为普通文本，已存入暂存区")
                                st.session_state["parsed_other"] = parsed.get("content", user_input)
                        else:
                            st.error("AI解析失败")
                    except Exception as e:
                        st.error(f"出错：{e}")
        else:
            st.warning("请输入内容或上传文件")

# ---------- 手动录入（DDL和资料分开） ----------
st.divider()
tab_ddl, tab_lib, tab_view = st.tabs(["📝 DDL管理", "📚 资料库管理", "📊 看板"])

# ----- DDL管理（整合原添加与解析、管理、导出等） -----
with tab_ddl:
    st.subheader("📝 添加/管理DDL")
    # 如果AI解析了DDL，自动填充
    with st.form("ddl_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            course = st.text_input("课程/科目", value=st.session_state.get("parsed_course", ""))
            deadline_raw = st.text_input("截止日期 (支持多种格式)", value=st.session_state.get("parsed_deadline", ""))
        with col2:
            notes = st.text_input("描述", value=st.session_state.get("parsed_notes", ""))
            tag = st.text_input("标签", placeholder="作业/考试")
            repeat = st.selectbox("重复", ["无", "每周", "每月"])
        submitted_ddl = st.form_submit_button("💾 保存DDL")
        if submitted_ddl:
            deadline = parse_flexible_date(deadline_raw)
            if not course or not deadline:
                st.error("课程和截止日期必填")
            else:
                # 生成重复任务
                new_rows = []
                try:
                    start_date = datetime.strptime(deadline, "%Y-%m-%d")
                    dates = []
                    if repeat == "无":
                        dates = [start_date]
                    elif repeat == "每周":
                        dates = [start_date + timedelta(weeks=i) for i in range(4)]
                    elif repeat == "每月":
                        for i in range(3):
                            m = start_date.month + i
                            y = start_date.year + (m-1)//12
                            m = (m-1)%12 + 1
                            try:
                                dates.append(datetime(y, m, start_date.day))
                            except:
                                dates.append(datetime(y, m, 1))
                except:
                    st.error("日期格式错误")
                    st.stop()
                for dt in dates:
                    new_rows.append({
                        "课程/科目": course,
                        "截止日期": dt.strftime("%Y-%m-%d"),
                        "描述": notes,
                        "标签": tag if tag else "未分类",
                        "重复": repeat,
                        "状态": "未完成",
                        "添加时间": datetime.now().strftime("%Y-%m-%d %H:%M")
                    })
                st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame(new_rows)], ignore_index=True)
                save_data()
                # 清空暂存
                for key in ["parsed_course", "parsed_deadline", "parsed_notes"]:
                    if key in st.session_state: del st.session_state[key]
                st.success(f"添加了 {len(new_rows)} 条DDL")
                st.rerun()

    # 显示DDL列表（管理）
    st.subheader("📋 当前DDL")
    search = st.text_input("搜索DDL", key="ddl_search")
    filter_status = st.selectbox("状态筛选", ["全部", "未完成", "已完成"], key="ddl_status")
    df_display = st.session_state.df.copy()
    if search:
        df_display = df_display[df_display["课程/科目"].str.contains(search, na=False) | df_display["描述"].str.contains(search, na=False)]
    if filter_status != "全部":
        df_display = df_display[df_display["状态"] == filter_status]
    if not df_display.empty:
        edited = st.data_editor(
            df_display[["课程/科目", "截止日期", "描述", "标签", "状态"]],
            column_config={
                "状态": st.column_config.SelectboxColumn("状态", options=["未完成", "已完成"])
            },
            hide_index=True,
            key="ddl_edit"
        )
        # 保存状态变化
        if not edited.equals(df_display[["课程/科目", "截止日期", "描述", "标签", "状态"]]):
            for _, row in edited.iterrows():
                mask = (st.session_state.df["课程/科目"] == row["课程/科目"]) & (st.session_state.df["截止日期"] == row["截止日期"])
                if mask.any():
                    st.session_state.df.loc[mask, "状态"] = row["状态"]
            save_data()
            st.success("状态已更新")
            st.rerun()
        # 批量删除
        st.divider()
        st.subheader("🗑️ 批量操作")
        df_del = df_display.copy()
        df_del["选择"] = False
        edited_del = st.data_editor(
            df_del[["选择", "课程/科目", "截止日期", "状态"]],
            column_config={"选择": st.column_config.CheckboxColumn("勾选")},
            hide_index=True,
            key="ddl_del"
        )
        col_del1, col_del2 = st.columns(2)
        with col_del1:
            if st.button("删除选中"):
                selected = edited_del[edited_del["选择"] == True]
                if not selected.empty:
                    for _, row in selected.iterrows():
                        mask = (st.session_state.df["课程/科目"] == row["课程/科目"]) & (st.session_state.df["截止日期"] == row["截止日期"])
                        if mask.any():
                            st.session_state.df = st.session_state.df.drop(st.session_state.df[mask].index)
                    save_data()
                    st.success(f"删除了 {len(selected)} 项")
                    st.rerun()
        with col_del2:
            if st.button("清除所有已完成"):
                before = len(st.session_state.df)
                st.session_state.df = st.session_state.df[st.session_state.df["状态"] != "已完成"]
                save_data()
                st.success(f"清除 {before - len(st.session_state.df)} 项")
                st.rerun()
    else:
        st.info("没有匹配的DDL")

    # 导出DDL
    st.subheader("📤 导出")
    if st.button("导出CSV"):
        csv = st.session_state.df.to_csv(index=False)
        b64 = base64.b64encode(csv.encode()).decode()
        st.markdown(f'<a href="data:file/csv;base64,{b64}" download="deadlines.csv">下载CSV</a>', unsafe_allow_html=True)

# ----- 资料库管理 -----
with tab_lib:
    st.subheader("📚 资料库")
    # 添加资料（从上传的文件或粘贴文本）
    with st.expander("➕ 添加资料到库"):
        lib_file = st.file_uploader("上传文件", type=["pdf", "png", "jpg", "jpeg", "txt", "pptx"], key="lib_upload")
        lib_text = st.text_area("或粘贴文本内容", height=100)
        lib_category = st.text_input("分类（如 数学课件）", placeholder="例如：数学课件")
        if st.button("保存到资料库"):
            content = ""
            filename = ""
            if lib_file is not None:
                content = extract_text_from_file(lib_file)
                filename = lib_file.name
                if not content:
                    st.warning("未能提取内容")
                    st.stop()
            elif lib_text.strip():
                content = lib_text
                filename = "粘贴文本"
            else:
                st.warning("请上传文件或输入文本")
                st.stop()
            if not lib_category.strip():
                lib_category = "未分类"
            # 生成摘要（取前200字）
            summary = content[:200] + ("..." if len(content)>200 else "")
            new_row = {
                "文件名": filename,
                "分类": lib_category,
                "摘要": summary,
                "上传时间": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "文件内容": content  # 可存储全文
            }
            st.session_state.library = pd.concat([st.session_state.library, pd.DataFrame([new_row])], ignore_index=True)
            save_library()
            st.success("资料已保存")
            st.rerun()

    # 显示资料库
    st.subheader("📂 已有资料")
    cat_filter = st.selectbox("分类筛选", ["全部"] + list(st.session_state.library["分类"].unique()), key="lib_cat")
    search_lib = st.text_input("搜索资料", key="lib_search")
    df_lib = st.session_state.library.copy()
    if cat_filter != "全部":
        df_lib = df_lib[df_lib["分类"] == cat_filter]
    if search_lib:
        df_lib = df_lib[df_lib["摘要"].str.contains(search_lib, na=False) | df_lib["文件名"].str.contains(search_lib, na=False)]
    if not df_lib.empty:
        for idx, row in df_lib.iterrows():
            with st.container():
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.markdown(f"**{row['文件名']}**  ({row['分类']})")
                    st.caption(row['摘要'])
                with col2:
                    if st.button("查看详情", key=f"view_{idx}"):
                        st.text_area("完整内容", row['文件内容'], height=200)
                    if st.button("删除", key=f"del_{idx}"):
                        st.session_state.library = st.session_state.library.drop(index=idx).reset_index(drop=True)
                        save_library()
                        st.rerun()
    else:
        st.info("暂无资料")

# ----- 看板（统计+月视图） -----
with tab_view:
    st.subheader("📊 数据看板")
    total = len(st.session_state.df)
    done = len(st.session_state.df[st.session_state.df["状态"] == "已完成"])
    if total > 0:
        st.metric("总任务", total, delta=f"已完成 {done}")
        st.progress(done/total if total>0 else 0, text=f"进度 {done/total*100:.0f}%")
    else:
        st.info("暂无DDL")

    # 月视图（简化）
    st.subheader("📆 月视图")
    # 取当前月份
    if "cal_year" not in st.session_state:
        st.session_state.cal_year = datetime.now().year
        st.session_state.cal_month = datetime.now().month
    c1, c2, c3 = st.columns([1,2,1])
    with c1:
        if st.button("◀"):
            if st.session_state.cal_month == 1:
                st.session_state.cal_month = 12
                st.session_state.cal_year -= 1
            else:
                st.session_state.cal_month -= 1
            st.rerun()
    with c2:
        st.write(f"{st.session_state.cal_year}年{st.session_state.cal_month}月")
    with c3:
        if st.button("▶"):
            if st.session_state.cal_month == 12:
                st.session_state.cal_month = 1
                st.session_state.cal_year += 1
            else:
                st.session_state.cal_month += 1
            st.rerun()
    year = st.session_state.cal_year
    month = st.session_state.cal_month
    # 生成日历数据
    first = datetime(year, month, 1)
    if month == 12:
        last = datetime(year+1, 1, 1) - timedelta(days=1)
    else:
        last = datetime(year, month+1, 1) - timedelta(days=1)
    start_week = first.weekday()
    total_days = last.day
    df_cal = st.session_state.df[st.session_state.df["状态"] != "已完成"]
    tasks = {}
    if not df_cal.empty:
        df_cal["截止日期"] = pd.to_datetime(df_cal["截止日期"], errors='coerce')
        df_cal = df_cal.dropna(subset=["截止日期"])
        for _, row in df_cal.iterrows():
            if row["截止日期"].year == year and row["截止日期"].month == month:
                key = row["截止日期"].strftime("%Y-%m-%d")
                tasks.setdefault(key, []).append(row["课程/科目"])
    cal = [None]*start_week + [datetime(year, month, d) for d in range(1, total_days+1)]
    while len(cal) < 42:
        cal.append(None)
    html = "<div style='display:grid;grid-template-columns:repeat(7,1fr);gap:2px;'>"
    for w in ["一","二","三","四","五","六","日"]:
        html += f"<div style='text-align:center;font-weight:bold;'>{w}</div>"
    for d in cal:
        if d is None:
            html += "<div style='min-height:40px;'></div>"
        else:
            key = d.strftime("%Y-%m-%d")
            t = tasks.get(key, [])
            color = "red" if len(t)>=3 else "orange" if len(t)>=1 else "green"
            html += f"<div style='border-top:3px solid {color};min-height:40px;background:#f9f9f9;padding:2px;'><div>{d.day}</div>"
            for task in t[:2]:
                html += f"<div style='font-size:9px;'>{task[:4]}</div>"
            if len(t)>2:
                html += f"<div style='font-size:9px;'>+{len(t)-2}</div>"
            html += "</div>"
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)

# ---------- 侧边栏（配置、备份、主题） ----------
with st.sidebar:
    st.header("⚙️ 设置")
    api_key = st.text_input("DeepSeek API Key", type="password", help="platform.deepseek.com 获取")
    st.divider()
    st.subheader("🎨 主题")
    if st.button("切换暗黑模式"):
        # 简单切换，通过session_state记录
        if "dark" not in st.session_state:
            st.session_state.dark = False
        st.session_state.dark = not st.session_state.dark
        if st.session_state.dark:
            st.markdown("""
            <style>
            .stApp { background-color: #1e1e1e; color: #fff; }
            .stApp * { color: #eee; }
            .stButton button { background-color: #333; color: white; }
            </style>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <style>
            .stApp { background-color: #fff; color: #000; }
            </style>
            """, unsafe_allow_html=True)

    st.divider()
    st.subheader("💾 数据备份")
    json_str = st.session_state.df.to_json(orient="records", force_ascii=False)
    st.download_button("📥 备份DDL", data=json_str, file_name="backup_ddl.json")
    lib_json = st.session_state.library.to_json(orient="records", force_ascii=False)
    st.download_button("📥 备份资料库", data=lib_json, file_name="backup_library.json")
    uploaded_backup = st.file_uploader("恢复DDL备份", type=["json"], key="restore_ddl")
    if uploaded_backup:
        import json as json_lib
        try:
            new_data = pd.DataFrame(json_lib.loads(uploaded_backup.read()))
            if not new_data.empty:
                st.session_state.df = new_data
                save_data()
                st.success("恢复成功")
                st.rerun()
        except Exception as e:
            st.error(f"恢复失败：{e}")

st.caption("💡 智能输入：文字直接解析DDL，文件自动提取内容并分类保存")
