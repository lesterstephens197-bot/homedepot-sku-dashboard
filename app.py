import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import calendar

# -------------------------------------------------------------------------
# 页面基础配置
# -------------------------------------------------------------------------
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
        "📅 月度多维度对比与趋势看板", 
        "📢 SPA 广告绩效诊断与运营看板",
        "🎯 下月销售目标与 SKU 销量拆解看板"
    ]
)

st.sidebar.markdown("---")

# =========================================================================
# 辅助函数：统一处理销售数据清洗 (带缓存提升性能)
# =========================================================================
@st.cache_data
def process_sales_data(file_bytes, file_name):
    try:
        if file_name.endswith('.csv'):
            df_sales = pd.read_csv(file_bytes)
        else:
            df_sales = pd.read_excel(file_bytes)
    except Exception as e:
        return None, f"读取文件失败: {str(e)}"

    df_sales.columns = df_sales.columns.astype(str).str.strip()

    # 拓展 Home Depot 报表常见列名识别
    date_col = next((c for c in df_sales.columns if c.lower() in ['日期', 'date', 'sales_date', 'transaction date']), None)
    sales_col = next((c for c in df_sales.columns if c.lower() in ['销量', 'units sold', 'units', 'quantity', 'qty']), None)
    cost_col = next((c for c in df_sales.columns if c.lower() in ['total cost', 'cost', '金额', '总金额', 'sales', 'retail amount', 'total sales']), None)
    category_col = next((c for c in df_sales.columns if c.lower() in ['产品名称', 'category', '品类', '品类名称', 'department name']), None)
    state_col = next((c for c in df_sales.columns if c.lower() in ['shipto state', 'state', '州', '省份', 'ship state']), None)
    sku_fields_available = [col for col in ['产品SKU', 'SKU', 'Merchant SKU', 'Vendor SKU', 'OMS ID', 'Internet SKU', 'Store SKU'] if col in df_sales.columns]

    if not date_col or not sales_col or not sku_fields_available:
        return None, f"解析失败！未能在表格中识别到必需列（日期、销量或产品SKU列）。当前识别到的列为: {list(df_sales.columns)}"

    df_sales['Clean_Date'] = pd.to_datetime(df_sales[date_col], errors='coerce')
    df_sales = df_sales.dropna(subset=['Clean_Date']) # 过滤非法日期
    
    df_sales['Clean_Units'] = pd.to_numeric(df_sales[sales_col], errors='coerce').fillna(0)
    df_sales['Clean_Cost'] = pd.to_numeric(df_sales[cost_col], errors='coerce').fillna(0) if cost_col else 0.0
    
    if category_col:
        df_sales['Clean_Category'] = df_sales[category_col].astype(str).str.strip().replace({'nan': '未分类', 'None': '未分类', '': '未分类'})
    else:
        df_sales['Clean_Category'] = '未分类'
        
    if state_col:
        df_sales['Clean_State'] = df_sales[state_col].astype(str).str.strip().str.upper().replace({'NAN': '未知', 'NONE': '未知', '': '未知'})

    primary_sku_col = sku_fields_available[0]
    df_sales['YearMonth'] = df_sales['Clean_Date'].dt.to_period('M').astype(str)

    return (df_sales, primary_sku_col), None


# =========================================================================
# 模块一：销售与品类管理决策看板
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
        res, err = process_sales_data(uploaded_sales_file.getvalue(), uploaded_sales_file.name)
        if err:
            st.error(err)
            st.stop()

        df_sales, primary_sku_col = res

        # 时间筛选防错处理
        min_d = df_sales['Clean_Date'].min().date()
        max_d = df_sales['Clean_Date'].max().date()

        st.sidebar.markdown("---")
        st.sidebar.markdown("### 🗓️ 2. 时间范围筛选")
        date_range = st.sidebar.date_input("分析时间范围", [min_d, max_d], min_value=min_d, max_value=max_d)

        if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
            start_date, end_date = date_range[0], date_range[1]
        else:
            start_date = end_date = date_range[0] if isinstance(date_range, (list, tuple)) and len(date_range) > 0 else min_d

        time_mask = (df_sales['Clean_Date'].dt.date >= start_date) & (df_sales['Clean_Date'].dt.date <= end_date)
        filtered_sales = df_sales[time_mask]

        if filtered_sales.empty:
            st.warning("⚠️ 所选时间范围内无有效销售数据。")
            st.stop()

        # 1. KPI 概览
        st.subheader("📌 1. 渠道总体经营成果 (Executive Performance)")
        total_units = filtered_sales['Clean_Units'].sum()
        total_cost = filtered_sales['Clean_Cost'].sum()
        total_skus = filtered_sales[primary_sku_col].nunique()
        avg_order_value = total_cost / total_units if total_units > 0 else 0.0

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("销售总金额 (Total Cost)", f"${total_cost:,.2f}")
        c2.metric("销售总出货量 (Units)", f"{int(total_units):,} 件")
        c3.metric("均价 / 件单价 (ASP)", f"${avg_order_value:.2f}")
        c4.metric("活跃动销 SKU 数", f"{total_skus} 款")

        st.markdown("---")

        # 2. ABC 帕累托诊断
        st.subheader("🏆 2. 产品结构 ABC 帕累托诊断与 SKU 动销效率全景表")
        st.caption("A 类：贡献前 80% 销售额的核心爆款 | B 类：贡献 80%-95% 的腰部主力款 | C 类：贡献最后 5% 的尾部/滞销款")

        sku_summary = filtered_sales.groupby(primary_sku_col).agg({
            'Clean_Cost': 'sum',
            'Clean_Units': 'sum'
        }).reset_index()

        active_sales = filtered_sales[filtered_sales['Clean_Units'] > 0]
        active_metrics = active_sales.groupby(primary_sku_col).agg(
            Active_Days=('Clean_Date', 'nunique'),
            First_Sale=('Clean_Date', 'min'),
            Last_Sale=('Clean_Date', 'max')
        ).reset_index()

        sku_summary = pd.merge(sku_summary, active_metrics, on=primary_sku_col, how='left')
        sku_summary['Active_Days'] = sku_summary['Active_Days'].fillna(0)
        sku_summary['Active_Daily_Avg'] = np.where(sku_summary['Active_Days'] > 0, sku_summary['Clean_Units'] / sku_summary['Active_Days'], 0)

        sku_summary = sku_summary.sort_values(by='Clean_Cost', ascending=False).reset_index(drop=True)
        sku_summary['Cumulative_Cost'] = sku_summary['Clean_Cost'].cumsum()
        sku_summary['Cost_Share (%)'] = (sku_summary['Clean_Cost'] / total_cost * 100) if total_cost > 0 else 0
        sku_summary['Cumulative_Share (%)'] = (sku_summary['Cumulative_Cost'] / total_cost * 100) if total_cost > 0 else 0

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
                    '销售总额 (\()': '\){:,.2f}', '销售总量 (件)': '{:,.0f}', '可动销天数 (天)': '{:,.0f} 天',
                    '动销日均销量 (件/天)': '{:,.1f} 件/天', '销售额占比 (%)': '{:.2f}%', '累计占比 (%)': '{:.2f}%'
                }), use_container_width=True
            )

        with tab_a: render_sku_table(df_a)
        with tab_b: render_sku_table(df_b)
        with tab_c: render_sku_table(df_c)
        with tab_all: render_sku_table(sku_summary)

        st.markdown("---")

        # 3. 运营分析视角
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
            if 'Clean_State' in filtered_sales.columns:
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
# 模块二：月度多维度对比与趋势看板
# =========================================================================
elif module == "📅 月度多维度对比与趋势看板":
    st.title("📅 月度多维度对比与动销日均升降幅诊断看板")
    st.caption("聚焦动销效率：精准对比各个 SKU 在不同月份的『动销日均销量』升降幅度，自动排查上升爆款与下滑风险款")
    st.markdown("---")

    st.sidebar.header("⚙️ 1. 销售数据上传")
    uploaded_sales_file = st.sidebar.file_uploader("上传销售报表 (CSV/Excel)", type=["csv", "xlsx"], key="monthly_uploader")

    if not uploaded_sales_file:
        st.info("👋 请在侧边栏上传 Excel 或 CSV 格式的销售报表以开启月度对比。")
    else:
        res, err = process_sales_data(uploaded_sales_file.getvalue(), uploaded_sales_file.name)
        if err: st.error(err); st.stop()
        df_sales, primary_sku_col = res

        all_months = sorted(df_sales['YearMonth'].unique())
        st.sidebar.markdown("---")
        st.sidebar.markdown("### 🗓️ 2. 对比月份设定")
        selected_months = st.sidebar.multiselect("选择要对比的月份 (建议选2个月以上)", all_months, default=all_months)

        if not selected_months:
            st.warning("请在侧边栏至少选择一个月份！")
            st.stop()

        m_sales = df_sales[df_sales['YearMonth'].isin(selected_months)]

        active_m_sales = m_sales[m_sales['Clean_Units'] > 0]
        active_days_df = active_m_sales.groupby([primary_sku_col, 'YearMonth'])['Clean_Date'].nunique().reset_index()
        active_days_df.rename(columns={'Clean_Date': 'Active_Days'}, inplace=True)

        sku_monthly_df = m_sales.groupby([primary_sku_col, 'YearMonth']).agg(
            Monthly_Units=('Clean_Units', 'sum'),
            Monthly_Cost=('Clean_Cost', 'sum')
        ).reset_index()

        sku_monthly_df = pd.merge(sku_monthly_df, active_days_df, on=[primary_sku_col, 'YearMonth'], how='left')
        sku_monthly_df['Active_Days'] = sku_monthly_df['Active_Days'].fillna(0)
        sku_monthly_df['Active_Daily_Avg'] = np.where(sku_monthly_df['Active_Days'] > 0, sku_monthly_df['Monthly_Units'] / sku_monthly_df['Active_Days'], 0)

        sorted_sel_months = sorted(selected_months)
        has_comparison = len(sorted_sel_months) >= 2

        if has_comparison:
            latest_m = sorted_sel_months[-1]
            prev_m = sorted_sel_months[-2]

            avg_pivot = sku_monthly_df.pivot(index=primary_sku_col, columns='YearMonth', values='Active_Daily_Avg').fillna(0)
            units_pivot = sku_monthly_df.pivot(index=primary_sku_col, columns='YearMonth', values='Monthly_Units').fillna(0)
            days_pivot = sku_monthly_df.pivot(index=primary_sku_col, columns='YearMonth', values='Active_Days').fillna(0)

            # 防止选中的月份在 Pivot 中缺失导致的 KeyError
            for m in [prev_m, latest_m]:
                if m not in avg_pivot.columns: avg_pivot[m] = 0.0
                if m not in units_pivot.columns: units_pivot[m] = 0.0
                if m not in days_pivot.columns: days_pivot[m] = 0.0

            comp_df = pd.DataFrame(index=avg_pivot.index)
            comp_df['Prev_Active_Avg'] = avg_pivot[prev_m]
            comp_df['Latest_Active_Avg'] = avg_pivot[latest_m]
            comp_df['Prev_Units'] = units_pivot[prev_m]
            comp_df['Latest_Units'] = units_pivot[latest_m]
            comp_df['Prev_Active_Days'] = days_pivot[prev_m]
            comp_df['Latest_Active_Days'] = days_pivot[latest_m]

            comp_df['Diff_Active_Avg'] = comp_df['Latest_Active_Avg'] - comp_df['Prev_Active_Avg']
            comp_df['Growth_Active_Avg (%)'] = np.where(
                comp_df['Prev_Active_Avg'] > 0,
                ((comp_df['Latest_Active_Avg'] - comp_df['Prev_Active_Avg']) / comp_df['Prev_Active_Avg'] * 100),
                np.where(comp_df['Latest_Active_Avg'] > 0, 100.0, 0.0)
            )

            def classify_trend(r):
                diff = r['Diff_Active_Avg']
                if diff > 0.5: return '🚀 动销日均大幅上升'
                elif diff > 0: return '📈 动销日均微升'
                elif diff == 0: return '➖ 日均持平'
                elif diff >= -0.5: return '⚠️ 动销日均微降'
                else: return '📉 动销日均大幅下滑'

            comp_df['Trend_Status'] = comp_df.apply(classify_trend, axis=1)
            comp_df = comp_df.reset_index()

            up_skus = comp_df[comp_df['Diff_Active_Avg'] > 0].sort_values(by='Diff_Active_Avg', ascending=False)
            down_skus = comp_df[comp_df['Diff_Active_Avg'] < 0].sort_values(by='Diff_Active_Avg', ascending=True)

            st.subheader(f"⚡ 1. 动销日均效率变化总览 (`{prev_m}` ➡️ `{latest_m}`)")

            col_kpi1, col_kpi2, col_kpi3 = st.columns(3)
            col_kpi1.success(f"🚀 **动销日均上升 SKU 数**: **{len(up_skus)}** 款\n\n日均出货效率有所提升")
            col_kpi2.error(f"📉 **动销日均下滑 SKU 数**: **{len(down_skus)}** 款\n\n日均出货效率走低")
            col_kpi3.info(f"➖ **日均持平/无出单 SKU 数**: **{len(comp_df) - len(up_skus) - len(down_skus)}** 款")

            st.markdown("---")

            st.subheader("📊 2. 动销日均变化 Top 10 榜单可视化")
            g1, g2 = st.columns(2)

            with g1:
                st.markdown("##### 🚀 动销日均销量『上升幅度最大 Top 10』 (件/天)")
                top_up = up_skus.head(10)
                if not top_up.empty:
                    fig_up = px.bar(top_up, x=primary_sku_col, y='Diff_Active_Avg', text='Diff_Active_Avg', color_discrete_sequence=['#10B981'], labels={primary_sku_col: '产品 SKU', 'Diff_Active_Avg': '日均提升量 (件/天)'})
                    fig_up.update_traces(texttemplate='+%{text:.1f} 件/天', textposition='outside')
                    st.plotly_chart(fig_up, use_container_width=True)
                else:
                    st.info("暂无上升 SKU")

            with g2:
                st.markdown("##### 📉 动销日均销量『下滑幅度最大 Top 10』 (件/天)")
                top_down = down_skus.head(10)
                if not top_down.empty:
                    fig_down = px.bar(top_down, x=primary_sku_col, y='Diff_Active_Avg', text='Diff_Active_Avg', color_discrete_sequence=['#EF4444'], labels={primary_sku_col: '产品 SKU', 'Diff_Active_Avg': '日均下滑量 (件/天)'})
                    fig_down.update_traces(texttemplate='%{text:.1f} 件/天', textposition='outside')
                    st.plotly_chart(fig_down, use_container_width=True)
                else:
                    st.info("暂无下滑 SKU")

            st.markdown("---")

            st.subheader("📋 3. 动销日均升降幅 SKU 详细诊断清单")
            tab_up, tab_down, tab_pivot, tab_all = st.tabs([
                f"🚀 动销日均上升榜 ({len(up_skus)} 款)", 
                f"📉 动销日均下滑榜 ({len(down_skus)} 款)", 
                "📊 全月份动销日均透视矩阵",
                "📋 完整升降数据清单"
            ])

            def render_avg_table(df_subset):
                disp = df_subset.rename(columns={
                    primary_sku_col: '产品 SKU',
                    'Trend_Status': '趋势状态',
                    'Prev_Active_Avg': f'{prev_m} 动销日均 (件/天)',
                    'Latest_Active_Avg': f'{latest_m} 动销日均 (件/天)',
                    'Diff_Active_Avg': '日均变动量 (件/天)',
                    'Growth_Active_Avg (%)': '动销日均变化率 (%)',
                    'Prev_Units': f'{prev_m} 总销量 (件)',
                    'Latest_Units': f'{latest_m} 总销量 (件)'
                })
                st.dataframe(
                    disp[[
                        '产品 SKU', '趋势状态', f'{latest_m} 动销日均 (件/天)', f'{prev_m} 动销日均 (件/天)',
                        '日均变动量 (件/天)', '动销日均变化率 (%)', f'{latest_m} 总销量 (件)', f'{prev_m} 总销量 (件)'
                    ]].style.format({
                        f'{latest_m} 动销日均 (件/天)': '{:.1f}',
                        f'{prev_m} 动销日均 (件/天)': '{:.1f}',
                        '日均变动量 (件/天)': '{:+.1f}',
                        '动销日均变化率 (%)': '{:+.1f}%',
                        f'{latest_m} 总销量 (件)': '{:,.0f}',
                        f'{prev_m} 总销量 (件)': '{:,.0f}'
                    }), use_container_width=True
                )

            with tab_up:
                if not up_skus.empty: render_avg_table(up_skus)
                else: st.info("没有发现动销日均上升的 SKU。")

            with tab_down:
                if not down_skus.empty: render_avg_table(down_skus)
                else: st.info("没有发现动销日均下滑的 SKU。")

            with tab_pivot:
                p_avg = sku_monthly_df.pivot(index=primary_sku_col, columns='YearMonth', values='Active_Daily_Avg').fillna(0)
                p_avg['平均动销日均'] = p_avg.mean(axis=1)
                p_avg = p_avg.sort_values(by='平均动销日均', ascending=False)
                st.dataframe(p_avg.style.format("{:.1f} 件/天"), use_container_width=True)

            with tab_all:
                render_avg_table(comp_df.sort_values(by='Diff_Active_Avg', ascending=False))

        else:
            st.info("💡 请在侧边栏至少勾选 2 个月份，系统将自动对比这两个月份的『动销日均销量』！")


# =========================================================================
# 模块三：SPA 广告绩效诊断与运营看板
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
            df_ad = pd.read_csv(uploaded_ad_file) if uploaded_ad_file.name.endswith('.csv') else pd.read_excel(uploaded_ad_file)
        except Exception as e:
            st.error(f"读取广告文件失败: {e}"); st.stop()

        df_ad.columns = df_ad.columns.astype(str).str.strip()
        campaign_col = next((c for c in df_ad.columns if c.lower() in ['campaign name', 'campaign']), None)
        spend_col = next((c for c in df_ad.columns if c.lower() in ['spend', 'cost', 'ad spend']), None)
        sales_col = next((c for c in df_ad.columns if c.lower() in ['spa sales', 'sales', 'ad sales']), None)
        clicks_col = next((c for c in df_ad.columns if c.lower() in ['clicks', 'click']), None)
        impressions_col = next((c for c in df_ad.columns if c.lower() in ['impressions', 'impression']), None)
        roas_col = next((c for c in df_ad.columns if c.lower() in ['spa roas', 'roas']), None)
        omsid_col = next((c for c in df_ad.columns if c.lower() in ['promoted omsid number', 'omsid', 'promoted oms id']), None)

        if not campaign_col or not spend_col or not sales_col:
            st.error("解析失败！请确保广告表格中包含 Campaign Name, Spend, SPA Sales 列。")
            st.stop()

        # 清洗数值
        for col in [spend_col, sales_col, clicks_col, impressions_col, roas_col]:
            if col and col in df_ad.columns:
                df_ad[col] = pd.to_numeric(df_ad[col].astype(str).str.replace('$', '', regex=False).str.replace(',', '', regex=False).str.replace('%', '', regex=False), errors='coerce').fillna(0)

        # 补全 ROAS
        if roas_col not in df_ad.columns or df_ad[roas_col].sum() == 0:
            df_ad['Clean_ROAS'] = np.where(df_ad[spend_col] > 0, df_ad[sales_col] / df_ad[spend_col], 0)
            roas_col = 'Clean_ROAS'

        st.sidebar.markdown("---")
        st.sidebar.header("🎯 2. 运营优化阈值设置")
        target_roas = st.sidebar.number_input("目标 ROAS", min_value=0.1, value=2.5, step=0.5)
        waste_spend_threshold = st.sidebar.number_input("零转化报警 Spend 阈值 ($)", min_value=1.0, value=30.0, step=10.0)

        total_spend = df_ad[spend_col].sum()
        total_sales = df_ad[sales_col].sum()
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
        d1.error(f"🔻 **无效花费资金浪费**: `\({total_wasted_spend:,.2f}`\n\n**{len(wasted_df)}** 项 Spend ≥\){waste_spend_threshold} 且出单为 0。")
        d2.warning(f"⚠️ **低效出血点广告**: **{len(bleed_df)}** 项\n\nSpend ≥ ${waste_spend_threshold} 且 ROAS 远低于目标。")
        d3.success(f"🚀 **高 ROAS 扩量机会**: **{len(potential_df)}** 项\n\nROAS 达标（≥ {target_roas}），建议增加预算！")

        cols_to_show = [c for c in [campaign_col, omsid_col, spend_col, sales_col, roas_col, clicks_col] if c and c in df_ad.columns]

        tab1, tab2, tab3 = st.tabs(["🔥 重点排查：无转化浪费项", "⚠️ 低效出血点列表", "🚀 扩量提额潜力项"])
        with tab1:
            if not wasted_df.empty: st.dataframe(wasted_df[cols_to_show].sort_values(by=spend_col, ascending=False), use_container_width=True)
            else: st.info("🎉 暂未发现无转化浪费项。")
        with tab2:
            if not bleed_df.empty: st.dataframe(bleed_df[cols_to_show].sort_values(by=spend_col, ascending=False), use_container_width=True)
            else: st.info("暂未发现出血点广告。")
        with tab3:
            if not potential_df.empty: st.dataframe(potential_df[cols_to_show].sort_values(by=roas_col, ascending=False), use_container_width=True)
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
        res, err = process_sales_data(uploaded_sales_file.getvalue(), uploaded_sales_file.name)
        if err: st.error(err); st.stop()
        df_sales, sku_col = res

        # 近 30 天基准期
        max_date = df_sales['Clean_Date'].max()
        last_30_days_start = max_date - pd.Timedelta(days=30)
        recent_sales = df_sales[df_sales['Clean_Date'] >= last_30_days_start]

        if recent_sales.empty:
            st.warning("⚠️ 历史数据中找不到近 30 天的有效销售数据。")
            st.stop()

        active_recent = recent_sales[recent_sales['Clean_Units'] > 0]
        active_days_df = active_recent.groupby(sku_col)['Clean_Date'].nunique().reset_index().rename(columns={'Clean_Date': 'Active_Days'})

        sku_recent = recent_sales.groupby(sku_col).agg(
            Recent_Units=('Clean_Units', 'sum'),
            Recent_Cost=('Clean_Cost', 'sum')
        ).reset_index()

        sku_recent = pd.merge(sku_recent, active_days_df, on=sku_col, how='left')
        sku_recent['Active_Days'] = sku_recent['Active_Days'].fillna(0)
        sku_recent['Avg_Price'] = np.where(sku_recent['Recent_Units'] > 0, sku_recent['Recent_Cost'] / sku_recent['Recent_Units'], 0)
        sku_recent['Active_Daily_Avg'] = np.where(sku_recent['Active_Days'] > 0, sku_recent['Recent_Units'] / sku_recent['Active_Days'], 0)

        last_month_cost = sku_recent['Recent_Cost'].sum()
        last_month_units = sku_recent['Recent_Units'].sum()

        st.sidebar.markdown("---")
        st.sidebar.markdown("### ⚙️ 2. 下月目标设定参数")

        target_mode = st.sidebar.radio("目标制定方式", ["按销售额增长率 (%)", "按自定义总销售额 ($)"])

        if target_mode == "按销售额增长率 (%)":
            growth_rate = st.sidebar.number_input("下月目标增长率 (%)", value=10.0, step=1.0)
            target_total_cost = last_month_cost * (1 + growth_rate / 100)
        else:
            target_total_cost = st.sidebar.number_input("下月目标总金额 ($)", value=float(round(last_month_cost * 1.1, 2)))
            growth_rate = ((target_total_cost - last_month_cost) / last_month_cost * 100) if last_month_cost > 0 else 0

        target_days = st.sidebar.number_input("下月份天数 (天)", min_value=28, max_value=31, value=30)

        # 1. 目标 KPI
        st.subheader("📌 1. 下月全盘经营目标概览")
        t1, t2, t3, t4 = st.columns(4)
        t1.metric("近 30 天实际完成额", f"${last_month_cost:,.2f}")
        t2.metric("下月目标销售额", f"${target_total_cost:,.2f}", delta=f"{growth_rate:+.1f}% 增长")

        avg_price_all = last_month_cost / last_month_units if last_month_units > 0 else 0
        target_total_units = target_total_cost / avg_price_all if avg_price_all > 0 else 0

        t3.metric("预估需出货总件数", f"{int(target_total_units):,} 件")
        t4.metric("下月日均目标营收", f"${target_total_cost / target_days:,.2f} /天")

        st.markdown("---")

        # 2. 算法自动拆解至 SKU
        st.subheader("📦 2. 各 SKU 下月目标销量与动销日均拆解")

        # 计算权重 (基于过去 30 天销售额占比)
        sku_recent['Cost_Weight'] = sku_recent['Recent_Cost'] / last_month_cost if last_month_cost > 0 else 0
        sku_recent['Target_Cost'] = sku_recent['Cost_Weight'] * target_total_cost
        sku_recent['Target_Units'] = np.where(sku_recent['Avg_Price'] > 0, sku_recent['Target_Cost'] / sku_recent['Avg_Price'], 0)
        sku_recent['Target_Daily_Avg'] = sku_recent['Target_Units'] / target_days

        sku_target_df = sku_recent.sort_values(by='Target_Cost', ascending=False).reset_index(drop=True)

        st.markdown("##### 💡 拆解推演结果明细")
        disp_target = sku_target_df.rename(columns={
            sku_col: '产品 SKU',
            'Recent_Cost': '近 30 天销售额 ($)',
            'Recent_Units': '近 30 天销量 (件)',
            'Avg_Price': '预估均价 ($)',
            'Cost_Weight': '销售权重占比',
            'Target_Cost': '下月目标销售额 ($)',
            'Target_Units': '下月目标销量 (件)',
            'Target_Daily_Avg': '下月目标日均 (件/天)'
        })

        st.dataframe(
            disp_target[[
                '产品 SKU', '销售权重占比', '预估均价 ($)', 
                '下月目标销售额 ($)', '下月目标销量 (件)', '下月目标日均 (件/天)',
                '近 30 天销售额 ($)', '近 30 天销量 (件)'
            ]].style.format({
                '销售权重占比': '{:.2%}',
                '预估均价 (\()': '\){:,.2f}',
                '下月目标销售额 (\()': '\){:,.2f}',
                '下月目标销量 (件)': '{:,.0f}',
                '下月目标日均 (件/天)': '{:,.1f}',
                '近 30 天销售额 (\()': '\){:,.2f}',
                '近 30 天销量 (件)': '{:,.0f}'
            }), use_container_width=True
        )

        # 目标拆解可视化
        fig_target = px.bar(
            sku_target_df.head(15), x=sku_col, y='Target_Cost', text='Target_Units',
            title="下月 Top 15 SKU 目标销售额与预估出货量拆解",
            labels={sku_col: '产品 SKU', 'Target_Cost': '目标销售额 ($)'},
            color_discrete_sequence=['#3B82F6']
        )
        fig_target.update_traces(texttemplate='%{text:,.0f} 件', textposition='outside')
        st.plotly_chart(fig_target, use_container_width=True)
