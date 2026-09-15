import io
import pandas as pd
import streamlit as st

# 1. 页面基本配置
st.set_page_config(
    page_title="Home Depot 销售绩效与品类管理决策看板",
    page_icon="📊",
    layout="wide",
)

# 2. 侧边栏导航与文件上传
with st.sidebar:
    st.title("📌 功能看板导航")

    analysis_module = st.radio(
        "请选择分析模块",
        [
            "📊 销售与品类管理决策看板",
            "📅 月度多维度对比与趋势看板",
            "📢 SPA 广告绩效诊断与运营看板",
            "🎯 下月销售目标与 SKU 销量拆解看板",
        ],
    )

    st.markdown("---")
    st.header("⚙️ 1. 销售数据上传")

    # 文件上传组件，支持 xlsx, xls, csv
    uploaded_file = st.file_uploader(
        "上传 Home Depot 销售报表 (CSV/Excel)", type=["xlsx", "xls", "csv"]
    )


# 3. 主页面标题与描述
st.title("📊 Home Depot 销售绩效与品类管理决策看板")
st.caption(
    "聚焦管理与运营决策：大盘趋势、帕累托 ABC 爆款诊断、全美物流布局与动销效率分析"
)
st.markdown("---")

# 4. 数据读取与逻辑处理
df = None

if uploaded_file is not None:
    try:
        # 获取上传文件的字节流（支持直接读取，避免 bytes 类型报错）
        file_bytes = uploaded_file.getvalue()

        # 根据文件扩展名判断读取方式
        if uploaded_file.name.endswith(".csv"):
            # 如果是 CSV 文件
            df = pd.read_csv(io.BytesIO(file_bytes))
        else:
            # 如果是 Excel 文件 (.xlsx 或 .xls)
            df = pd.read_excel(io.BytesIO(file_bytes))

        st.success(
            f"✅ 文件【{uploaded_file.name}】读取成功！共 {len(df)} 行，{len(df.columns)} 列数据。"
        )

        # ---------------- 这里编写你的数据分析/展示逻辑 ----------------
        st.subheader("数据预览")
        st.dataframe(df.head(10), use_container_width=True)

        # 示例：如果是“销售与品类管理决策看板”模块
        if analysis_module == "📊 销售与品类管理决策看板":
            st.markdown("### 📈 销售分析看板")
            # 在这里展示图表或指标卡片
            # col1, col2 = st.columns(2)
            # col1.metric("总销售额", f"${df['销售额'].sum():,.2f}")

    except Exception as e:
        # 捕获并提示读取异常
        st.error(f"读取文件失败: {e}")
else:
    # 未上传文件时的友好提示
    st.info("👈 请在左侧边栏上传 Home Depot 销售报表数据文件。")
