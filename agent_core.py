# agent_core.py
import json
import os
import streamlit as st
from openai import OpenAI
import tools

# ================= 安全读取 API Key =================
# 1. 优先尝试从 Streamlit 云端 Secrets 读取（部署在公网时生效）
try:
    API_KEY = st.secrets["DEEPSEEK_API_KEY"]
except Exception:
    # 2. 如果云端没有，尝试从系统环境变量读取（本地运行且配置了环境变量时生效）
    API_KEY = os.getenv("DEEPSEEK_API_KEY")

# 3. 如果都没有，为了防止报错，在这里填入你的 Key 仅供本地测试
# 【注意：一旦部署到云端，请务必确保这里为 "" 】
if not API_KEY:
    API_KEY = "" 

if not API_KEY:
    st.warning("⚠️ 未检测到 API Key，请检查配置！")

client = OpenAI(api_key=API_KEY, base_url="https://api.deepseek.com")
# ====================================================

# 构建给大模型看的函数调用格式
function_schemas = []
for tool in tools.TOOLS_SCHEMA:
    function_schemas.append({
        "type": "function",
        "function": {
            "name": tool["name"],
            "description": tool["description"],
            "parameters": {
                "type": "object",
                "properties": {k: {"type": "string"} for k in tool["parameters"].keys()},
                "required": list(tool["parameters"].keys())
            }
        }
    })

def run_agent(user_task, file_path, status_callback=None):
    ext = os.path.splitext(file_path)[1].lower()
    
    # 【核心提示词】：指导大模型在不同文件下如何选择工具和图表类型
    system_prompt = f"""你是一个极其聪明的通用助理。当前用户上传的文件路径：'{file_path}'，类型：'{ext}'。

你的工作流如下：
1. 如果文件是 .csv：如果你要画图，必须调用 `generate_chart`。
   - 如果用户让你画“折线图/趋势”，chart_type 参数填 "line"。
   - 如果用户让你画“饼图/占比”，chart_type 参数填 "pie"。
   - 如果没明确说，或者要画“柱状图/对比”，chart_type 参数填 "bar"。
2. 如果文件是 .txt, .pdf, .docx, .pptx：如果你要画图（比如用户要求可视化、提取关键词），必须调用 `generate_word_freq_chart` 来画词频图。你可以先调用 read_document 看看内容。
3. 如果用户让你总结文档：调用 read_document，然后直接在对话中输出总结。
4. 只有当用户明确要求“生成报告文件”时，才调用 generate_report。"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_task}
    ]
    
    step_count = 0
    while step_count < 8:
        step_count += 1
        
        try:
            response = client.chat.completions.create(
                model="deepseek-chat", 
                messages=messages, 
                tools=function_schemas, 
                tool_choice="auto"
            )
        except Exception as e:
            if status_callback: status_callback(f"❌ API 调用失败: {str(e)}")
            return "调用大模型失败，请检查 API Key 或网络。"

        msg = response.choices[0].message
        messages.append(msg)

        # 如果不需要调用工具，直接返回大模型的文本回答
        if not msg.tool_calls:
            if status_callback: status_callback("✅ 任务完成。")
            return msg.content 

        # 解析工具调用
        for tool_call in msg.tool_calls:
            func_name = tool_call.function.name
            args = json.loads(tool_call.function.arguments)
            
            if status_callback: status_callback(f"【步骤{step_count}】调用工具: `{func_name}`")

            result = ""
            # 动态路由执行工具
            if func_name == "read_document": 
                result = tools.read_document(args.get("file_path", file_path))
            elif func_name == "read_csv": 
                result = tools.read_csv(args.get("file_path", file_path))
            elif func_name == "calculate_stats": 
                result = tools.calculate_stats(args.get("file_path", file_path), args.get("column_name"))
            elif func_name == "generate_chart": 
                # 接收 chart_type 参数
                c_type = args.get("chart_type", "bar")
                result = tools.generate_chart(args.get("file_path", file_path), args.get("x_col"), args.get("y_col"), c_type)
            elif func_name == "generate_word_freq_chart": 
                result = tools.generate_word_freq_chart(args.get("file_path", file_path))
            elif func_name == "generate_report": 
                result = tools.generate_report(args.get("report_text"))

            if status_callback: status_callback(f"  -> 结果: {str(result)[:50]}...") 

            # 把工具执行结果发给大模型
            messages.append({
                "role": "tool", "tool_call_id": tool_call.id, "name": func_name, "content": result
            })

            # 如果模型调用了生成报告工具，任务直接结束
            if func_name == "generate_report":
                if status_callback: status_callback("✅ 报告文件已生成。")
                return "报告已生成，请在右侧下载。"
                
    return "达到最大执行步数，任务终止。"