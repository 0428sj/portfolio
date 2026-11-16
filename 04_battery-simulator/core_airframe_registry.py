# core_airframe_registry.py
import json
import os
import sys
from core_airframe import AIRFRAME_LIBRARY

DEFAULT_AIRFRAMES = set(AIRFRAME_LIBRARY.keys())

# 저장 기준 폴더(exe 로 묶였으면 exe 옆, 아니면 코드 옆)
def get_base_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))

# 저장 경로를 exe 파일 옆의 'airframes' 폴더로 지정
AIRFRAME_DIR = os.path.join(get_base_dir(), "airframes")

# airframes 폴더가 없으면 만든다
def ensure_dir():
    if not os.path.exists(AIRFRAME_DIR):
        os.makedirs(AIRFRAME_DIR)

# 사용자 기체를 메모리와 json 파일에 추가한다(기본 기체 덮어쓰기 금지)
def add_airframe(name, data):
    ensure_dir()
    if name in DEFAULT_AIRFRAMES:
        raise ValueError(f"'{name}' is a default airframe and cannot be overwritten.")
        
    AIRFRAME_LIBRARY[name] = data 
    fpath = os.path.join(AIRFRAME_DIR, f"{name}.json")
    with open(fpath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2) 
    print(f"[+] Airframe '{name}' saved to {fpath}")

# 사용자 기체를 메모리와 파일에서 지운다(기본 기체 삭제 금지)
def delete_airframe(name):
    if name in DEFAULT_AIRFRAMES:
        raise ValueError(f"'{name}' is a default airframe and cannot be deleted.")
        
    fpath = os.path.join(AIRFRAME_DIR, f"{name}.json")
    if os.path.exists(fpath):
        os.remove(fpath)
    if name in AIRFRAME_LIBRARY:
        AIRFRAME_LIBRARY.pop(name)
    print(f"[-] Airframe '{name}' deleted.")

# airframes 폴더의 json 을 읽어 기체 목록에 더한다
def load_all_airframes():
    ensure_dir()
    loaded_count = 0
    if os.path.exists(AIRFRAME_DIR):
        for fname in os.listdir(AIRFRAME_DIR):
            if fname.endswith(".json"):
                try:
                    name = fname.replace(".json", "")
                    if name in DEFAULT_AIRFRAMES:
                        continue
                    fpath = os.path.join(AIRFRAME_DIR, fname)
                    with open(fpath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if isinstance(data, dict):
                            AIRFRAME_LIBRARY[name] = data
                            loaded_count += 1
                except Exception as e:
                    print(f"[WARN] Failed to load {fname}: {e}")
    print(f"[✓] {len(AIRFRAME_LIBRARY)} airframes loaded ({loaded_count} custom).")

load_all_airframes()