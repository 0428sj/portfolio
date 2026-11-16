# battery_sim_controller.py
import os
import traceback
from PyQt5.QtWidgets import QMessageBox, QDialog

from core_airframe import AIRFRAME_LIBRARY
from core_battery_params import BATTERY_LIBRARY, usable_energy_scaled_Wh
from core_airframe_registry import delete_airframe
from core_battery_registry import delete_battery 
from core_path_loader import load_qgc_mission_commands 
from hover_unified import simulate_hover
from route_max_range import simulate_route_physics
from route_mission import simulate_route_segmented 
from core_physics_engine import find_vtol_optimal_speed

from battery_add_dialog import BatteryAddDialog
from airframe_add_dialog import AirframeAddDialog
from vtol_add_dialog import VTOLAddDialog
from plot_generator import save_plot_to_file
from report_generator import generate_html_report, generate_log_table 

# 화면 입력을 모아 시뮬레이션을 돌리고 결과를 화면에 쓰는 컨트롤러
class BatterySimController:
    # 화면(view)을 붙잡아 둔다
    def __init__(self, view):
        self.view = view 

    # [계산] 버튼: 입력 수집 → 시뮬레이션 → 리포트·그래프 출력
    def handle_solve(self):
        self.view.txt_out.clear() 
        try:
            # 1. 입력값 수집 및 검증
            inputs = self._gather_common_inputs()
            
            # 2. 시뮬레이션 실행
            results = self._run_simulation_logic(inputs)
            
            # 3. 결과 리포트 출력
            self._generate_output_report(results, inputs)

        except ValueError as ve:
            QMessageBox.warning(self.view, "입력 오류", str(ve))
            self.view.txt_out.setText(f"<span style='color:red;'>[입력 오류] {ve}</span>")
            
        except Exception as e:
            self.view.txt_out.append(f"\n--- 시스템 오류 발생 ---\n{e}")
            self.view.txt_out.append(traceback.format_exc())
            QMessageBox.critical(self.view, "시스템 오류", f"예기치 못한 오류 발생: {e}")
        finally:
            self.view.txt_out.moveCursor(self.view.txt_out.textCursor().Start)

    # 입력 칸 값을 실수로 읽고 범위를 검사한다
    def _validate_input(self, widget, name, min_val=None, max_val=None):
        text = widget.text().strip()
        if not text:
            raise ValueError(f"'{name}' 항목이 비어있습니다.")
        
        try:
            val = float(text)
        except ValueError:
            raise ValueError(f"'{name}' 항목에는 숫자만 입력해야 합니다.\n(입력된 값: '{text}')")
            
        if min_val is not None and val < min_val:
             raise ValueError(f"'{name}' 값은 최소 {min_val} 이상이어야 합니다.")
             
        if max_val is not None and val > max_val:
             raise ValueError(f"'{name}' 값은 최대 {max_val} 이하여야 합니다.")
             
        return val

    # 기체·배터리·조건 입력을 하나의 dict 로 모은다
    def _gather_common_inputs(self):
        inputs = {}
        inputs["air_name"] = self.view.cb_air.currentText()
        inputs["batt_name"] = self.view.cb_batt.currentText()
        
        inputs["n_serial"] = int(self.view.cb_batt_series.currentText())
        inputs["n_parallel"] = int(self.view.cb_batt_parallel.currentText())
        
        inputs["final_total_mass"] = self._validate_input(
            self.view.ed_total_mass, "Total Mass", min_val=0.1, max_val=500.0
        )
        inputs["temp_c"] = self._validate_input(
            self.view.ed_temp_c, "Temperature", min_val=-40.0, max_val=60.0
        )
        
        if not (self.view.rb_mission and self.view.rb_mission.isChecked()):
             inputs["altitude_m"] = self._validate_input(
                self.view.ed_alt_m, "Altitude", min_val=-500.0, max_val=10000.0
            )
        else:
            inputs["altitude_m"] = 0.0 

        p_base = BATTERY_LIBRARY.get(inputs["batt_name"])
        air_data = AIRFRAME_LIBRARY.get(inputs["air_name"])
        if not p_base or not air_data:
            raise ValueError("선택된 기체 또는 배터리 정보를 찾을 수 없습니다.")
            
        inputs["p_base"] = p_base
        inputs["air_data"] = air_data
        
        mass_airframe = air_data.get("mass_airframe_kg", 0.0)
        mass_total_batt = p_base.get("mass_ref_kg", 0.0) * inputs["n_serial"] * inputs["n_parallel"]
        
        if inputs["final_total_mass"] < (mass_airframe + mass_total_batt - 0.001): 
            raise ValueError(
                f"입력한 총 중량({inputs['final_total_mass']}kg)이 "
                f"기체+배터리 순수 무게({mass_airframe + mass_total_batt:.2f}kg)보다 가볍습니다.\n"
                "탑재중량(Payload)을 고려해 더 큰 값을 입력하세요."
            )

        p_scaled = p_base.copy()
        p_scaled["ns"] = p_base.get("ns", 6) * inputs["n_serial"]
        p_scaled["np"] = p_base.get("np", 1) * inputs["n_parallel"]
        p_scaled["cap_ah"] = p_base.get("cap_ah", 0) * inputs["n_parallel"]
        inputs["p_scaled"] = p_scaled
        
        v_native_s = air_data.get("v_native_s", 0)
        ns_total = p_scaled["ns"]
        
        if v_native_s != ns_total:
            msg = (
                f"[경고] 모터({v_native_s}S)와 배터리({ns_total}S) 전압 불일치\n\n"
                f"권장 전압과 다른 배터리를 사용하려고 합니다.\n"
                f"그대로 진행하시겠습니까?"
            )
            reply = QMessageBox.question(
                self.view, "전압 설정 경고", msg, 
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if reply == QMessageBox.No:
                raise ValueError("전압 불일치로 인해 시뮬레이션을 취소했습니다.")
        
        inputs["v_native_s"] = v_native_s
        inputs["ns_total"] = ns_total
        
        inputs["total_energy_wh"] = usable_energy_scaled_Wh(p_scaled, mass_total_batt)
        inputs["p_avionics_w"] = air_data.get("p_avionics_w", 25.0)
        inputs["v_cutoff_cell"] = p_scaled.get("v_cutoff_cell", 3.0)
        inputs["v_cutoff_pack"] = inputs["v_cutoff_cell"] * ns_total
        
        return inputs

    # 선택한 모드(호버·최대 거리·미션)에 맞는 시뮬레이션을 돌린다
    def _run_simulation_logic(self, inputs):
        sim_result = {} 
        mode = ""
        is_auto = False
        
        # 1. Hover
        if self.view.rb_hover.isChecked():
            mode = 'hover'
            is_auto = self.view.cb_hover_auto.isChecked()
            manual_thr = self.view.sp_hover_thr_pct.value()
            
            sim_result = simulate_hover(
                batt_params=inputs["p_scaled"], airframe_name=inputs["air_name"],
                total_usable_energy_Wh=inputs["total_energy_wh"],
                total_mass_kg=inputs["final_total_mass"], is_auto=is_auto,
                manual_throttle_pct=manual_thr, p_avionics_w=inputs["p_avionics_w"],
                temp_c=inputs["temp_c"], altitude_m=inputs["altitude_m"],
                v_cutoff_cell=inputs["v_cutoff_cell"]
            )
            
            avg_thr_pct = 0.0
            if is_auto and sim_result["log_data"]:
                try:
                    throttles = [row[5] for row in sim_result["log_data"]]
                    avg_thr_pct = (sum(throttles) / len(throttles)) * 100.0
                except BaseException:
                    pass
            sim_result["is_auto"] = is_auto
            sim_result["manual_thr"] = manual_thr
            sim_result["avg_thr_pct"] = avg_thr_pct

        # 2. Max Range
        elif self.view.rb_route.isChecked():
            mode = 'route_max_range'
            is_auto = False
            v_cruise_mps = self.view.sp_cruise_mps.value()

            sim_result = simulate_route_physics(
                batt_params=inputs["p_scaled"], airframe_name=inputs["air_name"],
                total_usable_energy_Wh=inputs["total_energy_wh"],
                total_mass_kg=inputs["final_total_mass"], v_mps=v_cruise_mps,
                p_avionics_w=inputs["p_avionics_w"], temp_c=inputs["temp_c"],
                altitude_m=inputs["altitude_m"],
                v_cutoff_cell=inputs["v_cutoff_cell"]
            )
            sim_result["v_mps"] = v_cruise_mps

        # 3. Mission
        elif self.view.rb_mission is not None and self.view.rb_mission.isChecked():
            mode = 'route_segmented'
            is_auto = False
            wp_path = self.view.ed_wp_path.text().strip()
            if not wp_path or not os.path.exists(wp_path):
                raise ValueError("유효한 Waypoints 파일을 선택해야 합니다.")
            
            v_cruise_mps = self.view.sp_cruise_mps.value()
            try:
                commands = load_qgc_mission_commands(wp_path)
            except ValueError as ve:
                 if "Loiter time is missing" in str(ve):
                     QMessageBox.critical(self.view, "미션 오류", "Loiter 시간 누락.")
                     return {"log_data": [], "summary_info": {}}
                 else:
                     raise
            
            if not commands:
                raise ValueError("명령어가 없습니다.")

            sim_result = simulate_route_segmented(
                batt_params=inputs["p_scaled"], airframe_name=inputs["air_name"],
                total_usable_energy_Wh=inputs["total_energy_wh"],
                total_mass_kg=inputs["final_total_mass"], commands=commands,
                v_cruise_mps=v_cruise_mps, p_avionics_w=inputs["p_avionics_w"],
                temp_c=inputs["temp_c"], v_cutoff_cell=inputs["v_cutoff_cell"]
            )
            
            seg_start_times = {}
            for row in sim_result.get("log_data", []):
                note = row[9] if len(row) > 9 else ""
                if "Seg" in str(note):
                    try:
                        idx = int(note.split()[1])
                        if idx not in seg_start_times:
                            seg_start_times[idx] = row[0]
                    except BaseException:
                        pass
            
            sim_result["seg_start_times"] = seg_start_times
            sim_result["v_default_mps"] = v_cruise_mps

        else:
            raise ValueError("모드를 선택하세요.")
        
        return {
            "log_data": sim_result.get("log_data", []),
            "summary_info": sim_result, 
            "mode": mode, 
            "is_auto": is_auto
        }

    # 결과를 HTML 리포트·로그 표·그래프 파일로 만든다
    def _generate_output_report(self, results, inputs):
        log_data = results.get("log_data", [])
        summary_info = results.get("summary_info", {})
        
        # VTOL 최적 속도 분석
        air_data = inputs["air_data"]
        air_name = inputs["air_name"]
        
        # type이 vtol이거나, 이름에 'VTOL'이 들어있으면 분석 시도
        is_vtol_check = (air_data.get("type", "").lower() == "vtol") or ("vtol" in air_name.lower())
        
        if is_vtol_check:
            try:
                opt_data = find_vtol_optimal_speed(
                    inputs["final_total_mass"], 
                    air_data, 
                    inputs["temp_c"], 
                    inputs["altitude_m"]
                )
                summary_info["vtol_opt"] = opt_data
            except Exception as e:
                self.view.txt_out.append(f"\n<b style='color:red;'>[VTOL 분석 실패] {e}</b>")

        if log_data and len(log_data) > 1:
            # HTML 리포트 생성
            report_html = generate_html_report(
                air_name=inputs["air_name"], v_native_s=inputs["v_native_s"],
                batt_name=inputs["batt_name"], ns_total=inputs["ns_total"], np_total=inputs["p_scaled"]['np'],
                total_energy_wh=inputs["total_energy_wh"], v_cutoff_pack=inputs["v_cutoff_pack"],
                log_data=log_data, summary_info=summary_info
            )
            self.view.txt_out.setHtml(report_html) 
            
            # 로그 테이블 생성 (누락됐던 부분 복구됨)
            log_table_html = generate_log_table(log_data)
            self.view.txt_out.append(log_table_html)
            
            # 그래프 저장
            saved_path = save_plot_to_file(
                log_data, inputs["v_cutoff_pack"], 
                results["mode"], results["is_auto"], 
                inputs["air_name"], inputs["batt_name"]
            )
            if saved_path:
                self.view.txt_out.append(f"\n<b style='line-height:1.5;'>[Plot] 그래프가 저장되었습니다:<br>{saved_path}</b>")
        else:
             self.view.txt_out.setText("시뮬레이션 완료되었으나 로그 데이터가 충분하지 않습니다.")

    # [배터리 추가] 버튼
    def handle_add_battery(self):
        dialog = BatteryAddDialog(self.view)
        if dialog.exec_() == QDialog.Accepted:
            QMessageBox.information(self.view, "성공", "새 배터리를 추가했습니다.")
            self.view.populate_combos()

    # [배터리 삭제] 버튼(기본 배터리는 삭제 불가)
    def handle_delete_battery(self):
        batt_name = self.view.cb_batt.currentText()
        if not batt_name:
            return
        reply = QMessageBox.question(self.view, '삭제 확인', f"'{batt_name}' 삭제?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            try:
                delete_battery(batt_name) 
                QMessageBox.information(self.view, "삭제 완료", f"'{batt_name}' 배터리를 삭제했습니다.")
                self.view.populate_combos()
            except ValueError as e: 
                QMessageBox.warning(self.view, "삭제 불가", str(e))
            except Exception as e:
                QMessageBox.critical(self.view, "오류", f"삭제 실패: {e}")

    # [기체 추가] 버튼
    def handle_add_airframe(self):
        dialog = AirframeAddDialog(self.view) 
        if dialog.exec_() == QDialog.Accepted:
            QMessageBox.information(self.view, "성공", "새 기체를 추가했습니다.")
            self.view.populate_combos()

    # [기체 삭제] 버튼(기본 기체는 삭제 불가)
    def handle_delete_airframe(self):
        air_name = self.view.cb_air.currentText()
        if not air_name:
            return
        reply = QMessageBox.question(self.view, '삭제 확인', f"'{air_name}' 삭제?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            try:
                delete_airframe(air_name) 
                QMessageBox.information(self.view, "삭제 완료", f"'{air_name}' 기체를 삭제했습니다.")
                self.view.populate_combos()
            except ValueError as e: 
                QMessageBox.warning(self.view, "삭제 불가", str(e))
            except Exception as e:
                QMessageBox.critical(self.view, "오류", f"삭제 실패: {e}")

    # [VTOL 추가] 버튼
    def handle_add_vtol(self):
        dialog = VTOLAddDialog(self.view)
        if dialog.exec_() == QDialog.Accepted:
            QMessageBox.information(self.view, "성공", "새 VTOL 기체를 추가했습니다.")
            self.view.populate_combos()