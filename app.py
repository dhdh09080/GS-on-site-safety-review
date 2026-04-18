import streamlit as st
import pandas as pd
import plotly.express as px
import io
import json
from datetime import datetime
from supabase import create_client, Client

st.set_page_config(page_title="GS건설 현장심사 시스템", layout="wide")

# ==========================================
# 🎨 게시판 UI 전용 커스텀 CSS
# ==========================================
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    
    /* 게시판 행(Row) 컨테이너 */
    .board-row {
        background-color: white;
        border-bottom: 1px solid #eee;
        padding: 10px 0;
        transition: all 0.2s;
    }
    .board-row:hover { background-color: #f1f8ff; }

    /* 뱃지 공통 스타일 */
    .badge {
        padding: 4px 10px;
        border-radius: 6px;
        font-weight: 700;
        font-size: 0.85rem;
        display: inline-block;
    }
    .excellent { background-color: #d4edda; color: #155724; }
    .normal { background-color: #fff3cd; color: #856404; }
    .warning { background-color: #f8d7da; color: #721c24; }
    
    /* 텍스트 스타일 */
    .site-title { font-weight: 600; color: #333; }
    .sub-info { color: #666; font-size: 0.85rem; }
    
    /* 헤더 스타일 */
    .board-header {
        background-color: #f1f3f5;
        padding: 12px 0;
        border-radius: 8px;
        font-weight: bold;
        color: #495057;
        margin-bottom: 10px;
        text-align: center;
    }
    </style>
    """, unsafe_allow_html=True)

# 1. Supabase 연결
@st.cache_resource
def init_connection():
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    return create_client(url, key)

try:
    supabase: Client = init_connection()
except:
    st.error("DB 연결에 실패했습니다.")
    st.stop()

# 세션 상태 관리
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'current_user' not in st.session_state: st.session_state.current_user = ""
if 'admin_view' not in st.session_state: st.session_state.admin_view = "list"
if 'edit_target_id' not in st.session_state: st.session_state.edit_target_id = None

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
# 사이드바 & 상단 로그인 처리
# ==========================================
st.sidebar.markdown(f"### 🏗️ GS건설 보건관리")
menu = st.sidebar.radio("메뉴 이동", ["📊 통계 대시보드", "📅 심사 게시판"])

# ==========================================
# [페이지 2] 심사 게시판 (메인 기능)
# ==========================================
if menu == "📅 심사 게시판":
    if not st.session_state.logged_in:
        st.title("🔐 관리자 인증")
        with st.form("login"):
            uid = st.text_input("아이디")
            upw = st.text_input("비밀번호", type="password")
            if st.form_submit_button("로그인"):
                pw_dict = st.secrets["passwords"]
                if uid in pw_dict and pw_dict[uid] == upw:
                    st.session_state.logged_in = True
                    st.session_state.current_user = uid
                    st.rerun()
                else: st.error("정보가 틀렸습니다.")
    else:
        # 로그인 후 헤더
        c_t, c_u = st.columns([5, 1])
        with c_t: st.title("📋 현장 내부심사 게시판")
        with c_u:
            st.write(f"👤 {st.session_state.current_user}")
            if st.button("로그아웃"): 
                st.session_state.logged_in = False
                st.rerun()

        st.divider()
        m_tab, t_tab = st.tabs(["📋 리스트 관리", "⚙️ 점수표 설정"])

        with m_tab:
            if st.session_state.admin_view == "list":
                # 상단 검색 및 신규 버튼
                col_search, col_add = st.columns([3, 1])
                with col_search:
                    sq = st.text_input("현장 검색", placeholder="현장명을 입력하세요...", label_visibility="collapsed")
                with col_add:
                    # 신규 버튼 강조
                    if st.button("➕ 신규 심사 등록", type="primary", use_container_width=True):
                        st.session_state.admin_view = "create"
                        st.rerun()

                res_df = load_results()
                if not res_df.empty:
                    if sq: res_df = res_df[res_df['현장명'].str.contains(sq)]
                    
                    # 게시판 헤더 (5열)
                    st.markdown("""
                        <div class='board-header'>
                            <div style='display: flex;'>
                                <div style='flex: 3;'>현장 제목</div>
                                <div style='flex: 1;'>분류</div>
                                <div style='flex: 1.5;'>심사 점수</div>
                                <div style='flex: 1.5;'>작성 정보</div>
                                <div style='flex: 1.2;'>관리</div>
                            </div>
                        </div>
                    """, unsafe_allow_html=True)

                    for _, row in res_df.iterrows():
                        score = row['최종점수']
                        if score >= 95: b_c, b_t = "excellent", "우수"
                        elif score >= 80: b_c, b_t = "normal", "보통"
                        else: b_c, b_t = "warning", "주의"

                        # 한 줄 컨테이너
                        with st.container():
                            c1, c2, c3, c4, c5 = st.columns([3, 1, 1.5, 1.5, 1.2])
                            
                            # 1. 현장 제목 (클릭 시 수정 페이지로)
                            if c1.button(f"🏢 {row['현장명']}", key=f"title_{row['id']}", use_container_width=True):
                                st.session_state.edit_target_id = int(row['id'])
                                st.session_state.admin_view = "edit"
                                st.rerun()
                            
                            # 2. 분류
                            c2.markdown(f"<div style='text-align:center; padding-top:10px;'>{row['현장타입']}</div>", unsafe_allow_html=True)
                            
                            # 3. 심사 점수
                            c3.markdown(f"<div style='text-align:center; padding-top:5px;'><span class='badge {b_c}'>{score}점 ({b_t})</span></div>", unsafe_allow_html=True)
                            
                            # 4. 작성 정보
                            updated_by = row['updated_by'] if 'updated_by' in row else '알수없음'
                            c4.markdown(f"<div style='text-align:center;' class='sub-text'>{updated_by}<br>{str(row['created_at'])[:10]}</div>", unsafe_allow_html=True)
                            
                            # 5. 관리 (수정/삭제 버튼)
                            with c5:
                                btn_edit, btn_del = st.columns(2)
                                if btn_edit.button("✏️", key=f"edit_ico_{row['id']}", help="수정"):
                                    st.session_state.edit_target_id = int(row['id'])
                                    st.session_state.admin_view = "edit"
                                    st.rerun()
                                if btn_del.button("🗑️", key=f"del_ico_{row['id']}", help="삭제"):
                                    # 삭제 시 한 번 더 물어보기 위해 타겟 아이디만 잡고 상세페이지의 삭제기능 유도 혹은 즉시 삭제
                                    supabase.table("audit_results").delete().eq("id", row['id']).execute()
                                    st.success("삭제되었습니다.")
                                    st.rerun()
                            st.write("---")
                else:
                    st.info("데이터가 없습니다.")

            # ---------------------------------------------------------
            # 생성 및 수정 뷰 (기존 코드 유지)
            # ---------------------------------------------------------
            elif st.session_state.admin_view in ["create", "edit"]:
                if st.button("⬅️ 목록으로 돌아가기"):
                    st.session_state.admin_view = "list"
                    st.session_state.edit_target_id = None
                    st.rerun()
                
                # (중략: 이전 버전의 상세 폼 로직 - create/edit 구분하여 점수 버튼 UI 출력)
                # ... 생략된 부분은 대장님이 기존에 쓰시던 10개 탭 입력 폼이 들어갑니다 ...
                st.info("여기에 상세 입력 폼이 나타납니다. (전체 코드를 위해 이전 폼 로직을 그대로 붙여넣으시면 됩니다)")

# [나머지 대시보드 및 템플릿 설정 코드는 이전과 동일하게 유지]
