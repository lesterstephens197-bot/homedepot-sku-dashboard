import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import timedelta

# 1. 页面基本配置
st.set_page_config(
    page_title="电商全景综合销售数据分析看板",
    page_icon="📊",
    layout="wide"
)

st.title("📊 电商全景综合销售数据分析看板")
st.caption("集成总揽 KPI、运营绩效、SKU 帕累托等级划分及渠道地址分析")

# 2. 数据加载与清洗
@st.cache_data
def load_data(uploaded_file):
    if uploaded_file.name.endswith('.csv'):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)
    
    # 清洗表头空格
    df.columns = df.columns.str.strip()

    # 订单日期解析
    if 'Order Date' in df.columns:
        df['Order Date'] = pd.to_datetime(df['Order Date'], errors='coerce')
    
    # 数值转换
    numeric_cols = ['Unit Cost', 'Quantity', 'Total Cost']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            
    # Total Cost 自动补充
    if 'Total Cost' in df.columns and 'Unit Cost' in df.columns and 'Quantity' in df.columns:
        df['Total Cost'] = df.apply(
            lambda r: r['Total Cost'] if r['Total Cost'] > 0 else r['Unit Cost'] * r['Quantity'], 
            axis=1
        )
    return df

# 侧边栏上传
st.sidebar.header("📁 数据导入")
uploaded_file = st.sidebar.file_uploader("上传 CSV 或 Excel 数据表", type=["csv", "xlsx"])

if uploaded_file is not None:
    raw_df = load_data(uploaded_file)
    
    # 过滤无效日期的行
    df = raw_df.dropna(subset=['Order Date']).copy() if 'Order Date' in raw_df.columns else raw_df.copy()

    # 全局最新日期判定
    max_date = df['Order Date'].max() if 'Order Date' in df.columns else pd.Timestamp.now()

    # 侧边栏筛选
    st.sidebar.subheader("🔍 全局筛选条件")
    
    # 日期范围筛选
    if 'Order Date' in df.columns and not df['Order Date'].isna().all():
        min_d = df['Order Date'].min().date()
        max_d = df['Order Date'].max().date()
        date_range = st.sidebar.date_input("订单日期区间", [min_d, max_d])
        if len(date_range) == 2:
            df = df[(df['Order Date'].dt.date >= date_range[0]) & (df['Order Date'].dt.date <= date_range[1])]

    # 品牌筛选
    if '品牌' in df.columns:
        brands = ['全部'] + list(df['品牌'].dropna().unique())
        selected_brand = st.sidebar.selectbox("选择品牌", brands)
        if selected_brand != '全部':
            df = df[df['品牌'] == selected_brand]

    # 运营筛选
    if '运营' in df.columns:
        operators = ['全部'] + list(df['运营'].dropna().unique())
        selected_operator = st.sidebar.selectbox("选择运营负责人", operators)
        if selected_operator != '全部':
            df = df[df['运营'] == selected_operator]

    # 选项卡切换四大核心看板
    tab_total, tab_op, tab_sku_rank, tab_hd = st.tabs([
        "📊 1. 核心总看板", 
        "👤 2. 分运营销售数据", 
        "🏆 3. 产品 SKU 排名与等级划分",
        "🏪 4. HD 门店 vs 个人地址占比"
    ])

    # =========================================================================
    # TAB 1: 核心总看板 (总销售、总销量、平均客单价、总单量)
    # =========================================================================
    with tab_total:
        st.header("📊 全局销售核心指标看板")
        
        # 1. 四大核心 KPI 指标计算
        total_sales = df['Total Cost'].sum() if 'Total Cost' in df.columns else 0
        total_qty = df['Quantity'].sum() if 'Quantity' in df.columns else 0
        total_orders = df['PO Number'].nunique() if 'PO Number' in df.columns else len(df)
        avg_order_value = total_sales / total_orders if total_orders > 0 else 0

        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        kpi1.metric("💰 总销售额 (Total Sales)", f"${total_sales:,.2f}")
        kpi2.metric("📦 总销量 (Total Quantity)", f"{int(total_qty):,} 件")
        kpi3.metric("💳 平均客单价 (AOV)", f"${avg_order_value:,.2f}")
        kpi4.metric("📄 总订单量 (Total POs)", f"{total_orders:,} 单")

        st.divider()

        # 2. 销售趋势分析图表
        st.subheader("📈 销售额与销量趋势走势")
        if 'Order Date' in df.columns and 'Total Cost' in df.columns:
            trend_type = st.radio("时间粒度切换:", ["按日 (Daily)", "按周 (Weekly)", "按月 (Monthly)"], horizontal=True)
            rule = 'D' if '按日' in trend_type else ('W' if '按周' in trend_type else 'ME')
            
            daily_df = df.set_index('Order Date').resample(rule).agg({
                'Total Cost': 'sum',
                'Quantity': 'sum',
                'PO Number': 'nunique'
            }).reset_index()

            fig_trend = px.line(
                daily_df, x='Order Date', y='Total Cost', 
                title="销售额走势图",
                labels={'Total Cost': '销售额 ($)', 'Order Date': '日期'},
                markers=True
            )
            st.plotly_chart(fig_trend, use_container_width=True)

    # =========================================================================
    # TAB 2: 分运营销售数据看板
    # =========================================================================
    with tab_op:
        st.header("👤 运营人员绩效与销售数据分析")

        if '运营' in df.columns:
            # 运营数据聚合计算
            op_summary = df.groupby('运营').agg(
                总销售额=('Total Cost', 'sum'),
                总销量=('Quantity', 'sum'),
                总订单量=('PO Number', 'nunique') if 'PO Number' in df.columns else ('运营', 'count'),
            ).reset_index()

            # 计算运营客单价与人均占比
            op_summary['平均客单价(AOV)'] = (op_summary['总销售额'] / op_summary['总订单量']).round(2)
            op_summary['销售额占比'] = (op_summary['总销售额'] / total_sales * 100).round(2) if total_sales > 0 else 0
            
            # 按销售额从高到低排序
            op_summary = op_summary.sort_values(by='总销售额', ascending=False)

            # 可视化对比图表
            c_op1, c_op2 = st.columns([3, 2])
            with c_op1:
                st.subheader("📊 运营销售额业绩对比")
                fig_op_bar = px.bar(
                    op_summary, x='运营', y='总销售额',
                    color='总销量',
                    text_auto='.2s',
                    title="各运营人员总销售额排名"
                )
                st.plotly_chart(fig_op_bar, use_container_width=True)

            with c_op2:
                st.subheader("🍩 运营销售额贡献占比")
                fig_op_pie = px.pie(
                    op_summary, names='运营', values='总销售额',
                    title="运营人员销售额份额占比", hole=0.4
                )
                st.plotly_chart(fig_op_pie, use_container_width=True)

            st.divider()
            st.subheader("📋 运营数据明细表")
            st.dataframe(
                op_summary,
                column_config={
                    "总销售额": st.column_config.NumberColumn("总销售额", format="$%.2f"),
                    "平均客单价(AOV)": st.column_config.NumberColumn("平均客单价(AOV)", format="$%.2f"),
                    "销售额占比": st.column_config.NumberColumn("销售额占比", format="%.2f%%"),
                },
                use_container_width=True,
                hide_index=True
            )
        else:
            st.warning("数据集中未检测到 `运营` 字段。")

    # =========================================================================
    # TAB 3: 产品 SKU 排名与等级划分看板
    # =========================================================================
    with tab_sku_rank:
        st.header("🏆 产品 SKU 综合排名与等级划分看板")
        st.caption("根据销售额累计贡献率（ABC 帕累托分类法）自动将 SKU 划分为：S级/A级 (前80%核心款)、B级 (80%-95%主力款)、C级 (最后5%尾部款)")

        sku_col = '产品SKU' if '产品SKU' in df.columns else ('Merchant SKU' if 'Merchant SKU' in df.columns else 'Vendor SKU')
        name_col = '产品名称' if '产品名称' in df.columns else 'Description'

        if sku_col in df.columns:
            # 聚合计算每个 SKU 的数据
            sku_rank_df = df.groupby(sku_col).agg(
                产品名称=(name_col, 'first') if name_col in df.columns else (sku_col, 'first'),
                品牌=('品牌', 'first') if '品牌' in df.columns else (sku_col, 'first'),
                运营=('运营', 'first') if '运营' in df.columns else (sku_col, 'first'),
                总销售额=('Total Cost', 'sum'),
                总销量=('Quantity', 'sum'),
                总订单数=('PO Number', 'nunique') if 'PO Number' in df.columns else (sku_col, 'count')
            ).reset_index()

            # 按销售额降序排列
            sku_rank_df = sku_rank_df.sort_values(by='总销售额', ascending=False).reset_index(drop=True)
            
            # 计算排名
            sku_rank_df['销售额排名'] = sku_rank_df.index + 1

            # 计算累计销售额及其占比（帕累托分析）
            total_sku_sales = sku_rank_df['总销售额'].sum()
            sku_rank_df['销售额占比'] = (sku_rank_df['总销售额'] / total_sku_sales) if total_sku_sales > 0 else 0
            sku_rank_df['累计销售额占比'] = sku_rank_df['销售额占比'].cumsum()

            # 定义等级划分函数
            def assign_grade(cum_pct):
                if cum_pct <= 0.80:
                    return 'S/A 级 (核心爆款)'
                elif cum_pct <= 0.95:
                    return 'B 级 (腰部主力)'
                else:
                    return 'C 级 (尾部滞销)'

            sku_rank_df['SKU 等级'] = sku_rank_df['累计销售额占比'].apply(assign_grade)

            # 等级看板统计概览
            grade_summary = sku_rank_df.groupby('SKU 等级').agg(
                SKU数量=(sku_col, 'count'),
                合计销售额=('总销售额', 'sum'),
                合计销量=('总销量', 'sum')
            ).reset_index()

            st.subheader("🏷️ SKU 等级划分汇总")
            g_col1, g_col2 = st.columns([1, 2])
            with g_col1:
                st.dataframe(
                    grade_summary,
                    column_config={
                        "合计销售额": st.column_config.NumberColumn("合计销售额", format="$%.2f")
                    },
                    use_container_width=True,
                    hide_index=True
                )
            with g_col2:
                fig_grade = px.pie(
                    grade_summary, names='SKU 等级', values='合计销售额',
                    title="各类等级 SKU 销售额占比结构", hole=0.4,
                    color_discrete_sequence=px.colors.qualitative.Set2
                )
                st.plotly_chart(fig_grade, use_container_width=True)

            st.divider()

            # 筛选与展示 SKU 完整排名表
            st.subheader("🔝 SKU 综合排名明细表")
            selected_grade = st.multiselect("过滤指定等级:", options=['S/A 级 (核心爆款)', 'B 级 (腰部主力)', 'C 级 (尾部滞销)'], default=['S/A 级 (核心爆款)', 'B 级 (腰部主力)', 'C 级 (尾部滞销)'])
            
            filtered_sku_df = sku_rank_df[sku_rank_df['SKU 等级'].isin(selected_grade)]

            search_sku_text = st.text_input("🔍 在当前列表中搜索 SKU / 产品名称", "")
            if search_sku_text:
                filtered_sku_df = filtered_sku_df[
                    filtered_sku_df[sku_col].astype(str).str.contains(search_sku_text, case=False) |
                    filtered_sku_df['产品名称'].astype(str).str.contains(search_sku_text, case=False)
                ]

            st.dataframe(
                filtered_sku_df,
                column_config={
                    "总销售额": st.column_config.NumberColumn("总销售额", format="$%.2f"),
                    "销售额占比": st.column_config.NumberColumn("销售额占比", format="%.2f%%"),
                    "累计销售额占比": st.column_config.ProgressColumn("累计销售额占比", format="%.1f%%", min_value=0, max_value=1),
                },
                use_container_width=True,
                hide_index=True
            )
        else:
            st.warning("缺少 SKU 字段。")

    # =========================================================================
    # TAB 4: HD 门店 vs 个人地址占比分析
    # =========================================================================
    with tab_hd:
        st.header("🏪 HD 门店 vs 个人地址 渠道对比分析")
        st.caption("基于 `ShipTo Address1` 和 `ShipTo Address2` 中包含 `C/O THD Ship to Store #` 的关键字识别 HD 门店订单")

        addr1 = df['ShipTo Address1'].astype(str) if 'ShipTo Address1' in df.columns else pd.Series(['']*len(df))
        addr2 = df['ShipTo Address2'].astype(str) if 'ShipTo Address2' in df.columns else pd.Series(['']*len(df))

        keyword_pattern = r'c/o\s*thd\s*ship\s*to\s*store'
        is_hd_store = addr1.str.contains(keyword_pattern, case=False, regex=True) | \
                      addr2.str.contains(keyword_pattern, case=False, regex=True)

        df['地址类型'] = df.apply(lambda r: 'HD门店 (Ship to Store)' if is_hd_store.loc[r.name] else '个人地址 (Home Delivery)', axis=1)

        hd_df = df[df['地址类型'] == 'HD门店 (Ship to Store)']
        home_df = df[df['地址类型'] == '个人地址 (Home Delivery)']

        hd_orders = hd_df['PO Number'].nunique() if 'PO Number' in hd_df.columns else len(hd_df)
        hd_sales = hd_df['Total Cost'].sum() if 'Total Cost' in hd_df.columns else 0

        home_orders = home_df['PO Number'].nunique() if 'PO Number' in home_df.columns else len(home_df)
        home_sales = home_df['Total Cost'].sum() if 'Total Cost' in home_df.columns else 0

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("HD 门店订单量占比", f"{(hd_orders/total_orders*100):.2f}%", f"{hd_orders:,} 单")
        k2.metric("HD 门店销售额占比", f"{(hd_sales/total_sales*100):.2f}%", f"${hd_sales:,.2f}")
        k3.metric("个人地址订单量占比", f"{(home_orders/total_orders*100):.2f}%", f"{home_orders:,} 单")
        k4.metric("个人地址销售额占比", f"{(home_sales/total_sales*100):.2f}%", f"${home_sales:,.2f}")

        st.divider()

        c_pie1, c_pie2 = st.columns(2)
        with c_pie1:
            st.subheader("📊 订单量分布占比")
            order_summary = df.groupby('地址类型')['PO Number'].nunique().reset_index() if 'PO Number' in df.columns else df['地址类型'].value_counts().reset_index()
            order_summary.columns = ['地址类型', '订单量']
            fig_order_pie = px.pie(order_summary, names='地址类型', values='订单量', title="HD 门店 vs 个人地址 订单数占比", hole=0.4)
            st.plotly_chart(fig_order_pie, use_container_width=True)

        with c_pie2:
            st.subheader("💰 销售额分布占比")
            sales_summary = df.groupby('地址类型')['Total Cost'].sum().reset_index() if 'Total Cost' in df.columns else pd.DataFrame()
            fig_sales_pie = px.pie(sales_summary, names='地址类型', values='Total Cost', title="HD 门店 vs 个人地址 销售额占比", hole=0.4)
            st.plotly_chart(fig_sales_pie, use_container_width=True)

        st.divider()

        st.subheader("🗺️ 哪个州的 HD 门店采购量最大？")
        state_col = 'ShipTo State' if 'ShipTo State' in df.columns else 'ShipTo Country'

        if state_col in hd_df.columns and not hd_df.empty:
            col_st1, col_st2 = st.columns([2, 1])

            hd_state_df = hd_df.groupby(state_col).agg(
                门店订单量=('PO Number', 'nunique') if 'PO Number' in hd_df.columns else (state_col, 'count'),
                门店销量=('Quantity', 'sum') if 'Quantity' in hd_df.columns else (state_col, 'count'),
                门店销售额=('Total Cost', 'sum') if 'Total Cost' in hd_df.columns else (state_col, 'count')
            ).reset_index().sort_values(by='门店订单量', ascending=False)

            with col_st1:
                fig_hd_state = px.bar(
                    hd_state_df.head(15), 
                    x=state_col, 
                    y='门店订单量',
                    color='门店销售额',
                    text_auto=True,
                    title="Top 15 HD 门店订单量最高州排行榜"
                )
                st.plotly_chart(fig_hd_state, use_container_width=True)

            with col_st2:
                st.write("📌 **HD 门店采购前 10 州明细**")
                st.dataframe(
                    hd_state_df.head(10),
                    column_config={
                        "门店销售额": st.column_config.NumberColumn("门店销售额", format="$%.2f")
                    },
                    use_container_width=True,
                    hide_index=True
                )
        else:
            st.info("数据中未检索到符合 `C/O THD Ship to Store #` 的 HD 门店订单。")

else:
    st.info("💡 请在左侧边栏上传 CSV 或 Excel 销售数据表。")
