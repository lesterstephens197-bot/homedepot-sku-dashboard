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
st.caption("集成动销分析（日均销量/动销天数）、运营绩效、SKU 帕累托等级划分、渠道地址分析及 SKU 维度退货扣款分析")

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

    date_cols = ['RTV Date', 'Order Date']
    for col in date_cols:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce')

    if 'RTV Date' in df.columns:
        df['RTV Month'] = df['RTV Date'].dt.to_period('M').astype(str)

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

# KPI 指标通用计算函数
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

# =========================================================================
# 3. 侧边栏：文件上传与全局筛选
# =========================================================================
st.sidebar.header("📁 数据导入")
uploaded_sales_file = st.sidebar.file_uploader("1. 上传销售分析数据表 (CSV/Excel)", type=["csv", "xlsx"], key="sales_uploader")
uploaded_return_file = st.sidebar.file_uploader("2. 上传退货数据表 (CSV/Excel)", type=["csv", "xlsx"], key="return_uploader")
# 新增：独立上传全量总出单表，用于匹配 RTV 退货率
uploaded_total_orders_file = st.sidebar.file_uploader("3. 上传全量总出单表 (CSV/Excel) [选填，用于匹配 RTV]", type=["csv", "xlsx"], key="total_orders_uploader")

if uploaded_sales_file is not None:
    raw_df = load_sales_data(uploaded_sales_file)
    df = raw_df.dropna(subset=['Order Date']).copy() if 'Order Date' in raw_df.columns else raw_df.copy()
    rtv_df = load_return_data(uploaded_return_file) if uploaded_return_file is not None else None
    
    # 加载全量总出单表数据
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
        "🔄 5. 退货与扣款 (SKU 维度分析)"
    ])

    # -------------------------------------------------------------------------
    # TAB 1: 核心总销售与动销看板
    # -------------------------------------------------------------------------
    with tab_total:
        st.header("📊 核心总销售与动销看板")
        if 'Order Date' in df.columns and not df['Order Date'].isna().all():
            max_date = df['Order Date'].max().date()
            min_date = df['Order Date'].min().date()

            st.subheader("⏱️ 时间视角选择")
            period_option = st.radio(
                "快速切换数据周期:", 
                ["全量数据", "近 7 天 (Recent 7 Days)", "近 15 天 (Recent 15 Days)", "近 30 天 (Recent 30 Days)", "自定义日期区间"], 
                horizontal=True
            )

            if "近 7 天" in period_option:
                start_date = max_date - timedelta(days=6)
                prev_start_date = start_date - timedelta(days=7)
                prev_end_date = start_date - timedelta(days=1)
                curr_label = f"近 7 天 ({start_date} 至 {max_date})"
                p_days = 7
            elif "近 15 天" in period_option:
                start_date = max_date - timedelta(days=14)
                prev_start_date = start_date - timedelta(days=15)
                prev_end_date = start_date - timedelta(days=1)
                curr_label = f"近 15 天 ({start_date} 至 {max_date})"
                p_days = 15
            elif "近 30 天" in period_option:
                start_date = max_date - timedelta(days=29)
                prev_start_date = start_date - timedelta(days=30)
                prev_end_date = start_date - timedelta(days=1)
                curr_label = f"近 30 天 ({start_date} 至 {max_date})"
                p_days = 30
            elif "自定义日期区间" in period_option:
                c1, c2 = st.columns(2)
                date_range = c1.date_input("选择起始与截止日期", [min_date, max_date])
                if len(date_range) == 2:
                    start_date, max_date = date_range[0], date_range[1]
                else:
                    start_date, max_date = min_date, max_date
                prev_start_date, prev_end_date = None, None
                curr_label = f"自定义区间 ({start_date} 至 {max_date})"
                p_days = (max_date - start_date).days + 1
            else:
                start_date, max_date = min_date, max_date
                prev_start_date, prev_end_date = None, None
                curr_label = f"全量数据区间 ({start_date} 至 {max_date})"
                p_days = (max_date - start_date).days + 1

            filtered_df = df[(df['Order Date'].dt.date >= start_date) & (df['Order Date'].dt.date <= max_date)]
            prev_df = df[(df['Order Date'].dt.date >= prev_start_date) & (df['Order Date'].dt.date <= prev_end_date)] if prev_start_date else pd.DataFrame()

            curr_sales, curr_qty, curr_orders, curr_aov, curr_days, curr_daily_sales, curr_daily_qty = calc_kpis(filtered_df, p_days)
            prev_sales, prev_qty, prev_orders, prev_aov, prev_days, prev_daily_sales, prev_daily_qty = calc_kpis(prev_df, p_days)

            sales_delta = f"{((curr_sales - prev_sales)/prev_sales*100):+.1f}% 环比" if prev_sales > 0 else None
            qty_delta = f"{((curr_qty - prev_qty)/prev_qty*100):+.1f}% 环比" if prev_qty > 0 else None
            d_sales_delta = f"{((curr_daily_sales - prev_daily_sales)/prev_daily_sales*100):+.1f}% 环比" if prev_daily_sales > 0 else None
            d_qty_delta = f"{((curr_daily_qty - prev_daily_qty)/prev_daily_qty*100):+.1f}% 环比" if prev_daily_qty > 0 else None

            st.caption(f"当前视图：**{curr_label}** | 统计动销天数：**{curr_days} 天**")

            kpi1, kpi2, kpi3, kpi4 = st.columns(4)
            kpi1.metric("💰 总销售额 (Total Sales)", f"${curr_sales:,.2f}", delta=sales_delta)
            kpi2.metric("📦 总销量 (Total Qty)", f"{int(curr_qty):,} 件", delta=qty_delta)
            kpi3.metric("🚀 日均销量 (Daily Velocity)", f"{curr_daily_qty:.1f} 件/天", delta=d_qty_delta)
            kpi4.metric("📈 日均销售额 (Daily Revenue)", f"${curr_daily_sales:,.2f}", delta=d_sales_delta)

            st.divider()

            st.subheader("⚔️ 近 7 天 vs 近 15 天 动销与对比")
            d7_start = max_date - timedelta(days=6)
            d15_start = max_date - timedelta(days=14)

            df_7 = df[(df['Order Date'].dt.date >= d7_start) & (df['Order Date'].dt.date <= max_date)]
            df_15 = df[(df['Order Date'].dt.date >= d15_start) & (df['Order Date'].dt.date <= max_date)]

            s7, q7, o7, a7, d7, ds7, dq7 = calc_kpis(df_7, 7)
            s15, q15, o15, a15, d15, ds15, dq15 = calc_kpis(df_15, 15)

            compare_table = pd.DataFrame({
                "指标维度": ["总销售额 ($)", "总销量 (件)", "日均销量 (件/天)", "日均销售额 ($)", "平均客单价 ($)", "总订单量 (单)"],
                "近 7 天": [f"${s7:,.2f}", f"{int(q7):,}", f"{dq7:.1f}", f"${ds7:,.2f}", f"${a7:,.2f}", f"{o7:,}"],
                "近 15 天": [f"${s15:,.2f}", f"{int(q15):,}", f"{dq15:.1f}", f"${ds15:,.2f}", f"${a15:,.2f}", f"{o15:,}"]
            })
            st.table(compare_table)

            st.divider()

            st.subheader("📈 销售额与出货量走势图")
            trend_type = st.radio("选择时间粒度:", ["按日 (Daily)", "按周 (Weekly)", "按月 (Monthly)"], horizontal=True)
            rule = 'D' if '按日' in trend_type else ('W' if '按周' in trend_type else 'ME')
            
            daily_df = filtered_df.set_index('Order Date').resample(rule).agg({
                'Total Cost': 'sum',
                'Quantity': 'sum',
                'PO Number': 'nunique'
            }).reset_index()

            fig_trend = px.line(
                daily_df, x='Order Date', y=['Total Cost', 'Quantity'], 
                title="所选区间内的销售额与销量走势",
                labels={'value': '数值', 'Order Date': '日期', 'variable': '指标'},
                markers=True
            )
            st.plotly_chart(fig_trend, use_container_width=True)

    # -------------------------------------------------------------------------
    # TAB 2: 分运营销售数据看板
    # -------------------------------------------------------------------------
    with tab_op:
        st.header("👤 运营人员绩效与销售数据分析看板")
        if '运营' in df.columns:
            op_summary = df.groupby('运营').agg(
                总销售额=('Total Cost', 'sum'),
                总销量=('Quantity', 'sum'),
                总订单量=('PO Number', 'nunique') if 'PO Number' in df.columns else ('运营', 'count'),
            ).reset_index()

            total_sales_all = df['Total Cost'].sum() if 'Total Cost' in df.columns else 1
            op_summary['平均客单价(AOV)'] = (op_summary['总销售额'] / op_summary['总订单量']).round(2)
            op_summary['销售额占比'] = (op_summary['总销售额'] / total_sales_all * 100).round(2)
            op_summary = op_summary.sort_values(by='总销售额', ascending=False)

            c_op1, c_op2 = st.columns([3, 2])
            with c_op1:
                st.subheader("📊 各运营人员总销售额排名")
                fig_op_bar = px.bar(
                    op_summary, x='运营', y='总销售额',
                    color='总销量', text_auto='.2s',
                    title="运营人员销售额与销量对比"
                )
                st.plotly_chart(fig_op_bar, use_container_width=True)

            with c_op2:
                st.subheader("🍩 运营销售额贡献占比")
                fig_op_pie = px.pie(
                    op_summary, names='运营', values='总销售额',
                    title="运营人员业绩占比图", hole=0.4
                )
                st.plotly_chart(fig_op_pie, use_container_width=True)

            st.divider()
            st.subheader("📋 运营业绩数据明细表")
            st.dataframe(
                op_summary,
                column_config={
                    "总销售额": st.column_config.NumberColumn("总销售额", format="$%.2f"),
                    "平均客单价(AOV)": st.column_config.NumberColumn("平均客单价(AOV)", format="$%.2f"),
                    "销售额占比": st.column_config.NumberColumn("销售额占比", format="%.2f%%"),
                },
                use_container_width=True, hide_index=True
            )

    # -------------------------------------------------------------------------
    # TAB 3: 产品 SKU 排名与动销分析
    # -------------------------------------------------------------------------
    with tab_sku_rank:
        st.header("🏆 产品 SKU 综合排名与动销深度分析看板")
        sku_col = '产品SKU' if '产品SKU' in df.columns else ('Merchant SKU' if 'Merchant SKU' in df.columns else 'Vendor SKU')
        name_col = '产品名称' if '产品名称' in df.columns else 'Description'

        if sku_col in df.columns:
            total_days_range = max((df['Order Date'].max() - df['Order Date'].min()).days + 1, 1) if 'Order Date' in df.columns else 1

            sku_rank_df = df.groupby(sku_col).agg(
                产品名称=(name_col, 'first') if name_col in df.columns else (sku_col, 'first'),
                品牌=('品牌', 'first') if '品牌' in df.columns else (sku_col, 'first'),
                运营=('运营', 'first') if '运营' in df.columns else (sku_col, 'first'),
                总销售额=('Total Cost', 'sum'),
                总销量=('Quantity', 'sum'),
                总订单数=('PO Number', 'nunique') if 'PO Number' in df.columns else (sku_col, 'count'),
                有销售天数=('Order Date', lambda x: x.dt.date.nunique()) if 'Order Date' in df.columns else (sku_col, 'count')
            ).reset_index()

            sku_rank_df['日均销量(件/天)'] = (sku_rank_df['总销量'] / total_days_range).round(2)
            sku_rank_df = sku_rank_df.sort_values(by='总销售额', ascending=False).reset_index(drop=True)

            total_sku_sales = sku_rank_df['总销售额'].sum()
            sku_rank_df['销售额占比'] = (sku_rank_df['总销售额'] / total_sku_sales) if total_sku_sales > 0 else 0
            sku_rank_df['累计销售额占比'] = sku_rank_df['销售额占比'].cumsum()

            def assign_grade(cum_pct):
                if cum_pct <= 0.80:
                    return 'S/A 级 (核心爆款)'
                elif cum_pct <= 0.95:
                    return 'B 级 (腰部主力)'
                else:
                    return 'C 级 (尾部滞销)'

            sku_rank_df['SKU 等级'] = sku_rank_df['累计销售额占比'].apply(assign_grade)

            st.dataframe(
                sku_rank_df,
                column_config={
                    "总销售额": st.column_config.NumberColumn("总销售额", format="$%.2f"),
                    "日均销量(件/天)": st.column_config.NumberColumn("日均销量(件/天)", format="%.2f"),
                    "销售额占比": st.column_config.NumberColumn("销售额占比", format="%.2f%%"),
                    "累计销售额占比": st.column_config.ProgressColumn("累计销售额占比", format="%.1f%%", min_value=0, max_value=1),
                },
                use_container_width=True, hide_index=True
            )

    # -------------------------------------------------------------------------
    # TAB 4: HD 门店 vs 个人地址占比分析
    # -------------------------------------------------------------------------
    with tab_hd:
        st.header("🏪 HD 门店 vs 个人地址 渠道分析看板")

        addr1 = df['ShipTo Address1'].astype(str) if 'ShipTo Address1' in df.columns else pd.Series(['']*len(df))
        addr2 = df['ShipTo Address2'].astype(str) if 'ShipTo Address2' in df.columns else pd.Series(['']*len(df))

        keyword_pattern = r'c/o\s*thd\s*ship\s*to\s*store'
        is_hd_store = addr1.str.contains(keyword_pattern, case=False, regex=True) | \
                      addr2.str.contains(keyword_pattern, case=False, regex=True)

        df['地址类型'] = df.apply(lambda r: 'HD门店 (Ship to Store)' if is_hd_store.loc[r.name] else '个人地址 (Home Delivery)', axis=1)

        hd_df = df[df['地址类型'] == 'HD门店 (Ship to Store)']
        home_df = df[df['地址类型'] == '个人地址 (Home Delivery)']

        tot_orders_all = df['PO Number'].nunique() if 'PO Number' in df.columns else len(df)
        tot_sales_all = df['Total Cost'].sum() if 'Total Cost' in df.columns else 1

        hd_orders = hd_df['PO Number'].nunique() if 'PO Number' in hd_df.columns else len(hd_df)
        hd_sales = hd_df['Total Cost'].sum() if 'Total Cost' in hd_df.columns else 0

        home_orders = home_df['PO Number'].nunique() if 'PO Number' in home_df.columns else len(home_df)
        home_sales = home_df['Total Cost'].sum() if 'Total Cost' in home_df.columns else 0

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("HD 门店订单量占比", f"{(hd_orders/tot_orders_all*100):.2f}%", f"{hd_orders:,} 单")
        k2.metric("HD 门店销售额占比", f"{(hd_sales/tot_sales_all*100):.2f}%", f"${hd_sales:,.2f}")
        k3.metric("个人地址订单量占比", f"{(home_orders/tot_orders_all*100):.2f}%", f"{home_orders:,} 单")
        k4.metric("个人地址销售额占比", f"{(home_sales/tot_sales_all*100):.2f}%", f"${home_sales:,.2f}")

    # -------------------------------------------------------------------------
    # TAB 5: 退货与扣款 (适配上传的总出单表表头进行自动匹配)
    # -------------------------------------------------------------------------
    with tab_returns:
        st.header("🔄 退货与扣款 (产品 SKU 深度分析看板)")
        
        if rtv_df is not None and not rtv_df.empty:
            rtv_sku_col = '产品SKU' if '产品SKU' in rtv_df.columns else ('PART#' if 'PART#' in rtv_df.columns else ('SKU' if 'SKU' in rtv_df.columns else None))
            rtv_name_col = '产品名称' if '产品名称' in rtv_df.columns else rtv_sku_col

            if not rtv_sku_col:
                st.error("⚠️ 未在退货表格中找到 SKU 列 (如 'PART#', 'SKU', '产品SKU')，请核对表头。")
            else:
                total_rtv_qty = rtv_df['QTY'].sum()
                total_rtv_cost = rtv_df['Total Cost'].sum()
                total_shipping_fee = rtv_df['10%运费'].sum()
                total_deduction = rtv_df['总扣款'].sum()

                rk1, rk2, rk3, rk4 = st.columns(4)
                rk1.metric("📦 累计退货件数", f"{int(total_rtv_qty):,} 件")
                rk2.metric("💵 退货货值 (Total Cost)", f"${total_rtv_cost:,.2f}")
                rk3.metric("🚚 10% 运费扣款", f"${total_shipping_fee:,.2f}")
                rk4.metric("💥 累计总扣款 (Total Charge)", f"${total_deduction:,.2f}")

                st.divider()

                # 判断使用“独立总出单表”还是“销售主表”
                if total_orders_df is not None:
                    match_source_df = total_orders_df
                    st.success("✅ 已检测到独立的【全量总出单表】，正使用其匹配 SKU 出货总量。")
                else:
                    match_source_df = df
                    st.info("💡 未单独上传【全量总出单表】，当前默认使用上传的【销售分析表】匹配 SKU 出货总量。")

                sku_rtv_summary = rtv_df.groupby(rtv_sku_col).agg(
                    产品名称=(rtv_name_col, 'first'),
                    退货次数=('RTV Number', 'count') if 'RTV Number' in rtv_df.columns else (rtv_sku_col, 'count'),
                    退货总件数=('QTY', 'sum'),
                    退货货值=('Total Cost', 'sum'),
                    运费扣款=('10%运费', 'sum'),
                    总扣款金额=('总扣款', 'sum'),
                    主要退货原因=('Reason', lambda x: x.mode()[0] if not x.empty else '未知') if 'Reason' in rtv_df.columns else (rtv_sku_col, lambda x: '未知')
                ).reset_index()

                # 根据指定的表头（产品SKU -> Merchant SKU -> Vendor SKU）识别匹配列
                target_sales_sku_col = None
                for col_name in ['产品SKU', 'Merchant SKU', 'Vendor SKU']:
                    if col_name in match_source_df.columns:
                        target_sales_sku_col = col_name
                        break

                if target_sales_sku_col and 'Quantity' in match_source_df.columns:
                    sales_qty_df = match_source_df.groupby(target_sales_sku_col)['Quantity'].sum().reset_index()
                    sales_qty_df.columns = [rtv_sku_col, '总出货销量']
                    
                    # 关联计算退货率
                    sku_rtv_summary = pd.merge(sku_rtv_summary, sales_qty_df, on=rtv_sku_col, how='left')
                    sku_rtv_summary['总出货销量'] = sku_rtv_summary['总出货销量'].fillna(0)
                else:
                    sku_rtv_summary['总出货销量'] = 0

                sku_rtv_summary['退货率'] = sku_rtv_summary.apply(
                    lambda r: (r['退货总件数'] / r['总出货销量'] * 100) if r['总出货销量'] > 0 else 0, axis=1
                )

                sku_rtv_summary = sku_rtv_summary.sort_values('总扣款金额', ascending=False)

                st.subheader("🏷️ 全量 SKU 退货、总出货量与退货率明细")
                
                search_rtv_sku = st.text_input("🔍 快速搜索退货 SKU 或产品名称:", "")
                filtered_rtv_summary = sku_rtv_summary.copy()
                
                if search_rtv_sku:
                    filtered_rtv_summary = filtered_rtv_summary[
                        filtered_rtv_summary[rtv_sku_col].astype(str).str.contains(search_rtv_sku, case=False) |
                        filtered_rtv_summary['产品名称'].astype(str).str.contains(search_rtv_sku, case=False)
                    ]

                st.dataframe(
                    filtered_rtv_summary,
                    column_config={
                        "退货货值": st.column_config.NumberColumn("退货货值", format="$%.2f"),
                        "运费扣款": st.column_config.NumberColumn("运费扣款", format="$%.2f"),
                        "总扣款金额": st.column_config.NumberColumn("总扣款金额", format="$%.2f"),
                        "总出货销量": st.column_config.NumberColumn("总出货销量", format="%d 件"),
                        "退货率": st.column_config.NumberColumn("退货率", format="%.2f%%"),
                    },
                    use_container_width=True, hide_index=True
                )

                st.divider()

                c_chart1, c_chart2 = st.columns(2)
                with c_chart1:
                    st.subheader("🔥 TOP 10 扣款金额最高 SKU")
                    fig_top_deduct = px.bar(
                        sku_rtv_summary.head(10),
                        x=rtv_sku_col, y='总扣款金额',
                        color='退货总件数', text_auto='.2s',
                        title="总扣款金额 TOP 10 SKU",
                        labels={'总扣款金额': '扣款金额 ($)', rtv_sku_col: 'SKU'}
                    )
                    st.plotly_chart(fig_top_deduct, use_container_width=True)

                with c_chart2:
                    st.subheader("⚠️ TOP 10 退货率最高 SKU")
                    high_rate_skus = sku_rtv_summary[sku_rtv_summary['总出货销量'] > 0].sort_values('退货率', ascending=False).head(10)
                    if not high_rate_skus.empty:
                        fig_top_rate = px.bar(
                            high_rate_skus,
                            x=rtv_sku_col, y='退货率',
                            color='退货总件数', text_auto='.2f',
                            title="退货率 TOP 10 SKU (%)",
                            labels={'退货率': '退货率 (%)', rtv_sku_col: 'SKU'}
                        )
                        st.plotly_chart(fig_top_rate, use_container_width=True)
                    else:
                        st.warning("暂无包含总销量的数据，请上传总出单表以渲染退货率排行榜。")

        else:
            st.info("💡 请在左侧侧边栏上传退货数据表以开启 SKU 深度退货分析。")

else:
    st.info("💡 请在左侧边栏上传 CSV 或 Excel 格式的销售数据表。")
