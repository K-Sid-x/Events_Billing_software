import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import json
import csv
import tempfile
import webbrowser
import os
from datetime import datetime, date
import sys

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
from views.invoice_parts.helpers import format_currency
from views.invoice_parts.calendar_widget import NativeCalendar

def center_popup(window, w, h):
    window.update_idletasks()
    sw, sh = window.winfo_screenwidth(), window.winfo_screenheight()
    window.geometry(f"{w}x{h}+{int((sw/2)-(w/2))}+{int((sh/2)-(h/2))}")

def add_hover(widget, default_bg, hover_bg):
    widget.bind("<Enter>", lambda e: widget.config(bg=hover_bg))
    widget.bind("<Leave>", lambda e: widget.config(bg=default_bg))

def open_history_popup(stock_view, item_name):
    popup = tk.Toplevel(stock_view)
    popup.title(f"Stock Ledger: {item_name}")
    popup.configure(bg=stock_view.BG); popup.grab_set()
    center_popup(popup, 1300, 750) 

    style = ttk.Style()
    style.configure("Stock.Treeview.Heading", font=("Arial", 9, "bold"), anchor="center")

    current_page = tk.IntVar(popup, value=1)
    items_per_page = 50
    full_filtered_data = [] 
    
    is_bulk_mode = tk.BooleanVar(value=False)
    selected_items = set()

    top_bar = tk.Frame(popup, bg=stock_view.BG)
    top_bar.pack(fill="x", pady=(15, 5), padx=20)
    
    tk.Label(top_bar, text=f"History: {item_name}", font=("Arial", 18, "bold"), bg=stock_view.BG, fg=stock_view.FG).pack(side="left")

    search_var = tk.StringVar()
    search_entry = tk.Entry(top_bar, textvariable=search_var, font=("Arial", 10), width=25, bg=stock_view.CARD, fg=stock_view.FG, insertbackground=stock_view.FG, highlightbackground=stock_view.BORDER, highlightthickness=1)
    search_entry.pack(side="left", padx=(20, 0), ipady=3)
    search_entry.insert(0, "Search records...")
    search_entry.bind("<FocusIn>", lambda args: search_entry.delete('0', 'end') if search_entry.get() == 'Search records...' else None)
    search_entry.bind("<FocusOut>", lambda args: search_entry.insert(0, 'Search records...') if not search_entry.get() else None)

    btn_clear = tk.Button(top_bar, text="✖", font=("Arial", 10, "bold"), bg=stock_view.CARD, fg=stock_view.DANGER, relief="flat", cursor="hand2", command=lambda: [search_var.set("Search records..."), hist_tree.focus_set(), load_history()])
    btn_clear.pack(side="left", padx=(0, 20), ipady=3)
    add_hover(btn_clear, stock_view.CARD, stock_view.BORDER)

    popup.bind("<Control-f>", lambda e: [search_entry.focus_set(), search_entry.select_range(0, tk.END)])

    # --- THE FIX: Inject Local Ledger Undo/Redo Engine ---
    undo_redo_frame = tk.Frame(top_bar, bg=stock_view.BG)
    undo_redo_frame.pack(side="right", padx=(0, 10))

    btn_undo = tk.Button(undo_redo_frame, text="⟲ Undo", font=("Arial", 10, "bold"), bg=stock_view.BG, fg=stock_view.SEC_FG, relief="solid", bd=1, padx=10, pady=3, state="disabled")
    btn_undo.pack(side="left", padx=5)

    btn_redo = tk.Button(undo_redo_frame, text="⟳ Redo", font=("Arial", 10, "bold"), bg=stock_view.BG, fg=stock_view.SEC_FG, relief="solid", bd=1, padx=10, pady=3, state="disabled")
    btn_redo.pack(side="left", padx=5)

    popup.undo_stack = []
    popup.redo_stack = []

    def update_undo_btns():
        if popup.undo_stack:
            btn_undo.config(bg=stock_view.CARD, fg=stock_view.BLUE, state="normal", cursor="hand2")
            add_hover(btn_undo, stock_view.CARD, stock_view.BORDER)
        else:
            btn_undo.config(bg=stock_view.BG, fg=stock_view.SEC_FG, state="disabled", cursor="")
            btn_undo.unbind("<Enter>"); btn_undo.unbind("<Leave>")
            
        if popup.redo_stack:
            btn_redo.config(bg=stock_view.CARD, fg=stock_view.BLUE, state="normal", cursor="hand2")
            add_hover(btn_redo, stock_view.CARD, stock_view.BORDER)
        else:
            btn_redo.config(bg=stock_view.BG, fg=stock_view.SEC_FG, state="disabled", cursor="")
            btn_redo.unbind("<Enter>"); btn_redo.unbind("<Leave>")

    # --- THE FIX: Use safe helpers instead of raw SQL in the UI layer! ---
    def exec_undo(e=None):
        if not popup.undo_stack: return
        act = popup.undo_stack.pop()
        popup.redo_stack.append(act)
        if act['type'] == 'delete_ledger':
            database.restore_stock_records(act['records'])
        update_undo_btns(); stock_view.load_data(); load_history()

    def exec_redo(e=None):
        if not popup.redo_stack: return
        act = popup.redo_stack.pop()
        popup.undo_stack.append(act)
        if act['type'] == 'delete_ledger':
            for r in act['records']:
                database.delete_single_stock_record(r[0])
        update_undo_btns(); stock_view.load_data(); load_history()
    # ----------------------------------------------------------------------

    btn_undo.config(command=exec_undo)
    btn_redo.config(command=exec_redo)
    popup.bind("<Control-z>", exec_undo)
    popup.bind("<Control-y>", exec_redo)
    # -----------------------------------------------------

    action_bar = tk.Frame(popup, bg=stock_view.BG)
    action_bar.pack(fill="x", padx=20, pady=(0, 5))

    std_tools = tk.Frame(action_bar, bg=stock_view.BG)
    std_tools.pack(fill="both", expand=True)

    btn_cols = tk.Menubutton(std_tools, text="⋮ Columns", font=("Arial", 9, "bold"), bg=stock_view.CARD, fg=stock_view.FG, relief="flat", cursor="hand2", padx=10)
    btn_cols.pack(side="right", padx=(5,0))
    col_menu = tk.Menu(btn_cols, tearoff=0, bg=stock_view.CARD, fg=stock_view.FG, activebackground=stock_view.BLUE)
    btn_cols.config(menu=col_menu)
    add_hover(btn_cols, stock_view.CARD, stock_view.BORDER)

    btn_hist_pdf = tk.Button(std_tools, text="🖨️ PDF", font=("Arial", 9, "bold"), bg=stock_view.CARD, fg=stock_view.FG, relief="flat", cursor="hand2")
    btn_hist_pdf.pack(side="right", padx=(5,0)); add_hover(btn_hist_pdf, stock_view.CARD, stock_view.BORDER)
    
    btn_hist_csv = tk.Button(std_tools, text="⭳ CSV", font=("Arial", 9, "bold"), bg=stock_view.CARD, fg=stock_view.FG, relief="flat", cursor="hand2")
    btn_hist_csv.pack(side="right", padx=(5,15)); add_hover(btn_hist_csv, stock_view.CARD, stock_view.BORDER)

    filter_opts = ["All Records", "Additions", "Losses", "Sales", "Custom Range"] if stock_view.b_type == "Sales" else ["All Records", "Additions", "Losses", "Custom Range"]
    
    history_filter_var = tk.StringVar(popup, value="All Records")
    history_combo = ttk.Combobox(std_tools, textvariable=history_filter_var, values=filter_opts, state="readonly", width=14, style="Theme.TCombobox", cursor="hand2")
    history_combo.pack(side="right")

    tk.Label(std_tools, text="Filter:", font=("Arial", 10, "bold"), bg=stock_view.BG, fg=stock_view.SEC_FG).pack(side="right", padx=(10, 5))

    date_frame = tk.Frame(std_tools, bg=stock_view.BG)

    # --- THE FIX: Leave custom range dates completely blank by default ---
    from_var = tk.StringVar(value="")
    to_var = tk.StringVar(value="")
    # ---------------------------------------------------------------------

    tk.Label(date_frame, text="From:", bg=stock_view.BG, fg=stock_view.SEC_FG, font=("Arial", 9, "bold")).pack(side="left")
    from_cont = tk.Frame(date_frame, bg=stock_view.BG); from_cont.pack(side="left", padx=(2, 10))
    entry_from = tk.Entry(from_cont, textvariable=from_var, width=12, font=("Arial", 10), justify="center", bg=stock_view.CARD, fg=stock_view.FG, insertbackground=stock_view.FG, highlightbackground=stock_view.BORDER, highlightthickness=1)
    entry_from.pack(side="left", ipady=2)
    tk.Button(from_cont, text="📅", font=("Arial", 9), bg=stock_view.CARD, fg=stock_view.FG, relief="flat", cursor="hand2", command=lambda: NativeCalendar(popup, from_var)).pack(side="left", padx=(2,0))

    tk.Label(date_frame, text="To:", bg=stock_view.BG, fg=stock_view.SEC_FG, font=("Arial", 9, "bold")).pack(side="left")
    to_cont = tk.Frame(date_frame, bg=stock_view.BG); to_cont.pack(side="left", padx=(2, 5))
    entry_to = tk.Entry(to_cont, textvariable=to_var, width=12, font=("Arial", 10), justify="center", bg=stock_view.CARD, fg=stock_view.FG, insertbackground=stock_view.FG, highlightbackground=stock_view.BORDER, highlightthickness=1)
    entry_to.pack(side="left", ipady=2)
    tk.Button(to_cont, text="📅", font=("Arial", 9), bg=stock_view.CARD, fg=stock_view.FG, relief="flat", cursor="hand2", command=lambda: NativeCalendar(popup, to_var)).pack(side="left", padx=(2,0))

    # --- THE FIX: Replaced 'Apply' with Red 'Cancel', and added real-time Trace triggers! ---
    def cancel_custom_range():
        history_filter_var.set("All Records")
        date_frame.pack_forget()
        load_history()

    btn_cancel_date = tk.Button(date_frame, text="✖ Cancel", bg=stock_view.DANGER, fg="#ffffff", relief="flat", cursor="hand2", font=("Arial", 8, "bold"), command=cancel_custom_range)
    btn_cancel_date.pack(side="left", padx=(5,0))

    def toggle_date_frame(*args):
        if history_filter_var.get() == "Custom Range": 
            date_frame.pack(side="right", padx=10)
            load_history() 
        else: 
            date_frame.pack_forget()
            load_history()

    history_combo.bind("<<ComboboxSelected>>", toggle_date_frame)
    
    from_var.trace("w", lambda *args: load_history())
    to_var.trace("w", lambda *args: load_history())
    search_entry.bind("<KeyRelease>", lambda e: load_history())
    # ----------------------------------------------------------------------------------------

    bulk_tools = tk.Frame(action_bar, bg=stock_view.BG)
    
    lbl_bulk_mode = tk.Label(bulk_tools, text="Delete Mode Active", font=("Arial", 11, "bold"), bg=stock_view.BG, fg=stock_view.DANGER)
    lbl_bulk_mode.pack(side="left", padx=(0, 15))
    
    def toggle_select_all():
        start = (current_page.get() - 1) * items_per_page
        visible_ids = set(row[0][0] for row in full_filtered_data[start : start + items_per_page])
        if not visible_ids: return
        if visible_ids.issubset(selected_items): selected_items.difference_update(visible_ids)
        else: selected_items.update(visible_ids)
        btn_bulk_delete.config(text=f"🗑 Confirm Delete ({len(selected_items)})")
        render_page()

    btn_select_all = tk.Button(bulk_tools, text="☑ Select Visible", font=("Arial", 10, "bold"), bg=stock_view.CARD, fg=stock_view.FG, relief="flat", cursor="hand2", padx=15, pady=5, command=toggle_select_all)
    btn_select_all.pack(side="left", padx=(0, 10)); add_hover(btn_select_all, stock_view.CARD, stock_view.BORDER)

    def cancel_bulk_mode():
        is_bulk_mode.set(False); selected_items.clear()
        bulk_tools.pack_forget(); std_tools.pack(fill="both", expand=True)
        hist_tree.heading("sno_sel", text="S.NO")
        load_history()

    btn_cancel_bulk = tk.Button(bulk_tools, text="Cancel", font=("Arial", 10, "bold"), bg=stock_view.CARD, fg=stock_view.FG, relief="flat", cursor="hand2", padx=15, pady=5, command=cancel_bulk_mode)
    btn_cancel_bulk.pack(side="left", padx=(0, 10)); add_hover(btn_cancel_bulk, stock_view.CARD, stock_view.BORDER)
    
    def confirm_bulk_delete():
        if not selected_items: 
            cancel_bulk_mode()
            return
            
        allowed, err_msg = database.check_stock_permission(action="delete", company_id=stock_view.comp_id)
        if not allowed:
            messagebox.showerror("Access Denied", err_msg, parent=popup)
            return
            
        if messagebox.askyesno("Confirm Delete", f"Permanently delete {len(selected_items)} historical records?\n\nThis will permanently alter inventory balances.", parent=popup):
            try:
                database.log_audit("Stock", "Ledger Bulk Deleted", record_ref=item_name, details=f"Deleted {len(selected_items)} history records from the ledger.", company_id=stock_view.comp_id)
                deleted_records = []
                for rec_id in list(selected_items):
                    row = database.get_stock_record(rec_id)
                    if row: deleted_records.append(row)
                    database.delete_single_stock_record(rec_id)
                
                if deleted_records and hasattr(popup, 'undo_stack'):
                    popup.undo_stack.append({"type": "delete_ledger", "records": deleted_records})
                    if len(popup.undo_stack) > 20: popup.undo_stack.pop(0)
                    popup.redo_stack.clear()
                    update_undo_btns()
                    
                stock_view.load_data()
                cancel_bulk_mode()
            except Exception as e:
                messagebox.showerror("System Error", f"Failed to delete records: {e}", parent=popup)

    btn_bulk_delete = tk.Button(bulk_tools, text="🗑 Confirm Delete (0)", font=("Arial", 10, "bold"), bg=stock_view.DANGER, fg="#ffffff", relief="flat", cursor="hand2", padx=15, pady=5, command=confirm_bulk_delete)
    btn_bulk_delete.pack(side="right")

    def enable_bulk_mode(initial_item=None):
        is_bulk_mode.set(True); selected_items.clear()
        if initial_item: selected_items.add(initial_item)
        std_tools.pack_forget(); bulk_tools.pack(fill="both", expand=True)
        hist_tree.heading("sno_sel", text="☑")
        btn_bulk_delete.config(text=f"🗑 Confirm Delete ({len(selected_items)})")
        render_page()

    summary_frame = tk.Frame(popup, bg=stock_view.CARD, highlightbackground=stock_view.BORDER, highlightthickness=1, padx=10, pady=15)
    summary_frame.pack(fill="x", padx=20, pady=(10, 10))

    # --- THE FIX: Massive, easy-to-read Data Tiles for the Ledger ---
    def make_big_label(parent, title, color):
        f = tk.Frame(parent, bg=stock_view.CARD)
        tk.Label(f, text=title, font=("Arial", 9, "bold"), bg=stock_view.CARD, fg=stock_view.SEC_FG).pack(anchor="center")
        lbl = tk.Label(f, text="0", font=("Arial", 18, "bold"), bg=stock_view.CARD, fg=color)
        lbl.pack(anchor="center", pady=(2, 0))
        f.pack(side="left", expand=True)
        return lbl

    lbl_added = make_big_label(summary_frame, "TOTAL ADDED", stock_view.GREEN)
    lbl_loss = make_big_label(summary_frame, "TOTAL LOSS", stock_view.DANGER)
    
    if stock_view.b_type == "Sales":
        lbl_sold = make_big_label(summary_frame, "TOTAL SOLD", stock_view.PURPLE)
        
    lbl_net = make_big_label(summary_frame, "NET QTY", stock_view.FG)
    lbl_val = make_big_label(summary_frame, "NET VALUE", stock_view.BLUE)
    
    ls_f = tk.Frame(summary_frame, bg=stock_view.CARD)
    tk.Label(ls_f, text="LOW STOCK ALERT", font=("Arial", 9, "bold"), bg=stock_view.CARD, fg=stock_view.SEC_FG).pack(anchor="center")
    lbl_low_stock = tk.Label(ls_f, text="0 ✏️", font=("Arial", 16, "bold"), bg=stock_view.CARD, fg=stock_view.YELLOW, cursor="hand2")
    lbl_low_stock.pack(anchor="center", pady=(2, 0))
    ls_f.pack(side="left", expand=True)
    # ----------------------------------------------------------------

    def edit_reorder_lvl(event):
        new_lvl = simpledialog.askfloat("Update Settings", f"Enter new Low Stock Alert level for {item_name}:", parent=popup)
        if new_lvl is not None and new_lvl >= 0:
            # --- THE FIX: Company-isolated, high-speed bulk updater ---
            database.bulk_update_stock_reorder_level(item_name, new_lvl, getattr(stock_view, "comp_id", 1))
            load_history()
            stock_view.load_data()
            
    lbl_low_stock.bind("<Double-1>", edit_reorder_lvl)

    tree_frame = tk.Frame(popup, bg=stock_view.CARD); tree_frame.pack(fill="both", expand=True, padx=20, pady=(0, 5))
    
    # --- THE FIX: Implement App-Wide Standardized Custom Scrollbars ---
    scroll_y = ttk.Scrollbar(tree_frame, orient="vertical", style="Stock.Vertical.TScrollbar")
    scroll_x = ttk.Scrollbar(tree_frame, orient="horizontal", style="Stock.Horizontal.TScrollbar")
    # ------------------------------------------------------------------

    is_sales = (stock_view.b_type == "Sales")
    
    # --- THE FIX: MVC Compliant GST Toggle Fetch ---
    has_gst = database.get_company_gst_toggle(getattr(stock_view, "comp_id", 1))
    # -----------------------------------------------
    
    # --- THE FIX: Add 'ghost' column to cleanly absorb table width expansion ---
    if is_sales:
        all_cols = ["sno_sel", "date", "type", "qty", "price", "balance", "mrp", "base", "gst", "hsn", "sku", "vendor", "batch", "expiry", "notes", "ghost"]
        default_visible = ["sno_sel", "date", "type", "qty", "price", "balance", "mrp", "base", "gst", "vendor", "notes", "ghost"]
    else:
        all_cols = ["sno_sel", "date", "type", "qty", "price", "base", "gst", "hsn", "vendor", "notes", "ghost"]
        default_visible = list(all_cols)
    # ---------------------------------------------------------------------------

    if not has_gst:
        for hidden_c in ["base", "gst", "hsn"]:
            if hidden_c in default_visible: default_visible.remove(hidden_c)
    
    all_cols = tuple(all_cols)

    hist_tree = ttk.Treeview(tree_frame, columns=all_cols, show="headings", height=12, style="Stock.Treeview", yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)
    scroll_y.config(command=hist_tree.yview)
    scroll_x.config(command=hist_tree.xview)

    default_widths = {
        "sno_sel": 50, "date": 100, "type": 90, "qty": 70, "price": 90, "balance": 90, "mrp": 90, "base": 90,
        "gst": 50, "hsn": 70, "sku": 90, "vendor": 110, "batch": 80, "expiry": 80, 
        "notes": 250
    }
    comp_id_val = getattr(stock_view, "comp_id", 1)
    try:
        raw_setting = database.get_ui_setting(f"stock_hist_cols_{comp_id_val}", "{}")
        h_w_dict = json.loads(raw_setting) if raw_setting else {}
        for k, v in default_widths.items():
            if k not in h_w_dict: h_w_dict[k] = v
    except Exception:
        h_w_dict = default_widths

    for col in all_cols: 
        if col == "ghost":
            hist_tree.heading(col, text="", anchor="center")
            hist_tree.column(col, width=10, minwidth=10, stretch=True)
            continue
            
        if col == "sno_sel": header_text = "S.NO"
        elif col == "price": header_text = "COST" if is_sales else ("PRICE (INC GST)" if has_gst else "PRICE")
        elif col == "base": header_text = "BASE MRP" if is_sales else "BASE RATE"
        elif col == "mrp": header_text = "MRP (INC)" if has_gst else "MRP"
        else: header_text = col.upper()
        
        hist_tree.heading(col, text=header_text, anchor="center")
        w = h_w_dict.get(col, 100) 
        
        # --- THE FIX: Stop notes from absorbing the stretch! Give it entirely to Ghost! ---
        if col == "notes":
            hist_tree.column(col, width=w, minwidth=100, stretch=False, anchor="w")
        else:
            hist_tree.column(col, width=w, minwidth=40, stretch=False, anchor="center")
        # ----------------------------------------------------------------------------------

    def save_hist_widths():
        # --- THE FIX: Skip Ghost when saving constraints ---
        new_w = {c: hist_tree.column(c, "width") for c in hist_tree["columns"] if c != "ghost"}
        try:
            import json
            database.save_ui_setting(f"stock_hist_cols_{comp_id_val}", json.dumps(new_w))
        except: pass

    def on_hist_sep_drag(event):
        if hist_tree.identify_region(event.x, event.y) == "separator":
            popup.after(50, save_hist_widths)

    hist_tree.bind("<B1-Motion>", on_hist_sep_drag, add="+")
    hist_tree.bind("<ButtonRelease-1>", lambda e: popup.after(50, save_hist_widths) if hist_tree.identify_region(e.x, e.y) == "separator" else None, add="+")

    scroll_y.pack(side="right", fill="y")
    scroll_x.pack(side="bottom", fill="x")
    hist_tree.pack(side="left", fill="both", expand=True)

    hist_tree.tag_configure("evenrow", background=stock_view.BG, foreground=stock_view.FG)
    hist_tree.tag_configure("oddrow", background=stock_view.CARD, foreground=stock_view.FG)
    hist_tree.tag_configure("selected_row", background=stock_view.BORDER)

    # --- THE FIX: Buttery smooth X/Y Scrolling ---
    def _fast_scroll(event, direction):
        delta = -1 * (event.delta / 120) if os.name == 'nt' else -1 * event.delta
        if direction == "y":
            hist_tree.yview_moveto(hist_tree.yview()[0] + (delta * 0.008))
        else:
            hist_tree.xview_moveto(hist_tree.xview()[0] + (delta * 0.02))
            
    hist_tree.bind("<MouseWheel>", lambda e: _fast_scroll(e, "y"))
    hist_tree.bind("<Shift-MouseWheel>", lambda e: _fast_scroll(e, "x"))
    # ---------------------------------------------

    col_vars = {}
    def update_display_cols(*args):
        # --- THE FIX: Make sure the Ghost column is always visible to hold the stretch! ---
        visible_cols = [c for c in all_cols if c in ["notes", "ghost"] or (c in col_vars and col_vars[c].get())]
        hist_tree["displaycolumns"] = visible_cols
        
        for col in all_cols: 
            if col == "ghost": hist_tree.column(col, stretch=True)
            else: hist_tree.column(col, stretch=False)

    for col in all_cols:
        if col in ["notes", "ghost"]: continue 
        if not has_gst and col in ["base", "gst", "hsn"]: continue
        
        col_vars[col] = tk.BooleanVar(popup, value=(col in default_visible))
        col_menu.add_checkbutton(label=hist_tree.heading(col)["text"], variable=col_vars[col], command=update_display_cols)
        
    update_display_cols()

    def on_popup_close():
        popup.destroy()

    popup.protocol("WM_DELETE_WINDOW", on_popup_close)
    popup.bind("<Escape>", lambda e: on_popup_close())

    pag_frame = tk.Frame(popup, bg=stock_view.BG); pag_frame.pack(fill="x", pady=(0, 15))
    center_pag = tk.Frame(pag_frame, bg=stock_view.BG); center_pag.pack(anchor="center") 
    
    btn_prev = tk.Button(center_pag, text="< Previous", font=("Arial", 10, "bold"), bg=stock_view.CARD, fg=stock_view.FG, relief="flat", cursor="hand2", padx=12, pady=3)
    btn_prev.pack(side="left", padx=5)
    lbl_page = tk.Label(center_pag, text="Page 1 of 1", font=("Arial", 10, "bold"), bg=stock_view.BG, fg=stock_view.SEC_FG)
    lbl_page.pack(side="left", padx=15)
    btn_next = tk.Button(center_pag, text="Next >", font=("Arial", 10, "bold"), bg=stock_view.CARD, fg=stock_view.FG, relief="flat", cursor="hand2", padx=12, pady=3)
    btn_next.pack(side="left", padx=5)

    def change_page(delta):
        current_page.set(current_page.get() + delta)
        render_page()

    btn_prev.config(command=lambda: change_page(-1))
    btn_next.config(command=lambda: change_page(1))

    def load_history(*args):
        nonlocal full_filtered_data
        
        # --- THE FIX: MVC Compliant History & Reorder Fetch ---
        history = database.get_stock_history_asc(item_name)
        reorder_lvl = database.get_stock_reorder_level(item_name, getattr(stock_view, "comp_id", 1))
        # ------------------------------------------------------
        
        lbl_low_stock.config(text=f"{reorder_lvl:g} ✏️")
        # --------------------------------------------------------------------------------------------------

        if not history: return

        def safe_date_parse(d_str):
            for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y"):
                try: return datetime.strptime(d_str, fmt)
                except: pass
            return datetime.min
                
        history.sort(key=lambda x: (safe_date_parse(x[3]), int(x[0])))

        current_filter = history_filter_var.get()
        f_start, f_end = None, None
        
        # --- THE FIX: Real-time safe parsing using the global safe_date_parse engine! ---
        if current_filter == "Custom Range":
            f_start = safe_date_parse(from_var.get().strip())
            f_end = safe_date_parse(to_var.get().strip())
            
            # If dates are invalid (e.g., user is currently typing), silently ignore the filter
            # instead of throwing an annoying error box.
            if f_start == datetime.min or f_end == datetime.min:
                f_start, f_end = None, None
            else:
                # Ensure the math doesn't break if start date is after end date
                if f_start > f_end:
                    f_start, f_end = f_end, f_start
        # --------------------------------------------------------------------------------

        search_query = search_var.get().strip().lower()
        if search_query == "search records...": search_query = ""

        running_balance = 0.0
        processed_data = []
        tot_add, tot_loss, tot_sold, net_val = 0.0, 0.0, 0.0, 0.0

        for h in history:
            rec_id, qty, price, rec_date, notes_raw, t_type = h[0], h[1], h[2], h[3], h[4], h[5]
            
            if t_type == 'ADD': running_balance += qty
            elif t_type in ('SOLD', 'LOSS'): running_balance -= qty
            
            if current_filter == "Additions" and t_type != 'ADD': continue
            if current_filter == "Losses" and t_type != 'LOSS': continue
            if current_filter == "Sales" and t_type != 'SOLD': continue
            
            if f_start and f_end:
                d_obj = safe_date_parse(rec_date)
                if d_obj != datetime.min and not (f_start <= d_obj <= f_end): continue

            if t_type == 'ADD': tot_add += qty; net_val += (qty * price)
            elif t_type == 'SOLD': tot_sold += qty; net_val -= (qty * price)
            else: tot_loss += qty; net_val -= (qty * price)

            try: display_date = safe_date_parse(rec_date).strftime(stock_view.date_fmt_code)
            except: display_date = rec_date

            mrp_val, gst_val, hsn_val, sku_val, vendor_val, batch_val, exp_val, clean_note = "", "", "", "", "", "", "", ""
            gst_pct, m_num = 0.0, 0.0
            
            try:
                j = json.loads(notes_raw)
                clean_note = j.get("notes", "")
                m = j.get("mrp")
                if m and float(m) > 0: 
                    m_num = float(m)
                    mrp_val = format_currency(m_num, stock_view.curr_fmt)
                    
                gst_val = j.get("gst", "")
                if gst_val and gst_val != "0%":
                    try: gst_pct = float(gst_val.replace('%', '').strip())
                    except: pass
                if gst_val == "0%": gst_val = ""
                
                hsn_val, sku_val = j.get("hsn", ""), j.get("sku", "")
                vendor_val, batch_val, exp_val = j.get("vendor", ""), j.get("batch", ""), j.get("expiry", "")
            except: clean_note = notes_raw

            base_val = ""
            if is_sales:
                if t_type == 'ADD' or t_type == 'LOSS':
                    if m_num > 0:
                        b_amt = m_num / (1 + (gst_pct/100)) if gst_pct > 0 else m_num
                        base_val = format_currency(b_amt, stock_view.curr_fmt)
                else: 
                    if price > 0:
                        b_amt = price / (1 + (gst_pct/100)) if gst_pct > 0 else price
                        base_val = format_currency(b_amt, stock_view.curr_fmt)
            else: 
                if price > 0:
                    b_amt = price / (1 + (gst_pct/100)) if gst_pct > 0 else price
                    base_val = format_currency(b_amt, stock_view.curr_fmt)

            if search_query:
                search_pool = f"{display_date} {t_type} {qty} {price} {mrp_val} {base_val} {clean_note} {vendor_val} {batch_val} {sku_val} {hsn_val}".lower()
                if search_query not in search_pool: continue
            
            # --- THE FIX: Pad the data with an empty string for the Ghost Column! ---
            if is_sales: 
                row_vals = [rec_id, display_date, t_type, f"{qty:g}", format_currency(price, stock_view.curr_fmt), f"{running_balance:g}", mrp_val, base_val, gst_val, hsn_val, sku_val, vendor_val, batch_val, exp_val, clean_note, ""]
            else: 
                row_vals = [rec_id, display_date, t_type, f"{qty:g}", format_currency(price, stock_view.curr_fmt), base_val, gst_val, hsn_val, vendor_val, clean_note, ""]
                
            processed_data.append((row_vals, "row"))

        # --- THE FIX: Inject purely the raw numbers into the massive fonts! ---
        lbl_added.config(text=f"{tot_add:g}")
        lbl_loss.config(text=f"{tot_loss:g}")
        if stock_view.b_type == "Sales": 
            lbl_sold.config(text=f"{tot_sold:g}")
            lbl_net.config(text=f"{(tot_add - tot_loss - tot_sold):g}")
        else:
            lbl_net.config(text=f"{(tot_add - tot_loss):g}")
            
        lbl_val.config(text=f"{format_currency(net_val, stock_view.curr_fmt)}")
        # ----------------------------------------------------------------------

        processed_data.reverse()
        full_filtered_data = processed_data
        current_page.set(1)
        render_page()

    def render_page():
        for item in hist_tree.get_children(): hist_tree.delete(item)
        
        total_items = len(full_filtered_data)
        total_pages = max(1, (total_items + items_per_page - 1) // items_per_page)
        
        cp = current_page.get()
        if cp < 1: cp = 1; current_page.set(1)
        if cp > total_pages: cp = total_pages; current_page.set(total_pages)
        
        lbl_page.config(text=f"Page {cp} of {total_pages}")
        btn_prev.config(state="normal" if cp > 1 else "disabled", bg=stock_view.CARD if cp > 1 else stock_view.BG)
        btn_next.config(state="normal" if cp < total_pages else "disabled", bg=stock_view.CARD if cp < total_pages else stock_view.BG)

        start_idx = (cp - 1) * items_per_page
        page_data = full_filtered_data[start_idx : start_idx + items_per_page]

        visible_idx = 1
        for row_vals, tag_type in page_data:
            rec_id = row_vals[0]
            display_vals = list(row_vals)
            
            display_vals[0] = ("☑" if rec_id in selected_items else "☐") if is_bulk_mode.get() else (start_idx + visible_idx)
            
            base_tag = "selected_row" if is_bulk_mode.get() and rec_id in selected_items else ("evenrow" if visible_idx % 2 == 0 else "oddrow")
            hist_tree.insert("", "end", iid=str(rec_id), values=display_vals, tags=(base_tag,))
            visible_idx += 1
            
        for i in range(visible_idx, items_per_page + 1):
            tag = "evenrow" if i % 2 == 0 else "oddrow"
            hist_tree.insert("", "end", values=["" for _ in all_cols], tags=(tag, "empty"))

    def delete_single_record():
        selected = hist_tree.selection()
        if not selected: return
        rec_id_str = selected[0]
        if "empty" in hist_tree.item(rec_id_str, "tags"): return
        
        allowed, err_msg = database.check_stock_permission(action="delete", company_id=stock_view.comp_id)
        if not allowed:
            messagebox.showerror("Access Denied", err_msg, parent=popup)
            return
        
        if messagebox.askyesno("Confirm Delete", "Permanently delete this individual transaction record?", parent=popup):
            try:
                rec_id = int(rec_id_str)
                row = database.get_stock_record(rec_id)
                database.log_audit("Stock", "Ledger Row Deleted", record_ref=item_name, details=f"Deleted a specific history record from the ledger.", company_id=stock_view.comp_id)
                
                if row and hasattr(popup, 'undo_stack'):
                    popup.undo_stack.append({"type": "delete_ledger", "records": [row]})
                    if len(popup.undo_stack) > 20: popup.undo_stack.pop(0)
                    popup.redo_stack.clear()
                    update_undo_btns()
                    
                database.delete_single_stock_record(rec_id)
                
                stock_view.load_data()
                load_history()
            except Exception as e:
                messagebox.showerror("System Error", f"Failed to delete record: {e}", parent=popup)

    def on_right_click(event):
        rec_id = hist_tree.identify_row(event.y)
        if not rec_id or "empty" in hist_tree.item(rec_id, "tags"): return
        hist_tree.selection_set(rec_id)
        
        menu = tk.Menu(popup, tearoff=0, font=("Arial", 10), bg=stock_view.CARD, fg=stock_view.FG, activebackground=stock_view.BLUE)
        if not is_bulk_mode.get():
            # --- THE FIX: Using lambda r=rec_id ensures the memory footprint never gets garbage collected! ---
            menu.add_command(label="☑ Select for Bulk Action", command=lambda r=rec_id: enable_bulk_mode(int(r)))
            menu.add_separator()
            # --- THE FIX: Trigger delete directly off the active selection to avoid lambda memory leaks entirely! ---
            menu.add_command(label="❌ Delete", command=delete_single_record, foreground=stock_view.DANGER)
            menu.add_command(label="🗑 Bulk Delete", command=lambda r=rec_id: enable_bulk_mode(int(r)), foreground=stock_view.DANGER)
        else:
            menu.add_command(label="Cancel Selection", command=cancel_bulk_mode)
            
        menu.tk_popup(event.x_root, event.y_root)

    hist_tree.bind("<Button-3>", on_right_click)

    def on_tree_bg_click(event):
        region = hist_tree.identify("region", event.x, event.y)
        if region == "separator":
            return
            
        item = hist_tree.identify_row(event.y)
        if not item or "empty" in hist_tree.item(item, "tags") or region == "nothing":
            # 10ms delay defeats the Tkinter ghosting race condition!
            popup.after(10, lambda: hist_tree.selection_remove(hist_tree.selection()) if hist_tree.selection() else None)
            return "break"

    def enforce_selection(e):
        for i in hist_tree.selection():
            if "empty" in hist_tree.item(i, "tags"): 
                hist_tree.selection_remove(i)

    def on_left_click(event):
        if not is_bulk_mode.get(): return
        if hist_tree.identify("region", event.x, event.y) == "cell":
            rec_id_str = hist_tree.identify_row(event.y)
            if not rec_id_str or "empty" in hist_tree.item(rec_id_str, "tags"): return
            
            rec_id = int(rec_id_str)
            if rec_id in selected_items: selected_items.remove(rec_id)
            else: selected_items.add(rec_id)
            
            btn_bulk_delete.config(text=f"🗑 Confirm Delete ({len(selected_items)})")
            render_page()

    hist_tree.bind("<ButtonPress-1>", on_tree_bg_click)
    hist_tree.bind("<<TreeviewSelect>>", enforce_selection)
    hist_tree.bind("<ButtonRelease-1>", on_left_click)

    def on_tree_double_click(event):
        if is_bulk_mode.get(): return
        region = hist_tree.identify("region", event.x, event.y)
        if region != "cell": return
        
        allowed, err_msg = database.check_stock_permission(action="history_edit", company_id=stock_view.comp_id)
        if not allowed:
            messagebox.showerror("Access Denied", err_msg, parent=popup)
            return
            
        col = hist_tree.identify_column(event.x)
        row_id_str = hist_tree.identify_row(event.y)
        if not row_id_str or "empty" in hist_tree.item(row_id_str, "tags"): return 
        
        visual_idx = int(col[1:]) - 1
        display_cols = hist_tree["displaycolumns"]
        if visual_idx >= len(display_cols): return
        col_name = display_cols[visual_idx]
        
        if col_name not in ["notes", "vendor", "batch", "sku", "expiry"]: 
            return
            
        type_idx = all_cols.index("type")
        row_type = hist_tree.item(row_id_str, "values")[type_idx]
        if "ADD" not in row_type and col_name in ["vendor", "batch", "sku", "expiry"]:
            messagebox.showwarning("Data Integrity Lock", "Vendor and Supply data can only be edited on 'ADD' (Purchase) records to maintain accurate accounting.\n\nPlease use the 'Notes' field for internal auditing.", parent=popup)
            return
            
        absolute_idx = all_cols.index(col_name)
        val = hist_tree.item(row_id_str, "values")[absolute_idx]

        if col_name == "vendor" and str(val).strip() != "":
            messagebox.showinfo("Locked", "Vendor is already assigned and cannot be edited. Please use the Notes field for amendments.", parent=popup)
            return

        x, y, w, h = hist_tree.bbox(row_id_str, col)
        
        entry = tk.Entry(hist_tree, font=("Arial", 10), bg=stock_view.BG, fg=stock_view.FG, insertbackground=stock_view.FG, highlightbackground=stock_view.BORDER, highlightthickness=1)
        entry.place(x=x, y=y, width=w, height=h)
        entry.insert(0, val)
        entry.focus_set()
        
        lb = None
        if col_name == "vendor":
            # --- THE FIX: MVC Compliant Customer List Fetch ---
            party_names = database.get_unique_customer_names(getattr(stock_view, "comp_id", 1))
            # --------------------------------------------------

            lb = tk.Listbox(hist_tree, font=("Arial", 10), height=4, bg=stock_view.BG, fg=stock_view.FG, selectbackground=stock_view.BLUE, highlightthickness=1, highlightbackground=stock_view.BORDER, cursor="hand2")

            def update_vendor_list(*args):
                s = entry.get().lower(); lb.delete(0, tk.END)
                m = [i for i in party_names if s in i.lower() and s != i.lower()]
                if s and m:
                    lb.place(x=x, y=y+h, width=w)
                    for match in m: lb.insert(tk.END, match)
                    lb.lift()
                else: lb.place_forget()

            entry.bind("<KeyRelease>", update_vendor_list)
            entry.bind("<Down>", lambda e: (lb.focus(), lb.selection_set(0)) if lb.winfo_ismapped() else None)

            def select_from_list(e=None):
                if lb.curselection():
                    entry.delete(0, tk.END)
                    entry.insert(0, lb.get(lb.curselection()[0]))
                    lb.place_forget()
                    save_edit()

            lb.bind("<Return>", select_from_list)
            lb.bind("<Double-Button-1>", select_from_list)
        
        def save_edit(e=None):
            new_val = entry.get()
            vals = list(hist_tree.item(row_id_str, "values"))
            vals[absolute_idx] = new_val
            hist_tree.item(row_id_str, values=vals)
            
            entry.destroy()
            if lb: lb.destroy()
            
            try:
                row = database.get_stock_record(row_id_str)
                raw_json = row[6] if row else "{}"
                try: j = json.loads(raw_json)
                except: j = {"notes": raw_json}
                
                j[col_name] = new_val
                
                database.update_stock_notes(row_id_str, json.dumps(j))
                database.log_audit("Stock", "Ledger Cell Edited", record_ref=item_name, details=f"Edited '{col_name}' field to '{new_val}' in history ledger.", company_id=stock_view.comp_id)
            except Exception as ex: print(ex)
            
        entry.bind("<Return>", save_edit)
        
        def check_focus(e=None):
            fw = popup.focus_get()
            if fw != entry and fw != lb:
                save_edit()
                
        entry.bind("<FocusOut>", lambda e: popup.after(150, check_focus))

    hist_tree.bind("<Double-1>", on_tree_double_click)

    def _get_export_data():
        # --- THE FIX: Block the Ghost Column from entering the PDF/CSV Exports! ---
        visible_keys = [c for c in hist_tree["displaycolumns"] if c != "ghost"]
        data = []
        for idx, (row_vals, tag) in enumerate(full_filtered_data):
            row_data = []
            for col_key in visible_keys:
                c_idx = all_cols.index(col_key)
                val = str(row_vals[c_idx])
                if col_key == "sno_sel": val = idx + 1 
                row_data.append(val)
            data.append(row_data)
        
        export_headers = [hist_tree.heading(c)["text"] for c in visible_keys]
        return export_headers, data

    def _export_hist_csv():
        headers, data = _get_export_data()
        if not data: return
        filepath = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")], title="Export Ledger", parent=popup)
        if not filepath: return
        try:
            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(headers)
                writer.writerows(data)
            messagebox.showinfo("Success", "Ledger exported!", parent=popup)
        except Exception as e: messagebox.showerror("Error", str(e), parent=popup)

    def _export_hist_pdf():
        headers, data = _get_export_data()
        if not data: return
        try:
            fd, filepath = tempfile.mkstemp(suffix=".html", prefix="Stock_Ledger_Report_")
            # --- THE FIX: Forces Landscape Printing mode (@page { size: landscape; }) and forbids text from wrapping (white-space: nowrap;) ---
            html = f"<html><head><style>@page {{ size: landscape; margin: 10mm; }} body{{font-family:Arial;padding:10px;font-size:11px;}}table{{width:100%;border-collapse:collapse;margin-top:15px;}}th,td{{border:1px solid #cbd5e1;padding:6px;text-align:left;white-space:nowrap;}}th{{background:#f8fafc;}}</style></head><body><h2>Audit Ledger: {item_name}</h2><table><tr>"
            # ----------------------------------------------------------------------------------------------------------------------------------
            for h in headers: html += f"<th>{h}</th>"
            html += "</tr>"
            for row in data:
                html += "<tr>"
                for cell in row: html += f"<td>{cell}</td>"
                html += "</tr>"
            html += "</table><script>window.print();</script></body></html>"
            with os.fdopen(fd, 'w', encoding='utf-8') as f: f.write(html)
            webbrowser.open(filepath)
        except Exception as e: messagebox.showerror("Error", str(e), parent=popup)

    btn_hist_csv.config(command=_export_hist_csv)
    btn_hist_pdf.config(command=_export_hist_pdf)

    def drop_focus(event):
        try:
            w_class = event.widget.winfo_class()
            if w_class not in ('Entry', 'Text', 'TCombobox', 'Listbox', 'Button', 'Treeview', 'Scrollbar', 'TScrollbar'):
                popup.focus_set()
                # --- THE FIX: Wipe the table highlight when clicking ANYWHERE away from the table! ---
                if hist_tree.selection():
                    hist_tree.selection_remove(hist_tree.selection())
        except: pass

    def bind_focus_drop(container):
        container.bind("<ButtonPress-1>", drop_focus, add="+")
        for child in container.winfo_children():
            if child.winfo_class() in ('Frame', 'Label', 'Canvas', 'Treeview'):
                bind_focus_drop(child)
                
    bind_focus_drop(popup)

    load_history()