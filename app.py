import streamlit as st
import pandas as pd
import plotly.express as px
import io
import json
import math
from datetime import datetime
from supabase import create_client, Client

# 1. 페이지 설정 및 디자인 (CSS)
st.set_page_config(page_title="GS건설 현장 내부심사 시스템", layout="wide")

st.markdown("""
    <style>
    /* 메인 배경색 및 글꼴 */
    .main { background-color: #f8f9fa; }
    
    /* 게시판 헤더 스타일 */
    .board-header {
        background-color: #495057;
        color: white;
        padding: 12px 0;
        border-radius: 8px 8px 0 0;
        font-weight: bold;
        text-align: center;
        display: flex;
        margin-top: 20px;
    }
    
    /* 게시판 행 스타일 */
    .board-row {
        background-color: white;
        border-bottom: 1px solid #dee2e6;
        padding: 10px 0;
        display: flex;
        align-items: center;
        transition: all 0.2s;
    }
    .board-row:hover { background-color: #f1f8ff; }

    /* 점수 뱃지 스타일 */
    .badge {
        padding: 5px 12px;
        border-radius: 20px;
        font-weight: bold;
        font-size: 0.85rem;
    }
    .excellent { background-color: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
    .normal { background-color: #fff3cd; color: #856404; border: 1px solid #ffeeba; }
    .warning { background-color: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
    
    /* 텍스트 가독성 */
    .sub-text { color: #6c757d; font-size: 0.8rem; line-height: 1.2; }
    .site-name-btn button {
        font-weight: 600 !important;
        color: #007bff !important;
        text-align: left !important;
        border: none !important;
        background: none !important;
        padding: 0 !important;
    }
    </style>
    """, unsafe_allow_html=True)

# 2. Supabase 연결 함수
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

# 3. 세션 상태 관리
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'current_user' not in st.session_state: st.session_state.current_user = ""
if 'admin_view' not in st.session_state: st.session_state.admin_view = "list"
if 'edit_target_id' not in st.session_state: st.session_state.edit_target_id = None

# 4. 데이터 로드 함수들
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
    "1. 방침 수립, 조직상황, 성과평가, 내부심사", "2. 인력 및 예산", "3. 위험성평가 및 이행",
    "4. 종사자 의견 청취 및 개선 조치", "5. 안전보건교육", "6. 비상 시 대응 계획 및 사고관리",
    "7. 계획 수립", "8. 회의 및 점검", "9. 장비 안전관리 (건기법 포함)", "10. 보건관리"
]

# ==========================================
# 사이드바 메뉴
# ==========================================
st.sidebar.title("🏗️ GS건설 보건관리")
menu = st.sidebar.radio("메뉴 이동", ["📊 통계 대시보드", "📅 심사 게시판"])

# ==========================================
# [페이지 1] 통계 대시보드
# ==========================================
if menu == "📊 통계 대시보드":
    st.title("🏗️ 전사 현장 심사 통계")
    df = load_results()
    if not df.empty:
        c1, c2, c3 = st.columns(3)
        c1.metric("총 점검 현장", f"{len(df)}개")
        c2.metric("전체 평균", f"{round(df['최종점수'].mean(), 1)}점")
        c3.metric("최고 점수", f"{df['최종점수'].max()}점")
        
        st.divider()
        fig = px.bar(df, x='현장명', y='최종점수', color='최종점수', color_continuous_scale='RdYlGn', range_y=[0, 105])
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("데이터가 없습니다.")

# ==========================================
# [페이지 2] 심사 게시판 (핵심)
# ==========================================
elif menu == "📅 심사 게시판":
    if not st.session_state.logged_in:
        st.title("🔐 관리자 인증")
        with st.form("login_form"):
            uid = st.text_input("아이디")
            upw = st.text_input("비밀번호", type="password")
            if st.form_submit_button("로그인"):
                pw_dict = st.secrets["passwords"]
                if uid in pw_dict and pw_dict[uid] == upw:
                    st.session_state.logged_in = True
                    st.session_state.current_user = uid
                    st.rerun()
                else: st.error("정보가 일치하지 않습니다.")
    else:
        # 로그인 성공 후 헤더
        head_c, user_c = st.columns([5, 1])
        with head_c: st.title("📋 현장 내부심사 게시판")
        with user_c:
            st.write(f"👤 **{st.session_state.current_user}**님")
            if st.button("로그아웃"): 
                st.session_state.logged_in = False
                st.rerun()

        st.divider()
        m_tab, t_tab = st.tabs(["📝 심사 목록 관리", "⚙️ 점수표(템플릿) 설정"])

        with m_tab:
            # ---------------------------------------------------------
            # 1. 목록 보기 (대장님 요청 5열 레이아웃)
            # ---------------------------------------------------------
            if st.session_state.admin_view == "list":
                col_search, col_add = st.columns([3, 1])
                with col_search:
                    sq = st.text_input("검색", placeholder="🔍 현장명을 입력하세요...", label_visibility="collapsed")
                with col_add:
                    if st.button("➕ 신규 심사 등록", type="primary", use_container_width=True):
                        st.session_state.admin_view = "create"
                        st.rerun()

                res_df = load_results()
                if not res_df.empty:
                    if sq: res_df = res_df[res_df['현장명'].str.contains(sq)]
                    
                    # 게시판 헤더 가이드
                    st.markdown("""
                        <div class='board-header'>
                            <div style='flex: 3;'>현장 제목</div>
                            <div style='flex: 1;'>분류</div>
                            <div style='flex: 1.5;'>심사 점수</div>
                            <div style='flex: 1.5;'>작성 정보</div>
                            <div style='flex: 1.2;'>관리</div>
                        </div>
                    """, unsafe_allow_html=True)

                    for _, row in res_df.iterrows():
                        score = row['최종점수']
                        if score >= 95: b_c, b_t = "excellent", "우수"
                        elif score >= 80: b_c, b_t = "normal", "보통"
                        else: b_c, b_t = "warning", "주의"

                        # 커스텀 행 시작
                        with st.container():
                            r1, r2, r3, r4, r5 = st.columns([3, 1, 1.5, 1.5, 1.2])
                            
                            # 1. 제목 (클릭 시 수정)
                            if r1.button(f"🏢 {row['현장명']}", key=f"t_{row['id']}", use_container_width=True):
                                st.session_state.edit_target_id = int(row['id'])
                                st.session_state.admin_view = "edit"
                                st.rerun()
                            
                            # 2. 분류
                            r2.markdown(f"<div style='text-align:center; padding-top:10px;'>{row['현장타입']}</div>", unsafe_allow_html=True)
                            
                            # 3. 점수 뱃지
                            r3.markdown(f"<div style='text-align:center; padding-top:5px;'><span class='badge {b_c}'>{score}점 ({b_t})</span></div>", unsafe_allow_html=True)
                            
                            # 4. 작성 정보
                            u_by = row.get('updated_by', '알수없음')
                            r4.markdown(f"<div style='text-align:center;' class='sub-text'>{u_by}<br>{str(row['created_at'])[:10]}</div>", unsafe_allow_html=True)
                            
                            # 5. 관리 버튼 (수정/삭제)
                            with r5:
                                edit_c, del_c = st.columns(2)
                                if edit_c.button("✏️", key=f"e_{row['id']}", help="수정"):
                                    st.session_state.edit_target_id = int(row['id'])
                                    st.session_state.admin_view = "edit"
                                    st.rerun()
                                if del_c.button("🗑️", key=f"d_{row['id']}", help="삭제"):
                                    supabase.table("audit_results").delete().eq("id", row['id']).execute()
                                    st.success("삭제되었습니다.")
                                    st.rerun()
                            st.markdown("<div style='border-bottom: 1px solid #eee;'></div>", unsafe_allow_html=True)
                else:
                    st.info("내역이 없습니다.")

            # ---------------------------------------------------------
            # 2. 신규 등록 및 수정 폼 (공통 로직)
            # ---------------------------------------------------------
            elif st.session_state.admin_view in ["create", "edit"]:
                if st.button("⬅️ 목록으로 돌아가기"):
                    st.session_state.admin_view = "list"
                    st.session_state.edit_target_id = None
                    st.rerun()
                
                # 수정 시 데이터 불러오기
                is_edit = (st.session_state.admin_view == "edit")
                current_data = {}
                s_name, s_type = "", "건축"
                
                if is_edit:
                    res_df = load_results()
                    row = res_df[res_df['id'] == st.session_state.edit_target_id].iloc[0]
                    s_name, s_type = row['현장명'], row['현장타입']
                    current_data = json.loads(row['details']) if pd.notna(row['details']) else {}

                st.subheader(f"📝 {'심사 내역 수정' if is_edit else '신규 심사 등록'}")
                
                with st.form("audit_form"):
                    f1, f2 = st.columns(2)
                    site_name = f1.text_input("현장명", value=s_name)
                    site_type = f2.selectbox("현장 분류", ["건축", "인프라", "플랜트"], index=["건축", "인프라", "플랜트"].index(s_type) if s_type in ["건축", "인프라", "플랜트"] else 0)
                    
                    st.divider()
                    tabs = st.tabs(main_categories)
                    template_df = load_template().fillna("")
                    input_results = {}

                    for i, cat in enumerate(main_categories):
                        with tabs[i]:
                            filtered = template_df[template_df['category'] == cat]
                            if filtered.empty:
                                st.info("문항이 없습니다.")
                            else:
                                for _, t_row in filtered.iterrows():
                                    st.markdown(f"**🔹 {t_row['item_name']}**")
                                    if t_row['penalty']: st.markdown(f":red[*(과태료: {t_row['penalty']})*]")
                                    
                                    # 기존 데이터 매칭
                                    prev = current_data.get(str(t_row['id']), {"score": int(t_row['max_score']), "is_na": False})
                                    
                                    c1, c2 = st.columns([5, 1])
                                    with c2: na_val = st.checkbox("해당없음", value=prev['is_na'], key=f"na_{t_row['id']}")
                                    with c1:
                                        m_score = int(t_row['max_score'])
                                        opts = list(range(m_score + 1))
                                        # 안전한 인덱스 설정
                                        def_idx = opts.index(min(int(prev['score']), m_score)) if int(prev['score']) in opts else len(opts)-1
                                        score_val = st.radio("점수 선택", options=opts, index=def_idx, horizontal=True, key=f"sc_{t_row['id']}", disabled=na_val, label_visibility="collapsed")
                                    
                                    input_results[t_row['id']] = {"score": score_val, "is_na": na_val, "max": t_row['max_score']}
                                    st.write("---")

                    if st.form_submit_button("✅ 최종 저장하기", use_container_width=True):
                        if not site_name:
                            st.error("현장명을 입력해주세요.")
                        else:
                            total_earned = sum([d['score'] for d in input_results.values() if not d['is_na']])
                            total_possible = sum([d['max'] for d in input_results.values() if not d['is_na']])
                            final_score = round((total_earned / total_possible * 100) if total_possible > 0 else 0, 1)
                            
                            db_data = {
                                "site_name": site_name, "site_type": site_type, "score": final_score,
                                "details": json.dumps(input_results), "updated_by": st.session_state.current_user,
                                "updated_at": datetime.utcnow().isoformat()
                            }
                            
                            if is_edit:
                                supabase.table("audit_results").update(db_data).eq("id", st.session_state.edit_target_id).execute()
                            else:
                                db_data["created_by"] = st.session_state.current_user
                                supabase.table("audit_results").insert(db_data).execute()
                            
                            st.success("성공적으로 저장되었습니다!")
                            st.session_state.admin_view = "list"
                            st.rerun()

        # ---------------------------------------------------------
        # 3. 템플릿(점수표) 설정 탭
        # ---------------------------------------------------------
        with t_tab:
            st.subheader("📥 엑셀 업로드 (대분류, 분류, PDCA, 점검사항, 과태료, 배점)")
            up_file = st.file_uploader("파일 선택", type=['xlsx'])
            if up_file:
                df_up = pd.read_excel(up_file)
                st.dataframe(df_up.head())
                if st.button("🚀 이 데이터로 점수표 덮어쓰기"):
                    recs = []
                    for _, r in df_up.iterrows():
                        recs.append({
                            "category": str(r['대분류']), "sub_category": str(r.get('분류', '')),
                            "pdca": str(r.get('PDCA', '')), "item_name": str(r['점검사항']),
                            "penalty": str(r.get('과태료', '')), "max_score": int(r['배점'])
                        })
                    supabase.table("checklist_template").delete().gt("id", 0).execute()
                    supabase.table("checklist_template").insert(recs).execute()
                    st.success("업데이트 완료!")
                    st.rerun()
            
            st.divider()
            st.subheader("⚙️ 웹에서 직접 수정")
            tmp_df = load_template()[['category', 'sub_category', 'pdca', 'item_name', 'penalty', 'max_score']]
            edt_df = st.data_editor(tmp_df, num_rows="dynamic", use_container_width=True)
            if st.button("💾 변경사항 저장"):
                recs = edt_df.to_dict('records')
                supabase.table("checklist_template").delete().gt("id", 0).execute()
                supabase.table("checklist_template").insert(recs).execute()
                st.success("저장되었습니다.")
