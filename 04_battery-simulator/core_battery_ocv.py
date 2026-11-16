# 셀 OCV(개방전압)–SOC 곡선 표와 비열 값
from scipy.interpolate import interp1d

OCV_LIBRARY = {
    "neo": {
        "soc": [
            0.00, 0.05, 0.10, 0.20, 0.30, 0.40, 0.50,
            0.60, 0.70, 0.80, 0.90, 0.95, 1.00
        ],
        "v":   [
            3.00, 3.12, 3.23, 3.35, 3.47, 3.55, 3.62,
            3.70, 3.78, 3.88, 4.00, 4.10, 4.20
        ],
        "specific_heat": 900.0,  # [J/kg·K]
    },

    "lipo": {
        "soc": [
            0.00, 0.05, 0.10, 0.20, 0.30, 0.40, 0.50,
            0.60, 0.70, 0.80, 0.90, 0.95, 1.00
        ],
        "v": [
            3.00, 3.18, 3.35, 3.55, 3.63, 3.70, 3.75,
            3.80, 3.85, 3.90, 4.05, 4.12, 4.20
        ],
        "specific_heat": 1000.0,  # [J/kg·K]
    },

    "liion": {
        "soc": [
            0.0, 0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 
            0.6, 0.7, 0.8, 0.9, 0.95, 1.0
        ],
        "v": [
            3.10, 3.38, 3.52, 3.63, 3.72, 3.78, 3.82,
            3.88, 3.93, 3.98, 4.08, 4.13, 4.20
        ],
        "specific_heat": 950.0,  # [J/kg·K]
    },
    "polaris": {
        "soc": [
            0.00, 0.05, 0.10, 0.15, 0.20, 0.30, 0.40, 
            0.50, 0.60, 0.70, 0.80, 0.90, 0.95, 1.00
        ],
        "v": [
            2.70, 3.05, 3.25, 3.38, 3.45, 3.56, 3.65, 
            3.72, 3.80, 3.89, 3.98, 4.08, 4.14, 4.20
        ],
        "specific_heat": 920.0,
    }
}

# 셀 종류별 SOC→OCV 보간 함수(없는 종류면 neo)
def get_ocv_curve(kind="neo"):

    data = OCV_LIBRARY.get(kind)
    if data is None:
        data = OCV_LIBRARY["neo"]
    
    volt_key = "v" if "v" in data else "voltage"
    return interp1d(
        data["soc"], data[volt_key],
        kind="cubic", fill_value="extrapolate"
    )


# 셀 종류별 비열(J/kg·K), 없으면 950
def get_specific_heat(kind="neo"):

    data = OCV_LIBRARY.get(kind)
    if data is None:
        return 950.0  # 기본값
    return data.get("specific_heat", 950.0)