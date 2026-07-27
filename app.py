import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# 页面基础配置
st.set_page_config(
    page_title="Home Depot 销售与品类分析看板",
    page_icon="📊",
    layout="wide"
)

st.title("📊 Home Depot 销售与品类深度分析看板")
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

    # 2. 表头字段匹配
    date_col = next((c for c in df.columns if c in ['日期', 'Date', 'sales_date']), None)
    sales_col = next((c for c in df.columns if c in ['销量', 'Units Sold', 'Units', 'Quantity']), None)
    cost_col = next((c for c in df.columns if c in ['Total Cost', 'Cost', '金额', '总金额']), None)
    category_col = next((c for c in df.columns if c in ['产品名称', 'Category', '品类', '品类名称']), None)
    state_col = next((c for c in df.columns if c in ['ShipTo State', 'State', '州', '省份']), None)

    # 按照优先级匹配产品 SKU 列
    sku_fields_available = []
    for col_name in ['产品SKU', 'SKU', 'Merchant SKU', 'Vendor SKU', 'OMS ID']:
        if col_name in df.columns:
            sku_fields_available.append(col_name)

    if not date_col or not sales_col or not sku_fields_available:
        st.error(f"解析失败！未能在表格中识别到必需列（日期、销量或产品SKU列）。当前识别到的表头列为: {list(df.columns)}")
        st.stop()

    # 数据清洗
    df['Clean_Date'] = pd.to_datetime(df[date_col])
    df['Clean_Units'] = pd.to_numeric(df[sales_col], errors='coerce').fillna(0)
    df['Clean_Cost'] = pd.to_numeric(df[cost_col], errors='coerce').fillna(0) if cost_col else 0
    if category_col:
        df['Clean_Category'] = df[category_col].astype(str).str.strip().replace({'nan': '未分类', 'None': '未分类', '': '未分类'})
    else:
        df['Clean_Category'] = '未分类'

    if state_col:
        df['Clean_State'] = df[state_col].astype(str).str.strip().str.upper().replace({'NAN': '未知', 'NONE': '未知', '': '未知'})

    # 3. 日期范围筛选
    min_d = df['Clean_Date'].min().date()
    max_d = df['Clean_Date'].max().date()
    
    st.sidebar.markdown("### 1. 时间范围筛选")
    date_range = st.sidebar.date_input("分析时间范围", [min_d, max_d], min_value=min_d, max_value=max_d)

    start_date = date_range[0] if len(date_range) >= 1 else min_d
    end_date = date_range[1] if len(date_range) == 2 else max_d

    # 切片过滤日期
    time_mask = (df['Clean_Date'].dt.date >= start_date) & (df['Clean_Date'].dt.date <= end_date)
    filtered_df = df[time_mask]

    # 4. 分析模式选择
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 2. 分析视角选择")
    view_mode = st.sidebar.radio("请选择看板视角", ["📦 单产品 SKU 深度看板", "🏷️ 产品品类 (产品名称) 汇总看板", "🌐 全大盘总体看板"])

    # ---------------------------------------------------------
    # 视角 1：单产品 SKU 深度看板
    # ---------------------------------------------------------
    if view_mode == "📦 单产品 SKU 深度看板":
        primary_sku_col = st.sidebar.selectbox("分析主键列", sku_fields_available, index=0)
        sku_list = sorted(filtered_df[primary_sku_col].dropna().astype(str).unique())
        selected_sku = st.sidebar.selectbox(f"选择 {primary_sku_col}", sku_list)

        sku_df = filtered_df[filtered_df[primary_sku_col].astype(str) == selected_sku].sort_values('Clean_Date')

        if not sku_df.empty:
            sku_info = sku_df.iloc[0]
            p_sku = sku_info.get('产品SKU', sku_info.get('SKU', '无'))
            p_name = sku_info.get('产品名称', '未填写')
            p_operator = sku_info.get('运营', '未分配')

            # KPI 指标
            total_units = sku_df['Clean_Units'].sum()
            total_cost = sku_df['Clean_Cost'].sum()
            
            daily_summary = sku_df.groupby('Clean_Date').agg({
                'Clean_Units': 'sum',
                'Clean_Cost': 'sum'
            }).reset_index()

            total_days = (daily_summary['Clean_Date'].max() - daily_summary['Clean_Date'].min()).days + 1
            active_days = len(daily_summary[daily_summary['Clean_Units'] > 0])
            overall_avg = total_units / total_days if total_days > 0 else 0
            active_avg = total_units / active_days if active_days > 0 else 0

            st.subheader(f"📌 产品 SKU: {selected_sku}（{p_name}）")
            st.caption(f"运营负责人: {p_operator}")

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("区间总销量 (Units)", f"{int(total_units):,} 件")
            c2.metric("区间总金额 (Total Cost)", f"${total_cost:,.2f}")
            c3.metric("全量自然日均销量", f"{overall_avg:.1f} 件/天")
            c4.metric("动销日均销量", f"{active_avg:.1f} 件/天")

            st.markdown("---")

            # 双轴趋势图（销量 + Total Cost）
            st.subheader("📈 每日销量 (Units) 与 销售金额 (Total Cost) 走势")
            fig_twin = go.Figure()

            fig_twin.add_trace(go.Bar(
                x=daily_summary['Clean_Date'],
                y=daily_summary['Clean_Units'],
                name='销量 (件)',
                marker_color='#3B82F6',
                opacity=0.7
            ))

            fig_twin.add_trace(go.Scatter(
                x=daily_summary['Clean_Date'],
                y=daily_summary['Clean_Cost'],
                name='Total Cost ($)',
                yaxis='y2',
                line=dict(color='#EF4444', width=2.5)
            ))

            fig_twin.update_layout(
                hovermode="x unified",
                xaxis_title="日期",
                yaxis=dict(title="销量 (件)"),
                yaxis2=dict(title="Total Cost ($)", overlaying='y', side='right'),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            st.plotly_chart(fig_twin, use_container_width=True)

            # 地图
            if state_col and 'Clean_State' in sku_df.columns:
                st.markdown("---")
                st.subheader("🗺️ 该 SKU 全美州级销量地图")
                state_df = sku_df.groupby('Clean_State').agg({'Clean_Units': 'sum', 'Clean_Cost': 'sum'}).reset_index()
                state_df['Share_Pct'] = (state_df['Clean_Units'] / total_units) * 100 if total_units > 0 else 0

                fig_map = px.choropleth(
                    state_df,
                    locations='Clean_State',
                    locationmode="USA-states",
                    color='Clean_Units',
                    scope="usa",
                    color_continuous_scale="Reds",
                    hover_data={'Clean_Units': ':,', 'Clean_Cost': ':$,.2f', 'Share_Pct': ':.2f%'},
                    title="各州销量热力分布"
                )
                st.plotly_chart(fig_map, use_container_width=True)

    # ---------------------------------------------------------
    # 视角 2：产品品类 (产品名称) 汇总看板
    # ---------------------------------------------------------
    elif view_mode == "🏷️ 产品品类 (产品名称) 汇总看板":
        st.subheader("🏷️ 产品品类 (产品名称) 销售数据看板")

        category_summary = filtered_df.groupby('Clean_Category').agg({
            'Clean_Units': 'sum',
            'Clean_Cost': 'sum',
            '产品SKU': 'nunique'
        }).reset_index().rename(columns={'产品SKU': 'SKU数量'})

        total_cat_units = category_summary['Clean_Units'].sum()
        total_cat_cost = category_summary['Clean_Cost'].sum()

        category_summary['Sales_Share'] = (category_summary['Clean_Units'] / total_cat_units) * 100 if total_cat_units > 0 else 0
        category_summary['Cost_Share'] = (category_summary['Clean_Cost'] / total_cat_cost) * 100 if total_cat_cost > 0 else 0
        category_summary = category_summary.sort_values(by='Clean_Cost', ascending=False)

        # 汇总 KPI
        c1, c2, c3 = st.columns(3)
        c1.metric("全品类总销量", f"{int(total_cat_units):,} 件")
        c2.metric("全品类总销售额 (Total Cost)", f"${total_cat_cost:,.2f}")
        c3.metric("涵盖品类数量", f"{len(category_summary)} 个品类")

        st.markdown("---")

        col_cat1, col_cat2 = st.columns(2)

        with col_cat1:
            fig_cat_bar = px.bar(
                category_summary,
                x='Clean_Category',
                y='Clean_Cost',
                text='Clean_Cost',
                title="各品类销售额 (Total Cost) 排名",
                labels={'Clean_Category': '产品名称/品类', 'Clean_Cost': 'Total Cost ($)'},
                color='Clean_Cost',
                color_continuous_scale='Blues'
            )
            fig_cat_bar.update_traces(texttemplate='$%{text:,.0f}', textposition='outside')
            st.plotly_chart(fig_cat_bar, use_container_width=True)

        with col_cat2:
            fig_cat_pie = px.pie(
                category_summary,
                values='Clean_Units',
                names='Clean_Category',
                title="各品类销量 (件数) 占比分布",
                hole=0.4
            )
            fig_cat_pie.update_traces(textinfo='percent+label')
            st.plotly_chart(fig_cat_pie, use_container_width=True)

        st.markdown("---")

        # 品类明细表格
        st.markdown("### 📋 品类数据明细表")
        st.dataframe(
            category_summary.rename(columns={
                'Clean_Category': '产品名称 (品类)',
                'Clean_Units': '总销量 (件)',
                'Clean_Cost': '总金额 Total Cost ($)',
                'Sales_Share': '销量占比 (%)',
                'Cost_Share': '销售额占比 (%)'
            }).style.format({
                '总销量 (件)': '{:,.0f}',
                '总金额 Total Cost ($)': '${:,.2f}',
                '销量占比 (%)': '{:.2f}%',
                '销售额占比 (%)': '{:.2f}%'
            }),
            use_container_width=True
        )

        st.markdown("---")

        # 单个品类深入下钻分析
        selected_category = st.selectbox("🔍 选择特定品类进行下钻明细查看", category_summary['Clean_Category'].tolist())
        cat_df = filtered_df[filtered_df['Clean_Category'] == selected_category]

        st.markdown(f"#### 📌 品类：【{selected_category}】 下的 SKU 表现排名")
        sku_in_cat = cat_df.groupby('产品SKU').agg({
            'Clean_Units': 'sum',
            'Clean_Cost': 'sum',
            '运营': 'first'
        }).reset_index().sort_values(by='Clean_Units', ascending=False)

        st.dataframe(
            sku_in_cat.rename(columns={
                'Clean_Units': '销量 (件)',
                'Clean_Cost': 'Total Cost ($)',
                '运营': '运营负责人'
            }).style.format({'销量 (件)': '{:,.0f}', 'Total Cost ($)': '${:,.2f}'}),
            use_container_width=True
        )

    # ---------------------------------------------------------
    # 视角 3：全大盘总体看板
    # ---------------------------------------------------------
    else:
        st.subheader("🌐 Home Depot 全大盘销售数据概览")

        total_units = filtered_df['Clean_Units'].sum()
        total_cost = filtered_df['Clean_Cost'].sum()
        total_orders = filtered_df['PO Number'].nunique() if 'PO Number' in filtered_df.columns else len(filtered_df)

        c1, c2, c3 = st.columns(3)
        c1.metric("全盘总销量 (Units)", f"{int(total_units):,} 件")
        c2.metric("全盘总金额 (Total Cost)", f"${total_cost:,.2f}")
        c3.metric("总订单数 (PO 件数)", f"{total_orders:,} 单")

        st.markdown("---")

        # 每日整体大盘走势
        daily_overall = filtered_df.groupby('Clean_Date').agg({
            'Clean_Units': 'sum',
            'Clean_Cost': 'sum'
        }).reset_index()

        fig_overall = go.Figure()
        fig_overall.add_trace(go.Bar(x=daily_overall['Clean_Date'], y=daily_overall['Clean_Units'], name='每日销量 (件)', marker_color='#93C5FD'))
        fig_overall.add_trace(go.Scatter(x=daily_overall['Clean_Date'], y=daily_overall['Clean_Cost'], name='每日 Total Cost ($)', yaxis='y2', line=dict(color='#1E40AF', width=2)))

        fig_overall.update_layout(
            title="全大盘每日销量与 Total Cost 趋势图",
            hovermode="x unified",
            xaxis_title="日期",
            yaxis=dict(title="销量 (件)"),
            yaxis2=dict(title="Total Cost ($)", overlaying='y', side='right'),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig_overall, use_container_width=True)

else:
    st.info("👋 请在左侧上传 Excel 或 CSV 格式的销售报表。")
