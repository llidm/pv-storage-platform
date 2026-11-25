import cvxpy as cp
import numpy as np

def run_optimization(pv_forecast, load_forecast, price_buy, params):
    T = 24
    p_grid = cp.Variable(T, nonneg=True)
    p_pv_self = cp.Variable(T, nonneg=True)
    p_pv_export = cp.Variable(T, nonneg=True)
    p_ch = cp.Variable(T, nonneg=True)
    p_dis = cp.Variable(T, nonneg=True)
    soc = cp.Variable(T+1, nonneg=True)
    
    # 新增：最高购电功率（用于计算需量电费）
    p_peak = cp.Variable(nonneg=True) 

    E_cap = params["storage_kwh"]
    p_ch_max = params["p_ch_max"]
    p_dis_max = params["p_dis_max"]
    eta_ch, eta_dis = 0.95, 0.95
    soc_min, soc_max = 0.1 * E_cap, 0.9 * E_cap
    soc_init = 0.2 * E_cap
    emission_factor = params["emission_factor"]
    carbon_weight = params["carbon_weight"]

    constraints = [soc[0] == soc_init]
    
    for t in range(T):
        constraints.append(p_pv_self[t] + p_dis[t] + p_grid[t] == load_forecast[t] + p_ch[t] + p_pv_export[t])
        constraints.append(p_pv_self[t] + p_pv_export[t] <= pv_forecast[t])
        constraints.append(p_ch[t] <= p_ch_max)
        constraints.append(p_dis[t] <= p_dis_max)
        constraints.append(soc[t+1] == soc[t] + eta_ch * p_ch[t] - p_dis[t] / eta_dis)
        constraints.append(soc[t+1] >= soc_min)
        constraints.append(soc[t+1] <= soc_max)
        
        # 新增约束：记录全天最大的购电功率
        constraints.append(p_grid[t] <= p_peak)

    constraints.append(soc[T] == soc_init)

    # 新增成本项：
    # 1. 电池衰减成本：频繁充放电会花钱（假设充放1度电损耗0.05元）
    degradation_cost = cp.sum(p_ch + p_dis) * 0.05
    # 2. 需量电费：最大购电功率 * 基础电价（假设基础容量费为 30元/kW）
    demand_charge = p_peak * 30 
    
    # 购电成本
    energy_cost = cp.sum(cp.multiply(price_buy, p_grid))
    
    # 碳排放
    carbon = cp.sum(p_grid) * emission_factor

    # 目标函数：经济成本（含衰减+需量） + 降碳惩罚
    w = carbon_weight
    objective = cp.Minimize(w * carbon * 0.1 + (1 - w) * (energy_cost + degradation_cost + demand_charge))
    
    prob = cp.Problem(objective, constraints)
    prob.solve(solver=cp.CLARABEL)

    if prob.status == cp.OPTIMAL:
        return {
            "grid_buy": p_grid.value,
            "charge": p_ch.value,
            "discharge": p_dis.value,
            "soc": soc.value[1:],
            "pv_self": p_pv_self.value,
            "peak_demand": p_peak.value  # 把最高需量传回前端
        }
    else:
        return None
