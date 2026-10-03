import csv
import tempfile
import os
import sys
import webbrowser
import json
import re
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

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

def add_hover(widget, default_bg, hover_bg):
    widget.bind("<Enter>", lambda e: widget.config(bg=hover_bg))
    widget.bind("<Leave>", lambda e: widget.config(bg=default_bg))

def export_csv(inv_view):
    parsed = inv_view.get_parsed_data()
    if inv_view.is_bulk_mode and inv_view.selected_items:
        parsed = [i for i in parsed if i['id'] in inv_view.selected_items]
        
    if not parsed:
        messagebox.showinfo("Export", "No data to export.")
        return

    filepath = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV Files", "*.csv")], title="Export Catalog")
    if not filepath: return

    try:
        with open(filepath, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            if getattr(inv_view, 'has_gst', True):
                writer.writerow(["Item Name", "Category", "Unit", "HSN/SAC", "Rate / Unit", "Description"])
                for i in parsed:
                    writer.writerow([i['name'], i['category'], i['unit'], i['hsn'], f"{i['rate']:.2f}", i['desc']])
            else:
                writer.writerow(["Item Name", "Category", "Unit", "Rate / Unit", "Description"])
                for i in parsed:
                    writer.writerow([i['name'], i['category'], i['unit'], f"{i['rate']:.2f}", i['desc']])
                    
        messagebox.showinfo("Success", f"Catalog exported successfully to:\n{filepath}")
        inv_view.cancel_bulk_mode()
    except Exception as e: messagebox.showerror("Export Error", str(e))

def export_pdf(inv_view):
    parsed = inv_view.get_parsed_data()
    if inv_view.is_bulk_mode and inv_view.selected_items:
        parsed = [i for i in parsed if i['id'] in inv_view.selected_items]
        
    if not parsed:
        messagebox.showinfo("Export", "No data to export.")
        return

    try:
        fd, filepath = tempfile.mkstemp(suffix=".html", prefix="Inventory_Report_")
        
        has_gst = getattr(inv_view, 'has_gst', True)
        
        html = f"<html><head><style>body{{font-family:Arial,sans-serif;padding:20px;color:#333;}}table{{width:100%;border-collapse:collapse;margin-top:20px;}}th,td{{border:1px solid #cbd5e1;text-align:left;padding:10px;}}th{{background-color:#f8fafc;}}</style></head><body><h2>Catalog Master List</h2><table><tr>"
        
        if has_gst:
            html += "<th>Item Name</th><th>Category</th><th>Unit</th><th>HSN/SAC</th><th>Rate / Unit</th></tr>"
            for i in parsed:
                html += f"<tr><td>{i['name']}</td><td>{i['category']}</td><td>{i['unit']}</td><td>{i['hsn']}</td><td>{format_currency(i['rate'], inv_view.curr_fmt)}</td></tr>"
        else:
            html += "<th>Item Name</th><th>Category</th><th>Unit</th><th>Rate / Unit</th></tr>"
            for i in parsed:
                html += f"<tr><td>{i['name']}</td><td>{i['category']}</td><td>{i['unit']}</td><td>{format_currency(i['rate'], inv_view.curr_fmt)}</td></tr>"
                
        html += "</table><script>window.print();</script></body></html>"
        
        with os.fdopen(fd, 'w', encoding='utf-8') as f: f.write(html)
        if os.name == 'nt': os.startfile(filepath)
        else:
            import subprocess
            subprocess.call(('open', filepath))
        inv_view.cancel_bulk_mode()
    except Exception as e: messagebox.showerror("Export Error", str(e))

def trigger_csv_import(inv_view):
    comp_id = getattr(inv_view.winfo_toplevel(), "active_company_id", 1)
    allowed, err_msg = database.check_catalog_permission(action="delete", company_id=comp_id)
    if not allowed:
        messagebox.showerror("Access Denied", err_msg, parent=inv_view)
        return
        
    filepath = filedialog.askopenfilename(defaultextension=".csv", filetypes=[("CSV Files", "*.csv")], title="Bulk Import Catalog")
    if not filepath: return
    
    try:
        with open(filepath, newline='', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            rows = list(reader)
    except Exception as e:
        messagebox.showerror("Error", f"Could not read file:\n{e}", parent=inv_view)
        return
        
    if not rows or len(rows) < 2:
        messagebox.showerror("Error", "File is empty.", parent=inv_view)
        return

    _open_staging_area(inv_view, rows[0], rows[1:])

def _open_staging_area(inv_view, headers, data):
    popup = tk.Toplevel(inv_view)
    popup.title("Staging Area - Review & Edit")
    popup.configure(bg=inv_view.BG)
    popup.grab_set()

    # --- THE FIX: Universal Focus Drop for Staging Area ---
    def bind_focus_drop(container):
        container.bind("<ButtonPress-1>", lambda e: popup.focus_set() if e.widget.winfo_class() not in ('Entry', 'Text', 'TCombobox', 'Listbox', 'Button', 'Treeview') else None, add="+")
        for child in container.winfo_children():
            if child.winfo_class() in ('Frame', 'Label', 'Canvas'):
                bind_focus_drop(child)
    
    popup.active_editor = None
    popup.editing_row_col = None
    popup.active_lb = None

    undo_stack = []
    redo_stack = []

    comp_id = getattr(inv_view.winfo_toplevel(), "active_company_id", 1)
    database.set_active_company(comp_id)
    # --- THE FIX: MVC Compliant Inventory Catalog Fetch ---
    all_inv = database.get_all_inventory()
    inv_names = [i[1] if len(i)>1 else "" for i in all_inv]
    # ------------------------------------------------------
    
    # --- THE FIX: Severed the link to the Stock table for import staging ---
    existing_names = list(set(inv_names))
    existing_names = [n for n in existing_names if n.strip()]
    existing_names_lower = {n.lower() for n in existing_names} # Cached for fast duplicate checking
    # ---------------------------------------------------------------------

    sw, sh = popup.winfo_screenwidth(), popup.winfo_screenheight()
    popup.geometry(f"1250x680+{int((sw/2)-625)}+{int((sh/2)-340)}")

    top_f = tk.Frame(popup, bg=inv_view.BG)
    top_f.pack(fill="x", padx=20, pady=(15,2))
    
    tk.Label(top_f, text="Review & Edit Import Data", font=("Arial", 16, "bold"), bg=inv_view.BG, fg=inv_view.FG).pack(side="left")
    
    btn_redo = tk.Button(top_f, text="⟳ Redo", font=("Arial", 10, "bold"), bg=inv_view.BG, fg=inv_view.SEC_FG, relief="flat", cursor="hand2", padx=10, pady=3, state="disabled")
    btn_redo.pack(side="right")
    
    btn_undo = tk.Button(top_f, text="⟲ Undo", font=("Arial", 10, "bold"), bg=inv_view.BG, fg=inv_view.SEC_FG, relief="flat", cursor="hand2", padx=10, pady=3, state="disabled")
    btn_undo.pack(side="right", padx=10)

    # --- THE FIX: Updated legend to explain the yellow rows ---
    legend_f = tk.Frame(popup, bg=inv_view.BG)
    legend_f.pack(anchor="w", padx=20, pady=(0, 10))
    tk.Label(legend_f, text="Right-click any row to DELETE. Double-click to Edit. (Press Ctrl+Z to Undo).", font=("Arial", 10), bg=inv_view.BG, fg=inv_view.SEC_FG).pack(side="left")
    
    warn_bg = "#713f12" if getattr(inv_view, 'is_dark', False) else "#fef08a"
    tk.Label(legend_f, text="  Rows in YELLOW  ", font=("Arial", 9, "bold"), bg=warn_bg, fg=inv_view.FG).pack(side="left", padx=5)
    tk.Label(legend_f, text="will overwrite existing items.", font=("Arial", 10), bg=inv_view.BG, fg=inv_view.SEC_FG).pack(side="left")
    # ----------------------------------------------------------

    def update_undo_ui():
        if undo_stack:
            btn_undo.config(bg=inv_view.CARD, fg=inv_view.FG, state="normal", cursor="hand2", relief="solid", bd=1, command=exec_undo)
            add_hover(btn_undo, inv_view.CARD, inv_view.BORDER)
        else:
            btn_undo.config(bg=inv_view.BG, fg=inv_view.SEC_FG, state="disabled", cursor="", relief="flat", bd=0)
            btn_undo.unbind("<Enter>"); btn_undo.unbind("<Leave>")
            
        if redo_stack:
            btn_redo.config(bg=inv_view.CARD, fg=inv_view.FG, state="normal", cursor="hand2", relief="solid", bd=1, command=exec_redo)
            add_hover(btn_redo, inv_view.CARD, inv_view.BORDER)
        else:
            btn_redo.config(bg=inv_view.BG, fg=inv_view.SEC_FG, state="disabled", cursor="", relief="flat", bd=0)
            btn_redo.unbind("<Enter>"); btn_redo.unbind("<Leave>")

    def push_action(act):
        undo_stack.append(act)
        if len(undo_stack) > 50: undo_stack.pop(0) 
        redo_stack.clear()
        update_undo_ui()

    def exec_undo(e=None):
        if not undo_stack: return
        act = undo_stack.pop()
        redo_stack.append(act)
        
        if act['type'] == 'edit':
            for r in raw_data_cache:
                if str(id(r)) == act['uid']: r[act['col']] = act['old']; break
        elif act['type'] == 'delete':
            raw_data_cache.insert(act['idx'], act['data'])
        elif act['type'] == 'clear_col':
            for r in raw_data_cache:
                if str(id(r)) in act['old_data']:
                    r[act['col']] = act['old_data'][str(id(r))]
                    
        update_undo_ui(); render_grid()

    def exec_redo(e=None):
        if not redo_stack: return
        act = redo_stack.pop()
        undo_stack.append(act)
        
        if act['type'] == 'edit':
            for r in raw_data_cache:
                if str(id(r)) == act['uid']: r[act['col']] = act['new']; break
        elif act['type'] == 'delete':
            for i, r in enumerate(raw_data_cache):
                if str(id(r)) == str(id(act['data'])):
                    raw_data_cache.pop(i)
                    break
        elif act['type'] == 'clear_col':
            for r in raw_data_cache:
                r[act['col']] = "" if act['col'] not in [3, 4] else "0.0"
                
        update_undo_ui(); render_grid()

    popup.bind("<Control-z>", exec_undo); popup.bind("<Control-Z>", exec_undo)
    popup.bind("<Control-y>", exec_redo); popup.bind("<Control-Y>", exec_redo)

    def confirm_import():
        destroy_ghosts()
        count = 0
        for r in raw_data_cache:
            # --- THE FIX: Security Check for Blank Names ---
            name = str(r[0]).strip()
            if not name: continue
            # -----------------------------------------------
            packed = json.dumps({"desc": r[5], "unit": r[2], "hsn": r[3], "category": r[1]})
            try: rt = float(r[4])
            except: rt = 0.0
            inv_view.safe_db_add(name, r[2], rt, packed)
            count += 1
            
        comp_id = getattr(inv_view.winfo_toplevel(), "active_company_id", 1)
        database.log_audit("Catalog", "Bulk Imported", record_ref=f"{count} Items", details=f"Mass imported {count} items via CSV.", company_id=comp_id)
        
        inv_view.load_data()
        popup.destroy()
        messagebox.showinfo("Import Success", f"Injected {count} items!")

    bottom_f = tk.Frame(popup, bg=inv_view.BG)
    bottom_f.pack(side="bottom", fill="x", padx=20, pady=20)
    tk.Button(bottom_f, text="Confirm & Import Data", font=("Arial", 12, "bold"), bg=inv_view.GREEN, fg="#ffffff", relief="flat", pady=10, cursor="hand2", command=confirm_import).pack(fill="x")

    frame = tk.Frame(popup, bg=inv_view.CARD)
    frame.pack(side="top", fill="both", expand=True, padx=20, pady=5)
    
    scroll_y = ttk.Scrollbar(frame, orient="vertical", style="Theme.Vertical.TScrollbar")
    # --- THE FIX: Apply the modern style to the horizontal scrollbar! ---
    scroll_x = ttk.Scrollbar(frame, orient="horizontal", style="Theme.Horizontal.TScrollbar")
    # --------------------------------------------------------------------
    
    has_gst = getattr(inv_view, 'has_gst', True)
    
    # --- THE FIX: Clean columns, completely removing QTY and TOTAL logic ---
    if has_gst:
        cols = ("Name", "Category", "Unit", "HSN", "Rate/Unit", "Description")
    else:
        cols = ("Name", "Category", "Unit", "Rate/Unit", "Description")
        
    tree = ttk.Treeview(frame, columns=cols, show="headings", yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set, height=15, style="Inv.Treeview")
    scroll_y.config(command=tree.yview)
    scroll_x.config(command=tree.xview)
    
    tree.tag_configure("evenrow", background=inv_view.BG, foreground=inv_view.FG)
    tree.tag_configure("oddrow", background=inv_view.CARD, foreground=inv_view.FG)
    # --- THE FIX: Duplicate tag coloring ---
    tree.tag_configure("duplicate", background=warn_bg, foreground=inv_view.FG)
    # ---------------------------------------
    
    for c in cols: tree.heading(c, text=c.upper(), anchor="center")
    
    # --- THE FIX: MVC Compliant Column Width Fetch ---
    try:
        raw_setting = database.get_ui_setting("inv_staging_cols", "{}")
        s_w = json.loads(raw_setting) if raw_setting else {}
    except:
        s_w = {}
    # -------------------------------------------------

    tree.column("Name", width=s_w.get("Name", 150), minwidth=100, stretch=False, anchor="w")
    tree.column("Category", width=s_w.get("Category", 100), minwidth=80, stretch=False, anchor="center")
    tree.column("Unit", width=s_w.get("Unit", 80), minwidth=60, stretch=False, anchor="center")
    
    if has_gst:
        tree.column("HSN", width=s_w.get("HSN", 100), minwidth=80, stretch=False, anchor="center")
        
    tree.column("Rate/Unit", width=s_w.get("Rate/Unit", 100), minwidth=80, stretch=False, anchor="center")
    tree.column("Description", width=s_w.get("Description", 250), minwidth=100, stretch=True, anchor="w") 

    def save_staging_widths():
        new_w = {c: tree.column(c, "width") for c in tree["columns"]}
        try:
            # --- THE FIX: Let the database engine handle the security stamp! ---
            database.save_ui_setting("inv_staging_cols", json.dumps(new_w))
            # -------------------------------------------------------------------
        except: pass

    def on_staging_sep_drag(event):
        if tree.identify_region(event.x, event.y) == "separator":
            popup.after(50, save_staging_widths)

    tree.bind("<B1-Motion>", on_staging_sep_drag, add="+")
    tree.bind("<ButtonRelease-1>", lambda e: popup.after(50, save_staging_widths), add="+")
        
    scroll_y.pack(side="right", fill="y")
    scroll_x.pack(side="bottom", fill="x")
    tree.pack(side="left", fill="both", expand=True)

    def destroy_ghosts():
        if popup.active_editor:
            try: popup.active_editor.destroy()
            except: pass
            popup.active_editor = None
        if popup.active_lb:
            try: popup.active_lb.destroy()
            except: pass
            popup.active_lb = None
        popup.editing_row_col = None

    # --- THE FIX: Buttery Smooth Horizontal & Vertical Scrolling for Import Window ---
    def _staging_fast_scroll(event, direction):
        destroy_ghosts()
        delta = -1 * (event.delta / 120) if os.name == 'nt' else -1 * event.delta
        if direction == "y":
            tree.yview_moveto(tree.yview()[0] + (delta * 0.008))
        else:
            tree.xview_moveto(tree.xview()[0] + (delta * 0.02))

    tree.bind("<MouseWheel>", lambda e: _staging_fast_scroll(e, "y"))
    tree.bind("<Shift-MouseWheel>", lambda e: _staging_fast_scroll(e, "x"))
    # -------------------------------------------------------------------------------

    tree.bind("<ButtonPress-1>", lambda e: destroy_ghosts() if tree.identify("region", e.x, e.y) != "cell" else None, add="+")

    def map_visual_to_real(visual_idx):
        if has_gst: return visual_idx
        v_map = {0:0, 1:1, 2:2, 3:4, 4:5}
        return v_map.get(visual_idx, visual_idx)

    def on_right_click(event):
        destroy_ghosts()
        region = tree.identify("region", event.x, event.y)
        menu = tk.Menu(popup, tearoff=0, font=("Arial", 10), bg=inv_view.CARD, fg=inv_view.FG, activebackground=inv_view.BLUE)
        
        row_id = tree.identify_row(event.y)
        if region == "cell" and row_id and "empty" not in tree.item(row_id, "tags"):
            menu.add_command(label="❌ Delete This Row", command=lambda: delete_row(row_id))
            menu.add_separator()

        col = tree.identify_column(event.x)
        if col:
            col_idx = int(col[1:]) - 1
            real_idx = map_visual_to_real(col_idx)
            menu.add_command(label=f"🧹 Clear Entire '{cols[col_idx]}' Column", command=lambda r_idx=real_idx: clear_column(r_idx))
            
        menu.tk_popup(event.x_root, event.y_root)

    def delete_row(row_id):
        for idx, r in enumerate(raw_data_cache):
            if str(id(r)) == row_id:
                push_action({'type': 'delete', 'idx': idx, 'data': r})
                raw_data_cache.pop(idx)
                break
        render_grid()

    def clear_column(idx):
        old_data = {}
        for c_idx, r in enumerate(raw_data_cache):
            old_data[str(id(r))] = r[idx]
            r[idx] = "" if idx != 4 else "0.0" 
        push_action({'type': 'clear_col', 'col': idx, 'old_data': old_data})
        render_grid()

    tree.bind("<Button-3>", on_right_click)

    def find_idx(possible):
        for i, h in enumerate(headers):
            if any(p.lower() in h.lower() for p in possible): return i
        return -1
        
    idx_name = find_idx(["name", "item", "product"])
    idx_cat = find_idx(["cat", "group", "type"])
    idx_unit = find_idx(["unit", "uom", "measure"])
    idx_hsn = find_idx(["hsn", "sac", "code"])
    idx_qty = find_idx(["qty/unit", "quantity/unit", "qty", "quantity"])
    idx_amt = find_idx(["amount", "total", "net"])
    idx_rate = find_idx(["rate", "price", "cost", "mrp"])
    idx_desc = find_idx(["desc", "note", "detail", "description"])

    raw_data_cache = []
    
    for row in data:
        if not any(row): continue 
        def s_get(idx, default=""): return row[idx].strip() if idx != -1 and idx < len(row) else default
            
        name = s_get(idx_name, "")
        if not name: continue 
        
        cat = s_get(idx_cat, "General")
        hsn = s_get(idx_hsn, "")
        desc = s_get(idx_desc, "")
        
        raw_qty = s_get(idx_qty, "")
        r_unit_raw = s_get(idx_unit, "")

        if not raw_qty and re.search(r'\d', r_unit_raw): raw_qty = r_unit_raw

        qty_match = re.search(r'\d+\.?\d*', raw_qty)
        qty = float(qty_match.group()) if qty_match else 0.0

        # --- THE FIX: Smart Unit Translator (Now with --Select--) ---
        full_units = ["--Select--", "Numbers (Nos.)", "Kilograms (Kg)", "Pieces (Pcs)", "Packets (Pkts)", 
                      "Running Feet (Rft)", "Running Metre (Rmt)", "Square Feet (Sq.ft.)", 
                      "Hours (Hours)", "Days (Days)", "Months (Months)", "Trips (Trip)"]
        # -------------------------------------------------------
        
        # --- THE FIX: Strip dots and symbols from BOTH sides for perfect matching ---
        extracted_unit_letters = re.sub(r'[^a-zA-Z]', '', r_unit_raw).lower()
        
        r_unit = "Numbers (Nos.)"  # Failsafe default
        if extracted_unit_letters:
            for u in full_units:
                clean_official_unit = re.sub(r'[^a-zA-Z]', '', u).lower()
                if extracted_unit_letters in clean_official_unit or clean_official_unit in extracted_unit_letters:
                    r_unit = u
                    break
        # ----------------------------------------------------------------------------
            
        try: rate = float(re.search(r'\d+\.?\d*', s_get(idx_rate, "0")).group())
        except: rate = 0.0
        
        try: amt = float(re.search(r'\d+\.?\d*', s_get(idx_amt, "0")).group())
        except: amt = 0.0
        
        if rate == 0.0 and qty > 0 and amt > 0: rate = amt / qty
        
        raw_data_cache.append([
            name, cat, r_unit, hsn, 
            f"{rate:.2f}", desc
        ])

    def render_grid(*args):
        for item in tree.get_children(): tree.delete(item)
        for i, r in enumerate(raw_data_cache):
            if has_gst:
                disp_vals = r
            else:
                disp_vals = [r[0], r[1], r[2], r[4], r[5]]
                
            # --- THE FIX: Apply yellow highlight if item name already exists! ---
            if str(r[0]).strip().lower() in existing_names_lower:
                row_tag = "duplicate"
            else:
                row_tag = "evenrow" if i % 2 == 0 else "oddrow"
            # --------------------------------------------------------------------
                
            tree.insert("", "end", iid=str(id(r)), values=disp_vals, tags=(row_tag,))
            
        for i in range(len(raw_data_cache), 15):
            tree.insert("", "end", iid=f"empty_{i}", values=["" for _ in cols], tags=("evenrow" if i % 2 == 0 else "oddrow", "empty"))

    render_grid() 

    def on_double_click(event):
        region = tree.identify("region", event.x, event.y)
        if region != "cell": return
        
        col = tree.identify_column(event.x)
        row_id = tree.identify_row(event.y) 
        if "empty" in tree.item(row_id, "tags"): return 
        
        if popup.editing_row_col == (row_id, col): return
        destroy_ghosts()
        popup.editing_row_col = (row_id, col)
        
        x, y, w, h = tree.bbox(row_id, col)
        col_idx = int(col[1:]) - 1
        real_idx = map_visual_to_real(col_idx)
        
        old_val = tree.item(row_id, "values")[col_idx]
        
        entry_var = tk.StringVar(value=old_val)
        entry = tk.Entry(tree, textvariable=entry_var, font=("Arial", 10), justify="left" if col_idx in [0, 5] else "center")
        entry.place(x=x, y=y, width=w, height=h)
        entry.focus_set()
        popup.active_editor = entry
        
        def save_edit(e=None):
            if not popup.active_editor: return
            new_val = entry_var.get()
            if new_val != old_val:
                push_action({'type': 'edit', 'uid': row_id, 'col': real_idx, 'old': old_val, 'new': new_val})
                for r in raw_data_cache:
                    if str(id(r)) == row_id: r[real_idx] = new_val; break
                render_grid()
            destroy_ghosts()

        entry.bind("<Return>", save_edit)
        entry.bind("<FocusOut>", lambda e: popup.after(250, save_edit))
        
        if col_idx == 0:
            lb = tk.Listbox(tree, font=("Arial", 10), height=4, bg=inv_view.BG, fg=inv_view.FG, selectbackground=inv_view.BLUE, highlightbackground=inv_view.BORDER, highlightthickness=1, cursor="hand2")
            popup.active_lb = lb
            
            def update_list(*args):
                s = entry_var.get().lower(); lb.delete(0, tk.END)
                m = [i for i in existing_names if s in i.lower() and s != i.lower()]
                if s and m:
                    lb.place(x=x, y=y+h+1, width=w)
                    for item in m[:10]: lb.insert(tk.END, item)
                    lb.lift()
                else: lb.place_forget()
                
            entry_var.trace("w", update_list)
            entry.bind("<Down>", lambda e: (lb.focus(), lb.selection_set(0)) if lb.winfo_ismapped() else None)
            
            def select_from_lb(event=None):
                if lb.curselection():
                    sel_name = lb.get(lb.curselection()[0])
                    entry_var.set(sel_name)
                    lb.place_forget()
                    
                    for inv_item in all_inv:
                        if len(inv_item) > 1 and inv_item[1].lower() == sel_name.lower():
                            for r in raw_data_cache:
                                if str(id(r)) == row_id: 
                                    r[2] = str(inv_item[2]) if len(inv_item)>2 else "Nos." 
                                    r[4] = str(inv_item[3]) if len(inv_item)>3 else "0.00" 
                                    try:
                                        j = json.loads(str(inv_item[4]) if len(inv_item)>4 else "{}")
                                        if j.get("category"): r[1] = j.get("category") 
                                        if j.get("hsn"): r[3] = j.get("hsn") 
                                    except: pass
                                    break
                            break
                    save_edit()
                return "break"
                
            lb.bind("<Return>", select_from_lb)
            lb.bind("<Double-Button-1>", select_from_lb)
        
    tree.bind("<Double-1>", on_double_click)

    # Arm the Universal Focus Drop
    bind_focus_drop(popup)