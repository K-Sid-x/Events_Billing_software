import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
import database
import os

def open_format_settings_modal(form):
    """
    form: The parent PurchaseForm instance. 
    It expects form to have standard color attributes and the generate_internal_voucher method.
    """
    f_pop = tk.Toplevel(form.pop)
    f_pop.title("Voucher Numbering Format")
    f_pop.geometry("450x450")
    f_pop.configure(bg=form.BG_COLOR)
    f_pop.grab_set()
    
    f_pop.update_idletasks()
    x = form.pop.winfo_rootx() + (form.pop.winfo_width() // 2) - (450 // 2)
    y = form.pop.winfo_rooty() + (form.pop.winfo_height() // 2) - (450 // 2)
    f_pop.geometry(f"+{x}+{y}")
    
    tk.Label(f_pop, text="Configure Voucher Numbering", font=("Segoe UI", 14, "bold"), bg=form.BG_COLOR, fg=form.TEXT_PRIMARY).pack(pady=(15, 5))
    tk.Label(f_pop, text="Choose how your internal purchases are numbered.", font=("Segoe UI", 9), bg=form.BG_COLOR, fg=form.TEXT_SECONDARY).pack(pady=(0, 15))
    
    form_f = tk.Frame(f_pop, bg=form.CARD_BG, padx=20, pady=15, highlightbackground=form.BORDER_COLOR, highlightthickness=1)
    form_f.pack(fill="x", padx=20)
    
    mode_var = tk.StringVar(value="Standard")
    custom_var = tk.StringVar(value="PV-[YYYY]-[SEQ]")
    preview_var = tk.StringVar(value="")
    
    def update_preview(*args):
        if mode_var.get() == "Standard": fmt = "PV-[YYYY]-[SEQ]"
        elif mode_var.get() == "Short": fmt = "[YY][MM]-[SEQ]"
        elif mode_var.get() == "FinYear": fmt = "PV-[FY]-[SEQ]"
        else: 
            fmt = custom_var.get()
            # --- THE FIX: Anchor the preview dynamically if the user types without [SEQ] ---
            if "[SEQ]" not in fmt: fmt += "[SEQ]"
            # -------------------------------------------------------------------------------
        
        # THE FIX: Disable/Gray Out the box if Custom is not selected!
        if mode_var.get() == "Custom":
            ent_custom.config(state="normal")
        else:
            ent_custom.config(state="disabled")
        
        # Run real-time DB scan from the parent form engine
        p = form.generate_internal_voucher(preview_mode=True, custom_fmt=fmt)
        preview_var.set(f"Preview: {p}")
        
    tk.Radiobutton(form_f, text="Standard (PV-YYYY-1)", variable=mode_var, value="Standard", font=("Segoe UI", 10), bg=form.CARD_BG, fg=form.TEXT_PRIMARY, selectcolor=form.BG_COLOR, cursor="hand2", command=update_preview).pack(anchor="w", pady=2)
    tk.Radiobutton(form_f, text="Short Month (YYMM-1)", variable=mode_var, value="Short", font=("Segoe UI", 10), bg=form.CARD_BG, fg=form.TEXT_PRIMARY, selectcolor=form.BG_COLOR, cursor="hand2", command=update_preview).pack(anchor="w", pady=2)
    tk.Radiobutton(form_f, text="Financial Year (PV-FY-1)", variable=mode_var, value="FinYear", font=("Segoe UI", 10), bg=form.CARD_BG, fg=form.TEXT_PRIMARY, selectcolor=form.BG_COLOR, cursor="hand2", command=update_preview).pack(anchor="w", pady=2)
    tk.Radiobutton(form_f, text="Custom Layout", variable=mode_var, value="Custom", font=("Segoe UI", 10), bg=form.CARD_BG, fg=form.TEXT_PRIMARY, selectcolor=form.BG_COLOR, cursor="hand2", command=update_preview).pack(anchor="w", pady=(2, 10))
    
    tk.Label(form_f, text="Custom Invoice:", font=("Segoe UI", 9, "bold"), bg=form.CARD_BG, fg=form.TEXT_SECONDARY).pack(anchor="w")
    # THE FIX: Added a helpful hint text for the user
    tk.Label(form_f, text="Tip: Use [SEQ] exactly where you want the numbering (1, 2, 3...) to appear.", font=("Segoe UI", 8, "italic"), bg=form.CARD_BG, fg=form.TEXT_SECONDARY).pack(anchor="w", pady=(0, 5))
    ent_custom = tk.Entry(form_f, textvariable=custom_var, font=("Segoe UI", 11), bg=form.BG_COLOR, fg=form.TEXT_PRIMARY, insertbackground=form.TEXT_PRIMARY, highlightthickness=1, highlightbackground=form.BORDER_COLOR)
    ent_custom.pack(fill="x", pady=(2, 10), ipady=3)
    custom_var.trace_add("write", update_preview)
    
    tk.Label(form_f, textvariable=preview_var, font=("Segoe UI", 11, "bold"), bg=form.CARD_BG, fg=form.ACCENT_BLUE).pack(anchor="w", pady=5)
    
    def fetch_current():
        try:
            conn = database.get_connection()
            c = conn.cursor()
            c.execute("SELECT purchase_voucher_format FROM company WHERE id=?", (form.comp_id,))
            row = c.fetchone()
            if row and row[0]: 
                if row[0] == "PV-[YYYY]-[SEQ]": mode_var.set("Standard")
                elif row[0] == "[YY][MM]-[SEQ]": mode_var.set("Short")
                elif row[0] == "PV-[FY]-[SEQ]": mode_var.set("FinYear")
                else: mode_var.set("Custom"); custom_var.set(row[0])
            conn.close()
        except: pass
        update_preview()
        
    fetch_current()
    
    def save_format():
        fmt = "PV-[YYYY]-[SEQ]"
        if mode_var.get() == "Short": fmt = "[YY][MM]-[SEQ]"
        elif mode_var.get() == "FinYear": fmt = "PV-[FY]-[SEQ]"
        elif mode_var.get() == "Custom": 
            fmt = custom_var.get().strip()
            # --- THE FIX: Auto-inject missing [SEQ] placeholder to prevent sequence crashes! ---
            if "[SEQ]" not in fmt: 
                fmt += "[SEQ]"
                custom_var.set(fmt)
            # -----------------------------------------------------------------------------------
        
        try:
            conn = database.get_connection()
            c = conn.cursor()
            c.execute("UPDATE company SET purchase_voucher_format=? WHERE id=?", (fmt, form.comp_id))
            conn.commit()
            conn.close()
            form.internal_voucher_var.set(form.generate_internal_voucher())
            f_pop.destroy()
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=f_pop)
            
    btn_fmt_save = tk.Button(f_pop, text="Save Format", font=("Segoe UI", 13, "bold"), bg=form.ACCENT_GREEN, fg="#ffffff", relief="flat", cursor="hand2", command=save_format)
    btn_fmt_save.pack(fill="x", padx=20, pady=(20, 10), ipady=12)
    form.add_hover(btn_fmt_save, form.ACCENT_GREEN, getattr(form, "SAVE_HOVER", "#047857"))