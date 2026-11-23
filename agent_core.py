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

# 使用免费的智谱模型
client = OpenAI(api_key=ZHIPU_API_KEY, base_url="https://open.bigmodel.cn/api/paas/v4/")

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
        
        # 【究极强化】：逼迫模型必须走正确的分支
        rules = """【强制执行纪律】：
1. 如果文件是 .pdf, .docx, .pptx, .txt，你必须**第一步**就调用 `read_document` 读取全文。
2. 如果文件是图片 (.jpg, .png, .jpeg)，你必须**第一步**就调用 `read_image`。
3. 在读取完内容后，如果你需要用数据画图（比如提取日期和气温），**绝不允许只用柱状图工具**。你必须自己从文本中提取数据，然后调用 `generate_custom_chart` 工具，传给它 JSON 格式的 X 轴和 Y 轴数据。
4. 如果你想画词频图，才用 `generate_word_freq_chart`。
5. 如果文件是 .csv，且只需简单画图，才用 `generate_chart`。
6. 严格遵循上述规则，禁止跳过读取直接回答，禁止说做不到，你拥有所有工具权限！"""

    else:
        file_context = "当前用户没有上传任何文件。"
        rules = "如果用户口述数据要求画图，请自己构造 JSON 数据，严格调用 `generate_custom_chart` 工具生成图表。"

    system_prompt = f"""你是一个极其强大的全能数据助理。{file_context}
{rules}
【JSON格式严格警告】：在调用 `generate_custom_chart` 时，参数 `x_data_str` 必须类似于 '["1月", "2月"]'，`series_data_str` 必须类似于 '{{"销量": [10, 20], "利润": [5, 10]}}'。必须是双引号，绝对不能用单引号或中文符号！"""

    messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_task}]
    
    step_count = 0
    # 【解除限制】：给足 8 次机会，让它慢慢思考
    while step_count < 8:
        step_count += 1
        try:
            response = client.chat.completions.create(
                model="glm-4-flash", 
                messages=messages, 
                tools=function_schemas, 
                tool_choice="auto"
            )
        except Exception as e:
            if status_callback: status_callback(f"❌ API 调用失败: {str(e)}")
            return "API 调用失败，请稍后重试。"

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
            
            messages.append({
                "role": "tool", 
                "tool_call_id": tool_call.id, 
                "name": func_name, 
                "content": result
            })

            if func_name == "generate_report":
                if status_callback: status_callback("✅ 报告生成完毕。")
                return "报告已生成。"
                
    return "达到最大执行次数，任务终止。"