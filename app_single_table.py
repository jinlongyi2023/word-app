
import os, random
import streamlit as st
from notion_client import Client
from notion_client.helpers import iterate_paginated_api

NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
DATABASE_ID  = os.environ.get("DATABASE_ID")

st.set_page_config(page_title="TOPIK 词库 · 单表简化版", page_icon="📚")
st.title("📚 TOPIK 词库（单表简化版）")

if not (NOTION_TOKEN and DATABASE_ID):
    st.error("请设置 NOTION_TOKEN 与 DATABASE_ID 环境变量。")
    st.stop()

notion = Client(auth=NOTION_TOKEN)

def get_text(prop):
    try:
        if prop.get("title"):
            return "".join([t.get("plain_text","") for t in prop["title"]])
        if prop.get("rich_text"):
            return "".join([t.get("plain_text","") for t in prop["rich_text"]])
    except Exception:
        pass
    return ""

def get_select_name(prop):
    try:
        sel = prop.get("select")
        return sel.get("name","") if sel else ""
    except Exception:
        return ""

@st.cache_data(ttl=60)
def load_options():
    db = notion.databases.retrieve(DATABASE_ID)
    props = db.get("properties", {})
    def pick(name, default):
        p = props.get(name, {})
        if p.get("type") == "select":
            return [o["name"] for o in p["select"]["options"]] or default
        return default
    src_types = pick("来源大类", ["必备","真题","高频","主题"])
    mapping = {
        "必备": ["初级","中级","高级"],
        "真题": ["听力","阅读"],
        "高频": ["动词","形容词","副词"],
        "主题": ["科技","生活","教育","环境","社会","文化"],
    }
    return src_types, mapping

def query_with_filter(filter_obj):
    results = []
    for page in iterate_paginated_api(notion.databases.query, database_id=DATABASE_ID, filter=filter_obj, page_size=100):
        results.append(page)
    return results

@st.cache_data(ttl=60)
def query_words(src_type=None, sub1=None, sub2=None):
    filters = []
    if src_type:
        filters.append({"property":"来源大类","select":{"equals":src_type}})
    if sub1:
        filters.append({"property":"子类1","select":{"equals":sub1}})
    if sub2:
        filters.append({"property":"子类2/分组","rich_text":{"contains": str(sub2)}})

    filter_obj = {"and": filters} if filters else None
    results = query_with_filter(filter_obj)
    data = []
    for r in results:
        p = r["properties"]
        w = get_text(p.get("单词", {}))
        m = get_text(p.get("中文释义", {}))
        pos = get_select_name(p.get("词性", {}))
        data.append((w,m,pos))
    return data

src_types, sub1_map = load_options()
src_type = st.sidebar.selectbox("来源大类", src_types, index=0)
sub1 = st.sidebar.selectbox("子类1", sub1_map.get(src_type, []))
sub2 = st.sidebar.text_input("子类2/分组（必备: Unit；真题: 届次，可留空）")
mode = st.sidebar.radio("模式", ["全部单词","闪卡","随机10个","测试"], index=0)

with st.spinner("读取中..."):
    data = query_words(src_type, sub1, sub2 if sub2 else None)

st.caption(f"筛选：{src_type} / {sub1}" + (f" / {sub2}" if sub2 else ""))

def show_list(items):
    for w,m,pos in items:
        st.write(f"**{w}** ({pos or '—'}) → {m or '（无释义）'}")

def show_flash(items):
    for i,(w,m,pos) in enumerate(items,1):
        with st.expander(f"{i}. {w} ({pos or '—'})"):
            st.write(m or "（无释义）")

def show_quiz(items):
    qs = items[:min(10,len(items))]
    answers = []
    for i,(w,m,pos) in enumerate(qs,1):
        answers.append(st.text_input(f"{i}. {w} 的中文释义：", key=f"q{i}").strip())
    if st.button("提交"):
        score = 0
        for (w,m,_),a in zip(qs,answers):
            if a == (m or ""):
                st.success(f"✅ {w}")
                score += 1
            else:
                st.error(f"❌ {w} | 正确：{m or '（无）'}")
        st.info(f"分数：{score}/{len(qs)}")

if not data:
    st.warning("无数据，请检查筛选条件与 Notion 字段。")
else:
    if mode == "全部单词":
        show_list(data)
    elif mode == "闪卡":
        show_flash(data)
    elif mode == "随机10个":
        show_list(random.sample(data, min(10, len(data))))
    else:
        show_quiz(data)
