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
# 3. 데이터 로드 및 버전 관리 함수
# ==========================================
def get_template_versions():
    try:
        res = supabase.table("checklist_template").select("version_name").execute()
        df = pd.DataFrame(res.data)
        if not df.empty and 'version_name' in df.columns:
            versions = df['version_name'].dropna().unique().tolist()
            return versions if versions else ["기본버전"]
        return ["기본버전"]
    except Exception:
        return ["기본버전"]

def load_template(version=None):
    try:
        query = supabase.table("checklist_template").select("*")
        if version and version != "기본버전":
            query = query.eq("version_name", version)
        res = query.order("id").execute()
        return pd.DataFrame(res.data)
    except Exception:
        try:
            res = supabase.table("checklist_template").select("*").order("id").execute()
            return pd.DataFrame(res.data)
        except:
            return pd.DataFrame()

def load_results():
    res = supabase.table("audit_results").select("*").order("inspection_date", desc=True).execute()
    df = pd.DataFrame(res.data)
    if not df.empty:
        df = df.rename(columns={"site_name": "현장명", "site_type": "현장타입", "score": "최종점수"})
        if 'inspection_date' not in df.columns: df['inspection_date'] = df['created_at'].str[:10]
        else: df['inspection_date'] = df['inspection_date'].fillna(df['created_at'].str[:10])
    return df

st.sidebar.title("🏗️ GS건설 내부심사")
menu = st.sidebar.radio("메뉴 이동", ["📊 통합 대시보드", "📅 로그인/점수 입력"])

# ==========================================
# [페이지 1] 통합 대시보드
# ==========================================
if menu == "📊 통합 대시보드":
    st.title("🏗️ GS건설 현장 내부심사 통합 대시보드")
    
    df = load_results()
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
    else:
        r1_c1, r1_c2 = st.columns(2)
        with r1_c1:
            st.markdown("#### 🏆 상위 3위 현장")
            st.table(dash_df.nlargest(3, '최종점수')[['현장명', '현장타입', '최종점수']].reset_index(drop=True))
        with r1_c2:
            st.markdown("#### ⚠️ 하위 3위 현장")
            st.table(dash_df.nsmallest(3, '최종점수')[['현장명', '현장타입', '최종점수']].sort_values('최종점수').reset_index(drop=True))
        st.divider()

        st.markdown("### 📍 현장 점수 분포 현황")
        r2_c1, r2_c2
