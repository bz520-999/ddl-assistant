"""
学习助手 Pro —— DDL 智能管理与学习资料库系统
============================================

功能概述：
    1. DDL 管理：自然语言/文件输入 → AI 解析 → 结构化任务管理
    2. 可视化：月历视图、任务分布柱状图、标签饼图
    3. 资料库：多格式文件上传、分类管理、全文检索
    4. AI 能力：DDL 语义解析、复习优先级规划
    5. 数据导入导出：CSV / ICS 日历 / Markdown / JSON 备份

技术栈：
    - 前端框架：Streamlit
    - LLM 服务：DeepSeek API (deepseek-chat)
    - 文件解析：pypdf, python-docx, python-pptx, easyocr
    - 可视化：Plotly, HTML/CSS Calendar Grid
    - 数据存储：CSV 文件持久化

作者：[你的名字]
日期：[日期]
"""

# ============================================================
# 1. 标准库导入
# ============================================================
import streamlit as st
import pandas as pd
import requests
import json
import os
from datetime import datetime, timedelta
import base64
import plotly.express as px

# ============================================================
# 2. 可选依赖导入（带容错，缺失时功能降级）
# ============================================================

# PDF 解析
try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

# Word 文档解析
try:
    from docx import Document
except ImportError:
    Document = None

# PowerPoint 解析
try:
    from pptx import Presentation
except ImportError:
    Presentation = None

# iCal 日历导出
try:
    from icalendar import Calendar, Event
except ImportError:
    Calendar = None
    Event = None

# 柔性日期解析
try:
    from dateutil import parser as date_parser
except ImportError:
    date_parser = None


# ============================================================
# 3. 页面全局配置
# ============================================================
st.set_page_config(
    page_title="学习助手 Pro",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# 全局 CSS：移动端适配 + 日历网格样式
st.markdown("""
<style>
    /* 主容器自适应 */
    .stApp { max-width: 100%; padding: 0.5rem; }
    .stDataFrame { font-size: 12px; }
    .stButton button { width: 100%; margin: 0.2rem 0; }

    /* 移动端：列布局转为纵向排列 */
    @media (max-width: 600px) {
        .row-widget.stColumns { flex-direction: column !important; }
    }

    /* 日历网格：7列等宽 */
    .cal-grid { display: grid; grid-template-columns: repeat(7, 1fr); gap: 2px; }
    .cal-cell { min-height: 60px; background: #f9f9f9; border-radius: 4px;
                padding: 2px; border-top: 3px solid #ddd; overflow: hidden; font-size: 11px; }
    .cal-cell .date { font-weight: bold; font-size: 13px; }
    .cal-weekday { text-align: center; font-weight: bold; color: #888; font-size: 13px; padding: 4px 0; }
</style>
""", unsafe_allow_html=True)


# ============================================================
# 4. 数据文件路径常量
# ============================================================
DDL_FILE = "deadlines.csv"          # DDL 数据文件
LIBRARY_FILE = "library.csv"        # 资料库数据文件
CATEGORIES_FILE = "categories.csv"  # 分类配置文件


# ============================================================
# 5. Session State 初始化
# ============================================================

# --- DDL 数据表 ---
# 字段：课程/科目 | 截止日期 | 描述 | 标签 | 重复 | 状态 | 添加时间
if "df" not in st.session_state:
    if os.path.exists(DDL_FILE):
        st.session_state.df = pd.read_csv(DDL_FILE)
        # 兼容旧数据：缺失列自动补全
        for col in ["重复", "状态"]:
            if col not in st.session_state.df.columns:
                st.session_state.df[col] = "无" if col == "重复" else "未完成"
    else:
        st.session_state.df = pd.DataFrame(columns=[
            "课程/科目", "截止日期", "描述", "标签", "重复", "状态", "添加时间"
        ])

# --- 资料库数据表 ---
# 字段：文件名 | 分类 | 摘要 | 上传时间 | 内容
if "library" not in st.session_state:
    if os.path.exists(LIBRARY_FILE):
        st.session_state.library = pd.read_csv(LIBRARY_FILE)
    else:
        st.session_state.library = pd.DataFrame(columns=[
            "文件名", "分类", "摘要", "上传时间", "内容"
        ])

# --- 分类列表 ---
if "categories" not in st.session_state:
    if os.path.exists(CATEGORIES_FILE):
        st.session_state.categories = pd.read_csv(CATEGORIES_FILE)["分类"].tolist()
    else:
        st.session_state.categories = ["未分类"]


# ============================================================
# 6. 数据持久化函数
# ============================================================

def save_ddl():
    """将 DDL 数据表写入 CSV 文件"""
    st.session_state.df.to_csv(DDL_FILE, index=False, encoding="utf-8-sig")

def save_library():
    """将资料库数据表写入 CSV 文件"""
    st.session_state.library.to_csv(LIBRARY_FILE, index=False, encoding="utf-8-sig")

def save_categories():
    """将分类列表写入 CSV 文件"""
    pd.DataFrame({"分类": st.session_state.categories}).to_csv(CATEGORIES_FILE, index=False)


# ============================================================
# 7. 辅助工具函数
# ============================================================

def parse_flexible_date(date_str):
    """
    柔性日期解析：支持多种格式输入，返回统一的 YYYY-MM-DD 字符串。

    解析优先级：
        1. 标准格式：YYYY-MM-DD, YYYY/MM/DD
        2. 短格式：MM/DD（自动补全为当前年份）
        3. dateutil 模糊解析（自然语言日期）

    Args:
        date_str: 用户输入的日期字符串

    Returns:
        str: YYYY-MM-DD 格式日期，解析失败返回 None
    """
    if not date_str:
        return None

    # 预处理：去除中文标点
    date_str = date_str.strip().replace("。", "").replace("，", ",")

    # 尝试确定性格式
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d"):
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue

    # 尝试 dateutil 模糊解析
    if date_parser:
        try:
            dt = date_parser.parse(date_str, fuzzy=True)
            return dt.strftime("%Y-%m-%d")
        except (ValueError, OverflowError):
            pass

    return None


def extract_text_from_file(uploaded_file):
    """
    从上传的文件中提取纯文本内容。

    支持格式及对应解析库：
        - PDF          → pypdf
        - Word (.docx) → python-docx
        - PPT (.pptx)  → python-pptx
        - 图片 (jpg等) → easyocr (OCR)
        - 其他 (txt等)  → 内置解码 (UTF-8/GBK)

    Args:
        uploaded_file: Streamlit UploadedFile 对象

    Returns:
        str: 提取的文本内容，失败返回空字符串
    """
    text = ""
    file_type = uploaded_file.type

    # --- PDF 文件 ---
    if file_type == "application/pdf":
        if PdfReader:
            reader = PdfReader(uploaded_file)
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        else:
            st.error("请安装 pypdf：pip install pypdf")

    # --- Word 文档 ---
    elif "word" in file_type or "document" in file_type:
        if Document:
            doc = Document(uploaded_file)
            for para in doc.paragraphs:
                text += para.text + "\n"
        else:
            st.error("请安装 python-docx：pip install python-docx")

    # --- PowerPoint ---
    elif "presentation" in file_type or "powerpoint" in file_type:
        if Presentation:
            prs = Presentation(uploaded_file)
            for slide in prs.slides:
                for shape in slide.shapes:
                    if hasattr(shape, "text"):
                        text += shape.text + "\n"
        else:
            st.error("请安装 python-pptx：pip install python-pptx")

    # --- 图片（OCR 识别）---
    elif file_type.startswith("image/"):
        try:
            import easyocr
            import tempfile
            reader = easyocr.Reader(['ch_sim', 'en'], gpu=False)
            # 写入临时文件供 easyocr 读取
            with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
                tmp.write(uploaded_file.read())
                tmp_path = tmp.name
            result = reader.readtext(tmp_path, detail=0, paragraph=True)
            text = " ".join(result)
        except ImportError:
            st.error("请安装 easyocr 和 opencv-python-headless")
        except Exception as e:
            st.error(f"OCR 失败：{e}")

    # --- 纯文本等其他格式 ---
    else:
        try:
            text = uploaded_file.read().decode("utf-8")
        except UnicodeDecodeError:
            try:
                uploaded_file.seek(0)
                text = uploaded_file.read().decode("gbk", errors="ignore")
            except Exception:
                st.error("无法解码文件，请检查文件编码")

    return text


def call_deepseek_api(api_key, prompt, temperature=0.1, timeout=30):
    """
    调用 DeepSeek Chat API 的通用封装函数。

    Args:
        api_key: DeepSeek API 密钥
        prompt: 用户提示词
        temperature: 生成温度，越低越确定性 (默认 0.1)
        timeout: 请求超时秒数 (默认 30)

    Returns:
        str: 模型返回的文本内容，失败返回 None
    """
    try:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature
        }
        response = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers=headers, json=payload, timeout=timeout
        )
        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"]
        else:
            st.error(f"API 调用失败（HTTP {response.status_code}）")
            return None
    except requests.exceptions.Timeout:
        st.error("API 请求超时，请稍后重试")
        return None
    except Exception as e:
        st.error(f"API 调用出错：{e}")
        return None


# ============================================================
# 8. 页面标题
# ============================================================
st.title("🎓 学习助手 Pro")


# ============================================================
# 9. 侧边栏：设置面板
# ============================================================
with st.sidebar:
    st.header("⚙️ 设置")

    # API Key 输入
    api_key = st.text_input(
        "DeepSeek API Key",
        type="password",
        help="前往 platform.deepseek.com 获取"
    )

    st.divider()

    # --- 主题切换 ---
    st.subheader("🎨 主题")
    if st.button("切换暗黑模式"):
        st.session_state.dark = not st.session_state.get("dark", False)
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

    # --- 数据备份与恢复 ---
    st.subheader("💾 数据备份")

    # 备份 DDL
    json_ddl = st.session_state.df.to_json(orient="records", force_ascii=False)
    st.download_button("📥 备份DDL", data=json_ddl, file_name="backup_ddl.json")

    # 备份资料库
    json_lib = st.session_state.library.to_json(orient="records", force_ascii=False)
    st.download_button("📥 备份资料库", data=json_lib, file_name="backup_library.json")

    # 恢复 DDL 备份
    uploaded_backup = st.file_uploader("恢复DDL备份", type=["json"], key="restore_ddl")
    if uploaded_backup:
        try:
            new_data = pd.DataFrame(json.loads(uploaded_backup.read()))
            if not new_data.empty:
                st.session_state.df = new_data
                save_ddl()
                st.success("DDL 备份恢复成功")
                st.rerun()
        except Exception as e:
            st.error(f"恢复失败：{e}")


# ============================================================
# 10. 智能输入区：统一处理文字输入和文件上传
# ============================================================
st.markdown("### ✨ 智能输入")

with st.container():
    input_col, btn_col = st.columns([5, 1])

    with input_col:
        smart_input = st.text_area(
            "输入DDL或上传文件",
            placeholder="例如：下周一交高数作业，或上传课件",
            height=80,
            key="smart_input"
        )

    with btn_col:
        st.write("")
        st.write("")
        send_btn

服务器繁忙，请稍后再试
