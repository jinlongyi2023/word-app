# app.py — TOPIK 背单词 · MVP 最终版
# 说明：
# 1) 支持注册/登录（Supabase Auth）
# 2) 目录→子目录→单词列表
# 3) 闪卡（翻牌）
# 4) 简单测验（单选）
# 5) 进度：已掌握 / 错词本
# 6) 会员：手动在 memberships 表开通后可访问全部；未开通也能体验公共词库
# 7) 去重策略：学一个词 → “全库同名词”一起标记进度（不改数据库结构）

import os
import random
import streamlit as st
from supabase import create_client, Client

# -------- 基础设置 --------
st.set_page_config(page_title="TOPIK 背单词 · MVP", page_icon="📚", layout="centered")

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")

if not SUPABASE_URL or not SUPABASE_ANON_KEY:
    st.error("环境变量缺失：请在部署平台设置 SUPABASE_URL 与 SUPABASE_ANON_KEY。")
    st.stop()

sb: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

# -------- 小工具函数 --------
def get_session_user():
    """从 session_state 取已登录用户。"""
    if "user" not in st.session_state:
        st.session_state.user = None
    return st.session_state.user

def require_login_ui():
    """登录/注册 UI。未登录时调用。"""
    tab_login, tab_signup = st.tabs(["登录", "注册"])

    with tab_login:
        email = st.text_input("邮箱", key="login_email")
        pw = st.text_input("密码", type="password", key="login_pw")
        if st.button("登录", type="primary", use_container_width=True):
            try:
                res = sb.auth.sign_in_with_password({"email": email, "password": pw})
                if res and res.user:
                    st.session_state.user = res.user
                    st.success("登录成功")
                    st.experimental_rerun()
                else:
                    st.error("登录失败，请检查邮箱/密码")
            except Exception as e:
                st.error(f"登录异常：{e}")

    with tab_signup:
        email2 = st.text_input("邮箱", key="signup_email")
        pw2 = st.text_input("密码", type="password", key="signup_pw")
        if st.button("注册", use_container_width=True):
            try:
                res = sb.auth.sign_up({"email": email2, "password": pw2})
                if res and res.user:
                    st.success("注册成功，请回到登录页登录")
                else:
                    st.error("注册失败，请稍后再试")
            except Exception as e:
                st.error(f"注册异常：{e}")

def mark_progress_for_all(word_kr: str, status: str, uid: str):
    """
    最简单的去重进度：按“韩文词拼写”在全库匹配，统一标记（known / wrong）。
    如果以后要更严格，可同时匹配词性 .eq("pos", 某值)。
    """
    try:
        q = sb.table("vocabularies").select("id, word_kr").eq("word_kr", word_kr).execute()
        all_same = q.data or []
        if not all_same:
            return
        for row in all_same:
            sb.table("user_progress").upsert({
                "user_id": uid,
                "vocab_id": row["id"],
                "status": status
            }).execute()
    except Exception as e:
        st.error(f"写入学习进度失败：{e}")

# -------- 顶栏 --------
col1, col2 = st.columns([1, 1])
with col1:
    st.title("📚 TOPIK 背单词 · MVP")
with col2:
    if get_session_user() and st.button("退出登录", use_container_width=True):
        st.session_state.user = None
        sb.auth.sign_out()
        st.experimental_rerun()

# -------- 登录态处理 --------
if get_session_user() is None:
    require_login_ui()
    st.stop()

uid = st.session_state.user.id

# -------- 会员状态 --------
try:
    mem = (
        sb.table("memberships")
        .select("is_active")
        .eq("user_id", uid)
        .maybe_single()
        .execute()
        .data
    )
    is_member = bool(mem and mem.get("is_active"))
except Exception:
    is_member = False

if not is_member:
    st.info("当前为非会员：可体验公共词库。购买会员后联系管理员开通权限。")

# -------- 目录 / 子目录选择 --------
try:
    cats = sb.table("categories").select("id, name").execute().data or []
except Exception as e:
    st.error(f"加载目录失败：{e}")
    st.stop()

if not cats:
    st.warning("还没有任何目录。请在数据库 `categories` 中先添加。")
    st.stop()

cat_map = {c["name"]: c["id"] for c in cats}
cat_name = st.selectbox("选择目录", list(cat_map.keys()))
cat_id = cat_map[cat_name]

try:
    subs = (
        sb.table("subcategories")
        .select("id, name")
        .eq("category_id", cat_id)
        .order("order_no")
        .execute()
        .data
        or []
    )
except Exception as e:
    st.error(f"加载子目录失败：{e}")
    st.stop()

if not subs:
    st.warning("该目录下暂无子目录。请在 `subcategories` 中添加（如 听力/阅读、Unit1~20）。")
    st.stop()

sub_map = {s["name"]: s["id"] for s in subs}
sub_name = st.selectbox("选择子目录", list(sub_map.keys()))
sub_id = sub_map[sub_name]

# -------- 取词汇 --------
limit = st.slider("每次加载数量", 10, 100, 30)
try:
    rows = (
        sb.table("vocabularies")
        .select("id, word_kr, meaning_zh, pos, example_kr, example_zh")
        .eq("category_id", cat_id)
        .eq("subcategory_id", sub_id)
        .limit(limit)
        .execute()
        .data
        or []
    )
except Exception as e:
    st.error(f"加载词汇失败：{e}")
    rows = []

# -------- UI：列表 / 闪卡 / 测验 / 进度 --------
T1, T2, T3, T4 = st.tabs(["单词列表", "闪卡", "测验", "我的进度"])

with T1:
    if not rows:
        st.warning("该子目录暂无词汇。")
    else:
        for r in rows:
            st.markdown(f"**{r['word_kr']}** · {r.get('pos','')}  \n{r['meaning_zh']}")
            with st.expander("例句"):
                st.write(r.get("example_kr") or "—")
                st.write(r.get("example_zh") or "—")
            c1, c2 = st.columns(2)
            if c1.button("已掌握", key=f"k_{r['id']}"):
                mark_progress_for_all(r["word_kr"], "known", uid)
                st.toast("已标记为已掌握（全库同名词同步）")
            if c2.button("加入错词本", key=f"w_{r['id']}"):
                mark_progress_for_all(r["word_kr"], "wrong", uid)
                st.toast("已加入错词本（全库同名词同步）")

with T2:
    if "fc_idx" not in st.session_state:
        st.session_state.fc_idx = 0
        st.session_state.fc_show_meaning = False
    if not rows:
        st.warning("该子目录暂无词汇。")
    else:
        r = rows[st.session_state.fc_idx % len(rows)]
        st.subheader(r["word_kr"])
        if st.button("翻牌 / 显示释义"):
            st.session_state.fc_show_meaning = not st.session_state.fc_show_meaning
        if st.session_state.fc_show_meaning:
            st.markdown(f"**{r['meaning_zh']}** · {r.get('pos','')}")
            with st.expander("例句"):
                st.write(r.get("example_kr") or "—")
                st.write(r.get("example_zh") or "—")
        c1, c2, c3 = st.columns(3)
        if c1.button("上一张"):
            st.session_state.fc_idx = (st.session_state.fc_idx - 1) % len(rows)
            st.session_state.fc_show_meaning = False
        if c2.button("已掌握（全库）"):
            mark_progress_for_all(r["word_kr"], "known", uid)
            st.toast("这张卡片已标记为已掌握")
        if c3.button("下一张"):
            st.session_state.fc_idx = (st.session_state.fc_idx + 1) % len(rows)
            st.session_state.fc_show_meaning = False

with T3:
    if len(rows) < 4:
        st.info("题库不足 4 条，无法出题。请增加词汇或提高加载数量。")
    else:
        q = random.choice(rows)
        options = {q["meaning_zh"]}
        while len(options) < 4:
            options.add(random.choice(rows)["meaning_zh"])
        options = list(options)
        random.shuffle(options)

        st.write(f"**题目**：`{q['word_kr']}` 的中文意思是？")
        ans = st.radio("选择一个答案", options, index=0)
        if st.button("提交答案", type="primary"):
            if ans == q["meaning_zh"]:
                st.success("答对啦！")
                mark_progress_for_all(q["word_kr"], "known", uid)
            else:
                st.error(f"答错了，正确答案：{q['meaning_zh']}")
                mark_progress_for_all(q["word_kr"], "wrong", uid)

with T4:
    try:
        k = (
            sb.table("user_progress")
            .select("vocab_id")
            .eq("user_id", uid)
            .eq("status", "known")
            .execute()
            .data
            or []
        )
        w = (
            sb.table("user_progress")
            .select("vocab_id")
            .eq("user_id", uid)
            .eq("status", "wrong")
            .execute()
            .data
            or []
        )
        st.write(f"✅ 已掌握：{len(k)}  |  ❗ 错词：{len(w)}")
    except Exception as e:
        st.error(f"读取进度失败：{e}")
