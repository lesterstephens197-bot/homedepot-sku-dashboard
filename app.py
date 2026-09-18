import streamlit as st
import pandas as pd
import plotly.express as px

# 1. 页面基本配置
st.set_page_config(
    page_title="跨境/电商销售数据分析看板",
    page_icon="📊",
    layout="wide"
)

st.title("📊 销售数据分析看板 (Sales Dashboard)")
st.caption("基于订单、商品与物流维度的全景数据监控")

# 2. 数据加载与清洗函数
@st.cache_data
def load_data(uploaded_file):
    if uploaded_file.name.endswith('.csv'):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)
    
    # 字段清洗与格式转换
    if 'Order Date' in df.columns:
        df['Order Date'] = pd.to_datetime(df['Order Date'], errors='coerce')
    
    # 数值类型安全转换
    numeric_cols = ['Unit Cost', 'Quantity', 'Total Cost']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            
    # 计算字段填充（防止 Total Cost 缺失）
    if 'Total Cost' in df.columns and 'Unit Cost' in df.columns and 'Quantity' in df.columns:
        df['Total Cost'] = df.apply(
            lambda r: r['Total Cost'] if r['Total Cost'] > 0 else r['Unit Cost'] * r['Quantity'], 
            axis=1
        )
    return df

# 侧边栏：文件上传
st.sidebar.header("📁 数据导入")
uploaded_file = st.sidebar.file_uploader("上传 CSV 或 Excel 数据表", type=["csv", "xlsx"])

if uploaded_file is not None:
    df = load_data(uploaded_file)
    
    # 侧边栏：筛选器
    st.sidebar.subheader("🔍 筛选条件")
    
    # 日期范围筛选
    if 'Order Date' in df.columns and not df['Order Date'].isna().all():
        min_date = df['Order Date'].min().date()
        max_date = df['Order Date'].max().date()
        date_range = st.sidebar.date_input("订单日期区间", [min_date, max_date])
        if len(date_range) == 2:
            df = df[(df['Order Date'].dt.date >= date_range[0]) & (df['Order Date'].dt.date <= date_range[1])]

    # 品牌筛选
    if '品牌' in df.columns:
        brands = ['全部'] + list(df['品牌'].dropna().unique())
        selected_brand = st.sidebar.selectbox("选择品牌", brands)
        if selected_brand != '全部':
            df = df[df['品牌'] == selected_brand]

    # 运营负责人筛选
    if '运营' in df.columns:
        operators = ['全部'] + list(df['运营'].dropna().unique())
        selected_operator = st.sidebar.selectbox("选择运营负责人", operators)
        if selected_operator != '全部':
            df = df[df['运营'] == selected_operator]

    # 订单状态筛选
    if 'Line Status' in df.columns:
        statuses = st.sidebar.multiselect("订单状态 (Line Status)", options=df['Line Status'].unique(), default=df['Line Status'].unique())
        if statuses:
            df = df[df['Line Status'].isin(statuses)]

    # 3. 核心 KPI 指标展示
    st.markdown("### 📈 核心指标概览 (KPIs)")
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    
    total_sales = df['Total Cost'].sum() if 'Total Cost' in df.columns else 0
    total_qty = df['Quantity'].sum() if 'Quantity' in df.columns else 0
    total_orders = df['PO Number'].nunique() if 'PO Number' in df.columns else len(df)
    avg_order_val = total_sales / total_orders if total_orders > 0 else 0

    kpi1.metric("总销售额", f"${total_sales:,.2f}")
    kpi2.metric("总销量", f"{int(total_qty):,}")
    kpi3.metric("订单总数 (PO)", f"{total_orders:,}")
    kpi4.metric("平均订单金额 (AOV)", f"${avg_order_val:,.2f}")

    st.divider()

    # 4. 图表可视化分析
    tab1, tab2, tab3, tab4 = st.tabs(["📅 趋势分析", "📦 商品与品牌", "👤 运营绩效", "🌍 地域分布"])

    # Tab 1: 销售趋势
    with tab1:
        st.subheader("每日/每月销售额趋势")
        if 'Order Date' in df.columns and 'Total Cost' in df.columns:
            trend_df = df.set_index('Order Date').resample('D')['Total Cost'].sum().reset_index()
            fig_trend = px.line(trend_df, x='Order Date', y='Total Cost', title="销售额随时间变化曲线", labels={'Total Cost': '销售额', 'Order Date': '日期'})
            st.plotly_chart(fig_trend, use_container_width=True)
        else:
            st.warning("缺少 Order Date 或 Total Cost 字段")

    # Tab 2: 商品与品牌分析
    with tab2:
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Top 10 热销产品 (按销售额)")
            product_col = '产品名称' if '产品名称' in df.columns else 'Description'
            if product_col in df.columns and 'Total Cost' in df.columns:
                top_p = df.groupby(product_col)['Total Cost'].sum().reset_index().sort_values(by='Total Cost', ascending=False).head(10)
                fig_p = px.bar(top_p, x='Total Cost', y=product_col, orientation='h', title="Top 10 产品列表", color='Total Cost')
                fig_p.update_layout(yaxis={'categoryorder':'total ascending'})
                st.plotly_chart(fig_p, use_container_width=True)

        with col2:
            st.subheader("品牌销售额占比")
            if '品牌' in df.columns and 'Total Cost' in df.columns:
                brand_df = df.groupby('品牌')['Total Cost'].sum().reset_index()
                fig_brand = px.pie(brand_df, names='品牌', values='Total Cost', title="品牌占比分布", hole=0.4)
                st.plotly_chart(fig_brand, use_container_width=True)

    # Tab 3: 运营人员绩效
    with tab3:
        st.subheader("运营人员业绩对比")
        if '运营' in df.columns and 'Total Cost' in df.columns:
            op_df = df.groupby('运营').agg({'Total Cost': 'sum', 'Quantity': 'sum', 'PO Number': 'nunique'}).reset_index()
            op_df.columns = ['运营', '总销售额', '总销量', '订单数']
            st.dataframe(op_df.style.highlight_max(axis=0, color='#d1e7dd'), use_container_width=True)
            
            fig_op = px.bar(op_df, x='运营', y='总销售额', text_auto='.2s', title="各运营销售额贡献")
            st.plotly_chart(fig_op, use_container_width=True)

    # Tab 4: 地区分布与物流状态
    with tab4:
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("地区/州订单量分布")
            state_col = 'ShipTo State' if 'ShipTo State' in df.columns else 'ShipTo Country'
            if state_col in df.columns:
                state_df = df.groupby(state_col)['PO Number'].nunique().reset_index().sort_values(by='PO Number', ascending=False).head(15)
                fig_state = px.bar(state_df, x=state_col, y='PO Number', title="前15个热门发货地区")
                st.plotly_chart(fig_state, use_container_width=True)

        with col2:
            st.subheader("订单状态分布 (Line Status)")
            if 'Line Status' in df.columns:
                status_df = df['Line Status'].value_counts().reset_index()
                status_df.columns = ['状态', '数量']
                fig_status = px.pie(status_df, names='状态', values='数量', title="订单状态占比")
                st.plotly_chart(fig_status, use_container_width=True)

    # 5. 明细表格数据展示
    st.divider()
    st.subheader("📋 详细数据列表")
    st.dataframe(df, use_container_width=True)

else:
    st.info("💡 请在左侧边栏上传 CSV 或 Excel 数据文件以解锁看板功能。")
