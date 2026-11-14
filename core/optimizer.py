import cvxpy as cp
import numpy as np


def run_optimization(pv_forecast, load_forecast, price_buy, params):
    """
    核心优化调度内核
    pv_forecast: 24h光伏预测 (kW)
    load_forecast: 24h负荷预测 (kW)
    price_buy: 24h购电电价 (元/kWh)
    params: 包含储能容量、充放电功率、排放因子等的字典
    """
    T = 24

    # 1. 定义决策变量
    p_grid = cp.Variable(T, nonneg=True)  # 逐时购电量 (kW)
    p_pv_self = cp.Variable(T, nonneg=True)  # 光伏自用电量
    p_pv_export = cp.Variable(T, nonneg=True)  # 光伏上网电量
    p_ch = cp.Variable(T, nonneg=True)  # 储能充电功率
    p_dis = cp.Variable(T, nonneg=True)  # 储能放电功率
    soc = cp.Variable(T + 1, nonneg=True)  # 荷电状态

    # 参数提取
    E_cap = params["storage_kwh"]
    p_ch_max = params["p_ch_max"]
    p_dis_max = params["p_dis_max"]
    eta_ch = 0.95  # 充电效率
    eta_dis = 0.95  # 放电效率
    soc_min = 0.1 * E_cap
    soc_max = 0.9 * E_cap
    soc_init = 0.2 * E_cap
    carbon_weight = params["carbon_weight"]
    emission_factor = params["emission_factor"]

    constraints = []
    constraints.append(soc[0] == soc_init)

    for t in range(T):
        # 功率平衡：光伏自用 + 放电 + 购电 = 负荷 + 充电 + 上网
        constraints.append(
            p_pv_self[t] + p_dis[t] + p_grid[t] == load_forecast[t] + p_ch[t] + p_pv_export[t]
        )
        # 光伏出力限制
        constraints.append(p_pv_self[t] + p_pv_export[t] <= pv_forecast[t])

        # 储能功率限制
        constraints.append(p_ch[t] <= p_ch_max)
        constraints.append(p_dis[t] <= p_dis_max)

        # SOC 动态与上下限
        constraints.append(soc[t + 1] == soc[t] + eta_ch * p_ch[t] - p_dis[t] / eta_dis)
        constraints.append(soc[t + 1] >= soc_min)
        constraints.append(soc[t + 1] <= soc_max)

    # 日末 SOC 回归初值，保证可持续
    constraints.append(soc[T] == soc_init)

    # 2. 目标函数：兼顾经济与降碳
    # 成本 = 购电费用 (上网收益暂忽略)
    cost = cp.sum(cp.multiply(price_buy, p_grid))
    # 碳排放 = 购电量 * 排放因子
    carbon = cp.sum(p_grid) * emission_factor

    # 因为成本(元)和碳(kg)量级不同，用权重做简单平衡
    # w=1 偏向降碳，w=0 偏向纯经济
    w = carbon_weight
    objective = cp.Minimize(w * carbon * 0.1 + (1 - w) * cost)

    # 3. 求解
    prob = cp.Problem(objective, constraints)
    prob.solve(solver=cp.CLARABEL)  # 使用默认的高效求解器

    if prob.status == cp.OPTIMAL:
        return {
            "grid_buy": p_grid.value,
            "charge": p_ch.value,
            "discharge": p_dis.value,
            "soc": soc.value[1:],
            "pv_self": p_pv_self.value
        }
    else:
        return None