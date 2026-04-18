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

# 2. 세션 상태 초기화 (페이지 전환용 State 추가)
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'current_user' not in st.session_state:
    st.session_state.current_user = ""
# UI 흐름 제어를 위한 상태 변수 ('list', 'create', 'edit')
if 'admin_view' not in st.session_state:
    st.session_state.admin_view = "list"
if 'edit_target_id' not in st.session_state:
    st.session_state.edit_target_id = None

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
    
    if not st.session_state.logged_in:
        st.title("⚙️ 관리자 시스템 접속")
        with st.form("login_form"):
            st.subheader("관리자 로그인")
            user_id = st.text_input("아이디")
            user_pw = st.text_input("비밀번호", type="password")
            submit_login = st.form_submit_button("로그인")
            
            if submit_login:
                try:
                    passwords = st.secrets["passwords"]
                    if user_id in passwords and passwords[user_id] == user_pw:
                        st.session_state.logged_in = True
                        st.session_state.current_user = user_id
                        st.rerun()
                    else:
                        st.error("아이디 또는 비밀번호가 일치하지 않습니다.")
                except KeyError:
                    if user_id == "gsmaster" and user_pw == "1234":
                        st.session_state.logged_in = True
                        st.session_state.current_user = "gsmaster"
                        st.rerun()
                    else:
                        st.error("설정된 접속 계정 정보를 확인해주세요.")
    else:
        # 로그인 성공 후 화면 레이아웃
        col_title, col_logout = st.columns([5, 1])
        with col_title:
            st.title("⚙️ 현장 내부심사 관리")
        with col_logout:
            st.write(f"👤 **{st.session_state.current_user}**님")
            if st.button("로그아웃"):
                st.session_state.logged_in = False
                st.session_state.current_user = ""
                st.session_state.admin_view = "list"
                st.rerun()
                
        st.divider()
        
        # 메인 관리 탭과 템플릿 설정 탭 분리
        main_tab, template_tab = st.tabs(["📝 현장 심사 관리", "⚙️ 점수표(템플릿) 설정"])
        
        with main_tab:
            # ---------------------------------------------------------
            # 뷰 모드 1: 리스트 (대장님 제안 UX + KeyError 방어코드 적용)
            # ---------------------------------------------------------
            if st.session_state.admin_view == "list":
                col_sub, col_btn = st.columns([4, 1])
                with col_sub:
                    st.subheader("📋 등록된 현장 목록")
                with col_btn:
                    if st.button("➕ 신규 현장 등록", type="primary", use_container_width=True):
                        st.session_state.admin_view = "create"
                        st.rerun()
                
                res_df = load_results()
                if not res_df.empty:
                    # [KeyError 방어코드] 옛날 데이터라 수정일 칸이 없으면 생성해 줌
                    if 'updated_at' not in res_df.columns:
                        res_df['updated_at'] = "-"
                    if 'updated_by' not in res_df.columns:
                        res_df['updated_by'] = "-"
                        
                    # 표출용 데이터프레임 가공
                    display_df = res_df[['id', '현장명', '현장타입', '최종점수', 'updated_at', 'updated_by']].copy()
                    display_df['updated_at'] = display_df['updated_at'].astype(str).str[:10] # 날짜만 표시
                    display_df.columns = ['ID', '현장명', '타입', '최종점수', '최근수정일', '수정자']
                    
                    st.dataframe(display_df, use_container_width=True, hide_index=True)
                    
                    st.write("---")
                    st.write("💡 **수정/삭제를 원하시는 현장을 아래에서 선택해주세요.**")
                    
                    # 수정할 현장 선택
                    res_df['표시명'] = res_df['현장명'] + " [" + res_df['현장타입'] + "] (" + res_df['created_at'].str[:10] + ")"
                    selected_display = st.selectbox("수정할 현장 선택:", ["선택 안함"] + res_df['표시명'].tolist())
                    
                    if selected_display != "선택 안함":
                        selected_row = res_df[res_df['표시명'] == selected_display].iloc[0]
                        if st.button(f"✏️ '{selected_row['현장명']}' 심사내역 수정하기"):
                            st.session_state.edit_target_id = int(selected_row['id'])
                            st.session_state.admin_view = "edit"
                            st.rerun()
                else:
                    st.info("등록된 현장 심사 데이터가 없습니다. 우측 상단의 '신규 현장 등록' 버튼을 눌러주세요.")

            # ---------------------------------------------------------
            # 뷰 모드 2: 신규 생성 (Create)
            # ---------------------------------------------------------
            elif st.session_state.admin_view == "create":
                if st.button("⬅️ 목록으로 돌아가기"):
                    st.session_state.admin_view = "list"
                    st.rerun()
                    
                st.subheader("📝 신규 현장 세부 심사 입력")
                template_df = load_template()
                
                with st.form("detail_input_form", clear_on_submit=False):
                    col1, col2 = st.columns(2)
                    with col1: site_name = st.text_input("현장명")
                    with col2: site_type = st.selectbox("현장 분류", ["건축", "인프라", "플랜트"])
                    
                    st.write("---")
                    input_tabs = st.tabs(main_categories)
                    input_data = {}
                    
                    if not template_df.empty and 'category' in template_df.columns:
                        template_df = template_df.fillna("") 
                        
                        for i, category in enumerate(main_categories):
                            with input_tabs[i]:
                                filtered_df = template_df[template_df['category'] == category]
                                if filtered_df.empty:
                                    st.info("등록된 평가 항목이 없습니다.")
                                else:
                                    sub_cats = filtered_df['sub_category'].unique()
                                    for sub_cat in sub_cats:
                                        if sub_cat.strip() != "":
                                            st.markdown(f"##### 📌 {sub_cat}")
                                        
                                        sub_df = filtered_df[filtered_df['sub_category'] == sub_cat]
                                        for index, row in sub_df.iterrows():
                                            pdca_tag = f" `[{row['pdca']}]`" if row['pdca'] != "" else ""
                                            penalty_tag = f" 🚨**(과태료: {row['penalty']})**" if row['penalty'] != "" else ""
                                            
                                            st.markdown(f"**🔹 {row['item_name']}**{pdca_tag}{penalty_tag} (배점: {row['max_score']}점)")
                                            
                                            c1, c2 = st.columns([5, 1])
                                            with c2: is_na = st.checkbox(f"해당없음", key=f"new_na_{row['id']}")
                                            with c1: 
                                                max_val = int(row['max_score'])
                                                options = list(range(max_val + 1))
                                                score = st.radio("점수", options=options, index=len(options)-1, horizontal=True, key=f"new_score_{row['id']}", disabled=is_na, label_visibility="collapsed")
                                            
                                            input_data[row['id']] = {"score": score, "is_na": is_na, "max": row['max_score']}
                                            st.write("---")

                    st.write("") 
                    if st.form_submit_button("✅ 전체 데이터 최종 저장", use_container_width=True):
                        if site_name:
                            total_score_earned = sum([d["score"] for d in input_data.values() if not d["is_na"]])
                            total_max_possible = sum([d["max"] for d in input_data.values() if not d["is_na"]])
                            final_score = round((total_score_earned / total_max_possible * 100) if total_max_possible > 0 else 0, 1)

                            supabase.table("audit_results").insert({
                                "site_name": site_name, 
                                "site_type": site_type, 
                                "score": final_score, 
                                "details": json.dumps(input_data),
                                "created_by": st.session_state.current_user,
                                "updated_by": st.session_state.current_user
                            }).execute()
                            
                            st.success(f"'{site_name}' 데이터가 저장되었습니다! (최종 점수: {final_score}점)")
                            st.session_state.admin_view = "list"
                            st.rerun()
                        else:
                            st.error("현장명을 입력해주세요.")

            # ---------------------------------------------------------
            # 뷰 모드 3: 기존 데이터 수정 (Edit)
            # ---------------------------------------------------------
            elif st.session_state.admin_view == "edit" and st.session_state.edit_target_id is not None:
                if st.button("⬅️ 목록으로 돌아가기"):
                    st.session_state.admin_view = "list"
                    st.session_state.edit_target_id = None
                    st.rerun()
                
                target_id = st.session_state.edit_target_id
                res_df = load_results()
                selected_row = res_df[res_df['id'] == target_id].iloc[0]
                current_details = json.loads(selected_row['details']) if pd.notna(selected_row['details']) else {}
                
                st.subheader(f"🔄 '{selected_row['현장명']}' 심사 수정")
                st.write("---")
                
                with st.form("edit_form"):
                    col1, col2 = st.columns(2)
                    with col1: edit_site_name = st.text_input("현장명 수정", value=selected_row['현장명'])
                    with col2: 
                        type_list = ["건축", "인프라", "플랜트"]
                        type_idx = type_list.index(selected_row['현장타입']) if selected_row['현장타입'] in type_list else 0
                        edit_site_type = st.selectbox("현장 분류 수정", type_list, index=type_idx)
                    
                    st.markdown("#### 📋 세부 항목 수정")
                    template_df = load_template()
                    edit_input_data = {}
                    
                    if not template_df.empty and 'category' in template_df.columns:
                        template_df = template_df.fillna("")
                        edit_tabs = st.tabs(main_categories)
                        for i, category in enumerate(main_categories):
                            with edit_tabs[i]:
                                filtered_df = template_df[template_df['category'] == category]
                                sub_cats = filtered_df['sub_category'].unique()
                                for sub_cat in sub_cats:
                                    if sub_cat.strip() != "":
                                        st.markdown(f"##### 📌 {sub_cat}")
                                    
                                    sub_df = filtered_df[filtered_df['sub_category'] == sub_cat]
                                    for index, row in sub_df.iterrows():
                                        pdca_tag = f" `[{row['pdca']}]`" if row['pdca'] != "" else ""
                                        penalty_tag = f" 🚨**(과태료: {row['penalty']})**" if row['penalty'] != "" else ""
                                        
                                        st.markdown(f"**🔹 {row['item_name']}**{pdca_tag}{penalty_tag} (배점: {row['max_score']}점)")
                                        
                                        str_id = str(row['id'])
                                        existing_data = current_details.get(str_id, {"score": 0.0, "is_na": False})
                                        
                                        max_val = int(row['max_score'])
                                        saved_score = int(float(existing_data.get("score", 0.0)))
                                        safe_score = min(saved_score, max_val)
                                        options = list(range(max_val + 1))
                                        
                                        try:
                                            default_index = options.index(safe_score)
                                        except ValueError:
                                            default_index = 0
                                        
                                        c1, c2 = st.columns([5, 1])
                                        with c2: edit_is_na = st.checkbox(f"해당없음", value=existing_data.get("is_na", False), key=f"edit_na_{row['id']}")
                                        with c1: 
                                            edit_score = st.radio("점수", options=options, index=default_index, horizontal=True, key=f"edit_score_{row['id']}", disabled=edit_is_na, label_visibility="collapsed")
                                        
                                        edit_input_data[row['id']] = {"score": edit_score, "is_na": edit_is_na, "max": row['max_score']}
                                        st.write("---")
                    
                    submit_col, del_col = st.columns([3, 1])
                    with submit_col:
                        if st.form_submit_button("💾 수정한 내용으로 업데이트", use_container_width=True):
                            total_score_earned = sum([d["score"] for d in edit_input_data.values() if not d["is_na"]])
                            total_max_possible = sum([d["max"] for d in edit_input_data.values() if not d["is_na"]])
                            final_score = round((total_score_earned / total_max_possible * 100) if total_max_possible > 0 else 0, 1)

                            supabase.table("audit_results").update({
                                "site_name": edit_site_name,
                                "site_type": edit_site_type,
                                "score": final_score,
                                "details": json.dumps(edit_input_data),
                                "updated_by": st.session_state.current_user,
                                "updated_at": datetime.utcnow().isoformat()
                            }).eq("id", target_id).execute()
                            
                            st.success(f"성공적으로 업데이트되었습니다!")
                            st.session_state.admin_view = "list"
                            st.session_state.edit_target_id = None
                            st.rerun()

                    with del_col:
                        if st.form_submit_button("🚨 이 데이터 삭제", use_container_width=True):
                            supabase.table("audit_results").delete().eq("id", target_id).execute()
                            st.error("데이터가 완전히 삭제되었습니다.")
                            st.session_state.admin_view = "list"
                            st.session_state.edit_target_id = None
                            st.rerun()

        # ---------------------------------------------------------
        # 분리된 템플릿 탭 (가끔 쓰는 기능)
        # ---------------------------------------------------------
        with template_tab:
            st.subheader("📥 엑셀 파일로 점수표 일괄 업로드")
            uploaded_file = st.file_uploader("엑셀 파일(.xlsx)을 업로드해주세요.", type=['xlsx'])
            
            if uploaded_file is not None:
                try:
                    df_upload = pd.read_excel(uploaded_file)
                    required_columns = ['대분류', '분류', 'PDCA', '점검사항', '과태료', '배점']
                    
                    if all(col in df_upload.columns for col in required_columns):
                        st.dataframe(df_upload, use_container_width=True)
                        if st.button("🚀 업로드한 데이터로 점수표 덮어쓰기"):
                            upload_records = []
                            for _, row in df_upload.iterrows():
                                upload_records.append({
                                    "category": str(row['대분류']),
                                    "sub_category": str(row['분류']) if pd.notna(row['분류']) else "",
                                    "pdca": str(row['PDCA']) if pd.notna(row['PDCA']) else "",
                                    "item_name": str(row['점검사항']),
                                    "penalty": str(row['과태료']) if pd.notna(row['과태료']) else "",
                                    "max_score": int(row['배점'])
                                })
                            
                            supabase.table("checklist_template").delete().gt("id", 0).execute()
                            if upload_records:
                                supabase.table("checklist_template").insert(upload_records).execute()
                            
                            st.success("✅ 엑셀 데이터가 성공적으로 반영되었습니다!")
                            st.rerun()
                    else:
                        st.error(f"⚠️ 엑셀 필수 제목을 확인해주세요: {', '.join(required_columns)}")
                except Exception as e:
                    st.error(f"오류가 발생했습니다: {e}")

            st.divider()
            st.subheader("⚙️ 점수표 웹에서 직접 수정")
            
            temp_df = load_template()
            if temp_df.empty:
                temp_df = pd.DataFrame(columns=['category', 'sub_category', 'pdca', 'item_name', 'penalty', 'max_score'])
            else:
                temp_df = temp_df[['category', 'sub_category', 'pdca', 'item_name', 'penalty', 'max_score']]
                
            edited_df = st.data_editor(
                temp_df, 
                num_rows="dynamic", 
                use_container_width=True,
                column_config={
                    "category": st.column_config.SelectboxColumn("대분류", options=main_categories, required=True),
                    "sub_category": st.column_config.TextColumn("분류"),
                    "pdca": st.column_config.TextColumn("PDCA"),
                    "item_name": st.column_config.TextColumn("점검사항", required=True),
                    "penalty": st.column_config.TextColumn("과태료"),
                    "max_score": st.column_config.NumberColumn("배점", min_value=0, step=1, required=True)
                }
            )
            
            if st.button("💾 위 표의 변경사항을 DB에 저장"):
                supabase.table("checklist_template").delete().gt("id", 0).execute()
                new_records = edited_df.to_dict('records')
                if new_records:
                    supabase.table("checklist_template").insert(new_records).execute()
                st.success("점수표가 업데이트 되었습니다!")
                st.rerun()
