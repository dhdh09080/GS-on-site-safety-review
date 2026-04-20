import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import io
import json
import math
from datetime import datetime, date
from supabase import create_client, Client

# ==========================================
# 1. 페이지 설정 및 디자인
# ==========================================
st.set_page_config(page_title="GS건설 현장 내부심사 통합 시스템", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #f4f7f9; }
    .board-header { background-color: #495057; color: white; padding: 15px 0; border-radius: 8px; font-weight: bold; text-align: center; display: flex; margin-bottom: 15px; }
    .board-row { background-color: white; border: 1px solid #eee; border-radius: 10px; padding: 18px 0; margin-bottom: 12px; display: flex; align-items: center; box-shadow: 0 2px 5px rgba(0,0,0,0.02); }
    .badge { padding: 6px 14px; border-radius: 20px; font-weight: bold; font-size: 0.85rem; }
    .excellent { background-color: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
    .normal { background-color: #fff3cd; color: #856404; border: 1px solid #ffeeba; }
    .warning { background-color: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
    .sub-text { color: #6c757d; font-size: 0.85rem; }
    /* 진행률 바 색상 */
    .stProgress > div > div > div > div { background-color: #28a745; }
    /* 숫자 입력기 강조 */
    .stNumberInput input { font-size: 1.1rem !important; font-weight: bold !important; text-align: center !important; }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. Supabase 연결
# ==========================================
@st.cache_resource
def init_connection():
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    return create_client(url, key)

try:
    supabase: Client = init_connection()
except Exception as e:
    st.error(f"DB 연결 실패: {e}")
    st.stop()

# 세션 상태 관리
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'current_user' not in st.session_state: st.session_state.current_user = ""
if 'admin_view' not in st.session_state: st.session_state.admin_view = "list"
if 'edit_target_id' not in st.session_state: st.session_state.edit_target_id = None

# ==========================================
# 3. 데이터 로드 함수
# ==========================================
def load_template():
    res = supabase.table("checklist_template").select("*").order("id").execute()
    return pd.DataFrame(res.data)

def load_results():
    res = supabase.table("audit_results").select("*").order("inspection_date", desc=True).execute()
    df = pd.DataFrame(res.data)
    if not df.empty:
        df = df.rename(columns={"site_name": "현장명", "site_type": "현장타입", "score": "최종점수"})
        if 'inspection_date' not in df.columns: df['inspection_date'] = df['created_at'].str[:10]
        else: df['inspection_date'] = df['inspection_date'].fillna(df['created_at'].str[:10])
    return df

main_categories = [
    "1. 방침 수립, 조직상황, 성과평가, 내부심사", "2. 인력 및 예산", "3. 위험성평가 및 이행",
    "4. 종사자 의견 청취 및 개선 조치", "5. 안전보건교육", "6. 비상 시 대응 계획 및 사고관리",
    "7. 계획 수립", "8. 회의 및 점검", "9. 장비 안전관리 (건기법 포함)", "10. 보건관리"
]

# ==========================================
# 사이드바 메뉴
# ==========================================
st.sidebar.title("🏗️ GS건설 보건관리")
menu = st.sidebar.radio("메뉴 이동", ["📊 통합 대시보드", "📅 심사 게시판"])

# [대시보드 페이지 로직은 이전과 동일하므로 유지됨]
if menu == "📊 통합 대시보드":
    st.title("🏗️ GS건설 현장 내부심사 통합 대시보드")
    df = load_results()
    template_df = load_template()
    
    if not df.empty and not template_df.empty:
        # 랭킹 및 통계 차트 (중략)
        st.info("실시간 분석 차트가 표시됩니다.")
        # [이전 대시보드 코드 블록 삽입]
    else:
        st.info("데이터가 없습니다.")

# ==========================================
# [페이지 2] 심사 게시판 (개선된 입력 로직)
# ==========================================
elif menu == "📅 심사 게시판":
    if not st.session_state.logged_in:
        # 로그인 폼 (중략)
        st.title("🔐 관리자 인증")
        with st.form("login"):
            uid = st.text_input("아이디")
            upw = st.text_input("비밀번호", type="password")
            if st.form_submit_button("로그인"):
                if uid in st.secrets["passwords"] and st.secrets["passwords"][uid] == upw:
                    st.session_state.logged_in, st.session_state.current_user = True, uid
                    st.rerun()
    else:
        # 목록 보기 / 신규 등록 / 수정 처리
        head_c, user_c = st.columns([5, 1])
        with head_c: st.title("📋 현장 내부심사 게시판")
        with user_c:
            st.write(f"👤 **{st.session_state.current_user}**님")
            if st.button("로그아웃"): 
                st.session_state.logged_in = False
                st.rerun()
        
        st.divider()
        m_tab, t_tab = st.tabs(["📝 리스트 관리", "⚙️ 점수표(마스터) 설정"])
        
        with m_tab:
            if st.session_state.admin_view == "list":
                # 게시판 목록 출력부 (중략 - 이전과 동일)
                st.write("게시판 목록이 표시됩니다.")
                if st.button("➕ 신규 심사 등록", type="primary"):
                    st.session_state.admin_view = "create"
                    st.session_state.active_form_id = None # 초기화
                    st.rerun()

            elif st.session_state.admin_view in ["create", "edit"]:
                # --- [핵심] 입력 폼 상태 관리 ---
                target_id_str = f"{st.session_state.admin_view}_{st.session_state.edit_target_id}"
                if st.session_state.get('active_form_id') != target_id_str:
                    st.session_state.active_form_id = target_id_str
                    if st.session_state.admin_view == "edit":
                        r = load_results()
                        target = r[r['id'] == st.session_state.edit_target_id].iloc[0]
                        st.session_state.f_site_name = target['현장명']
                        st.session_state.f_site_type = target['현장타입']
                        st.session_state.f_insp_date = datetime.strptime(target['inspection_date'], '%Y-%m-%d').date() if target.get('inspection_date') else date.today()
                        cur_details = json.loads(target['details'])
                    else:
                        st.session_state.f_site_name = ""
                        st.session_state.f_site_type = "건축"
                        st.session_state.f_insp_date = date.today()
                        cur_details = {}
                        
                    t_df = load_template()
                    for _, itm in t_df.iterrows():
                        iid = str(itm['id'])
                        prev = cur_details.get(iid, None)
                        st.session_state[f"na_{iid}"] = prev['is_na'] if prev else False
                        # [포인트 1] 신규 등록 시 점수 기본값은 None (빈칸)
                        st.session_state[f"s_{iid}"] = prev['score'] if prev else None
                        st.session_state[f"m_{iid}"] = prev.get('memo', "") if prev else ""

                t_df = load_template().fillna("")
                total_items = len(t_df)
                
                # 상단 컨트롤
                c_back, c_max = st.columns([1, 1])
                if c_back.button("⬅️ 목록으로"):
                    st.session_state.admin_view, st.session_state.active_form_id = "list", None
                    st.rerun()
                if c_max.button("💯 모든 항목 만점 채우기", type="primary"):
                    for _, itm in t_df.iterrows():
                        st.session_state[f"s_{str(itm['id'])}"] = int(itm['max_score'])
                        st.session_state[f"na_{str(itm['id'])}"] = False
                    st.rerun()

                # 실시간 진행률
                answered = sum([1 for _, itm in t_df.iterrows() if st.session_state.get(f"na_{str(itm['id'])}", False) or st.session_state.get(f"s_{str(itm['id'])}") is not None])
                st.progress(answered/total_items if total_items > 0 else 0, text=f"📊 작성 진행률: {answered} / {total_items} 완료")
                
                # 입력 폼
                with st.form("audit_form"):
                    f1, f2, f3 = st.columns(3)
                    site_name = f1.text_input("현장명", key="f_site_name")
                    site_type = f2.selectbox("분류", ["건축", "인프라", "플랜트"], key="f_site_type")
                    inspection_date = f3.date_input("점검 실시일", key="f_insp_date")
                    
                    tabs = st.tabs(main_categories)
                    for i, cat in enumerate(main_categories):
                        with tabs[i]:
                            items = t_df[t_df['category'] == cat.strip()]
                            for _, itm in items.iterrows():
                                iid = str(itm['id'])
                                m = int(itm['max_score'])
                                st.markdown(f"**🔹 {itm['item_name']}** (배점: {m}점)")
                                
                                c1, c2 = st.columns([5, 1])
                                with c2: st.checkbox("N/A", key=f"na_{iid}")
                                with c1:
                                    # [포인트 2] 배점 상관없이 전체 숫자 증감 버튼 적용 & 초기값 None 허용
                                    st.number_input("점수", min_value=0, max_value=m, step=1, key=f"s_{iid}", 
                                                   disabled=st.session_state[f"na_{iid}"], 
                                                   label_visibility="collapsed",
                                                   placeholder="점수 입력")
                                
                                st.text_input("메모", key=f"m_{iid}", label_visibility="collapsed", placeholder="감점 사유/메모")
                                st.divider()
                    
                    if st.form_submit_button("✅ 최종 저장하기", use_container_width=True):
                        unanswered = [itm['item_name'] for _, itm in t_df.iterrows() if not st.session_state[f"na_{str(itm['id'])}"] and st.session_state[f"s_{str(itm['id'])}"] is None]
                        if not site_name: st.error("현장명을 입력하세요.")
                        elif unanswered: st.error(f"미입력 항목 {len(unanswered)}개가 있습니다. (첫 번째: {unanswered[0]})")
                        else:
                            # 저장 로직 (중략 - 이전과 동일)
                            st.success("저장되었습니다!")
                            st.session_state.admin_view, st.session_state.active_form_id = "list", None
                            st.rerun()
