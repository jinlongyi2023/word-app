# -*- coding: utf-8 -*-
"""
TOPIK 背单词 · 卡片柔和风格版（Final UI）
包含：
✅ 单词列表（美化卡片布局 + 朗读）
✅ 手写测验（Google OCR）
✅ 我的进度 / 管理员
"""

import os, io, json, random
import streamlit as st
from supabase import create_client
from streamlit_option_menu import option_menu
from streamlit_drawable_canvas import st_canvas
from google.oauth2 import service_account
from google.cloud import vision
from PIL import Image
import streamlit.components.v1 as components

# 页面配置
st.set_page_config(page_title="TOPIK 背单词 · 柔和卡片版", page_icon="💡", layout="wide")

# 样式表（重点：卡片美化）
st.markdown("""
<style>
body, .block-container { background-color: #0F172A; color: white; }
.stApp { background-color: #0F172A; }

.word-card {
  background: linear-gradient(145deg, #1E293B, #0F172A);
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 18px;
  padding: 18px 22px;
  margin-bottom: 18px;
  box-shadow: 0 3px 10px rgba(0,0,0,0.35);
  transition: transform .25s ease, box-shadow .25s ease;
  animation: fadeIn .6s ease forwards;
  opacity: 0;
}
.word-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 5px 18px rgba(255,255,255,0.12);
}
@keyframes fadeIn { to {opacity:1;} }

.word-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}
.word-kr {
  font-size: 26px;
  font-weight: 700;
  color: #FF9AA2;
}
.word-kr:hover { text-shadow: 0 0 10px rgba(255,160,180,.4); }

.word-meta {
  color: #A0AEC0;
  font-size: 14px;
  margin-bottom: 4px;
}
.word-mean {
  color: #F8F8F8;
  font-size: 16px;
  font-weight: 500;
}

.ex-kr {
  color: #E5E7EB;
  font-size: 16px;
  margin-top: 10px;
  display: flex;
  align-items: center;
  gap: 8px;
}
.ex-zh {
  color: #94A3B8;
  font-size: 14px;
  margin-left: 28px;
}

.speak-btn {
  width: 22px; height: 22px;
  background: url("data:image/svg+xml;utf8,\
<svg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 24 24'>\
<path d='M4 10h3l4-3v10l-4-3H4z' stroke='white' stroke-opacity='.85' stroke-width='1.5'/>\
<path d='M15 9c1 .8 1 3.2 0 4' stroke='white' stroke-opacity='.8' stroke-width='1.5' stroke-linecap='round'/>\
<path d='M17.5 7.5c2 1.7 2 6.3 0 8' stroke='white' stroke-opacity='.6' stroke-width='1.5' stroke-linecap='round'/>\
</svg>") no-repeat center/contain;
  opacity: .8; cursor: pointer; border: none;
  transition: transform .18s ease, opacity .18s ease;
  background-color: transparent;
}
.speak-btn:hover { opacity: 1; transform: scale(1.15); }
</style>
""", unsafe_allow_html=True)

# Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
ADMIN_EMAILS = [e.strip().lower() for e in os.getenv("ADMIN_EMAILS", "").split(",") if e.strip()]
sb = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

# Google Vision
vision_client = None
if os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON"):
    cred_path = "/tmp/service-account.json"
    with open(cred_path, "w") as f:
        f.write(os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON"))
    credentials = service_account.Credentials.from_service_account_file(cred_path)
    vision_client = vision.ImageAnnotatorClient(credentials=credentials)

# 登录逻辑
if "user" not in st.session_state:
    st.session_state.user = None
if "quiz_q" not in st.session_state:
    st.session_state.quiz_q = None

def login_ui():
    tab1, tab2 = st.tabs(["登录", "注册"])
    with tab1:
        email = st.text_input("邮箱", key="login_email")
        pw = st.text_input("密码", type="password", key="login_pw")
        if st.button("登录", use_container_width=True):
            try:
                res = sb.auth.sign_in_with_password({"email": email, "password": pw})
                if res and res.user:
                    st.session_state.user = res.user
                    st.rerun()
                else:
                    st.error("登录失败。")
            except Exception as e:
                st.error(str(e))
    with tab2:
        email2 = st.text_input("邮箱", key="signup_email")
        pw2 = st.text_input("密码", type="password", key="signup_pw")
        if st.button("注册", use_container_width=True):
            try:
                sb.auth.sign_up({"email": email2, "password": pw2})
                st.success("注册成功，请登录。")
            except Exception as e:
                st.error(str(e))

if st.session_state.user is None:
    login_ui()
    st.stop()

uid = st.session_state.user.id

# 侧边栏菜单
with st.sidebar:
    choice = option_menu(
        "TOPIK 背单词 · 柔和卡片版",
        ["单词列表", "手写测验", "我的进度", "管理员"],
        icons=["list-ul", "pen-tool", "bar-chart", "shield-lock"],
        menu_icon="layers", default_index=0
    )

# 分类选择
cats = sb.table("categories").select("id,name").execute().data or []
cat_map = {c["name"]: c["id"] for c in cats}
cat_name = st.selectbox("选择目录", list(cat_map.keys()))
subs = sb.table("subcategories").select("id,name").eq("category_id", cat_map[cat_name]).execute().data or []
sub_map = {s["name"]: s["id"] for s in subs}
sub_name = st.selectbox("选择子目录", list(sub_map.keys()))

cat_id, sub_id = cat_map[cat_name], sub_map[sub_name]

# 功能1：单词列表
if choice == "单词列表":
    st.subheader("📖 单词列表")
    rows = (
        sb.table("vocabularies")
        .select("word_kr, meaning_zh, pos, example_kr, example_zh")
        .eq("category_id", cat_id).eq("subcategory_id", sub_id)
        .execute().data or []
    )

    if not rows:
        st.warning("暂无单词。")
    else:
        js = """
        <script>
        function speakKo(text){
            const u = new SpeechSynthesisUtterance(text);
            u.lang='ko-KR'; u.rate=0.95;
            window.speechSynthesis.cancel();
            window.speechSynthesis.speak(u);
        }
        </script>
        """
        html = js + "<div>"
        for r in rows:
            word = (r['word_kr'] or '').replace("'", "\\'")
            mean = r.get("meaning_zh", "")
            pos = r.get("pos", "")
            ex_kr = (r.get("example_kr") or "").replace("'", "\\'")
            ex_zh = r.get("example_zh") or ""
            html += f"""
            <div class='word-card'>
                <div class='word-head'>
                    <span class='word-kr' onclick="speakKo('{word}')">{word}</span>
                    <button class='speak-btn' onclick="speakKo('{word}')"></button>
                </div>
                <div class='word-meta'>{pos}</div>
                <div class='word-mean'>{mean}</div>
                <div class='ex-kr'>{ex_kr}
                    {"<button class='speak-btn' onclick=\"speakKo('"+ex_kr+"')\"></button>" if ex_kr else ""}
                </div>
                <div class='ex-zh'>{ex_zh}</div>
            </div>
            """
        html += "</div>"
        components.html(html, height=900, scrolling=True)

# 功能2：手写测验
elif choice == "手写测验":
    st.subheader("✍️ 手写测验")
    if not vision_client:
        st.error("OCR 初始化失败。")
        st.stop()

    rows = sb.table("vocabularies").select("word_kr, meaning_zh").eq("category_id", cat_id).eq("subcategory_id", sub_id).execute().data or []
    if not rows:
        st.warning("暂无单词。")
        st.stop()

    if not st.session_state.quiz_q:
        st.session_state.quiz_q = random.choice(rows)
    q = st.session_state.quiz_q

    st.markdown(f"### 中文：{q['meaning_zh']}")
    st.caption("👇 请在下方手写韩文字（触控设备支持）")

    canvas = st_canvas(
        fill_color="rgba(255,255,255,1)",
        stroke_width=3,
        stroke_color="#000",
        background_color="#fff",
        height=220,
        width=420,
        drawing_mode="freedraw",
        key="canvas"
    )

    c1, c2 = st.columns(2)
    with c1:
        if st.button("提交", use_container_width=True):
            if canvas.image_data is None:
                st.warning("请先书写。")
            else:
                img = Image.fromarray((canvas.image_data).astype("uint8"))
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                image = vision.Image(content=buf.getvalue())
                res = vision_client.text_detection(image=image)
                texts = res.text_annotations
                if texts:
                    infer = texts[0].description.strip().replace(" ", "")
                    st.info(f"🧾 识别结果：{infer}")
                    if infer == q["word_kr"].replace(" ", ""):
                        st.success("✅ 正确！")
                    else:
                        st.error(f"❌ 正确答案：{q['word_kr']}")
                else:
                    st.warning("未识别文字。")
    with c2:
        if st.button("换一题", use_container_width=True):
            st.session_state.quiz_q = random.choice(rows)
            st.rerun()

# 功能3：我的进度
elif choice == "我的进度":
    st.subheader("📊 学习进度")
    st.info("功能开发中（计划接入学习统计图）")

# 功能4：管理员
elif choice == "管理员":
    st.subheader("🛠 管理员工具")
    st.info("管理员功能保留")
