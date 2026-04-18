import streamlit as st
import pandas as pd
import plotly.express as px
import io
import json
from datetime import datetime
from supabase import create_client, Client

st.set_page_config(page_title="현장 내부심사 시스템", layout="wide")

# 1. Supabase 연결
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

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'current_user' not in st.session_state:
    st.session_state.current_user = ""

def load_template():
    res = supabase.table("checklist_template").select("*").order("id").execute()
    return pd.DataFrame(res.data)

def load_results():
    res = supabase.table("audit_results").select("*").order("created_at", desc=True).execute()
    df = pd.DataFrame(res.data)
    if not df.empty:
        df = df.rename(columns={"site_name": "현장명", "site_type": "현장타입", "score": "최종점수"})
    return df

main_categories = [
    "1. 방침 수립, 조직상황, 성과평가, 내부심사",
    "2. 인력 및 예산",
    "3. 위험성평가 및 이행",
    "4. 종사자 의견 청취 및 개선 조치",
    "5. 안전보건교육",
    "6. 비상 시 대응 계획 및 사고관리",
    "7. 계획 수립",
    "8. 회의 및 점검",
    "9. 장비 안전관리 (건기법 포함)",
    "10. 보건관리"
]

# ==========================================
# 사이드바 메뉴 설정
# ==========================================
st.sidebar.title("메뉴 네비게이션")
menu = st.sidebar.radio("이동할 페이지 선택:", ["📊 실시간 대시보드", "⚙️ 관리자 페이지"])

# ==========================================
# [페이지 1] 실시간 대시보드
# ==========================================
if menu == "📊 실시간 대시보드":
    st.title("🏗️ 현장 내부심사 통합 대시보드")
    df = load_results()

    if not df.empty:
        def get_grade(s):
            if s >= 95: return "95점 이상 (우수)"
            elif s >= 80: return "80점 이상 (보통)"
            else: return "80점 미만 (주의)"
            
        df['등급'] = df['최종점수'].apply(get_grade)
        
        col_table, col_chart = st.columns([1, 2])
        with col_table:
            st.subheader("📋 현장별 최종 점수표")
            if '현장타입' not in df.columns: df['현장타입'] = "-"
            st.dataframe(df[['현장명', '현장타입', '최종점수', '등급']], use_container_width=True, height=400)
            
        with col_chart:
            st.subheader("📊 현장 분류별 점수 분포")
            fig = px.scatter(
                df, x=df.index, y="최종점수", color="등급", symbol="현장타입",
                color_discrete_map={"95점 이상 (우수)": "#00b050", "80점 이상 (보통)": "#ffc000", "80점 미만 (주의)": "#ff0000"},
                hover_name="현장명", size_max=15
            )
            fig.update_traces(marker=dict(size=12, line=dict(width=1, color='DarkSlateGrey')))
            st.plotly_chart(fig, use_container_width=True)
            
        st.divider()
        st.subheader("📥 데이터 추출")
        def to_excel(df):
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                export_cols = ['현장명', '현장타입', '최종점수', '등급']
                if 'created_by' in df.columns: export_cols.append('created_by')
                if 'updated_by' in df.columns: export_cols.append('updated_by')
                df[export_cols].to_excel(writer, index=False, sheet_name='심사결과')
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
    st.title("⚙️ 관리자 시스템")
    
    if not st.session_state.logged_in:
        with st.form("login_form"):
            st.subheader("관리자 로그인")
            user_id = st.text_input("아이디")
