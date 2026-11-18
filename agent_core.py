# agent_core.py
import json
from openai import OpenAI
import tools
import os

API_KEY = os.getenv("DEEPSEEK_API_KEY")
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
    
    # 【核心修改】：不强制生成报告。让它根据用户需求灵活决定。
    system_prompt = f"""你是一个极其聪明的通用助理。
当前用户上传的文件路径：'{file_path}'，类型：'{ext}'。

你的工作流如下：
1. 如果用户让你“总结/提炼”文档内容：请调用 read_document 读取内容，然后【直接在对话中输出你的总结】，不需要调用生成报告的工具。
2. 如果用户让你“分析数据”：请调用 read_csv 和 calculate_stats。
3. 如果用户要求“画图”：调用 generate_chart。
4. 只有当用户明确说出“帮我生成/导出一份报告文件”时，你才去调用 generate_report。
请根据用户的具体指令灵活行动，不要死板。"""

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

        # 如果模型没有调用工具，说明它认为可以直接回答（或者任务已完成）
        if not msg.tool_calls:
            if status_callback: status_callback("✅ 任务完成。")
            # 把模型最终生成的文字返回给前端！
            return msg.content 

        for tool_call in msg.tool_calls:
            func_name = tool_call.function.name
            args = json.loads(tool_call.function.arguments)
            
            if status_callback: status_callback(f"【步骤{step_count}】调用工具: `{func_name}`")

            result = ""
            if func_name == "read_document": result = tools.read_document(args.get("file_path", file_path))
            elif func_name == "read_csv": result = tools.read_csv(args.get("file_path", file_path))
            elif func_name == "calculate_stats": result = tools.calculate_stats(args.get("file_path", file_path), args.get("column_name"))
            elif func_name == "generate_chart": result = tools.generate_chart(args.get("file_path", file_path), args.get("x_col"), args.get("y_col"))
            elif func_name == "generate_report": result = tools.generate_report(args.get("report_text"))

            if status_callback: status_callback(f"  -> 结果: {str(result)[:50]}...") 

            messages.append({
                "role": "tool", "tool_call_id": tool_call.id, "name": func_name, "content": result
            })

            # 如果模型主动调用了生成报告，说明它想结束任务
            if func_name == "generate_report":
                if status_callback: status_callback("✅ 报告文件已生成。")
                return "报告已生成，请在右侧下载。"

    return "超过最大步数"