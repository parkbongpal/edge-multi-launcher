import sys
import time
import subprocess
import psutil
import json
import os
import signal  # [추가] Ctrl+C 처리를 위한 모듈
from pathlib import Path
import threading

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QGridLayout, 
                             QPushButton, QVBoxLayout, QHBoxLayout, QLabel, 
                             QLineEdit, QMessageBox, QFrame, QTextEdit, QToolTip,
                             QMenu, QWidgetAction) # [추가] 팝업 메뉴 관련 클래스
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QPoint
from PyQt6.QtGui import QCursor, QFont, QColor, QAction

import win32gui
import win32con
import win32process
import win32api
import win32clipboard

# ==========================================
# 테마 및 레이아웃 설정 상수
# ==========================================
class Theme:
    PRIMARY = "#4F46E5"
    SURFACE = "#F8FAFC"
    CARD_BG = "#FFFFFF"
    BORDER = "#E2E8F0"
    TEXT_MAIN = "#1E293B"
    TEXT_SUB = "#64748B"
    SUCCESS = "#10B981"
    DANGER = "#EF4444"
    ACCENT = "#F59E0B"
    ACTIVE = "#8B5CF6"
    SPECIAL = "#EC4899"

BTN_SIZE = 38
H_SPACING = 2
V_SPACING = 5
WINDOW_LR_MARGIN = 12

class Styles:
    MAIN_WINDOW = f"background-color: {Theme.SURFACE};"
    CARD = f"QFrame {{ background-color: {Theme.CARD_BG}; border: 1px solid {Theme.BORDER}; border-radius: 12px; }}"
    LABEL_TITLE = f"color: {Theme.TEXT_MAIN}; font-size: 18px; font-weight: bold; border: none;"
    LABEL_SUB = f"color: {Theme.TEXT_SUB}; font-size: 13px; font-weight: 600; border: none;"
    INPUT = f"QLineEdit, QTextEdit {{ border: 1px solid {Theme.BORDER}; border-radius: 8px; padding: 8px 12px; background: {Theme.SURFACE}; font-size: 13px; color: {Theme.TEXT_MAIN}; }} QLineEdit:focus, QTextEdit:focus {{ border: 2px solid {Theme.PRIMARY}; background: white; }}"
    BTN_CMD = f"QPushButton {{ background: {Theme.SURFACE}; border: 1px solid {Theme.BORDER}; color: {Theme.TEXT_MAIN}; font-weight: bold; border-radius: 6px; font-size: 11px; }} QPushButton:hover {{ background: #EEF2FF; border: 1px solid {Theme.PRIMARY}; color: {Theme.PRIMARY}; }}"
    BTN_SPECIAL = f"QPushButton {{ background: {Theme.SPECIAL}; color: white; font-weight: bold; border-radius: 6px; border: none; font-size: 11px; }} QPushButton:hover {{ opacity: 0.9; }}"

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
    def is_window_focused(hwnd):
        try: return win32gui.GetForegroundWindow() == hwnd
        except: return False

    @staticmethod
    def ensure_modifiers_released():
        modifiers = [win32con.VK_MENU, win32con.VK_CONTROL, win32con.VK_SHIFT, win32con.VK_LWIN, win32con.VK_RWIN]
        for key in modifiers:
            win32api.keybd_event(key, 0, win32con.KEYEVENTF_KEYUP, 0)
        time.sleep(0.05)

    @staticmethod
    def verify_modifiers_released(timeout=0.5):
        modifiers = [win32con.VK_MENU, win32con.VK_CONTROL, win32con.VK_SHIFT]
        start = time.time()
        while time.time() - start < timeout:
            all_released = True
            for key in modifiers:
                if win32api.GetAsyncKeyState(key) & 0x8000:
                    all_released = False
                    win32api.keybd_event(key, 0, win32con.KEYEVENTF_KEYUP, 0)
            if all_released:
                return True
            time.sleep(0.02)
        return True

    @staticmethod
    def bring_to_front(hwnd, focus=True):
        try:
            if win32gui.IsIconic(hwnd): win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            if focus:
                win32api.keybd_event(win32con.VK_MENU, 0, 0, 0)
                win32gui.SetForegroundWindow(hwnd)
                win32api.keybd_event(win32con.VK_MENU, 0, win32con.KEYEVENTF_KEYUP, 0)
                win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
                WindowUtils.ensure_modifiers_released()
                WindowUtils.verify_modifiers_released()
                time.sleep(0.1)
            else:
                win32gui.SetWindowPos(hwnd, win32con.HWND_TOP, 0, 0, 0, 0, win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE)
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

    @staticmethod
    def wait_for_focus(hwnd, timeout=3.0, check_interval=0.05):
        start = time.time()
        while time.time() - start < timeout:
            if WindowUtils.is_window_focused(hwnd):
                time.sleep(0.15)
                return True
            time.sleep(check_interval)
        return False

    @staticmethod
    def click_at_position(hwnd, x, y):
        try:
            lParam = win32api.MAKELONG(int(x), int(y))
            win32gui.PostMessage(hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lParam)
            time.sleep(0.02)
            win32gui.PostMessage(hwnd, win32con.WM_LBUTTONUP, 0, lParam)
            return True
        except: return False

# ==========================================
# 전역 핫키 모니터링
# ==========================================
class GlobalHotkeyMonitor:
    def __init__(self, callback):
        self.callback = callback
        self.running = False
        self.thread = None
        self.last_f2_state = False
    
    def start(self):
        if self.running: return
        self.running = True
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()
    
    def stop(self):
        self.running = False
    
    def _monitor_loop(self):
        while self.running:
            try:
                current_state = win32api.GetAsyncKeyState(win32con.VK_F2) & 0x8000
                if current_state and not self.last_f2_state:
                    self.callback()
                self.last_f2_state = current_state
            except: pass
            time.sleep(0.05)

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

    def send_key_safely(self, hwnd, vk_key):
        for attempt in range(3):
            if WindowUtils.wait_for_focus(hwnd, timeout=2.5):
                try:
                    time.sleep(0.2)
                    win32api.keybd_event(vk_key, 0, 0, 0)
                    time.sleep(0.1)
                    win32api.keybd_event(vk_key, 0, win32con.KEYEVENTF_KEYUP, 0)
                    time.sleep(0.2)
                    return True
                except: pass
            time.sleep(0.3)
        return False

    def send_text_safely(self, hwnd, text, send_enter=False):
        if not WindowUtils.wait_for_focus(hwnd, timeout=2.0):
            return False
        try:
            for _ in range(3):
                try:
                    win32clipboard.OpenClipboard()
                    win32clipboard.EmptyClipboard()
                    win32clipboard.SetClipboardText(text)
                    win32clipboard.CloseClipboard()
                    break
                except: time.sleep(0.1)
            
            time.sleep(0.15)
            win32api.keybd_event(win32con.VK_CONTROL, 0, 0, 0)
            win32api.keybd_event(0x56, 0, 0, 0)
            time.sleep(0.05)
            win32api.keybd_event(0x56, 0, win32con.KEYEVENTF_KEYUP, 0)
            win32api.keybd_event(win32con.VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)
            
            if send_enter:
                time.sleep(0.15)
                win32api.keybd_event(win32con.VK_RETURN, 0, 0, 0)
                time.sleep(0.05)
                win32api.keybd_event(win32con.VK_RETURN, 0, win32con.KEYEVENTF_KEYUP, 0)
            return True
        except: return False

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

        if self.action_type == 'text':
            text = self.kwargs.get('text', '').strip()
            if not text:
                self.finished_signal.emit()
                return
            for _ in range(3):
                try:
                    win32clipboard.OpenClipboard()
                    win32clipboard.EmptyClipboard()
                    win32clipboard.SetClipboardText(text)
                    win32clipboard.CloseClipboard()
                    break
                except: time.sleep(0.1)

        for idx, (pid, hwnd) in enumerate(active_pids_hwnds, 1):
            if not WindowUtils.bring_to_front(hwnd, focus=True): 
                continue
            
            if self.action_type == 'f12':
                time.sleep(0.8 if idx == 1 else 0.6)
            else:
                time.sleep(0.5 if idx == 1 else 0.3)
            
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
                    self.log_signal.emit(f"📍 URL 전송 ({idx}/{len(active_pids_hwnds)})")
                except: pass
                
            elif self.action_type == 'text':
                WindowUtils.ensure_modifiers_released()
                time.sleep(0.1)
                
                send_enter = self.kwargs.get('send_enter', False)
                if self.send_text_safely(hwnd, text, send_enter):
                    suffix = "+Enter" if send_enter else ""
                    self.log_signal.emit(f"📝 텍스트 전송{suffix} ({idx}/{len(active_pids_hwnds)})")
                else:
                    self.log_signal.emit(f"⚠️ 텍스트 전송 실패 ({idx}/{len(active_pids_hwnds)})")
                    
            elif self.action_type == 'f12':
                if self.send_key_safely(hwnd, win32con.VK_F12):
                    self.log_signal.emit(f"🔧 F12 전송 ({idx}/{len(active_pids_hwnds)})")
                else:
                    self.log_signal.emit(f"⚠️ F12 전송 실패 ({idx}/{len(active_pids_hwnds)})")
                    
            elif self.action_type == 'key':
                km = { 'ctrl+t': (win32con.VK_CONTROL, 0x54), 'ctrl+w': (win32con.VK_CONTROL, 0x57), 'f5': (None, win32con.VK_F5) }
                combo = self.kwargs.get('key_combo', '')
                if combo in km:
                    mod, main = km[combo]
                    if mod: win32api.keybd_event(mod, 0, 0, 0)
                    win32api.keybd_event(main, 0, 0, 0)
                    time.sleep(0.05)
                    win32api.keybd_event(main, 0, win32con.KEYEVENTF_KEYUP, 0)
                    if mod: win32api.keybd_event(mod, 0, win32con.KEYEVENTF_KEYUP, 0)
                    self.log_signal.emit(f"⌨️ {combo} ({idx}/{len(active_pids_hwnds)})")
                    
            elif self.action_type == 'click':
                rel_x, rel_y = self.kwargs.get('rel_x', 0), self.kwargs.get('rel_y', 0)
                try:
                    if WindowUtils.click_at_position(hwnd, int(rel_x), int(rel_y)):
                        self.log_signal.emit(f"🖱️ 클릭 ({idx}/{len(active_pids_hwnds)})")
                    else:
                        self.log_signal.emit(f"⚠️ 클릭 실패 ({idx}/{len(active_pids_hwnds)})")
                except: pass
            
            time.sleep(0.15)
        self.finished_signal.emit()

# ==========================================
# UI 컴포넌트
# ==========================================
class HelpButton(QPushButton):
    """[수정] 마우스 오버 시 툴팁 즉시 표시, 클릭 시 팝업 고정 (사라짐 방지)"""
    def __init__(self, text, color, parent=None):
        super().__init__(text, parent)
        self.setFixedSize(80, 28)
        self.setStyleSheet(f"QPushButton {{ background-color: {color}; color: white; font-weight: bold; border-radius: 8px; border: none; font-size: 11px; }} QPushButton:hover {{ opacity: 0.9; }}")

    def enterEvent(self, event):
        # 마우스 오버: 즉시 툴팁 표시 (미리보기)
        QToolTip.showText(QCursor.pos(), self.toolTip(), self)
        super().enterEvent(event)

    def mousePressEvent(self, event):
        # 클릭: 팝업 메뉴로 고정 (클릭해야 사라짐)
        if event.button() == Qt.MouseButton.LeftButton:
            # 툴팁 내용을 담을 라벨 생성
            lbl = QLabel(self.toolTip())
            lbl.setStyleSheet(f"""
                QLabel {{
                    background-color: {Theme.SURFACE}; 
                    color: {Theme.TEXT_MAIN}; 
                    border: 1px solid {Theme.PRIMARY}; 
                    border-radius: 6px; 
                    padding: 8px;
                }}
            """)
            lbl.setTextFormat(Qt.TextFormat.RichText)
            
            # 메뉴 생성 (프레임 없는 팝업처럼 보이게 설정)
            menu = QMenu(self)
            menu.setWindowFlags(menu.windowFlags() | Qt.WindowType.FramelessWindowHint | Qt.WindowType.NoDropShadowWindowHint)
            menu.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            
            # 라벨을 메뉴 액션으로 추가
            act = QWidgetAction(menu)
            act.setDefaultWidget(lbl)
            menu.addAction(act)
            
            # 마우스 위치에 실행 (블로킹 동작) - 다른 곳 클릭 시 닫힘
            menu.exec(QCursor.pos())

class GridButton(QPushButton):
    def __init__(self, text, profile_id, parent_window):
        super().__init__(text)
        self.profile_id = profile_id
        self.parent_window = parent_window
        self.setCheckable(True)
        self.setFixedSize(BTN_SIZE, BTN_SIZE)
        self.is_closing = False
        self.is_active = False
        self.last_state = None 
        self.update_style()

    def update_style(self):
        is_managed = self.profile_id in self.parent_window.profile_windows
        current_state = (self.is_closing, self.is_active, is_managed, self.isChecked())
        
        if self.last_state == current_state:
            return 
        
        self.last_state = current_state

        base = "font-size: 13px; font-weight: bold; border-radius: 8px;"
        if self.is_closing: style = f"background-color: {Theme.DANGER}; color: white; border: none;"
        elif self.is_active: style = f"background-color: {Theme.ACTIVE}; color: white; border: 2px solid white;"
        elif is_managed: style = f"background-color: {Theme.PRIMARY}; color: white; border: none;"
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
        self.buttons = {}; self.profile_windows = {}
        self.is_dragging = False; self.is_right_dragging = False; self.last_hovered_id = None
        self.click_capture_mode = False
        self.click_capture_source_hwnd = None
        
        self.hotkey_monitor = GlobalHotkeyMonitor(self.on_f2_pressed)
        self.hotkey_monitor.start()
        
        calc_width = (BTN_SIZE * 10) + (H_SPACING * 9) + 20 + (WINDOW_LR_MARGIN * 2) + 4
        
        saved = AppDataConfig.load_window_position()
        if saved: 
            self.setGeometry(saved[0], saved[1], calc_width, saved[3])
        else: 
            self.setGeometry(100, 100, calc_width, 640)
        
        self.setFixedWidth(calc_width) 
        self.init_ui()
        self.check_timer = QTimer()
        self.check_timer.timeout.connect(self.check_windows_status)
        self.check_timer.start(200)

    def on_f2_pressed(self):
        if not self.click_capture_mode:
            self.click_capture_mode = True
            self.click_capture_source_hwnd = None
            self.status.setText("🎯 F2 활성 - 관리 중인 브라우저를 클릭하세요 (ESC: 취소)")

    def set_always_on_top(self, on):
        hwnd = int(self.winId()); flag = win32con.HWND_TOPMOST if on else win32con.HWND_NOTOPMOST
        win32gui.SetWindowPos(hwnd, flag, 0, 0, 0, 0, win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE)

    def init_ui(self):
        self.setStyleSheet(Styles.MAIN_WINDOW); central = QWidget(); self.setCentralWidget(central)
        layout = QVBoxLayout(central); layout.setSpacing(6)
        layout.setContentsMargins(WINDOW_LR_MARGIN, 8, WINDOW_LR_MARGIN, 12)
        
        header_layout = QHBoxLayout()
        
        # [수정] 커스텀 버튼 사용
        btn_help = HelpButton("💡 사용법", Theme.TEXT_SUB)
        
        help_text = """
        <p style='font-weight:bold; font-size:12px;'>[상태 색상]</p>
        <p>⬜ 미실행 &nbsp; 🟩 선택</p>
        <p>🟦 실행 &nbsp; &nbsp; 🟪 활성</p>
        <p>🟥 종료중</p>
        <hr>
        <p style='font-weight:bold; font-size:12px;'>[조작 방법]</p>
        <p>🖱️ <b>좌클릭/드래그:</b> 선택 및 활성화</p>
        <p>🖱️ <b>우클릭/드래그:</b> 해당 창 종료</p>
        <p>⌨️ <b>F2:</b> 클릭 좌표 동기화 모드</p>
        """
        btn_help.setToolTip(help_text)

        header = QLabel("🚀 Edge Multi-Launcher PRO"); header.setStyleSheet(Styles.LABEL_TITLE)
        
        header_layout.addStretch()  
        header_layout.addWidget(header) 
        header_layout.addStretch()  
        header_layout.addWidget(btn_help) 
        
        layout.addLayout(header_layout)
        
        layout.addWidget(self._create_control_card())
        
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
        
        btn_lay = QHBoxLayout()

        self.btn_launch = self._create_btn("실행 및 배치", Theme.SUCCESS, self.run_batch); btn_lay.addWidget(self.btn_launch)
        btn_lay.addWidget(self._create_btn("선택 해제", Theme.TEXT_SUB, self.clear_selection))
        btn_lay.addWidget(self._create_btn("전체 활성화", Theme.PRIMARY, self.activate_all_browsers))
        btn_lay.addWidget(self._create_btn("전체 최소화", Theme.ACCENT, self.minimize_all_browsers))
        btn_lay.addWidget(self._create_btn("전체 종료", Theme.DANGER, self.close_all_managed)); layout.addLayout(btn_lay)
        
        self.status = QLabel("Ready"); self.status.setAlignment(Qt.AlignmentFlag.AlignCenter); self.status.setStyleSheet(Styles.LABEL_SUB); layout.addWidget(self.status)
        
        layout.addStretch(1) 

    def _create_control_card(self):
        card = QFrame()
        card.setStyleSheet(Styles.CARD)
        
        h_main_lay = QHBoxLayout(card)
        h_main_lay.setContentsMargins(10, 8, 10, 8)
        h_main_lay.setSpacing(10)

        left_box = QVBoxLayout()
        left_box.setSpacing(4)
        
        title = QLabel("🎮 통합 제어")
        title.setStyleSheet(f"color: {Theme.PRIMARY}; font-weight: bold; border:none; font-size: 12px;")
        left_box.addWidget(title)

        self.unified_input = QTextEdit()
        self.unified_input.setFixedHeight(70) 
        self.unified_input.setPlaceholderText("URL/텍스트 입력\n(줄바꿈 가능)")
        self.unified_input.setStyleSheet(Styles.INPUT)
        left_box.addWidget(self.unified_input)
        
        h_main_lay.addLayout(left_box, stretch=4) 

        btns = [
            ("🌐 URL(현재)", lambda: self.send_url_to_all(False), Theme.PRIMARY),
            ("✨ URL(새탭)", lambda: self.send_url_to_all(True), Theme.ACCENT),
            ("📑 새탭", lambda: self.send_shortcut("ctrl+t"), Theme.SURFACE),
            ("✖️ 탭닫기", lambda: self.send_shortcut("ctrl+w"), Theme.SURFACE),
            
            ("📝 텍스트", lambda: self.send_text_to_all(False), Theme.SPECIAL),
            ("↵ 엔터포함", lambda: self.send_text_to_all(True), Theme.SUCCESS),
            ("🔃 F5", lambda: self.send_shortcut("f5"), Theme.SURFACE),
            ("🔧 F12", self.send_f12, Theme.SURFACE),
        ]

        right_grid = QGridLayout()
        right_grid.setSpacing(4)
        right_grid.setContentsMargins(0, 0, 0, 0)

        for i, (text, func, color) in enumerate(btns):
            b = QPushButton(text)
            b.setMinimumHeight(32)
            if color == Theme.SURFACE:
                b.setStyleSheet(Styles.BTN_CMD)
            else:
                b.setStyleSheet(f"QPushButton {{ background: {color}; color: white; border: none; font-weight: bold; border-radius: 6px; font-size: 11px; }} QPushButton:hover {{ opacity: 0.9; }}")
            b.clicked.connect(func)
            right_grid.addWidget(b, i // 4, i % 4)

        h_main_lay.addLayout(right_grid, stretch=6) 
        
        return card

    def _create_btn(self, text, color, func):
        btn = QPushButton(text); btn.setFixedHeight(35); btn.clicked.connect(func); btn.setStyleSheet(f"QPushButton {{ background-color: {color}; color: white; font-weight: bold; border-radius: 8px; border: none; font-size: 11px; }} QPushButton:hover {{ opacity: 0.9; }}"); return btn

    def activate_all_browsers(self):
        for h in [h for h in self.profile_windows.values() if WindowUtils.is_window_valid(h)]: WindowUtils.bring_to_front(h, focus=True); time.sleep(0.05)

    def minimize_all_browsers(self):
        for h in [h for h in self.profile_windows.values() if WindowUtils.is_window_valid(h)]:
            try: win32gui.ShowWindow(h, win32con.SW_MINIMIZE)
            except: pass

    def send_url_to_all(self, new_tab=False):
        url = self.unified_input.toPlainText().strip()
        if not url: return
        self.sync_thread = SyncThread('url', self.profile_windows, url=url, new_tab=new_tab)
        self.sync_thread.log_signal.connect(self.status.setText)
        self.sync_thread.start()

    def send_text_to_all(self, with_enter=False):
        text = self.unified_input.toPlainText().strip()
        if not text: 
            self.status.setText("⚠️ 전송할 텍스트가 없습니다")
            return
        self.sync_thread = SyncThread('text', self.profile_windows, text=text, send_enter=with_enter)
        self.sync_thread.log_signal.connect(self.status.setText)
        self.sync_thread.start()

    def send_f12(self):
        self.sync_thread = SyncThread('f12', self.profile_windows)
        self.sync_thread.log_signal.connect(self.status.setText)
        self.sync_thread.start()

    def send_shortcut(self, key):
        self.sync_thread = SyncThread('key', self.profile_windows, key_combo=key)
        self.sync_thread.log_signal.connect(self.status.setText)
        self.sync_thread.start()

    def check_windows_status(self):
        try:
            if self.click_capture_mode and not self.click_capture_source_hwnd:
                if win32api.GetAsyncKeyState(win32con.VK_ESCAPE) & 0x8000:
                    self.click_capture_mode = False
                    self.status.setText("🚫 동기화 취소됨 (ESC)")
                    return

                try:
                    if win32api.GetAsyncKeyState(win32con.VK_LBUTTON) & 0x8000:
                        time.sleep(0.05)
                        cursor_pos = win32api.GetCursorPos()
                        clicked_hwnd = win32gui.WindowFromPoint(cursor_pos)
                        root_hwnd = win32gui.GetAncestor(clicked_hwnd, win32con.GA_ROOT)
                        
                        if root_hwnd in self.profile_windows.values():
                            self.click_capture_source_hwnd = root_hwnd
                            client_pt = win32gui.ScreenToClient(root_hwnd, cursor_pos)
                            
                            self.status.setText(f"✅ 좌표 캡처: ({client_pt[0]}, {client_pt[1]}) - 전송 중...")
                            
                            self.sync_thread = SyncThread('click', self.profile_windows, 
                                                        rel_x=client_pt[0], rel_y=client_pt[1])
                            self.sync_thread.log_signal.connect(self.status.setText)
                            self.sync_thread.start()
                            
                            self.click_capture_mode = False
                            time.sleep(0.2)
                        else:
                            self.click_capture_mode = False
                            self.status.setText("🚫 동기화 취소됨 (외부 클릭)")
                            time.sleep(0.2)
                except: pass
            
            fg_hwnd = win32gui.GetForegroundWindow()
            for pid, hwnd in list(self.profile_windows.items()):
                if not WindowUtils.is_window_valid(hwnd):
                    del self.profile_windows[pid]
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
        except KeyboardInterrupt:
            # [추가] 타이머 내부에서 인터럽트 발생 시 무시하고 종료 흐름 따름
            pass

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
        self.check_timer.stop()
        self.hotkey_monitor.stop()
        pids = list(self.profile_windows.keys())
        if pids:
            rep = QMessageBox.question(self, "종료 확인", f"런처 종료 시 관리 중인 {len(pids)}개의 브라우저도 모두 종료하시겠습니까?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if rep == QMessageBox.StandardButton.Yes:
                for p in pids: self.close_profile(p)
                self.save_pos(); e.accept()
            else: 
                self.check_timer.start(200)
                e.ignore()
        else: self.save_pos(); e.accept()

    def moveEvent(self, e): super().moveEvent(e); self.save_pos()
    def resizeEvent(self, e): super().resizeEvent(e); self.save_pos()

if __name__ == "__main__":
    # [추가] Ctrl+C (SIGINT) 발생 시 즉시 종료하도록 설정 (타이머 오류 방지)
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    app = QApplication(sys.argv); app.setStyle("Fusion")
    window = LauncherWindow(); window.show(); sys.exit(app.exec())