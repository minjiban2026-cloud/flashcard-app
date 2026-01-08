import streamlit as st
import random
import json
import os
from supabase import create_client
from uuid import uuid4
from datetime import datetime

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_ANON_KEY = st.secrets["SUPABASE_ANON_KEY"]

supabase = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

# =======================
# 기본 설정
# =======================
st.set_page_config(page_title="임용 암기 카드", layout="centered")
DATA_FILE = "cards.json"

# =======================
# 데이터 저장 / 로드
# =======================
def load_cards():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_cards():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(st.session_state.cards, f, ensure_ascii=False, indent=2)

def export_cards():
    filename = f"cards_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    return filename, json.dumps(st.session_state.cards, ensure_ascii=False, indent=2)

def import_cards(uploaded_file, mode):
    data = json.load(uploaded_file)
    if not isinstance(data, list):
        return False

    for c in data:
        if "id" not in c:
            c["id"] = uuid4().hex[:10]
        if "wrong_count" not in c:
            c["wrong_count"] = 0

    if mode == "replace":
        st.session_state.cards = data
    else:
        existing_ids = {c["id"] for c in st.session_state.cards}
        for c in data:
            if c["id"] not in existing_ids:
                st.session_state.cards.append(c)

    save_cards()
    return True

# =======================
# 세션 상태 초기화
# =======================
if "cards" not in st.session_state:
    st.session_state.cards = load_cards()
if "index" not in st.session_state:
    st.session_state.index = 0
if "show_back" not in st.session_state:
    st.session_state.show_back = False
if "shuffled_ids" not in st.session_state:
    st.session_state.shuffled_ids = []
if "input_category" not in st.session_state:
    st.session_state.input_category = ""
if "input_front" not in st.session_state:
    st.session_state.input_front = ""
if "input_back" not in st.session_state:
    st.session_state.input_back = ""
if "enter_trigger" not in st.session_state:
    st.session_state.enter_trigger = ""

# =======================
# 유틸
# =======================
def find_card_index_by_id(card_id):
    for i, c in enumerate(st.session_state.cards):
        if c["id"] == card_id:
            return i
    return -1

# =======================
# 암기 콜백 (빠른 반응)
# =======================
def show_answer():
    st.session_state.show_back = True

def mark_correct():
    st.session_state.show_back = False
    st.session_state.index += 1
    st.rerun()

def mark_wrong(card_idx):
    st.session_state.cards[card_idx]["wrong_count"] += 1
    save_cards()
    st.session_state.show_back = False
    st.session_state.index += 1
    st.rerun()

def handle_enter(card_idx):
    # 문제 상태 → 정답 보기
    if not st.session_state.show_back:
        st.session_state.show_back = True
    # 정답 상태 → 다음 카드
    else:
        st.session_state.show_back = False
        st.session_state.index += 1

    # 입력값 비우기 (다시 Enter 받을 수 있게)
    st.session_state.enter_trigger = ""

def render_study_controls(card_idx, enter_only=True):
    if enter_only:
        if not st.session_state.show_back:
            st.button("Enter → 정답 보기", use_container_width=True, on_click=show_answer)
        else:
            st.button("Enter → 다음 카드", use_container_width=True, on_click=mark_correct)
    else:
        if not st.session_state.show_back:
            st.button("정답 보기", use_container_width=True, on_click=show_answer)
        else:
            c1, c2 = st.columns(2)
            with c1:
                st.button("✅ 맞음", use_container_width=True, on_click=mark_correct)
            with c2:
                st.button("❌ 틀림", use_container_width=True, on_click=mark_wrong, args=(card_idx,))

# =======================
# 상단 UI
# =======================
st.markdown(
    """
    <h2 style="text-align:center;">📘 임용 대비 암기 카드</h2>
    <p style="text-align:center; color:gray;">
    친구와 함께 실시간으로 공부하는 임용 스터디 웹앱
    </p>
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
# 카드 입력
# =======================
def save_card():
    c = st.session_state.input_category.strip()
    f = st.session_state.input_front.strip()
    b = st.session_state.input_back.strip()

    if c and f and b:
        st.session_state.cards.append({
            "id": uuid4().hex[:10],
            "category": c,
            "front": f,
            "back": b,
            "wrong_count": 0
        })
        save_cards()
        st.session_state.input_front = ""
        st.session_state.input_back = ""

if page == "➕ 카드 입력":
    st.subheader("카드 입력")

    st.text_input(
        "카테고리",
        key="input_category",
        placeholder="예: 전기전자, 교육과정"
    )
    st.text_input(
        "앞면 (문제)",
        key="input_front",
        placeholder="용어, 정의, 질문"
    )
    st.text_input(
        "뒷면 (정답)",
        key="input_back",
        placeholder="정답 입력 후 Enter",
        on_change=save_card
    )

    st.info(f"현재 카드 수 : {len(st.session_state.cards)} 장")


# =======================
# 암기 모드
# =======================
elif page == "🧠 암기 모드":
    st.subheader("암기 모드")

    if not st.session_state.cards:
        st.warning("먼저 카드를 입력하세요.")
    else:
        categories = sorted(set(c["category"] for c in st.session_state.cards))
        selected = st.selectbox("카테고리 선택", categories)

        col1, col2, col3 = st.columns(3)
        with col1:
            random_mode = st.checkbox("🔀 랜덤")
        with col2:
            wrong_only = st.checkbox("❗ 틀린 카드만")
        with col3:
            enter_only = st.checkbox("⌨️ Enter-only 모드", value=True)

        base = [c for c in st.session_state.cards if c["category"] == selected]
        if wrong_only:
            base = [c for c in base if c["wrong_count"] > 0]

        if not base:
            st.info("표시할 카드가 없습니다.")
        else:
            ids = [c["id"] for c in base]

            if random_mode:
                if (
                    not st.session_state.shuffled_ids
                    or set(st.session_state.shuffled_ids) != set(ids)
                ):
                    st.session_state.shuffled_ids = ids.copy()
                    random.shuffle(st.session_state.shuffled_ids)
                    st.session_state.index = 0
                    st.session_state.show_back = False
                order = st.session_state.shuffled_ids
            else:
                order = ids
                st.session_state.shuffled_ids = []

            cid = order[st.session_state.index % len(order)]
            idx = find_card_index_by_id(cid)
            card = st.session_state.cards[idx]

            label = "정답" if st.session_state.show_back else "문제"
            content = card["back"] if st.session_state.show_back else card["front"]

            st.markdown(
                f"""
                <div style="
                    max-width:600px;
                    margin:30px auto;
                    padding:50px;
                    background:#f9fafb;
                    border-radius:16px;
                    box-shadow:0 4px 12px rgba(0,0,0,0.08);
                    text-align:center;
                    font-size:24px;
                    line-height:1.6;
                ">
                    <b>[{label}]</b><br><br>{content}
                </div>
                """,
                unsafe_allow_html=True
            )

            # 👉 버튼 컨트롤 (Enter-only OFF일 때)
            if not enter_only:
                render_study_controls(idx, enter_only=False)

            # 👉 Enter-only 입력 (암기 모드 안에 있어야 함!)
            if enter_only:
                msg = st.chat_input(
                    "Enter만 누르면 다음 단계로 이동",
                    key="enter_box"
                )

                if msg is not None:
                    handle_enter(idx)
                    st.rerun()



# =======================
# 카드 관리
# =======================
elif page == "🛠️ 카드 관리":
    st.subheader("카드 관리")

    if not st.session_state.cards:
        st.info("카드가 없습니다.")
    else:
        categories = sorted(set(c["category"] for c in st.session_state.cards))
        cat = st.selectbox("카테고리", categories)

        cards = [c for c in st.session_state.cards if c["category"] == cat]
        ids = [c["id"] for c in cards]

        cid = st.selectbox(
            "카드 선택",
            ids,
            key="selected_card_id",
            format_func=lambda x: next(
                c["front"] for c in cards if c["id"] == x
            )
        )

        idx = find_card_index_by_id(st.session_state.selected_card_id)
        card = st.session_state.cards[idx]

        # 🔑 카드 변경 시 편집값 동기화
        if st.session_state.get("editing_card_id") != card["id"]:
            st.session_state.edit_front = card["front"]
            st.session_state.edit_back = card["back"]
            st.session_state.editing_card_id = card["id"]

        st.text_input("앞면", key="edit_front")
        st.text_input("뒷면", key="edit_back")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("💾 수정 저장"):
                card["front"] = st.session_state.edit_front
                card["back"] = st.session_state.edit_back
                save_cards()
                st.success("수정 완료")

        with col2:
            if st.button("🗑️ 카드 삭제"):
                st.session_state.cards.pop(idx)
                save_cards()
                st.rerun()

st.divider()
st.subheader("🧪 Supabase INSERT 테스트")

if st.button("DB에 테스트 카드 저장"):
    res = supabase.table("flashcard_app").insert({
        "category": "테스트",
        "front": "이게 보이면",
        "back": "Supabase 연결 성공",
        "wrong_count": 0
    }).execute()

    st.write(res.data)













