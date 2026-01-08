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
BACKUP_BUCKET = "flashcard-backup"
IMAGE_BUCKET = "flashcard-images"

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

def auto_backup():
    cards = fetch_cards()
    content = json.dumps(cards, ensure_ascii=False, indent=2)

    filename = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    supabase.storage.from_(BACKUP_BUCKET).upload(
        path=filename,
        file=content.encode("utf-8"),
        file_options={"content-type": "application/json"},
    )

def upload_image(file, folder):
    if file is None:
        return None
    filename = f"{folder}/{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.name}"
    supabase.storage.from_(IMAGE_BUCKET).upload(
        filename,
        file.getvalue(),
        file_options={"content-type": file.type}
    )
    return supabase.storage.from_(IMAGE_BUCKET).get_public_url(filename)

def insert_card(category, front, back, front_img, back_img):
    supabase.table(TABLE).insert({
        "category": category,
        "front": front,
        "back": back,
        "front_image_url": front_img,
        "back_image_url": back_img,
        "wrong_count": 0
    }).execute()

def update_card(card_id, category, front, back, front_img, back_img):
    supabase.table(TABLE).update({
        "category": category,
        "front": front,
        "back": back,
        "front_image_url": front_img,
        "back_image_url": back_img
    }).eq("id", card_id).execute()

def delete_card(card_id):
    supabase.table(TABLE).delete().eq("id", card_id).execute()

def increment_wrong(card):
    supabase.table(TABLE).update({
        "wrong_count": int(card["wrong_count"]) + 1
    }).eq("id", card["id"]).execute()
    auto_backup()

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

# =======================
# 공통 유틸
# =======================
def sync(rerun=False):
    st.session_state.cards = fetch_cards()
    if rerun:
        st.rerun()

def categories():
    return sorted({c["category"] for c in st.session_state.cards})

# =======================
# 상단 UI
# =======================
st.markdown("<h2 style='text-align:center;'>📘 임용 대비 암기 카드</h2>", unsafe_allow_html=True)

page = st.radio(
    "메뉴",
    ["➕ 카드 입력", "🧠 암기 모드", "🛠️ 카드 관리"],
    horizontal=True
)

# =======================
# 수동 백업
# =======================
st.divider()
data = json.dumps(fetch_cards(), ensure_ascii=False, indent=2)
st.download_button(
    "⬇️ 카드 전체 백업(JSON)",
    data,
    file_name=f"flashcard_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
    mime="application/json"
)

if "did_auto_backup" not in st.session_state:
    try:
        auto_backup()
        st.session_state.did_auto_backup = True
    except Exception as e:
        st.warning("자동 백업은 건너뛰었어요 (권한/연결 문제)")

# =======================
# 1️⃣ 카드 입력
# =======================
if page == "➕ 카드 입력":
    st.subheader("카드 입력")

    cat = st.text_input("카테고리")
    front = st.text_input("앞면 (문제)")
    back = st.text_input("뒷면 (정답)")

    front_file = st.file_uploader("앞면 이미지 (선택)", ["png", "jpg", "jpeg"])
    back_file = st.file_uploader("뒷면 이미지 (선택)", ["png", "jpg", "jpeg"])

    if st.button("➕ 카드 추가"):
        if not (cat and front and back):
            st.error("카테고리 / 문제 / 정답은 필수입니다.")
        else:
            front_img = upload_image(front_file, "front")
            back_img = upload_image(back_file, "back")
            insert_card(cat, front, back, front_img, back_img)
            sync(rerun=True)

# =======================
# 2️⃣ 암기 모드
# =======================
elif page == "🧠 암기 모드":
    st.subheader("암기 모드")

    if not st.session_state.cards:
        st.warning("카드가 없습니다.")
        st.stop()

    # ===== 옵션 =====
    cat = st.selectbox("카테고리", categories())
    random_mode = st.checkbox("🔀 랜덤")
    wrong_only = st.checkbox("❗ 틀린 카드만")
    enter_only = st.checkbox("⌨️ Enter-only 모드", value=True)

    # ===== 카드 필터 =====
    base = [c for c in st.session_state.cards if c["category"] == cat]
    if wrong_only:
        base = [c for c in base if int(c.get("wrong_count", 0)) > 0]

    if not base:
        st.info("표시할 카드가 없습니다.")
        st.stop()

    # ===== 순서 결정 =====
    ids = [c["id"] for c in base]

    if random_mode:
        if set(st.session_state.shuffled_ids) != set(ids):
            st.session_state.shuffled_ids = random.sample(ids, len(ids))
            st.session_state.index = 0
            st.session_state.show_back = False
        order = st.session_state.shuffled_ids
    else:
        order = ids
        st.session_state.shuffled_ids = []

    card_id = order[st.session_state.index % len(order)]
    card = next(c for c in base if c["id"] == card_id)

    # ===== 앞/뒤 내용 결정 =====
    is_back = st.session_state.show_back

    text = card["back"] if is_back else card["front"]
    img_url = card["back_image_url"] if is_back else card["front_image_url"]
    label = "정답" if is_back else "문제"

    # ===== 카드 UI =====
    st.markdown(
        f"""
        <div style="
            max-width:650px;
            margin:30px auto;
            padding:40px;
            background:#f9fafb;
            border-radius:16px;
            box-shadow:0 4px 12px rgba(0,0,0,0.08);
            text-align:center;
            font-size:24px;
            line-height:1.6;
        ">
            <b>[{label}]</b><br><br>{text}
        </div>
        """,
        unsafe_allow_html=True
    )

    # ===== 이미지 표시 (있을 때만) =====
    if img_url:
        st.image(img_url, use_column_width=True)

    # ===== 컨트롤 =====
    if enter_only:
        msg = st.chat_input("Enter (문제 → 정답 → 다음 카드)")
        if msg is not None:
            if not st.session_state.show_back:
                st.session_state.show_back = True
            else:
                st.session_state.show_back = False
                st.session_state.index += 1
            st.rerun()
    else:
        if not st.session_state.show_back:
            if st.button("정답 보기", use_container_width=True):
                st.session_state.show_back = True
                st.rerun()
        else:
            c1, c2 = st.columns(2)
            with c1:
                if st.button("✅ 맞음", use_container_width=True):
                    st.session_state.show_back = False
                    st.session_state.index += 1
                    st.rerun()
            with c2:
                if st.button("❌ 틀림", use_container_width=True):
                    increment_wrong(card)
                    st.session_state.show_back = False
                    st.session_state.index += 1
                    sync(rerun=True)


# =======================
# 3️⃣ 카드 관리
# =======================
elif page == "🛠️ 카드 관리":
    st.subheader("카드 관리")

    cat = st.selectbox("카테고리", categories())
    cards = [c for c in st.session_state.cards if c["category"] == cat]

    card = st.selectbox("카드 선택", cards, format_func=lambda c: c["front"])

    new_cat = st.text_input("카테고리", card["category"])
    new_front = st.text_input("앞면", card["front"])
    new_back = st.text_input("뒷면", card["back"])

    front_file = st.file_uploader("앞면 이미지 교체", ["png", "jpg", "jpeg"])
    back_file = st.file_uploader("뒷면 이미지 교체", ["png", "jpg", "jpeg"])

    c1, c2 = st.columns(2)
    with c1:
        if st.button("💾 수정 저장"):
            front_img = upload_image(front_file, "front") or card["front_image_url"]
            back_img = upload_image(back_file, "back") or card["back_image_url"]
            update_card(card["id"], new_cat, new_front, new_back, front_img, back_img)
            sync(rerun=True)
    with c2:
        if st.button("🗑️ 삭제"):
            delete_card(card["id"])
            sync(rerun=True)











