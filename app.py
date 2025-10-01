import streamlit as st
from notion_client import Client
import os
import random

# ================== 配置 ==================
NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
DATABASE_ID = os.environ.get("DATABASE_ID")
# =========================================

# 初始化 Notion 客户端
notion = Client(auth=NOTION_TOKEN)

st.set_page_config(page_title="TOPIK 韩语单词库 DEMO", page_icon="📚", layout="centered")
st.title("📚 TOPIK 韩语单词库 DEMO")

# 拉取数据函数
@st.cache_data
def get_words():
    """从 Notion 数据库获取单词数据"""
    results = notion.databases.query(database_id=DATABASE_ID)
    words = []
    for row in results["results"]:
        try:
            word = row["properties"]["单词"]["title"][0]["text"]["content"]
        except:
            word = "（空）"

        try:
            meaning = row["properties"]["中文释义"]["rich_text"][0]["text"]["content"]
        except:
            meaning = "（无释义）"

        try:
            pos = row["properties"]["词性"]["select"]["name"]
        except:
            pos = "（无词性）"

        words.append((word, meaning, pos))
    return words

words = get_words()

# ================== 页面选项 ==================
mode = st.sidebar.radio(
    "选择模式",
    ["📖 全部单词", "🎲 随机抽取10个", "📝 测验模式"]
)

# ================== 全部单词 ==================
if mode == "📖 全部单词":
    st.subheader("📖 全部单词")
    for w, m, p in words:
        st.write(f"**{w}** ({p}) ➡️ {m}")

# ================== 随机抽取 ==================
elif mode == "🎲 随机抽取10个":
    st.subheader("🎲 随机抽取 10 个单词")
    sample_words = random.sample(words, min(10, len(words)))
    for w, m, p in sample_words:
        st.write(f"**{w}** ({p}) ➡️ {m}")

# ================== 测验模式 ==================
elif mode == "📝 测验模式":
    st.subheader("📝 测验模式（输入释义）")
    if "quiz" not in st.session_state:
        st.session_state.quiz = random.sample(words, min(5, len(words)))
        st.session_state.answers = [""] * len(st.session_state.quiz)

    for i, (w, m, p) in enumerate(st.session_state.quiz):
        st.text_input(f"{i+1}. {w} ({p}) 的中文意思是？", key=f"answer_{i}")

    if st.button("提交答案"):
        correct = 0
        for i, (w, m, p) in enumerate(st.session_state.quiz):
            user_ans = st.session_state[f"answer_{i}"].strip()
            if user_ans == m:
                st.success(f"✅ {w} - {m}")
                correct += 1
            else:
                st.error(f"❌ {w} - 你的答案：{user_ans or '空'} | 正确答案：{m}")
        st.info(f"总分：{correct} / {len(st.session_state.quiz)}")
        # 清空 quiz，下次点按钮重新生成
        del st.session_state.quiz
