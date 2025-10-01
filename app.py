import streamlit as st
from notion_client import Client
import random

# ------------------------
# Notion 配置
# ------------------------
NOTION_TOKEN = st.secrets["NOTION_TOKEN"]
DATABASE_ID = st.secrets["DATABASE_ID"]

notion = Client(auth=NOTION_TOKEN)

# ------------------------
# 页面配置
# ------------------------
st.set_page_config(page_title="TOPIK 词库（单表版）", layout="wide")
st.title("📚 TOPIK 词库（单表简化版）")

# ------------------------
# 类别映射 (前端显示中文，后台查询英文)
# ------------------------
category_map = {
    "": "",
    "必备单词": "Essential",
    "真题单词": "Past Exam",
    "高频词汇": "High Frequency",
    "主题词汇": "Topic"
}

# ------------------------
# 查询函数
# ------------------------
def query_words(category=None, sub_category=None):
    filters = []

    if category:
        filters.append({
            "property": "category",
            "select": {"equals": category}
        })

    if sub_category:
        filters.append({
            "property": "subcategory",
            "select": {"equals": sub_category}
        })

    filter_obj = {"and": filters} if filters else None

    results = notion.databases.query(
        **{"database_id": DATABASE_ID, "filter": filter_obj} if filter_obj else {"database_id": DATABASE_ID}
    )

    words = []
    for r in results["results"]:
        props = r["properties"]
        word = props["word"]["title"][0]["text"]["content"] if props["word"]["title"] else ""
        meaning = props["meaning"]["rich_text"][0]["text"]["content"] if props["meaning"]["rich_text"] else ""
        pos = props["pos"]["select"]["name"] if props["pos"]["select"] else ""
        level = props["level"]["select"]["name"] if props["level"]["select"] else ""
        category_val = props["category"]["select"]["name"] if props["category"]["select"] else ""
        subcategory_val = props["subcategory"]["select"]["name"] if props["subcategory"]["select"] else ""
        mastered = props["mastered"]["checkbox"]

        words.append({
            "word": word,
            "meaning": meaning,
            "pos": pos,
            "level": level,
            "category": category_val,
            "subcategory": subcategory_val,
            "mastered": mastered
        })
    return words

# ------------------------
# 页面筛选条件
# ------------------------
ui_choice = st.selectbox("选择大类", list(category_map.keys()))
category = category_map[ui_choice]

subcategory = st.text_input("子类 (可填: 初级/中级/Unit/听力/阅读/科技/生活...)")

# ------------------------
# 模式选择
# ------------------------
mode = st.radio("模式", ["全部单词", "闪卡", "随机10个", "测试"])

# ------------------------
# 查询并展示
# ------------------------
if st.button("查询单词"):
    words = query_words(category if category else None, subcategory if subcategory else None)

    if not words:
        st.warning("没有查询到单词，请检查筛选条件。")
    else:
        if mode == "全部单词":
            st.table(words)

        elif mode == "闪卡":
            for w in words:
                with st.expander(w["word"]):
                    st.write(f"中文: {w['meaning']}")
                    st.write(f"词性: {w['pos']} | 等级: {w['level']} | 来源: {w['category']} / {w['subcategory']}")

        elif mode == "随机10个":
            sample = random.sample(words, min(10, len(words)))
            for w in sample:
                with st.expander(w["word"]):
                    st.write(f"中文: {w['meaning']}")
                    st.write(f"词性: {w['pos']} | 等级: {w['level']} | 来源: {w['category']} / {w['subcategory']}")

        elif mode == "测试":
            st.info("测试模式开发中...")
