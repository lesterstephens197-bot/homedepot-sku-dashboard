import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import timedelta

# =========================================================================
# 1. 页面基本配置
# =========================================================================
st.set_page_config(
    page_title="电商全景综合与退货分析看板",
    page_icon="📊",
    layout="wide"
)

st.title("📊 电商全景综合与退货分析看板")

# =========================================================================
# 2. 数据加载与清洗函数
# =========================================================================
@st.cache_data
def load_sales_data(uploaded_file):
    df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
    df.columns = df.columns.astype(str).str.strip()
    if 'Order Date' in df.columns:
        df['Order Date'] = pd.to_datetime(df['Order Date'], errors='coerce')
    for col in ['Unit Cost', 'Quantity', 'Total Cost']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    if 'Total Cost' in df.columns and 'Unit Cost' in df.columns and 'Quantity' in df.columns:
        df['Total Cost'] = df.apply(lambda r: r['Total Cost'] if r['Total Cost'] > 0 else r['Unit Cost'] * r['Quantity'], axis=1)
    return df

@st.cache_data
def load_rtv_data(uploaded_file):
    df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
    df.columns = df.columns.astype(str).str.strip()
    for col in ['RTV Date', 'Order Date']:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce')
    for col in ['QTY', 'UNIT COST', 'Total Cost', '10%运费', '总扣款']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    if 'Total Cost' in df.columns and 'UNIT COST' in df.columns and 'QTY' in df.columns:
        df['Total Cost'] = df.apply(lambda r: r['Total Cost'] if r['Total Cost'] > 0 else r['UNIT COST'] * r['QTY'], axis=1)
    if '总扣款' in df.columns and 'Total Cost' in df.columns and '10%运费' in df.columns:
        df['总扣款'] = df.apply(lambda r: r['总扣款'] if r['总扣款'] > 0 else r['Total Cost'] + r['10%运费'], axis=1)
    return df

def calc_kpis(data_df):
    sales = data_df['Total Cost'].sum() if 'Total Cost' in data_df.columns else 0
    qty = data_df['Quantity'].sum() if 'Quantity' in data_df.columns else 0
    orders = data_df['PO Number'].nunique() if 'PO Number' in data_df.columns else len(data_df)
    aov = sales / orders if orders > 0 else 0
    return sales, qty, orders, aov

# =========================================================================
# 3. 侧边栏文件上传（含销售与退货入口）
# =========================================================================
st.sidebar.header("📁 数据导入")
sales_file = st.sidebar.file_uploader("1️⃣ 上传销售数据表 (CSV/XLSX)", type=["csv", "xlsx"])
rtv_file = st.sidebar.file_uploader("2️⃣ 上传退货数据表 (CSV/XLSX)", type=["csv", "xlsx"])

# 4. 主界面 Tab 构建
tab_total, tab_op, tab_sku_rank, tab_hd, tab_rtv = st.tabs([
    "📊 核心总销售看板", 
    "👤 分运营销售数据", 
    "🏆 SKU 排名与等级",
    "🏪 HD 门店 vs 个人地址",
    "🔄 RTV 退货分析看板"
])

# -------------------------------------------------------------------------
# 销售看板逻辑 (仅当上传了销售表时渲染)
# -------------------------------------------------------------------------
if sales_file is not None:
    df = load_sales_data(sales_file)
    
    with tab_total:
        st.header("📊 核心总销售看板")
        if 'Order Date' in df.columns and not df['Order Date'].isna().all():
            max_date, min_date = df['Order Date'].max().date(), df['Order Date'].min().date()
            period_option = st.radio("时间周期:", ["全量数据", "近 7 天", "近 15 天", "近 30 天"], horizontal=True)
            
            if "近 7 天" in period_option:
                start_date = max_date - timedelta(days=6)
            elif "近 15 天" in period_option:
                start_date = max_date - timedelta(days=14)
            elif "近 30 天" in period_option:
                start_date = max_date - timedelta(days=29)
            else:
                start_date = min_date

            filtered_df = df[(df['Order Date'].dt.date >= start_date) & (df['Order Date'].dt.date <= max_date)]
            s, q, o, a = calc_kpis(filtered_df)

            k1, k2, k3, k4 = st.columns(4)
            k1.metric("总销售额", f"${s:,.2f}")
            k2.metric("总销量", f"{int(q):,} 件")
            k3.metric("客单价 (AOV)", f"${a:,.2f}")
            k4.metric("总订单量", f"{o:,} 单")
            
            fig_trend = px.line(filtered_df.groupby(filtered_df['Order Date'].dt.date)['Total Cost'].sum().reset_index(), x='Order Date', y='Total Cost', title="销售趋势")
            st.plotly_chart(fig_trend, use_container_width=True)

    with tab_op:
        st.header("👤 分运营销售数据")
        if '运营' in df.columns:
            op_summary = df.groupby('运营').agg(总销售额=('Total Cost', 'sum'), 总销量=('Quantity', 'sum')).reset_index()
            st.dataframe(op_summary, use_container_width=True)

    with tab_sku_rank:
        st.header("🏆 SKU 排名与等级划分")
        sku_col = '产品SKU' if '产品SKU' in df.columns else 'Merchant SKU'
        if sku_col in df.columns:
            sku_summary = df.groupby(sku_col).agg(总销售额=('Total Cost', 'sum'), 总销量=('Quantity', 'sum')).reset_index().sort_values(by='总销售额', ascending=False)
            st.dataframe(sku_summary, use_container_width=True)

    with tab_hd:
        st.header("🏪 HD 门店 vs 个人地址")
        addr = df['ShipTo Address1'].astype(str) if 'ShipTo Address1' in df.columns else pd.Series(['']*len(df))
        df['地址类型'] = df.apply(lambda r: 'HD门店' if 'c/o thd ship to store' in addr.loc[r.name].lower() else '个人地址', axis=1)
        st.dataframe(df.groupby('地址类型')['Total Cost'].sum().reset_index(), use_container_width=True)
else:
    with tab_total:
        st.info("👈 请在左侧侧边栏上传【销售数据表】以查看销售分析。")

# -------------------------------------------------------------------------
# 退货看板逻辑 (仅当上传了退货表时渲染)
# -------------------------------------------------------------------------
with tab_rtv:
    st.header("🔄 RTV 产品退货与扣款分析")
    if rtv_file is not None:
        rtv_df = load_rtv_data(rtv_file)
        
        # 退货 KPI 卡片
        r_tot_cost = rtv_df['Total Cost'].sum() if 'Total Cost' in rtv_df.columns else 0
        r_deduct = rtv_df['总扣款'].sum() if '总扣款' in rtv_df.columns else 0
        r_qty = rtv_df['QTY'].sum() if 'QTY' in rtv_df.columns else 0
        
        rk1, rk2, rk3 = st.columns(3)
        rk1.metric("退货总货值", f"${r_tot_cost:,.2f}")
        rk2.metric("总扣款金额", f"${r_deduct:,.2f}")
        rk3.metric("退货总件数", f"{int(r_qty):,} 件")
        
        st.divider()

        # SKU 退货黑榜
        if '产品SKU' in rtv_df.columns:
            st.subheader("🏆 SKU 退货黑榜")
            rtv_sku = rtv_df.groupby('产品SKU').agg(
                退货件数=('QTY', 'sum'),
                总扣款=('总扣款', 'sum'),
                退货次数=('RTV Number', 'nunique') if 'RTV Number' in rtv_df.columns else ('产品SKU', 'count')
            ).reset_index().sort_values(by='总扣款', ascending=False)
            
            fig_rtv_bar = px.bar(rtv_sku.head(10), x='产品SKU', y='总扣款', text_auto='.2s', title="退货扣款 Top 10 SKU")
            st.plotly_chart(fig_rtv_bar, use_container_width=True)
            st.dataframe(rtv_sku, use_container_width=True, hide_index=True)
    else:
        st.info("👈 请在左侧侧边栏上传【RTV 退货数据表】以查看退货分析。")
