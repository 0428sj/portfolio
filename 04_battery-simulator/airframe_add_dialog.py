# airframe_add_dialog.py
from PyQt5.QtWidgets import (
    QDialog, QLineEdit, QDialogButtonBox, QVBoxLayout, 
    QFormLayout, QMessageBox, QLabel
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

# 멀티콥터 기체(추력·전류 표 포함) 추가 창
class AirframeAddDialog(QDialog):
    # 입력 칸과 버튼을 배치한다
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Aircraft (with Aerodynamics)")
        self.setMinimumWidth(450)
        
        self.form = QFormLayout()
        self.ed_name = QLineEdit("My-HighSpeed-Drone")
        self.ed_v_native_s = QLineEdit("12")
        self.ed_mass_airframe = QLineEdit("7.5")
        self.ed_motor_model = QLineEdit("Custom-Motor")
        self.ed_prop_model = QLineEdit("30x10")
        self.ed_eff_shaft = QLineEdit("0.95")
        self.ed_p_avionics = QLineEdit("30.0")

        # 항력 관련
        self.ed_cd = QLineEdit("1.2")
        self.ed_area = QLineEdit("0.05")
        
        # === 신규: 배터리 노출 비율 ===
        self.ed_batt_exposure = QLineEdit("")

        self.form.addRow("Name:", self.ed_name)
        self.form.addRow("Native S-Count:", self.ed_v_native_s)
        self.form.addRow("Airframe Mass (kg):", self.ed_mass_airframe)
        self.form.addRow("Motor model:", self.ed_motor_model)
        self.form.addRow("Prop model:", self.ed_prop_model)
        self.form.addRow("eff_shaft (0-1):", self.ed_eff_shaft)
        self.form.addRow("Avionics Power (W):", self.ed_p_avionics)
        self.form.addRow("Drag Coeff (Cd):", self.ed_cd)
        self.form.addRow("Frontal Area (m²):", self.ed_area)
        self.form.addRow("Battery Exposure Ratio:", self.ed_batt_exposure)  # === 신규 ===
        
        # === 노출 비율 안내 ===
        self.lbl_exposure_tip = QLabel(
            "※ 비워두면 1.0 (100%)\n"
            "   완전 외장: 0.8~0.9 | 반매립: 0.5~0.7 | 완전 내장: 0.2~0.4"
        )
        self.lbl_exposure_tip.setStyleSheet("color: gray; font-size: 10px;")
        self.form.addRow("", self.lbl_exposure_tip)

        self.ed_thrust_table = QLineEdit("0.5:20.0, 1.0:50.0")
        self.ed_current_table = QLineEdit("0.5:8.0, 1.0:40.0")
        
        self.form.addRow("Thrust table (thr:N):", self.ed_thrust_table)
        self.form.addRow("Current table (thr:A):", self.ed_current_table)

        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

        layout = QVBoxLayout()
        layout.addLayout(self.form)
        layout.addWidget(self.buttons)
        self.setLayout(layout)

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

    # 입력을 검증해 기체를 등록하고 창을 닫는다
    def accept(self):
        try:
            name = self.ed_name.text().strip()
            if not name:
                raise ValueError("이름 필수")

            # 노출 비율: 비어있으면 None (계산 시 1.0 사용)
            batt_exposure = self._get_float_optional(self.ed_batt_exposure, default=None)
            
            # 유효성 검사 (입력했을 경우)
            if batt_exposure is not None:
                if batt_exposure < 0.0 or batt_exposure > 1.0:
                    raise ValueError("Battery Exposure Ratio는 0~1 사이 값이어야 합니다.")

            data = {
                "v_native_s": self._get_int(self.ed_v_native_s, "Native S"),
                "mass_airframe_kg": self._get_float(self.ed_mass_airframe, "Airframe Mass"),
                "motor_model": self.ed_motor_model.text(),
                "prop_model": self.ed_prop_model.text(),
                "eff_shaft": self._get_float(self.ed_eff_shaft, "eff_shaft"),
                "p_avionics_w": self._get_float(self.ed_p_avionics, "Avionics Power"),
                "cd": self._get_float(self.ed_cd, "Drag Coeff"),
                "frontal_area": self._get_float(self.ed_area, "Frontal Area"),
                "n_motors": 4, 
                "tables_are_per_motor": True, 
            }
            
            # 노출 비율 추가 (입력했을 때만)
            if batt_exposure is not None:
                data["batt_exposure_ratio"] = batt_exposure
            
            data["thrust_table"] = parse_table(self.ed_thrust_table.text())
            data["current_table"] = parse_table(self.ed_current_table.text())
            if not data["thrust_table"] or not data["current_table"]: 
                raise ValueError("테이블 필수")

            add_airframe(name=name, data=data)
            super().accept() 

        except Exception as e:
            QMessageBox.warning(self, "오류", f"실패: {e}")