import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# 页面基础配置
st.set_page_config(
    page_title="Home Depot 广告数据分析看板",
    page_icon="📢",
    layout="wide"
)

st.title("📢 Home Depot SPA 广告绩效深度分析看板")
st.markdown("---")

# 1. 侧边栏：文件上传
st.sidebar.header("⚙️ 广告数据文件上传")
uploaded_file = st.sidebar.file_uploader("上传 Home Depot 广告报表 (CSV/Excel)", type=["csv", "xlsx"])

if uploaded_file:
    try:
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)
    except Exception as e:
        st.error(f"读取文件失败，请检查文件格式: {e}")
        st.stop()

    # 清理表头空格
    df.columns = df.columns.str.strip()

    # 2. 关键表头自动匹配
    campaign_col = next((c for c in df.columns if c in ['Campaign Name', 'Campaign']), None)
    spend_col = next((c for c in df.columns if c in ['Spend', 'Cost', 'Ad Spend']), None)
    sales_col = next((c for c in df.columns if c in ['SPA Sales', 'Sales', 'Ad Sales']), None)
    clicks_col = next((c for c in df.columns if c in ['Clicks', 'Click']), None)
    impressions_col = next((c for c in df.columns if c in ['Impressions', 'Impression']), None)
    roas_col = next((c for c in df.columns if c in ['SPA ROAS', 'ROAS']), None)
    omsid_col = next((c for c in df.columns if c in ['Promoted OMSID Number', 'OMSID', 'Promoted OMS ID']), None)
    dept_col = next((c for c in df.columns if c in ['Promoted Dept Name', 'Promoted Dept Number', 'Dept']), None)
    start_date_col = next((c for c in df.columns if c in ['Schedule Start Date', 'Start Date']), None)
    end_date_col = next((c for c in df.columns if c in ['Schedule End Date', 'End Date']), None)

    if not campaign_col or not spend_col or not sales_col:
        st.error(f"解析失败！请确保表格包含关键列（Campaign Name, Spend, SPA Sales）。当前表头为: {list(df.columns)}")
        st.stop()

    # 数据清洗与数值类型转换
    for col in [spend_col, sales_col, clicks_col, impressions_col, roas_col]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col].astype(str).str.replace('$', '').str.replace(',', '').str.replace('%', ''), errors='coerce').fillna(0)

    # 计算全局衍生指标
    total_spend = df[spend_col].sum() if spend_col else 0
    total_sales = df[sales_col].sum() if sales_col else 0
    total_clicks = df[clicks_col].sum() if clicks_col else 0
    total_impressions = df[impressions_col].sum() if impressions_col else 0

    overall_roas = total_sales / total_spend if total_spend > 0 else 0
    overall_ctr = (total_clicks / total_impressions) * 100 if total_impressions > 0 else 0
    overall_cpc = total_spend / total_clicks if total_clicks > 0 else 0
    overall_acos = (total_spend / total_sales) * 100 if total_sales > 0 else 0

    # 3. 全局广告 KPI 汇总展示
    st.subheader("📌 广告整体表现概览 (Global Performance)")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("总广告花费 (Spend)", f"${total_spend:,.2f}")
    c2.metric("广告销售额 (SPA Sales)", f"${total_sales:,.2f}")
    c3.metric("整体 ROAS", f"{overall_roas:.2f}", delta=f"ACOS: {overall_acos:.1f}%", delta_color="inverse")
    c4.metric("总点击量 / 平均 CPC", f"{int(total_clicks):,} 次", delta=f"${overall_cpc:.2f}/点击")
    c5.metric("总曝光量 / CTR", f"{int(total_impressions):,} 次", delta=f"{overall_ctr:.2f}% CTR")

    st.markdown("---")

    # 4. 分析维度切换
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🔍 分析维度选择")
    view_mode = st.sidebar.radio("选择分析视角", ["🎯 广告活动 (Campaign) 深度分析", "📦 推广产品 (OMSID) 维度", "🏬 部门 (Dept) 维度"])

    # ---------------------------------------------------------
    # 视角 1：Campaign 广告活动分析
    # ---------------------------------------------------------
    if view_mode == "🎯 广告活动 (Campaign) 深度分析":
        st.subheader("🎯 广告活动 (Campaign) 表现对比与 ROAS 分析")

        # 汇总 Campaign 数据
        camp_summary = df.groupby(campaign_col).agg({
            spend_col: 'sum',
            sales_col: 'sum',
            clicks_col: 'sum' if clicks_col else 'count',
            impressions_col: 'sum' if impressions_col else 'count'
        }).reset_index()

        camp_summary['ROAS'] = camp_summary.apply(lambda row: row[sales_col] / row[spend_col] if row[spend_col] > 0 else 0, axis=1)
        camp_summary['CPC'] = camp_summary.apply(lambda row: row[spend_col] / row[clicks_col] if row[clicks_col] > 0 else 0, axis=1)
        camp_summary = camp_summary.sort_values(by=spend_col, ascending=False)

        col_c1, col_c2 = st.columns(2)

        # 花费与销售额柱状图对比
        with col_c1:
            fig_camp_bar = go.Figure()
            fig_camp_bar.add_trace(go.Bar(
                x=camp_summary[campaign_col],
                y=camp_summary[spend_col],
                name='广告花费 ($)',
                marker_color='#F59E0B'
            ))
            fig_camp_bar.add_trace(go.Bar(
                x=camp_summary[campaign_col],
                y=camp_summary[sales_col],
                name='广告销售额 ($)',
                marker_color='#10B981'
            ))
            fig_camp_bar.update_layout(
                title="各 Campaign 花费 (Spend) vs 销售额 (SPA Sales)",
                barmode='group',
                xaxis_title="Campaign 名称",
                yaxis_title="金额 ($)",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            st.plotly_chart(fig_camp_bar, use_container_width=True)

        # Spend vs ROAS 散点矩阵（诊断图）
        with col_c2:
            fig_scatter = px.scatter(
                camp_summary,
                x=spend_col,
                y='ROAS',
                size=sales_col,
                hover_name=campaign_col,
                color='ROAS',
                color_continuous_scale='RdYlGn',
                title="Campaign 花费 vs ROAS 诊断散点图 (气泡大小=Sales)",
                labels={spend_col: '广告花费 ($)', 'ROAS': 'ROAS'}
            )
            fig_scatter.add_hline(y=overall_roas, line_dash="dash", line_color="gray", annotation_text="全盘平均 ROAS")
            st.plotly_chart(fig_scatter, use_container_width=True)

        st.markdown("### 📋 Campaign 详细数据与效率排行榜")
        st.dataframe(
            camp_summary.rename(columns={
                campaign_col: 'Campaign 名称',
                spend_col: '广告花费 ($)',
                sales_col: '广告销售额 ($)',
                clicks_col: '点击数',
                impressions_col: '曝光数',
                'ROAS': 'ROAS',
                'CPC': '平均 CPC ($)'
            }).style.format({
                '广告花费 ($)': '${:,.2f}',
                '广告销售额 ($)': '${:,.2f}',
                '点击数': '{:,.0f}',
                '曝光数': '{:,.0f}',
                'ROAS': '{:.2f}',
                '平均 CPC ($)': '${:.2f}'
            }),
            use_container_width=True
        )

    # ---------------------------------------------------------
    # 视角 2：OMSID 产品维度分析
    # ---------------------------------------------------------
    elif view_mode == "📦 推广产品 (OMSID) 维度":
        st.subheader("📦 推广产品 (OMSID) 广告效果分析")

        if omsid_col:
            oms_summary = df.groupby(omsid_col).agg({
                spend_col: 'sum',
                sales_col: 'sum',
                clicks_col: 'sum' if clicks_col else 'count',
                impressions_col: 'sum' if impressions_col else 'count'
            }).reset_index()

            oms_summary['ROAS'] = oms_summary.apply(lambda row: row[sales_col] / row[spend_col] if row[spend_col] > 0 else 0, axis=1)
            oms_summary = oms_summary.sort_values(by=spend_col, ascending=False)

            # TOP OMSID 花费与 ROAS 展示
            top_10_oms = oms_summary.head(10)

            fig_oms = px.bar(
                top_10_oms,
                x=omsid_col,
                y=spend_col,
                color='ROAS',
                text='ROAS',
                title="TOP 10 广告花费 OMSID 及 ROAS 表现",
                labels={omsid_col: 'OMS ID', spend_col: '花费 ($)'},
                color_continuous_scale='Viridis'
            )
            fig_oms.update_traces(texttemplate='ROAS: %{text:.2f}', textposition='outside')
            st.plotly_chart(fig_oms, use_container_width=True)

            st.markdown("### 📋 所有 OMSID 广告投放明细")
            st.dataframe(
                oms_summary.rename(columns={
                    omsid_col: 'OMS ID',
                    spend_col: '广告花费 ($)',
                    sales_col: '广告销售额 ($)',
                    clicks_col: '点击数',
                    impressions_col: '曝光数',
                    'ROAS': 'ROAS'
                }).style.format({
                    '广告花费 ($)': '${:,.2f}',
                    '广告销售额 ($)': '${:,.2f}',
                    '点击数': '{:,.0f}',
                    '曝光数': '{:,.0f}',
                    'ROAS': '{:.2f}'
                }),
                use_container_width=True
            )
        else:
            st.warning("数据表中未查找到 `Promoted OMSID Number` 相关列。")

    # ---------------------------------------------------------
    # 视角 3：Dept 部门维度分析
    # ---------------------------------------------------------
    else:
        st.subheader("🏬 部门/品类 (Dept) 广告效率对比")

        if dept_col:
            dept_summary = df.groupby(dept_col).agg({
                spend_col: 'sum',
                sales_col: 'sum',
                clicks_col: 'sum' if clicks_col else 'count'
            }).reset_index()

            dept_summary['ROAS'] = dept_summary.apply(lambda row: row[sales_col] / row[spend_col] if row[spend_col] > 0 else 0, axis=1)
            dept_summary = dept_summary.sort_values(by=sales_col, ascending=False)

            fig_dept_pie = px.pie(
                dept_summary,
                values=spend_col,
                names=dept_col,
                title="各部门/品类广告花费 (Spend) 占比构成",
                hole=0.4
            )
            fig_dept_pie.update_traces(textinfo='percent+label')
            st.plotly_chart(fig_dept_pie, use_container_width=True)

            st.dataframe(
                dept_summary.rename(columns={
                    dept_col: '部门/品类 Dept',
                    spend_col: '广告花费 ($)',
                    sales_col: '广告销售额 ($)',
                    'ROAS': 'ROAS'
                }).style.format({
                    '广告花费 ($)': '${:,.2f}',
                    '广告销售额 ($)': '${:,.2f}',
                    'ROAS': '{:.2f}'
                }),
                use_container_width=True
            )
        else:
            st.warning("数据表中未查找到 `Promoted Dept Number` 或 `Promoted Dept Name` 相关列。")

else:
    st.info("👋 请在左侧上传 Home Depot SPA 广告报表（支持 CSV 或 Excel 格式）。")
