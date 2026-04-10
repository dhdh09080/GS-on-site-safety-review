import streamlit as st
import pandas as pd
import plotly.express as px
import io
import os

# 페이지 기본 설정
st.set_page_config(page_title="현장 내부심사 시스템", layout="wide")

# 데이터 파일 경로
DATA_FILE = "audit_results.csv"

# 1. 초기 데이터 로드 함수
def load_data():
    if os.path.exists(DATA_FILE):
        return pd.read_csv(DATA_FILE)
    else:
        return pd.DataFrame(columns=["현장명", "점수"])

# 세션(화면) 상태 초기화 (데이터 및 로그인 상태)
if 'df' not in st.session_state:
    st.session_state.df = load_data()
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False # 기본값: 로그아웃 상태

def save_data(new_df):
    st.session_state.df = new_df
    new_df.to_csv(DATA_FILE, index=False)

# ==========================================
# 사이드바 메뉴 설정
# ==========================================
st.sidebar.title("메뉴 네비게이션")
menu = st.sidebar.radio("이동할 페이지를 선택하세요:", ["📊 실시간 대시보드", "⚙️ 관리자 페이지"])

# ==========================================
# [페이지 1] 실시간 대시보드 (누구나 볼 수 있음)
# ==========================================
if menu == "📊 실시간 대시보드":
    st.title("🏗️ 현장 내부심사 통합 대시보드")
    df = st.session_state.df

    if not df.empty:
        # 등급 나누기
        def get_grade(s):
            if s >= 95: return "95점 이상 (우수)"
            elif s >= 80: return "80점 이상 (보통)"
            else: return "80점 미만 (주의)"
            
        df['등급'] = df['점수'].apply(get_grade)
        
        col_table, col_chart = st.columns([1, 2])
        
        with col_table:
            st.subheader("📋 현장별 점수표")
            display_df = df.sort_values(by="점수", ascending=False).reset_index(drop=True)
            st.dataframe(display_df[['현장명', '점수', '등급']], use_container_width=True, height=400)
            
        with col_chart:
            st.subheader("📊 점수 분포 그래프")
            fig = px.scatter(
                df, x=df.index, y="점수", color="등급",
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

        # 엑셀 다운로드 (누구나 가능)
        st.subheader("📥 데이터 추출")
        def to_excel(df):
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False, sheet_name='심사결과')
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
# [페이지 2] 관리자 페이지 (데이터 입력)
# ==========================================
elif menu == "⚙️ 관리자 페이지":
    st.title("⚙️ 관리자 전용 데이터 입력")
    
    # 로그인 되어있지 않은 경우 -> 로그인 폼 표시
    if not st.session_state.logged_in:
        st.info("데이터를 입력하려면 관리자 권한이 필요합니다.")
        with st.form("login_form"):
            st.subheader("관리자 로그인")
            user_id = st.text_input("아이디")
            user_pw = st.text_input("비밀번호", type="password") # 비밀번호 마스킹 처리
            submit_login = st.form_submit_button("로그인")
            
            if submit_login:
                if user_id == "gsmaster" and user_pw == "1234":
                    st.session_state.logged_in = True
                    st.rerun() # 로그인 성공 시 화면 새로고침하여 입력창 띄움
                else:
                    st.error("아이디 또는 비밀번호가 일치하지 않습니다.")
                    
    # 로그인 성공한 경우 -> 데이터 입력 폼 및 로그아웃 버튼 표시
    else:
        st.success(f"🔓 'gsmaster' 관리자님, 환영합니다.")
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
                new_row = pd.DataFrame([{"현장명": site_name, "점수": score}])
                updated_df = pd.concat([st.session_state.df, new_row], ignore_index=True)
                save_data(updated_df)
                st.success(f"✅ '{site_name}' 현장 데이터가 안전하게 저장되었습니다!")
                st.rerun()
