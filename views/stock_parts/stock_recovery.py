import os
import sys
import shutil
from datetime import date, datetime
import tkinter as tk
from tkinter import ttk, messagebox

# --- THE FIX: Bulletproof Executable Pathing ---
if getattr(sys, 'frozen', False):
    ROOT_DIR = os.path.dirname(sys.executable)
else:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parts_dir = os.path.dirname(current_dir)
    ROOT_DIR = os.path.dirname(parts_dir)

if ROOT_DIR not in sys.path: 
    sys.path.insert(0, ROOT_DIR)
# -----------------------------------------------

def get_db_path():
    import database
    return database.DB_PATH 

def run_silent_backup(stock_view):
    db_path = get_db_path()
    if not os.path.exists(db_path): return
    
    backup_dir = os.path.join(os.path.dirname(db_path), "backups")
    if not os.path.exists(backup_dir): os.makedirs(backup_dir)
    
    today_str = date.today().strftime("%Y-%m-%d")
    backup_file = os.path.join(backup_dir, f"backup_{today_str}.db")
    
    # Take a silent snapshot if one doesn't exist for today
    if not os.path.exists(backup_file):
        try: shutil.copy2(db_path, backup_file)
        except: pass
    
    # The Janitor: 7-Day Rolling Vault cleanup
    try:
        for f in os.listdir(backup_dir):
            if f.startswith("backup_") and f.endswith(".db"):
                date_str = f.replace("backup_", "").replace(".db", "")
                b_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                if (date.today() - b_date).days > 7:
                    os.remove(os.path.join(backup_dir, f))
    except: pass

def open_recovery_popup(stock_view):
    popup = tk.Toplevel(stock_view)
    popup.title("Data Recovery (Time Machine)")
    popup.configure(bg=stock_view.BG)
    popup.grab_set()
    
    popup.update_idletasks()
    w, h = 550, 420
    sw, sh = popup.winfo_screenwidth(), popup.winfo_screenheight()
    popup.geometry(f"{w}x{h}+{int((sw/2)-(w/2))}+{int((sh/2)-(h/2))}")

    tk.Label(popup, text="🚑 Safe Harbor Recovery", font=("Arial", 16, "bold"), bg=stock_view.BG, fg=stock_view.DANGER).pack(pady=(20, 5))
    tk.Label(popup, text="Restore your database to a previous day's snapshot.\nWarning: All changes made after the selected date will be wiped out.", font=("Arial", 10), bg=stock_view.BG, fg=stock_view.SEC_FG).pack(pady=(0, 20))

    frame = tk.Frame(popup, bg=stock_view.CARD, highlightbackground=stock_view.BORDER, highlightthickness=1)
    frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))

    db_path = get_db_path()
    backup_dir = os.path.join(os.path.dirname(db_path), "backups")
    
    backups = []
    if os.path.exists(backup_dir):
        for f in os.listdir(backup_dir):
            if f.startswith("backup_") and f.endswith(".db"):
                date_str = f.replace("backup_", "").replace(".db", "")
                backups.append((date_str, os.path.join(backup_dir, f)))
    
    backups.sort(key=lambda x: x[0], reverse=True)

    if not backups:
        tk.Label(frame, text="No backups found in the vault.", font=("Arial", 11, "bold"), bg=stock_view.CARD, fg=stock_view.SEC_FG).pack(pady=40)
        return

    lb = tk.Listbox(frame, font=("Arial", 11), bg=stock_view.BG, fg=stock_view.FG, selectbackground=stock_view.BLUE, highlightthickness=0, cursor="hand2")
    lb.pack(fill="both", expand=True, padx=10, pady=10)
    
    for b in backups:
        lb.insert(tk.END, f"  Snapshot Created: {b[0]}")

    def restore_snapshot():
        # --- THE FIX: Hard-block DB replacement to protect multi-company architecture ---
        messagebox.showerror(
            "Feature Disabled", 
            "CRITICAL WARNING: The Time Machine feature is disabled in Multi-Company mode.\n\nRestoring a database snapshot directly from the UI would overwrite and erase data for ALL companies sharing this application.\n\nTo restore a backup, your system administrator must manually replace the database file.", 
            parent=popup
        )
        return
        # --------------------------------------------------------------------------------

    btn = tk.Button(popup, text="⏱️ Restore Selected Snapshot", font=("Arial", 11, "bold"), bg=stock_view.DANGER, fg="#ffffff", relief="flat", cursor="hand2", pady=8, command=restore_snapshot)
    btn.pack(fill="x", padx=20, pady=(0, 20))
    
    # Keyboard Supremacy
    popup.bind("<Escape>", lambda e: popup.destroy())
    popup.bind("<Control-Return>", lambda e: restore_snapshot())