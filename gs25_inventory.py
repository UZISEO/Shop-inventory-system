# -*- coding: utf-8 -*-
"""
GS25 편의점 재고관리 시스템 - 완전 수정 버전
모든 오류 수정 및 안정성 개선 완료
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import io
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
import warnings
import logging

warnings.filterwarnings('ignore')

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ================================
# 페이지 설정 (반드시 최상단)
# ================================

st.set_page_config(
    page_title="GS25 재고관리",
    page_icon="🏪",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ================================
# 전역 상수 정의
# ================================

CATEGORIES = {
    "00": "중분류 전체", "01": "도시락", "02": "김밥", "03": "주먹밥",
    "04": "햄버거/샌드위치", "05": "카운터FF", "06": "FF간편식", "07": "냉장간편식품",
    "08": "냉동간편식품", "09": "빵류", "10": "점내조리", "11": "특정판매",
    "12": "외주조리", "13": "육가공", "14": "어묵/맛살", "15": "두부/나물",
    "16": "근채", "17": "과채", "18": "엽채", "19": "양념",
    "20": "샐러드", "21": "버섯", "22": "김치", "23": "나물",
    "24": "양곡", "25": "채소가공", "26": "국산과일", "27": "수입과일",
    "28": "건과", "29": "과일가공", "30": "국산돈육", "31": "계육/계란",
    "32": "국산우육", "33": "수입육", "34": "축산가공", "35": "어류",
    "36": "해물", "37": "건어", "38": "수산가공", "39": "우유",
    "40": "발효유", "41": "냉장음료", "42": "치즈/버터", "43": "아이스크림",
    "44": "얼음", "45": "커피/차음료", "46": "기능성음료", "47": "탄산음료",
    "48": "생수/탄산수", "49": "주스", "50": "맥주", "51": "소주/전통주",
    "52": "양주/와인", "53": "스낵", "54": "쿠키/샌드", "55": "캔디/껌",
    "56": "초콜릿", "57": "안주", "58": "면류", "59": "즉석식품",
    "60": "커피/차", "61": "조미료", "62": "통조림", "63": "씨리얼/유아식",
    "64": "식용유/참기름", "65": "담배", "66": "서비스상품", "67": "개인위생",
    "68": "의약/의료", "69": "건강", "70": "헤어/바디용품", "71": "화장품",
    "72": "미용소품", "73": "색조화장품(미사용)", "74": "바디용품(미사용)", "75": "생리대/화장지",
    "76": "생활용품", "77": "문화/가전", "78": "가사용품", "79": "의류용품",
    "80": "반려동물", "81": "한식", "82": "아시안", "83": "양식",
    "88": "특정판매/수수료", "89": "연관/세트-비식품", "90": "온라인주류", "91": "수수료상품",
    "93": "Other Business", "99": "소모품"
}

WEEKDAYS = {
    'Monday': '월요일', 'Tuesday': '화요일', 'Wednesday': '수요일',
    'Thursday': '목요일', 'Friday': '금요일', 'Saturday': '토요일', 'Sunday': '일요일'
}

# ================================
# 유틸리티 함수
# ================================

def safe_rerun():
    """버전 호환 가능한 rerun 함수"""
    try:
        if hasattr(st, 'rerun'):
            st.rerun()
        else:
            st.experimental_rerun()
    except Exception as e:
        logger.error(f"Rerun error: {e}")
        st.error("페이지 새로고침이 필요합니다. F5를 눌러주세요.")

def safe_str_convert(value):
    """안전한 문자열 변환"""
    try:
        if pd.isna(value):
            return ""
        if isinstance(value, (int, float)):
            if isinstance(value, float) and value.is_integer():
                return str(int(value))
            return str(value)
        return str(value).strip()
    except Exception:
        return ""

def safe_num_convert(value, default=0):
    """안전한 숫자 변환"""
    try:
        if pd.isna(value) or value == "":
            return default
        if isinstance(value, str):
            value = value.strip()
            if value == "":
                return default
        return float(value)
    except (ValueError, TypeError):
        return default

def clean_excel_data(df):
    """엑셀 데이터 정리"""
    try:
        df = df.fillna("")
        df.columns = [str(col).strip() for col in df.columns]
        df = df.dropna(how='all').reset_index(drop=True)
        return df
    except Exception as e:
        logger.error(f"Excel cleaning error: {e}")
        return df

def process_inventory_excel(file, category_code):
    """재고 엑셀 파일 처리"""
    try:
        # UploadedFile을 BytesIO로 변환
        file_bytes = file.read()
        file_buffer = io.BytesIO(file_bytes)
        
        df = pd.read_excel(file_buffer, engine='openpyxl')
        df = clean_excel_data(df)
        
        if df.empty:
            return None, "파일에 데이터가 없습니다."
        
        # 필수 컬럼 확인
        required = ['상품코드', '상품명']
        missing = [col for col in required if col not in df.columns]
        if missing:
            return None, f"필수 컬럼이 없습니다: {missing}"
        
        # 데이터 변환 - DataFrame.get() 대신 조건부 접근
        result = pd.DataFrame({
            '상품코드': df['상품코드'].apply(safe_str_convert),
            '상품명': df['상품명'].apply(safe_str_convert),
            '중분류': category_code,
            '매가': (df['매가'] if '매가' in df.columns else pd.Series([0]*len(df))).apply(lambda x: safe_num_convert(x, 0)),
            '재고수량': (df['재고수량'] if '재고수량' in df.columns else 
                       df['이월수량'] if '이월수량' in df.columns else 
                       pd.Series([0]*len(df))).apply(lambda x: safe_num_convert(x, 0)),
            '추천재고수량': (df['추천재고수량'] if '추천재고수량' in df.columns else 
                           pd.Series([0]*len(df))).apply(lambda x: safe_num_convert(x, 0)),
            '등록일시': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
        
        # 추천재고 기본값 설정
        mask = result['추천재고수량'] == 0
        result.loc[mask, '추천재고수량'] = result.loc[mask, '재고수량'].apply(
            lambda x: max(int(x * 1.5), 5)
        )
        
        # 유효한 데이터만 필터링
        result = result[
            (result['상품코드'].str.len() > 0) & 
            (result['상품명'].str.len() > 0)
        ]
        
        if result.empty:
            return None, "유효한 데이터가 없습니다."
            
        return result, None
        
    except Exception as e:
        logger.error(f"File processing error: {e}")
        return None, f"파일 처리 오류: {str(e)}"

# ================================
# 세션 상태 관리
# ================================

def init_session():
    """세션 상태 초기화"""
    if 'inventory' not in st.session_state:
        st.session_state.inventory = pd.DataFrame(columns=[
            '상품코드', '상품명', '중분류', '매가', '재고수량', '추천재고수량', '등록일시'
        ])
    
    if 'transactions' not in st.session_state:
        st.session_state.transactions = pd.DataFrame(columns=[
            '일시', '거래유형', '상품코드', '상품명', '수량', '변경전', '변경후', '요일', '월'
        ])
    
    if 'current_menu' not in st.session_state:
        st.session_state.current_menu = '🏠 대시보드'
    
    # 초기화 확인 카운터
    if 'reset_inventory_count' not in st.session_state:
        st.session_state.reset_inventory_count = 0
    
    if 'reset_trans_count' not in st.session_state:
        st.session_state.reset_trans_count = 0

def add_transaction(trans_type, code, name, qty, before, after):
    """거래 내역 추가"""
    try:
        now = datetime.now()
        weekday = WEEKDAYS.get(now.strftime('%A'), now.strftime('%A'))
        
        new_trans = pd.DataFrame({
            '일시': [now.strftime('%Y-%m-%d %H:%M:%S')],
            '거래유형': [trans_type],
            '상품코드': [str(code)],
            '상품명': [str(name)],
            '수량': [abs(qty)],
            '변경전': [before],
            '변경후': [after],
            '요일': [weekday],
            '월': [now.month]
        })
        
        st.session_state.transactions = pd.concat([
            st.session_state.transactions, new_trans
        ], ignore_index=True)
    except Exception as e:
        logger.error(f"Transaction error: {e}")

def update_stock(code, change, trans_type):
    """재고 업데이트"""
    try:
        inventory = st.session_state.inventory
        
        if code in inventory['상품코드'].values:
            idx = inventory[inventory['상품코드'] == code].index[0]
            before = inventory.loc[idx, '재고수량']
            after = max(0, before + change)
            
            inventory.loc[idx, '재고수량'] = after
            inventory.loc[idx, '등록일시'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            name = inventory.loc[idx, '상품명']
            add_transaction(trans_type, code, name, change, before, after)
            return True
        return False
    except Exception as e:
        logger.error(f"Stock update error: {e}")
        return False

# ================================
# 분석 및 차트 함수
# ================================

def get_low_stock_items():
    """재고 부족 상품 조회"""
    try:
        inventory = st.session_state.inventory
        if inventory.empty:
            return pd.DataFrame()
        
        low_stock = inventory[inventory['재고수량'] < inventory['추천재고수량']].copy()
        if not low_stock.empty:
            low_stock['부족수량'] = low_stock['추천재고수량'] - low_stock['재고수량']
            low_stock['중분류명'] = low_stock['중분류'].map(CATEGORIES).fillna('기타')
            return low_stock.sort_values('부족수량', ascending=False)
        return pd.DataFrame()
    except Exception as e:
        logger.error(f"Low stock error: {e}")
        return pd.DataFrame()

def create_category_chart():
    """중분류별 재고 구성 차트"""
    try:
        inventory = st.session_state.inventory
        if inventory.empty:
            return None
        
        if '중분류' not in inventory.columns:
            return None
        
        stats = inventory.groupby('중분류').agg({
            '재고수량': ['count', 'sum']
        })
        
        # MultiIndex 처리
        stats.columns = ['_'.join(col).strip() for col in stats.columns.values]
        stats.columns = ['상품수', '총재고']
        stats = stats.reset_index()
        stats['중분류명'] = stats['중분류'].map(CATEGORIES).fillna('기타')
        
        fig = px.pie(stats, values='상품수', names='중분류명',
                    title='중분류별 상품 구성', hole=0.4)
        fig.update_layout(height=400)
        return fig
    except Exception as e:
        logger.error(f"Category chart error: {e}")
        return None

def create_weekday_chart():
    """요일별 판매/폐기 분석"""
    try:
        trans = st.session_state.transactions
        if trans.empty:
            return None
        
        sales_data = trans[trans['거래유형'].isin(['판매', '폐기'])]
        if sales_data.empty:
            return None
        
        weekday_stats = sales_data.groupby(['요일', '거래유형'])['수량'].sum().reset_index()
        
        weekday_order = ['월요일', '화요일', '수요일', '목요일', '금요일', '토요일', '일요일']
        weekday_stats['요일'] = pd.Categorical(weekday_stats['요일'], categories=weekday_order, ordered=True)
        weekday_stats = weekday_stats.sort_values('요일')
        
        fig = px.bar(weekday_stats, x='요일', y='수량', color='거래유형',
                    title='요일별 판매/폐기 현황',
                    color_discrete_map={'판매': '#2E86AB', '폐기': '#F24236'})
        fig.update_layout(height=400)
        return fig
    except Exception as e:
        logger.error(f"Weekday chart error: {e}")
        return None

def create_monthly_chart():
    """월별 트렌드 분석"""
    try:
        trans = st.session_state.transactions
        if trans.empty:
            return None
        
        sales_data = trans[trans['거래유형'].isin(['판매', '폐기'])]
        if sales_data.empty:
            return None
        
        monthly_stats = sales_data.groupby(['월', '거래유형'])['수량'].sum().reset_index()
        
        fig = px.line(monthly_stats, x='월', y='수량', color='거래유형',
                     title='월별 판매/폐기 트렌드', markers=True,
                     color_discrete_map={'판매': '#2E86AB', '폐기': '#F24236'})
        fig.update_layout(height=400)
        return fig
    except Exception as e:
        logger.error(f"Monthly chart error: {e}")
        return None

def create_category_performance_chart():
    """중분류별 판매 성과"""
    try:
        trans = st.session_state.transactions
        inventory = st.session_state.inventory
        
        if trans.empty or inventory.empty:
            return None
        
        category_map = dict(zip(inventory['상품코드'], inventory['중분류']))
        sales_data = trans[trans['거래유형'] == '판매'].copy()
        
        if sales_data.empty:
            return None
            
        sales_data['중분류'] = sales_data['상품코드'].map(category_map)
        sales_data = sales_data.dropna(subset=['중분류'])
        sales_data['중분류명'] = sales_data['중분류'].map(CATEGORIES).fillna('기타')
        
        category_sales = sales_data.groupby('중분류명')['수량'].sum().reset_index()
        category_sales = category_sales.sort_values('수량', ascending=True)
        
        fig = px.bar(category_sales, x='수량', y='중분류명', orientation='h',
                    title='중분류별 총 판매량', color='수량',
                    color_continuous_scale='Blues')
        fig.update_layout(height=600)
        return fig
    except Exception as e:
        logger.error(f"Performance chart error: {e}")
        return None

# ================================
# UI 컴포넌트
# ================================

def render_header():
    """헤더 렌더링"""
    st.markdown("""
    <div style='text-align: center; padding: 1.5rem 0; background: linear-gradient(90deg, #667eea 0%, #764ba2 100%); 
                border-radius: 10px; margin-bottom: 2rem; color: white;'>
        <h1 style='margin: 0; font-size: 2.5rem;'>🏪 GS25 재고관리 시스템</h1>
        <p style='margin: 0.5rem 0 0 0; font-size: 1.2rem; opacity: 0.9;'>
            중분류 기반 AI 재고 최적화 & 데이터 분석 플랫폼
        </p>
    </div>
    """, unsafe_allow_html=True)

def render_sidebar():
    """사이드바 렌더링"""
    with st.sidebar:
        st.markdown("### 📋 시스템 메뉴")
        
        menu_options = [
            "🏠 대시보드",
            "📦 재고관리",
            "📁 파일업로드",
            "✏️ 상품관리",
            "📊 데이터분석",
            "🎯 발주관리",
            "💾 시스템관리"
        ]
        
        selected = st.radio("메뉴 선택", menu_options,
                           index=menu_options.index(st.session_state.current_menu)
                           if st.session_state.current_menu in menu_options else 0)
        st.session_state.current_menu = selected
        
        st.markdown("---")
        
        # 시스템 현황
        st.markdown("### 📈 현황")
        inventory = st.session_state.inventory
        
        if not inventory.empty:
            total_items = len(inventory)
            total_stock = inventory['재고수량'].sum()
            low_stock_count = len(get_low_stock_items())
            
            st.metric("총 상품", f"{total_items:,}개")
            st.metric("총 재고", f"{total_stock:,.0f}개")
            
            if low_stock_count > 0:
                st.error(f"⚠️ 발주필요: {low_stock_count}개")
            else:
                st.success("✅ 재고충분")
        else:
            st.info("재고 데이터 없음")
        
        st.markdown("---")
        st.markdown("### ℹ️ 시스템")
        st.caption("🏷️ 중분류: 93개")
        st.caption("📊 실시간 분석")
        st.caption("🤖 AI 추천")
        st.caption("📅 " + datetime.now().strftime("%Y-%m-%d"))

def create_download_excel(df, filename):
    """엑셀 다운로드 생성"""
    try:
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Data', index=False)
            
            worksheet = writer.sheets['Data']
            header_font = Font(bold=True, color="FFFFFF")
            header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
            
            for cell in worksheet[1]:
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = Alignment(horizontal="center")
        
        buffer.seek(0)
        return buffer.getvalue()
    except Exception as e:
        logger.error(f"Excel creation error: {e}")
        return None

# ================================
# 메인 페이지들
# ================================

def show_dashboard():
    """대시보드"""
    st.header("📊 종합 대시보드")
    
    inventory = st.session_state.inventory
    
    if inventory.empty:
        st.warning("📁 재고 데이터가 없습니다.")
        st.info("👈 사이드바에서 '📁 파일업로드' 또는 '✏️ 상품관리'를 선택하여 시작하세요.")
        return
    
    # 주요 지표
    col1, col2, col3, col4 = st.columns(4)
    
    total_items = len(inventory)
    total_stock = inventory['재고수량'].sum()
    total_value = (inventory['재고수량'] * inventory['매가']).sum()
    low_stock_items = len(get_low_stock_items())
    
    with col1:
        st.metric("총 상품 수", f"{total_items:,}개")
    with col2:
        st.metric("총 재고량", f"{total_stock:,.0f}개")
    with col3:
        st.metric("재고 가치", f"{total_value:,.0f}원")
    with col4:
        st.metric("발주 필요", f"{low_stock_items:,}개",
                 delta=f"-{low_stock_items}" if low_stock_items > 0 else "✅")
    
    # 차트 영역
    col1, col2 = st.columns(2)
    
    with col1:
        category_chart = create_category_chart()
        if category_chart:
            st.plotly_chart(category_chart, use_container_width=True)
        else:
            st.info("중분류별 차트 데이터 없음")
    
    with col2:
        st.subheader("⚠️ 발주 필요 상품 (TOP 5)")
        low_stock = get_low_stock_items()
        if not low_stock.empty:
            display_cols = ['상품명', '중분류명', '재고수량', '추천재고수량', '부족수량']
            if all(col in low_stock.columns for col in display_cols):
                st.dataframe(low_stock[display_cols].head(5), use_container_width=True)
            else:
                st.dataframe(low_stock.head(5), use_container_width=True)
        else:
            st.success("✅ 모든 상품 재고 충분!")
    
    # 중분류별 현황
    st.subheader("📈 중분류별 재고 현황")
    
    try:
        category_stats = inventory.groupby('중분류').agg({
            '재고수량': ['count', 'sum', 'mean'],
            '추천재고수량': 'sum'
        })
        
        # MultiIndex 처리
        category_stats.columns = ['_'.join(col).strip() for col in category_stats.columns.values]
        category_stats.columns = ['상품수', '총재고', '평균재고', '추천총재고']
        category_stats = category_stats.reset_index()
        category_stats['중분류명'] = category_stats['중분류'].map(CATEGORIES).fillna('기타')
        category_stats = category_stats[['중분류명', '상품수', '총재고', '평균재고', '추천총재고']]
        category_stats['평균재고'] = category_stats['평균재고'].round(1)
        
        st.dataframe(category_stats, use_container_width=True)
    except Exception as e:
        logger.error(f"Category stats error: {e}")
        st.error("중분류별 현황 표시 중 오류가 발생했습니다.")

def show_inventory_management():
    """재고 관리"""
    st.header("📦 재고 관리")
    
    inventory = st.session_state.inventory
    if inventory.empty:
        st.warning("조회할 재고가 없습니다.")
        return
    
    # 검색 및 필터
    col1, col2, col3 = st.columns(3)
    
    with col1:
        categories = ['전체'] + sorted([k for k in inventory['중분류'].unique() if k in CATEGORIES])
        selected_cat = st.selectbox("🏷️ 중분류", categories)
    
    with col2:
        search_code = st.text_input("🔍 상품코드")
    
    with col3:
        search_name = st.text_input("🔍 상품명")
    
    # 필터링
    filtered = inventory.copy()
    
    if selected_cat != '전체':
        filtered = filtered[filtered['중분류'] == selected_cat]
    
    if search_code:
        filtered = filtered[filtered['상품코드'].str.contains(search_code, case=False, na=False)]
    
    if search_name:
        filtered = filtered[filtered['상품명'].str.contains(search_name, case=False, na=False)]
    
    filtered['중분류명'] = filtered['중분류'].map(CATEGORIES).fillna('기타')
    
    st.markdown(f"### 📋 검색 결과: **{len(filtered):,}**건")
    
    if not filtered.empty:
        if selected_cat != '전체':
            st.markdown(f"#### 📊 {CATEGORIES.get(selected_cat, selected_cat)} 요약")
            
            summary_col1, summary_col2, summary_col3, summary_col4 = st.columns(4)
            
            cat_items = len(filtered)
            cat_stock = filtered['재고수량'].sum()
            cat_recommend = filtered['추천재고수량'].sum()
            cat_low = len(filtered[filtered['재고수량'] < filtered['추천재고수량']])
            
            with summary_col1:
                st.metric("상품 수", f"{cat_items:,}개")
            with summary_col2:
                st.metric("총 재고", f"{cat_stock:,.0f}개")
            with summary_col3:
                st.metric("추천 재고", f"{cat_recommend:,.0f}개")
            with summary_col4:
                st.metric("부족 상품", f"{cat_low:,}개")
        
        display_cols = ['상품코드', '상품명', '중분류명', '매가', '재고수량', '추천재고수량', '등록일시']
        st.dataframe(filtered[display_cols], use_container_width=True, height=400)
        
        excel_data = create_download_excel(filtered, "재고현황.xlsx")
        if excel_data:
            st.download_button(
                "📥 엑셀 다운로드",
                data=excel_data,
                file_name=f"재고현황_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
    else:
        st.info("검색 조건에 맞는 상품이 없습니다.")

def show_file_upload():
    """파일 업로드"""
    st.header("📁 파일 업로드")
    
    st.info("💡 엑셀 파일 업로드 시 중분류를 지정하여 상품을 자동 분류합니다.")
    
    st.subheader("🏷️ 중분류 선택")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        category_options = [k for k in CATEGORIES.keys() if k != "00"]
        
        if not category_options:
            st.error("카테고리 정보가 없습니다.")
            return
            
        selected_category = st.selectbox(
            "중분류를 선택하세요",
            options=category_options,
            format_func=lambda x: f"{x} - {CATEGORIES.get(x, '미분류')}"
        )
    
    with col2:
        st.markdown(f"**선택된 중분류:** `{selected_category} - {CATEGORIES.get(selected_category, '미분류')}`")
    
    st.subheader("📦 재고 파일 업로드")
    
    with st.expander("📋 파일 형식 안내", expanded=True):
        st.markdown("""
        **필수 컬럼:**
        - `상품코드`: 상품 고유 코드
        - `상품명`: 상품명
        
        **선택 컬럼:**
        - `매가`: 판매가격 (기본값: 0)
        - `재고수량` 또는 `이월수량`: 현재 재고 (기본값: 0)
        - `추천재고수량`: 권장 재고 (기본값: 현재 재고×1.5)
        
        **지원 형식:** .xlsx
        """)
    
    uploaded_file = st.file_uploader("엑셀 파일 선택", type=['xlsx'])
    
    if uploaded_file is not None:
        col1, col2 = st.columns(2)
        
        with col1:
            replace_mode = st.checkbox("기존 데이터 교체", value=False,
                                     help="체크 시 기존 데이터를 완전히 교체합니다")
        
        if st.button("📦 업로드 실행", type="primary"):
            with st.spinner("파일 처리 중..."):
                processed_data, error = process_inventory_excel(uploaded_file, selected_category)
                
                if error:
                    st.error(f"❌ {error}")
                elif processed_data is not None:
                    try:
                        if replace_mode:
                            st.session_state.inventory = processed_data
                            st.success(f"✅ {len(processed_data):,}건이 '{CATEGORIES[selected_category]}' 중분류로 등록되었습니다!")
                        else:
                            existing = st.session_state.inventory
                            
                            if existing.empty:
                                st.session_state.inventory = processed_data
                                st.success(f"✅ {len(processed_data):,}건 신규 등록!")
                            else:
                                existing_codes = set(existing['상품코드'].tolist())
                                new_data = processed_data[~processed_data['상품코드'].isin(existing_codes)]
                                
                                if not new_data.empty:
                                    st.session_state.inventory = pd.concat(
                                        [existing, new_data],
                                        ignore_index=True
                                    )
                                
                                st.success(f"✅ 신규 {len(new_data):,}건 추가!")
                        
                        st.balloons()
                        safe_rerun()
                        
                    except Exception as e:
                        st.error(f"데이터 저장 오류: {str(e)}")
                else:
                    st.warning("처리할 데이터가 없습니다.")

def show_product_management():
    """상품 관리"""
    st.header("✏️ 상품 관리")
    
    tab1, tab2, tab3 = st.tabs(["➕ 신규등록", "🔄 재고조정", "🎯 추천재고설정"])
    
    with tab1:
        st.subheader("➕ 신규 상품 등록")
        
        with st.form("new_product", clear_on_submit=True):
            col1, col2 = st.columns(2)
            
            with col1:
                new_code = st.text_input("상품코드 *", placeholder="8801234567890")
                new_name = st.text_input("상품명 *", placeholder="삼각김밥 참치마요")
                new_category = st.selectbox(
                    "중분류 *",
                    options=[k for k in CATEGORIES.keys() if k != "00"],
                    format_func=lambda x: f"{x} - {CATEGORIES[x]}"
                )
            
            with col2:
                new_price = st.number_input("매가 *", min_value=0, value=0, step=100)
                new_stock = st.number_input("현재재고 *", min_value=0, value=0, step=1)
                new_recommend = st.number_input("추천재고 *", min_value=0, value=0, step=1)
            
            if st.form_submit_button("🆕 등록", type="primary"):
                if not new_code or not new_name:
                    st.error("상품코드와 상품명은 필수입니다.")
                elif new_code in st.session_state.inventory['상품코드'].values:
                    st.error("이미 존재하는 상품코드입니다.")
                else:
                    new_product = pd.DataFrame({
                        '상품코드': [new_code],
                        '상품명': [new_name.strip()],
                        '중분류': [new_category],
                        '매가': [new_price],
                        '재고수량': [new_stock],
                        '추천재고수량': [new_recommend if new_recommend > 0 else max(int(new_stock * 1.5), 5)],
                        '등록일시': [datetime.now().strftime('%Y-%m-%d %H:%M:%S')]
                    })
                    
                    st.session_state.inventory = pd.concat([
                        st.session_state.inventory, new_product
                    ], ignore_index=True)
                    
                    add_transaction("신규등록", new_code, new_name, new_stock, 0, new_stock)
                    
                    st.success(f"✅ '{new_name}'이 {CATEGORIES[new_category]} 중분류로 등록되었습니다!")
                    safe_rerun()
    
    with tab2:
        st.subheader("🔄 재고 조정")
        
        if st.session_state.inventory.empty:
            st.warning("조정할 상품이 없습니다.")
            return
        
        search = st.text_input("🔍 상품 검색", placeholder="상품코드 또는 상품명")
        
        if search:
            filtered = st.session_state.inventory[
                (st.session_state.inventory['상품코드'].str.contains(search, case=False, na=False)) |
                (st.session_state.inventory['상품명'].str.contains(search, case=False, na=False))
            ]
            
            if not filtered.empty and len(filtered) > 0:
                options = []
                for _, row in filtered.iterrows():
                    option = f"{row['상품코드']} - {row['상품명']} (재고: {row['재고수량']:.0f})"
                    options.append(option)
                
                selected = st.selectbox("조정할 상품", ["선택하세요"] + options)
                
                if selected != "선택하세요":
                    code = selected.split(" - ")[0]
                    product_df = st.session_state.inventory[
                        st.session_state.inventory['상품코드'] == code
                    ]
                    
                    if not product_df.empty:
                        product = product_df.iloc[0]
                        current_stock = float(product['재고수량'])
                        
                        col1, col2, col3 = st.columns(3)
                        
                        with col1:
                            adj_type = st.selectbox("조정 유형", ["입고", "판매", "폐기", "직접조정"])
                        
                        with col2:
                            if adj_type == "직접조정":
                                new_stock = st.number_input("새 재고량", min_value=0, value=int(current_stock))
                                change = new_stock - current_stock
                            else:
                                qty = st.number_input("수량", min_value=1, value=1)
                                change = qty if adj_type == "입고" else -qty
                        
                        with col3:
                            expected = max(0, current_stock + change) if adj_type != "직접조정" else new_stock
                            st.metric("조정 후", f"{expected:.0f}개", delta=f"{change:+.0f}")
                        
                        if st.button("🔄 조정 실행", type="primary"):
                            if adj_type == "직접조정":
                                idx = st.session_state.inventory[
                                    st.session_state.inventory['상품코드'] == code
                                ].index[0]
                                st.session_state.inventory.loc[idx, '재고수량'] = new_stock
                                st.session_state.inventory.loc[idx, '등록일시'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                                add_transaction("직접조정", code, product['상품명'], change, current_stock, new_stock)
                            else:
                                update_stock(code, change, adj_type)
                            
                            st.success(f"✅ 재고 조정 완료! ({current_stock:.0f} → {expected:.0f})")
                            safe_rerun()
            else:
                st.info("검색 결과가 없습니다.")
    
    with tab3:
        st.subheader("🎯 추천재고수량 설정")
        
        if st.session_state.inventory.empty:
            st.warning("설정할 상품이 없습니다.")
            return
        
        st.markdown("#### 📊 중분류별 일괄 설정")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            batch_cat = st.selectbox(
                "중분류",
                options=[k for k in CATEGORIES.keys() if k != "00" and k in st.session_state.inventory['중분류'].unique()],
                format_func=lambda x: f"{x} - {CATEGORIES[x]}"
            )
        
        with col2:
            multiplier = st.number_input("배수", min_value=1.0, max_value=5.0, value=1.5, step=0.1)
        
        with col3:
            if st.button("🔄 일괄 적용"):
                cat_items = st.session_state.inventory[
                    st.session_state.inventory['중분류'] == batch_cat
                ]
                if not cat_items.empty:
                    for idx in cat_items.index:
                        current = st.session_state.inventory.loc[idx, '재고수량']
                        new_recommend = max(int(current * multiplier), 5)
                        st.session_state.inventory.loc[idx, '추천재고수량'] = new_recommend
                    
                    st.success(f"✅ {CATEGORIES[batch_cat]} 중분류 {len(cat_items)}개 상품 업데이트!")
                    safe_rerun()
                else:
                    st.warning("해당 중분류에 상품이 없습니다.")

def show_data_analysis():
    """데이터 분석"""
    st.header("📊 데이터 분석")
    
    transactions = st.session_state.transactions
    
    if transactions.empty:
        st.warning("분석할 거래 데이터가 없습니다.")
        return
    
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("시작일", datetime.now().date() - timedelta(days=30))
    with col2:
        end_date = st.date_input("종료일", datetime.now().date())
    
    filtered_trans = transactions.copy()
    filtered_trans['날짜'] = pd.to_datetime(filtered_trans['일시']).dt.date
    filtered_trans = filtered_trans[
        (filtered_trans['날짜'] >= start_date) & (filtered_trans['날짜'] <= end_date)
    ]
    
    if filtered_trans.empty:
        st.info("선택한 기간에 데이터가 없습니다.")
        return
    
    st.subheader("📈 기간 요약")
    
    col1, col2, col3, col4 = st.columns(4)
    
    total_trans = len(filtered_trans)
    total_sales = filtered_trans[filtered_trans['거래유형'] == '판매']['수량'].sum()
    total_disposal = filtered_trans[filtered_trans['거래유형'] == '폐기']['수량'].sum()
    disposal_rate = (total_disposal / (total_sales + total_disposal) * 100) if (total_sales + total_disposal) > 0 else 0
    
    with col1:
        st.metric("총 거래", f"{total_trans:,}건")
    with col2:
        st.metric("총 판매", f"{total_sales:,.0f}개")
    with col3:
        st.metric("총 폐기", f"{total_disposal:,.0f}개")
    with col4:
        st.metric("폐기율", f"{disposal_rate:.1f}%")
    
    col1, col2 = st.columns(2)
    
    with col1:
        weekday_chart = create_weekday_chart()
        if weekday_chart:
            st.plotly_chart(weekday_chart, use_container_width=True)
    
    with col2:
        monthly_chart = create_monthly_chart()
        if monthly_chart:
            st.plotly_chart(monthly_chart, use_container_width=True)
    
    category_chart = create_category_performance_chart()
    if category_chart:
        st.plotly_chart(category_chart, use_container_width=True)
    
    st.subheader("📋 상세 거래 내역")
    
    trans_types = st.multiselect(
        "거래 유형 필터",
        options=filtered_trans['거래유형'].unique(),
        default=filtered_trans['거래유형'].unique()
    )
    
    display_trans = filtered_trans[filtered_trans['거래유형'].isin(trans_types)]
    
    if not display_trans.empty:
        inventory = st.session_state.inventory
        if not inventory.empty:
            category_map = dict(zip(inventory['상품코드'], inventory['중분류']))
            display_trans['중분류'] = display_trans['상품코드'].map(category_map)
            display_trans['중분류명'] = display_trans['중분류'].map(CATEGORIES).fillna('기타')
            
            display_cols = ['일시', '거래유형', '상품명', '중분류명', '수량', '요일']
        else:
            display_cols = ['일시', '거래유형', '상품명', '수량', '요일']
        
        st.dataframe(
            display_trans[display_cols].sort_values('일시', ascending=False),
            use_container_width=True,
            height=400
        )

def show_order_management():
    """발주 관리"""
    st.header("🎯 발주 관리")
    
    low_stock = get_low_stock_items()
    
    if low_stock.empty:
        st.success("🎉 모든 상품의 재고가 충분합니다!")
        
        inventory = st.session_state.inventory
        if not inventory.empty:
            total_items = len(inventory)
            sufficient_items = len(inventory[inventory['재고수량'] >= inventory['추천재고수량']])
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("전체 상품", f"{total_items:,}개")
            with col2:
                st.metric("재고 충분", f"{sufficient_items:,}개")
            with col3:
                rate = (sufficient_items / total_items * 100) if total_items > 0 else 0
                st.metric("충족률", f"{rate:.1f}%")
        return
    
    st.subheader(f"⚠️ 발주 필요 상품: {len(low_stock):,}개")
    
    col1, col2, col3, col4 = st.columns(4)
    
    total_shortage = low_stock['부족수량'].sum()
    avg_shortage = low_stock['부족수량'].mean()
    critical_items = len(low_stock[low_stock['재고수량'] == 0])
    max_shortage = low_stock['부족수량'].max()
    
    with col1:
        st.metric("총 부족량", f"{total_shortage:,.0f}개")
    with col2:
        st.metric("평균 부족", f"{avg_shortage:.1f}개")
    with col3:
        st.metric("재고0 상품", f"{critical_items:,}개")
    with col4:
        st.metric("최대 부족", f"{max_shortage:,.0f}개")
    
    st.subheader("🏷️ 중분류별 발주 현황")
    
    category_shortage = low_stock.groupby('중분류명').agg({
        '부족수량': ['count', 'sum']
    })
    category_shortage.columns = ['_'.join(col).strip() for col in category_shortage.columns.values]
    category_shortage.columns = ['부족상품수', '총부족량']
    category_shortage = category_shortage.reset_index()
    
    fig = px.bar(category_shortage, x='중분류명', y='총부족량',
                title='중분류별 부족 수량', color='총부족량',
                color_continuous_scale='Reds')
    fig.update_layout(height=400, xaxis_tickangle=-45)
    st.plotly_chart(fig, use_container_width=True)
    
    st.subheader("📋 발주 우선순위")
    
    priority_filter = st.selectbox(
        "우선순위 필터",
        ["전체", "긴급 (재고0)", "높음 (부족20+)", "보통 (부족10-19)", "낮음 (부족10미만)"]
    )
    
    if priority_filter == "긴급 (재고0)":
        filtered_items = low_stock[low_stock['재고수량'] == 0]
    elif priority_filter == "높음 (부족20+)":
        filtered_items = low_stock[low_stock['부족수량'] >= 20]
    elif priority_filter == "보통 (부족10-19)":
        filtered_items = low_stock[(low_stock['부족수량'] >= 10) & (low_stock['부족수량'] < 20)]
    elif priority_filter == "낮음 (부족10미만)":
        filtered_items = low_stock[low_stock['부족수량'] < 10]
    else:
        filtered_items = low_stock
    
    if not filtered_items.empty:
        def get_priority(row):
            if row['재고수량'] == 0:
                return "🔴 긴급"
            elif row['부족수량'] >= 20:
                return "🟠 높음"
            elif row['부족수량'] >= 10:
                return "🟡 보통"
            else:
                return "🟢 낮음"
        
        filtered_items['우선순위'] = filtered_items.apply(get_priority, axis=1)
        
        display_cols = ['우선순위', '상품코드', '상품명', '중분류명', '재고수량', '추천재고수량', '부족수량']
        st.dataframe(filtered_items[display_cols], use_container_width=True, height=400)
        
        st.subheader("📋 발주서 생성")
        
        col1, col2 = st.columns(2)
        
        with col1:
            order_data = filtered_items[['상품코드', '상품명', '중분류명', '재고수량', '추천재고수량', '부족수량']].copy()
            order_data.columns = ['상품코드', '상품명', '중분류', '현재재고', '추천재고', '발주수량']
            order_data['발주일자'] = datetime.now().strftime('%Y-%m-%d')
            order_data['비고'] = ''
            
            excel_data = create_download_excel(order_data, "발주서.xlsx")
            if excel_data:
                st.download_button(
                    "📥 발주서 엑셀 다운로드",
                    data=excel_data,
                    file_name=f"발주서_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="primary"
                )
        
        with col2:
            if st.button("🚚 일괄 발주 요청", type="primary"):
                st.info(f"📋 {len(filtered_items)}개 상품 발주 요청 완료! (실제 발주 시스템 연동 필요)")
    else:
        st.info("선택한 우선순위에 해당하는 상품이 없습니다.")

def show_system_management():
    """시스템 관리"""
    st.header("💾 시스템 관리")
    
    tab1, tab2, tab3 = st.tabs(["📥 백업", "🔄 초기화", "📤 템플릿"])
    
    with tab1:
        st.subheader("📥 데이터 백업")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### 📦 재고 데이터")
            if not st.session_state.inventory.empty:
                count = len(st.session_state.inventory)
                st.write(f"백업 대상: **{count:,}**개 상품")
                
                backup_data = st.session_state.inventory.copy()
                backup_data['중분류명'] = backup_data['중분류'].map(CATEGORIES).fillna('기타')
                
                excel_data = create_download_excel(backup_data, "재고백업.xlsx")
                if excel_data:
                    st.download_button(
                        "📦 재고 백업",
                        data=excel_data,
                        file_name=f"재고백업_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        type="primary"
                    )
            else:
                st.warning("백업할 재고 데이터가 없습니다.")
        
        with col2:
            st.markdown("#### 📊 거래 내역")
            if not st.session_state.transactions.empty:
                count = len(st.session_state.transactions)
                st.write(f"백업 대상: **{count:,}**건 거래")
                
                excel_data = create_download_excel(st.session_state.transactions, "거래백업.xlsx")
                if excel_data:
                    st.download_button(
                        "📊 거래 백업",
                        data=excel_data,
                        file_name=f"거래백업_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        type="primary"
                    )
            else:
                st.warning("백업할 거래 데이터가 없습니다.")
    
    with tab2:
        st.subheader("🔄 데이터 초기화")
        st.error("⚠️ 주의: 삭제된 데이터는 복구할 수 없습니다!")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("📦 재고 데이터 초기화"):
                st.session_state.reset_inventory_count += 1
                
                if st.session_state.reset_inventory_count >= 2:
                    st.session_state.inventory = pd.DataFrame(columns=[
                        '상품코드', '상품명', '중분류', '매가', '재고수량', '추천재고수량', '등록일시'
                    ])
                    st.session_state.reset_inventory_count = 0
                    st.success("✅ 재고 데이터가 초기화되었습니다.")
                    safe_rerun()
                else:
                    st.warning("⚠️ 한 번 더 클릭하면 삭제됩니다.")
        
        with col2:
            if st.button("📊 거래 내역 초기화"):
                st.session_state.reset_trans_count += 1
                
                if st.session_state.reset_trans_count >= 2:
                    st.session_state.transactions = pd.DataFrame(columns=[
                        '일시', '거래유형', '상품코드', '상품명', '수량', '변경전', '변경후', '요일', '월'
                    ])
                    st.session_state.reset_trans_count = 0
                    st.success("✅ 거래 내역이 초기화되었습니다.")
                    safe_rerun()
                else:
                    st.warning("⚠️ 한 번 더 클릭하면 삭제됩니다.")
    
    with tab3:
        st.subheader("📤 업로드 템플릿")
        
        template_data = pd.DataFrame({
            '상품코드': ['8801234567890', '8801234567891'],
            '상품명': ['삼각김밥 참치마요', '삼각김밥 불고기'],
            '매가': [1200, 1300],
            '재고수량': [10, 15],
            '추천재고수량': [20, 25]
        })
        
        st.dataframe(template_data, use_container_width=True)
        
        excel_template = create_download_excel(template_data, "재고템플릿.xlsx")
        if excel_template:
            st.download_button(
                "📦 재고 업로드 템플릿 다운로드",
                data=excel_template,
                file_name="재고_업로드_템플릿.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary"
            )
        
        st.markdown("---")
        st.markdown("#### 📂 중분류 목록")
        
        cat_df = pd.DataFrame([
            {'코드': k, '중분류명': v} for k, v in CATEGORIES.items()
        ])
        
        col1, col2 = st.columns(2)
        mid = len(cat_df) // 2
        
        with col1:
            st.dataframe(cat_df[:mid], hide_index=True, use_container_width=True)
        with col2:
            st.dataframe(cat_df[mid:], hide_index=True, use_container_width=True)

# ================================
# 메인 애플리케이션
# ================================

def main():
    """메인 애플리케이션"""
    try:
        init_session()
        
        render_header()
        render_sidebar()
        
        menu = st.session_state.current_menu
        
        if menu == "🏠 대시보드":
            show_dashboard()
        elif menu == "📦 재고관리":
            show_inventory_management()
        elif menu == "📁 파일업로드":
            show_file_upload()
        elif menu == "✏️ 상품관리":
            show_product_management()
        elif menu == "📊 데이터분석":
            show_data_analysis()
        elif menu == "🎯 발주관리":
            show_order_management()
        elif menu == "💾 시스템관리":
            show_system_management()
        
        st.markdown("---")
        st.markdown("""
        <div style='text-align: center; color: #888; font-size: 0.9em; padding: 1rem;'>
            🏪 <strong>GS25 편의점 재고관리 시스템</strong> | 
            중분류 기반 AI 재고 최적화 | 
            버전 5.0.0 (Final)
        </div>
        """, unsafe_allow_html=True)
        
    except Exception as e:
        logger.error(f"Application error: {e}")
        st.error(f"시스템 오류: {e}")
        if st.button("🔄 새로고침"):
            safe_rerun()

if __name__ == "__main__":
    main()
