# agent_core.py
import json
import os
import streamlit as st
from openai import OpenAI
import tools

try:
    API_KEY = st.secrets["DEEPSEEK_API_KEY"]
    ZHIPU_API_KEY = st.secrets["ZHIPU_API_KEY"]
except Exception:
    API_KEY = os.getenv("DEEPSEEK_API_KEY")
    ZHIPU_API_KEY = os.getenv("ZHIPU_API_KEY")

if not API_KEY: API_KEY = "" 
if not ZHIPU_API_KEY: ZHIPU_API_KEY = ""

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
    if file_path and os.path.exists(file_path):
        ext = os.path.splitext(file_path)[1].lower()
        file_context = f"当前用户上传了文件，路径：'{file_path}'，类型：'{ext}'。"
        rules = """规则：
1. PDF/Word 等文档，先用 `read_document`。
2. 普通图片 (.jpg, .png)，先用 `read_image`。
3. 提取到数据后，用 `generate_custom_chart` 画图。"""
    else:
        file_context = "当前用户没有上传任何文件。"
        rules = "如果用户口述数据要求画图，请构造 JSON 数据，调用 `generate_custom_chart`。"

    system_prompt = f"""你是一个极其强大的全能数据助理。{file_context}
{rules}
【格式警告】：画图时，参数必须是标准的 JSON 字符串格式（双引号）。"""

    messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_task}]
    
    step_count = 0
    # 【防失控锁】：最大循环 4 次，防止 API 爆炸
    while step_count < 4:
        step_count += 1
        try:
            response = client.chat.completions.create(model="deepseek-chat", messages=messages, tools=function_schemas, tool_choice="auto")
        except Exception as e:
            if status_callback: status_callback(f"❌ API 调用失败: {str(e)}")
            return "API 调用失败，已停止重试。"

        msg = response.choices[0].message
        messages.append(msg)

        if not msg.tool_calls:
            if status_callback: status_callback("✅ 任务完成。")
            return msg.content 

        for tool_call in msg.tool_calls:
            func_name = tool_call.function.name
            try:
                args = json.loads(tool_call.function.arguments)
            except Exception:
                args = {}
                
            if status_callback: status_callback(f"【步骤{step_count}】调用工具: `{func_name}`")

            result = ""
            try:
                if func_name == "read_document": 
                    result = tools.read_document(args.get("file_path", file_path), ZHIPU_API_KEY)
                elif func_name == "read_image": 
                    result = tools.read_image(args.get("file_path", file_path), ZHIPU_API_KEY)
                elif func_name == "read_csv": 
                    result = tools.read_csv(args.get("file_path", file_path))
                elif func_name == "calculate_stats": 
                    result = tools.calculate_stats(args.get("file_path", file_path), args.get("column_name"))
                elif func_name == "generate_chart": 
                    result = tools.generate_chart(args.get("file_path", file_path), args.get("x_col"), args.get("y_col"), args.get("chart_type", "bar"))
                elif func_name == "generate_custom_chart":
                    result = tools.generate_custom_chart(args.get("x_data_str", "[]"), args.get("series_data_str", "{}"), args.get("chart_type", "line"), args.get("title", "数据分析"))
                elif func_name == "generate_word_freq_chart": 
                    result = tools.generate_word_freq_chart(args.get("file_path", file_path))
                elif func_name == "generate_report": 
                    result = tools.generate_report(args.get("report_text"))
            except Exception as e:
                result = f"工具执行报错: {str(e)}"

            if status_callback: status_callback(f"  -> 结果: {str(result)[:30]}...") 
            messages.append({"role": "tool", "tool_call_id": tool_call.id, "name": func_name, "content": result})

            if func_name == "generate_report":
                if status_callback: status_callback("✅ 报告生成完毕。")
                return "报告已生成。"
                
    return "已达最大执行次数限制，强制中止（防止扣费）。"