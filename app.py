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
        f_col1, f_col2 = st.columns(2)
        with f_col1:
            # 如果解析有结果，自动填充
            course_val = st.session_state.get("parsed_course", "")
            course = st.text_input("课程/科目", value=course_val)
            
            deadline_val = st.session_state.get("parsed_deadline", "")
            deadline = st.text_input("截止日期 (格式: 2026-07-30)", value=deadline_val)
            
        with f_col2:
            notes_val = st.session_state.get("parsed_notes", "")
            notes = st.text_input("描述/备注", value=notes_val)
            tag = st.text_input("标签 (如: 作业/考试)", placeholder="例如：作业")

        if st.button("💾 保存到列表", type="primary", use_container_width=True):
            if not course or not deadline:
                st.warning("⚠️ 课程和截止日期不能为空")
            else:
                new_row = {
                    "课程/科目": course,
                    "截止日期": deadline,
                    "描述": notes,
                    "标签": tag if tag else "未分类",
                    "添加时间": datetime.now().strftime("%Y-%m-%d %H:%M")
                }
                # 使用pd.concat添加行
                st.session_state.df = pd.concat(
                    [st.session_state.df, pd.DataFrame([new_row])], 
                    ignore_index=True
                )
                save_data()
                # 清空缓存
                for key in ["parsed_course", "parsed_deadline", "parsed_notes"]:
                    if key in st.session_state:
                        del st.session_state[key]
                st.success("✅ 保存成功！")
                st.rerun()

    with col2:
        st.subheader("📌 快速示例")
        st.info(
            """
            **试试复制这些：**
            - 下周一交高数作业
            - 7月30日前完成大创报告
            - 周五下午3点英语考试
            """
        )
        if st.button("填充示例到输入框"):
            st.session_state["sample_text"] = "下周一交高数作业第3章"
            st.rerun()
        # 如果session中有示例，回填到输入框（用js或rerun不太好实现，这里简单放个文字提示）
        # 实际上，我们可以用st.text_area的value参数，但为了演示，用户手动复制也行。

# ---------- 4.2 管理与搜索 ----------
with tab2:
    st.subheader("🔍 筛选与搜索")
    search_col1, search_col2 = st.columns(2)
    with search_col1:
        search_keyword = st.text_input("关键词搜索（标题/描述）", placeholder="输入关键词")
    with search_col2:
        filter_tag = st.selectbox("按标签筛选", ["全部"] + list(st.session_state.df["标签"].unique()))

    # 执行筛选
    df_display = st.session_state.df.copy()
    if search_keyword:
        df_display = df_display[
            df_display["课程/科目"].str.contains(search_keyword, na=False) |
            df_display["描述"].str.contains(search_keyword, na=False)
        ]
    if filter_tag != "全部":
        df_display = df_display[df_display["标签"] == filter_tag]

    # 显示数据表
    st.dataframe(df_display, use_container_width=True)

    # 删除功能
    st.subheader("🗑️ 删除任务")
    if not df_display.empty:
        # 用数字索引删除，但展示的是筛选后的，所以我们用原始df的索引
        # 这里简化操作：直接使用原始df的index进行删除（通过选择）
        delete_index = st.number_input("输入要删除的行号 (从0开始)", min_value=0, max_value=len(df_display)-1, step=1)
        if st.button("删除选中行"):
            # 获取要删除的原始索引
            original_idx = df_display.index[delete_index]
            st.session_state.df = st.session_state.df.drop(index=original_idx).reset_index(drop=True)
            save_data()
            st.success("删除成功！")
            st.rerun()
    else:
        st.info("当前没有匹配的任务")

# ---------- 4.3 导出与复习 ----------
with tab3:
    st.subheader("📤 导出数据")
    
    exp_col1, exp_col2 = st.columns(2)
    
    with exp_col1:
        # 导出CSV
        if st.button("⬇️ 导出 CSV"):
            csv = st.session_state.df.to_csv(index=False, encoding="utf-8-sig")
            b64 = base64.b64encode(csv.encode()).decode()
            href = f'<a href="data:file/csv;base64,{b64}" download="deadlines.csv">点击下载 CSV</a>'
            st.markdown(href, unsafe_allow_html=True)
            st.success("CSV已生成")

    with exp_col2:
        # 导出 iCal 日历
        if st.button("⬇️ 导出 日历 (.ics)"):
            if Calendar is None or Event is None:
                st.error("请先安装 icalendar 库: pip install icalendar")
            elif st.session_state.df.empty:
                st.warning("暂无数据可导出")
            else:
                try:
                    cal = Calendar()
                    cal.add('prodid', '-//DDL Manager//cn//')
                    cal.add('version', '2.0')
                    
                    for _, row in st.session_state.df.iterrows():
                        event = Event()
                        event.add('summary', row["课程/科目"])
                        event.add('description', f"{row['描述']} | 标签: {row['标签']}")
                        # 处理日期
                        try:
                            date_obj = datetime.strptime(row["截止日期"], "%Y-%m-%d").date()
                            event.add('dtstart', date_obj)
                            event.add('dtend', date_obj)  # 截止日当天
                            # 加个提醒（提前1天）
                            event.add('alarm', None)  # 简化处理
                            cal.add_component(event)
                        except:
                            continue
                    
                    # 生成文件
                    ics_data = cal.to_ical()
                    b64 = base64.b64encode(ics_data).decode()
                    href = f'<a href="data:text/calendar;base64,{b64}" download="deadlines.ics">点击下载 .ics (导入手机日历)</a>'
                    st.markdown(href, unsafe_allow_html=True)
                    st.success("日历文件已生成，导入手机即可自动提醒")
                except Exception as e:
                    st.error(f"导出失败：{e}")

    st.divider()
    st.subheader("📋 复习清单生成")
    if st.button("生成今日待办清单"):
        if st.session_state.df.empty:
            st.info("暂无任务")
        else:
            today = datetime.now().date()
            try:
                df_copy = st.session_state.df.copy()
                df_copy["截止日期_日期"] = pd.to_datetime(df_copy["截止日期"]).dt.date
                # 找出未来7天内的
                future_week = df_copy[df_copy["截止日期_日期"] >= today]
                if future_week.empty:
                    st.success("🎉 未来一周没有DDL，继续加油！")
                else:
                    st.write("#### 📌 未来一周待办：")
                    for _, row in future_week.iterrows():
                        st.markdown(f"- **{row['课程/科目']}** 截止: {row['截止日期']} | {row['描述']}")
            except:
                st.warning("日期格式有误，请确保截止日期为 YYYY-MM-DD 格式")
# ---------- 4.4 文件上传 ----------
with tab4:
    st.subheader("📎 上传资料自动提取DDL")
    uploaded_file = st.file_uploader("支持 PDF 或 TXT 文件", type=["pdf", "txt"])
    
    if uploaded_file is not None:
        file_text = ""
        if uploaded_file.type == "application/pdf":
            if PdfReader is None:
                st.error("请先安装 pypdf: pip install pypdf")
            else:
                try:
                    reader = PdfReader(uploaded_file)
                    for page in reader.pages:
                        file_text += page.extract_text()
                    st.success(f"PDF 读取成功，共提取 {len(file_text)} 个字符")
                except Exception as e:
                    st.error(f"PDF读取失败：{e}")
        else:
            # txt
            file_text = uploaded_file.read().decode("utf-8")
            st.success("TXT 读取成功")
        
        if file_text:
            st.text_area("提取的文本内容（可手动修改）", file_text, height=200)
            
            if st.button("将文本发送到'添加与解析'页解析"):
                # 存入session，切换到tab1
                st.session_state["parsed_text"] = file_text[:500]  # 取前500字防止太长
                st.info("已保存，请切换到【添加与解析】标签，点击 AI 解析（但需手动粘贴内容）")
                st.markdown("**建议操作：** 复制上方文本，切到【添加与解析】标签，粘贴到输入框点击解析。")

# ========== 5. 底部提示 ==========
st.divider()
st.caption("💡 提示：数据自动保存在本地的 deadlines.csv 文件中，删除该文件会清空所有数据。")
