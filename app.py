
import calendar
import io
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(
    page_title="SKU 月度动销看板",
    page_icon="📊",
    layout="wide"
)

st.title("📊 SKU 月度动销与日销对比")
st.caption(
    "按自然月对比 SKU 销量、日均销量、"
    "动销天数、销售额及环比变化"
)


# ==========================================
# 1. 数据加载
# ==========================================

@st.cache_data
def read_data(data, filename):
    buf = io.BytesIO(data)

    if filename.lower().endswith(".csv"):
        try:
            df = pd.read_csv(
                buf,
                encoding="utf-8-sig"
            )
        except UnicodeDecodeError:
            buf.seek(0)
            df = pd.read_csv(
                buf,
                encoding="gb18030"
            )
    else:
        df = pd.read_excel(buf)

    df.columns = (
        df.columns.astype(str).str.strip()
    )

    return df


def get_sku_column(columns):
    candidates = [
        "产品SKU",
        "Merchant SKU",
        "Vendor SKU",
        "PART#",
        "Vendor Part #",
        "SKU"
    ]

    for col in candidates:
        if col in columns:
            return col

    return None


# ==========================================
# 2. 上传销售数据
# ==========================================

uploaded_file = st.file_uploader(
    "上传销售数据（CSV / Excel）",
    type=["csv", "xlsx"]
)

if uploaded_file is None:
    st.info(
        "请上传销售数据表，至少包含 "
        "Order Date、Quantity 和 SKU 字段。"
    )
    st.stop()

df = read_data(
    uploaded_file.getvalue(),
    uploaded_file.name
)

sku_col = get_sku_column(df.columns)

required_columns = [
    "Order Date",
    "Quantity"
]

missing = [
    col for col in required_columns
    if col not in df.columns
]

if sku_col is None:
    missing.append("SKU")

if missing:
    st.error(
        "缺少必要字段：" + "、".join(missing)
    )
    st.stop()


# ==========================================
# 3. 数据清洗
# ==========================================

df["Order Date"] = pd.to_datetime(
    df["Order Date"],
    errors="coerce"
)

df["Quantity"] = pd.to_numeric(
    df["Quantity"],
    errors="coerce"
).fillna(0)

df = df.dropna(
    subset=["Order Date", sku_col]
).copy()

df["SKU"] = (
    df[sku_col].astype(str).str.strip()
)

df = df[
    df["SKU"].ne("")
    & df["SKU"].ne("nan")
].copy()

if df.empty:
    st.warning("没有有效的销售数据。")
    st.stop()

if "Total Cost" in df.columns:
    df["Total Cost"] = pd.to_numeric(
        df["Total Cost"],
        errors="coerce"
    )
else:
    df["Total Cost"] = float("nan")

if "Unit Cost" in df.columns:
    unit_cost = pd.to_numeric(
        df["Unit Cost"],
        errors="coerce"
    )

    df["Total Cost"] = (
        df["Total Cost"].fillna(
            unit_cost * df["Quantity"]
        )
    )

df["Total Cost"] = (
    df["Total Cost"].fillna(0)
)

df["月份"] = (
    df["Order Date"]
    .dt.to_period("M")
    .astype(str)
)

df["订单日"] = (
    df["Order Date"].dt.normalize()
)

name_col = next(
    (
        col for col in [
            "产品名称",
            "Description",
            "Product Name"
        ]
        if col in df.columns
    ),
    None
)

if name_col:
    df["产品名称"] = (
        df[name_col].fillna("").astype(str)
    )
else:
    df["产品名称"] = ""


# ==========================================
# 4. 全局筛选
# ==========================================

with st.sidebar:

    st.header("🔍 筛选条件")

    for field, label in [
        ("品牌", "品牌"),
        ("运营", "运营人员")
    ]:

        if field in df.columns:

            options = sorted(
                df[field]
                .dropna()
                .astype(str)
                .unique()
                .tolist()
            )

            selected = st.multiselect(
                label,
                options,
                default=options
            )

            df = df[
                df[field]
                .astype(str)
                .isin(selected)
            ]

    months = sorted(
        df["月份"].unique().tolist()
    )

    selected_months = st.multiselect(
        "对比月份",
        months,
        default=months
    )

    sku_options = sorted(
        df["SKU"].unique().tolist()
    )

    selected_skus = st.multiselect(
        "选择 SKU（留空为全部）",
        sku_options,
        default=[]
    )

if not selected_months:
    st.warning("请至少选择一个月份。")
    st.stop()

last_data_date = df["订单日"].max()

df = df[
    df["月份"].isin(selected_months)
].copy()

if selected_skus:
    df = df[
        df["SKU"].isin(selected_skus)
    ].copy()

if df.empty:
    st.warning("筛选后没有销售记录。")
    st.stop()


# ==========================================
# 5. 月度统计天数
# ==========================================

def get_month_days(month):

    year, mon = map(
        int,
        month.split("-")
    )

    full_days = calendar.monthrange(
        year,
        mon
    )[1]

    if (
        pd.notna(last_data_date)
        and month == last_data_date.strftime("%Y-%m")
    ):
        return min(
            last_data_date.day,
            full_days
        )

    return full_days


month_days = {
    month: get_month_days(month)
    for month in months
}


# ==========================================
# 6. SKU 月度数据汇总
# ==========================================

sku_names = (
    df.sort_values("Order Date")
    .groupby("SKU")["产品名称"]
    .last()
)

summary = (
    df.groupby(
        ["SKU", "月份"],
        as_index=False
    )
    .agg(
        月销量=("Quantity", "sum"),
        销售额=("Total Cost", "sum"),
        动销天数=(
            "订单日",
            lambda x: x[
                df.loc[x.index, "Quantity"] > 0
            ].nunique()
        ),
        订单数=(
            "PO Number",
            "nunique"
        ) if "PO Number" in df.columns
        else ("SKU", "size")
    )
)

summary["产品名称"] = (
    summary["SKU"].map(sku_names)
)

# 补齐没有销量的月份
sku_list = sorted(
    df["SKU"].unique()
)

grid = pd.MultiIndex.from_product(
    [
        sku_list,
        sorted(selected_months)
    ],
    names=["SKU", "月份"]
).to_frame(index=False)

summary = grid.merge(
    summary,
    on=["SKU", "月份"],
    how="left"
)

for col in [
    "月销量",
    "销售额",
    "动销天数",
    "订单数"
]:
    summary[col] = (
        summary[col].fillna(0)
    )

summary["产品名称"] = (
    summary["SKU"]
    .map(sku_names)
    .fillna("")
)

summary["统计天数"] = (
    summary["月份"].map(month_days)
)

summary["日均销量"] = (
    summary["月销量"]
    / summary["统计天数"].clip(lower=1)
)

summary["动销日均销量"] = (
    summary["月销量"]
    / summary["动销天数"].replace(
        0,
        float("nan")
    )
)

summary["动销率(%)"] = (
    summary["动销天数"]
    / summary["统计天数"].clip(lower=1)
    * 100
)

summary = summary.sort_values(
    ["SKU", "月份"]
).reset_index(drop=True)


# ==========================================
# 7. 环比增长计算
# ==========================================

summary["上月"] = (
    pd.PeriodIndex(
        summary["月份"],
        freq="M"
    ) - 1
).astype(str)

previous = summary[
    [
        "SKU",
        "月份",
        "月销量",
        "日均销量",
        "销售额"
    ]
].rename(
    columns={
        "月份": "上月",
        "月销量": "上月销量",
        "日均销量": "上月日均",
        "销售额": "上月销售额"
    }
)

summary = summary.merge(
    previous,
    on=["SKU", "上月"],
    how="left"
)

compare_fields = [
    (
        "月销量",
        "上月销量",
        "销量环比(%)"
    ),
    (
        "日均销量",
        "上月日均",
        "日销环比(%)"
    ),
    (
        "销售额",
        "上月销售额",
        "销售额环比(%)"
    )
]

for current, previous_col, result in compare_fields:

    summary[result] = (
        (
            summary[current]
            / summary[previous_col]
            - 1
        )
        .where(
            summary[previous_col] > 0
        )
        * 100
    )


# ==========================================
# 8. 月度整体表现
# ==========================================

st.divider()
st.header("一、月度整体表现")

monthly = (
    summary.groupby(
        "月份",
        as_index=False
    )
    .agg(
        总销量=("月销量", "sum"),
        总销售额=("销售额", "sum"),
        动销SKU数=(
            "月销量",
            lambda x: int((x > 0).sum())
        )
    )
)

monthly["统计天数"] = (
    monthly["月份"].map(month_days)
)

monthly["日均销量"] = (
    monthly["总销量"]
    / monthly["统计天数"].clip(lower=1)
)

monthly = monthly.sort_values("月份")

latest = monthly.iloc[-1]

c1, c2, c3, c4 = st.columns(4)

c1.metric(
    "最近所选月份",
    str(latest["月份"])
)

c2.metric(
    "当月总销量",
    f'{latest["总销量"]:,.0f}'
)

c3.metric(
    "当月日均销量",
    f'{latest["日均销量"]:,.2f} 件/天'
)

c4.metric(
    "当月动销 SKU 数",
    f'{latest["动销SKU数"]:,.0f}'
)

left, right = st.columns(2)

with left:

    fig = px.bar(
        monthly,
        x="月份",
        y="总销量",
        text_auto=".0f",
        title="各月总销量对比"
    )

    st.plotly_chart(
        fig,
        use_container_width=True
    )

with right:

    fig = px.line(
        monthly,
        x="月份",
        y="日均销量",
        markers=True,
        title="各月日均销量趋势"
    )

    st.plotly_chart(
        fig,
        use_container_width=True
    )


# ==========================================
# 9. SKU 各月份横向对比
# ==========================================

st.divider()
st.header("二、SKU 各月份动销对比")

metric = st.radio(
    "选择对比指标",
    [
        "月销量",
        "日均销量",
        "动销天数",
        "动销率(%)",
        "销售额",
        "销量环比(%)",
        "日销环比(%)"
    ],
    horizontal=True
)

top_n = st.slider(
    "显示销量排名前 N 的 SKU",
    min_value=5,
    max_value=50,
    value=15,
    step=5
)

top_skus = (
    summary.groupby("SKU")["月销量"]
    .sum()
    .sort_values(ascending=False)
    .head(top_n)
    .index
)

chart_df = summary[
    summary["SKU"].isin(top_skus)
]

fig = px.bar(
    chart_df,
    x="SKU",
    y=metric,
    color="月份",
    barmode="group",
    title=f"SKU 各月{metric}对比"
)

fig.update_layout(
    xaxis_tickangle=-40
)

st.plotly_chart(
    fig,
    use_container_width=True
)


# ==========================================
# 10. SKU × 月份对比矩阵
# ==========================================

st.subheader("SKU × 月份数据对比表")

pivot = summary.pivot(
    index="SKU",
    columns="月份",
    values=metric
)

st.dataframe(
    pivot.style.format(
        "{:,.2f}",
        na_rep="—"
    ),
    use_container_width=True
)


# ==========================================
# 11. 单 SKU 月度销售趋势
# ==========================================

st.divider()
st.header("三、单个 SKU 月度趋势")

focus_sku = st.selectbox(
    "选择要分析的 SKU",
    sku_list
)

focus = summary[
    summary["SKU"] == focus_sku
].sort_values("月份")

left, right = st.columns(2)

with left:

    fig = px.bar(
        focus,
        x="月份",
        y="月销量",
        text_auto=".0f",
        title=f"{focus_sku} 月销量"
    )

    st.plotly_chart(
        fig,
        use_container_width=True
    )

with right:

    fig = px.line(
        focus,
        x="月份",
        y="日均销量",
        markers=True,
        title=f"{focus_sku} 日均销量"
    )

    st.plotly_chart(
        fig,
        use_container_width=True
    )


# ==========================================
# 12. SKU 月度明细表
# ==========================================

st.divider()
st.header("四、SKU 月度销售明细")

display_columns = [
    "SKU",
    "产品名称",
    "月份",
    "月销量",
    "日均销量",
    "动销天数",
    "动销日均销量",
    "动销率(%)",
    "订单数",
    "销售额",
    "销量环比(%)",
    "日销环比(%)",
    "销售额环比(%)"
]

st.dataframe(
    summary[display_columns],
    use_container_width=True,
    hide_index=True
)


# ==========================================
# 13. 导出 CSV
# ==========================================

csv_data = (
    summary[display_columns]
    .to_csv(
        index=False,
        encoding="utf-8-sig"
    )
    .encode("utf-8-sig")
)

st.download_button(
    label="📥 导出 SKU 月度明细 CSV",
    data=csv_data,
    file_name="SKU_月度动销对比.csv",
    mime="text/csv"
)

st.caption(
    "统计口径：日均销量 = 月销量 ÷ 统计天数；"
    "动销日均销量 = 月销量 ÷ 动销天数；"
    "动销率 = 动销天数 ÷ 统计天数。"
    "最后一个数据月按数据截止日期计算，"
    "历史月份按完整自然月计算。"
)
