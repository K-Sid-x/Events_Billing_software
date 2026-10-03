import tkinter as tk
from tkinter import ttk, messagebox
import datetime
import os
import sys

# --- THE FIX: Bulletproof Executable Pathing ---
if getattr(sys, 'frozen', False):
    ROOT_DIR = os.path.dirname(sys.executable)
else:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parts_dir = os.path.dirname(current_dir)
    ROOT_DIR = os.path.dirname(parts_dir)

if ROOT_DIR not in sys.path: sys.path.append(ROOT_DIR)
# -----------------------------------------------

import database

def open_attendance_window(parent_view):
    t = parent_view.colors
    pop = tk.Toplevel(parent_view)
    pop.title("📅 Mark Daily Attendance")
    pop.geometry("750x700")
    pop.configure(bg=t["bg"])
    pop.grab_set()

    # Center the window
    pop.update_idletasks()
    sw = pop.winfo_screenwidth(); sh = pop.winfo_screenheight()
    x = int((sw/2) - (750/2)); y = int((sh/2) - (700/2))
    pop.geometry(f"+{max(0,x)}+{max(0,y)}")

    # Top Header & Date Picker
    header_f = tk.Frame(pop, bg=t["bg"])
    header_f.pack(fill="x", padx=20, pady=(20, 10))
    
    tk.Label(header_f, text="Daily Hajira & Headcount", font=("Segoe UI", 16, "bold"), bg=t["bg"], fg=t["text"]).pack(side="left")
    
    date_f = tk.Frame(header_f, bg=t["bg"])
    date_f.pack(side="right")
    tk.Label(date_f, text="Date:", font=("Segoe UI", 11, "bold"), bg=t["bg"], fg=t["text_sec"]).pack(side="left", padx=(0, 5))
    
    date_var = tk.StringVar(value=datetime.date.today().strftime("%Y-%m-%d"))
    date_ent = tk.Entry(date_f, textvariable=date_var, font=("Segoe UI", 11), width=12, bg=t["card"], fg=t["text"], insertbackground=t["text"], justify="center")
    date_ent.pack(side="left", ipady=3)

    # Bottom Save Button Area
    bottom_f = tk.Frame(pop, bg=t["bg"])
    bottom_f.pack(side="bottom", fill="x")
    tk.Frame(bottom_f, bg=t["border"], height=1).pack(fill="x", padx=20, pady=(10, 10))
    
    # Scrollable Container for Workers
    container = tk.Frame(pop, bg=t["card"], highlightbackground=t["border"], highlightthickness=1)
    container.pack(fill="both", expand=True, padx=20, pady=(0, 10))
    
    style = ttk.Style(pop)
    style.theme_use("default") # --- THE FIX: Unlock Custom Thick Scrollbars ---
    
    # --- THE FIX: Thick Dark Scrollbar for Attendance Canvas ---
    style.configure("Att.Vertical.TScrollbar", background=t["text_sec"], troughcolor=t["bg"], bordercolor=t["bg"], arrowcolor=t["text"], relief="flat")
    style.map("Att.Vertical.TScrollbar", background=[("active", t["accent_blue"])])
    # -----------------------------------------------------------
    
    canvas = tk.Canvas(container, bg=t["card"], highlightthickness=0)
    scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview, style="Att.Vertical.TScrollbar")
    main_f = tk.Frame(canvas, bg=t["card"])
    
    main_f.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas_window = canvas.create_window((0, 0), window=main_f, anchor="nw")
    canvas.bind("<Configure>", lambda e: canvas.itemconfig(canvas_window, width=e.width))

    canvas.configure(yscrollcommand=scrollbar.set)
    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")
    
    def _on_mousewheel(event):
        mult = int(-1*(event.delta/120)*2) if os.name == 'nt' else int(-1*event.delta)
        canvas.yview_scroll(mult, "units")
    canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", _on_mousewheel))
    canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))

    # Load Workers
    raw_labours = database.get_all_labours()

    attendance_data = [] # Will hold dicts of Tkinter variables for saving later

    if not raw_labours:
        tk.Label(main_f, text="No workers found. Add some workers first.", font=("Arial", 11, "italic"), bg=t["card"], fg=t["text_sec"]).pack(pady=30)
    else:
        # Header Row
        row_hdr = tk.Frame(main_f, bg=t["border"])
        row_hdr.pack(fill="x")
        tk.Label(row_hdr, text="NAME / PROFILE", font=("Segoe UI", 10, "bold"), bg=t["border"], fg=t["text"], width=30, anchor="w").pack(side="left", padx=(15, 10), pady=6)
        tk.Label(row_hdr, text="ATTENDANCE LOG", font=("Segoe UI", 10, "bold"), bg=t["border"], fg=t["text"]).pack(side="left", pady=6)
        
        def create_counter(parent_frame, label, var, step, min_val=0.0):
            wrap = tk.Frame(parent_frame, bg=t["bg"], highlightbackground=t["border"], highlightthickness=1)
            wrap.pack(side="left", padx=5)
            tk.Label(wrap, text=label, font=("Arial", 9, "bold"), bg=t["bg"], fg=t["text_sec"]).pack(side="left", padx=(8, 2))
            
            def dec():
                try: 
                    new_val = float(var.get()) - step
                    var.set(max(min_val, new_val))
                except: var.set(min_val)
                
            def inc():
                try: var.set(float(var.get()) + step)
                except: var.set(min_val)

            tk.Button(wrap, text="➖", font=("Arial", 8), bg=t["card"], fg=t["text"], relief="flat", cursor="hand2", command=dec, width=2).pack(side="left")
            ent = tk.Entry(wrap, textvariable=var, font=("Arial", 11, "bold"), width=5, justify="center", bg=t["card"], fg=t["accent_blue"], bd=0, highlightthickness=0)
            ent.pack(side="left", ipady=3)
            tk.Button(wrap, text="➕", font=("Arial", 8), bg=t["card"], fg=t["text"], relief="flat", cursor="hand2", command=inc, width=2).pack(side="left")

        for idx, l in enumerate(raw_labours):
            # --- THE FIX: Use secure dictionary helper instead of raw PRAGMA schema! ---
            l_dict = database.get_labour_dict(l[0])
            if not l_dict: continue
            # ---------------------------------------------------------------------------
            l_id = l_dict['id']
            name = str(l_dict.get('name', ''))
            
            bg_col = t["card"] if idx % 2 == 0 else t["bg"]
            
            row = tk.Frame(main_f, bg=bg_col)
            row.pack(fill="x")
            
            # Name & Type Column
            name_f = tk.Frame(row, bg=bg_col, width=250)
            name_f.pack(side="left", fill="y", padx=(15, 10), pady=12)
            name_f.pack_propagate(False)
            tk.Label(name_f, text=name, font=("Segoe UI", 12, "bold"), bg=bg_col, fg=t["text"], anchor="w").pack(fill="x")
            tk.Label(name_f, text="👤 Individual", font=("Arial", 9), bg=bg_col, fg=t["text_sec"], anchor="w").pack(fill="x")
            
            # Counter Column
            count_f = tk.Frame(row, bg=bg_col)
            count_f.pack(side="left", fill="y", pady=12)
            
            entry_data = {'id': l_id}
            
            hajira_var = tk.DoubleVar(value=1.0) 
            create_counter(count_f, "Hajira / Shift", hajira_var, step=0.5, min_val=0.0)
            entry_data['hajira'] = hajira_var
                
            attendance_data.append(entry_data)

    def save_attendance():
        att_date = date_var.get().strip()
        if not att_date:
            messagebox.showerror("Error", "Please enter a valid date.", parent=pop)
            return
            
        saved_count = 0
        skipped_count = 0
        for data in attendance_data:
            l_id = data['id']
            
            # --- THE FIX: Check for existing attendance to prevent double-wages! ---
            if database.check_labour_attendance_exists(l_id, att_date):
                skipped_count += 1
                continue
            # -----------------------------------------------------------------------
            
            try:
                # --- THE FIX: Eradicate the "Database Hammer" PRAGMA loop ---
                w_dict = database.get_labour_dict(l_id)
                if not w_dict: continue
                # ------------------------------------------------------------
                
                h_val = float(data['hajira'].get())
                if h_val > 0.0:
                    database.add_labour_attendance(l_id, att_date, h_val, 0.0, 0.0, "")
                    wage_amt = h_val * float(w_dict.get('daily_rate', 0.0))
                    if wage_amt > 0:
                        database.add_labour_ledger_entry(l_id, att_date, 'Wage', wage_amt, f"Auto-Wage: {h_val} Hajira")
                    saved_count += 1
            except Exception as e:
                print(f"Failed saving for worker {l_id}: {e}")

        # --- THE FIX: Report skipped duplicates so the user is aware ---
        msg = f"Attendance logged successfully for {saved_count} workers!"
        if skipped_count > 0:
            msg += f"\n\nSkipped {skipped_count} workers who already had attendance marked for {att_date}."
            
        if saved_count > 0:
            comp_id = getattr(parent_view.winfo_toplevel(), "active_company_id", 1)
            database.log_audit("Labours", "Marked Attendance", record_ref=f"{saved_count} Workers", details=f"Bulk marked attendance for {att_date}.", company_id=comp_id)
            
        messagebox.showinfo("Success", msg, parent=pop)
        # ---------------------------------------------------------------
        pop.destroy()

    tk.Button(bottom_f, text="💾 Save Attendance Log", font=("Segoe UI", 12, "bold"), bg=t["accent_green"], fg="#ffffff", relief="flat", cursor="hand2", padx=25, pady=8, command=save_attendance).pack(side="right", padx=20, pady=(0, 20))