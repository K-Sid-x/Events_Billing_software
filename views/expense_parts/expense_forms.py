import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
import sys
import json
import shutil
import time
import random
from datetime import date

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

import database
from views.invoice_parts.helpers import enable_copy_paste
from views.invoice_parts.calendar_widget import NativeCalendar

# Global fallbacks (Shadowed dynamically inside functions below)
BG_COLOR = "#0f172a"
CARD_BG = "#1e293b"
BORDER_COLOR = "#334155"
TEXT_PRIMARY = "#f8fafc"
TEXT_SECONDARY = "#94a3b8"
ACCENT_GREEN = "#10b981"
ACCENT_RED = "#ef4444"
ACCENT_BLUE = "#3b82f6"

def safe_smart_combo(cb_widget):
    cb_widget.bind("<Return>", lambda e: [e.widget.tk_focusNext().focus(), "break"])

def open_expense_form(parent, comp_id, date_fmt_code, rental_cats, refresh_cb, undo_cb, target_id=None, is_clone=False):
    if target_id and not is_clone:
        allowed, err_msg = database.check_expense_permission(int(target_id), action="edit", company_id=comp_id)
        if not allowed:
            messagebox.showerror("Access Denied", err_msg, parent=parent)
            return

    is_dark = database.get_ui_setting("dark_mode", "1") == "1"
    BG_COLOR = "#0f172a" if is_dark else "#e0f2fe"
    CARD_BG = "#1e293b" if is_dark else "#f0f9ff"
    BORDER_COLOR = "#334155" if is_dark else "#7dd3fc"
    TEXT_PRIMARY = "#f8fafc" if is_dark else "#0f172a"
    TEXT_SECONDARY = "#94a3b8" if is_dark else "#0284c7"
    ACCENT_GREEN = "#10b981"
    ACCENT_RED = "#ef4444"
    ACCENT_BLUE = "#3b82f6" if is_dark else "#0ea5e9"

    pop = tk.Toplevel(parent)
    pop.title("Add Expense" if not target_id or is_clone else "Edit Expense")
    
    window_width = 540
    window_height = 480 
    pop.geometry(f"{window_width}x{window_height}")
    pop.configure(bg=BG_COLOR)
    pop.update_idletasks()
    
    screen_width = pop.winfo_screenwidth()
    screen_height = pop.winfo_screenheight()
    pop.geometry(f"+{int((screen_width/2) - (window_width/2))}+{int((screen_height/2) - (window_height/2))}")
    pop.grab_set()

    # --- THE FIX: Robust Combobox and Listbox Contrast Override ---
    style = ttk.Style(pop)
    style.theme_use("default")
    pop.option_add("*TCombobox*Listbox.background", CARD_BG)
    pop.option_add("*TCombobox*Listbox.foreground", TEXT_PRIMARY)
    pop.option_add("*TCombobox*Listbox.selectBackground", ACCENT_BLUE)
    pop.option_add("*TCombobox*Listbox.selectForeground", TEXT_PRIMARY)
    
    # Required to defeat OS-level dark mode overriding on pure Tkinter Listboxes:
    pop.option_add("*Listbox.background", CARD_BG)
    pop.option_add("*Listbox.foreground", TEXT_PRIMARY)
    pop.option_add("*Listbox.selectBackground", ACCENT_BLUE)
    pop.option_add("*Listbox.selectForeground", TEXT_PRIMARY)
    
    style.configure("TCombobox", fieldbackground=BG_COLOR, background=CARD_BG, foreground=TEXT_PRIMARY, arrowcolor=TEXT_PRIMARY, bordercolor=BORDER_COLOR, lightcolor=BORDER_COLOR, darkcolor=BORDER_COLOR)
    style.map("TCombobox", fieldbackground=[("readonly", BG_COLOR)], selectbackground=[("readonly", BG_COLOR)], selectforeground=[("readonly", TEXT_PRIMARY)])

    past_titles = database.get_distinct_expense_titles()

    title_var = tk.StringVar()
    category_var = tk.StringVar(value="General")
    amount_var = tk.StringVar(value="0")
    date_var = tk.StringVar(value=date.today().strftime(date_fmt_code))
    notes_var = tk.StringVar()
    pay_method_var = tk.StringVar(value="Cash")
    status_var = tk.StringVar(value="Paid")
    receipt_path_var = tk.StringVar()

    # --- THE FIX: Static, clean payment methods ---
    all_methods = ["Cash", "UPI", "GooglePay", "PhonePe", "Debit Card", "Credit Card", "Bank Transfer", "Cheque"]

    if target_id:
        database.set_active_company(comp_id)
        r = database.get_general_expense_record(int(target_id))
        if r:
            # --- THE FIX: Dynamic Column Mapping for older databases ---
            conn = database.get_connection()
            c = conn.cursor()
            c.execute("PRAGMA table_info(general_expenses)")
            cols = [col[1] for col in c.fetchall()]
            conn.close()
            
            t_idx = cols.index("title") if "title" in cols else 2
            c_idx = cols.index("category") if "category" in cols else 3
            a_idx = cols.index("amount") if "amount" in cols else 4
            d_idx = cols.index("expense_date") if "expense_date" in cols else (cols.index("date") if "date" in cols else 1)
            n_idx = cols.index("notes") if "notes" in cols else 5
            p_idx = cols.index("pay_method") if "pay_method" in cols else 7
            s_idx = cols.index("status") if "status" in cols else 8
            rp_idx = cols.index("receipt_path") if "receipt_path" in cols else 9
            
            title_var.set(r[t_idx])
            category_var.set(r[c_idx])
            
            amt_val = r[a_idx]
            if amt_val == int(amt_val) if isinstance(amt_val, float) else False:
                amount_var.set(str(int(amt_val)))
            else:
                amount_var.set(str(amt_val))
                
            if not is_clone: date_var.set(r[d_idx])
            notes_var.set(r[n_idx] if r[n_idx] else "")
            
            try:
                pm = r[p_idx] if len(r) > p_idx and r[p_idx] else "Cash"
                if pm not in all_methods: all_methods.insert(0, pm)
                pay_method_var.set(pm)
                
                st = r[s_idx] if len(r) > s_idx and r[s_idx] else "Paid"
                status_var.set(st)
                
                rp = r[rp_idx] if len(r) > rp_idx and r[rp_idx] else ""
                receipt_path_var.set(rp)
            except: pass

    tk.Label(pop, text="Add Expense" if not target_id or is_clone else "Edit Expense", font=("Arial", 16, "bold"), bg=BG_COLOR, fg=TEXT_PRIMARY).pack(anchor="w", padx=20, pady=(15, 10))

    f = tk.Frame(pop, bg=BG_COLOR)
    f.pack(fill="both", expand=True, padx=20)

    def focus_next(event): event.widget.tk_focusNext().focus(); return "break"

    tk.Label(f, text="Title *", font=("Arial", 9, "bold"), bg=BG_COLOR, fg=TEXT_SECONDARY).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 2))
    t_ent = tk.Entry(f, textvariable=title_var, font=("Arial", 11), width=48, bg=BG_COLOR, fg=TEXT_PRIMARY, insertbackground=TEXT_PRIMARY, highlightbackground=BORDER_COLOR, highlightthickness=1)
    t_ent.grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 10), ipady=5)
    enable_copy_paste(t_ent)

    suggestion_box = tk.Listbox(pop, font=("Arial", 11), height=5, bg=CARD_BG, fg=TEXT_PRIMARY, selectbackground=ACCENT_BLUE, selectforeground="#ffffff", relief="solid", bd=1, highlightthickness=0)
    ignore_trace = [False]
    current_selection = [-1]

    def update_suggestions(*args):
        if ignore_trace[0]: return
        typed = title_var.get().lower()
        suggestion_box.delete(0, tk.END)
        current_selection[0] = -1
        if not typed:
            suggestion_box.place_forget()
            return
        matches = [t for t in past_titles if typed in t.lower()]
        if matches:
            for m in matches: suggestion_box.insert(tk.END, m)
            x = t_ent.winfo_rootx() - pop.winfo_rootx()
            y = t_ent.winfo_rooty() - pop.winfo_rooty() + t_ent.winfo_height()
            suggestion_box.place(x=x, y=y, width=t_ent.winfo_width())
            suggestion_box.lift()
        else:
            suggestion_box.place_forget()

    title_var.trace_add("write", update_suggestions)

    def set_active_item(idx):
        suggestion_box.selection_clear(0, tk.END)
        if 0 <= idx < suggestion_box.size():
            suggestion_box.selection_set(idx)
            suggestion_box.activate(idx)
            suggestion_box.see(idx)

    def apply_suggestion(sel_title):
        ignore_trace[0] = True
        title_var.set(sel_title)
        ignore_trace[0] = False
        suggestion_box.place_forget()
        
        # --- THE FIX: Clean database execution ---
        conn = database.get_connection()
        c = conn.cursor()
        c.execute("SELECT category FROM general_expenses WHERE title = ? AND company_id = ? LIMIT 1", (sel_title, comp_id))
        res = c.fetchone()
        if res: category_var.set(res[0])
        conn.close()
        cat_combo.focus_set()

    def on_entry_keydown(event):
        if event.keysym == "Down" and suggestion_box.winfo_ismapped():
            current_selection[0] = min(current_selection[0] + 1, suggestion_box.size() - 1)
            set_active_item(current_selection[0])
            return "break"
        elif event.keysym == "Up" and suggestion_box.winfo_ismapped():
            current_selection[0] = max(current_selection[0] - 1, -1)
            set_active_item(current_selection[0])
            return "break"
        elif event.keysym == "Return":
            if suggestion_box.winfo_ismapped() and current_selection[0] >= 0:
                apply_suggestion(suggestion_box.get(current_selection[0]))
                return "break"
            else:
                focus_next(event)
                return "break"

    t_ent.bind("<KeyPress>", on_entry_keydown)
    suggestion_box.bind("<ButtonRelease-1>", lambda e: apply_suggestion(suggestion_box.get(suggestion_box.nearest(e.y))) if suggestion_box.nearest(e.y) >= 0 else None)
    pop.bind("<Button-1>", lambda e: suggestion_box.place_forget() if e.widget not in (t_ent, suggestion_box) else None, add="+")

    tk.Label(f, text="Category", font=("Arial", 9, "bold"), bg=BG_COLOR, fg=TEXT_SECONDARY).grid(row=2, column=0, sticky="w", pady=(0, 2))
    
    cat_combo = ttk.Combobox(f, textvariable=category_var, values=rental_cats, font=("Arial", 10), state="readonly", width=24)
    cat_combo.grid(row=3, column=0, sticky="w", pady=(0, 10), padx=(0, 15), ipady=4)
    safe_smart_combo(cat_combo)

    tk.Label(f, text="Amount *", font=("Arial", 9, "bold"), bg=BG_COLOR, fg=TEXT_SECONDARY).grid(row=2, column=1, sticky="w", pady=(0, 2))
    a_ent = tk.Entry(f, textvariable=amount_var, font=("Arial", 11), width=18, bg=BG_COLOR, fg=TEXT_PRIMARY, insertbackground=TEXT_PRIMARY, highlightbackground=BORDER_COLOR, highlightthickness=1)
    a_ent.grid(row=3, column=1, sticky="w", pady=(0, 10), ipady=5)
    enable_copy_paste(a_ent); a_ent.bind("<Return>", focus_next)

    def amt_in(e):
        if amount_var.get() in ("0", "0.0"): amount_var.set("")
    def amt_out(e):
        if not amount_var.get().strip(): amount_var.set("0")
    a_ent.bind("<FocusIn>", amt_in)
    a_ent.bind("<FocusOut>", amt_out)

    tk.Label(f, text="Date", font=("Arial", 9, "bold"), bg=BG_COLOR, fg=TEXT_SECONDARY).grid(row=4, column=0, sticky="w", pady=(0, 2))
    d_f = tk.Frame(f, bg=BG_COLOR)
    d_f.grid(row=5, column=0, sticky="w", pady=(0, 10), padx=(0, 15))
    d_ent = tk.Entry(d_f, textvariable=date_var, font=("Arial", 11), width=14, bg=BG_COLOR, fg=TEXT_PRIMARY, insertbackground=TEXT_PRIMARY, highlightbackground=BORDER_COLOR, highlightthickness=1)
    d_ent.pack(side="left", ipady=5)
    enable_copy_paste(d_ent); d_ent.bind("<Return>", focus_next)
    tk.Button(d_f, text="📅", bg=CARD_BG, fg=TEXT_PRIMARY, relief="flat", cursor="hand2", command=lambda: NativeCalendar(pop, date_var)).pack(side="left", padx=5)

    tk.Label(f, text="Payment Method", font=("Arial", 9, "bold"), bg=BG_COLOR, fg=TEXT_SECONDARY).grid(row=4, column=1, sticky="w", pady=(0, 2))
    
    pay_combo = ttk.Combobox(f, textvariable=pay_method_var, values=all_methods, font=("Arial", 10), state="readonly", width=24)
    pay_combo.grid(row=5, column=1, sticky="w", pady=(0, 10), ipady=4)
    safe_smart_combo(pay_combo)

    # --- THE FIX: Kill the Blinking Typing Bar ---
    # Drops focus from text entries when clicking empty background space
    def drop_focus(event):
        try:
            w_class = event.widget.winfo_class()
            if w_class not in ('Entry', 'Text', 'TCombobox', 'Listbox', 'Button'):
                pop.focus_set()
        except: pass
    pop.bind("<ButtonPress-1>", drop_focus, add="+")
    # ---------------------------------------------

    tk.Label(f, text="Payment Status", font=("Arial", 9, "bold"), bg=BG_COLOR, fg=TEXT_SECONDARY).grid(row=6, column=0, sticky="w", pady=(0, 2))
    status_cb = ttk.Combobox(f, textvariable=status_var, values=["Paid", "Pending (Unpaid)"], font=("Arial", 10), state="readonly", width=24)
    status_cb.grid(row=7, column=0, sticky="w", pady=(0, 10), padx=(0, 15), ipady=4)
    safe_smart_combo(status_cb)

    tk.Label(f, text="Notes / Reason", font=("Arial", 9, "bold"), bg=BG_COLOR, fg=TEXT_SECONDARY).grid(row=8, column=0, columnspan=2, sticky="w", pady=(0, 2))
    n_ent = tk.Entry(f, textvariable=notes_var, font=("Arial", 11), width=48, bg=BG_COLOR, fg=TEXT_PRIMARY, insertbackground=TEXT_PRIMARY, highlightbackground=BORDER_COLOR, highlightthickness=1)
    n_ent.grid(row=9, column=0, columnspan=2, sticky="w", pady=(0, 15), ipady=5)
    enable_copy_paste(n_ent); n_ent.bind("<Return>", lambda e: btn_save.invoke())

    receipt_f = tk.Frame(f, bg=BG_COLOR)
    receipt_f.grid(row=10, column=0, columnspan=2, sticky="ew", pady=(0, 10))
    
    btn_attach = tk.Button(receipt_f, text="📎 Attach Receipt Image/PDF", font=("Arial", 9), bg=CARD_BG, fg=TEXT_PRIMARY, relief="solid", bd=1, highlightbackground=BORDER_COLOR, cursor="hand2", padx=10, pady=4)
    btn_attach.pack(side="left")
    
    display_name = "No file selected"
    if receipt_path_var.get():
        btn_attach.config(text="✓ Receipt Attached", fg=ACCENT_GREEN, bg=CARD_BG)
        display_name = os.path.basename(receipt_path_var.get())[:30] + "..."
        
    lbl_receipt_name = tk.Label(receipt_f, text=display_name, font=("Arial", 9, "italic"), bg=BG_COLOR, fg=TEXT_SECONDARY)
    lbl_receipt_name.pack(side="left", padx=10)

    def attach_file():
        p = filedialog.askopenfilename(parent=pop, title="Select Receipt", filetypes=[("All Files", "*.*")])
        if p:
            receipt_path_var.set(p)
            btn_attach.config(text="✓ Receipt Attached", fg=ACCENT_GREEN, bg=CARD_BG)
            lbl_receipt_name.config(text=os.path.basename(p)[:30] + "...")
            pop.lift(); pop.focus_force()
    btn_attach.config(command=attach_file)

    try:
        _init_amt = float(amount_var.get())
    except Exception:
        _init_amt = 0.0

    initial_snapshot = {
        "title": title_var.get().strip(),
        "category": category_var.get().strip(),
        "amount": _init_amt,
        "date": date_var.get().strip(),
        "pay_method": pay_method_var.get().strip(),
        "status": status_var.get().strip(),
        "notes": notes_var.get().strip(),
        "receipt": receipt_path_var.get().strip()
    }

    def save_expense():
        title = title_var.get().strip()
        try: amt = float(amount_var.get())
        except: messagebox.showerror("Error", "Amount must be a valid number.", parent=pop); return
        if not title: messagebox.showerror("Error", "Title is required.", parent=pop); return
        if amt < 0: messagebox.showerror("Error", "Amount must be a positive number.", parent=pop); return

        current_pay_val = pay_method_var.get().strip()
        
        if not current_pay_val:
            messagebox.showerror("Error", "Please select a valid Payment Method.", parent=pop)
            return

        safe_dir = os.path.join(ROOT_DIR, "expense_receipts")
        os.makedirs(safe_dir, exist_ok=True)
        
        final_receipt_path = ""
        raw_path = receipt_path_var.get().strip()
        if raw_path and os.path.exists(raw_path):
            norm_raw = os.path.normcase(os.path.abspath(raw_path))
            norm_safe = os.path.normcase(os.path.abspath(safe_dir))
            # Only copy if it's a new external file or if duplicating (is_clone) a record
            if not is_clone and norm_raw.startswith(norm_safe):
                final_receipt_path = raw_path
            else:
                ext = os.path.splitext(raw_path)[1]
                if not ext: ext = ".png"
                unique_name = f"receipt_{int(time.time() * 1000)}_{random.randint(1000, 9999)}{ext}"
                final_receipt_path = os.path.join(safe_dir, unique_name)
                try: shutil.copy2(raw_path, final_receipt_path)
                except: final_receipt_path = raw_path 

        notes_val = notes_var.get().strip()
        status_val = status_var.get().strip()
        cat_val = category_var.get().strip()
        date_val = date_var.get().strip()
        
        # --- THE FIX: Clean MVC Architecture + Audit Logging ---
        database.set_active_company(comp_id)
        try:
            if target_id and not is_clone:
                allowed, err_msg = database.check_expense_permission(int(target_id), action="edit", company_id=comp_id)
                if not allowed:
                    messagebox.showerror("Access Denied", err_msg, parent=pop)
                    return

                old_row = database.get_general_expense_record(int(target_id))
                database.update_general_expense(int(target_id), date_val, title, cat_val, amt, notes_val, current_pay_val, status_val, final_receipt_path)
                new_row = database.get_general_expense_record(int(target_id))
                undo_cb("EDIT", (old_row, new_row))

                diffs = []
                if initial_snapshot["title"] != title:
                    diffs.append(f"Title: '{initial_snapshot['title']}' ➔ '{title}'")
                if initial_snapshot["category"] != cat_val:
                    diffs.append(f"Category: '{initial_snapshot['category']}' ➔ '{cat_val}'")
                if abs(initial_snapshot["amount"] - amt) > 0.009:
                    diffs.append(f"Amount: @@CURR:{initial_snapshot['amount']}@@ ➔ @@CURR:{amt}@@")
                if initial_snapshot["date"] != date_val:
                    diffs.append(f"Date: @@DATE:{initial_snapshot['date']}@@ ➔ @@DATE:{date_val}@@")
                if initial_snapshot["pay_method"] != current_pay_val:
                    diffs.append(f"Mode: '{initial_snapshot['pay_method']}' ➔ '{current_pay_val}'")
                if initial_snapshot["status"] != status_val:
                    diffs.append(f"Status: '{initial_snapshot['status']}' ➔ '{status_val}'")
                if initial_snapshot["notes"] != notes_val:
                    diffs.append(f"Notes: '{initial_snapshot['notes'] or 'None'}' ➔ '{notes_val or 'None'}'")
                if initial_snapshot["receipt"] != raw_path:
                    diffs.append("Receipt Updated" if initial_snapshot["receipt"] else "Receipt Attached")

                if diffs:
                    database.log_audit(
                        "Expenses", "Edited",
                        record_ref=f"#{int(target_id)} • {title}",
                        details=" | ".join(diffs),
                        amount=amt, company_id=comp_id
                    )
            else:
                new_id = database.add_general_expense(date_val, title, cat_val, amt, notes_val, current_pay_val, status_val, final_receipt_path)
                undo_cb("ADD", new_id)

                act_lbl = "Cloned" if is_clone else "Created"
                det_parts = [
                    f"Category: {cat_val}",
                    f"Mode: {current_pay_val}",
                    f"Status: {status_val}",
                    f"Date: @@DATE:{date_val}@@"
                ]
                if notes_val:
                    det_parts.append(f"Note: {notes_val}")
                if final_receipt_path:
                    det_parts.append("Receipt: Attached")

                database.log_audit(
                    "Expenses", act_lbl,
                    record_ref=f"#{int(new_id)} • {title}",
                    details=" • ".join(det_parts),
                    amount=amt, company_id=comp_id
                )
        except Exception as e:
            messagebox.showerror("Database Error", str(e), parent=pop)
            return
        # ----------------------------------------
            
        refresh_cb()
        pop.destroy()

    btn_save = tk.Button(pop, text="Save Expense", font=("Arial", 12, "bold"), bg=ACCENT_BLUE, fg="#ffffff", relief="flat", cursor="hand2", width=18)
    btn_save.pack(side="right", padx=20, pady=(0, 25), ipady=6)
    btn_save.config(command=save_expense)