import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, date
import io
import openpyxl
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
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

@st.cache_data
def safe_convert_to_string(value):
    """안전하게 값을 문자열로 변환 (float 오류 방지)"""
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

@st.cache_data
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

def clean_dataframe(df):
    """데이터프레임 정리"""
    try:
        df.columns = [str(col).strip() for col in df.columns]
        df = df.dropna(how='all')
        df = df.reset_index(drop=True)
        return df
    except Exception as e:
        st.error(f"데이터프레임 정리 중 오류: {e}")
        return df

def process_excel_file(uploaded_file, file_type="재고"):
    """엑셀 파일 처리 함수 (오류 방지 강화)"""
    try:
        # 파일 읽기 - openpyxl 엔진 사용
        df = pd.read_excel(uploaded_file, engine='openpyxl')
        
        # 데이터프레임 정리
        df = clean_dataframe(df)
        
        if df.empty:
            st.error("파일에 데이터가 없습니다.")
            return None
        
        # 파일 타입별 처리
        if file_type == "재고":
            return process_inventory_file(df)
        elif file_type in ["입고", "판매", "폐기"]:
            return process_transaction_file(df)
        
        return df
        
    except Exception as e:
        st.error(f"파일 처리 중 오류가 발생했습니다: {str(e)}")
        return None

def process_inventory_file(df):
    """재고 파일 전용 처리"""
    try:
        # 필수 컬럼 확인
        required_columns = ['상품코드', '상품명']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            st.error(f"필수 컬럼이 없습니다: {missing_columns}")
            return None
        
        # 데이터 타입 변환
        df['상품코드'] = df['상품코드'].apply(safe_convert_to_string)
        df['상품명'] = df['상품명'].apply(safe_convert_to_string)
        
        # 옵셔널 컬럼 처리
        if '매가' in df.columns:
            df['매가'] = df['매가'].apply(lambda x: safe_convert_to_numeric(x, 0))
        else:
            df['매가'] = 0
            
        if '재고수량' in df.columns:
            df['재고수량'] = df['재고수량'].apply(lambda x: safe_convert_to_numeric(x, 0))
        elif '이월수량' in df.columns:
            df['재고수량'] = df['이월수량'].apply(lambda x: safe_convert_to_numeric(x, 0))
        else:
            df['재고수량'] = 0
        
        # 빈 상품코드나 상품명 제거
        df = df[(df['상품코드'] != "") & (df['상품명'] != "")]
        
        return df
        
    except Exception as e:
        st.error(f"재고 파일 처리 중 오류: {e}")
        return None

def process_transaction_file(df):
    """거래 파일 전용 처리"""
    try:
        # 수량 컬럼 찾기
        quantity_columns = ['수량', '판매수량', '입고수량', '폐기수량', '매입수량']
        quantity_col = None
        
        for col in quantity_columns:
            if col in df.columns:
                quantity_col = col
                break
        
        if quantity_col is None:
            st.error("수량 컬럼을 찾을 수 없습니다.")
            return None
        
        # 데이터 타입 변환
        df['상품코드'] = df['상품코드'].apply(safe_convert_to_string)
        df['수량'] = df[quantity_col].apply(lambda x: safe_convert_to_numeric(x, 0))
        
        if '상품명' in df.columns:
            df['상품명'] = df['상품명'].apply(safe_convert_to_string)
        else:
            df['상품명'] = ""
        
        # 유효한 데이터만 필터링
        df = df[(df['상품코드'] != "") & (df['수량'] > 0)]
        
        return df[['상품코드', '상품명', '수량']]
        
    except Exception as e:
        st.error(f"거래 파일 처리 중 오류: {e}")
        return None

def initialize_session_state():
    """세션 상태 초기화"""
    if 'inventory_data' not in st.session_state:
        st.session_state.inventory_data = pd.DataFrame(columns=[
            '상품코드', '상품명', '대분류', '매가', '재고수량', '최종수정일'
        ])
    
    if 'transaction_history' not in st.session_state:
        st.session_state.transaction_history = pd.DataFrame(columns=[
            '일시', '거래유형', '상품코드', '상품명', '수량', '변경전재고', '변경후재고'
        ])
    
    # 페이지 네비게이션용 상태
    if 'current_page' not in st.session_state:
        st.session_state.current_page = "🏠 대시보드"

def add_transaction_record(transaction_type, product_code, product_name, quantity, before_qty, after_qty):
    """거래 내역 추가"""
    try:
        new_record = pd.DataFrame({
            '일시': [datetime.now().strftime('%Y-%m-%d %H:%M:%S')],
            '거래유형': [transaction_type],
            '상품코드': [str(product_code)],
            '상품명': [str(product_name)],
            '수량': [float(quantity)],
            '변경전재고': [float(before_qty)],
            '변경후재고': [float(after_qty)]
        })
        st.session_state.transaction_history = pd.concat(
            [st.session_state.transaction_history, new_record], 
            ignore_index=True
        )
    except Exception as e:
        st.error(f"거래 내역 추가 중 오류: {e}")

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

def create_excel_download(df, filename):
    """엑셀 다운로드 파일 생성"""
    try:
        buffer = io.BytesIO()
        
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Data', index=False)
            
            worksheet = writer.sheets['Data']
            
            # 스타일 정의
            header_font = Font(bold=True, color="FFFFFF", size=12)
            header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
            border = Border(
                left=Side(style='thin'),
                right=Side(style='thin'),
                top=Side(style='thin'),
                bottom=Side(style='thin')
            )
            
            # 헤더 스타일 적용
            for cell in worksheet[1]:
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = Alignment(horizontal="center", vertical="center")
                cell.border = border
            
            # 열 너비 자동 조정
            for column in worksheet.columns:
                max_length = 0
                column_letter = column[0].column_letter
                
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                
                adjusted_width = min(max_length + 3, 50)
                worksheet.column_dimensions[column_letter].width = adjusted_width
        
        buffer.seek(0)
        return buffer.getvalue()
        
    except Exception as e:
        st.error(f"엑셀 파일 생성 중 오류: {e}")
        return None

def validate_product_code(code):
    """상품코드 유효성 검사"""
    code = str(code).strip()
    if not code or code == "":
        return False, "상품코드가 비어있습니다."
    if len(code) < 5:
        return False, "상품코드가 너무 짧습니다."
    return True, ""

def main():
    initialize_session_state()
    
    # 메인 헤더
    st.markdown("""
    <div style='text-align: center; padding: 1rem 0;'>
        <h1 style='color: #366092; margin-bottom: 0;'>🏪 GS25 편의점 재고관리 시스템</h1>
        <p style='color: #666; margin-top: 0;'>효율적인 재고 관리로 편의점 운영 최적화</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # 사이드바
    with st.sidebar:
        st.markdown("### 📋 시스템 메뉴")
        
        # 메뉴 선택
        menu_options = [
            "🏠 대시보드", 
            "📦 재고조회", 
            "📁 파일업로드", 
            "✏️ 직접입력", 
            "📊 거래내역", 
            "💾 데이터관리"
        ]
        
        # 현재 페이지를 기본값으로 설정
        current_index = 0
        if st.session_state.current_page in menu_options:
            current_index = menu_options.index(st.session_state.current_page)
        
        selected_menu = st.radio(
            "기능 선택",
            menu_options,
            index=current_index
        )
        
        # 선택된 메뉴 업데이트
        st.session_state.current_page = selected_menu
        
        st.markdown("---")
        
        # 현재 상태 표시
        st.markdown("### 📈 현재 상태")
        if not st.session_state.inventory_data.empty:
            total_items = len(st.session_state.inventory_data)
            total_stock = st.session_state.inventory_data['재고수량'].sum()
            zero_stock = len(st.session_state.inventory_data[st.session_state.inventory_data['재고수량'] == 0])
            
            st.metric("총 상품 수", f"{total_items:,}개")
            st.metric("총 재고량", f"{total_stock:,.0f}개")
            
            if zero_stock > 0:
                st.error(f"⚠️ 재고 없음: {zero_stock}개")
            else:
                st.success("✅ 모든 상품 재고 확보")
        else:
            st.info("📝 재고 데이터를 등록해주세요")
            
        # 시스템 정보
        st.markdown("---")
        st.markdown("### ℹ️ 시스템 정보")
        st.caption("버전: 2.1.0")
        st.caption("배포: Streamlit Cloud")
        st.caption("업데이트: 실시간")
    
    # 메인 컨텐츠 - 선택된 메뉴에 따라 표시
    if selected_menu == "🏠 대시보드":
        show_dashboard()
    elif selected_menu == "📦 재고조회":
        show_inventory_search()
    elif selected_menu == "📁 파일업로드":
        show_file_upload()
    elif selected_menu == "✏️ 직접입력":
        show_manual_input()
    elif selected_menu == "📊 거래내역":
        show_transaction_history()
    elif selected_menu == "💾 데이터관리":
        show_data_management()

def show_dashboard():
    """대시보드 화면"""
    st.header("📊 재고 현황 대시보드")
    
    if st.session_state.inventory_data.empty:
        st.warning("📝 재고 데이터가 없습니다. 파일을 업로드하거나 직접 입력해주세요.")
        
        # 시작 가이드
        st.markdown("### 🚀 시작하기")
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("""
            #### 📁 파일 업로드 방식
            - 기존 엑셀 재고 파일 업로드
            - 대량 데이터 한 번에 입력
            - 빠른 시스템 구축
            
            👈 **사이드바 > 📁 파일업로드** 선택
            """)
            
        with col2:
            st.markdown("""
            #### ✏️ 직접 입력 방식  
            - 상품별 개별 입력
            - 정확한 데이터 관리
            - 단계별 시스템 구축
            
            👈 **사이드바 > ✏️ 직접입력** 선택
            """)
        
        # 데모 데이터 생성 옵션
        st.markdown("---")
        st.markdown("### 🎯 빠른 체험")
        if st.button("📋 데모 데이터 생성", type="primary"):
            demo_data = pd.DataFrame({
                '상품코드': ['8801234567890', '8801234567891', '8801234567892'],
                '상품명': ['삼각김밥 참치마요', '삼각김밥 불고기', '컵라면 신라면'],
                '대분류': ['02', '02', '14'],
                '매가': [1200, 1300, 1800],
                '재고수량': [15, 12, 25],
                '최종수정일': [datetime.now().strftime('%Y-%m-%d %H:%M:%S')] * 3
            })
            st.session_state.inventory_data = demo_data
            st.success("✅ 데모 데이터가 생성되었습니다!")
            st.rerun()
        
        return
    
    # 주요 지표
    col1, col2, col3, col4 = st.columns(4)
    
    total_items = len(st.session_state.inventory_data)
    total_stock = st.session_state.inventory_data['재고수량'].sum()
    zero_stock = len(st.session_state.inventory_data[st.session_state.inventory_data['재고수량'] == 0])
    avg_stock = st.session_state.inventory_data['재고수량'].mean()
    
    with col1:
        st.metric("총 상품 수", f"{total_items:,}개")
    with col2:
        st.metric("총 재고량", f"{total_stock:,.0f}개")
    with col3:
        st.metric("재고 없음", f"{zero_stock:,}개", delta=f"-{zero_stock}" if zero_stock > 0 else "✅")
    with col4:
        st.metric("평균 재고", f"{avg_stock:.1f}개")
    
    # 카테고리별 현황
    if '대분류' in st.session_state.inventory_data.columns:
        st.subheader("📈 카테고리별 재고 현황")
        
        category_stats = st.session_state.inventory_data.groupby('대분류').agg({
            '재고수량': ['count', 'sum', 'mean']
        }).round(2)
        category_stats.columns = ['상품 수', '총 재고량', '평균 재고']
        
        # 카테고리명 추가
        category_stats['카테고리명'] = category_stats.index.map(CATEGORIES)
        category_stats = category_stats[['카테고리명', '상품 수', '총 재고량', '평균 재고']]
        
        st.dataframe(category_stats, use_container_width=True)
    
    # 알림 섹션
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("⚠️ 재고 부족 상품 (5개 이하)")
        low_stock = st.session_state.inventory_data[st.session_state.inventory_data['재고수량'] <= 5]
        if not low_stock.empty:
            st.dataframe(
                low_stock[['상품코드', '상품명', '재고수량']].head(10), 
                use_container_width=True
            )
        else:
            st.success("✅ 재고 부족 상품이 없습니다!")
    
    with col2:
        st.subheader("🔄 최근 거래 내역")
        if not st.session_state.transaction_history.empty:
            recent_transactions = st.session_state.transaction_history.tail(10)
            st.dataframe(
                recent_transactions[['일시', '거래유형', '상품명', '수량']],
                use_container_width=True
            )
        else:
            st.info("거래 내역이 없습니다.")

def show_inventory_search():
    """재고 조회 화면"""
    st.header("📦 재고 조회 및 검색")
    
    if st.session_state.inventory_data.empty:
        st.warning("조회할 재고 데이터가 없습니다.")
        return
    
    # 검색 필터
    with st.expander("🔍 검색 옵션", expanded=True):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            search_code = st.text_input("상품코드 검색", placeholder="예: 8801234567890")
        
        with col2:
            search_name = st.text_input("상품명 검색", placeholder="예: 삼각김밥")
        
        with col3:
            if '대분류' in st.session_state.inventory_data.columns:
                categories = ['전체'] + sorted(list(st.session_state.inventory_data['대분류'].unique()))
                selected_category = st.selectbox("카테고리 필터", categories)
            else:
                selected_category = '전체'
    
    # 데이터 필터링
    filtered_data = st.session_state.inventory_data.copy()
    
    if search_code:
        filtered_data = filtered_data[filtered_data['상품코드'].str.contains(search_code, na=False, case=False)]
    
    if search_name:
        filtered_data = filtered_data[filtered_data['상품명'].str.contains(search_name, na=False, case=False)]
    
    if selected_category != '전체':
        filtered_data = filtered_data[filtered_data['대분류'] == selected_category]
    
    # 결과 표시
    st.markdown(f"### 📋 검색 결과: **{len(filtered_data):,}**건")
    
    if not filtered_data.empty:
        st.dataframe(filtered_data, use_container_width=True, height=400)
        
        # 다운로드 버튼
        col1, col2, col3 = st.columns(3)
        with col2:
            excel_data = create_excel_download(filtered_data, "재고조회결과.xlsx")
            if excel_data:
                st.download_button(
                    label="📥 검색결과 엑셀 다운로드",
                    data=excel_data,
                    file_name=f"재고조회결과_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="primary"
                )
    else:
        st.info("🔍 검색 조건에 맞는 상품이 없습니다.")

def show_file_upload():
    """파일 업로드 화면"""
    st.header("📁 파일 업로드")
    
    # 업로드 안내
    st.info("💡 엑셀 파일(.xlsx)을 업로드하여 재고 데이터를 관리할 수 있습니다.")
    
    tab1, tab2, tab3, tab4 = st.tabs(["📦 재고 파일", "📈 입고 파일", "💰 판매 파일", "🗑️ 폐기 파일"])
    
    with tab1:
        st.subheader("📦 재고 데이터 업로드")
        
        # 파일 형식 안내
        with st.expander("📋 파일 형식 안내", expanded=True):
            st.markdown("""
            **필수 컬럼:**
            - `상품코드`: 상품의 고유 코드
            - `상품명`: 상품명
            
            **선택 컬럼:**
            - `매가`: 상품 가격 (기본값: 0)
            - `재고수량` 또는 `이월수량`: 현재 재고량 (기본값: 0)
            
            **지원 형식:** .xlsx (Excel 2007 이상)
            """)
        
        inventory_file = st.file_uploader(
            "재고 파일 선택",
            type=['xlsx'],
            key="inventory_file",
            help="Excel 파일(.xlsx)만 지원됩니다"
        )
        
        if inventory_file:
            col1, col2 = st.columns([1, 1])
            with col1:
                replace_data = st.checkbox("기존 데이터 교체", value=True, help="체크 시 기존 재고 데이터를 완전히 교체합니다")
            
            if st.button("📦 재고 데이터 업로드", type="primary", key="upload_inventory"):
                with st.spinner("파일을 처리하고 있습니다..."):
                    processed_df = process_excel_file(inventory_file, "재고")
                    
                    if processed_df is not None and not processed_df.empty:
                        # 대분류 설정 (기본값: 99)
                        processed_df['대분류'] = '99'
                        processed_df['최종수정일'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        
                        # 필수 컬럼만 선택
                        final_df = processed_df[['상품코드', '상품명', '대분류', '매가', '재고수량', '최종수정일']].copy()
                        
                        if replace_data:
                            st.session_state.inventory_data = final_df
                        else:
                            # 기존 데이터와 병합
                            existing_codes = st.session_state.inventory_data['상품코드'].tolist()
                            new_data = final_df[~final_df['상품코드'].isin(existing_codes)]
                            st.session_state.inventory_data = pd.concat([st.session_state.inventory_data, new_data], ignore_index=True)
                        
                        st.success(f"✅ 재고 데이터 {len(final_df):,}건이 성공적으로 업로드되었습니다!")
                        st.balloons()
                        st.rerun()
    
    with tab2:
        upload_transaction_tab("입고", "📈", "입고된 상품의 재고를 증가시킵니다.")
    
    with tab3:
        upload_transaction_tab("판매", "💰", "판매된 상품의 재고를 감소시킵니다.")
    
    with tab4:
        upload_transaction_tab("폐기", "🗑️", "폐기된 상품의 재고를 감소시킵니다.")

def upload_transaction_tab(transaction_type, icon, description):
    """거래 파일 업로드 탭"""
    st.subheader(f"{icon} {transaction_type} 데이터 업로드")
    st.info(f"💡 {description}")
    
    if st.session_state.inventory_data.empty:
        st.warning("⚠️ 먼저 재고 데이터를 업로드해주세요.")
        return
    
    transaction_file = st.file_uploader(
        f"{transaction_type} 파일 선택",
        type=['xlsx'],
        key=f"{transaction_type}_file",
        help="Excel 파일(.xlsx)을 선택해주세요"
    )
    
    if transaction_file:
        if st.button(f"{icon} {transaction_type} 데이터 처리", type="primary", key=f"process_{transaction_type}"):
            with st.spinner(f"{transaction_type} 데이터를 처리하고 있습니다..."):
                processed_df = process_excel_file(transaction_file, transaction_type)
                
                if processed_df is not None and not processed_df.empty:
                    success_count = 0
                    fail_count = 0
                    
                    progress_bar = st.progress(0)
                    total_rows = len(processed_df)
                    
                    for idx, row in processed_df.iterrows():
                        progress_bar.progress((idx + 1) / total_rows)
                        
                        product_code = safe_convert_to_string(row['상품코드'])
                        quantity = safe_convert_to_numeric(row['수량'], 0)
                        
                        is_valid, error_msg = validate_product_code(product_code)
                        
                        if not is_valid or quantity <= 0:
                            fail_count += 1
                            continue
                        
                        # 입고는 양수, 판매/폐기는 음수로 처리
                        quantity_change = quantity if transaction_type == "입고" else -quantity
                        
                        if update_inventory(product_code, quantity_change, transaction_type):
                            success_count += 1
                        else:
                            fail_count += 1
                    
                    progress_bar.empty()
                    
                    # 결과 표시
                    col1, col2 = st.columns(2)
                    with col1:
                        st.success(f"✅ 성공: **{success_count:,}**건")
                    with col2:
                        if fail_count > 0:
                            st.error(f"❌ 실패: **{fail_count:,}**건")
                    
                    if success_count > 0:
                        st.balloons()
                        st.rerun()

def show_manual_input():
    """직접 입력 화면"""
    st.header("✏️ 직접 입력")
    
    tab1, tab2 = st.tabs(["➕ 신규 상품 등록", "📝 재고 조정"])
    
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
                new_price = st.number_input("매가 *", min_value=0, value=0, step=100, help="원 단위")
                new_stock = st.number_input("초기재고 *", min_value=0, value=0, step=1, help="개 단위")
                
            col3, col4, col5 = st.columns([1, 1, 1])
            with col4:
                submitted = st.form_submit_button("🆕 상품 등록", type="primary", use_container_width=True)
            
            if submitted:
                # 유효성 검사
                is_valid, error_msg = validate_product_code(new_code)
                
                if not is_valid:
                    st.error(f"❌ {error_msg}")
                elif not new_name.strip():
                    st.error("❌ 상품명을 입력해주세요!")
                elif new_code in st.session_state.inventory_data['상품코드'].values:
                    st.error("❌ 이미 존재하는 상품코드입니다!")
                else:
                    # 신규 상품 추가
                    new_product = pd.DataFrame({
                        '상품코드': [new_code],
                        '상품명': [new_name.strip()],
                        '대분류': [new_category],
                        '매가': [new_price],
                        '재고수량': [new_stock],
                        '최종수정일': [datetime.now().strftime('%Y-%m-%d %H:%M:%S')]
                    })
                    
                    st.session_state.inventory_data = pd.concat([st.session_state.inventory_data, new_product], ignore_index=True)
                    
                    # 거래 내역 추가
                    add_transaction_record("신규등록", new_code, new_name, new_stock, 0, new_stock)
                    
                    st.success(f"✅ 신규 상품이 등록되었습니다! (코드: {new_code})")
                    st.balloons()
                    st.rerun()
    
    with tab2:
        st.subheader("📝 재고 조정")
        
        if st.session_state.inventory_data.empty:
            st.warning("⚠️ 조정할 재고 데이터가 없습니다. 먼저 재고를 등록해주세요.")
            return
        
        # 상품 검색 및 선택
        search_term = st.text_input("🔍 상품 검색 (코드 또는 상품명)", placeholder="검색어를 입력하세요")
        
        if search_term:
            # 검색 결과 필터링
            filtered_products = st.session_state.inventory_data[
                (st.session_state.inventory_data['상품코드'].str.contains(search_term, na=False, case=False)) |
                (st.session_state.inventory_data['상품명'].str.contains(search_term, na=False, case=False))
            ]
            
            if not filtered_products.empty:
                # 검색 결과를 선택 옵션으로 표시
                product_options = []
                for _, row in filtered_products.iterrows():
                    option = f"{row['상품코드']} - {row['상품명']} (재고: {row['재고수량']:.0f})"
                    product_options.append(option)
                
                selected_product = st.selectbox("조정할 상품 선택", ["선택해주세요"] + product_options)
                
                if selected_product != "선택해주세요":
                    selected_code = selected_product.split(" - ")[0]
                    product_info = st.session_state.inventory_data[
                        st.session_state.inventory_data['상품코드'] == selected_code
                    ].iloc[0]
                    
                    current_stock = float(product_info['재고수량'])
                    
                    # 조정 입력
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        adjustment_type = st.selectbox(
                            "조정 유형",
                            ["입고", "판매", "폐기", "직접조정"],
                            help="재고 변동 유형을 선택하세요"
                        )
                    
                    with col2:
                        if adjustment_type == "직접조정":
                            new_stock = st.number_input(
                                "새로운 재고량", 
                                min_value=0, 
                                value=int(current_stock),
                                help="설정할 재고량을 입력하세요"
                            )
                            adjustment_qty = new_stock - current_stock
                        else:
                            adjustment_qty = st.number_input(
                                "조정 수량", 
                                min_value=1, 
                                value=1, 
                                step=1,
                                help=f"{adjustment_type}할 수량을 입력하세요"
                            )
                            if adjustment_type in ["판매", "폐기"]:
                                adjustment_qty = -adjustment_qty
                    
                    with col3:
                        # 조정 후 예상 재고 표시
                        if adjustment_type == "직접조정":
                            expected_stock = new_stock
                        else:
                            expected_stock = max(0, current_stock + adjustment_qty)
                        
                        st.metric(
                            "조정 후 재고",
                            f"{expected_stock:,.0f}개",
                            delta=f"{adjustment_qty:+.0f}"
                        )
                    
                    # 조정 실행
                    col1, col2, col3 = st.columns([1, 1, 1])
                    with col2:
                        if st.button("📝 재고 조정 실행", type="primary", use_container_width=True):
                            try:
                                if adjustment_type == "직접조정":
                                    # 직접 조정
                                    idx = st.session_state.inventory_data[
                                        st.session_state.inventory_data['상품코드'] == selected_code
                                    ].index[0]
                                    
                                    st.session_state.inventory_data.loc[idx, '재고수량'] = new_stock
                                    st.session_state.inventory_data.loc[idx, '최종수정일'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                                    
                                    add_transaction_record("직접조정", selected_code, product_info['상품명'], adjustment_qty, current_stock, new_stock)
                                else:
                                    # 일반 조정
                                    update_inventory(selected_code, adjustment_qty, adjustment_type)
                                
                                st.success(f"✅ 재고 조정이 완료되었습니다! ({current_stock:.0f} → {expected_stock:.0f})")
                                st.balloons()
                                st.rerun()
                                
                            except Exception as e:
                                st.error(f"❌ 재고 조정 중 오류가 발생했습니다: {e}")
            else:
                st.info("🔍 검색 결과가 없습니다. 다른 검색어를 입력해보세요.")
        else:
            st.info("💡 상품코드나 상품명으로 검색하여 재고를 조정할 상품을 선택하세요.")

def show_transaction_history():
    """거래 내역 화면"""
    st.header("📊 거래 내역 관리")
    
    if st.session_state.transaction_history.empty:
        st.info("📝 거래 내역이 없습니다. 재고 변동이 발생하면 자동으로 기록됩니다.")
        return
    
    # 필터링 옵션
    with st.expander("🔍 필터 옵션", expanded=True):
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            transaction_types = ['전체'] + sorted(list(st.session_state.transaction_history['거래유형'].unique()))
            selected_type = st.selectbox("거래 유형", transaction_types)
        
        with col2:
            start_date = st.date_input("시작 날짜", datetime.now().date() - pd.Timedelta(days=7))
        
        with col3:
            end_date = st.date_input("종료 날짜", datetime.now().date())
        
        with col4:
            search_product = st.text_input("상품 검색", placeholder="상품명 또는 코드")
    
    # 데이터 필터링
    filtered_history = st.session_state.transaction_history.copy()
    
    # 거래유형 필터
    if selected_type != '전체':
        filtered_history = filtered_history[filtered_history['거래유형'] == selected_type]
    
    # 날짜 필터
    filtered_history['날짜'] = pd.to_datetime(filtered_history['일시']).dt.date
    filtered_history = filtered_history[
        (filtered_history['날짜'] >= start_date) & 
        (filtered_history['날짜'] <= end_date)
    ]
    
    # 상품 검색 필터
    if search_product:
        filtered_history = filtered_history[
            (filtered_history['상품코드'].str.contains(search_product, na=False, case=False)) |
            (filtered_history['상품명'].str.contains(search_product, na=False, case=False))
        ]
    
    # 결과 표시
    st.markdown(f"### 📋 거래 내역: **{len(filtered_history):,}**건")
    
    if not filtered_history.empty:
        # 통계 정보
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            total_transactions = len(filtered_history)
            st.metric("총 거래 건수", f"{total_transactions:,}")
        
        with col2:
            inbound_count = len(filtered_history[filtered_history['거래유형'] == '입고'])
            st.metric("입고 건수", f"{inbound_count:,}")
        
        with col3:
            sales_count = len(filtered_history[filtered_history['거래유형'] == '판매'])
            st.metric("판매 건수", f"{sales_count:,}")
        
        with col4:
            disposal_count = len(filtered_history[filtered_history['거래유형'] == '폐기'])
            st.metric("폐기 건수", f"{disposal_count:,}")
        
        # 거래 내역 테이블
        display_history = filtered_history.drop('날짜', axis=1).sort_values('일시', ascending=False)
        st.dataframe(display_history, use_container_width=True, height=400)
        
        # 다운로드 버튼
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            excel_data = create_excel_download(display_history, "거래내역.xlsx")
            if excel_data:
                st.download_button(
                    label="📥 거래내역 엑셀 다운로드",
                    data=excel_data,
                    file_name=f"거래내역_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="primary"
                )
    else:
        st.info("🔍 선택한 조건에 맞는 거래 내역이 없습니다.")

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
                
                inventory_excel = create_excel_download(st.session_state.inventory_data, "재고데이터_백업.xlsx")
                if inventory_excel:
                    st.download_button(
                        label="📦 재고 데이터 백업",
                        data=inventory_excel,
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
                
                history_excel = create_excel_download(st.session_state.transaction_history, "거래내역_백업.xlsx")
                if history_excel:
                    st.download_button(
                        label="📊 거래내역 백업",
                        data=history_excel,
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
            st.markdown("#### 🗑️ 개별 초기화")
            
            if st.button("📦 재고 데이터만 초기화", type="secondary"):
                if st.session_state.get('confirm_inventory_reset', False):
                    st.session_state.inventory_data = pd.DataFrame(columns=[
                        '상품코드', '상품명', '대분류', '매가', '재고수량', '최종수정일'
                    ])
                    st.session_state.confirm_inventory_reset = False
                    st.success("✅ 재고 데이터가 초기화되었습니다.")
                    st.rerun()
                else:
                    st.session_state.confirm_inventory_reset = True
                    st.warning("한 번 더 클릭하면 재고 데이터가 삭제됩니다.")
            
            if st.button("📊 거래내역만 초기화", type="secondary"):
                if st.session_state.get('confirm_history_reset', False):
                    st.session_state.transaction_history = pd.DataFrame(columns=[
                        '일시', '거래유형', '상품코드', '상품명', '수량', '변경전재고', '변경후재고'
                    ])
                    st.session_state.confirm_history_reset = False
                    st.success("✅ 거래내역이 초기화되었습니다.")
                    st.rerun()
                else:
                    st.session_state.confirm_history_reset = True
                    st.warning("한 번 더 클릭하면 거래내역이 삭제됩니다.")
        
        with col2:
            st.markdown("#### 🔄 전체 초기화")
            
            if st.button("🗑️ 모든 데이터 초기화", type="secondary"):
                if st.session_state.get('confirm_full_reset', False):
                    st.session_state.inventory_data = pd.DataFrame(columns=[
                        '상품코드', '상품명', '대분류', '매가', '재고수량', '최종수정일'
                    ])
                    st.session_state.transaction_history = pd.DataFrame(columns=[
                        '일시', '거래유형', '상품코드', '상품명', '수량', '변경전재고', '변경후재고'
                    ])
                    # 확인 플래그들도 초기화
                    for key in ['confirm_inventory_reset', 'confirm_history_reset', 'confirm_full_reset']:
                        if key in st.session_state:
                            del st.session_state[key]
                    
                    st.success("✅ 모든 데이터가 초기화되었습니다.")
                    st.rerun()
                else:
                    st.session_state.confirm_full_reset = True
                    st.error("⚠️ 한 번 더 클릭하면 모든 데이터가 삭제됩니다!")
    
    with tab3:
        st.subheader("📤 업로드 템플릿 다운로드")
        st.info("💡 올바른 형식의 엑셀 파일을 업로드하기 위한 템플릿을 제공합니다.")
        
        # 재고 템플릿
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### 📦 재고 업로드 템플릿")
            inventory_template = pd.DataFrame({
                '상품코드': ['8801234567890', '8801234567891', ''],
                '상품명': ['삼각김밥 참치마요', '삼각김밥 불고기', ''],
                '더보기': ['', '', ''],
                '매가': [1200, 1300, ''],
                '이월수량': [10, 15, ''],
                '매입수량': [0, 0, ''],
                '판매수량': [0, 0, ''],
                '차이수량': [0, 0, ''],
                '재고수량': [10, 15, '']
            })
            
            st.dataframe(inventory_template.head(2), use_container_width=True)
            
            inventory_excel = create_excel_download(inventory_template, "재고템플릿.xlsx")
            if inventory_excel:
                st.download_button(
                    label="📦 재고 템플릿 다운로드",
                    data=inventory_excel,
                    file_name="재고_업로드_템플릿.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="primary"
                )
        
        with col2:
            st.markdown("#### 📊 거래 업로드 템플릿")
            transaction_template = pd.DataFrame({
                '상품코드': ['8801234567890', '8801234567891', ''],
                '상품명': ['삼각김밥 참치마요', '삼각김밥 불고기', ''],
                '수량': [5, 3, '']
            })
            
            st.dataframe(transaction_template.head(2), use_container_width=True)
            
            transaction_excel = create_excel_download(transaction_template, "거래템플릿.xlsx")
            if transaction_excel:
                st.download_button(
                    label="📊 거래 템플릿 다운로드",
                    data=transaction_excel,
                    file_name="거래_업로드_템플릿.xlsx",
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
        Made with ❤️ using Streamlit | 
        버전 2.1.0 (Cloud 최적화)
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
