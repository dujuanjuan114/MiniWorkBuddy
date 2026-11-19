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
    
    # 【终极提示词】：明确告诉它怎么处理文本中的数据
    system_prompt = f"""你是一个极其强大的全能数据助理。当前文件路径：'{file_path}'，文件类型：'{ext}'。

请严格遵循以下规则：
1. 【CSV文件】：画图必须用 `generate_chart`（读取列名）。
2. 【文档文件(Word/PDF/TXT)】：如果你要画词频图，用 `generate_word_freq_chart`。
3. 【关键：文档数据提取画图】：如果用户要求根据文档里的具体数据画图（比如“提取温度变化画折线图”），你必须：
   - 先调用 `read_document` 阅读内容。
   - 然后，在脑子里把数据提取出来，转换成列表格式。
   - 最后，调用 `generate_custom_chart`。
   - 注意：`x_data_str` 必须传类似 '["11月1日", "11月2日"]' 的字符串；`y_data_str` 必须传类似 '["20", "14"]' 的字符串。绝对不能传中文逗号。
4. 如果用户要求总结：调用 `read_document` 并在对话输出。
5. 只有用户要求“生成报告文件”时，才调用 generate_report。"""

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
                # 接收大模型提取的 JSON 字符串
                x_str = args.get("x_data_str", "[]")
                y_str = args.get("y_data_str", "[]")
                result = tools.generate_custom_chart(x_str, y_str, args.get("chart_type", "line"), args.get("title", "数据分析"))
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