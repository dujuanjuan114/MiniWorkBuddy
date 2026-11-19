# tools.py
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import os
import PyPDF2
from docx import Document
from pptx import Presentation
import jieba
from collections import Counter
import urllib.request

# ================= 暴力解决云端中文字体 =================
font_path = "SimHei.ttf"
if not os.path.exists(font_path):
    try:
        url = "https://raw.githubusercontent.com/StellarCN/scp_zh/master/fonts/SimHei.ttf"
        urllib.request.urlretrieve(url, font_path)
    except Exception:
        pass

if os.path.exists(font_path):
    fm.fontManager.addfont(font_path)
    prop = fm.FontProperties(fname=font_path)
    plt.rcParams['font.family'] = prop.get_name()
    plt.rcParams['font.sans-serif'] = [prop.get_name()]
plt.rcParams['axes.unicode_minus'] = False
# =======================================================

def extract_text(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    text = ""
    try:
        if ext == '.txt':
            with open(file_path, 'r', encoding='utf-8') as f: text = f.read()
        elif ext == '.pdf':
            with open(file_path, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages: text += (page.extract_text() or "") + "\n"
        elif ext == '.docx':
            doc = Document(file_path)
            text = "\n".join([para.text for para in doc.paragraphs])
        elif ext == '.pptx':
            prs = Presentation(file_path)
            for slide in prs.slides:
                for shape in slide.shapes:
                    if hasattr(shape, "text"): text += shape.text + "\n"
    except: pass
    return text

def read_document(file_path):
    text = extract_text(file_path)
    if not text: return "读取失败或文件为空。"
    if len(text) > 3000: return f"文档读取成功（前3000字）：\n{text[:3000]}..."
    return f"文档读取成功：\n{text}"

def read_csv(file_path):
    try:
        df = pd.read_csv(file_path)
        return f"CSV读取成功，共{len(df)}行。前5行如下：\n{df.head(5).to_string()}"
    except Exception as e: return f"读取失败: {str(e)}"

def calculate_stats(file_path, column_name):
    try:
        df = pd.read_csv(file_path)
        if column_name not in df.columns: return f"错误：不存在 '{column_name}'。现有列：{list(df.columns)}"
        return f"列 '{column_name}' 总和 = {df[column_name].sum()}, 平均值 = {df[column_name].mean():.2f}"
    except Exception as e: return f"计算失败: {str(e)}"

def generate_chart(file_path, x_col, y_col, chart_type="bar"):
    try:
        df = pd.read_csv(file_path)
        plt.figure(figsize=(8, 5))
        
        c_type = str(chart_type).lower()
        if "line" in c_type or "折线" in c_type:
            plt.plot(df[x_col], df[y_col], marker='o', color='#1f77b4', linewidth=2)
            plt.title(f'{x_col} 趋势图')
        elif "pie" in c_type or "饼" in c_type:
            df_pie = df.head(5)
            plt.pie(df_pie[y_col], labels=df_pie[x_col], autopct='%1.1f%%', startangle=90)
            plt.title(f'{x_col} 占比图')
        else:
            plt.bar(df[x_col], df[y_col], color='skyblue')
            plt.title(f'{x_col} vs {y_col} 柱状图')
            
        if "pie" not in str(chart_type).lower() and "饼" not in str(chart_type):
            plt.xlabel(x_col)
            plt.ylabel(y_col)
            
        plt.savefig("chart_output.png")
        plt.close()
        return f"成功生成图表"
    except Exception as e:
        return f"生成图表失败: {str(e)}"

def generate_word_freq_chart(file_path):
    try:
        text = extract_text(file_path)
        if not text: return "文档内容为空。"
        
        words = jieba.lcut(text)
        stop_words = ['我们', '可以', '这个', '没有', '就是', '一个', '进行', '通过', '如果', '以及', '因为', '所以', '他们', '自己', '现在', '什么']
        words = [w for w in words if len(w) > 1 and not w.isdigit() and w not in stop_words and w.strip() != '']
        
        word_counts = Counter(words).most_common(10)
        if not word_counts: return "未提取到有效词汇。"

        labels = [item[0] for item in word_counts]
        values = [item[1] for item in word_counts]

        plt.figure(figsize=(10, 5))
        plt.bar(labels, values, color='coral')
        plt.title('文档高频关键词 Top 10')
        plt.xticks(rotation=45)
        
        plt.savefig("chart_output.png")
        plt.close()
        return f"成功生成文档高频词图表"
    except Exception as e:
        return f"生成词频图表失败: {str(e)}"

def generate_report(report_text):
    try:
        md_content = f"# 分析报告\n\n{report_text}\n\n"
        if os.path.exists("chart_output.png"):
            md_content += "## 可视化图表\n![图表](chart_output.png)\n"
        with open("final_report.md", "w", encoding="utf-8") as f: f.write(md_content)
        return "报告已生成"
    except Exception as e: return f"生成失败: {str(e)}"

TOOLS_SCHEMA = [
    {"name": "read_document", "description": "读取TXT/PDF/Word/PPT等文档的文字内容", "parameters": {"file_path": "文件路径"}},
    {"name": "read_csv", "description": "读取CSV表格数据", "parameters": {"file_path": "文件路径"}},
    {"name": "calculate_stats", "description": "计算CSV某列的总和和平均值", "parameters": {"file_path": "文件路径", "column_name": "列名"}},
    {"name": "generate_chart", "description": "针对CSV表格生成图表", "parameters": {"file_path": "文件路径", "x_col": "X轴", "y_col": "Y轴", "chart_type": "必须是bar、line或pie"}},
    {"name": "generate_word_freq_chart", "description": "针对TXT/Word/PDF等文档生成高频词柱状图（当用户要求对非CSV文件画图时使用）", "parameters": {"file_path": "文件路径"}},
    {"name": "generate_report", "description": "生成最终报告", "parameters": {"report_text": "报告内容"}}
]