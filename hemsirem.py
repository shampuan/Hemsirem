#!/usr/bin/env python3

import sys
import os
import json
from datetime import datetime, date, timedelta
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QPushButton, QTabWidget, QLineEdit,
                             QMessageBox, QGroupBox, QRadioButton, QDialog, QSizePolicy, QAbstractSpinBox,
                             QSpacerItem, QSystemTrayIcon, QMenu, QAction, QButtonGroup, QFormLayout)
from PyQt5.QtCore import Qt, QTimer, QTime, QDate, QUrl
from PyQt5.QtGui import QIcon, QPixmap, QFontMetrics
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent

class HemşiremApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Hemşirem")

        self.data_dir = os.path.join(os.path.expanduser("~"), ".Hemşirem")
        os.makedirs(self.data_dir, exist_ok=True)
        self.data_file = os.path.join(self.data_dir, "hemsiremdata.json")

        self.medications = self.load_medications()
        
        # self.days ve self.time_slots tanımlamaları buraya taşındı
        self.days = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
        self.time_slots = ["Sabah", "Öğleden önce", "Öğle", "İkindi", "Akşam", "Gece"]

        self.check_and_reset_weekly() # <-- Şimdi 'self.days' tanımlanmış durumda

        self.current_day_index = datetime.now().weekday() # 0 = Pazartesi, 6 = Pazar

        self.player = QMediaPlayer()
        self.player.setVolume(50)

        self.setup_ui()
        self.setup_alarm_timer()

        self.set_initial_window_size()
        self._last_checked_minute = -1 # Aynı dakika içinde birden fazla tetiklemeyi önlemek için

        # SİSTEM TEPSİSİ ENTEGRASYONU BAŞLANGICI
        self.setup_tray_icon()
        # SİSTEM TEPSİSİ ENTEGRASYONU SONU

    def load_resource(self, filename):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        resource_path = os.path.join(script_dir, filename)
        if os.path.exists(resource_path):
            return resource_path
        else:
            print(f"Uyarı: {filename} bulunamadı. Lütfen {filename} dosyasının programla aynı dizinde olduğundan emin olun.")
            return None

    def setup_ui(self):
        icon_path = self.load_resource("hemsirem.png")
        if icon_path:
            self.setWindowIcon(QIcon(icon_path))

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.main_layout = QVBoxLayout(central_widget)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        self.main_layout.setSpacing(10)

        header_layout = QVBoxLayout()
        header_layout.setContentsMargins(0,0,0,0)
        header_layout.setSpacing(5)

        title_button_row_layout = QHBoxLayout()

        self.logo_label = QLabel()
        logo_path = self.load_resource("hemsirem.png")
        if logo_path:
            pixmap = QPixmap(logo_path)
            scaled_pixmap = pixmap.scaled(96, 96, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.logo_label.setPixmap(scaled_pixmap)
        else:
            self.logo_label.setFixedSize(96, 96)
            self.logo_label.setStyleSheet("background-color: black;")

        title_button_row_layout.addWidget(self.logo_label)

        title_labels_container = QWidget()
        title_labels_layout = QVBoxLayout(title_labels_container)
        title_labels_layout.setContentsMargins(0,0,0,0)
        title_labels_layout.setSpacing(0)

        self.main_title_label = QLabel("HEMŞİREM")
        self.main_title_label.setAlignment(Qt.AlignCenter)
        self.main_title_label.setStyleSheet("font-size: 24px; font-weight: bold; font-family: 'Liberation Sans', sans-serif;")

        self.sub_title_label = QLabel("İlaç Zamanı Hatırlatıcısı")
        self.sub_title_label.setAlignment(Qt.AlignCenter)
        self.sub_title_label.setStyleSheet("font-size: 16px;")

        title_labels_layout.addWidget(self.main_title_label)
        title_labels_layout.addWidget(self.sub_title_label)

        title_button_row_layout.addStretch(1)
        title_button_row_layout.addWidget(title_labels_container)
        title_button_row_layout.addStretch(1)

        settings_button = QPushButton("Ayarlar")
        settings_button.clicked.connect(self.show_settings_dialog)
        title_button_row_layout.addWidget(settings_button)
        header_layout.addLayout(title_button_row_layout)

        self.current_time_label = QLabel(datetime.now().strftime("Bugün: %A Saat: %H:%M"))
        self.current_time_label.setAlignment(Qt.AlignCenter)
        # Font boyutu artırıldı
        self.current_time_label.setStyleSheet("font-size: 16px;")
        header_layout.addWidget(self.current_time_label)

        self.main_layout.addLayout(header_layout)

        self.tab_widget = QTabWidget()
        self.tab_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # self.days ve self.time_slots burada tanımlanıyordu, __init__ metoduna taşındı.

        self.day_widgets = {}
        for i, day in enumerate(self.days):
            day_widget = self.create_day_widget(day)
            self.tab_widget.addTab(day_widget, day)
            self.day_widgets[day] = day_widget
        self.main_layout.addWidget(self.tab_widget)

        self.main_layout.addSpacerItem(QSpacerItem(0, 5, QSizePolicy.Minimum, QSizePolicy.Fixed))

        self.about_button = QPushButton("Hakkında")
        self.about_button.clicked.connect(self.show_about_dialog)
        self.main_layout.addWidget(self.about_button, alignment=Qt.AlignCenter)

        self.main_layout.addSpacerItem(QSpacerItem(0, 5, QSizePolicy.Minimum, QSizePolicy.Fixed))

        self.update_ui_with_medication_data()

    def set_initial_window_size(self):
        # Yeni genişlik hesaplaması:
        # Minimum genişliği, içindeki elemanların minimum sığabileceği kadar belirleyelim.
        # time_slot_label (95) + spacer (15) + time_edit (70) + layout_spacing (5) + radio_button_min_width (~200) + sol/sağ kenar boşlukları

        radio_button_min_effective_width = 200

        # Güncellenen genişlik değeri: 80 yerine 95
        content_width = 10 + 95 + 15 + 70 + 5 + radio_button_min_effective_width + 10 # 405

        max_tab_name_width = 0
        font_metrics = QFontMetrics(self.tab_widget.font())
        for day in self.days:
            max_tab_name_width = max(max_tab_name_width, font_metrics.width(day))

        tab_overhead_per_tab = 25
        tab_bar_total_width_needed = (max_tab_name_width + tab_overhead_per_tab) * len(self.days)

        min_width = max(content_width, tab_bar_total_width_needed) + self.main_layout.contentsMargins().left() + self.main_layout.contentsMargins().right()

        header_height = self.logo_label.sizeHint().height() + \
                        self.main_title_label.sizeHint().height() + \
                        self.sub_title_label.sizeHint().height() + \
                        self.current_time_label.sizeHint().height() + \
                        self.main_layout.spacing() * 2

        # Sekme içeriği yüksekliği hesaplaması (Artık addStretch olmadan)
        # Day widget layout components:
        # 1. Top margin: 5px (from layout.setContentsMargins(5, 5, 5, 5))
        # 2. Header layout: estimated 25px (height of labels like 'Zaman Dilimi', 'Saat', 'Durum')
        # 3. Spacing after header: 5px (from layout.setSpacing(5))
        # 4. Six time slot rows: 6 * 25px (fixed height of QLineEdit in each row) = 150px
        # 5. Spacing between rows: 5 * 5px = 25px (5 gaps between 6 rows)
        # 6. Spacing after last row and before final QSpacerItem: 5px (from layout.setSpacing(5))
        # 7. Final spacer: 10px (QSpacerItem(0, 10, ...))
        # 8. Bottom margin: 5px (from layout.setContentsMargins(5, 5, 5, 5))

        tab_content_height = (
            5 + # Top margin
            25 + # Header layout height
            5 + # Spacing after header
            (len(self.time_slots) * 25) + # Height of all 6 time slot rows (6 * 25 = 150)
            ((len(self.time_slots) - 1) * 5) + # Spacing between rows (5 * 5 = 25)
            5 + # Spacing after last row and before final QSpacerItem
            10 + # Height of final QSpacerItem
            5 # Bottom margin (as requested, 5px below last element)
        ) # Total: 5 + 25 + 5 + 150 + 25 + 5 + 10 + 5 = 230

        if hasattr(self, 'about_button'):
            footer_height = self.about_button.sizeHint().height() + 10 + 10
        else:
            footer_height = 50 + 10

        min_height = header_height + self.tab_widget.tabBar().sizeHint().height() + tab_content_height + footer_height + self.main_layout.contentsMargins().top() + self.main_layout.contentsMargins().bottom() + 10

        self.setMinimumSize(int(min_width), int(min_height))
        self.resize(int(min_width), int(min_height))


    def create_day_widget(self, day_name):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        header_layout = QHBoxLayout()
        header_layout.setSpacing(5)

        header_layout.addSpacerItem(QSpacerItem(10, 0, QSizePolicy.Fixed, QSizePolicy.Minimum))

        time_slot_header = QLabel("Zaman Dilimi")
        # Genişlik 80'den 95'e çıkarıldı
        time_slot_header.setFixedWidth(95)
        time_slot_header.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        # Font boyutu ayarlandı
        time_slot_header.setStyleSheet("font-size: 14px;")
        header_layout.addWidget(time_slot_header)

        header_layout.addSpacerItem(QSpacerItem(15, 0, QSizePolicy.Fixed, QSizePolicy.Minimum))

        hour_header = QLabel("Saat")
        hour_header.setFixedWidth(70)
        hour_header.setAlignment(Qt.AlignCenter)
        # Font boyutu ayarlandı
        hour_header.setStyleSheet("font-size: 14px;")
        header_layout.addWidget(hour_header)

        header_layout.addSpacerItem(QSpacerItem(5, 0, QSizePolicy.Fixed, QSizePolicy.Minimum))

        status_header = QLabel("Durum")
        status_header.setAlignment(Qt.AlignCenter)
        # Font boyutu ayarlandı
        status_header.setStyleSheet("font-size: 14px;")
        header_layout.addWidget(status_header)
        header_layout.addStretch(1)

        header_layout.addSpacerItem(QSpacerItem(10, 0, QSizePolicy.Fixed, QSizePolicy.Minimum))

        layout.addLayout(header_layout)

        for time_slot in self.time_slots:
            row_layout = QHBoxLayout()
            row_layout.setSpacing(5)

            row_layout.addSpacerItem(QSpacerItem(10, 0, QSizePolicy.Fixed, QSizePolicy.Minimum))

            time_slot_label = QLabel(time_slot)
            time_slot_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            # Genişlik 80'den 95'e çıkarıldı
            time_slot_label.setFixedWidth(95)
            # Font boyutu ayarlandı
            time_slot_label.setStyleSheet("font-size: 14px;")
            row_layout.addWidget(time_slot_label)

            row_layout.addSpacerItem(QSpacerItem(15, 0, QSizePolicy.Fixed, QSizePolicy.Minimum))

            time_edit = QLineEdit()
            time_edit.setInputMask("99:99")
            time_edit.setAlignment(Qt.AlignCenter)
            time_edit.setFixedSize(70, 25)
            time_edit.setPlaceholderText("HH:MM")
            # Font boyutu ayarlandı
            time_edit.setStyleSheet("font-size: 14px;")

            setattr(widget, f'{time_slot.lower().replace(" ", "_")}_time_edit', time_edit)
            row_layout.addWidget(time_edit)

            radio_button_group_widget = QWidget()
            radio_button_layout = QHBoxLayout(radio_button_group_widget)
            radio_button_layout.setContentsMargins(0, 0, 0, 0)
            radio_button_layout.setSpacing(2)

            radio_button_group_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

            status_button_group = QButtonGroup(widget)
            setattr(widget, f'{day_name}_{time_slot}_status_button_group', status_button_group)

            self.rb_bilinmiyor = QRadioButton("Bilinmiyor")
            self.rb_ictim = QRadioButton("İçtim")
            self.rb_icmedim = QRadioButton("İçmedim")
            self.rb_hatirlamiyorum = QRadioButton("Hatırlamıyorum")

            # Font boyutu ayarlandı
            self.rb_bilinmiyor.setStyleSheet("font-size: 14px;")
            self.rb_ictim.setStyleSheet("font-size: 14px;")
            self.rb_icmedim.setStyleSheet("font-size: 14px;")
            self.rb_hatirlamiyorum.setStyleSheet("font-size: 14px;")

            status_button_group.addButton(self.rb_bilinmiyor, 0)
            status_button_group.addButton(self.rb_ictim, 1)
            status_button_group.addButton(self.rb_icmedim, 2)
            status_button_group.addButton(self.rb_hatirlamiyorum, 3)

            radio_button_layout.addWidget(self.rb_bilinmiyor)
            radio_button_layout.addWidget(self.rb_ictim)
            radio_button_layout.addWidget(self.rb_icmedim)
            radio_button_layout.addWidget(self.rb_hatirlamiyorum)
            radio_button_layout.addStretch(1)

            status_button_group.buttonToggled.connect(lambda btn, checked, d=day_name, ts=time_slot: self.on_status_radio_toggled(d, ts, btn.text(), checked))

            setattr(widget, f'{day_name}_{time_slot}_radio_group_widget', radio_button_group_widget)

            row_layout.addWidget(radio_button_group_widget)

            row_layout.addSpacerItem(QSpacerItem(10, 0, QSizePolicy.Fixed, QSizePolicy.Minimum))

            layout.addLayout(row_layout)

        layout.addSpacerItem(QSpacerItem(0, 10, QSizePolicy.Minimum, QSizePolicy.Fixed))
        # layout.addStretch(1) # Bu satır yorum satırı yapıldı
        return widget

    def on_status_radio_toggled(self, day, time_slot, status_text, checked):
        if checked:
            if day not in self.medications:
                self.medications[day] = {}
            if time_slot not in self.medications[day]:
                self.medications[day][time_slot] = {}
            self.medications[day][time_slot]['status'] = status_text
            self.save_medications()

    def update_ui_with_medication_data(self):
        for day_index, day_name in enumerate(self.days):
            for time_slot_index, time_slot_name in enumerate(self.time_slots):
                day_data = self.medications.get(day_name, {})
                slot_data = day_data.get(time_slot_name, {})

                widget = self.day_widgets[day_name]

                time_edit = getattr(widget, f'{time_slot_name.lower().replace(" ", "_")}_time_edit')

                try:
                    time_edit.textChanged.disconnect()
                except TypeError:
                    pass

                if 'time' in slot_data and slot_data['time']:
                    time_edit.setText(slot_data['time'])
                else:
                    time_edit.setText("00:00")

                time_edit.textChanged.connect(lambda text, d=day_name, ts=time_slot_name: self.save_time_setting(d, ts, text))

                status_button_group = getattr(widget, f'{day_name}_{time_slot_name}_status_button_group')
                current_status = slot_data.get('status', 'Bilinmiyor')

                if current_status == "Bilinmiyor":
                    status_button_group.buttons()[0].setChecked(True)
                elif current_status == "İçtim":
                    status_button_group.buttons()[1].setChecked(True)
                elif current_status == "İçmedim":
                    status_button_group.buttons()[2].setChecked(True)
                elif current_status == "Hatırlamıyorum":
                    status_button_group.buttons()[3].setChecked(True)
                else:
                    status_button_group.buttons()[0].setChecked(True)
                    self.medications[day_name][time_slot_name]['status'] = "Bilinmiyor"
                    self.save_medications()

    def save_time_setting(self, day, time_slot, time_str):
        if day not in self.medications:
            self.medications[day] = {}
        if time_slot not in self.medications[day]:
            self.medications[day][time_slot] = {}
        self.medications[day][time_slot]['time'] = time_str
        self.save_medications()

    def show_settings_dialog(self):
        dialog = SettingsDialog(self)

        # Doktor randevusu verilerini dialoga gönder
        appointment_data = self.medications.get("appointment_data", {})
        dialog.set_appointment_details(
            appointment_data.get("hospital", ""),
            appointment_data.get("doctor", ""),
            appointment_data.get("time", ""),
            appointment_data.get("date", ""),
            appointment_data.get("reminder_time", ""), # Yeni alan
            appointment_data.get("reminder_date", "")  # Yeni alan
        )

        # Günlük ilaç verilerini dialoga gönder
        daily_medications_data = self.medications.get("daily_medications", {})
        dialog.set_daily_medications(daily_medications_data)

        if dialog.exec_():
            # Dialogdan güncel doktor randevusu ve günlük ilaç verilerini al ve kaydet
            self.medications["appointment_data"] = dialog.get_appointment_details()
            self.medications["daily_medications"] = dialog.get_daily_medications()
            self.save_medications()

    def show_about_dialog(self):
        QMessageBox.about(self, "Hakkında", "Hemşirem İlaç ve Randevu Hatırlatıcısı\n"
                                          "Versiyon 1.0\n"
                                          "Lisans: GNU GPLv3\n"
                                          "Geliştirici: A. Serhat KILIÇOĞLU\n"
                                          "Github: github.com/shampuan\n\n"
                                          "Bu program ilaç hatırlatma amacıyla geliştirilmiştir. \nBu program, hiçbir garanti getirmez.")

    def load_medications(self):
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                print("Hata: medications.json dosyası bozuk. Yeni bir dosya oluşturuluyor.")
                return {}
        return {}

    def save_medications(self):
        with open(self.data_file, 'w', encoding='utf-8') as f:
            json.dump(self.medications, f, ensure_ascii=False, indent=4)

    def setup_alarm_timer(self):
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.check_for_alarms)
        self.timer.start(1000)

    def check_for_alarms(self):
        self.current_time_label.setText(datetime.now().strftime("Bugün: %A Saat: %H:%M"))

        current_qtime = QTime.currentTime()
        current_qdate = QDate.currentDate()
        current_minute = current_qtime.minute()

        # Aynı dakika içinde birden fazla kontrolü/tetiklemeyi önlemek için
        if current_minute == self._last_checked_minute:
            return
        self._last_checked_minute = current_minute

        alarm_triggered_this_minute = False

        # --- Doktor Randevusu Alarmı Kontrolü ---
        appointment_data = self.medications.get("appointment_data", {})
        app_time_str = appointment_data.get("time", "").strip() # Gerçek randevu saati
        app_date_str = appointment_data.get("date", "").strip() # Gerçek randevu tarihi
        reminder_time_str = appointment_data.get("reminder_time", "").strip() # Yeni: Hatırlatma saati
        reminder_date_str = appointment_data.get("reminder_date", "").strip() # Yeni: Hatırlatma tarihi

        app_alarm_time = None
        app_alarm_date = None
        reminder_alarm_time = None
        reminder_alarm_date = None

        if app_time_str and app_date_str and app_time_str != "  :  " and app_date_str != ".. . .":
            try:
                app_alarm_time = QTime.fromString(app_time_str, "HH:mm")
                app_alarm_date = QDate.fromString(app_date_str, "dd.MM.yyyy")
            except ValueError as e:
                print(f"Hata: Doktor randevu saati veya tarihi geçersiz formatta: {e}")

        if reminder_time_str and reminder_date_str and reminder_time_str != "  :  " and reminder_date_str != ".. . .":
            try:
                reminder_alarm_time = QTime.fromString(reminder_time_str, "HH:mm")
                reminder_alarm_date = QDate.fromString(reminder_date_str, "dd.MM.yyyy")
            except ValueError as e:
                print(f"Hata: Doktor randevu hatırlatma saati veya tarihi geçersiz formatta: {e}")

        # Sadece hem gerçek randevu bilgileri hem de hatırlatma bilgileri geçerliyse kontrol et
        if app_alarm_time and app_alarm_date and reminder_alarm_time and reminder_alarm_date:
            # Mevcut zaman hatırlatma tarih ve saatine uyuyor mu kontrol et
            if (current_qdate == reminder_alarm_date and
                current_qtime.hour() == reminder_alarm_time.hour() and
                current_qtime.minute() == reminder_alarm_time.minute()):

                # Gerçek randevuya kaç gün kaldığını hesapla
                today_date_py = date(current_qdate.year(), current_qdate.month(), current_qdate.day())
                appointment_date_py = date(app_alarm_date.year(), app_alarm_date.month(), app_alarm_date.day())
                days_until_actual_appointment = (appointment_date_py - today_date_py).days

                # Aynı hatırlatma için tekrar tetiklemeyi önle
                last_triggered_app_reminder_dt_str = self.medications.get("appointment_reminder_last_triggered_datetime", "")
                last_triggered_app_reminder_dt = None
                if last_triggered_app_reminder_dt_str:
                    try:
                        last_triggered_app_reminder_dt = datetime.strptime(last_triggered_app_reminder_dt_str, "%Y-%m-%d %H:%M")
                    except ValueError:
                        pass

                current_dt_for_reminder_check = datetime(current_qdate.year(), current_qdate.month(), current_qdate.day(),
                                                        current_qtime.hour(), current_qtime.minute())

                if last_triggered_app_reminder_dt is None or last_triggered_app_reminder_dt != current_dt_for_reminder_check:
                    self.trigger_alarm(alarm_type="appointment", current_time=current_qtime, days_left=days_until_actual_appointment)
                    self.medications["appointment_reminder_last_triggered_datetime"] = current_dt_for_reminder_check.strftime("%Y-%m-%d %H:%M")
                    self.save_medications()
                    alarm_triggered_this_minute = True


        # --- İlaç Alarmları Kontrolü (sadece randevu alarmı tetiklenmediyse) ---
        # Eğer randevu alarmı bu dakika içinde tetiklenmediyse, ilaç alarmlarını kontrol et
        if not alarm_triggered_this_minute:
            day_name = self.days[current_qdate.dayOfWeek() - 1] # QDate.dayOfWeek Pazartesi için 1 döndürür
            day_data = self.medications.get(day_name, {})

            for time_slot_name in self.time_slots:
                slot_data = day_data.get(time_slot_name, {})
                alarm_time_str = slot_data.get('time')
                status = slot_data.get('status', 'Bilinmiyor')

                if alarm_time_str:
                    if alarm_time_str == "  :  ":
                        continue

                    alarm_time = QTime.fromString(alarm_time_str, "HH:mm")
                    if (alarm_time.isValid() and
                        current_qtime.hour() == alarm_time.hour() and
                        current_qtime.minute() == alarm_time.minute() and
                        status != "İçtim"): # Sadece 'İçtim' durumunda değilse tetikle

                        self.trigger_alarm(alarm_type="medication", current_time=current_qtime) # alarm_type eklendi
                        alarm_triggered_this_minute = True
                        break # Bu dakika içinde bir ilaç alarmı bulunduysa diğerlerini kontrol etmeyi durdur.


    def trigger_alarm(self, alarm_type, current_time, days_left=None):
        if self.player.state() != QMediaPlayer.PlayingState:
            alarm_sound_path = self.load_resource("alarm.mp3")
            if alarm_sound_path:
                media_content = QMediaContent(QUrl.fromLocalFile(alarm_sound_path))
                self.player.setMedia(media_content)
                self.player.play()
            else:
                print(f"Uyarı: alarm.mp3 bulunamadı. Alarm sesi çalınamıyor.")

        if alarm_type == "appointment":
            alarm_dialog = DoctorAppointmentAlarmDialog(self)
            appointment_data = self.medications.get("appointment_data", {})
            alarm_dialog.set_appointment_details(appointment_data, days_left)
        elif alarm_type == "medication":
            alarm_dialog = AlarmDialog(self)
            alarm_dialog.set_alarm_time(current_time.toString("HH:mm"))

            # Güncel zaman dilimindeki ilaç bilgisini alarm ekranına gönder
            current_time_slot = ""
            current_hour_minute = current_time.toString("HH:mm")
            for ts_name in self.time_slots:
                day_data = self.medications.get(self.days[datetime.now().weekday()], {})
                slot_data = day_data.get(ts_name, {})
                alarm_time_str = slot_data.get('time')
                if alarm_time_str and QTime.fromString(alarm_time_str, "HH:mm").isValid() and current_hour_minute == alarm_time_str:
                    current_time_slot = ts_name
                    break

            daily_meds = self.medications.get("daily_medications", {}).get(current_time_slot, "")
            alarm_dialog.set_current_slot_medications(daily_meds)

            # Doktor randevu bilgisini ilaç alarm ekranına gönder (kullanıcının isteği üzerine kalabilir)
            appointment_data = self.medications.get("appointment_data", {})
            alarm_dialog.set_doctor_appointment_details(appointment_data)
        else: # Hata durumu veya bilinmeyen alarm tipi
            print("Hata: Bilinmeyen alarm tipi.")
            return

        alarm_dialog.exec_()
        self.player.stop()

    def check_and_reset_weekly(self):
        current_date_py = date.today()
        current_year, current_week_number, _ = current_date_py.isocalendar()

        last_reset_date_str = self.medications.get("last_reset_date")
        last_reset_date_py = None
        if last_reset_date_str:
            try:
                last_reset_date_py = datetime.strptime(last_reset_date_str, "%Y-%m-%d").date()
            except ValueError:
                pass

        perform_reset = False

        if last_reset_date_py:
            last_reset_year, last_reset_week_number, _ = last_reset_date_py.isocalendar()

            # Hata düzeltildi: 'last_year_number' yerine 'last_reset_year' kullanıldı
            if (current_week_number != last_reset_week_number) or (current_year > last_reset_year):
                perform_reset = True
        else:
            self.medications["last_reset_date"] = current_date_py.strftime("%Y-%m-%d")
            self.save_medications()
            print("İlk çalıştırma: Haftalık sıfırlama başlangıç tarihi ayarlandı.")
            return

        if perform_reset:
            print("Haftalık sıfırlama yapılıyor...")
            for day_name in self.days:
                if day_name in self.medications:
                    for time_slot_name in self.time_slots:
                        if time_slot_name in self.medications[day_name]:
                            self.medications[day_name][time_slot_name]['status'] = "Bilinmiyor"
            self.medications["last_reset_date"] = current_date_py.strftime("%Y-%m-%d")
            self.save_medications()
            self.update_ui_with_medication_data()

    # SİSTEM TEPSİSİ İŞLEVSELLİĞİ İÇİN YENİ METOTLAR BAŞLANGICI
    def setup_tray_icon(self):
        # Sistem tepsisi simgesini oluştur
        icon_path = self.load_resource("hemsirem.png") # Mevcut ikonunuzu kullanın
        if icon_path:
            self.tray_icon = QSystemTrayIcon(QIcon(icon_path), self)
        else:
            self.tray_icon = QSystemTrayIcon(QIcon(), self) # Varsayılan boş ikon

        self.tray_icon.setToolTip("Hemşirem İlaç Hatırlatıcısı") # Fare üzerine gelince görünen metin

        # Sağ tık menüsünü oluştur
        tray_menu = QMenu()

        # "Programı Aç" eylemi
        open_action = QAction("Programı Aç", self)
        open_action.triggered.connect(self.show_main_window)
        tray_menu.addAction(open_action)

        # "Çıkış" eylemi
        exit_action = QAction("Çıkış", self)
        exit_action.triggered.connect(QApplication.quit) # Uygulamayı kapatır
        tray_menu.addAction(exit_action)

        self.tray_icon.setContextMenu(tray_menu) # Menüyü simgeye ata

        # Simgesine çift tıklama olayını bağla (isteğe bağlı, programı açabilir)
        self.tray_icon.activated.connect(self.tray_icon_activated)

        # Sistem tepsisi simgesini göster
        self.tray_icon.show()

    def show_main_window(self):
        # Ana pencereyi gösterir ve normal duruma getirir
        self.showNormal()
        self.activateWindow() # Pencerenin öne gelmesini sağlar
        self.raise_()

    def tray_icon_activated(self, reason):
        # Sistem tepsisi simgesine tıklama/çift tıklama olaylarını yönetir
        if reason == QSystemTrayIcon.DoubleClick: # Çift tıklama algılandı
            self.show_main_window()
        # İsterseniz tek tıklama için de farklı bir eylem ekleyebilirsiniz:
        # elif reason == QSystemTrayIcon.Trigger:
        #     self.show_main_window()

    def closeEvent(self, event):
        # Pencere kapatma düğmesine basıldığında
        if self.tray_icon.isVisible():
            # Eğer sistem tepsisi simgesi görünürse (yani destekleniyorsa)
            self.hide() # Pencereyi gizle
            event.ignore() # Kapatma olayını yok say, programı kapatma
            # QMessageBox.information(self, "Hemşirem", "Program arka planda çalışmaya devam ediyor. Programı kapatmak için sistem tepsisindeki ikona sağ tıklayıp 'Çıkış'ı seçin.") # Bu satır kaldırıldı
        else:
            # Sistem tepsisi simgesi desteklenmiyorsa veya görünmezse, normal kapatma işlemi
            event.accept() # Kapatma olayını kabul et, programı kapat
    # SİSTEM TEPSİSİ İŞLEVSELLİĞİ İÇİN YENİ METOTLAR SONU

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Ayarlar")
        self.setFixedSize(500, 700) # Pencere boyutu 600'den 700'e yükseltildi

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        logo_label = QLabel()
        logo_path = self.parent().load_resource("hemsirem.png")
        if logo_path:
            pixmap = QPixmap(logo_path)
            scaled_pixmap = pixmap.scaled(96, 96, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            logo_label.setPixmap(scaled_pixmap)
        else:
            logo_label.setFixedSize(96, 96)
            logo_label.setStyleSheet("background-color: black;")
        layout.addWidget(logo_label, alignment=Qt.AlignLeft)

        # Doktor Randevusu Bölümü
        appointment_group = QGroupBox("Doktor Randevusu")
        appointment_form_layout = QFormLayout(appointment_group)

        self.hospital_name_edit = QLineEdit()
        appointment_form_layout.addRow("Hastane Adı:", self.hospital_name_edit)

        self.doctor_name_edit = QLineEdit()
        appointment_form_layout.addRow("Doktor Adı:", self.doctor_name_edit)

        self.appointment_time_edit = QLineEdit()
        self.appointment_time_edit.setInputMask("99:99")
        self.appointment_time_edit.setPlaceholderText("HH:MM")
        appointment_form_layout.addRow("Randevu Saati:", self.appointment_time_edit)

        self.appointment_date_edit = QLineEdit()
        self.appointment_date_edit.setInputMask("99.99.9999")
        self.appointment_date_edit.setPlaceholderText("GG.AA.YYYY")
        appointment_form_layout.addRow("Randevu Tarihi:", self.appointment_date_edit)

        # Yeni: Randevu Hatırlatma Saati ve Tarihi
        self.reminder_time_edit = QLineEdit()
        self.reminder_time_edit.setInputMask("99:99")
        self.reminder_time_edit.setPlaceholderText("HH:MM")
        appointment_form_layout.addRow("Hatırlatma Saati:", self.reminder_time_edit)

        self.reminder_date_edit = QLineEdit()
        self.reminder_date_edit.setInputMask("99.99.9999")
        self.reminder_date_edit.setPlaceholderText("GG.AA.YYYY")
        appointment_form_layout.addRow("Hatırlatma Tarihi:", self.reminder_date_edit)

        clear_appointment_button = QPushButton("Randevu Bilgilerini Sil")
        clear_appointment_button.clicked.connect(self.clear_appointment_fields)
        clear_button_layout = QHBoxLayout()
        clear_button_layout.addStretch(1)
        clear_button_layout.addWidget(clear_appointment_button)
        appointment_form_layout.addRow(clear_button_layout)

        layout.addWidget(appointment_group)

        # Günlük İlaç Bilgileri Bölümü (Tüm hafta için geçerli)
        daily_meds_group = QGroupBox("Günlük İlaç Bilgileri (Zaman Dilimine Göre)")
        daily_meds_form_layout = QFormLayout(daily_meds_group)

        self.daily_meds_edits = {}
        for slot in self.parent().time_slots:
            med_edit = QLineEdit()
            med_edit.setPlaceholderText(f"{slot} ilacını buraya girin...")
            self.daily_meds_edits[slot] = med_edit
            daily_meds_form_layout.addRow(f"{slot}:", med_edit)
        layout.addWidget(daily_meds_group)

        layout.addStretch()

        button_layout = QHBoxLayout()
        ok_button = QPushButton("Tamam")
        cancel_button = QPushButton("İptal")
        ok_button.clicked.connect(self.accept)
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)

    def set_appointment_details(self, hospital, doctor, app_time, app_date, reminder_time, reminder_date):
        self.hospital_name_edit.setText(hospital)
        self.doctor_name_edit.setText(doctor)
        self.appointment_time_edit.setText(app_time)
        self.appointment_date_edit.setText(app_date)
        self.reminder_time_edit.setText(reminder_time) # Yeni alan set edildi
        self.reminder_date_edit.setText(reminder_date)   # Yeni alan set edildi

    def get_appointment_details(self):
        return {
            "hospital": self.hospital_name_edit.text(),
            "doctor": self.doctor_name_edit.text(),
            "time": self.appointment_time_edit.text(),
            "date": self.appointment_date_edit.text(),
            "reminder_time": self.reminder_time_edit.text(), # Yeni alan döndürüldü
            "reminder_date": self.reminder_date_edit.text()    # Yeni alan döndürüldü
        }

    def clear_appointment_fields(self):
        reply = QMessageBox.question(self, 'Randevu Bilgilerini Sil',
                                     "Randevu bilgilerini silmek istediğinizden emin misiniz?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            self.hospital_name_edit.clear()
            self.doctor_name_edit.clear()
            self.appointment_time_edit.clear()
            self.appointment_date_edit.clear()
            self.reminder_time_edit.clear()  # Yeni alanlar da temizlendi
            self.reminder_date_edit.clear()    # Yeni alanlar da temizlendi

    def set_daily_medications(self, daily_meds_data):
        for slot, edit_widget in self.daily_meds_edits.items():
            edit_widget.setText(daily_meds_data.get(slot, ""))

    def get_daily_medications(self):
        daily_meds_data = {}
        for slot, edit_widget in self.daily_meds_edits.items():
            daily_meds_data[slot] = edit_widget.text()
        return daily_meds_data


class AlarmDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("İlacınızın Saati Geldi!")
        self.setMinimumSize(400, 250)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        header_layout = QHBoxLayout()
        logo_label = QLabel()
        logo_path = self.parent().load_resource("hemsirem.png")
        if logo_path:
            pixmap = QPixmap(logo_path)
            scaled_pixmap = pixmap.scaled(96, 96, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            logo_label.setPixmap(scaled_pixmap)
        else:
            logo_label.setFixedSize(96, 96)
            logo_label.setStyleSheet("background-color: black;")
        header_layout.addWidget(logo_label)

        title_label = QLabel("İlacınızın saati geldi!")
        title_label.setStyleSheet("font-size: 20px; font-weight: bold;")
        header_layout.addWidget(title_label)

        self.time_label = QLabel("12:00")
        self.time_label.setStyleSheet("font-size: 24px; font-weight: bold;")
        header_layout.addWidget(self.time_label, alignment=Qt.AlignRight)
        layout.addLayout(header_layout)

        self.medications_list_label = QLabel("Bu zaman diliminde alınacak ilaç: Tanımlanmadı.")
        self.medications_list_label.setWordWrap(True)
        self.medications_list_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        layout.addWidget(self.medications_list_label)

        layout.addStretch()

        self.appointment_display = QLabel("Doktor randevusu: Tanımlanmadı.")
        self.appointment_display.setWordWrap(True)
        self.appointment_display.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        layout.addWidget(self.appointment_display)

        button_layout = QHBoxLayout()
        ok_button = QPushButton("TAMAM")
        ok_button.clicked.connect(self.accept)
        button_layout.addWidget(ok_button)
        layout.addLayout(button_layout)

    def set_alarm_time(self, time_str):
        self.time_label.setText(time_str)

    def set_current_slot_medications(self, meds_text):
        if meds_text:
            meds_list = [m.strip() for m in meds_text.split(',') if m.strip()]

            if meds_list:
                formatted_meds = "<br>".join([f"<span style='font-size: 18px; font-weight: bold;'>• {med}</span>" for med in meds_list])
                self.medications_list_label.setText(f"<b>Bu zaman diliminde alınacak ilaçlar:</b><br>{formatted_meds}")
            else:
                self.medications_list_label.setText("<b>Bu zaman diliminde alınacak ilaç:</b> Tanımlanmadı.")
        else:
            self.medications_list_label.setText("<b>Bu zaman diliminde alınacak ilaç:</b> Tanımlanmadı.")

    def set_doctor_appointment_details(self, app_data):
        hospital = app_data.get("hospital", "")
        doctor = app_data.get("doctor", "")
        app_time = app_data.get("time", "")
        app_date = app_data.get("date", "")

        font_size = "12px"

        details_html = []
        if app_date and app_time and app_date != ".. . ." and app_time != "  :  ":
            details_html.append(f"<span style='font-size: {font_size}; font-weight: bold;'>Randevu:</span> <span style='font-size: {font_size};'>{app_date} - {app_time}</span>")
        if hospital:
            details_html.append(f"<span style='font-size: {font_size}; font-weight: bold;'>Hastane:</span> <span style='font-size: {font_size};'>{hospital}</span>")
        if doctor:
            details_html.append(f"<span style='font-size: {font_size}; font-weight: bold;'>Doktor:</span> <span style='font-size: {font_size};'>{doctor}</span>")

        if details_html:
            self.appointment_display.setText("<br>".join(details_html))
        else:
            self.appointment_display.setText(f"<span style='font-size: {font_size};'>Doktor randevusu tanımlanmadı.</span>")

class DoctorAppointmentAlarmDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Randevunuz Yaklaşıyor!") # Pencere başlığı güncellendi
        self.setMinimumSize(400, 250)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        header_layout = QHBoxLayout()
        logo_label = QLabel()
        logo_path = self.parent().load_resource("hemsirem.png")
        if logo_path:
            pixmap = QPixmap(logo_path)
            scaled_pixmap = pixmap.scaled(96, 96, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            logo_label.setPixmap(scaled_pixmap)
        else:
            logo_label.setFixedSize(96, 96)
            logo_label.setStyleSheet("background-color: black;")
        header_layout.addWidget(logo_label)

        self.title_label = QLabel("Randevunuz Yaklaşıyor!")
        self.title_label.setStyleSheet("font-size: 20px; font-weight: bold;")
        header_layout.addWidget(self.title_label)
        layout.addLayout(header_layout)

        self.datetime_label = QLabel()
        self.datetime_label.setWordWrap(True)
        layout.addWidget(self.datetime_label)

        self.hospital_label = QLabel()
        self.hospital_label.setWordWrap(True)
        layout.addWidget(self.hospital_label)

        self.doctor_label = QLabel()
        self.doctor_label.setWordWrap(True)
        layout.addWidget(self.doctor_label)

        layout.addStretch()

        button_layout = QHBoxLayout()
        ok_button = QPushButton("TAMAM")
        ok_button.clicked.connect(self.accept)
        button_layout.addWidget(ok_button)
        layout.addLayout(button_layout)

    def set_appointment_details(self, app_data, days_left=None):
        hospital = app_data.get("hospital", "")
        doctor = app_data.get("doctor", "")
        app_time = app_data.get("time", "")
        app_date = app_data.get("date", "")

        if days_left is not None:
            if days_left == 0:
                self.title_label.setText("Bugün Randevunuz Var!")
            elif days_left == 1:
                self.title_label.setText("Yarın Randevunuz Var!")
            elif days_left > 1:
                self.title_label.setText(f"{days_left} Gün Sonra Randevunuz Var!")
        else:
            self.title_label.setText("Randevunuz Yaklaşıyor!") # Varsayılan metin

        if app_date and app_time and app_date != ".. . ." and app_time != "  :  ":
            self.datetime_label.setText(f"<span style='font-size: 16px; font-weight: bold;'>Tarih ve Saat:</span> <span style='font-size: 16px;'>{app_date} - {app_time}</span>")
        else:
            self.datetime_label.setText("<span style='font-size: 16px; font-weight: bold;'>Tarih ve Saat:</span> Tanımlanmadı.")

        if hospital:
            self.hospital_label.setText(f"<span style='font-size: 16px; font-weight: bold;'>Hastane Adı:</span> <span style='font-size: 16px;'>{hospital}</span>")
        else:
            self.hospital_label.setText("<span style='font-size: 16px; font-weight: bold;'>Hastane Adı:</span> Tanımlanmadı.")

        if doctor:
            self.doctor_label.setText(f"<span style='font-size: 16px; font-weight: bold;'>Doktor Adı:</span> <span style='font-size: 16px;'>{doctor}</span>")
        else:
            self.doctor_label.setText("<span style='font-size: 16px; font-weight: bold;'>Doktor Adı:</span> Tanımlanmadı.")


if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    ex = HemşiremApp()
    ex.show()
    sys.exit(app.exec_())
