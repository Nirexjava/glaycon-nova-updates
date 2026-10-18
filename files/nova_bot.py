"""Nova Collector v4 - Crystal Saga Nova daily collector (embedded Qt WebEngine + screen recognition)."""
import os
import sys
import time
import threading
import traceback
import json
import uuid
from pathlib import Path
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
import cv2
import numpy as np
from PySide6.QtCore import Qt, QTimer, QUrl, QPoint, QStandardPaths, Signal, QEvent
from PySide6.QtGui import QImage, QCursor, QColor, QBrush, QIntValidator, QIcon, QShortcut, QKeySequence
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTextEdit, QLabel, QSplitter, QCheckBox, QTabWidget, QListWidget,
    QListWidgetItem, QSystemTrayIcon, QStyle, QMessageBox, QLineEdit, QComboBox, QSpinBox,
    QScrollArea, QFrame, QDialog, QPlainTextEdit, QFileDialog)
from PySide6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage, QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from cdp_input import Cdp, CdpError
from vision import best_match
import recorder
import updater
try:
    import theme
    from theme_defs import THEMES as THEME_LIST
except Exception:      # the look is optional - the bot works without it
    theme = None
    THEME_LIST = []
try:
    from lock_overlay import LockOverlay
except Exception:
    LockOverlay = None
try:
    from header_scenes import SCENES as SCENE_LIST
except Exception:
    SCENE_LIST = []
from shots import Library, Watcher, THUMB
from shots_ui import ShotsPanel
from tasks_def import TASKS, TASK_BY_ID, DEFAULT_POS, DISMISS_POINTS, ADVERT_POINTS

ROOT = Path(__file__).resolve().parent
VERSION = 'v4.47'
# Local-only DevTools port, used to send real browser-level mouse clicks and typing (see cdp_input.py).
CDP_PORT = int(os.environ.get('NOVA_CDP_PORT', '9333'))
os.environ['QTWEBENGINE_REMOTE_DEBUGGING'] = str(CDP_PORT)
# Keep the game rendering (and screenshots working) while the window is covered by other windows.
_FLAGS = '--disable-features=CalculateNativeWinOcclusion --disable-backgrounding-occluded-windows ' \
         '--disable-renderer-backgrounding --disable-background-timer-throttling'
os.environ['QTWEBENGINE_CHROMIUM_FLAGS'] = (os.environ.get('QTWEBENGINE_CHROMIUM_FLAGS', '') + ' ' + _FLAGS).strip()
URL = 'https://r2games.com/play?game=992'

# Where each picture is searched for (fractions of the game view: left, top, right, bottom).
WIDE = (.00, .10, .20, .98)       # the left menu of the Privileges / Shop / Perks screens
REGIONS = {
    'login_button': (.25, .35, .75, .75),
    'enter_game': (.20, .58, .78, .97),
    'ad_arrow': (.35, .00, .65, .10),
    'dragon_pack': (.15, .12, .85, .63),
    'notice_close': (.55, .03, 1.0, .50),
    'reward_obtained': (.19, .12, .82, .75),
    'back_arrow': (.00, .00, .25, .20),
    'icon_privileges': (.75, .03, 1.0, .20),
    'icon_shop': (.75, .03, 1.0, .20),
    'icon_perks': (.75, .03, 1.0, .20),
    'icon_pettheme': (.70, .06, .92, .19),
    'icon_slayer': (.80, .04, .99, .20),
    'valley_priest': (.68, .04, .92, .88),
    'valley_opt1': (.20, .68, .80, .84),
    'valley_opt2': (.20, .68, .80, .84),
    'valley_enter': (.40, .55, .75, .75),
    'valley_open': (.78, .05, .95, .20),
    'revive_btn': (.50, .25, .80, .65),
    'accept_revive': (.50, .25, .80, .65),
    'revive_spot': (.50, .25, .80, .65),
    'notice_limit': (.25, .35, .75, .65),
    'notice_confirm': (.25, .35, .75, .65),
    'icon_pettheme_b': (.70, .06, .92, .19),
    'icon_limited_b': (.50, .05, .95, .22),
    'settings_title': (.25, .00, .75, .16),
    'slayer_spin1': (.12, .55, .46, .88),
    'slayer_skip': (.50, .24, .88, .52),
    'pet_tab_battlepass': (.05, .80, .55, .98),
    'pet_claimall': (.45, .07, .75, .26),
    'pet_tab_battlepass_on': (.05, .80, .55, .98),
    'icon_daily': (.60, .60, 1.0, 1.0),
    'icon_limited': (.50, .05, .95, .22),
    'money_activate': (.0, .0, 1.0, 1.0),
    'money_unlock': (.0, .0, 1.0, 1.0),
    'lifetime_pass': WIDE,
    'menu_monthly': WIDE,
    'menu_deals': WIDE,
    'menu_daily_limit': WIDE,
    'menu_login_rewards': WIDE,
    'menu_online_bonus': WIDE,
    'menu_afk_bonus': WIDE,
    'claimed': (.62, .28, 1.0, .85),
    'claim_text': (.0, .0, 1.0, 1.0),     # replaced by each step's own region
    'claim_diamond': (.08, .68, .55, 1.0),
    'checkin_btn': (.45, .75, .90, 1.0),
    'shop_goldpack': (.15, .15, .62, .78),
    'purchase_btn': (.45, .40, .90, .80),
    'gold_tooltip': (.25, .35, .62, .70),
    'r2_login_tab': (.00, .78, .75, 1.0),
    'r2_claim_today': (.38, .05, .85, .22),
    'menu_level_rewards': WIDE,
    'char_title': (.00, .00, .45, .20),
    'rank_title': (.30, .00, .70, .26),
    'rank_claimpay': (.20, .50, .75, .85),
}
THRESH = {'purchase_btn': .70, 'gold_tooltip': .74, 'menu_daily_limit': .72, 'icon_privileges': .68, 'icon_shop': .68, 'icon_perks': .68, 'notice_close': .80, 'enter_game': .76, 'lifetime_pass': .77, 'claimed': .79, 'reward_obtained': .78, 'dragon_pack': .80, 'icon_pettheme': .76, 'icon_slayer': .72, 'valley_priest': .85, 'valley_opt1': .85, 'valley_opt2': .85, 'valley_enter': .85, 'valley_open': .85, 'revive_btn': .85, 'accept_revive': .85, 'revive_spot': .80, 'notice_limit': .85, 'notice_confirm': .85, 'icon_pettheme_b': .80, 'icon_limited_b': .80, 'settings_title': .80, 'slayer_spin1': .80, 'slayer_skip': .80, 'pet_tab_battlepass': .80, 'pet_claimall': .78, 'pet_tab_battlepass_on': .95, 'icon_daily': .74, 'icon_limited': .78,
          'back_arrow': .80, 'ad_arrow': .88, 'r2_login_tab': .78, 'r2_claim_today': .80, 'claim_text': .75, 'shop_goldpack': .90,
          'char_title': .80, 'rank_title': .80, 'rank_claimpay': .70, 'menu_level_rewards': .70}
DEFAULT_THRESH = .85
# Known PAID buttons. No click is ever allowed on top of one of these (checked on every click, whatever the task).
# Add a picture here whenever a new paid button is discovered. The free Gold Pack purchase is NOT in this list (it is checked separately).
MONEY_TPLS = ('money_activate', 'money_unlock', 'revive_spot')   # revive_spot = 'Revive on spot' (costs crystals)
MONEY_THRESH = .78
# Screens opened from an icon on the main page (not the top-right Perks/Privileges/Shop row): icon picture, name, and whether the icon may be missing.
EVENT_GOTO = {
    'pettheme': dict(icon='icon_pettheme', alts=('icon_pettheme_b',), name='Pet Theme', optional=True),
    'slayer': dict(icon='icon_slayer', name='Slayer', optional=True),
    'limited': dict(icon='icon_limited', alts=('icon_limited_b',), name='Limited-Time Event', optional=True),
    'daily': dict(icon='icon_daily', name='Daily', optional=False),
}
# Buttons that must also be GREEN (a grey "Claimed" button has the same word on it).
GREEN_CHECK = {'claim_text', 'checkin_btn', 'pet_claimall', 'rank_claimpay'}
# Pictures cut from the same screenshots share one scale; once one is found the others are
# searched near that scale first (much faster).
UI_TPLS = {'login_button', 'ad_arrow', 'icon_privileges', 'icon_shop', 'icon_perks', 'icon_pettheme', 'menu_monthly', 'menu_deals',
           'menu_daily_limit', 'menu_login_rewards', 'menu_online_bonus', 'menu_afk_bonus', 'claim_text', 'claim_diamond',
           'checkin_btn', 'shop_goldpack', 'purchase_btn', 'gold_tooltip', 'r2_login_tab', 'r2_claim_today', 'pet_tab_battlepass', 'pet_claimall', 'pet_tab_battlepass_on', 'icon_daily', 'icon_limited', 'icon_slayer', 'settings_title', 'slayer_spin1', 'slayer_skip', 'icon_pettheme_b', 'icon_limited_b'}
# Pictures that prove a screen has opened even if the back arrow is missed (the first open of a session can be slow).
OPEN_CUES = {'privileges': ['lifetime_pass', 'menu_monthly', 'menu_deals'], 'shop': ['menu_daily_limit', 'shop_goldpack'],
             'perks': ['menu_login_rewards', 'menu_online_bonus'], 'r2pass': ['r2_login_tab', 'r2_claim_today']}
ICON_FOR = {'privileges': 'icon_privileges', 'shop': 'icon_shop', 'perks': 'icon_perks', 'r2pass': 'icon_r2pass'}
# The three top-right icons sit in one row, left to right, equally spaced (ROW_STEP px apart at picture scale 1.0).
ROW_ORDER = ['icon_perks', 'icon_privileges', 'icon_shop']
ROW_POS = {'icon_perks': 0, 'icon_privileges': 1, 'icon_shop': 2, 'icon_r2pass': -3}   # R2 Pass: three places left of Perks
ROW_STEP = 95.0
# Login form: offsets from the middle of the orange Login button, in template pixels at scale 1.
LOGIN_OFFSETS = {'email': (-19, -217), 'password': (0, -140), 'keep': (-223, -79)}

# Game Settings window (opened from the gear under the minimap) and the Slayer screen. Fractions of the game view, taken from a recording.
SETTINGS_GEAR = (.9525, .1491)
SETTINGS_CLOSE = (.8819, .392)                  # empty spot outside the Settings window ("Tap outside to close")
SETTINGS_BOXES = ((-47.5, 366.5), (526.5, 366.5))   # Hide FX / Hide Models tick boxes: offset from the "Settings" banner centre (pixels at scale 1)
SKIP_BOX = (-248.0, 0.0)                        # Slayer "Skip Animation" tick box: offset from its label centre
SLAYER_DISMISS = (.668, .6866)                  # empty spot that closes the Slayer "Reward obtained" pop-up
SLAYER_MAX_SPINS = 60
MAP_LIST_POINT = (.80, .50)                 # the NPC name list on the right of the map window (scroll here)
MAP_LIST_ROI = (.73, .16, .875, .80)         # the part of the game view the list occupies (watched to see whether it moved)
MAP_GREEN_ROI = (.755, .25, .875, .75)       # green name buttons fill this when the map window is open
MAP_SCROLL_MODES = (('drag', 1), ('wheel', 1), ('drag', -1), ('wheel', -1))   # tried in turn until the list moves (drag = grab a name and pull it up, like by hand)
VALLEY_MAX_RUNS = 4                         # the game allows 2 a day; 4 is only a safety limit

try:
    SERVER_TZ = ZoneInfo('America/Los_Angeles')   # game server time (midnight reset)
except Exception:  # tzdata missing on Windows
    from datetime import timezone
    SERVER_TZ = timezone(timedelta(hours=-7))

# Which pictures each kind of step looks at. Matching runs in a worker thread, so the window
# never freezes however large the game window is.
POPUPS = ('reward_obtained', 'dragon_pack')


def step_needs(step):
    k = step['k']
    if k == 'ingame':
        return ['notice_close', 'login_button', 'enter_game', 'ad_arrow', 'dragon_pack', 'icon_privileges', 'back_arrow']
    if k == 'goto':
        return ['notice_close', 'ad_arrow', 'back_arrow', 'icon_privileges', 'icon_shop', 'icon_perks', 'dragon_pack'] + \
            list(OPEN_CUES.get(step.get('group'), [])) + ([EVENT_GOTO[step['group']]['icon']] + list(EVENT_GOTO[step['group']].get('alts', ())) if step.get('group') in EVENT_GOTO else [])
    if k == 'open':
        return [n for n in (step['find'], step.get('already'), 'dragon_pack', 'back_arrow' if step.get('already') else None) if n]
    if k == 'claim':
        return [n for n in (step['find'], step.get('claimed'), 'reward_obtained', 'dragon_pack') if n]
    if k == 'dotclaim':
        return ['reward_obtained', 'dragon_pack']
    if k == 'tapfrac':
        return [n for n in (step.get('expect'), 'dragon_pack', 'notice_close') if n]
    if k == 'perf':
        return ['settings_title', 'notice_close', 'dragon_pack', 'icon_privileges', 'icon_shop', 'icon_perks', 'back_arrow', 'ad_arrow']
    if k == 'valley':
        return ['valley_priest', 'valley_opt1', 'valley_opt2', 'valley_enter', 'valley_open', 'revive_btn', 'accept_revive', 'notice_limit', 'notice_confirm',
                'icon_privileges', 'icon_shop', 'icon_perks', 'back_arrow', 'notice_close', 'dragon_pack']
    if k == 'slayer':
        return ['slayer_spin1', 'slayer_skip', 'reward_obtained', 'dragon_pack', 'back_arrow']
    if k == 'shop_free':
        return ['shop_goldpack', 'purchase_btn', 'gold_tooltip', 'reward_obtained', 'dragon_pack', 'back_arrow', 'menu_daily_limit']
    return []


STYLE = """
QWidget { background:#0b0b0c; color:#cfcfd2; font-family:Consolas,'Cascadia Mono',monospace; font-size:11px; }
QTabWidget::pane { border:0; }
QTabBar::tab { background:#0b0b0c; color:#6d6d73; padding:7px 16px; letter-spacing:2px; border-bottom:2px solid transparent; }
QTabBar::tab:selected { color:#ffffff; border-bottom:2px solid #ffffff; }
QWidget#sidebar { background:#101012; border-right:1px solid #1d1d20; }
QLabel#caption { color:#6d6d73; letter-spacing:2px; font-size:10px; }
QLabel#taskTitle { color:#ffffff; font-size:14px; }
QLabel#muted { color:#6d6d73; }
QWidget#footer, QWidget#footer QLabel { background:#101012; color:#6d6d73; font-size:10px; letter-spacing:1px; }
QPushButton { background:#17171a; border:1px solid #2a2a2e; padding:6px 10px; letter-spacing:1px; }
QPushButton:hover { border-color:#5a5a60; }
QPushButton:disabled { color:#44444a; }
QPushButton#primary { background:#3a2410; border-color:#c4651a; color:#ffb070; }
QPushButton#day { background:#17171a; color:#8a8a90; border:1px solid #2a2a2e; padding:4px 0; min-width:40px; }
QPushButton#day:checked { background:#ffffff; color:#000000; border-color:#ffffff; }
QCheckBox#switch::indicator { width:30px; height:14px; border-radius:7px; background:#2a2a2e; border:1px solid #3a3a3e; }
QCheckBox#switch::indicator:checked { background:#c4651a; border-color:#c4651a; }
QListWidget, QTextEdit { background:#080809; border:1px solid #1d1d20; }
QListWidget::item { padding:4px; border-bottom:1px solid #141416; }
QListWidget::item:selected { background:#17171a; }
QLineEdit, QSpinBox, QComboBox { background:#17171a; border:1px solid #2a2a2e; padding:3px; }
QComboBox QAbstractItemView { background:#17171a; selection-background-color:#2a2a2e; }
QSplitter::handle { background:#1d1d20; }
QScrollArea { border:0; }
"""

DAY_NAMES = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']


class MainWindow(QMainWindow):
    remote_done = Signal(bool, str)

    log_signal = Signal(str)
    fallback_signal = Signal(int, int, str)
    analysis_done = Signal(object, object)
    analysing_reset = Signal()
    shot_saved = Signal(str)

    # ------------------------------------------------------------------ setup
    def __init__(self):
        super().__init__()
        self.log_signal.connect(self.log)
        self.fallback_signal.connect(self.qt_click)
        self.analysis_done.connect(self.on_analysis)
        self.analysing_reset.connect(lambda: setattr(self, 'analysing', False))
        self.shot_saved.connect(self.on_shot_saved)
        self.shots_panel = None
        self.shot_busy = False
        self.setWindowTitle('Glaycon Nova')
        if (ROOT / 'nova_icon.png').exists():
            self.setWindowIcon(QIcon(str(ROOT / 'nova_icon.png')))
        self.resize(1480, 920)
        self.running = False
        self.analysing = False
        self.results = None
        self.last_click = 0
        self.last_debug = 0
        self.positions_file = ROOT / 'calibration.json'
        self.state_file = ROOT / 'state.json'
        self.settings_file = ROOT / 'settings.json'
        self.history_file = ROOT / 'history.json'
        self.account_file = ROOT / 'account.json'
        self.cdp = Cdp(CDP_PORT)
        self.click_lock = threading.Lock()
        self.scale_hint = {}
        self.last_full = {}
        self.last_result = {}
        self.region_override = {}
        self.ui_scale = None
        self.cur_bgr = None
        self.snap_bgr = None
        self.last_frame = None
        self.auto_run_active = False
        self.run_started = 0
        self.page_loaded_at = None
        self.adbar_done = False
        self.login_busy = False
        self.login_done_at = 0.0
        self.accounts = []
        self.chain = []
        self.run_account = ''
        self.logged_in = None
        self.switch_t = 0.0
        self.bg_active = False
        self.cdp_warned = 0.0
        self.opened_once = False
        self.adfix = 0
        self.ad_wait_until = 0.0
        self.paused = False
        self.pause_t = 0.0
        self.pending_restart = None
        self.screen = None            # 'main', 'privileges', 'shop', 'perks' or None (unknown)
        self.queue = []
        self.qi = 0
        self.st = {}
        self.cur_task = None
        self.task_notes = {}
        self.task_failed = {}
        self.themes = None
        self.look_saved = {}
        self.scene_saved = {}
        self.lock_pos_saved = {}
        self.lock_ui = None
        self.manual_lock = False
        self.tcol = {'ok': '#4cd964', 'run': '#4ea1ff', 'fail': '#ff6b6b', 'wait': '#8a8a90', 'part': '#ffb340'}
        self.fail_memory = {}          # account -> {task id: note} from its last run (for RE-RUN FAILED)
        self._bot_input = False        # True while the bot itself sends a Qt click (never blocked / recorded)
        self.rec_folder = None
        self.rec_n = 0
        self.rec_t0 = 0.0
        self._lock_note_t = 0.0
        self.run_results = []
        self.fired = {}
        self.schedules = []
        self.sched_drafts = {}          # unsaved edits per schedule row (index -> copy)
        self.sched_btns = {}            # row index -> (SAVE, CANCEL) buttons
        self.positions = {}
        self.load_positions()
        self.templates = {}
        self.meta = {}
        try:
            self.meta = json.loads((ROOT / 'templates' / 'meta.json').read_text(encoding='utf-8'))
        except (ValueError, OSError):
            pass
        names = set(REGIONS) | set(self.meta)
        for name in names:
            img = cv2.imread(str(ROOT / 'templates' / f'{name}.png'), cv2.IMREAD_GRAYSCALE)
            if img is not None:
                self.templates[name] = img
        missing = [n for n in REGIONS if n not in self.templates and n != 'claim_text']
        self.build_ui()
        self.load_accounts()
        self.load_settings()
        self.refresh_account_widgets()
        self.rebuild_schedule_rows()
        self.start_look()
        self.start_lock_ui()
        self.tray = None
        try:
            if QSystemTrayIcon.isSystemTrayAvailable():
                self.tray = QSystemTrayIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon), self)
                self.tray.show()
        except Exception:
            self.tray = None
        self.auto_timer = QTimer(self)
        self.auto_timer.setInterval(30000)
        self.auto_timer.timeout.connect(self.auto_check)
        self.auto_timer.start()
        self.timer = QTimer(self)
        self.timer.setInterval(80)
        self.timer.timeout.connect(self.tick)
        self.clock_timer = QTimer(self)
        self.clock_timer.setInterval(1000)
        self.clock_timer.timeout.connect(self.update_clock)
        self.clock_timer.start()
        self.refresh_tasks()
        self.refresh_history()
        self.update_clock()
        self.update_shown = None
        self.step_started = time.monotonic()
        self.wd_restarts = {}
        self.last_report = ''
        self._report_box = None
        self.watchdog_timer = QTimer(self)
        self.watchdog_timer.setInterval(20000)
        self.watchdog_timer.timeout.connect(self.watchdog_check)
        self.watchdog_timer.start()
        self.remote_done.connect(self.on_remote_done)
        QTimer.singleShot(8000, lambda: self.check_updates(False))
        self.update_timer = QTimer(self)
        self.update_timer.setInterval(60000)
        self.update_timer.timeout.connect(lambda: self.check_updates(False))
        self.update_timer.start()
        QTimer.singleShot(30000, lambda: updater.confirm_ok(ROOT, VERSION))     # the new version started fine: keep it
        try:
            note = updater.startup_note(ROOT, VERSION)
            if note:
                self.log(note)
        except Exception:
            pass
        self.log('Browser loading. If the game shows the login page and an account is saved, the bot logs in by itself.')
        if missing:
            self.log('WARNING: missing picture files: ' + ', '.join(missing))

    def load_positions(self):
        if self.positions_file.exists():
            try:
                data = json.loads(self.positions_file.read_text(encoding='utf-8'))
                self.positions = {k: tuple(v) for k, v in data.items()
                                  if k in ('privileges', 'shop', 'perks', 'r2pass', 'ad_arrow') and isinstance(v, list)
                                  and len(v) == 2 and all(isinstance(x, (int, float)) and 0 <= x <= 1 for x in v)}
            except (ValueError, OSError):
                pass

    # --------------------------------------------------------------------- UI
    @staticmethod
    def caption(text):
        label = QLabel(text)
        label.setObjectName('caption')
        return label

    def build_ui(self):
        self.setStyleSheet(STYLE)
        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        outer.addWidget(self.tabs, 1)

        # ---- Controller tab: task sidebar + game + log (+ setup panel on the right)
        split = QSplitter(Qt.Orientation.Horizontal)
        self.split = split
        side = QWidget()
        side.setObjectName('sidebar')
        side.setMinimumWidth(240)
        side.setMaximumWidth(320)
        sv = QVBoxLayout(side)
        sv.setContentsMargins(10, 10, 10, 10)
        sv.addWidget(self.caption('DAILY COLLECTION'))
        self.badge = QLabel('')
        self.badge.setObjectName('badge')
        sv.addWidget(self.badge)
        self.status = QLabel('Idle')
        self.status.setObjectName('muted')
        self.status.setWordWrap(True)
        sv.addWidget(self.status)
        sv.addWidget(self.caption('ACCOUNT'))
        self.acct_combo = QComboBox()
        self.acct_combo.currentIndexChanged.connect(self.on_acct_combo)
        sv.addWidget(self.acct_combo)
        row = QHBoxLayout()
        self.start_btn = QPushButton('RUN NOW')
        self.start_btn.setObjectName('primary')
        self.start_btn.clicked.connect(lambda: self.run_now())
        row.addWidget(self.start_btn)
        self.stop_btn = QPushButton('STOP')
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(lambda: self.stop())
        row.addWidget(self.stop_btn)
        sv.addLayout(row)
        row2 = QHBoxLayout()
        self.pause_btn = QPushButton('PAUSE')
        self.pause_btn.setEnabled(False)
        self.pause_btn.setToolTip('Pause the run at any time; RESUME carries on from the step it was on.')
        self.pause_btn.clicked.connect(self.toggle_pause)
        row2.addWidget(self.pause_btn)
        self.refresh_btn = QPushButton('REFRESH')
        self.refresh_btn.setToolTip('Reload the game and choose where to continue: from the current collection or from the beginning.')
        self.refresh_btn.clicked.connect(self.refresh_run)
        row2.addWidget(self.refresh_btn)
        sv.addLayout(row2)
        self.runall_btn = QPushButton('RUN ALL ACCOUNTS')
        self.runall_btn.setToolTip('Collect for every account one after another (accounts already done today are skipped).')
        self.runall_btn.clicked.connect(self.run_all_accounts)
        sv.addWidget(self.runall_btn)
        self.rerun_btn = QPushButton('RE-RUN FAILED')
        self.rerun_btn.setToolTip('Run again only the collections that failed last time (for the selected account).')
        self.rerun_btn.clicked.connect(self.rerun_failed)
        sv.addWidget(self.rerun_btn)
        self.reset_btn = QPushButton(f'RESET PROGRESS  (0/{len(TASKS)})')
        self.reset_btn.setToolTip('Forget what was collected today so the list shows 0 done and you can run everything again from the start.')
        self.reset_btn.clicked.connect(self.reset_progress)
        sv.addWidget(self.reset_btn)
        sv.addWidget(self.caption('RUN NOW STARTS FROM'))
        self.from_combo = QComboBox()
        self.from_combo.addItem('Next unfinished collection', 'next')
        for t in TASKS:
            self.from_combo.addItem(t['title'] + '  (and everything after)', t['id'])
        sv.addWidget(self.from_combo)
        self.task_list = QListWidget()
        self.task_list.setMaximumHeight(190)
        self.task_list.setToolTip('Double-click a collection to run just that one.')
        self.task_list.itemDoubleClicked.connect(self.run_single)
        sv.addWidget(self.task_list)
        self.reload_btn = QPushButton('RELOAD GAME')
        self.reload_btn.clicked.connect(self.reload_game)
        sv.addWidget(self.reload_btn)
        self.update_btn = QPushButton('UPDATE')
        self.update_btn.setToolTip('Look for a new version of the bot (in the updates folder). If there is one it shows what is new and installs it.')
        self.update_btn.clicked.connect(lambda: self.check_updates(True))
        sv.addWidget(self.update_btn)
        self.report_btn = QPushButton('LAST REPORT')
        self.report_btn.setToolTip('Show the summary of the last run: what was collected, what failed and why.')
        self.report_btn.clicked.connect(self.show_report)
        sv.addWidget(self.report_btn)
        self.log_btn = QPushButton('LOG  (view / export)')
        self.log_btn.setToolTip('Open the full log of everything the bot did, and save it as a file to send for checking.')
        self.log_btn.clicked.connect(self.open_log)
        sv.addWidget(self.log_btn)
        shot_row = QHBoxLayout()
        self.cap_btn = QPushButton('CAPTURE')
        self.cap_btn.setToolTip('Take a screenshot of the game now (F9).')
        self.cap_btn.clicked.connect(lambda: self.shot_capture_now(self.shots_panel.current_label() if self.shots_panel else ''))
        self.shots_btn = QPushButton('SCREENSHOTS')
        self.shots_btn.setToolTip('Open the Screenshot Manager.')
        self.shots_btn.clicked.connect(lambda: self.shots_panel is not None and self.tabs.setCurrentWidget(self.shots_panel))
        shot_row.addWidget(self.cap_btn)
        shot_row.addWidget(self.shots_btn)
        sv.addLayout(shot_row)
        self.rec_btn = QPushButton('REC  (click recorder)')
        self.rec_btn.setCheckable(True)
        self.rec_btn.setToolTip('Record every click you make in the game: saves a screenshot of the game, a copy with the click marked, '
                                'and a list of click positions into the Recordings folder. Use it to show exactly what you did.')
        self.rec_btn.toggled.connect(self.toggle_rec)
        sv.addWidget(self.rec_btn)
        self.lock_cb = QCheckBox('Lock the game view while the bot runs')
        self.lock_cb.setChecked(True)
        self.lock_cb.setToolTip('Stray clicks and key presses on the game are ignored while a run is going, so you cannot upset it. '
                                'Untick to take control. The bot\'s own clicks always work, and the lock lifts while paused.')
        self.lock_cb.toggled.connect(self.save_settings)
        self.lock_cb.hide()      # no separate checkbox: the draggable lock badge on the game is the one lock control
        self.setup_btn = QPushButton('SETUP / CALIBRATION')
        self.setup_btn.setCheckable(True)
        self.setup_btn.toggled.connect(self.toggle_setup)
        sv.addWidget(self.setup_btn)
        self.streak_label = QLabel('')
        self.streak_label.setObjectName('muted')
        sv.addWidget(self.streak_label)
        sv.addSpacing(4)
        sv.addWidget(self.caption('HISTORY'))
        self.history_list = QListWidget()
        sv.addWidget(self.history_list, 1)
        split.addWidget(side)

        main = QWidget()
        mv = QVBoxLayout(main)
        mv.setContentsMargins(0, 0, 0, 0)
        mv.setSpacing(0)
        self.browser = QWebEngineView()
        profile_dir = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
        self.profile = QWebEngineProfile('NovaGameProfile', self)
        profile = self.profile
        profile.setPersistentStoragePath(str(Path(profile_dir) / 'web_profile'))
        profile.setCachePath(str(Path(profile_dir) / 'web_cache'))
        profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.AllowPersistentCookies)
        self.page = QWebEnginePage(profile, self.browser)
        self.browser.setPage(self.page)
        self.browser.settings().setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        self.browser.loadFinished.connect(self.on_loaded)
        self.browser.setUrl(QUrl(URL))
        mv.addWidget(self.browser, 1)
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumHeight(130)
        mv.addWidget(self.log_view)
        split.addWidget(main)
        self.game_area = main

        # Setup panel: docked to the right of the game so the game stays visible
        self.setup_panel = QWidget()
        self.setup_panel.setObjectName('sidebar')
        self.setup_panel.setMinimumWidth(260)
        self.setup_panel.setMaximumWidth(340)
        pv = QVBoxLayout(self.setup_panel)
        pv.setContentsMargins(10, 10, 10, 10)
        pv.addWidget(self.caption('BACKUP CALIBRATION'))
        note = QLabel('Normally not needed: the bot finds the icons by picture. If one is ever missed, click Capture, '
                      'then hover over that icon in the game within 3 seconds. The panel hides itself during the countdown.')
        note.setWordWrap(True)
        note.setObjectName('muted')
        pv.addWidget(note)
        cal = [('privileges', 'Privileges icon'), ('shop', 'Shop icon'), ('perks', 'Perks icon'), ('r2pass', 'R2 Pass icon'), ('ad_arrow', 'Ad-bar arrow')]
        for key, label in cal:
            btn = QPushButton('Capture ' + label)
            btn.clicked.connect(lambda checked=False, k=key: self.calibrate(k))
            pv.addWidget(btn)
        pv.addWidget(self.caption('TEST CLICKS'))
        for key, label in cal:
            tbtn = QPushButton('Test click ' + label)
            tbtn.clicked.connect(lambda checked=False, k=key: self.test_click(k))
            pv.addWidget(tbtn)
        pv.addWidget(self.caption('DIAGNOSTICS'))
        self.debug = QCheckBox('Log recognition scores')
        pv.addWidget(self.debug)
        self.diagnostic_btn = QPushButton('Diagnose visible game screen')
        self.diagnostic_btn.clicked.connect(self.diagnose)
        pv.addWidget(self.diagnostic_btn)
        pv.addStretch(1)
        self.setup_panel.hide()
        split.addWidget(self.setup_panel)
        split.setStretchFactor(1, 1)
        split.setSizes([260, 1220, 0])
        self.tabs.addTab(split, 'CONTROLLER')

        # ---- Accounts tab (several accounts; each schedule picks one)
        acc = QWidget()
        av = QHBoxLayout(acc)
        av.setContentsMargins(20, 16, 20, 16)
        left = QVBoxLayout()
        left.addWidget(self.caption('GAME ACCOUNTS'))
        self.acct_list = QListWidget()
        self.acct_list.setMaximumWidth(260)
        self.acct_list.currentRowChanged.connect(self.acct_selected)
        left.addWidget(self.acct_list, 1)
        newb = QPushButton('+ NEW ACCOUNT')
        newb.clicked.connect(self.acct_new)
        left.addWidget(newb)
        av.addLayout(left)
        right = QVBoxLayout()
        right.addWidget(self.caption('DETAILS'))
        right.addWidget(QLabel('If the game shows the login page (or another account is logged in), the bot logs in with these details.'))
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText('Name (for example Glaycon)')
        self.name_edit.setMaximumWidth(380)
        right.addWidget(self.name_edit)
        self.email_edit = QLineEdit()
        self.email_edit.setPlaceholderText('E-mail')
        self.email_edit.setMaximumWidth(380)
        right.addWidget(self.email_edit)
        self.password_edit = QLineEdit()
        self.password_edit.setPlaceholderText('Password')
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_edit.setMaximumWidth(380)
        right.addWidget(self.password_edit)
        self.autologin_cb = QCheckBox('Log in automatically when the game shows the login page')
        self.autologin_cb.setChecked(True)
        right.addWidget(self.autologin_cb)
        save = QPushButton('SAVE ACCOUNT')
        save.setMaximumWidth(380)
        save.clicked.connect(self.save_account)
        right.addWidget(save)
        delb = QPushButton('REMOVE THIS ACCOUNT')
        delb.setMaximumWidth(380)
        delb.clicked.connect(self.remove_account)
        right.addWidget(delb)
        warn = QLabel('Saved only on this PC, in account.json inside this folder (not encrypted). '
                      'Do not share that file or zip the folder with it inside.')
        warn.setObjectName('muted')
        warn.setWordWrap(True)
        warn.setMaximumWidth(380)
        right.addWidget(warn)
        self.acc_stats = QLabel('')
        right.addWidget(self.acc_stats)
        self.logged_label = QLabel('')
        self.logged_label.setObjectName('muted')
        right.addWidget(self.logged_label)
        logout = QPushButton('LOG OUT OF THE GAME (CLEAR SAVED LOGIN COOKIES)')
        logout.setMaximumWidth(380)
        logout.clicked.connect(self.clear_login)
        right.addWidget(logout)
        right.addStretch(1)
        av.addLayout(right, 1)
        self.tabs.addTab(acc, 'ACCOUNTS')

        # ---- Schedules tab (days, time, on/off per row)
        sch = QWidget()
        sv2 = QVBoxLayout(sch)
        sv2.setContentsMargins(16, 12, 16, 12)
        top = QHBoxLayout()
        top.addWidget(self.caption('SCHEDULE  -  starts the chosen collections at the set times (local PC time). Keep this window open.'))
        top.addStretch(1)
        add = QPushButton('+ ADD')
        add.clicked.connect(self.add_schedule)
        top.addWidget(add)
        sv2.addLayout(top)
        head = QHBoxLayout()
        for text, width in (('', 44), ('ACCOUNT', 150), ('COLLECTIONS', 190), ('DAYS', 300), ('TIME', 120)):
            lab = self.caption(text)
            lab.setFixedWidth(width)
            head.addWidget(lab)
        head.addStretch(1)
        sv2.addLayout(head)
        self.sched_box = QVBoxLayout()
        self.sched_box.setSpacing(4)
        sv2.addLayout(self.sched_box)
        self.notify_cb = QCheckBox('Show a Windows notification when a run finishes')
        self.notify_cb.setChecked(True)
        self.notify_cb.toggled.connect(self.save_settings)
        self.bg_cb = QCheckBox('Background mode: if the window is minimised when a run starts, keep working invisibly '
                               '(click-through, no pop-up) and minimise again afterwards')
        self.bg_cb.setChecked(True)
        self.bg_cb.toggled.connect(self.save_settings)
        sv2.addSpacing(6)
        sv2.addWidget(self.bg_cb)
        sv2.addSpacing(10)
        sv2.addWidget(self.notify_cb)
        sv2.addSpacing(10)
        look = QHBoxLayout()
        look.addWidget(self.caption('ANIMATED SCENES'))
        self.scene_combo = QComboBox()
        self.scene_combo.addItem('Off', 'off')
        for sid, sname in SCENE_LIST:
            self.scene_combo.addItem(sname, sid)
        self.scene_combo.setMinimumWidth(150)
        self.scene_combo.currentIndexChanged.connect(self.on_scene)
        look.addWidget(self.scene_combo)
        look.addSpacing(8)
        look.addWidget(self.caption('THEME'))
        self.theme_combo = QComboBox()
        for t in THEME_LIST:
            self.theme_combo.addItem(t['name'], t['id'])
        self.theme_combo.currentIndexChanged.connect(self.on_theme)
        look.addWidget(self.theme_combo)
        look.addSpacing(12)
        look.addWidget(self.caption('HEADER'))
        self.header_mode_combo = QComboBox()
        self.header_mode_combo.addItem('Animated', 'animated')
        self.header_mode_combo.addItem('Static', 'static')
        self.header_mode_combo.currentIndexChanged.connect(self.on_header_mode)
        look.addWidget(self.header_mode_combo)
        self.anim_cb = QCheckBox('Animation on')
        self.anim_cb.setChecked(True)
        self.anim_cb.toggled.connect(self.on_anim_toggle)
        look.addWidget(self.anim_cb)
        replay = QPushButton('REPLAY HEADER')
        replay.clicked.connect(lambda: self.themes and self.themes.replay())
        look.addWidget(replay)
        restore = QPushButton('RESTORE DEFAULT')
        restore.clicked.connect(lambda: self.themes and self.themes.restore_default())
        look.addWidget(restore)
        look.addStretch(1)
        sv2.addLayout(look)
        scn = QHBoxLayout()
        scn.addWidget(self.caption('SCENE SPEED'))
        self.scene_speed_combo = QComboBox()
        for lab, v in (('0.5x', 0.5), ('1x', 1.0), ('1.5x', 1.5), ('2x', 2.0)):
            self.scene_speed_combo.addItem(lab, v)
        self.scene_speed_combo.setCurrentIndex(1)
        self.scene_speed_combo.currentIndexChanged.connect(self.on_scene_speed)
        scn.addWidget(self.scene_speed_combo)
        prev = QPushButton('PREVIEW / REPLAY SCENE')
        prev.clicked.connect(lambda: self.themes and self.themes.preview_scene())
        scn.addWidget(prev)
        scn.addStretch(1)
        sv2.addLayout(scn)
        self.sched_info = QLabel('')
        self.sched_info.setObjectName('muted')
        self.sched_info.setWordWrap(True)
        sv2.addWidget(self.sched_info)
        sv2.addWidget(QLabel('At the time you set (and SAVE), the bot clears that account\'s "done" marks - like the game\'s daily reset - and then collects everything again. Times are your PC\'s local time, so it works whatever the game server\'s reset time is.'))
        sv2.addStretch(1)
        self.tabs.addTab(sch, 'SCHEDULES')

        # ---- Screenshot Manager tab (a failure here must never stop the bot from working)
        try:
            self.shot_lib = Library(ROOT)
            self.shot_watch = Watcher()
            self.shots_panel = ShotsPanel(self, self.shot_lib)
            self.tabs.addTab(self.shots_panel, 'SCREENSHOTS')
            self.shot_timer = QTimer(self)
            self.shot_timer.setInterval(1000)
            self.shot_timer.timeout.connect(self.shot_tick)
            self.shot_timer.start()
            sc = QShortcut(QKeySequence('F9'), self)
            sc.setContext(Qt.ShortcutContext.ApplicationShortcut)
            sc.activated.connect(lambda: self.shot_capture_now(self.shots_panel.current_label()))
            self.shot_shortcut = sc
        except Exception as exc:
            self.shots_panel = None
            self.shot_lib = None
            print('Screenshot Manager could not start:', exc)

        # ---- Footer: version, server time, reset countdown
        foot = QWidget()
        foot.setObjectName('footer')
        fl = QHBoxLayout(foot)
        fl.setContentsMargins(10, 3, 10, 3)
        fl.addWidget(QLabel(VERSION))
        fl.addStretch(1)
        self.clock_label = QLabel('')
        fl.addWidget(self.clock_label)
        outer.addWidget(foot)

    def on_theme(self, *_):
        if self.themes is not None:
            self.themes.set_theme(self.theme_combo.currentData())

    def on_scene(self, *_):
        if self.themes is not None:
            self.themes.set_scene(self.scene_combo.currentData())

    def on_scene_speed(self, *_):
        if self.themes is not None:
            self.themes.set_scene_speed(self.scene_speed_combo.currentData())

    def on_header_mode(self, *_):
        if self.themes is not None:
            self.themes.set_mode(self.header_mode_combo.currentData())

    def on_anim_toggle(self, on):
        if self.themes is not None:
            self.themes.set_anim(on)

    def game_locked(self):
        """True while the user's own mouse/keyboard input on the game is being ignored."""
        return bool(self.manual_lock or (self.running and not self.paused and self.lock_cb.isChecked()))

    def toggle_game_lock(self):
        if self.game_locked():
            self.manual_lock = False
            if self.running and not self.paused and self.lock_cb.isChecked():
                self.lock_cb.setChecked(False)           # also lift the automatic run lock
                self.log('Game unlocked (the automatic run lock was switched off).')
            else:
                self.log('Game unlocked.')
        else:
            self.manual_lock = True
            self.hook_input()
            self.log('Game locked: your clicks and keys on the game are ignored. The bot keeps working. Click the lock to unlock.')
        if self.lock_ui is not None:
            self.lock_ui.refresh()

    def start_lock_ui(self):
        if LockOverlay is None:
            return
        try:
            th = None
            try:
                th = theme.THEME_BY_ID[self.themes.theme_id] if self.themes is not None else None
            except Exception:
                th = None
            if th is None:
                from theme_defs import THEME_BY_ID, DEFAULT_THEME
                th = THEME_BY_ID[DEFAULT_THEME]
            self.lock_ui = LockOverlay(self.game_area, self, self.lock_pos_saved, th)
        except Exception as exc:
            self.lock_ui = None
            self.log(f'Lock control unavailable ({exc}).')

    def start_look(self):
        """Create the theme system (header, palette menu, icons). If anything fails the bot just keeps the classic look."""
        if theme is None:
            return
        try:
            self.themes = theme.ThemeManager(self, STYLE, self.look_saved, self.scene_saved)
        except Exception as exc:
            self.themes = None
            self.setStyleSheet(STYLE)
            self.log(f'Themes unavailable ({exc}) - using the classic look.')

    def toggle_setup(self, on):
        self.setup_panel.setVisible(bool(on))
        if on:
            total = max(900, self.split.width())
            self.split.setSizes([260, total - 260 - 300, 300])

    def enter_background(self):
        """Window minimised: Chromium stops drawing, so bring it back nearly transparent, click-through and unfocused."""
        if self.bg_active or not self.bg_cb.isChecked() or not self.isMinimized():
            return
        try:
            self.bg_active = True
            self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
            self.setWindowFlag(Qt.WindowType.WindowTransparentForInput, True)
            self.setWindowFlag(Qt.WindowType.WindowDoesNotAcceptFocus, True)
            self.setWindowOpacity(0.02)
            self.setWindowState(Qt.WindowState.WindowNoState)
            self.showNormal()
            self.lower()
            try:
                self.page.setLifecycleState(QWebEnginePage.LifecycleState.Active)
                if hasattr(self.page, 'setVisible'):
                    self.page.setVisible(True)
            except Exception:
                pass
            self.log('Background mode: window restored invisibly so the game keeps drawing; it will minimise again afterwards.')
        except Exception as exc:
            self.log(f'Background mode failed: {exc}')

    def leave_background(self):
        if not self.bg_active:
            return
        self.bg_active = False
        try:
            self.setWindowOpacity(1.0)
            self.setWindowFlag(Qt.WindowType.WindowTransparentForInput, False)
            self.setWindowFlag(Qt.WindowType.WindowDoesNotAcceptFocus, False)
            self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, False)
            self.showMinimized()
        except Exception as exc:
            self.log(f'Could not restore the window state: {exc}')

    def hide_setup_temporarily(self):
        """Hide the setup panel so the game has its normal size; returns True if it was showing."""
        was = self.setup_panel.isVisible()
        if was:
            self.setup_panel.hide()
        return was

    def restore_setup(self, was):
        if was:
            self.setup_panel.show()

    # ----------------------------------------------------------- schedule rows
    def add_schedule(self):
        self.schedules.append({'id': uuid.uuid4().hex[:8], 'on': False, 'acct': self.acct_names()[0] if self.acct_names() else '', 'seq': 'all', 'days': [True] * 7, 'h': 8, 'm': 10})
        self.save_settings()
        self.rebuild_schedule_rows()

    def remove_schedule(self, index):
        if 0 <= index < len(self.schedules):
            self.schedules.pop(index)
            self.sched_drafts = {(j if j < index else j - 1): d for j, d in self.sched_drafts.items() if j != index}
            self.save_settings()
            self.rebuild_schedule_rows()

    def rebuild_schedule_rows(self):
        while self.sched_box.count():
            item = self.sched_box.takeAt(0)
            lay = item.layout()
            if lay is not None:
                while lay.count():
                    w = lay.takeAt(0).widget()
                    if w is not None:
                        w.deleteLater()
            elif item.widget() is not None:
                item.widget().deleteLater()
        seq_items = [('all', 'All daily collections')] + [(t['id'], t['title']) for t in TASKS]
        self.sched_btns = {}
        for i, saved in enumerate(self.schedules):
            s = self.sched_drafts.get(i, saved)           # show unsaved edits while they are pending
            row = QHBoxLayout()
            on = QCheckBox()
            on.setObjectName('switch')
            on.setChecked(bool(saved.get('on')))
            on.setFixedWidth(44)
            on.toggled.connect(lambda v, i=i: self.sched_toggle(i, bool(v)))
            row.addWidget(on)
            acombo = QComboBox()
            for nm in self.acct_names():
                acombo.addItem(nm, nm)
            ai = acombo.findData(s.get('acct'))
            acombo.setCurrentIndex(max(0, ai))
            acombo.setFixedWidth(150)
            if self.acct_names() and ai < 0:
                saved['acct'] = self.acct_names()[0]
            acombo.currentIndexChanged.connect(lambda _x, i=i, c=acombo: self.sched_edit(i, 'acct', c.currentData()))
            row.addWidget(acombo)
            combo = QComboBox()
            for sid, title in seq_items:
                combo.addItem(title, sid)
            idx = combo.findData(s.get('seq', 'all'))
            combo.setCurrentIndex(max(0, idx))
            combo.setFixedWidth(190)
            combo.currentIndexChanged.connect(lambda _x, i=i, c=combo: self.sched_edit(i, 'seq', c.currentData()))
            row.addWidget(combo)
            days = s.get('days') or [True] * 7
            for d in range(7):
                b = QPushButton(DAY_NAMES[d])
                b.setObjectName('day')
                b.setCheckable(True)
                b.setChecked(bool(days[d]))
                b.toggled.connect(lambda v, i=i, d=d: self.sched_day(i, d, bool(v)))
                row.addWidget(b)
            hh = self.time_box(i, 'h', 23, int(s.get('h', 8)))
            mm = self.time_box(i, 'm', 59, int(s.get('m', 10)))
            row.addSpacing(10)
            row.addWidget(hh)
            row.addWidget(QLabel(':'))
            row.addWidget(mm)
            save = QPushButton('SAVE')
            save.setObjectName('primary')
            save.setFixedWidth(64)
            save.setToolTip('Save this schedule. At this time the bot clears the account\'s "done" marks and collects everything again.')
            save.clicked.connect(lambda _c=False, i=i: self.sched_save(i))
            cancel = QPushButton('CANCEL')
            cancel.setFixedWidth(74)
            cancel.clicked.connect(lambda _c=False, i=i: self.sched_cancel(i))
            dirty = i in self.sched_drafts
            save.setVisible(dirty)
            cancel.setVisible(dirty)
            self.sched_btns[i] = (save, cancel)
            row.addWidget(save)
            row.addWidget(cancel)
            rm = QPushButton('X')
            rm.setFixedWidth(30)
            rm.setToolTip('Delete this schedule')
            rm.clicked.connect(lambda _c=False, i=i: self.remove_schedule(i))
            row.addWidget(rm)
            row.addStretch(1)
            self.sched_box.addLayout(row)

    def time_box(self, i, key, maxv, value):
        box = QLineEdit(f'{value:02d}')
        box.setMaxLength(2)
        box.setFixedWidth(44)
        box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        box.setValidator(QIntValidator(0, maxv, box))

        def changed(text, i=i, key=key, maxv=maxv):
            if text.strip().isdigit():
                self.sched_edit(i, key, min(maxv, int(text)))
        box.textChanged.connect(changed)
        box.editingFinished.connect(lambda b=box: b.setText(f'{int(b.text() or 0):02d}'))
        return box

    def _draft(self, i):
        """The unsaved copy of schedule i (created on the first edit; SAVE / CANCEL appear)."""
        d = self.sched_drafts.get(i)
        if d is None:
            d = dict(self.schedules[i])
            d['days'] = list(self.schedules[i].get('days') or [True] * 7)
            self.sched_drafts[i] = d
        for b in self.sched_btns.get(i, ()):
            b.setVisible(True)
        return d

    def sched_edit(self, i, key, value):
        if 0 <= i < len(self.schedules):
            self._draft(i)[key] = value

    def sched_day(self, i, d, value):
        if 0 <= i < len(self.schedules):
            self._draft(i)['days'][d] = value

    def sched_toggle(self, i, value):
        """The on / off switch applies at once (no SAVE needed)."""
        if not (0 <= i < len(self.schedules)):
            return
        sc = self.schedules[i]
        sc['on'] = value
        if i in self.sched_drafts:
            self.sched_drafts[i]['on'] = value
        if value:
            self.skip_today_if_passed(sc)
        self.save_settings()
        self.update_clock()

    def skip_today_if_passed(self, sc):
        """Switching a schedule on (or saving a new time) after its time has passed today does not start a run
        straight away - it waits for the next scheduled time."""
        now = datetime.now()
        if now.hour * 60 + now.minute >= int(sc.get('h', 8)) * 60 + int(sc.get('m', 10)):
            self.fired.setdefault(f'{date.today().isoformat()}#{sc.get("id")}', {'n': 3, 'last': 0.0})

    def sched_save(self, i):
        d = self.sched_drafts.pop(i, None)
        if d is None or not (0 <= i < len(self.schedules)):
            return
        sc = self.schedules[i]
        old_time = (int(sc.get('h', 8)), int(sc.get('m', 10)))
        d['h'] = max(0, min(23, int(d.get('h', 8))))
        d['m'] = max(0, min(59, int(d.get('m', 10))))
        sc.update(d)
        # a changed time later today is allowed to fire again today; an earlier/passed time waits for tomorrow
        key = f'{date.today().isoformat()}#{sc.get("id")}'
        if (sc['h'], sc['m']) != old_time:
            self.fired.pop(key, None)
            if sc.get('on'):
                self.skip_today_if_passed(sc)
        self.save_settings()
        for b in self.sched_btns.get(i, ()):
            b.setVisible(False)
        names = ', '.join(DAY_NAMES[k] for k in range(7) if (sc.get('days') or [True] * 7)[k]) or 'no days'
        self.log(f'Schedule {i + 1} saved: {sc.get("acct")}, {names}, {sc["h"]:02d}:{sc["m"]:02d}'
                 f'{"" if sc.get("on") else " (switched OFF - turn the switch on to use it)"}.')
        self.update_clock()

    def sched_cancel(self, i):
        self.sched_drafts.pop(i, None)
        self.rebuild_schedule_rows()

    # -------------------------------------------------------- settings / state
    def load_settings(self):
        data = {}
        try:
            data = json.loads(self.settings_file.read_text(encoding='utf-8'))
        except (ValueError, OSError):
            pass
        self.notify_cb.blockSignals(True)
        self.notify_cb.setChecked(bool(data.get('notify', True)))
        self.notify_cb.blockSignals(False)
        self.logged_in = data.get('logged_in') or None
        look = data.get('look')
        if not isinstance(look, dict):          # v4.32 saved just 'seraph' / 'classic'
            look = {'theme': data.get('theme', 'seraph')}
        self.look_saved = look
        self.scene_saved = data.get('scene') if isinstance(data.get('scene'), dict) else {}
        self.lock_pos_saved = data.get('lock_pos') if isinstance(data.get('lock_pos'), dict) else {}
        if self.lock_ui is not None:
            self.lock_ui.set_position(self.lock_pos_saved)
        self.lock_cb.blockSignals(True)
        self.lock_cb.setChecked(True)            # runs always lock the game; the badge lifts it
        self.lock_cb.blockSignals(False)
        fm = data.get('fail_memory')
        if isinstance(fm, dict) and fm.get('day') == date.today().isoformat() and isinstance(fm.get('f'), dict):
            self.fail_memory = {a: dict(v) for a, v in fm['f'].items() if isinstance(v, dict)}
        self.bg_cb.blockSignals(True)
        self.bg_cb.setChecked(bool(data.get('background', True)))
        self.bg_cb.blockSignals(False)
        self.auto_update = bool(data.get('auto_update', True))
        if data.get('run_account') in self.acct_names():
            self.run_account = data['run_account']
        sched = data.get('schedules')
        if isinstance(sched, list):
            self.schedules = [s for s in sched if isinstance(s, dict)]
            for sc in self.schedules:
                sc.setdefault('id', uuid.uuid4().hex[:8])
        elif data:   # settings from v3: one auto-collect switch plus a "not before" time
            try:
                h, m = [int(x) for x in str(data.get('run_at', '08:10')).split(':')]
            except ValueError:
                h, m = 8, 10
            self.schedules = [{'id': uuid.uuid4().hex[:8], 'on': bool(data.get('auto')), 'seq': 'all', 'days': [True] * 7, 'h': h, 'm': m}]
        else:
            self.schedules = [{'id': uuid.uuid4().hex[:8], 'on': False, 'seq': 'all', 'days': [True] * 7, 'h': 8, 'm': 10}]
        today = date.today().isoformat()
        fired = data.get('fired')
        if isinstance(fired, dict):
            self.fired = {k: {'n': int(v.get('n', 0)), 'last': 0.0} for k, v in fired.items()
                          if str(k).startswith(today) and isinstance(v, dict)}

    def save_settings(self, *_):
        try:
            self.settings_file.write_text(json.dumps({
                'notify': self.notify_cb.isChecked(), 'schedules': self.schedules,
                'fired': {k: {'n': v.get('n', 0)} for k, v in self.fired.items() if k.startswith(date.today().isoformat())},
                'logged_in': self.logged_in, 'run_account': self.run_account, 'background': self.bg_cb.isChecked(), 'auto_update': getattr(self, 'auto_update', True),
                'input_lock': self.lock_cb.isChecked(), 'look': (self.themes.state() if self.themes is not None else self.look_saved), 'scene': (self.themes.scene_state() if self.themes is not None else self.scene_saved), 'lock_pos': (self.lock_ui.pos_state() if self.lock_ui is not None else self.lock_pos_saved), 'fail_memory': {'day': date.today().isoformat(), 'f': self.fail_memory}}, indent=1), encoding='utf-8')
        except OSError:
            pass

    # ---- accounts
    def acct_names(self):
        return [a['name'] for a in self.accounts]

    def load_accounts(self):
        data = {}
        try:
            data = json.loads(self.account_file.read_text(encoding='utf-8'))
        except (ValueError, OSError):
            pass
        accts = data.get('accounts') if isinstance(data, dict) else None
        if isinstance(accts, list):
            self.accounts = [a for a in accts if isinstance(a, dict) and a.get('name')]
        elif isinstance(data, dict) and data.get('email'):          # v4.0-v4.3 single account
            nm = str(data['email']).split('@')[0] or 'Account 1'
            self.accounts = [{'name': nm, 'email': data['email'], 'password': data.get('password', ''), 'auto': bool(data.get('auto', True))}]
        else:
            self.accounts = []
        if self.accounts and self.run_account not in self.acct_names():
            self.run_account = self.accounts[0]['name']

    def write_accounts(self):
        try:
            self.account_file.write_text(json.dumps({'accounts': self.accounts}, indent=1), encoding='utf-8')
            return True
        except OSError as exc:
            self.log(f'Could not save the accounts: {exc}')
            return False

    def account_by_name(self, name):
        for a in self.accounts:
            if a['name'] == name:
                return a
        return None

    def refresh_account_widgets(self, select=None):
        self.acct_list.blockSignals(True)
        self.acct_list.clear()
        for a in self.accounts:
            self.acct_list.addItem(a['name'])
        self.acct_list.blockSignals(False)
        self.acct_combo.blockSignals(True)
        self.acct_combo.clear()
        for a in self.accounts:
            self.acct_combo.addItem(a['name'], a['name'])
        idx = self.acct_combo.findData(self.run_account)
        self.acct_combo.setCurrentIndex(max(0, idx))
        self.acct_combo.blockSignals(False)
        if self.accounts and self.run_account not in self.acct_names():
            self.run_account = self.accounts[0]['name']
        target = select or self.run_account
        if target in self.acct_names():
            self.acct_list.setCurrentRow(self.acct_names().index(target))
        else:
            self.acct_selected(-1)
        self.logged_label.setText(f'Currently logged in to the game as: {self.logged_in}' if self.logged_in else '')

    def on_acct_combo(self, _i):
        name = self.acct_combo.currentData()
        if name and name != self.run_account and not self.running:
            self.run_account = name
            self.save_settings()
            self.refresh_tasks()
            self.update_badge()

    def acct_selected(self, row):
        a = self.accounts[row] if 0 <= row < len(self.accounts) else None
        self.name_edit.setText(a['name'] if a else '')
        self.email_edit.setText(a.get('email', '') if a else '')
        self.password_edit.setText(a.get('password', '') if a else '')
        self.autologin_cb.setChecked(bool(a.get('auto', True)) if a else True)

    def acct_new(self):
        self.acct_list.setCurrentRow(-1)
        self.name_edit.clear()
        self.email_edit.clear()
        self.password_edit.clear()
        self.autologin_cb.setChecked(True)
        self.name_edit.setFocus()

    def save_account(self):
        email, pw = self.email_edit.text().strip(), self.password_edit.text()
        name = self.name_edit.text().strip() or (email.split('@')[0] if email else '')
        if not name or not email:
            self.log('Type a name and an e-mail first.')
            return
        row = self.acct_list.currentRow()
        entry = {'name': name, 'email': email, 'password': pw, 'auto': self.autologin_cb.isChecked()}
        old = self.accounts[row]['name'] if 0 <= row < len(self.accounts) else None
        if old is None:
            existing = self.account_by_name(name)
            if existing is not None:
                self.accounts[self.accounts.index(existing)] = entry
            else:
                self.accounts.append(entry)
        else:
            self.accounts[row] = entry
            if old != name:                       # renamed: keep schedules / state / selection pointing at it
                for sc in self.schedules:
                    if sc.get('acct') == old:
                        sc['acct'] = name
                if self.run_account == old:
                    self.run_account = name
                if self.logged_in == old:
                    self.logged_in = name
        if self.write_accounts():
            self.log(f'Account "{name}" saved on this PC (account.json).')
        if not self.run_account:
            self.run_account = name
        self.save_settings()
        self.refresh_account_widgets(select=name)
        self.rebuild_schedule_rows()

    def remove_account(self):
        row = self.acct_list.currentRow()
        if not (0 <= row < len(self.accounts)):
            return
        name = self.accounts[row]['name']
        if QMessageBox.question(self, 'Remove', f'Remove the account "{name}"?') != QMessageBox.StandardButton.Yes:
            return
        self.accounts.pop(row)
        self.write_accounts()
        if self.run_account == name:
            self.run_account = self.accounts[0]['name'] if self.accounts else ''
        self.save_settings()
        self.refresh_account_widgets()
        self.rebuild_schedule_rows()
        self.refresh_tasks()

    def credentials(self):
        a = self.account_by_name(self.run_account)
        if a is None or not a.get('auto', True):
            return None
        email, pw = a.get('email', '').strip(), a.get('password', '')
        return (email, pw) if email and pw else None

    def clear_login(self):
        if QMessageBox.question(self, 'Log out', 'Delete the saved login cookies? The game will show its login page again.') == QMessageBox.StandardButton.Yes:
            self.profile.cookieStore().deleteAllCookies()
            self.logged_in = None
            self.save_settings()
            self.browser.reload()
            self.log('Saved login cookies cleared.')

    @staticmethod
    def server_date():
        """Kept under its old name: the 'day' of the saved marks is now the PC's local date."""
        return date.today().isoformat()

    def state_current(self, data):
        """With a schedule switched on, the marks are cleared by the schedule (or RESET PROGRESS), not by the date."""
        return data.get('sdate') == self.server_date() or any(sc.get('on') for sc in self.schedules)

    def reset_marks(self, acct, seq='all'):
        if seq == 'all':
            self.save_state({}, acct)
        else:
            done = self.load_state(acct)
            done.pop(seq, None)
            self.save_state(done, acct)

    def load_state(self, acct=None):
        acct = acct if acct is not None else self.run_account
        try:
            data = json.loads(self.state_file.read_text(encoding='utf-8'))
            if self.state_current(data):
                if isinstance(data.get('accts'), dict):
                    return dict(data['accts'].get(acct) or {})
                if isinstance(data.get('done'), dict):           # v4.0-v4.3 file: belongs to the first account
                    return dict(data['done']) if (not self.accounts or acct == self.accounts[0]['name']) else {}
        except (ValueError, OSError):
            pass
        return {}

    def save_state(self, done, acct=None):
        acct = acct if acct is not None else self.run_account
        allacc = {}
        try:
            data = json.loads(self.state_file.read_text(encoding='utf-8'))
            if self.state_current(data):
                if isinstance(data.get('accts'), dict):
                    allacc = data['accts']
                elif isinstance(data.get('done'), dict) and self.accounts:
                    allacc = {self.accounts[0]['name']: data['done']}
        except (ValueError, OSError):
            pass
        allacc[acct] = done
        try:
            self.state_file.write_text(json.dumps({'sdate': self.server_date(), 'accts': allacc}, indent=1), encoding='utf-8')
        except OSError:
            pass

    def pending_tasks(self, seq='all', acct=None):
        done = self.load_state(acct)
        ids = [t['id'] for t in TASKS] if seq == 'all' else [seq]
        return [i for i in ids if i in TASK_BY_ID and i not in done]

    # ------------------------------------------------------------ clock / views
    def next_schedule(self):
        """(datetime, schedule) of the next switched-on schedule, or None."""
        now = datetime.now()
        best = None
        for sc in self.schedules:
            if not sc.get('on'):
                continue
            days = sc.get('days') or [True] * 7
            for off in range(8):
                d = now + timedelta(days=off)
                if not days[d.weekday()]:
                    continue
                t = d.replace(hour=int(sc.get('h', 8)), minute=int(sc.get('m', 10)), second=0, microsecond=0)
                if t > now:
                    if best is None or t < best[0]:
                        best = (t, sc)
                    break
        return best

    def update_clock(self):
        now = datetime.now()
        nxt = self.next_schedule()
        if nxt:
            left = max(0, int((nxt[0] - now).total_seconds()))
            tail = f"NEXT RESET + RUN  {nxt[0]:%a %H:%M}  (in {left // 3600:02d}:{left % 3600 // 60:02d}:{left % 60:02d})"
        else:
            tail = 'NO SCHEDULE SWITCHED ON'
        self.clock_label.setText(f"PC TIME  {now:%H:%M:%S}      {tail}")
        self.update_badge()
        on = [s for s in self.schedules if s.get('on')]
        self.sched_info.setText(f'{len(on)} schedule(s) switched on.' if on else 'No schedule is switched on - nothing starts by itself.')

    def update_badge(self):
        done = self.load_state()
        n = sum(1 for t in TASKS if t['id'] in done)
        if self.running:
            text, colour = 'RUNNING', self.tcol['run']
        elif n == len(TASKS):
            text, colour = f'ALL DONE TODAY  {n}/{len(TASKS)}', self.tcol['ok']
        else:
            text, colour = f'DONE TODAY  {n}/{len(TASKS)}', self.tcol['part']
        self.badge.setText(text)
        self.badge.setStyleSheet(f'color:{colour}; font-weight:bold; letter-spacing:1px;')

    def refresh_tasks(self):
        """The results grid: one row per collection - green tick = collected, red cross = failed, ? = not done yet."""
        done = self.load_state()
        remembered = self.fail_memory.get(self.run_account, {})
        self.task_list.clear()
        for t in TASKS:
            tid = t['id']
            if tid in self.task_failed:
                mark, colour, note = '\u2718', self.tcol['fail'], self.task_failed[tid]
            elif tid in done:
                mark, colour, note = '\u2714', self.tcol['ok'], done[tid]
            elif self.running and self.cur_task == tid:
                mark, colour, note = '\u25b6', self.tcol['run'], 'running'
            elif tid in remembered:
                mark, colour, note = '\u2718', self.tcol['fail'], 'failed last run: ' + str(remembered[tid])
            else:
                mark, colour, note = '?', self.tcol['wait'], 'not done yet'
            item = QListWidgetItem(f'{mark}  {t["title"]}')
            item.setForeground(QBrush(QColor(colour)))
            item.setToolTip(str(note))
            item.setData(Qt.ItemDataRole.UserRole, tid)
            self.task_list.addItem(item)
        if hasattr(self, 'rerun_btn'):
            n = len([i for i in remembered if i in TASK_BY_ID and i not in done])
            self.rerun_btn.setText(f'RE-RUN FAILED  ({n})' if n else 'RE-RUN FAILED')
            self.rerun_btn.setEnabled(bool(n) and not self.running)

    def rerun_failed(self):
        done = self.load_state()
        ids = [i for i in self.fail_memory.get(self.run_account, {}) if i in TASK_BY_ID and i not in done]
        if not ids:
            self.log('Nothing failed last time for this account.')
            return
        self.start(ids, force=True)

    def read_history(self):
        try:
            data = json.loads(self.history_file.read_text(encoding='utf-8'))
            return data if isinstance(data, list) else []
        except (ValueError, OSError):
            return []

    def record_history(self, reason, ok):
        data = self.read_history()
        data.append({'when': datetime.now().strftime('%Y-%m-%d %H:%M'), 'ok': bool(ok), 'text': (f'[{self.run_account}] ' + reason)[:300]})
        try:
            self.history_file.write_text(json.dumps(data[-200:], indent=1), encoding='utf-8')
        except OSError:
            pass
        self.refresh_history()

    def refresh_history(self):
        data = self.read_history()
        self.history_list.clear()
        for item in reversed(data[-30:]):
            entry = QListWidgetItem(('OK  ' if item.get('ok') else 'FAIL  ') + item.get('when', '') + '\n' + item.get('text', '')[:70])
            entry.setToolTip(item.get('text', ''))
            self.history_list.addItem(entry)
        days = sorted({i['when'][:10] for i in data if i.get('ok') and 'when' in i}, reverse=True)
        streak, day = 0, date.today()
        if days and days[0] != day.isoformat():
            day -= timedelta(days=1)
        while day.isoformat() in days:
            streak += 1
            day -= timedelta(days=1)
        self.streak_label.setText(f'Streak: {streak} day(s)' if streak else '')
        self.acc_stats.setText(f'Successful runs recorded on {len(days)} day(s).   Current streak: {streak}.')

    def notify(self, title, text):
        if self.tray is not None and self.notify_cb.isChecked():
            try:
                self.tray.showMessage(title, text, QSystemTrayIcon.MessageIcon.Information, 8000)
            except Exception:
                pass

    def log(self, message):
        line = f"{datetime.now():%H:%M:%S}  {message}"
        self.log_view.append(line)
        tv = getattr(self, 'log_text_view', None)
        if tv is not None and getattr(self, 'log_dialog', None) is not None and self.log_dialog.isVisible():
            tv.appendPlainText(line)
        try:
            with (ROOT / 'nova_v2.log').open('a', encoding='utf-8') as f:
                f.write(line + '\n')
        except OSError:
            pass

    # ------------------------------------------------------------------- screenshots
    def shot_run_context(self):
        """Folder + file name for a screenshot taken during a bot run: the collection being worked on."""
        try:
            entry = self.queue[self.qi]
            tid, step = entry['task'], entry['step']
            if tid:
                return TASK_BY_ID[tid]['title'], self.status.text() or step.get('label', step['k'])
            return ('Login and Enter Game' if step['k'] in ('ingame', 'switch') else 'Main screen'), self.status.text() or 'screen'
        except Exception:
            return 'Unsorted', 'screen'

    def shot_classify(self, bgr):
        """Which system is on screen (used when the bot is idle and the player is exploring)."""
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        saved = (self.region_override, self.results, self.cur_bgr, self.last_result, self.last_full, self.scale_hint)
        try:
            self.region_override, self.results, self.cur_bgr = {}, None, bgr
            self.last_result, self.last_full, self.scale_hint = {}, {}, {}
            def f(n):
                return self.locate_raw(gray, n)[0] >= THRESH.get(n, DEFAULT_THRESH)
            if f('enter_game') or f('login_button'):
                return 'Login and Enter Game'
            if f('dragon_pack'):
                return 'Adverts'
            if f('back_arrow'):
                for group, cues in (('Privileges', ('lifetime_pass', 'menu_monthly', 'menu_deals')), ('Shop', ('menu_daily_limit',)),
                                    ('Perks', ('menu_login_rewards', 'menu_online_bonus', 'menu_afk_bonus')), ('R2 Pass', ('r2_login_tab', 'r2_claim_today'))):
                    if any(f(c) for c in cues):
                        return group
                return 'Other screens'
            if any(f(n) for n in ('icon_privileges', 'icon_shop', 'icon_perks')):
                return 'Main screen'
            return 'Unsorted'
        finally:
            self.region_override, self.results, self.cur_bgr, self.last_result, self.last_full, self.scale_hint = saved

    def shot_tick(self):
        """Idle watcher (1 per second): when the player opens a new screen and it has settled, save it."""
        try:
            if self.shot_lib is None or not self.shot_lib.settings.get('auto', True) or self.running or self.shot_busy:
                return
            if self.tabs.currentIndex() != 0 or self.page_loaded_at is None or self.isMinimized() or not self.isActiveWindow():
                return
            pix = self.browser.grab()
            if pix.isNull():
                return
            img = pix.scaled(THUMB[0], THUMB[1], Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.FastTransformation
                             ).toImage().convertToFormat(QImage.Format.Format_Grayscale8)
            h, w, stride = img.height(), img.width(), img.bytesPerLine()
            thumb = np.frombuffer(img.constBits(), dtype=np.uint8, count=stride * h).reshape((h, stride))[:, :w].copy()
            if float(thumb.std()) < 1.5:
                return                                              # blank widget (hidden / loading)
            if self.shot_watch.feed(thumb):
                self.shot_watch.mark(thumb)
                self.shot_capture('auto')
        except Exception as exc:
            self.log(f'Screenshot watcher: {exc}')

    def shot_offer_run(self, frame):
        """During a bot run the frames are already being analysed - reuse them (no extra grabs)."""
        try:
            if self.shot_lib is None or not self.shot_lib.settings.get('auto', True) or self.shot_busy or self.snap_bgr is None:
                return
            thumb = cv2.resize(frame, THUMB, interpolation=cv2.INTER_AREA)
            if self.shot_watch.feed(thumb):
                self.shot_watch.mark(thumb)
                self.shot_capture('auto', frame_bgr=self.snap_bgr.copy())
        except Exception as exc:
            self.log(f'Screenshot watcher: {exc}')

    def shot_capture_now(self, label=''):
        self.shot_capture('manual', manual=True, label=label)

    def shot_capture(self, source='auto', manual=False, label='', frame_bgr=None):
        """Take the screenshot on the GUI thread (cheap) and let a worker thread classify, compress and save it."""
        if self.shot_lib is None:
            return
        label = (label or (self.shots_panel.current_label() if self.shots_panel else '')).strip()
        if self.shot_busy and not manual:
            return
        bgr = frame_bgr
        if bgr is None and self.running and self.snap_bgr is not None:
            bgr = self.snap_bgr.copy()
        if bgr is None:
            gray = None if self.bg_active else self.snapshot()
            if gray is not None and float(gray[::16, ::16].std()) >= 1.5:
                bgr = self.snap_bgr.copy()
        run_ctx = self.shot_run_context() if self.running else None
        self.shot_busy = True
        threading.Thread(target=self._shot_worker, args=(bgr, source, manual, label, run_ctx), daemon=True).start()

    def _shot_worker(self, bgr, source, manual, label, run_ctx):
        msg = ''
        try:
            if bgr is None:                                          # hidden / covered window: ask the browser itself
                with self.click_lock:
                    data = self.cdp.screenshot()
                bgr = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
            if bgr is None:
                raise ValueError('no picture available')
            if run_ctx:
                group, name = run_ctx
            else:
                group = self.shot_classify(bgr)
                name = group
            if label:
                group, name = label, label
            rel = self.shot_lib.save(bgr, group, name, manual=manual, source=source,
                                     min_gap={'Main screen': 60.0, 'Login and Enter Game': 180.0}.get(group, 0.0))
            if rel:
                msg = f'Screenshot saved: screenshots/{rel}'
            elif manual:
                msg = 'Screenshot could not be saved.'
        except Exception as exc:
            msg = f'Screenshot failed: {exc}'
        finally:
            self.shot_busy = False
        self.shot_saved.emit(msg)

    def on_shot_saved(self, msg):
        if msg:
            self.log(msg)
        if self.shots_panel is not None:
            try:
                self.shots_panel.refresh()
            except Exception:
                pass

    # ------------------------------------------------------------------- log window
    def read_log_text(self, max_lines=6000):
        try:
            lines = (ROOT / 'nova_v2.log').read_text(encoding='utf-8', errors='replace').splitlines()
        except OSError:
            lines = []
        return '\n'.join(lines[-max_lines:])

    def open_log(self):
        """Log window (like the Monfort one): read everything the bot did, refresh it, export it to a file."""
        dlg = getattr(self, 'log_dialog', None)
        if dlg is None:
            dlg = QDialog(self)
            dlg.setWindowTitle('Glaycon Nova - Log')
            dlg.resize(980, 620)
            lay = QVBoxLayout(dlg)
            lay.addWidget(self.caption(f'LOG  -  Glaycon Nova {VERSION}  -  {ROOT / "nova_v2.log"}'))
            view = QPlainTextEdit()
            view.setReadOnly(True)
            view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
            lay.addWidget(view, 1)
            row = QHBoxLayout()
            b_ref, b_exp, b_clear, b_close = (QPushButton(t) for t in ('REFRESH', 'EXPORT', 'CLEAR LOG', 'CLOSE'))
            for b in (b_ref, b_exp, b_clear):
                row.addWidget(b)
            row.addStretch(1)
            row.addWidget(b_close)
            lay.addLayout(row)
            self.log_text_view = view

            def refresh():
                view.setPlainText(self.read_log_text())
                view.verticalScrollBar().setValue(view.verticalScrollBar().maximum())
            self.refresh_log_view = refresh
            b_ref.clicked.connect(refresh)
            b_exp.clicked.connect(self.export_log)
            b_clear.clicked.connect(self.clear_log)
            b_close.clicked.connect(dlg.close)
            self.log_dialog = dlg
        self.refresh_log_view()
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()

    def export_log(self):
        docs = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation) or str(ROOT)
        default = str(Path(docs) / f'Glaycon-Nova-log-{datetime.now():%Y%m%d-%H%M}.txt')
        path, _ = QFileDialog.getSaveFileName(self, 'Export log', default, 'Text file (*.txt);;All files (*)')
        if not path:
            return
        try:
            head = f'Glaycon Nova {VERSION} - exported {datetime.now():%Y-%m-%d %H:%M:%S} (PC time)\n' + '-' * 60 + '\n'
            Path(path).write_text(head + self.read_log_text(20000) + '\n', encoding='utf-8')
            self.log(f'Log exported to {path}')
            QMessageBox.information(self, 'Log exported', f'Saved:\n{path}')
        except OSError as exc:
            QMessageBox.warning(self, 'Export failed', str(exc))

    def clear_log(self):
        if QMessageBox.question(self, 'Clear log', 'Delete the saved log file?') != QMessageBox.StandardButton.Yes:
            return
        try:
            (ROOT / 'nova_v2.log').write_text('', encoding='utf-8')
        except OSError:
            pass
        self.log_view.clear()
        self.refresh_log_view()

    # ------------------------------------------------------------ watchdog / report
    def watchdog_check(self):
        """Every 20 s: a run whose current step has made no progress (no new step, no click) for 10 minutes is stopped, the game is reloaded and the
        remaining collections are started again (at most twice a day)."""
        if not self.running or self.paused or self.login_busy:
            return
        stuck = time.monotonic() - max(self.step_started, getattr(self, 'last_click', 0) or 0)
        if stuck < 600:
            return
        entry = self.queue[self.qi] if self.qi < len(self.queue) else None
        label = (entry['step'].get('label') or entry['step']['k']) if entry else '?'
        tid = (entry or {}).get('task')
        self.log(f'WATCHDOG: the step "{label}" has not moved or clicked for {int(stuck // 60)} minutes - stopping this run.')
        self.save_debug('watchdog')
        today = date.today().isoformat()
        n = self.wd_restarts.get(today, 0)
        todo = None
        if n < 2:
            ids = [t['id'] for t in TASKS]
            cur = tid if tid in ids else (self.current_task_id() if self.queue else None)
            if cur in ids:
                todo = ids[ids.index(cur):]
        self.task_failed['watchdog'] = f'stuck on "{label}" for {int(stuck // 60)} minutes'
        if todo:
            self.wd_restarts[today] = n + 1
            self.pending_restart = todo
            self.log('WATCHDOG: reloading the game and trying the rest again (once or twice a day only).')
        self.stop('FAILED: stuck on "' + label + '" - the watchdog stopped the run.')
        if todo:
            self.reload_game()
            QTimer.singleShot(60000, self.do_restart)

    def make_report(self, reason, ok, auto=False):
        """Build the short report of the run that just ended, save it under reports/ and show it (without stealing focus)."""
        done = self.load_state()
        ran = set(getattr(self, 'run_ids', []))
        lines = []
        n_done = 0
        for t in TASKS:
            tid = t['id']
            if tid in self.task_failed:
                lines.append(f'  FAILED   {t["title"]}: {self.task_failed[tid]}')
            elif tid in done:
                n_done += 1
                tag = 'done    ' if tid in ran else 'done earlier'
                note = str(done[tid])
                lines.append(f'  {tag} {t["title"]}: {note[:90]}')
            elif tid in ran:
                lines.append(f'  not done {t["title"]}')
            else:
                lines.append(f'  not run  {t["title"]}')
        extra = [f'  PROBLEM  {k}: {v}' for k, v in self.task_failed.items() if k not in TASK_BY_ID]
        head = (f'{"Scheduled run" if auto else "Run"} for {self.run_account} - {datetime.now():%a %d %b %Y %H:%M}\n'
                f'{"All good" if ok else "There were problems"}: {n_done} of {len(TASKS)} collections done today.')
        text = head + '\n' + '\n'.join(lines + extra)
        self.last_report = text
        try:
            d = ROOT / 'reports'
            d.mkdir(exist_ok=True)
            with open(d / f'report_{date.today().isoformat()}.txt', 'a', encoding='utf-8') as f:
                f.write(text + '\n\n')
        except OSError:
            pass
        if not self.isMinimized() and self.isVisible():
            self.show_report()

    def show_report(self):
        if not self.last_report:
            QMessageBox.information(self, 'Report', 'No run has finished yet in this session.')
            return
        box = QMessageBox(self)
        box.setWindowTitle('Run report')
        box.setIcon(QMessageBox.Icon.Information)
        head, _, body = self.last_report.partition('\n')
        first, _, rest = body.partition('\n')
        box.setText(head + '\n' + first)
        box.setDetailedText(rest)
        box.setStandardButtons(QMessageBox.StandardButton.Ok)
        box.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        box.setWindowModality(Qt.WindowModality.NonModal)
        box.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self._report_box = box
        box.show()

    # ------------------------------------------------------------------ updates
    def is_busy(self):
        return bool(self.running)

    def _remote_worker(self, manual):
        try:
            ver, err = updater.check_remote(ROOT, VERSION)
        except Exception as exc:
            ver, err = None, str(exc)
        self.remote_done.emit(bool(manual), err or '')

    def on_remote_done(self, manual, err):
        self._remote_busy = False
        if err:
            self.update_remote_err = err
        self.check_updates(manual, remote_done=True)

    def check_updates(self, manual=False, remote_done=False):
        """Look in the updates folder for a newer version. Automatic checks stay quiet unless something is new."""
        if not remote_done:
            now = time.time()
            if not getattr(self, '_remote_busy', False) and (manual or now - getattr(self, '_remote_last', 0) > 1800):
                self._remote_busy = True
                self._remote_last = now
                self.update_remote_err = ''
                threading.Thread(target=self._remote_worker, args=(manual,), daemon=True).start()
                if manual:
                    self.update_btn.setText('UPDATE  (checking...)')
                    return
        try:
            pkg = updater.find_pending(ROOT, VERSION)
        except Exception as exc:
            pkg = None
            if manual:
                QMessageBox.warning(self, 'Update', f'Could not check for updates: {exc}')
                return
        if pkg is None:
            self.update_btn.setText('UPDATE')
            if manual:
                self.update_up_to_date(getattr(self, 'update_remote_err', ''))
            return
        self.update_btn.setText(f'UPDATE  ({pkg.version} ready)')
        if not manual:
            if self.is_busy():
                if self.update_shown != ('log', pkg.version):
                    self.update_shown = ('log', pkg.version)
                    self.log(f'Update {pkg.version} is ready. It will be offered when the run finishes.')
                return
            if self.update_shown == ('shown', pkg.version):
                return
            if getattr(self, 'update_dialog_open', False):
                return
        self.show_update_dialog(pkg, manual)

    def update_up_to_date(self, err=''):
        box = QMessageBox(self)
        box.setWindowTitle('Update')
        box.setText(f'You are up to date ({VERSION}).\n\nNo new update was found.' + (f'\n\nNote: {err}' if err else ''))
        b_file = box.addButton('Install from file...', QMessageBox.ButtonRole.ActionRole)
        box.addButton('OK', QMessageBox.ButtonRole.AcceptRole)
        box.exec()
        if box.clickedButton() is b_file:
            path, _ = QFileDialog.getOpenFileName(self, 'Choose an update file', str(ROOT), 'Update (*.zip)')
            if not path:
                return
            pkg = updater.load_package(path)
            if pkg is None:
                QMessageBox.warning(self, 'Update', 'That file is not a valid update.')
            elif not updater.is_newer(pkg.version, VERSION):
                QMessageBox.information(self, 'Update', f'That update is {pkg.version}, which is not newer than {VERSION}.')
            else:
                self.show_update_dialog(pkg, True)

    def show_update_dialog(self, pkg, manual):
        self.update_dialog_open = True
        self.update_shown = ('shown', pkg.version)
        try:
            box = QMessageBox(self)
            box.setWindowTitle('Update available')
            box.setIcon(QMessageBox.Icon.Information)
            notes = '\n'.join('  - ' + n for n in pkg.notes[:14]) or '  (no notes)'
            when = f'  ({pkg.date})' if pkg.date else ''
            box.setText(f'New version {pkg.version}{when}\nYou have {VERSION}.\n\nWhat is new:\n{notes}')
            cb = QCheckBox('Install new updates by myself when the bot is idle')
            cb.setChecked(getattr(self, 'auto_update', True))
            box.setCheckBox(cb)
            b_inst = box.addButton('Install && restart'.replace('&&', '&'), QMessageBox.ButtonRole.AcceptRole)
            b_later = box.addButton('Later', QMessageBox.ButtonRole.RejectRole)
            auto = cb.isChecked() and not manual and not self.is_busy()
            left = [15]
            if auto:
                tick = QTimer(box)
                tick.setInterval(1000)

                def step():
                    left[0] -= 1
                    b_inst.setText(f'Install & restart ({left[0]})')
                    if left[0] <= 0:
                        tick.stop()
                        b_inst.click()
                tick.timeout.connect(step)
                b_inst.setText(f'Install & restart ({left[0]})')
                tick.start()
                box.buttonClicked.connect(lambda *_: tick.stop())
            box.exec()
            if getattr(self, 'auto_update', True) != cb.isChecked():
                self.auto_update = cb.isChecked()
                self.save_settings()
            if box.clickedButton() is b_inst:
                self.install_update(pkg)
        finally:
            self.update_dialog_open = False

    def install_update(self, pkg):
        if self.is_busy():
            QMessageBox.information(self, 'Update', 'A run is going. Stop it first (or wait until it finishes), then update.')
            return
        ok, msg, bdir = updater.install(ROOT, pkg, VERSION)
        if not ok:
            self.log(f'UPDATE FAILED - nothing was changed: {msg}')
            QMessageBox.warning(self, 'Update failed', f'The update was not installed. Your bot is unchanged.\n\n{msg}')
            return
        self.log(f'Update {pkg.version} installed (backup: {bdir.name}). Restarting the bot...')
        self.save_settings()
        try:
            updater.spawn_restart_helper(ROOT, os.getpid())
        except Exception as exc:
            self.log(f'Could not restart by itself ({exc}). Please close and open the bot.')
            QMessageBox.information(self, 'Update', f'Update {pkg.version} is installed. Please close the bot and open it again.')
            return
        QTimer.singleShot(300, QApplication.quit)

    def reload_game(self):
        self.page_loaded_at = None
        self.browser.reload()

    def hook_input(self):
        """Watch real mouse/keyboard input on the game view (for the input lock and the click recorder). The rendering
        widget inside the web view is created late, so this is repeated whenever the page loads or a run starts."""
        for w in (self.browser, self.browser.focusProxy()):
            if w is not None:
                w.installEventFilter(self)

    _LOCK_EVENTS = None

    def eventFilter(self, obj, ev):
        try:
            t = ev.type()
            if self._LOCK_EVENTS is None:
                E = QEvent.Type
                MainWindow._LOCK_EVENTS = {E.MouseButtonPress, E.MouseButtonRelease, E.MouseButtonDblClick, E.Wheel,
                                           E.KeyPress, E.KeyRelease, E.ContextMenu, E.TouchBegin, E.TouchUpdate, E.TouchEnd}
            if t not in self._LOCK_EVENTS or self._bot_input:
                return False
            if self.game_locked():
                if t == QEvent.Type.MouseButtonPress and time.monotonic() - self._lock_note_t > 30:
                    self._lock_note_t = time.monotonic()
                    self.log('Input lock: your click on the game was ignored while the bot runs (click the lock on the game to unlock).')
                return True
            if t == QEvent.Type.MouseButtonPress and self.rec_btn.isChecked() and self.rec_folder is not None:
                self.record_click(ev)
        except Exception as exc:
            self.log(f'Input filter: {exc}')
        return False

    def toggle_rec(self, on):
        if on:
            if self.running:
                self.rec_btn.blockSignals(True)
                self.rec_btn.setChecked(False)
                self.rec_btn.blockSignals(False)
                self.log('REC: stop the run first - a recording is for your own clicks.')
                return
            self.tabs.setCurrentIndex(0)
            self.hook_input()
            self.rec_folder = recorder.new_session(ROOT)
            self.rec_n = 0
            self.rec_t0 = time.monotonic()
            self.rec_btn.setText('REC  \u25cf recording - click to stop')
            self.rec_btn.setStyleSheet('color:#ff6b6b; font-weight:bold;')
            self.log(f'REC on: every click you make in the game is saved to {self.rec_folder}')
        else:
            self.rec_btn.setText('REC  (click recorder)')
            self.rec_btn.setStyleSheet('')
            if self.rec_folder is not None:
                self.log(f'REC off: {self.rec_n} click(s) saved in {self.rec_folder}')
            self.rec_folder = None

    def record_click(self, ev):
        """Runs on the GUI thread the instant before the click lands: grab the game as it is, save in a worker."""
        gp = ev.globalPosition().toPoint()
        pt = self.browser.mapFromGlobal(gp)
        wx, wy = pt.x(), pt.y()
        if not (0 <= wx < self.browser.width() and 0 <= wy < self.browser.height()):
            return
        pix = self.browser.grab()
        if pix.isNull():
            return
        image = pix.toImage().convertToFormat(QImage.Format.Format_RGBA8888)
        iw, ih, stride = image.width(), image.height(), image.bytesPerLine()
        raw = np.frombuffer(image.constBits(), dtype=np.uint8, count=stride * ih)
        bgr = cv2.cvtColor(raw.reshape((ih, stride))[:, :iw * 4].reshape((ih, iw, 4)).copy(), cv2.COLOR_RGBA2BGR)
        self.rec_n += 1
        n, folder, t0 = self.rec_n, self.rec_folder, self.rec_t0
        bw, bh = self.browser.width(), self.browser.height()
        btn = 'right' if ev.button() == Qt.MouseButton.RightButton else 'left'

        def work():
            try:
                recorder.save_click(folder, n, bgr, wx, wy, bw, bh, btn, t0)
            except Exception as exc:
                print('REC save failed:', exc)
        threading.Thread(target=work, daemon=True).start()
        self.status.setText(f'REC: click {n} saved')

    def on_loaded(self, ok):
        self.hook_input()
        if ok:
            self.page_loaded_at = time.monotonic()
            self.adbar_done = False
            if self.pending_restart:
                QTimer.singleShot(3000, self.do_restart)
        self.log('Game page loaded.' if ok else 'Page load failed. Try Reload game; the site may reject embedded browsers.')

    # ------------------------------------------------------------- calibration
    def pos(self, name):
        return self.positions.get(name) or DEFAULT_POS.get(name)

    def calibrate(self, name):
        if self.running:
            self.log('Stop collection before calibrating.')
            return
        was = self.hide_setup_temporarily()
        self.log(f'Hover over the {name} icon inside the game NOW. Capturing in 3 seconds; do not click.')
        QTimer.singleShot(3000, lambda n=name, w=was: self.capture_position(n, w))

    def capture_position(self, name, restore=False):
        try:
            pos = self.browser.mapFromGlobal(QCursor.pos())
            w, h = self.browser.width(), self.browser.height()
            if not (0 <= pos.x() < w and 0 <= pos.y() < h):
                self.log(f'Calibration failed: cursor was outside the embedded game for {name}.')
                return
            self.positions[name] = (round(pos.x() / w, 6), round(pos.y() / h, 6))
            self.positions_file.write_text(json.dumps(self.positions, indent=2), encoding='utf-8')
            self.log(f'Calibrated {name} at ({pos.x()}, {pos.y()}) of ({w}, {h}) - saved.')
        finally:
            self.restore_setup(restore)

    def test_click(self, name):
        if self.running:
            self.log('Stop collection before test clicks.')
            return
        was = self.hide_setup_temporarily()

        def go():
            self.last_click = 0
            self.click_frac(self.pos(name), f'TEST {name}')
            QTimer.singleShot(1500, lambda: self.restore_setup(was))
        QTimer.singleShot(400, go)

    # ------------------------------------------------------------------ vision
    def snapshot(self):
        # QWidget.grab returns the actual rendered browser pixels, no desktop screenshot needed.
        pix = self.browser.grab()
        if pix.isNull():
            return None
        image = pix.toImage().convertToFormat(QImage.Format.Format_RGBA8888)
        w, h = image.width(), image.height()
        stride = image.bytesPerLine()          # rows can contain padding
        raw = np.frombuffer(image.constBits(), dtype=np.uint8, count=stride * h)
        buf = raw.reshape((h, stride))[:, :w * 4].reshape((h, w, 4)).copy()
        self.snap_bgr = cv2.cvtColor(buf, cv2.COLOR_RGBA2BGR)
        return cv2.cvtColor(self.snap_bgr, cv2.COLOR_BGR2GRAY)

    def locate_raw(self, gray, name):
        """Find a picture in the frame. Returns (score, centre (x, y) in frame pixels, scale)."""
        template = self.templates.get(name)
        if template is None:
            return (0, None, None)
        h, w = gray.shape
        x1, y1, x2, y2 = self.region_override.get(name) or REGIONS[name]
        l, t, r, b = int(w * x1), int(h * y1), int(w * x2), int(h * y2)
        crop = gray[t:b, l:r]
        now = time.monotonic()
        hint = self.scale_hint.get(name)
        if hint is None and name in UI_TPLS and self.ui_scale:
            hint = self.ui_scale
        if hint is None and name in self.last_result and now - self.last_full.get(name, 0) < 1.0:
            return self.last_result[name]          # not seen recently: don't rescan every tick
        if hint is not None and now - self.last_full.get(name, 0) < 4:
            score, pt, scale = best_match(crop, template, hint)
        else:
            score, pt, scale = best_match(crop, template, None)
            self.last_full[name] = now
        if pt is None:
            result = (0, None, None)
        else:
            cx, cy = l + pt[0], t + pt[1]
            thr = THRESH.get(name, DEFAULT_THRESH)
            if name in GREEN_CHECK and score >= thr and not self.is_green(name, cx, cy, scale):
                score = min(score, .3)               # right word, wrong colour (grey "Claimed" etc.)
            if score >= thr:
                self.scale_hint[name] = scale
                if name in UI_TPLS and name != 'claim_text':
                    self.ui_scale = scale
            result = (score, (cx, cy), scale)
        self.last_result[name] = result
        return result

    def is_green(self, name, cx, cy, scale):
        bgr = self.cur_bgr
        if bgr is None:
            return True
        tpl = self.templates[name]
        tw, th = int(tpl.shape[1] * scale), int(tpl.shape[0] * scale)
        pad_x, pad_y = int(tw * .15), int(th * .25)
        h, w = bgr.shape[:2]
        box = bgr[max(0, cy - th // 2 - pad_y):min(h, cy + th // 2 + pad_y),
                  max(0, cx - tw // 2 - pad_x):min(w, cx + tw // 2 + pad_x)].astype(np.int16)
        if box.size == 0:
            return False
        B, G, R = box[..., 0], box[..., 1], box[..., 2]
        frac = float(((G > R + 10) & (G > B + 25) & (G > 90)).mean())
        return frac >= .30

    def locate(self, gray, name):
        """Result of the last analysis (computed in the worker thread) or, if there is none, computed now."""
        if self.results is not None:
            s, pt, _sc = self.results.get(name, (0, None, None))
            return (s, pt)
        s, pt, _sc = self.locate_raw(gray, name)
        return (s, pt)

    def scale_of(self, name):
        if self.results is not None:
            return (self.results.get(name) or (0, None, 1.0))[2] or 1.0
        return self.scale_hint.get(name) or 1.0

    def gold_tile(self, frame):
        """The Gold Pack tile - never the highlighted left-menu row (it looks like the tile's beige 'Free' bar)."""
        pt = self.found(frame, 'shop_goldpack')
        if pt is None:
            return None
        sc = self.scale_of('shop_goldpack')
        if pt[0] < frame.shape[1] * .17 or (sc is not None and not .70 <= sc <= 1.6):
            return None
        return pt

    def found(self, frame, name):
        score, pt = self.locate(frame, name)
        if self.debug.isChecked() and time.monotonic() - self.last_debug > 5:
            self.log(f'{name} score={score:.2f} (need {THRESH.get(name, DEFAULT_THRESH):.2f})')
            self.last_debug = time.monotonic()
        return pt if (pt is not None and score >= THRESH.get(name, DEFAULT_THRESH)) else None

    @staticmethod
    def changed(before, after, min_fraction=.035):
        if before is None or after is None or before.shape != after.shape:
            return False
        h, w = after.shape
        roi = (slice(int(h * .12), int(h * .83)), slice(0, int(w * .32)))
        a, b = before[roi], after[roi]
        return float(np.mean(cv2.absdiff(a, b) > 35)) >= min_fraction

    @staticmethod
    def frame_mean(frame):
        return float(frame[::8, ::8].mean())

    def popup_why(self, frame, ref_mean):
        """Why a reward / advert pop-up seems to be open (None = no pop-up). It dims the whole screen."""
        if self.found(frame, 'reward_obtained'):
            return 'reward banner'
        if self.found(frame, 'dragon_pack'):
            return 'Dragon Pack advert'
        if ref_mean is not None:
            ratio = self.frame_mean(frame) / max(ref_mean, 1e-6)
            if ratio < .80:
                return f'screen dimmed ({ratio:.2f} of normal)'
        return None

    def popup_open(self, frame, ref_mean):
        return self.popup_why(frame, ref_mean) is not None

    def tap_away(self, st, label, why):
        """Tap outside a pop-up, at most once every 1.2 s (taps made while its animation plays are ignored).
        Returns True when it has tried 8 times and should give up."""
        now = time.monotonic()
        if now - st.get('dtap', -99.0) < 1.2:
            return False
        if st.get('dismiss', 0) >= 8:
            return True
        if self.dismiss_click(st):
            st['dtap'] = now
            self.log(f'  {label}: pop-up still showing ({why}) - tapping outside (try {st["dismiss"]} of 8).')
        return False

    def save_debug(self, tag):
        """Save what the bot is looking at right now (for a problem report)."""
        try:
            (ROOT / 'debug').mkdir(exist_ok=True)
            path = ROOT / 'debug' / f'{tag}_{datetime.now():%Y%m%d_%H%M%S}.png'
            img = self.snap_bgr if self.snap_bgr is not None else self.last_frame
            if img is not None:
                cv2.imwrite(str(path), img)
                self.log(f'Saved screenshot of the problem: {path.name}')
        except Exception:
            pass

    # ------------------------------------------------------------------- input
    def to_logical(self, pt, frame):
        """Convert a point in screenshot pixels to browser-local logical pixels (HiDPI-safe)."""
        h, w = frame.shape
        return (int(pt[0] * self.browser.width() / w), int(pt[1] * self.browser.height() / h))

    def click(self, pt, label):
        if pt is None or time.monotonic() - self.last_click < 0.3:
            return False
        x, y = int(pt[0]), int(pt[1])
        w, h = self.browser.width(), self.browser.height()
        if not (0 <= x < w and 0 <= y < h):
            self.log(f'BLOCKED out-of-bounds click {label}: ({x}, {y}) vs browser {w}x{h}')
            return False
        hit = self.money_hit(x, y, w, h)
        if hit:
            self.log(f'BLOCKED click "{label}" at ({x}, {y}): it is on a paid button ({hit}). Nothing was pressed.')
            return False
        self.last_click = time.monotonic()
        threading.Thread(target=self._cdp_click_worker, args=(x, y, w, h, label), daemon=True).start()
        return True

    def money_hit(self, x, y, w, h):
        """Name of a known paid button under the click point, else None. Looks only at a small area around the click."""
        frame = self.last_frame
        if frame is None or not MONEY_TPLS:
            return None
        try:
            fh, fw = frame.shape[:2]
            fx, fy = x * fw / max(1, w), y * fh / max(1, h)
            for name in MONEY_TPLS:
                tpl = self.templates.get(name)
                if tpl is None:
                    continue
                reach = int(max(tpl.shape) * (self.ui_scale or 1.0) * 1.15)
                l, t = max(0, int(fx) - reach), max(0, int(fy) - reach)
                crop = frame[t:min(fh, int(fy) + reach), l:min(fw, int(fx) + reach)]
                if crop.shape[0] < 8 or crop.shape[1] < 8:
                    continue
                score, pt, sc = best_match(crop, tpl, self.ui_scale or 1.0)
                if pt is None or score < MONEY_THRESH:
                    continue
                cx, cy = l + pt[0], t + pt[1]
                half_w, half_h = tpl.shape[1] * (sc or 1.0) / 2 + 12, tpl.shape[0] * (sc or 1.0) / 2 + 12
                if abs(fx - cx) <= half_w and abs(fy - cy) <= half_h:
                    return f'{name} {score:.2f}'
        except Exception:
            return None
        return None

    def click_frac(self, frac, label):
        if frac is None:
            return False
        w, h = self.browser.width(), self.browser.height()
        return self.click((int(w * frac[0]), int(h * frac[1])), label)

    def icon_row_point(self, target, frame):
        """Where the target icon is, judged from the whole icon row. At least two of the three icons must be
        seen (even weakly) AND line up like the real row (same height, equal spacing) - far stricter than one
        loose picture match, so it cannot land on the game map. Returns ((x, y), scale) or None."""
        res = self.results or {}
        got = {}
        for i, n in enumerate(ROW_ORDER):
            sc, pt, s = res.get(n, (0, None, None))
            if pt is not None and s and sc >= .60:
                got[i] = (pt, s)
        if len(got) < 2:
            return None
        s_avg = sum(v[1] for v in got.values()) / len(got)
        step = ROW_STEP * s_avg
        ys = [v[0][1] for v in got.values()]
        if max(ys) - min(ys) > 0.08 * step:
            return None
        idx = sorted(got)
        for a in idx:
            for b in idx:
                if b > a and abs((got[b][0][0] - got[a][0][0]) - (b - a) * step) > 0.15 * step:
                    return None
        ti = ROW_POS[ICON_FOR[target]]
        if ti in got:
            cx = got[ti][0][0]
        else:
            a = idx[0]
            cx = got[a][0][0] + (ti - a) * step
        return (cx, sum(ys) / len(ys)), s_avg

    def click_tpl(self, name, frame, label):
        """Click the middle of a found picture (plus that picture's own click offset)."""
        pt = self.found(frame, name)
        if pt is None:
            return False
        scale = self.scale_of(name)
        m = self.meta.get(name, {})
        fx = pt[0] + m.get('dx', 0) * scale
        fy = pt[1] + m.get('dy', 0) * scale
        return self.click(self.to_logical((fx, fy), frame), label)

    def _cdp_click_worker(self, x, y, w, h, label):
        try:
            with self.click_lock:
                self.cdp.click(x, y)
            self.log_signal.emit(f'Clicked {label} at ({x}, {y}) / {w}x{h}')
        except (CdpError, OSError, ValueError) as exc:
            self.log_signal.emit(f'DevTools click unavailable ({exc}); falling back to Qt events.')
            self.fallback_signal.emit(x, y, label)

    def qt_click(self, x, y, label):
        """Fallback: synthetic Qt events with a hover and a held press (GUI thread)."""
        target = self.browser.focusProxy() or self.browser
        local_pt = target.mapFromGlobal(self.browser.mapToGlobal(QPoint(x, y)))
        if not target.rect().contains(local_pt):
            self.log(f'BLOCKED click: rendering widget did not contain {local_pt}')
            return
        self._bot_input = True
        try:
            QTest.mouseMove(target, local_pt)
            QTest.qWait(120)
            QTest.mouseClick(target, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, local_pt, 90)
        finally:
            self._bot_input = False
        self.log(f'Clicked {label} (Qt fallback) at ({x}, {y})')

    def close_advert(self, st):
        """Close the Dragon Pack advert on the MAIN screen: one tap on the chat panel (harmless - it never walks the
        character), then wait for the advert to fade away before even considering another tap."""
        now = time.monotonic()
        if now - st.get('adv_t', -99.0) < 2.5:
            return False
        n = st.get('adv_n', 0)
        if self.click_frac(ADVERT_POINTS[n % len(ADVERT_POINTS)], 'on the chat panel to close the Dragon Pack advert (safe spot)'):
            st['adv_t'], st['adv_n'] = now, n + 1
            return True
        return False

    def dismiss_click(self, st, why='pop-up'):
        """Tap outside a pop-up (only called while a pop-up is detected)."""
        i = st.get('dismiss', 0)
        frac = DISMISS_POINTS[i % len(DISMISS_POINTS)]
        if self.click_frac(frac, f'outside the {why} to close it'):
            st['dismiss'] = i + 1
            return True
        return False

    # ----------------------------------------------------------------- login
    def start_login(self, frame):
        """Type the e-mail and password into the login form and press Login (runs in a worker thread)."""
        creds = self.credentials()
        pt = self.found(frame, 'login_button')
        if creds is None or pt is None:
            return False
        scale = self.scale_of('login_button')

        def at(key):
            dx, dy = LOGIN_OFFSETS[key]
            return self.to_logical((pt[0] + dx * scale, pt[1] + dy * scale), frame)
        # Is "Keep me logged in" still unticked? (an empty box is light)
        kx, ky = pt[0] + LOGIN_OFFSETS['keep'][0] * scale, pt[1] + LOGIN_OFFSETS['keep'][1] * scale
        r = max(3, int(6 * scale))
        h, w = frame.shape
        patch = frame[max(0, int(ky) - r):min(h, int(ky) + r), max(0, int(kx) - r):min(w, int(kx) + r)]
        unticked = patch.size > 0 and float(patch.mean()) > 170
        points = {'email': at('email'), 'password': at('password'), 'keep': at('keep'), 'login': self.to_logical(pt, frame)}
        self.login_busy = True
        self.log('Login page detected - typing the e-mail and password (hidden) and pressing Login.')
        threading.Thread(target=self._login_worker, args=(creds, points, unticked), daemon=True).start()
        return True

    def _login_worker(self, creds, pts, tick_keep):
        email, password = creds
        try:
            with self.click_lock:
                c = self.cdp
                c.triple_click(*pts['email'])
                time.sleep(.25)
                c.insert_text(email)
                time.sleep(.35)
                c.triple_click(*pts['password'])
                time.sleep(.25)
                c.insert_text(password)
                time.sleep(.35)
                if tick_keep:
                    c.click(*pts['keep'])
                    time.sleep(.3)
                c.click(*pts['login'])
            self.log_signal.emit('Login submitted.')
        except (CdpError, OSError, ValueError) as exc:
            self.log_signal.emit(f'Login typing failed: {exc}')
        finally:
            self.login_done_at = time.monotonic()
            self.login_busy = False

    # ----------------------------------------------------------------- running
    def run_now(self):
        sel = self.from_combo.currentData()
        if sel in (None, 'next'):
            self.start()
            return
        ids = [t['id'] for t in TASKS]
        self.start(ids[ids.index(sel):], force=True)

    def toggle_pause(self):
        if not self.running:
            return
        if not self.paused:
            self.paused = True
            self.pause_t = time.monotonic()
            self.pause_btn.setText('RESUME')
            self.status.setText('Paused - press RESUME to continue')
            self.log('Paused. Nothing is clicked until you press RESUME.')
        else:
            delta = time.monotonic() - self.pause_t
            self.run_started += delta
            self.ad_wait_until += delta
            self.paused = False
            self.pause_btn.setText('PAUSE')
            self.log('Resumed - re-checking the screen and continuing the current step.')
            self.screen = None
            self.last_click = 0
            self.begin_step()

    def current_task_id(self):
        for e in self.queue[self.qi:]:
            if e['task']:
                return e['task']
        for e in reversed(self.queue[:self.qi]):
            if e['task']:
                return e['task']
        return TASKS[0]['id']

    def reset_progress(self):
        """Clear today's 'done' marks so the list shows 0/6 and everything can be collected again."""
        if self.running:
            QMessageBox.information(self, 'Reset', 'Stop the run first (or pause and use REFRESH), then reset.')
            return
        who = self.run_account or 'this account'
        box = QMessageBox(self)
        box.setWindowTitle('Reset progress')
        box.setText(f'Reset today\'s progress so it shows 0/{len(TASKS)} done?\n\nThe bot will treat every collection as not done yet.')
        b_one = box.addButton(f'Reset {who}', QMessageBox.ButtonRole.AcceptRole)
        b_all = box.addButton('Reset all accounts', QMessageBox.ButtonRole.DestructiveRole) if len(self.accounts) > 1 else None
        box.addButton('Cancel', QMessageBox.ButtonRole.RejectRole)
        box.exec()
        clicked = box.clickedButton()
        if clicked is b_one:
            self.save_state({})
            self.log(f'Progress reset for {who}: 0/{len(TASKS)} done.')
        elif b_all is not None and clicked is b_all:
            for a in self.accounts:
                self.save_state({}, a['name'])
            self.log(f'Progress reset for all accounts: 0/{len(TASKS)} done.')
        else:
            return
        self.refresh_tasks()
        self.update_badge()
        self.from_combo.setCurrentIndex(0)

    def refresh_run(self):
        if not self.running:
            self.reload_game()
            return
        ids = [t['id'] for t in TASKS]
        cur = self.current_task_id()
        was_paused = self.paused
        self.paused = True                       # nothing is clicked while the question is open
        box = QMessageBox(self)
        box.setWindowTitle('Refresh')
        box.setText('Reload the game page and start again.\nWhere should the run continue?')
        b_res = box.addButton(f'Resume from {TASK_BY_ID[cur]["title"]}', QMessageBox.ButtonRole.AcceptRole)
        b_beg = box.addButton('Start from beginning', QMessageBox.ButtonRole.DestructiveRole)
        box.addButton('Cancel', QMessageBox.ButtonRole.RejectRole)
        box.exec()
        clicked = box.clickedButton()
        if clicked is b_res:
            todo = ids[ids.index(cur):]
        elif clicked is b_beg:
            todo = ids
        else:
            self.paused = was_paused
            return
        self.paused = False
        self.pending_restart = todo
        self.stop('Stopped by user (refresh)')
        self.reload_game()
        QTimer.singleShot(60000, self.do_restart)          # fallback if the load signal never comes

    def do_restart(self):
        ids, self.pending_restart = self.pending_restart, None
        if ids and not self.running:
            self.log('Restarting after refresh.')
            self.start(ids, force=True)

    def run_all_accounts(self):
        """Collect for every account, one after another (each one logs in, collects what is not done today, then the next)."""
        if self.running:
            return
        names = self.acct_names()
        if len(names) < 2:
            self.log('Run all accounts needs at least two accounts (Accounts tab).')
            return
        self.chain = list(names)
        self.log('Run all accounts: ' + ', '.join(names))
        self.chain_next()

    def chain_next(self):
        if self.running:
            return
        while self.chain:
            name = self.chain.pop(0)
            if not self.pending_tasks('all', name):
                self.log(f'Run all accounts: {name} - everything already collected today, skipped.')
                continue
            self.log(f'Run all accounts: starting {name} ({len(self.chain)} more after it).')
            if self.start(self.pending_tasks('all', name), acct=name):
                return
            self.log(f'Run all accounts: could not start {name}.')
        self.log('Run all accounts: finished.')

    def run_single(self, item):
        tid = item.data(Qt.ItemDataRole.UserRole)
        if tid in TASK_BY_ID:
            self.start([tid], force=True)

    def start(self, task_ids=None, force=False, auto=False, acct=None):
        if self.running:
            return False
        if acct and acct in self.acct_names():
            self.run_account = acct
            self.acct_combo.blockSignals(True)
            self.acct_combo.setCurrentIndex(max(0, self.acct_combo.findData(acct)))
            self.acct_combo.blockSignals(False)
        if not self.run_account:
            self.log('Add an account first (Accounts tab).')
            return False
        done = self.load_state()
        ids = task_ids or [t['id'] for t in TASKS]
        todo = [i for i in ids if force or i not in done]
        if not todo:
            self.log('Everything selected has already been collected today (game day). Double-click a collection to run it again.')
            return False
        self.tabs.setCurrentIndex(0)   # the game must be visible to be screenshotted
        self.setup_btn.setChecked(False)
        self.queue = []
        first = self.accounts[0]['name'] if self.accounts else None
        if (self.logged_in and self.logged_in != self.run_account) or (not self.logged_in and len(self.accounts) > 1 and self.run_account != first):
            self.queue.append({'task': None, 'step': {'k': 'switch'}})
        self.queue.append({'task': None, 'step': {'k': 'ingame'}})
        self.queue.append({'task': None, 'step': {'k': 'perf', 'label': 'Settings: Hide FX and Hide Models (saves CPU)'}})
        for tid in todo:
            task = TASK_BY_ID[tid]
            self.queue.append({'task': tid, 'step': {'k': 'goto', 'group': task['group']}})
            for step in task['steps']:
                self.queue.append({'task': tid, 'step': step})
        self.queue.append({'task': None, 'step': {'k': 'goto', 'group': 'main'}})
        self.run_ids = list(todo)
        self.qi = 0
        self.task_notes = {}
        self.task_failed = {}
        self.run_results = []
        self.screen = None
        self.adfix = 0
        self.ad_wait_until = 0.0
        self.opened_once = False
        self.auto_run_active = auto
        if self.rec_btn.isChecked():
            self.rec_btn.setChecked(False)      # a run is the bot's clicks, not yours
        self.lock_cb.setChecked(True)           # every run starts locked; click the badge to take over
        self.running = True
        self.hook_input()
        self.run_started = time.monotonic()
        self.last_click = 0
        self.start_btn.setEnabled(False)
        self.runall_btn.setEnabled(False)
        self.acct_combo.setEnabled(False)
        self.pause_btn.setEnabled(True)
        self.stop_btn.setEnabled(True)
        self.log(f'Run started for account "{self.run_account}": ' + ', '.join(TASK_BY_ID[i]['title'] for i in todo))
        self.enter_background()
        self.begin_step()
        self.timer.start()
        return True

    def stop(self, reason='Stopped by user'):
        was_running = self.running
        user_stop = reason.startswith('Stopped by user')
        failed = bool(self.task_failed) or reason.startswith(('FAILED', 'Stopped after error'))
        ok = was_running and not user_stop and not failed
        was_auto = self.auto_run_active
        self.auto_run_active = False
        if was_running and failed and self.last_frame is not None:
            try:
                (ROOT / 'debug').mkdir(exist_ok=True)
                path = ROOT / 'debug' / f'fail_{datetime.now():%Y%m%d_%H%M%S}.png'
                cv2.imwrite(str(path), self.snap_bgr if self.snap_bgr is not None else self.last_frame)
                self.log(f'Saved debug screenshot: {path.name}')
            except Exception:
                pass
        summary = '; '.join(self.run_results) if self.run_results else reason
        if was_running and not user_stop:
            self.record_history(summary if self.run_results else reason, ok)
            self.notify('Nova Collector - ' + ('done' if ok else 'problem'), summary[:200])
            try:
                self.make_report(reason, ok, was_auto)
            except Exception as exc:
                self.log(f'(could not write the report: {exc})')
        if was_running and not user_stop:
            acct = self.run_account
            mem = {k: v for k, v in self.fail_memory.get(acct, {}).items() if k not in getattr(self, 'run_ids', [])}
            mem.update({k: v for k, v in self.task_failed.items() if k in TASK_BY_ID})
            self.fail_memory[acct] = mem
            self.save_settings()
        self.running = False
        self.paused = False
        self.pause_btn.setText('PAUSE')
        self.pause_btn.setEnabled(False)
        self.cur_task = None
        self.timer.stop()
        self.leave_background()
        self.start_btn.setEnabled(True)
        self.runall_btn.setEnabled(True)
        self.acct_combo.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.status.setText('Idle')
        self.refresh_tasks()
        self.update_badge()
        self.log(reason)
        if self.chain:
            if user_stop or not was_running:
                self.chain = []
                self.log('Run all accounts: cancelled.')
            else:
                QTimer.singleShot(3000, self.chain_next)
        if was_auto and was_running and failed and not user_stop:
            self.log('Auto run had problems; the game is reloaded and it tries again in about 10 minutes (up to 3 tries a day).')
            self.reload_game()

    def tick(self):
        """GUI thread: grab a frame (fast), then analyse it in a worker thread."""
        if not self.running or self.analysing or self.paused:
            return
        names = step_needs(self.queue[self.qi]['step']) if self.qi < len(self.queue) else []
        self.cap_t = time.monotonic()                      # when this picture was taken (the bot must not act on pictures older than its last move)
        frame = None if self.bg_active else self.snapshot()
        if frame is None or float(frame[::16, ::16].std()) < 1.5:       # background mode, or a blank widget grab
            self.analysing = True
            threading.Thread(target=self._analyse_cdp, args=(names,), daemon=True).start()
            return
        self.analysing = True
        threading.Thread(target=self._analyse, args=(frame, self.snap_bgr, names), daemon=True).start()

    def _analyse_cdp(self, names):
        """Screenshot taken by the browser itself (DevTools) - works when the window is hidden-ish/covered."""
        try:
            self.cap_t = time.monotonic()
            with self.click_lock:
                data = self.cdp.screenshot()
            bgr = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
            if bgr is None:
                raise ValueError('empty screenshot')
            self.snap_bgr = bgr
            gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        except Exception as exc:
            if time.monotonic() - self.cdp_warned > 20:
                self.cdp_warned = time.monotonic()
                self.log_signal.emit(f'DevTools screenshot failed: {exc}')
            self.analysing_reset.emit()
            return
        self._analyse(gray, bgr, names)

    def _analyse(self, frame, bgr, names):
        results = {}
        try:
            self.cur_bgr = bgr
            for n in names:
                results[n] = self.locate_raw(frame, n)
        except Exception as exc:
            self.log_signal.emit(f'Analysis error: {exc}')
        self.analysis_done.emit(frame, results)

    def on_analysis(self, frame, results):
        self.analysing = False
        if not self.running or self.paused:
            return
        self.frame_t = getattr(self, 'cap_t', time.monotonic())
        self.results = results
        self.shot_offer_run(frame)
        try:
            self._tick(frame)
        except Exception as exc:
            self.log(f'ERROR: {exc}')
            self.log(traceback.format_exc().splitlines()[-1])
            self.stop('Stopped after error')
        finally:
            self.results = None

    def begin_step(self):
        entry = self.queue[self.qi]
        step = entry['step']
        self.st = {'t0': time.monotonic(), 'ph': 'start', 'clicks': 0, 'tries': 0, 'dismiss': 0}
        self.step_started = time.monotonic()
        self.region_override = {}
        if step.get('region') and step.get('find'):
            self.region_override[step['find']] = step['region']
        if step.get('find') in ('claim_text', 'claim_diamond', 'checkin_btn'):
            self.scale_hint.pop(step['find'], None)       # button size differs from screen to screen
            self.last_full.pop(step['find'], None)
            self.last_result.pop(step['find'], None)
        tid = entry['task']
        if tid != self.cur_task:
            self.cur_task = tid
            self.refresh_tasks()
        title = TASK_BY_ID[tid]['title'] if tid else ''
        label = step.get('label') or {'ingame': 'getting into the game', 'goto': 'opening ' + str(step.get('group', ''))}.get(step['k'], step['k'])
        self.status.setText((title + ' - ' if title else '') + label)
        self.log(f'Step: {title + " - " if title else ""}{label}')

    def _tick(self, frame):
        now = time.monotonic()
        if now - self.run_started > 1500:
            self.task_failed['run'] = 'timed out'
            self.stop('FAILED: the run took more than 25 minutes and was stopped.')
            return
        self.last_frame = frame
        entry = self.queue[self.qi]
        step = entry['step']
        res = getattr(self, 'st_' + step['k'])(step, self.st, frame, now - self.st['t0'])
        if res is None:
            return
        kind, note = (res, '') if isinstance(res, str) else res
        tid = entry['task']
        if kind == 'skiptask':                               # nothing to do for this whole collection
            self.log(note)
            self.task_notes.setdefault(tid, []).append(note)
            while self.qi + 1 < len(self.queue) and self.queue[self.qi + 1]['task'] == tid:
                self.qi += 1
            self.advance()
            return
        if kind == 'fail':
            self.log(f'FAILED: {note}')
            self.save_debug('step_failed')
            if tid is None and step['k'] == 'ingame':
                self.task_failed['ingame'] = note
                self.run_results.append('Could not get into the game: ' + note)
                self.stop('FAILED: ' + note)
                return
            self.screen = None
            self.fail_task(tid, note)
            return
        if note:
            self.task_notes.setdefault(tid, []).append(note)
            self.log(note)
        self.advance()

    def advance(self):
        entry = self.queue[self.qi]
        tid = entry['task']
        self.qi += 1
        if self.qi >= len(self.queue) or self.queue[self.qi]['task'] != tid:
            self.complete_task(tid)
        if self.qi >= len(self.queue):
            self.finish_run()
            return
        self.begin_step()

    def complete_task(self, tid):
        if tid is None or tid in self.task_failed:
            return
        note = ' / '.join(self.task_notes.get(tid, [])) or 'done'
        done = self.load_state()
        done[tid] = note
        self.save_state(done)
        self.run_results.append(f'{TASK_BY_ID[tid]["title"]}: {note}')
        self.refresh_tasks()
        self.update_badge()

    def fail_task(self, tid, note):
        self.task_failed[tid] = note
        self.run_results.append(f'{TASK_BY_ID[tid]["title"]}: FAILED - {note}')
        while self.qi < len(self.queue) and self.queue[self.qi]['task'] == tid:
            self.qi += 1
        self.refresh_tasks()
        if self.qi >= len(self.queue):
            self.finish_run()
            return
        self.begin_step()

    @staticmethod
    def find_red_dots(bgr, region=(.50, .02, 1.0, .62), area=None):
        """Red notification dots inside a region (fractions of the picture). Returns [(x fraction, y fraction), ...].
        `area` is (min, max) dot area in pixels at a 3439-wide picture; the default suits the main page icons."""
        h, w = bgr.shape[:2]
        x0, y0, x1, y1 = int(w * region[0]), int(h * region[1]), int(w * region[2]), int(h * region[3])
        roi = bgr[y0:y1, x0:x1]
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        m = (((hsv[..., 0] < 7) | (hsv[..., 0] > 172)) & (hsv[..., 1] > 150) & (hsv[..., 2] > 170)).astype(np.uint8)
        m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        n, _lab, stats, cen = cv2.connectedComponentsWithStats(m)
        if area is None:
            lo, hi = (w * .0040) ** 2 * .5, (w * .0085) ** 2 * 1.2
        else:
            k = (w / 3439.0) ** 2
            lo, hi = area[0] * k, area[1] * k
        out = []
        for i in range(1, n):
            _x, _y, bw, bh, a = stats[i]
            if lo <= a <= hi and .7 <= bw / bh <= 1.4 and a / float(bw * bh) > .6:
                out.append(((x0 + cen[i][0]) / w, (y0 + cen[i][1]) / h))
        return sorted(out, key=lambda p: (round(p[1], 2), p[0]))

    def red_dot_report(self):
        """Report only (never clicks): which main-page icons still show a red dot after the run."""
        try:
            bgr = self.snap_bgr if self.snap_bgr is not None else self.cur_bgr
            if bgr is None or self.screen not in ('main', None):
                return
            dots = self.find_red_dots(bgr)
            where = ', '.join(f'({x * 100:.0f}%, {y * 100:.0f}%)' for x, y in dots) or 'none'
            self.log(f'Red dots still showing on the main page: {len(dots)} - {where}')
            if dots:
                self.run_results.append(f'{len(dots)} red dot(s) still on the main page (not collected by the bot yet)')
        except Exception as exc:
            self.log(f'Red-dot check skipped: {exc}')

    def finish_run(self):
        self.red_dot_report()
        if self.task_failed:
            self.stop('FAILED: ' + '; '.join(f'{TASK_BY_ID[k]["title"] if k in TASK_BY_ID else k}: {v}' for k, v in self.task_failed.items()))
        else:
            self.stop('SUCCESS: ' + ('; '.join(self.run_results) or 'finished') + '. Back on the main page.')

    # ------------------------------------------------------------------- steps
    def mark_logged_in(self):
        if self.logged_in != self.run_account:
            self.logged_in = self.run_account
            self.save_settings()
            self.logged_label.setText(f'Currently logged in to the game as: {self.logged_in}')

    def st_switch(self, step, st, frame, el):
        """Another account is logged in: clear the login cookies and reload so the login page shows."""
        now = time.monotonic()
        if st['ph'] == 'start':
            self.log(f'Switching account: logging out "{self.logged_in or "previous session"}" first.')
            self.profile.cookieStore().deleteAllCookies()
            self.page_loaded_at = None
            self.logged_in = None
            self.save_settings()
            self.browser.reload()
            st['ph'], st['tc'] = 'wait', now
            return None
        if self.page_loaded_at is not None and now - self.page_loaded_at >= 2.0:
            return 'next'
        if el > 45:
            return 'next'
        return None

    def adbar_busy(self, frame, now):
        """The advert bar must be folded away (small up arrow) before the game icons are used.
        Returns True while an arrow click is pending / settling."""
        if now < self.ad_wait_until:
            return True
        if self.adfix < 4 and self.found(frame, 'ad_arrow'):
            if self.click_tpl('ad_arrow', frame, 'the ad-bar up arrow (fold the adverts away)'):
                self.adfix += 1
                self.adbar_done = True
                self.ad_wait_until = now + 1.0
                return True
        return False

    def st_ingame(self, step, st, frame, el):
        """Log in if needed, remove the ad bar, press Enter Game, close the Dragon Pack advert."""
        now = time.monotonic()
        if el > (240 if self.auto_run_active else 120):
            return ('fail', 'could not get into the game (timed out). Is the game page showing something unexpected?')
        if self.login_busy:
            return None
        if self.found(frame, 'notice_close'):              # server notice / maintenance window: press its red X
            st.pop('main_since', None)
            if self.click_tpl('notice_close', frame, 'the red X of the game notice'):
                st['notices'] = st.get('notices', 0) + 1
            return None
        if self.found(frame, 'login_button'):
            st.pop('main_since', None)
            if now - self.login_done_at < 25:
                return None                                # waiting for the page to move on after Login
            if st.get('login_tries', 0) >= 2:
                return ('fail', 'the login page is still showing after 2 tries - check the e-mail and password on the Accounts tab')
            if self.credentials() is None:
                return ('fail', 'the game shows the login page but no account is saved (Accounts tab)')
            st['login_tries'] = st.get('login_tries', 0) + 1
            self.start_login(frame)
            return None
        if self.found(frame, 'enter_game'):
            st.pop('main_since', None)
            if not self.adbar_done:
                if self.found(frame, 'ad_arrow'):
                    ok = self.click_tpl('ad_arrow', frame, 'the ad-bar arrow')
                elif now - st.setdefault('enter_seen', now) > 2.0:
                    ok = self.click_frac(self.pos('ad_arrow'), 'the ad-bar arrow (saved/default position)')
                else:
                    ok = False
                if ok:
                    self.adbar_done = True
                    st['ad_t'] = now
                return None
            if now - st.get('ad_t', 0) < 1.0 or now - st.get('enter_t', 0) < 8:
                return None
            if st.get('enters', 0) >= 2 and not st.get('reloaded'):
                st['reloaded'], st['enters'], st['t0'] = True, 0, now
                self.adbar_done, self.adfix = False, 0
                self.log('Enter Game was pressed twice but nothing happened - reloading the game page once (the session may have expired).')
                self.reload_game()
                return None
            if st.get('enters', 0) >= 4:
                return ('fail', 'Enter Game was pressed 4 times but the game did not start')
            if self.click_tpl('enter_game', frame, 'Enter Game'):
                st['enter_t'] = now
                st['enters'] = st.get('enters', 0) + 1
            return None
        if self.found(frame, 'dragon_pack'):
            st.pop('main_since', None)
            self.close_advert(st)
            return None
        in_sub = self.found(frame, 'back_arrow')
        if self.found(frame, 'icon_privileges') and not in_sub:
            st.setdefault('main_since', now)
            if self.adbar_busy(frame, now):
                return None
            if now - st['main_since'] >= 0.9:              # stay a moment: adverts can pop up late
                self.screen = 'main'
                self.mark_logged_in()
                return ('ok', 'In the game.')
            return None
        if in_sub:
            if self.adbar_busy(frame, now):
                return None
            self.screen = None
            self.mark_logged_in()
            return ('ok', 'In the game (a menu screen is open).')
        st.pop('main_since', None)
        # Nothing recognisable on screen (e.g. the game map behind the icons): if Enter Game was pressed
        # a while ago, assume we are in the game and let the next step use the icon / saved positions.
        if st.get('enters', 0) >= 1 and now - st.get('enter_t', now) > 14:
            if self.adbar_busy(frame, now):
                return None
            self.screen = None
            self.mark_logged_in()
            return ('ok', 'In the game (main page not recognised by picture; using saved icon positions).')
        return None

    def st_goto(self, step, st, frame, el):
        """Get to the main page / Privileges / Shop / Perks."""
        target = step['group']
        now = time.monotonic()
        if self.screen == target and st['ph'] == 'start':
            return 'next'
        if target in EVENT_GOTO:
            return self.st_goto_event(step, st, frame, el)
        if el > 60:
            self.screen = None
            return ('fail', f'could not open {target}')
        if self.found(frame, 'notice_close'):
            self.click_tpl('notice_close', frame, 'the red X of the game notice')
            return None
        if self.found(frame, 'dragon_pack'):
            self.close_advert(st)
            return None
        back = self.found(frame, 'back_arrow')
        ph = st['ph']
        if not back and ph != 'back' and self.adbar_busy(frame, now):
            return None
        if ph == 'start':
            if target == 'main' and st.get('went_back') and not back and el >= 0.3:
                self.screen = 'main'                       # the back arrow did its job
                return 'next'
            if back:                                       # inside some menu screen: go back first
                if self.click_tpl('back_arrow', frame, 'the back arrow'):
                    st['ph'], st['tc'], st['went_back'] = 'back', now, True
                    st.pop('row_t', None)
                return None
            icons = [n for n in ('icon_privileges', 'icon_shop', 'icon_perks') if self.found(frame, n)]
            if target == 'main':
                if icons and el >= 0.15:
                    self.screen = 'main'
                    return 'next'
                if el > 3:
                    self.screen = 'main'
                    return ('ok', 'Could not confirm the main page; carrying on.')
                return None
            icon = ICON_FOR[target]
            main_seen = bool(icons)                      # at least one top-right icon recognised = main page is showing
            expected = self.pos(target)
            if target in self.positions:
                # Calibrated position: never click where a loose picture match says (it could land on the map).
                if (main_seen and el >= 0.15) or el > 2:
                    if self.click_frac(expected, f'the {target} icon (calibrated position)'):
                        st['ph'], st['tc'] = 'opening', now
            else:
                rp = self.icon_row_point(target, frame)
                if rp is not None and el >= 0.15:
                    (cx, cy), sc = rp
                    m = self.meta.get(icon) or self.meta.get('icon_perks', {})
                    fx, fy = cx + m.get('dx', 0) * sc, cy + m.get('dy', 0) * sc
                    fh, fw = frame.shape
                    if self.click(self.to_logical((fx, fy), frame), f'the {target} icon (found with the icon row)'):
                        st['ph'], st['tc'], st['auto_pos'] = 'opening', now, (fx / fw, fy / fh)
                    return None
                # No loose single-picture clicks any more (they could land on the minimap / game map).
                # Wait for the icon row to be recognisable; if it is not, use the default icon position.
                t0 = st.setdefault('row_t', now)
                if (main_seen and now - t0 > 0.8) or now - t0 > 2.5:
                    if expected[1] <= .07 and expected[0] >= .70:        # icons live in the top-right strip only
                        if self.click_frac(expected, f'the {target} icon (default position)'):
                            st['ph'], st['tc'] = 'opening', now
            return None
        if ph == 'back':
            if now - st['tc'] >= 0.4 and (not back or now - st['tc'] > 3.0):   # wait until the old screen is really gone
                st['ph'] = 'start'
                if back:
                    st['tries'] += 1
            return None
        if ph == 'opening':
            cue = back or any(self.found(frame, n) for n in OPEN_CUES.get(target, []))
            if now - st['tc'] >= 0.3 and cue:
                self.screen = target
                self.opened_once = True
                if st.get('auto_pos') and target not in self.positions:      # it worked: remember the spot
                    self.positions[target] = (round(st['auto_pos'][0], 6), round(st['auto_pos'][1], 6))
                    try:
                        self.positions_file.write_text(json.dumps(self.positions, indent=2), encoding='utf-8')
                        self.log(f'Saved the {target} icon position automatically (no calibration needed).')
                    except OSError:
                        pass
                return 'next'
            if now - st['tc'] > (10 if self.opened_once else 25):
                st['tries'] += 1
                if st['tries'] >= 3:
                    self.screen = None
                    return ('fail', f'the {target} screen did not open')
                st['ph'] = 'start'
            return None
        return None

    def st_goto_event(self, step, st, frame, el):
        """Open an event / system from an icon on the main screen (Pet Theme, Limited-Time Event, Daily). Event icons are only
        there some weeks: when the main screen is up and the icon is not showing, the whole collection is skipped."""
        target, now = step['group'], time.monotonic()
        cfg = EVENT_GOTO[target]
        icon, nm = cfg['icon'], cfg['name']
        if el > 60:
            self.screen = None
            return ('fail', f'could not open the {nm} screen')
        if self.found(frame, 'notice_close'):
            self.click_tpl('notice_close', frame, 'the red X of the game notice')
            return None
        if self.found(frame, 'dragon_pack'):
            self.close_advert(st)
            return None
        back = self.found(frame, 'back_arrow')
        ph = st['ph']
        if not back and ph != 'back' and self.adbar_busy(frame, now):
            return None
        if ph == 'start':
            if back:                                        # inside some menu screen: go back to the main page first
                if self.click_tpl('back_arrow', frame, 'the back arrow'):
                    st['ph'], st['tc'] = 'back', now
                    st.pop('main_t', None)
                return None
            main_seen = any(self.found(frame, n) for n in ('icon_privileges', 'icon_shop', 'icon_perks'))
            if not main_seen:
                if el > 12:
                    return ('skiptask', f'{nm}: could not see the main page, so it was skipped.')
                return None
            self.screen = 'main'
            t0 = st.setdefault('main_t', now)
            pt = self.found(frame, icon)
            icon_used = icon
            if pt is None:
                for alt in cfg.get('alts', ()):                 # other pictures of the same icon (the map behind it changes)
                    pt = self.found(frame, alt)
                    if pt is not None:
                        icon_used = alt
                        break
            if pt is None:
                st.pop('ppt', None)
                if now - t0 > 2.2:
                    self.log(f'  {nm} icon: best match {self.locate(frame, icon)[0]:.2f} (needs {THRESH[icon]:.2f}).')
                    if not cfg['optional']:
                        return ('fail', f'the {nm} icon was not found on the main page')
                    return ('skiptask', f'{nm}: the event icon is not showing this week - nothing to collect.')
                return None
            prev, st['ppt'] = st.get('ppt'), pt
            if prev is None or abs(prev[0] - pt[0]) > 5 or abs(prev[1] - pt[1]) > 5 or now - t0 < 0.6:
                return None                                 # wait until the icon sits still
            m = self.meta.get(icon_used, {})
            sc = self.scale_of(icon_used)
            if self.click(self.to_logical((pt[0] + m.get('dx', 0) * sc, pt[1] + m.get('dy', 0) * sc), frame), f'the {nm} icon'):
                st['ph'], st['tc'] = 'opening', now
            return None
        if ph == 'back':
            if now - st['tc'] >= 0.4 and (not back or now - st['tc'] > 3.0):
                st['ph'] = 'start'
            return None
        if ph == 'opening':
            if now - st['tc'] >= 0.4 and back:
                self.screen = target
                return 'next'
            if now - st['tc'] > 6:
                st['tries'] += 1
                if st['tries'] >= 3:
                    self.screen = None
                    return ('fail', f'the {nm} screen did not open')
                st['ph'] = 'start'
                st.pop('ppt', None)
            return None
        return None

    # ------------------------------------------------- Settings (Hide FX / Hide Models) and Slayer
    @staticmethod
    def tick_state(bgr, cx, cy, half):
        """True when a green check mark is inside the little tick box centred on (cx, cy) (frame pixels)."""
        h, w = bgr.shape[:2]
        x0, y0, x1, y1 = int(max(0, cx - half)), int(max(0, cy - half)), int(min(w, cx + half)), int(min(h, cy + half))
        box = bgr[y0:y1, x0:x1].astype(np.int16)
        if box.size == 0:
            return None
        B, G, R = box[..., 0], box[..., 1], box[..., 2]
        return float(((G > 150) & (G > R + 25) & (G > B + 80)).mean()) >= .06

    def slayer_counter(self, pt, scale):
        """(green, red) pixel counts of the coin counter under the Spin x1 button ("2/1"). Green = enough coins, red = not enough."""
        bgr = self.cur_bgr
        if bgr is None or pt is None:
            return None
        h, w = bgr.shape[:2]
        x0, x1 = int(max(0, pt[0] - 75 * scale)), int(min(w, pt[0] + 35 * scale))
        y0, y1 = int(max(0, pt[1] + 90 * scale)), int(min(h, pt[1] + 150 * scale))
        box = bgr[y0:y1, x0:x1].astype(np.int16)
        if box.size == 0:
            return None
        B, G, R = box[..., 0], box[..., 1], box[..., 2]
        green = int(((G > 170) & (G > B + 80) & (R > 90) & (G >= R - 30)).sum())
        red = int(((R > 190) & (G < 120) & (B < 120)).sum())
        return green, red

    def st_perf(self, step, st, frame, el):
        """Right after login: open the game's Settings and tick Hide FX and Hide Models (less CPU), then close it.
        A tick box is only pressed when it is NOT ticked yet, so running this again never switches anything off.
        This step never fails the run: if anything is unexpected it carries on and says so in the results."""
        now = time.monotonic()
        ph = st['ph']

        def soft(msg):
            self.run_results.append(msg)
            self.log(msg)
            return ('ok', '')
        if el > 60:
            return soft('Settings: skipped - took too long (Hide FX / Hide Models not changed).')
        if self.found(frame, 'notice_close'):
            self.click_tpl('notice_close', frame, 'the red X of the game notice')
            return None
        if self.found(frame, 'dragon_pack'):
            self.close_advert(st)
            return None
        title = self.found(frame, 'settings_title')
        if ph == 'start':
            if title is not None:                       # Settings is already open
                st['ph'], st['tc'] = 'opening', now
                return None
            main_seen = any(self.found(frame, n) for n in ('icon_privileges', 'icon_shop', 'icon_perks'))
            if self.found(frame, 'back_arrow') or not main_seen:
                if el > 20:
                    return soft('Settings: skipped - the main page was not showing (Hide FX / Hide Models not changed).')
                return None
            if el < 0.8 or self.adbar_busy(frame, now):
                return None
            if st.get('opens', 0) >= 3:
                return soft('Settings: skipped - the Settings window would not open (Hide FX / Hide Models not changed).')
            if self.click_frac(SETTINGS_GEAR, 'the Settings gear (under the minimap)'):
                st['opens'] = st.get('opens', 0) + 1
                st['ph'], st['tc'] = 'opening', now
            return None
        if ph == 'opening':
            if title is not None and now - st['tc'] >= 0.6:
                prev, st['tp'] = st.get('tp'), title
                if prev is None or abs(prev[0] - title[0]) > 4 or abs(prev[1] - title[1]) > 4:
                    return None                         # let the window finish sliding in
                st['ph'], st['box'], st['tc'] = 'tick', 0, now
                return None
            if now - st['tc'] > 4.0:
                st['ph'] = 'start'
                st.pop('tp', None)
            return None
        if ph == 'tick':
            if title is None:
                if now - st['tc'] > 3.0:
                    st['ph'] = 'start'
                return None
            bgr = self.cur_bgr
            if bgr is None:
                return None
            sc = self.scale_of('settings_title')
            names = ('Hide FX', 'Hide Models')
            i = st['box']
            if i >= 2:
                st['ph'], st['tc'], st['taps'] = 'closing', now, 0
                self.log('  Settings: Hide FX and Hide Models are both ticked.')
                return None
            ox, oy = SETTINGS_BOXES[i]
            cx, cy = title[0] + ox * sc, title[1] + oy * sc
            on = self.tick_state(bgr, cx, cy, 30 * sc)
            if on:
                st['box'], st['cl'] = i + 1, 0
                return None
            if now - st.get('lc', -9) < 1.0:
                return None
            if st.get('cl', 0) >= 3:
                st['box'], st['cl'] = i + 1, 0
                self.run_results.append(f'Settings: could not tick {names[i]} (it did not change after 3 presses).')
                self.log(f'Settings: could not tick {names[i]}.')
                return None
            if self.click(self.to_logical((cx, cy), frame), f'the {names[i]} tick box'):
                st['cl'] = st.get('cl', 0) + 1
                st['lc'] = now
            return None
        if ph == 'closing':
            main_seen = any(self.found(frame, n) for n in ('icon_privileges', 'icon_shop', 'icon_perks'))
            if title is None and main_seen:
                return ('ok', 'Settings: Hide FX and Hide Models are on (less CPU).')
            if now - st.get('lc2', -9) < 1.6:
                return None
            if st['taps'] >= 4:
                return soft('Settings: the window would not close by tapping outside (Hide FX / Hide Models were ticked).')
            if title is not None and self.click_frac(SETTINGS_CLOSE, 'outside the Settings window to close it'):
                st['taps'] += 1
                st['lc2'] = now
            return None
        return None

    def st_slayer(self, step, st, frame, el):
        """Slayer screen: make sure Skip Animation is ticked, then press Spin x1 for as long as the coin counter under the button
        is green (enough Dragon coins), closing the 'Reward obtained' pop-up after each spin. Spin x10 is never pressed."""
        now = time.monotonic()
        label = 'Slayer'
        if el > 420:
            return ('fail', f'{label}: took more than 7 minutes - stopped')
        if self.found(frame, 'dragon_pack'):
            self.dismiss_click(st, 'Dragon Pack advert')
            return None
        n = st.setdefault('n', 0)
        spin = self.found(frame, 'slayer_spin1')
        ph = st['ph']
        if ph in ('start', 'spin'):
            if self.found(frame, 'reward_obtained'):               # a reward pop-up from before: close it first
                if now - st.get('rt', -9) > 1.2:
                    st['rt'] = now
                    self.click_frac(SLAYER_DISMISS, 'outside the reward pop-up to close it')
                return None
            if spin is None or not self.found(frame, 'back_arrow'):
                if el > 12 and ph == 'start':
                    return ('fail', f'{label}: the Slayer screen with the Spin x1 button did not show')
                if ph == 'spin' and now - st.get('tc', now) > 8:
                    return ('ok', f'{label}: {n} spin(s) done (the screen changed, stopped).')
                return None
            prev, st['sp'] = st.get('sp'), spin
            if prev is None or abs(prev[0] - spin[0]) > 4 or abs(prev[1] - spin[1]) > 4 or el < 0.8:
                return None                                       # wait until the screen has settled
        if ph == 'start':
            sk = self.found(frame, 'slayer_skip')
            bgr = self.cur_bgr
            if sk is not None and bgr is not None:
                sc = self.scale_of('slayer_skip')
                cx, cy = sk[0] + SKIP_BOX[0] * sc, sk[1] + SKIP_BOX[1] * sc
                if not self.tick_state(bgr, cx, cy, 30 * sc):
                    if now - st.get('skt', -9) < 1.2:
                        return None
                    if st.get('skc', 0) >= 3:
                        self.log(f'  {label}: Skip Animation would not tick - spinning with the animation on.')
                    else:
                        if self.click(self.to_logical((cx, cy), frame), 'the Skip Animation tick box'):
                            st['skc'] = st.get('skc', 0) + 1
                            st['skt'] = now
                        return None
                else:
                    self.log(f'  {label}: Skip Animation is ticked.')
            elif el < 6:
                return None
            else:
                self.log(f'  {label}: Skip Animation label not found - spinning anyway.')
            st['ph'], st['tc'] = 'spin', now
            return None
        if ph == 'spin':
            cnt = self.slayer_counter(spin, self.scale_of('slayer_spin1'))
            sc2 = self.scale_of('slayer_spin1')
            if cnt is None:
                return None
            green, red = cnt
            enough = green >= 300 * sc2 * sc2 and red <= .15 * green
            if not enough:
                self.log(f'  {label}: coin counter green={green} red={red} -> not enough Dragon coins.')
                if n == 0:
                    return ('ok', f'{label}: no Dragon coins to spend (Skip Animation is on).')
                return ('ok', f'{label}: {n} spin(s) done, no Dragon coins left.')
            if n >= SLAYER_MAX_SPINS:
                return ('ok', f'{label}: {n} spins done (safety limit reached).')
            st['ref'] = self.frame_mean(frame)
            st['sig'] = cnt
            if self.click_tpl('slayer_spin1', frame, f'Spin x1 (spin {n + 1})'):
                st['ph'], st['tc'], st['dismiss'], st['seen'] = 'after', now, 0, False
                st.pop('pclear', None)
            return None
        # phase 'after': the reward pop-up shows (and fades); close it, then decide again
        if now - st['tc'] < 0.6:
            return None
        why = self.popup_why(frame, st.get('ref'))
        if why:
            st['seen'] = True
            st.pop('pclear', None)
            if now - st.get('dtap', -9) >= 1.2:
                if st['dismiss'] >= 10:
                    return ('fail', f'{label}: the reward pop-up would not close ({why})')
                if self.click_frac(SLAYER_DISMISS, 'outside the reward pop-up to close it'):
                    st['dismiss'] += 1
                    st['dtap'] = now
            return None
        st.setdefault('pclear', now)
        if now - st['pclear'] < 0.7:
            return None
        changed = False
        if spin is not None:
            cnt = self.slayer_counter(spin, self.scale_of('slayer_spin1'))
            sig = st.get('sig')
            if cnt is not None and sig is not None:
                changed = abs(cnt[0] - sig[0]) > .05 * max(1, sig[0]) or abs(cnt[1] - sig[1]) > 20
        if st['seen'] or changed:
            st['n'] = n + 1
            self.log(f'  {label}: spin {n + 1} done.')
            st['ph'], st['tc'] = 'spin', now
            st.pop('sp', None)
            return None
        if now - st['tc'] > 4.0:
            st['retry'] = st.get('retry', 0) + 1
            if st['retry'] >= 3:
                return ('ok', f'{label}: {n} spin(s) done; the next press did not register, stopped.')
            st['ph'], st['tc'] = 'spin', now
            st.pop('sp', None)
        return None

    # ------------------------------------------------------------- Valley of Light (Priest Event)
    def key_async(self, key, code, vk, label):
        """Press a keyboard key in the game through DevTools (worker thread). Not a user key event, so the input lock lets it through."""
        def work():
            try:
                with self.click_lock:
                    self.cdp.press_key(key, code, vk, 0.06)
                self.log_signal.emit(f'Pressed {label}')
            except (CdpError, OSError, ValueError) as exc:
                self.log_signal.emit(f'Key press failed ({exc})')
        threading.Thread(target=work, daemon=True).start()

    def map_open(self):
        """True when the map window is open: its NPC name buttons are green."""
        bgr = self.cur_bgr
        if bgr is None:
            return False
        h, w = bgr.shape[:2]
        x0, y0, x1, y1 = MAP_GREEN_ROI
        box = bgr[int(h * y0):int(h * y1), int(w * x0):int(w * x1)]
        if box.size == 0:
            return False
        hsv = cv2.cvtColor(box, cv2.COLOR_BGR2HSV)
        green = (hsv[..., 0] > 28) & (hsv[..., 0] < 60) & (hsv[..., 1] > 90) & (hsv[..., 2] > 60)
        return float(green.mean()) >= .25

    @staticmethod
    def list_crop(frame):
        h, w = frame.shape[:2]
        x0, y0, x1, y1 = MAP_LIST_ROI
        return frame[int(h * y0):int(h * y1), int(w * x0):int(w * x1)]

    @staticmethod
    def list_shift(before, after):
        """(moved, dy): did the list move between the two crops, and by how many pixels (None = moved but not measurable reliably)."""
        if before is None or after is None or before.shape != after.shape:
            return False, None
        if float(np.mean(cv2.absdiff(before, after) > 35)) < .04:
            return False, None
        try:
            win = cv2.createHanningWindow((before.shape[1], before.shape[0]), cv2.CV_32F)
            (dx, dy), resp = cv2.phaseCorrelate(before.astype(np.float32), after.astype(np.float32), win)
        except cv2.error:
            return True, None
        if resp < .35 or abs(dx) > 6 or abs(dy) < 3:         # many identical names (Guard, Guard...) can fool the measurement
            return True, None
        return True, abs(float(dy))

    def scroll_list_async(self, st, mode, sign, direction, units, px_css):
        """Move the map NPC list one step: `units` mouse-wheel notches, or a slow drag of `px_css` pixels.
        direction +1 = towards later names. For the wheel, sign flips the notch direction; for the drag, sign flips which way the pointer moves."""
        w, h = self.browser.width(), self.browser.height()
        x, yc = int(w * MAP_LIST_POINT[0]), int(h * MAP_LIST_POINT[1])
        st['sfin'] = None
        def work():
            try:
                with self.click_lock:
                    if mode == 'wheel':
                        self.cdp.scroll(x, yc, 100.0 * direction * sign, count=units, gap=0.07)
                    else:
                        half = int(px_css * direction * sign / 2)
                        # grab a name and pull it: pointer up shows the later names
                        self.cdp.drag(x, yc + half, x, yc - half, steps=30, step_delay=0.02, hold_start=0.1, hold_end=0.15)
            except (CdpError, OSError, ValueError) as exc:
                self.log_signal.emit(f'Scroll failed ({exc})')
            st['sfin'] = time.monotonic()
        threading.Thread(target=work, daemon=True).start()

    def hover_list_async(self, st):
        w, h = self.browser.width(), self.browser.height()
        x, y = int(w * MAP_LIST_POINT[0]), int(h * MAP_LIST_POINT[1])
        st['sfin'] = None
        def work():
            try:
                with self.click_lock:
                    self.cdp.hover(x, y, 0.7)
            except (CdpError, OSError, ValueError) as exc:
                self.log_signal.emit(f'Pointer move failed ({exc})')
            st['sfin'] = time.monotonic()
        threading.Thread(target=work, daemon=True).start()

    def map_scroll(self, st, frame, now, label):
        """Scroll the map's NPC list while watching it: grab a name and pull it up (or the wheel), whichever actually moves it."""
        crop = self.list_crop(frame)
        if crop.size == 0:
            return None
        # the game ignores the first wheel / drag after the map opens until the pointer has rested on the list: do that first
        if not st.get('warm'):
            st['warm'], st['sph'] = True, 'warm'
            self.hover_list_async(st)
            return None
        if st.get('sph') == 'warm':
            fin = st.get('sfin')
            if fin is None or now - fin < 0.4:
                return None
            st['sph'] = 'idle'
        cal = st.setdefault('cal', {})
        mul = st.setdefault('mul', {'wheel': 1.0, 'drag': 1.0})
        if st.get('sph') == 'busy':
            fin = st.get('sfin')
            if fin is None or getattr(self, 'frame_t', now) < fin + 0.5:
                return None                                    # still moving / settling (or this picture is older than the move)
            st['sph'] = 'idle'
            mode, sign, direction, units = st['sact']
            moved, dy = self.list_shift(st['sbefore'], crop)
            if moved:
                st['ever'], st['fails'], st['nm'] = True, 0, 0
                if dy is not None:
                    per = dy / max(1, units)
                    old = cal.get(mode)
                    cal[mode] = per if not old else min(old * 2, max(old * .5, per))
                elif mode == 'wheel':
                    mul[mode] = max(.2, mul[mode] * .5)       # moved too far to measure - smaller steps
                self.log(f'  {label}: the list moved ({mode}{f", {dy:.0f}px" if dy else ""}).')
            elif st.get('ever'):
                st['nm'] = st.get('nm', 0) + 1
                if st['nm'] < 3:
                    self.log(f'  {label}: that step did not register - trying again.')     # a missed drag is not the end of the list
                else:
                    st['nm'] = 0
                    st['rev'] = st.get('rev', 0) + 1
                    if st['rev'] > 3:
                        return ('fail', f'{label}: Priest (Event) was not found in the map list')
                    st['sdir'] = -st.get('sdir', 1)
                    self.log(f'  {label}: the list did not move 3 times in a row (end of the list) - turning around.')
            else:
                st['fails'] = st.get('fails', 0) + 1
                st['cf'] = st.get('cf', 0) + 1
                if st['cf'] >= 2:                                   # a way must fail twice before the next way is tried
                    st['cfg'], st['cf'] = (st.get('cfg', 0) + 1) % len(MAP_SCROLL_MODES), 0
                self.log(f'  {label}: the list did not move ({mode} {"+" if sign > 0 else "-"}) - trying again / another way.')
                if st['fails'] >= 10:
                    return ('fail', f'{label}: the map list would not scroll (mouse wheel and drag were both tried in both directions)')
            # (no waiting for the next tick: Priest (Event) was not in this picture, so go straight on)
        if st.get('sn', 0) >= 40:
            return ('fail', f'{label}: Priest (Event) was not found in the map list after 40 scroll steps')
        mode, sign = MAP_SCROLL_MODES[st.get('cfg', 0) % len(MAP_SCROLL_MODES)]
        direction = st.setdefault('sdir', 1)
        target = .5 * crop.shape[0]                           # aim for about half a page per step, in frame pixels
        k = self.browser.height() / max(1, frame.shape[0])
        if mode == 'wheel':
            per = cal.get('wheel')
            units = int(max(1, min(10, round(target / per)))) if per else max(1, round(3 * mul['wheel']))
            px_css = 0
        else:
            # grab the bottom name and pull it to the top: about 40% of the view height (the list follows about 1:1 or a bit more)
            per = cal.get('drag')
            hf = frame.shape[0]
            dist = (.46 * hf / per) if per else .42 * hf
            dist = max(.18 * hf, min(.45 * hf, dist * mul['drag']))
            units, px_css = max(1, int(dist)), int(dist * k)
        st['sact'] = (mode, sign, direction, units)
        st['sbefore'] = crop.copy()
        st['sph'] = 'busy'
        st['sn'] = st.get('sn', 0) + 1
        self.log(f'  {label}: scrolling the map list ({mode} {"down" if direction * sign > 0 else "up"}, step {st["sn"]}).')
        self.scroll_list_async(st, mode, sign, direction, units, px_css)
        return None

    def btn_active(self, pt, scale, half=(150, 40)):
        """True when the button around pt is coloured (gold) rather than greyed out."""
        bgr = self.cur_bgr
        if bgr is None or pt is None:
            return False
        h, w = bgr.shape[:2]
        x0, x1 = int(max(0, pt[0] - half[0] * scale)), int(min(w, pt[0] + half[0] * scale))
        y0, y1 = int(max(0, pt[1] - half[1] * scale)), int(min(h, pt[1] + half[1] * scale))
        box = bgr[y0:y1, x0:x1]
        if box.size == 0:
            return False
        sat = cv2.cvtColor(box, cv2.COLOR_BGR2HSV)[..., 1]
        return float((sat > 100).mean()) >= .5

    def st_valley(self, step, st, frame, el):
        """Valley of Light via the map: M > Priest (Event) > Enter Valley of Light > Party 3+ > Enter > Open > (die) > Revive,
        repeated until the 'reached entry limit' notice shows (Confirm, stop). Never presses Revive on Spot, Leave or Abandon Dungeon."""
        now = time.monotonic()
        label = 'Valley of Light'
        runs = st.setdefault('runs', 0)
        if el > 1500:
            return ('fail', f'{label}: took more than 25 minutes - stopped after {runs} run(s)')
        # the daily-limit notice: confirm it and finish (it can show up at the entry dialog)
        if st.get('limit'):
            if self.found(frame, 'notice_limit'):
                if now - st['nt'] > 4.0:                       # the picture is 1-2 s old: after a click, give it time to show the notice gone
                    if st.get('nclicks', 0) >= 3:
                        return ('fail', f'{label}: the entry-limit notice would not close')
                    if self.click_tpl('notice_confirm', frame, 'Confirm (daily entry limit notice)'):
                        st['nt'], st['nclicks'] = now, st.get('nclicks', 0) + 1
                return None
            if st.get('nclicks', 0) >= 1:
                if now - st['nt'] > 0.8:
                    return ('ok', f'{label}: {runs} run(s) done, daily entry limit reached.')
            elif now - st.setdefault('g0', now) > 3.0:         # it went away without a click
                return ('ok', f'{label}: {runs} run(s) done, daily entry limit reached.')
            return None
        if self.found(frame, 'notice_limit'):
            st['limit'], st['nt'] = True, -9.0
            self.log(f'  {label}: the entry-limit notice is showing - the daily runs are used up.')
            return None
        scale_of = self.scale_of
        # 1. dead: Revive window
        rv = self.found(frame, 'revive_btn')
        if rv is not None:
            st['died'] = True
            st['wait_until'] = now + 3.0
            if now - st.get('rt', -9) > 2.0:
                acc = self.found(frame, 'accept_revive')
                if acc is not None and self.btn_active(acc, scale_of('accept_revive')):
                    if self.click_tpl('accept_revive', frame, 'Accept Revive (it is available)'):
                        st['rt'] = now
                elif self.click_tpl('revive_btn', frame, 'Revive (never Revive on spot)'):
                    st['rt'] = now
            return None
        # 2. inside the dungeon: Open
        op = self.found(frame, 'valley_open')
        if op is not None:
            if now - st.get('ot', -9) > 3.0:
                if st.get('opens', 0) >= 8:
                    return ('fail', f'{label}: pressed Open 8 times but the character did not die')
                if self.click_tpl('valley_open', frame, 'Open (inside the Valley of Light)'):
                    st['ot'], st['opens'] = now, st.get('opens', 0) + 1
                    st['wait_until'] = now + 150
            return None
        # 3. entry dialog of the dungeon
        en = self.found(frame, 'valley_enter')
        if en is not None:
            if now - st.get('et', -9) > 3.0:
                if st.get('enters', 0) >= 8:
                    return ('fail', f'{label}: pressed Enter 8 times but the dungeon did not start')
                if self.click_tpl('valley_enter', frame, 'Enter (the Valley of Light dungeon, single player)'):
                    st['et'], st['enters'] = now, st.get('enters', 0) + 1
                    st['wait_until'] = now + 20
            return None
        # 4. Priest dialogs
        o2 = self.found(frame, 'valley_opt2')
        if o2 is not None:
            if now - st.get('o2t', -9) > 2.5 and self.click_tpl('valley_opt2', frame, 'Enter Valley Light (Party 3+)'):
                st['o2t'] = now
                st['wait_until'] = now + 15
            return None
        o1 = self.found(frame, 'valley_opt1')
        if o1 is not None:
            if now - st.get('o1t', -9) > 2.5 and self.click_tpl('valley_opt1', frame, 'Enter Valley of Light (Priest dialog)'):
                st['o1t'] = now
                st['wait_until'] = now + 10
            return None
        # 5. the map list
        pr = self.found(frame, 'valley_priest')
        if pr is not None:
            ft = getattr(self, 'frame_t', now)
            if st.get('sph') == 'busy' and (st.get('sfin') is None or ft < st['sfin'] + 0.5):
                return None                                    # this picture was taken while the list was still moving - wait for a fresh one
            st['sph'] = 'idle'
            if now - st.get('pt', -9) > 8.0 and ft - st.get('pt', -9) > 2.0 and self.click_tpl('valley_priest', frame, 'Priest (Event) in the map list'):
                st['pt'], st['wait_until'], st['map_until'] = now, now + 40, 0
                st['walks'] = st.get('walks', 0) + 1
            return None
        if now < st.get('wait_until', 0):
            if st.get('pt') and now - st['pt'] > 6 and self.map_open():
                if st.get('walks', 0) >= 6:
                    return ('fail', f'{label}: clicking Priest (Event) in the map did not make the character walk')
                st['wait_until'] = 0                           # the click did not take - the map is still open: look again
            else:
                return None
        # the map is open but Priest (Event) is not in view: scroll the list (watching whether it really moves)
        if self.map_open():
            return self.map_scroll(st, frame, now, label)
        st['sph'], st['warm'] = 'idle', False
        # 6. nothing of the above: back in town (or at the start) -> next run
        if st.get('died'):
            if self.found(frame, 'icon_privileges') or self.found(frame, 'icon_shop') or self.found(frame, 'icon_perks'):
                if now - st.get('rt', now) > 1.5:
                    st['runs'] = runs = runs + 1
                    st['died'] = False
                    st.pop('walks', None)
                    st.pop('mpress', None)
                    self.log(f'  {label}: run {runs} finished (revived).')
            return None
        if runs >= VALLEY_MAX_RUNS:
            return ('ok', f'{label}: {runs} runs done (safety limit reached).')
        if self.found(frame, 'back_arrow'):
            if el > 20:
                return ('fail', f'{label}: a menu screen is open - could not start')
            return None
        if not any(self.found(frame, n) for n in ('icon_privileges', 'icon_shop', 'icon_perks')):
            if el > 60:
                return ('fail', f'{label}: the main page is not showing')
            return None
        if st.get('mpress', 0) >= 6:
            return ('fail', f'{label}: the map did not open after 6 presses of M')
        self.key_async('m', 'KeyM', 77, 'M (open the map)')
        st['mpress'] = st.get('mpress', 0) + 1
        st['wait_until'] = now + 2.5
        return None

    def st_open(self, step, st, frame, el):
        """Click a left-menu entry (and make sure the screen changed)."""
        name, now = step['find'], time.monotonic()
        if self.found(frame, 'dragon_pack'):
            self.dismiss_click(st, 'Dragon Pack advert')
            return None
        if st['ph'] == 'start':
            if step.get('selected_ok') and st['clicks'] >= 1 and now - st['tc'] > 1.0 and self.found(frame, 'back_arrow') and self.found(frame, name) is None:
                return ('ok', f'{step.get("label", name)}: opened (its button now looks selected).')
            if step.get('already') and el >= 0.2 and self.found(frame, 'back_arrow') and (self.gold_tile(frame) if step['already'] == 'shop_goldpack' else self.found(frame, step['already'])):
                return ('ok', f'{step.get("label", name)}: already showing.')   # e.g. Shop opens on Daily Limit
            mpt = self.found(frame, name)
            if mpt is not None:
                prev, st['mpt'] = st.get('mpt'), mpt
                if el < 0.5 or prev is None or abs(prev[0] - mpt[0]) > 6 or abs(prev[1] - mpt[1]) > 6:
                    return None                               # the menu slides in - press it only when it sits still
                st['before'] = frame
                if self.click_tpl(name, frame, step.get('label', name)):
                    st['ph'], st['tc'] = 'wait', now
                    st['clicks'] += 1
            elif step.get('fallback') and el > 3.0 and st['clicks'] == 0 and self.found(frame, 'back_arrow'):
                st['before'] = frame                          # inside a menu screen only (back arrow showing): use the tab's fixed place
                if self.click_frac(step['fallback'], f'{step.get("label", name)} (picture not matched; using its fixed place)'):
                    st['ph'], st['tc'] = 'wait', now
                    st['clicks'] += 1
            elif el > 10:
                return ('fail', f'{step.get("label", name)} was not found on screen')
            return None
        if now - st['tc'] < 0.45:
            return None
        if self.changed(st.get('before'), frame) or st['clicks'] >= 2:
            return 'next'
        st['ph'] = 'start'        # nothing changed: it may have missed - click once more
        return None

    def st_tapfrac(self, step, st, frame, el):
        """Press a fixed place of the screen (a menu icon with no picture of its own), then wait until the expected picture shows.
        'at' = (x, y) as fractions of the game view; 'at_h' = (x, y) with x as a fraction of the view HEIGHT (for things pinned to the
        left edge, so the place does not move when the window gets wider)."""
        now, label = time.monotonic(), step.get('label', 'a screen')
        exp = step.get('expect')
        if st['ph'] == 'start':
            if el < 0.4:
                return None
            if self.found(frame, 'dragon_pack'):
                self.dismiss_click(st, 'Dragon Pack advert')
                return None
            if exp and self.found(frame, exp) and st['clicks'] == 0 and step.get('skip_if_open'):
                return ('ok', f'{label}: already open.')
            if st['clicks'] >= 3:
                return ('fail', f'{label}: the screen did not open after 3 presses')
            fh, fw = frame.shape
            if step.get('at_h'):
                xh, y = step['at_h']
                pt = (min(.98, xh * fh / fw), y)
            else:
                pt = step['at']
            if self.click_frac(pt, label):
                st['clicks'] += 1
                st['ph'], st['tc'] = 'wait', now
            return None
        if now - st['tc'] < step.get('wait', 1.0):
            return None
        if exp is None or self.found(frame, exp):
            return ('ok', f'{label}: opened.')
        if now - st['tc'] > 3.5:
            st['ph'] = 'start'
        return None

    def st_claim(self, step, st, frame, el):
        """Click a Claim / Check-in button when it is there, then close the reward pop-up."""
        name, now = step['find'], time.monotonic()
        label = step.get('label', name)
        if st['ph'] == 'start':
            if el < 0.25:
                return None                                # let the screen settle
            if self.found(frame, 'dragon_pack'):
                self.dismiss_click(st, 'Dragon Pack advert')
                return None
            if self.found(frame, name):
                st['ref'] = self.frame_mean(frame)
                if self.click_tpl(name, frame, label):
                    st['clicks'] += 1
                    st['ph'], st['tc'], st['dismiss'] = 'after', now, 0
                return None
            if step.get('claimed') and self.locate(frame, step['claimed'])[0] >= .70:
                return ('skip', f'{label}: already claimed today.')
            if el > step.get('wait', 3.0):
                return ('skip', f'{label}: nothing to claim (already claimed or not available).')
            return None
        # phase 'after': a pop-up (animation) may be showing; tap outside it until it is gone
        if now - st['tc'] < 0.5:
            return None
        why = self.popup_why(frame, st.get('ref'))
        if why:
            st.pop('pclear', None)
            if self.tap_away(st, label, why):
                if why.startswith('screen dimmed') and not self.found(frame, name):
                    return ('ok', f'{label}: claimed (the button is gone; the screen only looked dim).')
                return ('fail', f'{label}: a pop-up would not close ({why})')
            return None
        st.setdefault('pclear', now)
        if now - st['pclear'] < 0.6:
            return None
        if self.found(frame, name):
            if st['clicks'] < 2:
                st['ph'], st['t0'] = 'start', now - 0.25
                st.pop('pclear', None)
                return None
            if step.get('soft'):
                return ('ok', f'{label}: clicked (button still visible - timed reward?).')
            return ('fail', f'{label}: the button is still there after 2 clicks')
        return ('ok', f'{label}: claimed.')

    def st_dotclaim(self, step, st, frame, el):
        """Press whatever carries a red dot inside a region (e.g. the check-in milestone chests), then close the reward pop-up.
        Only dotted items are pressed, so nothing else in the region is touched."""
        now, label = time.monotonic(), step.get('label', 'red dot')
        if st['ph'] == 'start':
            if el < 0.5:
                return None
            if self.found(frame, 'dragon_pack'):
                self.dismiss_click(st, 'Dragon Pack advert')
                return None
            bgr = self.cur_bgr
            dots = self.find_red_dots(bgr, step['dot_region'], step.get('dot_area', (300, 3200))) if bgr is not None else []
            if not dots:
                if el > step.get('wait', 1.0):
                    return ('skip', f'{label}: nothing to claim (no red dot).')
                return None
            h, w = frame.shape[:2]
            ox, oy = step.get('dot_offset', (0.0, 0.0))
            x, y = (dots[0][0] + ox) * w, (dots[0][1] + oy) * h
            st['ref'] = self.frame_mean(frame)
            if self.click(self.to_logical((x, y), frame), label):
                st['clicks'] += 1
                st['ph'], st['tc'], st['dismiss'] = 'after', now, 0
            return None
        if now - st['tc'] < 0.5:
            return None
        why = self.popup_why(frame, st.get('ref'))
        if why:
            st.pop('pclear', None)
            if self.tap_away(st, label, why):
                return ('fail', f'{label}: a pop-up would not close ({why})')
            return None
        st.setdefault('pclear', now)
        if now - st['pclear'] < 0.6:
            return None
        return ('ok', f'{label}: claimed.')

    def st_shop_free(self, step, st, frame, el):
        """Buy the free Gold Pack. Never presses Purchase unless the dialog shows the Gold Pack.
        The tile is only pressed once it has stopped moving (the shop animates in), and pressed again if the
        purchase dialog does not appear."""
        now = time.monotonic()
        if st['ph'] == 'start':
            if self.found(frame, 'dragon_pack'):
                self.dismiss_click(st, 'Dragon Pack advert')
                return None
            pt = self.gold_tile(frame) if self.found(frame, 'back_arrow') else None   # never on the game map
            if pt is not None:
                prev, st['tile_pt'] = st.get('tile_pt'), pt
                stable = prev is not None and abs(prev[0] - pt[0]) < 6 and abs(prev[1] - pt[1]) < 6
                if el < 0.7 or not stable:
                    return None                                # wait until the tile sits still
                st['ref'] = self.frame_mean(frame)
                if self.click_tpl('shop_goldpack', frame, 'the Gold Pack'):
                    st['ph'], st['tc'] = 'dialog', now
                    st['presses'] = st.get('presses', 0) + 1
                return None
            st.pop('tile_pt', None)
            # The tile is not showing: the Shop may be on another tab (it remembers the last one). Press Daily Limit.
            if self.found(frame, 'back_arrow') and now - st.get('mtc', -99.0) > 1.6 and st.get('mclicks', 0) < 1 and el > 0.8:
                mpt = self.found(frame, 'menu_daily_limit')
                if mpt is not None:
                    prev, st['mpt'] = st.get('mpt'), mpt
                    if prev is not None and abs(prev[0] - mpt[0]) < 6 and abs(prev[1] - mpt[1]) < 6:
                        if self.click_tpl('menu_daily_limit', frame, 'Daily Limit menu (checking the right tab is open)'):
                            st['mtc'], st['mclicks'] = now, st.get('mclicks', 0) + 1
                    return None
            if (el > 8 or (st.get('mclicks', 0) >= 1 and now - st.get('mtc', 0) > 1.6)) and (st.get('mclicks', 0) >= 1 or not self.found(frame, 'back_arrow')):
                if self.found(frame, 'back_arrow'):
                    return ('skip', 'Gold Pack: not on the Daily Limit list (already bought today?).')
                return ('fail', 'Gold Pack: the Shop is not showing')
            return None
        if st['ph'] == 'dialog':
            if now - st['tc'] < 0.3:
                return None
            buy = self.found(frame, 'purchase_btn')
            if buy:
                if not self.found(frame, 'gold_tooltip'):
                    st.setdefault('buy_seen', now)             # the Gold Pack title fades in a moment after the button
                    if now - st['buy_seen'] < 3.0:
                        return None
                    self.dismiss_click(st, 'purchase dialog')
                    return ('fail', 'safety stop - the purchase dialog is not the free Gold Pack, nothing was bought')
                if self.click_tpl('purchase_btn', frame, 'Purchase (free Gold Pack)'):
                    st['ph'], st['tc'], st['dismiss'] = 'after', now, 0
                return None
            if now - st['tc'] > 3.0:
                if st['presses'] < 3:
                    self.log(f'  Gold Pack: no purchase dialog yet - pressing the Gold Pack again ({st["presses"] + 1} of 3).')
                    st['ph'] = 'start'
                    st.pop('tile_pt', None)
                    return None
                return ('fail', 'Gold Pack: the purchase dialog did not appear after 3 presses')
            return None
        # phase 'after'
        if now - st['tc'] < 0.5:
            return None
        why = self.popup_why(frame, st.get('ref')) or ('purchase dialog' if self.found(frame, 'purchase_btn') else None)
        if why:
            st.pop('pclear', None)
            if self.tap_away(st, 'Gold Pack', why):
                if why.startswith('screen dimmed'):
                    return ('ok', 'Gold Pack: bought (free) (the screen only looked dim).')
                return ('fail', f'Gold Pack: a pop-up would not close ({why})')
            return None
        st.setdefault('pclear', now)
        if now - st['pclear'] < 0.6:
            return None
        return ('ok', 'Gold Pack: bought (free).')

    # ----------------------------------------------------------------- auto run
    def auto_check(self):
        """Every 30 s: when a schedule's day and time have come, clear that account's marks (once a day), then collect."""
        if self.running:
            return
        if self.page_loaded_at is None or time.monotonic() - self.page_loaded_at < 25:
            return
        now = datetime.now()
        today = date.today().isoformat()
        for i, sc in enumerate(self.schedules):
            if not sc.get('on'):
                continue
            days = sc.get('days') or [True] * 7
            if not days[now.weekday()]:
                continue
            if now.hour * 60 + now.minute < int(sc.get('h', 8)) * 60 + int(sc.get('m', 10)):
                continue
            acct = sc.get('acct') if sc.get('acct') in self.acct_names() else (self.acct_names()[0] if self.acct_names() else None)
            if acct is None:
                continue
            seq = sc.get('seq', 'all')
            key = f'{today}#{sc.get("id", i)}'
            f = self.fired.get(key)
            if f is None:                                  # first time today: the scheduled "reset"
                self.reset_marks(acct, seq)
                f = self.fired[key] = {'n': 0, 'last': 0.0}
                self.log(f'Schedule {i + 1} ({acct}): {int(sc.get("h", 8)):02d}:{int(sc.get("m", 10)):02d} reached - progress cleared, collecting again.')
                self.refresh_tasks()
                self.update_badge()
            pending = self.pending_tasks(seq, acct)
            if not pending:
                self.save_settings()
                continue
            if f['n'] >= 3 or (f['n'] > 0 and time.monotonic() - f['last'] < 600):
                continue
            f['n'] += 1
            f['last'] = time.monotonic()
            self.log(f'Schedule {i + 1} ({acct}): starting (try {f["n"]} of 3).')
            if not self.start(pending, auto=True, acct=acct):
                f['n'] = 3
            self.save_settings()
            return

    # -------------------------------------------------------------- diagnostics
    def diagnose(self):
        if self.running or self.analysing:
            self.log('Stop the run before diagnosing.')
            return
        frame = self.snapshot()
        if frame is None:
            self.log('Diagnostic: browser screenshot unavailable.')
            return
        bgr = self.snap_bgr
        self.log(f'Diagnostic: game view {frame.shape[1]} x {frame.shape[0]} (this takes a few seconds)...')
        self.analysing = True

        def work():
            try:
                self.cur_bgr = bgr
                self.region_override = {}
                for name in sorted(REGIONS):
                    score, pt, scale = self.locate_raw(frame, name)
                    self.log_signal.emit(f'  {name}: {score:.2f} / {THRESH.get(name, DEFAULT_THRESH):.2f}  at {pt}  scale {scale}')
                self.log_signal.emit('Diagnostic finished.')
            finally:
                self.analysing = False
        threading.Thread(target=work, daemon=True).start()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
