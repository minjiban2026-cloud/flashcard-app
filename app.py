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

    except Exception as e:
        # ❗ 백업 실패해도 앱은 계속 동작
        st.warning("⚠️ 자동 백업 실패 (권한 또는 스토리지 설정 문제)")


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
# 세션 상태
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

# =======================
# 공통 유틸
# =======================
def sync():
    st.session_state.cards = fetch_cards()
    st.session_state.study_cards = None

def categories(cards):
    return sorted({c["category"] for c in cards})

# =======================
# UI 헤더
# =======================
st.markdown("<h2 style='text-align:center;'>📘 임용 대비 암기 카드</h2>", unsafe_allow_html=True)

page = st.radio(
    "메뉴",
    ["➕ 카드 입력", "🧠 암기 모드", "🛠️ 카드 관리"],
    horizontal=True
)
def save_card_fast():
    cat = (st.session_state.get("input_category", "") or "").strip()
    front = (st.session_state.get("input_front", "") or "").strip()
    back = (st.session_state.get("input_back", "") or "").strip()

    if not (cat and front and back):
        return

    front_file = st.session_state.get(f"input_front_image_{st.session_state.upload_key}")
    back_file = st.session_state.get(f"input_back_image_{st.session_state.upload_key}")

    front_img = upload_image(front_file, "front") if front_file else None
    back_img = upload_image(back_file, "back") if back_file else None

    insert_card(cat, front, back, front_img, back_img)

    # ✅ text_input은 직접 초기화 가능
    st.session_state["input_front"] = ""
    st.session_state["input_back"] = ""

    # ✅ file_uploader는 key 변경으로 리셋
    st.session_state.upload_key += 1

    sync()
    st.rerun()


# =======================
# 수동 백업
# =======================
st.download_button(
    "⬇️ 카드 전체 백업(JSON)",
    json.dumps(fetch_cards(), ensure_ascii=False, indent=2),
    file_name=f"flashcard_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
    mime="application/json"
)

# =======================
# 1️⃣ 카드 입력 (앞면→뒷면 Enter로 저장)
# =======================
if page == "➕ 카드 입력":
    st.subheader("카드 입력 (앞면 → 뒷면 Enter로 저장)")

    st.text_input(
        "카테고리",
        key="input_category",
        placeholder="예: 전기전자, 교육과정"
    )

    st.text_input(
        "앞면 (문제)",
        key="input_front",
        placeholder="문제/용어/개념"
    )

    # ✅ 여기서 Enter 누르면 자동 저장됨
    st.text_input(
        "뒷면 (정답) — Enter로 저장",
        key="input_back",
        placeholder="정답 입력 후 Enter",
        on_change=save_card_fast
    )

    st.file_uploader(
        "앞면 이미지 (선택)",
        type=["png", "jpg", "jpeg"],
        key="input_front_image"
    )
    st.file_uploader(
        "뒷면 이미지 (선택)",
        type=["png", "jpg", "jpeg"],
        key="input_back_image"
    )

    st.caption("✅ Enter로 저장되며, 저장 후 입력칸/이미지는 자동 초기화됩니다.")
    st.info(f"현재 카드 수: {len(st.session_state.cards)} 장")


# =======================
# 2️⃣ 암기 모드 (속도 최적화 핵심)
# =======================
elif page == "🧠 암기 모드":
    st.subheader("암기 모드")

    if not st.session_state.cards:
        st.warning("카드가 없습니다.")
        st.stop()

    # 최초 진입 시 카드 스냅샷 고정
    if st.session_state.study_cards is None:
        st.session_state.study_cards = st.session_state.cards.copy()
        st.session_state.index = 0
        st.session_state.show_back = False
        st.session_state.order = []

    cards = st.session_state.study_cards

    # ===== 옵션 =====
    cat = st.selectbox("카테고리", categories(cards))
    random_mode = st.checkbox("🔀 랜덤")
    wrong_only = st.checkbox("❗ 틀린 카드만")
    enter_only = st.checkbox("⌨️ Enter-only", value=True)

    # ===== 카드 필터 =====
    base = [c for c in cards if c["category"] == cat]
    if wrong_only:
        base = [c for c in base if int(c["wrong_count"]) > 0]

    if not base:
        st.info("표시할 카드가 없습니다.")
        st.stop()

    # ===== ID 목록 =====
    ids = [c["id"] for c in base]

    # 🔄 다시 섞기 버튼 (여기가 정답 위치)
    if random_mode:
        if st.button("🔄 다시 섞기"):
            st.session_state.order = random.sample(ids, len(ids))
            st.session_state.index = 0
            st.session_state.show_back = False

    # ===== 순서 결정 =====
    if random_mode:
        if not st.session_state.order or set(st.session_state.order) != set(ids):
            st.session_state.order = random.sample(ids, len(ids))
            st.session_state.index = 0
            st.session_state.show_back = False
        order = st.session_state.order
    else:
        order = ids
        st.session_state.order = []

    # ===== 현재 카드 =====
    cid = order[st.session_state.index % len(order)]
    card = next(c for c in base if c["id"] == cid)

    text = card["back"] if st.session_state.show_back else card["front"]
    img = card["back_image_url"] if st.session_state.show_back else card["front_image_url"]
    label = "정답" if st.session_state.show_back else "문제"

    st.markdown(
        f"""
        <div style="
            padding:40px;
            background:#f9fafb;
            border-radius:16px;
            text-align:center;
            font-size:24px;
        ">
        <b>[{label}]</b><br><br>{text}
        </div>
        """,
        unsafe_allow_html=True
    )

    if img:
        st.image(img, use_column_width=True)

    # ===== 컨트롤 =====
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
                if st.button("✅ 맞음"):
                    st.session_state.show_back = False
                    st.session_state.index += 1
            with c2:
                if st.button("❌ 틀림"):
                    increment_wrong(card["id"], int(card["wrong_count"]))
                    st.session_state.show_back = False
                    st.session_state.index += 1
                    sync()

# =======================
# 3️⃣ 카드 관리
# =======================
elif page == "🛠️ 카드 관리":
    st.subheader("카드 관리")

    cat = st.selectbox("카테고리", categories(st.session_state.cards))
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
            sync()
            st.success("수정 완료")
    with c2:
        if st.button("🗑️ 삭제"):
            delete_card(card["id"])
            sync()
            st.success("삭제 완료")

















