# core_battery_resistance.py
from core_battery_ocv import get_ocv_curve 


def temp_correct_resistance(r_ohm, temp_c, ref_temp=25.0):
    """
    온도 기반 저항 보정 (연속 함수)
    - 온도 상승 시 저항 감소 (~-0.5%/°C)
    - 저온에서는 비선형 급증
    - 고온에서는 열화 반영
    """
    temp_coeff = -0.005
    delta_t = temp_c - ref_temp
    base_factor = 1.0 + temp_coeff * delta_t
    
    if temp_c < 0:
        cold_penalty = 1.0 + 0.03 * abs(temp_c)
    else:
        cold_penalty = 1.0
    
    if temp_c > 60:
        hot_penalty = 1.0 + 0.01 * (temp_c - 60)
    else:
        hot_penalty = 1.0
    
    return r_ohm * base_factor * cold_penalty * hot_penalty


def soc_resistance_factor(soc):
    """
    SOC에 따른 내부저항 증가 계수
    """
    if soc >= 0.2:
        return 1.0
    elif soc >= 0.1:
        return 1.0 + 0.5 * (0.2 - soc) / 0.1
    else:
        return 1.5 + 1.0 * (0.1 - soc) / 0.1


# 셀 저항·직렬·병렬 수로 팩 내부저항(Ω)
def pack_r_ohm_from_params(p):
    ns = p.get("ns", 6)
    np = p.get("np", 1)
    r_cell = p.get("r_cell_ohm", 0.0015)
    return (r_cell * ns) / max(np, 1)


# 온도·SOC 를 반영한 실효 내부저항
def get_effective_resistance(r_base, temp_c, soc):
    r_temp = temp_correct_resistance(r_base, temp_c)
    r_final = r_temp * soc_resistance_factor(soc)
    return r_final


# 부하 전류에서 팩 OCV·단자전압(OCV − I·R)·저항을 돌려준다
def pack_voltage_under_load(params, current_a, temp_c=25.0, ocv_curve=None, soc_val=0.5):
    ns = params.get("ns", 6)
    
    if ocv_curve is None:
        ocv_kind = params.get("ocv_kind", "neo") 
        ocv_curve = get_ocv_curve(ocv_kind)
        if ocv_curve is None: 
            ocv_curve = get_ocv_curve("neo")
        
    try:
        v_cell_ocv = float(ocv_curve(soc_val)) 
    except Exception:
        v_cell_ocv = params.get("v_cell_nom", 3.7) 
        
    v_ocv = ns * v_cell_ocv 

    r_pack_base = pack_r_ohm_from_params(params)
    r_pack = get_effective_resistance(r_pack_base, temp_c, soc_val)
    
    v_load = max(0.0, v_ocv - float(current_a) * r_pack)
    return v_ocv, v_load, r_pack