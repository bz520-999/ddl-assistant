import streamlit as st
import pandas as pd
import requests
import json
import os
from datetime import datetime, timedelta
import base64
import plotly.express as px
import hashlib

# 文件处理依赖
try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

try:
    from docx import Document
except ImportError:
    Document = None

try:
    from pptx import Presentation
except ImportError:
    Presentation = None

try:
    from icalendar import Calendar, Event
except ImportError:
    Calendar = None
    Event = None

try:
    from dateutil import parser as date_parser
except ImportError:
    date_parser = None

# ---------- 页面配置 ----------
st.set_page_config(
    page_title="学习助手 Pro",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# 自定义CSS（手机优化）
st.markdown("""
<style>
    .stApp { max-width: 100%; padding: 0.5rem; }
    .stDataFrame { font-size: 12px; }
    .stButton button { width: 100%; margin: 0.2rem 0; }
    @media (max-width: 600px) {
        .row-widget.stColumns { flex-direction: column !important; }
    }
</style>
""", unsafe_allow_html=True)

# ---------- 数据文件 ----------
DDL_FILE = "deadlines.csv"
LIBRARY_FILE = "library.csv"
CATEGORIES_FILE = "categories.csv"

# ---------- 数据初始化 ----------
# DDL
if "df" not in st.session_state:
    if os.path.exists(DDL_FILE):
        st.session_state.df = pd.read_csv(DDL_FILE)
        for col in ["重复", "状态"]:
            if col not in st.session_state.df.columns:
                st.session_state.df[col] = "无" if col == "重复" else "未完成"
    else:
        st.session_state.df = pd.DataFrame(columns=[
            "课程/科目", "截止日期", "描述", "标签", "重复", "状态", "添加时间"
        ])

# 资料库
if "library" not in st.session_state:
    if os.path.exists(LIBRARY_FILE):
        st.session_state.library = pd.read_csv(LIBRARY_FILE)
    else:
        st.session_state.library = pd.DataFrame(columns=[
            "文件名", "分类", "摘要", "上传时间", "内容"
        ])

# 分类
if "categories" not in st.session_state:
    if os.path.exists(CATEGORIES_FILE):
        st.session_state.categories = pd.read_csv(CATEGORIES_FILE)["分类"].tolist()
    else:
        st.session_state.categories = ["未分类"]  # 默认分类

def save_ddl():
    st.session_state.df.to_csv(DDL_FILE, index=False, encoding="utf-8-sig")

def save_library():
    st.session_state.library.to_csv(LIBRARY_FILE, index=False, encoding="utf-8-sig")

def save_categories():
    pd.DataFrame({"分类": st.session_state.categories}).to_csv(CATEGORIES_FILE, index=False)

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
    """从各种文件中提取文本"""
    text = ""
    file_type = uploaded_file.type
    if file_type == "application/pdf":
        if PdfReader:
            reader = PdfReader(uploaded_file)
            for page in reader.pages:
                text += page.extract_text()
        else:
            st.error("请安装 pypdf")
    elif file_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document" or file_type == "application/msword":
        if Document:
            doc = Document(uploaded_file)
            for para in doc.paragraphs:
                text += para.text + "\n"
        else:
            st.error("请安装 python-docx")
    elif file_type == "application/vnd.openxmlformats-officedocument.presentationml.presentation" or file_type == "application/vnd.ms-powerpoint":
        if Presentation:
            prs = Presentation(uploaded_file)
            for slide in prs.slides:
                for shape in slide.shapes:
                    if hasattr(shape, "text"):
                        text += shape.text + "\n"
        else:
            st.error("请安装 python-pptx")
    elif file_type.startswith("image/"):
        try:
            import easyocr
            import tempfile
            reader = easyocr.Reader(['ch_sim', 'en'], gpu=False)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
                tmp.write(uploaded_file.read())
                tmp_path = tmp.name
            result = reader.readtext(tmp_path, detail=0, paragraph=True)
            text = " ".join(result)
        except ImportError:
            st.error("请安装 easyocr 和 opencv-python-headless")
        except Exception as e:
            st.error(f"OCR失败：{e}")
    else:  # txt 或其他文本格式
        try:
            text = uploaded_file.read().decode("utf-8")
        except:
            try:
                uploaded_file.seek(0)
                text = uploaded_file.read().decode("gbk", errors="ignore")
            except:
                st.error("无法解码文件，请确保是文本文件")
    return text

# ---------- 标题 ----------
st.title("🎓 学习助手 Pro")

# ---------- 侧边栏 ----------
with st.sidebar:
    st.header("⚙️ 设置")
    api_key = st.text_input("DeepSeek API Key", type="password", help="platform.deepseek.com 获取")
    st.divider()
    st.subheader("🎨 主题")
    if st.button("切换暗黑模式"):
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
                save_ddl()
                st.success("恢复成功")
                st.rerun()
        except Exception as e:
            st.error(f"恢复失败：{e}")

# ---------- 主界面标签 ----------
tab_ddl, tab_lib = st.tabs(["📝 DDL管理", "📚 资料库"])

# ==================== DDL 管理 ====================
with tab_ddl:
    st.subheader("📝 添加/管理DDL")
    # 智能输入（简版，可扩展）
    with st.form("ddl_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            course = st.text_input("课程/科目")
            deadline_raw = st.text_input("截止日期 (支持多种格式)")
        with col2:
            notes = st.text_input("描述")
            tag = st.text_input("标签", placeholder="作业/考试")
            repeat = st.selectbox("重复", ["无", "每周", "每月"])
        submitted_ddl = st.form_submit_button("💾 保存DDL")
        if submitted_ddl:
            deadline = parse_flexible_date(deadline_raw)
            if not course or not deadline:
                st.error("课程和截止日期必填")
            else:
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
                save_ddl()
                st.success(f"添加了 {len(new_rows)} 条DDL")
                st.rerun()

    # 显示DDL列表
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
        if not edited.equals(df_display[["课程/科目", "截止日期", "描述", "标签", "状态"]]):
            for _, row in edited.iterrows():
                mask = (st.session_state.df["课程/科目"] == row["课程/科目"]) & (st.session_state.df["截止日期"] == row["截止日期"])
                if mask.any():
                    st.session_state.df.loc[mask, "状态"] = row["状态"]
            save_ddl()
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
                    save_ddl()
                    st.success(f"删除了 {len(selected)} 项")
                    st.rerun()
        with col_del2:
            if st.button("清除所有已完成"):
                before = len(st.session_state.df)
                st.session_state.df = st.session_state.df[st.session_state.df["状态"] != "已完成"]
                save_ddl()
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

# ==================== 资料库管理 ====================
with tab_lib:
    st.subheader("📁 分类管理")
    # 显示现有分类
    col_cat1, col_cat2 = st.columns([3, 1])
    with col_cat1:
        st.write("当前分类：", ", ".join(st.session_state.categories))
    with col_cat2:
        new_cat = st.text_input("新建分类", key="new_cat_input")
        if st.button("➕ 添加分类"):
            if new_cat.strip() and new_cat.strip() not in st.session_state.categories:
                st.session_state.categories.append(new_cat.strip())
                save_categories()
                st.success(f"分类 '{new_cat.strip()}' 已添加")
                st.rerun()
            else:
                st.warning("分类已存在或为空")

    # 删除分类（仅当分类下无文件）
    with st.expander("🗑️ 删除分类（仅当为空）"):
        del_cat = st.selectbox("选择要删除的分类", st.session_state.categories, key="del_cat_select")
        if st.button("确认删除分类"):
            # 检查该分类下是否有文件
            if not st.session_state.library[st.session_state.library["分类"] == del_cat].empty:
                st.error(f"分类 '{del_cat}' 下还有文件，请先移走或删除文件")
            else:
                st.session_state.categories.remove(del_cat)
                save_categories()
                st.success(f"分类 '{del_cat}' 已删除")
                st.rerun()

    st.divider()
    st.subheader("📤 上传文件到资料库")
    with st.form("upload_lib_form"):
        uploaded_file = st.file_uploader("选择文件 (支持 PDF/Word/PPT/图片/TXT等)", type=None, key="lib_upload")
        # 选择分类
        cat_options = st.session_state.categories + ["新建分类..."]
        selected_cat = st.selectbox("选择分类", cat_options, key="lib_cat_select")
        if selected_cat == "新建分类...":
            new_cat_name = st.text_input("请输入新分类名称")
        else:
            new_cat_name = None
        lib_notes = st.text_area("备注（可选）")
        submitted_lib = st.form_submit_button("📥 保存到资料库")
        if submitted_lib and uploaded_file is not None:
            # 确定分类
            if new_cat_name and new_cat_name.strip():
                final_cat = new_cat_name.strip()
                if final_cat not in st.session_state.categories:
                    st.session_state.categories.append(final_cat)
                    save_categories()
            else:
                final_cat = selected_cat
            # 提取内容
            content = extract_text_from_file(uploaded_file)
            if content is None:
                st.error("文件内容提取失败，请检查文件格式")
                st.stop()
            # 生成摘要
            summary = content[:200] + ("..." if len(content)>200 else "")
            new_row = {
                "文件名": uploaded_file.name,
                "分类": final_cat,
                "摘要": summary,
                "上传时间": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "内容": content
            }
            st.session_state.library = pd.concat([st.session_state.library, pd.DataFrame([new_row])], ignore_index=True)
            save_library()
            st.success(f"文件 '{uploaded_file.name}' 已保存到分类 '{final_cat}'")
            st.rerun()

    st.divider()
    st.subheader("📂 资料浏览")
    # 筛选
    filter_cat = st.selectbox("按分类筛选", ["全部"] + st.session_state.categories, key="lib_filter_cat")
    search_lib = st.text_input("搜索资料（文件名或内容）", key="lib_search")
    df_lib = st.session_state.library.copy()
    if filter_cat != "全部":
        df_lib = df_lib[df_lib["分类"] == filter_cat]
    if search_lib:
        df_lib = df_lib[df_lib["文件名"].str.contains(search_lib, na=False) | df_lib["摘要"].str.contains(search_lib, na=False) | df_lib["内容"].str.contains(search_lib, na=False)]

    if df_lib.empty:
        st.info("暂无资料")
    else:
        # 按分类分组显示
        for cat in st.session_state.categories:
            cat_df = df_lib[df_lib["分类"] == cat]
            if cat_df.empty:
                continue
            st.markdown(f"### 📁 {cat}")
            for idx, row in cat_df.iterrows():
                with st.container():
                    col1, col2, col3 = st.columns([3, 1, 1])
                    with col1:
                        st.markdown(f"**{row['文件名']}**")
                        st.caption(row['摘要'])
                    with col2:
                        if st.button("📄 查看全文", key=f"view_{idx}"):
                            st.text_area("完整内容", row['内容'], height=150)
                    with col3:
                        if st.button("🗑️ 删除", key=f"del_{idx}"):
                            st.session_state.library = st.session_state.library.drop(index=idx).reset_index(drop=True)
                            save_library()
                            st.rerun()
            st.divider()

    # 导出资料库
    st.subheader("📤 导出资料库")
    if st.button("导出资料库CSV"):
        csv = st.session_state.library.to_csv(index=False)
        b64 = base64.b64encode(csv.encode()).decode()
        st.markdown(f'<a href="data:file/csv;base64,{b64}" download="library.csv">下载CSV</a>', unsafe_allow_html=True)

st.caption("💡 支持多种文件格式，自动提取文本，按分类管理，保留原文件名")
