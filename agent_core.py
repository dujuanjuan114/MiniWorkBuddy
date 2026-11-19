# agent_core.py
import json
import os
import streamlit as st
from openai import OpenAI
import tools

try:
    API_KEY = st.secrets["DEEPSEEK_API_KEY"]
except Exception:
    API_KEY = os.getenv("DEEPSEEK_API_KEY")
if not API_KEY: API_KEY = "" 

client = OpenAI(api_key=API_KEY, base_url="https://api.deepseek.com")

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
    
    # 【核心修复】：明确告诉大模型，文档和表格是两条画图路线！
    system_prompt = f"""你是一个强大的数据分析与文档处理助手。当前文件路径：'{file_path}'，文件类型：'{ext}'。

请严格根据文件类型执行操作：
1. 【如果是 .csv 文件】：如果用户要求画图，必须调用 `generate_chart`。
   - 画折线图，`chart_type` 填 "line"。
   - 画饼图，`chart_type` 填 "pie"。
   - 画柱状图，`chart_type` 填 "bar"。
2. 【如果是 .txt, .pdf, .docx, .pptx 等文档】：如果用户要求画图（比如提取关键词画图），**必须调用 `generate_word_freq_chart`**。这个工具会自动分析文档并画图。
3. 【如果用户要求总结文档】：调用 `read_document`，然后直接在对话中输出总结，不要画图。
4. 只有当用户明确要求“生成报告文件”时，才调用 generate_report。"""

    messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_task}]
    
    step_count = 0
    while step_count < 8:
        step_count += 1
        try:
            response = client.chat.completions.create(model="deepseek-chat", messages=messages, tools=function_schemas, tool_choice="auto")
        except Exception as e:
            if status_callback: status_callback(f"❌ API 调用失败: {str(e)}")
            return "API 调用失败。"

        msg = response.choices[0].message
        messages.append(msg)

        if not msg.tool_calls:
            if status_callback: status_callback("✅ 任务完成。")
            return msg.content 

        for tool_call in msg.tool_calls:
            func_name = tool_call.function.name
            args = json.loads(tool_call.function.arguments)
            if status_callback: status_callback(f"【步骤{step_count}】调用工具: `{func_name}`")

            result = ""
            if func_name == "read_document": result = tools.read_document(args.get("file_path", file_path))
            elif func_name == "read_csv": result = tools.read_csv(args.get("file_path", file_path))
            elif func_name == "calculate_stats": result = tools.calculate_stats(args.get("file_path", file_path), args.get("column_name"))
            elif func_name == "generate_chart": 
                result = tools.generate_chart(args.get("file_path", file_path), args.get("x_col"), args.get("y_col"), args.get("chart_type", "bar"))
            elif func_name == "generate_word_freq_chart": 
                result = tools.generate_word_freq_chart(args.get("file_path", file_path))
            elif func_name == "generate_report": 
                result = tools.generate_report(args.get("report_text"))

            if status_callback: status_callback(f"  -> 结果: {str(result)[:50]}...") 
            messages.append({"role": "tool", "tool_call_id": tool_call.id, "name": func_name, "content": result})

            if func_name == "generate_report":
                if status_callback: status_callback("✅ 报告生成完毕。")
                return "报告已生成。"
    return "超时终止。"