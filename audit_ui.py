import tkinter as tk
from tkinter import ttk
import tkinter.font as tkfont
import json
import re
from datetime import datetime
import database
from views.home_parts.ui_components import get_theme, create_perfect_button
from views.invoice_parts.helpers import (
    add_hover,
    enable_copy_paste,
    fetch_global_settings,
    smart_date_formatter,
    format_currency,
    isolate_tree_scroll
)

AUDIT_TABS = [
    "All Tabs", "Invoices", "Parties", "Purchases", "Catalog",
    "Stock", "Expenses", "Employees", "Labours", "Settings"
]

_ACTIVE_AUDIT_WINDOW = None
_HEADER_BADGE_REFRESHERS = []


def refresh_all_header_badges():
    """Updates all live '📜 Audit Log' header buttons across open views."""
    alive = []
    for fn in _HEADER_BADGE_REFRESHERS:
        try:
            if fn():
                alive.append(fn)
        except Exception:
            pass
    _HEADER_BADGE_REFRESHERS[:] = alive


def attach_audit_button(header_frame, default_tab="All Tabs"):
    """Drops an Admin-only '📜 Audit Log' button with an unseen count badge into any tab's header frame."""
    try:
        app = header_frame.winfo_toplevel()
        if getattr(app, "current_role", "") != "Admin":
            return None
    except Exception:
        return None

    theme = get_theme()
    default_bg = theme["accent_blue"]
    hover_bg = "#2563eb"

    btn_wrap = tk.Frame(header_frame, bg=default_bg, highlightthickness=1, highlightbackground=default_bg, cursor="hand2")
    inner = tk.Frame(btn_wrap, bg=default_bg, padx=12, pady=6, cursor="hand2")
    inner.pack(fill="both", expand=True)

    lbl_txt = tk.Label(inner, text="📜 Audit Log", font=("Segoe UI", 10, "bold"), bg=default_bg, fg="#ffffff", cursor="hand2")
    lbl_txt.pack(side="left")

    lbl_badge = tk.Label(inner, text="", font=("Segoe UI", 8, "bold"), bg="#ef4444", fg="#ffffff", padx=6, pady=1, cursor="hand2")

    def _update_header_badge():
        if not btn_wrap.winfo_exists():
            return False
        cid = getattr(app, "active_company_id", None) or getattr(database, "ACTIVE_COMPANY_ID", 1)
        counts = database.get_unseen_audit_counts(cid)
        total_unseen = counts.get("All Tabs", 0)
        if total_unseen > 0:
            lbl_badge.config(text=str(total_unseen))
            if not lbl_badge.winfo_ismapped():
                lbl_badge.pack(side="left", padx=(7, 0))
        else:
            if lbl_badge.winfo_ismapped():
                lbl_badge.pack_forget()
        return True

    _HEADER_BADGE_REFRESHERS.append(_update_header_badge)
    _update_header_badge()

    def _on_click(e=None):
        open_audit_window(header_frame, default_tab=default_tab)

    def _on_enter(e=None):
        btn_wrap.config(bg=hover_bg, highlightbackground=hover_bg)
        inner.config(bg=hover_bg)
        lbl_txt.config(bg=hover_bg)

    def _on_leave(e=None):
        btn_wrap.config(bg=default_bg, highlightbackground=default_bg)
        inner.config(bg=default_bg)
        lbl_txt.config(bg=default_bg)

    for w in (btn_wrap, inner, lbl_txt, lbl_badge):
        w.bind("<Button-1>", _on_click)
        w.bind("<Enter>", _on_enter)
        w.bind("<Leave>", _on_leave)

    btn_wrap.pack(side="right", padx=(10, 0))
    return btn_wrap


def open_audit_window(parent_widget, default_tab="All Tabs"):
    """Opens a non-blocking floating Audit Log window so Admin can inspect tabs side-by-side."""
    global _ACTIVE_AUDIT_WINDOW
    app = parent_widget.winfo_toplevel()
    if getattr(app, "current_role", "") != "Admin":
        return

    theme = get_theme()

    # Reuse existing floating window if already open
    if _ACTIVE_AUDIT_WINDOW is not None and _ACTIVE_AUDIT_WINDOW.winfo_exists():
        _ACTIVE_AUDIT_WINDOW.lift()
        _ACTIVE_AUDIT_WINDOW.focus_force()
        if hasattr(_ACTIVE_AUDIT_WINDOW, "select_tab"):
            _ACTIVE_AUDIT_WINDOW.select_tab(default_tab if default_tab in AUDIT_TABS else "All Tabs")
        return

    pop = tk.Toplevel(app)
    _ACTIVE_AUDIT_WINDOW = pop
    pop.title("📜 Activity & Audit Trail (Admin Only)")
    pop.geometry("1080x640")
    pop.configure(bg=theme["bg"])

    pop.update_idletasks()
    x = int((pop.winfo_screenwidth() / 2) - (1080 / 2))
    y = int((pop.winfo_screenheight() / 2) - (640 / 2))
    pop.geometry(f"+{x}+{y}")

    # Style Combobox & Adaptive Scrollbars (keeping 'default' theme intact)
    pop.option_add("*TCombobox*Listbox.background", theme["card"])
    pop.option_add("*TCombobox*Listbox.foreground", theme["text"])
    pop.option_add("*TCombobox*Listbox.selectBackground", theme["accent_blue"])
    pop.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")

    style = ttk.Style(pop)
    style.configure("Audit.Vertical.TScrollbar", background=theme["sec"], troughcolor=theme["bg"], bordercolor=theme["bg"], arrowcolor=theme["text"], relief="flat")
    style.configure("Audit.Horizontal.TScrollbar", background=theme["sec"], troughcolor=theme["bg"], bordercolor=theme["bg"], arrowcolor=theme["text"], relief="flat")
    style.map("Audit.Vertical.TScrollbar", background=[("active", theme["accent_blue"])])
    style.map("Audit.Horizontal.TScrollbar", background=[("active", theme["accent_blue"])])

    style.configure("Audit.TCombobox", fieldbackground=theme["bg"], background=theme["card"], foreground=theme["text"], arrowcolor=theme["text"], bordercolor=theme["border"], lightcolor=theme["border"], darkcolor=theme["border"])
    style.map("Audit.TCombobox", fieldbackground=[("readonly", theme["bg"])], selectbackground=[("readonly", theme["bg"])], selectforeground=[("readonly", theme["text"])])

    # Match Invoices main table heading & row styling
    style.configure("Audit.Treeview.Heading", font=("Arial", 10, "bold"), background=theme["card"], foreground=theme["text"], borderwidth=1, relief="solid", bordercolor=theme["border"])
    style.map("Audit.Treeview.Heading", background=[("active", theme["border"])])
    style.configure("Audit.Treeview", font=("Arial", 11), rowheight=38, background=theme["card"], fieldbackground=theme["card"], foreground=theme["text"], borderwidth=0)
    style.map("Audit.Treeview", background=[("selected", theme["accent_blue"])], foreground=[("selected", "#ffffff")])

    # =========================================================================
    # 1. TOP BAR: USER SELECTOR + SEARCH FILTER WITH ✖ CLEAR BUTTON
    # =========================================================================
    top_bar = tk.Frame(pop, bg=theme["card"], padx=20, pady=14, highlightbackground=theme["border"], highlightthickness=1)
    top_bar.pack(fill="x", padx=20, pady=(18, 10))

    tk.Label(top_bar, text="👤 Select User:", font=("Segoe UI", 10, "bold"), bg=theme["card"], fg=theme["text"]).pack(side="left", padx=(0, 8))

    users_raw = database.get_all_users()
    user_map = {"All Users": "All"}
    for u in users_raw:
        uid, uname, urole = u[0], u[1], u[2]
        label = f"USR-{int(uid):03d} • {uname} ({urole})"
        user_map[label] = uid

    user_var = tk.StringVar(value="All Users")
    cb_user = ttk.Combobox(top_bar, textvariable=user_var, values=list(user_map.keys()), state="readonly", font=("Segoe UI", 10, "bold"), width=26, style="Audit.TCombobox", cursor="hand2")
    cb_user.pack(side="left", ipady=3)

    tk.Label(top_bar, text="🔍 Search:", font=("Segoe UI", 10, "bold"), bg=theme["card"], fg=theme["text"]).pack(side="left", padx=(20, 8))
    search_var = tk.StringVar()
    ent_search = tk.Entry(top_bar, textvariable=search_var, font=("Arial", 11), width=26, bg=theme["bg"], fg=theme["text"], insertbackground=theme["text"], highlightbackground=theme["border"], highlightthickness=1)
    ent_search.pack(side="left", ipady=3)
    enable_copy_paste(ent_search)

    def clear_search():
        search_var.set("")
        pop.focus_set()
        refresh_logs()

    btn_clear = tk.Button(top_bar, text="✖", font=("Arial", 10, "bold"), bg=theme["bg"], fg=theme["error"], relief="solid", bd=1, cursor="hand2", command=clear_search)
    btn_clear.pack(side="left", padx=(5, 0), ipady=2, ipadx=8)
    add_hover(btn_clear, theme["bg"], theme["btn_hover"])

    btn_refresh = tk.Button(top_bar, text="↻ Refresh", font=("Segoe UI", 9, "bold"), bg=theme["bg"], fg=theme["text"], relief="solid", bd=1, cursor="hand2", padx=12, pady=3)
    btn_refresh.pack(side="right")
    add_hover(btn_refresh, theme["bg"], theme["btn_hover"])

    # =========================================================================
    # 2. SECOND BAR: TAB SELECTOR PILLS (WITH RED NOTIFICATION BADGES)
    # =========================================================================
    tab_bar = tk.Frame(pop, bg=theme["bg"], padx=20)
    tab_bar.pack(fill="x", pady=(0, 10))

    active_tab_var = tk.StringVar(value=default_tab if default_tab in AUDIT_TABS else "All Tabs")
    tab_buttons = {}

    def update_pill_styles_and_badges(counts_dict=None):
        if counts_dict is None:
            cid = getattr(app, "active_company_id", None) or getattr(database, "ACTIVE_COMPANY_ID", 1)
            counts_dict = database.get_unseen_audit_counts(cid)

        curr_active = active_tab_var.get()
        for t_name, (pill_f, lbl_t, lbl_b) in tab_buttons.items():
            bg_c = theme["accent_blue"] if t_name == curr_active else theme["card"]
            fg_c = "#ffffff" if t_name == curr_active else theme["text"]
            pill_f.config(bg=bg_c)
            lbl_t.config(bg=bg_c, fg=fg_c)

            c_val = counts_dict.get(t_name, 0)
            if c_val > 0:
                lbl_b.config(text=str(c_val))
                if not lbl_b.winfo_ismapped():
                    lbl_b.pack(side="left", padx=(6, 0))
            else:
                if lbl_b.winfo_ismapped():
                    lbl_b.pack_forget()

    def select_tab(tab_name):
        active_tab_var.set(tab_name)
        refresh_logs(mark_seen_now=True)

    pop.select_tab = select_tab

    for t_name in AUDIT_TABS:
        is_act = (t_name == active_tab_var.get())
        bg_init = theme["accent_blue"] if is_act else theme["card"]
        fg_init = "#ffffff" if is_act else theme["text"]

        pill_f = tk.Frame(tab_bar, bg=bg_init, padx=10, pady=5, cursor="hand2")
        pill_f.pack(side="left", padx=(0, 6))

        lbl_t = tk.Label(pill_f, text=t_name, font=("Segoe UI", 9, "bold"), bg=bg_init, fg=fg_init, cursor="hand2")
        lbl_t.pack(side="left")

        lbl_b = tk.Label(pill_f, text="", font=("Segoe UI", 8, "bold"), bg="#ef4444", fg="#ffffff", padx=5, pady=0, cursor="hand2")

        for w in (pill_f, lbl_t, lbl_b):
            w.bind("<Button-1>", lambda e, n=t_name: select_tab(n))

        tab_buttons[t_name] = (pill_f, lbl_t, lbl_b)

    # =========================================================================
    # 3. AUDIT TABLE (ZEBRA STRIPES + GHOST COLUMN + YELLOW HOVER TOOLTIP)
    # =========================================================================
    table_frame = tk.Frame(pop, bg=theme["card"], highlightbackground=theme["border"], highlightthickness=1)
    table_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))
    table_frame.columnconfigure(0, weight=1)
    table_frame.rowconfigure(0, weight=1)

    v_scr = ttk.Scrollbar(table_frame, orient="vertical", style="Audit.Vertical.TScrollbar")
    h_scr = ttk.Scrollbar(table_frame, orient="horizontal", style="Audit.Horizontal.TScrollbar")

    cols = ("date", "time", "user", "tab", "action", "details", "amount", "ghost")
    tree = ttk.Treeview(
        table_frame, columns=cols, show="headings", height=15,
        style="Audit.Treeview", yscrollcommand=v_scr.set, xscrollcommand=h_scr.set
    )

    v_scr.config(command=tree.yview)
    h_scr.config(command=tree.xview)

    tree.grid(row=0, column=0, sticky="nsew")
    v_scr.grid(row=0, column=1, sticky="ns")
    h_scr.grid(row=1, column=0, sticky="ew")

    tree.heading("date", text="DATE", anchor="w")
    tree.heading("time", text="EXACT TIME", anchor="w")
    tree.heading("user", text="USER (ID • NAME)", anchor="w")
    tree.heading("tab", text="TAB", anchor="w")
    tree.heading("action", text="ACTION", anchor="center")
    tree.heading("details", text="WHAT WAS DONE", anchor="w")
    tree.heading("amount", text="AMOUNT", anchor="e")
    tree.heading("ghost", text="")

    try:
        raw_w = database.get_ui_setting("audit_main_cols", "{}")
        w_dict = json.loads(raw_w) if raw_w else {}
    except Exception:
        w_dict = {}

    tree.column("date", width=w_dict.get("date", 165), minwidth=120, anchor="w", stretch=False)
    tree.column("time", width=w_dict.get("time", 105), minwidth=90, anchor="w", stretch=False)
    tree.column("user", width=w_dict.get("user", 165), minwidth=120, anchor="w", stretch=False)
    tree.column("tab", width=w_dict.get("tab", 95), minwidth=75, anchor="w", stretch=False)
    tree.column("action", width=w_dict.get("action", 115), minwidth=85, anchor="center", stretch=False)
    tree.column("details", width=w_dict.get("details", 380), minwidth=200, anchor="w", stretch=False)
    tree.column("amount", width=w_dict.get("amount", 125), minwidth=95, anchor="e", stretch=False)
    tree.column("ghost", width=10, minwidth=10, stretch=True)

    def save_audit_widths():
        new_w = {c: tree.column(c, "width") for c in tree["columns"] if c != "ghost"}
        try:
            database.save_ui_setting("audit_main_cols", json.dumps(new_w))
        except Exception:
            pass

    def on_sep_drag(event):
        if tree.identify_region(event.x, event.y) == "separator":
            pop.after(50, save_audit_widths)

    tree.bind("<B1-Motion>", on_sep_drag, add="+")
    tree.bind("<ButtonRelease-1>", lambda e: pop.after(50, save_audit_widths), add="+")

    def prevent_dummy_select(event):
        for iid in tree.selection():
            if "dummy" in tree.item(iid, "tags"):
                tree.selection_remove(iid)

    tree.bind("<<TreeviewSelect>>", prevent_dummy_select)

    # --- Yellow Highlight Tooltip for Overflowing "WHAT WAS DONE" Cells ---
    tooltip = tk.Toplevel(pop)
    tooltip.wm_overrideredirect(True)
    tooltip.wm_geometry("+0+0")
    tooltip.configure(bg="#fef08a", highlightbackground="#ca8a04", highlightthickness=1)
    tooltip_lbl = tk.Label(
        tooltip, text="", font=("Arial", 10, "bold"),
        bg="#fef08a", fg="#854d0e", justify="left", wraplength=460
    )
    tooltip_lbl.pack(padx=8, pady=4)
    tooltip.withdraw()

    row_font = tkfont.Font(family="Arial", size=11)

    def on_tree_motion(event):
        region = tree.identify("region", event.x, event.y)
        row_id = tree.identify_row(event.y)
        col = tree.identify_column(event.x)

        if region != "cell" or not row_id or "dummy" in tree.item(row_id, "tags"):
            tooltip.withdraw()
            return

        # Column #6 = WHAT WAS DONE
        if col == "#6":
            vals = tree.item(row_id, "values")
            cell_text = str(vals[5]).strip() if vals and len(vals) > 5 else ""

            if cell_text and cell_text != "—":
                col_w = tree.column("details", "width")
                text_w = row_font.measure(cell_text)
                if text_w > (col_w - 22):
                    tooltip_lbl.config(text=cell_text)
                    tooltip.wm_geometry(f"+{event.x_root + 15}+{event.y_root + 15}")
                    tooltip.deiconify()
                    return

        tooltip.withdraw()

    tree.bind("<Motion>", on_tree_motion)
    tree.bind("<Leave>", lambda e: tooltip.withdraw(), add="+")
    # ----------------------------------------------------------------------

    # Zebra stripe tags + month header + action color tags (matching InvoicesView)
    tree.tag_configure("even", background=theme["stripe_even"], foreground=theme["text"])
    tree.tag_configure("odd", background=theme["stripe_odd"], foreground=theme["text"])
    tree.tag_configure("month_header", background=theme["border"], foreground=theme["text"], font=("Arial", 10, "bold"))
    tree.tag_configure("act_delete", foreground=theme["error"])
    tree.tag_configure("act_create", foreground=theme["accent_green"])
    tree.tag_configure("act_edit", foreground=theme["accent_blue"])

    isolate_tree_scroll(tree)

    def safe_date_parse(date_str):
        for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d-%m-%Y", "%d/%m/%Y", "%m/%d/%Y"):
            try:
                return datetime.strptime(str(date_str).strip()[:10], fmt)
            except Exception:
                pass
        return datetime.min

    def refresh_logs(*args, mark_seen_now=False):
        tooltip.withdraw()
        for item in tree.get_children():
            tree.delete(item)

        cid = getattr(app, "active_company_id", None) or getattr(database, "ACTIVE_COMPANY_ID", 1)
        curr_fmt, date_fmt_code = fetch_global_settings(cid)

        selected_user_id = user_map.get(user_var.get(), "All")
        selected_tab = active_tab_var.get()
        q = search_var.get().strip()

        # Fetch current unseen counts BEFORE marking the active tab as seen so initial badges are visible
        counts_before = database.get_unseen_audit_counts(cid)

        rows = database.get_audit_logs(
            company_id=cid,
            user_id=selected_user_id,
            tab_name=selected_tab,
            search_query=q
        )

        last_month_str = ""
        row_counter = 0

        for idx, r in enumerate(rows, 1):
            _, uid, uname, urole, t_name, act, ref, det, amt, r_date, e_time, is_seen = r

            # Inject 📅 MONTH, YEAR header row just like Invoices main table
            dt = safe_date_parse(r_date)
            current_month_str = dt.strftime("%B, %Y").upper() if dt != datetime.min else "UNKNOWN DATE"
            if current_month_str != last_month_str:
                tree.insert(
                    "", "end", iid=f"dummy_header_{current_month_str}_{idx}",
                    values=(f"📅  {current_month_str}", "", "", "", "", "", "", ""),
                    tags=("month_header", "dummy")
                )
                last_month_str = current_month_str
                row_counter += 1

            disp_date = smart_date_formatter(r_date, date_fmt_code)
            disp_user = f"USR-{int(uid):03d} • {uname}"
            disp_amt = format_currency(amt, curr_fmt) if (amt and float(amt) != 0.0) else "—"
            disp_act = f"● {act}" if (int(is_seen or 0) == 0 and urole != "Admin") else act

            # Dynamically format any embedded @@CURR:val@@ and @@DATE:val@@ tokens using helpers.py
            disp_det = re.sub(
                r"@@CURR:([-+]?\d*\.?\d+)@@",
                lambda m: format_currency(float(m.group(1)), curr_fmt),
                str(det or "")
            )
            disp_det = re.sub(
                r"@@DATE:(.*?)@@",
                lambda m: smart_date_formatter(m.group(1), date_fmt_code),
                disp_det
            )
            if ref and str(ref).strip() and str(ref).strip() != "—" and str(ref).strip() not in disp_det:
                disp_det = f"[{str(ref).strip()}] {disp_det}"

            stripe_tag = "even" if row_counter % 2 == 0 else "odd"
            act_lower = str(act).lower()
            if "delete" in act_lower or "undo" in act_lower:
                tags = (stripe_tag, "act_delete")
            elif any(k in act_lower for k in ("create", "restore", "payment in", "advance in", "clone", "redo")):
                tags = (stripe_tag, "act_create")
            elif any(k in act_lower for k in ("edit", "update", "payment out", "advance out", "refund", "offset", "proof")):
                tags = (stripe_tag, "act_edit")
            else:
                tags = (stripe_tag,)

            tree.insert(
                "", "end",
                values=(disp_date, e_time, disp_user, t_name, disp_act, disp_det, disp_amt, ""),
                tags=tags
            )
            row_counter += 1

        # Pad with dummy zebra rows up to 15 rows just like Invoices main table
        if row_counter < 15:
            for idx in range(row_counter + 1, 16):
                stripe_tag = "even" if idx % 2 == 0 else "odd"
                tree.insert(
                    "", "end", iid=f"dummy_{idx}",
                    values=("", "", "", "", "", "", "", ""),
                    tags=(stripe_tag, "dummy")
                )

        # Mark the currently viewed tab's logs as seen in DB
        if selected_user_id == "All" and not q:
            database.mark_audit_logs_seen(company_id=cid, tab_name=selected_tab)
            refresh_all_header_badges()

        # On initial window open, show counts_before so the Admin sees the badge on the active tab too;
        # when clicking tabs or refreshing, show the updated remaining counts.
        if mark_seen_now:
            update_pill_styles_and_badges(database.get_unseen_audit_counts(cid))
        else:
            update_pill_styles_and_badges(counts_before)

    cb_user.bind("<<ComboboxSelected>>", lambda e: refresh_logs(mark_seen_now=True))
    search_var.trace_add("write", lambda *a: refresh_logs(mark_seen_now=True))
    btn_refresh.config(command=lambda: refresh_logs(mark_seen_now=True))

    refresh_logs(mark_seen_now=False)