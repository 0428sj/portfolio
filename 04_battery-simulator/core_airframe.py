# core_airframe.py

from core_base import density_ratio
from scipy.interpolate import PchipInterpolator
import numpy as np
from scipy.optimize import brentq
from core_base import G  # noqa: F401 (route_mission 이 여기서 G 를 가져다 씀)

AIRFRAME_LIBRARY = {
    "IDR-1000G": {
        "v_native_s": 6, # <-- 이 기체는 6S용
        "mass_airframe_kg": 6.0,
        "motor_model": "MN501S-300KV",
        "prop_model": "22x6.6",
        "cd": 1.2,             # 항력 계수 (일반 드론)
        "frontal_area": 0.25,  # 전면 단면적 (m^2)
        "eff_shaft": 1.00,
        "p_avionics_w": 25.0, 
        "n_motors": 4,
        "batt_exposure_ratio": 0.7,
        "tables_are_per_motor": True, 
        "thrust_table": {
            0.40: 11.81, 0.42: 12.80, 0.44: 13.94, 0.46: 15.10, 0.48: 16.34,
            0.50: 17.89, 0.52: 19.42, 0.54: 20.98, 0.56: 22.22, 0.58: 23.35,
            0.60: 24.81, 0.62: 25.94, 0.64: 27.49, 0.66: 28.84, 0.68: 29.50,
            0.70: 30.36, 0.75: 34.39, 0.80: 39.49, 0.90: 45.65, 1.00: 51.75
        },
        
        "current_table": {
            0.40: 4.25, 0.42: 4.72, 0.44: 5.28, 0.46: 5.90, 0.48: 6.62,
            0.50: 7.40, 0.52: 8.23, 0.54: 9.11, 0.56: 9.94, 0.58: 10.87,
            0.60: 11.83, 0.62: 12.79, 0.64: 13.98, 0.66: 15.08, 0.68: 16.11,
            0.70: 17.28, 0.75: 20.38, 0.80: 23.68, 0.90: 31.11, 1.00: 37.74
        },
    },
    "IDR-1500": {
        "v_native_s": 12, 
        "mass_airframe_kg": 14.0,
        "motor_model": "HobbyWing_X9_Pro",
        "prop_model": "34.7x11",
        "cd": 1.3,             # 대형 기체라 항력 계수가 좀 더 큼
        "frontal_area": 0.35,  # 면적도 2배 (0.1 m^2)
        "eff_shaft": 1.00,
        "p_avionics_w": 30.0, 
        "n_motors": 4, 
        "batt_exposure_ratio": 0.2,
        "tables_are_per_motor": True, 
        "thrust_table": {
            0.29: 9.65, 0.45: 29.43, 0.55: 48.76, 0.64: 68.84,
            0.68: 78.67, 0.72: 88.61, 0.73: 93.41, 0.81: 117.75,
            0.86: 137.65, 0.91: 156.43, 0.97: 177.27, 1.00: 188.44,
        },
        "current_table": {
            0.29: 1.6, 0.45: 6.1, 0.55: 11.4, 0.64: 19.2,
            0.68: 23.2, 0.72: 27.1, 0.73: 29.2, 0.81: 41.1,
            0.86: 51.6, 0.91: 62.8, 0.97: 77.4, 1.00: 82.7,
        },
    },
    "IVT-2500": {
        "type": "vtol",
        "v_native_s": 12,         
        "mass_airframe_kg": 9.72,  
        "p_avionics_w": 50.0,      
        "cd": 0.1,   
        "cl": 0.5,    
        "batt_exposure_ratio": 0.2,
        "stall_speed": 15.0,        
        "frontal_area": 0.15,   
        "wing_area": 1.00,         
        # --- 1. 이착륙(Hover) 모터: T-motor V605 KV210 + 22x7.4 ---
        "hover": {
            "enabled": True,
            "count": 4,
            "motor": "V605-KV210",
            "prop": "T-motor 22x7.4",
            "eff_shaft": 1.00,   
            
            "thrust_table": {
                0.40: 28.34, 0.42: 31.38, 0.44: 33.93, 0.46: 36.48, 0.48: 39.71,
                0.50: 42.95, 0.52: 45.70, 0.54: 48.93, 0.56: 51.58, 0.58: 54.13,
                0.60: 56.68, 0.62: 60.31, 0.64: 63.25, 0.66: 66.39, 0.68: 69.04,
                0.70: 72.37, 0.80: 89.24, 0.90: 106.99, 1.00: 125.13
            },
            "current_table": {
                0.40: 7.21, 0.42: 8.20, 0.44: 9.09, 0.46: 10.29, 0.48: 11.56,
                0.50: 12.94, 0.52: 14.12, 0.54: 15.46, 0.56: 16.76, 0.58: 18.00,
                0.60: 19.46, 0.62: 21.06, 0.64: 22.61, 0.66: 24.51, 0.68: 26.19,
                0.70: 28.11, 0.80: 38.69, 0.90: 52.16, 1.00: 68.30
            }
        },

        # --- 2. 추진(Cruise) 모터: Sunnysky X7015 KV200 ---
        "cruise": {
            "enabled": True,
            "count": 1,
            "motor": "X7015-KV200",
            "prop": "APC 19x10E",
            "eff_shaft": 0.95,
            "thrust_table": {
                0.40: 15.69, 0.45: 21.57, 0.50: 29.42, 0.55: 38.25, 
                0.60: 48.05, 0.65: 58.84, 0.70: 70.61, 0.75: 83.36, 
                0.80: 96.11, 0.90: 122.58, 1.00: 149.06
            },
            "current_table": {
                0.40: 7.5, 0.45: 11.0, 0.50: 16.0, 0.55: 22.5, 
                0.60: 30.0, 0.65: 40.0, 0.70: 52.0, 0.75: 65.0, 
                0.80: 80.0, 0.90: 110.0, 1.00: 140.0
            }
        }
    },
}

_SPL_CACHE = {}

# 추력·전류 표로 스로틀→값 보간 곡선을 만든다(캐시)
def _build_splines(airframe_name, frame_data):
    t_table = frame_data.get("thrust_table", {})
    c_table = frame_data.get("current_table", {})
    
    if not t_table:
        t_table = {0.0:0.0, 1.0:0.0}
    if not c_table:
        c_table = {0.0:0.0, 1.0:0.0}
    
    try:
        t_table = {float(k): float(v) for k, v in t_table.items()}
        c_table = {float(k): float(v) for k, v in c_table.items()}
    except ValueError:
      
        print(f"[Error] Invalid table format for {airframe_name}")
        t_table = {0.0:0.0, 1.0:0.0}
        c_table = {0.0:0.0, 1.0:0.0}

    if 0.0 not in t_table:
        t_table[0.0] = 0.0
    if 0.0 not in c_table:
        c_table[0.0] = 0.0
    
    xs = tuple(sorted(t_table.keys()))
    thrust_vals = tuple(t_table[x] for x in xs)
    current_vals = tuple(c_table[x] for x in xs)
    
    # 키를 (이름, 데이터해시) 조합으로 변경하여 충돌 방지
    key = (airframe_name, xs, thrust_vals, current_vals)
    
    if key in _SPL_CACHE:
        return _SPL_CACHE[key]
    
    spl_T = PchipInterpolator(xs, thrust_vals, extrapolate=True)
    spl_I = PchipInterpolator(xs, current_vals, extrapolate=True)
    _SPL_CACHE[key] = (spl_T, spl_I)
    return spl_T, spl_I

# 모터 개수
def _nm(frame):
    if "count" in frame:
        return float(frame["count"])
    return float(frame.get("n_motors", 1))

# 표가 모터 1개 기준이면 모터 수만큼 곱해 전체 값으로 만든다
def _scale_total(frame, per_motor_value):
    n = _nm(frame)
    # tables_are_per_motor가 없으면 기본 True로 가정
    return per_motor_value * n if frame.get("tables_are_per_motor", True) else per_motor_value


# 스로틀(0~1) → 전체 추력(N), 공기 밀도 보정 포함
def compute_thrust(throttle, airframe_name="IDR-1000G", temp_c=15, altitude_m=0, frame_data=None):
    if frame_data is None:
        frame_data = AIRFRAME_LIBRARY[airframe_name]
        
    spl_T, _ = _build_splines(airframe_name, frame_data)
    thr_pm = float(spl_T(float(np.clip(throttle, 0.0, 1.0))))
    thr_total_sea = _scale_total(frame_data, thr_pm)
    return thr_total_sea * density_ratio(temp_c, altitude_m)

# 스로틀(0~1) → 전체 전류(A)
def compute_current(throttle, airframe_name="IDR-1000G", frame_data=None):
    if frame_data is None:
        frame_data = AIRFRAME_LIBRARY[airframe_name]
        
    _, spl_I = _build_splines(airframe_name, frame_data)
    I_pm = float(spl_I(float(np.clip(throttle, 0.0, 1.0))))
    return _scale_total(frame_data, I_pm)

# 필요한 추력을 내는 스로틀을 찾는다(범위 밖이면 0 또는 1)
def throttle_for_required_thrust(required_thrust_N, airframe_name="IDR-1000G",
                                 temp_c=15, altitude_m=0, frame_data=None):
    if frame_data is None:
        frame_data = AIRFRAME_LIBRARY[airframe_name]
        
    # 스로틀 → 전체 추력
    def total_thrust(thr):
        return compute_thrust(thr, airframe_name, temp_c, altitude_m, frame_data)
    
    # 0%와 100% 추력 확인
    min_thr = total_thrust(0.0)
    max_thr = total_thrust(1.0)

    if required_thrust_N <= min_thr:
        return 0.0
    if required_thrust_N >= max_thr:
        return 1.0
        
    # 목표 추력과의 차이(근 찾기용)
    def f(thr):
        return total_thrust(thr) - required_thrust_N
    return float(brentq(f, 0.0, 1.0))

# 필요한 전류를 흘리는 스로틀을 찾는다(범위 밖이면 0 또는 1)
def throttle_for_current(required_current_A, airframe_name="IDR-1000G", frame_data=None):
    if frame_data is None:
        frame_data = AIRFRAME_LIBRARY[airframe_name]
        
    # 목표 전류와의 차이(근 찾기용)
    def f(thr):
        return compute_current(thr, airframe_name, frame_data) - required_current_A
    
    min_I = compute_current(0.0, airframe_name, frame_data)
    max_I = compute_current(1.0, airframe_name, frame_data)
    
    if required_current_A >= max_I:
        return 1.0
    if required_current_A <= min_I:
        return 0.0
        
    try:
        return float(brentq(f, 0.0, 1.0))
    except ValueError:
        return 1.0 if abs(f(1.0)) < abs(f(0.0)) else 0.0

