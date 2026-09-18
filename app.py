# =========================================================================
# TAB 1: 核心总销售看板 (包含总销售、总销量、平均客单价、总单量、近7/15天对比)
# =========================================================================
st.header("📊 全局与近7天/近15天 核心总销售看板")

if 'Order Date' in df.columns and not df['Order Date'].isna().all():
    max_date = df['Order Date'].max().date()
    min_date = df['Order Date'].min().date()

    # 1. 快捷时间范围切换
    st.subheader("⏱️ 时间区间快捷切换")
    period_option = st.radio(
        "选择看板时间范围:", 
        ["近 7 天 (Recent 7 Days)", "近 15 天 (Recent 15 Days)", "近 30 天 (Recent 30 Days)", "全量数据 / 自定义范围"], 
        horizontal=True
    )

    # 2. 根据选定周期切片数据与计算上一周期（用于环比）
    if "近 7 天" in period_option:
        start_date = max_date - timedelta(days=6)
        prev_start_date = start_date - timedelta(days=7)
        prev_end_date = start_date - timedelta(days=1)
        curr_label = f"近 7 天 ({start_date} ~ {max_date})"
    elif "近 15 天" in period_option:
        start_date = max_date - timedelta(days=14)
        prev_start_date = start_date - timedelta(days=15)
        prev_end_date = start_date - timedelta(days=1)
        curr_label = f"近 15 天 ({start_date} ~ {max_date})"
    elif "近 30 天" in period_option:
        start_date = max_date - timedelta(days=29)
        prev_start_date = start_date - timedelta(days=30)
        prev_end_date = start_date - timedelta(days=1)
        curr_label = f"近 30 天 ({start_date} ~ {max_date})"
    else:
        start_date, max_date = min_date, max_date
        prev_start_date, prev_end_date = None, None
        curr_label = f"全量数据区间 ({start_date} ~ {max_date})"

    # 数据过滤
    filtered_df = df[(df['Order Date'].dt.date >= start_date) & (df['Order Date'].dt.date <= max_date)]
    prev_df = df[(df['Order Date'].dt.date >= prev_start_date) & (df['Order Date'].dt.date <= prev_end_date)] if prev_start_date else pd.DataFrame()

    # KPI 计算函数
    def calc_kpis(data_df):
        sales = data_df['Total Cost'].sum() if 'Total Cost' in data_df.columns else 0
        qty = data_df['Quantity'].sum() if 'Quantity' in data_df.columns else 0
        orders = data_df['PO Number'].nunique() if 'PO Number' in data_df.columns else len(data_df)
        aov = sales / orders if orders > 0 else 0
        return sales, qty, orders, aov

    curr_sales, curr_qty, curr_orders, curr_aov = calc_kpis(filtered_df)
    prev_sales, prev_qty, prev_orders, prev_aov = calc_kpis(prev_df)

    # 计算环比
    sales_delta = f"{((curr_sales - prev_sales)/prev_sales*100):+.1f}% 环比" if prev_sales > 0 else None
    qty_delta = f"{((curr_qty - prev_qty)/prev_qty*100):+.1f}% 环比" if prev_qty > 0 else None
    orders_delta = f"{((curr_orders - prev_orders)/prev_orders*100):+.1f}% 环比" if prev_orders > 0 else None
    aov_delta = f"{((curr_aov - prev_aov)/prev_aov*100):+.1f}% 环比" if prev_aov > 0 else None

    st.caption(f"当前视图：**{curr_label}**")

    # 3. 核心 4 大指标卡片展示 (含环比 Delta)
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric("💰 总销售额 (Total Sales)", f"${curr_sales:,.2f}", delta=sales_delta)
    kpi2.metric("📦 总销量 (Total Quantity)", f"{int(curr_qty):,} 件", delta=qty_delta)
    kpi3.metric("💳 平均客单价 (AOV)", f"${curr_aov:,.2f}", delta=aov_delta)
    kpi4.metric("📄 总订单量 (Total POs)", f"{curr_orders:,} 单", delta=orders_delta)

    st.divider()

    # 4. 近 7 天 vs 近 15 天 销售数据对比表
    st.subheader("⚔️ 近 7 天 vs 近 15 天 核心指标快速对比")
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

    # 5. 销售趋势图
    st.subheader("📈 销售额走势图")
    daily_df = filtered_df.set_index('Order Date').resample('D').agg({'Total Cost': 'sum'}).reset_index()
    fig_trend = px.line(daily_df, x='Order Date', y='Total Cost', title="销售额每日走势", markers=True)
    st.plotly_chart(fig_trend, use_container_width=True)
