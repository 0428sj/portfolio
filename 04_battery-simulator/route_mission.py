# route_mission.py
import math
from core_airframe import AIRFRAME_LIBRARY, G
from core_battery_ocv import get_ocv_curve
from core_battery_resistance import pack_r_ohm_from_params, temp_correct_resistance
from core_physics_engine import (
    run_simulation_step, get_P_mech_target, 
    calculate_required_thrust_with_drag, calculate_vtol_cruise_thrust
)

# 호버 대비 ±30 % 추력의 출력 차로 상승·하강 속도(m/s)를 추정한다
def _calculate_v_climb_descend_mps(
    batt_params, airframe_name, total_mass_kg, temp_c, altitude_m, ocv_curve, frame_data=None
):
    try:
        THRUST_HOVER_N = total_mass_kg * G
        P_mech_hover = get_P_mech_target(batt_params, airframe_name, THRUST_HOVER_N, temp_c, altitude_m, ocv_curve, frame_data=frame_data)
        P_mech_climb = get_P_mech_target(batt_params, airframe_name, THRUST_HOVER_N * 1.3, temp_c, altitude_m, ocv_curve, frame_data=frame_data)
        P_mech_descend = get_P_mech_target(batt_params, airframe_name, THRUST_HOVER_N * 0.7, temp_c, altitude_m, ocv_curve, frame_data=frame_data)

        if P_mech_hover == 0.0:
            return 3.0, 3.0

        v_climb_mps = (P_mech_climb - P_mech_hover) / max(THRUST_HOVER_N, 0.1)
        v_descend_mps = (P_mech_hover - P_mech_descend) / max(THRUST_HOVER_N, 0.1)
        
        return max(0.5, min(v_climb_mps, 10.0)), max(0.5, min(v_descend_mps, 10.0))
    except Exception as e:
        print(f"[WARN] V_Climb calculation failed: {e}")
        return 3.0, 3.0

# QGC 미션 구간별(이륙·순항·로이터·착륙) 비행 시뮬레이션
def simulate_route_segmented(
    batt_params, airframe_name, total_usable_energy_Wh, total_mass_kg,
    commands, v_cruise_mps, 
    p_avionics_w, temp_c, v_cutoff_cell=3.0
):
    # 1. 기체 데이터 및 VTOL 초기화
    base_frame = AIRFRAME_LIBRARY[airframe_name]
    is_vtol = (base_frame.get("type") == "vtol")
    
    if is_vtol:
        hover_data = base_frame.get("hover", base_frame)
        cruise_data = base_frame.get("cruise", base_frame)
        cruise_data["cd"] = base_frame.get("cd", 0.8)
        cruise_data["frontal_area"] = base_frame.get("frontal_area", 0.15)
        cruise_data["wing_area"] = base_frame.get("wing_area", 0.5)
    else:
        hover_data = base_frame
        cruise_data = base_frame

    ns = batt_params.get("ns", 6)
    v_nom = ns * batt_params.get("v_cell_nom", 3.7)
    ocv_curve = get_ocv_curve(batt_params.get("ocv_kind", "neo"))
    V_cutoff_pack = v_cutoff_cell * ns
    dt_s = 1.0
    dt_h = dt_s / 3600.0
    
    THRUST_HOVER_N = total_mass_kg * G
    THRUST_CLIMB_N = THRUST_HOVER_N * 1.3
    THRUST_DESCEND_N = THRUST_HOVER_N * 0.7 

    init_alt = commands[0]['alt_asl'] if commands else 60.0
    LIMIT_CLIMB_MPS, LIMIT_DESCEND_MPS = _calculate_v_climb_descend_mps(
        batt_params, airframe_name, total_mass_kg, 
        temp_c, init_alt, ocv_curve, frame_data=hover_data
    )
    
    # 발열 변수
    sim_temp_c = temp_c
    batt_mass = batt_params.get("mass_ref_kg", 1.0)

    time_s = 0.0
    E_consumed_total_Wh = 0.0
    log_data = [] 
    
    total_E_climb_Wh = 0.0
    total_E_cruise_Wh = 0.0
    total_dist_cruise_m = 0.0
    segments_completed = 0
    
    result = { 
        "time_s": 0.0, "log_data": [], "status": "INIT", "percent": 0.0,
        "total_E_climb_Wh": 0.0, "total_E_cruise_Wh": 0.0,
        "total_dist_cruise_m": 0.0, "segments_completed": 0
    }
    
    # --- 명령어 루프 ---
    for idx, cmd_item in enumerate(commands, 1): 
        cmd = cmd_item['cmd']
        current_alt = cmd_item['alt_asl']
        status = None
        
        if cmd == 16 and is_vtol: 
            active_data = cruise_data
            use_wing_physics = True
        else:
            active_data = hover_data
            use_wing_physics = False
        eff_shaft = active_data.get("eff_shaft", 1.0)

        # --- A. LOITER ---
        if cmd == 19:
            duration = cmd_item['time_s']
            elapsed = 0.0
            
            P_target = get_P_mech_target(
                batt_params, airframe_name, THRUST_HOVER_N, 
                sim_temp_c, current_alt, ocv_curve, frame_data=active_data
            )

            while elapsed < duration:
                soc = 1.0 - (E_consumed_total_Wh / max(total_usable_energy_Wh, 1e-6))
                res = run_simulation_step(
                    batt_params, airframe_name, eff_shaft, ocv_curve, ns, v_nom, 
                    total_mass_kg, p_avionics_w, sim_temp_c, current_alt,
                    temp_correct_resistance(pack_r_ohm_from_params(batt_params), sim_temp_c),
                    ns * ocv_curve(soc), 'thrust', 
                    P_mech_target=P_target, frame_data=active_data,
                    dt_s=dt_s, current_temp_c=sim_temp_c, batt_mass_kg=batt_mass, v_mps=0.0, ambient_temp_c=temp_c
                )
                
                sim_temp_c = res["new_temp_c"]
                E_step = res['P_consumed'] * dt_h
                E_consumed_total_Wh += E_step
                total_E_climb_Wh += E_step 
                time_s += dt_s
                elapsed += dt_s
                
                note = f"Seg {idx} Loiter"
                if res['status_note']:
                    note += f" [{res['status_note']}]"
                
                log_data.append((
                    time_s, soc*100, res['V_load'], 
                    res['I_total'], res['P_consumed'], 
                    res['actual_throttle'], res['actual_thrust'],
                    res['new_temp_c'], res['c_rate'], note
                ))
                
                if "POWER" in res['status_note'] or "FAILED" in res['status_note'] or "Error" in res['status_note']:
                    status = res['status_note']
                    break

                if res['V_load'] < V_cutoff_pack: 
                    status = "VOLTAGE CUTOFF"
                    break
                if E_consumed_total_Wh >= total_usable_energy_Wh: 
                    status = "ENERGY LIMIT"
                    break
            
            if status: 
                result.update({"status": f"{note} ({status})", "percent": (elapsed/duration)*100})
                break

        # --- B. TAKEOFF/LAND ---
        elif cmd in [22, 21]:
            climb_m = cmd_item['climb_m']
            if abs(climb_m) > 0.1:
                is_climb = climb_m > 0
                v_vert = LIMIT_CLIMB_MPS if is_climb else LIMIT_DESCEND_MPS
                thrust_vert = THRUST_HOVER_N * (1.3 if is_climb else 0.7)
                duration = abs(climb_m) / v_vert
                elapsed = 0.0
                cmd_str = "TAKEOFF" if cmd == 22 else "LAND"
                
                P_target = get_P_mech_target(
                    batt_params, airframe_name, thrust_vert, 
                    sim_temp_c, current_alt, ocv_curve, frame_data=active_data
                )
                
                while elapsed < duration:
                    soc = 1.0 - (E_consumed_total_Wh / max(total_usable_energy_Wh, 1e-6))
                    sim_alt = current_alt + (v_vert * elapsed * (1 if is_climb else -1))
                    
                    res = run_simulation_step(
                        batt_params, airframe_name, eff_shaft, ocv_curve, ns, v_nom, 
                        total_mass_kg, p_avionics_w, sim_temp_c, sim_alt,
                        temp_correct_resistance(pack_r_ohm_from_params(batt_params), sim_temp_c),
                        ns * ocv_curve(soc), 'thrust', 
                        P_mech_target=P_target, frame_data=active_data,
                        dt_s=dt_s, current_temp_c=sim_temp_c, batt_mass_kg=batt_mass, v_mps=v_vert, ambient_temp_c=temp_c
                    )
                    
                    sim_temp_c = res["new_temp_c"]
                    E_step = res['P_consumed'] * dt_h
                    E_consumed_total_Wh += E_step
                    total_E_climb_Wh += E_step
                    time_s += dt_s
                    elapsed += dt_s
                    
                    note = f"Seg {idx} {cmd_str}"
                    if res['status_note']:
                        note += f" [{res['status_note']}]"

                    log_data.append((
                        time_s, soc*100, res['V_load'], 
                        res['I_total'], res['P_consumed'], 
                        res['actual_throttle'], res['actual_thrust'],
                        res['new_temp_c'], res['c_rate'], note
                    ))

                    if "POWER" in res['status_note'] or "FAILED" in res['status_note'] or "Error" in res['status_note']:
                        status = res['status_note']
                        break
                    
                    if res['V_load'] < V_cutoff_pack: 
                        status = "VOLTAGE CUTOFF"
                        break
                    if E_consumed_total_Wh >= total_usable_energy_Wh: 
                        status = "ENERGY LIMIT"
                        break
                
                if status: 
                    result.update({"status": f"{note} ({status})", "percent": (elapsed/duration)*100})
                    break

        # --- C. FLY ---
        elif cmd == 16:
            dist_target = cmd_item['dist_m']
            climb_m = cmd_item['climb_m']
            if dist_target < 0.1:
                dist_target = 0.1
            v_target_horiz = cmd_item['speed_mps'] if cmd_item['speed_mps'] else v_cruise_mps
            if v_target_horiz < 0.1:
                v_target_horiz = 0.1
            
            req_vz = (climb_m / dist_target) * v_target_horiz
            
            # 추력 계산
            if use_wing_physics:
                thrust_base = calculate_vtol_cruise_thrust(
                    total_mass_kg, v_target_horiz, active_data, sim_temp_c, current_alt
                )
                delta_thrust = 0.0
                if req_vz > 0:
                    delta_thrust = (total_mass_kg * G) * (req_vz / 20.0)
                target_thrust = thrust_base + delta_thrust
                note_suffix = "(VTOL)"
            else:
                thrust_base = calculate_required_thrust_with_drag(
                    total_mass_kg, v_target_horiz, active_data, sim_temp_c, current_alt
                )
                delta_thrust = 0.0
                if req_vz > 0:
                    delta_thrust = (THRUST_CLIMB_N - THRUST_HOVER_N) * (req_vz / LIMIT_CLIMB_MPS)
                else:
                    delta_thrust = (THRUST_DESCEND_N - THRUST_HOVER_N) * (abs(req_vz) / LIMIT_DESCEND_MPS)
                target_thrust = thrust_base + delta_thrust
                note_suffix = "(Multi)"
            
            dist_covered = 0.0
            P_target = get_P_mech_target(
                batt_params, airframe_name, target_thrust, 
                sim_temp_c, current_alt, ocv_curve, frame_data=active_data
            )

            while dist_covered < dist_target:
                soc = 1.0 - (E_consumed_total_Wh / max(total_usable_energy_Wh, 1e-6))
                current_path_ratio = dist_covered / dist_target
                sim_alt = current_alt + (climb_m * current_path_ratio)
                
                res = run_simulation_step(
                    batt_params, airframe_name, eff_shaft, ocv_curve, ns, v_nom, 
                    total_mass_kg, p_avionics_w, sim_temp_c, sim_alt,
                    temp_correct_resistance(pack_r_ohm_from_params(batt_params), sim_temp_c),
                    ns * ocv_curve(soc), 'thrust', 
                    P_mech_target=P_target, frame_data=active_data,
                    dt_s=dt_s, current_temp_c=sim_temp_c, batt_mass_kg=batt_mass, v_mps=v_target_horiz, ambient_temp_c=temp_c
                )
                
                sim_temp_c = res["new_temp_c"]
                actual_thrust = res["actual_thrust"]
                v_real = v_target_horiz
                if target_thrust > 1e-3:
                    thrust_ratio = actual_thrust / target_thrust
                    if thrust_ratio < 0.99:
                        v_real = v_target_horiz * math.sqrt(max(0.0, thrust_ratio))

                E_step = res['P_consumed'] * dt_h
                E_consumed_total_Wh += E_step
                total_E_cruise_Wh += E_step
                time_s += dt_s
                
                dist_step = v_real * dt_s
                dist_covered += dist_step
                total_dist_cruise_m += dist_step
                
                note = f"Seg {idx} Fly {v_real:.1f}m/s {note_suffix}"
                if res['status_note']:
                    note += f" [{res['status_note']}]"

                log_data.append((
                    time_s, soc*100, res['V_load'], 
                    res['I_total'], res['P_consumed'], 
                    res['actual_throttle'], res['actual_thrust'],
                    res['new_temp_c'], res['c_rate'], note
                ))
                
                if "POWER" in res['status_note'] or "FAILED" in res['status_note'] or "Error" in res['status_note']:
                    status = res['status_note']
                    break

                if res['V_load'] < V_cutoff_pack: 
                    status = "VOLTAGE CUTOFF"
                    break
                if E_consumed_total_Wh >= total_usable_energy_Wh: 
                    status = "ENERGY LIMIT"
                    break
            
            if status: 
                result.update({"status": f"{note} ({status})", "percent": (dist_covered/dist_target)*100})
                break

        segments_completed += 1
        
    if not status:
        result["status"] = "COMPLETED"
        result["percent"] = 100.0

    result.update({
        "time_s": time_s, "log_data": log_data,
        "total_E_climb_Wh": total_E_climb_Wh, "total_E_cruise_Wh": total_E_cruise_Wh,
        "total_dist_cruise_m": total_dist_cruise_m, "segments_completed": segments_completed,
        "commands": commands 
    })
    return result