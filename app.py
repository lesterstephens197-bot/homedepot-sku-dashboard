import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import timedelta
from io import BytesIO

# ============================================================
# 1. 页面配置
# ============================================================

st.set_page_config(
    page_title="电商全景销售与SKU动销分析看板",
    page_icon="📊",
    layout="wide"
)

st.title("📊 电商全景销售与SKU动销分析看板")
st.caption(
    "销售总览 | 月度对比 | SKU动销与日销 | 运营绩效 | "
    "SKU排名 | 渠道分析 | 退货与扣款"
)

# ============================================================
# 2. 基础工具函数
# ============================================================

def read_file(file):
    if file.name.lower().endswith(".csv"):
        try:
            return pd.read_csv(file, encoding="utf-8-sig")
        except UnicodeDecodeError:
            file.seek(0)
            return pd.read_csv(file, encoding="gb18030")
    return pd.read_excel(file)


def find_column(columns, candidates):
    for c in candidates:
        if c in columns:
            return c
    return None


def get_sku_col(columns):
    return find_column(
        columns,
        ["产品SKU", "Merchant SKU", "Vendor SKU", "PART#", "SKU"]
    )


def get_reason_col(columns):
    return find_column(
        columns,
        ["退货原因", "Return Reason", "Reason",
         "RTV Reason", "原因描述", "备注"]
    )


def safe_div(a, b):
    return a / b if b else 0


def csv_download(df, filename, label="下载CSV"):
    st.download_button(
        label,
        data=df.to_csv(index=False).encode("utf-8-sig"),
        file_name=filename,
        mime="text/csv"
    )


def month_days(month, last_data_date=None, mode="自然月"):
    p = pd.Period(month, freq="M")
    if mode == "自然月":
        return p.days_in_month
    if last_data_date is None:
        return p.days_in_month
    last_date = pd.Timestamp(last_data_date)
    if p == last_date.to_period("M"):
        return max(1, last_date.day)
    return p.days_in_month


def pct_change(current, previous):
    if pd.isna(previous) or previous == 0:
        return np.nan
    return (current / previous - 1) * 100


def add_month_change(df, group_cols, columns):
    result = df.sort_values(group_cols + ["月份"]).copy()
    for col in columns:
        previous = result.groupby(group_cols)[col].shift(1)
        result[col + "环比(%)"] = np.where(
            previous.ne(0) & previous.notna(),
            (result[col] / previous - 1) * 100,
            np.nan
        )
    return result


@st.cache_data
def load_sales_data(file):
    df = read_file(file)
    df.columns = df.columns.astype(str).str.strip()

    if "Order Date" not in df.columns:
        raise ValueError("销售表缺少 Order Date 字段")

    df["Order Date"] = pd.to_datetime(
        df["Order Date"], errors="coerce"
    )
    df = df.dropna(subset=["Order Date"]).copy()

    for col in ["Unit Cost", "Quantity", "Total Cost"]:
        if col not in df.columns:
            df[col] = 0
        df[col] = pd.to_numeric(
            df[col], errors="coerce"
        ).fillna(0)

    fallback_cost = df["Unit Cost"] * df["Quantity"]
    df["Total Cost"] = df["Total Cost"].where(
        df["Total Cost"] > 0, fallback_cost
    )

    df["月份"] = df["Order Date"].dt.strftime("%Y-%m")
    df["季度"] = df["Order Date"].dt.to_period("Q").astype(str)
    df["日期"] = df["Order Date"].dt.normalize()

    sku_col = get_sku_col(df.columns)
    if sku_col:
        df["分析SKU"] = df[sku_col].fillna("未知SKU").astype(str).str.strip()
    else:
        df["分析SKU"] = "未知SKU"

    name_col = find_column(
        df.columns, ["产品名称", "Description", "Product Name"]
    )
    df["分析产品名称"] = (
        df[name_col].fillna("").astype(str)
        if name_col else df["分析SKU"]
    )

    if "PO Number" not in df.columns:
        df["PO Number"] = [
            f"ROW-{i}" for i in range(len(df))
        ]

    return df


@st.cache_data
def load_return_data(file):
    df = read_file(file)
    df.columns = df.columns.astype(str).str.strip()

    for col in ["Order Date", "RTV Date"]:
        if col in df.columns:
            df[col] = pd.to_datetime(
                df[col], errors="coerce"
            )

    for col in ["QTY", "UNIT COST", "Total Cost",
                "10%运费", "总扣款"]:
        if col not in df.columns:
            df[col] = 0
        df[col] = pd.to_numeric(
            df[col], errors="coerce"
        ).fillna(0)

    fallback = df["QTY"] * df["UNIT COST"]
    df["Total Cost"] = df["Total Cost"].where(
        df["Total Cost"] > 0, fallback
    )
    df["10%运费"] = df["10%运费"].where(
        df["10%运费"] > 0, df["Total Cost"] * 0.1
    )
    df["总扣款"] = df["总扣款"].where(
        df["总扣款"] > 0,
        df["Total Cost"] + df["10%运费"]
    )

    for date_col, prefix in [
        ("Order Date", "Order"),
        ("RTV Date", "RTV")
    ]:
        if date_col in df.columns:
            df[prefix + "_YearMonth"] = (
                df[date_col].dt.strftime("%Y-%m")
            )
            df[prefix + "_YearQuarter"] = (
                df[date_col].dt.to_period("Q").astype(str)
            )

    return df


def sales_kpis(data, days=None):
    sales = data["Total Cost"].sum()
    qty = data["Quantity"].sum()
    orders = data["PO Number"].nunique()

    if days is None:
        if data.empty:
            days = 1
        else:
            days = max(
                (data["日期"].max() - data["日期"].min()).days + 1,
                1
            )

    return {
        "销售额": sales,
        "销量": qty,
        "订单量": orders,
        "客单价": safe_div(sales, orders),
        "日均销量": safe_div(qty, days),
        "日均销售额": safe_div(sales, days)
    }


# ============================================================
# 3. SKU月度数据计算
# ============================================================

def build_sku_monthly(data, day_mode="自然月"):
    if data.empty:
        return pd.DataFrame()

    monthly = data.groupby(
        ["分析SKU", "月份"], as_index=False
    ).agg(
        产品名称=("分析产品名称", "first"),
        月销售额=("Total Cost", "sum"),
        月销量=("Quantity", "sum"),
        月订单量=("PO Number", "nunique"),
        动销天数=("日期", "nunique")
    )

    # 补齐SKU在数据时间范围内没有销售的月份
    months = pd.period_range(
        data["日期"].min().to_period("M"),
        data["日期"].max().to_period("M"),
        freq="M"
    ).astype(str).tolist()

    sku_info = data.groupby("分析SKU", as_index=False).agg(
        产品名称=("分析产品名称", "first")
    )

    grid = pd.MultiIndex.from_product(
        [sku_info["分析SKU"], months],
        names=["分析SKU", "月份"]
    ).to_frame(index=False)

    monthly = grid.merge(
        monthly.drop(columns=["产品名称"]),
        on=["分析SKU", "月份"],
        how="left"
    ).merge(
        sku_info,
        on="分析SKU",
        how="left"
    )

    for col in ["月销售额", "月销量", "月订单量", "动销天数"]:
        monthly[col] = monthly[col].fillna(0)

    last_date = data["日期"].max()

    monthly["统计天数"] = monthly["月份"].apply(
        lambda m: month_days(m, last_date, day_mode)
    )

    monthly["日均销量"] = (
        monthly["月销量"] / monthly["统计天数"]
    )

    monthly["日均销售额"] = (
        monthly["月销售额"] / monthly["统计天数"]
    )

    monthly["动销率(%)"] = (
        monthly["动销天数"] / monthly["统计天数"] * 100
    )

    monthly["动销日均销量"] = np.where(
        monthly["动销天数"] > 0,
        monthly["月销量"] / monthly["动销天数"],
        0
    )

    monthly["平均单价"] = np.where(
        monthly["月销量"] > 0,
        monthly["月销售额"] / monthly["月销量"],
        0
    )

    monthly = add_month_change(
        monthly,
        ["分析SKU"],
        ["月销量", "月销售额", "日均销量"]
    )

    return monthly.sort_values(
        ["分析SKU", "月份"]
    ).reset_index(drop=True)


def build_monthly_summary(data, day_mode="自然月"):
    if data.empty:
        return pd.DataFrame()

    monthly = data.groupby("月份", as_index=False).agg(
        销售额=("Total Cost", "sum"),
        销量=("Quantity", "sum"),
        订单量=("PO Number", "nunique"),
        动销SKU数=("分析SKU", "nunique"),
        有销售天数=("日期", "nunique")
    )

    all_months = pd.DataFrame({
        "月份": pd.period_range(
            data["日期"].min().to_period("M"),
            data["日期"].max().to_period("M"),
            freq="M"
        ).astype(str)
    })

    monthly = all_months.merge(
        monthly, on="月份", how="left"
    ).fillna(0)

    last_date = data["日期"].max()
    monthly["统计天数"] = monthly["月份"].apply(
        lambda m: month_days(m, last_date, day_mode)
    )
    monthly["日均销量"] = monthly["销量"] / monthly["统计天数"]
    monthly["日均销售额"] = monthly["销售额"] / monthly["统计天数"]
    monthly["客单价"] = np.where(
        monthly["订单量"] > 0,
        monthly["销售额"] / monthly["订单量"],
        0
    )

    for col in ["销售额", "销量", "日均销量", "动销SKU数"]:
        prev = monthly[col].shift(1)
        monthly[col + "环比(%)"] = np.where(
            prev.notna() & prev.ne(0),
            (monthly[col] / prev - 1) * 100,
            np.nan
        )

    return monthly


# ============================================================
# 4. 文件上传与全局筛选
# ============================================================

st.sidebar.header("📁 数据导入")

sales_file = st.sidebar.file_uploader(
    "1. 上传销售数据",
    type=["csv", "xlsx"]
)

return_file = st.sidebar.file_uploader(
    "2. 上传退货数据（选填）",
    type=["csv", "xlsx"]
)

total_orders_file = st.sidebar.file_uploader(
    "3. 上传全量订单表（选填）",
    type=["csv", "xlsx"]
)

if sales_file is None:
    st.info("请先在左侧上传销售数据表。")
    st.stop()

try:
    raw_df = load_sales_data(sales_file)
except Exception as e:
    st.error(f"销售数据读取失败：{e}")
    st.stop()

if raw_df.empty:
    st.warning("销售表没有有效的 Order Date 数据。")
    st.stop()

rtv_df = (
    load_return_data(return_file)
    if return_file is not None else None
)

total_orders_df = (
    load_sales_data(total_orders_file)
    if total_orders_file is not None else None
)

df = raw_df.copy()

st.sidebar.header("🔍 全局筛选")

if "品牌" in df.columns:
    brands = sorted(df["品牌"].dropna().astype(str).unique())
    selected_brands = st.sidebar.multiselect(
        "品牌", brands, default=brands
    )
    df = df[df["品牌"].astype(str).isin(selected_brands)]

if "运营" in df.columns:
    operators = sorted(df["运营"].dropna().astype(str).unique())
    selected_operators = st.sidebar.multiselect(
        "运营负责人", operators, default=operators
    )
    df = df[df["运营"].astype(str).isin(selected_operators)]

if df.empty:
    st.warning("当前筛选条件下没有数据。")
    st.stop()

st.sidebar.divider()

day_mode = st.sidebar.radio(
    "日均销量计算口径",
    ["自然月", "当前月按已有数据天数"],
    index=0
)

st.sidebar.caption(
    "自然月：销量÷当月日历天数；"
    "当前月按已有数据天数：最新月份使用数据截止日期的日数。"
)

# ============================================================
# 5. 创建七大分析看板
# ============================================================

tabs = st.tabs([
    "📊 销售总览",
    "📅 月度销售对比",
    "📦 SKU月度动销与日销",
    "👤 运营绩效",
    "🏆 SKU排名",
    "🏪 渠道分析",
    "🔄 退货分析"
])

# ============================================================
# TAB 1：销售总览
# ============================================================

with tabs[0]:
    st.header("📊 销售总览")

    min_date = df["日期"].min().date()
    max_date = df["日期"].max().date()

    period = st.radio(
        "选择统计周期",
        ["全部", "近7天", "近15天", "近30天", "自定义"],
        horizontal=True
    )

    if period == "近7天":
        start = max_date - timedelta(days=6)
    elif period == "近15天":
        start = max_date - timedelta(days=14)
    elif period == "近30天":
        start = max_date - timedelta(days=29)
    elif period == "自定义":
        selected = st.date_input(
            "日期范围", (min_date, max_date)
        )
        if len(selected) == 2:
            start, max_date = selected
        else:
            start = min_date
    else:
        start = min_date

    filtered = df[
        (df["日期"].dt.date >= start) &
        (df["日期"].dt.date <= max_date)
    ].copy()

    days = max((max_date - start).days + 1, 1)
    k = sales_kpis(filtered, days)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("总销售额", f"${k['销售额']:,.2f}")
    c2.metric("总销量", f"{k['销量']:,.0f}")
    c3.metric("总订单量", f"{k['订单量']:,}")
    c4.metric("日均销量", f"{k['日均销量']:.2f}")

    c5, c6 = st.columns(2)
    c5.metric("日均销售额", f"${k['日均销售额']:,.2f}")
    c6.metric("平均客单价", f"${k['客单价']:,.2f}")

    st.divider()

    st.subheader("销售额与销量趋势")

    grain = st.radio(
        "时间粒度",
        ["按日", "按周", "按月"],
        horizontal=True
    )

    if grain == "按日":
        trend = filtered.groupby("日期", as_index=False).agg(
            销售额=("Total Cost", "sum"),
            销量=("Quantity", "sum")
        )
        x_col = "日期"
    elif grain == "按周":
        temp = filtered.copy()
        temp["周"] = temp["日期"].dt.to_period("W").dt.start_time
        trend = temp.groupby("周", as_index=False).agg(
            销售额=("Total Cost", "sum"),
            销量=("Quantity", "sum")
        )
        x_col = "周"
    else:
        trend = filtered.groupby("月份", as_index=False).agg(
            销售额=("Total Cost", "sum"),
            销量=("Quantity", "sum")
        )
        x_col = "月份"

    a, b = st.columns(2)

    with a:
        st.plotly_chart(
            px.line(
                trend, x=x_col, y="销售额",
                markers=True, title="销售额趋势"
            ),
            use_container_width=True
        )

    with b:
        st.plotly_chart(
            px.line(
                trend, x=x_col, y="销量",
                markers=True, title="销量趋势"
            ),
            use_container_width=True
        )

    st.subheader("近7天与近15天动销对比")

    d7 = df[df["日期"].dt.date >= max_date - timedelta(days=6)]
    d15 = df[df["日期"].dt.date >= max_date - timedelta(days=14)]

    k7 = sales_kpis(d7, 7)
    k15 = sales_kpis(d15, 15)

    compare = pd.DataFrame({
        "指标": ["销售额", "销量", "订单量", "日均销量", "日均销售额"],
        "近7天": [
            k7["销售额"], k7["销量"], k7["订单量"],
            k7["日均销量"], k7["日均销售额"]
        ],
        "近15天": [
            k15["销售额"], k15["销量"], k15["订单量"],
            k15["日均销量"], k15["日均销售额"]
        ]
    })

    st.dataframe(compare, use_container_width=True, hide_index=True)

# ============================================================
# TAB 2：月度销售对比
# ============================================================

with tabs[1]:
    st.header("📅 各月份销售数据对比")

    monthly = build_monthly_summary(df, day_mode)

    latest = monthly.iloc[-1]
    previous = monthly.iloc[-2] if len(monthly) > 1 else None

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "最新月销售额",
        f"${latest['销售额']:,.2f}",
        delta=(
            f"{latest['销售额环比(%)']:+.1f}%"
            if pd.notna(latest["销售额环比(%)"]) else None
        )
    )

    c2.metric(
        "最新月销量",
        f"{latest['销量']:,.0f}",
        delta=(
            f"{latest['销量环比(%)']:+.1f}%"
            if pd.notna(latest["销量环比(%)"]) else None
        )
    )

    c3.metric(
        "最新月日均销量",
        f"{latest['日均销量']:.2f}",
        delta=(
            f"{latest['日均销量环比(%)']:+.1f}%"
            if pd.notna(latest["日均销量环比(%)"]) else None
        )
    )

    c4.metric(
        "最新月动销SKU数",
        f"{latest['动销SKU数']:,.0f}",
        delta=(
            f"{latest['动销SKU数环比(%)']:+.1f}%"
            if pd.notna(latest["动销SKU数环比(%)"]) else None
        )
    )

    st.divider()

    c1, c2 = st.columns(2)

    with c1:
        st.plotly_chart(
            px.bar(
                monthly,
                x="月份",
                y="销售额",
                text_auto=".2s",
                title="各月销售额对比"
            ),
            use_container_width=True
        )

    with c2:
        st.plotly_chart(
            px.bar(
                monthly,
                x="月份",
                y="销量",
                text_auto=".2s",
                title="各月销量对比"
            ),
            use_container_width=True
        )

    c3, c4 = st.columns(2)

    with c3:
        st.plotly_chart(
            px.line(
                monthly,
                x="月份",
                y="日均销量",
                markers=True,
                title="各月日均销量趋势"
            ),
            use_container_width=True
        )

    with c4:
        st.plotly_chart(
            px.line(
                monthly,
                x="月份",
                y="动销SKU数",
                markers=True,
                title="各月动销SKU数量趋势"
            ),
            use_container_width=True
        )

    st.subheader("月度销售额与销量环比")

    c5, c6 = st.columns(2)

    with c5:
        st.plotly_chart(
            px.bar(
                monthly,
                x="月份",
                y="销售额环比(%)",
                title="销售额环比增长率"
            ),
            use_container_width=True
        )

    with c6:
        st.plotly_chart(
            px.bar(
                monthly,
                x="月份",
                y="销量环比(%)",
                title="销量环比增长率"
            ),
            use_container_width=True
        )

    st.subheader("月度完整数据")

    st.dataframe(
        monthly.round(2),
        use_container_width=True,
        hide_index=True
    )

    csv_download(
        monthly,
        "月度销售对比.csv",
        "导出月度销售数据"
    )

# ============================================================
# TAB 3：SKU月度动销与日销分析（核心新增模块）
# ============================================================

with tabs[2]:
    st.header("📦 SKU各月份动销与日销对比")

    st.caption(
        "月销量、日均销量、动销天数、动销率、动销日均销量、"
        "销售额、环比增长、月度排名和热力图"
    )

    sku_monthly = build_sku_monthly(df, day_mode)

    if sku_monthly.empty:
        st.warning("没有可分析的SKU数据。")
    else:
        sku_total = sku_monthly.groupby(
            "分析SKU"
        )["月销量"].sum().sort_values(ascending=False)

        all_skus = sku_total.index.tolist()
        all_months = sorted(sku_monthly["月份"].unique())

        st.subheader("🔍 SKU筛选")

        f1, f2, f3 = st.columns([2, 2, 1])

        with f1:
            sku_search = st.text_input(
                "搜索SKU或产品名称",
                placeholder="输入型号，例如 CTH80B"
            )

        with f2:
            sku_limit = st.selectbox(
                "默认显示SKU范围",
                ["全部SKU", "销量TOP10", "销量TOP20", "销量TOP50"],
                index=1
            )

        if sku_limit == "销量TOP10":
            default_skus = all_skus[:10]
        elif sku_limit == "销量TOP20":
            default_skus = all_skus[:20]
        elif sku_limit == "销量TOP50":
            default_skus = all_skus[:50]
        else:
            default_skus = all_skus

        if sku_search:
            matched = sku_monthly[
                sku_monthly["分析SKU"].str.contains(
                    sku_search, case=False, na=False, regex=False
                ) |
                sku_monthly["产品名称"].str.contains(
                    sku_search, case=False, na=False, regex=False
                )
            ]["分析SKU"].unique().tolist()

            default_skus = matched

        with f3:
            metric_choice = st.selectbox(
                "核心分析指标",
                ["月销量", "日均销量", "动销日均销量",
                 "动销天数", "动销率(%)", "月销售额"]
            )

        selected_skus = st.multiselect(
            "选择对比的SKU（可多选）",
            options=all_skus,
            default=default_skus
        )

        selected_months = st.multiselect(
            "选择对比月份",
            options=all_months,
            default=all_months
        )

        sku_view = sku_monthly[
            sku_monthly["分析SKU"].isin(selected_skus) &
            sku_monthly["月份"].isin(selected_months)
        ].copy()

        if sku_view.empty:
            st.info("请选择至少一个SKU和一个月份。")
        else:
            st.divider()

            # ------------------------------------------------
            # 3.1 SKU整体动销KPI
            # ------------------------------------------------

            st.subheader("SKU动销核心指标")

            total_qty = sku_view["月销量"].sum()
            total_sales = sku_view["月销售额"].sum()
            active_sku_count = sku_view.loc[
                sku_view["月销量"] > 0, "分析SKU"
            ].nunique()

            avg_daily = sku_view["日均销量"].sum() / max(
                sku_view["月份"].nunique(), 1
            )

            k1, k2, k3, k4 = st.columns(4)

            k1.metric("累计销量", f"{total_qty:,.0f} 件")
            k2.metric("累计销售额", f"${total_sales:,.2f}")
            k3.metric("有动销SKU数量", f"{active_sku_count:,}")
            k4.metric("平均每月合计日均销量", f"{avg_daily:.2f} 件/天")

            st.divider()

            # ------------------------------------------------
            # 3.2 多SKU月度趋势
            # ------------------------------------------------

            st.subheader("📈 SKU各月动销趋势对比")

            fig_line = px.line(
                sku_view,
                x="月份",
                y=metric_choice,
                color="分析SKU",
                markers=True,
                title=f"SKU各月{metric_choice}趋势",
                hover_data=[
                    "产品名称", "月销量", "日均销量",
                    "动销天数", "动销率(%)", "动销日均销量"
                ]
            )

            fig_line.update_layout(
                xaxis_title="月份",
                yaxis_title=metric_choice,
                legend_title="SKU",
                hovermode="x unified"
            )

            st.plotly_chart(
                fig_line,
                use_container_width=True
            )

            # ------------------------------------------------
            # 3.3 各月SKU销量柱状图
            # ------------------------------------------------

            st.subheader("📊 SKU各月份销量对比")

            fig_bar = px.bar(
                sku_view,
                x="月份",
                y=metric_choice,
                color="分析SKU",
                barmode="group",
                title=f"各SKU月度{metric_choice}对比"
            )

            st.plotly_chart(
                fig_bar,
                use_container_width=True
            )

            # ------------------------------------------------
            # 3.4 SKU月度动销热力图
            # ------------------------------------------------

            st.subheader("🔥 SKU月度动销热力图")

            heatmap_df = sku_view.pivot_table(
                index="分析SKU",
                columns="月份",
                values=metric_choice,
                aggfunc="sum",
                fill_value=0
            )

            fig_heat = px.imshow(
                heatmap_df,
                labels={
                    "x": "月份",
                    "y": "SKU",
                    "color": metric_choice
                },
                aspect="auto",
                color_continuous_scale="Blues",
                title=f"SKU月度{metric_choice}热力图"
            )

            fig_heat.update_layout(
                height=max(450, min(1400, len(heatmap_df) * 28))
            )

            st.plotly_chart(
                fig_heat,
                use_container_width=True
            )

            # ------------------------------------------------
            # 3.5 SKU月度排名
            # ------------------------------------------------

            st.divider()
            st.subheader("🏆 指定月份SKU动销排行榜")

            rank_month = st.selectbox(
                "选择排名月份",
                options=sorted(selected_months, reverse=True)
            )

            rank_df = sku_monthly[
                sku_monthly["月份"] == rank_month
            ].copy()

            rank_df = rank_df.sort_values(
                metric_choice, ascending=False
            )

            rank_df.insert(
                0, "排名", range(1, len(rank_df) + 1)
            )

            rank_top = st.slider(
                "显示TOP多少个SKU",
                min_value=5,
                max_value=100,
                value=20,
                step=5
            )

            top_df = rank_df.head(rank_top)

            fig_rank = px.bar(
                top_df.sort_values(metric_choice),
                x=metric_choice,
                y="分析SKU",
                orientation="h",
                text_auto=".2f",
                title=f"{rank_month} SKU {metric_choice} TOP{rank_top}"
            )

            fig_rank.update_layout(
                height=max(450, len(top_df) * 28)
            )

            st.plotly_chart(
                fig_rank,
                use_container_width=True
            )

            st.dataframe(
                rank_df.round(2),
                use_container_width=True,
                hide_index=True
            )

            # ------------------------------------------------
            # 3.6 SKU日销与动销效率诊断
            # ------------------------------------------------

            st.divider()
            st.subheader("🎯 SKU日销与动销效率分析")

            efficiency_month = st.selectbox(
                "选择效率分析月份",
                options=sorted(selected_months, reverse=True),
                key="eff_month"
            )

            eff_df = sku_monthly[
                sku_monthly["月份"] == efficiency_month
            ].copy()

            eff_df = eff_df[eff_df["月销量"] > 0]

            if not eff_df.empty:
                fig_scatter = px.scatter(
                    eff_df,
                    x="动销率(%)",
                    y="动销日均销量",
                    size="月销量",
                    color="月销售额",
                    hover_name="分析SKU",
                    hover_data=[
                        "产品名称", "月销量",
                        "日均销量", "动销天数"
                    ],
                    title="SKU动销率 vs 动销日均销量",
                    size_max=55
                )

                st.plotly_chart(
                    fig_scatter,
                    use_container_width=True
                )

                st.caption(
                    "右上角：销售频繁且出单日销量高；"
                    "左上角：销售不频繁但出单日销量高；"
                    "右下角：销售稳定但单日销量较低。"
                )

            # ------------------------------------------------
            # 3.7 SKU各月销量透视表
            # ------------------------------------------------

            st.divider()
            st.subheader("📋 SKU各月横向对比透视表")

            pivot_metric = st.selectbox(
                "选择透视表指标",
                [
                    "月销量", "日均销量", "动销日均销量",
                    "动销天数", "动销率(%)", "月销售额",
                    "月销量环比(%)", "日均销量环比(%)",
                    "月销售额环比(%)"
                ]
            )

            pivot_df = sku_view.pivot_table(
                index=["分析SKU", "产品名称"],
                columns="月份",
                values=pivot_metric,
                aggfunc="first"
            )

            pivot_df = pivot_df.reindex(
                columns=sorted(pivot_df.columns)
            )

            st.dataframe(
                pivot_df.round(2),
                use_container_width=True
            )

            csv_download(
                pivot_df.reset_index(),
                f"SKU月度{pivot_metric}对比.csv",
                "导出SKU月度透视表"
            )

            # ------------------------------------------------
            # 3.8 SKU完整月度数据
            # ------------------------------------------------

            st.divider()
            st.subheader("📑 SKU月度动销完整明细")

            detail_columns = [
                "分析SKU", "产品名称", "月份",
                "月销量", "月销售额", "月订单量",
                "统计天数", "动销天数", "动销率(%)",
                "日均销量", "动销日均销量",
                "日均销售额", "平均单价",
                "月销量环比(%)",
                "月销售额环比(%)",
                "日均销量环比(%)"
            ]

            detail_df = sku_view[detail_columns].copy()

            st.dataframe(
                detail_df.round(2),
                use_container_width=True,
                hide_index=True
            )

            csv_download(
                detail_df,
                "SKU月度动销完整明细.csv",
                "导出完整SKU月度数据"
            )

# ============================================================
# TAB 4：运营绩效
# ============================================================

with tabs[3]:
    st.header("👤 运营人员绩效分析")

    if "运营" not in df.columns:
        st.warning("销售数据中没有'运营'字段。")
    else:
        op_summary = df.groupby("运营", as_index=False).agg(
            销售额=("Total Cost", "sum"),
            销量=("Quantity", "sum"),
            订单量=("PO Number", "nunique"),
            动销SKU数=("分析SKU", "nunique")
        )

        op_summary["客单价"] = np.where(
            op_summary["订单量"] > 0,
            op_summary["销售额"] / op_summary["订单量"],
            0
        )

        total_sales = op_summary["销售额"].sum()

        op_summary["销售额占比(%)"] = np.where(
            total_sales > 0,
            op_summary["销售额"] / total_sales * 100,
            0
        )

        op_summary = op_summary.sort_values(
            "销售额", ascending=False
        )

        c1, c2 = st.columns(2)

        with c1:
            st.plotly_chart(
                px.bar(
                    op_summary,
                    x="运营",
                    y="销售额",
                    text_auto=".2s",
                    title="运营人员销售额排名"
                ),
                use_container_width=True
            )

        with c2:
            st.plotly_chart(
                px.pie(
                    op_summary,
                    names="运营",
                    values="销售额",
                    hole=0.4,
                    title="运营人员销售额贡献占比"
                ),
                use_container_width=True
            )

        st.subheader("运营人员各月销售对比")

        op_monthly = df.groupby(
            ["运营", "月份"], as_index=False
        ).agg(
            销售额=("Total Cost", "sum"),
            销量=("Quantity", "sum"),
            订单量=("PO Number", "nunique")
        )

        op_metric = st.selectbox(
            "选择运营对比指标",
            ["销售额", "销量", "订单量"]
        )

        st.plotly_chart(
            px.line(
                op_monthly,
                x="月份",
                y=op_metric,
                color="运营",
                markers=True,
                title=f"运营人员月度{op_metric}对比"
            ),
            use_container_width=True
        )

        st.dataframe(
            op_summary.round(2),
            use_container_width=True,
            hide_index=True
        )

        csv_download(
            op_monthly,
            "运营人员月度绩效.csv",
            "导出运营月度绩效"
        )

# ============================================================
# TAB 5：SKU排名与帕累托分析
# ============================================================

with tabs[4]:
    st.header("🏆 SKU综合排名与动销分析")

    sku_rank = df.groupby(
        "分析SKU", as_index=False
    ).agg(
        产品名称=("分析产品名称", "first"),
        总销售额=("Total Cost", "sum"),
        总销量=("Quantity", "sum"),
        总订单量=("PO Number", "nunique"),
        动销天数=("日期", "nunique")
    )

    days = max(
        (df["日期"].max() - df["日期"].min()).days + 1,
        1
    )

    sku_rank["日均销量"] = sku_rank["总销量"] / days

    sku_rank = sku_rank.sort_values(
        "总销售额", ascending=False
    ).reset_index(drop=True)

    sku_rank.insert(
        0, "排名", range(1, len(sku_rank) + 1)
    )

    total = sku_rank["总销售额"].sum()

    sku_rank["销售额占比(%)"] = np.where(
        total > 0,
        sku_rank["总销售额"] / total * 100,
        0
    )

    sku_rank["累计销售额占比(%)"] = (
        sku_rank["销售额占比(%)"].cumsum()
    )

    def sku_grade(pct):
        if pct <= 80:
            return "S/A级 核心产品"
        elif pct <= 95:
            return "B级 腰部产品"
        return "C级 尾部产品"

    sku_rank["SKU等级"] = (
        sku_rank["累计销售额占比(%)"].apply(sku_grade)
    )

    top_n = st.slider(
        "显示SKU排名数量",
        5, 100, 20, 5
    )

    rank_metric = st.radio(
        "排名指标",
        ["总销售额", "总销量", "日均销量"],
        horizontal=True
    )

    chart_df = sku_rank.sort_values(
        rank_metric, ascending=False
    ).head(top_n)

    st.plotly_chart(
        px.bar(
            chart_df.sort_values(rank_metric),
            x=rank_metric,
            y="分析SKU",
            orientation="h",
            title=f"SKU {rank_metric} TOP{top_n}"
        ),
        use_container_width=True
    )

    st.subheader("SKU完整排名")

    st.dataframe(
        sku_rank.round(2),
        use_container_width=True,
        hide_index=True
    )

    csv_download(
        sku_rank,
        "SKU综合排名.csv",
        "导出SKU排名"
    )

# ============================================================
# TAB 6：HD门店与个人地址分析
# ============================================================

with tabs[5]:
    st.header("🏪 HD门店 vs 个人地址分析")

    address1 = (
        df["ShipTo Address1"].fillna("").astype(str)
        if "ShipTo Address1" in df.columns
        else pd.Series("", index=df.index)
    )

    address2 = (
        df["ShipTo Address2"].fillna("").astype(str)
        if "ShipTo Address2" in df.columns
        else pd.Series("", index=df.index)
    )

    pattern = r"c/o\s*thd\s*ship\s*to\s*store"

    is_store = (
        address1.str.contains(pattern, case=False, regex=True) |
        address2.str.contains(pattern, case=False, regex=True)
    )

    channel_df = df.copy()

    channel_df["地址类型"] = np.where(
        is_store,
        "HD门店 Ship to Store",
        "个人地址 Home Delivery"
    )

    channel_summary = channel_df.groupby(
        "地址类型", as_index=False
    ).agg(
        销售额=("Total Cost", "sum"),
        销量=("Quantity", "sum"),
        订单量=("PO Number", "nunique")
    )

    c1, c2 = st.columns(2)

    with c1:
        st.plotly_chart(
            px.pie(
                channel_summary,
                names="地址类型",
                values="销售额",
                hole=0.4,
                title="渠道销售额占比"
            ),
            use_container_width=True
        )

    with c2:
        st.plotly_chart(
            px.pie(
                channel_summary,
                names="地址类型",
                values="订单量",
                hole=0.4,
                title="渠道订单量占比"
            ),
            use_container_width=True
        )

    st.subheader("渠道月度趋势")

    channel_monthly = channel_df.groupby(
        ["月份", "地址类型"], as_index=False
    ).agg(
        销售额=("Total Cost", "sum"),
        销量=("Quantity", "sum"),
        订单量=("PO Number", "nunique")
    )

    st.plotly_chart(
        px.bar(
            channel_monthly,
            x="月份",
            y="销售额",
            color="地址类型",
            barmode="group",
            title="HD门店与个人地址月度销售额"
        ),
        use_container_width=True
    )

    st.dataframe(
        channel_summary,
        use_container_width=True,
        hide_index=True
    )

# ============================================================
# TAB 7：退货与扣款分析
# ============================================================

with tabs[6]:
    st.header("🔄 退货与扣款综合分析")

    if rtv_df is None or rtv_df.empty:
        st.info("请上传退货数据表以查看退货分析。")
    else:
        rtv_sku = get_sku_col(rtv_df.columns)
        reason_col = get_reason_col(rtv_df.columns)

        c1, c2, c3, c4 = st.columns(4)

        c1.metric(
            "累计退货件数",
            f"{rtv_df['QTY'].sum():,.0f}"
        )
        c2.metric(
            "累计退货货值",
            f"${rtv_df['Total Cost'].sum():,.2f}"
        )
        c3.metric(
            "累计运费扣款",
            f"${rtv_df['10%运费'].sum():,.2f}"
        )
        c4.metric(
            "累计总扣款",
            f"${rtv_df['总扣款'].sum():,.2f}"
        )

        if not rtv_sku:
            st.warning("退货表缺少SKU字段。")
        else:
            rtv = rtv_df.copy()
            rtv["分析SKU"] = rtv[rtv_sku].astype(str).str.strip()

            source = (
                total_orders_df
                if total_orders_df is not None
                else raw_df
            )

            shipped = source.groupby(
                "分析SKU", as_index=False
            ).agg(
                总出货量=("Quantity", "sum")
            )

            returns = rtv.groupby(
                "分析SKU", as_index=False
            ).agg(
                退货件数=("QTY", "sum"),
                退货货值=("Total Cost", "sum"),
                运费扣款=("10%运费", "sum"),
                总扣款=("总扣款", "sum")
            )

            returns = returns.merge(
                shipped,
                on="分析SKU",
                how="left"
            )

            returns["总出货量"] = (
                returns["总出货量"].fillna(0)
            )

            returns["退货率(%)"] = np.where(
                returns["总出货量"] > 0,
                returns["退货件数"] /
                returns["总出货量"] * 100,
                np.nan
            )

            min_qty = st.slider(
                "最低出货量门槛",
                0, 500, 10
            )

            rank = returns[
                returns["总出货量"] >= min_qty
            ].copy()

            c1, c2 = st.columns(2)

            with c1:
                top_qty = rank.nlargest(
                    10, "退货件数"
                )

                st.plotly_chart(
                    px.bar(
                        top_qty,
                        x="退货件数",
                        y="分析SKU",
                        orientation="h",
                        title="退货件数TOP10"
                    ),
                    use_container_width=True
                )

            with c2:
                top_rate = rank.nlargest(
                    10, "退货率(%)"
                )

                st.plotly_chart(
                    px.bar(
                        top_rate,
                        x="退货率(%)",
                        y="分析SKU",
                        orientation="h",
                        title="退货率TOP10"
                    ),
                    use_container_width=True
                )

            st.subheader("SKU退货完整明细")

            st.dataframe(
                rank.round(2),
                use_container_width=True,
                hide_index=True
            )

            if reason_col:
                st.divider()
                st.subheader("退货原因分析")

                reason_df = rtv.copy()
                reason_df[reason_col] = (
                    reason_df[reason_col]
                    .fillna("未注明原因")
                    .astype(str)
                )

                reason_summary = reason_df.groupby(
                    reason_col, as_index=False
                ).agg(
                    退货件数=("QTY", "sum"),
                    总扣款=("总扣款", "sum")
                )

                st.plotly_chart(
                    px.pie(
                        reason_summary,
                        names=reason_col,
                        values="退货件数",
                        hole=0.4,
                        title="退货原因占比"
                    ),
                    use_container_width=True
                )

                st.dataframe(
                    reason_summary,
                    use_container_width=True,
                    hide_index=True
                )

            st.divider()
            st.subheader("退货月度趋势")

            if "RTV_YearMonth" in rtv.columns:
                return_monthly = rtv.dropna(
                    subset=["RTV_YearMonth"]
                ).groupby(
                    "RTV_YearMonth", as_index=False
                ).agg(
                    退货件数=("QTY", "sum"),
                    退货货值=("Total Cost", "sum"),
                    总扣款=("总扣款", "sum")
                )

                st.plotly_chart(
                    px.bar(
                        return_monthly,
                        x="RTV_YearMonth",
                        y="总扣款",
                        title="各月退货扣款趋势"
                    ),
                    use_container_width=True
                )

                st.dataframe(
                    return_monthly,
                    use_container_width=True,
                    hide_index=True
                )

            csv_download(
                returns,
                "SKU退货分析.csv",
                "导出SKU退货分析"
            )

# ============================================================
# 页面底部
# ============================================================

st.divider()

st.caption(
    "数据说明：销售额按 Total Cost 计算；"
    "月度按 Order Date 归属；"
    "日均销量按所选统计天数计算；"
    "动销日均销量=月销量/实际有销售记录的天数；"
    "SKU月度环比以相邻自然月为基准。"
)
