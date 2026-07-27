import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# 页面配置
st.set_page_config(
    page_title="Home Depot SKU Daily Sales Dashboard",
    page_icon="🛒",
    layout="wide"
)

st.title("🛒 Home Depot 单 SKU 日均销量分析看板")
st.markdown("---")

# 1. 侧边栏文件上传
st.sidebar.header("数据导入与设置")
uploaded_file = st.sidebar.file_uploader("上传 Supplier Hub 销售报表 (CSV 或 Excel)", type=["csv", "xlsx"])

if uploaded_file:
    # 读取数据
    try:
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)
    except Exception as e:
        st.error(f"读取文件失败，请检查文件格式: {e}")
        st.stop()

    # 2. 列名兼容性处理与预处理
    # 自动匹配常见字段名称
    date_col = next((c for c in df.columns if c.lower() in ['date', '日期', 'sales_date']), None)
    sku_col = next((c for c in df.columns if c.lower() in ['sku', 'internet #', 'retail sku', 'item']), None)
    sales_col = next((c for c in df.columns if c.lower() in ['units sold', 'units', 'sales_units', '销量']), None)
    revenue_col = next((c for c in df.columns if c.lower() in ['net sales', 'sales', 'revenue', '销售额']), None)
    inventory_col = next((c for c in df.columns if c.lower() in ['onhand inventory', 'on hand', 'inventory', '库存']), None)

    if not date_col or not sku_col or not sales_col:
        st.error("数据集中缺少必需字段（日期、SKU、销量），请检查导入的文件。")
        st.stop()

    # 数据格式清洗
    df['Clean_Date'] = pd.to_datetime(df[date_col])
    df['Clean_Units'] = pd.to_numeric(df[sales_col], errors='coerce').fillna(0)
    df['Clean_Revenue'] = pd.to_numeric(df[revenue_col], errors='coerce').fillna(0) if revenue_col else 0
    df['Clean_OnHand'] = pd.to_numeric(df[inventory_col], errors='coerce').fillna(1) if inventory_col else 1

    # 3. 筛选器
    sku_list = sorted(df[sku_col].dropna().astype(str).unique())
    selected_sku = st.sidebar.selectbox("选择要分析的 SKU / Internet #", sku_list)

    min_d = df['Clean_Date'].min().date()
    max_d = df['Clean_Date'].max().date()
    date_range = st.sidebar.date_input("选择日期区间", [min_d, max_d], min_value=min_d, max_value=max_d)

    if len(date_range) == 2:
        start_date, end_date = date_range
    else:
        start_date, end_date = min_d, max_d

    # 数据切片
    mask = (df[sku_col].astype(str) == selected_sku) & \
           (df['Clean_Date'].dt.date >= start_date) & \
           (df['Clean_Date'].dt.date <= end_date)
    sku_df = df[mask].sort_values('Clean_Date')

    if not sku_df.empty:
        # 按日期汇总（防止单日多条渠道明细重合）
        daily_summary = sku_df.groupby('Clean_Date').agg({
            'Clean_Units': 'sum',
            'Clean_Revenue': 'sum',
            'Clean_OnHand': 'sum'
        }).reset_index()

        # 计算核心指标
        total_days = (daily_summary['Clean_Date'].max() - daily_summary['Clean_Date'].min()).days + 1
        total_units = daily_summary['Clean_Units'].sum()
        total_revenue = daily_summary['Clean_Revenue'].sum()

        # 剔除库存为 0 且无销量的断货天数
        in_stock_df = daily_summary[(daily_summary['Clean_OnHand'] > 0) | (daily_summary['Clean_Units'] > 0)]
        in_stock_days = len(in_stock_df)

        overall_avg = total_units / total_days if total_days > 0 else 0
        instock_avg = total_units / in_stock_days if in_stock_days > 0 else 0

        # 滑动平均计算
        daily_summary['7D_Avg'] = daily_summary['Clean_Units'].rolling(window=7, min_periods=1).mean()
        daily_summary['14D_Avg'] = daily_summary['Clean_Units'].rolling(window=14, min_periods=1).mean()
        daily_summary['30D_Avg'] = daily_summary['Clean_Units'].rolling(window=30, min_periods=1).mean()

        # 4. 展示 KPI 卡片
        st.subheader(f"📌 SKU: {selected_sku} 核心表现")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("累计总销量", f"{int(total_units):,} 件")
        col2.metric("累计总销售额", f"${total_revenue:,.2f}")
        col3.metric("自然日均销量 (Overall)", f"{overall_avg:.1f} 件/天")
        col4.metric(
            "有库存日均销量 (In-Stock)", 
            f"{instock_avg:.1f} 件/天", 
            delta=f"{instock_avg - overall_avg:+.1f} (剔除断货影响)"
        )

        st.markdown("---")

        # 5. 趋势图表
        st.subheader("📈 日销量趋势与移动平均 (7D / 14D / 30D)")

        fig = go.Figure()

        # 每日实际销量柱状图
        fig.add_trace(go.Bar(
            x=daily_summary['Clean_Date'],
            y=daily_summary['Clean_Units'],
            name='单日销量',
            marker_color='#CBD5E1',
            opacity=0.7
        ))

        # 7日均线
        fig.add_trace(go.Scatter(
            x=daily_summary['Clean_Date'],
            y=daily_summary['7D_Avg'],
            name='7日移动平均',
            line=dict(color='#10B981', width=1.5)
        ))

        # 14日均线
        fig.add_trace(go.Scatter(
            x=daily_summary['Clean_Date'],
            y=daily_summary['14D_Avg'],
            name='14日移动平均',
            line=dict(color='#3B82F6', width=2.5)
        ))

        # 30日趋势线
        fig.add_trace(go.Scatter(
            x=daily_summary['Clean_Date'],
            y=daily_summary['30D_Avg'],
            name='30日趋势线',
            line=dict(color='#EF4444', width=2, dash='dash')
        ))

        fig.update_layout(
            hovermode="x unified",
            xaxis_title="日期",
            yaxis_title="销量 (Units)",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(l=20, r=20, t=40, b=20)
        )

        st.plotly_chart(fig, use_container_width=True)

        # 6. 数据明细展开
        with st.expander("查看每日数据明细"):
            st.dataframe(
                daily_summary.rename(columns={
                    'Clean_Date': '日期',
                    'Clean_Units': '销量',
                    'Clean_Revenue': '销售额',
                    'Clean_OnHand': '库存',
                    '7D_Avg': '7日均值',
                    '14D_Avg': '14日均值',
                    '30D_Avg': '30日均值'
                })
            )
    else:
        st.warning("选定时间范围内没有找到该 SKU 的销售记录。")

else:
    st.info("👋 请在左侧边栏上传从 Supplier Hub / Analytics 导出的销售数据表格（CSV 或 Excel）。")
