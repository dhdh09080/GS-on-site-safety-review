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
    .sub-text { color: #6c757d; font-size: 0.85rem; }
    /* 진행률 바 색상 변경 */
    .stProgress > div > div > div > div { background-color: #28a745; }
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

# 세션 상태 관리
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

# ==========================================
# 사이드바 메뉴
# ==========================================
st.sidebar.title("🏗️ GS건설 보건관리")
menu = st.sidebar.radio("메뉴 이동", ["📊 통합 대시보드", "📅 심사 게시판"])

# ==========================================
# [페이지 1] 통합 대시보드 (신규 차트 추가)
# ==========================================
if menu == "📊 통합 대시보드":
    st.title("🏗️ GS건설 현장 내부심사 통합 대시보드")
    df = load_results()
    template_df = load_template()
    
    if not df.empty and not template_df.empty:
        # [Row 1] 랭킹
        r1_c1, r1_c2 = st.columns(2)
        with r1_c1:
            st.markdown("#### 🏆 상위 3위 현장")
            st.table(df.nlargest(3, '최종점수')[['현장명', '현장타입', '최종점수']].reset_index(drop=True))
        with r1_c2:
            st.markdown("#### ⚠️ 하위 3위 현장")
            st.table(df.nsmallest(3, '최종점수')[['현장명', '현장타입', '최종점수']].sort_values('최종점수').reset_index(drop=True))
        st.divider()

        # [Row 2] 분포표 & 트렌드
        st.markdown("### 📍 현장 점수 분포 현황")
        r2_c1, r2_c2 = st.columns([3, 2])
        with r2_c1:
            exc = df[df['최종점수'] >= 95][['현장명', '최종점수']].rename(columns={'현장명':'95점이상 현장', '최종점수':'점수 '})
            nor = df[(df['최종점수'] >= 80) & (df['최종점수'] < 95)][['현장명', '최종점수']].rename(columns={'현장명':'80~95점 현장', '최종점수':'점수  '})
            war = df[df['최종점수'] < 80][['현장명', '최종점수']].rename(columns={'현장명':'80점미만 현장', '최종점수':'점수   '})
            dist_table = pd.concat([exc.reset_index(drop=True), nor.reset_index(drop=True), war.reset_index(drop=True)], axis=1).fillna("-")
            st.dataframe(dist_table, use_container_width=True)
        with r2_c2:
            df_sorted = df.sort_values(by='inspection_date', ascending=True)
            fig_scatter = px.scatter(df_sorted, x="inspection_date", y="최종점수", color="최종점수", hover_name="현장명", text="현장명", color_continuous_scale=['#dc3545', '#ffc107', '#28a745'], range_y=[0, 105], title="현장별 점수 분포 (점검 일자순)")
            fig_scatter.update_traces(marker=dict(size=18, opacity=0.8), textposition='top center')
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
                        'category': t_info.iloc[0]['category'], 'item_name': t_info.iloc[0]['item_name'],
                        'earned': val['score'], 'max': val['max']
                    })
        a_df = pd.DataFrame(analysis_data)

        if not a_df.empty:
            # [Row 3] 대시보드 끝판왕: 전사 취약 항목 TOP 5 & 개별 현장 트렌드
            r3_c1, r3_c2 = st.columns(2)
            with r3_c1:
                st.markdown("### 🚨 전사 취약 항목 TOP 5 (집중 관리 필요)")
                def calc_rate(x): return pd.Series({'achieve_rate': round((x['earned'].sum() / x['max'].sum()) * 100, 1)})
                item_stats = a_df.groupby('item_name').apply(calc_rate).reset_index()
                bottom_5 = item_stats.nsmallest(5, 'achieve_rate')
                fig_bot5 = px.bar(bottom_5, x='achieve_rate', y='item_name', orientation='h', title="평균 획득률 (%)", color='achieve_rate', color_continuous_scale='Reds_r', range_x=[0, 100])
                st.plotly_chart(fig_bot5, use_container_width=True)
                
            with r3_c2:
                st.markdown("### 📈 개별 현장 점수 트렌드 추이")
                sel_site = st.selectbox("조회할 현장을 선택하세요", df['현장명'].unique(), label_visibility="collapsed")
                trend_df = df[df['현장명'] == sel_site].sort_values('inspection_date')
                fig_trend = px.line(trend_df, x='inspection_date', y='최종점수', markers=True, title=f"'{sel_site}' 점수 변화 추이", range_y=[0, 105])
                fig_trend.update_traces(marker=dict(size=10), line=dict(width=3, color='#007bff'))
                st.plotly_chart(fig_trend, use_container_width=True)
            st.divider()

            # [Row 4] 사업부별 PDCA 평균 점수
            st.markdown("### 📊 사업부별 / PDCA별 평균 점수")
            pdca_stats = a_df.groupby(['site_type', 'pdca']).apply(lambda x: round((x['earned'].sum() / x['max'].sum()) * 100, 1)).unstack().fillna(0)
            overall_site_avg = df.groupby('현장타입')['최종점수'].mean().round(1)
            pdca_stats.insert(0, '전체 평균', overall_site_avg)
            
            r4_c1, r4_c2 = st.columns([1, 1])
            with r4_c1: st.dataframe(pdca_stats, use_container_width=True)
            with r4_c2:
                fig_radar = px.line_polar(a_df.groupby(['site_type', 'pdca']).apply(lambda x: (x['earned'].sum()/x['max'].sum())*100).reset_index(name='점수'),
                                         r='점수', theta='pdca', color='site_type', line_close=True, title="사업부별 PDCA 밸런스")
                st.plotly_chart(fig_radar, use_container_width=True)
            st.divider()

            st.markdown("### 📋 대분류 항목별 사업부 점수 비교")
            cat_stats = a_df.groupby(['category', 'site_type']).apply(lambda x: round((x['earned'].sum() / x['max'].sum()) * 100, 1)).unstack().fillna(0)
            cat_stats = cat_stats.reindex([cat.strip() for cat in main_categories if cat.strip() in cat_stats.index])
            cat_stats.insert(0, '평균 점수', cat_stats.mean(axis=1).round(1))
            st.dataframe(cat_stats, use_container_width=True)
    else:
        st.info("데이터가 없습니다.")

# ==========================================
# [페이지 2] 심사 게시판 및 폼 (Live Progress 적용)
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
        m_tab, t_tab = st.tabs(["📝 리스트 관리", "⚙️ 점수표(마스터) 설정"])
        
        with m_tab:
            # ---------------------------------------------------------
            # 게시판 목록
            # ---------------------------------------------------------
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
            
            # ---------------------------------------------------------
            # 폼 화면 (진행률, 일괄만점, 모바일 친화, 메모 기능)
            # ---------------------------------------------------------
            elif st.session_state.admin_view in ["create", "edit"]:
                # State 초기화 (한 번만 실행되도록)
                target_id_str = f"{st.session_state.admin_view}_{st.session_state.edit_target_id}"
                if st.session_state.get('active_form_id') != target_id_str:
                    st.session_state.active_form_id = target_id_str
                    if st.session_state.admin_view == "edit":
                        r = load_results()
                        target = r[r['id'] == st.session_state.edit_target_id].iloc[0]
                        st.session_state.f_site_name = target['현장명']
                        st.session_state.f_site_type = target['현장타입']
                        st.session_state.f_insp_date = datetime.strptime(target['inspection_date'], '%Y-%m-%d').date() if target.get('inspection_date') else date.today()
                        cur_details = json.loads(target['details'])
                    else:
                        st.session_state.f_site_name = ""
                        st.session_state.f_site_type = "건축"
                        st.session_state.f_insp_date = date.today()
                        cur_details = {}
                        
                    t_df = load_template()
                    for _, itm in t_df.iterrows():
                        iid = str(itm['id'])
                        prev = cur_details.get(iid, None)
                        st.session_state[f"na_{iid}"] = prev['is_na'] if prev else False
                        st.session_state[f"s_{iid}"] = prev['score'] if prev else None
                        st.session_state[f"m_{iid}"] = prev.get('memo', "") if prev else ""

                t_df = load_template().fillna("")
                t_df['category'] = t_df['category'].astype(str).str.strip()
                
                # --- [실시간 진행률 계산] ---
                total_items = len(t_df)
                answered = 0
                for _, itm in t_df.iterrows():
                    iid = str(itm['id'])
                    if st.session_state.get(f"na_{iid}", False) or st.session_state.get(f"s_{iid}") is not None:
                        answered += 1
                prog_pct = int((answered / total_items) * 100) if total_items > 0 else 0
                
                # 상단 컨트롤 및 진행률 바
                c_back, c_empty = st.columns([1, 4])
                if c_back.button("⬅️ 목록으로 돌아가기"):
                    st.session_state.admin_view, st.session_state.active_form_id = "list", None
                    st.rerun()
                
                st.subheader(f"📝 {'심사 내역 수정' if st.session_state.admin_view == 'edit' else '신규 심사 등록'}")
                st.progress(prog_pct / 100.0, text=f"📊 작성 진행률: {answered} / {total_items} 완료 ({prog_pct}%)")
                st.divider()
                
                # 기본 정보 입력
                f1, f2, f3 = st.columns(3)
                site_name = f1.text_input("현장명", key="f_site_name")
                site_type = f2.selectbox("분류", ["건축", "인프라", "플랜트"], key="f_site_type")
                inspection_date = f3.date_input("점검 실시일", key="f_insp_date")
                st.divider()

                tabs = st.tabs(main_categories)
                
                # 탭별 문항 렌더링
                for i, cat in enumerate(main_categories):
                    with tabs[i]:
                        items = t_df[t_df['category'] == cat.strip()]
                        if items.empty:
                            st.info("이 분류에 등록된 질문지가 없습니다.")
                        else:
                            # [마법의 버튼] 이 탭 전체 만점
                            if st.button(f"💯 '{cat.split('.')[1].strip()}' 항목 전체 만점 주기", key=f"max_{i}", type="secondary"):
                                for _, itm in items.iterrows():
                                    st.session_state[f"s_{itm['id']}"] = int(itm['max_score'])
                                    st.session_state[f"na_{itm['id']}"] = False
                                st.rerun() # 실시간 반영
                                
                            st.write("---")
                            for _, itm in items.iterrows():
                                iid = str(itm['id'])
                                m = int(itm['max_score'])
                                
                                st.markdown(f"**🔹 {itm['item_name']}** (배점: {m}점)")
                                if itm['penalty']: st.markdown(f":red[*(과태료: {itm['penalty']})*]")
                                
                                c1, c2 = st.columns([5, 1])
                                with c2:
                                    st.checkbox("해당없음", key=f"na_{iid}")
                                with c1:
                                    # [모바일 친화형 입력] 배점이 10점 이상이면 숫자 증감 버튼(number_input) 사용
                                    if m >= 10:
                                        st.number_input("점수", min_value=0, max_value=m, step=1, key=f"s_{iid}", disabled=st.session_state[f"na_{iid}"], label_visibility="collapsed")
                                    else:
                                        st.radio("점수", list(range(m + 1)), horizontal=True, key=f"s_{iid}", disabled=st.session_state[f"na_{iid}"], label_visibility="collapsed")
                                
                                # [메모 기능] 
                                st.text_input("감점 사유", key=f"m_{iid}", label_visibility="collapsed", placeholder="감점 사유나 특이사항이 있다면 적어주세요 (선택사항)")
                                st.write("---")
                
                # 하단 최종 저장 버튼 및 검증 (Validation)
                if st.button("✅ 최종 데이터 저장하기", type="primary", use_container_width=True):
                    unanswered_items = []
                    res_input = {}
                    
                    for _, itm in t_df.iterrows():
                        iid = str(itm['id'])
                        s_val = st.session_state[f"s_{iid}"]
                        na_val = st.session_state[f"na_{iid}"]
                        m_val = st.session_state[f"m_{iid}"]
                        
                        if not na_val and s_val is None:
                            unanswered_items.append(itm['item_name'])
                        
                        res_input[iid] = {"score": s_val, "is_na": na_val, "max": int(itm['max_score']), "memo": m_val}
                    
                    if not site_name:
                        st.error("🚨 현장명을 입력해주세요.")
                    elif len(unanswered_items) > 0:
                        st.error(f"🚨 아직 점수를 매기지 않은 문항이 {len(unanswered_items)}개 있습니다! (예: {unanswered_items[0]})")
                    else:
                        earn = sum([d['score'] for d in res_input.values() if not d['is_na']])
                        poss = sum([d['max'] for d in res_input.values() if not d['is_na']])
                        f_sc = round((earn/poss*100) if poss>0 else 0, 1)
                        payload = {
                            "site_name": site_name, "site_type": site_type, "score": f_sc, 
                            "inspection_date": inspection_date.isoformat(),
                            "details": json.dumps(res_input), "updated_by": st.session_state.current_user, 
                            "updated_at": datetime.utcnow().isoformat()
                        }
                        if st.session_state.admin_view == "edit": supabase.table("audit_results").update(payload).eq("id", st.session_state.edit_target_id).execute()
                        else:
                            payload["created_by"] = st.session_state.current_user
                            supabase.table("audit_results").insert(payload).execute()
                        
                        st.session_state.admin_view, st.session_state.active_form_id = "list", None
                        st.success("저장 완료!")
                        st.rerun()

        # ---------------------------------------------------------
        # 마스터 (템플릿) 설정 탭 
        # ---------------------------------------------------------
        with t_tab:
            st.subheader("📥 엑셀로 질문지(템플릿) 일괄 업로드")
            up = st.file_uploader("양식에 맞춘 엑셀 파일 선택", type=['xlsx'])
            if up:
                try:
                    df_up = pd.read_excel(up).fillna("")
                    st.dataframe(df_up.head())
                    if st.button("🚀 이 데이터로 점수표 덮어쓰기"):
                        recs = []
                        for _, r in df_up.iterrows():
                            try: max_s = int(r['배점'])
                            except: max_s = 0
                            recs.append({
                                "category": str(r['대분류']).strip(), "sub_category": str(r.get('분류', '')).strip(),
                                "pdca": str(r.get('PDCA', '')).strip(), "item_name": str(r['점검사항']).strip(),
                                "penalty": str(r.get('과태료', '')).strip(), "max_score": max_s
                            })
                        if recs:
                            supabase.table("checklist_template").delete().gt("id", 0).execute()
                            supabase.table("checklist_template").insert(recs).execute()
                            st.success("✅ 질문지가 완벽하게 업데이트되었습니다!")
                            st.rerun()
                except Exception as e:
                    st.error(f"엑셀 처리 중 오류 발생: {e}")
            
            st.divider()
            st.subheader("⚙️ 웹에서 질문지 직접 수정")
            tmp_df = load_template()
            if not tmp_df.empty:
                tmp_df = tmp_df[['category', 'sub_category', 'pdca', 'item_name', 'penalty', 'max_score']]
                edt_df = st.data_editor(
                    tmp_df, num_rows="dynamic", use_container_width=True,
                    column_config={"category": st.column_config.SelectboxColumn("대분류", options=main_categories, required=True), "max_score": st.column_config.NumberColumn("배점", required=True)}
                )
                if st.button("💾 변경사항 저장"):
                    try:
                        recs = edt_df.fillna("").to_dict('records')
                        for rec in recs: rec['category'] = str(rec['category']).strip()
                        supabase.table("checklist_template").delete().gt("id", 0).execute()
                        supabase.table("checklist_template").insert(recs).execute()
                        st.success("✅ 웹 수정사항이 저장되었습니다.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"저장 중 오류 발생: {e}")
            else:
                st.info("현재 등록된 템플릿이 없습니다. 엑셀을 업로드해주세요.")
