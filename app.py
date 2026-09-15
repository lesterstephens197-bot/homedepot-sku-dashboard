import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import calendar


# =========================================================
# Page Config
# =========================================================

st.set_page_config(
    page_title="THD Sales & SKU Dashboard",
    page_icon="📊",
    layout="wide",
)


# =========================================================
# Common Functions
# =========================================================

def clean_numeric(series):
    """Convert currency / percentage / comma-formatted strings to numeric."""
    if series is None:
        return pd.Series(dtype=float)

    if pd.api.types.is_numeric_dtype(series):
        return pd.to_numeric(series, errors="coerce").fillna(0)

    return (
        series.astype(str)
        .str.replace(",", "", regex=False)
        .str.replace("$", "", regex=False)
        .str.replace("%", "", regex=False)
        .str.replace(" ", "", regex=False)
        .replace({
            "": np.nan,
            "nan": np.nan,
            "None": np.nan,
            "-": np.nan
        })
        .pipe(pd.to_numeric, errors="coerce")
        .fillna(0)
    )


def find_column(df, candidates):
    """Find the first matching column."""
    normalized = {
        str(c).strip().lower(): c
        for c in df.columns
    }

    for candidate in candidates:
        key = str(candidate).strip().lower()

        if key in normalized:
            return normalized[key]

    # Fuzzy match
    for col in df.columns:
        col_lower = str(col).strip().lower()

        for candidate in candidates:
            if str(candidate).strip().lower() in col_lower:
                return col

    return None


def read_uploaded_file(uploaded_file):
    """Read CSV / XLSX / XLS."""
    try:
        file_name = uploaded_file.name.lower()

        if file_name.endswith(".csv"):
            try:
                return pd.read_csv(uploaded_file)
            except UnicodeDecodeError:
                uploaded_file.seek(0)
                return pd.read_csv(
                    uploaded_file,
                    encoding="gbk"
                )

        if file_name.endswith(".xlsx") or file_name.endswith(".xls"):
            return pd.read_excel(uploaded_file)

        st.error("请上传 CSV / XLSX / XLS 文件。")
        return None

    except Exception as e:
        st.error(f"文件读取失败：{e}")
        return None


def process_sales_data(df):
    """
    Standardize sales data.

    Required:
    - Date
    - SKU
    - Units

    Optional:
    - Sales / Revenue / GMV
    - Cost
    - Category
    - State
    """

    if df is None or df.empty:
        return None, "文件为空。"

    df = df.copy()

    df.columns = [
        str(c).strip()
        for c in df.columns
    ]

    # -------------------------
    # Find columns
    # -------------------------

    date_col = find_column(
        df,
        [
            "Date",
            "Order Date",
            "Sales Date",
            "Transaction Date",
            "日期",
            "订单日期",
            "销售日期",
        ],
    )

    sku_col = find_column(
        df,
        [
            "SKU",
            "Product SKU",
            "Merchant SKU",
            "Vendor SKU",
            "产品SKU",
            "商品SKU",
        ],
    )

    units_col = find_column(
        df,
        [
            "Units",
            "Unit",
            "Qty",
            "Quantity",
            "Sales Units",
            "销量",
            "销售数量",
        ],
    )

    amount_col = find_column(
        df,
        [
            "Sales",
            "Sales Amount",
            "Revenue",
            "GMV",
            "Net Sales",
            "Amount",
            "销售额",
            "销售金额",
            "GMV Amount",
        ],
    )

    cost_col = find_column(
        df,
        [
            "Cost",
            "COGS",
            "Product Cost",
            "Cost Amount",
            "成本",
            "成本金额",
        ],
    )

    category_col = find_column(
        df,
        [
            "Category",
            "Product Category",
            "Class",
            "Department",
            "类目",
            "品类",
        ],
    )

    state_col = find_column(
        df,
        [
            "State",
            "Ship State",
            "Shipping State",
            "州",
            "州代码",
        ],
    )

    # -------------------------
    # Required validation
    # -------------------------

    if date_col is None:
        return (
            None,
            "找不到日期列，请确保文件包含 Date / 日期 / Order Date 等字段。"
        )

    if sku_col is None:
        return (
            None,
            "找不到 SKU 列，请确保文件包含 SKU / Product SKU 等字段。"
        )

    if units_col is None:
        return (
            None,
            "找不到销量列，请确保文件包含 Units / Qty / Quantity 等字段。"
        )

    # -------------------------
    # Standardized dataframe
    # -------------------------

    out = pd.DataFrame()

    out["Clean_Date"] = pd.to_datetime(
        df[date_col],
        errors="coerce"
    )

    out["Clean_SKU"] = (
        df[sku_col]
        .astype(str)
        .str.strip()
    )

    out["Clean_Units"] = clean_numeric(
        df[units_col]
    )

    if amount_col is not None:
        out["Clean_Sales"] = clean_numeric(
            df[amount_col]
        )
    else:
        out["Clean_Sales"] = 0.0

    if cost_col is not None:
        out["Clean_Cost"] = clean_numeric(
            df[cost_col]
        )
    else:
        out["Clean_Cost"] = 0.0

    if category_col is not None:
        out["Clean_Category"] = (
            df[category_col]
            .fillna("Unknown")
            .astype(str)
            .str.strip()
        )
    else:
        out["Clean_Category"] = "Unknown"

    if state_col is not None:
        out["Clean_State"] = (
            df[state_col]
            .fillna("Unknown")
            .astype(str)
            .str.strip()
            .str.upper()
        )
    else:
        out["Clean_State"] = "Unknown"

    # -------------------------
    # Clean data
    # -------------------------

    out = out.dropna(
        subset=["Clean_Date"]
    )

    out = out[
        out["Clean_SKU"].notna()
    ]

    out = out[
        out["Clean_SKU"].astype(str).str.strip() != ""
    ]

    out["Clean_Date"] = (
        out["Clean_Date"]
        .dt.normalize()
    )

    return out, None


def pct_change(current, previous):
    if previous == 0:

        if current > 0:
            return np.nan

        return 0.0

    return (
        (current - previous)
        / previous
        * 100
    )


def pct_label(current, previous):

    if previous == 0:

        if current > 0:
            return "新增"

        return "—"

    return (
        f"{pct_change(current, previous):+.1f}%"
    )


def period_sum(
    df,
    start_date,
    end_date
):

    mask = (
        (df["Clean_Date"] >= pd.Timestamp(start_date))
        &
        (df["Clean_Date"] <= pd.Timestamp(end_date))
    )

    return (
        df.loc[mask]
        .groupby("Clean_SKU")["Clean_Units"]
        .sum()
    )


def money(value):
    return f"${value:,.0f}"


def number(value):
    return f"{value:,.0f}"


def upload_sales_sidebar(key):

    return st.sidebar.file_uploader(
        "上传销售数据",
        type=[
            "csv",
            "xlsx",
            "xls"
        ],
        key=key,
        help="支持 CSV / XLSX / XLS。",
    )


# =========================================================
# Navigation
# =========================================================

modules = [
    "📊 销售与品类管理决策看板",
    "📅 月度多维度对比与趋势看板",
    "📈 SKU 7/15天销量变化看板",
    "📢 SPA 广告绩效诊断与运营看板",
    "🎯 下月销售目标与 SKU 销量拆解看板",
]

st.sidebar.title("THD Dashboard")

module = st.sidebar.radio(
    "选择模块",
    modules
)


# =========================================================
# MODULE 1
# 销售与品类管理决策看板
# =========================================================

if module == "📊 销售与品类管理决策看板":

    st.title(
        "📊 销售与品类管理决策看板"
    )

    st.caption(
        "用于查看 SKU、品类、区域及销售结构表现。"
    )

    uploaded_sales_file = upload_sales_sidebar(
        "sales_module_1"
    )

    if uploaded_sales_file is None:

        st.info(
            "请先在左侧上传销售数据。"
        )

        st.stop()

    raw_sales = read_uploaded_file(
        uploaded_sales_file
    )

    df_sales, error = process_sales_data(
        raw_sales
    )

    if error:

        st.error(error)

        st.stop()

    min_date = (
        df_sales["Clean_Date"]
        .min()
        .date()
    )

    max_date = (
        df_sales["Clean_Date"]
        .max()
        .date()
    )

    st.sidebar.markdown("---")

    start_date = st.sidebar.date_input(
        "开始日期",
        value=min_date,
        min_value=min_date,
        max_value=max_date,
        key="m1_start",
    )

    end_date = st.sidebar.date_input(
        "结束日期",
        value=max_date,
        min_value=min_date,
        max_value=max_date,
        key="m1_end",
    )

    if start_date > end_date:

        st.error(
            "开始日期不能晚于结束日期。"
        )

        st.stop()

    period_df = df_sales[
        (
            df_sales["Clean_Date"]
            >= pd.Timestamp(start_date)
        )
        &
        (
            df_sales["Clean_Date"]
            <= pd.Timestamp(end_date)
        )
    ].copy()

    if period_df.empty:

        st.warning(
            "所选日期范围没有数据。"
        )

        st.stop()

    total_sales = (
        period_df["Clean_Sales"]
        .sum()
    )

    total_units = (
        period_df["Clean_Units"]
        .sum()
    )

    sku_count = (
        period_df["Clean_SKU"]
        .nunique()
    )

    avg_price = (
        total_sales / total_units
        if total_units
        else 0
    )

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "Sales",
        money(total_sales)
    )

    c2.metric(
        "Units",
        number(total_units)
    )

    c3.metric(
        "Active SKUs",
        number(sku_count)
    )

    c4.metric(
        "Avg. Selling Price",
        money(avg_price)
    )

    st.markdown("---")

    sku_summary = (
        period_df
        .groupby(
            "Clean_SKU",
            as_index=False
        )
        .agg(
            Sales=(
                "Clean_Sales",
                "sum"
            ),
            Units=(
                "Clean_Units",
                "sum"
            ),
            Cost=(
                "Clean_Cost",
                "sum"
            ),
        )
        .sort_values(
            "Sales",
            ascending=False
        )
    )

    total_sales_safe = (
        sku_summary["Sales"].sum()
    )

    if total_sales_safe:

        sku_summary[
            "Sales Share (%)"
        ] = (
            sku_summary["Sales"]
            / total_sales_safe
            * 100
        )

    else:

        sku_summary[
            "Sales Share (%)"
        ] = 0

    sku_summary[
        "Cumulative Share (%)"
    ] = (
        sku_summary["Sales Share (%)"]
        .cumsum()
    )

    def abc_class(value):

        if value <= 80:
            return "A"

        if value <= 95:
            return "B"

        return "C"

    sku_summary["ABC"] = (
        sku_summary[
            "Cumulative Share (%)"
        ]
        .apply(abc_class)
    )

    left, right = st.columns(2)

    with left:

        st.subheader(
            "Top SKU Sales"
        )

        top_sku = (
            sku_summary
            .head(15)
            .sort_values("Sales")
        )

        fig = px.bar(
            top_sku,
            x="Sales",
            y="Clean_SKU",
            orientation="h",
            text_auto=".2s",
        )

        fig.update_layout(
            height=500,
            xaxis_title="Sales",
            yaxis_title="SKU",
        )

        st.plotly_chart(
            fig,
            use_container_width=True
        )

    with right:

        st.subheader(
            "ABC SKU Distribution"
        )

        abc_count = (
            sku_summary
            .groupby("ABC")
            .size()
            .reset_index(
                name="SKU Count"
            )
        )

        fig = px.bar(
            abc_count,
            x="ABC",
            y="SKU Count",
            text_auto=True,
        )

        fig.update_layout(
            height=500
        )

        st.plotly_chart(
            fig,
            use_container_width=True
        )

    st.subheader(
        "SKU Performance"
    )

    table = sku_summary.copy()

    table["Sales"] = (
        table["Sales"]
        .map(lambda x: f"${x:,.0f}")
    )

    table["Sales Share (%)"] = (
        table["Sales Share (%)"]
        .map(lambda x: f"{x:.1f}%")
    )

    table["Cumulative Share (%)"] = (
        table["Cumulative Share (%)"]
        .map(lambda x: f"{x:.1f}%")
    )

    table["Units"] = (
        table["Units"]
        .map(lambda x: f"{x:,.0f}")
    )

    table["Cost"] = (
        table["Cost"]
        .map(lambda x: f"${x:,.0f}")
    )

    st.dataframe(
        table,
        use_container_width=True,
        hide_index=True
    )

    st.subheader(
        "Category / State Overview"
    )

    col_a, col_b = st.columns(2)

    with col_a:

        category_summary = (
            period_df
            .groupby(
                "Clean_Category",
                as_index=False
            )
            .agg(
                Sales=(
                    "Clean_Sales",
                    "sum"
                ),
                Units=(
                    "Clean_Units",
                    "sum"
                ),
            )
            .sort_values(
                "Sales",
                ascending=False
            )
        )

        fig = px.bar(
            category_summary.head(15),
            x="Sales",
            y="Clean_Category",
            orientation="h",
            text_auto=".2s",
        )

        fig.update_layout(
            height=450
        )

        st.plotly_chart(
            fig,
            use_container_width=True
        )

    with col_b:

        state_summary = (
            period_df
            .groupby(
                "Clean_State",
                as_index=False
            )
            .agg(
                Sales=(
                    "Clean_Sales",
                    "sum"
                ),
                Units=(
                    "Clean_Units",
                    "sum"
                ),
            )
            .sort_values(
                "Sales",
                ascending=False
            )
        )

        fig = px.bar(
            state_summary.head(15),
            x="Sales",
            y="Clean_State",
            orientation="h",
            text_auto=".2s",
        )

        fig.update_layout(
            height=450
        )

        st.plotly_chart(
            fig,
            use_container_width=True
        )


# =========================================================
# MODULE 2
# 月度多维度对比与趋势看板
# =========================================================

elif module == "📅 月度多维度对比与趋势看板":

    st.title(
        "📅 月度多维度对比与趋势看板"
    )

    st.caption(
        "按月份查看销售额、销量和 SKU 趋势。"
    )

    uploaded_sales_file = upload_sales_sidebar(
        "sales_module_2"
    )

    if uploaded_sales_file is None:

        st.info(
            "请先在左侧上传销售数据。"
        )

        st.stop()

    raw_sales = read_uploaded_file(
        uploaded_sales_file
    )

    df_sales, error = process_sales_data(
        raw_sales
    )

    if error:

        st.error(error)

        st.stop()

    df_sales["Month"] = (
        df_sales["Clean_Date"]
        .dt.to_period("M")
        .astype(str)
    )

    months = sorted(
        df_sales["Month"].unique()
    )

    if not months:

        st.warning(
            "没有有效月份数据。"
        )

        st.stop()

    st.sidebar.markdown("---")

    selected_months = st.sidebar.multiselect(
        "选择月份",
        options=months,
        default=months[
            -min(6, len(months)):
        ],
        key="m2_months",
    )

    if not selected_months:

        st.warning(
            "请至少选择一个月份。"
        )

        st.stop()

    month_df = df_sales[
        df_sales["Month"].isin(
            selected_months
        )
    ].copy()

    monthly = (
        month_df
        .groupby(
            "Month",
            as_index=False
        )
        .agg(
            Sales=(
                "Clean_Sales",
                "sum"
            ),
            Units=(
                "Clean_Units",
                "sum"
            ),
            Active_SKU=(
                "Clean_SKU",
                "nunique"
            ),
        )
    )

    monthly["Month"] = pd.Categorical(
        monthly["Month"],
        categories=selected_months,
        ordered=True,
    )

    monthly = monthly.sort_values(
        "Month"
    )

    c1, c2, c3 = st.columns(3)

    c1.metric(
        "Selected Sales",
        money(
            monthly["Sales"].sum()
        )
    )

    c2.metric(
        "Selected Units",
        number(
            monthly["Units"].sum()
        )
    )

    c3.metric(
        "Avg. Active SKUs",
        f"{monthly['Active_SKU'].mean():,.0f}"
    )

    col1, col2 = st.columns(2)

    with col1:

        fig = px.line(
            monthly,
            x="Month",
            y="Sales",
            markers=True,
            text="Sales",
        )

        fig.update_traces(
            texttemplate="$%{text:,.0f}",
            textposition="top center"
        )

        fig.update_layout(
            height=450,
            yaxis_title="Sales"
        )

        st.plotly_chart(
            fig,
            use_container_width=True
        )

    with col2:

        fig = px.line(
            monthly,
            x="Month",
            y="Units",
            markers=True,
            text="Units",
        )

        fig.update_traces(
            texttemplate="%{text:,.0f}",
            textposition="top center"
        )

        fig.update_layout(
            height=450,
            yaxis_title="Units"
        )

        st.plotly_chart(
            fig,
            use_container_width=True
        )

    st.subheader(
        "Monthly Summary"
    )

    monthly_display = monthly.copy()

    monthly_display["Sales"] = (
        monthly_display["Sales"]
        .map(lambda x: f"${x:,.0f}")
    )

    monthly_display["Units"] = (
        monthly_display["Units"]
        .map(lambda x: f"{x:,.0f}")
    )

    st.dataframe(
        monthly_display,
        use_container_width=True,
        hide_index=True
    )

    st.subheader(
        "SKU Monthly Sales"
    )

    sku_monthly = (
        month_df
        .groupby(
            ["Clean_SKU", "Month"],
            as_index=False
        )
        .agg(
            Sales=(
                "Clean_Sales",
                "sum"
            ),
            Units=(
                "Clean_Units",
                "sum"
            ),
        )
    )

    sku_pivot = sku_monthly.pivot(
        index="Clean_SKU",
        columns="Month",
        values="Sales",
    ).fillna(0)

    sku_pivot = sku_pivot.reindex(
        columns=selected_months,
        fill_value=0
    )

    sku_pivot["Total Sales"] = (
        sku_pivot.sum(axis=1)
    )

    sku_pivot = sku_pivot.sort_values(
        "Total Sales",
        ascending=False
    )

    display_pivot = sku_pivot.copy()

    for col in display_pivot.columns:

        display_pivot[col] = (
            display_pivot[col]
            .map(lambda x: f"${x:,.0f}")
        )

    st.dataframe(
        display_pivot,
        use_container_width=True
    )

    top_skus = (
        sku_pivot
        .head(10)
        .drop(
            columns="Total Sales"
        )
    )

    if not top_skus.empty:

        fig = px.line(
            top_skus.T,
            markers=True,
        )

        fig.update_layout(
            height=500,
            xaxis_title="Month",
            yaxis_title="Sales",
            legend_title="SKU",
        )

        st.plotly_chart(
            fig,
            use_container_width=True
        )


# =========================================================
# MODULE 3
# SKU 7/15天销量变化看板
# =========================================================

elif module == "📈 SKU 7/15天销量变化看板":

    st.title(
        "📈 SKU 7/15天销量变化看板"
    )

    st.caption(
        "比较每个 SKU 最近 7 天 vs 前 7 天、最近 15 天 vs 前 15 天的销量变化。"
    )

    uploaded_sales_file = upload_sales_sidebar(
        "sales_module_3"
    )

    if uploaded_sales_file is None:

        st.info(
            "请先在左侧上传销售数据。"
        )

        st.stop()

    raw_sales = read_uploaded_file(
        uploaded_sales_file
    )

    df_sales, error = process_sales_data(
        raw_sales
    )

    if error:

        st.error(error)

        st.stop()

    min_date = (
        df_sales["Clean_Date"]
        .min()
        .date()
    )

    max_date = (
        df_sales["Clean_Date"]
        .max()
        .date()
    )

    st.sidebar.markdown("---")

    # -------------------------
    # Date
    # -------------------------

    anchor_date = st.sidebar.date_input(
        "统计截止日期",
        value=max_date,
        min_value=min_date,
        max_value=max_date,
        key="m3_anchor",
        help="默认使用销售数据中的最新日期。",
    )

    # -------------------------
    # Filters
    # -------------------------

    min_7_units = st.sidebar.number_input(
        "最小最近7天销量",
        min_value=0,
        value=0,
        step=1,
        key="m3_min_units",
        help="设为 0 表示显示全部 SKU。",
    )

    trend_filter = st.sidebar.selectbox(
        "趋势筛选",
        [
            "全部 SKU",
            "持续上升",
            "持续下滑",
            "近期回升",
            "近期走弱",
            "基本持平",
        ],
        key="m3_trend",
    )

    sku_keyword = st.sidebar.text_input(
        "SKU 搜索",
        value="",
        key="m3_sku_search",
    ).strip()

    # -------------------------
    # Period Definition
    # -------------------------

    anchor = pd.Timestamp(
        anchor_date
    )

    # 最近7天
    cur7_start = (
        anchor
        - pd.Timedelta(days=6)
    )

    cur7_end = anchor

    # 前7天
    prev7_start = (
        anchor
        - pd.Timedelta(days=13)
    )

    prev7_end = (
        anchor
        - pd.Timedelta(days=7)
    )

    # 最近15天
    cur15_start = (
        anchor
        - pd.Timedelta(days=14)
    )

    cur15_end = anchor

    # 前15天
    prev15_start = (
        anchor
        - pd.Timedelta(days=29)
    )

    prev15_end = (
        anchor
        - pd.Timedelta(days=15)
    )

    # -------------------------
    # All SKU
    # -------------------------

    all_skus = pd.Index(
        df_sales[
            "Clean_SKU"
        ]
        .dropna()
        .astype(str)
        .str.strip()
        .unique(),
        name="Clean_SKU",
    )

    # -------------------------
    # Period Sales
    # -------------------------

    cur7 = (
        period_sum(
            df_sales,
            cur7_start,
            cur7_end
        )
        .reindex(
            all_skus,
            fill_value=0
        )
    )

    prev7 = (
        period_sum(
            df_sales,
            prev7_start,
            prev7_end
        )
        .reindex(
            all_skus,
            fill_value=0
        )
    )

    cur15 = (
        period_sum(
            df_sales,
            cur15_start,
            cur15_end
        )
        .reindex(
            all_skus,
            fill_value=0
        )
    )

    prev15 = (
        period_sum(
            df_sales,
            prev15_start,
            prev15_end
        )
        .reindex(
            all_skus,
            fill_value=0
        )
    )

    # -------------------------
    # Summary Table
    # -------------------------

    summary = pd.DataFrame(
        {
            "SKU": all_skus,
            "最近7天销量": cur7.values,
            "前7天销量": prev7.values,
            "最近15天销量": cur15.values,
            "前15天销量": prev15.values,
        }
    )

    summary["7天变化"] = (
        summary["最近7天销量"]
        -
        summary["前7天销量"]
    )

    summary["15天变化"] = (
        summary["最近15天销量"]
        -
        summary["前15天销量"]
    )

    summary["7天变化率数值"] = [
        pct_change(
            current,
            previous
        )
        for current, previous
        in zip(
            summary["最近7天销量"],
            summary["前7天销量"]
        )
    ]

    summary["15天变化率数值"] = [
        pct_change(
            current,
            previous
        )
        for current, previous
        in zip(
            summary["最近15天销量"],
            summary["前15天销量"]
        )
    ]

    summary["7天变化率"] = [
        pct_label(
            current,
            previous
        )
        for current, previous
        in zip(
            summary["最近7天销量"],
            summary["前7天销量"]
        )
    ]

    summary["15天变化率"] = [
        pct_label(
            current,
            previous
        )
        for current, previous
        in zip(
            summary["最近15天销量"],
            summary["前15天销量"]
        )
    ]

    # -------------------------
    # Trend Classification
    # -------------------------

    def get_trend(row):

        d7 = row["7天变化"]
        d15 = row["15天变化"]

        if d7 > 0 and d15 > 0:
            return "持续上升"

        if d7 < 0 and d15 < 0:
            return "持续下滑"

        if d7 > 0 and d15 < 0:
            return "近期回升"

        if d7 < 0 and d15 > 0:
            return "近期走弱"

        return "基本持平"

    summary["趋势"] = (
        summary
        .apply(
            get_trend,
            axis=1
        )
    )

    # -------------------------
    # Filters
    # -------------------------

    filtered = summary[
        summary["最近7天销量"]
        >= min_7_units
    ].copy()

    if sku_keyword:

        filtered = filtered[
            filtered["SKU"].str.contains(
                sku_keyword,
                case=False,
                na=False
            )
        ]

    if trend_filter != "全部 SKU":

        filtered = filtered[
            filtered["趋势"]
            == trend_filter
        ]

    # -------------------------
    # KPI
    # -------------------------

    total_cur7 = (
        summary["最近7天销量"]
        .sum()
    )

    total_prev7 = (
        summary["前7天销量"]
        .sum()
    )

    total_cur15 = (
        summary["最近15天销量"]
        .sum()
    )

    total_prev15 = (
        summary["前15天销量"]
        .sum()
    )

    total_7_pct = pct_change(
        total_cur7,
        total_prev7
    )

    total_15_pct = pct_change(
        total_cur15,
        total_prev15
    )

    rising = (
        summary["7天变化"] > 0
    ).sum()

    falling = (
        summary["7天变化"] < 0
    ).sum()

    k1, k2, k3, k4, k5 = st.columns(5)

    k1.metric(
        "统计截止日",
        anchor.strftime("%Y-%m-%d")
    )

    k2.metric(
        "最近7天销量",
        f"{total_cur7:,.0f}",
        (
            f"{total_7_pct:+.1f}%"
            if not pd.isna(total_7_pct)
            else "新增"
        )
    )

    k3.metric(
        "最近15天销量",
        f"{total_cur15:,.0f}",
        (
            f"{total_15_pct:+.1f}%"
            if not pd.isna(total_15_pct)
            else "新增"
        )
    )

    k4.metric(
        "7天上升 SKU",
        f"{rising:,}"
    )

    k5.metric(
        "7天下降 SKU",
        f"{falling:,}"
    )

    st.markdown("---")

    st.info(
        f"最近7天："
        f"{cur7_start.strftime('%m/%d')}"
        f"–"
        f"{cur7_end.strftime('%m/%d')}"
        f"  |  前7天："
        f"{prev7_start.strftime('%m/%d')}"
        f"–"
        f"{prev7_end.strftime('%m/%d')}"
        f"  |  最近15天："
        f"{cur15_start.strftime('%m/%d')}"
        f"–"
        f"{cur15_end.strftime('%m/%d')}"
        f"  |  前15天："
        f"{prev15_start.strftime('%m/%d')}"
        f"–"
        f"{prev15_end.strftime('%m/%d')}"
    )

    # =====================================================
    # Trend Distribution
    # =====================================================

    trend_count = (
        summary["趋势"]
        .value_counts()
        .reindex(
            [
                "持续上升",
                "近期回升",
                "基本持平",
                "近期走弱",
                "持续下滑",
            ],
            fill_value=0
        )
        .reset_index()
    )

    trend_count.columns = [
        "趋势",
        "SKU数量"
    ]

    left, right = st.columns(2)

    with left:

        st.subheader(
            "SKU 趋势分布"
        )

        fig = px.bar(
            trend_count,
            x="趋势",
            y="SKU数量",
            text_auto=True,
        )

        fig.update_layout(
            height=420
        )

        st.plotly_chart(
            fig,
            use_container_width=True
        )

    with right:

        st.subheader(
            "7天变化 vs 15天变化"
        )

        scatter_df = summary.copy()

        fig = px.scatter(
            scatter_df,
            x="7天变化",
            y="15天变化",
            hover_name="SKU",
            hover_data=[
                "最近7天销量",
                "最近15天销量",
                "趋势",
            ],
        )

        fig.add_hline(
            y=0,
            line_dash="dash"
        )

        fig.add_vline(
            x=0,
            line_dash="dash"
        )

        fig.update_layout(
            height=420,
            xaxis_title="7天销量变化",
            yaxis_title="15天销量变化",
        )

        st.plotly_chart(
            fig,
            use_container_width=True
        )

    # =====================================================
    # Top Increase / Decrease
    # =====================================================

    left, right = st.columns(2)

    with left:

        st.subheader(
            "Top 10：最近7天销量增长"
        )

        top_up = (
            summary
            .sort_values(
                "7天变化",
                ascending=False
            )
            .head(10)
            .sort_values(
                "7天变化"
            )
        )

        fig = px.bar(
            top_up,
            x="7天变化",
            y="SKU",
            orientation="h",
            text_auto=True,
        )

        fig.update_layout(
            height=450
        )

        st.plotly_chart(
            fig,
            use_container_width=True
        )

    with right:

        st.subheader(
            "Top 10：最近7天销量下降"
        )

        top_down = (
            summary
            .sort_values(
                "7天变化",
                ascending=True
            )
            .head(10)
            .sort_values(
                "7天变化",
                ascending=True
            )
        )

        fig = px.bar(
            top_down,
            x="7天变化",
            y="SKU",
            orientation="h",
            text_auto=True,
        )

        fig.update_layout(
            height=450
        )

        st.plotly_chart(
            fig,
            use_container_width=True
        )

    # =====================================================
    # Main SKU Table
    # =====================================================

    st.subheader(
        "SKU 7天 / 15天销量变化明细"
    )

    table = filtered[
        [
            "SKU",
            "最近7天销量",
            "前7天销量",
            "7天变化",
            "7天变化率",
            "最近15天销量",
            "前15天销量",
            "15天变化",
            "15天变化率",
            "趋势",
        ]
    ].copy()

    table = table.sort_values(
        [
            "7天变化",
            "最近7天销量"
        ],
        ascending=[
            False,
            False
        ]
    )

    table_display = table.copy()

    for col in [
        "最近7天销量",
        "前7天销量",
        "7天变化",
        "最近15天销量",
        "前15天销量",
        "15天变化",
    ]:

        table_display[col] = (
            table_display[col]
            .map(
                lambda x:
                f"{x:,.0f}"
            )
        )

    st.dataframe(
        table_display,
        use_container_width=True,
        hide_index=True,
        height=600,
    )

    # =====================================================
    # Download
    # =====================================================

    csv_data = (
        table
        .to_csv(index=False)
        .encode("utf-8-sig")
    )

    st.download_button(
        "下载 SKU 7/15天销量变化明细 CSV",
        data=csv_data,
        file_name=(
            "SKU_7_15_day_sales_change_"
            f"{anchor.strftime('%Y%m%d')}.csv"
        ),
        mime="text/csv",
    )

    # =====================================================
    # SKU Detail
    # =====================================================

    st.markdown("---")

    st.subheader(
        "SKU 单品趋势详情"
    )

    if len(filtered) > 0:

        sku_options = (
            filtered["SKU"]
            .tolist()
        )

        selected_sku = st.selectbox(
            "选择 SKU",
            sku_options,
            key="m3_selected_sku",
        )

        sku_daily = (
            df_sales[
                df_sales["Clean_SKU"]
                == selected_sku
            ]
            .groupby(
                "Clean_Date"
            )["Clean_Units"]
            .sum()
        )

        detail_start = (
            anchor
            - pd.Timedelta(days=29)
        )

        date_index = pd.date_range(
            start=detail_start,
            end=anchor,
            freq="D"
        )

        sku_daily = (
            sku_daily
            .reindex(
                date_index,
                fill_value=0
            )
        )

        sku_daily_df = (
            sku_daily
            .rename("Units")
            .reset_index()
        )

        sku_daily_df.columns = [
            "Date",
            "Units"
        ]

        sku_daily_df[
            "7D Rolling Avg"
        ] = (
            sku_daily_df["Units"]
            .rolling(7)
            .mean()
        )

        fig = go.Figure()

        fig.add_trace(
            go.Bar(
                x=sku_daily_df["Date"],
                y=sku_daily_df["Units"],
                name="Daily Units",
            )
        )

        fig.add_trace(
            go.Scatter(
                x=sku_daily_df["Date"],
                y=sku_daily_df[
                    "7D Rolling Avg"
                ],
                mode="lines",
                name="7D Rolling Avg",
            )
        )

        fig.add_vrect(
            x0=cur7_start,
            x1=cur7_end
            + pd.Timedelta(days=1),
            opacity=0.15,
            line_width=0,
            annotation_text="Recent 7D",
            annotation_position="top left",
        )

        fig.update_layout(
            height=500,
            xaxis_title="Date",
            yaxis_title="Units",
            hovermode="x unified",
        )

        st.plotly_chart(
            fig,
            use_container_width=True
        )

        detail_row = (
            summary[
                summary["SKU"]
                == selected_sku
            ]
            .iloc[0]
        )

        d1, d2, d3, d4 = st.columns(4)

        d1.metric(
            "最近7天",
            f"{detail_row['最近7天销量']:,.0f}",
            detail_row["7天变化率"]
        )

        d2.metric(
            "前7天",
            f"{detail_row['前7天销量']:,.0f}"
        )

        d3.metric(
            "最近15天",
            f"{detail_row['最近15天销量']:,.0f}",
            detail_row["15天变化率"]
        )

        d4.metric(
            "趋势",
            detail_row["趋势"]
        )

    else:

        st.warning(
            "当前筛选条件下没有 SKU。"
        )


# =========================================================
# MODULE 4
# SPA 广告绩效诊断与运营看板
# =========================================================

elif module == "📢 SPA 广告绩效诊断与运营看板":

    st.title(
        "📢 SPA 广告绩效诊断与运营看板"
    )

    st.caption(
        "支持分析广告 Spend、Sales、ROAS、Clicks、Impressions 等指标。"
    )

    uploaded_ad_file = st.sidebar.file_uploader(
        "上传 SPA 广告数据",
        type=[
            "csv",
            "xlsx",
            "xls"
        ],
        key="ad_module_4",
    )

    if uploaded_ad_file is None:

        st.info(
            "请先在左侧上传 SPA 广告数据。"
        )

        st.stop()

    raw_ad = read_uploaded_file(
        uploaded_ad_file
    )

    if raw_ad is None or raw_ad.empty:

        st.warning(
            "广告文件没有有效数据。"
        )

        st.stop()

    raw_ad.columns = [
        str(c).strip()
        for c in raw_ad.columns
    ]

    date_col = find_column(
        raw_ad,
        [
            "Date",
            "Report Date",
            "Day",
            "日期",
        ],
    )

    spend_col = find_column(
        raw_ad,
        [
            "Spend",
            "Ad Spend",
            "Media Spend",
            "花费",
            "广告花费",
        ],
    )

    sales_col = find_column(
        raw_ad,
        [
            "Sales",
            "Attributed Sales",
            "Ad Sales",
            "销售额",
        ],
    )

    roas_col = find_column(
        raw_ad,
        [
            "ROAS",
            "Return on Ad Spend",
        ],
    )

    clicks_col = find_column(
        raw_ad,
        [
            "Clicks",
            "Click",
            "点击",
        ],
    )

    impressions_col = find_column(
        raw_ad,
        [
            "Impressions",
            "Impression",
            "展示",
            "曝光",
        ],
    )

    campaign_col = find_column(
        raw_ad,
        [
            "Campaign",
            "Campaign Name",
            "Campaign ID",
            "广告活动",
        ],
    )

    omsid_col = find_column(
        raw_ad,
        [
            "OMSID",
            "Promoted OMSID",
            "Promoted OMSID Number",
            "OMS ID",
        ],
    )

    if spend_col is None or sales_col is None:

        st.error(
            "广告数据至少需要 Spend 和 Sales 两列。"
        )

        st.stop()

    ad = pd.DataFrame()

    if date_col:

        ad["Date"] = pd.to_datetime(
            raw_ad[date_col],
            errors="coerce"
        )

    else:

        ad["Date"] = pd.NaT

    ad["Spend"] = clean_numeric(
        raw_ad[spend_col]
    )

    ad["Sales"] = clean_numeric(
        raw_ad[sales_col]
    )

    if roas_col:

        ad["ROAS"] = clean_numeric(
            raw_ad[roas_col]
        )

    else:

        ad["ROAS"] = np.where(
            ad["Spend"] > 0,
            ad["Sales"]
            / ad["Spend"],
            0
        )

    if clicks_col:

        ad["Clicks"] = clean_numeric(
            raw_ad[clicks_col]
        )

    else:

        ad["Clicks"] = 0

    if impressions_col:

        ad["Impressions"] = clean_numeric(
            raw_ad[impressions_col]
        )

    else:

        ad["Impressions"] = 0

    if campaign_col:

        ad["Campaign"] = (
            raw_ad[campaign_col]
            .fillna("Unknown")
            .astype(str)
        )

    else:

        ad["Campaign"] = "Unknown"

    if omsid_col:

        ad["OMSID"] = (
            raw_ad[omsid_col]
            .fillna("Unknown")
            .astype(str)
        )

    else:

        ad["OMSID"] = "Unknown"

    ad["CTR (%)"] = np.where(
        ad["Impressions"] > 0,
        ad["Clicks"]
        / ad["Impressions"]
        * 100,
        0
    )

    ad["CPC"] = np.where(
        ad["Clicks"] > 0,
        ad["Spend"]
        / ad["Clicks"],
        0
    )

    total_spend = (
        ad["Spend"].sum()
    )

    total_sales_ad = (
        ad["Sales"].sum()
    )

    overall_roas = (
        total_sales_ad
        / total_spend
        if total_spend
        else 0
    )

    total_clicks = (
        ad["Clicks"].sum()
    )

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "Ad Spend",
        money(total_spend)
    )

    c2.metric(
        "Attributed Sales",
        money(total_sales_ad)
    )

    c3.metric(
        "ROAS",
        f"{overall_roas:.2f}"
    )

    c4.metric(
        "Clicks",
        f"{total_clicks:,.0f}"
    )

    st.markdown("---")

    campaign_summary = (
        ad
        .groupby(
            "Campaign",
            as_index=False
        )
        .agg(
            Spend=(
                "Spend",
                "sum"
            ),
            Sales=(
                "Sales",
                "sum"
            ),
            Clicks=(
                "Clicks",
                "sum"
            ),
            Impressions=(
                "Impressions",
                "sum"
            ),
        )
    )

    campaign_summary["ROAS"] = np.where(
        campaign_summary["Spend"] > 0,
        campaign_summary["Sales"]
        / campaign_summary["Spend"],
        0
    )

    campaign_summary = (
        campaign_summary
        .sort_values(
            "Sales",
            ascending=False
        )
    )

    col1, col2 = st.columns(2)

    with col1:

        st.subheader(
            "Campaign Performance"
        )

        st.dataframe(
            campaign_summary.style.format(
                {
                    "Spend": "${:,.0f}",
                    "Sales": "${:,.0f}",
                    "Clicks": "{:,.0f}",
                    "Impressions": "{:,.0f}",
                    "ROAS": "{:.2f}",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )

    with col2:

        top_campaign = (
            campaign_summary
            .head(15)
            .sort_values("ROAS")
        )

        fig = px.bar(
            top_campaign,
            x="ROAS",
            y="Campaign",
            orientation="h",
            text_auto=".2f",
        )

        fig.update_layout(
            height=500
        )

        st.plotly_chart(
            fig,
            use_container_width=True
        )

    if ad["Date"].notna().any():

        st.subheader(
            "Daily Advertising Trend"
        )

        daily_ad = (
            ad
            .dropna(
                subset=["Date"]
            )
            .groupby(
                "Date",
                as_index=False
            )
            .agg(
                Spend=(
                    "Spend",
                    "sum"
                ),
                Sales=(
                    "Sales",
                    "sum"
                ),
                Clicks=(
                    "Clicks",
                    "sum"
                ),
                Impressions=(
                    "Impressions",
                    "sum"
                ),
            )
        )

        daily_ad["ROAS"] = np.where(
            daily_ad["Spend"] > 0,
            daily_ad["Sales"]
            / daily_ad["Spend"],
            0
        )

        fig = px.line(
            daily_ad,
            x="Date",
            y="ROAS",
            markers=True,
        )

        fig.update_layout(
            height=450,
            yaxis_title="ROAS"
        )

        st.plotly_chart(
            fig,
            use_container_width=True
        )

    st.subheader(
        "OMSID Performance"
    )

    omsid_summary = (
        ad
        .groupby(
            "OMSID",
            as_index=False
        )
        .agg(
            Spend=(
                "Spend",
                "sum"
            ),
            Sales=(
                "Sales",
                "sum"
            ),
            Clicks=(
                "Clicks",
                "sum"
            ),
            Impressions=(
                "Impressions",
                "sum"
            ),
        )
    )

    omsid_summary["ROAS"] = np.where(
        omsid_summary["Spend"] > 0,
        omsid_summary["Sales"]
        / omsid_summary["Spend"],
        0
    )

    omsid_summary["CTR (%)"] = np.where(
        omsid_summary["Impressions"] > 0,
        omsid_summary["Clicks"]
        / omsid_summary["Impressions"]
        * 100,
        0
    )

    omsid_summary = (
        omsid_summary
        .sort_values(
            "Sales",
            ascending=False
        )
    )

    st.dataframe(
        omsid_summary.style.format(
            {
                "Spend": "${:,.0f}",
                "Sales": "${:,.0f}",
                "Clicks": "{:,.0f}",
                "Impressions": "{:,.0f}",
                "ROAS": "{:.2f}",
                "CTR (%)": "{:.2f}%",
            }
        ),
        use_container_width=True,
        hide_index=True,
    )


# =========================================================
# MODULE 5
# 下月销售目标与 SKU 销量拆解看板
# =========================================================

elif module == "🎯 下月销售目标与 SKU 销量拆解看板":

    st.title(
        "🎯 下月销售目标与 SKU 销量拆解看板"
    )

    st.caption(
        "根据最近一段时间 SKU 销售结构，将下月目标拆解到 SKU。"
    )

    uploaded_sales_file = upload_sales_sidebar(
        "sales_module_5"
    )

    if uploaded_sales_file is None:

        st.info(
            "请先在左侧上传销售数据。"
        )

        st.stop()

    raw_sales = read_uploaded_file(
        uploaded_sales_file
    )

    df_sales, error = process_sales_data(
        raw_sales
    )

    if error:

        st.error(error)

        st.stop()

    min_date = (
        df_sales["Clean_Date"]
        .min()
        .date()
    )

    max_date = (
        df_sales["Clean_Date"]
        .max()
        .date()
    )

    st.sidebar.markdown("---")

    lookback_days = st.sidebar.number_input(
        "参考历史天数",
        min_value=7,
        max_value=180,
        value=30,
        step=1,
        key="m5_lookback",
    )

    growth_rate = st.sidebar.number_input(
        "下月目标增长率 (%)",
        min_value=-100.0,
        max_value=500.0,
        value=20.0,
        step=5.0,
        key="m5_growth",
    )

    target_sales = st.sidebar.number_input(
        "下月销售目标 ($)",
        min_value=0.0,
        value=100000.0,
        step=5000.0,
        key="m5_target",
    )

    anchor_date = st.sidebar.date_input(
        "目标基准日",
        value=max_date,
        min_value=min_date,
        max_value=max_date,
        key="m5_anchor",
    )

    anchor = pd.Timestamp(
        anchor_date
    )

    lookback_start = (
        anchor
        - pd.Timedelta(
            days=lookback_days - 1
        )
    )

    ref_df = df_sales[
        (
            df_sales["Clean_Date"]
            >= lookback_start
        )
        &
        (
            df_sales["Clean_Date"]
            <= anchor
        )
    ].copy()

    if ref_df.empty:

        st.warning(
            "参考日期范围没有数据。"
        )

        st.stop()

    sku_ref = (
        ref_df
        .groupby(
            "Clean_SKU",
            as_index=False
        )
        .agg(
            Sales=(
                "Clean_Sales",
                "sum"
            ),
            Units=(
                "Clean_Units",
                "sum"
            ),
        )
    )

    sku_ref["Avg Price"] = np.where(
        sku_ref["Units"] > 0,
        sku_ref["Sales"]
        / sku_ref["Units"],
        0
    )

    sku_ref = sku_ref[
        sku_ref["Units"] > 0
    ].copy()

    if sku_ref.empty:

        st.warning(
            "参考期间没有销量。"
        )

        st.stop()

    base_sales = (
        sku_ref["Sales"].sum()
    )

    base_units = (
        sku_ref["Units"].sum()
    )

    # If target is 0, calculate it automatically
    if target_sales <= 0:

        target_sales = (
            base_sales
            * (
                1
                + growth_rate
                / 100
            )
        )

    sku_ref["Sales Share (%)"] = np.where(
        base_sales > 0,
        sku_ref["Sales"]
        / base_sales
        * 100,
        0
    )

    sku_ref["Target Sales"] = np.where(
        base_sales > 0,
        target_sales
        * sku_ref["Sales"]
        / base_sales,
        0
    )

    sku_ref["Target Units"] = np.where(
        sku_ref["Avg Price"] > 0,
        sku_ref["Target Sales"]
        / sku_ref["Avg Price"],
        0
    )

    # Next month days
    if anchor.month == 12:

        next_year = anchor.year + 1
        next_month = 1

    else:

        next_year = anchor.year
        next_month = anchor.month + 1

    days_next_month = calendar.monthrange(
        next_year,
        next_month
    )[1]

    sku_ref["Target Daily Units"] = (
        sku_ref["Target Units"]
        / days_next_month
    )

    sku_ref[
        "Target Sales Growth (%)"
    ] = growth_rate

    sku_ref = sku_ref.sort_values(
        "Target Sales",
        ascending=False
    )

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "参考期 Sales",
        money(base_sales)
    )

    c2.metric(
        "参考期 Units",
        number(base_units)
    )

    c3.metric(
        "下月 Sales Target",
        money(target_sales)
    )

    c4.metric(
        "目标增长率",
        f"{growth_rate:+.1f}%"
    )

    st.markdown("---")

    st.subheader(
        "SKU 目标拆解"
    )

    display_target = sku_ref.copy()

    for col in [
        "Sales",
        "Avg Price",
        "Target Sales"
    ]:

        display_target[col] = (
            display_target[col]
            .map(
                lambda x:
                f"${x:,.0f}"
            )
        )

    for col in [
        "Units",
        "Target Units"
    ]:

        display_target[col] = (
            display_target[col]
            .map(
                lambda x:
                f"{x:,.0f}"
            )
        )

    display_target[
        "Target Daily Units"
    ] = (
        display_target[
            "Target Daily Units"
        ]
        .map(
            lambda x:
            f"{x:,.1f}"
        )
    )

    display_target[
        "Sales Share (%)"
    ] = (
        display_target[
            "Sales Share (%)"
        ]
        .map(
            lambda x:
            f"{x:.1f}%"
        )
    )

    display_target[
        "Target Sales Growth (%)"
    ] = (
        display_target[
            "Target Sales Growth (%)"
        ]
        .map(
            lambda x:
            f"{x:+.1f}%"
        )
    )

    st.dataframe(
        display_target[
            [
                "Clean_SKU",
                "Sales",
                "Units",
                "Avg Price",
                "Sales Share (%)",
                "Target Sales",
                "Target Units",
                "Target Daily Units",
                "Target Sales Growth (%)",
            ]
        ],
        use_container_width=True,
        hide_index=True,
        height=600,
    )

    left, right = st.columns(2)

    with left:

        chart_df = (
            sku_ref
            .head(15)
            .sort_values(
                "Target Sales"
            )
        )

        fig = px.bar(
            chart_df,
            x="Target Sales",
            y="Clean_SKU",
            orientation="h",
            text_auto=".2s",
        )

        fig.update_layout(
            height=550,
            xaxis_title="Target Sales"
        )

        st.plotly_chart(
            fig,
            use_container_width=True
        )

    with right:

        chart_df = (
            sku_ref
            .head(15)
            .sort_values(
                "Target Units"
            )
        )

        fig = px.bar(
            chart_df,
            x="Target Units",
            y="Clean_SKU",
            orientation="h",
            text_auto=".0f",
        )

        fig.update_layout(
            height=550,
            xaxis_title="Target Units"
        )

        st.plotly_chart(
            fig,
            use_container_width=True
        )

    csv_target = (
        sku_ref
        .to_csv(index=False)
        .encode("utf-8-sig")
    )

    st.download_button(
        "下载 SKU 目标拆解 CSV",
        data=csv_target,
        file_name=(
            "SKU_Target_Breakdown_"
            f"{anchor.strftime('%Y%m%d')}.csv"
        ),
        mime="text/csv",
    )
