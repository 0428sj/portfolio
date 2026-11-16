# core_physics_engine.py
import math
from core_airframe import (
    AIRFRAME_LIBRARY, throttle_for_required_thrust, 
    compute_current, compute_thrust, throttle_for_current
)
from core_battery_ocv import get_specific_heat
from core_battery_resistance import pack_voltage_under_load
from core_base import G, air_density 
from core_battery_params import estimate_surface_area, c_rate_penalty


# 1. 배터리 발열 및 냉각 계산 (뉴턴 냉각 법칙 기반)
def calculate_next_battery_temp(
    current_temp_c, current_a, r_ohm, dt_s, 
    batt_mass_kg, batt_params, v_mps, ambient_temp_c,
    airframe_data=None
):
    """
    물리 기반 배터리 온도 모델
    - 줄 발열 (I²R)
    - 뉴턴 냉각 법칙 기반 열전달
    """
    
    # === 1. 발열 (Joule Heating) ===
    Q_gen = (current_a ** 2) * r_ohm * dt_s  # [J]
    
    # === 2. 배터리 열 특성 ===
    if "specific_heat" in batt_params:
        specific_heat = batt_params["specific_heat"]
    else:
        ocv_kind = batt_params.get("ocv_kind", "lipo")
        specific_heat = get_specific_heat(ocv_kind)
    
    if "surface_area_m2" in batt_params:
        batt_surface = batt_params["surface_area_m2"]
    else:
        batt_surface = estimate_surface_area(batt_mass_kg)
    
    if airframe_data is not None:
        exposure_ratio = airframe_data.get("batt_exposure_ratio", 1.0)
    else:
        exposure_ratio = 1.0
    
    effective_area = batt_surface * exposure_ratio
    
    # === 3. 냉각 (뉴턴 냉각 법칙) ===
    h_natural = 10.0
    h_forced = 10.0 + 12.0 * math.sqrt(max(v_mps, 0))
    h_total = max(h_natural, h_forced)
    
    temp_diff = current_temp_c - ambient_temp_c
    Q_transfer = h_total * effective_area * temp_diff * dt_s
    
    # === 4. 에너지 밀도 페널티 ===
    energy_density = batt_params.get("energy_density_wh_per_kg", 200.0)
    if energy_density > 250:
        cooling_penalty = 1.0 - 0.002 * (energy_density - 250)
        cooling_penalty = max(0.7, cooling_penalty)
        Q_transfer *= cooling_penalty
    
    # === 5. 온도 변화 계산 ===
    thermal_mass = batt_mass_kg * specific_heat
    delta_temp = (Q_gen - Q_transfer) / max(thermal_mass, 1.0)
    
    next_temp_c = current_temp_c + delta_temp
    
    return next_temp_c


# 2. VTOL 고정익 모드 추력 계산 (양력 + 실속 고려)
def calculate_vtol_cruise_thrust(total_mass_kg, v_mps, airframe_data, temp_c=15.0, altitude_m=0.0):

    cd           = airframe_data.get("cd", 0.3)
    frontal_area = airframe_data.get("frontal_area", 0.15)
    wing_area    = airframe_data.get("wing_area", 1.0)
    cl_max       = airframe_data.get("cl", 0.5)
    stall_speed  = airframe_data.get("stall_speed", None)
    aspect_ratio = airframe_data.get("aspect_ratio", 8.0)
    oswald_e     = airframe_data.get("oswald_e", 0.8)

    try:
        rho = air_density(temp_c, altitude_m)
    except BaseException:
        rho = 1.225

    if rho <= 0:
        rho = 1.225

    if stall_speed and stall_speed > 0.5:
        vr = max(0.0, v_mps / stall_speed)
        cl_eff = cl_max * min(1.0, vr ** 2)
    else:
        cl_eff = cl_max

    q = 0.5 * rho * v_mps**2  

    lift_N = q * cl_eff * wing_area
    parasite_drag = q * cd * frontal_area

    weight_N = total_mass_kg * G

    if v_mps > 0.5:
        cl_current = lift_N / (q * wing_area)
        cd_induced = (cl_current ** 2) / (math.pi * aspect_ratio * oswald_e)
        induced_drag = q * wing_area * cd_induced
    else:
        induced_drag = 0.0

    drag_total = parasite_drag + induced_drag
    vertical_shortfall = max(0.0, weight_N - lift_N)

    return math.sqrt(drag_total**2 + vertical_shortfall**2)


def transition_blend(v_mps, stall_speed, margin_low=0.9, margin_high=1.3):
    """
    VTOL 모드 전이 블렌딩
    - v < stall × 0.9: 완전 멀티콥터 (0.0)
    - v > stall × 1.3: 완전 고정익 (1.0)
    - 그 사이: 부드러운 전이 (코사인 보간)
    """
    if not stall_speed or stall_speed < 1:
        return 1.0
    
    v_start = stall_speed * margin_low
    v_end = stall_speed * margin_high
    
    if v_mps <= v_start:
        return 0.0
    elif v_mps >= v_end:
        return 1.0
    else:
        t = (v_mps - v_start) / (v_end - v_start)
        return 0.5 * (1.0 - math.cos(math.pi * t))


# 3. 멀티콥터 모드 추력 계산 (전이양력 + 항력)
def calculate_required_thrust_with_drag(
    total_mass_kg,
    v_mps,
    airframe_data,
    temp_c=15.0,
    altitude_m=0.0
):
    cd   = airframe_data.get("cd", 1.2)
    area = airframe_data.get("frontal_area", 0.05)

    try:
        rho = air_density(temp_c, altitude_m)
    except BaseException:
        rho = 1.225

    if rho <= 0:
        rho = 1.225

    k_lift_raw = 1.0 - 0.01 * abs(v_mps)
    k_lift = max(0.75, min(1.0, k_lift_raw))

    force_vertical = (total_mass_kg * G) * k_lift
    drag_force = 0.5 * rho * v_mps**2 * cd * area

    return math.sqrt(force_vertical**2 + drag_force**2)


# 실속 속도 부근에서 호버 추력과 순항 추력을 섞어 VTOL 필요 추력을 낸다
def calculate_vtol_thrust(total_mass_kg, v_mps, airframe_data, temp_c, altitude_m):

    hover_thrust  = calculate_required_thrust_with_drag(total_mass_kg, v_mps, airframe_data, temp_c, altitude_m)
    cruise_thrust = calculate_vtol_cruise_thrust(total_mass_kg, v_mps, airframe_data, temp_c, altitude_m)

    stall_speed = airframe_data.get("stall_speed", 12.0)
    w = transition_blend(v_mps, stall_speed)

    return (1 - w) * hover_thrust + w * cruise_thrust


# 속도를 훑어 1 m 당 에너지가 가장 작은 VTOL 순항 속도를 찾는다(실속 아래는 벌점)
def find_vtol_optimal_speed(total_mass_kg, airframe_data, temp_c=15.0, altitude_m=0.0):
    
    speeds = [v/2 for v in range(20, 100)]  
    profile = []

    rho = air_density(temp_c, altitude_m)
    if rho <= 0:
        rho = 1.225
    
    user_stall = airframe_data.get("stall_speed")
    
    if user_stall and user_stall > 0:
        stall_speed = user_stall
    else:
        wing_area = airframe_data.get("wing_area", 0.5)
        cl = airframe_data.get("cl", 0.8)
        stall_speed = math.sqrt((2 * total_mass_kg * G) / max(rho * wing_area * cl, 1e-9))

    for v in speeds:
        thrust = calculate_vtol_thrust(total_mass_kg, v, airframe_data, temp_c, altitude_m)
        power_W = thrust * max(v, 0.1)
        
        if v < stall_speed:
            penalty_factor = 10.0
        else:
            penalty_factor = 1.0
            
        energy_per_meter = (power_W / max(v, 0.1)) * penalty_factor
        
        wing_area = airframe_data.get("wing_area", 0.5)
        cl = airframe_data.get("cl", 0.8)
        
        if v < stall_speed:
            cl_eff = cl * (v / stall_speed)
        else:
            cl_eff = cl
            
        wing_lift = 0.5 * rho * v**2 * wing_area * cl_eff
        rotor_needed = max(0, total_mass_kg * G - wing_lift)

        profile.append((v, energy_per_meter, wing_lift, rotor_needed))

    v_opt, e_min, wing_lift_opt, rotor_opt = min(profile, key=lambda x: x[1])

    wing_ratio = wing_lift_opt / (total_mass_kg * G)
    rotor_ratio = rotor_opt / (total_mass_kg * G)

    return {
        "optimal_speed": v_opt,
        "stall_speed": stall_speed,
        "wing_ratio": wing_ratio,
        "rotor_ratio": rotor_ratio
    }


# 목표 추력에 필요한 축 출력(W) = 만충 부하 전압 × 전류 × 축 효율
def get_P_mech_target(batt_params, airframe_name, target_thrust_N, temp_c, altitude_m, ocv_curve, frame_data=None):
    try:
        thr_initial = throttle_for_required_thrust(target_thrust_N, airframe_name, temp_c, altitude_m, frame_data)
        I_initial = compute_current(thr_initial, airframe_name, frame_data)
        
        _, V_load_initial, _ = pack_voltage_under_load(
            batt_params, I_initial, temp_c, ocv_curve, soc_val=0.95
        )
        
        if frame_data is None:
            frame_data = AIRFRAME_LIBRARY[airframe_name]
        eff_shaft = frame_data.get("eff_shaft", 1.0)
        
        P_mech_target = (V_load_initial * I_initial) * eff_shaft
        
        if P_mech_target <= 0 and target_thrust_N > 0.1:
             return 0.0 
        return P_mech_target
    except Exception:
        return 0.0


# 5. 시뮬레이션 스텝 실행 (통합)
def run_simulation_step(
    batt_params, airframe_name, eff_shaft, ocv_curve, ns, v_nom, total_mass_kg,
    p_avionics_w, temp_c, altitude_m, R_pack, V_ocv, mode,
    P_mech_target=0.0, target_throttle=0.0, frame_data=None,
    dt_s=1.0, current_temp_c=25.0, batt_mass_kg=1.0, v_mps=0.0, ambient_temp_c=25.0
):
    step_results = {
        "V_load": 0.0, "I_total": 0.0, "P_consumed": 0.0,
        "actual_throttle": 0.0, "actual_thrust": 0.0,
        "status_note": "",
        "new_temp_c": current_temp_c,
        "c_rate": 0.0,  # 신규
    }

    try:
        if mode == 'thrust':
            P_elec_propulsion = P_mech_target / max(eff_shaft, 0.1) 
            P_total_target = P_elec_propulsion + p_avionics_w
            a = 1.0
            b = -V_ocv
            c = (P_total_target * R_pack)
            discriminant = b**2 - 4*a*c
            if discriminant < 0:
                step_results["status_note"] = "POWER SUPPLY FAILED"
                return step_results
            V_load = (-b + math.sqrt(discriminant)) / (2*a)
            
            I_propulsion = P_elec_propulsion / V_load
            actual_throttle = throttle_for_current(I_propulsion, airframe_name, frame_data)
            actual_thrust = compute_thrust(actual_throttle, airframe_name, temp_c, altitude_m, frame_data)
            I_total = P_total_target / V_load
            P_consumed = P_total_target

        else: # throttle mode
            actual_throttle = target_throttle 
            
            I_nom_fixed = compute_current(actual_throttle, airframe_name, frame_data)
            
            a = 1.0 + ( (I_nom_fixed * R_pack) / v_nom )
            
            b = -V_ocv
            c = p_avionics_w * R_pack
            discriminant = b**2 - 4*a*c
            if discriminant < 0:
                step_results["status_note"] = "POWER SUPPLY FAILED"
                return step_results
            V_load = (-b + math.sqrt(discriminant)) / (2*a)
            
            I_propulsion = I_nom_fixed * (V_load / v_nom)
        
            I_total = I_propulsion + (p_avionics_w / V_load)
            
            P_consumed = (V_load * I_total)
            actual_thrust = compute_thrust(actual_throttle, airframe_name, temp_c, altitude_m, frame_data) * (V_load / v_nom)

        # === C-rate 페널티 적용 ===
        cap_ah = batt_params.get("cap_ah", 1.0)
        current_c_rate = I_total / cap_ah
        
        r_mult, c_msg = c_rate_penalty(I_total, batt_params)
        if r_mult > 1.0:
            V_load = V_ocv - I_total * R_pack * r_mult
            V_load = max(0.0, V_load)
        
        step_results["c_rate"] = current_c_rate

        # 온도 계산
        new_temp = calculate_next_battery_temp(
            current_temp_c, I_total, R_pack, dt_s, 
            batt_mass_kg, batt_params, v_mps, ambient_temp_c,
            airframe_data=frame_data
        )
        step_results["new_temp_c"] = new_temp

        # 상태 메시지 조합 (온도 + C-rate)
        notes = []
        if new_temp > 80.0:
            notes.append("OVERHEAT")
        elif new_temp > 60.0:
            notes.append("HOT")
        
        if "C-HIGH" in c_msg or "C-OVER" in c_msg:
            notes.append(c_msg)
        
        step_results["status_note"] = " ".join(notes) if notes else ""

    except Exception as e:
        step_results["status_note"] = f"Sim Error: {e}"
        return step_results

    step_results.update({
        "V_load": V_load, "I_total": I_total, "P_consumed": P_consumed,
        "actual_throttle": actual_throttle, "actual_thrust": actual_thrust
    })
    return step_results