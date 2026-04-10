import streamlit as st
import pandas as pd
import plotly.express as px
import io
from supabase import create_client, Client

# 페이지 기본 설정
st.set_page_config(page_title="현장 내부심사 시스템", layout="wide")

# 1. Supabase DB 연결 설정
@st.cache_resource
def init_connection():
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    return create_client(url, key)

try:
    supabase: Client = init_connection()
except Exception as e:
    st.error("데이터베이스 연결에 실패했습니다. Streamlit Secrets 설정을 확인해주세요.")
    st.stop()

# 2. 로그인 상태 초기화
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

# 3. 데이터 불러오기 함수
def load_data():
    # Supabase에서 데이터 가져오기
    response = supabase.table("audit_results").select("*").execute()
    df = pd.DataFrame(response.data)
    
    if not df.empty:
        df = df.rename(columns={"site_name": "현장명", "score": "점수"})
        # 점수 기준 내림차순 정렬
        df = df.sort_values(by="점수", ascending=False).reset_index(drop=True)
    return df

# ==========================================
# 사이드바 메뉴 설정
# ==========================================
st.sidebar.title("메뉴 네비게이션")
menu = st.sidebar.radio("이동할 페이지를 선택하세요:", ["📊 실시간 대시보드", "⚙️ 관리자 페이지"])

# ==========================================
# [페이지 1] 실시간 대시보드
# ==========================================
if menu == "📊 실시간 대시보드":
    st.title("🏗️ 현장 내부심사 통합 대시보드")
    
    # DB에서 최신 데이터 불러오기
    df = load_data()

    if not df.empty:
        def get_grade(s):
            if s >= 95: return "95점 이상 (우수)"
            elif s >= 80: return "80점 이상 (보통)"
            else: return "80점 미만 (주의)"
            
        df['등급'] = df['점수'].apply(get_grade)
        
        col_table, col_chart = st.columns([1, 2])
        
        with col_table:
            st.subheader("📋 현장별 점수표")
            st.dataframe(df[['현장명', '점수', '등급']], use_container_width=True, height=400)
            
        with col_chart:
            st.subheader("📊 점수 분포 그래프")
            # 입력된 순서(created_at)대로 보여주기 위해 인덱스 활용
            fig = px.scatter(
                df.sort_values(by="created_at"), x=range(len(df)), y="점수", color="등급",
                color_discrete_map={
                    "95점 이상 (우수)": "#00b050",
                    "80점 이상 (보통)": "#ffc000",
                    "80점 미만 (주의)": "#ff0000"
                },
                hover_name="현장명", size_max=15
            )
            fig.update_traces(marker=dict(size=12, line=dict(width=1, color='DarkSlateGrey')))
            fig.update_layout(xaxis_title="입력 순서", yaxis_title="심사 점수", yaxis_range=[0, 105])
            st.plotly_chart(fig, use_container_width=True)

        st.divider()

        st.subheader("📥 데이터 추출")
        def to_excel(df):
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                # 불필요한 id와 created_at 열 빼고 엑셀 저장
                df[['현장명', '점수', '등급']].to_excel(writer, index=False, sheet_name='심사결과')
            return output.getvalue()
            
        excel_data = to_excel(df)
        st.download_button(
            label="엑셀 파일(.xlsx) 다운로드",
            data=excel_data,
            file_name="현장_내부심사_결과.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.info("현재 등록된 현장 데이터가 없습니다.")

# ==========================================
# [페이지 2] 관리자 페이지
# ==========================================
elif menu == "⚙️ 관리자 페이지":
    st.title("⚙️ 관리자 전용 데이터 입력")
    
    if not st.session_state.logged_in:
        st.info("데이터를 입력하려면 관리자 권한이 필요합니다.")
        with st.form("login_form"):
            st.subheader("관리자 로그인")
            user_id = st.text_input("아이디")
            user_pw = st.text_input("비밀번호", type="password")
            submit_login = st.form_submit_button("로그인")
            
            if submit_login:
                if user_id == "gsmaster" and user_pw == "1234":
                    st.session_state.logged_in = True
                    st.rerun()
                else:
                    st.error("아이디 또는 비밀번호가 일치하지 않습니다.")
                    
    else:
        st.success("🔓 'gsmaster' 관리자님, 환영합니다.")
        if st.button("로그아웃"):
            st.session_state.logged_in = False
            st.rerun()
            
        st.divider()
        st.subheader("📝 신규 현장 점수 입력")
        
        with st.form("input_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                site_name = st.text_input("현장명 (예: 양산자이파크)")
            with col2:
                score = st.number_input("점수", min_value=0.0, max_value=100.0, step=0.1)
            
            submitted = st.form_submit_button("데이터 저장하기")
            
            if submitted and site_name:
                # Supabase DB에 실시간으로 데이터 쏘기
                supabase.table("audit_results").insert({"site_name": site_name, "score": score}).execute()
                st.success(f"✅ '{site_name}' 현장 데이터가 클라우드 DB에 안전하게 저장되었습니다!")
                # 데이터가 입력된 후 화면을 새로고침하여 초기화
