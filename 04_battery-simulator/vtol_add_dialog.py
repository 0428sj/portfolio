# vtol_add_dialog.py
from PyQt5.QtWidgets import (
    QDialog, QLineEdit, QDialogButtonBox, QVBoxLayout, 
    QFormLayout, QMessageBox, QLabel, QGroupBox, QScrollArea, QWidget
)
from core_airframe_registry import add_airframe

# "0.5:20.0, 1.0:50.0" 형식 문자열을 {스로틀: 값} 표로 바꾼다
def parse_table(text):
    table = {}
    if not text.strip():
        return table
    try:
        pairs = text.split(',')
        for pair in pairs:
            key, value = pair.split(':')
            table[float(key.strip())] = float(value.strip())
    except BaseException:
        raise ValueError("테이블 형식 오류 (예: 0.5:20.0, 1.0:50.0)")
    return table

# VTOL 기체(호버·순항 특성) 추가 창
class VTOLAddDialog(QDialog):
    # 입력 칸과 버튼을 배치한다
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add VTOL Aircraft")
        self.setMinimumWidth(500)
        self.setMinimumHeight(700)
        
        self.main_layout = QVBoxLayout()
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)

        # --- [1] 공통 스펙 ---
        self.gb_common = QGroupBox("1. Common Specifications")
        form_common = QFormLayout()
        
        self.ed_name = QLineEdit("My-VTOL-X")
        self.ed_v_native_s = QLineEdit("12")
        self.ed_mass_airframe = QLineEdit("10.0") 
        self.ed_p_avionics = QLineEdit("40.0")
        
        # 공기역학
        self.ed_cd = QLineEdit("0.22")
        self.ed_cl = QLineEdit("0.8")
        self.ed_stall = QLineEdit("15.0")
        self.ed_area = QLineEdit("0.2")
        self.ed_wing_area = QLineEdit("0.7")
        
        # === 신규: 배터리 노출 비율 ===
        self.ed_batt_exposure = QLineEdit("")

        form_common.addRow("Name:", self.ed_name)
        form_common.addRow("Native S-Count:", self.ed_v_native_s)
        form_common.addRow("Airframe Mass (kg):", self.ed_mass_airframe)
        form_common.addRow("Avionics Power (W):", self.ed_p_avionics)
        
        form_common.addRow("Drag Coeff (Cd):", self.ed_cd)
        form_common.addRow("Lift Coeff (CL):", self.ed_cl)
        form_common.addRow("Stall Speed (m/s):", self.ed_stall)
        form_common.addRow("Frontal Area (m²):", self.ed_area)
        form_common.addRow("Wing Area (m²):", self.ed_wing_area)
        form_common.addRow("Battery Exposure Ratio:", self.ed_batt_exposure)  # === 신규 ===
        
        # === 노출 비율 안내 ===
        self.lbl_exposure_tip = QLabel(
            "※ 비워두면 1.0 (100%)\n"
            "   완전 외장: 0.8~0.9 | 반매립: 0.5~0.7 | 완전 내장: 0.2~0.4"
        )
        self.lbl_exposure_tip.setStyleSheet("color: gray; font-size: 10px;")
        form_common.addRow("", self.lbl_exposure_tip)
        
        self.gb_common.setLayout(form_common)
        self.content_layout.addWidget(self.gb_common)

        # --- [2] 호버링 모터 ---
        self.gb_hover = QGroupBox("2. Hover Propulsion")
        self.gb_hover.setCheckable(True) 
        self.gb_hover.setChecked(True)   
        
        form_hover = QFormLayout()
        self.ed_h_count = QLineEdit("4")
        self.ed_h_motor = QLineEdit("MN505")
        self.ed_h_prop = QLineEdit("22x6")
        self.ed_h_eff = QLineEdit("0.90")
        self.ed_h_thrust = QLineEdit("0.5:20.0, 1.0:50.0")
        self.ed_h_current = QLineEdit("0.5:8.0, 1.0:40.0")
        
        form_hover.addRow("Motor Count:", self.ed_h_count)
        form_hover.addRow("Motor Model:", self.ed_h_motor)
        form_hover.addRow("Prop Model:", self.ed_h_prop)
        form_hover.addRow("Efficiency (0-1):", self.ed_h_eff)
        form_hover.addRow("Thrust Table (kg->N auto):", self.ed_h_thrust)
        form_hover.addRow("Current Table (A):", self.ed_h_current)
        
        self.gb_hover.setLayout(form_hover)
        self.content_layout.addWidget(self.gb_hover)

        # --- [3] 크루즈 모터 ---
        self.gb_cruise = QGroupBox("3. Cruise Propulsion")
        self.gb_cruise.setCheckable(True)
        self.gb_cruise.setChecked(True)
        
        form_cruise = QFormLayout()
        self.ed_c_count = QLineEdit("1")
        self.ed_c_motor = QLineEdit("AT4130")
        self.ed_c_prop = QLineEdit("18x10")
        self.ed_c_eff = QLineEdit("0.95")
        self.ed_c_thrust = QLineEdit("0.5:15.0, 1.0:40.0")
        self.ed_c_current = QLineEdit("0.5:5.0, 1.0:30.0")
        
        form_cruise.addRow("Motor Count:", self.ed_c_count)
        form_cruise.addRow("Motor Model:", self.ed_c_motor)
        form_cruise.addRow("Prop Model:", self.ed_c_prop)
        form_cruise.addRow("Efficiency (0-1):", self.ed_c_eff)
        form_cruise.addRow("Thrust Table (kg->N auto):", self.ed_c_thrust)
        form_cruise.addRow("Current Table (A):", self.ed_c_current)
        
        self.gb_cruise.setLayout(form_cruise)
        self.content_layout.addWidget(self.gb_cruise)

        self.scroll.setWidget(self.content_widget)
        self.main_layout.addWidget(self.scroll)

        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.main_layout.addWidget(self.buttons)
        
        self.setLayout(self.main_layout)

    # 입력 칸 값을 실수로 읽고, 비었거나 숫자가 아니면 오류를 낸다
    def _get_float(self, widget, name):
        text = widget.text().strip()
        if not text:
            raise ValueError(f"'{name}' 값이 비어있습니다.")
        try:
            return float(text)
        except ValueError:
            raise ValueError(f"'{name}' 항목에는 숫자만 입력해야 합니다.\n(입력된 값: '{text}')")

    def _get_float_optional(self, widget, default=None):
        """선택적 입력 - 비어있으면 default 반환"""
        text = widget.text().strip()
        if not text:
            return default
        try:
            return float(text)
        except ValueError:
            return default

    # 입력 칸 값을 정수로 읽고, 비었거나 숫자가 아니면 오류를 낸다
    def _get_int(self, widget, name):
        text = widget.text().strip()
        if not text:
            raise ValueError(f"'{name}' 값이 비어있습니다.")
        try:
            return int(text)
        except ValueError:
            raise ValueError(f"'{name}' 항목에는 정수만 입력해야 합니다.\n(입력된 값: '{text}')")

    # 입력을 검증해 VTOL 기체를 등록하고 창을 닫는다
    def accept(self):
        try:
            name = self.ed_name.text().strip()
            if not name:
                raise ValueError("기체 이름은 필수입니다.")

            # 노출 비율: 비어있으면 None (계산 시 1.0 사용)
            batt_exposure = self._get_float_optional(self.ed_batt_exposure, default=None)
            
            # 유효성 검사 (입력했을 경우)
            if batt_exposure is not None:
                if batt_exposure < 0.0 or batt_exposure > 1.0:
                    raise ValueError("Battery Exposure Ratio는 0~1 사이 값이어야 합니다.")

            data = {
                "type": "vtol",
                "v_native_s": self._get_int(self.ed_v_native_s, "Native S"),
                "mass_airframe_kg": self._get_float(self.ed_mass_airframe, "Airframe Mass"),
                "p_avionics_w": self._get_float(self.ed_p_avionics, "Avionics Power"),
                
                "cd": self._get_float(self.ed_cd, "Drag Coeff"),
                "cl": self._get_float(self.ed_cl, "Lift Coeff"),
                "stall_speed": self._get_float(self.ed_stall, "Stall Speed"),
                "frontal_area": self._get_float(self.ed_area, "Frontal Area"),
                "wing_area": self._get_float(self.ed_wing_area, "Wing Area"),
                
                "tables_are_per_motor": True
            }
            
            # 노출 비율 추가 (입력했을 때만)
            if batt_exposure is not None:
                data["batt_exposure_ratio"] = batt_exposure

            if self.gb_hover.isChecked():
                data["hover"] = {
                    "enabled": True,
                    "count": self._get_int(self.ed_h_count, "Hover Motor Count"),
                    "motor": self.ed_h_motor.text(),
                    "prop": self.ed_h_prop.text(),
                    "eff_shaft": self._get_float(self.ed_h_eff, "Hover Efficiency"),
                    "thrust_table": parse_table(self.ed_h_thrust.text()),
                    "current_table": parse_table(self.ed_h_current.text())
                }
            else:
                data["hover"] = {"enabled": False}

            if self.gb_cruise.isChecked():
                data["cruise"] = {
                    "enabled": True,
                    "count": self._get_int(self.ed_c_count, "Cruise Motor Count"),
                    "motor": self.ed_c_motor.text(),
                    "prop": self.ed_c_prop.text(),
                    "eff_shaft": self._get_float(self.ed_c_eff, "Cruise Efficiency"),
                    "thrust_table": parse_table(self.ed_c_thrust.text()),
                    "current_table": parse_table(self.ed_c_current.text())
                }
            else:
                data["cruise"] = {"enabled": False}
            
            if not data["hover"]["enabled"] and not data["cruise"]["enabled"]:
                raise ValueError("호버링 또는 크루즈 중 적어도 하나는 활성화해야 합니다.")

            add_airframe(name=name, data=data)
            super().accept()

        except Exception as e:
            QMessageBox.warning(self, "입력 오류", f"{e}")