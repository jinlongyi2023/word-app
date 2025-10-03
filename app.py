import os
import random
import streamlit as st
from supabase import create_client, Client
from streamlit_option_menu import option_menu
from textwrap import dedent

# -------- 基础设置 --------
st.set_page_config(page_title="TOPIK 背单词 · MVP", page_icon="📚", layout="wide")

# 初始化 session_state
if "current" not in st.session_state:
    st.session_state.current = {
        "cat_id": None, "sub_id": None,
        "cat_name": "", "sub_name": ""
    }
if "user" not in st.session_state:
    st.session_state.user = None

def set_current(cat_id=None, cat_name=None, sub_id=None, sub_name=None):
    cur = st.session_state.current
    if cat_id is not None:  cur["cat_id"] = cat_id
    if cat_name is not None: cur["cat_name"] = cat_name
    if sub_id is not None:  cur["sub_id"] = sub_id
    if sub_name is not None: cur["sub_name"] = sub_name

# -------- 样式 --------
st.markdown(
    dedent("""
    <style>
      .app-title {font-size: 40px; font-weight: 800; letter-spacing: .5px;}
      .muted {color:#9CA3AF;font-size:14px}
      .card {background:#111827; border:1px solid #1F2937; border-radius:16px; padding:18px; margin:10px 0;}
      .btn-row button {border-radius:10px !important; height:42px;}
      .metric {font-size:13px;color:#9CA3AF;margin-bottom:6px}
      .big {font-size:18px;font-weight:700}
    </style>
    """),
    unsafe_allow_html=True
)

# -------- Supabase --------
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
SERVICE_ROLE_KEY = os.getenv("SERVICE_ROLE_KEY", "")
ADMIN_EMAILS = [e.strip().lower() for e in os.getenv("ADMIN_EMAILS", "").split(",") if e.strip()]

if not SUPABASE_URL or not SUPABASE_ANON_KEY:
    st.error("环境变量缺失：请在部署平台设置 SUPABASE_URL 与 SUPABASE_ANON_KEY。")
    st.stop()

sb: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

# -------- 登录模块 --------
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
    st.image("https://static-typical-placeholder/logo.png", width=120)  # 替换为你自己的logo
    choice = option_menu(
        "TOPIK 背单词 · MVP",
        ["单词列表", "闪卡", "测验", "我的进度", "管理员"],
        icons=["list-ul","book","pencil","bar-chart","shield-lock"],
        menu_icon="layers", default_index=0
    )

# -------- 数据：目录和子目录 --------
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

# -------- 功能页 --------
if choice == "单词列表":
    with st.container():
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("📖 单词列表")
    limit = st.slider("每次加载数量", 10, 100, 30)
    for r in rows:
        st.markdown(f"**{r['word_kr']}** ({r.get('pos','')}) - {r['meaning_zh']}")
    st.markdown('</div>', unsafe_allow_html=True)

elif choice == "闪卡":
    st.subheader("🎴 闪卡模式")
    rows = sb.table("vocabularies").select("id, word_kr, meaning_zh")\
        .eq("category_id", cat_id).eq("subcategory_id", sub_id).execute().data or []
    if rows:
        card = random.choice(rows)
        if st.button("抽一张卡片"):
            st.session_state.flash = card
        if "flash" in st.session_state:
            st.info(f"韩语：{st.session_state.flash['word_kr']}")
            st.success(f"中文：{st.session_state.flash['meaning_zh']}")
    else:
        st.write("暂无单词")

elif choice == "测验":
    st.subheader("✏️ 简单测验")
    rows = sb.table("vocabularies").select("id, word_kr, meaning_zh")\
        .eq("category_id", cat_id).eq("subcategory_id", sub_id).execute().data or []
    if rows:
        q = random.choice(rows)
        ans = st.text_input(f"韩语：{q['word_kr']} 的中文意思是？")
        if st.button("提交"):
            if ans.strip() == q['meaning_zh']:
                st.success("答对了！")
            else:
                st.error(f"答错了，正确答案：{q['meaning_zh']}")
    else:
        st.write("暂无单词")

elif choice == "我的进度":
    st.subheader("📊 我的进度")
    progress = sb.table("user_progress").select("status, count:count()").eq("user_id", uid).execute().data or []
    if progress:
        for p in progress:
            st.write(f"{p['status']}：{p['count']} 个")
    else:
        st.info("还没有进度数据")

elif choice == "管理员":
    st.subheader("🛠 管理员 - 手动开通会员")
    if st.session_state.user.email.lower() in ADMIN_EMAILS:
        target_email = st.text_input("输入要开通的用户邮箱")
        if st.button("✅ 开通会员"):
            try:
                # 查用户
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
