import streamlit as st
import pandas as pd
import plotly.express as px

# =========================================================================
# 1. 页面基本配置
# =========================================================================
st.set_page_config(
    page_title="RTV 产品退货与扣款分析看板",
    page_icon="🔄",
    layout="wide"
)

st.title("🔄 RTV 产品退货与扣款分析看板 (以 SKU 为核心)")
st.caption("基于 RTV 退货明细数据，深入分析 SKU 退货率、退货原因归因、运费扣款及渠道分布")

# =========================================================================
# 2. 数据加载与预处理
# =========================================================================
@st.cache_data
def load_rtv_data(uploaded_file):
    if uploaded_file.name.endswith('.csv'):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)
    
    # 清理列名首尾空格
    df.columns = df.columns.astype(str).str.strip()

    # 日期解析
    date_cols = ['RTV Date', 'Order Date']
    for col in date_cols:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce')

    # 数值列转换与缺省填充
    num_cols = ['QTY', 'UNIT COST', 'Total Cost', '10%运费', '总扣款']
    for col in num_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # 逻辑补全：如果 Total Cost 为 0，自动计算 QTY * UNIT COST
    if 'Total Cost' in df.columns and 'UNIT COST' in df.columns and 'QTY' in df.columns:
        df['Total Cost'] = df.apply(
            lambda r: r['Total Cost'] if r['Total Cost'] > 0 else r['UNIT COST'] * r['QTY'],
            axis=1
        )
    
    # 逻辑补全：如果 总扣款 为 0，且有 Total Cost 和 10%运费
    if '总扣款' in df.columns and 'Total Cost' in df.columns and '10%运费' in df.columns:
        df['总扣款'] = df.apply(
            lambda r: r['总扣款'] if r['总扣款'] > 0 else r['Total Cost'] + r['10%运费'],
            axis=1
        )

    return df

# =========================================================================
# 3. 侧边栏：文件上传与多维筛选
# =========================================================================
st.sidebar.header("📁 RTV 数据导入")
uploaded_file = st.sidebar.file_uploader("上传 RTV 退货数据表 (CSV/Excel)", type=["csv", "xlsx"])

if uploaded_file is not None:
    df = load_rtv_data(uploaded_file)

    st.sidebar.subheader("🔍 条件筛选")

    # 品牌筛选
    if 'Brand' in df.columns:
        brands = ['全部'] + list(df['Brand'].dropna().unique())
        selected_brand = st.sidebar.selectbox("选择品牌 (Brand)", brands)
        if selected_brand != '全部':
            df = df[df['Brand'] == selected_brand]

    # 店铺筛选
    if 'Store' in df.columns:
        stores = ['全部'] + list(df['Store'].astype(str).dropna().unique())
        selected_store = st.sidebar.selectbox("选择店铺/渠道 (Store)", stores)
        if selected_store != '全部':
            df = df[df['Store'].astype(str) == selected_store]

    # RTV 日期区间筛选
    if 'RTV Date' in df.columns and not df['RTV Date'].isna().all():
        min_date = df['RTV Date'].min().date()
        max_date = df['RTV Date'].max().date()
        date_range = st.sidebar.date_input("RTV 退货日期范围", [min_date, max_date])
        if len(date_range) == 2:
            df = df[(df['RTV Date'].dt.date >= date_range[0]) & (df['RTV Date'].dt.date <= date_range[1])]

    # =========================================================================
    # 4. 看板主体：四大页签
    # =========================================================================
    
    # 全局核心 KPI
    total_rtv_cost = df['Total Cost'].sum() if 'Total Cost' in df.columns else 0
    total_deduction = df['总扣款'].sum() if '总扣款' in df.columns else 0
    total_shipping = df['10%运费'].sum() if '10%运费' in df.columns else 0
    total_qty = df['QTY'].sum() if 'QTY' in df.columns else 0
    unique_skus = df['产品SKU'].nunique() if '产品SKU' in df.columns else 0
    total_records = len(df)

    # 1. 顶部 KPI 卡片展示
    kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
    kpi1.metric("💸 总退货货值", f"${total_rtv_cost:,.2f}")
    kpi2.metric("🛑 总扣款金额", f"${total_deduction:,.2f}")
    kpi3.metric("🚚 运费扣款合计", f"${total_shipping:,.2f}")
    kpi4.metric("📦 退货总件数", f"{int(total_qty):,} 件")
    kpi5.metric("🏷️ 涉及退货 SKU 数", f"{unique_skus:,} 个")

    st.divider()

    tab_sku, tab_reason, tab_channel, tab_trend = st.tabs([
        "🏆 1. SKU 退货黑榜与等级划分",
        "❓ 2. 退货原因归因分析 (Reason)",
        "🏪 3. 店铺 & 承运商扣款分析",
        "📈 4. RTV 退货时间走势"
    ])

    # -------------------------------------------------------------------------
    # TAB 1: 以 SKU 为核心的退货黑榜与等级划分
    # -------------------------------------------------------------------------
    with tab_sku:
        st.header("🏆 产品 SKU 退货黑榜与风险集中度")
        
        if '产品SKU' in df.columns:
            # 按 SKU 汇总数据
            sku_summary = df.groupby('产品SKU').agg(
                产品名称=('产品名称', 'first') if '产品名称' in df.columns else ('产品SKU', 'first'),
                Brand=('Brand', 'first') if 'Brand' in df.columns else ('产品SKU', 'first'),
                PART号=('PART#', 'first') if 'PART#' in df.columns else ('产品SKU', 'first'),
                退货总件数=('QTY', 'sum'),
                退货总货值=('Total Cost', 'sum'),
                运费扣款=('10%运费', 'sum'),
                总扣款金额=('总扣款', 'sum'),
                退货次数=('RTV Number', 'nunique') if 'RTV Number' in df.columns else ('产品SKU', 'count')
            ).reset_index()

            # 按退货总扣款金额降序
            sku_summary = sku_summary.sort_values(by='总扣款金额', ascending=False).reset_index(drop=True)
            sku_summary['扣款金额排名'] = sku_summary.index + 1

            # 帕累托法则 (80/20 法则)
            total_deduct_all = sku_summary['总扣款金额'].sum()
            sku_summary['扣款占比'] = (sku_summary['总扣款金额'] / total_deduct_all) if total_deduct_all > 0 else 0
            sku_summary['累计扣款占比'] = sku_summary['扣款占比'].cumsum()

            # 风险等级分类
            def assign_risk_level(cum_pct):
                if cum_pct <= 0.80:
                    return '高危 SKU (前80%退货扣款来源)'
                elif cum_pct <= 0.95:
                    return '中危 SKU (80%-95%)'
                else:
                    return '低危/偶发 SKU (后5%)'

            sku_summary['风险等级'] = sku_summary['累计扣款占比'].apply(assign_risk_level)

            # 顶部 Top 10 SKU 图表展示
            col_chart1, col_chart2 = st.columns([3, 2])
            with col_chart1:
                st.subheader("🔥 退货扣款金额 Top 10 SKU")
                fig_top_sku = px.bar(
                    sku_summary.head(10),
                    x='产品SKU',
                    y='总扣款金额',
                    color='退货总件数',
                    text_auto='.2s',
                    hover_data=['产品名称', 'Brand'],
                    title="退货总扣款金额最高的 10 个 SKU"
                )
                st.plotly_chart(fig_top_sku, use_container_width=True)

            with col_chart2:
                st.subheader("🍩 退货风险等级分布")
                risk_summary = sku_summary.groupby('风险等级').agg(
                    SKU数量=('产品SKU', 'count'),
                    合计扣款=('总扣款金额', 'sum')
                ).reset_index()
                fig_risk_pie = px.pie(
                    risk_summary, names='风险等级', values='合计扣款',
                    title="退货扣款结构占比 (帕累托法则)", hole=0.4,
                    color_discrete_sequence=px.colors.qualitative.Reds_r
                )
                st.plotly_chart(fig_risk_pie, use_container_width=True)

            st.divider()

            # 数据明细表与筛选
            st.subheader("📋 SKU 退货明细排行榜")
            search_sku = st.text_input("🔍 快速搜索特定 SKU 或产品名称", "")
            
            filtered_sku_summary = sku_summary.copy()
            if search_sku:
                filtered_sku_summary = filtered_sku_summary[
                    filtered_sku_summary['产品SKU'].astype(str).str.contains(search_sku, case=False) |
                    filtered_sku_summary['产品名称'].astype(str).str.contains(search_sku, case=False)
                ]

            st.dataframe(
                filtered_sku_summary,
                column_config={
                    "退货总货值": st.column_config.NumberColumn("退货总货值", format="$%.2f"),
                    "运费扣款": st.column_config.NumberColumn("10%运费扣款", format="$%.2f"),
                    "总扣款金额": st.column_config.NumberColumn("总扣款金额", format="$%.2f"),
                    "扣款占比": st.column_config.NumberColumn("扣款占比", format="%.2f%%"),
                    "累计扣款占比": st.column_config.ProgressColumn("累计扣款占比", format="%.1f%%", min_value=0, max_value=1),
                },
                use_container_width=True,
                hide_index=True
            )
        else:
            st.warning("数据集中未发现 `产品SKU` 列。")

    # -------------------------------------------------------------------------
    # TAB 2: 退货原因归因分析 (Reason)
    # -------------------------------------------------------------------------
    with tab_reason:
        st.header("❓ 退货原因 (Reason) 归因分析")

        if 'Reason' in df.columns:
            col_r1, col_r2 = st.columns([1, 1])
            
            # 全局原因汇总
            reason_summary = df.groupby('Reason').agg(
                退货次数=('Reason', 'count'),
                退货件数=('QTY', 'sum'),
                总扣款金额=('总扣款', 'sum')
            ).reset_index().sort_values(by='总扣款金额', ascending=False)

            with col_r1:
                st.subheader("📊 全局退货原因扣款排行")
                fig_reason_bar = px.bar(
                    reason_summary, x='Reason', y='总扣款金额',
                    color='退货件数', text_auto='.2s',
                    title="不同退货原因造成的损失总额"
                )
                st.plotly_chart(fig_reason_bar, use_container_width=True)

            with col_r2:
                st.subheader("🍩 退货原因次数占比")
                fig_reason_pie = px.pie(
                    reason_summary, names='Reason', values='退货次数',
                    title="退货原因频次分布", hole=0.4
                )
                st.plotly_chart(fig_reason_pie, use_container_width=True)

            st.divider()

            # SKU 交叉探针：单个 SKU 的退货原因穿透分析
            st.subheader("🔬 特定 SKU 的退货原因归因穿透")
            all_skus = list(df['产品SKU'].dropna().unique()) if '产品SKU' in df.columns else []
            selected_single_sku = st.selectbox("选择需要深度剖析的 SKU:", all_skus)

            if selected_single_sku:
                single_sku_df = df[df['产品SKU'] == selected_single_sku]
                
                # 单 SKU 基本指标
                s_qty = single_sku_df['QTY'].sum()
                s_deduct = single_sku_df['总扣款'].sum()
                
                st.info(f"👉 SKU **{selected_single_sku}** 累计退货 **{int(s_qty)}** 件，造成扣款金额 **${s_deduct:,.2f}**")

                single_reason = single_sku_df.groupby('Reason').agg(
                    退货件数=('QTY', 'sum'),
                    总扣款=('总扣款', 'sum'),
                    占比=('QTY', lambda x: x.sum() / s_qty * 100 if s_qty > 0 else 0)
                ).reset_index().sort_values(by='退货件数', ascending=False)

                c_s1, c_s2 = st.columns([2, 1])
                with c_s1:
                    fig_single_reason = px.bar(
                        single_reason, x='Reason', y='退货件数', text_auto=True,
                        title=f"{selected_single_sku} 退货原因细分分布"
                    )
                    st.plotly_chart(fig_single_reason, use_container_width=True)
                
                with c_s2:
                    st.dataframe(
                        single_reason,
                        column_config={
                            "总扣款": st.column_config.NumberColumn("总扣款", format="$%.2f"),
                            "占比": st.column_config.NumberColumn("件数占比", format="%.1f%%")
                        },
                        use_container_width=True,
                        hide_index=True
                    )

    # -------------------------------------------------------------------------
    # TAB 3: 店铺 & 承运商扣款分析
    # -------------------------------------------------------------------------
    with tab_channel:
        st.header("🏪 店铺 (Store) & 承运商 (Carrier) 扣款分析")

        c_st, c_ca = st.columns(2)

        with c_st:
            st.subheader("🏬 各店铺 (Store) 退货与扣款排行")
            if 'Store' in df.columns:
                store_summary = df.groupby('Store').agg(
                    退货件数=('QTY', 'sum'),
                    运费扣款=('10%运费', 'sum'),
                    总扣款金额=('总扣款', 'sum')
                ).reset_index().sort_values(by='总扣款金额', ascending=False)

                fig_store = px.bar(
                    store_summary, x='Store', y='总扣款金额',
                    text_auto='.2s', title="店铺扣款总额排行"
                )
                st.plotly_chart(fig_store, use_container_width=True)
                st.dataframe(
                    store_summary,
                    column_config={
                        "运费扣款": st.column_config.NumberColumn("运费扣款", format="$%.2f"),
                        "总扣款金额": st.column_config.NumberColumn("总扣款金额", format="$%.2f"),
                    },
                    use_container_width=True, hide_index=True
                )

        with c_ca:
            st.subheader("🚚 各承运商 (Carrier) 运费与退货分布")
            if 'Carrier' in df.columns:
                carrier_summary = df.groupby('Carrier').agg(
                    退货次数=('Carrier', 'count'),
                    退货件数=('QTY', 'sum'),
                    10百分之运费=('10%运费', 'sum')
                ).reset_index().sort_values(by='10百分之运费', ascending=False)

                fig_carrier = px.pie(
                    carrier_summary, names='Carrier', values='10百分之运费',
                    title="承运商 10% 运费扣款占比", hole=0.4
                )
                st.plotly_chart(fig_carrier, use_container_width=True)
                st.dataframe(
                    carrier_summary,
                    column_config={
                        "10百分之运费": st.column_config.NumberColumn("10%运费扣款", format="$%.2f")
                    },
                    use_container_width=True, hide_index=True
                )

    # -------------------------------------------------------------------------
    # TAB 4: RTV 退货时间走势
    # -------------------------------------------------------------------------
    with tab_trend:
        st.header("📈 RTV 退货趋势走势图")

        if 'RTV Date' in df.columns and not df['RTV Date'].isna().all():
            rule_option = st.radio("选择时间粒度:", ["按日 (Daily)", "按周 (Weekly)", "按月 (Monthly)"], horizontal=True)
            rule = 'D' if '按日' in rule_option else ('W' if '按周' in rule_option else 'ME')

            trend_df = df.set_index('RTV Date').resample(rule).agg({
                'QTY': 'sum',
                'Total Cost': 'sum',
                '总扣款': 'sum',
                '10%运费': 'sum'
            }).reset_index()

            fig_trend = px.line(
                trend_df, x='RTV Date', y=['总扣款', 'Total Cost', '10%运费'],
                title="RTV 退货扣款金额趋势走势",
                labels={'value': '金额 ($)', 'RTV Date': '日期', 'variable': '指标维度'},
                markers=True
            )
            st.plotly_chart(fig_trend, use_container_width=True)
        else:
            st.warning("数据集中缺少有效 `RTV Date` 日期数据。")

else:
    st.info("💡 请在左侧边栏上传包含 RTV 退货数据的 CSV 或 Excel 文件。")
