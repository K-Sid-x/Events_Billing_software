import csv
import tempfile
import os
import webbrowser
import json
import re
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
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

def _get_items_to_export(stock_view):
    parsed = stock_view.get_parsed_data(ignore_filters=True)
    if stock_view.is_bulk_mode and stock_view.selected_items: 
        parsed = [i for i in parsed if i[0] in stock_view.selected_items]
    return parsed

def export_csv(stock_view): 
    _run_csv_export(stock_view, _get_items_to_export(stock_view))

def export_pdf(stock_view): 
    _run_pdf_export(stock_view, _get_items_to_export(stock_view))

def _run_csv_export(stock_view, items_to_export):
    if not items_to_export: messagebox.showinfo("Export", "No data to export.", parent=stock_view); return
    filepath = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV Files", "*.csv")], title="Export Stock to CSV", parent=stock_view)
    if not filepath: return
    try:
        with open(filepath, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            if stock_view.b_type == "Sales":
                writer.writerow(["Item Name", "Added", "Loss", "Sold", "Net Qty", "Unit", "Net Value"])
                for i in items_to_export: writer.writerow([i[0], f"{i[1]:g}", f"{i[2]:g}", f"{i[3]:g}", f"{i[4]:g}", i[5], f"{i[6]:.2f}"])
            else:
                writer.writerow(["Item Name", "Added", "Loss", "Net Qty", "Unit", "Net Value"])
                for i in items_to_export: writer.writerow([i[0], f"{i[1]:g}", f"{i[2]:g}", f"{i[4]:g}", i[5], f"{i[6]:.2f}"])
        messagebox.showinfo("Success", f"Stock exported successfully to:\n{filepath}", parent=stock_view)
    except Exception as e: messagebox.showerror("Export Error", f"Failed to export data:\n{e}", parent=stock_view)

def _run_pdf_export(stock_view, items_to_export):
    if not items_to_export: messagebox.showinfo("Export", "No data to export.", parent=stock_view); return
    try:
        fd, filepath = tempfile.mkstemp(suffix=".html", prefix="Stock_Report_")
        html_content = f"<html><head><style>body{{font-family:Arial;padding:20px;color:#333;}}h2{{text-align:center;}}table{{width:100%;border-collapse:collapse;margin-top:20px;}}th,td{{border:1px solid #cbd5e1;padding:10px;text-align:center;}}th{{background:#f8fafc;}}</style></head><body><h2>Stock Ledger Summary</h2><table><tr><th>Item Name</th><th>Added</th><th>Loss</th>"
        if stock_view.b_type == "Sales": html_content += "<th>Sold</th>"
        html_content += "<th>Net Qty</th><th>Unit</th><th>Net Value</th></tr>"
        
        for i in items_to_export:
            html_content += f"<tr><td style='text-align:left;'>{i[0]}</td><td>{i[1]:g}</td><td>{i[2]:g}</td>"
            if stock_view.b_type == "Sales": html_content += f"<td>{i[3]:g}</td>"
            html_content += f"<td>{i[4]:g}</td><td>{i[5]}</td><td>{format_currency(i[6], stock_view.curr_fmt)}</td></tr>"
            
        html_content += "</table><script>window.print();</script></body></html>"
        with os.fdopen(fd, 'w', encoding='utf-8') as f: f.write(html_content)
        
        if os.name == 'nt': os.startfile(filepath)
        else:
            import subprocess
            subprocess.call(('open', filepath))
    except Exception as e: messagebox.showerror("Export Error", f"Failed to generate document:\n{e}", parent=stock_view)


def generate_purchase_order(stock_view):
    parsed = stock_view.get_parsed_data(ignore_filters=True)
    items_to_process = []
    
    if stock_view.is_bulk_mode and stock_view.selected_items:
        items_to_process = [i for i in parsed if i[0] in stock_view.selected_items]
    else:
        items_to_process = [i for i in parsed if i[4] <= i[9]]
        
    if not items_to_process:
        messagebox.showinfo("Purchase Order", "No items selected or no stock is currently below Reorder Level.", parent=stock_view)
        return
        
    # --- THE FIX: Build a vendor dictionary ONCE from a single database query to prevent micro-stuttering! ---
    raw_stock = database.get_all_stock_records_raw()
    vendor_map = {}
    for r in raw_stock:
        item_n, trans_type, notes = r[0], r[4], r[5]
        if trans_type == 'ADD':
            try:
                j = json.loads(notes)
                if j.get("vendor"): vendor_map[item_n] = j.get("vendor")
            except: pass
    # ---------------------------------------------------------------------------------------------------------
        
    po_data = {}
    for item in items_to_process:
        name, net, unit, reorder = item[0], item[4], item[5], item[9]
        vendor = vendor_map.get(name, "Uncategorized Suppliers")
        
        if vendor not in po_data: po_data[vendor] = []
        order_qty = max(1, (reorder - net) + (reorder * 0.5)) 
        po_data[vendor].append({"name": name, "curr": net, "req": order_qty, "unit": unit})
        
    try:
        fd, filepath = tempfile.mkstemp(suffix=".html", prefix="Purchase_Orders_")
        html = f"<html><head><style>body{{font-family:Arial,sans-serif;padding:30px;color:#1e293b;}}h1{{color:#0f172a;border-bottom:2px solid #3b82f6;padding-bottom:10px;}}table{{width:100%;border-collapse:collapse;margin-top:15px;margin-bottom:40px;}}th,td{{border:1px solid #cbd5e1;padding:12px;text-align:left;}}th{{background:#f8fafc;font-weight:bold;}}.vendor-title{{color:#3b82f6;font-size:18px;margin-bottom:-5px;}}</style></head><body>"
        html += "<h1>Automated Purchase Order Report</h1>"
        
        for v, items in po_data.items():
            html += f"<p class='vendor-title'><b>To Supplier:</b> {v}</p>"
            html += "<table><tr><th>Item Name</th><th>Current Stock</th><th>Suggested Order Qty</th><th>Unit</th></tr>"
            for i in items:
                html += f"<tr><td>{i['name']}</td><td>{i['curr']:g}</td><td><b>{i['req']:g}</b></td><td>{i['unit']}</td></tr>"
            html += "</table>"
        
        html += "<script>window.print();</script></body></html>"
        with os.fdopen(fd, 'w', encoding='utf-8') as f: f.write(html)
        
        if os.name == 'nt': os.startfile(filepath)
        else:
            import subprocess
            subprocess.call(('open', filepath))
    except Exception as e:
        messagebox.showerror("Error", f"Failed to generate POs:\n{e}", parent=stock_view)


def trigger_csv_import(stock_view):
    comp_id = getattr(stock_view.winfo_toplevel(), "active_company_id", 1)
    allowed, err_msg = database.check_stock_permission(action="import", company_id=comp_id)
    if not allowed:
        messagebox.showerror("Access Denied", err_msg, parent=stock_view)
        return
        
    filepath = filedialog.askopenfilename(defaultextension=".csv", filetypes=[("CSV Files", "*.csv"), ("Excel Files", "*.xlsx;*.xls")], title="Select CSV to Import")
    if not filepath: return
    
    rows = None
    try:
        with open(filepath, newline='', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            rows = list(reader)
    except UnicodeDecodeError:
        try:
            with open(filepath, newline='', encoding='cp1252') as f:
                reader = csv.reader(f)
                rows = list(reader)
        except Exception as e:
            messagebox.showerror("Error", f"Could not decode the file format:\n{e}", parent=stock_view)
            return
    except Exception as e:
        messagebox.showerror("Error", f"Could not read file:\n{e}", parent=stock_view)
        return
        
    if not rows or len(rows) < 2:
        messagebox.showerror("Error", "The file appears to be empty or has no data rows.", parent=stock_view)
        return

    headers = rows[0]
    data = rows[1:]
    
    _open_staging_area(stock_view, headers, data)

def clean_num(val_str):
    num_str = re.sub(r'[^\d\.\-]', '', str(val_str))
    try: return float(num_str) if num_str else 0.0
    except: return 0.0

def _open_staging_area(stock_view, headers, data):
    popup = tk.Toplevel(stock_view)
    popup.title("Data Staging Area - Review & Edit")
    popup.configure(bg=stock_view.BG)
    popup.grab_set()
    
    popup.active_editor = None
    popup.active_listbox = None
    popup.editing_row_col = None
    
    popup.update_idletasks()
    sw, sh = popup.winfo_screenwidth(), popup.winfo_screenheight()
    w, h = 1050, 680
    x, y = int((sw/2)-(w/2)), int((sh/2)-(h/2))
    popup.geometry(f"{w}x{h}+{x}+{y}")
    
    # --- THE FIX: MVC Compliant GST Toggle Fetch ---
    has_gst = database.get_company_gst_toggle(getattr(stock_view, "comp_id", 1))
    # -----------------------------------------------

    is_sales = (stock_view.b_type == "Sales")
    
    # --- THE FIX: Appended 'ghost' column to absorb table stretch ---
    if is_sales:
        if has_gst: cols = ("☑", "Name", "Qty", "Unit", "Base Rate", "GST", "Price (Inc GST)", "MRP", "HSN", "Amount", "Low Stock", "Vendor", "Batch", "Expiry", "ghost")
        else: cols = ("☑", "Name", "Qty", "Unit", "Price", "MRP", "Amount", "Low Stock", "Vendor", "Batch", "Expiry", "ghost")
    else:
        if has_gst: cols = ("☑", "Name", "Qty", "Unit", "Base Rate", "GST", "Price (Inc GST)", "Amount", "ghost")
        else: cols = ("☑", "Name", "Qty", "Unit", "Price", "Amount", "ghost")
    # ----------------------------------------------------------------

    def confirm_import():
        destroy_active_editors() 
        
        selected_count = sum(1 for child in tree.get_children() if "empty" not in tree.item(child, "tags") and tree.item(child, "values")[0] == "☑")
        if selected_count == 0:
            messagebox.showinfo("Nothing to Import", "Please select at least one row to import.", parent=popup)
            return
        
        from datetime import date
        today = date.today().strftime("%Y-%m-%d")
        count = 0
        
        # --- THE FIX: Use safe backend helper for Bulk Import instead of raw UI SQL! ---
        for child in tree.get_children():
            if "empty" in tree.item(child, "tags"): continue 
            v = tree.item(child, "values")
            
            if v[0] != "☑": continue
            
            name = v[cols.index("Name")]
            try: qty = float(v[cols.index("Qty")])
            except: qty = 0.0
            
            unit = v[cols.index("Unit")]
            
            try: cost = float(v[cols.index("Price (Inc GST)")]) if has_gst else float(v[cols.index("Price")])
            except: cost = 0.0
            
            notes_dict = {}
            if is_sales:
                try: mrp = float(v[cols.index("MRP")])
                except: mrp = 0.0
                try: reorder = float(v[cols.index("Low Stock")])
                except: reorder = 0.0
                
                vendor = v[cols.index("Vendor")]
                batch = v[cols.index("Batch")]
                exp = v[cols.index("Expiry")]
                
                notes_dict = {"mrp": mrp, "reorder_level": reorder, "vendor": vendor, "batch": batch, "expiry": exp, "notes": "Imported via CSV"}
                if has_gst:
                    notes_dict["gst"] = v[cols.index("GST")]
                    notes_dict["hsn"] = v[cols.index("HSN")]
            else:
                notes_dict = {"notes": "Imported via CSV"}
                if has_gst: notes_dict["gst"] = v[cols.index("GST")]
                
            database.add_stock(name, qty, unit, cost, json.dumps(notes_dict), today, "ADD")
            count += 1
        # -------------------------------------------------------------------------------
            
        comp_id = getattr(stock_view.winfo_toplevel(), "active_company_id", 1)
        database.log_audit("Stock", "Bulk Imported", record_ref=f"{count} Items", details=f"Mass imported {count} items via CSV into Stock.", company_id=comp_id)
        
        stock_view.load_data()
        popup.destroy()
        messagebox.showinfo("Import Success", f"Successfully injected {count} items into the database!", parent=stock_view)
    
    btn_confirm = tk.Button(popup, text="Confirm & Import Data", font=("Arial", 12, "bold"), bg=stock_view.GREEN, fg="#ffffff", relief="flat", pady=10, cursor="hand2", command=confirm_import)
    btn_confirm.pack(side="bottom", fill="x", padx=20, pady=(0,20))

    tk.Label(popup, text="Review & Edit Import Data", font=("Arial", 16, "bold"), bg=stock_view.BG, fg=stock_view.FG).pack(pady=(15,2), anchor="w", padx=20)
    tk.Label(popup, text="Click '☑' to select/unselect rows. Right-click to DELETE. Double-click any cell to edit.", font=("Arial", 10), bg=stock_view.BG, fg=stock_view.SEC_FG).pack(anchor="w", padx=20, pady=(0, 10))

    filter_frame = tk.Frame(popup, bg=stock_view.BG)
    filter_frame.pack(fill="x", padx=20, pady=(0, 10))
    tk.Label(filter_frame, text="Sort Preview:", bg=stock_view.BG, fg=stock_view.SEC_FG, font=("Arial", 10, "bold")).pack(side="left")
    
    sort_var = tk.StringVar(value="Import Order")
    sort_combo = ttk.Combobox(filter_frame, textvariable=sort_var, values=["Import Order", "A to Z", "Z to A", "Highest Price", "Lowest Price"], state="readonly", width=15, style="Theme.TCombobox", cursor="hand2")
    sort_combo.pack(side="left", padx=(10, 0))

    def toggle_all():
        destroy_active_editors()
        all_sel = all(r[0] == "☑" for r in raw_data_cache)
        new_val = "☐" if all_sel else "☑"
        for r in raw_data_cache: r[0] = new_val
        render_grid()

    btn_sel_all = tk.Button(filter_frame, text="☑ Toggle Select All", font=("Arial", 9, "bold"), bg=stock_view.BLUE, fg="#ffffff", relief="flat", cursor="hand2", command=toggle_all)
    btn_sel_all.pack(side="right", padx=(0, 0))

    frame = tk.Frame(popup, bg=stock_view.CARD)
    frame.pack(fill="both", expand=True, padx=20, pady=5)
    
    # --- THE FIX: Standardized Stock Scrollbars ---
    scroll_y = ttk.Scrollbar(frame, orient="vertical", style="Stock.Vertical.TScrollbar")
    scroll_x = ttk.Scrollbar(frame, orient="horizontal", style="Stock.Horizontal.TScrollbar")
    # ----------------------------------------------
        
    tree = ttk.Treeview(frame, columns=cols, show="headings", yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set, height=15, style="Stock.Treeview")
    scroll_y.config(command=tree.yview)
    scroll_x.config(command=tree.xview)
    
    tree.tag_configure("evenrow", background=stock_view.BG, foreground=stock_view.FG)
    tree.tag_configure("oddrow", background=stock_view.CARD, foreground=stock_view.FG)
    
    comp_id_val = getattr(stock_view, "comp_id", 1)
    try:
        raw_setting = database.get_ui_setting(f"stock_staging_cols_{comp_id_val}", "{}")
        s_w = json.loads(raw_setting) if raw_setting else {}
    except Exception:
        s_w = {}

    for c in cols:
        if c == "ghost":
            tree.heading(c, text="", anchor="center")
            tree.column(c, width=10, minwidth=10, stretch=True)
            continue
            
        tree.heading(c, text=c.upper() if c != "☑" else "☑", anchor="center")
        is_name = (c == "Name")
        is_check = (c == "☑")
        
        default_w = 40 if is_check else (70 if c in ["GST", "Unit", "Qty"] else (250 if is_name else 100))
        # --- THE FIX: Stop everything from stretching, let Ghost absorb it! ---
        tree.column(c, width=s_w.get(c, default_w), stretch=False, anchor="w" if is_name else "center")

    def save_staging_widths():
        # --- THE FIX: Ignore Ghost column when saving sizes ---
        new_w = {c: tree.column(c, "width") for c in tree["columns"] if c != "ghost"}
        try:
            database.save_ui_setting(f"stock_staging_cols_{comp_id_val}", json.dumps(new_w))
        except: pass

    def on_staging_sep_drag(event):
        if tree.identify_region(event.x, event.y) == "separator":
            popup.after(50, save_staging_widths)

    tree.bind("<B1-Motion>", on_staging_sep_drag, add="+")
    tree.bind("<ButtonRelease-1>", lambda e: popup.after(50, save_staging_widths) if tree.identify_region(e.x, e.y) == "separator" else None, add="+")
        
    scroll_y.pack(side="right", fill="y")
    scroll_x.pack(side="bottom", fill="x")
    tree.pack(side="left", fill="both", expand=True)

    def destroy_active_editors():
        if popup.active_listbox:
            try: popup.active_listbox.destroy()
            except: pass
            popup.active_listbox = None
        if popup.active_editor:
            try: popup.active_editor.destroy()
            except: pass
            popup.active_editor = None
        popup.editing_row_col = None

    # --- THE FIX: Buttery Smooth X/Y Scrolling ---
    def _fast_h_scroll(event):
        destroy_active_editors() 
        delta = -1 * (event.delta / 120) if os.name == 'nt' else -1 * event.delta
        tree.xview_moveto(tree.xview()[0] + (delta * 0.02))
    tree.bind("<Shift-MouseWheel>", _fast_h_scroll)
    
    def _fast_v_scroll(event):
        destroy_active_editors() 
        delta = -1 * (event.delta / 120) if os.name == 'nt' else -1 * event.delta
        tree.yview_moveto(tree.yview()[0] + (delta * 0.008))
    tree.bind("<MouseWheel>", _fast_v_scroll)
    # ---------------------------------------------

    def on_left_click(event):
        region = tree.identify("region", event.x, event.y)
        if region == "cell":
            col = tree.identify_column(event.x)
            row_id = tree.identify_row(event.y)
            if not row_id or "empty" in tree.item(row_id, "tags"): return
            
            if col == '#1': 
                destroy_active_editors()
                for r in raw_data_cache:
                    if str(id(r)) == row_id:
                        r[0] = "☐" if r[0] == "☑" else "☑"
                        break
                render_grid()
                        
    tree.bind("<ButtonRelease-1>", on_left_click)

    def on_right_click(event):
        destroy_active_editors()
        region = tree.identify("region", event.x, event.y)
        menu = tk.Menu(popup, tearoff=0, font=("Arial", 10), bg=stock_view.CARD, fg=stock_view.FG, activebackground=stock_view.BLUE)
        
        row_id = tree.identify_row(event.y)
        if region == "cell" and row_id and "empty" not in tree.item(row_id, "tags"):
            menu.add_command(label="❌ Delete This Row", command=lambda: delete_row(row_id))
            menu.add_separator()

        col = tree.identify_column(event.x)
        if col:
            col_idx = int(col[1:]) - 1
            col_name = cols[col_idx]
            if col_name not in ["☑", "ghost"]:
                menu.add_command(label=f"🧹 Clear Entire '{col_name}' Column", command=lambda: clear_column(col_idx))
            
        menu.tk_popup(event.x_root, event.y_root)

    def delete_row(row_id):
        for idx, r in enumerate(raw_data_cache):
            if str(id(r)) == row_id:
                raw_data_cache.pop(idx)
                break
        render_grid()

    def clear_column(idx):
        if idx == 0: return 
        for child in tree.get_children():
            if "empty" in tree.item(child, "tags"): continue
            vals = list(tree.item(child, "values"))
            c_name = cols[idx]
            
            if c_name in ["Qty", "Price", "Base Rate", "Price (Inc GST)", "MRP", "Amount", "Low Stock"]:
                vals[idx] = "0" if c_name == "Qty" else "0.00"
            elif c_name == "GST": vals[idx] = "0%"
            else: vals[idx] = ""
            
            tree.item(child, values=vals)
            
            for c_idx, cached_row in enumerate(raw_data_cache):
                if cached_row[1] == vals[1]:
                    raw_data_cache[c_idx] = vals
                    break

    tree.bind("<Button-3>", on_right_click)
    tree.bind("<ButtonPress-1>", lambda e: destroy_active_editors() if tree.identify("region", e.x, e.y) != "cell" else None, add="+")

    def find_col_idx(possible_names):
        for i, h in enumerate(headers):
            if any(p.lower() in h.lower() for p in possible_names): return i
        return -1
        
    idx_name = find_col_idx(["name", "desc", "item", "product"])
    idx_qty = find_col_idx(["qty", "qnty", "quant", "stock", "balance", "pieces"])
    idx_unit = find_col_idx(["unit", "uom", "measure"])
    if idx_unit == idx_qty: idx_unit = -1 
    
    idx_base = find_col_idx(["base", "taxable"])
    idx_price = find_col_idx(["cost", "price", "rate", "wholesale", "purchase", "inc gst"])
    idx_amount = find_col_idx(["amount", "total", "value", "sum"]) 
    if idx_price == idx_amount: idx_price = -1

    idx_mrp = find_col_idx(["mrp", "retail"]) if is_sales else -1
    idx_gst = find_col_idx(["gst", "tax"]) if has_gst else -1
    idx_hsn = find_col_idx(["hsn", "sac"]) if (is_sales and has_gst) else -1
    idx_reorder = find_col_idx(["reorder", "alert", "low", "min"]) if is_sales else -1
    idx_vendor = find_col_idx(["vendor", "supplier", "brand"]) if is_sales else -1
    idx_batch = find_col_idx(["batch", "lot"]) if is_sales else -1
    idx_exp = find_col_idx(["exp", "valid"]) if is_sales else -1

    raw_data_cache = []

    for row in data:
        if not any(row): continue 
        
        def safe_get(idx, default=""):
            if idx != -1 and idx < len(row): return row[idx].strip()
            return default
            
        name = safe_get(idx_name, "")
        if not name: continue 
        
        raw_qty_str = safe_get(idx_qty, "0")
        qty_val = 0.0
        split_unit = ""
        
        match = re.match(r'^\s*([0-9\.]+)\s*(.*)$', raw_qty_str)
        if match:
            try: qty_val = float(match.group(1))
            except: qty_val = 0.0
            split_unit = match.group(2).strip()
        else:
            try: qty_val = float(raw_qty_str)
            except: split_unit = raw_qty_str
            
        raw_mapped_unit = safe_get(idx_unit, "")
        if raw_mapped_unit and re.search(r'\d', raw_mapped_unit): raw_mapped_unit = ""
            
        final_unit = raw_mapped_unit if raw_mapped_unit else split_unit
        if not final_unit: final_unit = "Numbers (Nos.)"
        if final_unit != "Numbers (Nos.)": final_unit = final_unit.title()
        
        base_str = safe_get(idx_base, "")
        price_str = safe_get(idx_price, "")
        amt_str = safe_get(idx_amount, "")
        
        base_val = clean_num(base_str) if base_str else 0.0
        price_val = clean_num(price_str) if price_str else 0.0
        amt_val = clean_num(amt_str) if amt_str else 0.0
        
        calculated_unit_price = 0.0
        if amt_val > 0 and qty_val > 0:
            calculated_unit_price = round(amt_val / qty_val, 2)
            
        gst_str = safe_get(idx_gst, "0%") if has_gst else "0%"
        gst_pct = clean_num(gst_str.replace('%', ''))
        
        if has_gst:
            if price_val > 0 and base_val == 0:
                base_val = price_val / (1 + (gst_pct/100))
            elif base_val > 0 and price_val == 0:
                price_val = base_val + (base_val * gst_pct / 100)
            elif price_val == 0 and base_val == 0 and calculated_unit_price > 0:
                price_val = calculated_unit_price
                base_val = price_val / (1 + (gst_pct/100))
            
            if amt_val == 0 and qty_val > 0 and price_val > 0:
                amt_val = qty_val * price_val
        else:
            if price_val == 0 and calculated_unit_price > 0:
                price_val = calculated_unit_price
            if amt_val == 0 and qty_val > 0 and price_val > 0:
                amt_val = qty_val * price_val
            
        # --- THE FIX: Included empty string at end of raw cache for the Ghost Column ---
        if is_sales:
            mrp_str = safe_get(idx_mrp, "")
            mrp_val = clean_num(mrp_str) if mrp_str else 0.0
            if mrp_val == 0.0 and idx_mrp == -1 and price_val > 0:
                mrp_val = price_val

            hsn = safe_get(idx_hsn, "") if has_gst else ""
            reorder = safe_get(idx_reorder, "0") 
            vendor = safe_get(idx_vendor, "")
            batch = safe_get(idx_batch, "")
            exp = safe_get(idx_exp, "")
            
            if has_gst:
                raw_data_cache.append(["☑", name, f"{qty_val:g}", final_unit, f"{base_val:.2f}", f"{gst_pct:g}%", f"{price_val:.2f}", f"{mrp_val:.2f}", hsn, f"{amt_val:.2f}", reorder, vendor, batch, exp, ""])
            else:
                raw_data_cache.append(["☑", name, f"{qty_val:g}", final_unit, f"{price_val:.2f}", f"{mrp_val:.2f}", f"{amt_val:.2f}", reorder, vendor, batch, exp, ""])
        else:
            if has_gst:
                raw_data_cache.append(["☑", name, f"{qty_val:g}", final_unit, f"{base_val:.2f}", f"{gst_pct:g}%", f"{price_val:.2f}", f"{amt_val:.2f}", ""])
            else:
                raw_data_cache.append(["☑", name, f"{qty_val:g}", final_unit, f"{price_val:.2f}", f"{amt_val:.2f}", ""])
        # -------------------------------------------------------------------------------

    def render_grid(*args):
        for item in tree.get_children(): tree.delete(item)
        
        s_val = sort_var.get()
        working_data = list(raw_data_cache)
        
        # Sort using robust Price lookup regardless of GST mode
        if s_val == "A to Z": working_data.sort(key=lambda x: str(x[1]).lower())
        elif s_val == "Z to A": working_data.sort(key=lambda x: str(x[1]).lower(), reverse=True)
        elif s_val == "Highest Price": working_data.sort(key=lambda x: clean_num(x[cols.index("Price (Inc GST)")] if has_gst else x[cols.index("Price")]), reverse=True)
        elif s_val == "Lowest Price": working_data.sort(key=lambda x: clean_num(x[cols.index("Price (Inc GST)")] if has_gst else x[cols.index("Price")]))

        for i, r in enumerate(working_data):
            tag = "evenrow" if i % 2 == 0 else "oddrow"
            # Bind unique memory id so duplicate names never collide
            tree.insert("", "end", iid=str(id(r)), values=r, tags=(tag,))
            
        for i in range(len(working_data), 15):
            tag = "evenrow" if i % 2 == 0 else "oddrow"
            tree.insert("", "end", iid=f"empty_staging_{i}", values=["" for _ in cols], tags=(tag, "empty"))

    sort_combo.bind("<<ComboboxSelected>>", render_grid)
    render_grid() 

    existing_names = list(set([r[0] for r in database.get_grouped_stock()]))

    def on_double_click(event):
        region = tree.identify("region", event.x, event.y)
        if region != "cell": return
        
        col = tree.identify_column(event.x)
        row_id = tree.identify_row(event.y)
        if "empty" in tree.item(row_id, "tags"): return 
        
        if popup.editing_row_col == (row_id, col): return
        destroy_active_editors()
        
        popup.editing_row_col = (row_id, col)
        
        x, y, w, h = tree.bbox(row_id, col)
        col_idx = int(col[1:]) - 1
        
        if col_idx == 0 or cols[col_idx] == "ghost": return 
        
        val = tree.item(row_id, "values")[col_idx]
        col_name = cols[col_idx]
        
        entry = tk.Entry(tree, font=("Arial", 10), justify="left" if col_name == "Name" else "center")
        entry.place(x=x, y=y, width=w, height=h)
        entry.insert(0, val)
        entry.focus_set()
        
        popup.active_editor = entry
        
        def save_edit(e=None):
            if not popup.active_editor: return
            try:
                new_val = entry.get()
                vals = list(tree.item(row_id, "values"))
                vals[col_idx] = new_val
                
                qty = clean_num(vals[cols.index("Qty")])
                
                if has_gst:
                    base_idx = cols.index("Base Rate")
                    price_idx = cols.index("Price (Inc GST)")
                    gst_idx = cols.index("GST")
                    amt_idx = cols.index("Amount")
                    
                    base = clean_num(vals[base_idx])
                    price = clean_num(vals[price_idx])
                    gst = clean_num(str(vals[gst_idx]).replace("%", ""))
                    
                    if col_name == "Base Rate":
                        price = base * (1 + (gst/100))
                        vals[price_idx] = f"{price:.2f}"
                    elif col_name in ["Price (Inc GST)", "GST"]:
                        base = price / (1 + (gst/100))
                        vals[base_idx] = f"{base:.2f}"
                        if col_name == "GST": vals[gst_idx] = f"{gst:g}%"
                    
                    amt = qty * price
                    vals[amt_idx] = f"{amt:.2f}"
                else:
                    price_idx = cols.index("Price")
                    amt_idx = cols.index("Amount")
                    price = clean_num(vals[price_idx])
                    amt = qty * price
                    vals[amt_idx] = f"{amt:.2f}"
                
                tree.item(row_id, values=vals)
                
                for idx, cached_row in enumerate(raw_data_cache):
                    if str(id(cached_row)) == row_id:
                        raw_data_cache[idx] = vals
                        break
            except Exception as ex: print(ex)
            destroy_active_editors()

        entry.bind("<Return>", save_edit)
        
        if col_name == "Name":
            lb = tk.Listbox(tree, font=("Arial", 10), height=5, bg=stock_view.BG, fg=stock_view.FG, selectbackground=stock_view.BLUE, highlightbackground=stock_view.BORDER, highlightthickness=1, cursor="hand2")
            popup.active_listbox = lb
            
            def filter_names(*args):
                s = entry.get().lower()
                lb.delete(0, tk.END)
                m = [i for i in existing_names if s in i.lower()]
                if s and m:
                    lb.place(x=x, y=y+h, width=w)
                    for match in m: lb.insert(tk.END, match)
                    lb.lift()
                else:
                    lb.place_forget()
                    
            entry.bind("<KeyRelease>", filter_names)
            entry.bind("<Down>", lambda e: (lb.focus(), lb.selection_set(0)) if lb.winfo_ismapped() else None)
            
            def select_from_list(e=None):
                if lb.curselection():
                    entry.delete(0, tk.END)
                    entry.insert(0, lb.get(lb.curselection()[0]))
                    save_edit()
                    
            lb.bind("<Return>", select_from_list)
            lb.bind("<Double-Button-1>", select_from_list)
            
        def on_focus_out(e):
            popup.after(150, check_focus)
            
        def check_focus():
            fw = popup.focus_get()
            if fw != entry and fw != popup.active_listbox: save_edit()
                
        entry.bind("<FocusOut>", on_focus_out)
        
    tree.bind("<Double-1>", on_double_click)