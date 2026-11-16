# hover_unified.py
from core_airframe import AIRFRAME_LIBRARY, G
from core_battery_ocv import get_ocv_curve
from core_battery_resistance import pack_r_ohm_from_params, temp_correct_resistance
from core_physics_engine import run_simulation_step, get_P_mech_target

# 호버 비행 시간 시뮬레이션(전압 컷오프 또는 에너지 소진까지)
def simulate_hover(
    batt_params, airframe_name, total_usable_energy_Wh, total_mass_kg,
    is_auto, manual_throttle_pct, p_avionics_w, temp_c, altitude_m, v_cutoff_cell=3.0
):
    # 1. 기체 데이터 로드 및 VTOL 분기 처리
    base_frame = AIRFRAME_LIBRARY[airframe_name]
    
    if base_frame.get("type") == "vtol":
        active_data = base_frame.get("hover", base_frame)
    else:
        active_data = base_frame

    eff_shaft = active_data.get("eff_shaft", 1.0)
    
    # 2. 배터리 설정
    ns = batt_params.get("ns", 6)
    v_nom = ns * batt_params.get("v_cell_nom", 3.7) 
    ocv_kind = batt_params.get("ocv_kind", "neo")
    ocv_curve = get_ocv_curve(ocv_kind)
    if ocv_curve is None:
        ocv_curve = get_ocv_curve("neo")

    V_cutoff_pack = v_cutoff_cell * ns
    dt_s = 10.0
    dt_h = dt_s / 3600.0
    
    # 발열 변수
    sim_temp_c = temp_c
    batt_mass = batt_params.get("mass_ref_kg", 1.0)
    
    time_s = 0.0
    E_consumed_total_Wh = 0.0
    log_data = [] 
    
    mode_str = 'thrust' if is_auto else 'throttle'
    P_mech_target = 0.0
    target_throttle_pct = 0.0
    status_msg = "INIT"

    if is_auto:
        mode_str = 'thrust'
        try:
            required_thrust_N = total_mass_kg * G
            P_mech_target = get_P_mech_target(
                batt_params, airframe_name, required_thrust_N, 
                sim_temp_c, altitude_m, ocv_curve, frame_data=active_data
            )
            if P_mech_target <= 0.0:
                raise ValueError("Target Power is zero.")
        except Exception as e:
            return { "status": f"FAILED ({e})", "time_s": 0.0, "log_data": [], "percent": 0.0, "total_E_consumed_Wh": 0.0 }
    else:
        mode_str = 'throttle'
        target_throttle_pct = float(manual_throttle_pct) / 100.0

    # 5. 시뮬레이션 루프
    while E_consumed_total_Wh < total_usable_energy_Wh:
        current_soc = 1.0 - (E_consumed_total_Wh / max(total_usable_energy_Wh, 1e-6))
        
        try:
            v_cell_ocv = float(ocv_curve(current_soc))
        except Exception:
            v_cell_ocv = 3.7
        V_ocv = ns * v_cell_ocv
        r_pack_base = pack_r_ohm_from_params(batt_params)
        
        # 온도에 따른 저항 변화 반영
        R_pack = temp_correct_resistance(r_pack_base, sim_temp_c)

        step_results = run_simulation_step(
            batt_params=batt_params, airframe_name=airframe_name,
            eff_shaft=eff_shaft, ocv_curve=ocv_curve, ns=ns, v_nom=v_nom,
            total_mass_kg=total_mass_kg, p_avionics_w=p_avionics_w,
            temp_c=sim_temp_c, altitude_m=altitude_m,
            R_pack=R_pack, V_ocv=V_ocv,
            mode=mode_str,
            P_mech_target=P_mech_target,
            target_throttle=target_throttle_pct,
            frame_data=active_data,
            dt_s=dt_s, current_temp_c=sim_temp_c, batt_mass_kg=batt_mass, v_mps=0.0, ambient_temp_c=temp_c
        )

        sim_temp_c = step_results["new_temp_c"]
        V_load = step_results["V_load"]
        note = step_results["status_note"]

        if "POWER" in note or "FAILED" in note or "Error" in note:
            status_msg = note
            log_data.append((
                time_s, current_soc*100, V_load, 
                step_results["I_total"], step_results["P_consumed"], 
                step_results["actual_throttle"], step_results["actual_thrust"],
                step_results["new_temp_c"], step_results["c_rate"], note
            ))
            break
            
        if V_load < V_cutoff_pack:
            status_msg = "VOLTAGE CUTOFF"
            log_data.append((
                time_s, current_soc*100, V_load, 
                step_results["I_total"], step_results["P_consumed"], 
                step_results["actual_throttle"], step_results["actual_thrust"],
                step_results["new_temp_c"], step_results["c_rate"], status_msg
            ))
            break 

        E_consumed_step = step_results["P_consumed"] * dt_h
        E_consumed_total_Wh += E_consumed_step
        time_s += dt_s

        if int(time_s) % 60 == 0 or len(log_data) == 0:
            log_data.append((
                time_s, current_soc*100, V_load, 
                step_results["I_total"], step_results["P_consumed"], 
                step_results["actual_throttle"], step_results["actual_thrust"],
                step_results["new_temp_c"], step_results["c_rate"], note
            ))

    if E_consumed_total_Wh >= total_usable_energy_Wh:
        status_msg = "ENERGY LIMIT"
    
    if not log_data or (log_data[-1][0] != time_s):
        try: 
            log_data.append((
                time_s, current_soc*100, V_load, 
                step_results["I_total"], step_results["P_consumed"], 
                step_results["actual_throttle"], step_results["actual_thrust"],
                step_results["new_temp_c"], step_results["c_rate"], status_msg
            ))
        except BaseException:
            pass

    avg_thr = 0.0
    if is_auto and log_data:
        try:
            avg_thr = sum([row[5] for row in log_data]) / len(log_data) * 100.0
        except BaseException:
            pass

    return {
        "status": status_msg, "time_s": time_s, "log_data": log_data,
        "percent": (E_consumed_total_Wh / max(total_usable_energy_Wh, 1e-6)) * 100.0,
        "total_E_consumed_Wh": E_consumed_total_Wh, "is_auto": is_auto, "manual_thr": manual_throttle_pct, "avg_thr_pct": avg_thr
    }