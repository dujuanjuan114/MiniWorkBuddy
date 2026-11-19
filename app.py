# app.py
import streamlit as st
import os
import uuid
from agent_core import run_agent

st.set_page_config(page_title="全能智能助理", layout="wide")
st.title("📊 MiniWorkBuddy - 全能智能助理")

if "agent_text" not in st.session_state:
    st.session_state.agent_text = ""
if "has_run" not in st.session_state:
    st.session_state.has_run = False

st.sidebar.header("1. 上传文件")
uploaded_file = st.sidebar.file_uploader(
    "支持 CSV, TXT, PDF, Word, PPT", 
    type=["csv", "txt", "pdf", "docx", "pptx"]
)

col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("2. 下达任务")
    user_task = st.text_area("指令：", "帮我读取数据并画图。", height=100)
    
    if st.button("🚀 开始执行", type="primary"):
        if uploaded_file is None:
            st.warning("请先上传文件！")
        else:
            if os.path.exists("chart_output.png"): 
                try: os.remove("chart_output.png")
                except: pass
            if os.path.exists("final_report.md"): 
                try: os.remove("final_report.md")
                except: pass
                
            st.session_state.agent_text = ""
            st.session_state.has_run = False
            
            unique_id = uuid.uuid4().hex[:8]
            file_ext = os.path.splitext(uploaded_file.name)[1]
            file_path = f"uploaded_{unique_id}{file_ext}"
            
            with open(file_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            
            st.session_state.running = True
            st.session_state.file_path = file_path

    if st.session_state.get("running", False):
        st.subheader("3. 执行步骤 (ReAct)")
        status_area = st.empty()
        logs = []
        
        def update_status(text):
            logs.append(text)
            status_area.markdown("\n\n".join(logs))
        
        result_text = run_agent(user_task, st.session_state.file_path, status_callback=update_status)
        st.session_state.agent_text = result_text
        st.session_state.running = False
        st.session_state.has_run = True

with col2:
    st.subheader("4. 交付结果")
    
    if st.session_state.get("agent_text"):
        st.info("🤖 智能体回复：")
        st.markdown(st.session_state.agent_text)
    
    if st.session_state.get("has_run", False):
        if os.path.exists("chart_output.png") or os.path.exists("final_report.md"):
            st.divider()
            st.write("📁 附件下载区：")
            if os.path.exists("chart_output.png"):
                st.image("chart_output.png", caption="最新生成的图表")
                with open("chart_output.png", "rb") as f:
                    st.download_button("⬇️ 下载图表", f, file_name="图表.png", mime="image/png")
            if os.path.exists("final_report.md"):
                with open("final_report.md", "r", encoding="utf-8") as f:
                    st.download_button("⬇️ 下载报告文件", f.read(), file_name="报告.md")
        else:
            st.info("本次没有生成图表或报告文件。")
    elif not st.session_state.get("agent_text"):
        st.info("等待执行...")