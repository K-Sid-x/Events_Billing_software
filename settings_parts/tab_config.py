import tkinter as tk
from tkinter import ttk
import os
import database

def build_config_tab(parent, sv):
    # The redundant global focus listener has been stripped out to prevent memory leaks.

    BG_COLOR = sv.theme["BG_COLOR"]
    CARD_BG = sv.theme["CARD_BG"]
    BORDER_COLOR = sv.theme["BORDER_COLOR"]
    TEXT_PRIMARY = sv.theme["TEXT_PRIMARY"]
    TEXT_SECONDARY = sv.theme["TEXT_SECONDARY"]
    ACCENT_GREEN = sv.theme["ACCENT_GREEN"]
    ACCENT_BLUE = sv.theme["ACCENT_BLUE"]
    ACCENT_RED = sv.theme["ACCENT_RED"]
    ACCENT_YELLOW = sv.theme["ACCENT_YELLOW"]
    HEADER_BG = sv.theme["HEADER_BG"]

    main_cvs = tk.Canvas(parent, bg=BG_COLOR, highlightthickness=0)
    sv.config_cvs = main_cvs 
    
    scroll_y = ttk.Scrollbar(parent, orient="vertical", command=main_cvs.yview)
    main_f = tk.Frame(main_cvs, bg=BG_COLOR)
    
    def on_frame_configure(e):
        main_cvs.configure(scrollregion=main_cvs.bbox("all"))
    main_f.bind("<Configure>", on_frame_configure)
    
    frame_window_id = main_cvs.create_window((0, 0), window=main_f, anchor="nw", width=parent.winfo_width() - 30)
    main_cvs.configure(yscrollcommand=scroll_y.set)
    
    main_cvs.pack(side="left", fill="both", expand=True, padx=10, pady=10)
    scroll_y.pack(side="right", fill="y")
    
    def on_canvas_configure(e):
        if e.widget == main_cvs:
            main_cvs.itemconfig(frame_window_id, width=e.width)
    main_cvs.bind("<Configure>", on_canvas_configure)

    # --- THE FIX: Smart Global Scroll Hijacker ---
    def fast_local_scroll(event):
        try:
            w_class = event.widget.winfo_class()
            if w_class in ('TCombobox', 'Listbox', 'Treeview'): 
                return # Let native widgets handle their own scroll
            
            delta = 0
            if hasattr(event, 'num'):
                if event.num == 4: delta = -1
                elif event.num == 5: delta = 1
            if hasattr(event, 'delta') and event.delta != 0:
                # --- THE FIX: Removed the *4 multiplier to match global scrolling ---
                delta = int(-1*(event.delta/120)) if os.name == 'nt' else int(-1*event.delta)
            
            if delta != 0:
                main_cvs.yview_scroll(delta, "units")
            return "break"
        except: pass

    def restore_global_scroll(event=None):
        try:
            sv.bind_all("<MouseWheel>", sv._on_mousewheel)
            sv.bind_all("<Button-4>", sv._on_mousewheel)
            sv.bind_all("<Button-5>", sv._on_mousewheel)
        except: pass

    def on_tab_changed(event):
        try:
            selected_tab = event.widget.select()
            tab_text = event.widget.tab(selected_tab, "text")
            
            if "Configuration" in tab_text:
                # Override the global scroll when this tab is active
                sv.bind_all("<MouseWheel>", fast_local_scroll)
                sv.bind_all("<Button-4>", fast_local_scroll)
                sv.bind_all("<Button-5>", fast_local_scroll)
            else:
                # Hand control back to settings.py when leaving
                restore_global_scroll()
        except: pass
        
    # Bind the listener to the Notebook tabs
    sv.notebook.bind("<<NotebookTabChanged>>", on_tab_changed, add="+")
    
    # --- THE FIX: Failsafe release when navigating away via sidebar ---
    main_cvs.bind("<Destroy>", restore_global_scroll, add="+")
    # ---------------------------------------------

    g_frame = tk.Frame(main_f, bg=CARD_BG, padx=40, pady=30, highlightbackground=BORDER_COLOR, highlightthickness=1)
    g_frame.pack(fill="x", padx=10, pady=10)

    tk.Label(g_frame, text="Global Configuration", font=("Arial", 18, "bold"), bg=CARD_BG, fg=TEXT_PRIMARY).pack(anchor="w", pady=(0, 5))
    tk.Label(g_frame, text="Changes made here will instantly apply across all new and existing invoices.", font=("Arial", 10), bg=CARD_BG, fg=TEXT_SECONDARY).pack(anchor="w", pady=(0, 20))

    form_f = tk.Frame(g_frame, bg=BG_COLOR, padx=20, pady=20, highlightbackground=BORDER_COLOR, highlightthickness=1)
    form_f.pack(fill="x", pady=(0, 20))

    tk.Label(form_f, text="Date Format:", font=("Arial", 11, "bold"), bg=BG_COLOR, fg=TEXT_PRIMARY).grid(row=0, column=0, sticky="w", pady=(10, 15))
    date_opts = ["DD.MM.YYYY", "DD-MM-YYYY", "DD/MM/YYYY", "YYYY-MM-DD", "MM/DD/YYYY"]
    cb_date = ttk.Combobox(form_f, textvariable=sv.date_format_var, values=date_opts, state="readonly", font=("Arial", 11), width=35)
    cb_date.grid(row=0, column=1, sticky="w", padx=20, pady=(10, 15))
    sv.protect_scroll(cb_date)

    tk.Label(form_f, text="Currency Format:", font=("Arial", 11, "bold"), bg=BG_COLOR, fg=TEXT_PRIMARY).grid(row=1, column=0, sticky="w", pady=(5, 10))
    curr_opts = [
        "Indian Rupees (₹ 10,00,000.00)", 
        "US Dollar ($ 1,000,000.00)", 
        "Euro (€ 1.000.000,00)", 
        "British Pound (£ 1,000,000.00)", 
        "Generic Number (1,000,000.00)"
    ]
    cb_curr = ttk.Combobox(form_f, textvariable=sv.currency_var, values=curr_opts, state="readonly", font=("Arial", 11), width=35)
    cb_curr.grid(row=1, column=1, sticky="w", padx=20, pady=(5, 10))
    sv.protect_scroll(cb_curr)

    tk.Button(g_frame, text="💾 Save Configuration", font=("Arial", 11, "bold"), bg=ACCENT_GREEN, fg="#ffffff", cursor="hand2", relief="flat", padx=20, pady=8, command=lambda: sv._save_to_db("Global Configuration Saved Successfully!")).pack(anchor="w", pady=5)

    s_frame = tk.Frame(main_f, bg=CARD_BG, padx=40, pady=30, highlightbackground=BORDER_COLOR, highlightthickness=1)
    s_frame.pack(fill="x", padx=10, pady=10)
    
    tk.Label(s_frame, text="Digital Signatures", font=("Arial", 18, "bold"), bg=CARD_BG, fg=TEXT_PRIMARY).pack(anchor="w", pady=(0, 5))
    tk.Label(s_frame, text="Add profiles and designate who is signing the invoice. (Placed in the bottom right).", font=("Arial", 10), bg=CARD_BG, fg=TEXT_SECONDARY).pack(anchor="w", pady=(0, 20))

    sig_f = tk.Frame(s_frame, bg=BG_COLOR, padx=20, pady=20, highlightbackground=BORDER_COLOR, highlightthickness=1)
    sig_f.pack(fill="x", pady=(0, 15))
    
    tk.Label(sig_f, text="Designation / Role:", font=("Arial", 10, "bold"), bg=BG_COLOR, fg=TEXT_PRIMARY).grid(row=0, column=0, sticky="w", pady=5)
    sig_form_f = tk.Frame(sig_f, bg=BG_COLOR)
    tk.Entry(sig_form_f, textvariable=sv.sig_role_var, font=("Arial", 11), width=30, bg=CARD_BG, fg=TEXT_PRIMARY, insertbackground=TEXT_PRIMARY).pack(side="left")
    sig_form_f.grid(row=0, column=1, sticky="w", padx=15, pady=5)
    
    tk.Label(sig_f, text="Signature Image (PNG):", font=("Arial", 10, "bold"), bg=BG_COLOR, fg=TEXT_PRIMARY).grid(row=1, column=0, sticky="w", pady=(10,5))
    path_f = tk.Frame(sig_f, bg=BG_COLOR)
    path_f.grid(row=1, column=1, sticky="w", padx=15, pady=(10,5))
    
    tk.Entry(path_f, textvariable=sv.sig_path_var, font=("Arial", 10), width=30, state="readonly", bg=CARD_BG, fg=TEXT_PRIMARY, readonlybackground=CARD_BG, highlightbackground=BORDER_COLOR, highlightthickness=1).pack(side="left", ipady=3)
    tk.Button(path_f, text="Browse", font=("Arial", 9, "bold"), bg=BORDER_COLOR, fg=TEXT_PRIMARY, cursor="hand2", relief="flat", command=sv.browse_sig).pack(side="left", padx=5)
    tk.Button(path_f, text="Clear", font=("Arial", 9), bg=CARD_BG, fg=TEXT_PRIMARY, cursor="hand2", relief="flat", command=lambda: sv.sig_path_var.set("")).pack(side="left", padx=5)
    
    tk.Button(sig_f, text="➕ Add Signature", font=("Arial", 10, "bold"), bg=ACCENT_BLUE, fg="#ffffff", cursor="hand2", relief="flat", padx=15, command=sv.save_sig).grid(row=2, column=1, sticky="w", padx=15, pady=(15,0))

    sv.sig_preview_cvs = tk.Canvas(sig_f, width=120, height=60, bg=BG_COLOR, highlightbackground=BORDER_COLOR, highlightthickness=1)
    sv.sig_preview_cvs.grid(row=0, column=2, rowspan=3, sticky="w", padx=(20, 0))
    sv.sig_preview_cvs.create_text(60, 30, text="Preview", font=("Arial", 8), fill=TEXT_SECONDARY)
    
    def update_sig_preview(*args):
        path = sv.sig_path_var.get()
        sv.sig_preview_cvs.delete("all")
        if path and os.path.exists(path):
            try:
                from PIL import Image, ImageTk
                img = Image.open(path)
                resample_filter = Image.Resampling.LANCZOS if hasattr(Image, 'Resampling') else Image.ANTIALIAS
                ratio = min(110/img.width, 50/img.height)
                new_w, new_h = int(img.width * ratio), int(img.height * ratio)
                img = img.resize((new_w, new_h), resample_filter)
                sv._cached_sig_preview = ImageTk.PhotoImage(img)
                sv.sig_preview_cvs.create_image(60, 30, image=sv._cached_sig_preview, anchor="center")
            except:
                sv.sig_preview_cvs.create_text(60, 30, text="Error", fill="red")
        else:
            sv.sig_preview_cvs.create_text(60, 30, text="Preview", font=("Arial", 8), fill=TEXT_SECONDARY)
            
        sv.after(100, lambda: main_cvs.configure(scrollregion=main_cvs.bbox("all")))

    sv.sig_path_var.trace_add("write", update_sig_preview)
    update_sig_preview()

    tree_ctrl = tk.Frame(s_frame, bg=CARD_BG)
    tree_ctrl.pack(fill="x", pady=(5, 5))
    tk.Button(tree_ctrl, text="❌ Delete", font=("Arial", 9, "bold"), bg=ACCENT_RED, fg="#ffffff", cursor="hand2", relief="flat", command=sv.delete_sig).pack(side="right")
    tk.Button(tree_ctrl, text="⭐ Set Default", font=("Arial", 9, "bold"), bg=ACCENT_YELLOW, fg=BG_COLOR, cursor="hand2", relief="flat", command=sv.set_default_sig).pack(side="right", padx=(0, 10))

    style = ttk.Style(sv)
    style.configure("Sig.Treeview.Heading", font=("Arial", 9, "bold"), background=HEADER_BG, foreground=TEXT_PRIMARY, relief="raised", borderwidth=1)
    # --- THE FIX: Map active heading state so it stays readable on hover ---
    style.map("Sig.Treeview.Heading", background=[('active', BORDER_COLOR)])
    style.configure("Sig.Treeview", font=("Arial", 10), rowheight=30, background=BG_COLOR, fieldbackground=BG_COLOR, foreground=TEXT_PRIMARY, borderwidth=1, relief="solid", bordercolor=BORDER_COLOR)

    def fixed_map(option):
        return [elm for elm in style.map("Treeview", query_opt=option) if elm[:2] != ("!disabled", "!selected")]
    try:
        style.map("Sig.Treeview", foreground=fixed_map("foreground"), background=fixed_map("background"))
    except: pass

    style.map("Sig.Treeview", background=[("selected", BORDER_COLOR)], foreground=[("selected", "#ffffff")])

    tree_wrap = tk.Frame(s_frame, bg=CARD_BG, highlightbackground=BORDER_COLOR, highlightthickness=1)
    tree_wrap.pack(fill="x")
    
    cols = ("is_default", "role", "path")
    sv.sig_tree = ttk.Treeview(tree_wrap, columns=cols, show="headings", height=4, style="Sig.Treeview")
    sv.sig_tree.heading("is_default", text="Default", anchor="center")
    sv.sig_tree.heading("role", text="Designation / Role", anchor="w")
    sv.sig_tree.heading("path", text="Image Path", anchor="w")

    comp_id_val = getattr(sv, "comp_id", 1)
    try:
        import json
        conn = database.get_connection()
        c = conn.cursor()
        c.execute("SELECT setting_value FROM ui_settings WHERE setting_key=?", (f"sig_tab_cols_{comp_id_val}",))
        res = c.fetchone()
        conn.close()
        s_w = json.loads(res[0]) if res and res[0] else {}
    except:
        s_w = {}

    sv.sig_tree.column("is_default", width=s_w.get("is_default", 70), anchor="center", stretch=False)
    sv.sig_tree.column("role", width=s_w.get("role", 200))
    sv.sig_tree.column("path", width=s_w.get("path", 350))

    def save_sig_widths():
        new_w = {c: sv.sig_tree.column(c, "width") for c in sv.sig_tree["columns"]}
        try:
            # --- THE FIX: Use the secure gatekeeper to prevent ghost data and cross-company leaks ---
            database.save_ui_setting(f"sig_tab_cols_{comp_id_val}", json.dumps(new_w))
            # ----------------------------------------------------------------------------------------
        except: pass

    def on_sig_sep_drag(event):
        if sv.sig_tree.identify_region(event.x, event.y) == "separator":
            parent.after(50, save_sig_widths)

    sv.sig_tree.bind("<B1-Motion>", on_sig_sep_drag, add="+")
    sv.sig_tree.bind("<ButtonRelease-1>", lambda e: parent.after(50, save_sig_widths) if sv.sig_tree.identify_region(e.x, e.y) == "separator" else None, add="+")
    
    tree_scroll = ttk.Scrollbar(tree_wrap, orient="vertical", command=sv.sig_tree.yview)
    sv.sig_tree.configure(yscrollcommand=tree_scroll.set)
    tree_scroll.pack(side="right", fill="y")
    sv.sig_tree.pack(side="left", fill="both", expand=True)

    sv.sig_tree.tag_configure("evenrow", background=BG_COLOR, foreground=TEXT_PRIMARY)
    sv.sig_tree.tag_configure("oddrow", background=CARD_BG, foreground=TEXT_PRIMARY)

    def new_refresh_sig_tree():
        if not hasattr(sv, 'sig_tree'): return
        for item in sv.sig_tree.get_children(): sv.sig_tree.delete(item)
        
        for idx, s in enumerate(sv.signatures_list):
            def_val = "★ Yes" if s.get("is_default") else ""
            tag = "evenrow" if idx % 2 == 0 else "oddrow"
            sv.sig_tree.insert("", "end", values=(def_val, s.get("role", ""), s.get("path", "")), tags=(tag,))
            
        for i in range(len(sv.signatures_list), 4):
            tag = "evenrow" if i % 2 == 0 else "oddrow"
            sv.sig_tree.insert("", "end", values=("", "", ""), tags=(tag, "empty"))
            
        sv.after(100, lambda: main_cvs.configure(scrollregion=main_cvs.bbox("all")))
            
    sv.refresh_sig_tree = new_refresh_sig_tree
    sv.refresh_sig_tree()
    
    def prevent_dummy_select_sig(event):
        for iid in sv.sig_tree.selection():
            if 'empty' in sv.sig_tree.item(iid, 'tags'):
                sv.sig_tree.selection_remove(iid)
    sv.sig_tree.bind("<<TreeviewSelect>>", prevent_dummy_select_sig)

    b_frame = tk.Frame(main_f, bg=CARD_BG, padx=40, pady=30, highlightbackground=BORDER_COLOR, highlightthickness=1)
    b_frame.pack(fill="x", padx=10, pady=10)

    tk.Label(b_frame, text="Backup & Restore", font=("Arial", 18, "bold"), bg=CARD_BG, fg=TEXT_PRIMARY).pack(anchor="w", pady=(0, 5))
    tk.Label(b_frame, text="Export your entire layout, colors, fonts, and bank settings to a JSON file.", font=("Arial", 10), bg=CARD_BG, fg=TEXT_SECONDARY).pack(anchor="w", pady=(0, 20))

    btn_f = tk.Frame(b_frame, bg=CARD_BG)
    btn_f.pack(fill="x", anchor="w")

    tk.Button(btn_f, text="⭳ Backup Settings", font=("Arial", 11, "bold"), bg=BORDER_COLOR, fg=TEXT_PRIMARY, cursor="hand2", relief="flat", padx=20, pady=8, command=sv.export_backup).pack(side="left", padx=(0, 15))
    tk.Button(btn_f, text="⭱ Restore Settings", font=("Arial", 11, "bold"), bg=BORDER_COLOR, fg=TEXT_PRIMARY, cursor="hand2", relief="flat", padx=20, pady=8, command=sv.import_backup).pack(side="left")