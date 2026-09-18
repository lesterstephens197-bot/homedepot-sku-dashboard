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
st.caption("集成动销分析、运营绩效、双视角退货率分析、SKU退货率排行榜及退货原因分析")

# =========================================================================
# 2. 数据加载与清洗函数
# =========================================================================
@st.cache_data
def load_sales_data(uploaded_file):
    if uploaded_file.name.endswith('.csv'):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)
    
    df.columns = df.columns.astype(str).str.strip()

    if 'Order Date' in df.columns:
        df['Order Date'] = pd.to_datetime(df['Order Date'], errors='coerce')
        df['Order_YearMonth'] = df['Order Date'].dt.to_period('M').astype(str)
        df['Order_YearQuarter'] = df['Order Date'].dt.to_period('Q').astype(str)
    
    numeric_cols = ['Unit Cost', 'Quantity', 'Total Cost']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            
    if 'Total Cost' in df.columns and 'Unit Cost' in df.columns and 'Quantity' in df.columns:
        df['Total Cost'] = df.apply(
            lambda r: r['Total Cost'] if r['Total Cost'] > 0 else r['Unit Cost'] * r['Quantity'], 
            axis=1
        )
    return df

@st.cache_data
def load_return_data(uploaded_file):
    if uploaded_file.name.endswith('.csv'):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)
    
    df.columns = df.columns.astype(str).str.strip()

    if 'Order Date' in df.columns:
        df['Order Date'] = pd.to_datetime(df['Order Date'], errors='coerce')
        df['Order_YearMonth'] = df['Order Date'].dt.to_period('M').astype(str)
        df['Order_YearQuarter'] = df['Order Date'].dt.to_period('Q').astype(str)

    if 'RTV Date' in df.columns:
        df['RTV Date'] = pd.to_datetime(df['RTV Date'], errors='coerce')
        df['RTV_YearMonth'] = df['RTV Date'].dt.to_period('M').astype(str)
        df['RTV_YearQuarter'] = df['RTV Date'].dt.to_period('Q').astype(str)

    numeric_cols = ['QTY', 'UNIT COST', 'Total Cost', '10%运费', '总扣款']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    if 'Total Cost' in df.columns and 'UNIT COST' in df.columns and 'QTY' in df.columns:
        df['Total Cost'] = df.apply(lambda r: r['Total Cost'] if r['Total Cost'] > 0 else r['UNIT COST'] * r['QTY'], axis=1)
    
    if '10%运费' in df.columns and 'Total Cost' in df.columns:
        df['10%运费'] = df.apply(lambda r: r['10%运费'] if r['10%运费'] > 0 else r['Total Cost'] * 0.1, axis=1)

    if '总扣款' in df.columns and 'Total Cost' in df.columns and '10%运费' in df.columns:
        df['总扣款'] = df.apply(lambda r: r['总扣款'] if r['总扣款'] > 0 else (r['Total Cost'] + r['10%运费']), axis=1)

    return df

def get_sku_col(df_columns):
    for col in ['产品SKU', 'Merchant SKU', 'Vendor SKU', 'PART#', 'SKU']:
        if col in df_columns:
            return col
    return None

def get_reason_col(df_columns):
    for col in ['退货原因', 'Return Reason', 'Reason', 'RTV Reason', '原因描述', '备注']:
        if col in df_columns:
            return col
    return None

def build_rtv_analysis_table(rtv_df, sales_df, rtv_sku_col, sales_sku_col, date_type='Order', granularity='Monthly'):
    rtv_name_col = '产品名称' if '产品名称' in rtv_df.columns else rtv_sku_col
    
    if granularity == 'Overall':
        rtv_group = [rtv_sku_col]
        sales_group = [sales_sku_col]
        rtv_date_col, sales_date_col = None, None
    elif granularity == 'Monthly':
        rtv_date_col = 'Order_YearMonth' if date_type == 'Order' else 'RTV_YearMonth'
        sales_date_col = 'Order_YearMonth'
        rtv_group = [rtv_sku_col, rtv_date_col]
        sales_group = [sales_sku_col, sales_date_col]
    else: 
        rtv_date_col = 'Order_YearQuarter' if date_type == 'Order' else 'RTV_YearQuarter'
        sales_date_col = 'Order_YearQuarter'
        rtv_group = [rtv_sku_col, rtv_date_col]
        sales_group = [sales_sku_col, sales_date_col]

    rtv_summary = rtv_df.groupby(rtv_group).agg(
        产品名称=(rtv_name_col, 'first'),
        退货次数=('RTV Number', 'count') if 'RTV Number' in rtv_df.columns else (rtv_sku_col, 'count'),
        退货总件数=('QTY', 'sum'),
        退货货值=('Total Cost', 'sum'),
        运费扣款=('10%运费', 'sum'),
        总扣款金额=('总扣款', 'sum')
    ).reset_index()

    if sales_sku_col and 'Quantity' in sales_df.columns:
        sales_qty = sales_df.groupby(sales_group)['Quantity'].sum().reset_index()
        if granularity == 'Overall':
            sales_qty.columns = [rtv_sku_col, '总出货销量']
            rtv_summary = pd.merge(rtv_summary, sales_qty, on=rtv_sku_col, how='left')
        else:
            sales_qty.columns = [rtv_sku_col, rtv_date_col, '对应期出货量']
            rtv_summary = pd.merge(rtv_summary, sales_qty, on=[rtv_sku_col, rtv_date_col], how='left')
    else:
        qty_col = '总出货销量' if granularity == 'Overall' else '对应期出货量'
        rtv_summary[qty_col] = 0

    target_qty_col = '总出货销量' if granularity == 'Overall' else '对应期出货量'
    rtv_summary[target_qty_col] = rtv_summary[target_qty_col].fillna(0)
    
    rtv_summary['退货率'] = rtv_summary.apply(
        lambda r: (r['退货总件数'] / r[target_qty_col] * 100) if r[target_qty_col] > 0 else 0, axis=1
    )
    return rtv_summary.sort_values('退货总件数', ascending=False)

# =========================================================================
# 3. 侧边栏：文件上传
# =========================================================================
st.sidebar.header("📁 数据导入")
uploaded_sales_file = st.sidebar.file_uploader("1. 上传销售分析数据表 (CSV/Excel)", type=["csv", "xlsx"], key="sales_uploader")
uploaded_return_file = st.sidebar.file_uploader("2. 上传退货数据表 (CSV/Excel)", type=["csv", "xlsx"], key="return_uploader")
uploaded_total_orders_file = st.sidebar.file_uploader("3. 上传全量总出单表 (CSV/Excel) [选填，用于匹配 RTV]", type=["csv", "xlsx"], key="total_orders_uploader")

if uploaded_sales_file is not None:
    raw_df = load_sales_data(uploaded_sales_file)
    df = raw_df.dropna(subset=['Order Date']).copy() if 'Order Date' in raw_df.columns else raw_df.copy()
    rtv_df = load_return_data(uploaded_return_file) if uploaded_return_file is not None else None
    total_orders_df = load_sales_data(uploaded_total_orders_file) if uploaded_total_orders_file is not None else None

    tab_total, tab_op, tab_sku_rank, tab_hd, tab_returns = st.tabs([
        "📊 1. 核心总销售", "👤 2. 运营绩效", "🏆 3. SKU 动销排名", "🏪 4. HD 门店分析", "🔄 5. 退货与扣款 (综合诊断看板)"
    ])

    # -------------------------------------------------------------------------
    # TAB 5: 退货与扣款分析 (增加排名榜与退货原因看板)
    # -------------------------------------------------------------------------
    with tab_returns:
        st.header("🔄 SKU 退货率排名与退货原因诊断看板")

        if rtv_df is not None and not rtv_df.empty:
            rtv_sku_col = get_sku_col(rtv_df.columns)
            rtv_reason_col = get_reason_col(rtv_df.columns)
            
            if not rtv_sku_col:
                st.error("⚠️ 未在退货表格中找到 SKU 列 (如 'PART#', 'SKU', '产品SKU')。")
            else:
                match_source_df = total_orders_df if total_orders_df is not None else df
                source_label = "全量总出单表" if total_orders_df is not None else "销售分析表"
                sales_sku_col = get_sku_col(match_source_df.columns)

                # 包含 4 个核心视角子选项卡
                sub_tab_rank, sub_tab_reason, sub_tab_order, sub_tab_rtv = st.tabs([
                    "🏆 SKU 退货率与件数排行榜", 
                    "🧩 退货原因/理由占比分析", 
                    "🎯 按订单日期明细 (Order Date)", 
                    "💵 按退货处理日期明细 (RTV Date)"
                ])

                # -------------------------------------------------------------
                # 子视角 1：SKU 退货排行榜
                # -------------------------------------------------------------
                with sub_tab_rank:
                    st.markdown("### 🏆 SKU 退货率与退货件数排行榜 (整体视角)")
                    
                    # 算整体 SKU 汇总数据
                    rank_summary = build_rtv_analysis_table(
                        rtv_df, match_source_df, rtv_sku_col, sales_sku_col, date_type='Order', granularity='Overall'
                    )

                    # 可以筛选“最小出货量”，避免只卖了 1 件且退了 1 件导致 100% 退货率的干扰
                    min_sales_limit = st.slider("过滤低出货量 SKU (设置最小出货门槛件数):", min_value=0, max_value=500, value=10)
                    filtered_rank_df = rank_summary[rank_summary['总出货销量'] >= min_sales_limit]

                    c_top1, c_top2 = st.columns(2)
                    
                    with c_top1:
                        st.subheader("🔥 TOP 10 退货件数最多的 SKU")
                        top_qty_df = filtered_rank_df.sort_values('退货总件数', ascending=False).head(10)
                        fig_qty = px.bar(
                            top_qty_df, 
                            x='退货总件数', 
                            y=rtv_sku_col, 
                            orientation='h',
                            text='退货总件数',
                            title="退货总量 TOP 10 (件)",
                            color='退货总件数',
                            color_continuous_scale='Reds'
                        )
                        fig_qty.update_layout(yaxis={'categoryorder': 'total ascending'})
                        st.plotly_chart(fig_qty, use_container_width=True)

                    with c_top2:
                        st.subheader("⚠️ TOP 10 退货率最高的 SKU")
                        top_rate_df = filtered_rank_df.sort_values('退货率', ascending=False).head(10)
                        fig_rate = px.bar(
                            top_rate_df, 
                            x='退货率', 
                            y=rtv_sku_col, 
                            orientation='h',
                            text=top_rate_df['退货率'].apply(lambda x: f"{x:.1f}%"),
                            title=f"退货率 TOP 10 (%) [已过滤出货 < {min_sales_limit} 件的SKU]",
                            color='退货率',
                            color_continuous_scale='Oranges'
                        )
                        fig_rate.update_layout(yaxis={'categoryorder': 'total ascending'})
                        st.plotly_chart(fig_rate, use_container_width=True)

                    st.markdown("#### 📋 完整 SKU 退货综合排行榜单")
                    st.dataframe(
                        filtered_rank_df[['产品SKU', '产品名称', '总出货销量', '退货总件数', '退货率', '退货货值', '总扣款金额']]
                        if '产品SKU' in filtered_rank_df.columns else filtered_rank_df,
                        column_config={
                            "退货率": st.column_config.NumberColumn("退货率", format="%.2f%%"),
                            "退货货值": st.column_config.NumberColumn("退货货值", format="$%.2f"),
                            "总扣款金额": st.column_config.NumberColumn("总扣款金额", format="$%.2f"),
                        },
                        use_container_width=True, hide_index=True
                    )

                # -------------------------------------------------------------
                # 子视角 2：退货原因/理由占比看板
                # -------------------------------------------------------------
                with sub_tab_reason:
                    st.markdown("### 🧩 退货原因占比与问题痛点诊断")

                    if not rtv_reason_col:
                        st.warning("⚠️ 在退货数据表中未匹配到退货原因列（例如：'退货原因', 'Return Reason', 'Reason', '备注'）。")
                    else:
                        # 补充缺失值处理
                        rtv_df_reason = rtv_df.copy()
                        rtv_df_reason[rtv_reason_col] = rtv_df_reason[rtv_reason_col].fillna("未知/未填写理由")

                        r_c1, r_c2 = st.columns([2, 3])

                        with r_c1:
                            st.subheader("📊 全局退货原因占比 (按退货件数)")
                            reason_summary = rtv_df_reason.groupby(rtv_reason_col).agg(
                                退货件数=('QTY', 'sum') if 'QTY' in rtv_df_reason.columns else (rtv_sku_col, 'count'),
                                关联扣款=('总扣款', 'sum') if '总扣款' in rtv_df_reason.columns else (rtv_sku_col, 'count')
                            ).reset_index().sort_values('退货件数', ascending=False)

                            fig_pie = px.pie(
                                reason_summary, 
                                names=rtv_reason_col, 
                                values='退货件数', 
                                title="退货原因分布占比",
                                hole=0.4
                            )
                            fig_pie.update_traces(textposition='inside', textinfo='percent+label')
                            st.plotly_chart(fig_pie, use_container_width=True)

                        with r_c2:
                            st.subheader("🔍 按 SKU 钻取具体退货原因")
                            selected_sku_for_reason = st.selectbox(
                                "选择特定的 SKU 查看其退货主因:",
                                options=["全部 SKU"] + list(rtv_df_reason[rtv_sku_col].dropna().unique())
                            )

                            if selected_sku_for_reason != "全部 SKU":
                                sku_reason_df = rtv_df_reason[rtv_df_reason[rtv_sku_col] == selected_sku_for_reason]
                            else:
                                sku_reason_df = rtv_df_reason

                            sku_reason_summary = sku_reason_df.groupby([rtv_sku_col, rtv_reason_col]).agg(
                                退货件数=('QTY', 'sum') if 'QTY' in sku_reason_df.columns else (rtv_sku_col, 'count'),
                                退货扣款金额=('总扣款', 'sum') if '总扣款' in sku_reason_df.columns else (rtv_sku_col, 'count')
                            ).reset_index().sort_values('退货件数', ascending=False)

                            st.dataframe(
                                sku_reason_summary,
                                column_config={
                                    "退货扣款金额": st.column_config.NumberColumn("关联扣款金额", format="$%.2f")
                                },
                                use_container_width=True, hide_index=True
                            )

                # -------------------------------------------------------------
                # 子视角 3：按 Order Date 队列明细 (保留原视角)
                # -------------------------------------------------------------
                with sub_tab_order:
                    st.markdown("### 🎯 基于【订单日期 Order Date】计算的队列退货明细")
                    order_rtv_summary = build_rtv_analysis_table(
                        rtv_df, match_source_df, rtv_sku_col, sales_sku_col, date_type='Order', granularity='Monthly'
                    )
                    st.dataframe(order_rtv_summary, use_container_width=True, hide_index=True)

                # -------------------------------------------------------------
                # 子视角 4：按 RTV Date 财务明细 (保留原视角)
                # -------------------------------------------------------------
                with sub_tab_rtv:
                    st.markdown("### 💵 基于【退货处理日期 RTV Date】计算的当期财务扣款明细")
                    rtv_date_summary = build_rtv_analysis_table(
                        rtv_df, match_source_df, rtv_sku_col, sales_sku_col, date_type='RTV', granularity='Monthly'
                    )
                    st.dataframe(rtv_date_summary, use_container_width=True, hide_index=True)

        else:
            st.info("💡 请在左侧侧边栏上传退货数据表以开启退货看板分析。")
else:
    st.info("💡 请在左侧边栏上传销售数据表。")
