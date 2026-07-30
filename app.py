好的，我已经仔细阅读了你的完整代码。下面我为你产出两份交付物：**技术报告** 和 **整理注释后的代码**。

---

# 一、技术报告

## 1. 问题理解

### 1.1 问题背景

当代学生面临多课程、多任务并行的学习场景，截止日期（DDL）分散在各类通知渠道（微信群、邮件、课件），容易遗漏。同时，学习资料（PDF课件、Word笔记、PPT演示等）格式多样、缺乏统一管理。

### 1.2 核心痛点

| 痛点 | 具体表现 |
|---|---|
| DDL 信息分散 | 需要手动逐条记录，格式不统一 |
| 任务优先级模糊 | 缺乏可视化的时间分布和标签统计 |
| 资料管理碎片化 | 文件散落在不同设备，无法按课程分类检索 |
| 复习规划低效 | 人工判断哪些任务优先，缺乏 AI 辅助决策 |

### 1.3 目标用户

高校学生、研究生，以及任何需要管理多线程学习任务的用户。

### 1.4 预期效果

- 自然语言/文件输入，AI 自动识别 DDL 并结构化入库
- 可视化日历 + 图表一目了然掌握任务分布
- 资料库支持多格式文件上传、分类、全文检索
- AI 生成个性化复习优先级计划

---

## 2. 技术路线

```
用户输入（自然语言 / 文件）
        │
        ▼
┌─────────────────────┐
│   前端层 (Streamlit)  │  ← 页面渲染、表单交互、状态管理
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  智能解析层           │
│  ┌─────────────────┐ │
│  │ 日期解析引擎     │ │  ← dateutil + 自定义多格式适配
│  ├─────────────────┤ │
│  │ 文件内容提取     │ │  ← pypdf / python-docx / python-pptx / easyocr
│  ├─────────────────┤ │
│  │ AI 语义解析     │ │  ← DeepSeek API (NLU → 结构化 JSON)
│  └─────────────────┘ │
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  数据持久层           │  ← CSV 文件存储（deadlines.csv / library.csv / categories.csv）
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  展示与分析层         │
│  ├─ 月历视图         │  ← HTML/CSS Grid 动态渲染
│  ├─ Plotly 图表      │  ← 柱状图 + 饼图统计
│  ├─ 导出（CSV/ICS/MD）│  ← icalendar + base64 编码
│  └─ AI 复习规划      │  ← DeepSeek API 生成 Markdown 计划
└─────────────────────┘
```

### 技术选型理由

| 技术 | 选型 | 理由 |
|---|---|---|
| 前端框架 | Streamlit | 纯 Python 开发，快速原型，内置状态管理 |
| LLM 服务 | DeepSeek API | 中文理解优秀，性价比高，API 兼容 OpenAI 格式 |
| 文件解析 | pypdf / docx / pptx / easyocr | 覆盖主流文档格式，OCR 兜底图片场景 |
| 日期解析 | dateutil + 自定义规则 | 模糊解析 + 确定性格式兜底 |
| 数据存储 | CSV | 零依赖部署，适合轻量级单用户场景 |
| 可视化 | Plotly + HTML Calendar | 交互式图表 + 灵活的日历布局 |

---

## 3. 系统架构

### 3.1 整体架构

```
┌──────────────────────────────────────────────────┐
│                   客户端浏览器                      │
└──────────────────────┬───────────────────────────┘
                       │ HTTP
┌──────────────────────▼───────────────────────────┐
│              Streamlit 服务（app.py）               │
│                                                    │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐│
│  │ 智能输入  │  │ DDL管理  │  │ 资料库管理        ││
│  │ 解析模块  │  │   模块   │  │     模块          ││
│  └────┬─────┘  └────┬─────┘  └────┬─────────────┘│
│       │             │             │                │
│  ┌────▼─────────────▼─────────────▼──────────────┐│
│  │            Session State 状态管理               ││
│  └────┬─────────────┬─────────────┬──────────────┘│
│       │             │             │                │
│  ┌────▼─────┐ ┌─────▼────┐ ┌─────▼─────┐         │
│  │DDL数据层 │ │资料库层   │ │分类数据层  │         │
│  │(CSV R/W) │ │(CSV R/W) │ │(CSV R/W)  │         │
│  └──────────┘ └──────────┘ └───────────┘         │
└──────────────────────┬───────────────────────────┘
                       │ HTTPS
┌──────────────────────▼───────────────────────────┐
│           DeepSeek API（外部服务）                   │
│   ┌───────────────┐  ┌──────────────────────┐    │
│   │ DDL语义解析    │  │ 复习计划生成          │    │
│   │ (deepseek-chat)│  │ (deepseek-chat)      │    │
│   └───────────────┘  └──────────────────────┘    │
└──────────────────────────────────────────────────┘
```

### 3.2 模块划分

| 模块 | 职责 | 关键函数/组件 |
|---|---|---|
| 智能输入解析 | 自然语言→结构化DDL；文件→文本 | `parse_flexible_date()`, `extract_text_from_file()`, DeepSeek API调用 |
| DDL管理 | 增删改查、搜索筛选、重复任务展开 | DDL表单、`data_editor`、批量操作 |
| 可视化 | 月历视图、柱状图、饼图 | Plotly图表、HTML日历Grid |
| 导出与分享 | CSV/ICS/Markdown导出 | icalendar库、base64编码 |
| AI复习规划 | 基于DDL列表生成优先级建议 | DeepSeek API |
| 资料库 | 文件上传、分类管理、全文搜索 | `extract_text_from_file()`、分类CRUD |
| 数据持久化 | CSV读写、备份恢复 | `save_ddl()`, `save_library()`, JSON备份 |

---

## 4. 核心算法与实现方式

### 4.1 AI 语义解析（自然语言 → 结构化 DDL）

**原理：** 利用 LLM 的指令遵循能力，将用户自由文本映射为结构化 JSON。

**Prompt 设计：**
```
提取学习任务信息。规则：
1. 如果是DDL，提取课程名称、截止日期(转为YYYY-MM-DD)、描述。
2. 如果不是DDL，返回 {"type": "other", "content": "原文"}。
只返回JSON。
文本：{user_input}
```

**参数设置：**
- `model`: `deepseek-chat`
- `temperature`: `0.1`（低随机性，保证结构化输出稳定）
- `timeout`: 30s

**容错处理：**
- 响应内容去除 Markdown 代码块标记（```json...```）
- JSON 解析失败时 fallback 到手动输入模式

### 4.2 多格式文件内容提取

| 格式 | 库 | 实现方式 |
|---|---|---|
| PDF | pypdf | `PdfReader` 逐页 `extract_text()` |
| Word | python-docx | 遍历 `paragraphs` 拼接文本 |
| PPT | python-pptx | 遍历 `slides` → `shapes` → `.text` |
| 图片 | easyocr | OCR 识别中英文，`paragraph=True` 保持段落结构 |
| TXT | 内置 | UTF-8 优先，GBK 兜底 |

**依赖容错：** 每个库使用 `try/except ImportError` 做可选依赖处理，缺失时给出明确错误提示。

### 4.3 柔性日期解析

```
parse_flexible_date(date_str)
    ├── 格式1: YYYY-MM-DD  → 直接解析
    ├── 格式2: YYYY/MM/DD  → 直接解析
    ├── 格式3: MM/DD       → 补全年份后解析
    ├── dateutil fuzzy 模式 → 模糊解析自然语言日期
    └── 全部失败 → 返回 None
```

### 4.4 重复任务展开

当用户选择"每周"或"每月"重复时，系统自动展开：

- **每周**：以起始日期为基准，向后展开 4 周，生成 4 条记录
- **每月**：以起始日期为基准，向后展开 3 个月，自动处理月末边界（如 31 号在小月自动回退到 1 号）

---

## 5. 关键模块详细说明

### 5.1 Session State 状态管理

```
st.session_state
  ├── df          → DDL 数据表 (DataFrame)
  ├── library     → 资料库数据表 (DataFrame)
  ├── categories  → 分类列表 (List[str])
  ├── dark        → 主题切换标记 (bool)
  ├── cal_year    → 日历当前年 (int)
  ├── cal_month   → 日历当前月 (int)
  ├── parsed_*    → AI 解析暂存字段 (str)
  └── uploaded_*  → 文件上传暂存字段 (str)
```

### 5.2 月历视图渲染

- 计算当月第一天的星期偏移量（`start_week`）
- 填充前部空白 + 日期格 + 后部补全到 42 格（6 行 × 7 列）
- 颜色编码：≥3 任务=红色，1-2 任务=橙色，0 任务=绿色
- 当天高亮显示
- 每格最多显示 2 个任务名，超出显示 `+N`

### 5.3 数据备份与恢复

- **备份**：将 DataFrame 转为 JSON 字符串，通过 `st.download_button` 下载
- **恢复**：上传 JSON 文件 → 解析为 DataFrame → 覆盖 session_state → 持久化到 CSV → 触发 `st.rerun()` 刷新

---

## 6. 实验设计与效果评估

### 6.1 测试场景

| 场景 | 输入 | 预期输出 |
|---|---|---|
| 自然语言解析 | "下周一交高数作业" | 课程:高数，截止日期:具体日期，描述:作业 |
| 多格式日期 | "12/25" "2025年3月1日" | 正确解析为 YYYY-MM-DD |
| 重复任务 | 选择"每周" | 自动生成 4 条周间隔记录 |
| PDF 上传 | 课件 PDF | 正确提取文本并可保存到资料库 |
| OCR 识别 | 手写笔记图片 | 识别文字并入库 |
| 空输入/异常输入 | 空字符串、乱码 | 给出友好提示，不崩溃 |
| 备份恢复 | 导出 JSON 后导入 | 数据完整恢复 |

### 6.2 效果指标

| 指标 | 目标 |
|---|---|
| AI 解析准确率 | 常见中文学术场景 ≥ 90% |
| 文件提取覆盖率 | PDF/Word/PPT/TXT/图片 五类全覆盖 |
| 页面响应时间 | 本地操作 < 1s，AI 调用 < 5s |
| 数据可靠性 | CSV 持久化 + JSON 备份双保险 |
| 移动端适配 | 响应式 CSS，600px 以下自动纵向排列 |

---

## 7. 不足分析与改进方向

| 不足 | 说明 | 改进方向 |
|---|---|---|
| **存储方案局限** | CSV 文件在并发/大数据量下性能差，无事务保障 | 迁移至 SQLite 或轻量级数据库 |
| **单用户设计** | 无用户认证，多设备无法同步 | 引入用户系统 + 云端存储 |
| **AI 解析依赖网络** | DeepSeek API 不可用时核心功能降级 | 增加本地正则规则引擎作为 fallback |
| **OCR 精度有限** | easyocr 对手写体/复杂排版识别率一般 | 接入商业 OCR API 或自训练模型 |
| **日历交互性不足** | 纯 HTML 渲染，无法点击查看详情 | 改用前端日历组件（如 streamlit-calendar） |
| **无推送/提醒** | 用户需要主动打开应用查看 | 接入邮件/微信推送服务 |
| **图表维度有限** | 仅有星期分布和标签饼图 | 增加甘特图、课程工作量趋势图等 |
| **代码耦合度** | 所有逻辑在一个文件中，超 500 行 | 拆分为多模块（pages/、components/、utils/） |

---

# 二、整理后的代码（含详细注释）

```python
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
