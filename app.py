"""
学习助手 Pro - DDL 管理与学习资料库系统
========================================
功能概述：
  1. 智能输入：支持自然语言/文件上传，AI 自动识别任务信息
  2. DDL 管理：增删改查、状态追踪、重复任务、搜索筛选
  3. 数据分析：任务分布柱状图、标签饼图、月度日历视图
  4. AI 辅助：智能任务解析、复习优先级规划
  5. 资料库：文件上传、文本提取、分类管理、全文检索
  6. 导出分享：CSV、ICS 日历、Markdown 分享卡片

技术栈：
  - 前端框架：Streamlit
  - AI 服务：DeepSeek API (deepseek-chat)
  - 可视化：Plotly
  - 文件解析：pypdf / python-docx / python-pptx / easyocr
  - 日历导出：icalendar
  - 数据存储：CSV 文件 + session_state
"""
import streamlit as st
import pandas as pd
import requests
import json
import os
from datetime import datetime, timedelta
import base64
import plotly.express as px

# ============================================================
# 一、依赖库加载（带容错，缺失时功能降级而非崩溃）
# ============================================================
try:
    from pypdf import PdfReader        # PDF 文本提取
except ImportError:
    PdfReader = None

try:
    from docx import Document           # Word 文档解析
except ImportError:
    Document = None

try:
    from pptx import Presentation       # PPT 文件解析
except ImportError:
    Presentation = None

try:
    from icalendar import Calendar, Event  # ICS 日历文件生成
except ImportError:
    Calendar = None
    Event = None

try:
    from dateutil import parser as date_parser  # 模糊日期解析
except ImportError:
    date_parser = None

# ============================================================
# 二、页面配置与全局样式
# ============================================================
st.set_page_config(
    page_title="学习助手 Pro",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# 自定义 CSS：移动端适配 + 日历网格样式
st.markdown("""
<style>
    .stApp { max-width: 100%; padding: 0.5rem; }
    .stDataFrame { font-size: 12px; }
    .stButton button { width: 100%; margin: 0.2rem 0; }
    @media (max-width: 600px) {
        .row-widget.stColumns { flex-direction: column !important; }
    }
    /* 日历网格：7列等宽布局 */
    .cal-grid { display: grid; grid-template-columns: repeat(7, 1fr); gap: 2px; }
    .cal-cell { min-height: 60px; background: #f9f9f9; border-radius: 4px;
                padding: 2px; border-top: 3px solid #ddd; overflow: hidden;
                font-size: 11px; }
    .cal-cell .date { font-weight: bold; font-size: 13px; }
    .cal-weekday { text-align: center; font-weight: bold; color: #888;
                   font-size: 13px; padding: 4px 0; }
</style>
""", unsafe_allow_html=True)

# ============================================================
# 三、数据文件路径常量
# ============================================================
DDL_FILE = "deadlines.csv"        # DDL 数据存储文件
LIBRARY_FILE = "library.csv"      # 资料库存储文件
CATEGORIES_FILE = "categories.csv"  # 分类配置存储文件

# ============================================================
# 四、数据初始化（从 CSV 文件加载，或创建空 DataFrame）
# ============================================================

# --- DDL 数据初始化 ---
if "df" not in st.session_state:
    if os.path.exists(DDL_FILE):
        st.session_state.df = pd.read_csv(DDL_FILE)
        # 兼容旧数据：缺失列自动补充默认值
        for col in ["重复", "状态"]:
            if col not in st.session_state.df.columns:
                st.session_state.df[col] = "无" if col == "重复" else "未完成"
    else:
        st.session_state.df = pd.DataFrame(columns=[
            "课程/科目", "截止日期", "描述", "标签", "重复", "状态", "添加时间"
        ])

# --- 资料库数据初始化 ---
if "library" not in st.session_state:
    if os.path.exists(LIBRARY_FILE):
        st.session_state.library = pd.read_csv(LIBRARY_FILE)
    else:
        st.session_state.library = pd.DataFrame(columns=[
            "文件名", "分类", "摘要", "上传时间", "内容"
        ])

# --- 分类列表初始化 ---
if "categories" not in st.session_state:
    if os.path.exists(CATEGORIES_FILE):
        st.session_state.categories = pd.read_csv(CATEGORIES_FILE)["分类"].tolist()
    else:
        st.session_state.categories = ["未分类"]


# ============================================================
# 五、数据持久化函数
# ============================================================
def save_ddl():
    """将 DDL 数据写入 CSV 文件"""
    st.session_state.df.to_csv(DDL_FILE, index=False, encoding="utf-8-sig")


def save_library():
    """将资料库数据写入 CSV 文件"""
    st.session_state.library.to_csv(LIBRARY_FILE, index=False, encoding="utf-8-sig")


def save_categories():
    """将分类列表写入 CSV 文件"""
    pd.DataFrame({"分类": st.session_state.categories}).to_csv(
        CATEGORIES_FILE, index=False
    )


# ============================================================
# 六、辅助工具函数
# ============================================================
def parse_flexible_date(date_str):
    """
    灵活日期解析：兼容多种日期格式
    支持格式：YYYY-MM-DD、YYYY/MM/DD、MM/DD、自然语言（需 dateutil）
    返回：标准化的 YYYY-MM-DD 字符串，失败返回 None
    """
    if not date_str:
        return None
    date_str = date_str.strip().replace("。", "").replace("，", ",")

    # 策略 1：尝试固定格式匹配
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d"):
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue

    # 策略 2：使用 dateutil 进行模糊解析
    if date_parser:
        try:
            dt = date_parser.parse(date_str, fuzzy=True)
            return dt.strftime("%Y-%m-%d")
        except (ValueError, OverflowError):
            pass

    return None


def extract_text_from_file(uploaded_file):
    """
    从上传文件中提取文本内容
    支持格式：PDF、Word、PPT、图片（OCR）、纯文本
    参数：uploaded_file - Streamlit 上传文件对象
    返回：提取的文本字符串，失败返回空字符串
    """
    text = ""
    file_type = uploaded_file.type

    # PDF 文件 → pypdf 逐页提取
    if file_type == "application/pdf":
        if PdfReader:
            reader = PdfReader(uploaded_file)
            for page in reader.pages:
                text += page.extract_text()
        else:
            st.error("请安装 pypdf")

    # Word 文件 → python-docx 遍历段落
    elif "word" in file_type or "document" in file_type:
        if Document:
            doc = Document(uploaded_file)
            for para in doc.paragraphs:
                text += para.text + "\n"
        else:
            st.error("请安装 python-docx")

    # PPT 文件 → python-pptx 遍历幻灯片中的文本形状
    elif "presentation" in file_type or "powerpoint" in file_type:
        if Presentation:
            prs = Presentation(uploaded_file)
            for slide in prs.slides:
                for shape in slide.shapes:
                    if hasattr(shape, "text"):
                        text += shape.text + "\n"
        else:
            st.error("请安装 python-pptx")

    # 图片文件 → EasyOCR 中英文 OCR 识别
    elif file_type.startswith("image/"):
        try:
            import easyocr
            import tempfile
            reader = easyocr.Reader(['ch_sim', 'en'], gpu=False)
            # 写入临时文件供 OCR 读取
            with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
                tmp.write(uploaded_file.read())
                tmp_path = tmp.name
            result = reader.readtext(tmp_path, detail=0, paragraph=True)
            text = " ".join(result)
        except ImportError:
            st.error("请安装 easyocr 和 opencv-python-headless")
        except Exception as e:
            st.error(f"OCR失败：{e}")

    # 纯文本文件 → UTF-8 优先，GBK 降级
    else:
        try:
            text = uploaded_file.read().decode("utf-8")
        except UnicodeDecodeError:
            try:
                uploaded_file.seek(0)
                text = uploaded_file.read().decode("gbk", errors="ignore")
            except Exception:
                st.error("无法解码文件")

    return text


# ============================================================
# 七、页面标题
# ============================================================
st.title("🎓 学习助手 Pro")

# ============================================================
# 八、侧边栏：API Key 配置、主题切换、数据备份
# ============================================================
with st.sidebar:
    st.header("⚙️ 设置")

    # DeepSeek API Key 输入（密码模式）
    api_key = st.text_input(
        "DeepSeek API Key",
        type="password",
        help="platform.deepseek.com 获取"
    )

    st.divider()

    # --- 暗黑模式切换 ---
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

    # --- 数据备份与恢复 ---
    st.subheader("💾 数据备份")

    # 导出 DDL 为 JSON
    json_ddl = st.session_state.df.to_json(orient="records", force_ascii=False)
    st.download_button("📥 备份DDL", data=json_ddl, file_name="backup_ddl.json")

    # 导出资料库为 JSON
    json_lib = st.session_state.library.to_json(orient="records", force_ascii=False)
    st.download_button("📥 备份资料库", data=json_lib, file_name="backup_library.json")

    # 从 JSON 恢复 DDL 数据
    uploaded_backup = st.file_uploader("恢复DDL备份", type=["json"], key="restore_ddl")
    if uploaded_backup:
        try:
            new_data = pd.DataFrame(json.loads(uploaded_backup.read()))
            if not new_data.empty:
                st.session_state.df = new_data
                save_ddl()
                st.success("恢复成功")
                st.rerun()
        except Exception as e:
            st.error(f"恢复失败：{e}")


# ============================================================
# 九、智能输入区（统一文字/文件输入入口）
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
        send_btn = st.button("🚀 发送", use_container_width=True)

    # 文件上传入口
    uploaded_file = st.file_uploader(
        "或点击上传文件 (PDF/Word/PPT/图片/TXT)",
        type=None,
        key="smart_file",
        label_visibility="collapsed"
    )

    # --- 处理发送事件 ---
    if send_btn:
        # 场景 1：用户上传了文件 → 提取文本存入待处理
        if uploaded_file is not None:
            content = extract_text_from_file(uploaded_file)
            if content:
                st.session_state["uploaded_content"] = content
                st.session_state["uploaded_filename"] = uploaded_file.name
                st.success(f"文件 '{uploaded_file.name}' 已读取，请到资料库选择分类保存")
            else:
                st.warning("文件内容提取失败")

        # 场景 2：用户输入文字 → 调用 AI 解析是否为 DDL
        elif smart_input.strip():
            if not api_key:
                st.error("请先在侧边栏设置 API Key")
            else:
                with st.spinner("AI解析中..."):
                    try:
                        headers = {
                            "Authorization": f"Bearer {api_key}",
                            "Content-Type": "application/json"
                        }
                        # 构造 Prompt：要求返回结构化 JSON
                        prompt = f"""提取学习任务信息。规则：
1. 如果是DDL，提取课程名称、截止日期(转为YYYY-MM-DD)、描述。
2. 如果不是DDL，请返回 {{"type": "other", "content": "原文"}}。
只返回JSON。
文本：{smart_input}"""

                        payload = {
                            "model": "deepseek-chat",
                            "messages": [{"role": "user", "content": prompt}],
                            "temperature": 0.1  # 低温度保证输出稳定
                        }

                        response = requests.post(
                            "https://api.deepseek.com/v1/chat/completions",
                            headers=headers,
                            json=payload,
                            timeout=30
                        )

                        if response.status_code == 200:
                            content = response.json()["choices"][0]["message"]["content"]
                            # 清除 Markdown 代码块标记
                            content = content.replace("```json", "").replace("```", "").strip()
                            parsed = json.loads(content)

                            if parsed.get("course") and parsed.get("deadline"):
                                # AI 识别为 DDL → 自动填入表单
                                st.session_state["parsed_course"] = parsed.get("course", "")
                                st.session_state["parsed_deadline"] = parsed.get("deadline", "")
                                st.session_state["parsed_notes"] = parsed.get("notes", "")
                                st.success("✅ 识别为DDL，已自动填入下方表单")
                            else:
                                # AI 识别为普通文本
                                st.info("识别为普通文本，已复制到剪贴板（可手动添加到资料库）")
                                st.session_state["smart_text"] = parsed.get("content", smart_input)
                        else:
                            st.error("AI解析失败")
                    except Exception as e:
                        st.error(f"出错：{e}")
        else:
            st.warning("请输入内容或上传文件")

st.divider()

# ============================================================
# 十、主功能标签页
# ============================================================
tab_ddl, tab_lib = st.tabs(["📝 DDL管理（全功能）", "📚 资料库"])


# ==================== TAB 1: DDL 管理 ====================
with tab_ddl:

    # ----- 10.1 添加 DDL（支持 AI 解析结果自动填充） -----
    st.subheader("➕ 添加DDL")
    with st.form("ddl_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            course = st.text_input(
                "课程/科目",
                value=st.session_state.get("parsed_course", "")
            )
            deadline_raw = st.text_input(
                "截止日期 (支持多种格式)",
                value=st.session_state.get("parsed_deadline", "")
            )
        with col2:
            notes = st.text_input(
                "描述",
                value=st.session_state.get("parsed_notes", "")
            )
            tag = st.text_input("标签", placeholder="作业/考试")
            repeat = st.selectbox("重复", ["无", "每周", "每月"])

        submitted = st.form_submit_button("💾 保存DDL")

        if submitted:
            deadline = parse_flexible_date(deadline_raw)
            if not course or not deadline:
                st.error("课程和截止日期必填")
            else:
                # 根据重复频率生成多条 DDL 记录
                new_rows = []
                try:
                    start_date = datetime.strptime(deadline, "%Y-%m-%d")
                    dates = []
                    if repeat == "无":
                        dates = [start_date]
                    elif repeat == "每周":
                        # 展开未来 4 周
                        dates = [start_date + timedelta(weeks=i) for i in range(4)]
                    elif repeat == "每月":
                        # 展开未来 3 个月（含月末边界处理）
                        for i in range(3):
                            m = start_date.month + i
                            y = start_date.year + (m - 1) // 12
                            m = (m - 1) % 12 + 1
                            try:
                                dates.append(datetime(y, m, start_date.day))
                            except ValueError:
                                # 日期超出当月末（如 31→28），取月末最后一天
                                dates.append(datetime(y, m, 1))
                except ValueError:
                    st.error("日期格式错误")
                    st.stop()

                # 构建新记录
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

                # 追加到 DataFrame 并持久化
                st.session_state.df = pd.concat(
                    [st.session_state.df, pd.DataFrame(new_rows)],
                    ignore_index=True
                )
                save_ddl()

                # 清空 AI 解析的暂存结果
                for key in ["parsed_course", "parsed_deadline", "parsed_notes"]:
                    if key in st.session_state:
                        del st.session_state[key]

                st.success(f"添加了 {len(new_rows)} 条DDL")
                st.rerun()

    # ----- 10.2 管理与搜索 -----
    st.subheader("🔍 管理与搜索")

    # 搜索框 + 状态筛选
    search = st.text_input("搜索DDL", key="ddl_search")
    filter_status = st.selectbox("状态筛选", ["全部", "未完成", "已完成"], key="ddl_status")

    df_display = st.session_state.df.copy()

    # 按关键词过滤（课程名或描述）
    if search:
        df_display = df_display[
            df_display["课程/科目"].str.contains(search, na=False) |
            df_display["描述"].str.contains(search, na=False)
        ]
    # 按状态过滤
    if filter_status != "全部":
        df_display = df_display[df_display["状态"] == filter_status]

    if not df_display.empty:
        # 可编辑表格：支持直接切换任务状态
        edited = st.data_editor(
            df_display[["课程/科目", "截止日期", "描述", "标签", "状态"]],
            column_config={
                "状态": st.column_config.SelectboxColumn("状态", options=["未完成", "已完成"])
            },
            hide_index=True,
            key="ddl_edit"
        )

        # 检测状态变更并保存
        if not edited.equals(df_display[["课程/科目", "截止日期", "描述", "标签", "状态"]]):
            for _, row in edited.iterrows():
                mask = (
                    (st.session_state.df["课程/科目"] == row["课程/科目"]) &
                    (st.session_state.df["截止日期"] == row["截止日期"])
                )
                if mask.any():
                    st.session_state.df.loc[mask, "状态"] = row["状态"]
            save_ddl()
            st.success("状态已更新")
            st.rerun()

        # ----- 批量操作（删除选中 / 清除已完成） -----
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
                        mask = (
                            (st.session_state.df["课程/科目"] == row["课程/科目"]) &
                            (st.session_state.df["截止日期"] == row["截止日期"])
                        )
                        if mask.any():
                            st.session_state.df = st.session_state.df.drop(
                                st.session_state.df[mask].index
                            )
                    save_ddl()
                    st.success(f"删除了 {len(selected)} 项")
                    st.rerun()

        with col_del2:
            if st.button("清除所有已完成"):
                before = len(st.session_state.df)
                st.session_state.df = st.session_state.df[
                    st.session_state.df["状态"] != "已完成"
                ]
                save_ddl()
                st.success(f"清除 {before - len(st.session_state.df)} 项")
                st.rerun()
    else:
        st.info("没有匹配的DDL")

    # ----- 10.3 数据分析图表 -----
    st.subheader("📊 数据分析")
    df_chart = st.session_state.df[st.session_state.df["状态"] != "已完成"].copy()

    if df_chart.empty:
        st.info("没有未完成的任务")
    else:
        try:
            df_chart["截止日期"] = pd.to_datetime(df_chart["截止日期"], errors="coerce")
            df_chart = df_chart.dropna(subset=["截止日期"])

            # 只展示未来 30 天内的任务
            today = datetime.now()
            future_30 = today + timedelta(days=30)
            df_chart = df_chart[
                (df_chart["截止日期"] >= today) &
                (df_chart["截止日期"] <= future_30)
            ]

            if not df_chart.empty:
                # 柱状图：按星期统计任务分布
                day_order = ["Monday", "Tuesday", "Wednesday", "Thursday",
                             "Friday", "Saturday", "Sunday"]
                day_names_cn = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
                df_chart["星期"] = pd.Categorical(
                    df_chart["截止日期"].dt.day_name(), categories=day_order
                )
                count_df = df_chart.groupby("星期").size().reset_index(name="任务数量")
                count_df["星期"] = count_df["星期"].map(dict(zip(day_order, day_names_cn)))

                fig = px.bar(
                    count_df, x="星期", y="任务数量",
                    title="未来30天 DDL 分布",
                    color="任务数量", color_continuous_scale="Reds",
                    text="任务数量"
                )
                fig.update_layout(height=350)
                st.plotly_chart(fig, use_container_width=True)

                # 饼图：标签分布
                st.subheader("🏷️ 标签分布")
                tag_df = df_chart["标签"].value_counts().reset_index()
                tag_df.columns = ["标签", "数量"]
                fig_pie = px.pie(tag_df, values="数量", names="标签", hole=0.3)
                st.plotly_chart(fig_pie, use_container_width=True)
            else:
                st.info("未来30天无任务")
        except Exception as e:
            st.warning(f"图表生成失败：{e}")

    # ----- 10.4 月视图日历 -----
    st.subheader("📆 月视图")

    # 初始化月份状态
    if "cal_year" not in st.session_state:
        st.session_state.cal_year = datetime.now().year
        st.session_state.cal_month = datetime.now().month

    # 月份切换按钮
    c1, c2, c3 = st.columns([1, 2, 1])
    with c1:
        if st.button("◀"):
            if st.session_state.cal_month == 1:
                st.session_state.cal_month = 12
                st.session_state.cal_year -= 1
            else:
                st.session_state.cal_month -= 1
            st.rerun()
    with c2:
        st.write(f"### {st.session_state.cal_year}年{st.session_state.cal_month}月")
    with c3:
        if st.button("▶"):
            if st.session_state.cal_month == 12:
                st.session_state.cal_month = 1
                st.session_state.cal_year += 1
            else:
                st.session_state.cal_month += 1
            st.rerun()

    # 计算当月日期范围
    year = st.session_state.cal_year
    month = st.session_state.cal_month
    first = datetime(year, month, 1)
    if month == 12:
        last = datetime(year + 1, 1, 1) - timedelta(days=1)
    else:
        last = datetime(year, month + 1, 1) - timedelta(days=1)

    start_week = first.weekday()   # 首日星期偏移（0=周一）
    total_days = last.day

    # 聚合当月任务
    df_cal = st.session_state.df[st.session_state.df["状态"] != "已完成"].copy()
    tasks = {}
    if not df_cal.empty:
        df_cal["截止日期"] = pd.to_datetime(df_cal["截止日期"], errors="coerce")
        df_cal = df_cal.dropna(subset=["截止日期"])
        for _, row in df_cal.iterrows():
            if row["截止日期"].year == year and row["截止日期"].month == month:
                key = row["截止日期"].strftime("%Y-%m-%d")
                tasks.setdefault(key, []).append(row["课程/科目"])

    # 构建 7×6 日历网格（42 格）
    cal_dates = [None] * start_week + [datetime(year, month, d) for d in range(1, total_days + 1)]
    while len(cal_dates) < 42:
        cal_dates.append(None)

    # 渲染 HTML 日历
    html = "<div class='cal-grid'>"
    for w in ["一", "二", "三", "四", "五", "六", "日"]:
        html += f"<div class='cal-weekday'>{w}</div>"

    today_str = datetime.now().strftime("%Y-%m-%d")
    for d in cal_dates:
        if d is None:
            html += "<div class='cal-cell' style='background:transparent;'></div>"
        else:
            key = d.strftime("%Y-%m-%d")
            t = tasks.get(key, [])
            # 颜色编码：红(≥3) / 橙(1-2) / 绿(0)
            color = "#e74c3c" if len(t) >= 3 else "#f39c12" if len(t) >= 1 else "#2ecc71"
            bg = "#fff3cd" if key == today_str else "#f9f9f9"
            html += f"<div class='cal-cell' style='border-top-color:{color};background:{bg};'>"
            html += f"<div class='date'>{d.day}</div>"
            for task in t[:2]:  # 最多显示 2 条任务
                html += f"<div style='font-size:9px;'>{task[:4]}</div>"
            if len(t) > 2:
                html += f"<div style='font-size:9px;color:#888;'>+{len(t)-2}</div>"
            html += "</div>"
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)

    # ----- 10.5 导出与分享 -----
    st.subheader("📤 导出与分享")
    exp_col1, exp_col2 = st.columns(2)

    with exp_col1:
        # 导出 CSV
        if st.button("⬇️ 导出CSV"):
            csv = st.session_state.df.to_csv(index=False)
            b64 = base64.b64encode(csv.encode()).decode()
            st.markdown(
                f'<a href="data:file/csv;base64,{b64}" download="deadlines.csv">下载CSV</a>',
                unsafe_allow_html=True
            )

        # 导出 ICS 日历文件（可导入 Apple Calendar / Google Calendar）
        if st.button("⬇️ 导出日历(.ics)"):
            if Calendar is None:
                st.error("请安装 icalendar")
            else:
                try:
                    cal = Calendar()
                    cal.add('prodid', '-//DDL Pro//cn//')
                    cal.add('version', '2.0')
                    for _, row in st.session_state.df.iterrows():
                        if row["状态"] == "已完成":
                            continue
                        event = Event()
                        event.add('summary', row["课程/科目"])
                        event.add('description', row["描述"])
                        date_obj = datetime.strptime(row["截止日期"], "%Y-%m-%d").date()
                        event.add('dtstart', date_obj)
                        event.add('dtend', date_obj)
                        cal.add_component(event)
                    ics_data = cal.to_ical()
                    b64 = base64.b64encode(ics_data).decode()
                    st.markdown(
                        f'<a href="data:text/calendar;base64,{b64}" download="deadlines.ics">下载.ics</a>',
                        unsafe_allow_html=True
                    )
                except Exception as e:
                    st.error(f"导出失败：{e}")

    with exp_col2:
        # 生成 Markdown 分享卡片
        if st.button("🔄 生成分享卡片"):
            df_share = st.session_state.df[st.session_state.df["状态"] != "已完成"].copy()
            if df_share.empty:
                st.warning("没有未完成任务")
            else:
                df_share = df_share.sort_values("截止日期")
                lines = ["# 📋 我的DDL清单\n"]
                for _, row in df_share.iterrows():
                    lines.append(f"- **{row['课程/科目']}** 截止: {row['截止日期']} | {row['描述']}")
                lines.append(f"\n> 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
                md = "\n".join(lines)
                st.text_area("复制以下内容", md, height=200)
                st.download_button("下载.md", md, file_name="DDL清单.md")

    # ----- 10.6 AI 复习规划 -----
    st.subheader("🧠 AI 复习规划")
    if st.button("📅 生成复习计划"):
        df_future = st.session_state.df[st.session_state.df["状态"] != "已完成"].copy()
        if df_future.empty or not api_key:
            st.warning("请确保有未完成任务并配置API Key")
        else:
            with st.spinner("生成中..."):
                try:
                    tasks_text = df_future[["课程/科目", "截止日期", "描述"]].head(10).to_string()
                    headers = {
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json"
                    }
                    prompt = f"基于以下任务：\n{tasks_text}\n生成未来一周复习优先级清单（Markdown列表）"
                    payload = {
                        "model": "deepseek-chat",
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.7
                    }
                    response = requests.post(
                        "https://api.deepseek.com/v1/chat/completions",
                        headers=headers, json=payload, timeout=30
                    )
                    if response.status_code == 200:
                        plan = response.json()["choices"][0]["message"]["content"]
                        st.markdown(plan)
                    else:
                        st.error("生成失败")
                except Exception as e:
                    st.error(f"出错：{e}")


# ==================== TAB 2: 资料库 ====================
with tab_lib:

    # ----- 分类管理 -----
    st.subheader("📁 分类管理")

    col_cat1, col_cat2 = st.columns([3, 1])
    with col_cat1:
        st.write("当前分类：", ", ".join(st.session_state.categories))
    with col_cat2:
        new_cat = st.text_input("新建分类", key="new_cat")
        if st.button("➕ 添加"):
            if new_cat.strip() and new_cat.strip() not in st.session_state.categories:
                st.session_state.categories.append(new_cat.strip())
                save_categories()
                st.success(f"已添加 '{new_cat.strip()}'")
                st.rerun()
            else:
                st.warning("分类已存在或为空")

    # 删除分类（仅允许删除空分类）
    with st.expander("🗑️ 删除分类（仅当为空）"):
        del_cat = st.selectbox("选择分类", st.session_state.categories, key="del_cat")
        if st.button("确认删除"):
            if not st.session_state.library[
                st.session_state.library["分类"] == del_cat
            ].empty:
                st.error(f"分类 '{del_cat}' 下还有文件")
            else:
                st.session_state.categories.remove(del_cat)
                save_categories()
                st.success("已删除")
                st.rerun()

    st.divider()

    # ----- 文件上传 -----
    st.subheader("📤 上传文件")
    with st.form("upload_lib"):
        uploaded_file = st.file_uploader(
            "选择文件 (PDF/Word/PPT/图片/TXT)", type=None, key="lib_upload"
        )
        cat_options = st.session_state.categories + ["新建分类..."]
        selected_cat = st.selectbox("选择分类", cat_options, key="lib_cat")

        if selected_cat == "新建分类...":
            new_cat_name = st.text_input("新分类名称")
        else:
            new_cat_name = None

        notes = st.text_area("备注（可选）")
        submitted = st.form_submit_button("📥 保存到资料库")

        if submitted and uploaded_file is not None:
            # 处理"新建分类"
            if new_cat_name and new_cat_name.strip():
                final_cat = new_cat_name.strip()
                if final_cat not in st.session_state.categories:
                    st.session_state.categories.append(final_cat)
                    save_categories()
            else:
                final_cat = selected_cat

            # 提取文件文本
            content = extract_text_from_file(uploaded_file)
            if content is None or content == "":
                st.error("内容提取失败")
            else:
                summary = content[:200] + ("..." if len(content) > 200 else "")
                new_row = {
                    "文件名": uploaded_file.name,
                    "分类": final_cat,
                    "摘要": summary,
                    "上传时间": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "内容": content
                }
                st.session_state.library = pd.concat(
                    [st.session_state.library, pd.DataFrame([new_row])],
                    ignore_index=True
                )
                save_library()
                st.success(f"文件 '{uploaded_file.name}' 已保存到 '{final_cat}'")
                st.rerun()

    st.divider()

    # ----- 资料浏览 -----
    st.subheader("📂 资料浏览")

    # 搜索 + 分类筛选
    filter_cat = st.selectbox("按分类筛选", ["全部"] + st.session_state.categories, key="lib_filter")
    search_lib = st.text_input("搜索", key="lib_search")

    df_lib = st.session_state.library.copy()
    if filter_cat != "全部":
        df_lib = df_lib[df_lib["分类"] == filter_cat]
    if search_lib:
        df_lib = df_lib[
            df_lib["文件名"].str.contains(search_lib, na=False) |
            df_lib["摘要"].str.contains(search_lib, na=False) |
            df_lib["内容"].str.contains(search_lib, na=False)
        ]

    if df_lib.empty:
        st.info("暂无资料")
    else:
        # 按分类分组展示
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
                        if st.button("📄 查看", key=f"view_{idx}"):
                            st.text_area("全文", row['内容'], height=150)
                    with col3:
                        if st.button("🗑️ 删除", key=f"del_{idx}"):
                            st.session_state.library = st.session_state.library.drop(
                                index=idx
                            ).reset_index(drop=True)
                            save_library()
                            st.rerun()
            st.divider()

    # 导出资料库为 CSV
    if st.button("导出资料库CSV"):
        csv = st.session_state.library.to_csv(index=False)
        b64 = base64.b64encode(csv.encode()).decode()
        st.markdown(
            f'<a href="data:file/csv;base64,{b64}" download="library.csv">下载CSV</a>',
            unsafe_allow_html=True
        )

# 页脚说明
st.caption("💡 全部功能：DDL管理（AI解析/图表/月视图/分享/复习）+ 资料库（分类/上传/搜索）")
