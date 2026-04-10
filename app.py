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

try:
    supabase: Client = init_connection()
except Exception as e:
    st.error("데이터베이스 연결에 실패했습니다. Streamlit Secrets 설정을 확인해주세요.")
    st.stop()

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

# 대장님이 요청하신 10가지 대분류 리스트
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
                df[['현장명', '현장타입', '최종점수', '등급']].to_excel(writer, index=False, sheet_name='심사결과')
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
        
        tab1, tab2, tab3 = st.tabs(["📝 신규 점수 입력", "📋 입력 데이터 관리(삭제)", "⚙️ 점수표(템플릿) 설정"])
        
        # ----------------------------------------
        # 탭 1: 신규 점수 입력
        # ----------------------------------------
        with tab1:
            st.subheader("📝 현장 세부 심사 입력")
            template_df = load_template()
            
            with st.form("detail_input_form"):
                col1, col2 = st.columns(2)
                with col1: site_name = st.text_input("현장명")
                with col2: site_type = st.selectbox("현장 분류", ["건축", "인프라", "플랜트"])
                
                st.write("---")
                
                input_tabs = st.tabs(main_categories)
                input_data = {}
                
                for i, category in enumerate(main_categories):
                    with input_tabs[i]:
                        st.markdown(f"#### {category}")
                        
                        if not template_df.empty and 'category' in template_df.columns:
                            filtered_df = template_df[template_df['category'] == category]
                            
                            if filtered_df.empty:
                                st.info("이 분류에 등록된 평가 항목이 아직 없습니다. '점수표 설정' 탭에서 항목을 추가해주세요.")
                            else:
                                for index, row in filtered_df.iterrows():
                                    st.markdown(f"**🔹 {row['item_name']}** (배점: {row['max_score']}점)")
                                    
                                    c1, c2 = st.columns([3, 1])
                                    with c2: 
                                        is_na = st.checkbox(f"해당없음", key=f"na_{row['id']}")
                                    with c1: 
                                        score = st.number_input("점수 입력", min_value=0.0, max_value=float(row['max_score']), step=0.5, key=f"score_{row['id']}", disabled=is_na)
                                    
                                    input_data[row['id']] = {"score": score, "is_na": is_na, "max": row['max_score']}
                                    st.write("---")

                st.write("") 
                if st.form_submit_button("✅ 전체 데이터 최종 저장", use_container_width=True):
                    if site_name:
                        total_score_earned = 0
                        total_max_possible = 0
                        
                        for item_id, data in input_data.items():
                            if not data["is_na"]: 
                                total_score_earned += data["score"]
                                total_max_possible += data["max"]
                                
                        final_score = (total_score_earned / total_max_possible * 100) if total_max_possible > 0 else 0
                        final_score = round(final_score, 1)

                        supabase.table("audit_results").insert({
                            "site_name": site_name,
                            "site_type": site_type,
                            "score": final_score,
                            "details": json.dumps(input_data)
                        }).execute()
                        
                        st.success(f"'{site_name}' 데이터가 저장되었습니다! (최종 환산점수: {final_score}점)")
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
                    st.write("")
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
            st.write("대분류를 정확히 맞춰야 입력 탭에 정상적으로 표시됩니다.")
            
            temp_df = load_template()
            if temp_df.empty:
                temp_df = pd.DataFrame(columns=['category', 'item_name', 'max_score'])
            else:
                temp_df = temp_df[['category', 'item_name', 'max_score']]
                
            edited_df = st.data_editor(
                temp_df, 
                num_rows="dynamic", 
                use_container_width=True,
                column_config={
                    "category": st.column_config.SelectboxColumn(
                        "대분류 (Category)", 
                        options=main_categories,
                        required=True
                    ),
                    "item_name": st.column_config.TextColumn("세부 평가 항목명", required=True),
                    "max_score": st.column_config.NumberColumn("최대 배점", min_value=0.0, required=True)
                }
            )
            
            if st.button("💾 변경사항 DB에 완전 저장"):
                supabase.table("checklist_template").delete().gt("id", 0).execute()
                new_records = edited_df.to_dict('records')
                if new_records:
                    supabase.table("checklist_template").insert(new_records).execute()
                st.success("점수표가 새롭게 업데이트 되었습니다!")
                st.rerun()
