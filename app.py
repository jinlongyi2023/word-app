# -*- coding: utf-8 -*-
"""
TOPIK 背单词 · MVP （最终部署版）
- 修复：Google Vision OCR 默认凭证加载失败
- 实现：从环境变量读取 JSON 并动态写入 /tmp/service-account.json
"""

import os, json, io, base64, random, time
import streamlit as st
from supabase import create_client, Client
from streamlit_option_menu import option_menu
from textwrap import dedent
from streamlit_drawable_canvas import st_canvas
from google.cloud import vision
from google.oauth2 import service_account
from PIL import Image
import streamlit.components.v1 as components

# ========== 页面配置 ==========
st.set_page_config(page_title="TOPIK 背单词 · MVP", page_icon="📚", layout="wide")

# ========== 初始化 session ==========
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

# ========== 样式 ==========
st.markdown(dedent("""
    <style>
      .app-title {font-size: 40px; font-weight: 800; letter-spacing: .5px;}
      .muted {color:#9CA3AF; font-size:14px;}
      .card {background:#111827; border:1px solid #1F2937; border-radius:16px; padding:18px; margin:10px 0;}
      .btn-row button {border-radius:10px !important; height:42px;}
      .metric {font-size:13px; color:#9CA3AF; margin-bottom:6px;}
      .big {font-size:18px; font-weight:700;}
    </style>
"""), unsafe_allow_html=True)

# ========== Supabase ==========
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
SERVICE_ROLE_KEY = os.getenv("SERVICE_ROLE_KEY", "")
ADMIN_EMAILS = [e.strip().lower() for e in os.getenv("ADMIN_EMAILS", "").split(",") if e.strip()]

if not SUPABASE_URL or not SUPABASE_ANON_KEY:
    st.error("❌ 环境变量缺失：请设置 SUPABASE_URL 与 SUPABASE_ANON_KEY")
    st.stop()

sb: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

# ========== Google Vision OCR 初始化 ==========
CREDENTIALS_JSON = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON", "")
if not CREDENTIALS_JSON:
    st.error("❌ 未设置 GOOGLE_APPLICATION_CREDENTIALS_JSON 环境变量")
    st.stop()

# 将 JSON 写入临时文件并初始化凭证
try:
    cred_path = "/tmp/service-account.json"
    with open(cred_path, "w") as f:
        f.write(CREDENTIALS_JSON)
    credentials = service_account.Credentials.from_service_account_file(cred_path)
    vision_client = vision.ImageAnnotatorClient(credentials=credentials)
except Exception as e:
    st.error(f"⚠️ 初始化 Google Vision OCR 凭证失败：{e}")
    st.stop()

# ========== 登录/注册 ==========
def require_login_ui():
    tab_login, tab_signup = st.tabs(["登录", "注册"])
    with tab_login:
        email = st.text_input("邮箱", key="login_email")
        pw = st.text_input("密码", type="password", key="login_pw")
        if st.button("登录", use_container_width=True):
            try:
                res = sb.auth.sign_in_with_password({"email": email, "password": pw})
                if res and res.user:
                    st.session_state.user = res.user
                    st.success("登录成功！")
                    st.rerun()
                else:
                    st.error("登录失败，请检查邮箱或密码")
            except Exception as e:
                st.error(f"登录异常：{e}")

    with tab_signup:
        email2 = st.text_input("邮箱", key="signup_email")
        pw2 = st.text_input("密码", type="password", key="signup_pw")
        if st.button("注册", use_container_width=True):
            try:
                res = sb.auth.sign_up({"email": email2, "password": pw2})
                if res and res.user:
                    st.success("注册成功！请返回登录页登录")
                else:
                    st.error("注册失败，请稍后再试")
            except Exception as e:
                st.error(f"注册异常：{e}")

if st.session_state.user is None:
    require_login_ui()
    st.stop()

uid = st.session_state.user.id

# ========== 侧边栏菜单 ==========
with st.sidebar:
    choice = option_menu(
        "TOPIK 背单词 · MVP",
        ["单词列表", "闪卡", "测验", "我的进度", "管理员"],
        icons=["list-ul", "book", "pencil", "bar-chart", "shield-lock"],
        menu_icon="layers", default_index=0
    )

# ========== 分类与子类 ==========
cats = sb.table("categories").select("id, name").execute().data or []
if not cats:
    st.warning("请先在数据库 `categories` 添加目录数据。")
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

# ========== 手写测验 ==========
if choice == "测验":
    st.subheader("✏️ 手写测验（Google Vision OCR 自动判分）")
    rows = (
        sb.table("vocabularies")
        .select("id, word_kr, meaning_zh")
        .eq("category_id", cat_id)
        .eq("subcategory_id", sub_id)
        .execute()
        .data or []
    )

    if rows and not st.session_state.quiz_q:
        st.session_state.quiz_q = random.choice(rows)
    q = st.session_state.quiz_q

    if not rows:
        st.info("暂无单词数据。")
        st.stop()

    st.markdown(f"### 中文：{q['meaning_zh']}")
    st.caption("👇 请在下方手写韩文（iPad / 触屏设备均可）")

    canvas_result = st_canvas(
        fill_color="rgba(255,255,255,1)",
        stroke_width=3,
        stroke_color="#000000",
        background_color="#ffffff",
        height=200,
        width=400,
        drawing_mode="freedraw",
        key="canvas",
    )

    submit_col, change_col = st.columns(2)
    with submit_col:
        if st.button("提交", use_container_width=True):
            if canvas_result.image_data is not None:
                img = Image.fromarray((canvas_result.image_data).astype("uint8"))
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                buf.seek(0)
                image = vision.Image(content=buf.getvalue())

                try:
                    response = vision_client.text_detection(image=image)
                    texts = response.text_annotations
                    if texts:
                        infer_text = texts[0].description.strip().replace(" ", "")
                        st.info(f"🧾 识别结果：{infer_text}")
                        if infer_text == q["word_kr"].replace(" ", ""):
                            st.success("✅ 正确！")
                        else:
                            st.error(f"❌ 错误。正确答案：{q['word_kr']}")
                    else:
                        st.warning("未识别出文字，请重写。")
                except Exception as e:
                    st.error(f"OCR 识别异常：{e}")
            else:
                st.warning("请先手写后再提交。")

    with change_col:
        if st.button("换一题", use_container_width=True):
            st.session_state.quiz_q = random.choice(rows)
            if "canvas" in st.session_state:
                del st.session_state["canvas"]
            st.rerun()
