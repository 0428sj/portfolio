# battery_add_dialog.py
from PyQt5.QtWidgets import (
    QDialog, QLineEdit, QRadioButton, 
    QDialogButtonBox, QVBoxLayout, QFormLayout, 
    QLabel, QGroupBox, QMessageBox, QHBoxLayout
)
from core_battery_registry import add_battery

# 배터리 추가 창
class BatteryAddDialog(QDialog):
    # 입력 칸과 버튼을 배치한다
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Battery")
        self.setMinimumWidth(450)
        
        self.form = QFormLayout()
        self.ed_name = QLineEdit("My-6S-22Ah-Custom")
        self.ed_ns = QLineEdit("6")
        self.ed_np = QLineEdit("1")
        self.ed_v_nom = QLineEdit("3.7")
        self.ed_cap_ah = QLineEdit("22.0")
        self.ed_f_usable = QLineEdit("0.85")
        self.ed_edensity = QLineEdit("200.0")
        self.ed_r_cell = QLineEdit("0.0020")
        self.ed_v_cutoff = QLineEdit("3.0")
        self.ed_mass_ref = QLineEdit("2.5")
        self.ed_surface_area = QLineEdit("")
        self.ed_max_c_rate = QLineEdit("")
        self.ed_peak_c_rate = QLineEdit("")

        self.form.addRow("Name:", self.ed_name)
        self.form.addRow("Cells (ns):", self.ed_ns)
        self.form.addRow("Parallel (np):", self.ed_np)
        self.form.addRow("Nominal V/cell (V):", self.ed_v_nom)
        self.form.addRow("Capacity (Ah):", self.ed_cap_ah)
        self.form.addRow("Usable fraction (0-1):", self.ed_f_usable)
        self.form.addRow("Energy density (Wh/kg):", self.ed_edensity)
        self.form.addRow("Cell resistance (Ω):", self.ed_r_cell)
        self.form.addRow("Cutoff V/cell (V):", self.ed_v_cutoff)
        self.form.addRow("Battery Mass (kg):", self.ed_mass_ref)
        self.form.addRow("Surface Area (m²):", self.ed_surface_area)
        
        # 표면적 안내 라벨
        self.lbl_surface_tip = QLabel("※ 비워두면 질량 기반 자동 추정")
        self.lbl_surface_tip.setStyleSheet("color: gray; font-size: 10px;")
        self.form.addRow("", self.lbl_surface_tip)
        
        # C-rate 입력칸
        self.form.addRow("Max C-rate:", self.ed_max_c_rate)
        self.form.addRow("Peak C-rate:", self.ed_peak_c_rate)
        
        # C-rate 안내 라벨
        self.lbl_crate_tip = QLabel("※ 비워두면 C-rate 검증 안 함 (스펙시트 참고)")
        self.lbl_crate_tip.setStyleSheet("color: gray; font-size: 10px;")
        self.form.addRow("", self.lbl_crate_tip)

        # === OCV 타입 선택 ===
        self.ocv_group = QGroupBox("OCV Type")
        self.rb_neo = QRadioButton("Neo")
        self.rb_lipo = QRadioButton("LiPo")
        self.rb_liion = QRadioButton("Li-ion")
        self.rb_polaris = QRadioButton("Polaris")
        self.rb_custom = QRadioButton("Custom")
        self.rb_lipo.setChecked(True)
        
        ocv_layout = QHBoxLayout()
        ocv_layout.addWidget(self.rb_neo)
        ocv_layout.addWidget(self.rb_lipo)
        ocv_layout.addWidget(self.rb_liion)
        ocv_layout.addWidget(self.rb_polaris)
        ocv_layout.addWidget(self.rb_custom)
        self.ocv_group.setLayout(ocv_layout)

        # === Custom OCV + 비열 입력 그룹 ===
        self.custom_ocv_group = QGroupBox("Custom OCV_Thermal Data")
        ocv_form_layout = QFormLayout()
        self.ed_soc_list = QLineEdit("0.0, 0.2, 0.4, 0.6, 0.8, 1.0")
        self.ed_volt_list = QLineEdit("3.0, 3.3, 3.5, 3.7, 3.9, 4.2")
        self.ed_specific_heat = QLineEdit("950.0")
        
        ocv_form_layout.addRow("SOC list:", self.ed_soc_list)
        ocv_form_layout.addRow("Volt list:", self.ed_volt_list)
        ocv_form_layout.addRow("Specific Heat (J/kg·K):", self.ed_specific_heat)
        
        # 비열 안내 라벨
        self.lbl_heat_tip = QLabel("※ LiPo ~1000, Li-ion ~950, Neo ~900")
        self.lbl_heat_tip.setStyleSheet("color: gray; font-size: 10px;")
        ocv_form_layout.addRow("", self.lbl_heat_tip)
        
        self.custom_ocv_group.setLayout(ocv_form_layout)
        
        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

        layout = QVBoxLayout()
        layout.addLayout(self.form)
        layout.addWidget(self.ocv_group)
        layout.addWidget(self.custom_ocv_group)
        layout.addWidget(self.buttons)
        self.setLayout(layout)
        
        # 시그널 연결
        self.rb_neo.toggled.connect(self._update_ocv_state)
        self.rb_lipo.toggled.connect(self._update_ocv_state)
        self.rb_liion.toggled.connect(self._update_ocv_state)
        self.rb_polaris.toggled.connect(self._update_ocv_state)
        self.rb_custom.toggled.connect(self._update_ocv_state)
        self._update_ocv_state()

    def _update_ocv_state(self):
        """Custom 선택 시에만 OCV/비열 입력창 활성화"""
        is_custom = self.rb_custom.isChecked()
        self.custom_ocv_group.setEnabled(is_custom)

    # "3.0, 3.5, 4.2" 형식 문자열을 실수 리스트로 바꾼다
    def parse_list(self, text):
        try:
            return [float(x.strip()) for x in text.split(',') if x.strip()]
        except BaseException:
            raise ValueError("리스트 형식이 잘못되었습니다. (예: 3.0, 3.5, 4.2)")

    # 입력 칸 값을 실수로 읽고, 비었거나 숫자가 아니면 오류를 낸다
    def _get_float(self, widget, name):
        text = widget.text().strip()
        if not text: 
            raise ValueError(f"'{name}' 값이 비어있습니다.")
        try:
            return float(text)
        except ValueError:
            raise ValueError(f"'{name}' 항목에는 숫자만 입력해야 합니다.")

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
            raise ValueError(f"'{name}' 항목에는 정수만 입력해야 합니다.")

    # 입력을 검증해 배터리를 등록하고 창을 닫는다
    def accept(self):
        try:
            name_txt = self.ed_name.text().strip()
            if not name_txt: 
                raise ValueError("이름은 필수입니다.")

            mass_ref = self._get_float(self.ed_mass_ref, "Mass")
            
            # 표면적: 입력 없으면 None (나중에 자동 추정)
            surface_area = self._get_float_optional(self.ed_surface_area, default=None)
            
            # C-rate: 입력 없으면 None (검증 안 함)
            max_c_rate = self._get_float_optional(self.ed_max_c_rate, default=None)
            peak_c_rate = self._get_float_optional(self.ed_peak_c_rate, default=None)

            params = {
                "name": name_txt,
                "ns": self._get_int(self.ed_ns, "Cells (ns)"),
                "np": self._get_int(self.ed_np, "Parallel (np)"),
                "v_cell_nom": self._get_float(self.ed_v_nom, "Nominal V"),
                "cap_ah": self._get_float(self.ed_cap_ah, "Capacity"),
                "f_usable": self._get_float(self.ed_f_usable, "Usable frac"),
                "energy_density_wh_per_kg": self._get_float(self.ed_edensity, "Energy Density"),
                "r_cell_ohm": self._get_float(self.ed_r_cell, "Cell R"),
                "v_cutoff_cell": self._get_float(self.ed_v_cutoff, "Cutoff V"),
                "mass_ref_kg": mass_ref,
            }
            
            # 표면적 추가 (입력했을 때만)
            if surface_area is not None:
                params["surface_area_m2"] = surface_area
            
            # C-rate 추가 (입력했을 때만)
            if max_c_rate is not None:
                params["max_c_rate"] = max_c_rate
            if peak_c_rate is not None:
                params["peak_c_rate"] = peak_c_rate

            custom_soc = None
            custom_volt = None
            custom_specific_heat = None
            
            # OCV 종류 결정
            if self.rb_neo.isChecked(): 
                params["ocv_kind"] = "neo"
            elif self.rb_lipo.isChecked(): 
                params["ocv_kind"] = "lipo"
            elif self.rb_liion.isChecked(): 
                params["ocv_kind"] = "liion"
            elif self.rb_polaris.isChecked(): 
                params["ocv_kind"] = "polaris"
            else:  # Custom
                params["ocv_kind"] = "Custom"
                custom_soc = self.parse_list(self.ed_soc_list.text())
                custom_volt = self.parse_list(self.ed_volt_list.text())
                custom_specific_heat = self._get_float(self.ed_specific_heat, "Specific Heat")
                
                if len(custom_soc) != len(custom_volt) or len(custom_soc) < 2:
                    raise ValueError("Custom OCV 리스트 길이가 다르거나 너무 짧습니다.")
                
                # Custom 비열 저장
                params["specific_heat"] = custom_specific_heat

            add_battery(
                name=params["name"], 
                params=params, 
                custom_soc=custom_soc, 
                custom_volt=custom_volt
            )
            super().accept() 

        except Exception as e:
            QMessageBox.warning(self, "입력 오류", f"{e}")