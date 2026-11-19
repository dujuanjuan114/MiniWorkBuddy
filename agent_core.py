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
    
    # 【核心提示词】：教会大模型如何提取多个变量的数据
    system_prompt = f"""你是一个极其强大的全能数据助理。当前文件路径：'{file_path}'，类型：'{ext}'。

规则如下：
1. 如果文件是 CSV 且只需单变量画图，用 `generate_chart`。
2. 如果文件是文档(Word/PDF等)，且用户要求画图：
   - 必须先调用 `read_document` 阅读内容。
   - **重点**：如果文档里有多个变量的数据（例如同时有最高气温和最低气温），你必须把它们全部提取出来，调用 `generate_custom_chart` 画在同一张图上。
   - 参数要求：
     - `x_data_str`: 必须传类似 '["11月1日", "11月2日"]' 的 JSON 字符串。
     - `series_data_str`: 必须传字典格式的 JSON 字符串，如 '{{"最高气温": [20, 14], "最低气温": [2, 1]}}'。绝对不能用中文引号或单引号！
3. 如果用户要求总结：调用 `read_document` 并在对话输出。"""

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
            elif func_name == "generate_custom_chart":
                x_str = args.get("x_data_str", "[]")
                # 这里接收多变量字典
                series_str = args.get("series_data_str", "{}")
                result = tools.generate_custom_chart(x_str, series_str, args.get("chart_type", "line"), args.get("title", "数据分析"))
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