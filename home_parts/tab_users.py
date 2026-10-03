import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import hashlib
import json
import os
import sys
import shutil
import time
import database

try:
    from PIL import Image, ImageTk, ImageDraw
except ImportError:
    Image = ImageTk = ImageDraw = None

try:
    from settings_parts.interactive_cropper import InteractiveCropper
except ImportError:
    InteractiveCropper = None

SALT = "LedgerEvents_Secure_Salt_2026!"

ALL_SIDEBAR_ITEMS = [
    "Home", "Dashboard", "Parties", "Invoices", "Purchases", "Catalog",
    "Stock", "Balance Sheet", "Profit & Loss", "GST Report", "Expenses",
    "Employees", "Labours", "Settings"
]

def hash_password(password):
    return hashlib.sha256((password + SALT).encode('utf-8')).hexdigest()

def get_root_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def apply_adaptive_scrollbar_style(style, bg_col, border_col, text_col, accent_blue):
    """Applies Dark/Light UI adaptive styling to both Vertical and Horizontal scrollbars."""
    thumb_color = "#475569" if bg_col == "#0f172a" else "#94a3b8"
    style.configure(
        "Popup.Vertical.TScrollbar",
        background=thumb_color, troughcolor=bg_col,
        bordercolor=border_col, arrowcolor=text_col, relief="flat"
    )
    style.configure(
        "Popup.Horizontal.TScrollbar",
        background=thumb_color, troughcolor=bg_col,
        bordercolor=border_col, arrowcolor=text_col, relief="flat"
    )
    style.map("Popup.Vertical.TScrollbar", background=[("active", accent_blue)])
    style.map("Popup.Horizontal.TScrollbar", background=[("active", accent_blue)])


def open_user_form_popup(parent_win, theme, on_save_callback, edit_user_id=None):
    """Unified Profile Credentials + Company & Sidebar Access Control Window."""
    is_edit = edit_user_id is not None
    user_data = database.get_user_by_id(edit_user_id) if is_edit else None
    viewer_role = getattr(parent_win.winfo_toplevel(), "current_role", "Admin")
    is_master_admin = (is_edit and str(edit_user_id) == "1") or (viewer_role != "Admin")

    card_bg = theme.get("card", theme.get("bg", "#1e293b"))
    bg_col = theme.get("bg", "#0f172a")
    text_col = theme.get("text", "#f8fafc")
    sec_col = theme.get("sec", theme.get("text_sec", "#94a3b8"))
    border_col = theme.get("border", "#334155")
    accent_blue = theme.get("accent_blue", "#3b82f6")

    pop = tk.Toplevel(parent_win)
    pop.title("User Profile & Access Control" if is_edit else "Create User & Set Permissions")
    # --- THE FIX: Increased width from 1180 to 1280 ---
    pop.geometry("1280x650")
    pop.configure(bg=bg_col)
    pop.grab_set()

    pop.update_idletasks()
    x = int((pop.winfo_screenwidth() / 2) - (1280 / 2))
    y = int((pop.winfo_screenheight() / 2) - (650 / 2))
    pop.geometry(f"+{x}+{y}")

    # Style Combobox & Adaptive Scrollbars
    pop.option_add("*TCombobox*Listbox.background", card_bg)
    pop.option_add("*TCombobox*Listbox.foreground", text_col)
    pop.option_add("*TCombobox*Listbox.selectBackground", accent_blue)
    pop.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")

    style = ttk.Style(pop)
    apply_adaptive_scrollbar_style(style, bg_col, border_col, text_col, accent_blue)
    style.configure("Popup.TCombobox", fieldbackground=bg_col, background=card_bg, foreground=text_col, arrowcolor=text_col, bordercolor=border_col)
    style.map("Popup.TCombobox", fieldbackground=[("readonly", bg_col)], selectbackground=[("readonly", bg_col)], selectforeground=[("readonly", text_col)])

    # Determine Unique Display ID (fills deleted gaps automatically)
    if is_edit:
        disp_id = f"USR-{int(edit_user_id):03d}"
    else:
        existing_ids = {int(u[0]) for u in database.get_all_users()}
        next_id = 1
        while next_id in existing_ids:
            next_id += 1
        disp_id = f"USR-{next_id:03d}"

    # Load saved permissions
    saved_perms = {"companies": "all", "sidebars": list(ALL_SIDEBAR_ITEMS)}
    if is_edit and user_data and len(user_data) > 5 and user_data[5]:
        try:
            loaded = json.loads(user_data[5])
            if isinstance(loaded, dict):
                saved_perms.update(loaded)
        except Exception:
            pass

    # --- MAIN 2-COLUMN CONTAINER ---
    body = tk.Frame(pop, bg=bg_col, padx=20, pady=20)
    body.pack(fill="both", expand=True)

    # =========================================================================
    # LEFT PANEL: LARGER PROFILE PIC, USERNAME, PASSWORD & ROLE
    # =========================================================================
    left_card_outer = tk.Frame(body, bg=card_bg, width=340, highlightbackground=border_col, highlightthickness=1)
    left_card_outer.pack(side="left", fill="y", padx=(0, 15))
    left_card_outer.pack_propagate(False)

    # Pin the Save button frame to the bottom so it never scrolls out of view
    save_btn_frame = tk.Frame(left_card_outer, bg=card_bg, padx=20, pady=15)
    save_btn_frame.pack(side="bottom", fill="x")

    left_cvs = tk.Canvas(left_card_outer, bg=card_bg, highlightthickness=0)
    left_vscr = ttk.Scrollbar(left_card_outer, orient="vertical", command=left_cvs.yview, style="Popup.Vertical.TScrollbar")
    left_card = tk.Frame(left_cvs, bg=card_bg, padx=20, pady=20)

    left_cvs.create_window((0, 0), window=left_card, anchor="nw", width=315)
    left_cvs.configure(yscrollcommand=left_vscr.set)

    left_vscr.pack(side="right", fill="y")
    left_cvs.pack(side="left", fill="both", expand=True)

    tk.Label(left_card, text="Edit Profile" if is_edit else "New User", font=("Segoe UI", 15, "bold"), bg=card_bg, fg=text_col).pack(pady=(0, 2))
    tk.Label(left_card, text=f"Unique ID: {disp_id}", font=("Segoe UI", 10, "bold"), bg=card_bg, fg=accent_blue).pack(pady=(0, 10))

    pic_path_var = [user_data[4] if (user_data and len(user_data) > 4 and user_data[4]) else ""]
    pop.preview_img_ref = None

    # --- BIGGER 136x136 PROFILE PIC CIRCLE ---
    AVATAR_CANVAS_SIZE = 136
    AVATAR_CIRCLE_SIZE = 128
    AVATAR_CENTER = AVATAR_CANVAS_SIZE // 2

    preview_cvs = tk.Canvas(left_card, width=AVATAR_CANVAS_SIZE, height=AVATAR_CANVAS_SIZE, bg=card_bg, highlightthickness=0, cursor="hand2")
    preview_cvs.pack(pady=(0, 10))

    btn_upload = tk.Button(left_card, text="📷 Upload Profile Pic", font=("Segoe UI", 9, "bold"), bg=bg_col, fg=text_col, relief="solid", bd=1, cursor="hand2", padx=12, pady=4)
    btn_upload.pack(pady=(0, 14))

    def render_avatar_preview():
        preview_cvs.delete("all")
        path = pic_path_var[0]
        has_img = False

        if path and os.path.exists(path) and Image:
            try:
                img = Image.open(path).convert("RGBA")
                resamp = Image.Resampling.LANCZOS if hasattr(Image, 'Resampling') else Image.LANCZOS
                img = img.resize((AVATAR_CIRCLE_SIZE, AVATAR_CIRCLE_SIZE), resamp)

                scale = 4
                mask = Image.new("L", (AVATAR_CIRCLE_SIZE * scale, AVATAR_CIRCLE_SIZE * scale), 0)
                draw = ImageDraw.Draw(mask)
                draw.ellipse((0, 0, AVATAR_CIRCLE_SIZE * scale, AVATAR_CIRCLE_SIZE * scale), fill=255)
                mask = mask.resize((AVATAR_CIRCLE_SIZE, AVATAR_CIRCLE_SIZE), resamp)

                output = Image.new("RGBA", (AVATAR_CIRCLE_SIZE, AVATAR_CIRCLE_SIZE), (0, 0, 0, 0))
                output.paste(img, (0, 0), mask)

                pop.preview_img_ref = ImageTk.PhotoImage(output)
                preview_cvs.create_image(AVATAR_CENTER, AVATAR_CENTER, image=pop.preview_img_ref, anchor="center")
                btn_upload.config(text="📷 Change Profile Pic")
                has_img = True
            except Exception:
                pass

        if not has_img:
            if Image:
                scale = 4
                circ = Image.new("RGBA", (AVATAR_CIRCLE_SIZE * scale, AVATAR_CIRCLE_SIZE * scale), (0, 0, 0, 0))
                draw = ImageDraw.Draw(circ)
                draw.ellipse((0, 0, AVATAR_CIRCLE_SIZE * scale - 1, AVATAR_CIRCLE_SIZE * scale - 1), fill=bg_col, outline=border_col, width=10)
                resamp = Image.Resampling.LANCZOS if hasattr(Image, 'Resampling') else Image.LANCZOS
                circ = circ.resize((AVATAR_CIRCLE_SIZE, AVATAR_CIRCLE_SIZE), resamp)
                pop.preview_img_ref = ImageTk.PhotoImage(circ)
                preview_cvs.create_image(AVATAR_CENTER, AVATAR_CENTER, image=pop.preview_img_ref, anchor="center")
            else:
                preview_cvs.create_oval(4, 4, AVATAR_CANVAS_SIZE - 4, AVATAR_CANVAS_SIZE - 4, fill=bg_col, outline=border_col, width=2)
            preview_cvs.create_text(AVATAR_CENTER, AVATAR_CENTER, text="No Photo", font=("Segoe UI", 11, "bold"), fill=sec_col)
            btn_upload.config(text="📷 Upload Profile Pic")

    temp_crops = []

    def cleanup_unsaved_crops():
        for tc in temp_crops:
            if tc and os.path.exists(tc) and ("cropped_" in os.path.basename(tc) or "temp" in os.path.basename(tc)):
                try:
                    os.remove(tc)
                except Exception:
                    pass

    def on_popup_close():
        cleanup_unsaved_crops()
        pop.destroy()

    pop.protocol("WM_DELETE_WINDOW", on_popup_close)

    def choose_photo():
        path = filedialog.askopenfilename(title="Select Profile Picture", filetypes=[("Image Files", "*.png;*.jpg;*.jpeg")], parent=pop)
        if path:
            if InteractiveCropper:
                def on_cropped(cropped_path):
                    cleanup_unsaved_crops()
                    temp_crops.append(cropped_path)
                    pic_path_var[0] = cropped_path
                    render_avatar_preview()
                InteractiveCropper(pop, path, on_cropped)
            else:
                pic_path_var[0] = path
                render_avatar_preview()

    btn_upload.config(command=choose_photo)
    preview_cvs.bind("<Button-1>", lambda e: choose_photo())
    render_avatar_preview()

    tk.Frame(left_card, height=1, bg=border_col).pack(fill="x", pady=(0, 10))

    tk.Label(left_card, text="Username *", font=("Segoe UI", 9, "bold"), bg=card_bg, fg=sec_col).pack(anchor="w")
    user_var = tk.StringVar(value=user_data[1] if user_data else "")
    tk.Entry(left_card, textvariable=user_var, font=("Segoe UI", 11), bg=bg_col, fg=text_col, insertbackground=text_col, highlightbackground=border_col, highlightthickness=1, relief="flat").pack(fill="x", pady=(3, 10), ipady=5)

    pwd_label = "New Password (blank = keep current)" if is_edit else "Password *"
    tk.Label(left_card, text=pwd_label, font=("Segoe UI", 9, "bold"), bg=card_bg, fg=sec_col).pack(anchor="w")
    pass_var = tk.StringVar()
    tk.Entry(left_card, textvariable=pass_var, font=("Segoe UI", 11), show="●", bg=bg_col, fg=text_col, insertbackground=text_col, highlightbackground=border_col, highlightthickness=1, relief="flat").pack(fill="x", pady=(3, 10), ipady=5)

    tk.Label(left_card, text="Role *", font=("Segoe UI", 9, "bold"), bg=card_bg, fg=sec_col).pack(anchor="w")
    initial_role = user_data[3] if user_data else "Manager"
    role_var = tk.StringVar(value=initial_role)

    cb_role = ttk.Combobox(left_card, textvariable=role_var, values=["Manager", "Staff", "Custom"], state="readonly", font=("Segoe UI", 11), style="Popup.TCombobox")
    cb_role.pack(fill="x", pady=(3, 12), ipady=4)

    if is_master_admin:
        role_var.set("Admin")
        cb_role.config(state="disabled")
    elif initial_role not in ["Manager", "Staff"]:
        cb_role.config(state="normal")

    # --- THE FIX: Add Security Question Fields for Master Admin ---
    q_var = tk.StringVar()
    ans_var = tk.StringVar()

    if is_master_admin:
        conn = database.get_connection()
        c = conn.cursor()
        c.execute("SELECT setting_value FROM ui_settings WHERE setting_key='admin_sec_q'")
        q_row = c.fetchone()
        conn.close()
        current_q = q_row[0] if q_row else "What was the name of your first pet?"
        q_var.set(current_q)

        tk.Frame(left_card, height=1, bg=border_col).pack(fill="x", pady=(5, 10))
        tk.Label(left_card, text="Security Question (Recovery):", font=("Segoe UI", 9, "bold"), bg=card_bg, fg=sec_col).pack(anchor="w")
        q_cb = ttk.Combobox(left_card, textvariable=q_var, values=["What was the name of your first pet?", "What is your mother's maiden name?", "What city were you born in?", "What is the name of your favorite teacher?", "What was your childhood nickname?"], state="readonly", font=("Segoe UI", 10), style="Popup.TCombobox")
        q_cb.pack(fill="x", pady=(3, 10), ipady=3)

        tk.Label(left_card, text="New Answer (blank = keep current):", font=("Segoe UI", 9, "bold"), bg=card_bg, fg=sec_col).pack(anchor="w")
        tk.Entry(left_card, textvariable=ans_var, font=("Segoe UI", 11), show="●", bg=bg_col, fg=text_col, insertbackground=text_col, highlightbackground=border_col, highlightthickness=1, relief="flat").pack(fill="x", pady=(3, 10), ipady=4)
    # --------------------------------------------------------------

    # =========================================================================
    # RIGHT PANEL: COMPANY ACCESS & SIDEBAR ACCESS (WITH BOTTOM SCROLLBARS)
    # =========================================================================
    right_card = tk.Frame(body, bg=card_bg, padx=25, pady=20, highlightbackground=border_col, highlightthickness=1)
    right_card.pack(side="left", fill="both", expand=True)

    tk.Label(right_card, text="🔐 Access Permissions Matrix", font=("Segoe UI", 15, "bold"), bg=card_bg, fg=text_col).pack(anchor="w")
    sub_msg = "👑 Master Admin has permanent full access to all companies and sidebars." if is_master_admin else "Choose which companies and sidebar tabs this user can access."
    tk.Label(right_card, text=sub_msg, font=("Segoe UI", 9, "bold"), bg=card_bg, fg="#10b981" if is_master_admin else sec_col).pack(anchor="w", pady=(2, 12))

    # 3-Column Grid: Allowed Companies | Sidebar Tabs | Tab Rules
    matrix_split = tk.Frame(right_card, bg=card_bg)
    matrix_split.pack(fill="both", expand=True)
    matrix_split.grid_columnconfigure(0, weight=1, uniform="matrix_cols")
    matrix_split.grid_columnconfigure(1, weight=1, uniform="matrix_cols")
    matrix_split.grid_columnconfigure(2, weight=1, uniform="matrix_cols")
    matrix_split.grid_rowconfigure(0, weight=1)

    # --- COLUMN 1: ALLOWED COMPANIES ---
    comp_box = tk.Frame(matrix_split, bg=bg_col, padx=12, pady=12, highlightbackground=border_col, highlightthickness=1)
    comp_box.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

    comp_hdr = tk.Frame(comp_box, bg=bg_col)
    comp_hdr.pack(fill="x", pady=(0, 8))

    all_companies = database.get_all_companies(ignore_permissions=True)
    comp_vars = {}

    def toggle_all_comps(state=True):
        if is_master_admin:
            return
        for v in comp_vars.values():
            v.set(1 if state else 0)

    # Pack All/None buttons FIRST so they never get squashed by the label
    if not is_master_admin:
        tk.Button(
            comp_hdr, text="None", font=("Segoe UI", 8, "bold"),
            bg=card_bg, fg=text_col, activebackground=border_col, activeforeground="#ffffff",
            relief="solid", bd=1, cursor="hand2", padx=10, pady=2,
            command=lambda: toggle_all_comps(False)
        ).pack(side="right", padx=(6, 0))
        tk.Button(
            comp_hdr, text="All", font=("Segoe UI", 8, "bold"),
            bg=accent_blue, fg="#ffffff", activebackground=accent_blue, activeforeground="#ffffff",
            relief="flat", bd=0, cursor="hand2", padx=12, pady=3,
            command=lambda: toggle_all_comps(True)
        ).pack(side="right")

    tk.Label(comp_hdr, text="🏢 Allowed Companies", font=("Segoe UI", 10, "bold"), bg=bg_col, fg=text_col).pack(side="left")

    tk.Frame(comp_box, height=1, bg=border_col).pack(fill="x", pady=(0, 6))

    comp_scroll_area = tk.Frame(comp_box, bg=bg_col)
    comp_scroll_area.pack(fill="both", expand=True)

    comp_cvs = tk.Canvas(comp_scroll_area, bg=bg_col, highlightthickness=0, width=100)
    comp_vscr = ttk.Scrollbar(comp_scroll_area, orient="vertical", command=comp_cvs.yview, style="Popup.Vertical.TScrollbar")
    comp_hscr = ttk.Scrollbar(comp_box, orient="horizontal", command=comp_cvs.xview, style="Popup.Horizontal.TScrollbar")
    comp_inner = tk.Frame(comp_cvs, bg=bg_col)

    comp_cvs.create_window((0, 0), window=comp_inner, anchor="nw")
    comp_cvs.configure(yscrollcommand=comp_vscr.set, xscrollcommand=comp_hscr.set)

    comp_vscr.pack(side="right", fill="y")
    comp_cvs.pack(side="left", fill="both", expand=True)
    comp_hscr.pack(side="bottom", fill="x", pady=(4, 0))

    saved_comp_list = saved_perms.get("companies", "all")
    for c_row in all_companies:
        cid, cname, cgst = c_row[0], c_row[1], c_row[8]
        badge = "GST" if cgst == 1 else "Non-GST"
        is_checked = True if (is_master_admin or saved_comp_list == "all" or int(cid) in [int(x) for x in saved_comp_list]) else False
        var = tk.IntVar(value=1 if is_checked else 0)
        comp_vars[int(cid)] = var

        cb = tk.Checkbutton(
            comp_inner, text=f"{cname} ({badge})", variable=var,
            font=("Segoe UI", 9, "bold"), bg=bg_col, fg=text_col,
            selectcolor=card_bg, activebackground=bg_col, activeforeground=text_col,
            anchor="w", cursor="hand2"
        )
        if is_master_admin:
            cb.config(state="disabled")
        cb.pack(fill="x", pady=2, anchor="nw")

    if not all_companies:
        tk.Label(comp_inner, text="No companies created yet.", font=("Segoe UI", 9), bg=bg_col, fg=sec_col).pack(pady=10, anchor="nw")

    # --- COLUMN 2: ALLOWED SIDEBAR TABS ---
    side_box = tk.Frame(matrix_split, bg=bg_col, padx=12, pady=12, highlightbackground=border_col, highlightthickness=1)
    side_box.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

    side_hdr = tk.Frame(side_box, bg=bg_col)
    side_hdr.pack(fill="x", pady=(0, 8))

    sidebar_vars = {}

    def toggle_all_sidebars(state=True):
        if is_master_admin:
            return
        for k, v in sidebar_vars.items():
            v.set(1 if (k == "Home" or state) else 0)
        render_rules_for_tab(active_rule_tab[0])

    # Pack All/None buttons FIRST so they never get squashed by the label
    if not is_master_admin:
        tk.Button(
            side_hdr, text="None", font=("Segoe UI", 8, "bold"),
            bg=card_bg, fg=text_col, activebackground=border_col, activeforeground="#ffffff",
            relief="solid", bd=1, cursor="hand2", padx=10, pady=2,
            command=lambda: toggle_all_sidebars(False)
        ).pack(side="right", padx=(6, 0))
        tk.Button(
            side_hdr, text="All", font=("Segoe UI", 8, "bold"),
            bg=accent_blue, fg="#ffffff", activebackground=accent_blue, activeforeground="#ffffff",
            relief="flat", bd=0, cursor="hand2", padx=12, pady=3,
            command=lambda: toggle_all_sidebars(True)
        ).pack(side="right")

    tk.Label(side_hdr, text="📑 Sidebar Tabs", font=("Segoe UI", 10, "bold"), bg=bg_col, fg=text_col).pack(side="left")

    tk.Frame(side_box, height=1, bg=border_col).pack(fill="x", pady=(0, 6))

    side_scroll_area = tk.Frame(side_box, bg=bg_col)
    side_scroll_area.pack(fill="both", expand=True)

    side_cvs = tk.Canvas(side_scroll_area, bg=bg_col, highlightthickness=0, width=100)
    side_vscr = ttk.Scrollbar(side_scroll_area, orient="vertical", command=side_cvs.yview, style="Popup.Vertical.TScrollbar")
    side_hscr = ttk.Scrollbar(side_box, orient="horizontal", command=side_cvs.xview, style="Popup.Horizontal.TScrollbar")
    side_inner = tk.Frame(side_cvs, bg=bg_col)

    side_cvs.create_window((0, 0), window=side_inner, anchor="nw")
    side_cvs.configure(yscrollcommand=side_vscr.set, xscrollcommand=side_hscr.set)

    side_vscr.pack(side="right", fill="y")
    side_cvs.pack(side="left", fill="both", expand=True)
    side_hscr.pack(side="bottom", fill="x", pady=(4, 0))

    # Load saved Invoice & Party Action Rules for this user
    saved_inv_rules = saved_perms.get("invoice_rules", {}) if isinstance(saved_perms.get("invoice_rules"), dict) else {}
    inv_same_day_var = tk.IntVar(value=1 if saved_inv_rules.get("same_day_only", False) else 0)
    inv_max_past_edits_var = tk.StringVar(value=str(saved_inv_rules.get("max_past_edits", 1)))
    inv_limit_edits_var = tk.IntVar(value=1 if saved_inv_rules.get("limit_edits", False) else 0)
    inv_max_edits_var = tk.StringVar(value=str(saved_inv_rules.get("max_edits", 2)))

    saved_party_rules = saved_perms.get("party_rules", {}) if isinstance(saved_perms.get("party_rules"), dict) else {}
    party_lock_ob_var = tk.IntVar(value=1 if saved_party_rules.get("lock_opening_balance", False) else 0)
    party_block_waive_var = tk.IntVar(value=1 if saved_party_rules.get("block_waive_off", False) else 0)
    inv_lock_past_pay_var = tk.IntVar(
        value=1 if (saved_inv_rules.get("lock_past_payments", False) or saved_party_rules.get("lock_past_payments", False)) else 0
    )

    saved_exp_rules = saved_perms.get("expense_rules", {}) if isinstance(saved_perms.get("expense_rules"), dict) else {}
    exp_same_day_var = tk.IntVar(value=1 if saved_exp_rules.get("same_day_only", False) else 0)
    exp_max_past_edits_var = tk.StringVar(value=str(saved_exp_rules.get("max_past_edits", 1)))
    exp_limit_edits_var = tk.IntVar(value=1 if saved_exp_rules.get("limit_edits", False) else 0)
    exp_max_edits_var = tk.StringVar(value=str(saved_exp_rules.get("max_edits", 2)))
    exp_block_del_var = tk.IntVar(value=1 if saved_exp_rules.get("block_delete", False) else 0)

    saved_purch_rules = saved_perms.get("purchase_rules", {}) if isinstance(saved_perms.get("purchase_rules"), dict) else {}
    purch_same_day_var = tk.IntVar(value=1 if saved_purch_rules.get("same_day_only", False) else 0)
    purch_max_past_edits_var = tk.StringVar(value=str(saved_purch_rules.get("max_past_edits", 1)))
    purch_limit_edits_var = tk.IntVar(value=1 if saved_purch_rules.get("limit_edits", False) else 0)
    purch_max_edits_var = tk.StringVar(value=str(saved_purch_rules.get("max_edits", 2)))
    purch_block_del_var = tk.IntVar(value=1 if saved_purch_rules.get("block_delete", False) else 0)

    saved_cat_rules = saved_perms.get("catalog_rules", {}) if isinstance(saved_perms.get("catalog_rules"), dict) else {}
    cat_lock_edit_var = tk.IntVar(value=1 if saved_cat_rules.get("lock_edit", False) else 0)
    cat_lock_del_var = tk.IntVar(value=1 if saved_cat_rules.get("lock_delete", False) else 0)

    saved_stock_rules = saved_perms.get("stock_rules", {}) if isinstance(saved_perms.get("stock_rules"), dict) else {}
    stock_lock_adj_var = tk.IntVar(value=1 if saved_stock_rules.get("lock_adjustments", False) else 0)
    stock_lock_del_var = tk.IntVar(value=1 if saved_stock_rules.get("lock_delete", False) else 0)
    stock_hide_vals_var = tk.IntVar(value=1 if saved_stock_rules.get("hide_financials", False) else 0)

    saved_emp_rules = saved_perms.get("employee_rules", {}) if isinstance(saved_perms.get("employee_rules"), dict) else {}
    emp_lock_pay_var = tk.IntVar(value=1 if saved_emp_rules.get("lock_payroll", False) else 0)
    emp_lock_del_var = tk.IntVar(value=1 if saved_emp_rules.get("lock_delete", False) else 0)
    emp_hide_vals_var = tk.IntVar(value=1 if saved_emp_rules.get("hide_financials", False) else 0)

    saved_labour_rules = saved_perms.get("labour_rules", {}) if isinstance(saved_perms.get("labour_rules"), dict) else {}
    labour_lock_pay_var = tk.IntVar(value=1 if saved_labour_rules.get("lock_payroll", False) else 0)
    labour_lock_del_var = tk.IntVar(value=1 if saved_labour_rules.get("lock_delete", False) else 0)
    labour_hide_vals_var = tk.IntVar(value=1 if saved_labour_rules.get("hide_financials", False) else 0)

    # --- THE FIX: Load GST Tab Rules ---
    saved_gst_rules = saved_perms.get("gst_rules", {}) if isinstance(saved_perms.get("gst_rules"), dict) else {}
    gst_lock_ca_submit_var = tk.IntVar(value=1 if saved_gst_rules.get("lock_ca_submit", False) else 0)
    gst_lock_ca_undo_var = tk.IntVar(value=1 if saved_gst_rules.get("lock_ca_undo", False) else 0)
    gst_lock_export_var = tk.IntVar(value=1 if saved_gst_rules.get("lock_export", False) else 0)
    # -----------------------------------

    # --- COLUMN 3: TAB RULES WINDOW (3RD SIDE PANEL) ---
    rules_box = tk.Frame(matrix_split, bg=bg_col, padx=12, pady=12, highlightbackground=border_col, highlightthickness=1)
    rules_box.grid(row=0, column=2, sticky="nsew", padx=(8, 0))

    rules_hdr = tk.Frame(rules_box, bg=bg_col)
    rules_hdr.pack(fill="x", pady=(0, 8))

    rules_title_lbl = tk.Label(rules_hdr, text="⚙️ Tab Rules: Invoices", font=("Segoe UI", 10, "bold"), bg=bg_col, fg=text_col)
    rules_title_lbl.pack(side="left")

    tk.Frame(rules_box, height=1, bg=border_col).pack(fill="x", pady=(0, 8))

    rules_body = tk.Frame(rules_box, bg=bg_col)
    rules_body.pack(fill="both", expand=True)

    active_rule_tab = ["Invoices"]
    tab_row_frames = {}

    def render_rules_for_tab(tab_name):
        active_rule_tab[0] = tab_name
        rules_title_lbl.config(text=f"⚙️ Rules: {tab_name}")

        # Highlight selected row in Sidebar Tabs column
        for t_key, (r_frame, r_cb, r_lbl, r_arrow) in tab_row_frames.items():
            if t_key == tab_name:
                r_frame.config(bg=card_bg)
                r_cb.config(bg=card_bg, activebackground=card_bg)
                r_lbl.config(bg=card_bg)
                r_arrow.config(bg=card_bg, fg=accent_blue, text="▶")
            else:
                r_frame.config(bg=bg_col)
                r_cb.config(bg=bg_col, activebackground=bg_col)
                r_lbl.config(bg=bg_col)
                r_arrow.config(bg=bg_col, fg=sec_col, text="›")

        for child in rules_body.winfo_children():
            child.destroy()

        if is_master_admin:
            tk.Label(
                rules_body, text="👑 Master Admin has unrestricted access to all actions in every tab.",
                font=("Segoe UI", 9), bg=bg_col, fg="#10b981", wraplength=210, justify="left"
            ).pack(anchor="w", pady=10)
            return

        if sidebar_vars.get(tab_name) and sidebar_vars[tab_name].get() == 0:
            tk.Label(
                rules_body, text=f"🔒 '{tab_name}' tab is currently unchecked.\n\nTick '{tab_name}' in Sidebar Tabs to configure its rules.",
                font=("Segoe UI", 9), bg=bg_col, fg=sec_col, wraplength=210, justify="left"
            ).pack(anchor="w", pady=10)
            return

        if tab_name == "Invoices":
            tk.Label(
                rules_body, text="Control what this user can do inside Invoices:",
                font=("Segoe UI", 8, "bold"), bg=bg_col, fg=sec_col, wraplength=215, justify="left"
            ).pack(anchor="w", pady=(0, 10))

            # Rule 1: Limit Past Days' Bill Edits
            tk.Checkbutton(
                rules_body, text="Limit Past Days' Bill Edits",
                variable=inv_same_day_var, font=("Segoe UI", 9, "bold"),
                bg=bg_col, fg=text_col, selectcolor=card_bg,
                activebackground=bg_col, activeforeground=text_col,
                anchor="w", justify="left", cursor="hand2", wraplength=210
            ).pack(fill="x", pady=(2, 4), anchor="w")

            past_spin_row = tk.Frame(rules_body, bg=bg_col)
            past_spin_row.pack(fill="x", padx=(22, 0), pady=(0, 10))
            tk.Label(past_spin_row, text="Max Edits:", font=("Segoe UI", 8, "bold"), bg=bg_col, fg=sec_col).pack(side="left")
            tk.Spinbox(
                past_spin_row, from_=0, to=20, textvariable=inv_max_past_edits_var,
                width=4, font=("Segoe UI", 9, "bold"), justify="center",
                bg=card_bg, fg=text_col, buttonbackground=border_col,
                insertbackground=text_col, relief="solid", bd=1
            ).pack(side="left", padx=6, ipady=1)
            tk.Label(past_spin_row, text="total (0=Lock)", font=("Segoe UI", 8), bg=bg_col, fg=sec_col).pack(side="left")

            # Rule 2: Limit Today's Bill Edits
            tk.Checkbutton(
                rules_body, text="Limit Today's Bill Edits",
                variable=inv_limit_edits_var, font=("Segoe UI", 9, "bold"),
                bg=bg_col, fg=text_col, selectcolor=card_bg,
                activebackground=bg_col, activeforeground=text_col,
                anchor="w", cursor="hand2", wraplength=210
            ).pack(fill="x", pady=(2, 4), anchor="w")

            spin_row = tk.Frame(rules_body, bg=bg_col)
            spin_row.pack(fill="x", padx=(22, 0), pady=(0, 10))
            tk.Label(spin_row, text="Max Edits:", font=("Segoe UI", 8, "bold"), bg=bg_col, fg=sec_col).pack(side="left")
            tk.Spinbox(
                spin_row, from_=0, to=20, textvariable=inv_max_edits_var,
                width=4, font=("Segoe UI", 9, "bold"), justify="center",
                bg=card_bg, fg=text_col, buttonbackground=border_col,
                insertbackground=text_col, relief="solid", bd=1
            ).pack(side="left", padx=6, ipady=1)
            tk.Label(spin_row, text="/ day", font=("Segoe UI", 8), bg=bg_col, fg=sec_col).pack(side="left")

            # Rule 3: Lock Past Days' Payment Deletions
            tk.Checkbutton(
                rules_body, text="Lock Past Days' Payment Deletions",
                variable=inv_lock_past_pay_var, font=("Segoe UI", 9, "bold"),
                bg=bg_col, fg="#ef4444", selectcolor=card_bg,
                activebackground=bg_col, activeforeground="#ef4444",
                anchor="w", justify="left", cursor="hand2", wraplength=210
            ).pack(fill="x", pady=(2, 8), anchor="w")

            tk.Label(
                rules_body,
                text="ℹ️ Note: Non-Admin users can move bills to the Recycle Bin, but permanent deletion is locked to Admin only.",
                font=("Segoe UI", 8), bg=bg_col, fg=sec_col,
                wraplength=210, justify="left"
            ).pack(anchor="w", pady=(6, 0))
        elif tab_name == "Parties":
            tk.Label(
                rules_body, text="Control what this user can do inside Parties:",
                font=("Segoe UI", 8, "bold"), bg=bg_col, fg=sec_col, wraplength=215, justify="left"
            ).pack(anchor="w", pady=(0, 10))

            # Rule 1: Lock Opening Balance Edits on Existing Parties
            tk.Checkbutton(
                rules_body, text="Lock Opening Balance on Existing Parties",
                variable=party_lock_ob_var, font=("Segoe UI", 9, "bold"),
                bg=bg_col, fg=text_col, selectcolor=card_bg,
                activebackground=bg_col, activeforeground=text_col,
                anchor="w", justify="left", cursor="hand2", wraplength=210
            ).pack(fill="x", pady=(2, 8), anchor="w")

            # Rule 2: Block Waiving / Write-Offs in Party Ledger
            tk.Checkbutton(
                rules_body, text="Block Waiving / Write-Offs in Ledger",
                variable=party_block_waive_var, font=("Segoe UI", 9, "bold"),
                bg=bg_col, fg="#ef4444", selectcolor=card_bg,
                activebackground=bg_col, activeforeground="#ef4444",
                anchor="w", justify="left", cursor="hand2", wraplength=210
            ).pack(fill="x", pady=(2, 8), anchor="w")

            # Rule 3: Lock Past Days' Payment Deletions
            tk.Checkbutton(
                rules_body, text="Lock Past Days' Payment Deletions",
                variable=inv_lock_past_pay_var, font=("Segoe UI", 9, "bold"),
                bg=bg_col, fg="#ef4444", selectcolor=card_bg,
                activebackground=bg_col, activeforeground="#ef4444",
                anchor="w", justify="left", cursor="hand2", wraplength=210
            ).pack(fill="x", pady=(2, 8), anchor="w")

            tk.Label(
                rules_body,
                text="ℹ️ Note: Deleting parties is permanently locked to Admin only.",
                font=("Segoe UI", 8), bg=bg_col, fg=sec_col,
                wraplength=210, justify="left"
            ).pack(anchor="w", pady=(6, 0))
        elif tab_name == "Expenses":
            tk.Label(
                rules_body, text="Control what this user can do inside Expenses:",
                font=("Segoe UI", 8, "bold"), bg=bg_col, fg=sec_col, wraplength=215, justify="left"
            ).pack(anchor="w", pady=(0, 10))

            # Rule 1: Limit Past Days' Expense Edits & Deletions
            tk.Checkbutton(
                rules_body, text="Limit Past Days' Expense Edits",
                variable=exp_same_day_var, font=("Segoe UI", 9, "bold"),
                bg=bg_col, fg=text_col, selectcolor=card_bg,
                activebackground=bg_col, activeforeground=text_col,
                anchor="w", justify="left", cursor="hand2", wraplength=210
            ).pack(fill="x", pady=(2, 4), anchor="w")

            exp_past_spin = tk.Frame(rules_body, bg=bg_col)
            exp_past_spin.pack(fill="x", padx=(22, 0), pady=(0, 10))
            tk.Label(exp_past_spin, text="Max Edits:", font=("Segoe UI", 8, "bold"), bg=bg_col, fg=sec_col).pack(side="left")
            tk.Spinbox(
                exp_past_spin, from_=0, to=20, textvariable=exp_max_past_edits_var,
                width=4, font=("Segoe UI", 9, "bold"), justify="center",
                bg=card_bg, fg=text_col, buttonbackground=border_col,
                insertbackground=text_col, relief="solid", bd=1
            ).pack(side="left", padx=6, ipady=1)
            tk.Label(exp_past_spin, text="total (0=Lock)", font=("Segoe UI", 8), bg=bg_col, fg=sec_col).pack(side="left")

            # Rule 2: Limit Today's Expense Edits
            tk.Checkbutton(
                rules_body, text="Limit Today's Expense Edits",
                variable=exp_limit_edits_var, font=("Segoe UI", 9, "bold"),
                bg=bg_col, fg=text_col, selectcolor=card_bg,
                activebackground=bg_col, activeforeground=text_col,
                anchor="w", cursor="hand2", wraplength=210
            ).pack(fill="x", pady=(2, 4), anchor="w")

            exp_today_spin = tk.Frame(rules_body, bg=bg_col)
            exp_today_spin.pack(fill="x", padx=(22, 0), pady=(0, 10))
            tk.Label(exp_today_spin, text="Max Edits:", font=("Segoe UI", 8, "bold"), bg=bg_col, fg=sec_col).pack(side="left")
            tk.Spinbox(
                exp_today_spin, from_=0, to=20, textvariable=exp_max_edits_var,
                width=4, font=("Segoe UI", 9, "bold"), justify="center",
                bg=card_bg, fg=text_col, buttonbackground=border_col,
                insertbackground=text_col, relief="solid", bd=1
            ).pack(side="left", padx=6, ipady=1)
            tk.Label(exp_today_spin, text="/ day", font=("Segoe UI", 8), bg=bg_col, fg=sec_col).pack(side="left")

            # Rule 3: Lock All Expense Deletions
            tk.Checkbutton(
                rules_body, text="Lock Deleting Expenses (Admin Only)",
                variable=exp_block_del_var, font=("Segoe UI", 9, "bold"),
                bg=bg_col, fg="#ef4444", selectcolor=card_bg,
                activebackground=bg_col, activeforeground="#ef4444",
                anchor="w", justify="left", cursor="hand2", wraplength=210
            ).pack(fill="x", pady=(2, 8), anchor="w")

            tk.Label(
                rules_body,
                text="ℹ️ Note: When 'Limit Past Days' Expense Edits' is ticked, past days' expenses also cannot be deleted or bulk-reassigned by non-Admins.",
                font=("Segoe UI", 8), bg=bg_col, fg=sec_col,
                wraplength=210, justify="left"
            ).pack(anchor="w", pady=(4, 0))
        elif tab_name == "Purchases":
            tk.Label(
                rules_body, text="Control what this user can do inside Purchases:",
                font=("Segoe UI", 8, "bold"), bg=bg_col, fg=sec_col, wraplength=215, justify="left"
            ).pack(anchor="w", pady=(0, 10))

            # Rule 1: Limit Past Days' Bill Edits
            tk.Checkbutton(
                rules_body, text="Limit Past Days' Bill Edits",
                variable=purch_same_day_var, font=("Segoe UI", 9, "bold"),
                bg=bg_col, fg=text_col, selectcolor=card_bg,
                activebackground=bg_col, activeforeground=text_col,
                anchor="w", justify="left", cursor="hand2", wraplength=210
            ).pack(fill="x", pady=(2, 4), anchor="w")

            purch_past_spin = tk.Frame(rules_body, bg=bg_col)
            purch_past_spin.pack(fill="x", padx=(22, 0), pady=(0, 10))
            tk.Label(purch_past_spin, text="Max Edits:", font=("Segoe UI", 8, "bold"), bg=bg_col, fg=sec_col).pack(side="left")
            tk.Spinbox(
                purch_past_spin, from_=0, to=20, textvariable=purch_max_past_edits_var,
                width=4, font=("Segoe UI", 9, "bold"), justify="center",
                bg=card_bg, fg=text_col, buttonbackground=border_col,
                insertbackground=text_col, relief="solid", bd=1
            ).pack(side="left", padx=6, ipady=1)
            tk.Label(purch_past_spin, text="total (0=Lock)", font=("Segoe UI", 8), bg=bg_col, fg=sec_col).pack(side="left")

            # Rule 2: Limit Today's Bill Edits
            tk.Checkbutton(
                rules_body, text="Limit Today's Bill Edits",
                variable=purch_limit_edits_var, font=("Segoe UI", 9, "bold"),
                bg=bg_col, fg=text_col, selectcolor=card_bg,
                activebackground=bg_col, activeforeground=text_col,
                anchor="w", cursor="hand2", wraplength=210
            ).pack(fill="x", pady=(2, 4), anchor="w")

            purch_today_spin = tk.Frame(rules_body, bg=bg_col)
            purch_today_spin.pack(fill="x", padx=(22, 0), pady=(0, 10))
            tk.Label(purch_today_spin, text="Max Edits:", font=("Segoe UI", 8, "bold"), bg=bg_col, fg=sec_col).pack(side="left")
            tk.Spinbox(
                purch_today_spin, from_=0, to=20, textvariable=purch_max_edits_var,
                width=4, font=("Segoe UI", 9, "bold"), justify="center",
                bg=card_bg, fg=text_col, buttonbackground=border_col,
                insertbackground=text_col, relief="solid", bd=1
            ).pack(side="left", padx=6, ipady=1)
            tk.Label(purch_today_spin, text="/ day", font=("Segoe UI", 8), bg=bg_col, fg=sec_col).pack(side="left")

            # Rule 3: Lock Moving Bills to Recycle Bin
            tk.Checkbutton(
                rules_body, text="Lock Moving Bills to Recycle Bin",
                variable=purch_block_del_var, font=("Segoe UI", 9, "bold"),
                bg=bg_col, fg="#ef4444", selectcolor=card_bg,
                activebackground=bg_col, activeforeground="#ef4444",
                anchor="w", justify="left", cursor="hand2", wraplength=210
            ).pack(fill="x", pady=(2, 8), anchor="w")

            # Rule 4: Lock Past Payment Deletions
            tk.Checkbutton(
                rules_body, text="Lock Past Days' Payment Deletions",
                variable=inv_lock_past_pay_var, font=("Segoe UI", 9, "bold"),
                bg=bg_col, fg="#ef4444", selectcolor=card_bg,
                activebackground=bg_col, activeforeground="#ef4444",
                anchor="w", justify="left", cursor="hand2", wraplength=210
            ).pack(fill="x", pady=(2, 8), anchor="w")

            tk.Label(
                rules_body,
                text="ℹ️ Note: When 'Limit Past Days' Bill Edits' is ticked, past days' bills also cannot be moved to the Recycle Bin or returned (Debit Note) by non-Admins.",
                font=("Segoe UI", 8), bg=bg_col, fg=sec_col,
                wraplength=210, justify="left"
            ).pack(anchor="w", pady=(4, 0))
        elif tab_name == "Catalog":
            tk.Label(
                rules_body, text="Control what this user can do inside the Catalog:",
                font=("Segoe UI", 8, "bold"), bg=bg_col, fg=sec_col, wraplength=215, justify="left"
            ).pack(anchor="w", pady=(0, 10))

            tk.Checkbutton(
                rules_body, text="Lock Adding & Editing Items",
                variable=cat_lock_edit_var, font=("Segoe UI", 9, "bold"),
                bg=bg_col, fg=text_col, selectcolor=card_bg,
                activebackground=bg_col, activeforeground=text_col,
                anchor="w", justify="left", cursor="hand2", wraplength=210
            ).pack(fill="x", pady=(2, 8), anchor="w")

            tk.Checkbutton(
                rules_body, text="Lock Deleting & Bulk Importing",
                variable=cat_lock_del_var, font=("Segoe UI", 9, "bold"),
                bg=bg_col, fg="#ef4444", selectcolor=card_bg,
                activebackground=bg_col, activeforeground="#ef4444",
                anchor="w", justify="left", cursor="hand2", wraplength=210
            ).pack(fill="x", pady=(2, 8), anchor="w")
            
            tk.Label(
                rules_body,
                text="ℹ️ Note: When 'Lock Deleting & Bulk Importing' is active, the user cannot mass-overwrite items.",
                font=("Segoe UI", 8), bg=bg_col, fg=sec_col,
                wraplength=210, justify="left"
            ).pack(anchor="w", pady=(4, 0))
        elif tab_name == "Stock":
            tk.Label(
                rules_body, text="Control what this user can do inside Stock:",
                font=("Segoe UI", 8, "bold"), bg=bg_col, fg=sec_col, wraplength=215, justify="left"
            ).pack(anchor="w", pady=(0, 10))

            tk.Checkbutton(
                rules_body, text="Lock Manual Adjustments (Add/Loss)",
                variable=stock_lock_adj_var, font=("Segoe UI", 9, "bold"),
                bg=bg_col, fg=text_col, selectcolor=card_bg,
                activebackground=bg_col, activeforeground=text_col,
                anchor="w", justify="left", cursor="hand2", wraplength=210
            ).pack(fill="x", pady=(2, 8), anchor="w")

            tk.Checkbutton(
                rules_body, text="Lock Deleting Stock & History Edits",
                variable=stock_lock_del_var, font=("Segoe UI", 9, "bold"),
                bg=bg_col, fg="#ef4444", selectcolor=card_bg,
                activebackground=bg_col, activeforeground="#ef4444",
                anchor="w", justify="left", cursor="hand2", wraplength=210
            ).pack(fill="x", pady=(2, 8), anchor="w")

            tk.Checkbutton(
                rules_body, text="Hide Financial Totals (Net Book / Loss)",
                variable=stock_hide_vals_var, font=("Segoe UI", 9, "bold"),
                bg=bg_col, fg=text_col, selectcolor=card_bg,
                activebackground=bg_col, activeforeground=text_col,
                anchor="w", justify="left", cursor="hand2", wraplength=210
            ).pack(fill="x", pady=(2, 8), anchor="w")
            
            tk.Label(
                rules_body,
                text="ℹ️ Note: When locked, users cannot delete stock items from the main list or alter past ledger records.",
                font=("Segoe UI", 8), bg=bg_col, fg=sec_col,
                wraplength=210, justify="left"
            ).pack(anchor="w", pady=(4, 0))
        elif tab_name == "Employees":
            tk.Label(
                rules_body, text="Control what this user can do inside Employees:",
                font=("Segoe UI", 8, "bold"), bg=bg_col, fg=sec_col, wraplength=215, justify="left"
            ).pack(anchor="w", pady=(0, 10))

            tk.Checkbutton(
                rules_body, text="Lock Payroll & Salary Changes",
                variable=emp_lock_pay_var, font=("Segoe UI", 9, "bold"),
                bg=bg_col, fg=text_col, selectcolor=card_bg,
                activebackground=bg_col, activeforeground=text_col,
                anchor="w", justify="left", cursor="hand2", wraplength=210
            ).pack(fill="x", pady=(2, 8), anchor="w")

            tk.Checkbutton(
                rules_body, text="Lock Deleting Employees & Payments",
                variable=emp_lock_del_var, font=("Segoe UI", 9, "bold"),
                bg=bg_col, fg="#ef4444", selectcolor=card_bg,
                activebackground=bg_col, activeforeground="#ef4444",
                anchor="w", justify="left", cursor="hand2", wraplength=210
            ).pack(fill="x", pady=(2, 8), anchor="w")

            tk.Checkbutton(
                rules_body, text="Hide Financial Totals (Salaries/Advances)",
                variable=emp_hide_vals_var, font=("Segoe UI", 9, "bold"),
                bg=bg_col, fg=text_col, selectcolor=card_bg,
                activebackground=bg_col, activeforeground=text_col,
                anchor="w", justify="left", cursor="hand2", wraplength=210
            ).pack(fill="x", pady=(2, 8), anchor="w")
        elif tab_name == "Labours":
            tk.Label(
                rules_body, text="Control what this user can do inside Labours:",
                font=("Segoe UI", 8, "bold"), bg=bg_col, fg=sec_col, wraplength=215, justify="left"
            ).pack(anchor="w", pady=(0, 10))

            tk.Checkbutton(
                rules_body, text="Lock Payments & Advances",
                variable=labour_lock_pay_var, font=("Segoe UI", 9, "bold"),
                bg=bg_col, fg=text_col, selectcolor=card_bg,
                activebackground=bg_col, activeforeground=text_col,
                anchor="w", justify="left", cursor="hand2", wraplength=210
            ).pack(fill="x", pady=(2, 8), anchor="w")

            tk.Checkbutton(
                rules_body, text="Lock Deleting Workers & Logs",
                variable=labour_lock_del_var, font=("Segoe UI", 9, "bold"),
                bg=bg_col, fg="#ef4444", selectcolor=card_bg,
                activebackground=bg_col, activeforeground="#ef4444",
                anchor="w", justify="left", cursor="hand2", wraplength=210
            ).pack(fill="x", pady=(2, 8), anchor="w")

            tk.Checkbutton(
                rules_body, text="Hide Financial Totals",
                variable=labour_hide_vals_var, font=("Segoe UI", 9, "bold"),
                bg=bg_col, fg=text_col, selectcolor=card_bg,
                activebackground=bg_col, activeforeground=text_col,
                anchor="w", justify="left", cursor="hand2", wraplength=210
            ).pack(fill="x", pady=(2, 8), anchor="w")
        elif tab_name == "GST Report":
            tk.Label(
                rules_body, text="Control what this user can do inside GST Report:",
                font=("Segoe UI", 8, "bold"), bg=bg_col, fg=sec_col, wraplength=215, justify="left"
            ).pack(anchor="w", pady=(0, 10))

            tk.Checkbutton(
                rules_body, text="Lock Marking Bills as 'Submitted'",
                variable=gst_lock_ca_submit_var, font=("Segoe UI", 9, "bold"),
                bg=bg_col, fg=text_col, selectcolor=card_bg,
                activebackground=bg_col, activeforeground=text_col,
                anchor="w", justify="left", cursor="hand2", wraplength=210
            ).pack(fill="x", pady=(2, 8), anchor="w")

            tk.Checkbutton(
                rules_body, text="Lock Reversing CA Submissions",
                variable=gst_lock_ca_undo_var, font=("Segoe UI", 9, "bold"),
                bg=bg_col, fg="#ef4444", selectcolor=card_bg,
                activebackground=bg_col, activeforeground="#ef4444",
                anchor="w", justify="left", cursor="hand2", wraplength=210
            ).pack(fill="x", pady=(2, 8), anchor="w")

            tk.Checkbutton(
                rules_body, text="Lock Exporting GST Reports",
                variable=gst_lock_export_var, font=("Segoe UI", 9, "bold"),
                bg=bg_col, fg=text_col, selectcolor=card_bg,
                activebackground=bg_col, activeforeground=text_col,
                anchor="w", justify="left", cursor="hand2", wraplength=210
            ).pack(fill="x", pady=(2, 8), anchor="w")
            
            tk.Label(
                rules_body,
                text="ℹ️ Note: If CA Submissions are reversed, previously locked invoices will become editable again.",
                font=("Segoe UI", 8), bg=bg_col, fg=sec_col,
                wraplength=210, justify="left"
            ).pack(anchor="w", pady=(4, 0))
        else:
            tk.Label(
                rules_body, text=f"Standard access enabled for '{tab_name}'.\n\n(Custom rules for this tab will appear here once configured.)",
                font=("Segoe UI", 9), bg=bg_col, fg=sec_col, wraplength=210, justify="left"
            ).pack(anchor="w", pady=10)

    saved_side_list = saved_perms.get("sidebars", "all")
    for s_name in ALL_SIDEBAR_ITEMS:
        is_checked = True if (is_master_admin or s_name == "Home" or saved_side_list == "all" or s_name in saved_side_list) else False
        var = tk.IntVar(value=1 if is_checked else 0)
        sidebar_vars[s_name] = var

        disp_lbl = "Home (Always On)" if s_name == "Home" else s_name
        row_f = tk.Frame(side_inner, bg=bg_col, cursor="hand2")
        row_f.pack(fill="x", pady=1, anchor="nw")

        # Compact standalone checkbutton with white tick (fg=text_col)
        cb = tk.Checkbutton(
            row_f, variable=var,
            bg=bg_col, fg=text_col,
            selectcolor=card_bg,
            activebackground=bg_col, activeforeground=text_col,
            cursor="hand2",
            command=lambda n=s_name: render_rules_for_tab(n)
        )
        if is_master_admin or s_name == "Home":
            cb.config(state="disabled")
        cb.pack(side="left", padx=(6, 4))

        # Clickable tab name label (won't affect checkbox when clicked)
        lbl_name = tk.Label(
            row_f, text=disp_lbl,
            font=("Segoe UI", 9, "bold"), bg=bg_col, fg=text_col,
            anchor="w", cursor="hand2"
        )
        lbl_name.pack(side="left", fill="x", expand=True)

        arrow_lbl = tk.Label(row_f, text="›", font=("Segoe UI", 10, "bold"), bg=bg_col, fg=sec_col, padx=6, cursor="hand2")
        arrow_lbl.pack(side="right")

        def select_tab_only(e=None, n=s_name):
            render_rules_for_tab(n)

        row_f.bind("<Button-1>", select_tab_only)
        lbl_name.bind("<Button-1>", select_tab_only)
        arrow_lbl.bind("<Button-1>", select_tab_only)
        tab_row_frames[s_name] = (row_f, cb, lbl_name, arrow_lbl)

    render_rules_for_tab("Invoices")

    # Clamp scrollregion to canvas size so short lists stay pinned at the top and never scroll into the middle
    def _bind_box_scroll(canvas_widget, inner_frame):
        def _sync_region(event=None):
            bbox = canvas_widget.bbox("all")
            if not bbox:
                return
            cw = max(canvas_widget.winfo_width(), bbox[2])
            ch = max(canvas_widget.winfo_height(), bbox[3])
            canvas_widget.configure(scrollregion=(0, 0, cw, ch))
            if bbox[3] <= canvas_widget.winfo_height():
                canvas_widget.yview_moveto(0.0)
            if bbox[2] <= canvas_widget.winfo_width():
                canvas_widget.xview_moveto(0.0)

        inner_frame.bind("<Configure>", _sync_region)
        canvas_widget.bind("<Configure>", _sync_region)

        def _on_wheel(e):
            delta = -1 if e.delta > 0 else 1
            if (e.state & 0x0001) != 0:
                if canvas_widget.xview() != (0.0, 1.0):
                    canvas_widget.xview_scroll(delta, "units")
            else:
                if canvas_widget.yview() != (0.0, 1.0):
                    canvas_widget.yview_scroll(delta, "units")

        def _bind_recursive(w):
            w.bind("<MouseWheel>", _on_wheel)
            for ch in w.winfo_children():
                _bind_recursive(ch)

        canvas_widget.bind("<MouseWheel>", _on_wheel)
        _bind_recursive(inner_frame)

    _bind_box_scroll(comp_cvs, comp_inner)
    _bind_box_scroll(side_cvs, side_inner)
    _bind_box_scroll(left_cvs, left_card)

    # Smart Role Presets when switching dropdown
    def apply_role_preset(role_name):
        if is_master_admin:
            return
        if role_name == "Manager":
            for k, v in sidebar_vars.items():
                v.set(0 if k == "Settings" else 1)
        elif role_name == "Staff":
            staff_tabs = {"Home", "Parties", "Invoices", "Purchases", "Catalog", "Stock"}
            for k, v in sidebar_vars.items():
                v.set(1 if k in staff_tabs else 0)
        render_rules_for_tab(active_rule_tab[0])

    if not is_edit:
        apply_role_preset("Manager")

    def on_role_select(event):
        selected = role_var.get()
        if selected == "Custom":
            cb_role.config(state="normal")
            role_var.set("")
            cb_role.focus_set()
        else:
            cb_role.config(state="readonly")
            apply_role_preset(selected)

    cb_role.bind("<<ComboboxSelected>>", on_role_select)

    def save_user():
        u = user_var.get().strip()
        p = pass_var.get().strip()
        r = "Admin" if (is_edit and str(edit_user_id) == "1") else (user_data[3] if (viewer_role != "Admin" and user_data) else role_var.get().strip())

        if not u or not r:
            messagebox.showerror("Required", "Username and Role are required.", parent=pop)
            return
        if not is_edit and not p:
            messagebox.showerror("Required", "Password is required for a new user.", parent=pop)
            return

        selected_comps = [cid for cid, v in comp_vars.items() if v.get() == 1]
        selected_sides = [sname for sname, v in sidebar_vars.items() if v.get() == 1 or sname == "Home"]

        if not is_master_admin and all_companies and not selected_comps:
            if not messagebox.askyesno("No Company Selected", "You haven't ticked any company for this user. They won't see any companies on the Home screen.\n\nSave anyway?", parent=pop):
                return

        if not is_master_admin and len(selected_sides) <= 1:
            if not messagebox.askyesno("No Sidebar Tabs", "Only 'Home' is ticked. This user won't see any tabs inside a company.\n\nSave anyway?", parent=pop):
                return

        try:
            clean_max_past_edits = max(0, int(inv_max_past_edits_var.get().strip()))
        except Exception:
            clean_max_past_edits = 1

        try:
            clean_max_edits = max(0, int(inv_max_edits_var.get().strip()))
        except Exception:
            clean_max_edits = 2

        try:
            clean_exp_past_edits = max(0, int(exp_max_past_edits_var.get().strip()))
        except Exception:
            clean_exp_past_edits = 1

        try:
            clean_exp_max_edits = max(0, int(exp_max_edits_var.get().strip()))
        except Exception:
            clean_exp_max_edits = 2

        try:
            clean_purch_past_edits = max(0, int(purch_max_past_edits_var.get().strip()))
        except Exception:
            clean_purch_past_edits = 1

        try:
            clean_purch_max_edits = max(0, int(purch_max_edits_var.get().strip()))
        except Exception:
            clean_purch_max_edits = 2

        perms_dict = saved_perms if (viewer_role != "Admin" and is_edit) else {
            "companies": "all" if (is_edit and str(edit_user_id) == "1") else selected_comps,
            "sidebars": "all" if (is_edit and str(edit_user_id) == "1") else selected_sides,
            "invoice_rules": {} if (is_edit and str(edit_user_id) == "1") else {
                "same_day_only": bool(inv_same_day_var.get() == 1),
                "max_past_edits": clean_max_past_edits,
                "limit_edits": bool(inv_limit_edits_var.get() == 1),
                "max_edits": clean_max_edits,
                "lock_past_payments": bool(inv_lock_past_pay_var.get() == 1)
            },
            "party_rules": {} if (is_edit and str(edit_user_id) == "1") else {
                "lock_opening_balance": bool(party_lock_ob_var.get() == 1),
                "block_waive_off": bool(party_block_waive_var.get() == 1),
                "lock_past_payments": bool(inv_lock_past_pay_var.get() == 1)
            },
            "expense_rules": {} if (is_edit and str(edit_user_id) == "1") else {
                "same_day_only": bool(exp_same_day_var.get() == 1),
                "max_past_edits": clean_exp_past_edits,
                "limit_edits": bool(exp_limit_edits_var.get() == 1),
                "max_edits": clean_exp_max_edits,
                "block_delete": bool(exp_block_del_var.get() == 1)
            },
            "purchase_rules": {} if (is_edit and str(edit_user_id) == "1") else {
                "same_day_only": bool(purch_same_day_var.get() == 1),
                "max_past_edits": clean_purch_past_edits,
                "limit_edits": bool(purch_limit_edits_var.get() == 1),
                "max_edits": clean_purch_max_edits,
                "block_delete": bool(purch_block_del_var.get() == 1)
            },
            "catalog_rules": {} if (is_edit and str(edit_user_id) == "1") else {
                "lock_edit": bool(cat_lock_edit_var.get() == 1),
                "lock_delete": bool(cat_lock_del_var.get() == 1)
            },
            "stock_rules": {} if (is_edit and str(edit_user_id) == "1") else {
                "lock_adjustments": bool(stock_lock_adj_var.get() == 1),
                "lock_delete": bool(stock_lock_del_var.get() == 1),
                "hide_financials": bool(stock_hide_vals_var.get() == 1)
            },
            "employee_rules": {} if (is_edit and str(edit_user_id) == "1") else {
                "lock_payroll": bool(emp_lock_pay_var.get() == 1),
                "lock_delete": bool(emp_lock_del_var.get() == 1),
                "hide_financials": bool(emp_hide_vals_var.get() == 1)
            },
            "labour_rules": {} if (is_edit and str(edit_user_id) == "1") else {
                "lock_payroll": bool(labour_lock_pay_var.get() == 1),
                "lock_delete": bool(labour_lock_del_var.get() == 1),
                "hide_financials": bool(labour_hide_vals_var.get() == 1)
            },
            "gst_rules": {} if (is_edit and str(edit_user_id) == "1") else {
                "lock_ca_submit": bool(gst_lock_ca_submit_var.get() == 1),
                "lock_ca_undo": bool(gst_lock_ca_undo_var.get() == 1),
                "lock_export": bool(gst_lock_export_var.get() == 1)
            }
        }
        perms_json = json.dumps(perms_dict)

        old_pic = user_data[4] if (is_edit and user_data and len(user_data) > 4 and user_data[4]) else ""
        final_pic = pic_path_var[0]
        if final_pic and os.path.exists(final_pic) and "user_avatars" not in final_pic:
            safe_dir = os.path.join(get_root_dir(), "user_avatars")
            os.makedirs(safe_dir, exist_ok=True)
            ext = os.path.splitext(final_pic)[1] or ".png"
            dest = os.path.join(safe_dir, f"avatar_{int(time.time()*1000)}{ext}")
            try:
                shutil.copy2(final_pic, dest)
                # 1. Wipe the temp cropper file immediately
                if "cropped_" in os.path.basename(final_pic) or "temp" in os.path.basename(final_pic):
                    try:
                        os.remove(final_pic)
                    except Exception:
                        pass
                # 2. Wipe the old replaced avatar from user_avatars so it doesn't pile up
                if old_pic and old_pic != dest and os.path.exists(old_pic) and "user_avatars" in old_pic:
                    try:
                        os.remove(old_pic)
                    except Exception:
                        pass
                final_pic = dest
            except Exception:
                pass
        cleanup_unsaved_crops()

        # --- THE FIX: Save the new Q&A if provided ---
        if is_master_admin:
            sec_q = q_var.get().strip()
            sec_a = ans_var.get().strip()
            if sec_q and sec_a:
                conn = database.get_connection()
                c = conn.cursor()
                c.execute("REPLACE INTO ui_settings (setting_key, setting_value, company_id) VALUES (?, ?, ?)", ('admin_sec_q', sec_q, 0))
                c.execute("REPLACE INTO ui_settings (setting_key, setting_value, company_id) VALUES (?, ?, ?)", ('admin_sec_a', hash_password(sec_a.lower()), 0))
                conn.commit()
                conn.close()
        # ---------------------------------------------

        if is_edit:
            new_hash = hash_password(p) if p else None
            database.update_user_details(edit_user_id, u, r, final_pic, new_hash, perms_json)
            messagebox.showinfo("Success", f"Profile & permissions for '{u}' ({disp_id}) updated!", parent=pop)
        else:
            new_id = database.add_user(u, hash_password(p), r, final_pic, perms_json)
            messagebox.showinfo("Success", f"User '{u}' created with Unique ID USR-{new_id:03d}!", parent=pop)

        on_save_callback()
        pop.destroy()

    tk.Button(save_btn_frame, text="💾 Save User & Access", font=("Segoe UI", 11, "bold"), bg=accent_blue, fg="#ffffff", cursor="hand2", relief="flat", pady=8, command=save_user).pack(fill="x")


def open_security_manager(home_view):
    current_role = getattr(home_view.app, 'current_role', '')
    if current_role != "Admin":
        messagebox.showerror("Access Denied", "Only the Master Admin can manage users and security.", parent=home_view)
        return

    theme = home_view.colors

    pop = tk.Toplevel(home_view)
    pop.title("Global Security & Users")
    pop.geometry("900x580")
    pop.configure(bg=theme["bg"])
    pop.grab_set()

    pop.update_idletasks()
    x = int((pop.winfo_screenwidth() / 2) - (900 / 2))
    y = int((pop.winfo_screenheight() / 2) - (580 / 2))
    pop.geometry(f"+{x}+{y}")

    tk.Label(pop, text="🛡️ Global Security & User Profiles", font=("Segoe UI", 18, "bold"), bg=theme["bg"], fg=theme["text"]).pack(pady=(20, 15))

    main_f = tk.Frame(pop, bg=theme["card"], padx=30, pady=25, highlightbackground=theme["border"], highlightthickness=1)
    main_f.pack(fill="both", expand=True, padx=20, pady=(0, 20))

    table_header_f = tk.Frame(main_f, bg=theme["card"])
    table_header_f.pack(fill="x", pady=(0, 15))

    all_comps_total = len(database.get_all_companies(ignore_permissions=True))
    avatar_colors = ["#3b82f6", "#8b5cf6", "#ec4899", "#10b981", "#f59e0b", "#ef4444"]
    pop.tree_avatar_refs = []

    def make_row_avatar(pic_path, name, fallback_color):
        """Creates a smooth 32x32 circular avatar thumbnail for the Treeview row."""
        if not Image or not ImageTk or not ImageDraw:
            return None
        size = 32
        scale = 4
        resamp = Image.Resampling.LANCZOS if hasattr(Image, 'Resampling') else Image.LANCZOS
        if pic_path and os.path.exists(pic_path):
            try:
                img = Image.open(pic_path).convert("RGBA").resize((size, size), resamp)
                mask = Image.new("L", (size * scale, size * scale), 0)
                ImageDraw.Draw(mask).ellipse((0, 0, size * scale - 1, size * scale - 1), fill=255)
                mask = mask.resize((size, size), resamp)
                out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
                out.paste(img, (0, 0), mask)
                return ImageTk.PhotoImage(out)
            except Exception:
                pass
        # Fallback: smooth colored circle when user has no photo
        try:
            circ = Image.new("RGBA", (size * scale, size * scale), (0, 0, 0, 0))
            ImageDraw.Draw(circ).ellipse((0, 0, size * scale - 1, size * scale - 1), fill=fallback_color)
            circ = circ.resize((size, size), resamp)
            return ImageTk.PhotoImage(circ)
        except Exception:
            return None

    def refresh_user_tree():
        for item in tree.get_children():
            tree.delete(item)
        pop.tree_avatar_refs.clear()

        for idx, u in enumerate(database.get_all_users()):
            u_id, u_name, u_role = u[0], u[1], u[2]
            u_pic = u[3] if len(u) > 3 else ""
            formatted_id = f"USR-{int(u_id):03d}"

            if str(u_id) == "1":
                display_role = f"👑 {u_role} (Master)"
                access_summary = "All Companies • All Tabs"
                tag = "master_admin"
            else:
                display_role = u_role
                perms = database.get_user_permissions(u_id)
                c_list = perms.get("companies", "all")
                s_list = perms.get("sidebars", "all")
                c_txt = "All Companies" if c_list == "all" else f"{len(c_list)}/{all_comps_total} Companies"
                s_txt = "All Tabs" if s_list == "all" else f"{len(s_list)}/{len(ALL_SIDEBAR_ITEMS)} Tabs"
                access_summary = f"{c_txt} • {s_txt}"
                tag = "evenrow" if idx % 2 == 0 else "oddrow"

            fallback_col = avatar_colors[idx % len(avatar_colors)]
            row_img = make_row_avatar(u_pic, u_name, fallback_col)
            if row_img:
                pop.tree_avatar_refs.append(row_img)
                tree.insert("", "end", text="", image=row_img, values=(formatted_id, u_name, display_role, access_summary), tags=(str(u_id), tag))
            else:
                tree.insert("", "end", text="👤", values=(formatted_id, u_name, display_role, access_summary), tags=(str(u_id), tag))

    def delete_selected_user():
        selected = tree.selection()
        if not selected:
            messagebox.showwarning("Select User", "Please select a user from the list first.", parent=pop)
            return

        item_id = tree.item(selected[0], "tags")[0]
        item_code = tree.item(selected[0], "values")[0]
        item_username = tree.item(selected[0], "values")[1]

        if str(item_id) == "1":
            messagebox.showerror("Access Denied", "The Master Admin (USR-001) has absolute power and can never be deleted.", parent=pop)
            return

        current_uid = getattr(home_view.app, 'current_user_id', None)
        if current_uid and str(item_id) == str(current_uid):
            messagebox.showerror("Access Denied", "You cannot delete your own account while logged in.", parent=pop)
            return

        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to permanently delete '{item_username}' ({item_code})?", parent=pop):
            # Wipe physical avatar photo from user_avatars before deleting DB row
            u_row = database.get_user_by_id(item_id)
            if u_row and len(u_row) > 4 and u_row[4] and os.path.exists(u_row[4]):
                if "user_avatars" in u_row[4]:
                    try:
                        os.remove(u_row[4])
                    except Exception:
                        pass
            database.delete_user(item_id)
            refresh_user_tree()

    def edit_selected_user():
        selected = tree.selection()
        if not selected:
            messagebox.showwarning("Select User", "Please select a user from the list to edit or configure permissions.", parent=pop)
            return
        item_id = tree.item(selected[0], "tags")[0]
        open_user_form_popup(pop, theme, refresh_user_tree, edit_user_id=item_id)

    # Pack action buttons FIRST so they are never pushed off-screen by the header label
    tk.Button(table_header_f, text="❌ Delete User", font=("Segoe UI", 10, "bold"), bg="#ef4444", fg="#ffffff", cursor="hand2", relief="flat", padx=15, pady=5, command=delete_selected_user).pack(side="right")
    tk.Button(table_header_f, text="🔐 Edit & Permissions", font=("Segoe UI", 10, "bold"), bg=theme["accent_blue"], fg="#ffffff", cursor="hand2", relief="flat", padx=15, pady=5, command=edit_selected_user).pack(side="right", padx=10)
    tk.Button(table_header_f, text="➕ Create User", font=("Segoe UI", 10, "bold"), bg="#10b981", fg="#ffffff", cursor="hand2", relief="flat", padx=15, pady=5, command=lambda: open_user_form_popup(pop, theme, refresh_user_tree)).pack(side="right")

    tk.Label(table_header_f, text="Registered Users", font=("Segoe UI", 14, "bold"), bg=theme["card"], fg=theme["text"]).pack(side="left")

    tree_wrap = tk.Frame(main_f, bg=theme["card"], highlightbackground=theme["border"], highlightthickness=1)
    tree_wrap.pack(fill="both", expand=True)

    style = ttk.Style(pop)
    apply_adaptive_scrollbar_style(style, theme["bg"], theme["border"], theme["text"], theme["accent_blue"])
    style.configure("User.Treeview.Heading", font=("Segoe UI", 10, "bold"), background=theme["border"], foreground=theme["text"], relief="flat", borderwidth=1)
    style.map("User.Treeview.Heading", background=[("active", theme["border"])], foreground=[("active", theme["text"])])
    style.configure("User.Treeview", font=("Segoe UI", 11), rowheight=44, background=theme["bg"], fieldbackground=theme["bg"], foreground=theme["text"], borderwidth=1, relief="solid", bordercolor=theme["border"])
    style.map("User.Treeview", background=[("selected", theme["accent_blue"])], foreground=[("selected", "#ffffff")], fieldbackground=[("!disabled", theme["bg"])])

    cols = ("uid", "username", "role", "access")
    tree = ttk.Treeview(tree_wrap, columns=cols, show="tree headings", height=9, style="User.Treeview")
    tree.heading("#0", text="Pic", anchor="center")
    tree.heading("uid", text="Unique ID", anchor="w")
    tree.heading("username", text="Username", anchor="w")
    tree.heading("role", text="Assigned Role", anchor="w")
    tree.heading("access", text="Access Scope", anchor="w")

    tree.column("#0", width=65, stretch=False, anchor="center")
    tree.column("uid", width=110, anchor="w")
    tree.column("username", width=210, anchor="w")
    tree.column("role", width=170, anchor="w")
    tree.column("access", width=240, anchor="w")

    tree_vscroll = ttk.Scrollbar(tree_wrap, orient="vertical", command=tree.yview, style="Popup.Vertical.TScrollbar")
    tree_hscroll = ttk.Scrollbar(main_f, orient="horizontal", command=tree.xview, style="Popup.Horizontal.TScrollbar")
    tree.configure(yscrollcommand=tree_vscroll.set, xscrollcommand=tree_hscroll.set)
    tree_vscroll.pack(side="right", fill="y")
    tree.pack(side="left", fill="both", expand=True)
    tree_hscroll.pack(side="bottom", fill="x", pady=(4, 0))

    tree.tag_configure("evenrow", background=theme["bg"], foreground=theme["text"])
    tree.tag_configure("oddrow", background=theme["card"], foreground=theme["text"])
    tree.tag_configure("master_admin", background="#3f3f46", foreground="#10b981", font=("Segoe UI", 11, "bold"))

    tree.bind("<Double-1>", lambda e: edit_selected_user())
    refresh_user_tree()