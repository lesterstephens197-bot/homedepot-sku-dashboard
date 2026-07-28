import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# 页面基础配置
st.set_page_config(
    page_title="Home Depot 销售与广告综合分析看板",
    page_icon="📊",
    layout="wide"
)

# 侧边栏：顶部大模块选择
st.sidebar.title("📌 功能看板导航")
module = st.sidebar.selectbox(
    "请选择分析模块",
    ["📊 销售与品类分析看板", "📢 SPA 广告绩效分析看板"]
)

st.sidebar.markdown("---")

# =========================================================================
# 模块一：销售与品类分析看板 (Sales & Category Dashboard)
# =========================================================================
if module == "📊 销售与品类分析看板":
    st.title("📊 Home Depot 销售与品类深度分析看板")
    st.markdown("---")

    st.sidebar.header("⚙️ 销售数据设置")
    uploaded_sales_file = st.sidebar.file_uploader("上传 Home Depot 销售报表 (CSV/Excel)", type=["csv", "xlsx"], key="sales_uploader")

    if not uploaded_sales_file:
        st.info("👋 请在左侧侧边栏上传 Excel 或 CSV 格式的销售报表。")
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

        # 表头字段匹配
        date_col = next((c for c in df_sales.columns if c in ['日期', 'Date', 'sales_date']), None)
        sales_col = next((c for c in df_sales.columns if c in ['销量', 'Units Sold', 'Units', 'Quantity']), None)
        cost_col = next((c for c in df.columns if c in ['Total Cost', 'Cost', '金额', '总金额']), None)
        category_col = next((c for c in df.columns if c in ['产品名称', 'Category', '品类', '品类名称']), None)
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

        min_d = df_sales['Clean_Date'].min().date()
        max_d = df_sales['Clean_Date'].max().date()

        st.sidebar.markdown("### 1. 时间范围筛选")
        date_range = st.sidebar.date_input("分析时间范围", [min_d, max_d], min_value=min_d, max_value=max_d)

        start_date = date_range[0] if len(date_range) >= 1 else min_d
        end_date = date_range[1] if len(date_range) == 2 else max_d

        time_mask = (df_sales['Clean_Date'].dt.date >= start_date) & (df_sales['Clean_Date'].dt.date <= end_date)
        filtered_sales = df_sales[time_mask]

        st.sidebar.markdown("---")
        st.sidebar.markdown("### 2. 分析视角选择")
        view_mode = st.sidebar.radio("选择销售分析视角", ["📦 单产品 SKU 深度看板", "🏷️ 产品品类 (产品名称) 汇总看板", "🌐 全大盘总体看板"])

        # 视角 1: 单 SKU
        if view_mode == "📦 单产品 SKU 深度看板":
            primary_sku_col = st.sidebar.selectbox("分析主键列", sku_fields_available, index=0)
            sku_list = sorted(filtered_sales[primary_sku_col].dropna().astype(str).unique())
            selected_sku = st.sidebar.selectbox(f"选择 {primary_sku_col}", sku_list)

            sku_df = filtered_sales[filtered_sales[primary_sku_col].astype(str) == selected_sku].sort_values('Clean_Date')

            if not sku_df.empty:
                sku_info = sku_df.iloc[0]
                p_sku = sku_info.get('产品SKU', sku_info.get('SKU', '无'))
                p_name = sku_info.get('产品名称', '未填写')
                p_operator = sku_info.get('运营', '未分配')

                total_units = sku_df['Clean_Units'].sum()
                total_cost = sku_df['Clean_Cost'].sum()

                daily_summary = sku_df.groupby('Clean_Date').agg({'Clean_Units': 'sum', 'Clean_Cost': 'sum'}).reset_index()
                total_days = (daily_summary['Clean_Date'].max() - daily_summary['Clean_Date'].min()).days + 1
                active_days = len(daily_summary[daily_summary['Clean_Units'] > 0])
                overall_avg = total_units / total_days if total_days > 0 else 0
                active_avg = total_units / active_days if active_days > 0 else 0

                st.subheader(f"📌 产品 SKU: {selected_sku}（{p_name}）")
                st.caption(f"运营负责人: {p_operator}")

                c1, c2, c3, c4 = st.columns(4)
                c1.metric("区间总销量 (Units)", f"{int(total_units):,} 件")
                c2.metric("区间总金额 (Total Cost)", f"${total_cost:,.2f}")
                c3.metric("全量自然日均销量", f"{overall_avg:.1f} 件/天")
                c4.metric("动销日均销量", f"{active_avg:.1f} 件/天")

                st.markdown("---")
                st.subheader("📈 每日销量 (Units) 与 销售金额 (Total Cost) 走势")
                fig_twin = go.Figure()
                fig_twin.add_trace(go.Bar(x=daily_summary['Clean_Date'], y=daily_summary['Clean_Units'], name='销量 (件)', marker_color='#3B82F6', opacity=0.7))
                fig_twin.add_trace(go.Scatter(x=daily_summary['Clean_Date'], y=daily_summary['Clean_Cost'], name='Total Cost ($)', yaxis='y2', line=dict(color='#EF4444', width=2.5)))
                fig_twin.update_layout(hovermode="x unified", xaxis_title="日期", yaxis=dict(title="销量 (件)"), yaxis2=dict(title="Total Cost ($)", overlaying='y', side='right'))
                st.plotly_chart(fig_twin, use_container_width=True)

                if state_col and 'Clean_State' in sku_df.columns:
                    st.markdown("---")
                    st.subheader("🗺️ 该 SKU 全美州级销量地图")
                    state_df = sku_df.groupby('Clean_State').agg({'Clean_Units': 'sum', 'Clean_Cost': 'sum'}).reset_index()
                    state_df['Share_Pct'] = (state_df['Clean_Units'] / total_units) * 100 if total_units > 0 else 0

                    fig_map = px.choropleth(
                        state_df, locations='Clean_State', locationmode="USA-states", color='Clean_Units', scope="usa",
                        color_continuous_scale="Reds", hover_data={'Clean_Units': ':,', 'Clean_Cost': ':$,.2f', 'Share_Pct': ':.2f%'}, title="各州销量热力分布"
                    )
                    st.plotly_chart(fig_map, use_container_width=True)

        # 视角 2: 品类汇总
        elif view_mode == "🏷️ 产品品类 (产品名称) 汇总看板":
            st.subheader("🏷️ 产品品类 (产品名称) 销售数据看板")
            category_summary = filtered_sales.groupby('Clean_Category').agg({'Clean_Units': 'sum', 'Clean_Cost': 'sum', '产品SKU': 'nunique'}).reset_index().rename(columns={'产品SKU': 'SKU数量'})
            total_cat_units = category_summary['Clean_Units'].sum()
            total_cat_cost = category_summary['Clean_Cost'].sum()

            category_summary['Sales_Share'] = (category_summary['Clean_Units'] / total_cat_units) * 100 if total_cat_units > 0 else 0
            category_summary['Cost_Share'] = (category_summary['Clean_Cost'] / total_cat_cost) * 100 if total_cat_cost > 0 else 0
            category_summary = category_summary.sort_values(by='Clean_Cost', ascending=False)

            c1, c2, c3 = st.columns(3)
            c1.metric("全品类总销量", f"{int(total_cat_units):,} 件")
            c2.metric("全品类总销售额 (Total Cost)", f"${total_cat_cost:,.2f}")
            c3.metric("涵盖品类数量", f"{len(category_summary)} 个品类")

            st.markdown("---")
            col_cat1, col_cat2 = st.columns(2)
            with col_cat1:
                fig_cat_bar = px.bar(category_summary, x='Clean_Category', y='Clean_Cost', text='Clean_Cost', title="各品类销售额 (Total Cost) 排名", color='Clean_Cost', color_continuous_scale='Blues')
                fig_cat_bar.update_traces(texttemplate='$%{text:,.0f}', textposition='outside')
                st.plotly_chart(fig_cat_bar, use_container_width=True)

            with col_cat2:
                fig_cat_pie = px.pie(category_summary, values='Clean_Units', names='Clean_Category', title="各品类销量 (件数) 占比分布", hole=0.4)
                fig_cat_pie.update_traces(textinfo='percent+label')
                st.plotly_chart(fig_cat_pie, use_container_width=True)

            st.markdown("---")
            st.markdown("### 📋 品类数据明细表")
            st.dataframe(category_summary.rename(columns={'Clean_Category': '产品名称 (品类)', 'Clean_Units': '总销量 (件)', 'Clean_Cost': '总金额 Total Cost ($)', 'Sales_Share': '销量占比 (%)', 'Cost_Share': '销售额占比 (%)'}).style.format({'总销量 (件)': '{:,.0f}', '总金额 Total Cost ($)': '${:,.2f}', '销量占比 (%)': '{:.2f}%', '销售额占比 (%)': '{:.2f}%'}), use_container_width=True)

        # 视角 3: 全大盘
        else:
            st.subheader("🌐 Home Depot 全大盘销售数据概览")
            total_units = filtered_sales['Clean_Units'].sum()
            total_cost = filtered_sales['Clean_Cost'].sum()
            total_orders = filtered_sales['PO Number'].nunique() if 'PO Number' in filtered_sales.columns else len(filtered_sales)

            c1, c2, c3 = st.columns(3)
            c1.metric("全盘总销量 (Units)", f"{int(total_units):,} 件")
            c2.metric("全盘总金额 (Total Cost)", f"${total_cost:,.2f}")
            c3.metric("总订单数 (PO 件数)", f"{total_orders:,} 单")

            st.markdown("---")
            daily_overall = filtered_sales.groupby('Clean_Date').agg({'Clean_Units': 'sum', 'Clean_Cost': 'sum'}).reset_index()
            fig_overall = go.Figure()
            fig_overall.add_trace(go.Bar(x=daily_overall['Clean_Date'], y=daily_overall['Clean_Units'], name='每日销量 (件)', marker_color='#93C5FD'))
            fig_overall.add_trace(go.Scatter(x=daily_overall['Clean_Date'], y=daily_overall['Clean_Cost'], name='每日 Total Cost ($)', yaxis='y2', line=dict(color='#1E40AF', width=2)))
            fig_overall.update_layout(title="全大盘每日销量与 Total Cost 趋势图", hovermode="x unified", xaxis_title="日期", yaxis=dict(title="销量 (件)"), yaxis2=dict(title="Total Cost ($)", overlaying='y', side='right'))
            st.plotly_chart(fig_overall, use_container_width=True)


# =========================================================================
# 模块二：广告绩效分析看板 (SPA Ad Dashboard)
# =========================================================================
else:
    st.title("📢 Home Depot SPA 广告绩效深度分析看板")
    st.markdown("---")

    st.sidebar.header("⚙️ 广告数据设置")
    uploaded_ad_file = st.sidebar.file_uploader("上传 Home Depot 广告报表 (CSV/Excel)", type=["csv", "xlsx"], key="ad_uploader")

    # 主界面上传入口
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

        # 广告字段匹配
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

        # 数据清洗
        for col in [spend_col, sales_col, clicks_col, impressions_col, roas_col]:
            if col and col in df_ad.columns:
                df_ad[col] = pd.to_numeric(df_ad[col].astype(str).str.replace('$', '').str.replace(',', '').str.replace('%', ''), errors='coerce').fillna(0)

        total_spend = df_ad[spend_col].sum() if spend_col else 0
        total_sales = df_ad[sales_col].sum() if sales_col else 0
        total_clicks = df_ad[clicks_col].sum() if clicks_col else 0
        total_impressions = df_ad[impressions_col].sum() if impressions_col else 0

        overall_roas = total_sales / total_spend if total_spend > 0 else 0
        overall_ctr = (total_clicks / total_impressions) * 100 if total_impressions > 0 else 0
        overall_cpc = total_spend / total_clicks if total_clicks > 0 else 0
        overall_acos = (total_spend / total_sales) * 100 if total_sales > 0 else 0

        # KPI 卡片
        st.subheader("📌 广告整体表现概览 (Global Performance)")
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("总广告花费 (Spend)", f"${total_spend:,.2f}")
        c2.metric("广告销售额 (SPA Sales)", f"${total_sales:,.2f}")
        c3.metric("整体 ROAS", f"{overall_roas:.2f}", delta=f"ACOS: {overall_acos:.1f}%", delta_color="inverse")
        c4.metric("总点击量 / 平均 CPC", f"{int(total_clicks):,} 次", delta=f"${overall_cpc:.2f}/点击")
        c5.metric("总曝光量 / CTR", f"{int(total_impressions):,} 次", delta=f"{overall_ctr:.2f}% CTR")

        st.markdown("---")

        st.sidebar.markdown("---")
        st.sidebar.markdown("### 🔍 广告分析维度选择")
        ad_view_mode = st.sidebar.radio("选择广告分析视角", ["🎯 广告活动 (Campaign) 深度分析", "📦 推广产品 (OMSID) 维度", "🏬 部门 (Dept) 维度"])

        # 视角 1: Campaign
        if ad_view_mode == "🎯 广告活动 (Campaign) 深度分析":
            st.subheader("🎯 广告活动 (Campaign) 表现对比与 ROAS 分析")
            camp_summary = df_ad.groupby(campaign_col).agg({
                spend_col: 'sum', sales_col: 'sum',
                clicks_col: 'sum' if clicks_col else 'count',
                impressions_col: 'sum' if impressions_col else 'count'
            }).reset_index()

            camp_summary['ROAS'] = camp_summary.apply(lambda row: row[sales_col] / row[spend_col] if row[spend_col] > 0 else 0, axis=1)
            camp_summary['CPC'] = camp_summary.apply(lambda row: row[spend_col] / row[clicks_col] if row[clicks_col] > 0 else 0, axis=1)
            camp_summary = camp_summary.sort_values(by=spend_col, ascending=False)

            col_c1, col_c2 = st.columns(2)
            with col_c1:
                fig_camp_bar = go.Figure()
                fig_camp_bar.add_trace(go.Bar(x=camp_summary[campaign_col], y=camp_summary[spend_col], name='广告花费 ($)', marker_color='#F59E0B'))
                fig_camp_bar.add_trace(go.Bar(x=camp_summary[campaign_col], y=camp_summary[sales_col], name='广告销售额 ($)', marker_color='#10B981'))
                fig_camp_bar.update_layout(title="各 Campaign 花费 vs 销售额", barmode='group', xaxis_title="Campaign 名称", yaxis_title="金额 ($)")
                st.plotly_chart(fig_camp_bar, use_container_width=True)

            with col_c2:
                fig_scatter = px.scatter(
                    camp_summary, x=spend_col, y='ROAS', size=sales_col, hover_name=campaign_col, color='ROAS',
                    color_continuous_scale='RdYlGn', title="Campaign 花费 vs ROAS 散点诊断图"
                )
                fig_scatter.add_hline(y=overall_roas, line_dash="dash", line_color="gray", annotation_text="全盘平均 ROAS")
                st.plotly_chart(fig_scatter, use_container_width=True)

            st.markdown("### 📋 Campaign 详细数据与效率排行榜")
            st.dataframe(camp_summary.rename(columns={campaign_col: 'Campaign 名称', spend_col: '广告花费 ($)', sales_col: '广告销售额 ($)', clicks_col: '点击数', impressions_col: '曝光数', 'ROAS': 'ROAS', 'CPC': '平均 CPC ($)'}).style.format({'广告花费 ($)': '${:,.2f}', '广告销售额 ($)': '${:,.2f}', '点击数': '{:,.0f}', '曝光数': '{:,.0f}', 'ROAS': '{:.2f}', '平均 CPC ($)': '${:.2f}'}), use_container_width=True)

        # 视角 2: OMSID
        elif ad_view_mode == "📦 推广产品 (OMSID) 维度":
            st.subheader("📦 推广产品 (OMSID) 广告效果分析")
            if omsid_col:
                oms_summary = df_ad.groupby(omsid_col).agg({spend_col: 'sum', sales_col: 'sum', clicks_col: 'sum' if clicks_col else 'count', impressions_col: 'sum' if impressions_col else 'count'}).reset_index()
                oms_summary['ROAS'] = oms_summary.apply(lambda row: row[sales_col] / row[spend_col] if row[spend_col] > 0 else 0, axis=1)
                oms_summary = oms_summary.sort_values(by=spend_col, ascending=False)

                top_10_oms = oms_summary.head(10)
                fig_oms = px.bar(top_10_oms, x=omsid_col, y=spend_col, color='ROAS', text='ROAS', title="TOP 10 广告花费 OMSID 及 ROAS 表现", color_continuous_scale='Viridis')
                fig_oms.update_traces(texttemplate='ROAS: %{text:.2f}', textposition='outside')
                st.plotly_chart(fig_oms, use_container_width=True)

                st.markdown("### 📋 所有 OMSID 广告投放明细")
                st.dataframe(oms_summary.rename(columns={omsid_col: 'OMS ID', spend_col: '广告花费 ($)', sales_col: '广告销售额 ($)', clicks_col: '点击数', impressions_col: '曝光数', 'ROAS': 'ROAS'}).style.format({'广告花费 ($)': '${:,.2f}', '广告销售额 ($)': '${:,.2f}', '点击数': '{:,.0f}', '曝光数': '{:,.0f}', 'ROAS': '{:.2f}'}), use_container_width=True)

        # 视角 3: Dept
        else:
            st.subheader("🏬 部门/品类 (Dept) 广告效率对比")
            if dept_col:
                dept_summary = df_ad.groupby(dept_col).agg({spend_col: 'sum', sales_col: 'sum', clicks_col: 'sum' if clicks_col else 'count'}).reset_index()
                dept_summary['ROAS'] = dept_summary.apply(lambda row: row[sales_col] / row[spend_col] if row[spend_col] > 0 else 0, axis=1)
                dept_summary = dept_summary.sort_values(by=sales_col, ascending=False)

                fig_dept_pie = px.pie(dept_summary, values=spend_col, names=dept_col, title="各部门/品类广告花费占比", hole=0.4)
                fig_dept_pie.update_traces(textinfo='percent+label')
                st.plotly_chart(fig_dept_pie, use_container_width=True)

                st.dataframe(dept_summary.rename(columns={dept_col: '部门/品类 Dept', spend_col: '广告花费 ($)', sales_col: '广告销售额 ($)', 'ROAS': 'ROAS'}).style.format({'广告花费 ($)': '${:,.2f}', '广告销售额 ($)': '${:,.2f}', 'ROAS': '{:.2f}'}), use_container_width=True)
