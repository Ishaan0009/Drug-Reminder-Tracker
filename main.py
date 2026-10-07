# main.py
"""
Drug Reminder & Tracker (Light-only, smooth animations)
Save to Desktop\Drug\main.py and run.
Requires:
    pip install pillow
Optional (Windows toasts):
    pip install winotify
"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk
import sqlite3
import os
import datetime
import threading
import time
import platform

# Optional Windows toasts via winotify — uncomment if you install it
try:
    from winotify import Notification, audio
    WINOTIFY_AVAILABLE = True
except Exception:
    WINOTIFY_AVAILABLE = False

# winsound for simple audio on Windows
try:
    import winsound
except Exception:
    winsound = None

# ---------------- Config / Colors ----------------
APP_TITLE = "💊 Drug Reminder & Tracker"
DB_FILE = "drug_reminder.db"
FONT_DEFAULT = "Segoe UI"

# Light theme palette (single theme, no dark)
BG = "#F7F7FB"
PANEL = "#FFFFFF"
ACCENT = "#7C3AED"  # purple accent
TEXT = "#0F172A"
SUBTEXT = "#6B7280"
ENTRY_BG = "#FFFFFF"
ENTRY_BORDER = "#E6E6F0"
PROGRESS_BG = "#EEF2FF"

# ---------------- Database helpers ----------------
def db_connect():
    return sqlite3.connect(DB_FILE)

def init_db():
    conn = db_connect()
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS patients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        age INTEGER,
        note TEXT,
        photo TEXT,
        created_at TEXT
    )""")
    c.execute("""
    CREATE TABLE IF NOT EXISTS medicines (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id INTEGER,
        name TEXT,
        dosage TEXT,
        times TEXT,
        status TEXT DEFAULT 'Pending',
        added_date TEXT,
        FOREIGN KEY(patient_id) REFERENCES patients(id)
    )""")
    conn.commit()
    conn.close()

# ---------------- Utilities ----------------
def now_hhmm():
    return datetime.datetime.now().strftime("%H:%M")

def normalize_time(t):
    try:
        return datetime.datetime.strptime(t.strip(), "%H:%M").strftime("%H:%M")
    except Exception:
        return None

def parse_times(csv_field):
    if not csv_field:
        return []
    return [s.strip() for s in csv_field.split(",") if s.strip()]

def play_wav_if_available(filepath):
    if winsound and os.path.isfile(filepath) and platform.system().lower() == "windows":
        try:
            winsound.PlaySound(filepath, winsound.SND_FILENAME | winsound.SND_ASYNC)
        except Exception:
            pass

# ---------------- App ----------------
class DrugReminderApp:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("1200x720")
        self.root.minsize(960, 600)

        # app state
        self.current_font = FONT_DEFAULT
        self.custom_wav = None
        self.sound_on = True
        self._img_cache = {}
        self.patient_panel = None
        self.settings_panel = None
        self.sidebar_visible = True

        # init db
        init_db()

        # build UI
        self.build_ui()
        self.apply_theme()
        self.load_patients()

        # reminder loop (non-blocking)
        self.root.after(5000, self.reminder_check)

    # ---------------- UI building ----------------
    def build_ui(self):
        # top bar
        topbar = tk.Frame(self.root, bg=BG)
        topbar.pack(fill="x", padx=10, pady=8)

        # hamburger (left)
        self.menu_btn = tk.Button(topbar, text="≡", width=3, command=self.toggle_sidebar_animated, bg=PANEL)
        self.menu_btn.pack(side="left", padx=(4,12))

        # logo
        self.logo_lbl = tk.Label(topbar, text=APP_TITLE, font=(self.current_font, 16, "bold"), bg=BG, fg=ACCENT)
        self.logo_lbl.pack(side="left", anchor="w")

        # spacer
        spacer = tk.Frame(topbar, bg=BG)
        spacer.pack(side="left", expand=True, fill="x")

        # help and settings (right)
        self.help_btn = tk.Button(topbar, text="❓", width=3, command=self.show_help, bg=PANEL)
        self.help_btn.pack(side="right", padx=6)
        self.settings_btn = tk.Button(topbar, text="⚙", width=3, command=self.toggle_settings_panel_animated, bg=PANEL)
        self.settings_btn.pack(side="right", padx=6)

        # content frame (sidebar + main)
        self.content = tk.Frame(self.root, bg=BG)
        self.content.pack(fill="both", expand=True, padx=10, pady=(0,10))

        # left sidebar (patients)
        self.sidebar = tk.Frame(self.content, width=280, bg=PANEL, bd=0, relief="flat")
        self.sidebar.pack(side="left", fill="y", padx=(0,8))
        self.sidebar.pack_propagate(False)

        # sidebar header
        sb_head = tk.Frame(self.sidebar, bg=PANEL)
        sb_head.pack(fill="x", pady=(8,4), padx=8)
        tk.Label(sb_head, text="🧑‍⚕️ Patients", bg=PANEL, font=(self.current_font, 12, "bold")).pack(side="left")
        tk.Button(sb_head, text="➕", width=3, bg=PANEL, command=self.open_patient_panel_add).pack(side="right")

        # listbox
        self.patient_listbox = tk.Listbox(self.sidebar, activestyle="none", exportselection=False, bd=0, highlightthickness=0)
        self.patient_listbox.pack(fill="both", expand=True, padx=8, pady=(6,8))
        self.patient_listbox.bind("<<ListboxSelect>>", lambda e: self.on_patient_select())

        # bottom sidebar actions
        sb_bottom = tk.Frame(self.sidebar, bg=PANEL)
        sb_bottom.pack(fill="x", pady=6, padx=8)
        tk.Button(sb_bottom, text="✏️ Edit", command=self.open_patient_panel_edit, bg=PANEL).pack(side="left", expand=True, fill="x", padx=3)
        tk.Button(sb_bottom, text="🗑 Delete", command=self.delete_patient, bg=PANEL).pack(side="left", expand=True, fill="x", padx=3)

        # main area
        self.main_area = tk.Frame(self.content, bg=BG)
        self.main_area.pack(side="left", fill="both", expand=True)

        # profile card
        profile = tk.Frame(self.main_area, bg=PANEL, bd=0, relief="flat")
        profile.pack(fill="x", pady=(0,8))
        profile.configure(height=140)

        # photo container
        pf = tk.Frame(profile, width=160, height=120, bg=PANEL, bd=1, relief="solid")
        pf.pack(side="left", padx=8, pady=8)
        pf.pack_propagate(False)
        self.photo_label = tk.Label(pf, text="🖼️\nNo Photo", bg=PANEL, justify="center")
        self.photo_label.pack(fill="both", expand=True)

        # info frame
        self.info_frame = tk.Frame(profile, bg=BG)
        self.info_frame.pack(side="left", fill="x", expand=True, padx=(12,8))
        self.name_lbl = tk.Label(self.info_frame, text="Select a patient", font=(self.current_font, 16, "bold"), bg=BG, fg=TEXT)
        self.name_lbl.pack(anchor="w")
        self.age_lbl = tk.Label(self.info_frame, text="", font=(self.current_font, 10), bg=BG, fg=SUBTEXT)
        self.age_lbl.pack(anchor="w", pady=(4,0))
        self.note_lbl = tk.Label(self.info_frame, text="", font=(self.current_font, 10), bg=BG, fg=SUBTEXT, wraplength=700, justify="left")
        self.note_lbl.pack(anchor="w", pady=(4,0))

        # action buttons
        actions = tk.Frame(profile, bg=PANEL)
        actions.pack(side="right", padx=8, pady=8)
        tk.Button(actions, text="✅ Mark Taken", bg="#2ea24f", fg="white", command=lambda: self.change_status_selected("Taken")).pack(fill="x", pady=4)
        tk.Button(actions, text="❌ Mark Missed", bg="#e04b4b", fg="white", command=lambda: self.change_status_selected("Missed")).pack(fill="x", pady=4)

        # medicine form
        medform = tk.Frame(self.main_area, bg=BG)
        medform.pack(fill="x", pady=(0,8), padx=(0,6))
        tk.Label(medform, text="💊 Medicine name", bg=BG, fg=TEXT).grid(row=0, column=0, sticky="w")
        tk.Label(medform, text="⚖️ Dosage (opt)", bg=BG, fg=TEXT).grid(row=0, column=1, sticky="w")
        tk.Label(medform, text="⏰ Times (HH:MM, comma separated)", bg=BG, fg=TEXT).grid(row=0, column=2, sticky="w")
        self.med_name_e = tk.Entry(medform, bg=ENTRY_BG, bd=1, relief="solid")
        self.med_name_e.grid(row=1, column=0, sticky="ew", padx=6, pady=6)
        self.med_dos_e = tk.Entry(medform, bg=ENTRY_BG, bd=1, relief="solid")
        self.med_dos_e.grid(row=1, column=1, sticky="ew", padx=6, pady=6)
        self.med_times_e = tk.Entry(medform, bg=ENTRY_BG, bd=1, relief="solid")
        self.med_times_e.grid(row=1, column=2, sticky="ew", padx=6, pady=6)
        medform.columnconfigure(0, weight=2)
        medform.columnconfigure(1, weight=1)
        medform.columnconfigure(2, weight=2)
        tk.Button(medform, text="➕ Add Medicine", bg=ACCENT, fg="white", command=self.add_medicine).grid(row=1, column=3, padx=(8,0))

        # progress and canvas
        prog = tk.Frame(self.main_area, bg=BG)
        prog.pack(fill="x", pady=(0,8))
        self.progress_label = tk.Label(prog, text="Progress — 0/0 (0%)", bg=BG, fg=TEXT)
        self.progress_label.pack(side="left")
        self.prog_canvas = tk.Canvas(prog, width=56, height=56, bg=BG, highlightthickness=0)
        self.prog_canvas.pack(side="right")

        # table area
        table_frame = tk.Frame(self.main_area, bg=PANEL, bd=0)
        table_frame.pack(fill="both", expand=True)
        cols = ("id","name","dosage","time","status","added")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings", selectmode="extended")
        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscroll=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        for c,w in zip(cols,(60,360,120,110,100,130)):
            self.tree.heading(c, text=c.capitalize())
            self.tree.column(c, width=w, anchor="center")

        # bottom actions
        bottom_actions = tk.Frame(self.main_area, bg=BG)
        bottom_actions.pack(fill="x", pady=(8,0))
        tk.Button(bottom_actions, text="🗑 Delete Selected", command=self.delete_selected_meds).pack(side="left", padx=6)

        # placeholders
        self.patient_ids = []
        self.settings_widgets = {}

    # ---------------- Theme apply (single light theme) ----------------
    def apply_theme(self):
        self.root.configure(bg=BG)
        # Treeview styling
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", font=(self.current_font, 10), rowheight=26)
        style.configure("Treeview.Heading", font=(self.current_font, 10, "bold"), background=ACCENT, foreground="white")
        style.map("Treeview", background=[("selected", ACCENT)])
        # status tags
        self.tree.tag_configure("Pending", background=PANEL, foreground=TEXT)
        self.tree.tag_configure("Taken", background="#DCFCE7", foreground="#065f46")
        self.tree.tag_configure("Missed", background="#FFE6E6", foreground="#7f1d1d")
        # update input styles
        for entry in (self.med_name_e, self.med_dos_e, self.med_times_e):
            entry.configure(bg=ENTRY_BG, fg=TEXT, insertbackground=TEXT, highlightbackground=ENTRY_BORDER, highlightthickness=1)

    # ---------------- Sidebar animation (smooth) ----------------
    def toggle_sidebar_animated(self):
        # animate collapse/expand of left sidebar smoothly
        if self.sidebar_visible:
            # slide left to hide: gradually reduce width
            def step(w):
                if w <= 0:
                    self.sidebar.pack_forget()
                    self.sidebar_visible = False
                    return
                self.sidebar.config(width=w)
                self.root.after(8, lambda: step(w-20))
            step(self.sidebar.winfo_width())
        else:
            # show then expand width
            self.sidebar.pack(side="left", fill="y", padx=(0,8))
            self.sidebar_visible = True
            start = 0
            target = 280
            self.sidebar.config(width=start)
            def step(w):
                if w >= target:
                    self.sidebar.config(width=target)
                    return
                self.sidebar.config(width=w)
                self.root.after(8, lambda: step(w+20))
            step(start)

    # ---------------- Settings panel (smooth slide in/out from right) ----------------
    def toggle_settings_panel_animated(self):
        if self.settings_panel and self.settings_panel.winfo_exists():
            # slide out and destroy
            self.slide_out_right(self.settings_panel, destroy_after=True)
            self.settings_panel = None
            return
        # create settings panel off-screen to right
        w = 360
        h = self.root.winfo_height() - 140
        root_x = self.root.winfo_rootx()
        root_w = self.root.winfo_width()
        start_x = root_x + root_w
        y = 80
        self.settings_panel = tk.Toplevel(self.root)
        self.settings_panel.overrideredirect(True)
        self.settings_panel.attributes("-topmost", True)
        self.settings_panel.geometry(f"{w}x{h}+{start_x}+{y}")
        # content
        frame = tk.Frame(self.settings_panel, bg=PANEL)
        frame.pack(fill="both", expand=True)
        tk.Label(frame, text="⚙ Settings", font=(self.current_font, 14, "bold"), bg=PANEL).pack(anchor="w", padx=12, pady=(12,8))
        # Sound switch and WAV upload
        sf = tk.Frame(frame, bg=PANEL)
        sf.pack(fill="x", padx=12, pady=6)
        self.sound_var = tk.BooleanVar(value=self.sound_on)
        tk.Checkbutton(sf, text="🔔 Sound notifications", variable=self.sound_var, bg=PANEL, command=self.on_sound_toggle).pack(anchor="w")
        tk.Button(frame, text="🎵 Upload WAV (optional)", command=self.select_wav).pack(anchor="w", padx=12, pady=(6,4))
        self.wav_lbl = tk.Label(frame, text=f"Current: {os.path.basename(self.custom_wav) if self.custom_wav else 'Default'}", bg=PANEL)
        self.wav_lbl.pack(anchor="w", padx=12, pady=(0,6))
        # Font selector
        tk.Label(frame, text="🔤 Font", bg=PANEL).pack(anchor="w", padx=12, pady=(6,0))
        self.font_var = tk.StringVar(value=self.current_font)
        fonts = (FONT_DEFAULT, "Arial", "Tahoma", "Calibri")
        self.font_combo = ttk.Combobox(frame, values=fonts, textvariable=self.font_var, state="readonly")
        self.font_combo.pack(anchor="w", padx=12, pady=(4,6))
        self.font_combo.bind("<<ComboboxSelected>>", lambda e: self.change_font(self.font_var.get()))
        tk.Button(frame, text="Close", command=self.toggle_settings_panel_animated).pack(side="bottom", pady=12, padx=12, fill="x")
        # slide in from right
        end_x = root_x + root_w - w - 10
        self.slide_in_from_right(self.settings_panel, start_x, end_x, y)

    # slide helpers
    def slide_in_from_right(self, toplevel, start_x, end_x, y, step=24, delay=10):
        # move leftwards until end_x
        def move(x):
            if x <= end_x:
                toplevel.geometry(f"+{end_x}+{y}")
                return
            toplevel.geometry(f"+{x}+{y}")
            toplevel.after(delay, lambda: move(x-step))
        move(start_x)

    def slide_out_right(self, toplevel, destroy_after=False, step=24, delay=10):
        # slide to right off-screen and optionally destroy
        try:
            geom = toplevel.geometry()
            # geometry like "360x560+100+100"
            parts = geom.split("+")
            if len(parts) >= 2:
                curr_x = int(parts[1])
            else:
                curr_x = toplevel.winfo_x()
            root_x = self.root.winfo_rootx()
            root_w = self.root.winfo_width()
            target = root_x + root_w + 20
        except Exception:
            try:
                curr_x = toplevel.winfo_x()
                target = self.root.winfo_rootx() + self.root.winfo_width() + 20
            except Exception:
                curr_x = 0
                target = 10000

        def move(x):
            if x >= target:
                if destroy_after:
                    try:
                        toplevel.destroy()
                    except Exception:
                        pass
                return
            try:
                toplevel.geometry(f"+{x}+{toplevel.winfo_y()}")
            except Exception:
                pass
            toplevel.after(delay, lambda: move(x+step))
        move(curr_x)

    # ---------------- Patient panel (left slide-in, smooth) ----------------
    def open_patient_panel_add(self):
        self.show_patient_panel(mode="add")

    def open_patient_panel_edit(self):
        sel = self.patient_listbox.curselection()
        if not sel:
            messagebox.showwarning("Select", "Select a patient to edit.")
            return
        idx = sel[0]
        pid = self.patient_ids[idx]
        self.show_patient_panel(mode="edit", pid=pid)

    def show_patient_panel(self, mode="add", pid=None):
        # if panel exists, destroy first
        if self.patient_panel and self.patient_panel.winfo_exists():
            try:
                self.patient_panel.destroy()
            except Exception:
                pass
            self.patient_panel = None

        # create panel off-left
        w = 420
        h = self.root.winfo_height() - 120
        root_x = self.root.winfo_rootx()
        start_x = root_x - w - 20
        y = 80
        # use Toplevel to allow absolute placement
        self.patient_panel = tk.Toplevel(self.root)
        self.patient_panel.overrideredirect(True)
        self.patient_panel.attributes("-topmost", True)
        self.patient_panel.geometry(f"{w}x{h}+{start_x}+{y}")
        frame = tk.Frame(self.patient_panel, bg=PANEL, bd=2, relief="solid")
        frame.pack(fill="both", expand=True)

        title = "➕ Add Patient" if mode == "add" else "✏️ Edit Patient"
        tk.Label(frame, text=title, font=(self.current_font, 14, "bold"), bg=PANEL).pack(anchor="w", padx=12, pady=(12,8))

        frm = tk.Frame(frame, bg=PANEL)
        frm.pack(fill="both", expand=True, padx=12, pady=6)

        tk.Label(frm, text="Name", bg=PANEL).grid(row=0, column=0, sticky="w")
        name_e = tk.Entry(frm, bg=ENTRY_BG)
        name_e.grid(row=0, column=1, sticky="ew", pady=6)

        tk.Label(frm, text="Age", bg=PANEL).grid(row=1, column=0, sticky="w")
        age_e = tk.Entry(frm, bg=ENTRY_BG)
        age_e.grid(row=1, column=1, sticky="ew", pady=6)

        tk.Label(frm, text="Note", bg=PANEL).grid(row=2, column=0, sticky="w")
        note_e = tk.Entry(frm, bg=ENTRY_BG)
        note_e.grid(row=2, column=1, sticky="ew", pady=6)

        photo_var = tk.StringVar()
        tk.Label(frm, text="Photo (choose)", bg=PANEL).grid(row=3, column=0, sticky="w")
        tk.Button(frm, text="Choose...", command=lambda: photo_var.set(filedialog.askopenfilename(filetypes=[("Images","*.png;*.jpg;*.jpeg;*.gif")]))).grid(row=3, column=1, sticky="w")
        frm.columnconfigure(1, weight=1)

        # prefill if edit
        if mode == "edit" and pid:
            conn = db_connect(); c = conn.cursor()
            c.execute("SELECT name, age, note, photo FROM patients WHERE id=?", (pid,))
            row = c.fetchone(); conn.close()
            if row:
                n,a,no,ph = row
                if n: name_e.insert(0, n)
                if a: age_e.insert(0, str(a))
                if no: note_e.insert(0, no)
                if ph: photo_var.set(ph)

        btns = tk.Frame(frame, bg=PANEL)
        btns.pack(fill="x", pady=10, padx=12)

        def do_save():
            n = name_e.get().strip()
            if not n:
                messagebox.showwarning("Missing", "Enter patient name")
                return
            a = age_e.get().strip()
            no = note_e.get().strip()
            ph = photo_var.get().strip() or None
            conn = db_connect(); c = conn.cursor()
            if mode == "add":
                c.execute("INSERT INTO patients (name, age, note, photo, created_at) VALUES (?, ?, ?, ?, ?)",
                          (n, int(a) if a.isdigit() else None, no, ph, datetime.date.today().isoformat()))
                new_id = c.lastrowid
            else:
                c.execute("UPDATE patients SET name=?, age=?, note=?, photo=? WHERE id=?", (n, int(a) if a.isdigit() else None, no, ph, pid))
                new_id = pid
            conn.commit(); conn.close()
            # close panel and refresh
            try:
                self.patient_panel.destroy()
            except Exception:
                pass
            self.patient_panel = None
            self.load_patients()
            self.select_patient_by_id(new_id)

        tk.Button(btns, text="✅ Done", bg=ACCENT, fg="white", command=do_save).pack(side="left", padx=6)
        tk.Button(btns, text="Close", command=lambda: (self.patient_panel.destroy(), setattr(self, "patient_panel", None))).pack(side="left", padx=6)

        # slide in from left to x= root_x + 8
        end_x = root_x + 8
        self.slide_in_from_left(self.patient_panel, start_x, end_x, y)

    def slide_in_from_left(self, toplevel, start_x, end_x, y, step=24, delay=8):
        def move(x):
            if x >= end_x:
                toplevel.geometry(f"+{end_x}+{y}")
                return
            toplevel.geometry(f"+{x}+{y}")
            toplevel.after(delay, lambda: move(x+step))
        move(start_x)

    # ---------------- Patients CRUD ----------------
    def load_patients(self):
        conn = db_connect(); c = conn.cursor()
        c.execute("SELECT id, name, age FROM patients ORDER BY id DESC")
        rows = c.fetchall(); conn.close()
        self.patient_ids = []
        self.patient_listbox.delete(0, "end")
        for r in rows:
            pid, name, age = r
            self.patient_ids.append(pid)
            display = f"{name} — {age or ''}"
            self.patient_listbox.insert("end", display)

    def select_patient_by_id(self, pid):
        if not hasattr(self, "patient_ids"):
            return
        try:
            idx = self.patient_ids.index(pid)
            self.patient_listbox.selection_clear(0, "end")
            self.patient_listbox.selection_set(idx)
            self.patient_listbox.see(idx)
            self.on_patient_select()
        except Exception:
            pass

    def on_patient_select(self):
        sel = self.patient_listbox.curselection()
        if not sel:
            self.clear_patient_display()
            return
        pid = self.patient_ids[sel[0]]
        self.show_patient(pid)

    def show_patient(self, pid):
        conn = db_connect(); c = conn.cursor()
        c.execute("SELECT name, age, note, photo FROM patients WHERE id=?", (pid,))
        row = c.fetchone(); conn.close()
        if not row:
            self.clear_patient_display()
            return
        name, age, note, photo = row
        self.name_lbl.config(text=f"👤 {name}")
        self.age_lbl.config(text=f"🧾 Age: {age}" if age else "🧾 Age: —")
        self.note_lbl.config(text=f"📝 {note}" if note else "")
        # image preview
        if photo and os.path.isfile(photo):
            try:
                img = Image.open(photo).convert("RGBA")
                img.thumbnail((150,150), Image.LANCZOS)
                tkimg = ImageTk.PhotoImage(img)
                self._img_cache['photo'] = tkimg
                self.photo_label.config(image=tkimg, text="")
            except Exception:
                self.photo_label.config(image="", text="🖼️ No Photo")
        else:
            self.photo_label.config(image="", text="🖼️ No Photo")
        # load medicines
        self.load_medicines(pid)

    def clear_patient_display(self):
        self.name_lbl.config(text="Select a patient")
        self.age_lbl.config(text="")
        self.note_lbl.config(text="")
        self.photo_label.config(image="", text="🖼️ No Photo")
        self.clear_medicines()
        self.update_progress(0,0)

    def delete_patient(self):
        sel = self.patient_listbox.curselection()
        if not sel:
            messagebox.showwarning("Select", "Select a patient first")
            return
        idx = sel[0]; pid = self.patient_ids[idx]
        if not messagebox.askyesno("Confirm", "Delete patient and all medicines?"):
            return
        conn = db_connect(); c = conn.cursor()
        c.execute("DELETE FROM medicines WHERE patient_id=?", (pid,))
        c.execute("DELETE FROM patients WHERE id=?", (pid,))
        conn.commit(); conn.close()
        self.load_patients()
        self.clear_patient_display()

    # ---------------- Medicines ----------------
    def add_medicine(self):
        sel = self.patient_listbox.curselection()
        if not sel:
            messagebox.showwarning("Select", "Select a patient first")
            return
        pid = self.patient_ids[sel[0]]
        name = self.med_name_e.get().strip()
        dosage = self.med_dos_e.get().strip()
        times_raw = self.med_times_e.get().strip()
        if not name or not times_raw:
            messagebox.showwarning("Missing", "Enter medicine name and times (HH:MM comma separated)")
            return
        times = []
        for t in times_raw.split(","):
            nt = normalize_time(t)
            if not nt:
                messagebox.showerror("Invalid time", f"Invalid: {t.strip()}")
                return
            times.append(nt)
        conn = db_connect(); c = conn.cursor()
        c.execute("INSERT INTO medicines (patient_id, name, dosage, times, status, added_date) VALUES (?, ?, ?, ?, ?, ?)",
                  (pid, name, dosage, ",".join(times), "Pending", datetime.date.today().isoformat()))
        conn.commit(); conn.close()
        # clear fields
        self.med_name_e.delete(0,"end"); self.med_dos_e.delete(0,"end"); self.med_times_e.delete(0,"end")
        self.load_medicines(pid)

    def load_medicines(self, pid):
        for r in self.tree.get_children():
            self.tree.delete(r)
        conn = db_connect(); c = conn.cursor()
        c.execute("SELECT id, name, dosage, times, status, added_date FROM medicines WHERE patient_id=? ORDER BY id DESC", (pid,))
        rows = c.fetchall(); conn.close()
        total = 0; taken = 0
        for row in rows:
            mid, name, dosage, times_csv, status, added = row
            times = parse_times(times_csv)
            if times:
                for t in times:
                    total += 1
                    disp = status or "Pending"
                    if disp == "Taken":
                        taken += 1
                    self.tree.insert("", "end", values=(mid, name, dosage, t, disp, added), tags=(disp,))
            else:
                total += 1
                disp = status or "Pending"
                if disp == "Taken":
                    taken += 1
                self.tree.insert("", "end", values=(mid, name, dosage, "-", disp, added), tags=(disp,))
        self.update_progress(taken, total)

    def clear_medicines(self):
        for r in self.tree.get_children():
            self.tree.delete(r)

    def change_status_selected(self, new_status):
        sels = self.tree.selection()
        if not sels:
            messagebox.showwarning("Select", "Select medicines in table")
            return
        for s in sels:
            mid = self.tree.item(s)["values"][0]
            conn = db_connect(); c = conn.cursor()
            c.execute("UPDATE medicines SET status=? WHERE id=?", (new_status, mid))
            conn.commit(); conn.close()
        sel = self.patient_listbox.curselection()
        if sel:
            self.load_medicines(self.patient_ids[sel[0]])

    def delete_selected_meds(self):
        sels = self.tree.selection()
        if not sels:
            messagebox.showwarning("Select", "Select rows")
            return
        if not messagebox.askyesno("Confirm", "Delete selected medicines?"):
            return
        for s in sels:
            mid = self.tree.item(s)["values"][0]
            conn = db_connect(); c = conn.cursor()
            c.execute("DELETE FROM medicines WHERE id=?", (mid,))
            conn.commit(); conn.close()
        sel = self.patient_listbox.curselection()
        if sel:
            self.load_medicines(self.patient_ids[sel[0]])

    # ---------------- Progress UI ----------------
    def update_progress(self, taken, total):
        pct = int((taken / total * 100) if total else 0)
        self.progress_label.config(text=f"Progress — {taken}/{total} ({pct}%)")
        self.draw_progress_circle(pct)

    def draw_progress_circle(self, pct):
        self.prog_canvas.delete("all")
        x,y,r = 28,28,20
        outline_col = "#E6E6F0"
        self.prog_canvas.create_oval(x-r, y-r, x+r, y+r, outline=outline_col, width=6)
        if pct > 0:
            extent = int(360 * pct / 100)
            self.prog_canvas.create_arc(x-r, y-r, x+r, y+r, start=90, extent=-extent, style="arc", outline=ACCENT, width=6)
        self.prog_canvas.create_text(x,y, text=f"{pct}%", fill=ACCENT, font=(self.current_font, 9, "bold"))

    # ---------------- Reminder Loop ----------------
    def reminder_check(self):
        now = now_hhmm()
        try:
            conn = db_connect(); c = conn.cursor()
            c.execute("SELECT m.id, p.name, m.name, m.times FROM medicines m JOIN patients p ON m.patient_id=p.id WHERE m.status='Pending'")
            rows = c.fetchall(); conn.close()
            for mid, pname, mname, times_csv in rows:
                for t in parse_times(times_csv):
                    if t == now:
                        # Preference: use winotify if available, else print and play sound
                        if WINOTIFY_AVAILABLE:
                            try:
                                toast = Notification(app_id="Drug Reminder",
                                                     title=f"💊 {pname}",
                                                     msg=f"Take {mname} at {t}",
                                                     duration="short")
                                toast.set_audio(audio.Reminder, loop=False)
                                toast.show()
                            except Exception:
                                print(f"Reminder (toast failed): {pname} - {mname} at {t}")
                        else:
                            print(f"Reminder: {pname} - {mname} at {t}")
                        # play sound
                        if self.sound_on:
                            if self.custom_wav:
                                threading.Thread(target=play_wav_if_available, args=(self.custom_wav,), daemon=True).start()
                            else:
                                # default beep (if possible)
                                if winsound and platform.system().lower()=="windows":
                                    try:
                                        winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
                                    except Exception:
                                        pass
                        break
        except Exception as e:
            print("Reminder error:", e)
        finally:
            # schedule next check
            self.root.after(30000, self.reminder_check)

    # ---------------- Settings helpers ----------------
    def on_sound_toggle(self):
        self.sound_on = bool(self.sound_var.get())

    def select_wav(self):
        f = filedialog.askopenfilename(filetypes=[("WAV files","*.wav")])
        if f:
            self.custom_wav = f
            if hasattr(self, "wav_lbl"):
                self.wav_lbl.config(text=f"Current: {os.path.basename(f)}")

    def change_font(self, font_name):
        self.current_font = font_name
        # apply to some prominent labels
        self.logo_lbl.config(font=(self.current_font, 16, "bold"))
        self.name_lbl.config(font=(self.current_font, 16, "bold"))
        # tree heading updated by apply_theme call
        self.apply_theme()

    # ---------------- Helpers ----------------
    def show_help(self):
        messagebox.showinfo("Help",
                            "How to use:\n"
                            "1. Add patient (➕), upload photo (optional).\n"
                            "2. Select patient, add medicines with times (HH:MM comma separated).\n"
                            "3. Toggle settings (⚙) to change sound/font or upload WAV.\n"
                            "Reminders run every 30 seconds while app is open.")

# ---------------- Run ----------------
if __name__ == "__main__":
    root = tk.Tk()
    app = DrugReminderApp(root)
    app.apply_theme()
    root.mainloop()
