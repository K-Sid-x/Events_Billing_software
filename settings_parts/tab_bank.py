import tkinter as tk
from tkinter import ttk
import database

def build_bank_tab(parent, sv):
    # The redundant global focus listener has been stripped out to prevent memory leaks.

    BG_COLOR = sv.theme["BG_COLOR"]
    CARD_BG = sv.theme["CARD_BG"]
    BORDER_COLOR = sv.theme["BORDER_COLOR"]
    TEXT_PRIMARY = sv.theme["TEXT_PRIMARY"]
    TEXT_SECONDARY = sv.theme["TEXT_SECONDARY"]
    ACCENT_BLUE = sv.theme["ACCENT_BLUE"]
    ACCENT_RED = sv.theme["ACCENT_RED"]
    ACCENT_YELLOW = sv.theme["ACCENT_YELLOW"]
    ACCENT_GREEN = sv.theme["ACCENT_GREEN"]
    HEADER_BG = sv.theme["HEADER_BG"]

    main_f = tk.Frame(parent, bg=CARD_BG, padx=30, pady=20, highlightbackground=BORDER_COLOR, highlightthickness=1)
    main_f.pack(fill="both", expand=True, padx=20, pady=20)

    form_f = tk.Frame(main_f, bg=CARD_BG)
    form_f.pack(fill="x", pady=(0, 20))

    def make_entry(f, v):
        return tk.Entry(f, textvariable=v, font=("Arial", 11), width=30, bg=BG_COLOR, fg=TEXT_PRIMARY, insertbackground=TEXT_PRIMARY, highlightbackground=BORDER_COLOR, highlightthickness=1)

    tk.Label(form_f, text="Alias (Short Name)", font=("Arial", 9, "bold"), bg=CARD_BG, fg=TEXT_SECONDARY).grid(row=0, column=0, sticky="w", padx=(0, 15))
    make_entry(form_f, sv.bank_alias_var).grid(row=1, column=0, sticky="w", padx=(0, 15), pady=(2, 10), ipady=4)

    tk.Label(form_f, text="Bank Name *", font=("Arial", 9, "bold"), bg=CARD_BG, fg=TEXT_SECONDARY).grid(row=0, column=1, sticky="w", padx=(0, 15))
    make_entry(form_f, sv.bank_name_var).grid(row=1, column=1, sticky="w", padx=(0, 15), pady=(2, 10), ipady=4)

    tk.Label(form_f, text="Account Name", font=("Arial", 9, "bold"), bg=CARD_BG, fg=TEXT_SECONDARY).grid(row=0, column=2, sticky="w", padx=(0, 15))
    make_entry(form_f, sv.bank_acname_var).grid(row=1, column=2, sticky="w", padx=(0, 15), pady=(2, 10), ipady=4)

    tk.Label(form_f, text="Account Number *", font=("Arial", 9, "bold"), bg=CARD_BG, fg=TEXT_SECONDARY).grid(row=2, column=0, sticky="w", padx=(0, 15))
    make_entry(form_f, sv.bank_ac_var).grid(row=3, column=0, sticky="w", padx=(0, 15), pady=(2, 10), ipady=4)

    tk.Label(form_f, text="IFSC Code", font=("Arial", 9, "bold"), bg=CARD_BG, fg=TEXT_SECONDARY).grid(row=2, column=1, sticky="w", padx=(0, 15))
    make_entry(form_f, sv.bank_ifsc_var).grid(row=3, column=1, sticky="w", padx=(0, 15), pady=(2, 10), ipady=4)

    tk.Label(form_f, text="Branch Name", font=("Arial", 9, "bold"), bg=CARD_BG, fg=TEXT_SECONDARY).grid(row=2, column=2, sticky="w", padx=(0, 15))
    make_entry(form_f, sv.bank_branch_var).grid(row=3, column=2, sticky="w", padx=(0, 15), pady=(2, 10), ipady=4)

    # --- THE FIX: Insert PAN Number Box into the UI Grid ---
    tk.Label(form_f, text="PAN Number", font=("Arial", 9, "bold"), bg=CARD_BG, fg=TEXT_SECONDARY).grid(row=4, column=0, sticky="w", padx=(0, 15), pady=(10, 0))
    make_entry(form_f, sv.bank_pan_var).grid(row=5, column=0, sticky="w", padx=(0, 15), pady=(2, 10), ipady=4)
    # -------------------------------------------------------

    tk.Label(form_f, text="Payment QR Code Image (Optional)", font=("Arial", 9, "bold"), bg=CARD_BG, fg=TEXT_SECONDARY).grid(row=6, column=0, sticky="w", padx=(0, 15), pady=(10, 0))
    
    qr_f = tk.Frame(form_f, bg=CARD_BG)
    qr_f.grid(row=7, column=0, columnspan=2, sticky="w", padx=(0, 15), pady=(2, 10))
    
    tk.Entry(qr_f, textvariable=sv.bank_qr_var, font=("Arial", 10), width=45, bg=BG_COLOR, fg=TEXT_PRIMARY, readonlybackground=BG_COLOR, highlightbackground=BORDER_COLOR, highlightthickness=1, state="readonly").pack(side="left", ipady=4, padx=(0, 10))
    
    tk.Button(qr_f, text="Browse QR", font=("Arial", 9, "bold"), bg=BORDER_COLOR, fg=TEXT_PRIMARY, cursor="hand2", relief="flat", command=sv.browse_bank_qr).pack(side="left", ipady=2)
    tk.Button(qr_f, text="Clear", font=("Arial", 9), bg=BG_COLOR, fg=TEXT_PRIMARY, cursor="hand2", relief="flat", command=lambda: [sv.bank_qr_var.set(""), sv.update_qr_preview("")]).pack(side="left", ipady=2, padx=5)

    sv.qr_preview_cvs = tk.Canvas(form_f, width=60, height=60, bg=BG_COLOR, highlightbackground=BORDER_COLOR, highlightthickness=1)
    sv.qr_preview_cvs.grid(row=6, column=2, rowspan=2, sticky="w", padx=(0, 15), pady=(10, 0))
    sv.qr_preview_cvs.create_text(30, 30, text="Preview", font=("Arial", 8), fill=TEXT_SECONDARY)

    btn_action_f = tk.Frame(form_f, bg=CARD_BG)
    btn_action_f.grid(row=8, column=0, columnspan=3, sticky="w", pady=(15, 10))

    sv.btn_bank_save = tk.Button(btn_action_f, text="Add Bank Account", font=("Arial", 10, "bold"), bg=ACCENT_BLUE, fg="#ffffff", cursor="hand2", relief="flat", padx=20, command=sv.save_bank)
    sv.btn_bank_save.pack(side="left")
    
    sv.btn_bank_cancel = tk.Button(btn_action_f, text="Cancel Edit", font=("Arial", 10), bg=BG_COLOR, fg=TEXT_PRIMARY, cursor="hand2", relief="solid", bd=1, highlightbackground=BORDER_COLOR, padx=10, command=sv.cancel_bank_edit)

    tk.Frame(main_f, height=1, bg=BORDER_COLOR).pack(fill="x", pady=10)

    table_header_f = tk.Frame(main_f, bg=CARD_BG)
    table_header_f.pack(fill="x", pady=(10, 5))
    
    tk.Label(table_header_f, text="Saved Bank Accounts", font=("Arial", 12, "bold"), bg=CARD_BG, fg=TEXT_PRIMARY).pack(side="left")
    
    tk.Button(table_header_f, text="❌ Delete", font=("Arial", 10, "bold"), bg=ACCENT_RED, fg="#ffffff", cursor="hand2", relief="flat", padx=10, command=sv.delete_bank).pack(side="right")
    tk.Button(table_header_f, text="✏️ Edit", font=("Arial", 10, "bold"), bg=ACCENT_BLUE, fg="#ffffff", cursor="hand2", relief="flat", padx=10, command=sv.edit_bank).pack(side="right", padx=(0, 10))
    tk.Button(table_header_f, text="⭐ Set Default", font=("Arial", 10, "bold"), bg=ACCENT_YELLOW, fg=BG_COLOR, cursor="hand2", relief="flat", padx=10, command=sv.set_default_bank).pack(side="right", padx=(0, 10))

    tree_f = tk.Frame(main_f, bg=CARD_BG, highlightbackground=BORDER_COLOR, highlightthickness=1)
    tree_f.pack(fill="both", expand=True, pady=(5, 0))

    style = ttk.Style(sv)
    style.configure("Bank.Treeview.Heading", font=("Arial", 9, "bold"), background=HEADER_BG, foreground=TEXT_PRIMARY, relief="raised", borderwidth=1)
    # --- THE FIX: Map active heading state so it stays readable on hover ---
    style.map("Bank.Treeview.Heading", background=[('active', BORDER_COLOR)])
    style.configure("Bank.Treeview", font=("Arial", 10), rowheight=35, background=BG_COLOR, fieldbackground=BG_COLOR, foreground=TEXT_PRIMARY, borderwidth=1, relief="solid", bordercolor=BORDER_COLOR)

    def fixed_map(option):
        return [elm for elm in style.map("Treeview", query_opt=option) if elm[:2] != ("!disabled", "!selected")]
    try:
        style.map("Bank.Treeview", foreground=fixed_map("foreground"), background=fixed_map("background"))
    except: pass

    style.map("Bank.Treeview", background=[("selected", BORDER_COLOR)], foreground=[("selected", "#ffffff")])

    cols = ("is_default", "alias", "name", "ac_name", "ac", "ifsc", "branch", "pan", "qr_status")
    sv.bank_tree = ttk.Treeview(tree_f, columns=cols, show="headings", height=8, style="Bank.Treeview")
    sv.bank_tree.heading("is_default", text="Default", anchor="center")
    sv.bank_tree.heading("alias", text="Alias", anchor="w")
    sv.bank_tree.heading("name", text="Bank Name", anchor="w")
    sv.bank_tree.heading("ac_name", text="A/C Name", anchor="w")
    sv.bank_tree.heading("ac", text="A/C Number", anchor="w")
    sv.bank_tree.heading("ifsc", text="IFSC", anchor="w")
    sv.bank_tree.heading("branch", text="Branch", anchor="w")
    sv.bank_tree.heading("pan", text="PAN", anchor="w")
    sv.bank_tree.heading("qr_status", text="QR", anchor="center")
    
    comp_id_val = getattr(sv, "comp_id", 1)
    try:
        import json
        conn = database.get_connection()
        c = conn.cursor()
        c.execute("SELECT setting_value FROM ui_settings WHERE setting_key=?", (f"bank_tab_cols_{comp_id_val}",))
        res = c.fetchone()
        conn.close()
        b_w = json.loads(res[0]) if res and res[0] else {}
    except:
        b_w = {}

    sv.bank_tree.column("is_default", width=b_w.get("is_default", 70), anchor="center", stretch=False)
    sv.bank_tree.column("alias", width=b_w.get("alias", 100))
    sv.bank_tree.column("name", width=b_w.get("name", 140))
    sv.bank_tree.column("ac_name", width=b_w.get("ac_name", 140))
    sv.bank_tree.column("ac", width=b_w.get("ac", 130))
    sv.bank_tree.column("ifsc", width=b_w.get("ifsc", 100))
    sv.bank_tree.column("branch", width=b_w.get("branch", 100))
    sv.bank_tree.column("pan", width=b_w.get("pan", 100))
    sv.bank_tree.column("qr_status", width=b_w.get("qr_status", 50), anchor="center", stretch=False)

    def save_bank_widths():
        new_w = {c: sv.bank_tree.column(c, "width") for c in sv.bank_tree["columns"]}
        try:
            # --- THE FIX: Use the secure gatekeeper to prevent ghost data and cross-company leaks ---
            database.save_ui_setting(f"bank_tab_cols_{comp_id_val}", json.dumps(new_w))
            # ----------------------------------------------------------------------------------------
        except: pass

    def on_bank_sep_drag(event):
        if sv.bank_tree.identify_region(event.x, event.y) == "separator":
            parent.after(50, save_bank_widths)

    sv.bank_tree.bind("<B1-Motion>", on_bank_sep_drag, add="+")
    sv.bank_tree.bind("<ButtonRelease-1>", lambda e: parent.after(50, save_bank_widths) if sv.bank_tree.identify_region(e.x, e.y) == "separator" else None, add="+")

    # --- THE FIX: Added Vertical Scrollbar ---
    tree_scroll = ttk.Scrollbar(tree_f, orient="vertical", command=sv.bank_tree.yview)
    sv.bank_tree.configure(yscrollcommand=tree_scroll.set)
    tree_scroll.pack(side="right", fill="y")
    sv.bank_tree.pack(side="left", fill="both", expand=True)

    sv.bank_tree.tag_configure("evenrow", background=BG_COLOR, foreground=TEXT_PRIMARY)
    sv.bank_tree.tag_configure("oddrow", background=CARD_BG, foreground=TEXT_PRIMARY)

    def new_refresh_bank_tree():
        if not hasattr(sv, 'bank_tree'): return
        for item in sv.bank_tree.get_children(): sv.bank_tree.delete(item)
        
        for idx, b in enumerate(sv.banks_list):
            def_val = "★ Yes" if b.get("is_default") else ""
            qr_val = "✅" if b.get("qr_path") else ""
            tag = "evenrow" if idx % 2 == 0 else "oddrow"
            sv.bank_tree.insert("", "end", values=(def_val, b.get("alias", ""), b.get("name", ""), b.get("ac_name", ""), b.get("ac", ""), b.get("ifsc", ""), b.get("branch", ""), b.get("pan", ""), qr_val), tags=(tag,))
            
        for i in range(len(sv.banks_list), 8):
            tag = "evenrow" if i % 2 == 0 else "oddrow"
            sv.bank_tree.insert("", "end", values=("", "", "", "", "", "", "", "", ""), tags=(tag, "empty"))
            
    sv.refresh_bank_tree = new_refresh_bank_tree
    sv.refresh_bank_tree()
    
    def prevent_dummy_select(event):
        for iid in sv.bank_tree.selection():
            if 'empty' in sv.bank_tree.item(iid, 'tags'):
                sv.bank_tree.selection_remove(iid)
    sv.bank_tree.bind("<<TreeviewSelect>>", prevent_dummy_select)