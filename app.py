import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import io
import json
import math
from datetime import datetime
from supabase import create_client, Client

# 1. 페이지 설정 및 디자인
st.set_page_config(page_title="GS건설 현장 내부심사 대시보드", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .board-header { background-color: #495057; color: white; padding: 15px 0; border-radius: 8px; font-weight: bold; text-align: center; display: flex; margin-top: 25px; margin-bottom: 15px; }
    .board-row { background-color: white; border: 1px solid #eee; border-radius: 10px; padding: 18px 0; margin-bottom: 12px; display: flex; align-items: center; transition: all 0.2s; box-shadow: 0 2px 5px rgba(0,0,0,0.02); }
    .board-row:hover { background-color: #f1f8ff; border-color: #007bff; transform: translateY(-1px); }
    .badge { padding: 6px 14px; border-radius: 20px; font-weight: bold; font-size: 0.9rem; }
    .excellent { background-color: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
    .normal { background-color: #fff3cd; color: #856404; border: 1px solid #ffeeba; }
    .warning { background-color: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
    .sub-text { color: #6c757d; font-size: 0.85rem; line-height: 1.4; }
    </style>
    """, unsafe_allow_html=True)

# 2. Supabase 연결
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

# 4. 데이터 로드 및 분석 함수
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
# [페이지 1] 통계 대시보드 (대장님 요청 사항 반영)
# ==========================================
menu = st.sidebar.radio("메뉴 이동", ["📊 통계 대시보드", "📅 심사 게시판"])

if menu == "📊 통계 대시보드":
    st.title("🏗️ 전사 현장 심사 통계 대시보드")
    df = load_results()
    template_df = load_template()
    
    if not df.empty and not template_df.empty:
        # --- [1, 2] 상위/하위 3위 리스트 ---
        st.subheader("🏆 현장 심사 랭킹 (Top & Bottom 3)")
        col_top, col_bottom = st.columns(2)
        
        with col_top:
            st.markdown("#### ✅ 상위 3위 현장")
            top3 = df.nlargest(3, '최종점수')[['현장명', '현장타입', '최종점수']]
            st.table(top3.assign(순위=[1,2,3]).set_index('순위'))
            
        with col_bottom:
            st.markdown("#### ⚠️ 하위 3위 현장")
            bottom3 = df.nsmallest(3, '최종점수')[['현장명', '현장타입', '최종점수']].sort_values(by='최종점수')
            st.table(bottom3.assign(순위=['최하위','2위','3위']).set_index('순위'))

        st.divider()

        # --- [3] 현장 점수 분포표 ---
        st.subheader("📊 현장 점수 분포 현황")
        
        excellent_count = len(df[df['최종점수'] >= 95])
        normal_count = len(df[(df['최종점수'] >= 80) & (df['최종점수'] < 95)])
        warning_count = len(df[df['최종점수'] < 80])
        
        dist_df = pd.DataFrame({
            '구분': ['우수 (95점↑)', '보통 (80~95점)', '주의 (80점↓)'],
            '현장수': [excellent_count, normal_count, warning_count],
            '색상': ['#28a745', '#ffc107', '#dc3545']
        })
        
        col_dist_chart, col_dist_val = st.columns([2, 1])
        with col_dist_chart:
            fig_dist = px.pie(dist_df, values='현장수', names='구분', color='구분',
                             color_discrete_map={'우수 (95점↑)':'#28a745', '보통 (80~95점)':'#ffc107', '주의 (80점↓)':'#dc3545'},
                             hole=0.4)
            st.plotly_chart(fig_dist, use_container_width=True)
        with col_dist_val:
            st.write("")
            st.write("")
            st.metric("총 점검 현장 수", f"{len(df)}개")
            st.write(f"- **우수 현장:** {excellent_count}개")
            st.write(f"- **보통 현장:** {normal_count}개")
            st.write(f"- **주의 현장:** {warning_count}개")

        st.divider()

        # --- [4, 5] 데이터 분석 로직 (JSON 파싱) ---
        # 이 부분은 각 항목의 배점과 획득점을 계산하여 대분류/PDCA별 평균을 냅니다.
        analysis_data = []
        for _, row in df.iterrows():
            details = json.loads(row['details']) if isinstance(row['details'], str) else row['details']
            for item_id, val in details.items():
                # 템플릿 정보 매칭
                t_info = template_df[template_df['id'] == int(item_id)]
                if not t_info.empty and not val['is_na']:
                    analysis_data.append({
                        'site_type': row['현장타입'],
                        'category': t_info.iloc[0]['category'],
                        'pdca': t_info.iloc[0]['pdca'],
                        'earned': val['score'],
                        'max': val['max']
                    })
        
        analysis_df = pd.DataFrame(analysis_data)
        
        if not analysis_df.empty:
            # --- [4] 대분류 별 평균 점수 (사업부별) ---
            st.subheader("📈 사업부별 대분류 평균 점수 (100점 만점 환산)")
            cat_stats = analysis_df.groupby(['site_type', 'category']).agg({'earned':'sum', 'max':'sum'}).reset_index()
            cat_stats['평균점수'] = round((cat_stats['earned'] / cat_stats['max']) * 100, 1)
            
            fig_cat = px.bar(cat_stats, x='category', y='평균점수', color='site_type', barmode='group',
                            title="대분류별 성과 비교", labels={'category':'대분류', '평균점수':'환산 점수'})
            fig_cat.update_layout(xaxis={'categoryorder':'array', 'categoryarray': main_categories})
            st.plotly_chart(fig_cat, use_container_width=True)

            st.divider()

            # --- [5] 사업부별 PDCA 평균 점수 ---
            st.subheader("🔄 사업부별 PDCA 단계별 분석")
            pdca_stats = analysis_df.groupby(['site_type', 'pdca']).agg({'earned':'sum', 'max':'sum'}).reset_index()
            pdca_stats['평균점수'] = round((pdca_stats['earned'] / pdca_stats['max']) * 100, 1)
            
            # 전체 평균 추가
            total_pdca = analysis_df.groupby('pdca').agg({'earned':'sum', 'max':'sum'}).reset_index()
            total_pdca['평균점수'] = round((total_pdca['earned'] / total_possible) * 100, 1) if 'total_possible' in locals() else round((total_pdca['earned'] / total_pdca['max']) * 100, 1)
            total_pdca['site_type'] = '전체 평균'
            
            combined_pdca = pd.concat([pdca_stats, total_pdca])
            combined_pdca = combined_pdca[combined_pdca['pdca'].isin(['P', 'D', 'C', 'A'])] # PDCA만 필터링
            
            fig_pdca = px.line_polar(combined_pdca, r='평균점수', theta='pdca', color='site_type', line_close=True,
                                    template="plotly_dark", title="PDCA 밸런스 차트")
            st.plotly_chart(fig_pdca, use_container_width=True)
            
            st.info("💡 **PDCA 분석 가이드:** 차트가 바깥쪽으로 넓게 퍼질수록 해당 단계의 관리가 잘 되고 있음을 의미합니다.")
    else:
        st.info("충분한 분석 데이터가 없습니다. 먼저 현장 심사 결과를 등록해주세요.")

# ==========================================
# [페이지 2] 심사 게시판 (기존 코드와 동일)
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
            # --- [목록 보기] ---
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

                        with st.container():
                            r1, r2, r3, r4, r5 = st.columns([3, 1, 1.5, 1.5, 1.2])
                            if r1.button(f"🏢 {row['현장명']}", key=f"t_{row['id']}", use_container_width=True):
                                st.session_state.edit_target_id = int(row['id'])
                                st.session_state.admin_view = "edit"
                                st.rerun()
                            r2.markdown(f"<div style='text-align:center; padding-top:12px;'>{row['현장타입']}</div>", unsafe_allow_html=True)
                            r3.markdown(f"<div style='text-align:center; padding-top:8px;'><span class='badge {b_c}'>{score}점 ({b_t})</span></div>", unsafe_allow_html=True)
                            u_by = row.get('updated_by', '알수없음')
                            r4.markdown(f"<div style='text-align:center;' class='sub-text'>{u_by}<br>{str(row['created_at'])[:10]}</div>", unsafe_allow_html=True)
                            with r5:
                                edit_c, del_c = st.columns(2)
                                if edit_c.button("✏️", key=f"e_{row['id']}"):
                                    st.session_state.edit_target_id = int(row['id'])
                                    st.session_state.admin_view = "edit"
                                    st.rerun()
                                if del_c.button("🗑️", key=f"d_{row['id']}"):
                                    supabase.table("audit_results").delete().eq("id", row['id']).execute()
                                    st.rerun()
                else:
                    st.info("내역이 없습니다.")

            # --- [신규/수정 폼] (중복 방지를 위해 기존 로직 유지) ---
            elif st.session_state.admin_view in ["create", "edit"]:
                if st.button("⬅️ 목록으로 돌아가기"):
                    st.session_state.admin_view = "list"
                    st.rerun()
                
                is_edit = (st.session_state.admin_view == "edit")
                current_data = {}
                s_name, s_type = "", "건축"
                
                if is_edit:
                    res_df = load_results()
                    row = res_df[res_df['id'] == st.session_state.edit_target_id].iloc[0]
                    s_name, s_type = row['현장명'], row['현장타입']
                    current_data = json.loads(row['details']) if pd.notna(row['details']) else {}

                with st.form("audit_form"):
                    f1, f2 = st.columns(2)
                    site_name = f1.text_input("현장명", value=s_name)
                    site_type = f2.selectbox("현장 분류", ["건축", "인프라", "플랜트"], index=["건축", "인프라", "플랜트"].index(s_type) if s_type in ["건축", "인프라", "플랜트"] else 0)
                    
                    st.divider()
                    tabs = st.tabs(main_categories)
                    template_df_input = load_template().fillna("")
                    input_results = {}

                    for i, cat in enumerate(main_categories):
                        with tabs[i]:
                            filtered = template_df_input[template_df_input['category'] == cat]
                            for _, t_row in filtered.iterrows():
                                st.markdown(f"**🔹 {t_row['item_name']}**")
                                prev = current_data.get(str(t_row['id']), {"score": int(t_row['max_score']), "is_na": False})
                                c1, c2 = st.columns([5, 1])
                                with c2: na_val = st.checkbox("해당없음", value=prev['is_na'], key=f"na_{t_row['id']}")
                                with c1:
                                    m_score = int(t_row['max_score'])
                                    opts = list(range(m_score + 1))
                                    def_idx = opts.index(min(int(prev['score']), m_score)) if int(prev['score']) in opts else len(opts)-1
                                    score_val = st.radio("점수", options=opts, index=def_idx, horizontal=True, key=f"sc_{t_row['id']}", disabled=na_val, label_visibility="collapsed")
                                input_results[t_row['id']] = {"score": score_val, "is_na": na_val, "max": t_row['max_score']}

                    if st.form_submit_button("✅ 최종 저장하기"):
                        if site_name:
                            total_earned = sum([d['score'] for d in input_results.values() if not d['is_na']])
                            total_possible = sum([d['max'] for d in input_results.values() if not d['is_na']])
                            final_score = round((total_earned / total_possible * 100) if total_possible > 0 else 0, 1)
                            db_data = {"site_name": site_name, "site_type": site_type, "score": final_score, "details": json.dumps(input_results), "updated_by": st.session_state.current_user, "updated_at": datetime.utcnow().isoformat()}
                            if is_edit: supabase.table("audit_results").update(db_data).eq("id", st.session_state.edit_target_id).execute()
                            else: 
                                db_data["created_by"] = st.session_state.current_user
                                supabase.table("audit_results").insert(db_data).execute()
                            st.session_state.admin_view = "list"
                            st.rerun()

        with t_tab:
            # --- [템플릿 설정] ---
            st.subheader("⚙️ 시스템 설정")
            up_file = st.file_uploader("엑셀 업로드", type=['xlsx'])
            if up_file and st.button("🚀 업로드 실행"):
                df_up = pd.read_excel(up_file)
                recs = []
                for _, r in df_up.iterrows():
                    recs.append({"category": str(r['대분류']), "sub_category": str(r.get('분류', '')), "pdca": str(r.get('PDCA', '')), "item_name": str(r['점검사항']), "penalty": str(r.get('과태료', '')), "max_score": int(r['배점'])})
                supabase.table("checklist_template").delete().gt("id", 0).execute()
                supabase.table("checklist_template").insert(recs).execute()
                st.rerun()
