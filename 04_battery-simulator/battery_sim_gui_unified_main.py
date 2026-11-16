# battery_sim_gui_unified_main.py
import sys
import os
from PyQt5.QtWidgets import (
    QApplication, QWidget, QComboBox, QLineEdit, 
    QLabel, QRadioButton, QMessageBox, QFileDialog, QToolButton, QPushButton, QGroupBox,
    QDoubleSpinBox, QCheckBox, QTextEdit
)
from PyQt5 import uic


from core_airframe import AIRFRAME_LIBRARY
from core_battery_params import BATTERY_LIBRARY

from battery_sim_controller import BatterySimController

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller가 만들어주는 임시 폴더(_MEIPASS) 경로를 확인
        base_path = sys._MEIPASS
    except Exception:
        # 패킹 안 된 상태면 그냥 현재 폴더 사용
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

# 메인 창(.ui 를 읽어 화면을 만든다)
class BatterySimWindow(QWidget):
    
    # .ui 를 불러오고 콤보·버튼을 컨트롤러에 연결한다
    def __init__(self, parent=None):
        super().__init__(parent)
        
        ui_path = resource_path("battery_sim_gui_unified.ui")
        
        if not os.path.exists(ui_path):
            # 혹시라도 없으면 에러 메시지 띄움
            QMessageBox.critical(None, "Error", f"UI file not found at:\n{ui_path}")
            raise FileNotFoundError(f"UI file not found: {ui_path}")
            
        uic.loadUi(ui_path, self)
        
        # --- 1. 위젯 매핑 (UI의 모든 컴포넌트를 self.변수로) ---
        self.cb_air = self.findChild(QComboBox, "cb_air")
        self.cb_batt = self.findChild(QComboBox, "cb_batt")
        self.cb_batt_series = self.findChild(QComboBox, "cb_batt_series")
        self.cb_batt_parallel = self.findChild(QComboBox, "cb_batt_parallel")
        self.ed_total_mass = self.findChild(QLineEdit, "ed_total_mass")
        self.lbl_air_mass = self.findChild(QLabel, "lbl_air_mass")
        self.lbl_batt_mass = self.findChild(QLabel, "lbl_batt_mass")
        self.ed_temp_c = self.findChild(QLineEdit, "ed_temp_c")
        self.ed_alt_m = self.findChild(QLineEdit, "ed_alt_m")
        self.rb_hover = self.findChild(QRadioButton, "rb_hover")
        self.rb_route = self.findChild(QRadioButton, "rb_route")
        
        self.ed_wp_path = self.findChild(QLineEdit, "ed_wp_path")
        self.btn_wp_browse = self.findChild(QToolButton, "btn_wp_browse")
        self.btn_wp_clear = self.findChild(QToolButton, "btn_wp_clear")
        
        self.btn_add_batt = self.findChild(QPushButton, "btn_add_batt")
        self.btn_del_batt = self.findChild(QPushButton, "btn_del_batt")
        self.btn_add_air = self.findChild(QPushButton, "btn_add_air")
        self.btn_del_air = self.findChild(QPushButton, "btn_del_air")
        self.btn_add_vtol = self.findChild(QPushButton, "btn_add_vtol")
        
        self.gb_hover = self.findChild(QGroupBox, "gb_hover")
        self.gb_route = self.findChild(QGroupBox, "gb_route")
        
        self.btn_solve = self.findChild(QPushButton, "btn_solve")
        self.txt_out = self.findChild(QTextEdit, "txt_out")
        self.sp_hover_thr_pct = self.findChild(QDoubleSpinBox, "sp_hover_thr_pct")
        self.sp_cruise_mps = self.findChild(QDoubleSpinBox, "sp_cruise_mps")
        self.cb_hover_auto = self.findChild(QCheckBox, "cb_hover_auto")
        
        self.rb_hover = self.findChild(QRadioButton, "rb_hover")
        self.rb_route = self.findChild(QRadioButton, "rb_route")
        self.rb_mission = self.findChild(QRadioButton, "rb_mission")

        self.gb_hover = self.findChild(QGroupBox, "gb_hover")
        self.gb_route = self.findChild(QGroupBox, "gb_route")
        self.gb_mission = self.findChild(QGroupBox, "gb_mission") 
        
        self.populate_combos()
        
        self.controller = BatterySimController(self)
        
        self.connect_signals() 
        
        self._update_hybrid_mass()
        self._update_mode_options_state()

    def populate_combos(self):
        """(View) 콤보박스를 채웁니다."""
        self.cb_air.clear()
        self.cb_air.addItems(sorted(AIRFRAME_LIBRARY.keys()))
        self.cb_batt.clear()
        self.cb_batt.addItems(sorted(BATTERY_LIBRARY.keys()))

    def connect_signals(self):
        """(View) UI 시그널을 컨트롤러의 핸들러에 연결합니다."""

        self.btn_solve.clicked.connect(self.controller.handle_solve)
        
        self.btn_add_batt.clicked.connect(self.controller.handle_add_battery)
        self.btn_del_batt.clicked.connect(self.controller.handle_delete_battery)
        self.btn_add_air.clicked.connect(self.controller.handle_add_airframe)
        self.btn_del_air.clicked.connect(self.controller.handle_delete_airframe)
        if self.btn_add_vtol:
            self.btn_add_vtol.clicked.connect(self.controller.handle_add_vtol)
        
        # GUI 내부 상태 변경 시그널
        self.cb_air.currentIndexChanged.connect(self._update_hybrid_mass)
        self.cb_batt.currentIndexChanged.connect(self._update_hybrid_mass)
        self.cb_batt_series.currentIndexChanged.connect(self._update_hybrid_mass)
        self.cb_batt_parallel.currentIndexChanged.connect(self._update_hybrid_mass)
        
        self.btn_wp_browse.clicked.connect(self.on_browse_wp)
        self.btn_wp_clear.clicked.connect(self.on_clear_wp)
        
        self.rb_hover.toggled.connect(self._update_mode_options_state)
        self.rb_route.toggled.connect(self._update_mode_options_state)
        if self.rb_mission is not None:
            self.rb_mission.toggled.connect(self._update_mode_options_state)


    def _update_mode_options_state(self):
        """(View) 모드 라디오버튼에 따라 옵션 그룹 활성화/비활성화"""
        is_hover   = self.rb_hover.isChecked()
        is_route   = self.rb_route.isChecked()     
        is_mission = bool(self.rb_mission and self.rb_mission.isChecked())

        self.gb_hover.setEnabled(is_hover)
        self.gb_route.setEnabled(is_route)
        if self.gb_mission:
            self.gb_mission.setEnabled(is_mission)

        self.sp_cruise_mps.setEnabled(is_route)
        wp_enable = is_mission
        self.ed_wp_path.setEnabled(wp_enable)
        self.btn_wp_browse.setEnabled(wp_enable)
        self.btn_wp_clear.setEnabled(wp_enable)
        self.ed_alt_m.setEnabled(not is_mission)

    def _update_hybrid_mass(self):
        """(View) 콤보박스 변경 시 무게 자동 계산"""
        try:
            air_name = self.cb_air.currentText()
            air_data = AIRFRAME_LIBRARY.get(air_name, {})
            mass_airframe = air_data.get("mass_airframe_kg", 0.0)
            self.lbl_air_mass.setText(f"{mass_airframe:.4f}")
            
            batt_name = self.cb_batt.currentText()
            p_base = BATTERY_LIBRARY.get(batt_name, {})
            mass_base = p_base.get("mass_ref_kg", 0.0)
            
            n_serial = int(self.cb_batt_series.currentText())
            n_parallel = int(self.cb_batt_parallel.currentText())
            
            mass_total_batt = mass_base * n_serial * n_parallel
            self.lbl_batt_mass.setText(f"{mass_total_batt:.4f}")
            
            mass_auto_total = mass_airframe + mass_total_batt
            self.ed_total_mass.setText(f"{mass_auto_total:.2f}")
        except Exception:
            self.lbl_air_mass.setText("Error")
            self.lbl_batt_mass.setText("Error")

    def on_browse_wp(self):
        """(View) 웨이포인트 파일 탐색기 열기"""
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Waypoint File", "", 
            "Waypoint Files (*.plan *.waypoints);;All Files (*)"
        )
        if path:
            self.ed_wp_path.setText(path)
            
    def on_clear_wp(self):
        """(View) 웨이포인트 경로 지우기"""
        self.ed_wp_path.clear()


# --- 애플리케이션 실행 (변경 없음) ---
if __name__ == "__main__":
    app = QApplication(sys.argv)
    from PyQt5.QtWidgets import QDoubleSpinBox, QCheckBox, QTextEdit
    
    window = BatterySimWindow()
    window.show()
    sys.exit(app.exec_())