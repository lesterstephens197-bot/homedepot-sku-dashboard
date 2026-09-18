import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import timedelta

# 1. 页面基本配置
st.set_page_config(
    page_title="高级电商销售与运营数据看板",
    page_icon="📈",
    layout="wide"
)

st.title("📈 进阶销售数据分析看板")
st.caption("聚焦 SKU 动销分析、产品地域分布与 HD 门店 vs 个人地址渠道对比分析")

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

    # 全局最新日期判定（以数据集中最新一天为“今天”）
    max_date = df['Order Date'].max() if 'Order Date' in df.columns else pd.Timestamp.now()

    # 侧边栏筛选
    st.sidebar.subheader("🔍 全局筛选")
    
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

    # 选项卡切换三大深度板块
    tab_sku, tab_geo, tab_hd = st.tabs([
        "🚀 1. SKU 动销与近况分析", 
        "🗺️ 2. 产品-地区/州分布分析", 
        "🏪 3. HD 门店 vs 个人地址占比分析"
    ])

    # =========================================================================
    # TAB 1: SKU 动销与近况分析 (7天 / 15天 趋势)
    # =========================================================================
    with tab_sku:
        st.header("📦 SKU 维度动销与销量变化分析")
        st.caption(f"以数据集中最新日期 **{max_date.strftime('%Y-%m-%d')}** 为基准计算近7天、近15天的环比变化")

        # 确定 SKU 关键字段
        sku_col = '产品SKU' if '产品SKU' in df.columns else ('Merchant SKU' if 'Merchant SKU' in df.columns else 'Vendor SKU')
        name_col = '产品名称' if '产品名称' in df.columns else 'Description'

        if sku_col in df.columns and 'Quantity' in df.columns:
            # 时间窗口定义
            d7_start = max_date - timedelta(days=6)
            d14_start = max_date - timedelta(days=13)
            d15_start = max_date - timedelta(days=14)
            d30_start = max_date - timedelta(days=29)

            # 切片计算各个时间段销量
            df_7d = df[df['Order Date'] >= d7_start]
            df_prior_7d = df[(df['Order Date'] < d7_start) & (df['Order Date'] >= d14_start)]

            df_15d = df[df['Order Date'] >= d15_start]
            df_prior_15d = df[(df['Order Date'] < d15_start) & (df['Order Date'] >= d30_start)]

            # 基础聚合：总销量、总销售额、首售日期、末售日期、动销天数
            sku_summary = df.groupby([sku_col]).agg(
                产品名称=(name_col, 'first') if name_col in df.columns else (sku_col, 'first'),
                品牌=('品牌', 'first') if '品牌' in df.columns else (sku_col, 'first'),
                累计总销量=('Quantity', 'sum'),
                累计销售额=('Total Cost', 'sum'),
                首次售出日期=('Order Date', 'min'),
                最近售出日期=('Order Date', 'max')
            ).reset_index()

            # 计算动销天数（首次售出到最近售出的天数，至少为1天）
            sku_summary['动销天数'] = (sku_summary['最近售出日期'] - sku_summary['首次售出日期']).dt.days + 1
            sku_summary['日均销量(全周期)'] = (sku_summary['累计总销量'] / sku_summary['动销天数']).round(2)

            # 近7天 / 上个7天 销量计算
            q_7d = df_7d.groupby(sku_col)['Quantity'].sum().rename('近7天销量')
            q_prior_7d = df_prior_7d.groupby(sku_col)['Quantity'].sum().rename('上个7天销量')

            # 近15天 / 上个15天 销量计算
            q_15d = df_15d.groupby(sku_col)['Quantity'].sum().rename('近15天销量')
            q_prior_15d = df_prior_15d.groupby(sku_col)['Quantity'].sum().rename('上个15天销量')

            # 合并切片数据
            sku_metrics = sku_summary.merge(q_7d, on=sku_col, how='left')\
                                     .merge(q_prior_7d, on=sku_col, how='left')\
                                     .merge(q_15d, on=sku_col, how='left')\
                                     .merge(q_prior_15d, on=sku_col, how='left').fillna(0)

            sku_metrics['7天销量增量'] = sku_metrics['近7天销量'] - sku_metrics['上个7天销量']
            sku_metrics['7天销量环比'] = sku_metrics.apply(
                lambda r: 0 if r['上个7天销量'] == 0 else (r['近7天销量'] - r['上个7天销量']) / r['上个7天销量'], 
                axis=1
            )

            sku_metrics['15天销量增量'] = sku_metrics['近15天销量'] - sku_metrics['上个15天销量']
            sku_metrics['15天销量环比'] = sku_metrics.apply(
                lambda r: 0 if r['上个15天销量'] == 0 else (r['近15天销量'] - r['上个15天销量']) / r['上个15天销量'], 
                axis=1
            )
            
            # 格式化展示表格
            st.subheader("📊 SKU 动销及近7天/15天销量对比表")
            
            # 搜索 SKU
            search_sku = st.text_input("🔍 搜索特定 SKU 或 产品名称", "")
            if search_sku:
                sku_metrics = sku_metrics[
                    sku_metrics[sku_col].astype(str).str.contains(search_sku, case=False) | 
                    sku_metrics['产品名称'].astype(str).str.contains(search_sku, case=False)
                ]

            st.dataframe(
                sku_metrics.sort_values(by='近7天销量', ascending=False),
                column_config={
                    "首次售出日期": st.column_config.DateColumn("首次售出日期", format="YYYY-MM-DD"),
                    "最近售出日期": st.column_config.DateColumn("最近售出日期", format="YYYY-MM-DD"),
                    "累计销售额": st.column_config.NumberColumn("累计销售额", format="$%.2f"),
                    "7天销量环比": st.column_config.ProgressColumn("7天销量环比", format="%.1f%%", min_value=-1, max_value=2),
                    "15天销量环比": st.column_config.ProgressColumn("15天销量环比", format="%.1f%%", min_value=-1, max_value=2),
                },
                use_container_width=True,
                hide_index=True
            )

            # 单 SKU 趋势下钻
            st.divider()
            st.subheader("📈 单 SKU 每日销量走势下钻")
            selected_sku_single = st.selectbox("选择要分析的 SKU", options=sku_metrics[sku_col].unique())
            
            if selected_sku_single:
                single_df = df[df[sku_col] == selected_sku_single]
                daily_single = single_df.groupby('Order Date')['Quantity'].sum().reset_index()
                fig_single = px.line(
                    daily_single, x='Order Date', y='Quantity', 
                    title=f"SKU: {selected_sku_single} 每日销量趋势",
                    markers=True
                )
                st.plotly_chart(fig_single, use_container_width=True)

        else:
            st.warning("数据表中缺少 `产品SKU` / `Merchant SKU` 或 `Quantity` 字段。")

    # =========================================================================
    # TAB 2: 产品-地区/州分布分析
    # =========================================================================
    with tab_geo:
        st.header("🗺️ 产品名称维度的地区/州销售分布")

        p_col = '产品名称' if '产品名称' in df.columns else 'Description'
        state_col = 'ShipTo State' if 'ShipTo State' in df.columns else 'ShipTo Country'

        if p_col in df.columns and state_col in df.columns:
            col_left, col_right = st.columns([1, 2])

            with col_left:
                st.subheader("🎯 筛选产品")
                product_list = list(df[p_col].dropna().unique())
                selected_prod = st.selectbox("选择指定产品名称进行地域分析:", options=product_list)

                top_n = st.slider("展示前 N 个热门地区/州", min_value=5, max_value=30, value=10)

            # 过滤指定产品
            prod_geo_df = df[df[p_col] == selected_prod]

            with col_right:
                st.subheader(f"📌 [{selected_prod}] 在各州/地区的销量分布")
                
                geo_summary = prod_geo_df.groupby(state_col).agg(
                    订单量=('PO Number', 'nunique') if 'PO Number' in df.columns else (state_col, 'count'),
                    销量=('Quantity', 'sum') if 'Quantity' in df.columns else (state_col, 'count'),
                    销售额=('Total Cost', 'sum') if 'Total Cost' in df.columns else (state_col, 'count')
                ).reset_index().sort_values(by='销量', ascending=False)

                fig_geo_bar = px.bar(
                    geo_summary.head(top_n), 
                    x='销量', 
                    y=state_col, 
                    orientation='h',
                    color='销售额',
                    text_auto=True,
                    title=f"Top {top_n} 销量地区 ({state_col})"
                )
                fig_geo_bar.update_layout(yaxis={'categoryorder': 'total ascending'})
                st.plotly_chart(fig_geo_bar, use_container_width=True)

            # 交叉透视表：产品 vs 地区矩阵
            st.divider()
            st.subheader("📊 产品 x 地区销量交叉透视表 (Top 10 产品 vs Top 10 地区)")
            top10_prods = df.groupby(p_col)['Quantity'].sum().nlargest(10).index
            top10_states = df.groupby(state_col)['Quantity'].sum().nlargest(10).index

            pivot_df = df[(df[p_col].isin(top10_prods)) & (df[state_col].isin(top10_states))]
            pivot_table = pd.pivot_table(
                pivot_df, 
                values='Quantity', 
                index=p_col, 
                columns=state_col, 
                aggfunc='sum', 
                fill_value=0
            )

            fig_heatmap = px.imshow(
                pivot_table, 
                text_auto=True, 
                aspect="auto", 
                color_continuous_scale="Viridis",
                title="热力图：核心产品在核心地区的销量分布"
            )
            st.plotly_chart(fig_heatmap, use_container_width=True)

        else:
            st.warning("数据表中缺少 `产品名称`/`Description` 或 `ShipTo State`/`ShipTo Country` 字段。")

    # =========================================================================
    # TAB 3: HD 门店 vs 个人地址占比分析
    # =========================================================================
    with tab_hd:
        st.header("🏪 HD 门店 vs 个人地址 渠道对比分析")
        st.caption("基于 `ShipTo Address1` 和 `ShipTo Address2` 中包含 `C/O THD Ship to Store #` 的关键字识别 HD 门店订单")

        addr1 = df['ShipTo Address1'].astype(str) if 'ShipTo Address1' in df.columns else pd.Series(['']*len(df))
        addr2 = df['ShipTo Address2'].astype(str) if 'ShipTo Address2' in df.columns else pd.Series(['']*len(df))

        # 匹配规则：同时检测 Address1 和 Address2
        keyword_pattern = r'c/o\s*thd\s*ship\s*to\s*store'
        is_hd_store = addr1.str.contains(keyword_pattern, case=False, regex=True) | \
                      addr2.str.contains(keyword_pattern, case=False, regex=True)

        df['地址类型'] = df.apply(lambda r: 'HD门店 (Ship to Store)' if is_hd_store.loc[r.name] else '个人地址 (Home Delivery)', axis=1)

        # 1. 核心 KPI 汇总
        total_orders = df['PO Number'].nunique() if 'PO Number' in df.columns else len(df)
        total_sales = df['Total Cost'].sum() if 'Total Cost' in df.columns else 0

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

        # 2. 占比图表展示
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

        # 3. HD 门店订单的州/地区分布（哪个州的门店买最多）
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

        # 4. 采购量最高的 Top 10 具体 HD 门店
        st.divider()
        st.subheader("🏬 采购量最高的具体 HD 门店 Top 10")
        if not hd_df.empty:
            # 合并完整地址
            hd_df['完整门店地址'] = hd_df['ShipTo Address1'].fillna('') + " " + hd_df['ShipTo Address2'].fillna('')
            top_stores = hd_df.groupby(['ShipTo State', '完整门店地址']).agg(
                订单量=('PO Number', 'nunique') if 'PO Number' in hd_df.columns else ('完整门店地址', 'count'),
                销售额=('Total Cost', 'sum') if 'Total Cost' in hd_df.columns else ('完整门店地址', 'count')
            ).reset_index().sort_values(by='订单量', ascending=False).head(10)

            st.dataframe(
                top_stores,
                column_config={
                    "销售额": st.column_config.NumberColumn("销售额", format="$%.2f")
                },
                use_container_width=True,
                hide_index=True
            )

else:
    st.info("💡 请在左侧边栏上传 CSV 或 Excel 销售数据表。")
