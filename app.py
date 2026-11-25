import streamlit as st
import streamlit.components.v1 as components
import numpy as np
import plotly.graph_objects as go
import plotly.io as pio
import pandas as pd
import numpy_financial as npf
from core.optimizer import run_optimization
from core.metrics import compute_metrics
from io import BytesIO


st.set_page_config(
    page_title="光储荷协同优化决策平台",
    layout="wide",
    page_icon="🌿",
    initial_sidebar_state="locked",  # 锁定侧边栏，隐藏折叠按钮
    menu_items=None
)

st.markdown("""
<style>
    /* 隐藏默认菜单和右上角工具栏 */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    [data-testid="stToolbar"] {display: none !important;}
    header[data-testid="stHeader"] {
        background-color: transparent !important;
        height: 3rem !important;
    }
    /* ======= 页面美化 ======= */
    .main-title {
        text-align: center;
        background: linear-gradient(90deg, #1b5e20, #4caf50, #2e7d32);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 900;
        font-size: 2.8rem;
        margin-bottom: 5px;
        letter-spacing: 1px;
    }
    .sub-title {
        text-align: center;
        color: #558b2f;
        font-size: 1.05rem;
        margin-bottom: 30px;
        font-weight: 500;
    }
    /* 指标卡片 */
    div[data-testid="stMetric"] {
        background-color: #ffffff !important;
        padding: 20px !important;
        border-radius: 12px !important;
        box-shadow: 0 4px 15px rgba(46, 125, 50, 0.08) !important;
        border-top: 4px solid #4caf50 !important;
        transition: all 0.3s ease !important;
    }
    div[data-testid="stMetric"]:hover {
        transform: translateY(-5px);
        box-shadow: 0 8px 25px rgba(46, 125, 50, 0.2) !important;
    }
    div[data-testid="stMetric"] label {
        color: #555555 !important;
        font-size: 1rem !important;
        font-weight: bold !important;
    }
    div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
        color: #2e7d32 !important;
        font-weight: 900 !important;
        font-size: 2.1rem !important;
    }
    /* 侧边栏面板美化 */
    [data-testid="stSidebar"] {
        background-color: #ffffff !important;
        border-right: 1px solid #e0e0e0;
        box-shadow: 2px 0 10px rgba(0,0,0,0.02);
    }
    /* 下载按钮美化 */
    .stDownloadButton button {
        background: linear-gradient(135deg, #43a047, #2e7d32) !important;
        color: white !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: bold !important;
        font-size: 1.05rem !important;
        padding: 12px 24px !important;
        transition: all 0.3s ease !important;
        box-shadow: 0 4px 10px rgba(46, 125, 50, 0.3) !important;
    }
    .stDownloadButton button:hover {
        transform: scale(1.02);
        box-shadow: 0 6px 15px rgba(46, 125, 50, 0.5) !important;
    }
    /* ======= Radio 伪装顶部导航栏 ======= */
    [data-testid="stRadio"] label > div:first-child {
        display: none !important;
    }
    [data-testid="stRadio"] {
        display: flex !important;
        justify-content: center !important;
        width: 100% !important;
        margin-top: 20px !important;
    }
    div[role="radiogroup"] {
        display: flex !important;
        justify-content: center !important;
        gap: 50px !important;
        border-bottom: 2px solid #e0e0e0 !important;
        padding-bottom: 15px !important;
        width: 100% !important;
    }
    div[role="radiogroup"] > label {
        font-size: 1.5rem !important;
        font-weight: 900 !important;
        color: #757575 !important;
        cursor: pointer;
        margin: 0 !important;
        padding: 0 !important;
    }
    div[role="radiogroup"] > label:hover {
        color: #2e7d32 !important;
    }
    div[role="radiogroup"] > label[data-checked="true"] {
        color: #2e7d32 !important;
        border-bottom: 4px solid #43a047 !important;
        padding-bottom: 11px !important;
    }
</style>
""", unsafe_allow_html=True)
st.markdown('<div class="main-title">🌿 光储荷协同智能调度系统</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Photovoltaic-Storage-Load Synergistic Optimization Platform</div>',
            unsafe_allow_html=True)

with st.sidebar:
    st.markdown("### 🛠 参数配置中心")
    st.markdown("---")

    st.markdown("**📂 时序数据上传（CSV）**")
    st.caption("格式：hour, pv, load，共24行；不上传则使用模拟数据")

    template_df = pd.DataFrame({
        "hour": list(range(24)),
        "pv": [0,0,0,0,0,0,10,40,120,260,420,380,320,240,140,60,20,0,0,0,0,0,0,0],
        "load": [200,195,190,192,198,205,220,245,270,300,340,360,350,330,310,290,270,250,240,230,220,215,210,205]
    })
    buf = BytesIO()
    template_df.to_csv(buf, index=False, encoding="utf-8-sig")
    buf.seek(0)
    st.download_button(
        label="📥 下载CSV模板",
        data=buf,
        file_name="光储荷时序模板.csv",
        mime="text/csv"
    )

    uploaded_file = st.file_uploader("上传光伏负荷时序表", type="csv")
    use_real_data = False
    pv_forecast = None
    load_forecast = None
    if uploaded_file is not None:
        try:
            df_upload = pd.read_csv(uploaded_file)

            need_cols = {"hour", "pv", "load"}
            if not need_cols.issubset(df_upload.columns):
                st.error("❌ CSV缺少必要列！必须包含 hour、pv、load")
            elif len(df_upload) != 24:
                st.error("❌ 数据行数不对，必须是24个时刻（0~23点）")
            else:
                df_upload = df_upload.sort_values("hour").reset_index(drop=True)
                pv_forecast = df_upload["pv"].values.astype(float)
                load_forecast = df_upload["load"].values.astype(float)

                if np.any(pv_forecast < 0) or np.any(load_forecast < 0):
                    st.error("❌ pv、load不能为负数！")
                else:
                    st.success("✅ 数据读取成功！使用上传真实时序数据")
                    use_real_data = True
        except Exception as e:
            st.error(f"文件读取失败：{str(e)}")
    st.markdown("**🔆 光伏发电**")
    pv_capacity = st.number_input("光伏装机容量 (kW)", min_value=10, max_value=5000, value=500, step=10,
                                  disabled=use_real_data)
    pv_efficiency = st.slider("系统转换效率", 0.6, 1.0, 0.85, 0.01, disabled=use_real_data)
    st.markdown("**🔋 储能配置**")
    storage_kwh = st.number_input("储能系统容量 (kWh)", min_value=0, max_value=2000, value=200, step=10)
    p_ch_max = st.number_input("最大充电功率 (kW)", min_value=0, max_value=500, value=100, step=10)
    p_dis_max = st.number_input("最大放电功率 (kW)", min_value=0, max_value=500, value=100, step=10)
    with st.expander("⚙️ 外部环境与电价", expanded=False):
        price_peak = st.number_input("峰段电价 (元/kWh)", value=1.2, step=0.05)
        price_flat = st.number_input("平段电价 (元/kWh)", value=0.7, step=0.05)
        price_valley = st.number_input("谷段电价 (元/kWh)", value=0.3, step=0.05)
        # 修复：增加 format="%.3f"，±按钮正常工作
        emission_factor = st.number_input("电网排放因子 (tCO₂/MWh)", value=0.785, step=0.001, format="%.3f")
    st.markdown("---")
    st.markdown("**🎯 优化目标权重**")
    carbon_weight = st.slider("降碳权重 (0=纯经济, 1=纯降碳)", 0.0, 1.0, 0.0, 0.05)

T = 24
hours = np.arange(T)

if not use_real_data:
    np.random.seed(42)
    noise = np.random.normal(0, 0.05, T)
    irradiance = 1000 * np.exp(-((hours - 12.5) ** 2) / (2 * 3.0 ** 2)) * (1 + noise)
    irradiance = np.clip(irradiance, 0, 1000)
    pv_forecast = pv_capacity * (irradiance / 1000.0) * pv_efficiency
    load_base = 0.55 * pv_capacity
    load_noise = np.random.normal(0, 0.02, T)
    load_forecast = load_base * (1 + 0.3 * np.sin((hours - 8) * np.pi / 12)) * (1 + load_noise)


price_buy = np.ones(T) * price_flat
price_buy[0:7] = price_valley      # 0~6 深夜谷段
price_buy[11:14] = price_flat      # 中午光伏大发，平段
price_buy[17:22] = price_peak       # 17~21 晚高峰，电价最贵，储能放电

params = {
    "storage_kwh": storage_kwh, "p_ch_max": p_ch_max, "p_dis_max": p_dis_max,
    "carbon_weight": carbon_weight, "emission_factor": emission_factor
}
baseline_grid_buy = np.maximum(0, load_forecast - pv_forecast)
res = run_optimization(pv_forecast, load_forecast, price_buy, params)
metrics = compute_metrics(res, pv_forecast, price_buy, params, baseline_grid_buy)

pio.templates.default = "plotly_white"
layout_theme = dict(
    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
    font=dict(color='#424242', family="sans-serif"),
    xaxis=dict(showgrid=True, gridcolor='#f0f0f0', zeroline=False),
    yaxis=dict(showgrid=True, gridcolor='#f0f0f0', zeroline=False),
    hovermode="x unified",
    margin=dict(l=20, r=20, t=40, b=20),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5)
)

fig1 = go.Figure()
fig1.add_trace(go.Scatter(x=hours, y=load_forecast, name="园区负荷", mode="lines",
                          line=dict(color='#2196f3', width=3, shape='spline')))
fig1.add_trace(go.Scatter(x=hours, y=pv_forecast, name="光伏出力", mode="lines", fill='tozeroy',
                          line=dict(color='#ff9800', width=3, shape='spline'), fillcolor='rgba(255, 152, 0, 0.15)'))
fig1.update_layout(height=340, **layout_theme)

fig2 = go.Figure()
if res is not None:
    fig2.add_trace(go.Bar(x=hours, y=res["charge"], name="储能充电 (消纳)", marker_color='#66bb6a', opacity=0.85))
    fig2.add_trace(go.Bar(x=hours, y=-res["discharge"], name="储能放电 (顶峰)", marker_color='#ef5350', opacity=0.85))
    fig2.add_trace(go.Scatter(x=hours, y=res["soc"], name="荷电状态 (SOC)", mode="lines+markers", yaxis="y2",
                              line=dict(color='#2e7d32', width=4)))
    fig2.update_layout(
        yaxis2=dict(title="SOC (kWh)", overlaying='y', side='right', showgrid=False, color='#2e7d32'),
        height=380, barmode='relative', **layout_theme
    )

nav_selection = st.radio(
    "导航菜单",
    ["📊 核心调度与效益", "🔍 多方案深度对比", "📉 敏感性边界分析", "📄 智能评估报告导出"],
    horizontal=True,
    label_visibility="collapsed"
)

if nav_selection == "📊 核心调度与效益":
    st.markdown("### 📌 年度综合效益核算")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("⚡ 光伏自用率", f"{metrics['self_use_rate'] * 100:.1f}%")
    m2.metric("🌱 年减碳量", f"{metrics['co2_reduction']:.1f} 吨")
    m3.metric("💰 年电费节省", f"{metrics['annual_saving'] / 10000:.2f} 万元")
    m4.metric("⏳ 静态回收期", f"{metrics['payback']:.1f} 年")
    st.markdown("<br>", unsafe_allow_html=True)
    col_chart1, col_chart2 = st.columns(2)
    with col_chart1:
        st.markdown("<h4 style='text-align: center; color: #2e7d32; margin-bottom: 0;'>📈 时序预测曲线 (24h)</h4>",
                    unsafe_allow_html=True)
        st.plotly_chart(fig1, use_container_width=True)
    with col_chart2:
        st.markdown("<h4 style='text-align: center; color: #2e7d32; margin-bottom: 0;'>⚡ 逐时智能调度策略</h4>",
                    unsafe_allow_html=True)
        st.plotly_chart(fig2, use_container_width=True)
elif nav_selection == "🔍 多方案深度对比":
    st.markdown("### 🔍 多配置方案测算对比")
    st.info("系统自动测算 100kWh / 200kWh / 300kWh 三种储能配置的经济与减排效益。")
    compare_results = []
    for cap in [100, 200, 300]:
        temp_params = params.copy()
        temp_params["storage_kwh"] = cap
        res_temp = run_optimization(pv_forecast, load_forecast, price_buy, temp_params)
        if res_temp is not None:
            m_temp = compute_metrics(res_temp, pv_forecast, price_buy, temp_params, baseline_grid_buy)
            compare_results.append({
                "储能容量": f"{cap} kWh",
                "光伏自用率": f"{m_temp['self_use_rate'] * 100:.1f}%",
                "年减碳量": f"{m_temp['co2_reduction']:.1f} 吨",
                "年电费节省": f"{m_temp['annual_saving'] / 10000:.2f} 万元",
                "静态回收期": f"{m_temp['payback']:.1f} 年"
            })
    df_compare = pd.DataFrame(compare_results)
    st.dataframe(df_compare, use_container_width=True, hide_index=True)
    fig_compare = go.Figure()
    fig_compare.add_trace(
        go.Bar(x=df_compare["储能容量"], y=[float(x.split()[0]) for x in df_compare["年减碳量"]], name="年减碳量 (吨)",
               marker_color='#43a047'))
    fig_compare.add_trace(
        go.Scatter(x=df_compare["储能容量"], y=[float(x.split()[0]) for x in df_compare["静态回收期"]],
                   name="回收期 (年)", mode='lines+markers+text', text=df_compare["静态回收期"],
                   textposition="top center", yaxis="y2", marker_color='#ff7043', line=dict(width=3)))
    fig_compare.update_layout(**{
        **layout_theme,
        "title": "不同储能配置的减碳与回收期对比",
        "yaxis": dict(title="年减碳量 (吨)", showgrid=True, gridcolor='#f0f0f0', zeroline=False),
        "yaxis2": dict(title="回收期 (年)", overlaying='y', side='right', showgrid=False),
        "height": 450,
        "margin": dict(t=60)
    })
    st.plotly_chart(fig_compare, use_container_width=True)
elif nav_selection == "📉 敏感性边界分析":
    st.markdown("### 📉 电价波动敏感性分析")
    st.info("系统测算当电价在 ±20% 范围波动时，项目经济性的边界与抗风险能力。")
    price_factors = [0.8, 0.9, 1.0, 1.1, 1.2]
    sensitivity_results = []
    for factor in price_factors:
        price_buy_sens = price_buy * factor
        baseline_cost_sens = (baseline_grid_buy * price_buy_sens).sum()
        res_sens = run_optimization(pv_forecast, load_forecast, price_buy_sens, params)
        if res_sens is not None:
            daily_cost = (res_sens["grid_buy"] * price_buy_sens).sum()
            annual_saving = max(0, (baseline_cost_sens - daily_cost)) * 365
            capex = params["storage_kwh"] * 1000
            net_cashflow = annual_saving - capex * 0.02
            payback = capex / net_cashflow if net_cashflow > 0 else 999
            sensitivity_results.append({
                "电价情景": f"{int((factor - 1) * 100)}%" if factor != 1.0 else "基准",
                "年电费节省 (万元)": annual_saving / 10000,
                "静态回收期 (年)": payback
            })
    df_sens = pd.DataFrame(sensitivity_results)
    fig_sens = go.Figure()
    fig_sens.add_trace(
        go.Bar(x=df_sens["电价情景"], y=df_sens["年电费节省 (万元)"], name="年电费节省 (万元)", marker_color='#81c784',
               yaxis="y"))
    fig_sens.add_trace(
        go.Scatter(x=df_sens["电价情景"], y=df_sens["静态回收期 (年)"], name="回收期 (年)", mode='lines+markers+text',
                   text=[f"{x:.1f}年" for x in df_sens["静态回收期 (年)"]], textposition="top center",
                   marker_color='#ef5350', line=dict(width=3), yaxis="y2"))
    fig_sens.update_layout(**{
        **layout_theme,
        "title": "电价波动对经济性的敏感性分析",
        "yaxis": dict(title="年电费节省 (万元)", showgrid=True, gridcolor='#f0f0f0', zeroline=False),
        "yaxis2": dict(title="静态回收期 (年)", overlaying='y', side='right', showgrid=False),
        "height": 450,
        "margin": dict(t=60)
    })
    st.plotly_chart(fig_sens, use_container_width=True)
elif nav_selection == "📄 智能评估报告导出":
    st.markdown("### 📄 生成智能评估报告")
    st.write("基于当前系统参数，自动生成排版精美的专业报告。")
    report_html = f"""
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: 'Microsoft YaHei', sans-serif; background-color: #ffffff; color: #333333; padding: 40px; line-height: 1.6; }}
            .header {{ border-top: 8px solid #2e7d32; padding-top: 20px; margin-bottom: 30px; }}
            h1 {{ color: #1b5e20; text-align: center; margin-top: 0; }}
            h3 {{ color: #2e7d32; border-bottom: 2px solid #c8e6c9; padding-bottom: 8px; margin-top: 30px; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 15px; }}
            th, td {{ border: 1px solid #e0e0e0; padding: 12px; text-align: left; }}
            th {{ background-color: #f1f8e9; color: #2e7d32; font-weight: bold; }}
            tr:nth-child(even) {{ background-color: #fafafa; }}
            .highlight {{ color: #2e7d32; font-weight: bold; font-size: 1.2em; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🌿 光储荷协同优化调度方案评估报告</h1>
            <p style="text-align: center; color: #757575; font-size: 14px;">—— 基于多目标优化与智能测算生成 ——</p>
        </div>
        <h3>01. 系统基础参数</h3>
        <table>
            <tr><th>光伏装机容量</th><td>{pv_capacity} kW</td><th>储能配置容量</th><td>{storage_kwh} kWh</td></tr>
            <tr><th>降碳权重设定</th><td>{carbon_weight}</td><th>电网排放因子</th><td>{emission_factor:.3f} tCO₂/MWh</td></tr>
            <tr><th>数据源</th><td>{'上传自定义时序CSV' if use_real_data else '内置模拟时序数据'}</td><td></td><td></td></tr>
        </table>
        <h3>02. 节能减排核心指标 (年度)</h3>
        <table>
            <tr><th>光伏自用率</th><td class="highlight">{metrics['self_use_rate'] * 100:.1f}%</td></tr>
            <tr><th>年减少外购电量</th><td>{metrics['annual_grid_reduction']:.0f} kWh</td></tr>
            <tr><th>年 CO₂ 减排量</th><td class="highlight">{metrics['co2_reduction']:.1f} 吨</td></tr>
        </table>
        <h3>03. 经济效益指标 (年度)</h3>
        <table>
            <tr><th>年电费节约</th><td class="highlight">{metrics['annual_saving'] / 10000:.2f} 万元</td></tr>
            <tr><th>静态投资回收期</th><td>{metrics['payback']:.1f} 年</td></tr>
            <tr><th>10年净现值 (NPV)</th><td>{metrics['npv'] / 10000:.2f} 万元</td></tr>
        </table>
        <p style="margin-top: 50px; text-align: center; color: #9e9e9e; font-size: 12px; border-top: 1px solid #eeeeee; padding-top: 20px;">
            Generated by Photovoltaic-Storage-Load Optimization Platform
        </p>
    </body>
    </html>
    """
    col_btn, col_tip = st.columns([1, 2])
    with col_btn:
        st.download_button(
            label="📥 下载评估报告",
            data=report_html.encode('utf-8'),
            file_name="optimization_report.html",
            mime="text/html",
            use_container_width=True
        )
    with col_tip:
        st.info("💡 下载后双击文件即可在浏览器中打开，按 `Ctrl+P` 可直接另存为 PDF。")
    st.markdown("<br>### 👀 报告在线预览", unsafe_allow_html=True)
    components.html(report_html, height=500, scrolling=True)