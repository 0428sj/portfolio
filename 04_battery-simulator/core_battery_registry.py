# core_battery_registry.py
import json
import os
import sys
from core_battery_params import BATTERY_LIBRARY
from core_battery_ocv import OCV_LIBRARY

DEFAULT_BATTERIES = set(BATTERY_LIBRARY.keys())


# 저장 기준 폴더(exe 로 묶였으면 exe 옆, 아니면 코드 옆)
def get_base_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable) # exe 파일 옆
    else:
        return os.path.dirname(os.path.abspath(__file__)) # 파이썬 스크립트 옆

# 저장 경로를 exe 파일 옆의 'batteries' 폴더로 지정
REGISTRY_PATH = os.path.join(get_base_dir(), "batteries")

# batteries 폴더가 없으면 만든다
def ensure_dir():
    if not os.path.exists(REGISTRY_PATH):
        os.makedirs(REGISTRY_PATH)

# 사용자 배터리를 메모리와 json 파일에 추가한다(기본 배터리 덮어쓰기 금지)
def add_battery(name, params, custom_soc=None, custom_volt=None):
    ensure_dir()
    if name in DEFAULT_BATTERIES:
        raise ValueError(f"'{name}' is a default battery and cannot be overwritten.")
        
    BATTERY_LIBRARY[name] = params
    ocv_data = {}
    ocv_kind = params.get("ocv_kind", "neo")

    if ocv_kind == "Custom" and custom_soc and custom_volt:
        ocv_data["soc"] = custom_soc
        ocv_data["voltage"] = custom_volt
        params["ocv_kind"] = name 
        OCV_LIBRARY[name] = ocv_data 
    else:
        ocv_data = OCV_LIBRARY.get(ocv_kind, {}) 

    pack = {"params": params, "ocv": ocv_data, "resistance": {}}
    fpath = os.path.join(REGISTRY_PATH, f"{name}.json")
    with open(fpath, "w", encoding="utf-8") as f:
        json.dump(pack, f, indent=2)
    print(f"[+] Battery '{name}' saved to {fpath}")

# 사용자 배터리를 메모리와 파일에서 지운다(기본 배터리 삭제 금지)
def delete_battery(name):
    if name in DEFAULT_BATTERIES:
        raise ValueError(f"'{name}' is a default battery and cannot be deleted.")

    fpath = os.path.join(REGISTRY_PATH, f"{name}.json")
    if os.path.exists(fpath):
        os.remove(fpath)
    if name in BATTERY_LIBRARY:
        BATTERY_LIBRARY.pop(name)
    if name in OCV_LIBRARY and name not in DEFAULT_BATTERIES:
        OCV_LIBRARY.pop(name)
    print(f"[-] Battery '{name}' deleted.")

# batteries 폴더의 json 을 읽어 배터리 목록에 더한다
def load_all_batteries():
    ensure_dir()
    loaded_count = 0
    
    if os.path.exists(REGISTRY_PATH):
        for fname in os.listdir(REGISTRY_PATH):
            if fname.endswith(".json"):
                try:
                    name = fname.replace(".json", "")
                    if name in DEFAULT_BATTERIES:
                        continue
                        
                    fpath = os.path.join(REGISTRY_PATH, fname)
                    with open(fpath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if "params" in data:
                            BATTERY_LIBRARY[name] = data["params"]
                        if "ocv" in data and data["ocv"]: 
                            OCV_LIBRARY[name] = data["ocv"]
                    loaded_count += 1
                except Exception as e:
                    print(f"[WARN] Failed to load battery {fname}: {e}")
    print(f"[✓] {len(BATTERY_LIBRARY)} batteries loaded ({loaded_count} custom).")

load_all_batteries()