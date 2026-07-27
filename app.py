import streamlit as st
import pandas as pd
import plotly.graph_objects as go

# 页面基础配置
st.set_page_config(
    page_title="Home Depot 产品 SKU 销量分析看板",
    page_icon="📦",
    layout="wide"
)

st.title("📦 Home Depot 产品 SKU 深度日均销量看板")
st.markdown("---")

# 1. 侧边栏：数据文件导入与设置
st.sidebar.header("⚙️ 数据与维度设置")
uploaded_file = st.sidebar.file_uploader("上传 Home Depot 销售报表 (CSV/Excel)", type=["csv", "xlsx"])

if uploaded_file:
    try:
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)
    except Exception as e:
        st.error(f"读取文件失败，请检查文件格式: {e}")
        st.stop()

    # 清理表头首尾空格
    df.columns = df.columns.str.strip()

    # 2. 表头字段匹配 (强指定：优先抓取 'SKU' 列)
    # 日期列
    date_col = next((c for c in df.columns if c in ['日期', 'Date', 'sales_date']), None)
    
    # 销量列
    sales_col = next((c for c in df.columns if c in ['销量', 'Units Sold', 'Units', 'Quantity']), None)
    
    # SKU 优先级调整：强制将 'SKU' 列排在第一位，其次才是其他 ID
    sku_fields_available = []
    for col_name in ['SKU', 'Merchant SKU', 'Vendor SKU', 'OMS ID', 'Internet #']:
        if col_name in df.columns:
            sku_fields_available.append(col_name)

    if not date_col or not sales_col or not sku_fields_available:
        st.error(f"解析失败！未能在表格中识别到必需列（日期、销量或 SKU 列）。现识别到的列有: {list(df.columns)}")
        st.stop()

    # 3. 维度选择 (默认直接选中 'SKU')
    st.sidebar.markdown("### 1. 选择检索维度")
    primary_sku_col = st.sidebar.selectbox("分析主键", sku_fields_available, index=0)

    # 数据格式清洗
    df['Clean_Date'] = pd.to_datetime(df[date_col])
    df['Clean_Units'] = pd.to_numeric(df[sales_col], errors='coerce').fillna(0)

    # 4. 产品 SKU 下拉选择器
    sku_list = sorted(df[primary_sku_col].dropna().astype(str).unique())
    st.sidebar.markdown("### 2. 选择产品 SKU")
    selected_sku = st.sidebar.selectbox(f"选择具体 {primary_sku_col}", sku_list)

    # 提取当前产品 SKU 的属性信息
    sku_mask = df[primary_sku_col].astype(str) == selected_sku
    sku_info = df[sku_mask].iloc[0]

    # 侧边栏属性卡片展示
    p_name = sku_info.get('产品名称', '未填写')
    p_operator = sku_info.get('运营', '未分配')
    p_sku = sku_info.get('SKU', '无')
    p_oms = sku_info.get('OMS ID', '无')
    p_merchant = sku_info.get('Merchant SKU', '无')
    p_vendor = sku_info.get('Vendor SKU', '无')

    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📋 产品 SKU 详细属性")
    st.sidebar.info(
        f"**产品 SKU**: {p_sku}\n\n"
        f"**产品名称**: {p_name}\n\n"
        f"**运营负责人**: {p_operator}\n\n"
        f"**OMS ID**: {p_oms}\n\n"
        f"**Merchant SKU**: {p_merchant}\n\n"
        f"**Vendor SKU**: {p_vendor}"
    )

    # 日期范围筛选
    min_d = df['Clean_Date'].min().date()
    max_d = df['Clean_Date'].max().date()
    date_range = st.sidebar.date_input("分析时间范围", [min_d, max_d], min_value=min_d, max_value=max_d)

    start_date = date_range[0] if len(date_range) >= 1 else min_d
    end_date = date_range[1] if len(date_range) == 2 else max_d

    # 5. 数据过滤与聚合
    filter_mask = sku_mask & (df['Clean_Date'].dt.date >= start_date) & (df['Clean_Date'].dt.date <= end_date)
    sku_df = df[filter_mask].sort_values('Clean_Date')

    if not sku_df.empty:
        # 按日汇总销量
        daily_summary = sku_df.groupby('Clean_Date').agg({
            'Clean_Units': 'sum'
        }).reset_index()

        # 计算日均与动销指标
        total_days = (daily_summary['Clean_Date'].max() - daily_summary['Clean_Date'].min()).days + 1
        total_units = daily_summary['Clean_Units'].sum()

        # 有实际出单的动销天数
        active_days = len(daily_summary[daily_summary['Clean_Units'] > 0])

        overall_avg = total_units / total_days if total_days > 0 else 0
        active_avg = total_units / active_days if active_days > 0 else 0

        # 滑动平均计算 (7D, 14D, 30D)
        daily_summary['7D_Avg'] = daily_summary['Clean_Units'].rolling(7, min_periods=1).mean()
        daily_summary['14D_Avg'] = daily_summary['Clean_Units'].rolling(14, min_periods=1).mean()
        daily_summary['30D_Avg'] = daily_summary['Clean_Units'].rolling(30, min_periods=1).mean()

        # 6. KPI 指标卡片展示
        st.subheader(f"📌 产品 SKU: {selected_sku} ( {p_name} )")
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("区间总销量", f"{int(total_units):,} 件")
        col2.metric("总天数 / 动销天数", f"{total_days} 天 / {active_days} 天")
        col3.metric("全量自然日均 (Overall)", f"{overall_avg:.1f} 件/天")
        col4.metric(
            "动销日均 (Excl. 0 Sales)", 
            f"{active_avg:.1f} 件/天", 
            delta=f"{active_avg - overall_avg:+.1f} (剔除未出单/断货日)", 
            delta_color="normal"
        )

        st.markdown("---")

        # 7. 趋势走势图表
        st.subheader("📈 产品 SKU 每日销量走势与 7D / 14D / 30D 移动平均线")

        fig = go.Figure()

        # 每日真实销量柱状图
        fig.add_trace(go.Bar(
            x=daily_summary['Clean_Date'],
            y=daily_summary['Clean_Units'],
            name='单日销量',
            marker_color='#CBD5E1',
            opacity=0.75
        ))

        # 7 日均线
        fig.add_trace(go.Scatter(
            x=daily_summary['Clean_Date'],
            y=daily_summary['7D_Avg'],
            name='7日移动平均 (7D)',
            line=dict(color='#10B981', width=1.5)
        ))

        # 14 日均线
        fig.add_trace(go.Scatter(
            x=daily_summary['Clean_Date'],
            y=daily_summary['14D_Avg'],
            name='14日移动平均 (14D)',
            line=dict(color='#3B82F6', width=2.5)
        ))

        # 30 日趋势线
        fig.add_trace(go.Scatter(
            x=daily_summary['Clean_Date'],
            y=daily_summary['30D_Avg'],
            name='30日趋势线 (30D)',
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

        # 8. 明细表格
        with st.expander("📄 查看该产品 SKU 每日汇总明细"):
            st.dataframe(
                daily_summary.rename(columns={
                    'Clean_Date': '日期',
                    'Clean_Units': '单日销量',
                    '7D_Avg': '7日均值',
                    '14D_Avg': '14日均值',
                    '30D_Avg': '30日均值'
                }),
                use_container_width=True
            )
    else:
        st.warning("选定日期范围内未查找到该产品 SKU 的销量记录。")
else:
    st.info("👋 请在左侧上传带有 `SKU`、`日期`、`销量` 等列的 Excel 或 CSV 销售报表。")
