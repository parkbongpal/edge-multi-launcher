import sys
import time
import subprocess
import psutil
import json
import os
from pathlib import Path

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QGridLayout, 
                             QPushButton, QVBoxLayout, QHBoxLayout, QLabel, 
                             QLineEdit, QMessageBox, QFrame)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QPoint
from PyQt6.QtGui import QCursor, QFont, QColor

import win32gui
import win32con
import win32process
import win32api
import win32clipboard

# ==========================================
# 테마 및 레이아웃 설정 상수
# ==========================================
class Theme:
    PRIMARY = "#4F46E5"    # 실행 중 (Blue)
    SURFACE = "#F8FAFC"
    CARD_BG = "#FFFFFF"
    BORDER = "#E2E8F0"
    TEXT_MAIN = "#1E293B"
    TEXT_SUB = "#64748B"
    SUCCESS = "#10B981"    # 선택됨 (Green)
    DANGER = "#EF4444"     # 종료 중 (Red)
    ACCENT = "#F59E0B"     # 기타 강조 (Orange)
    ACTIVE = "#8B5CF6"     # 실제로 눈에 보이는 창 (Purple)

# [수정 포인트] 이 수치들을 조절하면 레이아웃이 자동으로 변합니다.
BTN_SIZE = 45           # 버튼 가로세로 크기
H_SPACING = 2           # 버튼 사이 좌우 간격 (원하시는 숫자로 변경하세요)
V_SPACING = 5           # 버튼 사이 상하 간격
WINDOW_LR_MARGIN = 12   # 윈도우 좌우 여백

class Styles:
    MAIN_WINDOW = f"background-color: {Theme.SURFACE};"
    CARD = f"QFrame {{ background-color: {Theme.CARD_BG}; border: 1px solid {Theme.BORDER}; border-radius: 12px; }}"
    LABEL_TITLE = f"color: {Theme.TEXT_MAIN}; font-size: 18px; font-weight: bold; border: none;"
    LABEL_SUB = f"color: {Theme.TEXT_SUB}; font-size: 13px; font-weight: 600; border: none;"
    INPUT = f"QLineEdit {{ border: 1px solid {Theme.BORDER}; border-radius: 8px; padding: 0 12px; background: {Theme.SURFACE}; font-size: 13px; color: {Theme.TEXT_MAIN}; }} QLineEdit:focus {{ border: 2px solid {Theme.PRIMARY}; background: white; }}"
    BTN_SYNC = f"QPushButton {{ background: {Theme.SURFACE}; border: 1px solid {Theme.BORDER}; color: {Theme.PRIMARY}; font-weight: bold; border-radius: 8px; font-size: 12px; }} QPushButton:hover {{ background: #EEF2FF; border: 1px solid {Theme.PRIMARY}; }}"

# ==========================================
# 비즈니스 로직 및 유틸리티
# ==========================================
EDGE_PATH = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
APPDATA_DIR = Path(os.getenv('LOCALAPPDATA')) / 'EdgeMultiLauncher'
CONFIG_FILE = APPDATA_DIR / 'window_config.json'

class AppDataConfig:
    @staticmethod
    def save_window_position(x, y, width, height):
        try:
            APPDATA_DIR.mkdir(parents=True, exist_ok=True)
            config = {'window_x': int(x), 'window_y': int(y), 'window_width': int(width), 'window_height': int(height)}
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f: 
                json.dump(config, f, indent=2)
        except: pass
    
    @staticmethod
    def load_window_position():
        try:
            if CONFIG_FILE.exists():
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f: 
                    config = json.load(f)
                return (config['window_x'], config['window_y'], config['window_width'], config['window_height'])
        except: pass
        return None

class WindowUtils:
    @staticmethod
    def get_monitors():
        monitors = win32api.EnumDisplayMonitors()
        info_list = []
        for handle, _, rect in monitors:
            info = win32api.GetMonitorInfo(handle)
            is_p = (info['Flags'] & win32con.MONITORINFOF_PRIMARY) != 0
            info_list.append({'is_primary': is_p, 'x': rect[0], 'y': rect[1], 'width': rect[2] - rect[0], 'height': rect[3] - rect[1]})
        if not info_list: return None, None
        m1 = next((m for m in info_list if m['is_primary']), info_list[0])
        m2 = next((m for m in info_list if not m['is_primary']), m1)
        return m1, m2

    @staticmethod
    def is_window_valid(hwnd):
        try: return win32gui.IsWindow(hwnd) and win32gui.IsWindowVisible(hwnd)
        except: return False

    @staticmethod
    def bring_to_front(hwnd, focus=True):
        try:
            if win32gui.IsIconic(hwnd): win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            if focus:
                win32api.keybd_event(win32con.VK_MENU, 0, 0, 0)
                win32gui.SetForegroundWindow(hwnd)
                win32api.keybd_event(win32con.VK_MENU, 0, win32con.KEYEVENTF_KEYUP, 0)
                win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
            else:
                win32gui.SetWindowPos(hwnd, win32con.HWND_TOP, 0, 0, 0, 0, 
                                      win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE)
            return True
        except: return False

    @staticmethod
    def activate_and_move(hwnd, x, y, w, h):
        try:
            if win32gui.IsIconic(hwnd): win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32gui.ShowWindow(hwnd, win32con.SW_NORMAL)
            win32gui.MoveWindow(hwnd, int(x), int(y), int(w), int(h), True)
            time.sleep(0.05) 
            rect = win32gui.GetWindowRect(hwnd)
            if abs(rect[0] - x) > 5 or abs(rect[1] - y) > 5:
                win32gui.MoveWindow(hwnd, int(x), int(y), int(w), int(h), True)
            WindowUtils.bring_to_front(hwnd, focus=True)
            return True
        except: return False

    @staticmethod
    def get_all_edge_hwnds():
        hwnds = set()
        def cb(hwnd, _):
            if win32gui.IsWindowVisible(hwnd) and win32gui.GetClassName(hwnd) == 'Chrome_WidgetWin_1':
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                try:
                    if 'msedge' in psutil.Process(pid).name().lower(): hwnds.add(hwnd)
                except: pass
            return True
        win32gui.EnumWindows(cb, None)
        return hwnds

# ==========================================
# 조작용 쓰레드
# ==========================================
class LauncherThread(QThread):
    log_signal = pyqtSignal(str)
    profile_launched_signal = pyqtSignal(int, int) 
    finished_signal = pyqtSignal()

    def __init__(self, selected_ids, existing_profile_windows):
        super().__init__()
        self.selected_ids = sorted(selected_ids)
        self.existing_profile_windows = existing_profile_windows

    def get_target_pos(self, i, m1, m2):
        rem = i % 10
        if 2 <= i <= 9: gIdx = i - 2
        elif 1 <= rem <= 8: gIdx = rem - 1
        else:
            gIdx = (i - 9) % 8
            if gIdx < 0: gIdx += 8
        col, row = gIdx % 4, gIdx // 4
        m2_w, m2_h = m2['width'] // 3.6, m2['height'] // 2
        m2_gap = (m2['width'] - m2_w) / 3
        m1_w, m1_h = m1['width'] // 3.6, m1['height'] // 2
        m1_gap = (m1['width'] - m1_w) / 3
        
        if (2 <= i <= 9) or (1 <= rem <= 8): 
            return m2['x'] + (col * m2_gap), m2['y'] + (row * m2_h), m2_w, m2_h
        else: 
            return m1['x'] + (col * m1_gap), m1['y'] + (row * m1_h), m1_w, m1_h

    def run(self):
        m1, m2 = WindowUtils.get_monitors()
        if not m2: m2 = m1
        initial_hwnds = WindowUtils.get_all_edge_hwnds()
        ids_to_launch = []

        for i in self.selected_ids:
            if i in self.existing_profile_windows and WindowUtils.is_window_valid(self.existing_profile_windows[i]):
                tx, ty, tw, th = self.get_target_pos(i, m1, m2)
                WindowUtils.activate_and_move(self.existing_profile_windows[i], tx, ty, tw, th)
                self.profile_launched_signal.emit(i, self.existing_profile_windows[i])
            else:
                ids_to_launch.append(i)
        
        if not ids_to_launch:
            self.finished_signal.emit()
            return

        self.log_signal.emit(f"🚀 {len(ids_to_launch)}개 일괄 실행...")
        for i in ids_to_launch:
            subprocess.Popen([EDGE_PATH, f"--profile-directory=Profile {i}", "--new-window", "--no-first-run", "--no-default-browser-check"])
        
        matched_count = 0
        total_to_match = len(ids_to_launch)
        start_poll_time = time.time()
        captured_hwnds = set()
        
        while matched_count < total_to_match and (time.time() - start_poll_time < 40):
            time.sleep(0.3)
            current_all = WindowUtils.get_all_edge_hwnds()
            new_hwnds = list(current_all - initial_hwnds - captured_hwnds)
            
            for hwnd in new_hwnds:
                if matched_count < total_to_match:
                    target_id = ids_to_launch[matched_count]
                    tx, ty, tw, th = self.get_target_pos(target_id, m1, m2)
                    WindowUtils.activate_and_move(hwnd, tx, ty, tw, th)
                    self.profile_launched_signal.emit(target_id, hwnd)
                    captured_hwnds.add(hwnd)
                    matched_count += 1
                    self.log_signal.emit(f"📍 {target_id}번 감지 완료 ({matched_count}/{total_to_match})")
        
        self.log_signal.emit("✅ 배치 프로세스 완료")
        self.finished_signal.emit()

class SyncThread(QThread):
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal()

    def __init__(self, action_type, profile_windows, **kwargs):
        super().__init__()
        self.action_type = action_type
        self.profile_windows = profile_windows
        self.kwargs = kwargs

    def run(self):
        sorted_items = sorted(self.profile_windows.items())
        active_pids_hwnds = [(pid, hwnd) for pid, hwnd in sorted_items if WindowUtils.is_window_valid(hwnd)]
        if not active_pids_hwnds: 
            self.finished_signal.emit()
            return

        if self.action_type == 'url':
            url = self.kwargs.get('url', '').strip()
            for _ in range(3):
                try:
                    win32clipboard.OpenClipboard()
                    win32clipboard.EmptyClipboard()
                    win32clipboard.SetClipboardText(url)
                    win32clipboard.CloseClipboard()
                    break
                except: time.sleep(0.1)

        for idx, (pid, hwnd) in enumerate(active_pids_hwnds, 1):
            if not WindowUtils.bring_to_front(hwnd, focus=True): continue 
            time.sleep(0.5 if idx == 1 else 0.2)
            if self.action_type == 'url':
                try:
                    if self.kwargs.get('new_tab', False):
                        win32api.keybd_event(win32con.VK_CONTROL, 0, 0, 0)
                        win32api.keybd_event(0x54, 0, 0, 0)
                        time.sleep(0.05)
                        win32api.keybd_event(0x54, 0, win32con.KEYEVENTF_KEYUP, 0)
                        win32api.keybd_event(win32con.VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)
                        time.sleep(0.3)
                    win32api.keybd_event(win32con.VK_CONTROL, 0, 0, 0)
                    win32api.keybd_event(0x4C, 0, 0, 0)
                    time.sleep(0.05)
                    win32api.keybd_event(0x4C, 0, win32con.KEYEVENTF_KEYUP, 0)
                    win32api.keybd_event(win32con.VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)
                    time.sleep(0.2) 
                    win32api.keybd_event(win32con.VK_CONTROL, 0, 0, 0)
                    win32api.keybd_event(0x56, 0, 0, 0)
                    time.sleep(0.05)
                    win32api.keybd_event(0x56, 0, win32con.KEYEVENTF_KEYUP, 0)
                    win32api.keybd_event(win32con.VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)
                    time.sleep(0.15)
                    win32api.keybd_event(win32con.VK_RETURN, 0, 0, 0)
                    time.sleep(0.05)
                    win32api.keybd_event(win32con.VK_RETURN, 0, win32con.KEYEVENTF_KEYUP, 0)
                    self.log_signal.emit(f"📍 전송 ({idx}/{len(active_pids_hwnds)})")
                except: pass
            elif self.action_type == 'key':
                km = {'ctrl+t': (win32con.VK_CONTROL, 0x54), 'ctrl+w': (win32con.VK_CONTROL, 0x57), 'f5': (None, win32con.VK_F5)}
                combo = self.kwargs.get('key_combo', '')
                if combo in km:
                    mod, main = km[combo]
                    if mod: win32api.keybd_event(mod, 0, 0, 0)
                    win32api.keybd_event(main, 0, 0, 0)
                    time.sleep(0.05)
                    win32api.keybd_event(main, 0, win32con.KEYEVENTF_KEYUP, 0)
                    if mod: win32api.keybd_event(mod, 0, win32con.KEYEVENTF_KEYUP, 0)
                    self.log_signal.emit(f"⌨️ {combo} ({idx}/{len(active_pids_hwnds)})")
            time.sleep(0.1)
        self.finished_signal.emit()

# ==========================================
# UI 컴포넌트
# ==========================================
class GridButton(QPushButton):
    def __init__(self, text, profile_id, parent_window):
        super().__init__(text)
        self.profile_id = profile_id
        self.parent_window = parent_window
        self.setCheckable(True)
        self.setFixedSize(BTN_SIZE, BTN_SIZE)
        self.is_closing = False
        self.is_active = False 
        self.update_style()

    def update_style(self):
        base = "font-size: 14px; font-weight: bold; border-radius: 8px;"
        if self.is_closing: style = f"background-color: {Theme.DANGER}; color: white; border: none;"
        elif self.is_active: style = f"background-color: {Theme.ACTIVE}; color: white; border: 2px solid white;"
        elif self.profile_id in self.parent_window.profile_windows: style = f"background-color: {Theme.PRIMARY}; color: white; border: none;"
        elif self.isChecked(): style = f"background-color: {Theme.SUCCESS}; color: white; border: none;"
        else: style = f"background-color: white; border: 1px solid {Theme.BORDER}; color: {Theme.TEXT_MAIN};"
        self.setStyleSheet(f"QPushButton {{ {base} {style} }} QPushButton:hover {{ opacity: 0.8; }}")

    def show_close_animation(self):
        self.is_closing = True; self.is_active = False; self.update_style()
        QTimer.singleShot(400, self.reset_from_close)
    
    def reset_from_close(self): self.is_closing = False; self.setChecked(False); self.update_style()

    def mousePressEvent(self, event):
        self.parent_window.set_always_on_top(True); self.parent_window.last_hovered_id = self.profile_id; self.grabMouse()
        if event.button() == Qt.MouseButton.LeftButton:
            self.parent_window.is_dragging = True
            if self.profile_id in self.parent_window.profile_windows: self.parent_window.activate_profile(self.profile_id, focus=False)
            else: self.parent_window.target_drag_state = not self.isChecked(); self.setChecked(self.parent_window.target_drag_state)
        elif event.button() == Qt.MouseButton.RightButton: 
            self.parent_window.is_right_dragging = True; self.parent_window.close_profile(self.profile_id)
        self.update_style()

    def mouseMoveEvent(self, event):
        if not event.buttons(): return
        if self.parent_window.is_dragging or self.parent_window.is_right_dragging:
            global_pos = QCursor.pos(); local_pos = self.parent_window.centralWidget().mapFromGlobal(global_pos)
            target = self.parent_window.centralWidget().childAt(local_pos)
            w = target
            while w and not isinstance(w, GridButton): w = w.parent()
            if isinstance(w, GridButton):
                pid = w.profile_id
                if pid == self.parent_window.last_hovered_id: return
                self.parent_window.last_hovered_id = pid
                if self.parent_window.is_dragging:
                    if pid in self.parent_window.profile_windows: self.parent_window.activate_profile(pid, focus=False)
                    else: w.setChecked(self.parent_window.target_drag_state)
                elif self.parent_window.is_right_dragging: self.parent_window.close_profile(pid)
                w.update_style()

    def mouseReleaseEvent(self, event):
        self.releaseMouse()
        if self.parent_window.is_dragging and not self.parent_window.is_right_dragging:
            if self.profile_id in self.parent_window.profile_windows: self.parent_window.activate_profile(self.profile_id, focus=True)
        self.parent_window.is_dragging = False; self.parent_window.is_right_dragging = False; self.parent_window.last_hovered_id = None
        self.parent_window.set_always_on_top(False); self.update_style()

class LauncherWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Edge Multi-Launcher PRO")
        self.buttons = {}; self.profile_windows = {}; self.is_dragging = False; self.is_right_dragging = False; self.last_hovered_id = None 
        
        # [수정] 윈도우 너비 자동 계산 공식 적용
        calc_width = (BTN_SIZE * 10) + (H_SPACING * 9) + 20 + (WINDOW_LR_MARGIN * 2) + 4
        
        saved = AppDataConfig.load_window_position()
        if saved: 
            self.setGeometry(saved[0], saved[1], calc_width, saved[3])
        else: 
            self.setGeometry(100, 100, calc_width, 850)
        
        self.setFixedWidth(calc_width) 
        self.init_ui()
        self.check_timer = QTimer(); self.check_timer.timeout.connect(self.check_windows_status); self.check_timer.start(400) 

    def set_always_on_top(self, on):
        hwnd = int(self.winId()); flag = win32con.HWND_TOPMOST if on else win32con.HWND_NOTOPMOST
        win32gui.SetWindowPos(hwnd, flag, 0, 0, 0, 0, win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE)

    def init_ui(self):
        self.setStyleSheet(Styles.MAIN_WINDOW); central = QWidget(); self.setCentralWidget(central)
        layout = QVBoxLayout(central); layout.setSpacing(8)
        layout.setContentsMargins(WINDOW_LR_MARGIN, 8, WINDOW_LR_MARGIN, 12)
        
        header = QLabel("🚀 Edge Multi-Launcher PRO"); header.setStyleSheet(Styles.LABEL_TITLE)
        layout.addWidget(header, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._create_batch_card())
        
        grid_card = QFrame(); grid_card.setStyleSheet(Styles.CARD)
        grid_lay = QVBoxLayout(grid_card)
        grid_lay.setContentsMargins(10, 10, 10, 10) 
        
        grid_widget = QWidget()
        grid = QGridLayout(grid_widget)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(H_SPACING) 
        grid.setVerticalSpacing(V_SPACING)
        
        for i in range(1, 101):
            btn = GridButton(str(i), i, self)
            self.buttons[i] = btn
            grid.addWidget(btn, (i-1)//10, (i-1)%10)
        
        grid_lay.addWidget(grid_widget); layout.addWidget(grid_card)
        layout.addWidget(self._create_legend_card()) # 범례 및 가이드 복구
        
        btn_lay = QHBoxLayout()
        self.btn_launch = self._create_btn("실행 및 배치", Theme.SUCCESS, self.run_batch); btn_lay.addWidget(self.btn_launch)
        btn_lay.addWidget(self._create_btn("선택 해제", Theme.TEXT_SUB, self.clear_selection))
        btn_lay.addWidget(self._create_btn("전체 활성화", Theme.PRIMARY, self.activate_all_browsers))
        btn_lay.addWidget(self._create_btn("전체 최소화", Theme.ACCENT, self.minimize_all_browsers))
        btn_lay.addWidget(self._create_btn("전체 종료", Theme.DANGER, self.close_all_managed)); layout.addLayout(btn_lay)
        self.status = QLabel("Ready"); self.status.setAlignment(Qt.AlignmentFlag.AlignCenter); self.status.setStyleSheet(Styles.LABEL_SUB); layout.addWidget(self.status)

    def _create_batch_card(self):
        card = QFrame(); card.setStyleSheet(Styles.CARD); v_lay = QVBoxLayout(card); v_lay.setContentsMargins(10, 6, 10, 6); v_lay.setSpacing(5)
        title = QLabel("⚡ 일괄 조작"); title.setStyleSheet(f"color: {Theme.PRIMARY}; font-weight: bold; border:none;"); v_lay.addWidget(title)
        h_lay = QHBoxLayout(); h_lay.setSpacing(5)
        self.url_input = QLineEdit(); self.url_input.setFixedHeight(36); self.url_input.setPlaceholderText("URL 입력...")
        self.url_input.setStyleSheet(Styles.INPUT); self.url_input.returnPressed.connect(lambda: self.send_url_to_all(False)); h_lay.addWidget(self.url_input, stretch=1)
        for lbl, func in [("현재", lambda: self.send_url_to_all(False)), ("새탭", lambda: self.send_url_to_all(True))]:
            b = QPushButton(lbl); b.setFixedSize(45, 36); b.setStyleSheet(f"background-color: {Theme.PRIMARY if lbl=='새탭' else Theme.ACCENT}; color: white; font-weight: bold; border-radius: 8px; border: none; font-size: 11px;"); b.clicked.connect(func); h_lay.addWidget(b)
        for lbl, key in [("탭열기", "ctrl+t"), ("탭닫기", "ctrl+w"), ("🔃F5", "f5")]:
            b = QPushButton(lbl); b.setFixedSize(45, 36); b.setStyleSheet(Styles.BTN_SYNC); b.clicked.connect(lambda ch, k=key: self.send_shortcut(k)); h_lay.addWidget(b)
        v_lay.addLayout(h_lay); return card

    def _create_legend_card(self):
            card = QFrame()
            card.setStyleSheet(Styles.CARD)
            lay = QHBoxLayout(card)
            lay.setContentsMargins(12, 8, 12, 8)
            
            # 색상 범례 리스트 (기존 유지)
            colors = [("⬜", "미실행"), ("🟩", "선택"), ("🟦", "실행"), ("🟪", "활성"), ("🟥", "종료중")]
            color_section = QHBoxLayout()
            color_section.setSpacing(8)
            for icon, txt in colors:
                l = QLabel(f"{icon} {txt}")
                l.setStyleSheet("font-size: 12px; font-weight: 600; border: none; color: #475569;")
                color_section.addWidget(l)
            
            # [수정] HTML 줄바꿈(<br/>)과 폰트 스타일 적용
            guide = QLabel(
                '<div style="line-height: 140%;">'
                '<span style="color: black;">🖱️ 좌클릭/드래그: 선택,활성화</span><br/>'
                '<span style="color: red;">🖱️ 우클릭/드래그: 종료</span>'
                '</div>'
            )
            # 가독성 좋은 '맑은 고딕' 적용 및 우측 정렬
            guide.setStyleSheet("""
                font-family: 'Malgun Gothic', 'Segoe UI', sans-serif;
                font-size: 12px; 
                font-weight: bold; 
                border: none;
            """)
            guide.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            
            lay.addLayout(color_section)
            lay.addStretch()
            lay.addWidget(guide)
            return card

    def _create_btn(self, text, color, func):
        btn = QPushButton(text); btn.setFixedHeight(40); btn.clicked.connect(func); btn.setStyleSheet(f"QPushButton {{ background-color: {color}; color: white; font-weight: bold; border-radius: 8px; border: none; font-size: 11px; }} QPushButton:hover {{ opacity: 0.9; }}"); return btn

    def activate_all_browsers(self):
        for h in [h for h in self.profile_windows.values() if WindowUtils.is_window_valid(h)]: WindowUtils.bring_to_front(h, focus=True); time.sleep(0.05)

    def minimize_all_browsers(self):
        for h in [h for h in self.profile_windows.values() if WindowUtils.is_window_valid(h)]:
            try: win32gui.ShowWindow(h, win32con.SW_MINIMIZE)
            except: pass

    def send_url_to_all(self, new_tab=False):
        url = self.url_input.text().strip(); 
        if not url: return
        self.sync_thread = SyncThread('url', self.profile_windows, url=url, new_tab=new_tab); self.sync_thread.log_signal.connect(self.status.setText); self.sync_thread.start()

    def send_shortcut(self, key):
        self.sync_thread = SyncThread('key', self.profile_windows, key_combo=key); self.sync_thread.log_signal.connect(self.status.setText); self.sync_thread.start()

    def check_windows_status(self):
        fg_hwnd = win32gui.GetForegroundWindow()
        for pid, hwnd in list(self.profile_windows.items()):
            if not WindowUtils.is_window_valid(hwnd):
                del self.profile_windows[pid]; 
                if pid in self.buttons: self.buttons[pid].is_active = False; self.buttons[pid].show_close_animation()
            else:
                if pid in self.buttons:
                    if hwnd == fg_hwnd: self.buttons[pid].is_active = True; continue
                    if win32gui.IsIconic(hwnd): self.buttons[pid].is_active = False
                    else:
                        try:
                            rect = win32gui.GetWindowRect(hwnd); points = [((rect[0]+rect[2])//2, (rect[1]+rect[3])//2), (rect[0]+15, rect[1]+15)]
                            visible = False
                            for pt in points:
                                at_pt = win32gui.WindowFromPoint(pt)
                                if at_pt and win32gui.GetAncestor(at_pt, win32con.GA_ROOT) == hwnd: visible = True; break
                            self.buttons[pid].is_active = visible
                        except: self.buttons[pid].is_active = False
        for btn in self.buttons.values():
            if not btn.is_closing: btn.update_style()

    def clear_selection(self):
        for btn in self.buttons.values(): btn.setChecked(False); btn.update_style()

    def run_batch(self):
        sel = [i for i, b in self.buttons.items() if b.isChecked()]
        if not sel: self.status.setText("⚠️ 선택된 프로필 없음"); return
        self.btn_launch.setEnabled(False); self.thread = LauncherThread(sel, self.profile_windows)
        self.thread.log_signal.connect(self.status.setText); self.thread.profile_launched_signal.connect(lambda p, h: self.profile_windows.update({p: h}))
        self.thread.finished_signal.connect(lambda: (self.btn_launch.setEnabled(True), self.check_windows_status())); self.thread.start()

    def activate_profile(self, pid, focus=True):
        if pid in self.profile_windows: WindowUtils.bring_to_front(self.profile_windows[pid], focus=focus)

    def close_profile(self, pid):
        if pid in self.profile_windows:
            try: win32gui.PostMessage(self.profile_windows[pid], win32con.WM_CLOSE, 0, 0)
            except: pass

    def close_all_managed(self):
        pids = list(self.profile_windows.keys())
        if pids and QMessageBox.question(self, "확인", f"{len(pids)}개 브라우저 종료?") == QMessageBox.StandardButton.Yes:
            for p in pids: self.close_profile(p)

    def save_pos(self): g = self.geometry(); AppDataConfig.save_window_position(g.x(), g.y(), g.width(), g.height())

    def closeEvent(self, e):
        pids = list(self.profile_windows.keys())
        if pids:
            rep = QMessageBox.question(self, "종료 확인", f"런처 종료 시 관리 중인 {len(pids)}개의 브라우저도 모두 종료하시겠습니까?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if rep == QMessageBox.StandardButton.Yes:
                for p in pids: self.close_profile(p)
                self.save_pos(); e.accept()
            else: e.ignore()
        else: self.save_pos(); e.accept()

    def moveEvent(self, e): super().moveEvent(e); self.save_pos()
    def resizeEvent(self, e): super().resizeEvent(e); self.save_pos()

if __name__ == "__main__":
    app = QApplication(sys.argv); app.setStyle("Fusion")
    window = LauncherWindow(); window.show(); sys.exit(app.exec())