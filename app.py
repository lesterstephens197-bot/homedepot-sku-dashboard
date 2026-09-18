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
st.caption("集成动销分析、运营绩效、SKU 帕累托划分、渠道分析及【队列 vs 当期】双视角退货率分析")

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
        df['Order_YearMonth'] = df['Order Date'].dt.to_period('M').astype(str)
        df['Order_YearQuarter'] = df['Order Date'].dt.to_period('Q').astype(str)
    
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

    # 同时解析 Order Date 和 RTV Date
    if 'Order Date' in df.columns:
        df['Order Date'] = pd.to_datetime(df['Order Date'], errors='coerce')
        df['Order_YearMonth'] = df['Order Date'].dt.to_period('M').astype(str)
        df['Order_YearQuarter'] = df['Order Date'].dt.to_period('Q').astype(str)

    if 'RTV Date' in df.columns:
        df['RTV Date'] = pd.to_datetime(df['RTV Date'], errors='coerce')
        df['RTV_YearMonth'] = df['RTV Date'].dt.to_period('M').astype(str)
        df['RTV_YearQuarter'] = df['RTV Date'].dt.to_period('Q').astype(str)

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

def get_sku_col(df_columns):
    for col in ['产品SKU', 'Merchant SKU', 'Vendor SKU', 'PART#', 'SKU']:
        if col in df_columns:
            return col
    return None

# 计算核心退货率统计表通用逻辑
def build_rtv_analysis_table(rtv_df, sales_df, rtv_sku_col, sales_sku_col, date_type='Order', granularity='Monthly'):
    rtv_name_col = '产品名称' if '产品名称' in rtv_df.columns else rtv_sku_col
    
    # 确定聚合维度列
    if granularity == 'Overall':
        rtv_group = [rtv_sku_col]
        sales_group = [sales_sku_col]
        rtv_date_col, sales_date_col = None, None
    elif granularity == 'Monthly':
        rtv_date_col = 'Order_YearMonth' if date_type == 'Order' else 'RTV_YearMonth'
        sales_date_col = 'Order_YearMonth'
        rtv_group = [rtv_sku_col, rtv_date_col]
        sales_group = [sales_sku_col, sales_date_col]
    else: # Quarterly
        rtv_date_col = 'Order_YearQuarter' if date_type == 'Order' else 'RTV_YearQuarter'
        sales_date_col = 'Order_YearQuarter'
        rtv_group = [rtv_sku_col, rtv_date_col]
        sales_group = [sales_sku_col, sales_date_col]

    # RTV 汇总
    rtv_summary = rtv_df.groupby(rtv_group).agg(
        产品名称=(rtv_name_col, 'first'),
        退货次数=('RTV Number', 'count') if 'RTV Number' in rtv_df.columns else (rtv_sku_col, 'count'),
        退货总件数=('QTY', 'sum'),
        退货货值=('Total Cost', 'sum'),
        运费扣款=('10%运费', 'sum'),
        总扣款金额=('总扣款', 'sum')
    ).reset_index()

    # 匹配出货量
    if sales_sku_col and 'Quantity' in sales_df.columns:
        sales_qty = sales_df.groupby(sales_group)['Quantity'].sum().reset_index()
        if granularity == 'Overall':
            sales_qty.columns = [rtv_sku_col, '总出货销量']
            rtv_summary = pd.merge(rtv_summary, sales_qty, on=rtv_sku_col, how='left')
        else:
            sales_qty.columns = [rtv_sku_col, rtv_date_col, '对应期出货量']
            rtv_summary = pd.merge(rtv_summary, sales_qty, on=[rtv_sku_col, rtv_date_col], how='left')
    else:
        qty_col = '总出货销量' if granularity == 'Overall' else '对应期出货量'
        rtv_summary[qty_col] = 0

    target_qty_col = '总出货销量' if granularity == 'Overall' else '对应期出货量'
    rtv_summary[target_qty_col] = rtv_summary[target_qty_col].fillna(0)
    
    rtv_summary['退货率'] = rtv_summary.apply(
        lambda r: (r['退货总件数'] / r[target_qty_col] * 100) if r[target_qty_col] > 0 else 0, axis=1
    )
    return rtv_summary.sort_values('总扣款金额', ascending=False)

# =========================================================================
# 3. 侧边栏：文件上传
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

    # 看板 5 大选项卡
    tab_total, tab_op, tab_sku_rank, tab_hd, tab_returns = st.tabs([
        "📊 1. 核心总销售", "👤 2. 运营绩效", "🏆 3. SKU 动销排名", "🏪 4. HD 门店分析", "🔄 5. 退货与扣款 (双视角呈现)"
    ])

    # -------------------------------------------------------------------------
    # TAB 5: 退货与扣款分析 (双视角同屏对比)
    # -------------------------------------------------------------------------
    with tab_returns:
        st.header("🔄 SKU 退货与扣款综合分析看板")

        if rtv_df is not None and not rtv_df.empty:
            rtv_sku_col = get_sku_col(rtv_df.columns)
            
            if not rtv_sku_col:
                st.error("⚠️ 未在退货表格中找到 SKU 列 (如 'PART#', 'SKU', '产品SKU')。")
            else:
                match_source_df = total_orders_df if total_orders_df is not None else df
                source_label = "全量总出单表" if total_orders_df is not None else "销售分析表"
                sales_sku_col = get_sku_col(match_source_df.columns)

                # 顶部控制面板
                st.subheader("⚙️ 全局设置与时间粒度")
                c_granularity, c_info = st.columns([2, 3])
                with c_granularity:
                    granularity = st.radio(
                        "选择分析的时间跨度:",
                        ["按整体 (Overall)", "按月份 (Monthly)", "按季度 (Quarterly)"],
                        horizontal=True
                    )
                with c_info:
                    st.info(f"💡 出货数据匹配自：**{source_label}**。下方已为你并行呈现两种核心计算视角。")

                st.divider()

                # 将 2 种计算视角通过子选项卡 (Sub-tabs) 分开呈现
                sub_tab_order, sub_tab_rtv = st.tabs([
                    "🎯 视角 1：按订单日期队列 (Order Date View) - 评估真实退货率", 
                    "💵 视角 2：按退货发生日期 (RTV Date View) - 评估财务扣款"
                ])

                # -------------------------------------------------------------
                # 视角 1：按 Order Date (订单日期/队列退货率)
                # -------------------------------------------------------------
                with sub_tab_order:
                    st.markdown("### 🎯 视角 1：基于【订单日期 Order Date】计算（队列退货率）")
                    st.caption("逻辑：衡量 **某月/季发出的订单中，累计发生退货的比例**。适合产品质量评估与 SKU 真实退货率追踪。")

                    if 'Order Date' not in rtv_df.columns or rtv_df['Order Date'].isna().all():
                        st.warning("⚠️ 退货表中缺乏有效 'Order Date'，无法生成该视角下的分析数据。")
                    else:
                        g_type = 'Overall' if '按整体' in granularity else ('Monthly' if '按月份' in granularity else 'Quarterly')
                        order_rtv_summary = build_rtv_analysis_table(
                            rtv_df, match_source_df, rtv_sku_col, sales_sku_col, date_type='Order', granularity=g_type
                        )

                        # KPI 指标
                        k1, k2, k3, k4 = st.columns(4)
                        k1.metric("📦 订单期退货件数", f"{int(order_rtv_summary['退货总件数'].sum()):,} 件")
                        k2.metric("💵 退货货值", f"${order_rtv_summary['退货货值'].sum():,.2f}")
                        k3.metric("🚚 运费扣款", f"${order_rtv_summary['运费扣款'].sum():,.2f}")
                        k4.metric("💥 累计扣款", f"${order_rtv_summary['总扣款金额'].sum():,.2f}")

                        # 过滤搜索与展示
                        search_key1 = st.text_input("🔍 视角 1 - 搜索特定 SKU / 产品名称:", "", key="search1")
                        filtered_df1 = order_rtv_summary.copy()
                        if search_key1:
                            filtered_df1 = filtered_df1[
                                filtered_df1[rtv_sku_col].astype(str).str.contains(search_key1, case=False) |
                                filtered_df1['产品名称'].astype(str).str.contains(search_key1, case=False)
                            ]

                        qty_col_name = "总出货销量" if g_type == 'Overall' else "对应期出货量"
                        st.dataframe(
                            filtered_df1,
                            column_config={
                                "退货货值": st.column_config.NumberColumn("退货货值", format="$%.2f"),
                                "运费扣款": st.column_config.NumberColumn("运费扣款", format="$%.2f"),
                                "总扣款金额": st.column_config.NumberColumn("总扣款金额", format="$%.2f"),
                                qty_col_name: st.column_config.NumberColumn(qty_col_name, format="%d 件"),
                                "退货率": st.column_config.NumberColumn("队列退货率", format="%.2f%%"),
                            },
                            use_container_width=True, hide_index=True
                        )

                # -------------------------------------------------------------
                # 视角 2：按 RTV Date (退货发生日期/财务退货率)
                # -------------------------------------------------------------
                with sub_tab_rtv:
                    st.markdown("### 💵 视角 2：基于【退货日期 RTV Date】计算（当期损益率）")
                    st.caption("逻辑：衡量 **当期发生的实际退货件数 ÷ 当期发货总件数**。适合财务对账与当月损益核算。")

                    if 'RTV Date' not in rtv_df.columns or rtv_df['RTV Date'].isna().all():
                        st.warning("⚠️ 退货表中缺乏有效 'RTV Date'，无法生成该视角下的分析数据。")
                    else:
                        g_type = 'Overall' if '按整体' in granularity else ('Monthly' if '按月份' in granularity else 'Quarterly')
                        rtv_date_summary = build_rtv_analysis_table(
                            rtv_df, match_source_df, rtv_sku_col, sales_sku_col, date_type='RTV', granularity=g_type
                        )

                        # KPI 指标
                        rk1, rk2, rk3, rk4 = st.columns(4)
                        rk1.metric("📦 当期退货处理件数", f"{int(rtv_date_summary['退货总件数'].sum()):,} 件")
                        rk2.metric("💵 退货货值", f"${rtv_date_summary['退货货值'].sum():,.2f}")
                        rk3.metric("🚚 运费扣款", f"${rtv_date_summary['运费扣款'].sum():,.2f}")
                        rk4.metric("💥 实际发生总扣款", f"${rtv_date_summary['总扣款金额'].sum():,.2f}")

                        # 过滤搜索与展示
                        search_key2 = st.text_input("🔍 视角 2 - 搜索特定 SKU / 产品名称:", "", key="search2")
                        filtered_df2 = rtv_date_summary.copy()
                        if search_key2:
                            filtered_df2 = filtered_df2[
                                filtered_df2[rtv_sku_col].astype(str).str.contains(search_key2, case=False) |
                                filtered_df2['产品名称'].astype(str).str.contains(search_key2, case=False)
                            ]

                        qty_col_name = "总出货销量" if g_type == 'Overall' else "对应期出货量"
                        st.dataframe(
                            filtered_df2,
                            column_config={
                                "退货货值": st.column_config.NumberColumn("退货货值", format="$%.2f"),
                                "运费扣款": st.column_config.NumberColumn("运费扣款", format="$%.2f"),
                                "总扣款金额": st.column_config.NumberColumn("总扣款金额", format="$%.2f"),
                                qty_col_name: st.column_config.NumberColumn(qty_col_name, format="%d 件"),
                                "退货率": st.column_config.NumberColumn("当期退货率", format="%.2f%%"),
                            },
                            use_container_width=True, hide_index=True
                        )

        else:
            st.info("💡 请在左侧侧边栏上传退货数据表以开启退货看板分析。")
else:
    st.info("💡 请在左侧边栏上传销售数据表。")
