# -*- coding: utf-8 -*-
"""
TOPIK 背单词 · 融合版（最终部署）
保留功能：
  ✅ 单词列表（点击单词或小喇叭朗读；优雅小动画，暗色主题）
  ✅ 手写测验（Google Vision OCR 自动判分）
  ✅ 我的进度
  ✅ 管理员（保留基础操作）
移除：
  ❌ 普通测验、闪卡模式
环境变量（Railway → Variables）：
  - SUPABASE_URL
  - SUPABASE_ANON_KEY
  - SERVICE_ROLE_KEY（可选）
  - ADMIN_EMAILS（逗号分隔）
  - GOOGLE_APPLICATION_CREDENTIALS_JSON（粘贴整个 service-account.json 内容）
"""

import os, io, json, random
import streamlit as st
from textwrap import dedent
from supabase import create_client, Client
from streamlit_option_menu import option_menu
from streamlit_drawable_canvas import st_canvas
from google.oauth2 import service_account
from google.cloud import vision
from PIL import Image
import streamlit.components.v1 as components

# ------------------------ 页面布局 ------------------------
st.set_page_config(page_title="TOPIK 背单词 · 融合版", page_icon="📚", layout="wide")

# ------------------------ Session 初始化 ------------------------
if "current" not in st.session_state:
    st.session_state.current = {"cat_id": None, "sub_id": None, "cat_name": "", "sub_name": ""}
if "user" not in st.session_state:
    st.session_state.user = None
if "quiz_q" not in st.session_state:
    st.session_state.quiz_q = None

def set_current(cat_id=None, cat_name=None, sub_id=None, sub_name=None):
    cur = st.session_state.current
    if cat_id is not None: cur["cat_id"] = cat_id
    if cat_name is not None: cur["cat_name"] = cat_name
    if sub_id is not None: cur["sub_id"] = sub_id
    if sub_name is not None: cur["sub_name"] = sub_name

# ------------------------ 样式 ------------------------
st.markdown(dedent("""
<style>
/* 深色UI优化 */
:root { --card: #0F172A; --border:#1E293B; --muted:#94A3B8; }
.block-container { padding-top: 1.2rem; }
h1,h2,h3 { letter-spacing: .3px; }

.card { background: var(--card); border:1px solid var(--border);
        border-radius:16px; padding:18px; margin:10px 0; }
.muted { color: var(--muted); font-size: 13px; }

/* 按钮统一圆角 */
.stButton>button { border-radius: 10px; height: 42px; }

/* 单词列表样式 */
.word-card { margin-bottom: 1.6rem; padding: 1rem; border-bottom: 1px solid rgba(255,255,255,.08); }
.word-head { display: flex; align-items: center; gap: 10px; margin-bottom: 6px; }
.word-kr { font-size: 22px; font-weight: 700; color: #FFB6C1; cursor: pointer; transition: .2s; }
.word-kr:hover { color:#ffd4dc; text-shadow:0 0 8px rgba(255,200,210,.4); }
.word-pos { color:#999; font-size:14px; }
.word-mean { color:#ccc; font-size:15px; margin-left:8px; }
.ex-kr { color:#eaeaea; font-size: 16px; margin-left: 1.8rem; display:flex; align-items:center; gap:8px; }
.ex-zh { color:#888; font-size: 14px; margin-left: 1.8rem; }

/* 优雅小喇叭按钮（白色扁平风），带 hover/active 小动画 */
.speak-btn {
  width: 22px; height: 22px; min-width:22px;
  background: url("data:image/svg+xml;utf8,\
<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none'>\
<path d='M4 10h3l4-3v10l-4-3H4z' stroke='white' stroke-opacity='.9' stroke-width='1.5'/>\
<path d='M15 9c1 .8 1 3.2 0 4' stroke='white' stroke-opacity='.8' stroke-width='1.5' stroke-linecap='round'/>\
<path d='M17.5 7.5c2 1.7 2 6.3 0 8' stroke='white' stroke-opacity='.6' stroke-width='1.5' stroke-linecap='round'/>\
</svg>") no-repeat center/contain;
  opacity: .75; border: none; cursor: pointer; transition: transform .15s ease, opacity .15s ease;
  background-color: transparent;
}
.speak-btn:hover { opacity: 1; transform: scale(1.12); }
.speak-btn:active { transform: scale(0.96) translateY(1px); opacity: .9; }
</style>
"""), unsafe_allow_html=True)

# ------------------------ Supabase ------------------------
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
SERVICE_ROLE_KEY = os.getenv("SERVICE_ROLE_KEY", "")
ADMIN_EMAILS = [e.strip().lower() for e in os.getenv("ADMIN_EMAILS", "").split(",") if e.strip()]

if not SUPABASE_URL or not SUPABASE_ANON_KEY:
    st.error("❌ 环境变量缺失：请设置 SUPABASE_URL 与 SUPABASE_ANON_KEY")
    st.stop()

sb: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

# ------------------------ Google Vision OCR 初始化 ------------------------
vision_client = None
_creds_json = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON", "")
if _creds_json:
    try:
        cred_path = "/tmp/service-account.json"
        with open(cred_path, "w") as f:
            f.write(_creds_json)
        credentials = service_account.Credentials.from_service_account_file(cred_path)
        vision_client = vision.ImageAnnotatorClient(credentials=credentials)
    except Exception as e:
        st.error(f"⚠️ OCR 初始化失败：{e}")
else:
    st.caption("🔎 提示：未检测到 GOOGLE_APPLICATION_CREDENTIALS_JSON，OCR不可用")

# ------------------------ 登录 / 注册 ------------------------
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

# ------------------------ 左侧菜单 ------------------------
with st.sidebar:
    choice = option_menu(
        "TOPIK 背单词 · 融合版",
        ["单词列表", "手写测验", "我的进度", "管理员"],
        icons=["list-ul", "pen-tool", "bar-chart", "shield-lock"],
        menu_icon="layers", default_index=0
    )

# ------------------------ 分类选择 ------------------------
cats = sb.table("categories").select("id,name").execute().data or []
if not cats:
    st.warning("数据库中暂无分类，请先在 Supabase 添加。")
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

# ========================= 页面功能 =========================

# 1) 单词列表（朗读 + 动画）
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
        # 朗读组件（浏览器 SpeechSynthesis）
        base_html = """
        <script>
        function speakTextKo(text){
          const u = new SpeechSynthesisUtterance(text);
          u.lang = 'ko-KR';
          u.rate = 0.95;
          window.speechSynthesis.cancel(); // 防止叠音
          window.speechSynthesis.speak(u);
        }
        </script>
        """
        html = base_html + "<div>"

        for r in rows:
            word = (r.get("word_kr") or "").replace("'", "\\'")
            pos = r.get("pos", "") or ""
            mean = r.get("meaning_zh", "") or ""
            ex_kr = (r.get("example_kr", "") or "").replace("'", "\\'")
            ex_zh = r.get("example_zh", "") or ""

            html += f"""
            <div class="word-card">
              <div class="word-head">
                <span class="word-kr" onclick="speakTextKo('{word}')">{word}</span>
                <button class="speak-btn" onclick="speakTextKo('{word}')"></button>
                <span class="word-pos">{pos}</span>
                <span class="word-mean">{mean}</span>
              </div>
              <div class="ex-kr">
                {ex_kr}
                {"<button class='speak-btn' onclick=\"speakTextKo('" + ex_kr + "')\"></button>" if ex_kr else ""}
              </div>
              <div class="ex-zh">{ex_zh}</div>
            </div>
            """

        html += "</div>"
        components.html(html, height=900, scrolling=True)

# 2) 手写测验（Google Vision OCR）
elif choice == "手写测验":
    st.subheader("✍️ 手写测验（Google Vision OCR 自动判分）")

    if not vision_client:
        st.error("OCR 服务未初始化：请检查 GOOGLE_APPLICATION_CREDENTIALS_JSON 是否已正确设置。")
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
    st.caption("👇 请在下方手写韩文（iPad/触控设备均可）")

    canvas_result = st_canvas(
        fill_color="rgba(255,255,255,1)",
        stroke_width=3,
        stroke_color="#000000",
        background_color="#ffffff",
        height=220, width=420,
        drawing_mode="freedraw",
        key="canvas",
    )

    col1, col2 = st.columns(2)
    with col1:
        if st.button("提交", use_container_width=True):
            if canvas_result.image_data is None:
                st.warning("请先书写后再提交。")
            else:
                # 将画布转PNG字节
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

    with col2:
        if st.button("换一题", use_container_width=True):
            st.session_state.quiz_q = random.choice(rows)
            if "canvas" in st.session_state:  # 清空手写区缓存
                del st.session_state["canvas"]
            st.rerun()

# 3) 我的进度
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
        st.info("暂无学习记录。开始学习吧！")

# 4) 管理员
elif choice == "管理员":
    st.subheader("🛠 管理员")
    if st.session_state.user.email.lower() in ADMIN_EMAILS:
        st.caption("你拥有管理员权限。这里保留了一个示例：手动开通会员。")
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
                    st.error("未找到该邮箱的用户。")
            except Exception as e:
                st.error(f"操作失败：{e}")
    else:
        st.warning("你没有管理员权限。")
