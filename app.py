import streamlit as st
import random
from supabase import create_client

# =======================
# Supabase 연결
# =======================
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_ANON_KEY = st.secrets["SUPABASE_ANON_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

TABLE = "flashcard_app"

# =======================
# 기본 설정
# =======================
st.set_page_config(page_title="임용 암기 카드", layout="centered")

# =======================
# DB 유틸
# =======================
def fetch_cards():
    """DB에서 카드 전체 불러오기"""
    res = supabase.table(TABLE).select("*").order("created_at", desc=False).execute()
    return res.data or []

def insert_card(category: str, front: str, back: str):
    supabase.table(TABLE).insert({
        "category": category,
        "front": front,
        "back": back,
        "wrong_count": 0
    }).execute()

def update_card(card_id: str, front: str, back: str, category: str | None = None):
    payload = {"front": front, "back": back}
    if category is not None:
        payload["category"] = category
    supabase.table(TABLE).update(payload).eq("id", card_id).execute()

def delete_card(card_id: str):
    supabase.table(TABLE).delete().eq("id", card_id).execute()

def increment_wrong(card_id: str, current_wrong: int):
    supabase.table(TABLE).update({"wrong_count": int(current_wrong) + 1}).eq("id", card_id).execute()

# =======================
# 세션 상태 초기화
# =======================
if "cards" not in st.session_state:
    st.session_state.cards = fetch_cards()

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

if "page" not in st.session_state:
    st.session_state.page = "➕ 카드 입력"

# =======================
# 유틸
# =======================
def sync_from_db(rerun: bool = False):
    st.session_state.cards = fetch_cards()
    if rerun:
        st.rerun()

def get_categories(cards):
    return sorted({c["category"] for c in cards})

def clamp_index(n):
    if n <= 0:
        st.session_state.index = 0
    else:
        st.session_state.index = st.session_state.index % n

# =======================
# 암기 콜백 (빠른 반응)
# =======================
def show_answer():
    st.session_state.show_back = True

def mark_correct():
    st.session_state.show_back = False
    st.session_state.index += 1
    st.rerun()

def mark_wrong(card_id: str, current_wrong: int):
    increment_wrong(card_id, current_wrong)
    # DB 반영 후 최신화
    st.session_state.show_back = False
    st.session_state.index += 1
    sync_from_db(rerun=True)

def handle_enter(card_id: str, current_wrong: int):
    # 문제 상태 → 정답 보기
    if not st.session_state.show_back:
        st.session_state.show_back = True
        st.rerun()
    # 정답 상태 → 다음 카드
    else:
        # Enter-only에서는 "맞음" 처리로 다음 카드
        st.session_state.show_back = False
        st.session_state.index += 1
        st.rerun()

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

# 페이지(탭 이동 안정화)
page = st.radio(
    "메뉴",
    ["➕ 카드 입력", "🧠 암기 모드", "🛠️ 카드 관리"],
    horizontal=True,
    key="page"
)

# 공통: DB 동기화 버튼
with st.container():
    c1, c2 = st.columns([1, 4])
    with c1:
        if st.button("🔄 DB 동기화", use_container_width=True, key="sync_btn"):
            sync_from_db(rerun=True)
    with c2:
        st.caption("여러 명이 동시에 입력/수정하면, 이 버튼으로 최신 데이터를 불러올 수 있어요.")

# =======================
# 1) 카드 입력 (DB INSERT)
# =======================
def save_card_to_db():
    c = st.session_state.input_category.strip()
    f = st.session_state.input_front.strip()
    b = st.session_state.input_back.strip()

    if c and f and b:
        insert_card(c, f, b)
        # 입력창 초기화
        st.session_state.input_front = ""
        st.session_state.input_back = ""
        # 최신화
        sync_from_db(rerun=True)

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
        on_change=save_card_to_db
    )

    st.info(f"현재 카드 수 : {len(st.session_state.cards)} 장")

# =======================
# 2) 암기 모드 (DB SELECT + wrong_count UPDATE)
# =======================
elif page == "🧠 암기 모드":
    st.subheader("암기 모드")

    if not st.session_state.cards:
        st.warning("먼저 카드를 입력하세요.")
    else:
        categories = get_categories(st.session_state.cards)
        if not categories:
            st.warning("카테고리가 없습니다. 카드를 먼저 입력하세요.")
            st.stop()

        selected = st.selectbox("카테고리 선택", categories, key="study_category")

        col1, col2, col3 = st.columns(3)
        with col1:
            random_mode = st.checkbox("🔀 랜덤", key="study_random")
        with col2:
            wrong_only = st.checkbox("❗ 틀린 카드만", key="study_wrong_only")
        with col3:
            enter_only = st.checkbox("⌨️ Enter-only 모드", value=True, key="study_enter_only")

        base = [c for c in st.session_state.cards if c["category"] == selected]
        if wrong_only:
            base = [c for c in base if int(c.get("wrong_count", 0)) > 0]

        if not base:
            st.info("표시할 카드가 없습니다.")
        else:
            ids = [c["id"] for c in base]

            if random_mode:
                # 랜덤 모드: 현재 base 집합과 다르면 새 셔플
                if (not st.session_state.shuffled_ids) or (set(st.session_state.shuffled_ids) != set(ids)):
                    st.session_state.shuffled_ids = ids.copy()
                    random.shuffle(st.session_state.shuffled_ids)
                    st.session_state.index = 0
                    st.session_state.show_back = False
                order = st.session_state.shuffled_ids
            else:
                order = ids
                st.session_state.shuffled_ids = []

            clamp_index(len(order))

            cid = order[st.session_state.index % len(order)]
            # base에서 해당 id 카드 찾기
            card = next((c for c in base if c["id"] == cid), None)
            if card is None:
                # 목록이 바뀌었을 때 안전 처리
                sync_from_db(rerun=True)

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

            # 컨트롤 영역
            if enter_only:
                # chat_input은 텍스트가 있어야 제출되므로,
                # "한 글자만 입력하고 Enter" 방식이 가장 안정적이야.
                msg = st.chat_input("한 글자 입력 후 Enter (문제→정답→다음)", key="enter_box")
                if msg is not None:
                    handle_enter(card["id"], int(card.get("wrong_count", 0)))
            else:
                if not st.session_state.show_back:
                    st.button("정답 보기", use_container_width=True, on_click=show_answer, key="btn_show_answer")
                else:
                    c1, c2 = st.columns(2)
                    with c1:
                        st.button("✅ 맞음", use_container_width=True, on_click=mark_correct, key="btn_correct")
                    with c2:
                        st.button(
                            "❌ 틀림",
                            use_container_width=True,
                            on_click=mark_wrong,
                            args=(card["id"], int(card.get("wrong_count", 0))),
                            key="btn_wrong"
                        )

# =======================
# 3) 카드 관리 (DB UPDATE/DELETE)
# =======================
elif page == "🛠️ 카드 관리":
    st.subheader("카드 관리")

    if not st.session_state.cards:
        st.info("카드가 없습니다.")
    else:
        categories = get_categories(st.session_state.cards)
        cat = st.selectbox("카테고리", categories, key="manage_category")

        cards = [c for c in st.session_state.cards if c["category"] == cat]
        if not cards:
            st.info("해당 카테고리에 카드가 없습니다.")
            st.stop()

        ids = [c["id"] for c in cards]

        cid = st.selectbox(
            "카드 선택",
            ids,
            key="selected_card_id",
            format_func=lambda x: next((c["front"] for c in cards if c["id"] == x), x)
        )

        card = next((c for c in cards if c["id"] == cid), None)
        if card is None:
            sync_from_db(rerun=True)

        # 카드 바뀔 때 편집값 동기화
        if st.session_state.get("editing_card_id") != card["id"]:
            st.session_state.edit_front = card["front"]
            st.session_state.edit_back = card["back"]
            st.session_state.edit_category = card["category"]
            st.session_state.editing_card_id = card["id"]

        st.text_input("카테고리", key="edit_category")
        st.text_input("앞면", key="edit_front")
        st.text_input("뒷면", key="edit_back")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("💾 수정 저장", key="btn_update"):
                new_cat = st.session_state.edit_category.strip()
                new_front = st.session_state.edit_front.strip()
                new_back = st.session_state.edit_back.strip()

                if not (new_cat and new_front and new_back):
                    st.error("카테고리/앞면/뒷면은 비울 수 없습니다.")
                else:
                    update_card(card["id"], new_front, new_back, category=new_cat)
                    st.success("수정 완료")
                    sync_from_db(rerun=True)

        with col2:
            if st.button("🗑️ 카드 삭제", key="btn_delete"):
                delete_card(card["id"])
                st.success("삭제 완료")
                sync_from_db(rerun=True)
















