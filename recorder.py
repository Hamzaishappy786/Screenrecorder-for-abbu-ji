import tkinter as tk
from tkinter import filedialog, messagebox
import subprocess
import threading
import os
import sys
import time
import tempfile
import ctypes
from ctypes import wintypes

try:
    import keyboard
    HAS_KEYBOARD = True
except ImportError:
    HAS_KEYBOARD = False

try:
    import pynput.mouse as mouse_module
    HAS_PYNPUT = True
except ImportError:
    HAS_PYNPUT = False


# ═════════════════════════════════════════════════════════
#  Asset path helper (works both as .py and compiled .exe)
# ═════════════════════════════════════════════════════════
def _asset(name):
    base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)


# ═════════════════════════════════════════════════════════
#  Win32 plumbing
# ═════════════════════════════════════════════════════════
user32   = ctypes.WinDLL('user32',   use_last_error=True)
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)

LRESULT = ctypes.c_ssize_t
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT,
                              wintypes.WPARAM, wintypes.LPARAM)

WS_POPUP          = 0x80000000
WS_CHILD          = 0x40000000
WS_VISIBLE        = 0x10000000
WS_EX_TOPMOST     = 0x00000008
WS_EX_LAYERED     = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW  = 0x00000080
WS_EX_NOACTIVATE  = 0x08000000
LWA_ALPHA         = 0x02
SW_HIDE           = 0
SW_SHOWNA         = 8
HWND_TOPMOST      = wintypes.HWND(-1)
SWP_NOMOVE        = 0x0002
SWP_NOSIZE        = 0x0001
SWP_NOACTIVATE    = 0x0010
PM_REMOVE         = 0x0001
MW_FILTERMODE_EXCLUDE = 0
WDA_EXCLUDEFROMCAPTURE = 0x11   # Win10 2004+: hide window from screen capture


class WNDCLASSEXW(ctypes.Structure):
    _fields_ = [
        ('cbSize',        wintypes.UINT),
        ('style',         wintypes.UINT),
        ('lpfnWndProc',   WNDPROC),
        ('cbClsExtra',    ctypes.c_int),
        ('cbWndExtra',    ctypes.c_int),
        ('hInstance',     wintypes.HINSTANCE),
        ('hIcon',         wintypes.HICON),
        ('hCursor',       wintypes.HANDLE),
        ('hbrBackground', wintypes.HBRUSH),
        ('lpszMenuName',  wintypes.LPCWSTR),
        ('lpszClassName', wintypes.LPCWSTR),
        ('hIconSm',       wintypes.HICON),
    ]


class MAGTRANSFORM(ctypes.Structure):
    _fields_ = [('v', (ctypes.c_float * 3) * 3)]


def _bind_win32():
    user32.DefWindowProcW.restype  = LRESULT
    user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT,
                                      wintypes.WPARAM, wintypes.LPARAM]
    user32.RegisterClassExW.restype  = wintypes.ATOM
    user32.RegisterClassExW.argtypes = [ctypes.POINTER(WNDCLASSEXW)]
    user32.CreateWindowExW.restype  = wintypes.HWND
    user32.CreateWindowExW.argtypes = [
        wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
        ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
        wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID,
    ]
    user32.SetLayeredWindowAttributes.argtypes = [
        wintypes.HWND, wintypes.COLORREF, ctypes.c_byte, wintypes.DWORD]
    user32.SetWindowPos.argtypes = [
        wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
        ctypes.c_int, ctypes.c_int, wintypes.UINT]
    user32.ShowWindow.argtypes    = [wintypes.HWND, ctypes.c_int]
    user32.DestroyWindow.argtypes = [wintypes.HWND]
    user32.PeekMessageW.argtypes  = [ctypes.POINTER(wintypes.MSG), wintypes.HWND,
                                     wintypes.UINT, wintypes.UINT, wintypes.UINT]
    kernel32.GetModuleHandleW.restype  = wintypes.HMODULE
    kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]


_bind_win32()


# ═════════════════════════════════════════════════════════
#  Full-screen cursor-anchored zoom (Magnification API)
# ═════════════════════════════════════════════════════════
class ScreenZoom:
    STEP = 0.25
    MIN  = 1.0
    MAX  = 6.0
    CLASS_NAME = 'AbbuJiZoomHost'

    def __init__(self):
        self._want    = self.MIN
        self._lock    = threading.Lock()
        self._running = True
        self._ok      = False
        self._err     = None
        self._wndproc = None

        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

        deadline = time.time() + 2.0
        while time.time() < deadline and self._ok is False and self._err is None:
            time.sleep(0.02)

    @property
    def available(self):
        return self._ok

    def zoom_in(self):
        with self._lock:
            self._want = min(self.MAX, self._want + self.STEP)

    def zoom_out(self):
        with self._lock:
            self._want = max(self.MIN, self._want - self.STEP)

    def reset(self):
        with self._lock:
            self._want = self.MIN

    def cleanup(self):
        self.reset()
        self._running = False
        if self._thread.is_alive():
            self._thread.join(timeout=1.5)

    def _run(self):
        try:
            mag = ctypes.WinDLL('Magnification.dll')
        except OSError as e:
            self._err = str(e)
            return

        mag.MagInitialize.restype  = wintypes.BOOL
        mag.MagUninitialize.restype = wintypes.BOOL
        mag.MagSetWindowSource.restype  = wintypes.BOOL
        mag.MagSetWindowSource.argtypes = [wintypes.HWND, wintypes.RECT]
        mag.MagSetWindowTransform.restype  = wintypes.BOOL
        mag.MagSetWindowTransform.argtypes = [wintypes.HWND,
                                              ctypes.POINTER(MAGTRANSFORM)]
        mag.MagSetWindowFilterList.restype  = wintypes.BOOL
        mag.MagSetWindowFilterList.argtypes = [wintypes.HWND, ctypes.c_int,
                                               ctypes.c_int,
                                               ctypes.POINTER(wintypes.HWND)]

        if not mag.MagInitialize():
            self._err = 'MagInitialize failed'
            return

        hinst = kernel32.GetModuleHandleW(None)
        self._wndproc = WNDPROC(user32.DefWindowProcW)

        wc = WNDCLASSEXW()
        wc.cbSize        = ctypes.sizeof(WNDCLASSEXW)
        wc.lpfnWndProc   = self._wndproc
        wc.hInstance     = hinst
        wc.lpszClassName = self.CLASS_NAME
        user32.RegisterClassExW(ctypes.byref(wc))

        sw = user32.GetSystemMetrics(0)
        sh = user32.GetSystemMetrics(1)

        host = user32.CreateWindowExW(
            WS_EX_TOPMOST | WS_EX_LAYERED | WS_EX_TRANSPARENT
            | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE,
            self.CLASS_NAME, 'Zoom', WS_POPUP,
            0, 0, sw, sh, None, None, hinst, None)

        if not host:
            self._err = 'Overlay window creation failed'
            mag.MagUninitialize()
            return

        user32.SetLayeredWindowAttributes(host, 0, 255, LWA_ALPHA)

        magwin = user32.CreateWindowExW(
            0, 'Magnifier', 'MagnifierControl', WS_CHILD | WS_VISIBLE,
            0, 0, sw, sh, host, None, hinst, None)

        if not magwin:
            self._err = 'Magnifier control creation failed'
            user32.DestroyWindow(host)
            mag.MagUninitialize()
            return

        excl = (wintypes.HWND * 1)(host)
        mag.MagSetWindowFilterList(magwin, MW_FILTERMODE_EXCLUDE, 1, excl)

        self._ok = True

        applied = self.MIN
        visible = False
        pt  = wintypes.POINT()
        msg = wintypes.MSG()

        try:
            while self._running:
                while user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, PM_REMOVE):
                    user32.TranslateMessage(ctypes.byref(msg))
                    user32.DispatchMessageW(ctypes.byref(msg))

                with self._lock:
                    want = self._want

                if abs(want - applied) > 1e-6:
                    applied = want
                    mt = MAGTRANSFORM()
                    mt.v[0][0] = applied
                    mt.v[1][1] = applied
                    mt.v[2][2] = 1.0
                    mag.MagSetWindowTransform(magwin, ctypes.byref(mt))

                    should_show = applied > self.MIN + 1e-6
                    if should_show and not visible:
                        user32.ShowWindow(host, SW_SHOWNA)
                        visible = True
                    elif not should_show and visible:
                        user32.ShowWindow(host, SW_HIDE)
                        visible = False

                if visible:
                    user32.GetCursorPos(ctypes.byref(pt))
                    inv = 1.0 / applied
                    src = wintypes.RECT()
                    src.left   = int(pt.x * (1.0 - inv))
                    src.top    = int(pt.y * (1.0 - inv))
                    src.right  = src.left + int(sw * inv)
                    src.bottom = src.top  + int(sh * inv)
                    mag.MagSetWindowSource(magwin, src)
                    user32.SetWindowPos(host, HWND_TOPMOST, 0, 0, 0, 0,
                                        SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)
                    time.sleep(0.033)   # 30 fps while zoomed — light on old CPUs
                else:
                    time.sleep(0.1)     # idle: negligible CPU
        finally:
            try:
                user32.ShowWindow(host, SW_HIDE)
                user32.DestroyWindow(host)
                mag.MagUninitialize()
            except Exception:
                pass


# ═════════════════════════════════════════════════════════
#  Floating red dot — top-right of screen while recording
# ═════════════════════════════════════════════════════════
class RecordingDot:
    SIZE = 26

    def __init__(self, root):
        self.root = root
        self.win  = None
        self._dot = None
        self._canvas = None
        self._on  = True

    def show(self):
        if self.win:
            return
        s = self.SIZE
        self.win = tk.Toplevel(self.root)
        self.win.overrideredirect(True)
        self.win.attributes('-topmost', True)
        self.win.attributes('-transparentcolor', '#0d1117')

        sw = self.win.winfo_screenwidth()
        self.win.geometry(f'{s}x{s}+{sw - s - 14}+{12}')

        self._canvas = tk.Canvas(self.win, width=s, height=s,
                                 bg='#0d1117', highlightthickness=0)
        self._canvas.pack()
        self._dot = self._canvas.create_oval(4, 4, s - 4, s - 4,
                                             fill='#f85149', outline='')

        # Hide the dot from the recording itself (Win10 2004+; harmless if it fails)
        try:
            self.win.update_idletasks()
            hwnd = user32.GetParent(self.win.winfo_id())
            user32.SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE)
        except Exception:
            pass

    def blink(self):
        if not self.win:
            return
        self._on = not self._on
        self._canvas.itemconfig(self._dot,
                                fill='#f85149' if self._on else '#5a1d1d')

    def hide(self):
        if self.win:
            try:
                self.win.destroy()
            except Exception:
                pass
            self.win = None


# ═════════════════════════════════════════════════════════
#  Custom "Save Ho Gaya" dialog with clickable path
# ═════════════════════════════════════════════════════════
class SaveDialog:
    BG     = '#0d1117'
    BORDER = '#21262d'
    TEXT   = '#e6edf3'
    MUTED  = '#7d8590'
    GREEN  = '#2ea043'
    BLUE   = '#58a6ff'

    def __init__(self, root, save_path, size_mb):
        self.win = tk.Toplevel(root)
        self.win.title('Save Ho Gaya')
        self.win.configure(bg=self.BG)
        self.win.resizable(False, False)
        self.win.grab_set()
        self.win.attributes('-topmost', True)

        W, H = 540, 300
        sx = root.winfo_screenwidth()
        sy = root.winfo_screenheight()
        self.win.geometry(f'{W}x{H}+{(sx-W)//2}+{(sy-H)//2}')

        tk.Frame(self.win, bg=self.GREEN, height=5).pack(fill='x')

        body = tk.Frame(self.win, bg=self.BG)
        body.pack(fill='both', expand=True, padx=30, pady=(20, 0))

        top = tk.Frame(body, bg=self.BG)
        top.pack(fill='x')
        tk.Label(top, text='✅', font=('Segoe UI', 28),
                 bg=self.BG).pack(side='left', padx=(0, 12))
        tk.Label(top, text='Video Save Ho Gayi!',
                 font=('Segoe UI', 17, 'bold'),
                 fg=self.TEXT, bg=self.BG).pack(side='left', anchor='w')

        tk.Frame(body, bg=self.BORDER, height=1).pack(fill='x', pady=14)

        tk.Label(body, text=f'File Size:  {size_mb:.1f} MB',
                 font=('Segoe UI', 11), fg=self.MUTED,
                 bg=self.BG).pack(anchor='w')

        tk.Label(body, text='', bg=self.BG).pack()

        path_row = tk.Frame(body, bg=self.BG)
        path_row.pack(anchor='w', fill='x')

        tk.Label(path_row, text='  ➤ ', font=('Segoe UI', 13, 'bold'),
                 fg=self.BLUE, bg=self.BG).pack(side='left')

        folder  = os.path.dirname(save_path)
        fname   = os.path.basename(save_path)
        display = (fname[:52] + '…') if len(fname) > 55 else fname

        link = tk.Label(path_row, text=display,
                        font=('Segoe UI', 11, 'underline'),
                        fg=self.BLUE, bg=self.BG, cursor='hand2')
        link.pack(side='left')
        link.bind('<Button-1>', lambda _: os.startfile(folder))

        tk.Label(path_row, text='  (click karein — folder khulega)',
                 font=('Segoe UI', 9, 'italic'),
                 fg='#484f58', bg=self.BG).pack(side='left')

        btn_row = tk.Frame(self.win, bg=self.BG)
        btn_row.pack(fill='x', padx=30, pady=20)

        tk.Button(btn_row, text='  Theek Hai  ',
                  font=('Segoe UI', 11, 'bold'),
                  bg=self.GREEN, fg='white',
                  activebackground='#238636',
                  relief='flat', padx=12, pady=8,
                  cursor='hand2',
                  command=self.win.destroy).pack(side='right')

        self.win.wait_window()


# ═════════════════════════════════════════════════════════
#  Rounded button widget
# ═════════════════════════════════════════════════════════
def _round_rect(canvas, x1, y1, x2, y2, r, **kw):
    pts = [x1+r, y1, x2-r, y1, x2, y1, x2, y1+r,
           x2, y2-r, x2, y2, x2-r, y2, x1+r, y2,
           x1, y2, x1, y2-r, x1, y1+r, x1, y1]
    return canvas.create_polygon(pts, smooth=True, **kw)


class RoundButton(tk.Canvas):
    def __init__(self, parent, text, fill, hover, command=None,
                 width=600, height=82, radius=20,
                 font=('Segoe UI', 18, 'bold'), fg='#ffffff'):
        super().__init__(parent, width=width, height=height,
                         bg=parent['bg'], highlightthickness=0, bd=0)
        self._fill, self._hover, self._fg = fill, hover, fg
        self._command = command
        self._enabled = True
        self._shape = _round_rect(self, 2, 2, width-2, height-2,
                                  radius, fill=fill, outline='')
        self._text = self.create_text(width // 2, height // 2,
                                      text=text, fill=fg, font=font)
        self.bind('<Enter>',    self._enter)
        self.bind('<Leave>',    self._leave)
        self.bind('<Button-1>', self._click)
        self.configure(cursor='hand2')

    def _enter(self, _):
        if self._enabled:
            self.itemconfig(self._shape, fill=self._hover)

    def _leave(self, _):
        if self._enabled:
            self.itemconfig(self._shape, fill=self._fill)

    def _click(self, _):
        if self._enabled and self._command:
            self._command()

    def set_enabled(self, enabled):
        self._enabled = enabled
        if enabled:
            self.itemconfig(self._shape, fill=self._fill)
            self.itemconfig(self._text,  fill=self._fg)
            self.configure(cursor='hand2')
        else:
            self.itemconfig(self._shape, fill='#21262d')
            self.itemconfig(self._text,  fill='#484f58')
            self.configure(cursor='arrow')


# ═════════════════════════════════════════════════════════
#  Main application
# ═════════════════════════════════════════════════════════
class RecorderApp:
    BG      = '#0d1117'
    CARD    = '#161b22'
    BORDER  = '#21262d'
    TEXT    = '#e6edf3'
    MUTED   = '#7d8590'
    GREEN   = '#238636'
    GREEN_H = '#2ea043'
    RED     = '#b62324'
    RED_H   = '#da3633'
    ACCENT  = '#58a6ff'
    LIVE    = '#f85149'

    def __init__(self, root):
        self.root = root
        self.root.title('Screen Recorder')
        self.root.resizable(False, False)
        self.root.configure(bg=self.BG)
        self.root.state('zoomed')   # start maximized

        ico = _asset('me-holding-a-pic.ico')
        if os.path.exists(ico):
            try:
                self.root.iconbitmap(ico)
            except Exception:
                pass

        self.recording  = False
        self.proc       = None
        self.tmp        = None
        self.start_ts   = None
        self._blink     = False
        self._mouse_listener = None

        self.zoom = ScreenZoom()
        self.dot_overlay = RecordingDot(root)

        self._build_ui()
        self._setup_hotkeys()
        self._tick()

    # ── layout ───────────────────────────────────────────
    def _build_ui(self):
        outer = tk.Frame(self.root, bg=self.BG)
        outer.pack(fill='both', expand=True)
        outer.grid_rowconfigure(0, weight=1)
        outer.grid_columnconfigure(0, weight=1)
        root = tk.Frame(outer, bg=self.BG)
        root.grid(row=0, column=0, sticky='')

        # ── header ──
        header = tk.Frame(root, bg=self.BG)
        header.pack(fill='x', pady=(38, 0))

        tk.Label(header, text='●  REC', font=('Segoe UI', 13, 'bold'),
                 fg=self.LIVE, bg=self.BG).pack()
        tk.Label(header, text='Screen Recorder',
                 font=('Segoe UI', 34, 'bold'),
                 fg=self.TEXT, bg=self.BG).pack(pady=(6, 0))
        tk.Label(header, text='Custom made screen recorder for just my family',
                 font=('Segoe UI', 13), fg=self.MUTED, bg=self.BG).pack(pady=(8, 0))

        # ── status card ──
        card = tk.Frame(root, bg=self.CARD, highlightbackground=self.BORDER,
                        highlightthickness=1)
        card.pack(fill='x', padx=54, pady=(34, 0))

        inner = tk.Frame(card, bg=self.CARD)
        inner.pack(pady=(26, 0))

        self.dot = tk.Canvas(inner, width=20, height=20, bg=self.CARD,
                             highlightthickness=0)
        self.dot_id = self.dot.create_oval(4, 4, 17, 17,
                                           fill=self.GREEN_H, outline='')
        self.dot.pack(side='left', padx=(0, 14))

        self.status_var = tk.StringVar(value='Tayyar hai')
        tk.Label(inner, textvariable=self.status_var,
                 font=('Segoe UI', 19, 'bold'),
                 fg=self.TEXT, bg=self.CARD).pack(side='left')

        self.timer_var = tk.StringVar(value='00:00')
        self.timer_lbl = tk.Label(card, textvariable=self.timer_var,
                                  font=('Consolas', 46, 'bold'),
                                  fg=self.MUTED, bg=self.CARD)
        self.timer_lbl.pack(pady=(6, 26))

        # ── buttons ──
        btns = tk.Frame(root, bg=self.BG)
        btns.pack(pady=(32, 0))

        self.btn_start = RoundButton(
            btns, '●   Recording Shuru Karo',
            self.GREEN, self.GREEN_H, command=self.start_recording)
        self.btn_start.pack(pady=(0, 16))

        self.btn_stop = RoundButton(
            btns, '■   Roko aur Save Karo',
            self.RED, self.RED_H, command=self.stop_recording)
        self.btn_stop.pack()
        self.btn_stop.set_enabled(False)

        # ── tips ──
        tips = tk.Frame(root, bg=self.CARD, highlightbackground=self.BORDER,
                        highlightthickness=1)
        tips.pack(fill='x', padx=54, pady=(32, 0))

        tk.Label(tips, text='ZOOM KAISE KAREIN',
                 font=('Segoe UI', 11, 'bold'), fg=self.ACCENT,
                 bg=self.CARD).pack(pady=(18, 12))

        for line in (
            'Alt + X dabaye rakhein  +  scroll UPAR   →   Zoom In',
            'Alt + X dabaye rakhein  +  scroll NEECHE →   Zoom Out',
            'Alt + 0   →   Zoom bilkul normal',
        ):
            tk.Label(tips, text=line, font=('Segoe UI', 12),
                     fg=self.MUTED, bg=self.CARD).pack(pady=4)

        self.zoom_note = tk.Label(tips, text='', font=('Segoe UI', 11),
                                  fg=self.MUTED, bg=self.CARD)
        self.zoom_note.pack(pady=(12, 18))

        if not self.zoom.available:
            self.zoom_note.config(
                text='⚠  Zoom is system par kaam nahi kar raha', fg=self.LIVE)
        elif not (HAS_KEYBOARD and HAS_PYNPUT):
            self.zoom_note.config(
                text='⚠  keyboard + pynput install karein zoom ke liye',
                fg=self.LIVE)

    # ── timer + blinking dots ────────────────────────────
    def _tick(self):
        if self.recording and self.start_ts:
            secs = int(time.time() - self.start_ts)
            self.timer_var.set(f'{secs // 60:02d}:{secs % 60:02d}')
            self._blink = not self._blink
            self.dot.itemconfig(self.dot_id,
                                fill=self.LIVE if self._blink else self.CARD)
            self.dot_overlay.blink()
        self.root.after(500, self._tick)

    # ── recording ────────────────────────────────────────
    def _ffmpeg(self):
        bundled = _asset(os.path.join('ffmpeg', 'ffmpeg.exe'))
        return bundled if os.path.exists(bundled) else 'ffmpeg'

    def start_recording(self):
        if self.recording:
            return

        self.tmp = tempfile.mktemp(suffix='.mp4')
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()

        # Tuned for weak CPUs: 15 fps, ultrafast x264, zerolatency
        cmd = [
            self._ffmpeg(), '-y',
            '-f', 'gdigrab',
            '-framerate', '15',
            '-video_size', f'{sw}x{sh}',
            '-i', 'desktop',
            '-c:v', 'libx264',
            '-preset', 'ultrafast',
            '-tune', 'zerolatency',
            '-crf', '28',
            '-pix_fmt', 'yuv420p',
            self.tmp,
        ]

        try:
            self.proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW)
        except FileNotFoundError:
            messagebox.showerror(
                'FFmpeg Nahi Mila',
                'ffmpeg\\ffmpeg.exe is folder mein rakhein.\n\n'
                'ffmpeg.org se Windows build download karein.')
            return

        self.recording = True
        self.start_ts  = time.time()
        self.status_var.set('Recording ho rahi hai')
        self.timer_lbl.config(fg=self.TEXT)
        self.timer_var.set('00:00')
        self.btn_start.set_enabled(False)
        self.btn_stop.set_enabled(True)
        self.dot_overlay.show()
        self.root.after(400, self.root.iconify)

    def stop_recording(self):
        if not self.recording:
            return

        if self.proc:
            try:
                self.proc.stdin.write(b'q')
                self.proc.stdin.flush()
            except Exception:
                self.proc.terminate()
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.proc.kill()
            self.proc = None

        self.recording = False
        self.start_ts  = None
        self.zoom.reset()
        self.dot_overlay.hide()

        self.root.deiconify()
        self.root.lift()
        self.status_var.set('Tayyar hai')
        self.dot.itemconfig(self.dot_id, fill=self.GREEN_H)
        self.timer_lbl.config(fg=self.MUTED)
        self.timer_var.set('00:00')
        self.btn_start.set_enabled(True)
        self.btn_stop.set_enabled(False)

        save_path = filedialog.asksaveasfilename(
            title='Video Kahan Save Karein?',
            defaultextension='.mp4',
            filetypes=[('MP4 Video', '*.mp4')],
            initialfile=f"recording_{time.strftime('%Y-%m-%d_%H-%M')}.mp4")

        if save_path and self.tmp and os.path.exists(self.tmp):
            try:
                os.replace(self.tmp, save_path)
                size_mb = os.path.getsize(save_path) / (1024 * 1024)
                SaveDialog(self.root, save_path, size_mb)
            except Exception as e:
                messagebox.showerror('Error', str(e))
        elif self.tmp and os.path.exists(self.tmp):
            os.remove(self.tmp)
        self.tmp = None

    # ── hotkeys ──────────────────────────────────────────
    def _setup_hotkeys(self):
        if not (HAS_KEYBOARD and HAS_PYNPUT and self.zoom.available):
            return

        def on_scroll(x, y, dx, dy):
            try:
                if keyboard.is_pressed('alt') and keyboard.is_pressed('x'):
                    if dy > 0:
                        self.zoom.zoom_in()
                    elif dy < 0:
                        self.zoom.zoom_out()
            except Exception:
                pass

        self._mouse_listener = mouse_module.Listener(on_scroll=on_scroll)
        self._mouse_listener.daemon = True
        self._mouse_listener.start()

        try:
            keyboard.add_hotkey('alt+0', self.zoom.reset)
        except Exception:
            pass

    # ── shutdown ─────────────────────────────────────────
    def on_close(self):
        if self.recording:
            self.stop_recording()
        self.zoom.cleanup()
        self.dot_overlay.hide()
        if self._mouse_listener:
            try:
                self._mouse_listener.stop()
            except Exception:
                pass
        self.root.destroy()


# ═════════════════════════════════════════════════════════
#  Entry point
# ═════════════════════════════════════════════════════════
def main():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            user32.SetProcessDPIAware()
        except Exception:
            pass

    root = tk.Tk()
    app = RecorderApp(root)
    root.protocol('WM_DELETE_WINDOW', app.on_close)
    root.mainloop()


if __name__ == '__main__':
    main()
