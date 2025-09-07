import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, date
import io
import openpyxl
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import warnings
import traceback
warnings.filterwarnings('ignore')

# 페이지 설정
st.set_page_config(
    page_title="GS25 재고관리 시스템",
    page_icon="🏪",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 대분류 카테고리 정의
CATEGORIES = {
    "01": "FreshFood",
    "02": "간편식품", 
    "03": "조리식품",
    "04": "냉장식품",
    "05": "채소",
    "06": "과일",
    "07": "축산",
    "08": "수산",
    "09": "유제품",
    "10": "빙과류",
    "11": "음료",
    "12": "주류",
    "13": "과자",
    "14": "일반식품",
    "15": "서비스",
    "16": "헬스",
    "17": "뷰티",
    "18": "일상용품",
    "19": "심플리쿡",
    "20": "미식일상",
    "21": "Other Business",
    "99": "소모품"
}

def safe_convert_to_string(value):
    """안전하게 값을 문자열로 변환"""
    try:
        if pd.isna(value) or value is None:
            return ""
        if isinstance(value, (int, float)):
            if pd.isna(value) or np.isnan(value):
                return ""
            if isinstance(value, float) and value.is_integer():
                return str(int(value))
            return str(value)
        return str(value).strip()
    except Exception:
        return str(value) if value is not None else ""

def safe_convert_to_numeric(value, default=0):
    """안전하게 숫자로 변환"""
    try:
        if pd.isna(value) or value is None or value == "":
            return default
        if isinstance(value, str):
            value = value.strip()
            if value == "":
                return default
        return float(value)
    except (ValueError, TypeError):
        return default

def initialize_session_state():
    """세션 상태 초기화"""
    if 'inventory_data' not in st.session_state:
        st.session_state.inventory_data = pd.DataFrame(columns=[
            '상품코드', '상품명', '대분류', '매가', '재고수량', '추천재고수량', '최종수정일'
        ])
    
    if 'transaction_history' not in st.session_state:
        st.session_state.transaction_history = pd.DataFrame(columns=[
            '일시', '거래유형', '상품코드', '상품명', '수량', '변경전재고', '변경후재고', '요일', '월'
        ])
    
    if 'current_page' not in st.session_state:
        st.session_state.current_page = "🏠 대시보드"

def add_transaction_record(transaction_type, product_code, product_name, quantity, before_qty, after_qty):
    """거래 내역 추가 (요일/월 정보 포함)"""
    try:
        now = datetime.now()
        weekday = now.strftime('%A')  # 요일 (영어)
        weekday_kr = {'Monday': '월요일', 'Tuesday': '화요일', 'Wednesday': '수요일', 
                     'Thursday': '목요일', 'Friday': '금요일', 'Saturday': '토요일', 'Sunday': '일요일'}
        
        new_record = pd.DataFrame({
            '일시': [now.strftime('%Y-%m-%d %H:%M:%S')],
            '거래유형': [transaction_type],
            '상품코드': [str(product_code)],
            '상품명': [str(product_name)],
            '수량': [float(quantity)],
            '변경전재고': [float(before_qty)],
            '변경후재고': [float(after_qty)],
            '요일': [weekday_kr.get(weekday, weekday)],
            '월': [now.month]
        })
        st.session_state.transaction_history = pd.concat(
            [st.session_state.transaction_history, new_record], 
            ignore_index=True
        )
    except Exception as e:
        st.error(f"거래 내역 추가 중 오류: {e}")

def process_excel_file(uploaded_file, selected_category="99"):
    """엑셀 파일 처리 (대분류 지정 포함)"""
    try:
        df = pd.read_excel(uploaded_file, engine='openpyxl')
        df = df.fillna("")
        df.columns = [str(col).strip() for col in df.columns]
        
        if df.empty:
            st.error("파일에 데이터가 없습니다.")
            return None
        
        # 필수 컬럼 확인
        required_columns = ['상품코드', '상품명']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            st.error(f"필수 컬럼이 없습니다: {missing_columns}")
            return None
        
        # 데이터 변환
        df['상품코드'] = df['상품코드'].apply(safe_convert_to_string)
        df['상품명'] = df['상품명'].apply(safe_convert_to_string)
        df['대분류'] = selected_category  # 사용자가 선택한 대분류 적용
        
        # 매가 처리
        if '매가' in df.columns:
            df['매가'] = df['매가'].apply(lambda x: safe_convert_to_numeric(x, 0))
        else:
            df['매가'] = 0
        
        # 재고수량 처리
        if '재고수량' in df.columns:
            df['재고수량'] = df['재고수량'].apply(lambda x: safe_convert_to_numeric(x, 0))
        elif '이월수량' in df.columns:
            df['재고수량'] = df['이월수량'].apply(lambda x: safe_convert_to_numeric(x, 0))
        else:
            df['재고수량'] = 0
        
        # 추천재고수량 처리 (기본값: 현재 재고의 1.5배)
        if '추천재고수량' in df.columns:
            df['추천재고수량'] = df['추천재고수량'].apply(lambda x: safe_convert_to_numeric(x, 0))
        else:
            df['추천재고수량'] = (df['재고수량'] * 1.5).round().astype(int)
        
        df['최종수정일'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # 빈 상품코드나 상품명 제거
        df = df[(df['상품코드'] != "") & (df['상품명'] != "")]
        
        return df[['상품코드', '상품명', '대분류', '매가', '재고수량', '추천재고수량', '최종수정일']]
        
    except Exception as e:
        st.error(f"파일 처리 중 오류: {e}")
        return None

def update_inventory(product_code, quantity_change, transaction_type):
    """재고 업데이트"""
    try:
        product_code = str(product_code)
        
        if product_code in st.session_state.inventory_data['상품코드'].values:
            idx = st.session_state.inventory_data[
                st.session_state.inventory_data['상품코드'] == product_code
            ].index[0]
            
            before_qty = float(st.session_state.inventory_data.loc[idx, '재고수량'])
            after_qty = max(0, before_qty + quantity_change)
            
            st.session_state.inventory_data.loc[idx, '재고수량'] = after_qty
            st.session_state.inventory_data.loc[idx, '최종수정일'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            product_name = str(st.session_state.inventory_data.loc[idx, '상품명'])
            add_transaction_record(transaction_type, product_code, product_name, abs(quantity_change), before_qty, after_qty)
            
            return True
        return False
    except Exception as e:
        st.error(f"재고 업데이트 중 오류: {e}")
        return False

def get_low_stock_recommendations():
    """추천 재고 대비 부족한 상품 목록"""
    if st.session_state.inventory_data.empty:
        return pd.DataFrame()
    
    low_stock = st.session_state.inventory_data[
        st.session_state.inventory_data['재고수량'] < st.session_state.inventory_data['추천재고수량']
    ].copy()
    
    if not low_stock.empty:
        low_stock['부족수량'] = low_stock['추천재고수량'] - low_stock['재고수량']
        low_stock['대분류명'] = low_stock['대분류'].map(CATEGORIES)
        return low_stock.sort_values('부족수량', ascending=False)
    
    return pd.DataFrame()

def create_sales_analysis_chart():
    """판매/폐기 데이터 분석 차트"""
    if st.session_state.transaction_history.empty:
        return None, None
    
    # 판매/폐기 데이터만 필터링
    sales_disposal = st.session_state.transaction_history[
        st.session_state.transaction_history['거래유형'].isin(['판매', '폐기'])
    ].copy()
    
    if sales_disposal.empty:
        return None, None
    
    # 요일별 분석
    weekday_analysis = sales_disposal.groupby(['요일', '거래유형'])['수량'].sum().reset_index()
    weekday_order = ['월요일', '화요일', '수요일', '목요일', '금요일', '토요일', '일요일']
    weekday_analysis['요일'] = pd.Categorical(weekday_analysis['요일'], categories=weekday_order, ordered=True)
    weekday_analysis = weekday_analysis.sort_values('요일')
    
    # 월별 분석
    monthly_analysis = sales_disposal.groupby(['월', '거래유형'])['수량'].sum().reset_index()
    
    # 요일별 차트
    fig_weekday = px.bar(
        weekday_analysis, 
        x='요일', 
        y='수량', 
        color='거래유형',
        title='요일별 판매/폐기 현황',
        color_discrete_map={'판매': '#2E86AB', '폐기': '#F24236'}
    )
    fig_weekday.update_layout(height=400)
    
    # 월별 차트
    fig_monthly = px.line(
        monthly_analysis, 
        x='월', 
        y='수량', 
        color='거래유형',
        title='월별 판매/폐기 트렌드',
        markers=True,
        color_discrete_map={'판매': '#2E86AB', '폐기': '#F24236'}
    )
    fig_monthly.update_layout(height=400)
    
    return fig_weekday, fig_monthly

def create_category_analysis_chart():
    """대분류별 재고 현황 차트"""
    if st.session_state.inventory_data.empty:
        return None
    
    category_stats = st.session_state.inventory_data.groupby('대분류').agg({
        '재고수량': ['count', 'sum'],
        '추천재고수량': 'sum'
    }).round(2)
    
    category_stats.columns = ['상품수', '현재재고', '추천재고']
    category_stats['대분류명'] = category_stats.index.map(CATEGORIES)
    category_stats = category_stats.reset_index()
    
    # 도넛 차트로 대분류별 상품 수 표시
    fig = px.pie(
        category_stats, 
        values='상품수', 
        names='대분류명',
        title='대분류별 상품 구성비',
        hole=0.4
    )
    fig.update_layout(height=500)
    
    return fig

def main():
    initialize_session_state()
    
    # 메인 헤더
    st.markdown("""
    <div style='text-align: center; padding: 1rem 0;'>
        <h1 style='color: #366092; margin-bottom: 0;'>🏪 GS25 편의점 재고관리 시스템</h1>
        <p style='color: #666; margin-top: 0;'>AI 기반 재고 최적화 및 데이터 분석</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # 사이드바
    with st.sidebar:
        st.markdown("### 📋 시스템 메뉴")
        
        menu_options = [
            "🏠 대시보드", 
            "📦 재고관리", 
            "📁 파일업로드", 
            "✏️ 직접입력", 
            "📊 데이터분석", 
            "🎯 재고추천",
            "💾 데이터관리"
        ]
        
        current_index = 0
        if st.session_state.current_page in menu_options:
            current_index = menu_options.index(st.session_state.current_page)
        
        selected_menu = st.radio("기능 선택", menu_options, index=current_index)
        st.session_state.current_page = selected_menu
        
        st.markdown("---")
        
        # 현재 상태 표시
        st.markdown("### 📈 현재 상태")
        if not st.session_state.inventory_data.empty:
            total_items = len(st.session_state.inventory_data)
            total_stock = st.session_state.inventory_data['재고수량'].sum()
            low_stock_count = len(get_low_stock_recommendations())
            
            st.metric("총 상품 수", f"{total_items:,}개")
            st.metric("총 재고량", f"{total_stock:,.0f}개")
            
            if low_stock_count > 0:
                st.error(f"⚠️ 발주 필요: {low_stock_count}개")
            else:
                st.success("✅ 재고 충분")
        else:
            st.info("📝 재고 데이터를 등록해주세요")
    
    # 메인 컨텐츠
    if selected_menu == "🏠 대시보드":
        show_dashboard()
    elif selected_menu == "📦 재고관리":
        show_inventory_management()
    elif selected_menu == "📁 파일업로드":
        show_file_upload()
    elif selected_menu == "✏️ 직접입력":
        show_manual_input()
    elif selected_menu == "📊 데이터분석":
        show_data_analysis()
    elif selected_menu == "🎯 재고추천":
        show_stock_recommendations()
    elif selected_menu == "💾 데이터관리":
        show_data_management()

def show_dashboard():
    """대시보드 화면"""
    st.header("📊 종합 대시보드")
    
    if st.session_state.inventory_data.empty:
        st.warning("📝 재고 데이터가 없습니다. 파일을 업로드하거나 직접 입력해주세요.")
        
        st.info("👈 시작하려면 사이드바에서 다음 중 선택하세요:")
        st.markdown("- **📁 파일업로드**: 엑셀 파일로 재고 데이터 업로드")
        st.markdown("- **✏️ 직접입력**: 수동으로 상품 정보 입력")
        
        return
    
    # 주요 지표
    col1, col2, col3, col4 = st.columns(4)
    
    total_items = len(st.session_state.inventory_data)
    total_stock = st.session_state.inventory_data['재고수량'].sum()
    total_recommended = st.session_state.inventory_data['추천재고수량'].sum()
    low_stock_items = len(get_low_stock_recommendations())
    
    with col1:
        st.metric("총 상품 수", f"{total_items:,}개")
    with col2:
        st.metric("현재 재고", f"{total_stock:,.0f}개")
    with col3:
        st.metric("추천 재고", f"{total_recommended:,.0f}개")
    with col4:
        st.metric("발주 필요", f"{low_stock_items:,}개", delta=f"-{low_stock_items}" if low_stock_items > 0 else "✅")
    
    # 차트 영역
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📈 대분류별 재고 구성")
        category_chart = create_category_analysis_chart()
        if category_chart:
            st.plotly_chart(category_chart, use_container_width=True)
        else:
            st.info("차트를 생성할 데이터가 부족합니다.")
    
    with col2:
        st.subheader("⚠️ 발주 필요 상품 (TOP 5)")
        low_stock = get_low_stock_recommendations()
        if not low_stock.empty:
            display_low_stock = low_stock[['상품명', '대분류명', '재고수량', '추천재고수량', '부족수량']].head(5)
            st.dataframe(display_low_stock, use_container_width=True)
        else:
            st.success("✅ 모든 상품의 재고가 충분합니다!")
    
    # 최근 거래 현황
    st.subheader("🔄 최근 거래 현황")
    if not st.session_state.transaction_history.empty:
        recent_transactions = st.session_state.transaction_history.tail(10)
        st.dataframe(recent_transactions[['일시', '거래유형', '상품명', '수량', '요일']], use_container_width=True)
    else:
        st.info("거래 내역이 없습니다.")

def show_inventory_management():
    """재고 관리 화면"""
    st.header("📦 재고 관리")
    
    if st.session_state.inventory_data.empty:
        st.warning("조회할 재고 데이터가 없습니다.")
        return
    
    # 필터링 옵션
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # 대분류 필터
        categories = ['전체'] + sorted(list(st.session_state.inventory_data['대분류'].unique()))
        selected_category = st.selectbox("🏷️ 대분류 필터", categories)
    
    with col2:
        search_code = st.text_input("🔍 상품코드 검색")
    
    with col3:
        search_name = st.text_input("🔍 상품명 검색")
    
    # 데이터 필터링
    filtered_data = st.session_state.inventory_data.copy()
    
    if selected_category != '전체':
        filtered_data = filtered_data[filtered_data['대분류'] == selected_category]
    
    if search_code:
        filtered_data = filtered_data[filtered_data['상품코드'].str.contains(search_code, na=False, case=False)]
    
    if search_name:
        filtered_data = filtered_data[filtered_data['상품명'].str.contains(search_name, na=False, case=False)]
    
    # 대분류명 추가
    filtered_data['대분류명'] = filtered_data['대분류'].map(CATEGORIES)
    
    # 결과 표시
    st.markdown(f"### 📋 검색 결과: **{len(filtered_data):,}**건")
    
    if not filtered_data.empty:
        # 대분류별 요약 (선택된 카테고리가 있을 때)
        if selected_category != '전체':
            st.markdown(f"#### 📊 {CATEGORIES.get(selected_category, selected_category)} 요약")
            
            summary_col1, summary_col2, summary_col3, summary_col4 = st.columns(4)
            
            category_items = len(filtered_data)
            category_stock = filtered_data['재고수량'].sum()
            category_recommended = filtered_data['추천재고수량'].sum()
            category_low_stock = len(filtered_data[filtered_data['재고수량'] < filtered_data['추천재고수량']])
            
            with summary_col1:
                st.metric("상품 수", f"{category_items:,}개")
            with summary_col2:
                st.metric("총 재고", f"{category_stock:,.0f}개")
            with summary_col3:
                st.metric("추천 재고", f"{category_recommended:,.0f}개")
            with summary_col4:
                st.metric("부족 상품", f"{category_low_stock:,}개")
        
        # 데이터 테이블
        display_columns = ['상품코드', '상품명', '대분류명', '매가', '재고수량', '추천재고수량', '최종수정일']
        st.dataframe(filtered_data[display_columns], use_container_width=True, height=400)
        
    else:
        st.info("🔍 검색 조건에 맞는 상품이 없습니다.")

def show_file_upload():
    """파일 업로드 화면 (대분류 지정 포함)"""
    st.header("📁 파일 업로드")
    
    st.info("💡 엑셀 파일 업로드 시 대분류를 지정하여 상품을 분류할 수 있습니다.")
    
    # 대분류 선택
    st.subheader("🏷️ 업로드할 상품의 대분류 선택")
    selected_category = st.selectbox(
        "대분류를 선택하세요",
        options=list(CATEGORIES.keys()),
        format_func=lambda x: f"{x} - {CATEGORIES[x]}",
        key="upload_category"
    )
    
    st.markdown(f"**선택된 대분류:** `{selected_category} - {CATEGORIES[selected_category]}`")
    
    # 파일 업로드
    st.subheader("📦 재고 데이터 업로드")
    
    with st.expander("📋 파일 형식 안내", expanded=True):
        st.markdown("""
        **필수 컬럼:**
        - `상품코드`: 상품의 고유 코드
        - `상품명`: 상품명
        
        **선택 컬럼:**
        - `매가`: 상품 가격 (기본값: 0)
        - `재고수량` 또는 `이월수량`: 현재 재고량 (기본값: 0)
        - `추천재고수량`: 권장 재고량 (기본값: 현재 재고의 1.5배)
        
        **지원 형식:** .xlsx (Excel 2007 이상)
        
        **참고:** 업로드되는 모든 상품은 위에서 선택한 대분류로 자동 분류됩니다.
        """)
    
    uploaded_file = st.file_uploader(
        "재고 파일 선택",
        type=['xlsx'],
        key="category_inventory_file",
        help="Excel 파일(.xlsx)을 선택해주세요"
    )
    
    if uploaded_file:
        col1, col2 = st.columns([1, 1])
        with col1:
            replace_data = st.checkbox("기존 데이터 교체", value=False, 
                                     help="체크하지 않으면 기존 데이터에 추가됩니다")
        
        if st.button("📦 재고 데이터 업로드", type="primary", key="upload_with_category"):
            with st.spinner("파일을 처리하고 있습니다..."):
                processed_df = process_excel_file(uploaded_file, selected_category)
                
                if processed_df is not None and not processed_df.empty:
                    if replace_data:
                        st.session_state.inventory_data = processed_df
                        st.success(f"✅ 재고 데이터 {len(processed_df):,}건이 '{CATEGORIES[selected_category]}' 대분류로 등록되었습니다!")
                    else:
                        # 기존 데이터와 병합 (중복 상품코드 처리)
                        existing_codes = st.session_state.inventory_data['상품코드'].tolist()
                        new_data = processed_df[~processed_df['상품코드'].isin(existing_codes)]
                        updated_data = processed_df[processed_df['상품코드'].isin(existing_codes)]
                        
                        if not new_data.empty:
                            st.session_state.inventory_data = pd.concat([st.session_state.inventory_data, new_data], ignore_index=True)
                        
                        if not updated_data.empty:
                            for _, row in updated_data.iterrows():
                                idx = st.session_state.inventory_data[st.session_state.inventory_data['상품코드'] == row['상품코드']].index[0]
                                st.session_state.inventory_data.loc[idx] = row
                        
                        st.success(f"✅ 신규 {len(new_data):,}건, 업데이트 {len(updated_data):,}건이 '{CATEGORIES[selected_category]}' 대분류로 처리되었습니다!")
                    
                    st.balloons()
                    st.rerun()

def show_manual_input():
    """직접 입력 화면"""
    st.header("✏️ 직접 입력 및 수정")
    
    tab1, tab2, tab3 = st.tabs(["➕ 신규 상품 등록", "📝 재고 조정", "🏷️ 추천재고 설정"])
    
    with tab1:
        st.subheader("➕ 신규 상품 등록")
        
        with st.form("new_product_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            
            with col1:
                new_code = st.text_input("상품코드 *", placeholder="예: 8801234567890")
                new_name = st.text_input("상품명 *", placeholder="예: 삼각김밥 참치마요")
                new_category = st.selectbox(
                    "대분류 *", 
                    options=list(CATEGORIES.keys()),
                    format_func=lambda x: f"{x} - {CATEGORIES[x]}"
                )
            
            with col2:
                new_price = st.number_input("매가 *", min_value=0, value=0, step=100)
                new_stock = st.number_input("현재재고 *", min_value=0, value=0, step=1)
                new_recommended = st.number_input("추천재고 *", min_value=0, value=0, step=1)
                
            submitted = st.form_submit_button("🆕 상품 등록", type="primary", use_container_width=True)
            
            if submitted:
                if not new_code or not new_name:
                    st.error("❌ 상품코드와 상품명을 입력해주세요!")
                elif new_code in st.session_state.inventory_data['상품코드'].values:
                    st.error("❌ 이미 존재하는 상품코드입니다!")
                else:
                    new_product = pd.DataFrame({
                        '상품코드': [new_code],
                        '상품명': [new_name.strip()],
                        '대분류': [new_category],
                        '매가': [new_price],
                        '재고수량': [new_stock],
                        '추천재고수량': [new_recommended if new_recommended > 0 else max(new_stock * 1.5, 10)],
                        '최종수정일': [datetime.now().strftime('%Y-%m-%d %H:%M:%S')]
                    })
                    
                    st.session_state.inventory_data = pd.concat([st.session_state.inventory_data, new_product], ignore_index=True)
                    add_transaction_record("신규등록", new_code, new_name, new_stock, 0, new_stock)
                    
                    st.success(f"✅ '{new_name}'이(가) {CATEGORIES[new_category]} 대분류로 등록되었습니다!")
                    st.balloons()
                    st.rerun()
    
    with tab2:
        st.subheader("📝 재고 조정")
        
        if st.session_state.inventory_data.empty:
            st.warning("⚠️ 조정할 재고 데이터가 없습니다.")
            return
        
        # 상품 검색
        search_term = st.text_input("🔍 상품 검색 (코드 또는 상품명)")
        
        if search_term:
            filtered_products = st.session_state.inventory_data[
                (st.session_state.inventory_data['상품코드'].str.contains(search_term, na=False, case=False)) |
                (st.session_state.inventory_data['상품명'].str.contains(search_term, na=False, case=False))
            ]
            
            if not filtered_products.empty:
                product_options = []
                for _, row in filtered_products.iterrows():
                    option = f"{row['상품코드']} - {row['상품명']} (재고: {row['재고수량']:.0f}, 추천: {row['추천재고수량']:.0f})"
                    product_options.append(option)
                
                selected_product = st.selectbox("조정할 상품 선택", ["선택해주세요"] + product_options)
                
                if selected_product != "선택해주세요":
                    selected_code = selected_product.split(" - ")[0]
                    product_info = st.session_state.inventory_data[
                        st.session_state.inventory_data['상품코드'] == selected_code
                    ].iloc[0]
                    
                    current_stock = float(product_info['재고수량'])
                    recommended_stock = float(product_info['추천재고수량'])
                    
                    # 조정 UI
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        adjustment_type = st.selectbox("조정 유형", ["입고", "판매", "폐기", "직접조정"])
                    
                    with col2:
                        if adjustment_type == "직접조정":
                            new_stock = st.number_input("새로운 재고량", min_value=0, value=int(current_stock))
                            adjustment_qty = new_stock - current_stock
                        else:
                            adjustment_qty = st.number_input("조정 수량", min_value=1, value=1, step=1)
                            if adjustment_type in ["판매", "폐기"]:
                                adjustment_qty = -adjustment_qty
                    
                    with col3:
                        expected_stock = max(0, current_stock + adjustment_qty) if adjustment_type != "직접조정" else new_stock
                        
                        # 상태 표시
                        if expected_stock < recommended_stock:
                            delta_color = "red"
                            status = f"부족 ({recommended_stock - expected_stock:.0f})"
                        else:
                            delta_color = "green"
                            status = "충분"
                        
                        st.metric("조정 후 재고", f"{expected_stock:,.0f}개", delta=f"{adjustment_qty:+.0f}")
                        st.markdown(f"**재고 상태:** :{delta_color}[{status}]")
                    
                    if st.button("📝 재고 조정 실행", type="primary"):
                        try:
                            if adjustment_type == "직접조정":
                                idx = st.session_state.inventory_data[st.session_state.inventory_data['상품코드'] == selected_code].index[0]
                                st.session_state.inventory_data.loc[idx, '재고수량'] = new_stock
                                st.session_state.inventory_data.loc[idx, '최종수정일'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                                add_transaction_record("직접조정", selected_code, product_info['상품명'], adjustment_qty, current_stock, new_stock)
                            else:
                                update_inventory(selected_code, adjustment_qty, adjustment_type)
                            
                            st.success(f"✅ 재고 조정 완료! ({current_stock:.0f} → {expected_stock:.0f})")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ 조정 중 오류: {e}")
            else:
                st.info("🔍 검색 결과가 없습니다.")
    
    with tab3:
        st.subheader("🏷️ 추천재고수량 설정")
        
        if st.session_state.inventory_data.empty:
            st.warning("⚠️ 설정할 상품이 없습니다.")
            return
        
        # 대분류별 일괄 설정
        st.markdown("#### 📊 대분류별 일괄 설정")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            batch_category = st.selectbox(
                "대분류 선택",
                options=list(CATEGORIES.keys()),
                format_func=lambda x: f"{x} - {CATEGORIES[x]}"
            )
        
        with col2:
            multiplier = st.number_input("배수 설정", min_value=1.0, max_value=5.0, value=1.5, step=0.1,
                                       help="현재 재고 × 배수 = 추천 재고")
        
        with col3:
            if st.button("🔄 일괄 적용", type="secondary"):
                category_items = st.session_state.inventory_data[st.session_state.inventory_data['대분류'] == batch_category]
                if not category_items.empty:
                    for idx in category_items.index:
                        current_stock = st.session_state.inventory_data.loc[idx, '재고수량']
                        new_recommended = max(int(current_stock * multiplier), 5)  # 최소 5개
                        st.session_state.inventory_data.loc[idx, '추천재고수량'] = new_recommended
                    
                    st.success(f"✅ {CATEGORIES[batch_category]} 대분류 {len(category_items)}개 상품의 추천재고가 업데이트되었습니다!")
                    st.rerun()
                else:
                    st.warning(f"⚠️ {CATEGORIES[batch_category]} 대분류에 상품이 없습니다.")
        
        st.markdown("---")
        
        # 개별 상품 설정
        st.markdown("#### 🎯 개별 상품 설정")
        
        search_for_recommend = st.text_input("🔍 상품 검색 (추천재고 설정용)", key="recommend_search")
        
        if search_for_recommend:
            filtered_for_recommend = st.session_state.inventory_data[
                (st.session_state.inventory_data['상품코드'].str.contains(search_for_recommend, na=False, case=False)) |
                (st.session_state.inventory_data['상품명'].str.contains(search_for_recommend, na=False, case=False))
            ]
            
            if not filtered_for_recommend.empty:
                # 편집 가능한 데이터프레임
                st.markdown("**추천재고수량을 직접 수정하세요:**")
                
                edited_df = st.data_editor(
                    filtered_for_recommend[['상품코드', '상품명', '재고수량', '추천재고수량']],
                    column_config={
                        "상품코드": st.column_config.TextColumn("상품코드", disabled=True),
                        "상품명": st.column_config.TextColumn("상품명", disabled=True),
                        "재고수량": st.column_config.NumberColumn("현재재고", disabled=True),
                        "추천재고수량": st.column_config.NumberColumn("추천재고", min_value=0, step=1)
                    },
                    hide_index=True,
                    use_container_width=True
                )
                
                if st.button("💾 변경사항 저장", type="primary"):
                    try:
                        for _, row in edited_df.iterrows():
                            idx = st.session_state.inventory_data[st.session_state.inventory_data['상품코드'] == row['상품코드']].index[0]
                            st.session_state.inventory_data.loc[idx, '추천재고수량'] = row['추천재고수량']
                        
                        st.success("✅ 추천재고수량이 업데이트되었습니다!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ 저장 중 오류: {e}")

def show_data_analysis():
    """데이터 분석 화면"""
    st.header("📊 데이터 분석 및 통계")
    
    if st.session_state.transaction_history.empty:
        st.warning("📝 분석할 거래 데이터가 없습니다. 거래가 발생하면 자동으로 데이터가 수집됩니다.")
        return
    
    # 기간 선택
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("📅 분석 시작일", datetime.now().date() - pd.Timedelta(days=30))
    with col2:
        end_date = st.date_input("📅 분석 종료일", datetime.now().date())
    
    # 데이터 필터링
    filtered_history = st.session_state.transaction_history.copy()
    filtered_history['날짜'] = pd.to_datetime(filtered_history['일시']).dt.date
    filtered_history = filtered_history[
        (filtered_history['날짜'] >= start_date) & 
        (filtered_history['날짜'] <= end_date)
    ]
    
    if filtered_history.empty:
        st.info("📊 선택한 기간에 거래 데이터가 없습니다.")
        return
    
    # 요약 통계
    st.subheader("📈 기간별 요약 통계")
    
    summary_col1, summary_col2, summary_col3, summary_col4 = st.columns(4)
    
    total_transactions = len(filtered_history)
    total_sales = filtered_history[filtered_history['거래유형'] == '판매']['수량'].sum()
    total_disposal = filtered_history[filtered_history['거래유형'] == '폐기']['수량'].sum()
    total_inbound = filtered_history[filtered_history['거래유형'] == '입고']['수량'].sum()
    
    with summary_col1:
        st.metric("총 거래 건수", f"{total_transactions:,}건")
    with summary_col2:
        st.metric("총 판매량", f"{total_sales:,.0f}개")
    with summary_col3:
        st.metric("총 폐기량", f"{total_disposal:,.0f}개")
    with summary_col4:
        disposal_rate = (total_disposal / (total_sales + total_disposal) * 100) if (total_sales + total_disposal) > 0 else 0
        st.metric("폐기율", f"{disposal_rate:.1f}%")
    
    # 차트 생성
    weekday_chart, monthly_chart = create_sales_analysis_chart()
    
    if weekday_chart and monthly_chart:
        st.subheader("📊 판매/폐기 패턴 분석")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.plotly_chart(weekday_chart, use_container_width=True)
        
        with col2:
            st.plotly_chart(monthly_chart, use_container_width=True)
    
    # 대분류별 분석
    st.subheader("🏷️ 대분류별 거래 분석")
    
    # 거래 내역에 대분류 정보 추가
    inventory_dict = st.session_state.inventory_data.set_index('상품코드')['대분류'].to_dict()
    filtered_history['대분류'] = filtered_history['상품코드'].map(inventory_dict)
    filtered_history['대분류명'] = filtered_history['대분류'].map(CATEGORIES)
    
    # 대분류별 판매/폐기 현황
    category_analysis = filtered_history[filtered_history['거래유형'].isin(['판매', '폐기'])].groupby(['대분류명', '거래유형'])['수량'].sum().reset_index()
    
    if not category_analysis.empty:
        fig_category = px.bar(
            category_analysis,
            x='대분류명',
            y='수량',
            color='거래유형',
            title='대분류별 판매/폐기 현황',
            color_discrete_map={'판매': '#2E86AB', '폐기': '#F24236'}
        )
        fig_category.update_layout(height=500, xaxis_tickangle=-45)
        st.plotly_chart(fig_category, use_container_width=True)
    
    # 상세 데이터 테이블
    st.subheader("📋 상세 거래 내역")
    
    # 거래 유형별 필터
    transaction_filter = st.multiselect(
        "거래 유형 선택",
        options=filtered_history['거래유형'].unique(),
        default=filtered_history['거래유형'].unique()
    )
    
    filtered_display = filtered_history[filtered_history['거래유형'].isin(transaction_filter)]
    
    if not filtered_display.empty:
        st.dataframe(
            filtered_display[['일시', '거래유형', '상품명', '대분류명', '수량', '요일']].sort_values('일시', ascending=False),
            use_container_width=True,
            height=400
        )
        
        # 다운로드 버튼
        if st.button("📥 분석 데이터 다운로드"):
            excel_data = filtered_display.to_excel(index=False)
            st.download_button(
                label="📊 엑셀로 다운로드",
                data=excel_data,
                file_name=f"거래분석_{start_date}_{end_date}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
    else:
        st.info("선택한 조건에 맞는 거래가 없습니다.")

def show_stock_recommendations():
    """재고 추천 화면"""
    st.header("🎯 재고 추천 및 발주 관리")
    
    if st.session_state.inventory_data.empty:
        st.warning("📝 추천할 재고 데이터가 없습니다.")
        return
    
    # 발주 필요 상품 목록
    low_stock_items = get_low_stock_recommendations()
    
    if low_stock_items.empty:
        st.success("🎉 모든 상품의 재고가 추천 수준을 충족합니다!")
        
        # 전체 재고 현황 요약
        st.subheader("📊 전체 재고 현황")
        
        total_items = len(st.session_state.inventory_data)
        sufficient_stock = len(st.session_state.inventory_data[
            st.session_state.inventory_data['재고수량'] >= st.session_state.inventory_data['추천재고수량']
        ])
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("전체 상품", f"{total_items:,}개")
        with col2:
            st.metric("재고 충분", f"{sufficient_stock:,}개")
        with col3:
            sufficiency_rate = (sufficient_stock / total_items * 100) if total_items > 0 else 0
            st.metric("충족률", f"{sufficiency_rate:.1f}%")
        
        return
    
    # 발주 우선순위 표시
    st.subheader(f"⚠️ 발주 필요 상품: {len(low_stock_items):,}개")
    
    # 요약 정보
    col1, col2, col3, col4 = st.columns(4)
    
    total_shortage = low_stock_items['부족수량'].sum()
    avg_shortage = low_stock_items['부족수량'].mean()
    max_shortage = low_stock_items['부족수량'].max()
    critical_items = len(low_stock_items[low_stock_items['재고수량'] == 0])
    
    with col1:
        st.metric("총 부족 수량", f"{total_shortage:,.0f}개")
    with col2:
        st.metric("평균 부족", f"{avg_shortage:.1f}개")
    with col3:
        st.metric("최대 부족", f"{max_shortage:,.0f}개")
    with col4:
        st.metric("재고 0인 상품", f"{critical_items:,}개", delta=f"-{critical_items}" if critical_items > 0 else "✅")
    
    # 대분류별 발주 현황
    st.subheader("🏷️ 대분류별 발주 현황")
    
    category_shortage = low_stock_items.groupby('대분류명').agg({
        '부족수량': ['count', 'sum']
    }).round(2)
    category_shortage.columns = ['부족상품수', '총부족수량']
    category_shortage = category_shortage.reset_index()
    
    fig_shortage = px.bar(
        category_shortage,
        x='대분류명',
        y='총부족수량',
        title='대분류별 부족 수량',
        color='총부족수량',
        color_continuous_scale='Reds'
    )
    fig_shortage.update_layout(height=400, xaxis_tickangle=-45)
    st.plotly_chart(fig_shortage, use_container_width=True)
    
    # 발주 우선순위 테이블
    st.subheader("📋 발주 우선순위 (부족수량 기준)")
    
    # 우선순위 필터
    priority_filter = st.selectbox(
        "우선순위 필터",
        ["전체", "긴급 (재고 0)", "높음 (부족 20개 이상)", "보통 (부족 10개 이상)", "낮음 (부족 10개 미만)"]
    )
    
    if priority_filter == "긴급 (재고 0)":
        filtered_recommendations = low_stock_items[low_stock_items['재고수량'] == 0]
    elif priority_filter == "높음 (부족 20개 이상)":
        filtered_recommendations = low_stock_items[low_stock_items['부족수량'] >= 20]
    elif priority_filter == "보통 (부족 10개 이상)":
        filtered_recommendations = low_stock_items[(low_stock_items['부족수량'] >= 10) & (low_stock_items['부족수량'] < 20)]
    elif priority_filter == "낮음 (부족 10개 미만)":
        filtered_recommendations = low_stock_items[low_stock_items['부족수량'] < 10]
    else:
        filtered_recommendations = low_stock_items
    
    if not filtered_recommendations.empty:
        # 우선순위 표시를 위한 컬럼 추가
        def get_priority(row):
            if row['재고수량'] == 0:
                return "🔴 긴급"
            elif row['부족수량'] >= 20:
                return "🟠 높음"
            elif row['부족수량'] >= 10:
                return "🟡 보통"
            else:
                return "🟢 낮음"
        
        filtered_recommendations['우선순위'] = filtered_recommendations.apply(get_priority, axis=1)
        
        display_columns = ['우선순위', '상품코드', '상품명', '대분류명', '재고수량', '추천재고수량', '부족수량']
        st.dataframe(
            filtered_recommendations[display_columns],
            use_container_width=True,
            height=400
        )
        
        # 발주서 생성
        st.subheader("📋 발주서 생성")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("📄 발주서 다운로드", type="primary"):
                # 발주서 형식으로 데이터 정리
                order_sheet = filtered_recommendations[['상품코드', '상품명', '대분류명', '현재재고', '추천재고', '발주수량']].copy()
                order_sheet.columns = ['상품코드', '상품명', '대분류', '현재재고', '추천재고', '발주수량']
                order_sheet['발주일자'] = datetime.now().strftime('%Y-%m-%d')
                order_sheet['비고'] = ''
                
                excel_data = order_sheet.to_excel(index=False)
                st.download_button(
                    label="📥 발주서 엑셀 다운로드",
                    data=excel_data,
                    file_name=f"발주서_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
        
        with col2:
            # 일괄 발주 처리 (가상)
            if st.button("🚚 일괄 발주 요청", type="secondary"):
                st.info(f"📋 {len(filtered_recommendations)}개 상품의 발주가 요청되었습니다. (실제 발주 시스템 연동 필요)")
    
    else:
        st.info(f"📊 '{priority_filter}' 조건에 해당하는 상품이 없습니다.")

def show_data_management():
    """데이터 관리 화면"""
    st.header("💾 데이터 관리")
    
    tab1, tab2, tab3 = st.tabs(["📥 데이터 백업", "🔄 데이터 초기화", "📤 템플릿 다운로드"])
    
    with tab1:
        st.subheader("📥 데이터 백업")
        st.info("💡 정기적인 백업으로 데이터 손실을 방지하세요.")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### 📦 재고 데이터 백업")
            if not st.session_state.inventory_data.empty:
                items_count = len(st.session_state.inventory_data)
                st.write(f"백업 대상: **{items_count:,}**개 상품")
                
                # 백업 파일 생성
                backup_data = st.session_state.inventory_data.copy()
                backup_data['대분류명'] = backup_data['대분류'].map(CATEGORIES)
                
                excel_data = backup_data.to_excel(index=False)
                st.download_button(
                    label="📦 재고 데이터 백업",
                    data=excel_data,
                    file_name=f"재고데이터_백업_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="primary"
                )
            else:
                st.warning("백업할 재고 데이터가 없습니다.")
        
        with col2:
            st.markdown("#### 📊 거래내역 백업")
            if not st.session_state.transaction_history.empty:
                history_count = len(st.session_state.transaction_history)
                st.write(f"백업 대상: **{history_count:,}**건 거래내역")
                
                excel_data = st.session_state.transaction_history.to_excel(index=False)
                st.download_button(
                    label="📊 거래내역 백업",
                    data=excel_data,
                    file_name=f"거래내역_백업_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="primary"
                )
            else:
                st.warning("백업할 거래내역이 없습니다.")
    
    with tab2:
        st.subheader("🔄 데이터 초기화")
        st.error("⚠️ **주의**: 이 작업은 되돌릴 수 없습니다. 반드시 백업을 먼저 진행하세요!")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("📦 재고 데이터만 초기화", type="secondary"):
                if st.session_state.get('confirm_inventory_reset', False):
                    st.session_state.inventory_data = pd.DataFrame(columns=[
                        '상품코드', '상품명', '대분류', '매가', '재고수량', '추천재고수량', '최종수정일'
                    ])
                    st.session_state.confirm_inventory_reset = False
                    st.success("✅ 재고 데이터가 초기화되었습니다.")
                    st.rerun()
                else:
                    st.session_state.confirm_inventory_reset = True
                    st.warning("한 번 더 클릭하면 재고 데이터가 삭제됩니다.")
        
        with col2:
            if st.button("📊 거래내역만 초기화", type="secondary"):
                if st.session_state.get('confirm_history_reset', False):
                    st.session_state.transaction_history = pd.DataFrame(columns=[
                        '일시', '거래유형', '상품코드', '상품명', '수량', '변경전재고', '변경후재고', '요일', '월'
                    ])
                    st.session_state.confirm_history_reset = False
                    st.success("✅ 거래내역이 초기화되었습니다.")
                    st.rerun()
                else:
                    st.session_state.confirm_history_reset = True
                    st.warning("한 번 더 클릭하면 거래내역이 삭제됩니다.")
    
    with tab3:
        st.subheader("📤 업로드 템플릿 다운로드")
        st.info("💡 올바른 형식의 엑셀 파일을 업로드하기 위한 템플릿을 제공합니다.")
        
        # 재고 템플릿
        inventory_template = pd.DataFrame({
            '상품코드': ['8801234567890', '8801234567891', ''],
            '상품명': ['삼각김밥 참치마요', '삼각김밥 불고기', ''],
            '매가': [1200, 1300, ''],
            '재고수량': [10, 15, ''],
            '추천재고수량': [20, 25, ''],
            '비고': ['', '', '']
        })
        
        st.dataframe(inventory_template.head(2), use_container_width=True)
        
        excel_data = inventory_template.to_excel(index=False)
        st.download_button(
            label="📦 재고 업로드 템플릿 다운로드",
            data=excel_data,
            file_name="재고_업로드_템플릿.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary"
        )
        
        # 카테고리 안내
        st.markdown("---")
        st.markdown("#### 📂 대분류 카테고리 안내")
        
        categories_df = pd.DataFrame([
            {'코드': k, '카테고리명': v} for k, v in CATEGORIES.items()
        ])
        
        col1, col2 = st.columns(2)
        half_point = len(categories_df) // 2
        
        with col1:
            st.dataframe(categories_df[:half_point], hide_index=True, use_container_width=True)
        with col2:
            st.dataframe(categories_df[half_point:], hide_index=True, use_container_width=True)

# 푸터
def show_footer():
    """푸터 표시"""
    st.markdown("---")
    st.markdown(
        """
        <div style='text-align: center; color: gray; font-size: 0.9em; padding: 1rem 0;'>
        🏪 <strong>GS25 편의점 재고관리 시스템</strong> | 
        Made with ❤️ using Streamlit & Plotly | 
        버전 3.0.0 (AI 분석 기능 포함)
        </div>
        """, 
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    try:
        main()
        show_footer()
    except Exception as e:
        st.error(f"시스템 오류가 발생했습니다: {e}")
        st.error("페이지를 새로고침하거나 관리자에게 문의하세요.")
        if st.button("🔄 페이지 새로고침"):
            st.rerun()
