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
st.caption("集成核心总销售、近7/15天对比、运营绩效、SKU 帕累托等级划分及渠道地址分析")

# =========================================================================
# 2. 数据加载与清洗函数
# =========================================================================
@st.cache_data
def load_data(uploaded_file):
    if uploaded_file.name.endswith('.csv'):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)
    
    # 清洗表头首尾空格
    df.columns = df.columns.astype(str).str.strip()

    # 订单日期解析
    if 'Order Date' in df.columns:
        df['Order Date'] = pd.to_datetime(df['Order Date'], errors='coerce')
    
    # 数值转换
    numeric_cols = ['Unit Cost', 'Quantity', 'Total Cost']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            
    # Total Cost 自动补充计算（如果缺失或为0，用单价 * 数量）
    if 'Total Cost' in df.columns and 'Unit Cost' in df.columns and 'Quantity' in df.columns:
        df['Total Cost'] = df.apply(
            lambda r: r['Total Cost'] if r['Total Cost'] > 0 else r['Unit Cost'] * r['Quantity'], 
            axis=1
        )
    return df

# KPI 指标通用计算函数
def calc_kpis(data_df):
    sales = data_df['Total Cost'].sum() if 'Total Cost' in data_df.columns else 0
    qty = data_df['Quantity'].sum() if 'Quantity' in data_df.columns else 0
    orders = data_df['PO Number'].nunique() if 'PO Number' in data_df.columns else len(data_df)
    aov = sales / orders if orders > 0 else 0
    return sales, qty, orders, aov

# =========================================================================
# 3. 侧边栏：文件上传与全局筛选
# =========================================================================
st.sidebar.header("📁 数据导入")
uploaded_file = st.sidebar.file_uploader("上传 CSV 或 Excel 销售数据表", type=["csv", "xlsx"])

if uploaded_file is not None:
    raw_df = load_data(uploaded_file)
    
    # 过滤无效日期的行
    df = raw_df.dropna(subset=['Order Date']).copy() if 'Order Date' in raw_df.columns else raw_df.copy()

    st.sidebar.subheader("🔍 全局维度筛选")
    
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

    # =========================================================================
    # 4. 看板 4 大主选项卡划分
    # =========================================================================
    tab_total, tab_op, tab_sku_rank, tab_hd = st.tabs([
        "📊 1. 核心总销售看板 (含近7天/15天)", 
        "👤 2. 分运营销售数据看板", 
        "🏆 3. 产品 SKU 排名与等级划分",
        "🏪 4. HD 门店 vs 个人地址占比"
    ])

    # -------------------------------------------------------------------------
    # TAB 1: 核心总销售看板
    # -------------------------------------------------------------------------
    with tab_total:
        st.header("📊 核心总销售看板")
        
        if 'Order Date' in df.columns and not df['Order Date'].isna().all():
            max_date = df['Order Date'].max().date()
            min_date = df['Order Date'].min().date()

            # 1.1 时间视角切换
            st.subheader("⏱️ 时间视角选择")
            period_option = st.radio(
                "快速切换数据周期:", 
                ["全量数据", "近 7 天 (Recent 7 Days)", "近 15 天 (Recent 15 Days)", "近 30 天 (Recent 30 Days)", "自定义日期区间"], 
                horizontal=True
            )

            # 根据所选时间跨度过滤数据并计算上周期环比
            if "近 7 天" in period_option:
                start_date = max_date - timedelta(days=6)
                prev_start_date = start_date - timedelta(days=7)
                prev_end_date = start_date - timedelta(days=1)
                curr_label = f"近 7 天 ({start_date} 至 {max_date})"
            elif "近 15 天" in period_option:
                start_date = max_date - timedelta(days=14)
                prev_start_date = start_date - timedelta(days=15)
                prev_end_date = start_date - timedelta(days=1)
                curr_label = f"近 15 天 ({start_date} 至 {max_date})"
            elif "近 30 天" in period_option:
                start_date = max_date - timedelta(days=29)
                prev_start_date = start_date - timedelta(days=30)
                prev_end_date = start_date - timedelta(days=1)
                curr_label = f"近 30 天 ({start_date} 至 {max_date})"
            elif "自定义日期区间" in period_option:
                c1, c2 = st.columns(2)
                date_range = c1.date_input("选择起始与截止日期", [min_date, max_date])
                if len(date_range) == 2:
                    start_date, max_date = date_range[0], date_range[1]
                else:
                    start_date, max_date = min_date, max_date
                prev_start_date, prev_end_date = None, None
                curr_label = f"自定义区间 ({start_date} 至 {max_date})"
            else:
                start_date, max_date = min_date, max_date
                prev_start_date, prev_end_date = None, None
                curr_label = f"全量数据区间 ({start_date} 至 {max_date})"

            # 当前周期与上一周期数据切片
            filtered_df = df[(df['Order Date'].dt.date >= start_date) & (df['Order Date'].dt.date <= max_date)]
            prev_df = df[(df['Order Date'].dt.date >= prev_start_date) & (df['Order Date'].dt.date <= prev_end_date)] if prev_start_date else pd.DataFrame()

            # 计算当前与上一周期 KPI
            curr_sales, curr_qty, curr_orders, curr_aov = calc_kpis(filtered_df)
            prev_sales, prev_qty, prev_orders, prev_aov = calc_kpis(prev_df)

            # 计算环比增幅
            sales_delta = f"{((curr_sales - prev_sales)/prev_sales*100):+.1f}% 环比" if prev_sales > 0 else None
            qty_delta = f"{((curr_qty - prev_qty)/prev_qty*100):+.1f}% 环比" if prev_qty > 0 else None
            orders_delta = f"{((curr_orders - prev_orders)/prev_orders*100):+.1f}% 环比" if prev_orders > 0 else None
            aov_delta = f"{((curr_aov - prev_aov)/prev_aov*100):+.1f}% 环比" if prev_aov > 0 else None

            st.caption(f"当前视图：**{curr_label}**")

            # 1.2 核心 4 大指标卡片
            kpi1, kpi2, kpi3, kpi4 = st.columns(4)
            kpi1.metric("💰 总销售额 (Total Sales)", f"${curr_sales:,.2f}", delta=sales_delta)
            kpi2.metric("📦 总销量 (Total Quantity)", f"{int(curr_qty):,} 件", delta=qty_delta)
            kpi3.metric("💳 平均客单价 (AOV)", f"${curr_aov:,.2f}", delta=aov_delta)
            kpi4.metric("📄 总订单量 (Total POs)", f"{curr_orders:,} 单", delta=orders_delta)

            st.divider()

            # 1.3 近 7 天 vs 近 15 天 指标快速对比表
            st.subheader("⚔️ 近 7 天 vs 近 15 天 销售数据对比")
            d7_start = max_date - timedelta(days=6)
            d15_start = max_date - timedelta(days=14)

            df_7 = df[(df['Order Date'].dt.date >= d7_start) & (df['Order Date'].dt.date <= max_date)]
            df_15 = df[(df['Order Date'].dt.date >= d15_start) & (df['Order Date'].dt.date <= max_date)]

            s7, q7, o7, a7 = calc_kpis(df_7)
            s15, q15, o15, a15 = calc_kpis(df_15)

            compare_table = pd.DataFrame({
                "指标维度": ["总销售额 ($)", "总销量 (件)", "总订单量 (单)", "平均客单价 ($)", "日均销售额 ($)", "日均订单量 (单)"],
                "近 7 天": [f"${s7:,.2f}", f"{int(q7):,}", f"{o7:,}", f"${a7:,.2f}", f"${(s7/7):,.2f}", f"{(o7/7):.1f}"],
                "近 15 天": [f"${s15:,.2f}", f"{int(q15):,}", f"{o15:,}", f"${a15:,.2f}", f"${(s15/15):,.2f}", f"{(o15/15):.1f}"]
            })
            st.table(compare_table)

            st.divider()

            # 1.4 销售趋势图
            st.subheader("📈 销售额走势图")
            trend_type = st.radio("选择时间粒度:", ["按日 (Daily)", "按周 (Weekly)", "按月 (Monthly)"], horizontal=True)
            rule = 'D' if '按日' in trend_type else ('W' if '按周' in trend_type else 'ME')
            
            daily_df = filtered_df.set_index('Order Date').resample(rule).agg({
                'Total Cost': 'sum',
                'Quantity': 'sum',
                'PO Number': 'nunique'
            }).reset_index()

            fig_trend = px.line(
                daily_df, x='Order Date', y='Total Cost', 
                title="所选区间内的销售额走势",
                labels={'Total Cost': '销售额 ($)', 'Order Date': '日期'},
                markers=True
            )
            st.plotly_chart(fig_trend, use_container_width=True)
        else:
            st.warning("数据集中未包含有效的 `Order Date` 日期字段。")

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
                    color='总销量',
                    text_auto='.2s',
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
                use_container_width=True,
                hide_index=True
            )
        else:
            st.warning("数据集中未检测到 `运营` 字段。")

    # -------------------------------------------------------------------------
    # TAB 3: 产品 SKU 排名与等级划分看板
    # -------------------------------------------------------------------------
    with tab_sku_rank:
        st.header("🏆 产品 SKU 综合排名与等级划分看板")
        st.caption("基于 ABC 帕累托分类法自动划分等级：S/A级 (贡献前80%销售额爆款)、B级 (80%-95%腰部款)、C级 (最后5%尾部款)")

        sku_col = '产品SKU' if '产品SKU' in df.columns else ('Merchant SKU' if 'Merchant SKU' in df.columns else 'Vendor SKU')
        name_col = '产品名称' if '产品名称' in df.columns else 'Description'

        if sku_col in df.columns:
            sku_rank_df = df.groupby(sku_col).agg(
                产品名称=(name_col, 'first') if name_col in df.columns else (sku_col, 'first'),
                品牌=('品牌', 'first') if '品牌' in df.columns else (sku_col, 'first'),
                运营=('运营', 'first') if '运营' in df.columns else (sku_col, 'first'),
                总销售额=('Total Cost', 'sum'),
                总销量=('Quantity', 'sum'),
                总订单数=('PO Number', 'nunique') if 'PO Number' in df.columns else (sku_col, 'count')
            ).reset_index()

            sku_rank_df = sku_rank_df.sort_values(by='总销售额', ascending=False).reset_index(drop=True)
            sku_rank_df['销售额排名'] = sku_rank_df.index + 1

            total_sku_sales = sku_rank_df['总销售额'].sum()
            sku_rank_df['销售额占比'] = (sku_rank_df['总销售额'] / total_sku_sales) if total_sku_sales > 0 else 0
            sku_rank_df['累计销售额占比'] = sku_rank_df['销售额占比'].cumsum()

            # 等级划分法则
            def assign_grade(cum_pct):
                if cum_pct <= 0.80:
                    return 'S/A 级 (核心爆款)'
                elif cum_pct <= 0.95:
                    return 'B 级 (腰部主力)'
                else:
                    return 'C 级 (尾部滞销)'

            sku_rank_df['SKU 等级'] = sku_rank_df['累计销售额占比'].apply(assign_grade)

            grade_summary = sku_rank_df.groupby('SKU 等级').agg(
                SKU数量=(sku_col, 'count'),
                合计销售额=('总销售额', 'sum'),
                合计销量=('总销量', 'sum')
            ).reset_index()

            st.subheader("🏷️ 各等级 SKU 汇总分布")
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
                    title="各等级 SKU 销售额结构占比", hole=0.4,
                    color_discrete_sequence=px.colors.qualitative.Set2
                )
                st.plotly_chart(fig_grade, use_container_width=True)

            st.divider()

            st.subheader("🔝 SKU 综合排名与划分明细")
            selected_grade = st.multiselect("按等级筛选:", options=['S/A 级 (核心爆款)', 'B 级 (腰部主力)', 'C 级 (尾部滞销)'], default=['S/A 级 (核心爆款)', 'B 级 (腰部主力)', 'C 级 (尾部滞销)'])
            
            filtered_sku_df = sku_rank_df[sku_rank_df['SKU 等级'].isin(selected_grade)]

            search_sku_text = st.text_input("🔍 搜索特定 SKU / 产品名称", "")
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
            st.warning("数据集中未检测到 SKU 标识字段。")

    # -------------------------------------------------------------------------
    # TAB 4: HD 门店 vs 个人地址占比分析
    # -------------------------------------------------------------------------
    with tab_hd:
        st.header("🏪 HD 门店 vs 个人地址 渠道分析看板")

        addr1 = df['ShipTo Address1'].astype(str) if 'ShipTo Address1' in df.columns else pd.Series(['']*len(df))
        addr2 = df['ShipTo Address2'].astype(str) if 'ShipTo Address2' in df.columns else pd.Series(['']*len(df))

        # 正则识别 Home Depot 门店订单
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

        # HD 门店采购大州分析
        st.subheader("🗺️ HD 门店热门采购州排行榜")
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
                st.write("📌 **Top 10 HD 门店州数据**")
                st.dataframe(
                    hd_state_df.head(10),
                    column_config={
                        "门店销售额": st.column_config.NumberColumn("门店销售额", format="$%.2f")
                    },
                    use_container_width=True,
                    hide_index=True
                )
        else:
            st.info("数据中未检索到 HD 门店订单或缺少州字段。")

else:
    st.info("💡 请在左侧边栏上传 CSV 或 Excel 格式的销售数据表。")
