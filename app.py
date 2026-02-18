import streamlit as st
import random
import json
import re
import uuid
import httpx
from datetime import datetime
from supabase import create_client
from postgrest.exceptions import APIError

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
    padding: 36px 36px;
    border-radius: 28px;
    box-shadow: 0 24px 48px rgba(0,0,0,0.08);
    font-size: 22px;
    line-height: 1.7;
    text-align: center;
    white-space: pre-wrap;

    display: flex;
    flex-direction: column;
    justify-content: center;
}

.flashcard-label {
    font-size: 12px;
    font-weight: 700;
    color: #6366F1;
    margin-bottom: 10px;
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
.flashcard-image {
    width: 25%;
    max-width: 140px;
    min-width: 90px;
    margin: 14px auto 0 auto;
    display: block;
    border-radius: 10px;
}

.flashcard-text {
    white-space: pre-wrap;
}
</style>
""", unsafe_allow_html=True)

# =======================
# DB 유틸
# =======================
def fetch_cards():
    return supabase.table(TABLE).select("*").order("created_at").execute().data or []

def fetch_cards_safe():
    """
    Supabase가 Paused/기동 중/네트워크 문제여도 앱이 죽지 않게
    실패 시 None 반환
    """
    try:
        return fetch_cards()
    except (httpx.ConnectError, APIError, Exception):
        return None

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

def safe_filename(name: str) -> str:
    """Supabase Storage에서 허용되는 안전한 파일명으로 변환 (영문/숫자/._- 만 허용)"""
    return re.sub(r"[^a-zA-Z0-9._-]", "_", name)

def upload_image(file, folder):
    if file is None:
        return None
    try:
        safe_name = safe_filename(file.name)
        filename = f"{folder}/{uuid.uuid4().hex}_{safe_name}"

        supabase.storage.from_(IMAGE_BUCKET).upload(
            filename,
            file.getvalue(),
            file_options={"content-type": file.type},
        )
        return supabase.storage.from_(IMAGE_BUCKET).get_public_url(filename)
    except Exception:
        st.warning("⚠️ 이미지 업로드 실패 (파일명 또는 Storage 설정 문제)")
        return None

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
    supabase.table(TABLE).update({"wrong_count": current + 1}).eq("id", card_id).execute()

def reset_wrong(card_id):
    supabase.table(TABLE).update({"wrong_count": 0}).eq("id", card_id).execute()

def reset_wrong_by_category(category):
    supabase.table(TABLE).update({"wrong_count": 0}).eq("category", category).execute()

# =======================
# 세션 상태 (핵심 유지)
# =======================
if "cards" not in st.session_state:
    data = fetch_cards_safe()
    st.session_state.cards = data if data is not None else []
    st.session_state.supabase_ok = (data is not None)

if "supabase_ok" not in st.session_state:
    st.session_state.supabase_ok = True

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
    data = fetch_cards_safe()
    if data is None:
        st.session_state.supabase_ok = False
        st.session_state.cards = []
        st.session_state.study_cards = None
        return
    st.session_state.cards = data
    st.session_state.study_cards = None
    st.session_state.supabase_ok = True

def categories(cards):
    return sorted({c["category"] for c in cards})

# =======================
# 헤더 & Supabase 연결 실패 방어막
# =======================
st.markdown('<div class="app-title">📘 임용 대비 암기 카드</div>', unsafe_allow_html=True)

if not st.session_state.supabase_ok:
    st.error("⚠️ Supabase 프로젝트가 잠들어 있거나(Paused), 깨는 중이거나 네트워크 문제로 연결에 실패했습니다.\n\nSupabase에서 Resume 후 아래 버튼을 눌러주세요.")
    if st.button("🔄 다시 시도"):
        data = fetch_cards_safe()
        if data is not None:
            st.session_state.cards = data
            st.session_state.supabase_ok = True
        st.rerun()
    st.stop()

# =======================
# 메뉴
# =======================
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
# 1️⃣ 카드 입력 (카테고리 유지)
# =======================
if page == "➕ 카드 입력":

    st.text_input("카테고리", key="input_category", placeholder="예: 전기전자")

    with st.form("card_input_form", clear_on_submit=True):
        st.text_input("앞면", key="input_front", placeholder="문제 또는 개념")
        st.text_area("뒷면 (줄바꿈 가능)", key="input_back", height=160, placeholder="Enter = 줄바꿈")

        st.file_uploader("앞면 이미지 (선택)", ["png", "jpg", "jpeg"],
                         key=f"input_front_image_{st.session_state.upload_key}")
        st.file_uploader("뒷면 이미지 (선택)", ["png", "jpg", "jpeg"],
                         key=f"input_back_image_{st.session_state.upload_key}")

        submitted = st.form_submit_button("💾 저장")

    if submitted:
        save_card_fast()

    st.caption(f"📚 카드 수 {len(st.session_state.cards)}")

# =======================
# 2️⃣ 암기 모드
# =======================
elif page == "🧠 암기 모드":

    if not st.session_state.cards:
        st.warning("카드가 없습니다.")
        st.stop()

    if st.session_state.study_cards is None:
        st.session_state.study_cards = st.session_state.cards.copy()
        st.session_state.index = 0
        st.session_state.show_back = False
        st.session_state.order = []

    cards = st.session_state.study_cards

    cat = st.selectbox("카테고리", categories(cards))

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        random_mode = st.checkbox("🔀 랜덤")
    with c2:
        wrong_only = st.checkbox("❗ 오답만")
    with c3:
        enter_only = st.checkbox("⌨️ 엔터 온리", value=True)
    with c4:
        recall_mode = st.checkbox("🧠 회상 모드")

    st.caption("회상 모드: 설명을 보고 해당 개념을 떠올리는 연습")

    base = [c for c in cards if c["category"] == cat]
    if wrong_only:
        base = [c for c in base if int(c["wrong_count"]) > 0]

    if not base:
        st.info("표시할 카드가 없습니다.")
        st.stop()

    ids = [c["id"] for c in base]

    if random_mode:
        if st.button("🔄 다시 섞기"):
            st.session_state.order = random.sample(ids, len(ids))
            st.session_state.index = 0
            st.session_state.show_back = False

        if not st.session_state.order or set(st.session_state.order) != set(ids):
            st.session_state.order = random.sample(ids, len(ids))
            st.session_state.index = 0
            st.session_state.show_back = False

        order = st.session_state.order
    else:
        order = ids
        st.session_state.order = []

    cid = order[st.session_state.index % len(order)]
    card = next(c for c in base if c["id"] == cid)

    if recall_mode:
        first_label, second_label = "설명", "개념"
        first_text, second_text = card["back"], card["front"]
        first_img, second_img = card["back_image_url"], card["front_image_url"]
    else:
        first_label, second_label = "문제", "정답"
        first_text, second_text = card["front"], card["back"]
        first_img, second_img = card["front_image_url"], card["back_image_url"]

    label = second_label if st.session_state.show_back else first_label
    text = second_text if st.session_state.show_back else first_text
    img = second_img if st.session_state.show_back else first_img

    st.markdown(f'<div class="progress">{st.session_state.index + 1} / {len(order)}</div>',
                unsafe_allow_html=True)

    st.markdown(
        f"""
        <div class="flashcard">
            <div class="flashcard-label">{label}</div>
            <div class="flashcard-text">{text}</div>
            {"<img src='" + img + "' class='flashcard-image' />" if img else ""}
        </div>
        """,
        unsafe_allow_html=True
    )

    if enter_only:
        st.caption("⌨️ Enter 키를 눌러 진행합니다")
        if st.button("▶️ 다음 (Enter 대체)", use_container_width=True):
            if not st.session_state.show_back:
                st.session_state.show_back = True
            else:
                st.session_state.show_back = False
                st.session_state.index += 1
    else:
        if not st.session_state.show_back:
            if st.button("정답 보기", use_container_width=True):
                st.session_state.show_back = True
        else:
            cc1, cc2 = st.columns(2)
            with cc1:
                if st.button("✅ 정답"):
                    st.session_state.show_back = False
                    st.session_state.index += 1
            with cc2:
                if st.button("❌ 오답"):
                    increment_wrong(card["id"], int(card["wrong_count"]))
                    st.session_state.show_back = False
                    st.session_state.index += 1
                    sync()

            if st.button("🧹 이 카드 오답 제외"):
                reset_wrong(card["id"])
                st.session_state.show_back = False
                sync()

    if wrong_only:
        if st.button("🧹 이 카테고리 오답 전체 리셋"):
            reset_wrong_by_category(cat)
            sync()
            st.success("이 카테고리의 오답이 모두 초기화되었습니다.")
            st.stop()

# =======================
# 3️⃣ 카드 관리
# =======================
elif page == "🛠️ 카드 관리":

    cat = st.selectbox("카테고리", categories(st.session_state.cards))
    cards = [c for c in st.session_state.cards if c["category"] == cat]
    card = st.selectbox("카드 선택", cards, format_func=lambda c: c["front"])

    new_cat = st.text_input("카테고리", card["category"])
    new_front = st.text_input("앞면", card["front"])
    new_back = st.text_area("뒷면 (줄바꿈 가능)", card["back"], height=160)

    front_file = st.file_uploader("앞면 이미지 교체", ["png", "jpg", "jpeg"])
    back_file = st.file_uploader("뒷면 이미지 교체", ["png", "jpg", "jpeg"])

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







































