# core_path_loader.py
import os
import json
import math

# 두 위경도 사이 거리(m)
def _haversine_m(lat1, lon1, lat2, lon2):
    R = 6371000.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat/2)**2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2)
    return 2 * R * math.asin(math.sqrt(a))

def load_qgc_mission_commands(path):
    """
    QGC 파일을 파싱하여 '명령어' 리스트를 반환합니다.
    속도 변경(178) 명령을 만나면 상태를 갱신하고, 이후 모든 웨이포인트에 적용합니다.
    """
    if not path or not os.path.exists(path):
        return []

    ext = os.path.splitext(path)[1].lower()
    
    raw_cmds = []  
    
    # [수정] 상태 유지 변수 (초기값 None -> 나중에 시뮬레이터 기본 속도 사용)
    active_speed_mps = None 
    
    home_asl_altitude_m = None 
    DEFAULT_ALT_AGL = 60.0

    try:
        # --- 1. JSON 파일 (.plan) 파싱 ---
        if ext == ".plan":
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            items = data.get("mission", {}).get("items", [])
            
            for it in items:
                cmd = it.get("command", 0)
                params = it.get("params", [0]*7)
                frame = it.get("frame", 3) 
                
                # [수정] CMD 178: 속도 변경 -> 상태 변수 갱신 후 유지
                if cmd == 178: 
                    # params[1]이 속도 (m/s)
                    if len(params) > 1 and params[1] > 0:
                        active_speed_mps = float(params[1])
                    continue 

                if cmd not in [16, 19, 21, 22]: 
                    continue
                
                coord = it.get("coordinate", [])
                if len(coord) < 3:
                    continue
                
                lat_raw = float(coord[0])
                lon_raw = float(coord[1])
                alt_raw = float(coord[2])
                time_s_raw = float(params[0]) if cmd == 19 and len(params) > 0 else None

                # AGL/ASL 변환
                if home_asl_altitude_m is None:
                    if frame == 0:
                        home_asl_altitude_m = alt_raw
                    else:
                        home_asl_altitude_m = 0.0 

                if cmd != 21 and alt_raw == 0.0: 
                        alt_raw = DEFAULT_ALT_AGL 

                alt_asl = alt_raw
                if frame == 3: 
                    alt_asl = home_asl_altitude_m + alt_raw
                
                if cmd == 19 and (time_s_raw is None or time_s_raw <= 0.0):
                        raise ValueError("Loiter time is missing or zero.")

                raw_cmds.append({
                    "lat": lat_raw, "lon": lon_raw, "alt_asl": alt_asl, 
                    "alt_raw": alt_raw, 
                    "speed_mps": active_speed_mps, # [핵심] 현재 유지 중인 속도 적용
                    "cmd": cmd, "time_s": time_s_raw
                })
                # [핵심] 여기서 active_speed_mps를 초기화하지 않음! (상태 유지)

        # --- 2. 텍스트 파일 (.waypoints) 파싱 ---
        else: 
            with open(path, "r", encoding="utf-8") as f:
                for ln in f:
                    ln = ln.strip()
                    if not ln or ln.upper().startswith("QGC") or ln.startswith("#"):
                        continue
                    parts = ln.replace("\t", " ").split()
                    if len(parts) < 12:
                        continue
                    
                    cmd = int(parts[3])
                    frame = int(parts[2])
                    
                    # [수정] CMD 178: 속도 변경 -> 상태 변수 갱신
                    if cmd == 178: 
                        val = float(parts[5])
                        if val > 0:
                            active_speed_mps = val
                        continue 

                    if cmd not in [16, 19, 21, 22]: 
                        continue
                        
                    lat_raw = float(parts[-4])
                    lon_raw = float(parts[-3])
                    alt_raw = float(parts[-2])
                    time_s_raw = float(parts[4]) if cmd == 19 else None

                    if home_asl_altitude_m is None:
                        if frame == 0:
                            home_asl_altitude_m = alt_raw
                        else:
                            home_asl_altitude_m = 0.0 

                    if cmd != 21 and alt_raw == 0.0: 
                         alt_raw = DEFAULT_ALT_AGL 

                    alt_asl = alt_raw
                    if frame == 3: 
                        alt_asl = home_asl_altitude_m + alt_raw
                    
                    if cmd == 19 and (time_s_raw is None or time_s_raw <= 0.0):
                         raise ValueError("Loiter time is missing or zero.")

                    if abs(lat_raw) > 90 and abs(lon_raw) <= 90:
                        lat, lon = lon_raw, lat_raw
                    else:
                        lat, lon = lat_raw, lon_raw

                    raw_cmds.append({
                        "lat": lat, "lon": lon, "alt_asl": alt_asl, 
                        "alt_raw": alt_raw, 
                        "speed_mps": active_speed_mps, # [핵심] 현재 유지 중인 속도 적용
                        "cmd": cmd, "time_s": time_s_raw
                    })
                    # [핵심] 여기서 active_speed_mps를 초기화하지 않음!

    except ValueError as ve:
        raise ve
    except Exception as e:
        raise ValueError(f"[Path Loader] Parse Error: {e}")

    if len(raw_cmds) < 1:
        return []

    # --- 3. 명령어 목록 변환 (거리 계산 등) ---
    commands = []
    last_nav = raw_cmds[0] 
    
    for i in range(1, len(raw_cmds)):
        cmd_item = raw_cmds[i]
        cmd = cmd_item['cmd']
        
        if abs(cmd_item['lat']) < 0.0001 and abs(cmd_item['lon']) < 0.0001:
            cmd_item['lat'] = last_nav['lat']
            cmd_item['lon'] = last_nav['lon']
        
        if last_nav and 'lat' in last_nav:
            cruise_dist_m = _haversine_m(last_nav['lat'], last_nav['lon'], cmd_item['lat'], cmd_item['lon'])
            climb_dist_m = cmd_item['alt_asl'] - last_nav['alt_asl']
        else:
            cruise_dist_m = 0.0
            climb_dist_m = 0.0

        base_info = {
            "alt_asl": cmd_item['alt_asl'], "alt_agl": cmd_item['alt_raw'],
            "start_alt_asl": last_nav['alt_asl']
        }

        if cmd == 16: # FLY
            commands.append({
                "type": "FLY", "cmd": 16, 
                "dist_m": cruise_dist_m, "climb_m": climb_dist_m,
                "speed_mps": cmd_item['speed_mps'], # 적용된 속도 전달
                **base_info
            })
        elif cmd == 22: # TAKEOFF
            commands.append({
                "type": "TAKEOFF", "cmd": 22, 
                "dist_m": 0.0, "climb_m": climb_dist_m, **base_info
            })
        elif cmd == 21: # LAND
            commands.append({
                "type": "LAND", "cmd": 21, 
                "dist_m": 0.0, "climb_m": climb_dist_m, **base_info
            })
        elif cmd == 19: # LOITER
            commands.append({
                "type": "LOITER", "cmd": 19, 
                "time_s": cmd_item['time_s'], **base_info
            })
            
        last_nav = cmd_item 

    return commands