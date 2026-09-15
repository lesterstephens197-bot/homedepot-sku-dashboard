```python
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import calendar

# =========================================================================
# 页面基础配置
# =========================================================================

st.set_page_config(
    page_title="Home Depot 销售与广告综合决策看板",
    page_icon="📊",
    layout="wide"
)

# =========================================================================
# 侧边栏：顶部模块导航
# =========================================================================

st.sidebar.title("📌 功能看板导航")

module = st.sidebar.radio(
    "请选择分析模块",
    [
        "📊 销售与品类管理决策看板",
        "📈 SKU 7天/15天销量变化看板",
        "📅 月度多维度对比与趋势看板",
        "📢 SPA 广告绩效诊断与运营看板",
        "🎯 下月销售目标与 SKU 销量拆解看板"
    ]
)

st.sidebar.markdown("---")


# =========================================================================
# 辅助函数：读取销售文件
# =========================================================================

def load_sales_file(uploaded_file):

    try:
        if uploaded_file.name.lower().endswith(".csv"):
            return pd.read_csv(uploaded_file)
        else:
            return pd.read_excel(uploaded_file)

    except Exception as e:
        st.error(f"读取文件失败，请检查文件格式：{e}")
        st.stop()


# =========================================================================
# 辅助函数：销售数据清洗
# =========================================================================

def process_sales_data(df_sales):

    df_sales = df_sales.copy()

    df_sales.columns = (
        df_sales.columns
        .astype(str)
        .str.strip()
    )

    # 日期
    date_col = next(
        (
            c for c in df_sales.columns
            if c in [
                "日期",
                "Date",
                "sales_date",
                "Sales Date",
                "Order Date"
            ]
        ),
        None
    )

    # 销量
    sales_col = next(
        (
            c for c in df_sales.columns
            if c in [
                "销量",
                "Units Sold",
                "Units",
                "Quantity",
                "Qty"
            ]
        ),
        None
    )

    # 金额
    cost_col = next(
        (
            c for c in df_sales.columns
            if c in [
                "Total Cost",
                "Cost",
                "金额",
                "总金额",
                "Sales",
                "Revenue",
                "Sales Amount"
            ]
        ),
        None
    )

    # 品类
    category_col = next(
        (
            c for c in df_sales.columns
            if c in [
                "产品名称",
                "Category",
                "品类",
                "品类名称",
                "Product Category"
            ]
        ),
        None
    )

    # 州
    state_col = next(
        (
            c for c in df_sales.columns
            if c in [
                "ShipTo State",
                "State",
                "州",
                "省份"
            ]
        ),
        None
    )

    # SKU
    sku_fields_available = [
        col for col in [
            "产品SKU",
            "SKU",
            "Merchant SKU",
            "Vendor SKU",
            "OMS ID",
            "OMSID"
        ]
        if col in df_sales.columns
    ]

    if not date_col or not sales_col or not sku_fields_available:

        return (
            None,
            "解析失败！未能识别到必需列：日期、销量或产品SKU。"
            f"\n当前列为：{list(df_sales.columns)}"
        )

    # 日期
    df_sales["Clean_Date"] = pd.to_datetime(
        df_sales[date_col],
        errors="coerce"
    )

    df_sales = df_sales.dropna(
        subset=["Clean_Date"]
    )

    # 销量
    df_sales["Clean_Units"] = pd.to_numeric(
        df_sales[sales_col]
        .astype(str)
        .str.replace(",", "", regex=False),
        errors="coerce"
    ).fillna(0)

    # 金额
    if cost_col:

        df_sales["Clean_Cost"] = pd.to_numeric(
            df_sales[cost_col]
            .astype(str)
            .str.replace("$", "", regex=False)
            .str.replace(",", "", regex=False),
            errors="coerce"
        ).fillna(0)

    else:

        df_sales["Clean_Cost"] = 0

    # 品类
    if category_col:

        df_sales["Clean_Category"] = (
            df_sales[category_col]
            .astype(str)
            .str.strip()
            .replace(
                {
                    "nan": "未分类",
                    "None": "未分类",
                    "": "未分类"
                }
            )
        )

    else:

        df_sales["Clean_Category"] = "未分类"

    # 州
    if state_col:

        df_sales["Clean_State"] = (
            df_sales[state_col]
            .astype(str)
            .str.strip()
            .str.upper()
            .replace(
                {
                    "NAN": "未知",
                    "NONE": "未知",
                    "": "未知"
                }
            )
        )

    # SKU
    primary_sku_col = sku_fields_available[0]

    df_sales[primary_sku_col] = (
        df_sales[primary_sku_col]
        .astype(str)
        .str.strip()
    )

    # 月份
    df_sales["YearMonth"] = (
        df_sales["Clean_Date"]
        .dt.to_period("M")
        .astype(str)
    )

    return (df_sales, primary_sku_col), None


# =========================================================================
# 辅助函数：增长率
# =========================================================================

def calc_growth(current, previous):

    if previous > 0:
        return (current - previous) / previous * 100

    elif current > 0:
        return 100.0

    else:
        return 0.0


# =========================================================================
# 模块一：销售与品类管理决策看板
# =========================================================================

if module == "📊 销售与品类管理决策看板":

    st.title("📊 Home Depot 销售绩效与品类管理决策看板")

    st.caption(
        "聚焦管理与运营决策：
```
