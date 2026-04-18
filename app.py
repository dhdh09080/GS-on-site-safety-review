import streamlit as st
import pandas as pd
import plotly.express as px
import io
import json
import math
from datetime import datetime
from supabase import create_client, Client

st.set_page_config(page_title="현장 내부심사 게시판", layout="wide")

# 1. Supabase 연결 (생략 - 기존 코드 유지)
@st.cache_resource
def init_connection():
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    return create_client(url, key)

try:
    supabase: Client = init_connection()
except Exception as e:
    st.error("DB 연결 실패")
    st.stop()

# 세션 상태 초기화
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'current_user' not in st.session_state: st.session_state.current_user = ""
if 'admin_view' not in st.session_state: st.session_state.admin_view = "list"
if 'edit_target_id' not in st.session_state: st.session_state.edit_target_id = None

# 데이터 로드 함수 (생략 - 기존 코드 유지)
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

# 사이드바
st.sidebar.title("📌 GS건설 관리")
menu = st.sidebar.radio("메뉴", ["📊 대시보드", "📝 심사 게시판"])

if menu == "📊 대시보드":
    st.title("🏗️ 전사 현장 심사 통계")
    # ... (대시보드 코드 생략)

elif menu == "📝 심사 게시판":
    if not st.session_state.logged_in:
        # ... (로그인 폼 생략)
        st.title("🔐 관리자 인증")
        with st.form("login_form"):
            user_id = st.text_input("아이디")
            user_pw = st.text_input("비밀번호", type="password")
            if st.form_submit_button("로그인"):
                if "passwords" in st.secrets:
                    passwords = st.secrets["passwords"]
                    if user_id in passwords and passwords[user_id] == user_pw:
                        st.session_state.logged_in = True
                        st.session_state.current_user = user_id
                        st.rerun()
                    else: st.error("정보 불일치")
                else: st.error("Secrets 설정 필요")
    else:
        # 로그인 후 게시판 UI
        st.title("📋 현장 내부심사 게시판")
        st.divider()
        
        main_tab, template_tab = st.tabs(["📝 게시판 목록", "⚙️ 점수표 설정"])
        
        with main_tab:
            if st.session_state.admin_view == "list":
                # 상단 툴바
                c_search, c_write = st.columns([4, 1])
                with c_search:
                    search_q = st.text_input("🔍 현장명 검색", placeholder="현장 이름을 입력하세요...")
                with c_write:
                    st.write(" ")
                    if st.button("➕ 신규 심사 등록", type="primary", use_container_width=True):
                        st.session_state.admin_view = "create"
                        st.rerun()

                res_df = load_results()
                if not res_df.empty:
                    # 안전장치 및 필터링
                    if 'updated_at' not in res_df.columns: res_df['updated_at'] = "-"
                    if 'updated_by' not in res_df.columns: res_df['updated_by'] = "-"
                    if search_q:
                        res_df = res_df[res_df['현장명'].str.contains(search_q)]

                    # --- 게시판 헤더 (진짜 게시판 느낌) ---
                    st.write("---")
                    h_col1, h_col2, h_col3, h_col4 = st.columns([4, 1, 1, 1])
                    h_col1.write("**제목 (현장명)**")
                    h_col2.write("**타입**")
                    h_col3.write("**점수(등급)**")
                    h_col4.write("**작성일**")
                    st.write("---")

                    # --- 게시물 리스트 생성 ---
                    for _, row in res_df.iterrows():
                        # 점수에 따른 등급/색상 설정
                        score = row['최종점수']
                        if score >= 95: badge, color = "🟢 우수", "green"
                        elif score >= 80: badge, color = "🟡 보통", "orange"
                        else: badge, color = "🔴 주의", "red"
                        
                        # 한 줄 컨테이너 (게시물 한 칸)
                        with st.container():
                            r_col1, r_col2, r_col3, r_col4 = st.columns([4, 1, 1, 1])
                            
                            # 제목을 버튼으로 만들어 클릭 시 바로 이동하게 구현
                            if r_col1.button(f"📄 {row['현장명']}", key=f"btn_{row['id']}", use_container_width=True):
                                st.session_state.edit_target_id = int(row['id'])
                                st.session_state.admin_view = "edit"
                                st.rerun()
                            
                            r_col2.write(f"<{row['현장타입']}>")
                            r_col3.markdown(f":{color}[**{score}점**]  \n{badge}")
                            r_col4.write(str(row['created_at'])[:10])
                            st.write("---")
                else:
                    st.info("내역이 없습니다.")

            # (생략 - create, edit, template 탭 로직은 이전과 동일하게 유지)
            elif st.session_state.admin_view == "create":
                # ... (이전 신규 입력 폼 코드)
                if st.button("⬅️ 목록으로"):
                    st.session_state.admin_view = "list"
                    st.rerun()
                # (중략 - 이전 버전의 form 코드 유지)
                st.write("신규 입력 폼 구현부")
                
            elif st.session_state.admin_view == "edit":
                # ... (이전 수정 폼 코드)
                if st.button("⬅️ 목록으로"):
                    st.session_state.admin_view = "list"
                    st.rerun()
                # (중략 - 이전 버전의 form 코드 유지)
                st.write("수정 폼 구현부")
