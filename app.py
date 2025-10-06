# -*- coding: utf-8 -*-
"""
TOPIK 背单词 · 融合版 (app12)
功能整合：
✅ 单词列表（朗读）
✅ 闪卡模式
✅ 测验（文本输入版）
✅ 手写测验（OCR识别）
✅ 学习进度
✅ 管理员功能
"""

import os, io, json, random, base64, time
import streamlit as st
from supabase import create_client, Client
from streamlit_option_menu import option_menu
from textwrap import dedent
from streamlit_drawable_canvas import st_canvas
from google.oauth2 import service_account
from google.cloud import vision
from PIL import Image
import streamlit.components.v1 as components

# ========== 页面配置 ==========
st.set_page_config(page_title="TOPIK 背单词 · 融合版", page_icon="📚", layout="wide")

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

# ========== Supabase 连接 ==========
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
ADMIN_EMAILS = [e.strip().lower() for e in os.getenv("ADMIN_EMAILS", "").split(",") if e.strip()]
sb: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

# ========== Google OCR 初始化 ==========
CREDENTIALS_JSON = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON", "")
if not CREDENTIALS_JSON:
    st.warning("⚠️ 尚未设置 GOOGLE_APPLICATION_CREDENTIALS_JSON 环境变量（OCR不可用）")
    vision_client = None
else:
    try:
        cred_path = "/tmp/service-account.json"
        with open(cred_path, "w") as f:
            f.write(CREDENTIALS_JSON)
        credentials = service_account.Credentials.from_service_account_file(cred_path)
        vision_client = vision.ImageAnnotatorClient(credentials=credentials)
    except Exception as e:
        st.error(f"OCR 初始化失败：{e}")
        vision_client = None

# ========== 登录 ==========
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

# ========== 侧边栏 ==========
with st.sidebar:
    choice = option_menu(
        "TOPIK 背单词 · 融合版",
        ["单词列表", "闪卡模式", "测验", "手写测验", "我的进度", "管理员"],
        icons=["list-ul", "cards", "pencil", "pen-tool", "bar-chart", "shield-lock"],
        menu_icon="layers", default_index=0
    )

# ========== 分类选择 ==========
cats = sb.table("categories").select("id,name").execute().data or []
if not cats:
    st.warning("数据库中暂无分类。请先添加。")
    st.stop()
cat_map = {c["name"]: c["id"] for c in cats}
cat_name = st.selectbox("选择目录", list(cat_map.keys()))
cat_id = cat_map[cat_name]

subs = sb.table("subcategories").select("id,name").eq("category_id", cat_id).execute().data or []
if not subs:
    st.warning("该目录下暂无子目录。")
    st.stop()
sub_map = {s["name"]: s["id"] for s in subs}
sub_name = st.selectbox("选择子目录", list(sub_map.keys()))
sub_id = sub_map[sub_name]
set_current(cat_id, cat_name, sub_id, sub_name)

# ===================== 功能区 =====================

# 1️⃣ 单词列表
if choice == "单词列表":
    st.subheader("📖 单词列表")
    rows = (
        sb.table("vocabularies")
        .select("id, word_kr, meaning_zh, pos, example_kr, example_zh")
        .eq("category_id", cat_id)
        .eq("subcategory_id", sub_id)
        .execute()
        .data or []
    )
    if not rows:
        st.info("暂无词汇数据，请检查分类或导入 CSV。")
    else:
        for r in rows:
            html_block = f"""
            <div style="margin-bottom:1.2rem; padding:0.6rem 0; border-bottom:1px solid #222;">
                <div style="display:flex; align-items:center; gap:8px;">
                    <span style="font-size:20px; font-weight:600; color:#ffb3c1;">{r['word_kr']}</span>
                    <button class='speak-btn' onclick='speakWord(`{r['word_kr']}`)'>🔊</button>
                    <span style="color:#ccc;">({r.get('pos','')}) - {r['meaning_zh']}</span>
                </div>
                <div style="margin-left:1.5rem; color:#aaa; font-size:15px;">{r.get('example_kr','')}</div>
                <div style="margin-left:1.5rem; color:#888; font-size:14px;">{r.get('example_zh','')}</div>
            </div>
            """
            components.html(html_block, height=120)
        components.html("""
            <script>
            function speakWord(word){
                const utter = new SpeechSynthesisUtterance(word);
                utter.lang = 'ko-KR';
                speechSynthesis.speak(utter);
            }
            </script>
        """, height=0)

# 2️⃣ 闪卡模式
elif choice == "闪卡模式":
    st.subheader("🎴 闪卡模式")
    rows = (
        sb.table("vocabularies")
        .select("id, word_kr, meaning_zh")
        .eq("category_id", cat_id).eq("subcategory_id", sub_id)
        .execute().data or []
    )
    if not rows:
        st.warning("暂无词汇数据。")
    else:
        if st.button("🎲 抽一张卡片", use_container_width=True):
            st.session_state.flash = random.choice(rows)
        card = st.session_state.flash
        if card:
            st.info(f"韩语：{card['word_kr']}")
            st.success(f"中文：{card['meaning_zh']}")
        else:
            st.info("点击上方按钮抽一张卡片~")

# 3️⃣ 文本测验
elif choice == "测验":
    st.subheader("✏️ 测验（文字输入）")
    rows = (
        sb.table("vocabularies")
        .select("id, word_kr, meaning_zh")
        .eq("category_id", cat_id).eq("subcategory_id", sub_id)
        .execute().data or []
    )
    if not rows:
        st.warning("暂无词汇。")
    else:
        if st.button("换一题", use_container_width=True):
            st.session_state.quiz_q = random.choice(rows)
        q = st.session_state.quiz_q or random.choice(rows)
        st.write(f"### 中文：{q['meaning_zh']}")
        answer = st.text_input("请输入韩语：")
        if st.button("提交答案"):
            if answer.strip() == q["word_kr"].strip():
                st.success("✅ 正确！")
            else:
                st.error(f"❌ 错误，正确答案是：{q['word_kr']}")

# 4️⃣ 手写测验（OCR）
elif choice == "手写测验":
    st.subheader("✍️ 手写测验（Google Vision OCR 自动判分）")
    if not vision_client:
        st.error("OCR 服务未初始化，请检查凭证。")
        st.stop()

    rows = (
        sb.table("vocabularies")
        .select("id, word_kr, meaning_zh")
        .eq("category_id", cat_id)
        .eq("subcategory_id", sub_id)
        .execute().data or []
    )
    if not rows:
        st.warning("暂无单词数据。")
        st.stop()

    if not st.session_state.quiz_q:
        st.session_state.quiz_q = random.choice(rows)
    q = st.session_state.quiz_q

    st.markdown(f"### 中文：{q['meaning_zh']}")
    st.caption("👇 请手写韩文（iPad/触控设备可用）")

    canvas_result = st_canvas(
        fill_color="rgba(255,255,255,1)",
        stroke_width=3,
        stroke_color="#000000",
        background_color="#ffffff",
        height=200, width=400,
        drawing_mode="freedraw", key="canvas",
    )

    col1, col2 = st.columns(2)
    with col1:
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
                st.warning("请先书写后再提交。")
    with col2:
        if st.button("换一题", use_container_width=True):
            st.session_state.quiz_q = random.choice(rows)
            if "canvas" in st.session_state:
                del st.session_state["canvas"]
            st.rerun()

# 5️⃣ 学习进度
elif choice == "我的进度":
    st.subheader("📊 我的学习进度")
    progress = (
        sb.table("user_progress")
        .select("last_page, updated_at")
        .eq("user_id", uid)
        .order("updated_at", desc=True)
        .limit(1)
        .execute().data
    )
    if progress:
        last = progress[0]
        st.success(f"上次学习位置：{last['last_page']}")
        st.caption(f"更新时间：{last['updated_at']}")
    else:
        st.info("暂无记录，请开始学习~")

# 6️⃣ 管理员
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
                    st.error("未找到该邮箱的用户")
            except Exception as e:
                st.error(f"操作失败：{e}")
    else:
        st.warning("你没有管理员权限。")
