# agent_core.py
import json
from openai import OpenAI
import tools
import os

# 优先读环境变量（部署在云端用），如果没有，用本地保底的 Key（本地测试用）
API_KEY = os.getenv("DEEPSEEK_API_KEY")
if not API_KEY: 
    API_KEY = "sk-7754c740b2d4467e8d2a6993ced5d608" # 如果你本地测试，记得填你的 Key
    
client = OpenAI(api_key=API_KEY, base_url="https://api.deepseek.com")

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
    
    # 【已升级】系统提示词，教大模型如何选择图表类型
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
        response = client.chat.completions.create(
            model="deepseek-chat", messages=messages, tools=function_schemas, tool_choice="auto"
        )
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
            if func_name == "read_document": 
                result = tools.read_document(args.get("file_path", file_path))
            elif func_name == "read_csv": 
                result = tools.read_csv(args.get("file_path", file_path))
            elif func_name == "calculate_stats": 
                result = tools.calculate_stats(args.get("file_path", file_path), args.get("column_name"))
            elif func_name == "generate_chart": 
                # 【已升级】接收 chart_type 参数
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

            if func_name == "generate_report":
                if status_callback: status_callback("✅ 报告文件已生成。")
                return "报告已生成，请在右侧下载。"
                
    return "超过最大步数"