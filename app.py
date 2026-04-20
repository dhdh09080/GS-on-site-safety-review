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
    .incomplete { background-color: #e9ecef; color: #495057; border: 1px solid #dee2e6; }
    .missing-tag { color: #d63384; font-size: 0.75rem; margin-top: 4px; font-weight: 500; }
    .sub-text { color: #6c757d; font-size: 0.85rem; }
    .stProgress > div > div > div > div { background-color: #28a745; }
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

if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'current_user' not in st.session_state: st.session_state.current_user = ""
if 'admin_view' not in st.session_state: st.session_state.admin_view = "list"
if 'edit_target_id' not in st.session_state: st.session_state.edit_target_id = None

# ==========================================
# 3. 데이터 로드 및 가공
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

st.sidebar.title("🏗️ GS건설 보건관리")
menu = st.sidebar.radio("메뉴 이동", ["📊 통합 대시보드", "📅 심사 게시판"])

# [대시보드 페이지 로직 동일하므로 중략]
if menu == "📊 통합 대시보드":
    st.title("🏗️ GS건설 현장 내부심사 통합 대시보드")
    df = load_results()
    # (기존 대시보드 코드 동일하게 유지)

# ==========================================
# [페이지 2] 심사 게시판 (미입력 알림 강화)
# ==========================================
elif menu == "📅 심사 게시판":
    if not st.session_state.logged_in:
        st.title("🔐 관리자 인증")
        with st.form("login"):
            uid = st.text_input("아이디")
            upw = st.text_input("비밀번호", type="password")
            if st.form_submit_button("로그인"):
                if uid in st.secrets["passwords"] and st.secrets["passwords"][uid] == upw:
                    st.session_state.logged_in, st.session_state.current_user = True, uid
                    st.rerun()
    else:
        head_c, user_c = st.columns([5, 1])
        with head_c: st.title("📋 현장 내부심사 게시판")
        with user_c:
            if st.button("로그아웃"): 
                st.session_state.logged_in = False
                st.rerun()
        
        st.divider()
        m_tab, t_tab = st.tabs(["📝 리스트 관리", "⚙️ 점수표(마스터) 설정"])
        
        with m_tab:
            # ---------------------------------------------------------
            # 게시판 목록 (미입력 추적 기능 포함)
            # ---------------------------------------------------------
            if st.session_state.admin_view == "list":
                if st.session_state.get('flash_msg'):
                    st.info(st.session_state.flash_msg)
                    st.session_state.flash_msg = "" 
                
                col_s, col_a = st.columns([3, 1])
                sq = col_s.text_input("검색", placeholder="현장명 검색...", label_visibility="collapsed")
                if col_a.button("➕ 신규 심사 등록 (방 만들기)", type="primary", use_container_width=True):
                    st.session_state.admin_view = "create"
                    st.rerun()
                
                res_df = load_results()
                t_df = load_template()
                
                if not res_df.empty:
                    if sq: res_df = res_df[res_df['현장명'].str.contains(sq)]
                    
                    st.markdown("<div class='board-header'><div style='flex:3;'>현장 제목 및 미입력 현황</div><div style='flex:1;'>분류</div><div style='flex:1.5;'>입력 상태</div><div style='flex:1.5;'>점검 일자</div><div style='flex:1.2;'>관리</div></div>", unsafe_allow_html=True)
                    
                    for _, row in res_df.iterrows():
                        details_dict = json.loads(row['details']) if row['details'] else {}
                        
                        # [미입력 분석 로직]
                        missing_parts = []
                        total_q = len(t_df)
                        answered_q = 0
                        
                        if not t_df.empty:
                            for _, itm in t_df.iterrows():
                                iid = str(itm['id'])
                                data = details_dict.get(iid)
                                if data and (data.get('is_na') or data.get('score') is not None):
                                    answered_q += 1
                            
                            # 탭별 미입력 체크 (간소화)
                            for cat in main_categories:
                                cat_items = t_df[t_df['category'] == cat.strip()]
                                if not cat_items.empty:
                                    cat_answered = True
                                    for _, ci in cat_items.iterrows():
                                        cid = str(ci['id'])
                                        if not details_dict.get(cid) or (not details_dict[cid].get('is_na') and details_dict[cid].get('score') is None):
                                            cat_answered = False
                                            break
                                    if not cat_answered:
                                        # 1. 방침 수립 -> 방침수립
                                        missing_parts.append(cat.split('.')[1].strip())

                        progress_pct = int((answered_q / total_q) * 100) if total_q > 0 else 0
                        
                        # 배지 색상 결정
                        sc = row['최종점수']
                        if progress_pct == 0: b_c, b_t = "incomplete", "입력대기"
                        elif progress_pct < 100: b_c, b_t = "warning", f"작성중 ({progress_pct}%)"
                        else:
                            if sc >= 95: b_c, b_t = "excellent", f"{sc}점 (완료)"
                            elif sc >= 80: b_c, b_t = "normal", f"{sc}점 (완료)"
                            else: b_c, b_t = "warning", f"{sc}점 (완료)"

                        with st.container():
                            r1, r2, r3, r4, r5 = st.columns([3, 1, 1.5, 1.5, 1.2])
                            
                            # 1. 현장 제목 및 미입력 안내
                            with r1:
                                if st.button(f"🏢 {row['현장명']}", key=f"t_{row['id']}", use_container_width=True):
                                    st.session_state.edit_target_id, st.session_state.admin_view = int(row['id']), "edit"
                                    st.rerun()
                                if missing_parts and progress_pct < 100:
                                    st.markdown(f"<div class='missing-tag'>⚠️ 미입력: {', '.join(missing_parts[:3])}{'...' if len(missing_parts)>3 else ''}</div>", unsafe_allow_html=True)
                            
                            r2.markdown(f"<div style='text-align:center; padding-top:12px;'>{row['현장타입']}</div>", unsafe_allow_html=True)
                            r3.markdown(f"<div style='text-align:center; padding-top:8px;'><span class='badge {b_c}'>{b_t}</span></div>", unsafe_allow_html=True)
                            r4.markdown(f"<div style='text-align:center;' class='sub-text'><b>{row['inspection_date']}</b><br>({row.get('updated_by','-')})</div>", unsafe_allow_html=True)
                            
                            with r5:
                                ec, dc = st.columns(2)
                                if ec.button("✏️", key=f"e_{row['id']}"):
                                    st.session_state.edit_target_id, st.session_state.admin_view = int(row['id']), "edit"
                                    st.rerun()
                                if dc.button("🗑️", key=f"d_{row['id']}"):
                                    supabase.table("audit_results").delete().eq("id", row['id']).execute()
                                    st.rerun()
                            st.markdown("<div style='border-bottom:1px solid #eee;'></div>", unsafe_allow_html=True)

            # [신규 방 만들기 / 심사 수정 입력 로직은 기존 기능 유지]
            elif st.session_state.admin_view == "create":
                # (기존 코드와 동일)
                st.subheader("새로운 심사 방 생성")
                # ...
                
            elif st.session_state.admin_view == "edit":
                # (기존의 실시간 진행률 + 탭별 일괄 해당없음 기능 포함)
                st.subheader("심사 데이터 입력")
                # ...
