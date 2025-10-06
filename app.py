import streamlit as st
import os
import json
import base64
import requests
import io
import time
from google.cloud import vision
from google.oauth2 import service_account
from PIL import Image
from supabase import create_client, Client

# ==========================
# 环境变量配置
# ==========================
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")
GOOGLE_CREDENTIALS_JSON = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON")

if not SUPABASE_URL or not SUPABASE_KEY:
    st.error("❌ 未检测到 Supabase 环境变量，请检查 Railway Variables。")

if not GOOGLE_CREDENTIALS_JSON:
    st.error("❌ 未设置 GOOGLE_APPLICATION_CREDENTIALS_JSON 环境变量。")
else:
    creds_dict = json.loads(GOOGLE_CREDENTIALS_JSON)
    credentials = service_account.Credentials.from_service_account_info(creds_dict)
    vision_client = vision.ImageAnnotatorClient(credentials=credentials)

# 初始化 Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ==========================
# 页面配置
# ==========================
st.set_page_config(page_title="TOPIK 词汇 · 柔和渐显版", layout="wide", page_icon="📘")

st.markdown("""
    <style>
    /* 整体背景柔和渐显 */
    body { 
        background: #f9f9fb; 
        animation: fadeIn 1.2s ease-in;
    }
    @keyframes fadeIn {
        0% {opacity: 0;}
        100% {opacity: 1;}
    }
    /* 卡片样式 */
    .word-card {
        background: white;
        border-radius: 15px;
        padding: 18px;
        margin-bottom: 14px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.08);
        transition: transform .2s, box-shadow .3s;
    }
    .word-card:hover {
        transform: translateY(-3px);
        box-shadow: 0 4px 10px rgba(0,0,0,0.1);
    }
    .play-button {
        font-size: 18px;
        cursor: pointer;
        color: #007bff;
        margin-left: 8px;
    }
    </style>
""", unsafe_allow_html=True)

# ==========================
# 页面导航
# ==========================
menu = st.sidebar.radio("📚 TOPIK 背单词 · 柔和渐显版", ["📖 单词列表", "✍️ 手写测验", "📊 我的进度"])

# ==========================
# 单词列表页面
# ==========================
if menu == "📖 单词列表":
    st.subheader("📘 TOPIK 单词列表")

    categories = supabase.table("vocabularies").select("category").execute()
    categories = sorted({row["category"] for row in categories.data if row["category"]})
    if not categories:
        st.warning("没有找到单词数据，请检查数据库。")
    else:
        selected_cat = st.selectbox("选择目录", categories)
        subcategories = (
            supabase.table("vocabularies")
            .select("subcategory")
            .eq("category", selected_cat)
            .execute()
        )
        subs = sorted({row["subcategory"] for row in subcategories.data if row["subcategory"]})
        selected_sub = st.selectbox("选择子目录", subs)

        vocab_data = (
            supabase.table("vocabularies")
            .select("*")
            .eq("category", selected_cat)
            .eq("subcategory", selected_sub)
            .execute()
        ).data

        for v in vocab_data:
            st.markdown(f"""
                <div class='word-card'>
                    <b style='font-size:20px;color:#222'>{v['word_kr']}</b>
                    <span style='color:#999;margin-left:8px'>({v.get('pos','')})</span>
                    <br>
                    <span style='color:#444'>{v['meaning_zh']}</span><br>
                    <span style='color:#666'>{v.get('example_kr','')}</span>
                    <span class='play-button' onclick="new Audio('https://translate.google.com/translate_tts?ie=UTF-8&tl=ko&q={v['word_kr']}&client=tw-ob').play()">🔊</span><br>
                    <small style='color:#999'>{v.get('example_zh','')}</small>
                </div>
            """, unsafe_allow_html=True)

# ==========================
# 手写测验页面（OCR识别）
# ==========================
elif menu == "✍️ 手写测验":
    st.subheader("✍️ 手写测验（Google Vision OCR 自动判分）")
    categories = supabase.table("vocabularies").select("category").execute()
    categories = sorted({row["category"] for row in categories.data if row["category"]})

    if not categories:
        st.warning("暂无单词数据")
    else:
        selected_cat = st.selectbox("选择目录", categories)
        subs = (
            supabase.table("vocabularies")
            .select("subcategory")
            .eq("category", selected_cat)
            .execute()
        )
        subs = sorted({row["subcategory"] for row in subs.data if row["subcategory"]})
        selected_sub = st.selectbox("选择子目录", subs)

        rows = (
            supabase.table("vocabularies")
            .select("*")
            .eq("category", selected_cat)
            .eq("subcategory", selected_sub)
            .execute()
        ).data

        if rows:
            import random
            quiz = random.choice(rows)
            st.write(f"**中文：** {quiz['meaning_zh']}")
            st.write("✍️ 请在下方手写答案（支持触屏 / iPad）")

            from streamlit_drawable_canvas import st_canvas
            canvas_result = st_canvas(
                fill_color="#00000000",
                stroke_width=5,
                stroke_color="#333",
                background_color="#fff",
                height=180,
                width=400,
                drawing_mode="freedraw",
                key="canvas",
            )

            if st.button("提交"):
                if canvas_result.image_data is not None:
                    img = Image.fromarray(canvas_result.image_data.astype("uint8")).convert("RGB")
                    buf = io.BytesIO()
                    img.save(buf, format="PNG")
                    content = buf.getvalue()
                    image = vision.Image(content=content)
                    response = vision_client.text_detection(image=image)
                    texts = response.text_annotations

                    if texts:
                        ocr_text = texts[0].description.strip()
                        st.info(f"🔍 OCR 识别结果：{ocr_text}")
                        correct = quiz["word_kr"].strip()
                        if ocr_text == correct:
                            st.success("✅ 正确！太棒了！")
                        else:
                            st.error(f"❌ 错误。正确答案是：{correct}")
                    else:
                        st.warning("未识别出文字，请重试。")

            if st.button("换一题"):
                st.rerun()
        else:
            st.warning("没有找到单词记录。")

# ==========================
# 我的进度页面
# ==========================
elif menu == "📊 我的进度":
    st.subheader("📊 学习进度统计")
    st.info("该功能即将上线，可显示你的学习历史与测验正确率。")

