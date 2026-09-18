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
st.caption("聚焦 SKU 动销分析、产品地域分布与客户复购行为深度挖掘")

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
    tab_sku, tab_geo, tab_repeat = st.tabs([
        "🚀 1. SKU 动销与近况分析", 
        "🗺️ 2. 产品-地区/州分布分析", 
        "🔄 3. 客户复购率深度看板"
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

            # 【修复点】：使用 sku_metrics 计算 7天/15天 增量与环比
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
    # TAB 3: 复购率分析看板
    # =========================================================================
    with tab_repeat:
        st.header("🔄 客户复购率与客户生命周期分析")

        # 判定客户唯一标识 (优先选择 电话 > 姓名+地址 > 姓名)
        if 'ShipTo Day Phone' in df.columns and df['ShipTo Day Phone'].notna().sum() > 0:
            user_id_col = 'ShipTo Day Phone'
        elif 'ShipTo Name' in df.columns:
            user_id_col = 'ShipTo Name'
        elif 'ShipTo Address1' in df.columns:
            user_id_col = 'ShipTo Address1'
        else:
            user_id_col = None

        order_id_col = 'Customer Order Number' if 'Customer Order Number' in df.columns else 'PO Number'

        if user_id_col and order_id_col in df.columns:
            st.info(f"💡 当前判定唯一客户的依据字段为: **`{user_id_col}`**；订单判定依据字段为: **`{order_id_col}`**")

            # 1. 客户粒度聚合计算
            cust_df = df.groupby(user_id_col).agg(
                订单次数=(order_id_col, 'nunique'),
                消费总金额=('Total Cost', 'sum') if 'Total Cost' in df.columns else (order_id_col, 'count'),
                购买总件数=('Quantity', 'sum') if 'Quantity' in df.columns else (order_id_col, 'count'),
                首次购买时间=('Order Date', 'min') if 'Order Date' in df.columns else (order_id_col, 'min'),
                最近购买时间=('Order Date', 'max') if 'Order Date' in df.columns else (order_id_col, 'max')
            ).reset_index()

            total_customers = len(cust_df)
            repeat_customers = len(cust_df[cust_df['订单次数'] > 1])
            repeat_rate = (repeat_customers / total_customers * 100) if total_customers > 0 else 0

            # 消费金额占比（复购客户贡献金额 vs 单次客户贡献金额）
            repeat_users_list = cust_df[cust_df['订单次数'] > 1][user_id_col]
            repeat_sales = df[df[user_id_col].isin(repeat_users_list)]['Total Cost'].sum() if 'Total Cost' in df.columns else 0
            total_sales_all = df['Total Cost'].sum() if 'Total Cost' in df.columns else 0
            repeat_sales_ratio = (repeat_sales / total_sales_all * 100) if total_sales_all > 0 else 0

            # 展示核心复购 KPI
            rc1, rc2, rc3, rc4 = st.columns(4)
            rc1.metric("总客户数 (Unique Users)", f"{total_customers:,}")
            rc2.metric("复购客户数 (Repeat Users)", f"{repeat_customers:,}")
            rc3.metric("客户整体复购率", f"{repeat_rate:.2f}%")
            rc4.metric("复购客户销售额贡献占比", f"{repeat_sales_ratio:.2f}%")

            st.divider()

            # 图表分析：购买次数分布与复购时间间隔
            col_rep1, col_rep2 = st.columns(2)

            with col_rep1:
                st.subheader("📊 客户购买频次分布")
                freq_df = cust_df['订单次数'].value_counts().reset_index()
                freq_df.columns = ['购买次数', '客户数量']
                freq_df['购买次数类型'] = freq_df['购买次数'].apply(lambda x: f"{x}次" if x < 5 else "5次及以上")
                
                freq_summary = freq_df.groupby('购买次数类型')['客户数量'].sum().reset_index()
                fig_freq = px.pie(freq_summary, names='购买次数类型', values='客户数量', title="客户购买次数比例 (占比分布)", hole=0.4)
                st.plotly_chart(fig_freq, use_container_width=True)

            with col_rep2:
                st.subheader("⏱️ 复购周期 (再次下单平均间隔天数)")
                if 'Order Date' in df.columns:
                    # 仅筛选复购订单并按时间和客户排序计算 diff
                    df_sorted = df.sort_values(by=[user_id_col, 'Order Date'])
                    df_sorted['prev_order_date'] = df_sorted.groupby(user_id_col)['Order Date'].shift(1)
                    df_sorted['days_between_orders'] = (df_sorted['Order Date'] - df_sorted['prev_order_date']).dt.days

                    repeat_intervals = df_sorted[df_sorted['days_between_orders'] > 0]['days_between_orders']
                    avg_days = repeat_intervals.mean() if len(repeat_intervals) > 0 else 0

                    st.metric("平均再次购买间隔", f"{avg_days:.1f} 天")

                    fig_hist = px.histogram(
                        repeat_intervals, 
                        nbins=20, 
                        labels={'value': '间隔天数'},
                        title="复购间隔天数分布直方图"
                    )
                    st.plotly_chart(fig_hist, use_container_width=True)

            # 复购高价值客户 (VIP) 列表
            st.subheader("👑 核心复购高价值客户列表 (Top 20)")
            st.dataframe(
                cust_df[cust_df['订单次数'] > 1].sort_values(by='消费总金额', ascending=False).head(20),
                use_container_width=True,
                hide_index=True
            )

        else:
            st.warning("数据表中缺少用于判定客户的唯一标识字段（如 `ShipTo Day Phone` / `ShipTo Name`）或订单编号 `PO Number`。")

else:
    st.info("💡 请在左侧边栏上传 CSV 或 Excel 销售数据表。")
