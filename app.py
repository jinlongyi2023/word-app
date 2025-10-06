# -*- coding: utf-8 -*-
"""
TOPIK 背单词 · MVP
功能：
- 登录注册（Supabase）
- 分类选择（categories / subcategories）
- 单词展示 + 浏览器朗读功能（韩语）
- 闪卡模式
- 简单测验
- 学习进度
- 管理员开通会员
"""

import os
import random
import streamlit as st
from supabase import create_client, Client
from streamlit_option_menu import option_menu
from textwrap import dedent
import streamlit.components.v1 as components

# -------- 页面配置 --------
st.set_page_config(page_title="TOPIK 背单词 · MVP", page_icon="📚", layout="wide")

# -------- 初始化 session --------
if "current" not in st.session_state:
    st.session_state.current = {"cat_id": None, "sub_id": None, "cat_name": "", "sub_name": ""}
if "user" not in st.session_state:
    st.session_state.user = None
if "flash" not in st.session_state:
    st.session_state.flash = None
if "quiz_q" not in st.session_state:
    st.session_state.quiz_q = None

def set_current(cat_id=None, cat_name=None, sub_id=None, sub_name=None):
    cur = st.session_state.current
    if cat_id is not None:
        cur["cat_id"] = cat_id
    if cat_name is not None:
        cur["cat_name"] = cat_name
    if sub_id is not None:
        cur["sub_id"] = sub_id
    if sub_name is not None:
        cur["sub_name"] = sub_name

# -------- 样式 --------
st.markdown(
    dedent("""
    <style>
      .app-title {font-size: 40px; font-weight: 800; letter-spacing: .5px;}
      .muted {color:#9CA3AF; font-size:14px;}
      .card {background:#111827; border:1px solid #1F2937; border-radius:16px; padding:18px; margin:10px 0;}
      .btn-row button {border-radius:10px !important; height:42px;}
      .metric {font-size:13px; color:#9CA3AF; margin-bottom:6px;}
      .big {font-size:18px; font-weight:700;}
      .col-right {padding-left:10px; padding-right:10px;}
    </style>
    """),
    unsafe_allow_html=True
)

# -------- Supabase 连接 --------
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
SERVICE_ROLE_KEY = os.getenv("SERVICE_ROLE_KEY", "")
ADMIN_EMAILS = [e.strip().lower() for e in os.getenv("ADMIN_EMAILS", "").split(",") if e.strip()]

if not SUPABASE_URL or not SUPABASE_ANON_KEY:
    st.error("环境变量缺失：请在部署平台设置 SUPABASE_URL 与 SUPABASE_ANON_KEY。")
    st.stop()

sb: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

# -------- 登录 / 注册 --------
def require_login_ui():
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
                    st.rerun()
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

if st.session_state.user is None:
    require_login_ui()
    st.stop()

uid = st.session_state.user.id

# -------- 侧边栏菜单 --------
with st.sidebar:
    st.image("https://static-typical-placeholder/logo.png", width=120)
    choice = option_menu(
        "TOPIK 背单词 · MVP",
        ["单词列表", "闪卡", "测验", "我的进度", "管理员"],
        icons=["list-ul","book","pencil","bar-chart","shield-lock"],
        menu_icon="layers", default_index=0
    )

# -------- 分类与子类 --------
cats = sb.table("categories").select("id, name").execute().data or []
if not cats:
    st.warning("还没有任何目录。请在数据库 `categories` 中先添加。")
    st.stop()

cat_map = {c["name"]: c["id"] for c in cats}
cat_name = st.selectbox("选择目录", list(cat_map.keys()))
cat_id = cat_map[cat_name]

subs = sb.table("subcategories").select("id, name").eq("category_id", cat_id).execute().data or []
if not subs:
    st.warning("该目录下暂无子目录。")
    st.stop()

sub_map = {s["name"]: s["id"] for s in subs}
sub_name = st.selectbox("选择子目录", list(sub_map.keys()))
sub_id = sub_map[sub_name]

set_current(cat_id, cat_name, sub_id, sub_name)

st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown('<div class="metric">当前目录</div>', unsafe_allow_html=True)
st.markdown(f'<div class="big">{cat_name} / {sub_name}</div>', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

# ====================== 功能页 ======================

# 1) 单词列表（带朗读功能）
if choice == "单词列表":
    st.subheader("📖 单词列表")
    limit = st.slider("每次加载数量", 10, 100, 30)
    rows = (
        sb.table("vocabularies")
        .select("id, word_kr, meaning_zh, pos, example_kr, example_zh")
        .eq("category_id", cat_id).eq("subcategory_id", sub_id)
        .limit(limit).execute().data or []
    )

    for r in rows:
        word_kr = r["word_kr"]
        pos = r.get("pos") or ""
        meaning_zh = r.get("meaning_zh") or ""
        example_kr = r.get("example_kr") or ""
        example_zh = r.get("example_zh") or ""

        # 构建例句朗读按钮
        example_button = ""
        if example_kr:
            example_button = f"""
            <button class='speak-btn' onclick='speakWord(`{example_kr}`)'>🔊</button>
            """

        html_block = f"""
        <div style="margin-bottom:1.2rem; padding:0.6rem 0; border-bottom:1px solid #222;">
            <div style="display:flex; align-items:center; gap:8px;">
                <span style="font-size:20px; font-weight:600;">{word_kr}</span>
                <button class='speak-btn' onclick='speakWord(`{word_kr}`)'>🔊</button>
                <span style="color:#ccc;">({pos}) - {meaning_zh}</span>
            </div>
            <div style="margin-left:1.5rem; color:#aaa; font-size:15px; display:flex; align-items:center; gap:6px;">
                <span>{example_kr}</span>
                {example_button}
            </div>
            <div style="margin-left:1.5rem; color:#888; font-size:14px;">{example_zh}</div>
        </div>

        <style>
        .speak-btn {{
            background:none;
            border:none;
            cursor:pointer;
            font-size:18px;
            transition:all 0.2s ease;
            color:#ccc;
        }}
        .speak-btn:hover {{
            color:#ff6b9d;
            text-shadow:0 0 6px #ff99bb;
            transform:scale(1.1);
        }}
        </style>

        <script>
        function speakWord(text) {{
            const utter = new SpeechSynthesisUtterance(text);
            utter.lang = 'ko-KR';
            speechSynthesis.speak(utter);
        }}
        </script>
        """  # 结束多行字符串

        components.html(html_block, height=130)

# 2) 闪卡模式
elif choice == "闪卡":
    st.subheader("🎴 闪卡模式")
    rows = (
        sb.table("vocabularies")
        .select("id, word_kr, meaning_zh")
        .eq("category_id", cat_id).eq("subcategory_id", sub_id)
        .execute().data or []
    )

    col1, col2 = st.columns([2, 1])
    with col1:
        if st.button("🎲 抽一张卡片", use_container_width=True, type="primary"):
            st.session_state.flash = random.choice(rows) if rows else None

        card = st.session_state.flash
        if card:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.info(f"韩语：{card['word_kr']}")
            st.success(f"中文：{card['meaning_zh']}")
            st.markdown('</div>', unsafe_allow_html=True)
        elif not rows:
            st.write("暂无单词")
        else:
            st.write("点击上方按钮抽一张卡片～")

    with col2:
        st.markdown('<div class="card col-right">', unsafe_allow_html=True)
        st.markdown("⭐ 提示：点击 **抽一张卡片**，会显示中韩释义。")
        st.markdown("💡 建议：抽到的词可以在右上角加收藏（后续可做『错词本/收藏夹』）。")
        st.markdown('</div>', unsafe_allow_html=True)

# 3) 简单测验
elif choice == "测验":
    st.subheader("✏️ 简单测验")
    rows = (
        sb.table("vocabularies")
        .select("id, word_kr, meaning_zh")
        .eq("category_id", cat_id).eq("subcategory_id", sub_id)
        .execute().data or []
    )

    if rows and not st.session_state.quiz_q:
        st.session_state.quiz_q = random.choice(rows)

    q = st.session_state.quiz_q
    if not rows:
        st.write("暂无单词")
    elif not q:
        st.info("点击『换一题』开始练习～")
    else:
        ans = st.text_input(f"韩语：{q['word_kr']} 的中文意思是？", key="quiz_ans")
        submit_col, change_col = st.columns(2)
        with submit_col:
            if st.button("提交", use_container_width=True):
                if ans.strip() == q['meaning_zh'].strip():
                    st.success("答对了！")
                else:
                    st.error(f"答错了，正确答案：{q['meaning_zh']}")
        with change_col:
            if st.button("换一题", use_container_width=True):
                st.session_state.quiz_q = random.choice(rows)
                st.session_state.quiz_ans = ""
                st.rerun()

# 4) 我的进度
elif choice == "我的进度":
    st.subheader("📊 我的进度")
    progress = (
        sb.table("user_progress")
        .select("status, count:count()")
        .eq("user_id", uid).execute().data or []
    )
    if progress:
        for p in progress:
            st.write(f"{p['status']}：{p['count']} 个")
    else:
        st.info("还没有进度数据")

# 5) 管理员开通会员
elif choice == "管理员":
    st.subheader("🛠 管理员 - 手动开通会员")
    if st.session_state.user.email.lower() in ADMIN_EMAILS:
        target_email = st.text_input("输入要开通的用户邮箱")
        if st.button("✅ 开通会员", use_container_width=True):
            try:
                res = sb.auth.admin.get_user_by_email(target_email)
                if res and res.user:
                    sb.table("memberships").upsert({
                        "user_id": res.user.id,
                        "is_active": True,
                        "plan": "manual",
                        "granted_by": st.session_state.user.email
                    }).execute()
                    st.success(f"{target_email} 已开通会员")
                else:
                    st.error("未找到该邮箱的用户，请确认已注册")
            except Exception as e:
                st.error(f"操作失败：{e}")
    else:
        st.warning("你没有管理员权限")
