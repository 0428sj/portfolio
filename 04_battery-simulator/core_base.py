# core_base.py

# ──────────────────────────────
# 물리 상수
# ──────────────────────────────
G = 9.80665
R_AIR = 287.05
RHO0 = 1.225
T0 = 288.15
P0 = 101325
L = 0.0065

# ──────────────────────────────
# 단위 변환
# ──────────────────────────────
def to_kg(value_g):
    return value_g / 1000.0

# km/h → m/s
def to_mps(value_kmh):
    return value_kmh / 3.6

# ──────────────────────────────
# 대기 밀도 계산
# ──────────────────────────────
def air_density(temp_c=15.0, altitude_m=0.0):
    """표준대기 기반 공기밀도 계산"""
    T = T0 - L * altitude_m
    P = P0 * (1 - L * altitude_m / T0) ** (G / (R_AIR * L))
    rho = P / (R_AIR * (T + temp_c - 15))
    return rho

def density_ratio(temp_c=15.0, altitude_m=0.0):
    """표준밀도 대비 비율"""
    return air_density(temp_c, altitude_m) / RHO0
