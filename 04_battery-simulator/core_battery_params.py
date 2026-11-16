# core_battery_params.py

BATTERY_LIBRARY = {
    "Neo-6S-47Ah": {
        "ns": 6,
        "np": 1,
        "v_cell_nom": 3.65,
        "cap_ah": 47.64,
        "f_usable": 0.85,
        "energy_density_wh_per_kg": 350,   
        "r_cell_ohm": 0.0013,
        "ocv_kind": "neo",
        "mass_ref_kg": 3.1267,            
        "v_cutoff_cell": 3.0,   
        "surface_area_m2": 0.0580,  # [m²] 배터리 표면적   
        "max_c_rate": 25.0,
        "peak_c_rate": 50.0,        
    },
    "LiPo-6S-30Ah": {
        "ns": 6,
        "np": 1,
        "v_cell_nom": 3.7,
        "cap_ah": 30.0,
        "f_usable": 0.80,
        "energy_density_wh_per_kg": 190,
        "r_cell_ohm": 0.0016,
        "ocv_kind": "lipo",
        "mass_ref_kg": 3.5,
        "v_cutoff_cell": 3.3,  
        "surface_area_m2": 0.0737,  # [m²]  
        "max_c_rate": 25.0,
        "peak_c_rate": 50.0,           
    },
    "Polaris-6S-16Ah": {
        "ns": 6,
        "np": 1,
        "v_cell_nom": 3.7,         
        "cap_ah": 16.0,          
        "f_usable": 0.90,         
        "energy_density_wh_per_kg": 273.2, 
        "r_cell_ohm": 0.0025,      # 반고체는 내부저항 약간 높은 편
        "ocv_kind": "polaris",       # 방전 곡선은 Li-ion과 비슷함
        "mass_ref_kg": 1.3,        
        "v_cutoff_cell": 2.8,  
        "surface_area_m2": 0.0737,  # [m²]     
        "max_c_rate": 5.0,
        "peak_c_rate": None,  
    },            
    "LiIon-6S-30Ah": {
        "ns": 6,
        "np": 1,
        "v_cell_nom": 3.7,
        "cap_ah": 30.0,               
        "f_usable": 0.85,             
        "energy_density_wh_per_kg": 259.1,
        "r_cell_ohm": 0.0022,         
        "ocv_kind": "liion", 
        "mass_ref_kg": 2.57,
        "v_cutoff_cell": 3.0,       
        "surface_area_m2": 0.0737,  # [m²]    
        "max_c_rate": None,
        "peak_c_rate": None,    
    },
    "LiPo-6S-22Ah": {
        "ns": 6,
        "np": 1,
        "v_cell_nom": 3.7,
        "cap_ah": 22.0,
        "f_usable": 0.85,         
        "energy_density_wh_per_kg": 185.0, 
        "r_cell_ohm": 0.0015,    
        "ocv_kind": "lipo",
        "mass_ref_kg": 2.64,     
        "v_cutoff_cell": 3.3,     
        "surface_area_m2": 0.0465,  # [m²] 
        "max_c_rate": None,
        "peak_c_rate": None,
    },
}  


# 정격 에너지 × 사용 비율(에너지 밀도 상한이 있으면 더 작은 쪽)
def usable_energy_scaled_Wh(batt_params, batt_mass_kg=None):

    p = batt_params  

    # 정격 에너지 (Wh)
    v_nom = p["ns"] * p["v_cell_nom"]
    E_nom = v_nom * p["cap_ah"]

    # 배터리별 사용 비율
    usable_frac = p.get("f_usable", 0.80)
    E_cap = E_nom * usable_frac

    # 에너지밀도 기반 상한 (선택)
    ed = p.get("energy_density_wh_per_kg", None)
    if ed is not None and batt_mass_kg is not None:
        E_ed = ed * max(batt_mass_kg, 0.0) * usable_frac
        return min(E_cap, E_ed)

    return E_cap


# 배터리 질량으로 겉넓이(m²)를 추정한다(발열 계산용)
def estimate_surface_area(mass_kg):

    return 0.02 * (mass_kg ** 0.67)

# C-rate 가 허용치에 가까우면 내부저항 배수를 키운다 → (배수, 표시 문자열)
def c_rate_penalty(current_a, batt_params):

    cap_ah = batt_params.get("cap_ah", 1.0)
    max_c = batt_params.get("max_c_rate", None)
    
    if max_c is None:
        return 1.0, ""  # 검증 스킵
    
    current_c = current_a / cap_ah
    ratio = current_c / max_c
    
    if ratio < 0.9:
        # 정상 구간
        return 1.0, f"({current_c:.1f}C)"
    
    elif ratio < 1.0:
        # 경고 구간 (90~100%): 저항 최대 10% 증가
        r_mult = 1.0 + 0.1 * (ratio - 0.9) / 0.1
        return r_mult, f"C-HIGH ({current_c:.1f}C)"
    
    else:
        # 초과 구간: 저항 증가 (초과분당 15%)
        overshoot = ratio - 1.0
        r_mult = 1.1 + 0.15 * overshoot
        r_mult = min(r_mult, 1.5)  # 최대 1.5배 제한
        return r_mult, f"C-OVER ({current_c:.1f}C>{max_c:.0f}C)"