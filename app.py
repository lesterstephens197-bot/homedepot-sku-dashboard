import streamlit as st
import pandas as pd
import plotly.graph_objects as go

# 页面配置
st.set_page_config(
    page_title="Home Depot SKU Daily Sales Analytics",
    page_icon="🛒",
    layout="wide"
)

st.title("🛒 Home Depot 单 SKU 日均销量分析看板")
st.markdown("---")

# 1. 侧边栏文件上传
st.sidebar.header("⚙️ 数据配置")
uploaded_file = st.sidebar.file_uploader("上传 Home Depot 销售报表 (CSV/Excel)", type=["csv", "xlsx"])

if uploaded_file:
    try:
        # 读取文件
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)
    except Exception as e:
        st.error(f"文件读取失败，请检查文件格式: {e}")
        st.stop()

    # 清理表头首尾空格
    df.columns = df.columns.str.strip()

    # 2. 精准匹配你的表头列名
    # 日期列优先找 '日期'
    date_col = next((c for c in df.columns if c in ['日期', 'Date', 'sales_date']), None)
    
    # SKU 优先列顺序：OMS ID (HD Internet #) -> Merchant SKU -> Vendor SKU -> SKU
    sku_col = None
    for target_sku in ['OMS ID', 'Merchant SKU', 'Vendor SKU', 'SKU', 'Internet #']:
        if target_sku in df.columns:
            sku_col = target_sku
            break

    # 销量列优先找 '销量'
    sales_col = next((c for c in df.columns if c in ['销量', 'Units Sold', 'Units', 'Quantity']), None)
    
    # 金额列优先找 'Total Cost'，其次 'Unit Cost'
    revenue_col = next((c for c in df.columns if c in ['Total Cost', 'Net Sales', 'Sales', 'Total Amount']), None)

    # 检查核心列是否存在
    if not date_col or not sku_col or not sales_col:
        st.error(f"解析失败！未能在表格中识别到必需列（日期、SKU 或 销量）。现识别到的列有: {list(df.columns)}")
        st.stop()

    # 3. 数据清洗与规范化
    df['Clean_Date'] = pd.to_datetime(df[date_col])
    df['Clean_Units'] = pd.to_numeric(df[sales_col], errors='coerce').fillna(0)
    
    # 如果有 Total Cost 列直接用；若只有 Unit Cost 则乘以销量
    if revenue_col:
        df['Clean_Revenue'] = pd.to_numeric(df[revenue_col], errors='coerce').fillna(0)
    elif 'Unit Cost' in df.columns:
        unit_cost = pd.to_numeric(df['Unit Cost'], errors='coerce').fillna(0)
        df['Clean_Revenue'] = unit_cost * df['Clean_Units']
    else:
        df['Clean_Revenue'] = 0

    # 4. 侧边栏筛选器
    st.sidebar.markdown("---")
    
    # 允许选择作为识别主键的字段（方便按 OMS ID 或 Merchant SKU 查）
    sku_selector_col = st.sidebar.selectbox("选择检索的 SKU 标识字段", [sku_col] + [c for c in ['OMS ID', 'Merchant SKU', 'Vendor SKU', 'SKU'] if c in df.columns and c != sku_col])
    
    sku_list = sorted(df[sku_selector_col].dropna().astype(str).unique())
    selected_sku = st.sidebar.selectbox(f"选择具体 SKU ({sku_selector_col})", sku_list)

    # 显示产品辅助信息（产品名称 / 运营）
    sku_mask = df[sku_selector_col].astype(str) == selected_sku
    product_name = df[sku_mask]['产品名称'].iloc[0] if '产品名称' in df.columns and not df[sku_mask]['产品名称'].empty else "无"
    operator_name = df[sku_mask]['运营'].iloc[0] if '运营' in df.columns and not df[sku_mask]['运营'].empty else "无"

    st.sidebar.info(f"**产品名称**: {product_name}\n\n**负责人**: {operator_name}")

    # 日期区间选择
    min_d = df['Clean_Date'].min().date()
    max_d = df['Clean_Date'].max().date()
    date_range = st.sidebar.date_input("分析日期区间", [min_d, max_d], min_value=min_d, max_value=max_d)

    start_date = date_range[0] if len(date_range) >= 1 else min_d
    end_date = date_range[1] if len(date_range) == 2 else max_d

    # 5. 数据切片与汇总
    filter_mask = sku_mask & (df['Clean_Date'].dt.date >= start_date) & (df['Clean_Date'].dt.date <= end_date)
    sku_df = df[filter_mask].sort_values('Clean_Date')

    if not sku_df.empty:
        # 按单日汇总销量与金额
        daily_summary = sku_df.groupby('Clean_Date').agg({
            'Clean_Units': 'sum',
            'Clean_Revenue': 'sum'
        }).reset_index()

        # 计算天数与动销指标
        total_days = (daily_summary['Clean_Date'].max() - daily_summary['Clean_Date'].min()).days + 1
        total_units = daily_summary['Clean_Units'].sum()
        total_revenue = daily_summary['Clean_Revenue'].sum()

        # 有出单的动销天数
        active_days = len(daily_summary[daily_summary['Clean_Units'] > 0])

        overall_avg = total_units / total_days if total_days > 0 else 0
        active_avg = total_units / active_days if active_days > 0 else 0

        # 滑动平均计算
        daily_summary['7D_Avg'] = daily_summary['Clean_Units'].rolling(7, min_periods=1).mean()
        daily_summary['14D_Avg'] = daily_summary['Clean_Units'].rolling(14, min_periods=1).mean()
        daily_summary['30D_Avg'] = daily_summary['Clean_Units'].rolling(30, min_periods=1).mean()

        # 6. KPI 卡片展示
        st.subheader(f"📌 SKU ({sku_selector_col}: {selected_sku}) - 运营数据看板")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("区间总销量", f"{int(total_units):,} 件")
        col2.metric("区间总金额", f"${total_revenue:,.2f}")
        col3.metric("全量日均 (Overall)", f"{overall_avg:.1f} 件/天")
        col4.metric("动销日均 (Excl. 0 Sales)", f"{active_avg:.1f} 件/天", 
                    delta=f"{active_avg - overall_avg:+.1f} (出单日均)", delta_color="normal")

        st.markdown("---")

        # 7. 动态销量走势图
        st.subheader("📈 每日销量走势与移动平均 (7D / 14D / 30D)")

        fig = go.Figure()

        # 柱状图：每日实际销量
        fig.add_trace(go.Bar(
            x=daily_summary['Clean_Date'],
            y=daily_summary['Clean_Units'],
            name='单日销量',
            marker_color='#94A3B8',
            opacity=0.7
        ))

        # 7日线
        fig.add_trace(go.Scatter(
            x=daily_summary['Clean_Date'],
            y=daily_summary['7D_Avg'],
            name='7日移动平均',
            line=dict(color='#10B981', width=1.5)
        ))

        # 14日线
        fig.add_trace(go.Scatter(
            x=daily_summary['Clean_Date'],
            y=daily_summary['14D_Avg'],
            name='14日移动平均',
            line=dict(color='#3B82F6', width=2.5)
        ))

        # 30日线
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
            margin=dict(l=20, r=20, t=30, b=20)
        )

        st.plotly_chart(fig, use_container_width=True)

        # 8. 明细列表
        with st.expander("查看数据源明细数据"):
            st.dataframe(
                daily_summary.rename(columns={
                    'Clean_Date': '日期',
                    'Clean_Units': '单日销量',
                    'Clean_Revenue': '总金额',
                    '7D_Avg': '7日均值',
                    '14D_Avg': '14日均值',
                    '30D_Avg': '30日均值'
                })
            )
    else:
        st.warning("该日期区间内无选中 SKU 的销量数据。")

else:
    st.info("👋 请在左侧上传带有上述表头信息的 Excel 或 CSV 销售报表。")
