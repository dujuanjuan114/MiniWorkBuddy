# tools.py
import pandas as pd
import matplotlib.pyplot as plt
import os
import PyPDF2
from docx import Document
from pptx import Presentation
import jieba
from collections import Counter

# 解决画图中文乱码
plt.rcParams['font.sans-serif'] = ['SimHei'] 
plt.rcParams['axes.unicode_minus'] = False

# 读取文档
def read_document(file_path):
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
        
        if len(text) > 3000:
            text = text[:3000] + "\n...(文档过长，已截断)"
        return f"文档读取成功，内容如下：\n{text}"
    except Exception as e:
        return f"读取文档失败: {str(e)}"

# 原有CSV读取
def read_csv(file_path):
    try:
        df = pd.read_csv(file_path)
        return f"CSV读取成功，共{len(df)}行。前5行如下：\n{df.head(5).to_string()}"
    except Exception as e:
        return f"读取失败: {str(e)}"

# 原有数据计算
def calculate_stats(file_path, column_name):
    try:
        df = pd.read_csv(file_path)
        if column_name not in df.columns:
            return f"错误：不存在 '{column_name}'。现有列：{list(df.columns)}"
        return f"列 '{column_name}' 总和 = {df[column_name].sum()}, 平均值 = {df[column_name].mean():.2f}"
    except Exception as e:
        return f"计算失败: {str(e)}"

# 原有CSV画图
def generate_chart(file_path, x_col, y_col):
    try:
        df = pd.read_csv(file_path)
        plt.figure(figsize=(8, 5))
        plt.bar(df[x_col], df[y_col], color='skyblue')
        plt.title(f'{x_col} vs {y_col}')
        img_path = "chart_output.png"
        plt.savefig(img_path)
        plt.close()
        return f"表格图表已生成"
    except Exception as e:
        return f"生成图表失败: {str(e)}"

# 【新增】：文档词频分析画图
def generate_word_freq_chart(file_path):
    try:
        # 先获取文本
        text = read_document(file_path)
        if "失败" in text or "不支持" in text:
            return text
        
        # 使用 jieba 分词，只保留长度大于1的词
        words = jieba.lcut(text)
        words = [w for w in words if len(w) > 1 and w not in ['我们', '可以', '这个', '没有', '就是', '一个', '进行', '通过', '如果']]
        
        # 统计前10个高频词
        word_counts = Counter(words).most_common(10)
        if not word_counts:
            return "文档内容太少，无法提取关键词。"

        labels = [item[0] for item in word_counts]
        values = [item[1] for item in word_counts]

        plt.figure(figsize=(10, 5))
        plt.bar(labels, values, color='coral')
        plt.title('文档高频关键词 Top 10')
        plt.xticks(rotation=45)
        
        img_path = "chart_output.png"
        plt.savefig(img_path)
        plt.close()
        return f"文档词频图表已生成，高频词包含：{labels[:3]}等"
    except Exception as e:
        return f"生成词频图表失败: {str(e)}"

def generate_report(report_text):
    try:
        md_content = f"# 分析报告\n\n{report_text}\n\n"
        if os.path.exists("chart_output.png"):
            md_content += "## 可视化图表\n![图表](chart_output.png)\n"
        with open("final_report.md", "w", encoding="utf-8") as f:
            f.write(md_content)
        return "报告已生成：final_report.md"
    except Exception as e:
        return f"生成报告失败: {str(e)}"

# 【更新工具说明书】
TOOLS_SCHEMA = [
    {"name": "read_document", "description": "读取TXT/PDF/Word/PPT等文档的文字内容", "parameters": {"file_path": "文件路径"}},
    {"name": "read_csv", "description": "读取CSV表格数据", "parameters": {"file_path": "文件路径"}},
    {"name": "calculate_stats", "description": "计算CSV某列的总和和平均值", "parameters": {"file_path": "文件路径", "column_name": "列名"}},
    {"name": "generate_chart", "description": "针对CSV表格生成柱状图", "parameters": {"file_path": "文件路径", "x_col": "X轴", "y_col": "Y轴"}},
    {"name": "generate_word_freq_chart", "description": "针对TXT/PDF/Word/PPT等文档生成高频词柱状图（当用户要求对文档画图时使用）", "parameters": {"file_path": "文件路径"}},
    {"name": "generate_report", "description": "根据分析结果生成最终报告", "parameters": {"report_text": "报告内容"}}
]