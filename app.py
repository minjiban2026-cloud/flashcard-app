import streamlit as st
import random
import json
import re
import uuid
import httpx
import html
from datetime import datetime
from io import BytesIO
from supabase import create_client
from postgrest.exceptions import APIError
import pdfplumber

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
:root{
  --bg1:#f8fafc;
  --bg2:#eef2ff;
  --card:#ffffff;
  --text:#0f172a;
  --muted:#64748b;
  --line:#e5e7eb;
  --brand:#4f46e5;
  --brand2:#7c3aed;
  --shadow: 0 18px 40px rgba(2,6,23,0.10);
  --shadow2: 0 10px 22px rgba(2,6,23,0.08);
}

.stApp{
  background: radial-gradient(1200px 600px at 20% 0%, rgba(79,70,229,0.10), transparent 55%),
              radial-gradient(900px 520px at 90% 10%, rgba(124,58,237,0.10), transparent 55%),
              linear-gradient(180deg, var(--bg1) 0%, var(--bg2) 100%);
  font-family: -apple-system, BlinkMacSystemFont, "Apple SD Gothic Neo", sans-serif;
  color: var(--text);
}

.block-container{
  max-width: 760px;
  padding-top: 1.25rem;
  padding-bottom: 4rem;
}

.app-title{
  display:flex;
  align-items:center;
  justify-content:center;
  gap:10px;
  font-size: 26px;
  font-weight: 900;
  letter-spacing: -0.4px;
  margin: 0 0 0.7rem 0;
}

div[role="radiogroup"]{
  background: rgba(255,255,255,0.7);
  border: 1px solid rgba(229,231,235,0.8);
  border-radius: 999px;
  padding: 10px 14px;
  box-shadow: var(--shadow2);
}

.stTextInput input,
.stTextArea textarea,
.stSelectbox [data-baseweb="select"]{
  border-radius: 14px !important;
  border: 1px solid rgba(229,231,235,0.95) !important;
  box-shadow: 0 1px 0 rgba(2,6,23,0.03) !important;
}

.flashcard{
  background: var(--card);
  padding: 34px 34px;
  border-radius: 28px;
  box-shadow: var(--shadow);
  font-size: 22px;
  line-height: 1.7;
  text-align: center;
  white-space: pre-wrap;
  display:flex;
  flex-direction:column;
  justify-content:center;
  border: 1px solid rgba(229,231,235,0.65);
}

.flashcard-label{
  display:inline-flex;
  align-self:center;
  font-size: 12px;
  font-weight: 800;
  color: var(--brand);
  background: rgba(79,70,229,0.10);
  border: 1px solid rgba(79,70,229,0.18);
  padding: 4px 10px;
  border-radius: 999px;
  margin-bottom: 12px;
}

.progress{
  font-size: 12px;
  color: var(--muted);
  text-align: right;
  margin: 2px 2px 8px 2px;
}

.flashcard-image{
  width: 52%;
  max-width: 320px;
  min-width: 140px;
  margin: 16px auto 0 auto;
  display:block;
  border-radius: 14px;
  border: 1px solid rgba(229,231,235,0.9);
  box-shadow: 0 8px 18px rgba(2,6,23,0.08);
}

.flashcard-text{
  white-space: pre-wrap;
}

.stButton button{
  border-radius: 14px !important;
  padding: 10px 14px !important;
  font-weight: 800 !important;
  border: 1px solid rgba(229,231,235,0.95) !important;
  box-shadow: 0 10px 22px rgba(2,6,23,0.06);
}

div[data-testid="stFormSubmitButton"] > button{
  background: linear-gradient(135deg, var(--brand), var(--brand2)) !important;
  color: white !important;
  border: none !important;
}
div[data-testid="stFormSubmitButton"] > button:hover{
  opacity: 0.93;
  transform: translateY(-1px);
}

details{
  background: rgba(255,255,255,0.72);
  border: 1px solid rgba(229,231,235,0.85);
  border-radius: 16px;
  padding: 8px 12px;
  box-shadow: var(--shadow2);
}
details > summary{
  font-weight: 900;
  color: var(--text);
}

.stCaption{
  color: var(--muted) !important;
}
</style>
""", unsafe_allow_html=True)

# =======================
# DB 유틸
# =======================
def fetch_cards():
    return supabase.table(TABLE).select("*").order("created_at").execute().data or []

def fetch_cards_safe():
    try:
        return fetch_cards()
    except (httpx.ConnectError, APIError, Exception):
        return None

# ✅ 캐시(로딩 속도 개선 핵심)
@st.cache_data(ttl=60, show_spinner=False)
def cached_fetch_cards_safe():
    return fetch_cards_safe()

def clear_cards_cache():
    try:
        st.cache_data.clear()
    except Exception:
        pass

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

def manual_backup_now():
    try:
        cards = fetch_cards()
        content = json.dumps(cards, ensure_ascii=False, indent=2)
        filename = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}_manual.json"
        supabase.storage.from_(BACKUP_BUCKET).upload(
            filename,
            content.encode("utf-8"),
            file_options={"content-type": "application/json"},
        )
        return True
    except:
        return False

def safe_filename(name: str) -> str:
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

def upload_image_bytes(data: bytes, folder: str, filename: str, content_type="image/png"):
    """파일 업로드 위젯이 아니라 메모리상의 bytes를 그대로 Storage에 업로드할 때 사용"""
    try:
        safe_name = safe_filename(filename)
        path = f"{folder}/{uuid.uuid4().hex}_{safe_name}"
        supabase.storage.from_(IMAGE_BUCKET).upload(
            path,
            data,
            file_options={"content-type": content_type},
        )
        return supabase.storage.from_(IMAGE_BUCKET).get_public_url(path)
    except Exception:
        st.warning("⚠️ 이미지 업로드 실패 (파일명 또는 Storage 설정 문제)")
        return None

# =======================
# 📄 PDF → 암기카드 자동 추출
# - "암기카드 앱"류에서 내보낸 PDF 전용: 홀수 페이지=문제 4개(2x2),
#   짝수 페이지=답 4개(2x2, 좌우가 뒤바뀐 배치)를 가정
# - 앞면은 텍스트로, 뒷면은 표/그림이 섞여 있어도 안전하게
#   "답 카드 영역을 통째로 이미지로 캡처"해서 back_image_url로 사용
# =======================
_PDF_MIRROR_POS = {"TL": "TR", "TR": "TL", "BL": "BR", "BR": "BL"}

def _pdf_quadrant_blocks(page):
    W, H = page.width, page.height
    xmid, ymid = W / 2, H / 2
    words = page.extract_words(use_text_flow=False, keep_blank_chars=False)
    quads = {"TL": [], "TR": [], "BL": [], "BR": []}
    for w in words:
        cx = (w["x0"] + w["x1"]) / 2
        cy = (w["top"] + w["bottom"]) / 2
        key = ("T" if cy < ymid else "B") + ("L" if cx < xmid else "R")
        quads[key].append(w)
    blocks = {}
    for k, ws in quads.items():
        ws_sorted = sorted(ws, key=lambda w: (round(w["top"] / 3), w["x0"]))
        lines, cur_line, cur_top = [], [], None
        for w in ws_sorted:
            if cur_top is None or abs(w["top"] - cur_top) < 5:
                cur_line.append(w)
                cur_top = w["top"] if cur_top is None else cur_top
            else:
                lines.append(cur_line)
                cur_line = [w]
                cur_top = w["top"]
        if cur_line:
            lines.append(cur_line)
        line_texts = []
        for line in lines:
            line_sorted = sorted(line, key=lambda w: w["x0"])
            line_texts.append(" ".join(x["text"] for x in line_sorted))
        blocks[k] = line_texts
    return blocks

def _pdf_parse_block(lines):
    full = " ".join(lines)
    m = re.search(r"<\s*(.*?)\s*>", full)
    category = m.group(1).replace(" ", "") if m else None
    body_lines, header_done = [], False
    for line in lines:
        if not header_done:
            if ">" in line:
                header_done = True
                after = line.split(">", 1)[1].strip()
                if after:
                    body_lines.append(after)
                continue
            else:
                continue
        else:
            body_lines.append(line)
    return category, "\n".join(l for l in body_lines if l.strip()).strip()

def _pdf_crop_bbox(page, pos, margin=6):
    W, H = page.width, page.height
    xmid, ymid = W / 2, H / 2
    if pos == "TL":
        return (margin, margin, xmid - margin, ymid - margin)
    if pos == "TR":
        return (xmid + margin, margin, W - margin, ymid - margin)
    if pos == "BL":
        return (margin, ymid + margin, xmid - margin, H - margin)
    if pos == "BR":
        return (xmid + margin, ymid + margin, W - margin, H - margin)

def extract_cards_from_pdf(file_bytes: bytes):
    """PDF bytes -> [{category, front, back_image_bytes, src_pages}, ...]"""
    cards = []
    with pdfplumber.open(BytesIO(file_bytes)) as pdf:
        n = len(pdf.pages)
        for i in range(0, n, 2):
            if i + 1 >= n:
                break
            qpage, apage = pdf.pages[i], pdf.pages[i + 1]
            qblocks = _pdf_quadrant_blocks(qpage)
            for pos in ["TL", "TR", "BL", "BR"]:
                qlines = qblocks[pos]
                if not qlines:
                    continue
                qcat, qbody = _pdf_parse_block(qlines)
                if not qbody:
                    continue
                back_pos = _PDF_MIRROR_POS[pos]
                bbox = _pdf_crop_bbox(apage, back_pos)
                cropped = apage.crop(bbox)
                img = cropped.to_image(resolution=200)
                buf = BytesIO()
                img.original.save(buf, format="PNG")
                cards.append({
                    "category": qcat or "미분류",
                    "front": qbody,
                    "back_image_bytes": buf.getvalue(),
                    "src_pages": [i + 1, i + 2],
                    "include": True,
                })
    return cards

def insert_card(category, front, back, front_img, back_img):
    try:
        supabase.table(TABLE).insert({
            "category": category,
            "front": front,
            "back": back,
            "front_image_url": front_img,
            "back_image_url": back_img,
            "wrong_count": 0
        }).execute()
        auto_backup()
        clear_cards_cache()
        return True
    except Exception:
        st.error("⚠️ 카드 저장에 실패했습니다. (Supabase 연결/정책/RLS/네트워크 확인)")
        return False

def update_card(card_id, category, front, back, front_img, back_img):
    try:
        supabase.table(TABLE).update({
            "category": category,
            "front": front,
            "back": back,
            "front_image_url": front_img,
            "back_image_url": back_img,
        }).eq("id", card_id).execute()
        auto_backup()
        clear_cards_cache()
        return True
    except Exception:
        st.error("⚠️ 카드 수정에 실패했습니다. (Supabase 연결/정책/RLS/네트워크 확인)")
        return False

def delete_card(card_id):
    try:
        supabase.table(TABLE).delete().eq("id", card_id).execute()
        auto_backup()
        clear_cards_cache()
        return True
    except Exception:
        st.error("⚠️ 카드 삭제에 실패했습니다. (Supabase 연결/정책/RLS/네트워크 확인)")
        return False

def increment_wrong(card_id, current):
    try:
        supabase.table(TABLE).update({"wrong_count": int(current) + 1}).eq("id", card_id).execute()
        clear_cards_cache()
    except Exception:
        st.warning("⚠️ 오답 카운트 반영 실패 (네트워크/DB 상태 확인)")

def reset_wrong(card_id):
    try:
        supabase.table(TABLE).update({"wrong_count": 0}).eq("id", card_id).execute()
        clear_cards_cache()
    except Exception:
        st.warning("⚠️ 오답 초기화 실패 (네트워크/DB 상태 확인)")

def reset_wrong_by_category(category):
    try:
        supabase.table(TABLE).update({"wrong_count": 0}).eq("category", category).execute()
        clear_cards_cache()
    except Exception:
        st.warning("⚠️ 카테고리 오답 초기화 실패 (네트워크/DB 상태 확인)")

def delete_category(category: str):
    try:
        supabase.table(TABLE).delete().eq("category", category).execute()
        auto_backup()
        clear_cards_cache()
        return True
    except Exception:
        st.error("⚠️ 카테고리 삭제에 실패했습니다. (Supabase 연결/정책/RLS/네트워크 확인)")
        return False

def merge_category(from_cat: str, to_cat: str):
    try:
        supabase.table(TABLE).update({"category": to_cat}).eq("category", from_cat).execute()
        auto_backup()
        clear_cards_cache()
        return True
    except Exception:
        st.error("⚠️ 카테고리 병합에 실패했습니다. (Supabase 연결/정책/RLS/네트워크 확인)")
        return False

def list_backups(limit=30):
    try:
        items = supabase.storage.from_(BACKUP_BUCKET).list(path="")
        names = []
        for it in items or []:
            nm = it.get("name")
            if nm and nm.lower().endswith(".json") and nm.startswith("backup_"):
                names.append(nm)
        names.sort(reverse=True)
        return names[:limit]
    except Exception:
        return []

def download_backup_json(filename: str):
    try:
        data = supabase.storage.from_(BACKUP_BUCKET).download(filename)
        raw = data.read() if hasattr(data, "read") else data
        obj = json.loads(raw.decode("utf-8"))
        return obj if isinstance(obj, list) else None
    except Exception:
        return None

def restore_from_backup(filename: str):
    backup_cards = download_backup_json(filename)
    if backup_cards is None:
        st.error("⚠️ 백업 파일을 읽을 수 없습니다. (형식/권한/파일 손상)")
        return False

    cleaned = []
    for c in backup_cards:
        if isinstance(c, dict) and ("category" in c) and ("front" in c) and ("back" in c):
            cleaned.append(c)

    if not cleaned:
        st.error("⚠️ 백업 데이터가 비어있거나 유효한 카드가 없습니다. 복구를 중단했습니다.")
        return False

    try:
        current = fetch_cards_safe()
        if current is None:
            st.error("⚠️ 현재 DB를 읽지 못했습니다. (Supabase 상태 확인)")
            return False

        ids = [c.get("id") for c in current if c.get("id") is not None]
        if ids:
            chunk = 200
            for i in range(0, len(ids), chunk):
                batch = ids[i:i+chunk]
                supabase.table(TABLE).delete().in_("id", batch).execute()

        chunk2 = 200
        for i in range(0, len(cleaned), chunk2):
            supabase.table(TABLE).insert(cleaned[i:i+chunk2]).execute()

        auto_backup()
        clear_cards_cache()
        return True

    except Exception:
        st.error("⚠️ 복구 중 오류가 발생했습니다. (RLS/권한/DB 스키마/네트워크 확인)")
        return False

# =======================
# ✅ 렌더링 전용 정리 (DB 영향 없음)
# - 기존 카드 데이터는 절대 수정하지 않음
# - 화면에 보여줄 때만 '</div>' 같은 찌꺼기 줄을 제거
# - HTML 깨짐 방지(escape) + 줄바꿈 유지(<br>)
# =======================
def render_safe_text(s: str) -> str:
    s = s or ""
    lines = s.splitlines()
    cleaned = []
    for line in lines:
        t = line.strip().lower()
        if t in ("</div>", "<div>"):
            continue
        cleaned.append(line)
    s2 = "\n".join(cleaned)
    return html.escape(s2).replace("\n", "<br>")

# =======================
# 세션 상태 (핵심 유지)
# =======================
if "supabase_ok" not in st.session_state:
    st.session_state.supabase_ok = True

if "cards" not in st.session_state:
    with st.spinner("Supabase에서 카드 불러오는 중..."):
        data = cached_fetch_cards_safe()
    st.session_state.cards = data if data is not None else []
    st.session_state.supabase_ok = (data is not None)

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

if "study_filter_sig" not in st.session_state:
    st.session_state.study_filter_sig = None

# =======================
# 공통
# =======================
def sync():
    # 변경 직후에는 캐시를 비우고 최신을 받는다
    clear_cards_cache()
    with st.spinner("동기화 중..."):
        data = cached_fetch_cards_safe()
    if data is None:
        st.session_state.supabase_ok = False
        st.session_state.cards = []
        st.session_state.study_cards = None
        return
    st.session_state.cards = data
    st.session_state.study_cards = None
    st.session_state.supabase_ok = True

def categories(cards):
    return sorted({c["category"] for c in cards if c.get("category") is not None})

def count_by_category(cards, category):
    return sum(1 for c in cards if c.get("category") == category)

# =======================
# 헤더 & Supabase 연결 실패 방어막
# =======================
st.markdown('<div class="app-title">📘 임용 대비 암기 카드</div>', unsafe_allow_html=True)

if not st.session_state.supabase_ok:
    st.error("⚠️ Supabase 프로젝트가 잠들어 있거나(Paused), 깨는 중이거나 네트워크 문제로 연결에 실패했습니다.\n\nSupabase에서 Resume 후 아래 버튼을 눌러주세요.")
    if st.button("🔄 다시 시도"):
        clear_cards_cache()
        with st.spinner("다시 시도 중..."):
            data = cached_fetch_cards_safe()
        if data is not None:
            st.session_state.cards = data
            st.session_state.supabase_ok = True
        st.rerun()
    st.stop()

# =======================
# 메뉴
# =======================
page = st.radio("", ["➕ 카드 입력", "🧠 암기 모드", "🛠️ 카드 관리", "📄 PDF 가져오기"], horizontal=True)

# =======================
# 카드 저장 (form 대응)
# =======================
def save_card_fast():
    cat = (st.session_state.get("input_category") or "").strip()
    front = (st.session_state.get("input_front") or "").strip()
    back = (st.session_state.get("input_back") or "").strip()

    # ✅ 원래처럼: 뒷면 텍스트가 없으면 저장 불가
    if not (cat and front and back):
        st.warning("카테고리/앞면/뒷면을 모두 입력해야 저장됩니다.")
        return

    front_file = st.session_state.get(f"input_front_image_{st.session_state.upload_key}")
    back_file = st.session_state.get(f"input_back_image_{st.session_state.upload_key}")

    front_img = upload_image(front_file, "front") if front_file else None
    back_img = upload_image(back_file, "back") if back_file else None

    ok = insert_card(cat, front, back, front_img, back_img)
    if not ok:
        return

    st.session_state.upload_key += 1
    st.session_state.input_front = ""
    st.session_state.input_back = ""
    sync()
    st.rerun()

# =======================
# 1️⃣ 카드 입력
# =======================
if page == "➕ 카드 입력":
    st.text_input("카테고리", key="input_category", placeholder="예: 전기전자")

    with st.form("card_input_form", clear_on_submit=False):
        st.text_input("앞면", key="input_front", placeholder="문제 또는 개념")
        st.text_area("뒷면 (줄바꿈 가능)", key="input_back", height=160, placeholder="Enter = 줄바꿈")

        st.file_uploader("앞면 이미지 (선택)", ["png", "jpg", "jpeg"],
                         key=f"input_front_image_{st.session_state.upload_key}")
        st.file_uploader("뒷면 이미지 (선택)", ["png", "jpg", "jpeg"],
                         key=f"input_back_image_{st.session_state.upload_key}")

        st.form_submit_button("💾 저장", on_click=save_card_fast)

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
    cat_list = categories(cards)
    if not cat_list:
        st.warning("카테고리가 없습니다. 카드 입력에서 카테고리를 먼저 추가하세요.")
        st.stop()

    cat = st.selectbox("카테고리", cat_list)

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

    q = st.text_input(
        "🔎 검색",
        key="study_search_q",
        placeholder="앞면/뒷면에서 키워드로 찾기 (예: CRC, 오스테나이트, 서브넷)",
    ).strip().lower()

    filter_sig = (cat, bool(random_mode), bool(wrong_only), bool(enter_only), bool(recall_mode), q)
    if st.session_state.study_filter_sig is None:
        st.session_state.study_filter_sig = filter_sig
    elif st.session_state.study_filter_sig != filter_sig:
        st.session_state.study_filter_sig = filter_sig
        st.session_state.index = 0
        st.session_state.show_back = False
        st.session_state.order = []

    base = [c for c in cards if c.get("category") == cat]
    if wrong_only:
        base = [c for c in base if int(c.get("wrong_count") or 0) > 0]

    if q:
        base = [
            c for c in base
            if (q in (c.get("front") or "").lower()) or (q in (c.get("back") or "").lower())
        ]

    if not base:
        st.info("표시할 카드가 없습니다." if not q else "검색 결과가 없습니다. 다른 키워드로 시도해보세요.")
        st.stop()

    ids = [c["id"] for c in base if c.get("id") is not None]
    if not ids:
        st.info("표시할 카드가 없습니다.")
        st.stop()

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

    st.session_state.index = st.session_state.index % max(len(order), 1)

    cid = order[st.session_state.index % len(order)]
    try:
        card = next(c for c in base if c["id"] == cid)
    except StopIteration:
        st.session_state.index = 0
        st.session_state.show_back = False
        st.session_state.order = []
        st.rerun()

    if recall_mode:
        first_label, second_label = "설명", "개념"
        first_text, second_text = card.get("back") or "", card.get("front") or ""
        first_img, second_img = card.get("back_image_url"), card.get("front_image_url")
    else:
        first_label, second_label = "문제", "정답"
        first_text, second_text = card.get("front") or "", card.get("back") or ""
        first_img, second_img = card.get("front_image_url"), card.get("back_image_url")

    label = second_label if st.session_state.show_back else first_label
    text = second_text if st.session_state.show_back else first_text
    img = second_img if st.session_state.show_back else first_img

    safe_text = render_safe_text(text)

    st.markdown(
        f'<div class="progress">{st.session_state.index + 1} / {len(order)}</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        f"""
        <div class="flashcard">
            <div class="flashcard-label">{html.escape(label)}</div>
            <div class="flashcard-text">{safe_text}</div>
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
                    increment_wrong(card["id"], int(card.get("wrong_count") or 0))
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
    if not st.session_state.cards:
        st.warning("카드가 없습니다. 먼저 카드 입력에서 카드를 추가하세요.")
        st.stop()

    cat_list = categories(st.session_state.cards)
    if not cat_list:
        st.warning("카테고리가 없습니다. 카드 입력에서 카테고리를 먼저 추가하세요.")
        st.stop()

    cat = st.selectbox("카테고리", cat_list)
    cards = [c for c in st.session_state.cards if c.get("category") == cat]

    if not cards:
        st.info("이 카테고리에 카드가 없습니다.")
        st.stop()

    card = st.selectbox("카드 선택", cards, format_func=lambda c: (c.get("front") or "(앞면 없음)"))

    st.markdown("### 🖼️ 현재 등록된 이미지")
    p1, p2 = st.columns(2)
    with p1:
        st.caption(f"앞면 이미지: {'✅ 있음' if card.get('front_image_url') else '❌ 없음'}")
        if card.get("front_image_url"):
            st.image(card["front_image_url"], use_container_width=True)
    with p2:
        st.caption(f"뒷면 이미지: {'✅ 있음' if card.get('back_image_url') else '❌ 없음'}")
        if card.get("back_image_url"):
            st.image(card["back_image_url"], use_container_width=True)

    new_cat = st.text_input("카테고리", card.get("category") or "")
    new_front = st.text_input("앞면", card.get("front") or "")
    new_back = st.text_area("뒷면 (줄바꿈 가능)", card.get("back") or "", height=160)

    front_file = st.file_uploader("앞면 이미지 교체", ["png", "jpg", "jpeg"])
    back_file = st.file_uploader("뒷면 이미지 교체", ["png", "jpg", "jpeg"])

    c1, c2 = st.columns(2)
    with c1:
        if st.button("💾 수정"):
            front_img = upload_image(front_file, "front") or card.get("front_image_url")
            back_img = upload_image(back_file, "back") or card.get("back_image_url")
            ok = update_card(card["id"], new_cat, new_front, new_back, front_img, back_img)
            if ok:
                sync()
                st.success("수정 완료")

    with c2:
        if st.button("🗑️ 삭제"):
            ok = delete_card(card["id"])
            if ok:
                sync()
                st.success("삭제 완료")

    st.markdown("---")
    with st.expander("🗂️ 카테고리 관리 (삭제/병합)", expanded=False):
        st.caption("카테고리는 별도 테이블이 아니라 카드의 category 값입니다. 삭제/병합은 카드에 직접 반영됩니다.")

        all_cats = categories(st.session_state.cards)
        if not all_cats:
            st.info("카테고리가 없습니다.")
            st.stop()

        target_cat = st.selectbox("대상 카테고리", all_cats, key="cat_manage_target")
        target_count = count_by_category(st.session_state.cards, target_cat)
        st.caption(f"선택 카테고리 카드 수: {target_count}개")

        st.markdown("#### 🔀 카테고리 병합(이름 변경)")
        to_cat = st.text_input("병합/변경할 카테고리 이름", key="cat_merge_to", placeholder="예: 전기전자").strip()
        merge_confirm = st.checkbox("병합을 실행합니다. (대상 카테고리의 모든 카드 category 값이 변경됩니다)", key="cat_merge_confirm")

        if st.button("🔀 병합 실행"):
            if not merge_confirm:
                st.warning("병합 동의 체크박스를 먼저 선택하세요.")
                st.stop()
            if not to_cat:
                st.warning("변경할 카테고리 이름을 입력하세요.")
                st.stop()
            if to_cat == target_cat:
                st.info("대상과 동일한 이름입니다. 변경할 필요가 없습니다.")
                st.stop()

            manual_backup_now()
            ok = merge_category(target_cat, to_cat)
            if ok:
                sync()
                st.success(f"병합 완료: '{target_cat}' → '{to_cat}'")
                st.rerun()

        st.markdown("#### 🗑️ 카테고리 삭제(해당 카테고리 카드 전체 삭제)")
        st.caption("⚠️ 이 작업은 되돌리기 어렵습니다. 실행 전에 자동으로 수동 백업을 1회 생성합니다.")
        del_confirm1 = st.checkbox("이 카테고리를 삭제하면 해당 카드가 모두 삭제됨을 이해했습니다.", key="cat_del_confirm1")

        del_phrase = f"DELETE {target_cat}"
        st.code(del_phrase)

        del_confirm2 = st.text_input(
            "확인을 위해 위 문구를 정확히 입력하세요:",
            value="",
            key="cat_del_confirm2",
            placeholder=del_phrase
        )

        if st.button("🗑️ 카테고리 삭제 실행"):
            if not del_confirm1:
                st.warning("체크박스를 먼저 선택하세요.")
                st.stop()
            if del_confirm2.strip() != del_phrase:
                st.warning("확인 문구가 정확하지 않습니다. 위 문구를 그대로 입력하세요.")
                st.stop()

            manual_backup_now()
            ok = delete_category(target_cat)
            if ok:
                sync()
                st.success(f"삭제 완료: '{target_cat}' 카테고리의 카드가 모두 삭제되었습니다.")
                st.rerun()

    st.markdown("---")
    with st.expander("♻️ 백업 복구 (전체 덮어쓰기)", expanded=False):
        st.caption("⚠️ 선택한 백업으로 DB의 카드가 **전체 교체**됩니다. (현재 데이터는 삭제 후 백업 데이터로 복원)")

        b1, b2 = st.columns(2)
        with b1:
            if st.button("📦 지금 상태 수동 백업 만들기"):
                ok = manual_backup_now()
                if ok:
                    st.success("수동 백업 생성 완료")
                else:
                    st.error("수동 백업 생성 실패 (Storage/권한/네트워크 확인)")

        with b2:
            if st.button("🔄 백업 목록 새로고침"):
                st.rerun()

        backups = list_backups(limit=30)
        if not backups:
            st.info("백업 파일이 없습니다. (auto_backup이 동작했는지, Storage 버킷/권한 확인)")
            st.stop()

        selected = st.selectbox("복구할 백업 선택", backups, key="restore_backup_file")

        c3, c4 = st.columns(2)
        with c3:
            if st.button("👀 백업 미리보기"):
                preview = download_backup_json(selected)
                if preview is None:
                    st.error("백업 미리보기 실패 (파일 손상/권한/형식 문제)")
                else:
                    st.success(f"카드 {len(preview)}개")
                    st.json(preview[:3])

        with c4:
            confirm = st.checkbox("이 백업으로 복구(전체 덮어쓰기)에 동의합니다.", key="restore_confirm")

        if st.button("🚨 복구 실행", disabled=not confirm):
            with st.spinner("복구 중..."):
                ok = restore_from_backup(selected)
            if ok:
                sync()
                st.success("✅ 복구 완료! (DB가 백업 상태로 교체되었습니다)")
                st.rerun()

# =======================
# 4️⃣ PDF 가져오기
# =======================
elif page == "📄 PDF 가져오기":
    st.caption("문제 4개(2x2) → 답 4개(2x2) 순서로 페이지가 이어지는 '암기카드' PDF를 업로드하면 "
               "카드를 자동으로 추출합니다. 앞면은 텍스트로, 뒷면은 표/그림이 섞여 있어도 안전하도록 "
               "이미지로 캡처해서 넣습니다.")

    if "pdf_cards" not in st.session_state:
        st.session_state.pdf_cards = None
    if "pdf_review_idx" not in st.session_state:
        st.session_state.pdf_review_idx = 0

    pdf_file = st.file_uploader("암기카드 PDF 업로드", ["pdf"], key="pdf_upload")

    if st.button("🔍 PDF 분석하기", disabled=(pdf_file is None)):
        with st.spinner("PDF에서 카드를 추출하는 중... (페이지가 많으면 시간이 걸릴 수 있어요)"):
            try:
                extracted = extract_cards_from_pdf(pdf_file.getvalue())
            except Exception:
                st.error("⚠️ PDF 분석에 실패했습니다. 파일 형식이나 레이아웃을 확인해주세요.")
                extracted = None
        if extracted is not None:
            st.session_state.pdf_cards = extracted
            st.session_state.pdf_review_idx = 0
            st.success(f"총 {len(extracted)}개의 카드를 찾았습니다. 아래에서 확인 후 저장하세요.")

    cards = st.session_state.pdf_cards
    if cards:
        st.markdown("---")
        included = sum(1 for c in cards if c["include"])
        st.caption(f"📚 추출된 카드 {len(cards)}개 · 저장 대상으로 선택된 카드 {included}개")

        # 카테고리별 개수 요약
        with st.expander("카테고리별 개수 보기", expanded=False):
            cat_counts = {}
            for c in cards:
                cat_counts[c["category"]] = cat_counts.get(c["category"], 0) + 1
            for cat, cnt in sorted(cat_counts.items(), key=lambda x: -x[1]):
                st.write(f"- {cat}: {cnt}개")

        # 한 장씩 확인하는 네비게이터
        st.session_state.pdf_review_idx = st.session_state.pdf_review_idx % len(cards)
        idx = st.session_state.pdf_review_idx
        card = cards[idx]

        st.markdown(f"**카드 {idx + 1} / {len(cards)}** (PDF {card['src_pages'][0]}-{card['src_pages'][1]}페이지)")

        card["category"] = st.text_input("카테고리", value=card["category"], key=f"pdf_cat_{idx}")
        card["front"] = st.text_area("앞면(문제)", value=card["front"], height=100, key=f"pdf_front_{idx}")
        st.caption("뒷면(답) — PDF에서 캡처한 이미지 그대로 저장됩니다")
        st.image(card["back_image_bytes"], use_container_width=True)
        card["include"] = st.checkbox("✅ 이 카드를 저장 대상에 포함", value=card["include"], key=f"pdf_inc_{idx}")

        nav1, nav2, nav3 = st.columns(3)
        with nav1:
            if st.button("◀ 이전 카드"):
                st.session_state.pdf_review_idx -= 1
                st.rerun()
        with nav2:
            if st.button("이 카드 제외하고 다음 ▶"):
                card["include"] = False
                st.session_state.pdf_review_idx += 1
                st.rerun()
        with nav3:
            if st.button("다음 카드 ▶"):
                st.session_state.pdf_review_idx += 1
                st.rerun()

        st.markdown("---")
        st.warning(f"'저장 실행'을 누르면 선택된 {included}개 카드가 Supabase에 실제로 추가됩니다.")
        if st.button("💾 선택한 카드 전체 저장", type="primary"):
            to_save = [c for c in cards if c["include"]]
            progress = st.progress(0, text="저장 중...")
            saved, failed = 0, 0
            for n, c in enumerate(to_save, start=1):
                back_url = upload_image_bytes(
                    c["back_image_bytes"], "back", f"pdf_{c['src_pages'][0]}_{c['src_pages'][1]}.png"
                )
                ok = insert_card(c["category"], c["front"], "(PDF 이미지 참고)", None, back_url)
                if ok:
                    saved += 1
                else:
                    failed += 1
                progress.progress(n / len(to_save), text=f"저장 중... ({n}/{len(to_save)})")
            progress.empty()
            st.success(f"✅ {saved}개 저장 완료" + (f" · ⚠️ {failed}개 실패" if failed else ""))
            st.session_state.pdf_cards = None
            sync()
            st.rerun()
