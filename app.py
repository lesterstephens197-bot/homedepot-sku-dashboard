import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

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
        "🗓️ 月度环比与多维度对比看板",  # 🆕 新增月度对比模块
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

        # 表头自动匹配
        date_col = next((c for c in df_sales.columns if c in ['日期', 'Date', 'sales_date']), None)
        sales_col = next((c for c in df_sales.columns if c in ['销量', 'Units Sold', 'Units', 'Quantity']), None)
        cost_col = next((c for c in df_sales.columns if c in ['Total Cost', 'Cost', '金额', '总金额']), None)
        category_col = next((c for c in df_sales.columns if c in ['产品名称', 'Category', '品类', '品类名称']), None)
        state_col = next((c for c in df_sales.columns if c in ['ShipTo State', 'State', '州', '省份']), None)

        sku_fields_available = [col for col in ['产品SKU', 'SKU', 'Merchant SKU', 'Vendor SKU', 'OMS ID'] if col in df_sales.columns]

        if not date_col or not sales_col or not sku_fields_available:
            st.error(f"解析失败！未能在表格中识别到必需列（日期、销量或产品SKU列）。当前识别到的表头列为: {list(df_sales.columns)}")
            st.stop()

        # 数据清洗
        df_sales['Clean_Date'] = pd.to_datetime(df_sales[date_col])
        df_sales['Clean_Units'] = pd.to_numeric(df_sales[sales_col], errors='coerce').fillna(0)
        df_sales['Clean_Cost'] = pd.to_numeric(df_sales[cost_col], errors='coerce').fillna(0) if cost_col else 0
        df_sales['Clean_Category'] = df_sales[category_col].astype(str).str.strip().replace({'nan': '未分类', 'None': '未分类', '': '未分类'}) if category_col else '未分类'
        if state_col:
            df_sales['Clean_State'] = df_sales[state_col].astype(str).str.strip().str.upper().replace({'NAN': '未知', 'NONE': '未知', '': '未知'})

        primary_sku_col = sku_fields_available[0]

        # 时间筛选
        min_d = df_sales['Clean_Date'].min().date()
        max_d = df_sales['Clean_Date'].max().date()

        st.sidebar.markdown("---")
        st.sidebar.markdown("### 🗓️ 2. 时间范围筛选")
        date_range = st.sidebar.date_input("分析时间范围", [min_d, max_d], min_value=min_d, max_value=max_d)

        start_date = date_range[0] if len(date_range) >= 1 else min_d
        end_date = date_range[1] if len(date_range) == 2 else max_d

        time_mask = (df_sales['Clean_Date'].dt.date >= start_date) & (df_sales['Clean_Date'].dt.date <= end_date)
        filtered_sales = df_sales[time_mask]

        # 1. 管理层高阶 KPI 概览
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

        # 2. ABC 帕累托诊断与 SKU 动销效率全景表
        st.subheader("🏆 2. 产品结构 ABC 帕累托诊断与 SKU 动销效率全景表")
        st.caption("A 类：贡献前 80% 销售额的核心爆款 | B 类：贡献 80%-95% 的腰部主力款 | C 类：贡献最后 5% 的尾部/滞销款")

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

        tab_a, tab_b, tab_c, tab_all = st.tabs([
            f"🟢 A 类核心爆款 ({len(df_a)} 款)", f"🟡 B 类腰部潜力 ({len(df_b)} 款)", 
            f"🔴 C 类尾部滞销 ({len(df_c)} 款)", f"📊 全量 SKU 动销效率排行榜 ({len(sku_summary)} 款)"
        ])

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

        with tab_a: render_sku_table(df_a)
        with tab_b: render_sku_table(df_b)
        with tab_c: render_sku_table(df_c)
        with tab_all: render_sku_table(sku_summary)

        st.markdown("---")

        # 3. 细分视角分析
        st.sidebar.markdown("---")
        st.sidebar.markdown("### 🔍 3. 运营分析视角")
        view_mode = st.sidebar.radio("选择细分视角", ["📦 单产品 SKU 动销深度分析", "🗺️ 全美物流仓储与地理分布", "🏷️ 品类占比与结构分析"])

        if view_mode == "📦 单产品 SKU 动销深度分析":
            st.subheader("📦 单产品 SKU 动销效率与日均走势")
            selected_sku = st.sidebar.selectbox(f"选择 {primary_sku_col}", sku_summary[primary_sku_col].unique())
            sku_df = filtered_sales[filtered_sales[primary_sku_col].astype(str) == str(selected_sku)].sort_values('Clean_Date')

            if not sku_df.empty:
                total_sku_units = sku_df['Clean_Units'].sum()
                total_sku_cost = sku_df['Clean_Cost'].sum()
                daily_summary = sku_df.groupby('Clean_Date').agg({'Clean_Units': 'sum', 'Clean_Cost': 'sum'}).reset_index()
                
                total_range_days = (end_date - start_date).days + 1
                active_days = len(daily_summary[daily_summary['Clean_Units'] > 0])
                overall_avg = total_sku_units / total_range_days if total_range_days > 0 else 0
                active_avg = total_sku_units / active_days if active_days > 0 else 0
                active_rate = (active_days / total_range_days) * 100 if total_range_days > 0 else 0

                s1, s2, s3, s4 = st.columns(4)
                s1.metric("区间总销量", f"{int(total_sku_units):,} 件")
                s2.metric("区间总金额", f"${total_sku_cost:,.2f}")
                s3.metric("动销率", f"{active_rate:.1f}%")
                s4.metric("动销日均销量", f"{active_avg:.1f} 件/天", delta=f"自然日均: {overall_avg:.1f}")

                fig_sku_trend = go.Figure()
                fig_sku_trend.add_trace(go.Bar(x=daily_summary['Clean_Date'], y=daily_summary['Clean_Units'], name='销量 (件)', marker_color='#3B82F6'))
                fig_sku_trend.add_trace(go.Scatter(x=daily_summary['Clean_Date'], y=daily_summary['Clean_Cost'], name='金额 ($)', yaxis='y2', line=dict(color='#10B981', width=2.5)))
                fig_sku_trend.update_layout(title=f"SKU: {selected_sku} - 每日销量与金额趋势", hovermode="x unified", yaxis=dict(title="销量 (件)"), yaxis2=dict(title="金额 ($)", overlaying='y', side='right'))
                st.plotly_chart(fig_sku_trend, use_container_width=True)

        elif view_mode == "🗺️ 全美物流仓储与地理分布":
            st.subheader("🗺️ 全美各州销量热力分布")
            if state_col and 'Clean_State' in filtered_sales.columns:
                state_df = filtered_sales.groupby('Clean_State').agg({'Clean_Units': 'sum', 'Clean_Cost': 'sum'}).reset_index()
                state_df['Share_Pct'] = (state_df['Clean_Units'] / total_units) * 100 if total_units > 0 else 0
                state_df = state_df.sort_values(by='Clean_Units', ascending=False)

                m1, m2 = st.columns([2, 1])
                with m1:
                    fig_map = px.choropleth(state_df, locations='Clean_State', locationmode="USA-states", color='Clean_Units', scope="usa", color_continuous_scale="Viridis", title="美国各州出货量热力图")
                    st.plotly_chart(fig_map, use_container_width=True)
                with m2:
                    st.markdown("### 🏆 Top 10 销量集中州")
                    st.dataframe(state_df.head(10).rename(columns={'Clean_State': '州', 'Clean_Units': '销量', 'Clean_Cost': '销售额', 'Share_Pct': '占比 (%)'}), use_container_width=True)

        else:
            st.subheader("🏷️ 产品品类 (Category) 销售结构分析")
            cat_df = filtered_sales.groupby('Clean_Category').agg({'Clean_Units': 'sum', 'Clean_Cost': 'sum', primary_sku_col: 'nunique'}).reset_index().sort_values(by='Clean_Cost', ascending=False)
            fig_cat = px.bar(cat_df, x='Clean_Category', y='Clean_Cost', text='Clean_Cost', color='Clean_Units', title="各品类销售额与出货件数表现")
            fig_cat.update_traces(texttemplate='$%{text:,.0f}', textposition='outside')
            st.plotly_chart(fig_cat, use_container_width=True)

# =========================================================================
# 模块二：月度环比与多维度对比看板 (🆕 Monthly Comparison Dashboard)
# =========================================================================
elif module == "🗓️ 月度环比与多维度对比看板":
    st.title("🗓️ 月度环比与多维度对比分析看板")
    st.caption("聚焦月度业绩演变：月度大盘趋势、MoM 环比分析、双月 SKU 增减对比与品类结构动态")
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
        state_col = next((c for c in df_sales.columns if c in ['ShipTo State', 'State', '州', '省份']), None)
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

        # -----------------------------------------------------------------
        # 1. 整体月度走势图表
        # -----------------------------------------------------------------
        st.subheader("📈 1. 整体月度销售额与出货量趋势")
        monthly_summary = df_sales.groupby('Year_Month').agg({
            'Clean_Cost': 'sum',
            'Clean_Units': 'sum',
            sku_col: 'nunique'
        }).reset_index().rename(columns={sku_col: 'Active_SKUs'})

        monthly_summary['ASP'] = monthly_summary['Clean_Cost'] / monthly_summary['Clean_Units']
        monthly_summary['Cost_MoM (%)'] = monthly_summary['Clean_Cost'].pct_change() * 100
        monthly_summary['Units_MoM (%)'] = monthly_summary['Clean_Units'].pct_change() * 100

        fig_m_trend = go.Figure()
        fig_m_trend.add_trace(go.Bar(x=monthly_summary['Year_Month'], y=monthly_summary['Clean_Units'], name='月度销量 (件)', marker_color='#3B82F6'))
        fig_m_trend.add_trace(go.Scatter(x=monthly_summary['Year_Month'], y=monthly_summary['Clean_Cost'], name='月度销售额 ($)', yaxis='y2', line=dict(color='#10B981', width=3)))

        fig_m_trend.update_layout(
            title="月度销售额 (Total Cost) 与出货量 (Units) 演变图",
            hovermode="x unified",
            yaxis=dict(title="销量 (件)"),
            yaxis2=dict(title="销售额 ($)", overlaying='y', side='right')
        )
        st.plotly_chart(fig_m_trend, use_container_width=True)

        st.markdown("### 📋 月度经营绩效汇总表")
        st.dataframe(
            monthly_summary.rename(columns={
                'Year_Month': '月份', 'Clean_Cost': '月销售额 ($)', 'Clean_Units': '月出货量 (件)',
                'Active_SKUs': '动销 SKU 数', 'ASP': '件单价 ($)',
                'Cost_MoM (%)': '销售额环比 MoM (%)', 'Units_MoM (%)': '销量环比 MoM (%)'
            }).style.format({
                '月销售额 ($)': '${:,.2f}', '月出货量 (件)': '{:,.0f}', '动销 SKU 数': '{:,.0f}',
                '件单价 ($)': '${:.2f}', '销售额环比 MoM (%)': '{:+.2f}%', '销量环比 MoM (%)': '{:+.2f}%'
            }), use_container_width=True
        )

        st.markdown("---")

        # -----------------------------------------------------------------
        # 2. 两个月份深度对比诊断
        # -----------------------------------------------------------------
        st.subheader("🔍 2. 任意双月深度对比诊断 (Month vs Month)")
        
        c_m1, c_m2 = st.columns(2)
        with c_m1:
            month_a = st.selectbox("选择基准月份 (Month A)", available_months, index=0)
        with c_m2:
            default_idx_b = len(available_months) - 1 if len(available_months) > 1 else 0
            month_b = st.selectbox("选择对比月份 (Month B)", available_months, index=default_idx_b)

        df_mA = df_sales[df_sales['Year_Month'] == month_a]
        df_mB = df_sales[df_sales['Year_Month'] == month_b]

        cost_A = df_mA['Clean_Cost'].sum()
        cost_B = df_mB['Clean_Cost'].sum()
        units_A = df_mA['Clean_Units'].sum()
        units_B = df_mB['Clean_Units'].sum()

        diff_cost = cost_B - cost_A
        diff_units = units_B - units_A
        pct_cost = (diff_cost / cost_A * 100) if cost_A > 0 else 0
        pct_units = (diff_units / units_A * 100) if units_A > 0 else 0

        st.markdown(f"#### 📌 【{month_b}】 vs 【{month_a}】 核心对比结果")
        k1, k2, k3, k4 = st.columns(4)
        k1.metric(f"{month_a} 销售额", f"${cost_A:,.2f}")
        k2.metric(f"{month_b} 销售额", f"${cost_B:,.2f}", delta=f"${diff_cost:+,.2f} ({pct_cost:+.1f}%)")
        k3.metric(f"{month_a} 销量", f"{int(units_A):,} 件")
        k4.metric(f"{month_b} 销量", f"{int(units_B):,} 件", delta=f"{int(diff_units):+,} 件 ({pct_units:+.1f}%)")

        # -----------------------------------------------------------------
        # SKU 维度的月度增减量排查
        # -----------------------------------------------------------------
        st.markdown("### 📦 两个月份之间 SKU 销量/金额增减变化明细")

        sku_mA = df_mA.groupby(sku_col).agg({'Clean_Cost': 'sum', 'Clean_Units': 'sum'}).reset_index().rename(columns={'Clean_Cost': 'Cost_A', 'Clean_Units': 'Units_A'})
        sku_mB = df_mB.groupby(sku_col).agg({'Clean_Cost': 'sum', 'Clean_Units': 'sum'}).reset_index().rename(columns={'Clean_Cost': 'Cost_B', 'Clean_Units': 'Units_B'})

        sku_comp = pd.merge(sku_mA, sku_mB, on=sku_col, how='outer').fillna(0)
        sku_comp['Cost_Diff'] = sku_comp['Cost_B'] - sku_comp['Cost_A']
        sku_comp['Units_Diff'] = sku_comp['Units_B'] - sku_comp['Units_A']
        sku_comp = sku_comp.sort_values(by='Cost_Diff', ascending=False)

        tab_inc, tab_dec, tab_comp_all = st.tabs(["🚀 增长拉动 TOP SKU", "🔻 下滑拖累 TOP SKU", "📊 全部 SKU 对比总表"])

        with tab_inc:
            st.caption(f"在 {month_b} 相比 {month_a} 销售额增长最多的 SKU 列表：")
            st.dataframe(
                sku_comp[sku_comp['Cost_Diff'] > 0].rename(columns={
                    sku_col: '产品 SKU', 'Cost_A': f'{month_a} 金额 ($)', 'Cost_B': f'{month_b} 金额 ($)',
                    'Cost_Diff': '金额增量 ($)', 'Units_A': f'{month_a} 销量', 'Units_B': f'{month_b} 销量', 'Units_Diff': '销量增量'
                }).style.format({
                    f'{month_a} 金额 ($)': '${:,.2f}', f'{month_b} 金额 ($)': '${:,.2f}', '金额增量 ($)': '+${:,.2f}',
                    f'{month_a} 销量': '{:,.0f}', f'{month_b} 销量': '{:,.0f}', '销量增量': '+{:,.0f}'
                }), use_container_width=True
            )

        with tab_dec:
            st.caption(f"在 {month_b} 相比 {month_a} 销售额下滑最多的 SKU 列表：")
            st.dataframe(
                sku_comp[sku_comp['Cost_Diff'] < 0].sort_values(by='Cost_Diff', ascending=True).rename(columns={
                    sku_col: '产品 SKU', 'Cost_A': f'{month_a} 金额 ($)', 'Cost_B': f'{month_b} 金额 ($)',
                    'Cost_Diff': '金额减量 ($)', 'Units_A': f'{month_a} 销量', 'Units_B': f'{month_b} 销量', 'Units_Diff': '销量减量'
                }).style.format({
                    f'{month_a} 金额 ($)': '${:,.2f}', f'{month_b} 金额 ($)': '${:,.2f}', '金额减量 ($)': '${:,.2f}',
                    f'{month_a} 销量': '{:,.0f}', f'{month_b} 销量': '{:,.0f}', '销量减量': '{:,.0f}'
                }), use_container_width=True
            )

        with tab_comp_all:
            st.dataframe(
                sku_comp.rename(columns={
                    sku_col: '产品 SKU', 'Cost_A': f'{month_a} 金额 ($)', 'Cost_B': f'{month_b} 金额 ($)',
                    'Cost_Diff': '金额变化 ($)', 'Units_A': f'{month_a} 销量', 'Units_B': f'{month_b} 销量', 'Units_Diff': '销量变化'
                }).style.format({
                    f'{month_a} 金额 ($)': '${:,.2f}', f'{month_b} 金额 ($)': '${:,.2f}', '金额变化 ($)': '${:,.2f}',
                    f'{month_a} 销量': '{:,.0f}', f'{month_b} 销量': '{:,.0f}', '销量变化': '{:,.0f}'
                }), use_container_width=True
            )

        st.markdown("---")

        # -----------------------------------------------------------------
        # 品类维度的月度结构演变
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
# 模块四：下月销售目标与 SKU 销量拆解看板 (Target Setting & SKU Forecasting)
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
        st.caption("系统已根据每个 SKU 近 30 天的**销售贡献权重**与**件单价**，将总目标精准拆解至各个 SKU：")

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

        st.markdown("---")

        st.subheader("📊 3. 重点 SKU 下月目标销量 vs 近 30 天实际销量对比")
        top10_forecast = forecast_df.head(10)
        
        fig_target = go.Figure()
        fig_target.add_trace(go.Bar(x=top10_forecast['产品 SKU'], y=top10_forecast['近30天销量 (件)'], name='近 30 天实际销量', marker_color='#93C5FD'))
        fig_target.add_trace(go.Bar(x=top10_forecast['产品 SKU'], y=top10_forecast['下月预测销量 (件)'], name='下月目标拆解销量', marker_color='#1D4ED8'))
        fig_target.update_layout(barmode='group', hovermode="x unified", title="TOP 10 重点 SKU 下月拆解目标与历史对比 (件)")
        st.plotly_chart(fig_target, use_container_width=True)
