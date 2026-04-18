import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import io
import json
import math
from datetime import datetime, date
from supabase import create_client, Client

# 1. 페이지 설정 및 디자인
st.set_page_config(page_title="GS건설 현장 내부심사 통합 시스템", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #f4f7f9; }
    .board-header { background-color: #495057; color: white; padding: 15px 0; border-radius: 8px; font-weight: bold; text-align: center; display: flex; margin-bottom: 15px; }
    .board-row { background-color: white; border: 1px solid #eee; border-radius: 10px; padding: 18px 0; margin-bottom: 12px; display: flex; align-items: center; box-shadow: 0 2px 5px rgba(0,0,0,0.02); }
    .badge { padding: 6px 14px; border-radius: 20px; font-weight: bold; font-size: 0.85rem; }
    .excellent { background-color: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
    .normal { background-color: #fff3cd; color: #856404; border: 1px solid #ffeeba; }
    .warning { background-color: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
    .sub-text { color: #6c757d; font-size: 0.85rem; }
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

# 세션 상태 관리
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'current_user' not in st.session_state: st.session_state.current_user = ""
if 'admin_view' not in st.session_state: st.session_state.admin_view = "list"
if 'edit_target_id' not in st.session_state: st.session_state.edit_target_id = None

# 3. 데이터 로드 및 가공
def load_template():
    res = supabase.table("checklist_template").select("*").order("id").execute()
    return pd.DataFrame(res.data)

def load_results():
    # 전체 리스트 로드
    res = supabase.table("audit_results").select("*").order("inspection_date", desc=True).execute()
    df = pd.DataFrame(res.data)
    if not df.empty:
        df = df.rename(columns={"site_name": "현장명", "site_type": "현장타입", "score": "최종점수"})
        # 만약 inspection_date가 없으면 created_at으로 대체(안전장치)
        if 'inspection_date' not in df.columns: df['inspection_date'] = df['created_at'].str[:10]
        else: df['inspection_date'] = df['inspection_date'].fillna(df['created_at'].str[:10])
    return df

main_categories = ["1. 방침 수립", "2. 인력 및 예산", "3. 위험성평가", "4. 의견 청취", "5. 교육", "6. 비상대응", "7. 계획수립", "8. 회의점검", "9. 장비관리", "10. 보건관리"]

# ==========================================
# 사이드바 메뉴
# ==========================================
st.sidebar.title("🏗️ GS건설 보건관리")
menu = st.sidebar.radio("메뉴 이동", ["📊 통합 대시보드", "📅 심사 게시판"])

# ==========================================
# [페이지 1] 통합 대시보드 (점검일 기준)
# ==========================================
if menu == "📊 통합 대시보드":
    st.title("🏗️ GS건설 현장 내부심사 통합 대시보드")
    df = load_results()
    template_df = load_template()
    
    if not df.empty and not template_df.empty:
        # --- [Row 1] 랭킹 정보 ---
        r1_c1, r1_c2 = st.columns(2)
        with r1_c1:
            st.markdown("#### 🏆 상위 3위 현장")
            st.table(df.nlargest(3, '최종점수')[['현장명', '현장타입', '최종점수']].reset_index(drop=True))
        with r1_c2:
            st.markdown("#### ⚠️ 하위 3위 현장")
            st.table(df.nsmallest(3, '최종점수')[['현장명', '현장타입', '최종점수']].sort_values('최종점수').reset_index(drop=True))

        st.divider()

        # --- [Row 2] 점수 분포표 & 산점도 (점검 일자 기준) ---
        st.markdown("### 📍 현장 점수 분포 현황")
        r2_c1, r2_c2 = st.columns([3, 2])
        
        with r2_c1:
            st.markdown("**[점수 등급별 현장 리스트]**")
            exc = df[df['최종점수'] >= 95][['현장명', '최종점수']].rename(columns={'현장명':'95점이상 현장', '최종점수':'점수 '})
            nor = df[(df['최종점수'] >= 80) & (df['최종점수'] < 95)][['현장명', '최종점수']].rename(columns={'현장명':'80~95점 현장', '최종점수':'점수  '})
            war = df[df['최종점수'] < 80][['현장명', '최종점수']].rename(columns={'현장명':'80점미만 현장', '최종점수':'점수   '})
            dist_table = pd.concat([exc.reset_index(drop=True), nor.reset_index(drop=True), war.reset_index(drop=True)], axis=1).fillna("-")
            st.dataframe(dist_table, use_container_width=True)
            
        with r2_c2:
            # [대장님 요청] 점검 일자(inspection_date) 기준으로 산점도 정렬
            df_sorted = df.sort_values(by='inspection_date', ascending=True)
            
            fig_scatter = px.scatter(
                df_sorted, 
                x="inspection_date", 
                y="최종점수", 
                color="최종점수",
                hover_name="현장명",
                text="현장명",
                color_continuous_scale=['#dc3545', '#ffc107', '#28a745'],
                range_y=[0, 105],
                title="현장별 점수 분포 (점검 일자순)"
            )
            fig_scatter.update_traces(marker=dict(size=18, opacity=0.8), textposition='top center')
            fig_scatter.update_layout(xaxis_title="점검 실시일 (← 과거 / 현재 →)", yaxis_title="최종 점수")
            st.plotly_chart(fig_scatter, use_container_width=True)

        st.divider()

        # 데이터 심층 분석 로직
        analysis_data = []
        for _, row in df.iterrows():
            details = json.loads(row['details']) if isinstance(row['details'], str) else row['details']
            for item_id, val in details.items():
                t_info = template_df[template_df['id'] == int(item_id)]
                if not t_info.empty and not val.get('is_na', False):
                    analysis_data.append({
                        'site_type': row['현장타입'], 'pdca': t_info.iloc[0]['pdca'],
                        'category': t_info.iloc[0]['category'], 'earned': val['score'], 'max': val['max']
                    })
        a_df = pd.DataFrame(analysis_data)

        if not a_df.empty:
            st.markdown("### 📊 사업부별 / PDCA별 평균 점수")
            pdca_stats = a_df.groupby(['site_type', 'pdca']).apply(lambda x: round((x['earned'].sum() / x['max'].sum()) * 100, 1)).unstack().fillna(0)
            overall_site_avg = df.groupby('현장타입')['최종점수'].mean().round(1)
            pdca_stats.insert(0, '전체 평균', overall_site_avg)
            
            r3_c1, r3_c2 = st.columns([1, 1])
            with r3_c1: st.dataframe(pdca_stats, use_container_width=True)
            with r3_c2:
                fig_radar = px.line_polar(a_df.groupby(['site_type', 'pdca']).apply(lambda x: (x['earned'].sum()/x['max'].sum())*100).reset_index(name='점수'),
                                         r='점수', theta='pdca', color='site_type', line_close=True, title="사업부별 PDCA 밸런스")
                st.plotly_chart(fig_radar, use_container_width=True)
    else:
        st.info("데이터가 없습니다.")

# ==========================================
# [페이지 2] 심사 게시판 (날짜 입력 추가)
# ==========================================
elif menu == "📅 심사 게시판":
    if not st.session_state.logged_in:
        st.title("🔐 관리자 인증")
        with st.form("login"):
            uid = st.text_input("아이디")
            upw = st.text_input("비밀번호", type="password")
            if st.form_submit_button("로그인"):
                if uid in st.secrets["passwords"] and st.secrets["passwords"][uid] == upw:
                    st.session_state.logged_in, st.session_state.current_user = True, uid
                    st.rerun()
    else:
        head_c, user_c = st.columns([5, 1])
        with head_c: st.title("📋 현장 내부심사 게시판")
        with user_c:
            if st.button("로그아웃"): 
                st.session_state.logged_in = False
                st.rerun()
        
        st.divider()
        m_tab, t_tab = st.tabs(["📝 리스트 관리", "⚙️ 점수표 설정"])
        
        with m_tab:
            if st.session_state.admin_view == "list":
                col_s, col_a = st.columns([3, 1])
                sq = col_s.text_input("검색", placeholder="현장명 검색...", label_visibility="collapsed")
                if col_a.button("➕ 신규 심사 등록", type="primary", use_container_width=True):
                    st.session_state.admin_view = "create"
                    st.rerun()
                
                res_df = load_results()
                if not res_df.empty:
                    if sq: res_df = res_df[res_df['현장명'].str.contains(sq)]
                    
                    st.markdown("<div class='board-header'><div style='flex:3;'>현장 제목</div><div style='flex:1;'>분류</div><div style='flex:1.5;'>심사 점수</div><div style='flex:1.5;'>점검 일자</div><div style='flex:1.2;'>관리</div></div>", unsafe_allow_html=True)
                    
                    for _, row in res_df.iterrows():
                        sc = row['최종점수']
                        b_c = "excellent" if sc >= 95 else "normal" if sc >= 80 else "warning"
                        # 점검 일자 표시 (없으면 작성일)
                        disp_date = row.get('inspection_date') if row.get('inspection_date') else str(row['created_at'])[:10]
                        
                        with st.container():
                            r1, r2, r3, r4, r5 = st.columns([3, 1, 1.5, 1.5, 1.2])
                            if r1.button(f"🏢 {row['현장명']}", key=f"t_{row['id']}", use_container_width=True):
                                st.session_state.edit_target_id, st.session_state.admin_view = int(row['id']), "edit"
                                st.rerun()
                            r2.markdown(f"<div style='text-align:center; padding-top:12px;'>{row['현장타입']}</div>", unsafe_allow_html=True)
                            r3.markdown(f"<div style='text-align:center; padding-top:8px;'><span class='badge {b_c}'>{sc}점</span></div>", unsafe_allow_html=True)
                            r4.markdown(f"<div style='text-align:center;' class='sub-text'><b>{disp_date}</b><br>({row.get('updated_by','-')})</div>", unsafe_allow_html=True)
                            with r5:
                                ec, dc = st.columns(2)
                                if ec.button("✏️", key=f"e_{row['id']}"):
                                    st.session_state.edit_target_id, st.session_state.admin_view = int(row['id']), "edit"
                                    st.rerun()
                                if dc.button("🗑️", key=f"d_{row['id']}"):
                                    supabase.table("audit_results").delete().eq("id", row['id']).execute()
                                    st.rerun()
                            st.markdown("<div style='border-bottom:1px solid #eee;'></div>", unsafe_allow_html=True)
            
            elif st.session_state.admin_view in ["create", "edit"]:
                if st.button("⬅️ 목록으로"):
                    st.session_state.admin_view, st.session_state.edit_target_id = "list", None
                    st.rerun()
                
                is_edit = (st.session_state.admin_view == "edit")
                s_name, s_type, s_date, cur_details = "", "건축", date.today(), {}
                if is_edit:
                    r = load_results()
                    target = r[r['id'] == st.session_state.edit_target_id].iloc[0]
                    s_name, s_type, cur_details = target['현장명'], target['현장타입'], json.loads(target['details'])
                    s_date = datetime.strptime(target['inspection_date'], '%Y-%m-%d').date() if target.get('inspection_date') else date.today()
                
                with st.form("audit_form"):
                    f1, f2, f3 = st.columns(3)
                    site_name = f1.text_input("현장명", value=s_name)
                    site_type = f2.selectbox("분류", ["건축", "인프라", "플랜트"], index=["건축", "인프라", "플랜트"].index(s_type))
                    inspection_date = f3.date_input("점검 실시일", value=s_date)
                    
                    st.divider()
                    tabs = st.tabs(main_categories)
                    t_df = load_template().fillna("")
                    res_input = {}
                    for i, cat in enumerate(main_categories):
                        with tabs[i]:
                            items = t_df[t_df['category'] == cat]
                            for _, itm in items.iterrows():
                                st.markdown(f"**🔹 {itm['item_name']}**")
                                prev = cur_details.get(str(itm['id']), {"score": int(itm['max_score']), "is_na": False})
                                c1, c2 = st.columns([5, 1])
                                with c2: na = st.checkbox("N/A", value=prev['is_na'], key=f"na_{itm['id']}")
                                with c1:
                                    m = int(itm['max_score'])
                                    opt = list(range(m + 1))
                                    sc_idx = opt.index(min(int(prev['score']), m)) if int(prev['score']) in opt else m
                                    sc = st.radio("점수", opt, index=sc_idx, horizontal=True, key=f"s_{itm['id']}", disabled=na, label_visibility="collapsed")
                                res_input[itm['id']] = {"score": sc, "is_na": na, "max": itm['max_score']}
                    
                    if st.form_submit_button("✅ 저장"):
                        if site_name:
                            earn = sum([d['score'] for d in res_input.values() if not d['is_na']])
                            poss = sum([d['max'] for d in res_input.values() if not d['is_na']])
                            f_sc = round((earn/poss*100) if poss>0 else 0, 1)
                            payload = {
                                "site_name": site_name, "site_type": site_type, "score": f_sc, 
                                "inspection_date": inspection_date.isoformat(), # 날짜 저장
                                "details": json.dumps(res_input), "updated_by": st.session_state.current_user, 
                                "updated_at": datetime.utcnow().isoformat()
                            }
                            if is_edit: supabase.table("audit_results").update(payload).eq("id", st.session_state.edit_target_id).execute()
                            else:
                                payload["created_by"] = st.session_state.current_user
                                supabase.table("audit_results").insert(payload).execute()
                            st.session_state.admin_view = "list"
                            st.rerun()

        with t_tab:
            st.subheader("⚙️ 템플릿 설정")
            # (생략: 이전과 동일한 템플릿 로직)
