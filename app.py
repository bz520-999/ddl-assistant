import streamlit as st
import pandas as pd
import requests
import json
import os
from datetime import datetime
from io import BytesIO, StringIO
import base64

# 处理PDF的库
try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

# 处理日历导出的库
try:
    from icalendar import Calendar, Event
except ImportError:
    Calendar = None
    Event = None

# ========== 1. 页面配置 ==========
st.set_page_config(page_title="学习DDL管理智能体", layout="wide")
st.title("📚 学习DDL与资料管理智能体")

# ========== 2. 初始化数据（存CSV） ==========
DATA_FILE = "deadlines.csv"

# 初始化session_state中的数据框
if "df" not in st.session_state:
    if os.path.exists(DATA_FILE):
        st.session_state.df = pd.read_csv(DATA_FILE)
    else:
        # 创建空表结构
        st.session_state.df = pd.DataFrame(columns=["课程/科目", "截止日期", "描述", "标签", "添加时间"])

# 保存数据的函数
def save_data():
    st.session_state.df.to_csv(DATA_FILE, index=False, encoding="utf-8-sig")

# ========== 3. 侧边栏：配置API ==========
with st.sidebar:
    st.header("⚙️ 配置")
    api_key = st.text_input("请输入 DeepSeek API Key", type="password", help="在 platform.deepseek.com 获取")
    st.caption("如果不填，AI解析功能不可用，但手动录入依然正常")

    st.divider()
    st.subheader("📊 数据统计")
    total = len(st.session_state.df)
    if total > 0:
        # 计算未来7天内的DDL
        try:
            df_temp = st.session_state.df.copy()
            df_temp["截止日期"] = pd.to_datetime(df_temp["截止日期"])
            upcoming = df_temp[df_temp["截止日期"] >= datetime.now()].shape[0]
            st.metric("总任务数", total, delta=f"即将到来 {upcoming} 项")
        except:
            st.metric("总任务数", total)
    else:
        st.info("暂无数据")

# ========== 4. 主界面：选项卡 ==========
tab1, tab2, tab3, tab4 = st.tabs(["📝 添加与解析", "🔍 管理与搜索", "📅 导出与复习", "📂 文件上传"])

# ---------- 4.1 添加与解析 ----------
with tab1:
    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("✍️ 一句话添加DDL")
        user_input = st.text_area("输入你的DDL（例如：下周一交高数作业第3章）", height=100)

        # 解析按钮
        if st.button("🤖 AI 智能解析", use_container_width=True):
            if not api_key:
                st.error("❌ 请先在左侧侧边栏输入DeepSeek API Key！")
            elif not user_input.strip():
                st.warning("⚠️ 请先输入内容")
            else:
                with st.spinner("AI正在解析中..."):
                    try:
                        # 调用DeepSeek API
                        headers = {
                            "Authorization": f"Bearer {api_key}",
                            "Content-Type": "application/json"
                        }
                        # 强约束AI输出JSON格式
                        prompt = f"""
                        你是一个信息提取助手。从以下文本中提取学习任务信息。
                        规则：
                        1. 提取"课程名称"。
                        2. 提取"截止日期"，如果包含"明天""下周一"等，请转换为具体的 YYYY-MM-DD 格式（今年年份）。
                        3. 提取"描述/备注"。
                        请只返回一个合法的JSON对象，格式如下：
                        {{"course": "课程名", "deadline": "2026-07-30", "notes": "备注内容"}}
                        
                        文本内容：{user_input}
                        """
                        
                        payload = {
                            "model": "deepseek-chat",
                            "messages": [
                                {"role": "system", "content": "你是一个严格的信息提取助手，只返回JSON。"},
                                {"role": "user", "content": prompt}
                            ],
                            "temperature": 0.1
                        }
                        
                        response = requests.post(
                            "https://api.deepseek.com/v1/chat/completions",
                            headers=headers,
                            json=payload,
                            timeout=30
                        )
                        
                        if response.status_code == 200:
                            result = response.json()
                            ai_content = result["choices"][0]["message"]["content"]
                            
                            # 清洗一下，防止AI返回markdown代码块
                            ai_content = ai_content.replace("```json", "").replace("```", "").strip()
                            parsed = json.loads(ai_content)
                            
                            # 自动填入session_state的临时变量
                            st.session_state["parsed_course"] = parsed.get("course", "")
                            st.session_state["parsed_deadline"] = parsed.get("deadline", "")
                            st.session_state["parsed_notes"] = parsed.get("notes", "")
                            st.success("✅ 解析成功！请点击下方'保存到列表'按钮")
                        else:
                            st.error(f"❌ API调用失败：{response.text}")
                    except Exception as e:
                        st.error(f"❌ 解析出错：{e}，请检查API Key或稍后重试")

        # 手动输入表单
        st.divider()
        st.subheader("🖊️ 手动录入（或填入解析结果）")
        
        # 使用列布局让表单紧凑
        f_col1, f_col2 = st.columns(2
