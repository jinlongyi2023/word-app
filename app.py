import os
import streamlit as st
from notion_client import Client

# 获取环境变量
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
DATABASE_ID = os.getenv("DATABASE_ID")

notion = Client(auth=NOTION_TOKEN)

# 查询 Notion 数据库
def query_words(category=None, sub_category=None):
    filter_conditions = []

    if category:
        filter_conditions.append({"property": "大类", "select": {"equals": category}})
    if sub_category:
        filter_conditions.append({"property": "子类", "select": {"equals": sub_category}})

    if filter_conditions:
        filter_obj = {"and": filter_conditions}
    else:
        filter_obj = {}

    results = notion.databases.query(
        database_id=DATABASE_ID,
        filter=filter_obj if filter_conditions else None
    )

    words = []
    for row in results["results"]:
        props = row["properties"]
        word = props["单词"]["title"][0]["plain_text"] if props["单词"]["title"] else ""
        meaning = props["中文释义"]["rich_text"][0]["plain_text"] if props["中文释义"]["rich_text"] else ""
        pos = props["词性"]["select"]["name"] if props["词性"]["select"] else ""
        level = props["难度等级"]["select"]["name"] if props["难度等级"]["select"] else ""
        category = props["大类"]["select"]["name"] if props["大类"]["select"] else ""
        sub_category = props["子类"]["select"]["name"] if props["子类"]["select"] else ""
        mastered = props["已掌握"]["checkbox"]

        words.append({
            "单词": word,
            "释义": meaning,
            "词性": pos,
            "难度等级": level,
            "大类": category,
            "子类": sub_category,
            "已掌握": mastered
        })
    return words

# Streamlit 前端
st.set_page_config(page_title="TOPIK 词库（单表版）", layout="wide")
st.title("📚 TOPIK 词库（单表简化版）")

# 筛选条件
category = st.selectbox("选择大类", ["", "必备", "真题", "高频", "主题"])
sub_category = st.text_input("子类（可填如：初级/中级/Unit/听力/阅读等）")

# 查询数据
if st.button("查询单词"):
    data = query_words(category if category else None, sub_category if sub_category else None)
    if data:
        st.write(f"共找到 {len(data)} 条单词：")
        st.table(data)
    else:
        st.warning("没有找到符合条件的单词")

# 模式切换
mode = st.radio("模式", ["全部单词", "闪卡", "随机10个", "测试"])

words = query_words(category if category else None, sub_category if sub_category else None)

if mode == "全部单词":
    st.subheader("全部单词")
    for w in words:
        st.write(f"{w['单词']} ({w['词性']}) - {w['释义']}  [{w['大类']}/{w['子类']}]")

elif mode == "闪卡":
    st.subheader("闪卡模式")
    for w in words:
        with st.expander(w['单词']):
            st.write(f"{w['释义']} ({w['词性']})")

elif mode == "随机10个":
    import random
    st.subheader("随机抽取10个")
    sample = random.sample(words, min(10, len(words)))
    for w in sample:
        st.write(f"{w['单词']} - {w['释义']}")

elif mode == "测试":
    st.subheader("测试模式（显示单词，不显示释义）")
    for w in words:
        st.write(f"👉 {w['单词']}   （请写出中文释义）")

st.write(props.keys())
