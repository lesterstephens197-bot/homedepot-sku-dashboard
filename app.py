import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import calendar

# 页面基础配置
st.set_page_config(
    page_title="Home Depot 销售与广告综合决策看板",
    page_icon="📊",
    layout="wide"
)

# -------------------------------------------------------------------------
# 侧边栏：顶部大模块选择 (功能看板导航)
# -------------------------------------------------------------------------
st.sidebar.title("📌 功能看板导航")
module = st.sidebar.radio(
    "请选择分析模块",
    [
        "📊 销售与品类管理决策看板", 
        "🗓️ 月度环比与多维度对比看板",
        "📢 SPA 广告绩效诊断与运营看板",
        "🎯 下月销售目标与 SKU 销量拆解看板"
    ]
)

st.sidebar.markdown("---")

# =========================================================================
# 模块一：销售与品类管理决策看板 (Sales & Management Dashboard)
# =========================================================================
if module == "📊 销售与品类管理决策看板":
    st.title("📊 Home Depot 销售绩效与品类管理决策看板")
    st.caption("聚焦管理与运营决策：大盘走势、帕累托 ABC 爆款诊断、全美物流布局与动销效率分析")
    st.markdown("---")

    st.sidebar.header("⚙️ 1. 销售数据上传")
    uploaded_sales_file = st.sidebar.file_uploader("上传 Home Depot 销售报表 (CSV/Excel)", type=["csv", "xlsx"], key="sales_uploader")

    if not uploaded_sales_file:
        st.info("👋 请在侧边栏上传 Excel 或 CSV 格式的 Home Depot 销售报表。")
    else:
        try:
            if uploaded_sales_file.name.endswith('.csv'):
                df_sales = pd.read_csv(uploaded_sales_file)
            else:
                df_sales = pd.read_excel(uploaded_sales_file)
        except Exception as e:
            st.error(f"读取文件失败，请检查文件格式: {e}")
            st.stop()

        df_sales.columns = df_sales.columns.str.strip()

        date_col = next((c for c in df_sales.columns if c in ['日期', 'Date', 'sales_date']), None)
        sales_col = next((c for c in df_sales.columns if c in ['销量', 'Units Sold', 'Units', 'Quantity']), None)
        cost_col = next((c for c in df_sales.columns if c in ['Total Cost', 'Cost', '金额', '总金额']), None)
        category_col = next((c for c in df_sales.columns if c in ['产品名称', 'Category', '品类', '品类名称']), None)
        state_col = next((c for c in df_sales.columns if c in ['ShipTo State', 'State', '州', '省份']), None)

        sku_fields_available = [col for col in ['产品SKU', 'SKU', 'Merchant SKU', 'Vendor SKU', 'OMS ID'] if col in df_sales.columns]

        if not date_col or not sales_col or not sku_fields_available:
            st.error(f"解析失败！未能在表格中识别到必需列（日期、销量或产品SKU列）。当前识别到的表头列为: {list(df_sales.columns)}")
            st.stop()

        df_sales['Clean_Date'] = pd.to_datetime(df_sales[date_col])
        df_sales['Clean_Units'] = pd.to_numeric(df_sales[sales_col], errors='coerce').fillna(0)
        df_sales['Clean_Cost'] = pd.to_numeric(df_sales[cost_col], errors='coerce').fillna(0) if cost_col else 0
        df_sales['Clean_Category'] = df_sales[category_col].astype(str).str.strip().replace({'nan': '未分类', 'None': '未分类', '': '未分类'}) if category_col else '未分类'
        if state_col:
            df_sales['Clean_State'] = df_sales[state_col].astype(str).str.strip().str.upper().replace({'NAN': '未知', 'NONE': '未知', '': '未知'})

        primary_sku_col = sku_fields_available[0]

        min_d = df_sales['Clean_Date'].min().date()
        max_d = df_sales['Clean_Date'].max().date()

        st.sidebar.markdown("---")
        st.sidebar.markdown("### 🗓️ 2. 时间范围筛选")
        date_range = st.sidebar.date_input("分析时间范围", [min_d, max_d], min_value=min_d, max_value=max_d)

        start_date = date_range[0] if len(date_range) >= 1 else min_d
        end_date = date_range[1] if len(date_range) == 2 else max_d

        time_mask = (df_sales['Clean_Date'].dt.date >= start_date) & (df_sales['Clean_Date'].dt.date <= end_date)
        filtered_sales = df_sales[time_mask]

        st.subheader("📌 1. 渠道总体经营成果 (Executive Performance)")
        total_units = filtered_sales['Clean_Units'].sum()
        total_cost = filtered_sales['Clean_Cost'].sum()
        total_skus = filtered_sales[primary_sku_col].nunique()
        avg_order_value = total_cost / total_units if total_units > 0 else 0

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("销售总金额 (Total Cost)", f"${total_cost:,.2f}")
        c2.metric("销售总出货量 (Units)", f"{int(total_units):,} 件")
        c3.metric("均价 / 件单价 (ASP)", f"${avg_order_value:.2f}")
        c4.metric("活跃动销 SKU 数", f"{total_skus} 款")

        st.markdown("---")

        st.subheader("🏆 2. 产品结构 ABC 帕累托诊断与 SKU 动销效率全景表")
        active_sales = filtered_sales[filtered_sales['Clean_Units'] > 0]

        sku_summary = filtered_sales.groupby(primary_sku_col).agg({
            'Clean_Cost': 'sum',
            'Clean_Units': 'sum',
        }).reset_index()

        active_metrics = active_sales.groupby(primary_sku_col).agg({
            'Clean_Date': ['nunique', 'min', 'max']
        }).reset_index()
        active_metrics.columns = [primary_sku_col, 'Active_Days', 'First_Sale', 'Last_Sale']

        sku_summary = pd.merge(sku_summary, active_metrics, on=primary_sku_col, how='left')
        sku_summary['Active_Days'] = sku_summary['Active_Days'].fillna(0)

        sku_summary['Active_Daily_Avg'] = sku_summary.apply(
            lambda row: row['Clean_Units'] / row['Active_Days'] if row['Active_Days'] > 0 else 0, axis=1
        )

        sku_summary = sku_summary.sort_values(by='Clean_Cost', ascending=False).reset_index(drop=True)

        sku_summary['Cumulative_Cost'] = sku_summary['Clean_Cost'].cumsum()
        sku_summary['Cost_Share (%)'] = (sku_summary['Clean_Cost'] / total_cost) * 100 if total_cost > 0 else 0
        sku_summary['Cumulative_Share (%)'] = (sku_summary['Cumulative_Cost'] / total_cost) * 100 if total_cost > 0 else 0

        def assign_abc(pct):
            if pct <= 80: return 'A 类 (核心爆款)'
            elif pct <= 95: return 'B 类 (腰部主力)'
            else: return 'C 类 (尾部/滞销)'

        sku_summary['ABC_Class'] = sku_summary['Cumulative_Share (%)'].apply(assign_abc)
        abc_counts = sku_summary['ABC_Class'].value_counts()

        col_abc1, col_abc2 = st.columns([1, 1])
        with col_abc1:
            fig_abc = px.pie(
                sku_summary, values='Clean_Cost', names='ABC_Class', title="ABC 分级销售额占比构成", hole=0.4,
                color='ABC_Class', color_discrete_map={'A 类 (核心爆款)': '#10B981', 'B 类 (腰部主力)': '#F59E0B', 'C 类 (尾部/滞销)': '#EF4444'}
            )
            fig_abc.update_traces(textinfo='percent+label')
            st.plotly_chart(fig_abc, use_container_width=True)

        with col_abc2:
            st.markdown("### 💡 帕累托品类优化诊断建议")
            a_count = abc_counts.get('A 类 (核心爆款)', 0)
            b_count = abc_counts.get('B 类 (腰部主力)', 0)
            c_count = abc_counts.get('C 类 (尾部/滞销)', 0)
            st.success(f"🟢 **A 类核心爆款 ({a_count} 款 SKU)**：贡献全盘 **80%** 营收！重点监控库存与供应链。")
            st.warning(f"🟡 **B 类腰部潜力 ({b_count} 款 SKU)**：贡献 **15%** 营收，可适当增加广告投放。")
            st.error(f"🔴 **C 类尾部滞销 ({c_count} 款 SKU)**：仅贡献 **5%** 营收，评估是否清仓。")

        st.markdown("### 📋 各分类 SKU 详细名单与动销效率列表")
        df_a = sku_summary[sku_summary['ABC_Class'] == 'A 类 (核心爆款)'].copy()
        df_b = sku_summary[sku_summary['ABC_Class'] == 'B 类 (腰部主力)'].copy()
        df_c = sku_summary[sku_summary['ABC_Class'] == 'C 类 (尾部/滞销)'].copy()

        def render_sku_table(df_subset):
            display_df = df_subset.rename(columns={
                primary_sku_col: '产品 SKU', 'Clean_Cost': '销售总额 ($)', 'Clean_Units': '销售总量 (件)',
                'Cost_Share (%)': '销售额占比 (%)', 'Cumulative_Share (%)': '累计占比 (%)',
                'Active_Days': '可动销天数 (天)', 'Active_Daily_Avg': '动销日均销量 (件/天)',
                'First_Sale': '首次出单日期', 'Last_Sale': '最近出单日期'
            }).copy()
            display_df['首次出单日期'] = pd.to_datetime(display_df['首次出单日期']).dt.strftime('%Y-%m-%d').fillna('无出单')
            display_df['最近出单日期'] = pd.to_datetime(display_df['最近出单日期']).dt.strftime('%Y-%m-%d').fillna('无出单')

            st.dataframe(
                display_df[[
                    '产品 SKU', '销售总额 ($)', '销售总量 (件)', '可动销天数 (天)', 
                    '动销日均销量 (件/天)', '销售额占比 (%)', '累计占比 (%)', '首次出单日期', '最近出单日期'
                ]].style.format({
                    '销售总额 ($)': '${:,.2f}', '销售总量 (件)': '{:,.0f}', '可动销天数 (天)': '{:,.0f} 天',
                    '动销日均销量 (件/天)': '{:,.1f} 件/天', '销售额占比 (%)': '{:.2f}%', '累计占比 (%)': '{:.2f}%'
                }), use_container_width=True
            )

        tab_a, tab_b, tab_c, tab_all = st.tabs([f"🟢 A 类 ({len(df_a)})", f"🟡 B 类 ({len(df_b)})", f"🔴 C 类 ({len(df_c)})", f"📊 全量 ({len(sku_summary)})"])
        with tab_a: render_sku_table(df_a)
        with tab_b: render_sku_table(df_b)
        with tab_c: render_sku_table(df_c)
        with tab_all: render_sku_table(sku_summary)

# =========================================================================
# 模块二：月度环比与多维度对比看板 (含日均销量对比)
# =========================================================================
elif module == "🗓️ 月度环比与多维度对比看板":
    st.title("🗓️ 月度环比与多维度对比分析看板")
    st.caption("聚焦月度业绩演变：月度大盘趋势、日均销量 (Velocity) 动销速率对比、双月 SKU 增减与品类结构")
    st.markdown("---")

    st.sidebar.header("⚙️ 1. 销售数据上传")
    uploaded_sales_file = st.sidebar.file_uploader("上传销售报表 (CSV/Excel)", type=["csv", "xlsx"], key="month_comp_uploader")

    if not uploaded_sales_file:
        st.info("👋 请先在侧边栏上传跨月销售报表（CSV/Excel）。看板将自动解析数据中的月份信息进行对比分析。")
    else:
        try:
            if uploaded_sales_file.name.endswith('.csv'): df_sales = pd.read_csv(uploaded_sales_file)
            else: df_sales = pd.read_excel(uploaded_sales_file)
        except Exception as e:
            st.error(f"读取文件失败: {e}"); st.stop()

        df_sales.columns = df_sales.columns.str.strip()

        date_col = next((c for c in df_sales.columns if c in ['日期', 'Date', 'sales_date']), None)
        sales_col = next((c for c in df_sales.columns if c in ['销量', 'Units Sold', 'Units', 'Quantity']), None)
        cost_col = next((c for c in df_sales.columns if c in ['Total Cost', 'Cost', '金额', '总金额']), None)
        category_col = next((c for c in df_sales.columns if c in ['产品名称', 'Category', '品类', '品类名称']), None)
        sku_col = next((c for c in ['产品SKU', 'SKU', 'Merchant SKU', 'Vendor SKU', 'OMS ID'] if c in df_sales.columns), None)

        if not date_col or not sales_col or not sku_col:
            st.error("数据表缺失关键列（日期、销量或 SKU），请检查文件！")
            st.stop()

        df_sales['Clean_Date'] = pd.to_datetime(df_sales[date_col])
        df_sales['Clean_Units'] = pd.to_numeric(df_sales[sales_col], errors='coerce').fillna(0)
        df_sales['Clean_Cost'] = pd.to_numeric(df_sales[cost_col], errors='coerce').fillna(0) if cost_col else 0
        df_sales['Clean_Category'] = df_sales[category_col].astype(str).str.strip().replace({'nan': '未分类', 'None': '未分类', '': '未分类'}) if category_col else '未分类'
        df_sales['Year_Month'] = df_sales['Clean_Date'].dt.to_period('M').astype(str)

        available_months = sorted(df_sales['Year_Month'].unique())

        if len(available_months) < 1:
            st.warning("数据表中未发现有效的时间月份记录。")
            st.stop()

        # 计算每月自然天数与实际有销售天数
        def get_month_days(ym_str):
            y, m = map(int, ym_str.split('-'))
            return calendar.monthrange(y, m)[1]

        # -----------------------------------------------------------------
        # 1. 大盘月度总出货与【日均销量】趋势对比
        # -----------------------------------------------------------------
        st.subheader("📈 1. 整体月度【日均销量 (Units/Day)】与销售额趋势")

        monthly_summary = df_sales.groupby('Year_Month').agg(
            Clean_Cost=('Clean_Cost', 'sum'),
            Clean_Units=('Clean_Units', 'sum'),
            Active_Days=('Clean_Date', 'nunique'),
            Active_SKUs=(sku_col, 'nunique')
        ).reset_index()

        monthly_summary['Calendar_Days'] = monthly_summary['Year_Month'].apply(get_month_days)
        monthly_summary['Daily_Avg_Units (Calendar)'] = monthly_summary['Clean_Units'] / monthly_summary['Calendar_Days']
        monthly_summary['Daily_Avg_Units (Active)'] = monthly_summary['Clean_Units'] / monthly_summary['Active_Days']
        monthly_summary['Daily_Avg_Cost'] = monthly_summary['Clean_Cost'] / monthly_summary['Calendar_Days']

        monthly_summary['Units_Daily_MoM (%)'] = monthly_summary['Daily_Avg_Units (Calendar)'].pct_change() * 100
        monthly_summary['Cost_MoM (%)'] = monthly_summary['Clean_Cost'].pct_change() * 100

        fig_m_daily = go.Figure()
        fig_m_daily.add_trace(go.Bar(x=monthly_summary['Year_Month'], y=monthly_summary['Daily_Avg_Units (Calendar)'], name='自然日均销量 (件/天)', marker_color='#3B82F6'))
        fig_m_daily.add_trace(go.Scatter(x=monthly_summary['Year_Month'], y=monthly_summary['Daily_Avg_Cost'], name='自然日均销售额 ($/天)', yaxis='y2', line=dict(color='#10B981', width=3)))

        fig_m_daily.update_layout(
            title="月度日均出货速率 (Daily Sales Velocity) 演变图",
            hovermode="x unified",
            yaxis=dict(title="日均销量 (件/天)"),
            yaxis2=dict(title="日均销售额 ($/天)", overlaying='y', side='right')
        )
        st.plotly_chart(fig_m_daily, use_container_width=True)

        st.markdown("### 📋 月度经营与日均出货速率汇总表")
        st.dataframe(
            monthly_summary.rename(columns={
                'Year_Month': '月份', 'Clean_Cost': '月销售额 ($)', 'Clean_Units': '月总出货量 (件)',
                'Calendar_Days': '当月天数', 'Daily_Avg_Units (Calendar)': '自然日均销量 (件/天)',
                'Daily_Avg_Units (Active)': '实际动销日均 (件/天)', 'Daily_Avg_Cost': '自然日均销售额 ($/天)',
                'Units_Daily_MoM (%)': '日均销量环比 MoM (%)'
            }).style.format({
                '月销售额 ($)': '${:,.2f}', '月总出货量 (件)': '{:,.0f}', '自然日均销量 (件/天)': '{:,.1f} 件/天',
                '实际动销日均 (件/天)': '{:,.1f} 件/天', '自然日均销售额 ($/天)': '${:,.2f}/天', '日均销量环比 MoM (%)': '{:+.2f}%'
            }), use_container_width=True
        )

        st.markdown("---")

        # -----------------------------------------------------------------
        # 2. 双月日均销量 (Sales Velocity) 深度对比
        # -----------------------------------------------------------------
        st.subheader("🔍 2. 任意双月【日均销量 (Units/Day)】对比与 SKU 速率诊断")
        
        c_m1, c_m2 = st.columns(2)
        with c_m1: month_a = st.selectbox("选择基准月份 (Month A)", available_months, index=0)
        with c_m2: 
            default_idx_b = len(available_months) - 1 if len(available_months) > 1 else 0
            month_b = st.selectbox("选择对比月份 (Month B)", available_months, index=default_idx_b)

        days_a = get_month_days(month_a)
        days_b = get_month_days(month_b)

        df_mA = df_sales[df_sales['Year_Month'] == month_a]
        df_mB = df_sales[df_sales['Year_Month'] == month_b]

        daily_units_A = df_mA['Clean_Units'].sum() / days_a if days_a > 0 else 0
        daily_units_B = df_mB['Clean_Units'].sum() / days_b if days_b > 0 else 0
        diff_daily_units = daily_units_B - daily_units_A
        pct_daily_units = (diff_daily_units / daily_units_A * 100) if daily_units_A > 0 else 0

        st.markdown(f"#### 📌 【{month_b}】 vs 【{month_a}】 日均销量对比概览")
        k1, k2, k3 = st.columns(3)
        k1.metric(f"{month_a} 全盘日均销量", f"{daily_units_A:.1f} 件/天", help=f"当月天数: {days_a} 天")
        k2.metric(f"{month_b} 全盘日均销量", f"{daily_units_B:.1f} 件/天", delta=f"{diff_daily_units:+.1f} 件/天 ({pct_daily_units:+.1f}%)", help=f"当月天数: {days_b} 天")
        k3.metric("月天数差异", f"{days_b - days_a:+} 天", help="自动排查因为大小月/润年天数不同造成的总销差额")

        # SKU 级别的日均销量对比
        st.markdown("### 📦 双月各 SKU【日均销量 (件/天)】增减变化排行榜")

        sku_mA_v = df_mA.groupby(sku_col).agg({'Clean_Units': 'sum'}).reset_index()
        sku_mA_v['Daily_A'] = sku_mA_v['Clean_Units'] / days_a

        sku_mB_v = df_mB.groupby(sku_col).agg({'Clean_Units': 'sum'}).reset_index()
        sku_mB_v['Daily_B'] = sku_mB_v['Clean_Units'] / days_b

        sku_v_comp = pd.merge(
            sku_mA_v[[sku_col, 'Clean_Units', 'Daily_A']],
            sku_mB_v[[sku_col, 'Clean_Units', 'Daily_B']],
            on=sku_col, how='outer'
        ).fillna(0)

        sku_v_comp['Daily_Diff'] = sku_v_comp['Daily_B'] - sku_v_comp['Daily_A']
        sku_v_comp['Daily_Growth (%)'] = (sku_v_comp['Daily_Diff'] / sku_v_comp['Daily_A']) * 100
        sku_v_comp['Daily_Growth (%)'] = sku_v_comp['Daily_Growth (%)'].fillna(0).replace([float('inf'), -float('inf')], 0)

        sku_v_comp = sku_v_comp.sort_values(by='Daily_Diff', ascending=False)

        tab_v_inc, tab_v_dec, tab_v_all = st.tabs(["🚀 日均销量提速 TOP SKU", "🔻 日均销量失速 TOP SKU", "📊 全部 SKU 日均对比表"])

        with tab_v_inc:
            st.caption(f"在 {month_b} 相比 {month_a} **日均出货件数增长最多** 的产品：")
            st.dataframe(
                sku_v_comp[sku_v_comp['Daily_Diff'] > 0].rename(columns={
                    sku_col: '产品 SKU', 
                    'Clean_Units_x': f'{month_a} 总销量', 'Daily_A': f'{month_a} 日均 (件/天)',
                    'Clean_Units_y': f'{month_b} 总销量', 'Daily_B': f'{month_b} 日均 (件/天)',
                    'Daily_Diff': '日均销量增量 (件/天)', 'Daily_Growth (%)': '日均增速 (%)'
                }).style.format({
                    f'{month_a} 总销量': '{:,.0f}', f'{month_a} 日均 (件/天)': '{:,.1f}',
                    f'{month_b} 总销量': '{:,.0f}', f'{month_b} 日均 (件/天)': '{:,.1f}',
                    '日均销量增量 (件/天)': '+{:,.1f} 件/天', '日均增速 (%)': '+{:.1f}%'
                }), use_container_width=True
            )

        with tab_v_dec:
            st.caption(f"在 {month_b} 相比 {month_a} **日均出货件数下滑最多** 的产品：")
            st.dataframe(
                sku_v_comp[sku_v_comp['Daily_Diff'] < 0].sort_values(by='Daily_Diff', ascending=True).rename(columns={
                    sku_col: '产品 SKU', 
                    'Clean_Units_x': f'{month_a} 总销量', 'Daily_A': f'{month_a} 日均 (件/天)',
                    'Clean_Units_y': f'{month_b} 总销量', 'Daily_B': f'{month_b} 日均 (件/天)',
                    'Daily_Diff': '日均销量减量 (件/天)', 'Daily_Growth (%)': '日均增速 (%)'
                }).style.format({
                    f'{month_a} 总销量': '{:,.0f}', f'{month_a} 日均 (件/天)': '{:,.1f}',
                    f'{month_b} 总销量': '{:,.0f}', f'{month_b} 日均 (件/天)': '{:,.1f}',
                    '日均销量减量 (件/天)': '{:,.1f} 件/天', '日均增速 (%)': '{:.1f}%'
                }), use_container_width=True
            )

        with tab_v_all:
            st.dataframe(
                sku_v_comp.rename(columns={
                    sku_col: '产品 SKU', 
                    'Clean_Units_x': f'{month_a} 总销量', 'Daily_A': f'{month_a} 日均 (件/天)',
                    'Clean_Units_y': f'{month_b} 总销量', 'Daily_B': f'{month_b} 日均 (件/天)',
                    'Daily_Diff': '日均变化 (件/天)', 'Daily_Growth (%)': '日均增速 (%)'
                }).style.format({
                    f'{month_a} 总销量': '{:,.0f}', f'{month_a} 日均 (件/天)': '{:,.1f}',
                    f'{month_b} 总销量': '{:,.0f}', f'{month_b} 日均 (件/天)': '{:,.1f}',
                    '日均变化 (件/天)': '{:,.1f}', '日均增速 (%)': '{:+.1f}%'
                }), use_container_width=True
            )

        st.markdown("---")

        # -----------------------------------------------------------------
        # 3. 品类维度的月度结构演变
        # -----------------------------------------------------------------
        st.subheader("🏷️ 3. 月度品类结构分布与演变 (Category Mix)")
        cat_monthly = df_sales.groupby(['Year_Month', 'Clean_Category']).agg({'Clean_Cost': 'sum', 'Clean_Units': 'sum'}).reset_index()

        fig_cat_monthly = px.bar(
            cat_monthly, x='Year_Month', y='Clean_Cost', color='Clean_Category',
            title="各月份产品品类销售额构成（堆叠图）", labels={'Year_Month': '月份', 'Clean_Cost': '销售额 ($)', 'Clean_Category': '产品品类'}
        )
        st.plotly_chart(fig_cat_monthly, use_container_width=True)

# =========================================================================
# 模块三：广告绩效诊断与运营看板 (SPA Ad Operations Dashboard)
# =========================================================================
elif module == "📢 SPA 广告绩效诊断与运营看板":
    st.title("📢 Home Depot SPA 广告绩效诊断与运营决策看板")
    st.caption("聚焦运营动作：止损排查、高 ROAS 扩量、转化率诊断与预算分配")
    st.markdown("---")

    st.sidebar.header("⚙️ 1. 广告数据上传")
    uploaded_ad_file = st.sidebar.file_uploader("上传 Home Depot 广告报表 (CSV/Excel)", type=["csv", "xlsx"], key="ad_uploader")

    if not uploaded_ad_file:
        st.info("👋 请在侧边栏上传您的 Home Depot SPA 广告报表。")
    else:
        try:
            if uploaded_ad_file.name.endswith('.csv'): df_ad = pd.read_csv(uploaded_ad_file)
            else: df_ad = pd.read_excel(uploaded_ad_file)
        except Exception as e:
            st.error(f"读取广告文件失败: {e}"); st.stop()

        df_ad.columns = df_ad.columns.str.strip()
        campaign_col = next((c for c in df_ad.columns if c in ['Campaign Name', 'Campaign']), None)
        spend_col = next((c for c in df_ad.columns if c in ['Spend', 'Cost', 'Ad Spend']), None)
        sales_col = next((c for c in df_ad.columns if c in ['SPA Sales', 'Sales', 'Ad Sales']), None)
        clicks_col = next((c for c in df_ad.columns if c in ['Clicks', 'Click']), None)
        impressions_col = next((c for c in df_ad.columns if c in ['Impressions', 'Impression']), None)
        roas_col = next((c for c in df_ad.columns if c in ['SPA ROAS', 'ROAS']), None)
        omsid_col = next((c for c in df_ad.columns if c in ['Promoted OMSID Number', 'OMSID', 'Promoted OMS ID']), None)

        if not campaign_col or not spend_col or not sales_col:
            st.error(f"解析失败！请确保包含 Campaign Name, Spend, SPA Sales 列。")
            st.stop()

        for col in [spend_col, sales_col, clicks_col, impressions_col, roas_col]:
            if col and col in df_ad.columns:
                df_ad[col] = pd.to_numeric(df_ad[col].astype(str).str.replace('$', '').str.replace(',', '').str.replace('%', ''), errors='coerce').fillna(0)

        st.sidebar.markdown("---")
        st.sidebar.header("🎯 2. 运营优化阈值设置")
        target_roas = st.sidebar.number_input("目标 ROAS", min_value=0.1, value=2.5, step=0.5)
        waste_spend_threshold = st.sidebar.number_input("零转化报警 Spend 阈值 ($)", min_value=1.0, value=30.0, step=10.0)

        total_spend = df_ad[spend_col].sum() if spend_col else 0
        total_sales = df_ad[sales_col].sum() if sales_col else 0
        total_clicks = df_ad[clicks_col].sum() if clicks_col else 0
        total_impressions = df_ad[impressions_col].sum() if impressions_col else 0

        overall_roas = total_sales / total_spend if total_spend > 0 else 0
        overall_ctr = (total_clicks / total_impressions) * 100 if total_impressions > 0 else 0
        overall_cpc = total_spend / total_clicks if total_clicks > 0 else 0

        st.subheader("📌 1. 广告大盘核心指标 (Macro Overview)")
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("总广告花费 (Spend)", f"${total_spend:,.2f}")
        c2.metric("广告销售额 (SPA Sales)", f"${total_sales:,.2f}")
        roas_delta = overall_roas - target_roas
        c3.metric("整体 ROAS", f"{overall_roas:.2f}", delta=f"{roas_delta:+.2f} vs 目标", delta_color="normal" if roas_delta >= 0 else "inverse")
        c4.metric("总点击 / 平均 CPC", f"{int(total_clicks):,} 次", delta=f"${overall_cpc:.2f}/点击", delta_color="off")
        c5.metric("总曝光 / CTR", f"{int(total_impressions):,} 次", delta=f"{overall_ctr:.2f}% CTR", delta_color="off")

        st.markdown("---")
        st.subheader("🚨 2. 运营调优诊断中心 (Actionable Insights)")
        wasted_df = df_ad[(df_ad[spend_col] >= waste_spend_threshold) & (df_ad[sales_col] == 0)]
        total_wasted_spend = wasted_df[spend_col].sum()
        bleed_df = df_ad[(df_ad[spend_col] >= waste_spend_threshold) & (df_ad[sales_col] > 0) & (df_ad[roas_col] < (target_roas * 0.6))]
        potential_df = df_ad[(df_ad[roas_col] >= target_roas) & (df_ad[spend_col] < (total_spend / max(len(df_ad), 1)))]

        d1, d2, d3 = st.columns(3)
        d1.error(f"🔻 **无效花费资金浪费**: `${total_wasted_spend:,.2f}`\n\n**{len(wasted_df)}** 项 Spend ≥ ${waste_spend_threshold} 且出单为 0。")
        d2.warning(f"⚠️ **低效出血点广告**: **{len(bleed_df)}** 项\n\nSpend ≥ ${waste_spend_threshold} 且 ROAS 远低于目标。")
        d3.success(f"🚀 **高 ROAS 扩量机会**: **{len(potential_df)}** 项\n\nROAS 达标（≥ {target_roas}），建议增加每日预算！")

        tab1, tab2, tab3 = st.tabs(["🔥 重点排查：无转化浪费项", "⚠️ 低效出血点列表", "🚀 扩量提额潜力项"])
        with tab1:
            if not wasted_df.empty: st.dataframe(wasted_df[[campaign_col, omsid_col, spend_col, clicks_col, impressions_col]].sort_values(by=spend_col, ascending=False), use_container_width=True)
            else: st.info("🎉 暂未发现无转化浪费项。")
        with tab2:
            if not bleed_df.empty: st.dataframe(bleed_df[[campaign_col, omsid_col, spend_col, sales_col, roas_col, clicks_col]].sort_values(by=spend_col, ascending=False), use_container_width=True)
            else: st.info("暂未发现出血点广告。")
        with tab3:
            if not potential_df.empty: st.dataframe(potential_df[[campaign_col, omsid_col, spend_col, sales_col, roas_col]].sort_values(by=roas_col, ascending=False), use_container_width=True)
            else: st.info("暂未识别到潜力广告。")

# =========================================================================
# 模块四：下月销售目标与 SKU 销量拆解看板
# =========================================================================
else:
    st.title("🎯 下月销售目标制定与 SKU 销量预测拆解看板")
    st.caption("基于历史动销速率与目标增长率，科学预测下月销售目标并层层拆解至各 SKU")
    st.markdown("---")

    st.sidebar.header("⚙️ 1. 历史销售数据上传")
    uploaded_sales_file = st.sidebar.file_uploader("上传历史销售报表 (CSV/Excel)", type=["csv", "xlsx"], key="target_uploader")

    if not uploaded_sales_file:
        st.info("👋 请先在侧边栏上传历史销售报表。系统将自动抓取近 30 天的动销数据进行下月目标推演。")
    else:
        try:
            if uploaded_sales_file.name.endswith('.csv'): df_sales = pd.read_csv(uploaded_sales_file)
            else: df_sales = pd.read_excel(uploaded_sales_file)
        except Exception as e:
            st.error(f"读取文件失败: {e}"); st.stop()

        df_sales.columns = df_sales.columns.str.strip()

        date_col = next((c for c in df_sales.columns if c in ['日期', 'Date', 'sales_date']), None)
        sales_col = next((c for c in df_sales.columns if c in ['销量', 'Units Sold', 'Units', 'Quantity']), None)
        cost_col = next((c for c in df_sales.columns if c in ['Total Cost', 'Cost', '金额', '总金额']), None)
        sku_col = next((c for c in ['产品SKU', 'SKU', 'Merchant SKU', 'Vendor SKU', 'OMS ID'] if c in df_sales.columns), None)

        if not date_col or not sales_col or not sku_col:
            st.error("数据表缺失关键列（日期、销量或 SKU），请检查上载的文件！")
            st.stop()

        df_sales['Clean_Date'] = pd.to_datetime(df_sales[date_col])
        df_sales['Clean_Units'] = pd.to_numeric(df_sales[sales_col], errors='coerce').fillna(0)
        df_sales['Clean_Cost'] = pd.to_numeric(df_sales[cost_col], errors='coerce').fillna(0) if cost_col else 0

        max_date = df_sales['Clean_Date'].max()
        last_30_days_start = max_date - pd.Timedelta(days=30)
        recent_sales = df_sales[df_sales['Clean_Date'] >= last_30_days_start]

        sku_recent = recent_sales.groupby(sku_col).agg(
            Recent_Units=('Clean_Units', 'sum'),
            Recent_Cost=('Clean_Cost', 'sum'),
            Active_Days=('Clean_Date', lambda x: x[df_sales.loc[x.index, 'Clean_Units'] > 0].nunique()),
            Avg_Price=('Clean_Cost', lambda x: x.sum() / df_sales.loc[x.index, 'Clean_Units'].sum() if df_sales.loc[x.index, 'Clean_Units'].sum() > 0 else 0)
        ).reset_index()

        sku_recent['Active_Daily_Avg'] = sku_recent.apply(
            lambda r: r['Recent_Units'] / r['Active_Days'] if r['Active_Days'] > 0 else 0, axis=1
        )

        last_month_cost = sku_recent['Recent_Cost'].sum()

        st.sidebar.markdown("---")
        st.sidebar.markdown("### ⚙️ 2. 下月目标设定参数")
        
        target_mode = st.sidebar.radio("目标制定方式", ["按销售额增长率 (%)", "按自定义总销售额 ($)"])
        
        if target_mode == "按销售额增长率 (%)":
            growth_rate = st.sidebar.number_input("下月目标增长率 (%)", value=10.0, step=1.0)
            target_total_cost = last_month_cost * (1 + growth_rate / 100)
        else:
            target_total_cost = st.sidebar.number_input("下月目标总金额 ($)", value=float(round(last_month_cost * 1.1, 2)))
            growth_rate = ((target_total_cost - last_month_cost) / last_month_cost * 100) if last_month_cost > 0 else 0

        st.subheader("📌 1. 下月全盘经营目标")
        t1, t2, t3, t4 = st.columns(4)
        t1.metric("近 30 天实际完成额", f"${last_month_cost:,.2f}")
        t2.metric("下月目标销售额", f"${target_total_cost:,.2f}", delta=f"{growth_rate:+.1f}% 增长")
        
        avg_price_all = sku_recent['Recent_Cost'].sum() / sku_recent['Recent_Units'].sum() if sku_recent['Recent_Units'].sum() > 0 else 0
        target_total_units = target_total_cost / avg_price_all if avg_price_all > 0 else 0
        
        t3.metric("预估需出货总件数", f"{int(target_total_units):,} 件")
        t4.metric("下月日均目标营收", f"${target_total_cost / 30:,.2f} /天")

        st.markdown("---")

        st.subheader("📦 2. 各 SKU 下月预测销量与每日目标件数拆解清单")

        sku_recent['Sales_Share'] = sku_recent['Recent_Cost'] / last_month_cost if last_month_cost > 0 else 0
        sku_recent['Target_Cost_Allocated'] = target_total_cost * sku_recent['Sales_Share']
        
        sku_recent['Target_Units_Forecast'] = sku_recent.apply(
            lambda r: r['Target_Cost_Allocated'] / r['Avg_Price'] if r['Avg_Price'] > 0 else 0, axis=1
        )
        sku_recent['Target_Daily_Units'] = sku_recent['Target_Units_Forecast'] / 30

        forecast_df = sku_recent.rename(columns={
            sku_col: '产品 SKU',
            'Recent_Cost': '近30天销售额 ($)',
            'Recent_Units': '近30天销量 (件)',
            'Active_Daily_Avg': '近30天动销日均 (件/天)',
            'Avg_Price': '平均件单价 ($)',
            'Target_Cost_Allocated': '下月目标金额 ($)',
            'Target_Units_Forecast': '下月预测销量 (件)',
            'Target_Daily_Units': '下月目标日均 (件/天)'
        }).sort_values(by='下月目标金额 ($)', ascending=False)

        st.dataframe(
            forecast_df[[
                '产品 SKU', '平均件单价 ($)', '近30天销量 (件)', 
                '近30天动销日均 (件/天)', '下月预测销量 (件)', 
                '下月目标日均 (件/天)', '下月目标金额 ($)'
            ]].style.format({
                '平均件单价 ($)': '${:,.2f}',
                '近30天销量 (件)': '{:,.0f}',
                '近30天动销日均 (件/天)': '{:,.1f}',
                '下月预测销量 (件)': '{:,.0f} 件',
                '下月目标日均 (件/天)': '{:,.1f} 件/天',
                '下月目标金额 ($)': '${:,.2f}'
            }),
            use_container_width=True
        )
