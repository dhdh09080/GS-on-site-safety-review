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
st.set_page_config(page_title="GS건설 현장 내부심사 통합 대시보드", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #f4f7f9; }
    /* 테이블 가독성 강화 */
    .styled-table { width: 100%; border-collapse: collapse; margin: 10px 0; font-size: 0.9em; min-width: 400px; }
    .styled-table thead tr { background-color: #007bff; color: #ffffff; text-align: left; }
    .styled-table th, .styled-table td { padding: 12px 15px; border: 1px solid #ddd; }
    /* 게시판 스타일 유지 */
    .board-header { background-color: #495057; color: white; padding: 12px 0; border-radius: 8px; font-weight: bold; text-align: center; display: flex; margin-bottom: 10px; }
    .board-row { background-color: white; border: 1px solid #eee; border-radius: 10px; padding: 15px 0; margin-bottom: 10px; display: flex; align-items: center; }
    .badge { padding: 5px 12px; border-radius: 20px; font-weight: bold; font-size: 0.8rem; }
    .excellent { background-color: #d4edda; color: #155724; }
    .normal { background-color: #fff3cd; color: #856404; }
    .warning { background-color: #f8d7da; color: #721c24; }
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
    res = supabase.table("audit_results").select("*").order("created_at", desc=True).execute()
    df = pd.DataFrame(res.data)
    if not df.empty:
        df = df.rename(columns={"site_name": "현장명", "site_type": "현장타입", "score": "최종점수"})
    return df

main_categories = ["1. 방침 수립", "2. 인력 및 예산", "3. 위험성평가", "4. 의견 청취", "5. 교육", "6. 비상대응", "7. 계획수립", "8. 회의점검", "9. 장비관리", "10. 보건관리"]

# ==========================================
# [페이지 1] 통합 대시보드 (신규 레이아웃)
# ==========================================
menu = st.sidebar.radio("메뉴 이동", ["📊 통합 대시보드", "📅 심사 게시판"])

if menu == "📊 통합 대시보드":
    st.title("🏗️ GS건설 현장 내부심사 통합 대시보드")
    df = load_results()
    template_df = load_template()
    
    if not df.empty and not template_df.empty:
        # 데이터 전처리 (항목별, PDCA별 점수 추출)
        analysis_data = []
        for _, row in df.iterrows():
            details = json.loads(row['details']) if isinstance(row['details'], str) else row['details']
            for item_id, val in details.items():
                t_info = template_df[template_df['id'] == int(item_id)]
                if not t_info.empty and not val.get('is_na', False):
                    analysis_data.append({
                        'site_type': row['현장타입'], 'site_name': row['현장명'],
                        'category': t_info.iloc[0]['category'], 'pdca': t_info.iloc[0]['pdca'],
                        'earned': val['score'], 'max': val['max'], 'score_pct': row['최종점수']
                    })
        a_df = pd.DataFrame(analysis_data)

        # --- [Row 1] 랭킹 정보 ---
        r1_c1, r1_c2 = st.columns(2)
        with r1_c1:
            st.markdown("#### 🏆 상위 3위 현장")
            st.table(df.nlargest(3, '최종점수')[['현장명', '현장타입', '최종점수']].reset_index(drop=True))
        with r1_c2:
            st.markdown("#### ⚠️ 하위 3위 현장")
            st.table(df.nsmallest(3, '최종점수')[['현장명', '현장타입', '최종점수']].sort_values('최종점수').reset_index(drop=True))

        st.divider()

        # --- [Row 2] 점수 분포표 & 산점도 (이미지 3번 스타일) ---
        st.markdown("### 📍 현장 점수 분포 리스트")
        r2_c1, r2_c2 = st.columns([3, 2])
        
        with r2_c1:
            # 엑셀 형태의 분포 리스트 가공
            exc = df[df['최종점수'] >= 95][['현장명', '최종점수']].rename(columns={'현장명':'95점이상 현장', '최종점수':'점수 '})
            nor = df[(df['최종점수'] >= 80) & (df['최종점수'] < 95)][['현장명', '최종점수']].rename(columns={'현장명':'80~95점 현장', '최종점수':'점수  '})
            war = df[df['최종점수'] < 80][['현장명', '최종점수']].rename(columns={'현장명':'80점미만 현장', '최종점수':'점수   '})
            
            # 길이 맞춰서 병합
            max_l = max(len(exc), len(nor), len(war))
            dist_table = pd.concat([exc.reset_index(drop=True), nor.reset_index(drop=True), war.reset_index(drop=True)], axis=1).fillna("-")
            st.dataframe(dist_table, use_container_width=True)
            
        with r2_c2:
            fig_scatter = px.scatter(df, x=df.index, y="최종점수", color="최종점수",
                                    color_continuous_scale=['red', 'yellow', 'green'],
                                    range_y=[0, 100], title="현장별 점수 분포도")
            st.plotly_chart(fig_scatter, use_container_width=True)

        st.divider()

        # --- [Row 3] 사업부별 PDCA 평균 (이미지 1번 스타일) ---
        st.markdown("### 📊 사업부별 / PDCA별 평균 점수")
        pdca_stats = a_df.groupby(['site_type', 'pdca']).apply(lambda x: round((x['earned'].sum() / x['max'].sum()) * 100, 1)).unstack().fillna(0)
        overall_avg = df.groupby('현장타입')['최종점수'].mean().round(1)
        pdca_stats.insert(0, '전체 평균', overall_avg)
        
        r3_c1, r3_c2 = st.columns([1, 1])
        with r3_c1:
            st.markdown("**[사업부별 PDCA 통계]**")
            st.dataframe(pdca_stats, use_container_width=True)
        
        with r3_c2:
            fig_pdca = px.line_polar(a_df.groupby(['site_type', 'pdca']).apply(lambda x: (x['earned'].sum()/x['max'].sum())*100).reset_index(name='점수'),
                                    r='점수', theta='pdca', color='site_type', line_close=True, title="PDCA 밸런스 비교")
            st.plotly_chart(fig_pdca, use_container_width=True)

        st.divider()

        # --- [Row 4] 항목별(대분류) 평균 점수 (이미지 2번 스타일) ---
        st.markdown("### 📋 대분류 항목별 사업부 점수 비교")
        cat_stats = a_df.groupby(['category', 'site_type']).apply(lambda x: round((x['earned'].sum() / x['max'].sum()) * 100, 1)).unstack().fillna(0)
        cat_stats.insert(0, '전체 평균 ', cat_stats.mean(axis=1).round(1))
        
        st.dataframe(cat_stats, use_container_width=True)
        
    else:
        st.info("분석할 심사 데이터가 충분하지 않습니다.")

# ==========================================
# [페이지 2] 심사 게시판 (관리자용)
# ==========================================
elif menu == "📅 심사 게시판":
    if not st.session_state.logged_in:
        st.title("🔐 관리자 인증")
        with st.form("login"):
            uid = st.text_input("ID")
            upw = st.text_input("PW", type="password")
            if st.form_submit_button("로그인"):
                if uid in st.secrets["passwords"] and st.secrets["passwords"][uid] == upw:
                    st.session_state.logged_in = True
                    st.session_state.current_user = uid
                    st.rerun()
    else:
        # 기존 게시판 코드 유지
        head_c, user_c = st.columns([5, 1])
        with head_c: st.subheader("📋 현장 내부심사 리스트 관리")
        with user_c:
            if st.button("로그아웃"): 
                st.session_state.logged_in = False
                st.rerun()
        
        m_tab, t_tab = st.tabs(["📝 리스트", "⚙️ 설정"])
        with m_tab:
            if st.session_state.admin_view == "list":
                col_s, col_a = st.columns([3, 1])
                sq = col_s.text_input("검색", placeholder="현장명...", label_visibility="collapsed")
                if col_a.button("➕ 신규 추가", type="primary", use_container_width=True):
                    st.session_state.admin_view = "create"
                    st.rerun()
                
                res_df = load_results()
                if not res_df.empty:
                    if sq: res_df = res_df[res_df['현장명'].str.contains(sq)]
                    for _, row in res_df.iterrows():
                        with st.container():
                            c1, c2, c3, c4, c5 = st.columns([3, 1, 1.5, 1.5, 1.2])
                            if c1.button(f"🏢 {row['현장명']}", key=f"t_{row['id']}", use_container_width=True):
                                st.session_state.edit_target_id, st.session_state.admin_view = int(row['id']), "edit"
                                st.rerun()
                            c2.write(f"**{row['현장타입']}**")
                            sc = row['최종점수']
                            b_c = "excellent" if sc >= 95 else "normal" if sc >= 80 else "warning"
                            c3.markdown(f"<span class='badge {b_c}'>{sc}점</span>", unsafe_allow_html=True)
                            c4.write(f"{row.get('updated_by','-')}\n{str(row['created_at'])[:10]}")
                            with c5:
                                if st.button("🗑️", key=f"d_{row['id']}"):
                                    supabase.table("audit_results").delete().eq("id", row['id']).execute()
                                    st.rerun()
                            st.divider()
            
            elif st.session_state.admin_view in ["create", "edit"]:
                if st.button("⬅️ 돌아가기"):
                    st.session_state.admin_view, st.session_state.edit_target_id = "list", None
                    st.rerun()
                
                # [입력 폼 생략 - 이전과 동일한 10개 탭 코드]
                st.info("상세 입력/수정 화면입니다.")
                # (이전의 input_results와 form 로직이 여기에 포함됩니다.)

        with t_tab:
            st.subheader("⚙️ 템플릿 마스터 관리")
            # [템플릿 업로드 코드 생략]
