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
    # 【修改】：判断是否有文件
    if file_path and os.path.exists(file_path):
        ext = os.path.splitext(file_path)[1].lower()
        file_context = f"当前用户上传了文件，路径：'{file_path}'，类型：'{ext}'。"
        rules = """规则如下：
1. 图片(.jpg, .png)：调用 `read_image` 识别。
2. CSV：读取并处理数据，单变量画图用 `generate_chart`。
3. 文档(Word/PDF)：先调用 `read_document`，提取多变量数据时用 `generate_custom_chart`。"""
    else:
        file_context = "当前用户没有上传任何文件。"
        rules = """规则如下：
1. 如果用户只是聊天或提问，请直接回答，不要调用任何工具。
2. 如果用户口述了一些数据要求你画图（比如：“帮我画个图，X是苹果香蕉，Y是10和20”），请你自己构造数据，调用 `generate_custom_chart` 工具。"""

    system_prompt = f"""你是一个极其强大的全能数据助理。{file_context}

{rules}

【重要格式要求】：
画自定义图时，`x_data_str` 和 `series_data_str` 必须传标准的 JSON 字符串（如 '["A", "B"]' 和 '{{"销量": [10, 20]}}'），绝对不能用中文引号！
只有当用户明确要求“生成一份报告文件”时，才调用 generate_report。"""

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
            # 只有存在文件时，才允许调用读取文件的工具
            if func_name == "read_document" and file_path: result = tools.read_document(args.get("file_path", file_path))
            elif func_name == "read_image" and file_path: result = tools.read_image(args.get("file_path", file_path), ZHIPU_API_KEY)
            elif func_name == "read_csv" and file_path: result = tools.read_csv(args.get("file_path", file_path))
            elif func_name == "calculate_stats" and file_path: result = tools.calculate_stats(args.get("file_path", file_path), args.get("column_name"))
            elif func_name == "generate_chart" and file_path: 
                result = tools.generate_chart(args.get("file_path", file_path), args.get("x_col"), args.get("y_col"), args.get("chart_type", "bar"))
            
            # 无论有没有文件，都可以调用生成自定义图表的工具（因为数据是模型自己构造的）
            elif func_name == "generate_custom_chart":
                result = tools.generate_custom_chart(args.get("x_data_str", "[]"), args.get("series_data_str", "{}"), args.get("chart_type", "line"), args.get("title", "数据分析"))
            
            elif func_name == "generate_word_freq_chart" and file_path: 
                result = tools.generate_word_freq_chart(args.get("file_path", file_path))
            elif func_name == "generate_report": 
                result = tools.generate_report(args.get("report_text"))
            else:
                result = "错误：由于用户未上传文件，无法调用读取文件的工具。"

            if status_callback: status_callback(f"  -> 结果: {str(result)[:50]}...") 
            messages.append({"role": "tool", "tool_call_id": tool_call.id, "name": func_name, "content": result})

            if func_name == "generate_report":
                if status_callback: status_callback("✅ 报告生成完毕。")
                return "报告已生成。"
    return "超时终止。"