import streamlit as st
import random
import json
from datetime import datetime
from supabase import create_client

# =======================
# Supabase 연결
# =======================
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_ANON_KEY = st.secrets["SUPABASE_ANON_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

TABLE = "flashcard_app"
BACKUP_BUCKET = "flashcard-backup"   # ← Supabase Storage 버킷 이름

# =======================
# 기본 설정
# =======================
st.set_page_config(page_title="임용 암기 카드", layout="centered")

# =======================
# DB 유틸
# =======================
def fetch_cards():
    res = supabase.table(TABLE).select("*").order("created_at").execute()
    return res.data or []

def insert_card(category, front, back):
    supabase.table(TABLE).insert({
        "category": category,
        "front": front,
        "back": back,
        "wrong_count": 0
    }).execute()
    auto_backup()

def update_card(card_id, front, back, category):
    supabase.table(TABLE).update({
        "category": category,
        "front": front,
        "back": back
    }).eq("id", card_id).execute()
    auto_backup()

def delete_card(card_id):
    supabase.table(TABLE).delete().eq("id", card_id).execute()
    auto_backup()

def increment_wrong(card_id, current_wrong):
    supabase.table(TABLE).update({
        "wrong_count": current_wrong + 1
    }).eq("id", card_id).execute()
    auto_backup()

# =======================
# 🔐 자동 백업 (서버)
# =======================
def auto_backup():
    cards = fetch_cards()
    content = json.dumps(cards, ensure_ascii=False, indent=2)
    filename = f"auto_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    supabase.storage.from_(BACKUP_BUCKET).upload(
        filename,
        content.encode("utf-8"),
        file_options={"content-type": "application/json"}
    )

# =======================
# 세션 상태
# =======================
if "cards" not in st.session_state:
    st.session_state.cards = fetch_cards()
if "index" not in st.session_state:
    st.session_state.index = 0
if "show_back" not in st.session_state:
    st.session_state.show_back = False
if "shuffled_ids" not in st.session_state:
    st.session_state.shuffled_ids = []
if "page" not in st.session_state:
    st.session_state.page = "➕ 카드 입력"

# =======================
# 공통 유틸
# =======================
def sync_from_db(rerun=False):
    st.session_state.cards = fetch_cards()
    if rerun:
        st.rerun()

def categories():
    return sorted({c["category"] for c in st.session_state.cards})

# =======================
# UI 상단
# =======================
st.markdown(
    """
    <h2 style="text-align:center;">📘 임용 대비 암기 카드</h2>
    <p style="text-align:center; color:gray;">친구와 함께 실시간으로 공부하는 임용 스터디 웹앱</p>
    """,
    unsafe_allow_html=True
)

page = st.radio(
    "메뉴",
    ["➕ 카드 입력", "🧠 암기 모드", "🛠️ 카드 관리"],
    horizontal=True,
    key="page"
)

# =======================
# 🔄 수동 백업 (다운로드)
# =======================
st.divider()
st.subheader("📦 백업")

if st.button("⬇️ 카드 전체 백업(JSON 다운로드)"):
    data = json.dumps(fetch_cards(), ensure_ascii=False, indent=2)
    filename = f"flashcard_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    st.download_button(
        "📥 백업 파일 받기",
        data,
        file_name=filename,
        mime="application/json"
    )

# =======================
# 1️⃣ 카드 입력
# =======================
if page == "➕ 카드 입력":
    st.subheader("카드 입력")

    category = st.text_input("카테고리")
    front = st.text_input("앞면 (문제)")
    back = st.text_input("뒷면 (정답)")

    if st.button("➕ 카드 추가"):
        if category and front and back:
            insert_card(category, front, back)
            sync_from_db(rerun=True)
        else:
            st.error("모든 칸을 입력하세요.")

    st.info(f"현재 카드 수: {len(st.session_state.cards)} 장")

# =======================
# 2️⃣ 암기 모드
# =======================
elif page == "🧠 암기 모드":
    st.subheader("암기 모드")

    if not st.session_state.cards:
        st.warning("카드가 없습니다.")
    else:
        cat = st.selectbox("카테고리", categories())
        base = [c for c in st.session_state.cards if c["category"] == cat]

        if not base:
            st.info("카드 없음")
        else:
            idx = st.session_state.index % len(base)
            card = base[idx]

            label = "정답" if st.session_state.show_back else "문제"
            text = card["back"] if st.session_state.show_back else card["front"]

            st.markdown(
                f"<div style='padding:40px;text-align:center;font-size:24px;"
                f"background:#f9fafb;border-radius:16px;'>{label}<br><br>{text}</div>",
                unsafe_allow_html=True
            )

            if not st.session_state.show_back:
                if st.button("정답 보기"):
                    st.session_state.show_back = True
                    st.rerun()
            else:
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("✅ 맞음"):
                        st.session_state.show_back = False
                        st.session_state.index += 1
                        st.rerun()
                with c2:
                    if st.button("❌ 틀림"):
                        increment_wrong(card["id"], card["wrong_count"])
                        st.session_state.show_back = False
                        st.session_state.index += 1
                        sync_from_db(rerun=True)

# =======================
# 3️⃣ 카드 관리
# =======================
elif page == "🛠️ 카드 관리":
    st.subheader("카드 관리")

    cat = st.selectbox("카테고리", categories())
    cards = [c for c in st.session_state.cards if c["category"] == cat]

    card = st.selectbox(
        "카드 선택",
        cards,
        format_func=lambda c: c["front"]
    )

    new_cat = st.text_input("카테고리", card["category"])
    new_front = st.text_input("앞면", card["front"])
    new_back = st.text_input("뒷면", card["back"])

    c1, c2 = st.columns(2)
    with c1:
        if st.button("💾 수정 저장"):
            update_card(card["id"], new_front, new_back, new_cat)
            sync_from_db(rerun=True)
    with c2:
        if st.button("🗑️ 삭제"):
            delete_card(card["id"])
            sync_from_db(rerun=True)














