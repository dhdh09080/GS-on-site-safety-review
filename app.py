import streamlit as st
import pandas as pd
import plotly.express as px
import io
import json
from supabase import create_client, Client

st.set_page_config(page_title="현장 내부심사 시스템", layout="wide")

# 1. Supabase 연결
@st.cache_resource
def init_connection():
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    return create_client(url, key)

supabase: Client = init_connection()

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

# 데이터 불러오기 함수들
def load_template():
    res = supabase.table("checklist_template").select("*").order("id").execute()
    return pd.DataFrame(res.data)

def load_results():
    res = supabase.table("audit_results").select("*").order("created_at", desc=True).execute()
    df = pd.DataFrame(res.data)
    if not df.empty:
        df = df.rename(columns={"site_name": "현장명", "site_type": "현장타입", "score": "최종점수"})
    return df

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
            # 타입이 없을 경우 빈칸 처리
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
        st.download_button("📥 엑셀 다운로드", data=io.BytesIO(), file_name="임시.xlsx") # 엑셀 다운로드 기능은 기존과 동일하게 유지 가능하여 축약함.
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
            if st.form_submit_button("로그인") and st.text_input("아이디") == "gsmaster" and st.text_input("비밀번호", type="password") == "1234":
                st.session_state.logged_in = True
                st.rerun()
    else:
        st.write("🔓 'gsmaster' 관리자님, 환영합니다.")
        if st.button("로그아웃"):
            st.session_state.logged_in = False
            st.rerun()
            
        st.divider()
        
        # 3개의 탭으로 기능 완벽 분리
        tab1, tab2, tab3 = st.tabs(["📝 신규 점수 입력", "📋 입력 데이터 관리(삭제)", "⚙️ 점수표(템플릿) 설정"])
        
        # ----------------------------------------
        # 탭 1: 신규 점수 입력 (세부 점수 & 해당없음)
        # ----------------------------------------
        with tab1:
            st.subheader("📝 현장 세부 심사 입력")
            template_df = load_template()
            
            if template_df.empty:
                st.warning("점수표가 비어있습니다. '점수표 설정' 탭에서 항목을 먼저 추가해주세요.")
            else:
                with st.form("detail_input_form"):
                    col1, col2 = st.columns(2)
                    with col1: site_name = st.text_input("현장명")
                    with col2: site_type = st.selectbox("현장 분류", ["건축", "인프라", "플랜트"])
                    
                    st.markdown("#### 📋 세부 평가 항목")
                    
                    input_data = {}
                    # 템플릿에 따라 동적으로 입력 폼 생성
                    for index, row in template_df.iterrows():
                        st.markdown(f"**[{row['category']}]** {row['item_name']} (배점: {row['max_score']}점)")
                        
                        c1, c2 = st.columns([3, 1])
                        with c2: 
                            is_na = st.checkbox(f"해당없음", key=f"na_{row['id']}")
                        with c1: 
                            # 해당 없음 체크 시 점수 입력 비활성화 (0점 처리)
                            score = st.number_input("점수 입력", min_value=0.0, max_value=float(row['max_score']), step=0.5, key=f"score_{row['id']}", disabled=is_na)
                        
                        input_data[row['id']] = {"score": score, "is_na": is_na, "max": row['max_score']}
                        st.write("---")

                    if st.form_submit_button("✅ 전체 데이터 저장"):
                        if site_name:
                            total_score_earned = 0
                            total_max_possible = 0
                            
                            for item_id, data in input_data.items():
                                if not data["is_na"]: # 해당없는 항목은 분모와 분자에서 모두 제외
                                    total_score_earned += data["score"]
                                    total_max_possible += data["max"]
                                    
                            # 100점 만점으로 환산 (해당없음 제외)
                            final_score = (total_score_earned / total_max_possible * 100) if total_max_possible > 0 else 0
                            final_score = round(final_score, 1)

                            # DB에 쏘기
                            supabase.table("audit_results").insert({
                                "site_name": site_name,
                                "site_type": site_type,
                                "score": final_score,
                                "details": json.dumps(input_data) # 세부 점수를 JSON으로 압축해서 저장
                            }).execute()
                            
                            st.success(f"'{site_name}' 데이터가 저장되었습니다! (환산점수: {final_score}점)")
                        else:
                            st.error("현장명을 입력해주세요.")

        # ----------------------------------------
        # 탭 2: 입력 데이터 관리 (수정 및 삭제)
        # ----------------------------------------
        with tab2:
            st.subheader("📋 입력된 데이터 목록 및 삭제")
            st.info("💡 잘못 입력된 데이터의 ID를 선택하여 삭제할 수 있습니다.")
            
            res_df = load_results()
            if not res_df.empty:
                st.dataframe(res_df[['id', '현장명', '현장타입', '최종점수', 'created_at']], use_container_width=True)
                
                col_del1, col_del2 = st.columns([3, 1])
                with col_del1:
                    delete_id = st.selectbox("🗑️ 삭제할 데이터의 ID를 선택하세요:", res_df['id'].tolist())
                with col_del2:
                    st.write("") # 줄맞춤용
                    st.write("")
                    if st.button("🚨 선택 데이터 삭제"):
                        supabase.table("audit_results").delete().eq("id", delete_id).execute()
                        st.success("데이터가 삭제되었습니다. (새로고침을 위해 메뉴를 다시 눌러주세요)")
            else:
                st.write("입력된 데이터가 없습니다.")

        # ----------------------------------------
        # 탭 3: 점수표(템플릿) 설정
        # ----------------------------------------
        with tab3:
            st.subheader("⚙️ 점수표 항목 자유 수정")
            st.write("항목을 직접 수정하거나 행을 추가/삭제한 뒤 '변경사항 DB에 저장' 버튼을 누르세요.")
            
            temp_df = load_template()
            if temp_df.empty:
                temp_df = pd.DataFrame(columns=['category', 'item_name', 'max_score'])
            else:
                temp_df = temp_df[['category', 'item_name', 'max_score']] # id 숨기기
                
            # Streamlit의 강력한 데이터 에디터 기능
            edited_df = st.data_editor(temp_df, num_rows="dynamic", use_container_width=True)
            
            if st.button("💾 변경사항 DB에 완전 저장"):
                # 1. 기존 템플릿 싹 지우기 (초기화)
                # Supabase 보안상 ID 필터가 필요하여 0보다 큰 것 모두 지우는 꼼수 사용
                supabase.table("checklist_template").delete().gt("id", 0).execute()
                
                # 2. 에디터에 있는 내용으로 다시 밀어넣기
                new_records = edited_df.to_dict('records')
                if new_records:
                    supabase.table("checklist_template").insert(new_records).execute()
                st.success("점수표가 새롭게 업데이트 되었습니다!")
                st.rerun()
