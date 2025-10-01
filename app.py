import streamlit as st
from notion_client import Client
import random

# --------------------
# 配置
# --------------------
NOTION_TOKEN = st.secrets["NOTION_TOKEN"]   # 在 Railway/Streamlit Cloud 的 secrets 设置
DATABASE_ID = st.secrets["DATABASE_ID"]

notion = Client(auth=NOTION_TOKEN)

# --------------------
# 从 Notion 查询单词
# --------------------
def query_words(category=None, subcategory=None):
    filters = []
    if category:
        filters.append({
            "property": "category",
            "select": {"equals": category}
        })
    if subcategory:
        filters.append({
            "property": "subcategory",
            "select": {"equals": subcategory}
        })

    filter_query = {"and": filters} if filters else {}

    results = notion.databases.query(
        database_id=DATABASE_ID,
        filter=filter_query if filters else None
    )

    words = []
    for row in results["results"]:
        props = row["properties"]
        words.append({
            "word": props["word"]["title"][0]["text"]["content"] if props["word"]["title"] else "",
            "meaning": props["meaning"]["rich_text"][0]["text"]["content"] if props["meaning"]["rich_text"] else "",
            "pos": props["pos"]["select"]["name"] if props["pos"]["select"] else "",
            "level": props["level"]["select"]["name"] if props["level"]["select"] else "",
            "category": props["category"]["select"]["name"] if props["category"]["select"] else "",
            "subcategory": props["subcategory"]["select"]["name"] if props["subcategory"]["select"] else "",
            "mastered": props["mastered"]["checkbox"] if "mastered" in props else False
        })
    return words

# --------------------
# Streamlit 界面
# --------------------
st.set_page_config(page_title="TOPIK 词库（单表版）", layout="wide")
st.title("📚 TOPIK 词库（单表简化版）")

# 筛选条件
category = st.selectbox("选择大类", ["", "必备单词", "真题单词", "高频词汇", "主题词汇"])
subcategory = st.text_input("子类 (可填: 初级/中级/Unit/听力/阅读/科技/生活...)")

if st.button("查询单词"):
    data = query_words(category if category else None, subcategory if subcategory else None)

    if not data:
        st.warning("⚠️ 没有查到单词，请检查筛选条件")
    else:
        mode = st.radio("模式", ["全部单词", "闪卡", "随机10个", "测试"])

        if mode == "全部单词":
            st.table(data)

        elif mode == "闪卡":
            for w in data:
                with st.expander(w["word"]):
                    st.write(f"📖 释义: {w['meaning']}")
                    st.write(f"词性: {w['pos']} | 等级: {w['level']} | 子类: {w['subcategory']}")

        elif mode == "随机10个":
            sample = random.sample(data, min(10, len(data)))
            st.table(sample)

        elif mode == "测试":
            score = 0
            for w in random.sample(data, min(5, len(data))):
                answer = st.text_input(f"{w['word']} 的中文意思是？", key=w['word'])
                if answer.strip() == w["meaning"]:
                    score += 1
            st.success(f"你的得分：{score}/{min(5, len(data))}")
