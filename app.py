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
st.set_page_config(
    page_title="임용 대비 암기 카드",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# =======================
# 🎨 UI 스타일 (수정 금지 영역)
# =======================
st.markdown("""
<style>
.stApp {
    background: linear-gradient(180deg, #f9fafb 0%, #eef2ff 100%);
    font-family: -apple-system, BlinkMacSystemFont, "Apple SD Gothic Neo", sans-serif;
}

.block-container {
    max-width: 720px;
    padding-top: 1.5rem;
    padding-bottom: 4rem;
}

/* 헤더 */
.app-title {
    font-size: 26px;
    font-weight: 800;
    text-align: center;
    margin-bottom: 1.5rem;
}

/* 카드 */
.flashcard {
    background: white;
    padding: 48px 36px;
    border-radius: 28px;
    box-shadow: 0 24px 48px rgba(0,0,0,0.08);
    font-size: 22px;
    line-height: 1.7;
    text-align: center;
    white-space: pre-wrap;   /* ✅ 줄바꿈 가독성 핵심 */
}

.flashcard-label {
    font-size: 12px;
    font-weight: 700;
    color: #6366F1;
    margin-bottom: 16px;
}

.progress {
    font-size: 12px;
    color: #9CA3AF;
    text-align: right;
    margin-bottom: 8px;
}

/* 저장 버튼 (Primary Action) */
div[data-testid="stFormSubmitButton"] > button {
    background: linear-gradient(135deg, #6366F1, #818CF8);
    color: white;
    border-radius: 14px;
    font-weight: 700;
    padding: 10px 18px;
    border: none;
}

div[data-testid="stFormSubmitButton"] > button:hover {
    opacity: 0.9;
}

/* 이미지 크기 제한 */
.flashcard + img {
    max-width: 360px;
    width: 100%;
    margin: 18px auto 0 auto;
    display: block;
    border-radius: 16px;
}
</style>
""", unsafe_allow_html=True)

# =======================
# DB 유틸
# =======================
def fetch_cards():
    return supabase.table(TABLE).select("*").order("created_at").execute().data or []

def auto_backup():
    try:
        cards = fetch_cards()
        content = json.dumps(cards, ensure_ascii=False, indent=2)
        filename = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        supabase.storage.from_(BACKUP_BUCKET).upload(
            filename,
            content.encode("utf-8"),
            file_options={"content-type": "application/json"},
        )
    except:
        pass

def upload_image(file, folder):
    if file is None:
        return None
    filename = f"{folder}/{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.name}"
    supabase.storage.from_(IMAGE_BUCKET).upload(
        filename,
        file.getvalue(),
        file_options={"content-type": file.type},
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
    auto_backup()

def update_card(card_id, category, front, back, front_img, back_img):
    supabase.table(TABLE).update({
        "category": category,
        "front": front,
        "back": back,
        "front_image_url": front_img,
        "back_image_url": back_img,
    }).eq("id", card_id).execute()
    auto_backup()

def delete_card(card_id):
    supabase.table(TABLE).delete().eq("id", card_id).execute()
    auto_backup()

def increment_wrong(card_id, current):
    supabase.table(TABLE).update({
        "wrong_count": current + 1
    }).eq("id", card_id).execute()

# =======================
# 세션 상태 (핵심 유지)
# =======================
if "cards" not in st.session_state:
    st.session_state.cards = fetch_cards()
if "study_cards" not in st.session_state:
    st.session_state.study_cards = None
if "index" not in st.session_state:
    st.session_state.index = 0
if "show_back" not in st.session_state:
    st.session_state.show_back = False
if "order" not in st.session_state:
    st.session_state.order = []
if "upload_key" not in st.session_state:
    st.session_state.upload_key = 0

# =======================
# 공통
# =======================
def sync():
    st.session_state.cards = fetch_cards()
    st.session_state.study_cards = None

def categories(cards):
    return sorted({c["category"] for c in cards})

# =======================
# 헤더 & 메뉴
# =======================
st.markdown('<div class="app-title">📘 임용 대비 암기 카드</div>', unsafe_allow_html=True)

page = st.radio("", ["➕ 카드 입력", "🧠 암기 모드", "🛠️ 카드 관리"], horizontal=True)

# =======================
# 카드 저장 (form 대응)
# =======================
def save_card_fast():
    cat = (st.session_state.get("input_category") or "").strip()
    front = (st.session_state.get("input_front") or "").strip()
    back = (st.session_state.get("input_back") or "").strip()

    if not (cat and front and back):
        return

    front_file = st.session_state.get(f"input_front_image_{st.session_state.upload_key}")
    back_file = st.session_state.get(f"input_back_image_{st.session_state.upload_key}")

    front_img = upload_image(front_file, "front") if front_file else None
    back_img = upload_image(back_file, "back") if back_file else None

    insert_card(cat, front, back, front_img, back_img)

    st.session_state.upload_key += 1
    sync()
    st.rerun()

# =======================
# 1️⃣ 카드 입력 (form)
# =======================
if page == "➕ 카드 입력":

    with st.form("card_input_form", clear_on_submit=True):

        st.text_input("카테고리", key="input_category")
        st.text_input("앞면", key="input_front")

        st.text_area(
            "뒷면 (줄바꿈 가능)",
            key="input_back",
            height=160,
            placeholder="Enter = 줄바꿈"
        )

        st.file_uploader(
            "앞면 이미지 (선택)",
            ["png","jpg","jpeg"],
            key=f"input_front_image_{st.session_state.upload_key}"
        )
        st.file_uploader(
            "뒷면 이미지 (선택)",
            ["png","jpg","jpeg"],
            key=f"input_back_image_{st.session_state.upload_key}"
        )

        submitted = st.form_submit_button("💾 저장")

    if submitted:
        save_card_fast()

    st.caption(f"📚 카드 수 {len(st.session_state.cards)}")

# =======================
# 2️⃣ 암기 모드 (랜덤 / 오답 / 엔터온리 복구 + 확장)
# =======================
elif page == "🧠 암기 모드":

    if not st.session_state.cards:
        st.warning("카드가 없습니다.")
        st.stop()

    # ── 암기 세션 초기화 (최초 진입 시 1회)
    if st.session_state.study_cards is None:
        st.session_state.study_cards = st.session_state.cards.copy()
        st.session_state.index = 0
        st.session_state.show_back = False
        st.session_state.order = []

    cards = st.session_state.study_cards

    # ── 옵션 영역
    cat = st.selectbox("카테고리", categories(cards))

    c1, c2, c3 = st.columns(3)
    with c1:
        random_mode = st.checkbox("🔀 랜덤")
    with c2:
        wrong_only = st.checkbox("❗ 오답만")
    with c3:
        enter_only = st.checkbox("⌨️ 엔터 온리", value=True)

    # ── 카드 필터링
    base = [c for c in cards if c["category"] == cat]
    if wrong_only:
        base = [c for c in base if int(c["wrong_count"]) > 0]

    if not base:
        st.info("표시할 카드가 없습니다.")
        st.stop()

    ids = [c["id"] for c in base]

    # ── 랜덤 + 다시 섞기
    if random_mode:
        if st.button("🔄 다시 섞기"):
            st.session_state.order = random.sample(ids, len(ids))
            st.session_state.index = 0
            st.session_state.show_back = False

        # 최초 랜덤 진입 시 자동 섞기
        if not st.session_state.order or set(st.session_state.order) != set(ids):
            st.session_state.order = random.sample(ids, len(ids))
            st.session_state.index = 0
            st.session_state.show_back = False

        order = st.session_state.order
    else:
        order = ids
        st.session_state.order = []

    # ── 현재 카드
    cid = order[st.session_state.index % len(order)]
    card = next(c for c in base if c["id"] == cid)

    label = "정답" if st.session_state.show_back else "문제"
    text = card["back"] if st.session_state.show_back else card["front"]
    img = card["back_image_url"] if st.session_state.show_back else card["front_image_url"]

    # ── 카드 UI
    st.markdown(
        f'<div class="progress">{st.session_state.index + 1} / {len(order)}</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        f"""
        <div class="flashcard">
            <div class="flashcard-label">{label}</div>
            {text}
        </div>
        """,
        unsafe_allow_html=True
    )

    if img:
        st.image(img)

    # ── 컨트롤 영역
    if enter_only:
        msg = st.chat_input("Enter → 문제 / 정답 / 다음 카드")
        if msg is not None:
            if not st.session_state.show_back:
                st.session_state.show_back = True
            else:
                st.session_state.show_back = False
                st.session_state.index += 1
    else:
        if not st.session_state.show_back:
            if st.button("정답 보기"):
                st.session_state.show_back = True
        else:
            c1, c2 = st.columns(2)
            with c1:
                if st.button("✅ 정답"):
                    st.session_state.show_back = False
                    st.session_state.index += 1
            with c2:
                if st.button("❌ 오답"):
                    increment_wrong(card["id"], int(card["wrong_count"]))
                    st.session_state.show_back = False
                    st.session_state.index += 1
                    sync()


# =======================
# 3️⃣ 카드 관리 (줄바꿈 가능)
# =======================
elif page == "🛠️ 카드 관리":

    cat = st.selectbox("카테고리", categories(st.session_state.cards))
    cards = [c for c in st.session_state.cards if c["category"] == cat]
    card = st.selectbox("카드 선택", cards, format_func=lambda c: c["front"])

    new_cat = st.text_input("카테고리", card["category"])
    new_front = st.text_input("앞면", card["front"])

    new_back = st.text_area(
        "뒷면 (줄바꿈 가능)",
        card["back"],
        height=160
    )

    front_file = st.file_uploader("앞면 이미지 교체", ["png","jpg","jpeg"])
    back_file = st.file_uploader("뒷면 이미지 교체", ["png","jpg","jpeg"])

    c1, c2 = st.columns(2)
    with c1:
        if st.button("💾 수정"):
            front_img = upload_image(front_file, "front") or card["front_image_url"]
            back_img = upload_image(back_file, "back") or card["back_image_url"]
            update_card(card["id"], new_cat, new_front, new_back, front_img, back_img)
            sync()
            st.success("수정 완료")

    with c2:
        if st.button("🗑️ 삭제"):
            delete_card(card["id"])
            sync()
            st.success("삭제 완료")


























