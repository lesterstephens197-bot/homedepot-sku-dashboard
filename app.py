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
st.caption("集成动销分析（日均销量/动销天数）、运营绩效、SKU 帕累托等级划分、渠道地址分析及多维度 SKU 退货率分析")

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
        # 兼容旧列名
        df['YearMonth'] = df['Order_YearMonth']
        df['YearQuarter'] = df['Order_YearQuarter']
    
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

    # 解析两个日期维度：Order Date 与 RTV Date
    if 'Order Date' in df.columns:
        df['Order Date'] = pd.to_datetime(df['Order Date'], errors='coerce')
        df['Order_YearMonth'] = df['Order Date'].dt.to_period('M').astype(str)
        df['Order_YearQuarter'] = df['Order Date'].dt.to_period('Q').astype(str)

    if 'RTV Date' in df.columns:
        df['RTV Date'] = pd.to_datetime(df['RTV Date'], errors='coerce')
        df['RTV_YearMonth'] = df['RTV Date'].dt.to_period('M').astype(str)
        df['RTV_YearQuarter'] = df['RTV Date'].dt.to_period('Q').astype(str)

    # 默认 YearMonth / YearQuarter 基于 RTV Date（无则尝试 Order Date）
    target_date_col = 'RTV Date' if 'RTV Date' in df.columns else ('Order Date' if 'Order Date' in df.columns else None)
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

# 识别 SKU 列工具函数
def get_sku_col(df_columns):
    for col in ['产品SKU', 'Merchant SKU', 'Vendor SKU', 'PART#', 'SKU']:
        if col in df_columns:
            return col
    return None

# 识别退货原因列工具函数
def get_reason_col(df_columns):
    for col in ['退货原因', 'Return Reason', 'Reason', 'RTV Reason', '原因描述', '备注']:
        if col in df_columns:
            return col
    return None

# 构建通用退货与出货对齐表函数
def build_rtv_analysis_table(rtv_df, sales_df, rtv_sku_col, sales_sku_col, date_type='Order', granularity='Monthly'):
    rtv_name_col = '产品名称' if '产品名称' in rtv_df.columns else rtv_sku_col
    
    if granularity == 'Overall':
        rtv_group = [rtv_sku_col]
        sales_group = [sales_sku_col] if sales_sku_col else []
    elif granularity == 'Monthly':
        rtv_date_col = 'Order_YearMonth' if (date_type == 'Order' and 'Order_YearMonth' in rtv_df.columns) else 'YearMonth'
        sales_date_col = 'Order_YearMonth' if 'Order_YearMonth' in sales_df.columns else 'YearMonth'
        rtv_group = [rtv_sku_col, rtv_date_col]
        sales_group = [sales_sku_col, sales_date_col] if sales_sku_col else []
    else: # Quarterly
        rtv_date_col = 'Order_YearQuarter' if (date_type == 'Order' and 'Order_YearQuarter' in rtv_df.columns) else 'YearQuarter'
        sales_date_col = 'Order_YearQuarter' if 'Order_YearQuarter' in sales_df.columns else 'YearQuarter'
        rtv_group = [rtv_sku_col, rtv_date_col]
        sales_group = [sales_sku_col, sales_date_col] if sales_sku_col else []

    rtv_summary = rtv_df.groupby(rtv_group).agg(
        产品名称=(rtv_name_col, 'first'),
        退货次数=('RTV Number', 'count') if 'RTV Number' in rtv_df.columns else (rtv_sku_col, 'count'),
        退货总件数=('QTY', 'sum'),
        退货货值=('Total Cost', 'sum'),
        运费扣款=('10%运费', 'sum'),
        总扣款金额=('总扣款', 'sum')
    ).reset_index()

    if sales_sku_col and 'Quantity' in sales_df.columns:
        sales_qty = sales_df.groupby(sales_group)['Quantity'].sum().reset_index()
        if granularity == 'Overall':
            sales_qty.columns = [rtv_sku_col, '总出货销量']
            rtv_summary = pd.merge(rtv_summary, sales_qty, on=rtv_sku_col, how='left')
        else:
            sales_qty.columns = [rtv_sku_col, rtv_group[1], '对应期出货量']
            rtv_summary = pd.merge(rtv_summary, sales_qty, on=[rtv_sku_col, rtv_group[1]], how='left')
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
        "🔄 5. 退货与扣款 (综合诊断)"
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

            # -----------------------------------------------------------------
            # 需求二新增：各品类动销 SKU 数量分布
            # -----------------------------------------------------------------
            st.divider()
            st.subheader("📦 各品类动销 SKU 数量分布统计")

            sku_c = get_sku_col(df.columns)
            name_c = '产品名称' if '产品名称' in df.columns else ('Description' if 'Description' in df.columns else sku_c)

            if sku_c and name_c:
                category_keywords = ['家用除湿机', '工业除湿机', '冷风机', '帐篷空调', '分体空调', '床垫']
                cat_stats = []
                
                for kw in category_keywords:
                    count = df[df[name_c].astype(str).str.contains(kw, case=False, na=False)][sku_c].nunique()
                    cat_stats.append({'产品分类': kw, '动销 SKU 数量': count})
                    
                matched_mask = df[name_c].astype(str).str.contains('|'.join(category_keywords), case=False, na=False)
                other_count = df[~matched_mask][sku_c].nunique()
                if other_count > 0:
                    cat_stats.append({'产品分类': '其他产品', '动销 SKU 数量': other_count})

                cat_df = pd.DataFrame(cat_stats)
                
                c_cat1, c_cat2 = st.columns([3, 2])
                with c_cat1:
                    fig_cat = px.bar(
                        cat_df, x='产品分类', y='动销 SKU 数量', 
                        text='动销 SKU 数量', color='动销 SKU 数量', 
                        color_continuous_scale='Blues',
                        title="各品类动销 SKU 数量对比"
                    )
                    st.plotly_chart(fig_cat, use_container_width=True)
                with c_cat2:
                    st.dataframe(cat_df, use_container_width=True, hide_index=True)

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
        sku_col = get_sku_col(df.columns)
        name_col = '产品名称' if '产品名称' in df.columns else 'Description'

        if sku_col:
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

            # -----------------------------------------------------------------
            # 需求三新增：加入产品排名序号
            # -----------------------------------------------------------------
            sku_rank_df.insert(0, '排名序号', range(1, len(sku_rank_df) + 1))

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
                    "排名序号": st.column_config.NumberColumn("排名序号", format="%d"),
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
    # TAB 5: 退货与扣款 (综合诊断：含 SKU 退货率排名与退货理由占比)
    # -------------------------------------------------------------------------
    with tab_returns:
        st.header("🔄 退货与扣款综合诊断看板")

        if rtv_df is not None and not rtv_df.empty:
            rtv_sku_col = get_sku_col(rtv_df.columns)
            rtv_reason_col = get_reason_col(rtv_df.columns)

            if not rtv_sku_col:
                st.error("⚠️ 未在退货表格中找到 SKU 列 (如 'PART#', 'SKU', '产品SKU')，请核对表头。")
            else:
                match_source_df = total_orders_df if total_orders_df is not None else df
                sales_sku_col = get_sku_col(match_source_df.columns)

                # 顶部 KPI 汇总卡片
                rk1, rk2, rk3, rk4 = st.columns(4)
                rk1.metric("📦 累计退货件数", f"{int(rtv_df['QTY'].sum()):,} 件")
                rk2.metric("💵 退货货值 (Total Cost)", f"${rtv_df['Total Cost'].sum():,.2f}")
                rk3.metric("🚚 10% 运费扣款", f"${rtv_df['10%运费'].sum():,.2f}")
                rk4.metric("💥 累计总扣款", f"${rtv_df['总扣款'].sum():,.2f}")

                st.divider()

                # -------------------------------------------------------------
                # 需求一新增：Tab 5 全局 SKU 专属筛选入口
                # -------------------------------------------------------------
                st.markdown("### 🔍 退货分析 SKU 专属筛选")
                unique_rtv_skus = sorted(rtv_df[rtv_sku_col].dropna().astype(str).unique())
                selected_rtv_skus = st.multiselect(
                    "选择要分析的特定产品 SKU (支持多选与搜索，留空则匹配全部 SKU):",
                    options=unique_rtv_skus,
                    default=[]
                )
                st.divider()

                # 子功能选项卡划分
                sub_tab_rank, sub_tab_reason, sub_tab_order, sub_tab_rtv = st.tabs([
                    "🏆 SKU 退货率排行榜", 
                    "🧩 退货原因/理由占比分析", 
                    "🎯 按订单日期明细 (Order Date 视角)", 
                    "💵 按退货日期明细 (RTV Date 视角)"
                ])

                # -------------------------------------------------------------
                # 模块 1：SKU 退货率与件数排行榜
                # -------------------------------------------------------------
                with sub_tab_rank:
                    st.subheader("🏆 SKU 退货率与退货件数排行榜")
                    
                    rank_summary = build_rtv_analysis_table(
                        rtv_df, match_source_df, rtv_sku_col, sales_sku_col, date_type='Order', granularity='Overall'
                    )

                    if selected_rtv_skus:
                        rank_summary = rank_summary[rank_summary[rtv_sku_col].astype(str).isin(selected_rtv_skus)]

                    min_sales_limit = st.slider("过滤低销量 SKU (设置最小出货量门槛):", min_value=0, max_value=500, value=10)
                    filtered_rank_df = rank_summary[rank_summary['总出货销量'] >= min_sales_limit]

                    col_rank1, col_rank2 = st.columns(2)
                    
                    with col_rank1:
                        st.markdown("##### 🔥 退货件数 TOP 10 SKU")
                        top_qty_df = filtered_rank_df.sort_values('退货总件数', ascending=False).head(10)
                        fig_qty = px.bar(
                            top_qty_df, 
                            x='退货总件数', 
                            y=rtv_sku_col, 
                            orientation='h',
                            text='退货总件数',
                            color='退货总件数',
                            color_continuous_scale='Reds'
                        )
                        fig_qty.update_layout(yaxis={'categoryorder': 'total ascending'})
                        st.plotly_chart(fig_qty, use_container_width=True)

                    with col_rank2:
                        st.markdown("##### ⚠️ 退货率 TOP 10 SKU (%)")
                        top_rate_df = filtered_rank_df.sort_values('退货率', ascending=False).head(10)
                        fig_rate = px.bar(
                            top_rate_df, 
                            x='退货率', 
                            y=rtv_sku_col, 
                            orientation='h',
                            text=top_rate_df['退货率'].apply(lambda x: f"{x:.1f}%"),
                            color='退货率',
                            color_continuous_scale='Oranges'
                        )
                        fig_rate.update_layout(yaxis={'categoryorder': 'total ascending'})
                        st.plotly_chart(fig_rate, use_container_width=True)

                    st.markdown("##### 📋 全量 SKU 退货排行榜")
                    st.dataframe(
                        filtered_rank_df.sort_values('退货率', ascending=False),
                        column_config={
                            "退货率": st.column_config.NumberColumn("退货率", format="%.2f%%"),
                            "退货货值": st.column_config.NumberColumn("退货货值", format="$%.2f"),
                            "总扣款金额": st.column_config.NumberColumn("总扣款金额", format="$%.2f"),
                        },
                        use_container_width=True, hide_index=True
                    )

                # -------------------------------------------------------------
                # 模块 2：退货原因/理由占比看板
                # -------------------------------------------------------------
                with sub_tab_reason:
                    st.subheader("🧩 退货原因占比与问题下钻诊断")

                    if not rtv_reason_col:
                        st.warning("⚠️ 在退货数据表中未找到退货原因列（如：'退货原因', 'Return Reason', 'Reason', '备注'）。")
                    else:
                        rtv_df_reason = rtv_df.copy()
                        if selected_rtv_skus:
                            rtv_df_reason = rtv_df_reason[rtv_df_reason[rtv_sku_col].astype(str).isin(selected_rtv_skus)]

                        rtv_df_reason[rtv_reason_col] = rtv_df_reason[rtv_reason_col].fillna("未注明原因")

                        r_col1, r_col2 = st.columns([2, 3])

                        with r_col1:
                            st.markdown("##### 📊 总体退货原因分布占比")
                            reason_summary = rtv_df_reason.groupby(rtv_reason_col).agg(
                                退货件数=('QTY', 'sum') if 'QTY' in rtv_df_reason.columns else (rtv_sku_col, 'count'),
                                关联扣款=('总扣款', 'sum') if '总扣款' in rtv_df_reason.columns else (rtv_sku_col, 'count')
                            ).reset_index().sort_values('退货件数', ascending=False)

                            fig_pie = px.pie(
                                reason_summary, 
                                names=rtv_reason_col, 
                                values='退货件数', 
                                hole=0.4
                            )
                            fig_pie.update_traces(textposition='inside', textinfo='percent+label')
                            st.plotly_chart(fig_pie, use_container_width=True)

                        with r_col2:
                            st.markdown("##### 🔍 按 SKU 钻取具体退货原因")
                            selected_sku = st.selectbox(
                                "选择特定 SKU 查看其退货主因:",
                                options=["全部 SKU"] + list(rtv_df_reason[rtv_sku_col].dropna().unique())
                            )

                            if selected_sku != "全部 SKU":
                                sku_reason_df = rtv_df_reason[rtv_df_reason[rtv_sku_col] == selected_sku]
                            else:
                                sku_reason_df = rtv_df_reason

                            sku_reason_summary = sku_reason_df.groupby([rtv_sku_col, rtv_reason_col]).agg(
                                退货件数=('QTY', 'sum') if 'QTY' in sku_reason_df.columns else (rtv_sku_col, 'count'),
                                关联扣款金额=('总扣款', 'sum') if '总扣款' in sku_reason_df.columns else (rtv_sku_col, 'count')
                            ).reset_index().sort_values('退货件数', ascending=False)

                            st.dataframe(
                                sku_reason_summary,
                                column_config={
                                    "关联扣款金额": st.column_config.NumberColumn("关联扣款金额", format="$%.2f")
                                },
                                use_container_width=True, hide_index=True
                            )

                # -------------------------------------------------------------
                # 模块 3：按 Order Date 队列明细 (解决了时间对齐问题)
                # -------------------------------------------------------------
                with sub_tab_order:
                    st.subheader("🎯 视角 1：基于【订单日期 Order Date】计算（队列退货率）")
                    st.caption("📌 该视角使用退货表里的 Order Date 进行筛选与聚合，保证同一时间段内的出货量与退货量基准完全一致。")
                    
                    g_type_ord = st.radio("时间粒度选择:", ["按整体 (Overall)", "按月份 (Monthly)", "按季度 (Quarterly)"], horizontal=True, key="ord_g")
                    gran_ord = 'Overall' if '整体' in g_type_ord else ('Monthly' if '月份' in g_type_ord else 'Quarterly')
                    
                    order_rtv_summary = build_rtv_analysis_table(
                        rtv_df, match_source_df, rtv_sku_col, sales_sku_col, date_type='Order', granularity=gran_ord
                    )

                    # 应用 SKU 筛选
                    if selected_rtv_skus:
                        order_rtv_summary = order_rtv_summary[order_rtv_summary[rtv_sku_col].astype(str).isin(selected_rtv_skus)]

                    st.dataframe(
                        order_rtv_summary,
                        column_config={
                            "退货率": st.column_config.NumberColumn("退货率", format="%.2f%%"),
                            "退货货值": st.column_config.NumberColumn("退货货值", format="$%.2f"),
                            "运费扣款": st.column_config.NumberColumn("运费扣款", format="$%.2f"),
                            "总扣款金额": st.column_config.NumberColumn("总扣款金额", format="$%.2f"),
                        },
                        use_container_width=True, hide_index=True
                    )

                # -------------------------------------------------------------
                # 模块 4：按 RTV Date 财务明细
                # -------------------------------------------------------------
                with sub_tab_rtv:
                    st.subheader("💵 视角 2：基于【退货处理日期 RTV Date】计算（当期财务损益）")
                    st.caption("📌 该视角基于退货发生的时间统计当期扣款金额与损失。")

                    g_type_rtv = st.radio("时间粒度选择:", ["按整体 (Overall)", "按月份 (Monthly)", "按季度 (Quarterly)"], horizontal=True, key="rtv_g")
                    gran_rtv = 'Overall' if '整体' in g_type_rtv else ('Monthly' if '月份' in g_type_rtv else 'Quarterly')

                    rtv_date_summary = build_rtv_analysis_table(
                        rtv_df, match_source_df, rtv_sku_col, sales_sku_col, date_type='RTV', granularity=gran_rtv
                    )

                    # 应用 SKU 筛选
                    if selected_rtv_skus:
                        rtv_date_summary = rtv_date_summary[rtv_date_summary[rtv_sku_col].astype(str).isin(selected_rtv_skus)]

                    st.dataframe(
                        rtv_date_summary,
                        column_config={
                            "退货率": st.column_config.NumberColumn("退货率", format="%.2f%%"),
                            "退货货值": st.column_config.NumberColumn("退货货值", format="$%.2f"),
                            "运费扣款": st.column_config.NumberColumn("运费扣款", format="$%.2f"),
                            "总扣款金额": st.column_config.NumberColumn("总扣款金额", format="$%.2f"),
                        },
                        use_container_width=True, hide_index=True
                    )

        else:
            st.info("💡 请在左侧侧边栏上传退货数据表以开启退货与扣款综合诊断分析。")

else:
    st.info("💡 请在左侧边栏上传 CSV 或 Excel 格式的销售数据表。")
