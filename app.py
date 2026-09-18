import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import timedelta

# =========================================================================
# 1. 页面基本配置
# =========================================================================
st.set_page_config(
    page_title="电商全景综合销售数据分析看板",
    page_icon="📊",
    layout="wide"
)

st.title("📊 电商全景综合销售数据分析看板")
st.caption("集成动销分析、运营绩效、SKU 帕累托划分、渠道分析及同订单日期对齐的 SKU 退货率分析")

# =========================================================================
# 2. 数据加载与清洗函数
# =========================================================================
@st.cache_data
def load_sales_data(uploaded_file):
    if uploaded_file.name.endswith('.csv'):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)
    
    df.columns = df.columns.astype(str).str.strip()

    if 'Order Date' in df.columns:
        df['Order Date'] = pd.to_datetime(df['Order Date'], errors='coerce')
        df['YearMonth'] = df['Order Date'].dt.to_period('M').astype(str)
        df['YearQuarter'] = df['Order Date'].dt.to_period('Q').astype(str)
    
    numeric_cols = ['Unit Cost', 'Quantity', 'Total Cost']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            
    if 'Total Cost' in df.columns and 'Unit Cost' in df.columns and 'Quantity' in df.columns:
        df['Total Cost'] = df.apply(
            lambda r: r['Total Cost'] if r['Total Cost'] > 0 else r['Unit Cost'] * r['Quantity'], 
            axis=1
        )
    return df

@st.cache_data
def load_return_data(uploaded_file):
    if uploaded_file.name.endswith('.csv'):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)
    
    df.columns = df.columns.astype(str).str.strip()

    # 日期解析
    date_cols = ['Order Date', 'RTV Date']
    for col in date_cols:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce')

    # 【核心逻辑修正】：严格优先使用 Order Date（订单日期）计算时间维度，保证与出单表同频对齐
    target_date_col = 'Order Date' if 'Order Date' in df.columns else ('RTV Date' if 'RTV Date' in df.columns else None)
    if target_date_col:
        df['YearMonth'] = df[target_date_col].dt.to_period('M').astype(str)
        df['YearQuarter'] = df[target_date_col].dt.to_period('Q').astype(str)

    numeric_cols = ['QTY', 'UNIT COST', 'Total Cost', '10%运费', '总扣款']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    if 'Total Cost' in df.columns and 'UNIT COST' in df.columns and 'QTY' in df.columns:
        df['Total Cost'] = df.apply(lambda r: r['Total Cost'] if r['Total Cost'] > 0 else r['UNIT COST'] * r['QTY'], axis=1)
    
    if '10%运费' in df.columns and 'Total Cost' in df.columns:
        df['10%运费'] = df.apply(lambda r: r['10%运费'] if r['10%运费'] > 0 else r['Total Cost'] * 0.1, axis=1)

    if '总扣款' in df.columns and 'Total Cost' in df.columns and '10%运费' in df.columns:
        df['总扣款'] = df.apply(lambda r: r['总扣款'] if r['总扣款'] > 0 else (r['Total Cost'] + r['10%运费']), axis=1)

    return df

def calc_kpis(data_df, period_days=None):
    sales = data_df['Total Cost'].sum() if 'Total Cost' in data_df.columns else 0
    qty = data_df['Quantity'].sum() if 'Quantity' in data_df.columns else 0
    orders = data_df['PO Number'].nunique() if 'PO Number' in data_df.columns else len(data_df)
    aov = sales / orders if orders > 0 else 0
    
    if period_days and period_days > 0:
        days = period_days
    elif 'Order Date' in data_df.columns and not data_df['Order Date'].isna().all():
        days = max((data_df['Order Date'].max() - data_df['Order Date'].min()).days + 1, 1)
    else:
        days = 1
        
    daily_sales = sales / days
    daily_qty = qty / days
    
    return sales, qty, orders, aov, days, daily_sales, daily_qty

def get_sku_col(df_columns):
    for col in ['产品SKU', 'Merchant SKU', 'Vendor SKU', 'PART#', 'SKU']:
        if col in df_columns:
            return col
    return None

# =========================================================================
# 3. 侧边栏：文件上传与全局筛选
# =========================================================================
st.sidebar.header("📁 数据导入")
uploaded_sales_file = st.sidebar.file_uploader("1. 上传销售分析数据表 (CSV/Excel)", type=["csv", "xlsx"], key="sales_uploader")
uploaded_return_file = st.sidebar.file_uploader("2. 上传退货数据表 (CSV/Excel)", type=["csv", "xlsx"], key="return_uploader")
uploaded_total_orders_file = st.sidebar.file_uploader("3. 上传全量总出单表 (CSV/Excel) [选填，用于匹配 RTV]", type=["csv", "xlsx"], key="total_orders_uploader")

if uploaded_sales_file is not None:
    raw_df = load_sales_data(uploaded_sales_file)
    df = raw_df.dropna(subset=['Order Date']).copy() if 'Order Date' in raw_df.columns else raw_df.copy()
    rtv_df = load_return_data(uploaded_return_file) if uploaded_return_file is not None else None
    total_orders_df = load_sales_data(uploaded_total_orders_file) if uploaded_total_orders_file is not None else None

    st.sidebar.subheader("🔍 全局维度筛选")
    
    if '品牌' in df.columns:
        brands = ['全部'] + list(df['品牌'].dropna().unique())
        selected_brand = st.sidebar.selectbox("选择品牌", brands)
        if selected_brand != '全部':
            df = df[df['品牌'] == selected_brand]
            if rtv_df is not None and 'Brand' in rtv_df.columns:
                rtv_df = rtv_df[rtv_df['Brand'] == selected_brand]

    if '运营' in df.columns:
        operators = ['全部'] + list(df['运营'].dropna().unique())
        selected_operator = st.sidebar.selectbox("选择运营负责人", operators)
        if selected_operator != '全部':
            df = df[df['运营'] == selected_operator]

    # =========================================================================
    # 4. 看板 5 大选项卡划分
    # =========================================================================
    tab_total, tab_op, tab_sku_rank, tab_hd, tab_returns = st.tabs([
        "📊 1. 核心总销售与动销看板", 
        "👤 2. 分运营销售数据看板", 
        "🏆 3. 产品 SKU 排名与动销分析",
        "🏪 4. HD 门店 vs 个人地址占比",
        "🔄 5. 退货与扣款 (Order Date 维度精准匹配)"
    ])

    # -------------------------------------------------------------------------
    # TAB 1 - TAB 4 (保持原逻辑不变，省略以突出重点)
    # -------------------------------------------------------------------------
    with tab_total:
        st.header("📊 核心总销售与动销看板")
        if 'Order Date' in df.columns and not df['Order Date'].isna().all():
            max_date = df['Order Date'].max().date()
            min_date = df['Order Date'].min().date()

            period_option = st.radio(
                "快速切换数据周期:", 
                ["全量数据", "近 7 天 (Recent 7 Days)", "近 15 天 (Recent 15 Days)", "近 30 天 (Recent 30 Days)", "自定义日期区间"], 
                horizontal=True
            )

            if "近 7 天" in period_option:
                start_date = max_date - timedelta(days=6)
                p_days = 7
            elif "近 15 天" in period_option:
                start_date = max_date - timedelta(days=14)
                p_days = 15
            elif "近 30 天" in period_option:
                start_date = max_date - timedelta(days=29)
                p_days = 30
            elif "自定义日期区间" in period_option:
                c1, c2 = st.columns(2)
                date_range = c1.date_input("选择起始与截止日期", [min_date, max_date])
                start_date, max_date = (date_range[0], date_range[1]) if len(date_range) == 2 else (min_date, max_date)
                p_days = (max_date - start_date).days + 1
            else:
                start_date, max_date = min_date, max_date
                p_days = (max_date - start_date).days + 1

            filtered_df = df[(df['Order Date'].dt.date >= start_date) & (df['Order Date'].dt.date <= max_date)]
            curr_sales, curr_qty, curr_orders, curr_aov, curr_days, curr_daily_sales, curr_daily_qty = calc_kpis(filtered_df, p_days)

            kpi1, kpi2, kpi3, kpi4 = st.columns(4)
            kpi1.metric("💰 总销售额", f"${curr_sales:,.2f}")
            kpi2.metric("📦 总销量", f"{int(curr_qty):,} 件")
            kpi3.metric("🚀 日均销量", f"{curr_daily_qty:.1f} 件/天")
            kpi4.metric("📈 日均销售额", f"${curr_daily_sales:,.2f}")

    with tab_op:
        st.header("👤 运营人员绩效看板")
        if '运营' in df.columns:
            op_summary = df.groupby('运营').agg(
                总销售额=('Total Cost', 'sum'),
                总销量=('Quantity', 'sum')
            ).reset_index()
            st.dataframe(op_summary, use_container_width=True)

    with tab_sku_rank:
        st.header("🏆 产品 SKU 排名看板")
        sku_col = get_sku_col(df.columns)
        if sku_col:
            sku_summary = df.groupby(sku_col).agg(总销售额=('Total Cost', 'sum'), 总销量=('Quantity', 'sum')).reset_index()
            st.dataframe(sku_summary, use_container_width=True)

    with tab_hd:
        st.header("🏪 HD 门店 vs 个人地址看板")
        st.info("渠道占比计算中...")

    # -------------------------------------------------------------------------
    # TAB 5: 退货与扣款 (基于 Order Date 进行跨表对齐计算退货率)
    # -------------------------------------------------------------------------
    with tab_returns:
        st.header("🔄 退货与扣款分析 (按 Order Date 订单日期对齐)")

        if rtv_df is not None and not rtv_df.empty:
            rtv_sku_col = get_sku_col(rtv_df.columns)
            rtv_name_col = '产品名称' if '产品名称' in rtv_df.columns else rtv_sku_col

            if 'Order Date' not in rtv_df.columns or rtv_df['Order Date'].isna().all():
                st.warning("⚠️ 退货表中缺乏有效的 'Order Date' (订单日期) 列，无法按订单日期进行精准退货率对齐！")

            if not rtv_sku_col:
                st.error("⚠️ 未在退货表格中找到 SKU 列 (如 'PART#', 'SKU', '产品SKU')。")
            else:
                match_source_df = total_orders_df if total_orders_df is not None else df
                source_label = "全量总出单表" if total_orders_df is not None else "销售分析表"
                sales_sku_col = get_sku_col(match_source_df.columns)

                st.subheader("⚙️ 分析维度控制台")
                c_mode, c_info = st.columns([2, 3])
                with c_mode:
                    time_granularity = st.radio(
                        "选择分析的时间视角:",
                        ["按整体 (Overall)", "按月份 (Monthly)", "按季度 (Quarterly)"],
                        horizontal=True
                    )
                with c_info:
                    st.success(f"🎯 **精准对齐模式**：已锁定退货表中的【**Order Date**】与【**{source_label}**】进行匹配，以确保出货与退货发生在同一订单周期内。")

                # 根据订单日期分组计算
                if "按整体" in time_granularity:
                    group_cols = [rtv_sku_col]
                    sales_group_cols = [sales_sku_col] if sales_sku_col else []

                    sku_rtv_summary = rtv_df.groupby(group_cols).agg(
                        产品名称=(rtv_name_col, 'first'),
                        退货次数=('RTV Number', 'count') if 'RTV Number' in rtv_df.columns else (rtv_sku_col, 'count'),
                        退货总件数=('QTY', 'sum'),
                        退货货值=('Total Cost', 'sum'),
                        运费扣款=('10%运费', 'sum'),
                        总扣款金额=('总扣款', 'sum')
                    ).reset_index()

                    if sales_sku_col and 'Quantity' in match_source_df.columns:
                        sales_qty_df = match_source_df.groupby(sales_group_cols)['Quantity'].sum().reset_index()
                        sales_qty_df.columns = [rtv_sku_col, '总出货销量']
                        sku_rtv_summary = pd.merge(sku_rtv_summary, sales_qty_df, on=rtv_sku_col, how='left')
                    else:
                        sku_rtv_summary['总出货销量'] = 0

                elif "按月份" in time_granularity:
                    group_cols = [rtv_sku_col, 'YearMonth']
                    sales_group_cols = [sales_sku_col, 'YearMonth'] if sales_sku_col and 'YearMonth' in match_source_df.columns else []

                    sku_rtv_summary = rtv_df.groupby(group_cols).agg(
                        产品名称=(rtv_name_col, 'first'),
                        退货次数=('RTV Number', 'count') if 'RTV Number' in rtv_df.columns else (rtv_sku_col, 'count'),
                        退货总件数=('QTY', 'sum'),
                        退货货值=('Total Cost', 'sum'),
                        运费扣款=('10%运费', 'sum'),
                        总扣款金额=('总扣款', 'sum')
                    ).reset_index()

                    if sales_group_cols and 'Quantity' in match_source_df.columns:
                        sales_qty_df = match_source_df.groupby(sales_group_cols)['Quantity'].sum().reset_index()
                        sales_qty_df.columns = [rtv_sku_col, 'YearMonth', '总出货销量']
                        sku_rtv_summary = pd.merge(sku_rtv_summary, sales_qty_df, on=[rtv_sku_col, 'YearMonth'], how='left')
                    else:
                        sku_rtv_summary['总出货销量'] = 0

                else: # 按季度
                    group_cols = [rtv_sku_col, 'YearQuarter']
                    sales_group_cols = [sales_sku_col, 'YearQuarter'] if sales_sku_col and 'YearQuarter' in match_source_df.columns else []

                    sku_rtv_summary = rtv_df.groupby(group_cols).agg(
                        产品名称=(rtv_name_col, 'first'),
                        退货次数=('RTV Number', 'count') if 'RTV Number' in rtv_df.columns else (rtv_sku_col, 'count'),
                        退货总件数=('QTY', 'sum'),
                        退货货值=('Total Cost', 'sum'),
                        运费扣款=('10%运费', 'sum'),
                        总扣款金额=('总扣款', 'sum')
                    ).reset_index()

                    if sales_group_cols and 'Quantity' in match_source_df.columns:
                        sales_qty_df = match_source_df.groupby(sales_group_cols)['Quantity'].sum().reset_index()
                        sales_qty_df.columns = [rtv_sku_col, 'YearQuarter', '总出货销量']
                        sku_rtv_summary = pd.merge(sku_rtv_summary, sales_qty_df, on=[rtv_sku_col, 'YearQuarter'], how='left')
                    else:
                        sku_rtv_summary['总出货销量'] = 0

                # 计算精准退货率
                sku_rtv_summary['总出货销量'] = sku_rtv_summary['总出货销量'].fillna(0)
                sku_rtv_summary['退货率'] = sku_rtv_summary.apply(
                    lambda r: (r['退货总件数'] / r['总出货销量'] * 100) if r['总出货销量'] > 0 else 0, axis=1
                )
                sku_rtv_summary = sku_rtv_summary.sort_values('总扣款金额', ascending=False)

                st.divider()

                # 指标汇总
                rk1, rk2, rk3, rk4 = st.columns(4)
                rk1.metric("📦 筛选出的退货总件数", f"{int(sku_rtv_summary['退货总件数'].sum()):,} 件")
                rk2.metric("💵 退货货值", f"${sku_rtv_summary['退货货值'].sum():,.2f}")
                rk3.metric("🚚 运费扣款", f"${sku_rtv_summary['运费扣款'].sum():,.2f}")
                rk4.metric("💥 累计总扣款", f"${sku_rtv_summary['总扣款金额'].sum():,.2f}")

                st.divider()

                # 筛选与表格展示
                st.subheader("📋 基于 Order Date 匹配的退货率与明细")
                s1, s2 = st.columns([2, 2])
                with s1:
                    search_rtv_sku = st.text_input("🔍 搜索特定 SKU / 产品名称:", "")
                with s2:
                    if "按月份" in time_granularity and 'YearMonth' in sku_rtv_summary.columns:
                        month_filter = st.multiselect("筛选订单月份:", options=sorted(sku_rtv_summary['YearMonth'].unique()), default=sorted(sku_rtv_summary['YearMonth'].unique()))
                        sku_rtv_summary = sku_rtv_summary[sku_rtv_summary['YearMonth'].isin(month_filter)]
                    elif "按季度" in time_granularity and 'YearQuarter' in sku_rtv_summary.columns:
                        quarter_filter = st.multiselect("筛选订单季度:", options=sorted(sku_rtv_summary['YearQuarter'].unique()), default=sorted(sku_rtv_summary['YearQuarter'].unique()))
                        sku_rtv_summary = sku_rtv_summary[sku_rtv_summary['YearQuarter'].isin(quarter_filter)]

                if search_rtv_sku:
                    sku_rtv_summary = sku_rtv_summary[
                        sku_rtv_summary[rtv_sku_col].astype(str).str.contains(search_rtv_sku, case=False) |
                        sku_rtv_summary['产品名称'].astype(str).str.contains(search_rtv_sku, case=False)
                    ]

                st.dataframe(
                    sku_rtv_summary,
                    column_config={
                        "退货货值": st.column_config.NumberColumn("退货货值", format="$%.2f"),
                        "运费扣款": st.column_config.NumberColumn("运费扣款", format="$%.2f"),
                        "总扣款金额": st.column_config.NumberColumn("总扣款金额", format="$%.2f"),
                        "总出货销量": st.column_config.NumberColumn("同订单日期出货量", format="%d 件"),
                        "退货率": st.column_config.NumberColumn("订单期退货率", format="%.2f%%"),
                    },
                    use_container_width=True, hide_index=True
                )
        else:
            st.info("💡 请在左侧侧边栏上传退货数据表以开启退货分析。")
else:
    st.info("💡 请在左侧边栏上传销售数据表。")
