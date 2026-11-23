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
import json
import base64
from openai import OpenAI
import fitz  # PyMuPDF

# ================= 解决云端中文字体 =================
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

def extract_text(file_path, zhipu_api_key=None):
    ext = os.path.splitext(file_path)[1].lower()
    text = ""
    try:
        if ext == '.txt':
            with open(file_path, 'r', encoding='utf-8') as f: text = f.read()
        elif ext == '.pdf':
            with open(file_path, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages: 
                    text += (page.extract_text() or "") + "\n"
            
            if len(text.strip()) < 50 and zhipu_api_key:
                text = ""
                doc = fitz.open(file_path)
                for page_num in range(min(3, len(doc))):
                    page = doc[page_num]
                    pix = page.get_pixmap()
                    img_data = pix.tobytes("jpeg")
                    base64_image = base64.b64encode(img_data).decode('utf-8')
                    
                    vision_client = OpenAI(api_key=zhipu_api_key, base_url="https://open.bigmodel.cn/api/paas/v4/")
                    response = vision_client.chat.completions.create(
                        model="glm-4v-flash",
                        messages=[{
                            "role": "user",
                            "content": [
                                {"type": "text", "text": "请精准提取图片中的文字，如果是表格请用Markdown输出。"},
                                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                            ]
                        }]
                    )
                    text += f"\n--- 第 {page_num + 1} 页 ---\n" + response.choices[0].message.content
        elif ext == '.docx':
            doc = Document(file_path)
            text = "\n".join([para.text for para in doc.paragraphs])
        elif ext == '.pptx':
            prs = Presentation(file_path)
            for slide in prs.slides:
                for shape in slide.shapes:
                    if hasattr(shape, "text"): text += shape.text + "\n"
    except Exception as e: 
        return f"读取异常: {str(e)}"
    return text

def read_document(file_path, zhipu_api_key=None):
    text = extract_text(file_path, zhipu_api_key)
    if not text: return "读取失败或文件为空。"
    # 【解除封印】：不再截断，全量返回
    return f"文档读取成功，完整内容如下：\n{text}"

def read_image(file_path, zhipu_api_key):
    try:
        with open(file_path, "rb") as image_file:
            base64_image = base64.b64encode(image_file.read()).decode('utf-8')
        vision_client = OpenAI(api_key=zhipu_api_key, base_url="https://open.bigmodel.cn/api/paas/v4/")
        response = vision_client.chat.completions.create(
            model="glm-4v-flash",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": "请精准提取图片中的所有文字。如果是表格数据，请务必用 Markdown 格式输出表格，保留行列结构。"},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                ]
            }]
        )
        return f"图片识别成功，内容如下：\n{response.choices[0].message.content}"
    except Exception as e:
        return f"图片识别失败: {str(e)}"

def read_csv(file_path):
    try:
        df = pd.read_csv(file_path)
        return f"CSV读取成功，共{len(df)}行。前5行如下：\n{df.head(5).to_string()}"
    except Exception as e: return f"读取失败: {str(e)}"

def calculate_stats(file_path, column_name):
    try:
        df = pd.read_csv(file_path)
        if column_name not in df.columns: return f"错误：不存在 '{column_name}'。"
        return f"列 '{column_name}' 总和 = {df[column_name].sum()}, 平均值 = {df[column_name].mean():.2f}"
    except Exception as e: return f"计算失败: {str(e)}"

def generate_chart(file_path, x_col, y_col, chart_type="bar"):
    try:
        df = pd.read_csv(file_path)
        plt.figure(figsize=(10, 5))
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
        if "pie" not in c_type and "饼" not in c_type:
            plt.xlabel(x_col)
            plt.ylabel(y_col)
        plt.savefig("chart_output.png")
        plt.close()
        return f"成功生成图表"
    except Exception as e: return f"生成图表失败: {str(e)}"

def generate_custom_chart(x_data_str, series_data_str, chart_type="line", title="数据分析图"):
    try:
        x_data = json.loads(x_data_str) if isinstance(x_data_str, str) else x_data_str
        series_dict = json.loads(series_data_str) if isinstance(series_data_str, str) else series_data_str
        
        plt.figure(figsize=(10, 6))
        c_type = str(chart_type).lower()

        if "pie" in c_type or "饼" in c_type:
            first_key = list(series_dict.keys())[0]
            first_data = [float(v) for v in series_dict[first_key]]
            plt.pie(first_data[:8], labels=x_data[:8], autopct='%1.1f%%', startangle=90)
            plt.title(f"{title} ({first_key})")
        elif "bar" in c_type or "柱" in c_type:
            import numpy as np
            x_indexes = np.arange(len(x_data))
            width = 0.8 / len(series_dict)
            for i, (label, y_data) in enumerate(series_dict.items()):
                y_data = [float(v) for v in y_data]
                plt.bar(x_indexes + i * width - 0.4 + width/2, y_data, width=width, label=label)
            plt.xticks(x_indexes, x_data, rotation=45)
            plt.legend()
            plt.title(title)
        else:
            for label, y_data in series_dict.items():
                y_data = [float(v) for v in y_data]
                plt.plot(x_data, y_data, marker='o', linewidth=2, label=label)
            plt.xticks(rotation=45)
            plt.legend()
            plt.title(title)

        plt.tight_layout()
        plt.savefig("chart_output.png")
        plt.close()
        return f"成功生成包含 {len(series_dict)} 个数据系列的 {chart_type} 图表"
    except Exception as e: return f"生成自定义图表失败: {str(e)}"

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
    except Exception as e: return f"生成词频图表失败: {str(e)}"

def generate_report(report_text):
    try:
        md_content = f"# 分析报告\n\n{report_text}\n\n"
        if os.path.exists("chart_output.png"):
            md_content += "## 可视化图表\n![图表](chart_output.png)\n"
        with open("final_report.md", "w", encoding="utf-8") as f: f.write(md_content)
        return "报告已生成"
    except Exception as e: return f"生成失败: {str(e)}"

TOOLS_SCHEMA = [
    {"name": "read_document", "description": "读取TXT/PDF/Word/PPT文档。自动兼容扫描版图片PDF", "parameters": {"file_path": "文件路径"}},
    {"name": "read_image", "description": "识别普通图片(.png, .jpg)中的文字和表格", "parameters": {"file_path": "文件路径"}},
    {"name": "read_csv", "description": "读取CSV表格数据", "parameters": {"file_path": "文件路径"}},
    {"name": "calculate_stats", "description": "计算CSV某列的总和和平均值", "parameters": {"file_path": "文件路径", "column_name": "列名"}},
    {"name": "generate_chart", "description": "针对CSV文件生成图表", "parameters": {"file_path": "文件路径", "x_col": "X轴", "y_col": "Y轴", "chart_type": "bar、line或pie"}},
    {"name": "generate_custom_chart", "description": "根据提取的数据生成多变量图表", "parameters": {"x_data_str": "X轴JSON", "series_data_str": "Y轴JSON", "chart_type": "bar、line或pie", "title": "标题"}},
    {"name": "generate_word_freq_chart", "description": "针对文档生成高频词柱状图", "parameters": {"file_path": "文件路径"}},
    {"name": "generate_report", "description": "生成最终报告", "parameters": {"report_text": "报告内容"}}
]