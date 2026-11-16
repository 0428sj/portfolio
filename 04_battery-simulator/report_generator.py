# report_generator.py

# 결과 요약 HTML 리포트를 만든다
def generate_html_report(air_name, v_native_s, batt_name, ns_total, np_total,
                         total_energy_wh, v_cutoff_pack, log_data, summary_info):
    
    if not log_data or len(log_data) < 1:
        return "<p>No simulation data available.</p>"
    
    # 1. 초기 상태 추정치
    
    summary = ""
    
    # [VTOL 효율 분석 박스]
    vtol_info_html = ""
    if "vtol_opt" in summary_info:
        opt = summary_info["vtol_opt"]
        v_opt = opt.get('optimal_speed', 0)
        v_stall = opt.get('stall_speed', 0)
        margin = v_opt - v_stall
        
        wing_pct = opt.get('wing_ratio', 0) * 100
        rotor_pct = opt.get('rotor_ratio', 0) * 100
        
        if rotor_pct < 0:
            rotor_pct = 0.0
        if wing_pct > 100:
            wing_pct = 100.0

        vtol_info_html = (
            f"<div style='margin-top: 15px; border-top: 1px solid #ccc; padding-top: 5px; font-size: 0.9em; color: #333;'>"
            f"<span>&bull; VTOL Analysis (Ref): Opt Speed {v_opt:.1f} m/s, "
            f"Stall {v_stall:.1f} m/s (Margin {margin:+.1f}), "
            f"Wing Lift {wing_pct:.0f}%</span>"
            f"</div>"
        )

    # (A) HOVER 모드
    if "avg_thr_pct" in summary_info:
        is_auto = summary_info.get("is_auto", False)
        manual_thr = summary_info.get("manual_thr", 0.0)
        avg_thr_pct = summary_info.get("avg_thr_pct", 0.0)
        time_s = summary_info.get("time_s", 0.0)
        
        mode_label = "AUTO" if is_auto else "MANUAL"
        param_str = f"Avg Thr {avg_thr_pct:.1f}%" if is_auto else f"Fixed Thr {manual_thr:.1f}%"
        
        summary = (
            f"<p style='line-height:1.4;'>"
            f"<b>Hover Simulation - {mode_label} ({param_str})</b><br>"
            f"<b>Max Hover Time: <span style='color:red;'>{time_s / 60.0 :.2f} min</span></b>"
            f"</p>"
        )

    # (B) MISSION 모드
    elif "commands" in summary_info:
        result = summary_info
        commands = result.get("commands", [])
        seg_start_times = result.get("seg_start_times", {})
        v_default = result.get("v_default_mps", 0.0)
        
        status = result.get("status", "UNKNOWN")
        time_s = result.get("time_s", 0.0)
        total_dist_m = result.get("total_dist_cruise_m", 0.0)
        dist_km = total_dist_m / 1000.0
        
        segments_completed = result.get("segments_completed", 0)
        total_segs = len(commands)
        
        summary = "<p style='line-height:1.4;'><b>Route Simulation - Waypoint Mission</b><br>"
        if status == "COMPLETED":
            summary += f"<b>Result: <span style='color:green;'>[SUCCESS]</span> All {total_segs} segments cleared.</b><br>"
        else:
            summary += (
                f"<b>Result: <span style='color:red;'>[FAILURE]</span></b><br>"
                f"Stopped at segment {segments_completed + 1} / {total_segs}<br>"
                f"<b>Reason: {status}</b><br>"
            )
            
        summary += (
            f"<b>Total Flight Time: <span style='color:red;'>{time_s / 60.0 :.2f} min</span></b><br>"
            f"<b>Total Flight Distance: <span style='color:red;'>{dist_km:.2f} km</span></b><br>"
            f"<b>Energy Consumed: {result.get('total_E_consumed_Wh', 0):.1f} Wh / {total_energy_wh:.1f} Wh</b>"
            f"</p>"
        )
        
        summary += "<br><b>--- Mission Segment Log ---</b><br>"
        
        home_alt = commands[0].get('start_alt_asl', 0.0) if commands else 0.0
        summary += f"<span style='font-size:9pt;'>Home Alt: {home_alt:.1f}m (ASL)</span><br>"
        
        for i, cmd in enumerate(commands):
            seg_idx = i + 1
            cmd_type = cmd['type']
            start_t = seg_start_times.get(seg_idx, 0.0)
            if i < len(commands) - 1:
                end_t = seg_start_times.get(seg_idx + 1, time_s)
            else:
                end_t = time_s
            duration = max(0.0, end_t - start_t)
            
            detail = ""
            if cmd_type == 'FLY':
                spd = cmd.get('speed_mps')
                if not spd:
                    spd = v_default
                detail = f"Dist {cmd['dist_m']:.0f}m @ {spd:.1f}m/s"
            elif cmd_type == 'LOITER':
                detail = f"Hold {cmd['time_s']}s"
            elif cmd_type in ['TAKEOFF', 'LAND']:
                detail = f"Vert {cmd['climb_m']:.1f}m"
            
            alt_info = f"{cmd['alt_asl']:.1f}m"
            style = "color:gray;" if start_t == 0.0 and seg_idx > 1 else "color:black;"
            dur_str = f"[{duration:.0f}s]" if (start_t > 0 or seg_idx == 1) else "[-]"

            summary += (
                f"<span style='{style}'><b>Seg {seg_idx} {dur_str}: {cmd_type}</b> "
                f"- {detail} (Alt {alt_info})</span><br>"
            )

    # (C) MAX RANGE 모드
    elif "v_mps" in summary_info:
        v_mps = summary_info.get("v_mps", 0.0)
        time_s = summary_info.get("time_s", 0.0)
        total_dist_m = summary_info.get("total_dist_m", 0.0)
        
        if total_dist_m == 0 and time_s > 0:
            total_dist_m = time_s * v_mps
            
        dist_km = total_dist_m / 1000.0
        
        summary = (
            f"<p style='line-height:1.4;'><b>Route Simulation - Max Range Mode</b><br>"
            f"<b>Cruise Speed: {v_mps} m/s ({(v_mps*3.6):.0f} km/h)</b><br>"
            f"<b>Max Distance: <span style='color:red;'>{dist_km:.2f} km</span></b><br>"
            f"<b>Max Time: <span style='color:red;'>{time_s / 60.0 :.2f} min</span></b></p>"
        )

    else:
        summary = "<p><b>Unknown Simulation Mode</b></p>"

    report = (
        f"<div style='font-family: sans-serif; line-height:1.5;'>"
        f"<h3>Simulation Report</h3>"
        f"<b>Aircraft:</b> {air_name}<br>"
        f"<b>Battery:</b> {batt_name}<br>"
        f"<b>Usable Energy:</b> {total_energy_wh:.1f} Wh<br>"
        f"<hr>"
        f"{summary}"    
        f"{vtol_info_html}" 
        f"</div>"
    )
    return report

# 로그를 최대 50줄로 줄여 HTML 표로 만든다
def generate_log_table(log_data):
    if not log_data:
        return ""
    
    sample_step = max(1, len(log_data) // 50) 
    
    header = (
        f"{'Time':>7s} | {'SOC%':>6s} | {'V_Load':>7s} | "
        f"{'Current':>8s} | {'Power':>8s} | {'Thr%':>6s} | {'Thrust':>7s} | "
        f"{'Temp':>7s} | {'C-rate':>6s} | Note\n"
    )
    
    table_body = ""
    for row in log_data[:-1:sample_step]:
        temp_c = row[7] if len(row) > 7 else 0.0
        c_rate = row[8] if len(row) > 8 else 0.0
        note = row[9] if len(row) > 9 else ""
        table_body += (
            f"{row[0]:>7.0f}s | {row[1]:>6.1f}% | {row[2]:>7.2f}V | {row[3]:>8.1f}A | "
            f"{row[4]:>8.1f}W | {row[5]*100:>6.1f}% | {row[6]:>7.1f}N | "
            f"{temp_c:>6.1f}°C | {c_rate:>5.2f}C | {note}\n"
        )
    
    if len(log_data) > 0:
        row = log_data[-1]
        temp_c = row[7] if len(row) > 7 else 0.0
        c_rate = row[8] if len(row) > 8 else 0.0
        note = row[9] if len(row) > 9 else ""
        table_body += (
            f"{row[0]:>7.0f}s | {row[1]:>6.1f}% | {row[2]:>7.2f}V | {row[3]:>8.1f}A | "
            f"{row[4]:>8.1f}W | {row[5]*100:>6.1f}% | {row[6]:>7.1f}N | "
            f"{temp_c:>6.1f}°C | {c_rate:>5.2f}C | {note}\n"
        )
    
    return (
        f"\n<b style='line-height:1.5;'>--- Simulation Log (Time | SOC | Voltage | Current | Power | Throttle | Thrust | Temp | C-rate | Note) ---</b>"
        f"<pre style='line-height:1.2; font-size: 9pt; background-color: #f0f0f0; padding: 5px;'>"
        f"{header}"
        f"{'-' * (len(header) + 20)}\n"
        f"{table_body}"
        f"</pre>"
    )