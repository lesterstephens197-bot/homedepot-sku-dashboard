import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import calendar

# 页面基础配置
st.set_page_config(
    page_title="Home Depot 销售与广告综合决策看板",
    page_icon="📊",
    layout="wide"
)

# -------------------------------------------------------------------------
# 侧边栏：顶部大模块选择 (功能看板导航)
# -------------------------------------------------------------------------
st.sidebar.title("📌 功能看板导航")
module = st.sidebar.radio(
    "请选择分析模块",
    [
        "🔥 SKU 7天/15天销量变化看板",
        "📊 销售与品类管理决策看板", 
        "📅 月度多维度对比与趋势看板", 
        "📢 SPA 广告绩效诊断与运营看板",
        "🎯 下月销售目标与 SKU 销量拆解看板"
    ]
)

st.sidebar.markdown("---")

# =========================================================================
# 辅助函数：统一处理销售数据清洗
# =========================================================================
def process_sales_data(df_sales):
    df_sales.columns = df_sales.columns.str.strip()

    date_col = next((c for c in df_sales.columns if c in ['日期', 'Date', 'sales_date']), None)
    sales_col = next((c for c in df_sales.columns if c in ['销量', 'Units Sold', 'Units', 'Quantity']), None)
    cost_col = next((c for c in df_sales.columns if c in ['Total Cost', 'Cost', '金额', '总金额']), None)
    category_col = next((c for c in df_sales.columns if c in ['产品名称', 'Category', '品类', '品类名称']), None)
    state_col = next((c for c in df_sales.columns if c in ['ShipTo State', 'State', '州', '省份']), None)
    sku_fields_available = [col for col in ['产品SKU', 'SKU', 'Merchant SKU', 'Vendor SKU', 'OMS ID'] if col in df_sales.columns]

    if not date_col or not sales_col or not sku_fields_available:
        return None, f"解析失败！未能在表格中识别到必需列（日期、销量或产品SKU列）。当前列为: {list(df_sales.columns)}"

    df_sales['Clean_Date'] = pd.to_datetime(df_sales[date_col])
    df_sales['Clean_Units'] = pd.to_numeric(df_sales[sales_col], errors='coerce').fillna(0)
    df_sales['Clean_Cost'] = pd.to_numeric(df_sales[cost_col], errors='coerce').fillna(0) if cost_col else 0
    df_sales['Clean_Category'] = df_sales[category_col].astype(str).str.strip().replace({'nan': '未分类', 'None': '未分类', '': '未分类'}) if category_col else '未分类'
    if state_col:
        df_sales['Clean_State'] = df_sales[state_col].astype(str).str.strip().str.upper().replace({'NAN': '未知', 'NONE': '未知', '': '未知'})

    primary_sku_col = sku_fields_available[0]
    df_sales['YearMonth'] = df_sales['Clean_Date'].dt.to_period('M').astype(str)

    return (df_sales, primary_sku_col), None


# =========================================================================
# 模块一：🔥 SKU 7天/15天销量变化看板 (高直观度重构版)
# =========================================================================
if module == "🔥 SKU 7天/15天销量变化看板":
    st.title("🔥 SKU 7天 / 15天 销量变化与动销爆款看板")
    st.caption("⚡ 实时监测近 7 天与近 15 天的销量爆发力与下滑风险，智能识别异动 SKU")
    st.markdown("---")

    st.sidebar.header("⚙️ 1. 数据源上传")
    uploaded_sales_file = st.sidebar.file_uploader("上传 Home Depot 销售报表 (CSV/Excel)", type=["csv", "xlsx"], key="short_term_uploader")

    if not uploaded_sales_file:
        st.info("👋 请在侧边栏上传包含每日历史销量的销售报表，系统将自动切割计算近 7 天与 15 天的动销变化。")
    else:
        try:
            df_raw = pd.read_csv(uploaded_sales_file) if uploaded_sales_file.name.endswith('.csv') else pd.read_excel(uploaded_sales_file)
        except Exception as e:
            st.error(f"读取文件失败: {e}"); st.stop()

        res, err = process_sales_data(df_raw)
        if err: st.error(err); st.stop()
        df_sales, sku_col = res

        max_date = df_sales['Clean_Date'].max()
        min_date = df_sales['Clean_Date'].min()

        st.sidebar.success(f"📅 **数据最新日期**: {max_date.strftime('%Y-%m-%d')}")

        # 时间窗口切割
        d_last_7_start = max_date - pd.Timedelta(days=6)
        d_prev_7_start = max_date - pd.Timedelta(days=13)
        d_prev_7_end = max_date - pd.Timedelta(days=7)

        d_last_15_start = max_date - pd.Timedelta(days=14)
        d_prev_15_start = max_date - pd.Timedelta(days=29)
        d_prev_15_end = max_date - pd.Timedelta(days=15)

        # 数据过滤与聚合
        df_l7 = df_sales[(df_sales['Clean_Date'] >= d_last_7_start) & (df_sales['Clean_Date'] <= max_date)]
        df_p7 = df_sales[(df_sales['Clean_Date'] >= d_prev_7_start) & (df_sales['Clean_Date'] <= d_prev_7_end)]
        df_l15 = df_sales[(df_sales['Clean_Date'] >= d_last_15_start) & (df_sales['Clean_Date'] <= max_date)]
        df_p15 = df_sales[(df_sales['Clean_Date'] >= d_prev_15_start) & (df_sales['Clean_Date'] <= d_prev_15_end)]

        s_l7 = df_l7.groupby(sku_col).agg(Units_L7=('Clean_Units', 'sum'), Cost_L7=('Clean_Cost', 'sum'))
        s_p7 = df_p7.groupby(sku_col).agg(Units_P7=('Clean_Units', 'sum'))
        s_l15 = df_l15.groupby(sku_col).agg(Units_L15=('Clean_Units', 'sum'), Cost_L15=('Clean_Cost', 'sum'))
        s_p15 = df_p15.groupby(sku_col).agg(Units_P15=('Clean_Units', 'sum'))

        all_skus = pd.DataFrame({sku_col: df_sales[sku_col].unique()})
        metrics_df = all_skus.merge(s_l7, on=sku_col, how='left')\
                             .merge(s_p7, on=sku_col, how='left')\
                             .merge(s_l15, on=sku_col, how='left')\
                             .merge(s_p15, on=sku_col, how='left')\
                             .fillna(0)

        # 计算指标
        metrics_df['Diff_7D'] = metrics_df['Units_L7'] - metrics_df['Units_P7']
        metrics_df['Growth_7D'] = metrics_df.apply(
            lambda r: ((r['Units_L7'] - r['Units_P7']) / r['Units_P7'] * 100) if r['Units_P7'] > 0 else (100.0 if r['Units_L7'] > 0 else 0), axis=1
        )

        metrics_df['Diff_15D'] = metrics_df['Units_L15'] - metrics_df['Units_P15']
        metrics_df['Growth_15D'] = metrics_df.apply(
            lambda r: ((r['Units_L15'] - r['Units_P15']) / r['Units_P15'] * 100) if r['Units_P15'] > 0 else (100.0 if r['Units_L15'] > 0 else 0), axis=1
        )

        metrics_df['Avg_Daily_7D'] = metrics_df['Units_L7'] / 7.0
        metrics_df['Avg_Daily_15D'] = metrics_df['Units_L15'] / 15.0

        # 分类逻辑
        def classify_status(r):
            if r['Units_L7'] == 0 and r['Units_P7'] == 0:
                return "⚠️ 动销停滞"
            elif r['Growth_7D'] >= 30 and r['Diff_7D'] >= 3:
                return "🚀 7天爆发"
            elif r['Growth_7D'] <= -30 and r['Diff_7D'] <= -3:
                return "📉 7天下滑"
            elif r['Growth_15D'] >= 15:
                return "📈 15天稳增"
            else:
                return "➖ 平稳波动"

        metrics_df['Status'] = metrics_df.apply(classify_status, axis=1)

        # -----------------------------------------------------------------
        # 1. 直观卡片层 (大盘及状态预警)
        # -----------------------------------------------------------------
        u7_total = metrics_df['Units_L7'].sum()
        u7_prev = metrics_df['Units_P7'].sum()
        g7_total = ((u7_total - u7_prev) / u7_prev * 100) if u7_prev > 0 else 0

        u15_total = metrics_df['Units_L15'].sum()
        u15_prev = metrics_df['Units_P15'].sum()
        g15_total = ((u15_total - u15_prev) / u15_prev * 100) if u15_prev > 0 else 0

        # 顶部 KPI 展现
        st.subheader("💡 1. 全盘动销动向速览")
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("近 7 天出货总量", f"{int(u7_total):,} 件", delta=f"{g7_total:+.1f}% (vs 前7天)")
        k2.metric("近 15 天出货总量", f"{int(u15_total):,} 件", delta=f"{g15_total:+.1f}% (vs 前15天)")
        k3.metric("近 7 天销售总额", f"${metrics_df['Cost_L7'].sum():,.2f}")
        k4.metric("近 7 天日均销售额", f"${(metrics_df['Cost_L7'].sum() / 7):,.2f} /天")

        # SKU 分组红绿灯预警卡片
        st.markdown("
