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

# 侧边栏：顶部大模块选择
st.sidebar.title("📌 功能看板导航")
module = st.sidebar.selectbox(
    "请选择分析模块",
    ["📊 销售与品类管理决策看板", "📢 SPA 广告绩效诊断与运营看板"]
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

        # 优先选择 SKU 列（根据用户偏好）
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

        # -----------------------------------------------------------------
        # 1. 管理层高阶 KPI 概览 (Executive Overview)
        # -----------------------------------------------------------------
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

        # -----------------------------------------------------------------
        # 2. ABC 帕累托爆款/滞销分析（含详细 SKU 列表）
        # -----------------------------------------------------------------
        st.subheader("🏆 2. 产品结构 ABC 帕累托诊断 (含详细 SKU 明细列表)")
        st.caption("A 类：贡献前 80% 销售额的核心爆款 | B 类：贡献 80%-95% 的腰部主力款 | C 类：贡献最后 5% 的尾部/滞销款")

        # 汇总各 SKU 的销售表现
        sku_summary = filtered_sales.groupby(primary_sku_col).agg({
            'Clean_Cost': 'sum',
            'Clean_Units': 'sum',
            'Clean_Date': ['nunique', 'min', 'max']
        }).reset_index()

        sku_summary.columns = [primary_sku_col, 'Total_Cost', 'Total_Units', 'Active_Days', 'First_Sale', 'Last_Sale']
        sku_summary = sku_summary.sort_values(by='Total_Cost', ascending=False).reset_index(drop=True)

        # 累计占比计算 ABC 分级
        sku_summary['Cumulative_Cost'] = sku_summary['Total_Cost'].cumsum()
        sku_summary['Cost_Share (%)'] = (sku_summary['Total_Cost'] / total_cost) * 100 if total_cost > 0 else 0
        sku_summary['Cumulative_Share (%)'] = (sku_summary['Cumulative_Cost'] / total_cost) * 100 if total_cost > 0 else 0

        def assign_abc(pct):
            if pct <= 80:
                return 'A 类 (核心爆款)'
            elif pct <= 95:
                return 'B 类 (腰部主力)'
            else:
                return 'C 类 (尾部/滞销)'

        sku_summary['ABC_Class'] = sku_summary['Cumulative_Share (%)'].apply(assign_abc)

        abc_counts = sku_summary['ABC_Class'].value_counts()
        abc_costs = sku_summary.groupby('ABC_Class')['Total_Cost'].sum()

        col_abc1, col_abc2 = st.columns([1, 1])
        with col_abc1:
            fig_abc = px.pie(
                sku_summary,
                values='Total_Cost',
                names='ABC_Class',
                title="ABC 分级销售额占比构成",
                hole=0.4,
                color='ABC_Class',
                color_discrete_map={'A 类 (核心爆款)': '#10B981', 'B 类 (腰部主力)': '#F59E0B', 'C 类 (尾部/滞销)': '#EF4444'}
            )
            fig_abc.update_traces(textinfo='percent+label')
            st.plotly_chart(fig_abc, use_container_width=True)

        with col_abc2:
            st.markdown("### 💡 帕累托品类优化诊断建议")
            a_count = abc_counts.get('A 类 (核心爆款)', 0)
            b_count = abc_counts.get('B 类 (腰部主力)', 0)
            c_count = abc_counts.get('C 类 (尾部/滞销)', 0)
            
            st.success(f"🟢 **A 类核心爆款 ({a_count} 款 SKU)**：贡献了全盘 **80%** 的营收！建议运营重点监控备货与供应链，防止断货。")
            st.warning(f"🟡 **B 类腰部潜力 ({b_count} 款 SKU)**：贡献了 **15%** 的营收，可增加广告投放尝试拉升为 A 类。")
            st.error(f"🔴 **C 类尾部滞销 ({c_count} 款 SKU)**：仅贡献 **5%** 的营收，存在资金挤压风险。建议排查是否需要清仓下架。")

        # -----------------------------------------------------------------
        # 详细 SKU 列表展示（标签页）
        # -----------------------------------------------------------------
        st.markdown("### 📋 各分类 SKU 详细名单与数据明细")

        df_a = sku_summary[sku_summary['ABC_Class'] == 'A 类 (核心爆款)'].copy()
        df_b = sku_summary[sku_summary['ABC_Class'] == 'B 类 (腰部主力)'].copy()
        df_c = sku_summary[sku_summary['ABC_Class'] == 'C 类 (尾部/滞销)'].copy()

        tab_a, tab_b, tab_c, tab_all = st.tabs([
            f"🟢 A 类核心爆款 ({len(df_a)} 款)", 
            f"🟡 B 类腰部潜力 ({len(df_b)} 款)", 
            f"🔴 C 类尾部滞销 ({len(df_c)} 款)",
            f"📊 全量 SKU 排行榜 ({len(sku_summary)} 款)"
        ])

        def render_sku_table(df_subset):
            display_df = df_subset.rename(columns={
                primary_sku_col: '产品 SKU',
                'Total_Cost': '销售总额 ($)',
                'Total_Units': '销售总量 (件)',
                'Cost_Share (%)': '销售额占比 (%)',
                'Cumulative_Share (%)': '累计占比 (%)',
                'Active_Days': '有动销天数',
                'First_Sale': '首次出单日期',
                'Last_Sale': '最近出单日期'
            })
            display_df['首次出单日期'] = display_df['首次出单日期'].dt.strftime('%Y-%m-%d')
            display_df['最近出单日期'] = display_df['最近出单日期'].dt.strftime('%Y-%m-%d')

            st.dataframe(
                display_df[[
                    '产品 SKU', '销售总额 ($)', '销售总量 (件)', '销售额占比 (%)', 
                    '累计占比 (%)', '有动销天数', '首次出单日期', '最近出单日期'
                ]].style.format({
                    '销售总额 ($)': '${:,.2f}',
                    '销售总量 (件)': '{:,.0f}',
                    '销售额占比 (%)': '{:.2f}%',
                    '累计占比 (%)': '{:.2f}%',
                    '有动销天数': '{:,.0f} 天'
                }),
                use_container_width=True
            )

        with tab_a:
            st.caption("🟢 **A 类核心爆款明细**：以下产品为店铺主要利润来源，请重点保持库存充足与 Listing 稳定。")
            render_sku_table(df_a)

        with tab_b:
            st.caption("🟡 **B 类腰部潜力明细**：具有一定出货量，建议优化 Listing 关键词或增加 SPA 广告测试扩量。")
            render_sku_table(df_b)

        with tab_c:
            st.caption("🔴 **C 类尾部滞销明细**：长尾出货或长期无动销款，建议核查库存仓储费，评估促销或清仓。")
            render_sku_table(df_c)

        with tab_all:
            st.caption("📊 **全量 SKU 按销售额降序总览**")
            render_sku_table(sku_summary)

        st.markdown("---")

        # -----------------------------------------------------------------
        # 3. 视角切换：单 SKU 运营详情 vs 全美地理仓储布局
        # -----------------------------------------------------------------
        st.sidebar.markdown("---")
        st.sidebar.markdown("### 🔍 3. 运营分析视角")
        view_mode = st.sidebar.radio("选择细分视角", ["📦 单产品 SKU 动销深度分析", "🗺️ 全美物流仓储与地理分布", "🏷️ 品类占比与结构分析"])

        if view_mode == "📦 单产品 SKU 动销深度分析":
            st.subheader("📦 单产品 SKU 动销效率与日均走势")
            selected_sku = st.sidebar.selectbox(f"选择 {primary_sku_col}", sku_summary[primary_sku_col].unique())

            sku_df = filtered_sales[filtered_sales[primary_sku_col].astype(str) == str(selected_sku)].sort_values('Clean_Date')

            if not sku_df.empty:
                sku_info = sku_df.iloc[0]
                p_name = sku_info.get('产品名称', '未填写')
                p_operator = sku_info.get('运营', '未分配')

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
                s3.metric("动销率 (Active Sales Rate)", f"{active_rate:.1f}%", help="有产生销售的天数占比")
                s4.metric("动销日均销量", f"{active_avg:.1f} 件/天", delta=f"自然日均: {overall_avg:.1f}")

                fig_sku_trend = go.Figure()
                fig_sku_trend.add_trace(go.Bar(x=daily_summary['Clean_Date'], y=daily_summary['Clean_Units'], name='销量 (件)', marker_color='#3B82F6'))
                fig_sku_trend.add_trace(go.Scatter(x=daily_summary['Clean_Date'], y=daily_summary['Clean_Cost'], name='金额 ($)', yaxis='y2', line=dict(color='#10B981', width=2.5)))
                fig_sku_trend.update_layout(title=f"SKU: {selected_sku} - 每日销量与金额趋势", hovermode="x unified", yaxis=dict(title="销量 (件)"), yaxis2=dict(title="金额 ($)", overlaying='y', side='right'))
                st.plotly_chart(fig_sku_trend, use_container_width=True)

        elif view_mode == "🗺️ 全美物流仓储与地理分布":
            st.subheader("🗺️ 全美各州销量热力分布 (指导海外仓与 3PL 分仓备货)")
            
            if state_col and 'Clean_State' in filtered_sales.columns:
                state_df = filtered_sales.groupby('Clean_State').agg({'Clean_Units': 'sum', 'Clean_Cost': 'sum'}).reset_index()
                state_df['Share_Pct'] = (state_df['Clean_Units'] / total_units) * 100 if total_units > 0 else 0
                state_df = state_df.sort_values(by='Clean_Units', ascending=False)

                m1, m2 = st.columns([2, 1])
                with m1:
                    fig_map = px.choropleth(
                        state_df, locations='Clean_State', locationmode="USA-states", color='Clean_Units', scope="usa",
                        color_continuous_scale="Viridis", hover_data={'Clean_Units': ':,', 'Clean_Cost': ':$,.2f', 'Share_Pct': ':.2f%'}, title="美国各州出货量热力图"
                    )
                    st.plotly_chart(fig_map, use_container_width=True)

                with m2:
                    st.markdown("### 🏆 Top 10 销量集中州")
                    st.dataframe(
                        state_df.head(10).rename(columns={'Clean_State': '州 (State)', 'Clean_Units': '销量 (件)', 'Clean_Cost': '销售额 ($)', 'Share_Pct': '占比 (%)'}).style.format({'销量 (件)': '{:,.0f}', '销售额 ($)': '${:,.2f}', '占比 (%)': '{:.2f}%'}),
                        use_container_width=True
                    )
            else:
                st.warning("数据表中未查找到 `ShipTo State` 或 `State` 列。")

        else:
            st.subheader("🏷️ 产品品类 (Category) 销售结构分析")
            cat_df = filtered_sales.groupby('Clean_Category').agg({'Clean_Units': 'sum', 'Clean_Cost': 'sum', primary_sku_col: 'nunique'}).reset_index()
            cat_df = cat_df.sort_values(by='Clean_Cost', ascending=False)

            fig_cat = px.bar(cat_df, x='Clean_Category', y='Clean_Cost', text='Clean_Cost', color='Clean_Units', title="各品类销售额与出货件数表现", labels={'Clean_Category': '品类', 'Clean_Cost': '销售额 ($)'})
            fig_cat.update_traces(texttemplate='$%{text:,.0f}', textposition='outside')
            st.plotly_chart(fig_cat, use_container_width=True)


# =========================================================================
# 模块二：广告绩效诊断与运营看板 (SPA Ad Operations & Diagnostics Dashboard)
# =========================================================================
else:
    st.title("📢 Home Depot SPA 广告绩效诊断与运营决策看板")
    st.caption("聚焦运营动作：止损排查、高 ROAS 扩量、转化率诊断与预算分配")
    st.markdown("---")

    st.sidebar.header("⚙️ 1. 广告数据上传")
    uploaded_ad_file = st.sidebar.file_uploader("上传 Home Depot 广告报表 (CSV/Excel)", type=["csv", "xlsx"], key="ad_uploader")

    if not uploaded_ad_file:
        st.info("👋 请在下方或左侧侧边栏上传您的 Home Depot SPA 广告报表 (例如：工作簿6.xlsx)。")
        uploaded_ad_file = st.file_uploader("点击或拖拽上传 Home Depot 广告报表 (CSV/Excel)", type=["csv", "xlsx"], key="main_ad_uploader")

    if uploaded_ad_file:
        try:
            if uploaded_ad_file.name.endswith('.csv'):
                df_ad = pd.read_csv(uploaded_ad_file)
            else:
                df_ad = pd.read_excel(uploaded_ad_file)
        except Exception as e:
            st.error(f"读取广告文件失败，请检查文件格式: {e}")
            st.stop()

        df_ad.columns = df_ad.columns.str.strip()

        campaign_col = next((c for c in df_ad.columns if c in ['Campaign Name', 'Campaign']), None)
        spend_col = next((c for c in df_ad.columns if c in ['Spend', 'Cost', 'Ad Spend']), None)
        sales_col = next((c for c in df_ad.columns if c in ['SPA Sales', 'Sales', 'Ad Sales']), None)
        clicks_col = next((c for c in df_ad.columns if c in ['Clicks', 'Click']), None)
        impressions_col = next((c for c in df_ad.columns if c in ['Impressions', 'Impression']), None)
        roas_col = next((c for c in df_ad.columns if c in ['SPA ROAS', 'ROAS']), None)
        omsid_col = next((c for c in df_ad.columns if c in ['Promoted OMSID Number', 'OMSID', 'Promoted OMS ID']), None)
        dept_col = next((c for c in df_ad.columns if c in ['Promoted Dept Name', 'Promoted Dept Number', 'Dept']), None)

        if not campaign_col or not spend_col or not sales_col:
            st.error(f"解析失败！请确保广告表包含关键列（Campaign Name, Spend, SPA Sales）。当前识别到的表头为: {list(df_ad.columns)}")
            st.stop()

        for col in [spend_col, sales_col, clicks_col, impressions_col, roas_col]:
            if col and col in df_ad.columns:
                df_ad[col] = pd.to_numeric(df_ad[col].astype(str).str.replace('$', '').str.replace(',', '').str.replace('%', ''), errors='coerce').fillna(0)

        st.sidebar.markdown("---")
        st.sidebar.header("🎯 2. 运营优化阈值设置")
        target_roas = st.sidebar.number_input("目标 ROAS (Target ROAS)", min_value=0.1, value=2.5, step=0.5)
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
        c4.metric("总点击量 / 平均 CPC", f"{int(total_clicks):,} 次", delta=f"${overall_cpc:.2f}/点击", delta_color="off")
        c5.metric("总曝光量 / CTR", f"{int(total_impressions):,} 次", delta=f"{overall_ctr:.2f}% CTR", delta_color="off")

        st.markdown("---")

        st.subheader("🚨 2. 运营调优诊断中心 (Actionable Insights)")
        wasted_df = df_ad[(df_ad[spend_col] >= waste_spend_threshold) & (df_ad[sales_col] == 0)]
        total_wasted_spend = wasted_df[spend_col].sum()
        bleed_df = df_ad[(df_ad[spend_col] >= waste_spend_threshold) & (df_ad[sales_col] > 0) & (df_ad[roas_col] < (target_roas * 0.6))]
        potential_df = df_ad[(df_ad[roas_col] >= target_roas) & (df_ad[spend_col] < (total_spend / max(len(df_ad), 1)))]

        d1, d2, d3 = st.columns(3)
        with d1:
            st.error(f"🔻 **无效花费资金浪费**: `${total_wasted_spend:,.2f}`")
            st.caption(f"存在 **{len(wasted_df)}** 个项目 Spend ≥ ${waste_spend_threshold} 且出单数为 0。建议立即降低出价或暂停！")
        with d2:
            st.warning(f"⚠️ **低效出血点广告**: **{len(bleed_df)}** 项")
            st.caption(f"Spend ≥ ${waste_spend_threshold} 且 ROAS 远低于目标（<{target_roas * 0.6:.2f}）。建议否定不相关词。")
        with d3:
            st.success(f"🚀 **高 ROAS 扩量机会**: **{len(potential_df)}** 项")
            st.caption(f"ROAS 达标（≥ {target_roas}）但预算占比偏低。建议增加 Daily Budget！")

        tab1, tab2, tab3 = st.tabs(["🔥 重点排查：无转化浪费项", "⚠️ 低效出血点列表", "🚀 扩量提额潜力项"])
        with tab1:
            if not wasted_df.empty:
                st.dataframe(wasted_df[[campaign_col, omsid_col, spend_col, clicks_col, impressions_col]].sort_values(by=spend_col, ascending=False).style.format({spend_col: '${:,.2f}', clicks_col: '{:,.0f}', impressions_col: '{:,.0f}'}), use_container_width=True)
            else:
                st.info("🎉 暂未发现满足该阈值的纯浪费广告项目。")

        with tab2:
            if not bleed_df.empty:
                st.dataframe(bleed_df[[campaign_col, omsid_col, spend_col, sales_col, roas_col, clicks_col]].sort_values(by=spend_col, ascending=False).style.format({spend_col: '${:,.2f}', sales_col: '${:,.2f}', roas_col: '{:.2f}', clicks_col: '{:,.0f}'}), use_container_width=True)
            else:
                st.info("暂未发现低效出血点广告。")

        with tab3:
            if not potential_df.empty:
                st.dataframe(potential_df[[campaign_col, omsid_col, spend_col, sales_col, roas_col]].sort_values(by=roas_col, ascending=False).style.format({spend_col: '${:,.2f}', sales_col: '${:,.2f}', roas_col: '{:.2f}'}), use_container_width=True)
            else:
                st.info("暂未识别到潜力广告。")

        st.markdown("---")

        st.subheader("🧩 3. Campaign 广告活动四象限矩阵 (Strategy Matrix)")
        camp_summary = df_ad.groupby(campaign_col).agg({spend_col: 'sum', sales_col: 'sum', clicks_col: 'sum' if clicks_col else 'count', impressions_col: 'sum' if impressions_col else 'count'}).reset_index()
        camp_summary['ROAS'] = camp_summary.apply(lambda row: row[sales_col] / row[spend_col] if row[spend_col] > 0 else 0, axis=1)
        avg_camp_spend = camp_summary[spend_col].median()

        fig_quadrant = px.scatter(camp_summary, x=spend_col, y='ROAS', size=sales_col, hover_name=campaign_col, color='ROAS', color_continuous_scale='RdYlGn', title="Campaign Spend vs ROAS 四象限诊断（气泡大小 = 销售额）", labels={spend_col: '广告花费 Spend ($)', 'ROAS': 'ROAS'})
        fig_quadrant.add_hline(y=target_roas, line_dash="dash", line_color="red", annotation_text=f"目标 ROAS ({target_roas})")
        fig_quadrant.add_vline(x=avg_camp_spend, line_dash="dash", line_color="blue", annotation_text=f"中位数 Spend (${avg_camp_spend:.1f})")
        st.plotly_chart(fig_quadrant, use_container_width=True)

        st.markdown("---")

        st.subheader("📦 4. 推广产品 (OMSID) 流量与转化诊断")
        if omsid_col:
            oms_summary = df_ad.groupby(omsid_col).agg({spend_col: 'sum', sales_col: 'sum', clicks_col: 'sum' if clicks_col else 'count', impressions_col: 'sum' if impressions_col else 'count'}).reset_index()
            oms_summary['ROAS'] = oms_summary.apply(lambda row: row[sales_col] / row[spend_col] if row[spend_col] > 0 else 0, axis=1)
            oms_summary['CTR (%)'] = oms_summary.apply(lambda row: (row[clicks_col] / row[impressions_col]) * 100 if row[impressions_col] > 0 else 0, axis=1)
            oms_summary = oms_summary.sort_values(by=spend_col, ascending=False)

            col_o1, col_o2 = st.columns(2)
            with col_o1:
                fig_oms_bar = px.bar(oms_summary.head(10), x=omsid_col, y=[spend_col, sales_col], barmode='group', title="TOP 10 花费 OMSID 的 Spend 与 Sales 对比", labels={'value': '金额 ($)', omsid_col: 'OMS ID'})
                st.plotly_chart(fig_oms_bar, use_container_width=True)

            with col_o2:
                fig_ctr_roas = px.scatter(oms_summary, x='CTR (%)', y='ROAS', size=spend_col, hover_name=omsid_col, title="OMSID 点击率 (CTR) vs ROAS（气泡大小 = Spend）", labels={'CTR (%)': '点击率 CTR (%)', 'ROAS': 'ROAS'})
                st.plotly_chart(fig_ctr_roas, use_container_width=True)

            st.dataframe(oms_summary.rename(columns={omsid_col: 'OMS ID', spend_col: '广告花费 ($)', sales_col: '广告销售额 ($)', clicks_col: '点击数', impressions_col: '曝光数', 'ROAS': 'ROAS', 'CTR (%)': '点击率 (%)'}).style.format({'广告花费 ($)': '${:,.2f}', '广告销售额 ($)': '${:,.2f}', '点击数': '{:,.0f}', '曝光数': '{:,.0f}', 'ROAS': '{:.2f}', 'CTR (%)': '{:.2f}%'}), use_container_width=True)
