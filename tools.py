# tools.py
import pandas as pd
import matplotlib.pyplot as plt
import os
import PyPDF2
from docx import Document
from pptx import Presentation

# ========== 新增：多格式文档读取工具 ==========
def read_document(file_path):
    """支持读取 txt, pdf, docx, pptx"""
    ext = os.path.splitext(file_path)[1].lower()
    text = ""
    try:
        if ext == '.txt':
            with open(file_path, 'r', encoding='utf-8') as f:
                text = f.read()
        elif ext == '.pdf':
            with open(file_path, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages:
                    text += (page.extract_text() or "") + "\n"
        elif ext == '.docx':
            doc = Document(file_path)
            text = "\n".join([para.text for para in doc.paragraphs])
        elif ext == '.pptx':
            prs = Presentation(file_path)
            for slide in prs.slides:
                for shape in slide.shapes:
                    if hasattr(shape, "text"):
                        text += shape.text + "\n"
        else:
            return f"暂不支持 {ext} 格式"
        
        # 防止文档太长把大模型撑爆，截取前 3000 字
        if len(text) > 3000:
            text = text[:3000] + "\n...(文档过长，已截断)"
        return f"文档读取成功，内容如下：\n{text}"
    except Exception as e:
        return f"读取文档失败: {str(e)}"

# ========== 原有的 CSV 分析工具 ==========
def read_csv(file_path):
    try:
        df = pd.read_csv(file_path)
        return f"CSV读取成功，共{len(df)}行。前5行如下：\n{df.head(5).to_string()}"
    except Exception as e:
        return f"读取失败: {str(e)}"

def calculate_stats(file_path, column_name):
    try:
        df = pd.read_csv(file_path)
        if column_name not in df.columns:
            return f"错误：不存在 '{column_name}'。现有列：{list(df.columns)}"
        return f"列 '{column_name}' 总和 = {df[column_name].sum()}, 平均值 = {df[column_name].mean():.2f}"
    except Exception as e:
        return f"计算失败: {str(e)}"

def generate_chart(file_path, x_col, y_col):
    try:
        df = pd.read_csv(file_path)
        plt.figure(figsize=(8, 5))
        plt.rcParams['font.sans-serif'] = ['SimHei'] 
        plt.rcParams['axes.unicode_minus'] = False
        plt.bar(df[x_col], df[y_col], color='skyblue')
        plt.title(f'{x_col} vs {y_col}')
        img_path = "chart_output.png"
        plt.savefig(img_path)
        plt.close()
        return f"图表已生成"
    except Exception as e:
        return f"生成图表失败: {str(e)}"

def generate_report(report_text):
    try:
        md_content = f"# 分析报告\n\n{report_text}\n\n"
        if os.path.exists("chart_output.png"):
            md_content += "## 数据可视化\n![图表](chart_output.png)\n"
        with open("final_report.md", "w", encoding="utf-8") as f:
            f.write(md_content)
        return "报告已生成：final_report.md"
    except Exception as e:
        return f"生成报告失败: {str(e)}"

# ========== 更新工具说明书 ==========
TOOLS_SCHEMA = [
    {"name": "read_document", "description": "读取TXT/PDF/Word/PPT等文档的文字内容", "parameters": {"file_path": "文件路径"}},
    {"name": "read_csv", "description": "读取CSV表格数据", "parameters": {"file_path": "文件路径"}},
    {"name": "calculate_stats", "description": "计算CSV某列的总和和平均值", "parameters": {"file_path": "文件路径", "column_name": "列名"}},
    {"name": "generate_chart", "description": "针对CSV数据生成柱状图", "parameters": {"file_path": "文件路径", "x_col": "X轴", "y_col": "Y轴"}},
    {"name": "generate_report", "description": "根据分析结果生成最终报告", "parameters": {"report_text": "报告内容"}}
]