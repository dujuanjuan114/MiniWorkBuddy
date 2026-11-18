# app.py
import streamlit as st
import os
from agent_core import run_agent

st.set_page_config(page_title="通用文档分析 Agent", layout="wide")
st.title("📊 MiniWorkBuddy - 全能智能助理")

st.sidebar.header("1. 上传文件")
uploaded_file = st.sidebar.file_uploader(
    "支持 CSV, TXT, PDF, Word, PPT", 
    type=["csv", "txt", "pdf", "docx", "pptx"]
)

col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("2. 下达任务")
    default_task = "帮我总结一下这个文件的核心内容。"
    user_task = st.text_area("指令：", default_task, height=100)
    
    if st.button("🚀 开始执行", type="primary"):
        if uploaded_file is None:
            st.warning("请先上传文件！")
        else:
            file_ext = os.path.splitext(uploaded_file.name)[1]
            file_path = f"uploaded_file{file_ext}"
            
            with open(file_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            
            st.session_state.running = True
            st.session_state.file_path = file_path
            # 每次运行前清空之前的文本结果
            st.session_state.agent_text = ""

    if st.session_state.get("running", False):
        st.subheader("3. 执行步骤 (ReAct)")
        status_area = st.empty()
        logs = []
        
        def update_status(text):
            logs.append(text)
            status_area.markdown("\n\n".join(logs))
        
        # 接收 Agent 返回的文本结果
        result_text = run_agent(user_task, st.session_state.file_path, status_callback=update_status)
        st.session_state.agent_text = result_text
        st.session_state.running = False

with col2:
    st.subheader("4. 交付结果")
    
    # 【新增】：展示大模型直接输出的文字内容
    if st.session_state.get("agent_text"):
        st.info("🤖 智能体回复：")
        st.markdown(st.session_state.agent_text)
    
    # 如果生成了文件，展示下载区
    if os.path.exists("final_report.md") or os.path.exists("chart_output.png"):
        st.divider()
        st.write("📁 附件下载区：")
        if os.path.exists("chart_output.png"):
            st.image("chart_output.png", caption="数据图表")
            with open("chart_output.png", "rb") as f:
                st.download_button("⬇️ 下载图表", f, file_name="图表.png", mime="image/png")
        if os.path.exists("final_report.md"):
            with open("final_report.md", "r", encoding="utf-8") as f:
                st.download_button("⬇️ 下载报告文件", f.read(), file_name="报告.md")
    elif not st.session_state.get("agent_text"):
        st.info("等待执行...")