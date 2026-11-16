# route_max_range.py
import math
from core_airframe import AIRFRAME_LIBRARY
from core_battery_ocv import get_ocv_curve
from core_battery_resistance import pack_r_ohm_from_params, temp_correct_resistance
from core_physics_engine import (
    run_simulation_step, get_P_mech_target, 
    calculate_required_thrust_with_drag, calculate_vtol_thrust
)

# 일정 속도로 직진할 때 최대 비행 거리 시뮬레이션
def simulate_route_physics(
    batt_params, airframe_name, total_usable_energy_Wh, total_mass_kg,
    v_mps, p_avionics_w, temp_c, altitude_m, v_cutoff_cell=3.0
):
    base_frame = AIRFRAME_LIBRARY[airframe_name]
    is_vtol = (base_frame.get("type") == "vtol")
    
    if is_vtol:
        active_data = base_frame.get("cruise", base_frame)
        active_data["cd"] = base_frame.get("cd", 0.8)
        active_data["frontal_area"] = base_frame.get("frontal_area", 0.15)
        active_data["wing_area"] = base_frame.get("wing_area", 0.5)
        active_data["cl"] = base_frame.get("cl", 0.8)

        target_thrust_N = calculate_vtol_thrust(
            total_mass_kg, v_mps, active_data, temp_c, altitude_m
        )
    else:
        active_data = base_frame
        target_thrust_N = calculate_required_thrust_with_drag(
            total_mass_kg, v_mps, active_data, temp_c, altitude_m
        )

    eff_shaft = active_data.get("eff_shaft", 1.0)
    ns = batt_params.get("ns", 6)
    v_nom = ns * batt_params.get("v_cell_nom", 3.7)
    ocv_curve = get_ocv_curve(batt_params.get("ocv_kind", "neo"))
    V_cutoff_pack = v_cutoff_cell * ns
    dt_s = 10.0
    dt_h = dt_s / 3600.0
    
    # 발열 변수
    sim_temp_c = temp_c
    batt_mass = batt_params.get("mass_ref_kg", 1.0)

    time_s = 0.0
    E_consumed_total_Wh = 0.0
    log_data = [] 
    status_msg = "INIT"
    accumulated_dist_m = 0.0

    P_mech_target = get_P_mech_target(batt_params, airframe_name, target_thrust_N, sim_temp_c, altitude_m, ocv_curve, frame_data=active_data)
    
    if P_mech_target == 0.0:
        return { "status": "FAILED (P_mech calc error)", "time_s": 0.0, "log_data": [], "total_dist_m": 0.0, "percent": 0.0 }
    
    while E_consumed_total_Wh < total_usable_energy_Wh:
        current_soc = 1.0 - (E_consumed_total_Wh / max(total_usable_energy_Wh, 1e-6))
        
        res = run_simulation_step(
            batt_params, airframe_name, eff_shaft, ocv_curve, ns, v_nom, 
            total_mass_kg, p_avionics_w, sim_temp_c, altitude_m, 
            temp_correct_resistance(pack_r_ohm_from_params(batt_params), sim_temp_c),
            ns * ocv_curve(current_soc), 'thrust', P_mech_target=P_mech_target, frame_data=active_data,
            dt_s=dt_s, current_temp_c=sim_temp_c, batt_mass_kg=batt_mass, v_mps=v_mps, ambient_temp_c=temp_c
        )

        sim_temp_c = res["new_temp_c"]
        V_load = res["V_load"]
        actual_thrust = res["actual_thrust"]
        
        # 실제 속도 역산 (Real Speed)
        if target_thrust_N > 1e-3:
            thrust_ratio = actual_thrust / target_thrust_N
            v_real = v_mps * math.sqrt(max(0.0, thrust_ratio)) if thrust_ratio < 0.99 else v_mps
        else:
            v_real = v_mps

        accumulated_dist_m += v_real * dt_s
        
        note = res["status_note"]
        if thrust_ratio < 0.99: 
            note = f"Slow {v_real:.1f}m/s" + (f" {note}" if note else "")
        
        if "POWER" in note or "FAILED" in note or "Error" in note: 
            status_msg = note
            log_data.append((
                time_s, current_soc*100, V_load, 
                res["I_total"], res["P_consumed"], 
                res["actual_throttle"], res["actual_thrust"],
                res["new_temp_c"], res["c_rate"], note
            ))
            break
            
        if V_load < V_cutoff_pack:
            status_msg = "VOLTAGE CUTOFF"
            log_data.append((
                time_s, current_soc*100, V_load, 
                res["I_total"], res["P_consumed"], 
                res["actual_throttle"], res["actual_thrust"],
                res["new_temp_c"], res["c_rate"], status_msg
            ))
            break 
            
        E_consumed_step = res["P_consumed"] * dt_h
        E_consumed_total_Wh += E_consumed_step
        time_s += dt_s
        
        if int(time_s) % 60 == 0 or len(log_data) == 0:
            log_data.append((
                time_s, current_soc*100, V_load, 
                res["I_total"], res["P_consumed"], 
                res["actual_throttle"], res["actual_thrust"],
                res["new_temp_c"], res["c_rate"], note
            ))

    if E_consumed_total_Wh >= total_usable_energy_Wh: 
        status_msg = "ENERGY LIMIT"
    
    if not log_data or log_data[-1][0] != time_s:
        try: 
            log_data.append((
                time_s, current_soc*100, V_load, 
                res["I_total"], res["P_consumed"], 
                res["actual_throttle"], res["actual_thrust"],
                res["new_temp_c"], res["c_rate"], status_msg
            ))
        except BaseException:
            pass
         
    return {
        "status": status_msg, "time_s": time_s, "log_data": log_data,
        "total_dist_m": accumulated_dist_m, "percent": (E_consumed_total_Wh / max(total_usable_energy_Wh, 1e-6)) * 100.0,
        "total_E_consumed_Wh": E_consumed_total_Wh
    }