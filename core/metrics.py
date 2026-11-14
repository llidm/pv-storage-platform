import numpy_financial as npf


def compute_metrics(dispatch, forecast, prices, params, baseline_grid_buy):
    """
    计算节能降碳与经济指标
    """
    annual_factor = 365

    # 1. 节能减排指标
    pv_self_use = dispatch["pv_self"].sum()
    pv_total = forecast.sum()
    self_use_rate = pv_self_use / pv_total if pv_total > 0 else 0

    grid_buy_daily = dispatch["grid_buy"].sum()
    baseline_daily = baseline_grid_buy.sum()

    # 年减少外购电量 (kWh)
    annual_grid_reduction = max(0, (baseline_daily - grid_buy_daily)) * annual_factor
    # 年CO2减排 (吨)
    co2_reduction = annual_grid_reduction * params["emission_factor"] / 1000

    # 2. 经济指标
    # 节约的电费 (基线购电费 - 优化后购电费)
    daily_cost = (dispatch["grid_buy"] * prices).sum()
    baseline_cost = (baseline_grid_buy * prices).sum()
    annual_saving = max(0, (baseline_cost - daily_cost)) * annual_factor

    # 假设储能投资 1000元/kWh, 寿命 10年
    capex = params["storage_kwh"] * 1000
    opex = capex * 0.02
    net_cashflow = annual_saving - opex

    # 静态回收期
    payback = capex / net_cashflow if net_cashflow > 0 else 999

    # NPV (假设折现率 6%)
    npv = npf.npv(0.06, [-capex] + [net_cashflow] * 10)

    return {
        "self_use_rate": self_use_rate,
        "annual_grid_reduction": annual_grid_reduction,
        "co2_reduction": co2_reduction,
        "annual_saving": annual_saving,
        "payback": payback,
        "npv": npv
    }