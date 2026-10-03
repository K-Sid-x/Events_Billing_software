import tkinter as tk
from tkinter import ttk
import os
import database
import json

from views.invoice_parts.calendar_widget import NativeCalendar
from views.customers_parts.ledger_core import execute_ledger_load, treeview_sort_column, on_sale_double_click, on_purch_double_click, set_ledger_cursor, undo_last_payment, redo_last_payment, show_net_balance_breakdown
from views.customers_parts.ledger_payments import open_payment_popup, view_payment_history, open_contra_settlement_popup
from views.customers_parts.ledger_export import export_ledger_statement

def build_ui(ledger):
    c = ledger.colors
    
    try:
        # --- THE FIX: Route settings through Gatekeeper! ---
        s_raw = database.get_ui_setting(f"ledger_s_cols_{ledger.comp_id}", "{}")
        p_raw = database.get_ui_setting(f"ledger_p_cols_{ledger.comp_id}", "{}")
        
        ledger.app.ledger_s_widths = json.loads(s_raw) if s_raw else {}
        ledger.app.ledger_p_widths = json.loads(p_raw) if p_raw else {}
        # ---------------------------------------------------
    except:
        if not hasattr(ledger.app, 'ledger_s_widths'): ledger.app.ledger_s_widths = {}
        if not hasattr(ledger.app, 'ledger_p_widths'): ledger.app.ledger_p_widths = {}
    
    style = ttk.Style(ledger)
    style.theme_use("default") # --- THE FIX: Unlock Custom Thick Scrollbars! ---
    
    # --- THE FIX: Actually DEFINE the thick scrollbar colors! ---
    style.configure("Ledger.Vertical.TScrollbar", background=c["text_sec"], troughcolor=c["bg"], bordercolor=c["bg"], arrowcolor=c["text"], relief="flat")
    style.configure("Ledger.Horizontal.TScrollbar", background=c["text_sec"], troughcolor=c["bg"], bordercolor=c["bg"], arrowcolor=c["text"], relief="flat")
    style.map("Ledger.Vertical.TScrollbar", background=[("active", c["accent_blue"])])
    style.map("Ledger.Horizontal.TScrollbar", background=[("active", c["accent_blue"])])
    # ------------------------------------------------------------
    
    style.configure("Ledger.Treeview", font=("Segoe UI", 10), rowheight=30, background=c["card"], fieldbackground=c["card"], foreground=c["text"], borderwidth=0)
    style.map("Ledger.Treeview", background=[("selected", c["border"])], foreground=[("selected", c["text"])])
    style.configure("Ledger.Treeview.Heading", font=("Segoe UI", 10, "bold"), background=c["header"], foreground=c["text"], borderwidth=1, bordercolor=c["border"], relief="solid")
    style.map("Ledger.Treeview.Heading", background=[("active", c["border"])], foreground=[("active", c["text"])])
    style.configure("Ledger.TCombobox", fieldbackground=c["card"], background=c["header"], foreground=c["text"], arrowcolor=c["text"], bordercolor=c["border"])
    style.map("Ledger.TCombobox", fieldbackground=[("readonly", c["card"])], selectbackground=[("readonly", c["card"])], selectforeground=[("readonly", c["text"])])
    
    ledger.option_add("*TCombobox*Listbox.background", c["card"])
    ledger.option_add("*TCombobox*Listbox.foreground", c["text"])
    ledger.option_add("*TCombobox*Listbox.selectBackground", c["border"])
    ledger.option_add("*TCombobox*Listbox.selectForeground", c["text"])

    header_f = tk.Frame(ledger, bg=c["card"], highlightbackground=c["border"], highlightthickness=1)
    header_f.pack(fill="x", padx=15, pady=(15, 10))
    col1 = tk.Frame(header_f, bg=c["card"], padx=20, pady=15)
    col1.pack(side="left", fill="x", expand=True)
    col2 = tk.Frame(header_f, bg=c["card"], padx=20, pady=15)
    col2.pack(side="right", fill="x", expand=True)
    
    # --- THE FIX: Show Display Name (with Alias) in the Ledger Header ---
    tk.Label(col1, text=getattr(ledger, 'display_name', ledger.party_name), font=("Segoe UI", 22, "bold"), bg=c["card"], fg=c["accent_blue"]).pack(anchor="w", pady=(0, 5))
    # --------------------------------------------------------------------
    if ledger.phone_clean and ledger.phone_clean != "N/A": tk.Label(col1, text=f"📞 {ledger.phone_clean}", font=("Segoe UI", 11), bg=c["card"], fg=c["text_sec"]).pack(anchor="w")
    if ledger.addr_text != "N/A" and ledger.addr_text: tk.Label(col1, text=f"📍 {ledger.addr_text}", font=("Segoe UI", 11), bg=c["card"], fg=c["text_sec"]).pack(anchor="w")
    if ledger.email_str: tk.Label(col1, text=f"📧 {ledger.email_str}", font=("Segoe UI", 11), bg=c["card"], fg=c["text_sec"]).pack(anchor="w")
    if ledger.is_gst_company and ledger.state_text:
        tk.Label(col1, text=f"State: {ledger.state_text}", font=("Segoe UI", 11), bg=c["card"], fg=c["text_sec"]).pack(anchor="w", pady=(4,0))

    if ledger.gstin_str: tk.Label(col2, text=f"GSTIN: {ledger.gstin_str}", font=("Segoe UI", 12, "bold"), bg=c["card"], fg=c["text"]).pack(anchor="e", pady=2)
    if ledger.pan_text != "N/A": tk.Label(col2, text=f"PAN: {ledger.pan_text}", font=("Segoe UI", 12, "bold"), bg=c["card"], fg=c["text"]).pack(anchor="e", pady=2)
    
    # --- THE FIX: Look strictly for "Dr" marker to apply the Receivable label ---
    ob_lbl = "(Receivable)" if 'Dr' in ledger.ob_type else "(Payable)"
    if ledger.ob_val == 0: ob_lbl = ""
    tk.Label(col2, text=f"Opening Balance: {ledger.fmt(ledger.ob_val)} {ob_lbl}", font=("Segoe UI", 11), bg=c["card"], fg=c["text_sec"]).pack(anchor="e", pady=(5,0))
    
    wallet_f = tk.Frame(col2, bg=c["card"])
    wallet_f.pack(anchor="e", pady=5)
    
    ledger.lbl_adv_in = tk.Label(wallet_f, text=f"Advance (In): {ledger.fmt(ledger.advance_in)}", font=("Segoe UI", 11, "bold"), bg=c["card"], fg=c["accent_green"] if ledger.advance_in > 0 else c["text_sec"])
    ledger.lbl_adv_in.pack(anchor="e")
    
    ledger.lbl_adv_out = tk.Label(wallet_f, text=f"Advance (Out): {ledger.fmt(ledger.advance_out)}", font=("Segoe UI", 11, "bold"), bg=c["card"], fg=c["accent_blue"] if ledger.advance_out > 0 else c["text_sec"])
    ledger.lbl_adv_out.pack(anchor="e")
    
    from views.customers_parts.ledger_core import perform_offset
    if ledger.advance_in > 0 and ledger.advance_out > 0:
        tk.Button(wallet_f, text="🔄 Offset Balances", font=("Segoe UI", 9, "bold"), bg=c["border"], fg=c["text"], relief="flat", cursor="hand2", command=lambda: perform_offset(ledger)).pack(anchor="e", pady=(2,0))

    toolbar = tk.Frame(ledger, bg=c["bg"])
    toolbar.pack(fill="x", padx=15, pady=(0, 5))
    
    tk.Label(toolbar, text="Filter:", font=("Segoe UI", 10, "bold"), bg=c["bg"], fg=c["text_sec"]).pack(side="left")
    ledger.filter_var = tk.StringVar(value="All Time")
    cb_filter = ttk.Combobox(toolbar, textvariable=ledger.filter_var, values=["This Month", "This Financial Year", "All Time", "Custom Range..."], state="readonly", width=18, style="Ledger.TCombobox")
    cb_filter.pack(side="left", padx=10)

    tk.Label(toolbar, text="Search:", font=("Segoe UI", 10, "bold"), bg=c["bg"], fg=c["text_sec"]).pack(side="left", padx=(15, 5))
    ledger.search_var = tk.StringVar()
    
    search_entry = tk.Entry(toolbar, textvariable=ledger.search_var, font=("Segoe UI", 10), width=18, bg=c["card"], fg=c["text"], insertbackground=c["text"], highlightbackground=c["border"], highlightcolor=c["accent_blue"], highlightthickness=1, bd=0, relief="flat")
    search_entry.pack(side="left")
    search_entry.insert(0, "Bill No / Amount...")
    search_entry.bind("<FocusIn>", lambda e: search_entry.delete(0, 'end') if search_entry.get() == "Bill No / Amount..." else None)
    search_entry.bind("<FocusOut>", lambda e: search_entry.insert(0, "Bill No / Amount...") if not search_entry.get() else None)

    ledger.custom_date_f = tk.Frame(toolbar, bg=c["bg"])
    ledger.from_var = tk.StringVar(value="Start Date")
    ledger.to_var = tk.StringVar(value="End Date")

    btn_from = tk.Button(ledger.custom_date_f, textvariable=ledger.from_var, bg=c["card"], fg=c["text"], font=("Segoe UI", 10), relief="solid", bd=1, cursor="hand2", width=12)
    btn_from.config(command=lambda: NativeCalendar(ledger, ledger.from_var, anchor_widget=btn_from))
    btn_from.pack(side="left", padx=5)
    tk.Label(ledger.custom_date_f, text="to", bg=c["bg"], fg=c["text_sec"], font=("Segoe UI", 10)).pack(side="left")
    btn_to = tk.Button(ledger.custom_date_f, textvariable=ledger.to_var, bg=c["card"], fg=c["text"], font=("Segoe UI", 10), relief="solid", bd=1, cursor="hand2", width=12)
    btn_to.config(command=lambda: NativeCalendar(ledger, ledger.to_var, anchor_widget=btn_to, ref_date_var=ledger.from_var))
    btn_to.pack(side="left", padx=5)
    tk.Button(ledger.custom_date_f, text="Apply", bg=c["accent_blue"], fg="#ffffff", font=("Segoe UI", 10, "bold"), relief="flat", cursor="hand2", command=lambda: execute_ledger_load(ledger)).pack(side="left", padx=5)

    def on_filter_change(*args):
        if ledger.filter_var.get() == "Custom Range...": ledger.custom_date_f.pack(side="left", padx=5)
        else:
            ledger.custom_date_f.pack_forget()
            execute_ledger_load(ledger)

    cb_filter.bind("<<ComboboxSelected>>", on_filter_change)
    ledger.search_var.trace_add("write", lambda *a: execute_ledger_load(ledger) if search_entry.get() != "Bill No / Amount..." else None)

    tk.Button(toolbar, text="📄 Export Statement", bg=c["border"], fg=c["text"], font=("Segoe UI", 10, "bold"), relief="flat", cursor="hand2", command=lambda: export_ledger_statement(ledger), padx=10, pady=4).pack(side="right")

    # --- THE FIX: Reverted to Original Clean Horizontal Layout! ---
    btn_group = tk.Frame(toolbar, bg=c["card"], highlightbackground=c["border"], highlightthickness=1)
    btn_group.pack(side="right", padx=(10, 15))

    ledger.btn_undo = tk.Button(btn_group, text="↺ Undo", font=("Segoe UI", 10, "bold"), bg=c["card"], fg=c["text_sec"], relief="flat", padx=10, pady=2, command=lambda: undo_last_payment(ledger), state="disabled")
    ledger.btn_undo.pack(side="left")

    tk.Frame(btn_group, width=1, bg=c["border"]).pack(side="left", fill="y")

    ledger.btn_redo = tk.Button(btn_group, text="↻ Redo", font=("Segoe UI", 10, "bold"), bg=c["card"], fg=c["text_sec"], relief="flat", padx=10, pady=2, command=lambda: redo_last_payment(ledger), state="disabled")
    ledger.btn_redo.pack(side="left")

    tk.Button(toolbar, text="📜 View Payment History", font=("Segoe UI", 9, "bold"), bg=c["card"], fg=c["text"], relief="solid", bd=1, cursor="hand2", padx=15, pady=3, command=lambda: view_payment_history(ledger)).pack(side="right", padx=(0, 10))
    # --------------------------------------------------------------

    split_container = tk.Frame(ledger, bg=c["bg"])
    split_container.pack(fill="both", expand=True, padx=15)
    
    sales_f = tk.Frame(split_container, bg=c["card"], highlightbackground=c["border"], highlightthickness=1)
    sales_f.pack(side="left", fill="both", expand=True, padx=(0, 5))
    
    tk.Label(sales_f, text="📦 Invoices / Receivables (Debit)", font=("Segoe UI", 12, "bold"), bg=c["header"], fg=c["text"], pady=10).pack(fill="x")
    
    # --- THE FIX: Apply isolated thick scrollbar styles ---
    s_scroll_y = ttk.Scrollbar(sales_f, orient="vertical", style="Ledger.Vertical.TScrollbar")
    s_scroll_x = ttk.Scrollbar(sales_f, orient="horizontal", style="Ledger.Horizontal.TScrollbar")
    # ------------------------------------------------------
    
    # --- THE FIX: Insert TDS Column into Sales Ledger ---
    ledger.sales_tree = ttk.Treeview(sales_f, columns=("date", "inv", "amount", "tds", "balance", "status", "ghost"), show="headings", yscrollcommand=s_scroll_y.set, xscrollcommand=s_scroll_x.set, style="Ledger.Treeview")
    s_scroll_y.config(command=ledger.sales_tree.yview)
    s_scroll_x.config(command=ledger.sales_tree.xview)
    
    for col, default_w, min_w, a, s in [("date", 90, 60, "center", False), ("inv", 140, 80, "center", False), ("amount", 100, 70, "e", False), ("tds", 80, 60, "e", False), ("balance", 100, 70, "e", False), ("status", 110, 80, "center", False)]:
        w = ledger.app.ledger_s_widths.get(col, default_w)
        ledger.sales_tree.heading(col, text=col.upper() if col != "inv" else "INVOICE NO", anchor=a, command=lambda _c=col: treeview_sort_column(ledger.sales_tree, _c, "S", ledger))
        ledger.sales_tree.column(col, width=w, minwidth=min_w, stretch=s, anchor=a)
        
    ledger.sales_tree.heading("ghost", text="")
    ledger.sales_tree.column("ghost", width=10, minwidth=10, stretch=True)
    # ----------------------------------------------------------
        
    s_scroll_y.pack(side="right", fill="y")
    s_scroll_x.pack(side="bottom", fill="x")
    ledger.sales_tree.pack(fill="both", expand=True, padx=2, pady=2)

    purch_f = tk.Frame(split_container, bg=c["card"], highlightbackground=c["border"], highlightthickness=1)
    purch_f.pack(side="right", fill="both", expand=True, padx=(5, 0))
    tk.Label(purch_f, text="🛒 Purchases / Payables (Credit)", font=("Segoe UI", 12, "bold"), bg=c["header"], fg=c["text"], pady=10).pack(fill="x")
    
    p_scroll_y = ttk.Scrollbar(purch_f, orient="vertical", style="Ledger.Vertical.TScrollbar")
    p_scroll_x = ttk.Scrollbar(purch_f, orient="horizontal", style="Ledger.Horizontal.TScrollbar")
    
    # --- THE FIX: Insert TDS Column into Purchase Ledger ---
    ledger.purch_tree = ttk.Treeview(purch_f, columns=("date", "inv", "amount", "tds", "balance", "status", "ghost"), show="headings", yscrollcommand=p_scroll_y.set, xscrollcommand=p_scroll_x.set, style="Ledger.Treeview")
    p_scroll_y.config(command=ledger.purch_tree.yview)
    p_scroll_x.config(command=ledger.purch_tree.xview)
    
    for col, default_w, min_w, a, s in [("date", 90, 60, "center", False), ("inv", 140, 80, "center", False), ("amount", 100, 70, "e", False), ("tds", 80, 60, "e", False), ("balance", 100, 70, "e", False), ("status", 110, 80, "center", False)]:
        w = ledger.app.ledger_p_widths.get(col, default_w)
        ledger.purch_tree.heading(col, text=col.upper() if col != "inv" else "BILL NO", anchor=a, command=lambda _c=col: treeview_sort_column(ledger.purch_tree, _c, "P", ledger))
        ledger.purch_tree.column(col, width=w, minwidth=min_w, stretch=s, anchor=a)

    ledger.purch_tree.heading("ghost", text="")
    ledger.purch_tree.column("ghost", width=10, minwidth=10, stretch=True)
    # -------------------------------------------------------------
        
    p_scroll_y.pack(side="right", fill="y")
    p_scroll_x.pack(side="bottom", fill="x")
    ledger.purch_tree.pack(fill="both", expand=True, padx=2, pady=2)

    ledger.sales_tree.tag_configure("stripe_even", background=c["stripe_even"], foreground=c["text"])
    ledger.sales_tree.tag_configure("stripe_odd", background=c["stripe_odd"], foreground=c["text"])
    ledger.purch_tree.tag_configure("stripe_even", background=c["stripe_even"], foreground=c["text"])
    ledger.purch_tree.tag_configure("stripe_odd", background=c["stripe_odd"], foreground=c["text"])

    s_tot_f = tk.Frame(sales_f, bg=c["header"], bd=0, highlightbackground=c["border"], highlightthickness=1)
    s_tot_f.pack(fill="x")
    for i in range(3): s_tot_f.columnconfigure(i, weight=1)
    ledger.lbl_s_inv = tk.Label(s_tot_f, text="Total Invoiced\n0.00", bg=c["header"], fg=c["text"], font=("Segoe UI", 10, "bold"))
    ledger.lbl_s_inv.grid(row=0, column=0, pady=8)
    ledger.lbl_s_rec = tk.Label(s_tot_f, text="Total Received\n0.00", bg=c["header"], fg=c["accent_green"], font=("Segoe UI", 10, "bold"))
    ledger.lbl_s_rec.grid(row=0, column=1, pady=8)
    ledger.lbl_s_pend = tk.Label(s_tot_f, text="Total Receivable\n0.00", bg=c["header"], fg=c["error"], font=("Segoe UI", 10, "bold"))
    ledger.lbl_s_pend.grid(row=0, column=2, pady=8)

    p_tot_f = tk.Frame(purch_f, bg=c["header"], bd=0, highlightbackground=c["border"], highlightthickness=1)
    p_tot_f.pack(fill="x")
    for i in range(3): p_tot_f.columnconfigure(i, weight=1)
    ledger.lbl_p_bill = tk.Label(p_tot_f, text="Total Billed\n0.00", bg=c["header"], fg=c["text"], font=("Segoe UI", 10, "bold"))
    ledger.lbl_p_bill.grid(row=0, column=0, pady=8)
    ledger.lbl_p_paid = tk.Label(p_tot_f, text="Total Paid\n0.00", bg=c["header"], fg=c["accent_green"], font=("Segoe UI", 10, "bold"))
    ledger.lbl_p_paid.grid(row=0, column=1, pady=8)
    ledger.lbl_p_pend = tk.Label(p_tot_f, text="Total Payable\n0.00", bg=c["header"], fg=c["accent_blue"], font=("Segoe UI", 10, "bold"))
    ledger.lbl_p_pend.grid(row=0, column=2, pady=8)

    footer_f = tk.Frame(ledger, bg=c["card"], highlightbackground=c["border"], highlightthickness=1)
    footer_f.pack(fill="x", padx=15, pady=15)
    
    ledger.lbl_grand = tk.Label(footer_f, text="", font=("Segoe UI", 16, "bold"), bg=c["card"], pady=15, cursor="hand2")
    ledger.lbl_grand.pack(side="left", padx=10)
    ledger.lbl_grand.bind("<Button-1>", lambda e: show_net_balance_breakdown(ledger))

    tk.Button(footer_f, text="📤 Make Payment", font=("Segoe UI", 10, "bold"), bg=c["accent_blue"], fg="#ffffff", relief="flat", cursor="hand2", padx=15, pady=5, command=lambda: open_payment_popup(ledger, "make")).pack(side="right", padx=10)
    tk.Button(footer_f, text="📥 Receive Payment", font=("Segoe UI", 10, "bold"), bg=c["accent_green"], fg="#ffffff", relief="flat", cursor="hand2", padx=15, pady=5, command=lambda: open_payment_popup(ledger, "receive")).pack(side="right", padx=10)
    
    # --- THE FIX: The New Settle / Contra Bills Button ---
    tk.Button(footer_f, text="⚖️ Settle / Contra Bills", font=("Segoe UI", 10, "bold"), bg=c["border"], fg=c["text"], relief="flat", cursor="hand2", padx=15, pady=5, command=lambda: open_contra_settlement_popup(ledger)).pack(side="right", padx=10)
    # -----------------------------------------------------

    def remove_focus(e):
        if e.widget.winfo_class() not in ['Entry', 'TCombobox', 'Listbox', 'Text']:
            ledger.focus_set()
            
    ledger.bind("<ButtonPress-1>", remove_focus)
    header_f.bind("<ButtonPress-1>", remove_focus)
    toolbar.bind("<ButtonPress-1>", remove_focus)
    split_container.bind("<ButtonPress-1>", remove_focus)
    sales_f.bind("<ButtonPress-1>", remove_focus)
    purch_f.bind("<ButtonPress-1>", remove_focus)
    footer_f.bind("<ButtonPress-1>", remove_focus)

    def save_ledger_widths():
        # --- THE FIX: Added "tds" to the memory loop so its width is saved correctly! ---
        for c_name in ("date", "inv", "amount", "tds", "balance", "status"):
            # MATHEMATICAL CLAMP: Prevent 0-width crashes
            ledger.app.ledger_s_widths[c_name] = max(30, ledger.sales_tree.column(c_name, "width"))
            ledger.app.ledger_p_widths[c_name] = max(30, ledger.purch_tree.column(c_name, "width"))
        try:
            # --- THE FIX: Route settings through Gatekeeper! ---
            s_key = f"ledger_s_cols_{ledger.comp_id}"
            p_key = f"ledger_p_cols_{ledger.comp_id}"
            database.save_ui_setting(s_key, json.dumps(ledger.app.ledger_s_widths))
            database.save_ui_setting(p_key, json.dumps(ledger.app.ledger_p_widths))
            # ---------------------------------------------------
        except: pass

    def on_ledger_sep_drag(event, tree):
        if tree.identify_region(event.x, event.y) == "separator":
            ledger.after(50, save_ledger_widths)

    ledger.sales_tree.bind("<B1-Motion>", lambda e: on_ledger_sep_drag(e, ledger.sales_tree), add="+")
    ledger.purch_tree.bind("<B1-Motion>", lambda e: on_ledger_sep_drag(e, ledger.purch_tree), add="+")

    ledger.sales_tree.bind("<ButtonRelease-1>", lambda e: ledger.after(50, save_ledger_widths) if ledger.sales_tree.identify_region(e.x, e.y) == "separator" else None, add="+")
    ledger.purch_tree.bind("<ButtonRelease-1>", lambda e: ledger.after(50, save_ledger_widths) if ledger.purch_tree.identify_region(e.x, e.y) == "separator" else None, add="+")

    # --- THE FIX: Buttery Smooth X/Y Scrolling for Sales Table ---
    def fast_scroll_s(event, direction):
        delta = -1 * (event.delta / 120) if os.name == 'nt' else -1 * event.delta
        if direction == "y":
            ledger.sales_tree.yview_moveto(ledger.sales_tree.yview()[0] + (delta * 0.008))
        else:
            ledger.sales_tree.xview_moveto(ledger.sales_tree.xview()[0] + (delta * 0.02))

    # --- THE FIX: Buttery Smooth X/Y Scrolling for Purchases Table ---
    def fast_scroll_p(event, direction):
        delta = -1 * (event.delta / 120) if os.name == 'nt' else -1 * event.delta
        if direction == "y":
            ledger.purch_tree.yview_moveto(ledger.purch_tree.yview()[0] + (delta * 0.008))
        else:
            ledger.purch_tree.xview_moveto(ledger.purch_tree.xview()[0] + (delta * 0.02))

    ledger.sales_tree.bind("<MouseWheel>", lambda e: fast_scroll_s(e, "y"))
    ledger.sales_tree.bind("<Shift-MouseWheel>", lambda e: fast_scroll_s(e, "x"))
    ledger.purch_tree.bind("<MouseWheel>", lambda e: fast_scroll_p(e, "y"))
    ledger.purch_tree.bind("<Shift-MouseWheel>", lambda e: fast_scroll_p(e, "x"))

    ledger.sales_tree.bind("<Motion>", lambda e: set_ledger_cursor(e, ledger.sales_tree))
    ledger.purch_tree.bind("<Motion>", lambda e: set_ledger_cursor(e, ledger.purch_tree))
    ledger.sales_tree.bind("<Double-1>", lambda e: on_sale_double_click(e, ledger))
    ledger.purch_tree.bind("<Double-1>", lambda e: on_purch_double_click(e, ledger))