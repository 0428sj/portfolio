# plot_generator.py
import matplotlib
matplotlib.use('Agg') 
import matplotlib.pyplot as plt
import numpy as np
import os
import datetime
import sys

# 저장 기준 폴더(exe 로 묶였으면 exe 옆, 아니면 코드 옆)
def get_base_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))

# 기준 폴더 아래 하위 폴더를 만들고 경로를 돌려준다
def _ensure_dir(dir_name):
    base = get_base_dir()
    full_path = os.path.join(base, dir_name)
    if not os.path.exists(full_path):
        os.makedirs(full_path)
    return full_path

def _plot_common(ax1, time_m, v_load, v_cutoff_pack, title_str):
    """공통 플롯 설정 (전압)"""
    ax1.set_title(title_str)
    color = 'tab:blue'
    ax1.set_xlabel('Time (minutes)')
    ax1.set_ylabel('Voltage (V)', color=color)
    ax1.plot(time_m, v_load, color=color, label="V_load")
    ax1.axhline(y=v_cutoff_pack, color=color, linestyle='--', label=f"Cutoff ({v_cutoff_pack:.1f}V)")
    ax1.tick_params(axis='y', labelcolor=color)
    ax1.grid(True, linestyle=':', alpha=0.6)

def _plot_secondary(ax1, time_m, soc_pct, temps):
    """보조축 설정 (SOC 및 온도)"""
    ax2 = ax1.twinx()
    
    # SOC (초록 점선)
    color_soc = 'tab:green'
    ax2.set_ylabel('SOC (%) / Temp (°C)', color='k') 
    ax2.plot(time_m, soc_pct, color=color_soc, linestyle=':', label="SOC (%)")
    
    # 온도 (빨간 실선)
    color_temp = 'tab:red'
    ax2.plot(time_m, temps, color=color_temp, linewidth=1.5, label="Temp (°C)")
    
    # 범례 합치기
    lines, labels = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines + lines2, labels + labels2, loc='lower left')

# 그림을 저장하고 닫는다
def _save_fig(fig, filepath):
    fig.tight_layout()
    plt.savefig(filepath)
    plt.close(fig) 

# 로그로 그래프를 그려 route_plots 폴더에 저장한다
def save_plot_to_file(log_data, v_cutoff_pack, mode, is_auto, air_name, batt_name):
    print(f"[Plot] 호출됨. 모드: {mode}")
    
    if not log_data or len(log_data) < 2:
        return None 

    # 데이터 분리 (인덱스 변경됨: temp=7, c_rate=8, note=9)
    time_arr = [row[0] for row in log_data]
    soc_arr = [row[1] for row in log_data]
    v_load_arr = [row[2] for row in log_data]
    temp_arr = [row[7] if len(row) > 7 else 25.0 for row in log_data]
    
    time_m = np.array(time_arr) / 60.0
    soc_pct = np.array(soc_arr)
    v_load = np.array(v_load_arr)
    temps = np.array(temp_arr)
    
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{air_name}_{batt_name}_{timestamp}.png"
    
    fig, ax1 = plt.subplots(figsize=(10, 6))
    
    if mode == 'hover':
        target_path = _ensure_dir('hover_plots')
        filepath = os.path.join(target_path, filename)
        mode_str = "Hover (Auto)" if is_auto else "Hover (Manual)"
        _plot_common(ax1, time_m, v_load, v_cutoff_pack, f"{mode_str} - Volt & Temp")
        _plot_secondary(ax1, time_m, soc_pct, temps)
        
    elif 'route' in mode:
        target_path = _ensure_dir('route_plots')
        filepath = os.path.join(target_path, filename)
        _plot_common(ax1, time_m, v_load, v_cutoff_pack, "Route Sim - Volt & Temp")
        _plot_secondary(ax1, time_m, soc_pct, temps)
    else:
        return None
        
    _save_fig(fig, filepath)
    print(f"[Plot] 저장 완료: {filepath}")
    return filepath