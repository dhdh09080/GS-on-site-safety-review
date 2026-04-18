import streamlit as st
import pandas as pd
import plotly.express as px
import io
import json
from datetime import datetime
from supabase import create_client, Client

# 페이지 설정
st.set_page_config(page_title="GS건설 현장심사 시스템", layout="wide")

# ==========================================
# 🎨 장인 정신이 깃든 커스텀 CSS (디자인)
# ==========================================
st.markdown("""
    <style>
    /* 전체 배경색 살짝 조정 */
    .main { background-color: #f8f9fa; }
    
    /* 게시판 카드 스타일 */
    .stButton>button {
        width: 100%;
        border-radius: 10px;
        border: 1px solid #e0e0e0;
        background-color: white;
        padding: 15px 25px;
        transition: all 0.3s ease;
        text-align: left !important;
        box-shadow: 0 2px 4px rgba(0,0,0,0.02);
    }
    
    /* 게시판 카드 마우스 오버 효과 */
    .stButton>button:hover {
        border-color: #007bff;
        background-color: #f0f7ff;
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.08);
    }

    /* 배점 배지 스타일 */
    .badge-excellent { background-color: #d4edda; color: #155724; padding: 2px 8px; border-radius: 5px; font-weight: bold; }
    .badge-normal { background-color: #fff3cd; color: #856404; padding: 2px 8px; border-radius: 5px; font-weight: bold; }
    .badge-warning { background-color: #f8d7da; color: #721c24; padding: 2px 8px; border-radius: 5px; font-weight: bold; }
    
    /* 서브 정보 텍스트 */
    .sub-text { color: #6c757d; font-size: 0.85rem; }
    </style>
    """, unsafe_allow_html=True)

# 1. Supabase 연결 (기존과 동일)
@st.cache_resource
def init_connection():
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    return create_client(url, key)

try:
    supabase: Client = init_connection()
except:
    st.stop()

# 세션 상태 관리
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'current_user' not in st.session_state: st.session_state.current_user = ""
if 'admin_view' not in st.session_state: st.session_state.admin_view = "list"
if 'edit_target_id' not in st.session_state: st.session_state.edit_target_id = None

# 데이터 로드
def load_template():
    res = supabase.table("checklist_template").select("*").order("id").execute()
    return pd.DataFrame(res.data)

def load_results():
    res = supabase.table("audit_results").select("*").order("created_at", desc=True).execute()
    df = pd.DataFrame(res.data)
    if not df.empty:
        df = df.rename(columns={"site_name": "현장명", "site_type": "현장타입", "score": "최종점수"})
    return df

main_categories = ["1. 방침 수립, 조직상황, 성과평가, 내부심사", "2. 인력 및 예산", "3. 위험성평가 및 이행", "4. 종사자 의견 청취 및 개선 조치", "5. 안전보건교육", "6. 비상 시 대응 계획 및 사고관리", "7. 계획 수립", "8. 회의 및 점검", "9. 장비 안전관리 (건기법 포함)", "10. 보건관리"]

# ==========================================
# 사이드바
# ==========================================
st.sidebar.markdown(f"### 🏗️ GS건설 보건관리시스템")
menu = st.sidebar.radio("메뉴 바로가기", ["📊 전사 대시보드", "📅 심사 게시판"])

# ==========================================
# [페이지 1] 대시보드
# ==========================================
if menu == "📊 전사 대시보드":
    st.title("🏗️ 전사 현장 심사 통계")
    df = load_results()
    if not df.empty:
        col_m1, col_m2, col_m3 = st.columns(3)
        col_m1.metric("총 점검 현장", f"{len(df)}개")
        col_m2.metric("평균 점수", f"{round(df['최종점수'].mean(), 1)}점")
        col_m3.metric("최고 점수", f"{df['최종점수'].max()}점")
        
        st.write("---")
        fig = px.bar(df, x='현장명', y='최종점수', color='최종점수', color_continuous_scale='RdYlGn', title="현장별 심사 점수")
        st.plotly_chart(fig, use_container_width=True)

# ==========================================
# [페이지 2] 게시판 (장인 버전)
# ==========================================
elif menu == "📅 심사 게시판":
    if not st.session_state.logged_in:
        # 로그인 폼 생략 (기존과 동일)
        st.title("🔐 관리자 인증")
        with st.form("login_form"):
            user_id = st.text_input("아이디")
            user_pw = st.text_input("비밀번호", type="password")
            if st.form_submit_button("로그인"):
                passwords = st.secrets["passwords"]
                if user_id in passwords and passwords[user_id] == user_pw:
                    st.session_state.logged_in = True
                    st.session_state.current_user = user_id
                    st.rerun()
                else: st.error("정보 불일치")
    else:
        # 헤더
        c_head, c_user = st.columns([5, 1])
        with c_head: st.title("📋 현장 내부심사 게시판")
        with c_user: 
            st.write(f"👤 {st.session_state.current_user}")
            if st.button("로그아웃"): 
                st.session_state.logged_in = False
                st.rerun()

        st.divider()
        
        m_tab, t_tab = st.tabs(["📋 게시물 목록", "⚙️ 점수표 설정"])
        
        with m_tab:
            # ----------------------------------------
            # 뷰: 목록 리스트
            # ----------------------------------------
            if st.session_state.admin_view == "list":
                c_search, c_write = st.columns([4, 1])
                with c_search:
                    search_q = st.text_input("", placeholder="🔍 현장명 검색...", label_visibility="collapsed")
                with c_write:
                    if st.button("➕ 신규 심사 등록", type="primary", use_container_width=True):
                        st.session_state.admin_view = "create"
                        st.rerun()

                res_df = load_results()
                if not res_df.empty:
                    if search_q: res_df = res_df[res_df['현장명'].str.contains(search_q)]
                    
                    # 게시판 헤더
                    st.markdown("""
                        <div style='display: flex; padding: 10px 25px; background: #f1f3f5; border-radius: 8px; font-weight: bold; color: #495057; margin-bottom: 10px;'>
                            <div style='flex: 4;'>현장 제목</div>
                            <div style='flex: 1.5; text-align: center;'>심사 점수</div>
                            <div style='flex: 1; text-align: right;'>작성 정보</div>
                        </div>
                    """, unsafe_allow_html=True)

                    for _, row in res_df.iterrows():
                        score = row['최종점수']
                        # 뱃지 스타일 결정
                        if score >= 95: b_class, b_text = "excellent", "우수"
                        elif score >= 80: b_class, b_text = "normal", "보통"
                        else: b_class, b_text = "warning", "주의"

                        # 카드 형식의 게시물 한 줄
                        with st.container():
                            # 제목 클릭 버튼
                            if st.button(f"🏢 {row['현장명']}   |   분류: {row['현장타입']}", key=f"post_{row['id']}"):
                                st.session_state.edit_target_id = int(row['id'])
                                st.session_state.admin_view = "edit"
                                st.rerun()
                            
                            # 버튼 아래에 세부 정보를 절대 위치처럼 배치 (CSS 트릭)
                            st.markdown(f"""
                                <div style='display: flex; margin-top: -55px; margin-bottom: 25px; padding: 0 25px; pointer-events: none;'>
                                    <div style='flex: 4;'></div>
                                    <div style='flex: 1.5; text-align: center;'>
                                        <span class='badge-{b_class}'>{score}점 ({b_text})</span>
                                    </div>
                                    <div style='flex: 1; text-align: right;' class='sub-text'>
                                        {row['updated_by'] if 'updated_by' in row else '알수없음'}<br>{str(row['created_at'])[:10]}
                                    </div>
                                </div>
                            """, unsafe_allow_html=True)
                else:
                    st.info("내역이 없습니다.")

            # (생략: create, edit 뷰 - 기존 폼 코드와 동일하게 작동하되 '목록 돌아가기' 버튼 위치만 조정)
            elif st.session_state.admin_view == "create":
                if st.button("⬅️ 목록으로"): 
                    st.session_state.admin_view = "list"
                    st.rerun()
                st.subheader("📝 신규 심사 등록")
                # ... (이전 form 코드 동일)
                
            elif st.session_state.admin_view == "edit":
                if st.button("⬅️ 목록으로"): 
                    st.session_state.admin_view = "list"
                    st.rerun()
                # ... (이전 edit form 코드 동일)

        with t_tab:
            st.subheader("⚙️ 시스템 마스터 설정")
            # ... (이전 템플릿 설정 코드 동일)
