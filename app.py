import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import io
import json
import math
from datetime import datetime, date
from supabase import create_client, Client

# ==========================================
# 1. 페이지 설정 및 디자인
# ==========================================
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
    .incomplete { background-color: #e9ecef; color: #495057; border: 1px solid #dee2e6; }
    .missing-tag { color: #d63384; font-size: 0.75rem; margin-top: 4px; font-weight: 500; }
    .sub-text { color: #6c757d; font-size: 0.85rem; }
    .stProgress > div > div > div > div { background-color: #28a745; }
    div[data-baseweb="select"] { font-size: 1.05rem !important; font-weight: bold !important; text-align: center !important; cursor: pointer; }
    
    /* 플로팅 저장 버튼 고정 스타일 */
    div.st-key-floating_save {
        position: fixed;
        bottom: 40px;
        right: 40px;
        z-index: 99999;
    }
    div.st-key-floating_save > button {
        border-radius: 50px !important;
        padding: 15px 30px !important;
        font-size: 1.1rem !important;
        box-shadow: 0px 8px 24px rgba(0, 123, 255, 0.4) !important;
        transition: all 0.3s ease !important;
    }
    div.st-key-floating_save > button:hover {
        transform: translateY(-5px) !important;
        box-shadow: 0px 12px 28px rgba(0, 123, 255, 0.6) !important;
    }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. Supabase 연결
# ==========================================
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

if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'current_user' not in st.session_state: st.session_state.current_user = ""
if 'admin_view' not in st.session_state: st.session_state.admin_view = "list"
if 'edit_target_id' not in st.session_state: st.session_state.edit_target_id = None

# ==========================================
# 3. 데이터 로드 및 가공
# ==========================================
def load_template():
    res = supabase.table("checklist_template").select("*").order("id").execute()
    return pd.DataFrame(res.data)

def load_results():
    res = supabase.table("audit_results").select("*").order("inspection_date", desc=True).execute()
    df = pd.DataFrame(res.data)
    if not df.empty:
        df = df.rename(columns={"site_name": "현장명", "site_type": "현장타입", "score": "최종점수"})
        if 'inspection_date' not in df.columns: df['inspection_date'] = df['created_at'].str[:10]
        else: df['inspection_date'] = df['inspection_date'].fillna(df['created_at'].str[:10])
    return df

main_categories = [
    "1. 방침 수립, 조직상황, 성과평가, 내부심사", "2. 인력 및 예산", "3. 위험성평가 및 이행",
    "4. 종사자 의견 청취 및 개선 조치", "5. 안전보건교육", "6. 비상 시 대응 계획 및 사고관리",
    "7. 계획 수립", "8. 회의 및 점검", "9. 장비 안전관리 (건기법 포함)", "10. 보건관리"
]

st.sidebar.title("🏗️ GS건설 내부심사")
menu = st.sidebar.radio("메뉴 이동", ["📊 통합 대시보드", "📅 로그인/점수 입력"])

# ==========================================
# [페이지 1] 통합 대시보드 (오류 철통 방어 적용)
# ==========================================
if menu == "📊 통합 대시보드":
    st.title("🏗️ GS건설 현장 내부심사 통합 대시보드")
    
    df = load_results()
    template_df = load_template()
    
    # [방어 1] 내용물이 있는 유효한 현장 데이터만 필터링 (빈 껍데기 방 제외)
    valid_rows = []
    if not df.empty:
        for _, row in df.iterrows():
            d = row.get('details')
            d_dict = json.loads(d) if isinstance(d, str) and d else d
            if isinstance(d_dict, dict) and len(d_dict) > 0:
                valid_rows.append(row)
    dash_df = pd.DataFrame(valid_rows)
    
    if dash_df.empty:
        st.info("💡 아직 점수가 입력된 현장 심사 데이터가 없습니다. 게시판에서 심사를 진행해주세요!")
    elif template_df.empty:
        st.warning("💡 기준이 될 템플릿(점수표) 데이터가 없습니다. 마스터 설정에서 엑셀을 업로드해주세요.")
    else:
        # 1. 랭킹
        r1_c1, r1_c2 = st.columns(2)
        with r1_c1:
            st.markdown("#### 🏆 상위 3위 현장")
            st.table(dash_df.nlargest(3, '최종점수')[['현장명', '현장타입', '최종점수']].reset_index(drop=True))
        with r1_c2:
            st.markdown("#### ⚠️ 하위 3위 현장")
            st.table(dash_df.nsmallest(3, '최종점수')[['현장명', '현장타입', '최종점수']].sort_values('최종점수').reset_index(drop=True))
        st.divider()

        # 2. 분포도
        st.markdown("### 📍 현장 점수 분포 현황")
        r2_c1, r2_c2 = st.columns([3, 2])
        with r2_c1:
            exc = dash_df[dash_df['최종점수'] >= 95][['현장명', '최종점수']].rename(columns={'현장명':'95점이상 현장', '최종점수':'점수 '})
            nor = dash_df[(dash_df['최종점수'] >= 80) & (dash_df['최종점수'] < 95)][['현장명', '최종점수']].rename(columns={'현장명':'80~95점 현장', '최종점수':'점수  '})
            war = dash_df[dash_df['최종점수'] < 80][['현장명', '최종점수']].rename(columns={'현장명':'80점미만 현장', '최종점수':'점수   '})
            dist_table = pd.concat([exc.reset_index(drop=True), nor.reset_index(drop=True), war.reset_index(drop=True)], axis=1).fillna("-")
            st.dataframe(dist_table, use_container_width=True)
        with r2_c2:
            df_sorted = dash_df.sort_values(by='inspection_date', ascending=True)
            fig_scatter = px.scatter(df_sorted, x="inspection_date", y="최종점수", color="최종점수", hover_name="현장명", text="현장명", color_continuous_scale=['#dc3545', '#ffc107', '#28a745'], range_y=[0, 105], title="현장별 점수 분포 (점검 일자순)")
            fig_scatter.update_traces(marker=dict(size=18, opacity=0.8), textposition='top center')
            st.plotly_chart(fig_scatter, use_container_width=True)
        st.divider()

        # 세부 분석 데이터 파싱
        analysis_data = []
        for _, row in dash_df.iterrows():
            details = json.loads(row['details']) if isinstance(row['details'], str) else row['details']
            for item_id, val in details.items():
                t_info = template_df[template_df['id'].astype(str) == str(item_id)]
                if not t_info.empty and isinstance(val, dict):
                    if not val.get('is_na', False) and val.get('score') is not None:
                        analysis_data.append({
                            'site_type': row['현장타입'], 'pdca': t_info.iloc[0]['pdca'],
                            'category': t_info.iloc[0]['category'], 'item_name': t_info.iloc[0]['item_name'],
                            'earned': val['score'], 'max': val['max']
                        })
        a_df = pd.DataFrame(analysis_data)

        if a_df.empty:
            st.info("💡 아직 세부 문항 점수가 채점된 현장이 없습니다.")
        else:
            # [방어 2] ZeroDivisionError 방지 안전 함수
            def calc_score_safe(x):
                tm = x['max'].sum()
                return round((x['earned'].sum() / tm) * 100, 1) if tm > 0 else 0
                
            def calc_rate_safe(x): 
                tm = x['max'].sum()
                return pd.Series({'achieve_rate': round((x['earned'].sum() / tm) * 100, 1) if tm > 0 else 0})

            # 3. 취약항목 및 트렌드
            r3_c1, r3_c2 = st.columns(2)
            with r3_c1:
                st.markdown("### 🚨 전사 취약 항목 TOP 5")
                item_stats = a_df.groupby('item_name').apply(calc_rate_safe).reset_index()
                bottom_5 = item_stats.nsmallest(5, 'achieve_rate')
                fig_bot5 = px.bar(bottom_5, x='achieve_rate', y='item_name', orientation='h', title="평균 획득률 (%)", color='achieve_rate', color_continuous_scale='Reds_r', range_x=[0, 100])
                st.plotly_chart(fig_bot5, use_container_width=True)
                
            with r3_c2:
                st.markdown("### 📈 개별 현장 점수 트렌드 추이")
                sel_site = st.selectbox("조회할 현장을 선택하세요", dash_df['현장명'].unique(), label_visibility="collapsed")
                trend_df = dash_df[dash_df['현장명'] == sel_site].sort_values('inspection_date')
                fig_trend = px.line(trend_df, x='inspection_date', y='최종점수', markers=True, title=f"'{sel_site}' 점수 변화 추이", range_y=[0, 105])
                fig_trend.update_traces(marker=dict(size=10), line=dict(width=3, color='#007bff'))
                st.plotly_chart(fig_trend, use_container_width=True)
            st.divider()

            # 4. 사업부/PDCA 통계
            st.markdown("### 📊 사업부별 / PDCA별 평균 점수")
            pdca_stats = a_df.groupby(['site_type', 'pdca']).apply(calc_score_safe).unstack().fillna(0)
            overall_site_avg = dash_df.groupby('현장타입')['최종점수'].mean().round(1)
            pdca_stats.insert(0, '전체 평균', overall_site_avg)
            
            r4_c1, r4_c2 = st.columns([1, 1])
            with r4_c1: st.dataframe(pdca_stats, use_container_width=True)
            with r4_c2:
                fig_radar = px.line_polar(a_df.groupby(['site_type', 'pdca']).apply(calc_score_safe).reset_index(name='점수'),
                                         r='점수', theta='pdca', color='site_type', line_close=True, title="사업부별 PDCA 밸런스")
                st.plotly_chart(fig_radar, use_container_width=True)
            st.divider()

            # 5. 대분류 통계
            st.markdown("### 📋 대분류 항목별 사업부 점수 비교")
            cat_stats = a_df.groupby(['category', 'site_type']).apply(calc_score_safe).unstack().fillna(0)
            ordered_cats = [cat.strip() for cat in main_categories if cat.strip() in cat_stats.index]
            cat_stats = cat_stats.reindex(ordered_cats)
            cat_stats.insert(0, '평균 점수', cat_stats.mean(axis=1).round(1))
            st.dataframe(cat_stats, use_container_width=True)

# ==========================================
# [페이지 2] 심사 게시판
# ==========================================
elif menu == "📅 로그인/점수 입력":
    if not st.session_state.logged_in:
        st.title("🔐 관리자 인증")
        with st.form("login"):
            uid = st.text_input("아이디")
            upw = st.text_input("비밀번호", type="password")
            if st.form_submit_button("로그인"):
                if uid in st.secrets["passwords"] and st.secrets["passwords"][uid] == upw:
                    st.session_state.logged_in, st.session_state.current_user = True, uid
                    st.rerun()
                else: st.error("정보가 일치하지 않습니다.")
    else:
        head_c, user_c = st.columns([5, 1])
        with head_c: st.title("📋 현장 내부심사 게시판")
        with user_c:
            if st.button("로그아웃"): 
                st.session_state.logged_in = False
                st.rerun()
        
        st.divider()
        m_tab, t_tab = st.tabs(["📝 리스트 관리", "⚙️ 점수표(마스터) 설정"])
        
        with m_tab:
            # ---------------------------------------------------------
            # 게시판 목록
            # ---------------------------------------------------------
            if st.session_state.admin_view == "list":
                if st.session_state.get('flash_msg'):
                    st.info(st.session_state.flash_msg)
                    st.session_state.flash_msg = "" 
                
                col_s, col_a = st.columns([3, 1])
                sq = col_s.text_input("검색", placeholder="현장명 검색...", label_visibility="collapsed")
                if col_a.button("➕ 신규 심사 등록 (방 만들기)", type="primary", use_container_width=True):
                    st.session_state.admin_view = "create"
                    st.rerun()
                
                res_df = load_results()
                t_df = load_template()
                
                if not res_df.empty:
                    if sq: res_df = res_df[res_df['현장명'].str.contains(sq)]
                    st.markdown("<div class='board-header'><div style='flex:3;'>현장 제목 및 미입력 현황</div><div style='flex:1;'>분류</div><div style='flex:1.5;'>입력 상태</div><div style='flex:1.5;'>점검 일자</div><div style='flex:1.2;'>관리</div></div>", unsafe_allow_html=True)
                    
                    for _, row in res_df.iterrows():
                        details_dict = json.loads(row['details']) if row['details'] else {}
                        
                        missing_parts = []
                        total_q = len(t_df)
                        answered_q = 0
                        
                        if not t_df.empty:
                            for _, itm in t_df.iterrows():
                                iid = str(itm['id'])
                                data = details_dict.get(iid)
                                if data and (data.get('is_na') or data.get('score') is not None):
                                    answered_q += 1
                            
                            for cat in main_categories:
                                cat_items = t_df[t_df['category'] == cat.strip()]
                                if not cat_items.empty:
                                    cat_answered = True
                                    for _, ci in cat_items.iterrows():
                                        cid = str(ci['id'])
                                        if not details_dict.get(cid) or (not details_dict[cid].get('is_na') and details_dict[cid].get('score') is None):
                                            cat_answered = False
                                            break
                                    if not cat_answered:
                                        missing_parts.append(cat.split('.')[1].strip() if len(cat.split('.')) > 1 else cat.strip())

                        progress_pct = int((answered_q / total_q) * 100) if total_q > 0 else 0
                        sc = row['최종점수']
                        
                        if progress_pct == 0: b_c, b_t = "incomplete", "입력대기"
                        elif progress_pct < 100: b_c, b_t = "warning", f"작성중 ({progress_pct}%)"
                        else:
                            if sc >= 95: b_c, b_t = "excellent", f"{sc}점"
                            elif sc >= 80: b_c, b_t = "normal", f"{sc}점"
                            else: b_c, b_t = "warning", f"{sc}점"

                        with st.container():
                            r1, r2, r3, r4, r5 = st.columns([3, 1, 1.5, 1.5, 1.2])
                            with r1:
                                if st.button(f"🏢 {row['현장명']}", key=f"t_{row['id']}", use_container_width=True):
                                    st.session_state.edit_target_id, st.session_state.admin_view = int(row['id']), "edit"
                                    st.rerun()
                                if missing_parts and progress_pct < 100:
                                    st.markdown(f"<div class='missing-tag'>⚠️ 미입력: {', '.join(missing_parts[:3])}{'...' if len(missing_parts)>3 else ''}</div>", unsafe_allow_html=True)
                            
                            r2.markdown(f"<div style='text-align:center; padding-top:12px;'>{row['현장타입']}</div>", unsafe_allow_html=True)
                            r3.markdown(f"<div style='text-align:center; padding-top:8px;'><span class='badge {b_c}'>{b_t}</span></div>", unsafe_allow_html=True)
                            r4.markdown(f"<div style='text-align:center;' class='sub-text'><b>{row['inspection_date']}</b><br>({row.get('updated_by','-')})</div>", unsafe_allow_html=True)
                            
                            with r5:
                                ec, dc = st.columns(2)
                                if ec.button("✏️", key=f"e_{row['id']}"):
                                    st.session_state.edit_target_id, st.session_state.admin_view = int(row['id']), "edit"
                                    st.rerun()
                                if dc.button("🗑️", key=f"d_{row['id']}"):
                                    supabase.table("audit_results").delete().eq("id", row['id']).execute()
                                    st.rerun()
                            st.markdown("<div style='border-bottom:1px solid #eee;'></div>", unsafe_allow_html=True)

            # ---------------------------------------------------------
            # 신규 심사 등록 (방 만들기)
            # ---------------------------------------------------------
            elif st.session_state.admin_view == "create":
                st.subheader("📝 새로운 현장 심사 방 만들기")
                st.info("💡 현장 기본 정보를 먼저 등록합니다. 방이 만들어진 후 목록에서 접속하여 점수를 입력하세요.")
                with st.form("create_room_form"):
                    f1, f2, f3 = st.columns(3)
                    site_name = f1.text_input("현장명")
                    site_type = f2.selectbox("분류", ["건축", "인프라", "플랜트"])
                    inspection_date = f3.date_input("점검 실시일", value=date.today())
                    if st.form_submit_button("✅ 심사 방 생성하기", use_container_width=True):
                        if not site_name: st.error("현장명을 입력해주세요.")
                        else:
                            payload = {
                                "site_name": site_name, "site_type": site_type, "score": 0, 
                                "inspection_date": inspection_date.isoformat(),
                                "details": json.dumps({}), "created_by": st.session_state.current_user,
                                "updated_by": st.session_state.current_user, "updated_at": datetime.utcnow().isoformat()
                            }
                            supabase.table("audit_results").insert(payload).execute()
                            st.session_state.flash_msg = "✅ 심사 방이 생성되었습니다!"
                            st.session_state.admin_view = "list"
                            st.rerun()
                if st.button("⬅️ 취소하고 돌아가기"):
                    st.session_state.admin_view = "list"
                    st.rerun()

            # ---------------------------------------------------------
            # 심사 데이터 입력 (Live 폼)
            # ---------------------------------------------------------
            elif st.session_state.admin_view == "edit":
                t_df = load_template().fillna("")
                t_df['category'] = t_df['category'].astype(str).str.strip()
                total_items = len(t_df)

                target_id_str = f"edit_{st.session_state.edit_target_id}"
                if st.session_state.get('active_form_id') != target_id_str:
                    st.session_state.active_form_id = target_id_str
                    r = load_results()
                    target = r[r['id'] == st.session_state.edit_target_id].iloc[0]
                    st.session_state['f_site_name'] = target['현장명']
                    st.session_state['f_site_type'] = target['현장타입']
                    st.session_state['f_insp_date'] = datetime.strptime(target['inspection_date'], '%Y-%m-%d').date() if target.get('inspection_date') else date.today()
                    
                    cur_details = json.loads(target['details']) if target['details'] else {}
                    for _, itm in t_df.iterrows():
                        iid = str(itm['id'])
                        prev = cur_details.get(iid, None)
                        if prev is None:
                            st.session_state[f"chk_na_{iid}"] = False
                            st.session_state[f"sel_s_{iid}"] = None
                            st.session_state[f"txt_m_{iid}"] = ""
                        else:
                            st.session_state[f"chk_na_{iid}"] = prev.get('is_na', False)
                            st.session_state[f"sel_s_{iid}"] = prev.get('score', None)
                            st.session_state[f"txt_m_{iid}"] = prev.get('memo', "")

                c_back, c_empty = st.columns([1, 4])
                if c_back.button("⬅️ 목록으로 돌아가기"):
                    st.session_state.admin_view, st.session_state.active_form_id = "list", None
                    st.rerun()

                st.subheader(f"📝 '{st.session_state.f_site_name}' 심사 진행")
                
                answered = sum([1 for _, itm in t_df.iterrows() if st.session_state.get(f"chk_na_{str(itm['id'])}", False) or st.session_state.get(f"sel_s_{str(itm['id'])}") is not None])
                st.progress(answered/total_items if total_items > 0 else 0, text=f"📊 전체 작성 진행률: {answered} / {total_items} 완료")
                
                with st.expander("현장 기본 정보 (수정 필요 시 클릭)"):
                    f1, f2, f3 = st.columns(3)
                    new_s_name = f1.text_input("현장명", key="f_site_name")
                    new_s_type = f2.selectbox("분류", ["건축", "인프라", "플랜트"], key="f_site_type")
                    new_s_date = f3.date_input("점검 실시일", key="f_insp_date")

                st.divider()

                tabs = st.tabs(main_categories)
                for i, cat in enumerate(main_categories):
                    with tabs[i]:
                        items = t_df[t_df['category'] == cat.strip()]
                        if items.empty:
                            st.info("이 분류에 등록된 질문지가 없습니다.")
                        else:
                            if st.button(f"🚫 '{cat.split('.')[1].strip() if len(cat.split('.'))>1 else cat}' 파트 전체 '해당없음' 처리", key=f"btn_all_na_{i}"):
                                for _, itm in items.iterrows():
                                    iid = str(itm['id'])
                                    st.session_state[f"chk_na_{iid}"] = True
                                    st.session_state[f"sel_s_{iid}"] = None
                                st.rerun()
                            
                            st.write("---")
                            for _, itm in items.iterrows():
                                iid = str(itm['id'])
                                m = int(itm['max_score'])
                                st.markdown(f"**🔹 {itm['item_name']}** (배점: {m}점)")
                                
                                c_score, c_na, c_memo = st.columns([1.5, 1, 5])
                                with c_na: 
                                    na_val = st.checkbox("해당없음", key=f"chk_na_{iid}")
                                with c_score:
                                    opt = list(range(m + 1))
                                    curr_val = st.session_state.get(f"sel_s_{iid}")
                                    s_val = st.selectbox(
                                        "점수", options=opt, 
                                        index=opt.index(curr_val) if curr_val in opt else None, 
                                        placeholder="점수 선택 ⌄", disabled=na_val, label_visibility="collapsed", key=f"sel_s_{iid}"
                                    )
                                with c_memo:
                                    st.text_input("메모", label_visibility="collapsed", placeholder="감점 사유 및 메모 (선택)", key=f"txt_m_{iid}")
                                st.write("---")

                if st.button("💾 데이터 저장하기 (중간 저장 가능)", type="primary", use_container_width=True, key="floating_save"):
                    unanswered = [itm['item_name'] for _, itm in t_df.iterrows() if not st.session_state.get(f"chk_na_{str(itm['id'])}") and st.session_state.get(f"sel_s_{str(itm['id'])}") is None]
                    
                    res_input = {}
                    for _, itm in t_df.iterrows():
                        iid = str(itm['id'])
                        res_input[iid] = {"score": st.session_state[f"sel_s_{iid}"], "is_na": st.session_state[f"chk_na_{iid}"], "max": int(itm['max_score']), "memo": st.session_state[f"txt_m_{iid}"]}
                    
                    earn = sum([d['score'] for d in res_input.values() if not d['is_na'] and d['score'] is not None])
                    poss = sum([d['max'] for d in res_input.values() if not d['is_na'] and d['score'] is not None])
                    f_sc = round((earn/poss*100) if poss>0 else 0, 1)
                    
                    payload = {
                        "site_name": st.session_state.f_site_name, "site_type": st.session_state.f_site_type, "score": f_sc, 
                        "inspection_date": st.session_state.f_insp_date.isoformat(),
                        "details": json.dumps(res_input), "updated_by": st.session_state.current_user, 
                        "updated_at": datetime.utcnow().isoformat()
                    }
                    supabase.table("audit_results").update(payload).eq("id", st.session_state.edit_target_id).execute()
                    
                    st.session_state.admin_view, st.session_state.active_form_id = "list", None
                    if unanswered: st.session_state.flash_msg = f"⚠️ 임시 저장 완료! (미입력 항목 {len(unanswered)}개 남음)"
                    else: st.session_state.flash_msg = "✅ 모든 항목이 완벽하게 저장되었습니다!"
                    st.rerun()

        # ---------------------------------------------------------
        # 마스터 (템플릿) 설정 탭 
        # ---------------------------------------------------------
        with t_tab:
            st.subheader("📥 엑셀로 질문지(템플릿) 일괄 업로드")
            up = st.file_uploader("양식에 맞춘 엑셀 파일 선택", type=['xlsx'])
            if up and st.button("🚀 이 데이터로 점수표 덮어쓰기"):
                df_up = pd.read_excel(up).fillna("")
                recs = []
                for _, r in df_up.iterrows():
                    try: max_s = int(r['배점'])
                    except: max_s = 0
                    recs.append({"category": str(r['대분류']).strip(), "sub_category": str(r.get('분류', '')).strip(), "pdca": str(r.get('PDCA', '')).strip(), "item_name": str(r['점검사항']).strip(), "penalty": str(r.get('과태료', '')).strip(), "max_score": max_s})
                supabase.table("checklist_template").delete().gt("id", 0).execute()
                supabase.table("checklist_template").insert(recs).execute()
                st.success("✅ 업데이트 완료!")
                st.rerun()
            
            st.divider()
            st.subheader("⚙️ 웹에서 직접 수정")
            tmp_df = load_template()
            if not tmp_df.empty:
                tmp_df = tmp_df[['category', 'sub_category', 'pdca', 'item_name', 'penalty', 'max_score']]
                edt_df = st.data_editor(tmp_df, num_rows="dynamic", use_container_width=True, column_config={"category": st.column_config.SelectboxColumn("대분류", options=main_categories, required=True), "max_score": st.column_config.NumberColumn("배점", required=True)})
                if st.button("💾 변경사항 저장"):
                    recs = edt_df.fillna("").to_dict('records')
                    for rec in recs: rec['category'] = str(rec['category']).strip()
                    supabase.table("checklist_template").delete().gt("id", 0).execute()
                    supabase.table("checklist_template").insert(recs).execute()
                    st.success("✅ 저장 완료.")
                    st.rerun()
