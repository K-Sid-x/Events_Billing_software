import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import json
from datetime import date
import sys
import os

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
from views.invoice_parts.calendar_widget import NativeCalendar

def center_popup(window, w, h):
    window.update_idletasks()
    sw = window.winfo_screenwidth()
    sh = window.winfo_screenheight()
    x = int((sw / 2) - (w / 2))
    y = int((sh / 2) - (h / 2))
    window.geometry(f"{w}x{h}+{x}+{y}")

def apply_focus(stock_view, w):
    w.bind("<FocusIn>", lambda e: w.config(bg=stock_view.FOCUS_BG), add="+")
    w.bind("<FocusOut>", lambda e: w.config(bg=stock_view.BG), add="+")

def focus_next(event):
    event.widget.tk_focusNext().focus()
    return "break"

def bind_combo_enter(cb):
    cb.bind("<Return>", lambda e: [cb.event_generate('<Down>'), "break"][1])


def open_loss_popup(stock_view):
    _build_stock_form(stock_view, "Record Stock Loss / Damage", "LOSS", stock_view.DANGER, is_loss=True)

def open_add_popup(stock_view):
    _build_stock_form(stock_view, "Add New Stock Item", "ADD", stock_view.BLUE, is_loss=False)


def _build_stock_form(stock_view, title, trans_type, btn_color, is_loss=False):
    allowed, err_msg = database.check_stock_permission(action="adjust", company_id=stock_view.comp_id)
    if not allowed:
        messagebox.showerror("Access Denied", err_msg, parent=stock_view)
        return
        
    popup = tk.Toplevel(stock_view)
    popup.title(title)
    popup.configure(bg=stock_view.CARD); popup.grab_set()

    # --- THE FIX: MVC Compliant Fetches (No Raw SQL) ---
    existing_names = database.get_unique_stock_names(stock_view.comp_id)
    party_names = database.get_unique_customer_names(stock_view.comp_id)
    has_gst = database.get_company_gst_toggle(stock_view.comp_id)
    # ---------------------------------------------------

    def bind_focus_drop(container):
        container.bind("<ButtonPress-1>", lambda e: popup.focus_set() if e.widget.winfo_class() not in ('Entry', 'Text', 'TCombobox', 'Listbox', 'Button') else None, add="+")
        for child in container.winfo_children():
            if child.winfo_class() in ('Frame', 'Label', 'Canvas'):
                bind_focus_drop(child)

    tk.Label(popup, text=title, font=("Arial", 16, "bold"), bg=stock_view.CARD, fg=stock_view.FG).pack(anchor="w", pady=(15, 0), padx=20)
    form = tk.Frame(popup, bg=stock_view.CARD); form.pack(fill="both", expand=True, padx=20, pady=(5,0))
    
    full_units = ["Numbers (Nos.)", "Kilograms (Kg)", "Pieces (Pcs)", "Packets (Pkts)", "Running Feet (Rft)", "Running Metre (Rmt)", "Square Feet (Sq.ft.)", "Bundles (Bdl.)"]
    
    # --- THE FIX: Inherit the dynamic global date format instead of hardcoding ---
    name_var = tk.StringVar(); date_var = tk.StringVar(value=date.today().strftime(stock_view.date_fmt_code))
    qty_var = tk.StringVar(value="0"); unit_var = tk.StringVar(value="Numbers (Nos.)")
    # -----------------------------------------------------------------------------
    price_var = tk.StringVar(value="0.0"); mrp_var = tk.StringVar(value="0.0")
    gst_var = tk.StringVar(value="0%"); hsn_var = tk.StringVar()
    reorder_var = tk.StringVar(value="5"); dep_var = tk.StringVar(value="0.0")
    
    sku_var = tk.StringVar(); vendor_var = tk.StringVar()
    batch_var = tk.StringVar(); exp_var = tk.StringVar()

    is_sales = (stock_view.b_type == "Sales")

    r1 = tk.Frame(form, bg=stock_view.CARD); r1.pack(fill="x", pady=5)
    df = tk.Frame(r1, bg=stock_view.CARD); df.pack(side="left", expand=True, fill="x", padx=(0,5))
    tk.Label(df, text="Date *", bg=stock_view.CARD, fg=stock_view.SEC_FG, font=("Arial", 9, "bold")).pack(anchor="w")
    di = tk.Frame(df, bg=stock_view.CARD); di.pack(anchor="w")
    de = tk.Entry(di, textvariable=date_var, font=("Arial", 11), width=12, bg=stock_view.BG, fg=stock_view.FG, insertbackground=stock_view.FG, highlightbackground=stock_view.BORDER, highlightthickness=1)
    de.pack(side="left", ipady=3); apply_focus(stock_view, de); de.bind("<Return>", focus_next)
    tk.Button(di, text="📅", font=("Arial", 10), bg=stock_view.BORDER, fg=stock_view.FG, relief="flat", command=lambda: NativeCalendar(popup, date_var)).pack(side="left")
    de.focus()

    if is_sales and not is_loss:
        sf = tk.Frame(r1, bg=stock_view.CARD); sf.pack(side="left", expand=True, fill="x", padx=(5,0))
        tk.Label(sf, text="Scan Barcode / SKU", bg=stock_view.CARD, fg=stock_view.SEC_FG, font=("Arial", 9, "bold")).pack(anchor="w")
        se = tk.Entry(sf, textvariable=sku_var, font=("Arial", 11), bg=stock_view.BG, fg=stock_view.FG, insertbackground=stock_view.FG, highlightbackground=stock_view.BORDER, highlightthickness=1)
        se.pack(fill="x", ipady=3); apply_focus(stock_view, se); se.bind("<Return>", focus_next)

    tk.Label(form, text="Item Name *", bg=stock_view.CARD, fg=stock_view.SEC_FG, font=("Arial", 9, "bold")).pack(anchor="w", pady=(0, 0))
    ne = tk.Entry(form, textvariable=name_var, font=("Arial", 11), bg=stock_view.BG, fg=stock_view.FG, insertbackground=stock_view.FG, highlightbackground=stock_view.BORDER, highlightthickness=1)
    ne.pack(fill="x", ipady=3, pady=(0, 5)); apply_focus(stock_view, ne)

    lb = tk.Listbox(form, font=("Arial", 10), height=4, bg=stock_view.BG, fg=stock_view.FG, selectbackground=stock_view.BLUE, highlightbackground=stock_view.BORDER, highlightthickness=1, cursor="hand2")
    
    def fetch_latest_price_and_unit(selected_item):
        info = database.get_latest_stock_info(selected_item)
        if info:
            fetched_unit = info[0]
            matched_full = next((u for u in full_units if fetched_unit in u), full_units[0])
            unit_var.set(matched_full); price_var.set(str(info[1]))
            try:
                j = json.loads(info[2])
                if not is_loss:
                    if j.get("mrp"): mrp_var.set(str(j.get("mrp")))
                    if j.get("gst"): gst_var.set(j.get("gst"))
                    if j.get("hsn"): hsn_var.set(j.get("hsn"))
                    if j.get("reorder_level"): reorder_var.set(str(j.get("reorder_level")))
                    if j.get("vendor"): vendor_var.set(j.get("vendor"))
                    if j.get("depreciation"): dep_var.set(str(j.get("depreciation")))
            except: pass

    def update_list(*args):
        s = name_var.get().lower(); lb.delete(0, tk.END)
        m = [i for i in existing_names if s in i.lower() and s != i.lower()]
        if s and m: popup.update_idletasks(); lb.place(x=ne.winfo_x(), y=ne.winfo_y()+ne.winfo_height()+2, width=ne.winfo_width()); [lb.insert(tk.END, x) for x in m]; lb.lift()
        else: lb.place_forget()
    name_var.trace("w", update_list)
    ne.bind("<Down>", lambda e: (lb.focus(), lb.selection_set(0)) if lb.winfo_ismapped() else None)
    
    r3 = tk.Frame(form, bg=stock_view.CARD); r3.pack(fill="x", pady=5)
    qf = tk.Frame(r3, bg=stock_view.CARD); qf.pack(side="left", expand=True, fill="x", padx=(0,5))
    uf = tk.Frame(r3, bg=stock_view.CARD); uf.pack(side="left", expand=True, fill="x", padx=5 if not is_loss else 0)

    tk.Label(qf, text="Quantity *", bg=stock_view.CARD, fg=stock_view.SEC_FG, font=("Arial", 9, "bold")).pack(anchor="w")
    qe = tk.Entry(qf, textvariable=qty_var, font=("Arial", 11), bg=stock_view.BG, fg=stock_view.FG, insertbackground=stock_view.FG, highlightbackground=stock_view.BORDER, highlightthickness=1)
    qe.pack(fill="x", ipady=3); apply_focus(stock_view, qe); qe.bind("<FocusIn>", lambda a: qe.delete('0','end') if qe.get()=='0' else None, add="+"); qe.bind("<Return>", focus_next)
    
    # --- THE FIX: Pressing Enter now accepts your typing, and clicking away hides the box! ---
    ne.bind("<Return>", lambda e: [lb.place_forget(), qe.focus(), "break"][1])
    lb.bind("<Return>", lambda e: [name_var.set(lb.get(lb.curselection()[0])), fetch_latest_price_and_unit(name_var.get()), lb.place_forget(), qe.focus(), "break"][3] if lb.curselection() else None)
    lb.bind("<Double-Button-1>", lambda e: [name_var.set(lb.get(lb.curselection()[0])), fetch_latest_price_and_unit(name_var.get()), lb.place_forget(), qe.focus()])
    
    def hide_item_lb(e=None):
        fw = popup.focus_get()
        if fw != ne and fw != lb: lb.place_forget()
    ne.bind("<FocusOut>", lambda e: popup.after(150, hide_item_lb))
    # ---------------------------------------------------------------------------------------

    tk.Label(uf, text="Unit", bg=stock_view.CARD, fg=stock_view.SEC_FG, font=("Arial", 9, "bold")).pack(anchor="w")
    uc = ttk.Combobox(uf, textvariable=unit_var, values=full_units, state="readonly", style="Theme.TCombobox")
    uc.pack(fill="x", ipady=3); bind_combo_enter(uc); uc.bind("<Right>", focus_next)

    if not is_loss:
        rf = tk.Frame(r3, bg=stock_view.CARD); rf.pack(side="left", expand=True, fill="x", padx=(5,0))
        tk.Label(rf, text="Low Stock Lvl", bg=stock_view.CARD, fg=stock_view.SEC_FG, font=("Arial", 9, "bold")).pack(anchor="w")
        re_e = tk.Entry(rf, textvariable=reorder_var, font=("Arial", 11), bg=stock_view.BG, fg=stock_view.FG, insertbackground=stock_view.FG, highlightbackground=stock_view.BORDER, highlightthickness=1)
        re_e.pack(fill="x", ipady=3); apply_focus(stock_view, re_e); re_e.bind("<Return>", focus_next)

    try:
        curr = stock_view.curr_fmt.split('(')[1][0]
    except:
        curr = "₹"
        
    r4 = tk.Frame(form, bg=stock_view.CARD); r4.pack(fill="x", pady=5)
    cf = tk.Frame(r4, bg=stock_view.CARD); cf.pack(side="left", expand=True, fill="x", padx=(0,5 if not is_loss else 0))
    
    if is_loss: price_label_text = f"MRP ({curr})"
    elif is_sales: price_label_text = f"Wholesale Cost ({curr})"
    else: price_label_text = f"Price / Rate (Inc. GST) ({curr})" if has_gst else f"Price / Rate ({curr})"
        
    tk.Label(cf, text=price_label_text, bg=stock_view.CARD, fg=stock_view.SEC_FG, font=("Arial", 9, "bold")).pack(anchor="w")
    
    ce = tk.Entry(cf, textvariable=price_var, font=("Arial", 11), bg=stock_view.BG, fg=stock_view.FG, insertbackground=stock_view.FG, highlightbackground=stock_view.BORDER, highlightthickness=1)
    ce.pack(fill="x", ipady=3); apply_focus(stock_view, ce); ce.bind("<FocusIn>", lambda a: ce.delete('0','end') if ce.get()=='0.0' else None, add="+"); ce.bind("<Return>", focus_next)

    # --- THE FIX: Moved Depreciation to Row 4 so it has room to breathe! ---
    if not is_loss:
        dep_f = tk.Frame(r4, bg=stock_view.CARD); dep_f.pack(side="left", expand=True, fill="x", padx=(5,0))
        tk.Label(dep_f, text="Depreciation % / Yr", bg=stock_view.CARD, fg=stock_view.SEC_FG, font=("Arial", 9, "bold")).pack(anchor="w")
        dep_e = tk.Entry(dep_f, textvariable=dep_var, font=("Arial", 11), bg=stock_view.BG, fg=stock_view.FG, insertbackground=stock_view.FG, highlightbackground=stock_view.BORDER, highlightthickness=1)
        dep_e.pack(fill="x", ipady=3); apply_focus(stock_view, dep_e); dep_e.bind("<Return>", focus_next)
    # -----------------------------------------------------------------------

    if is_sales and not is_loss:
        mf = tk.Frame(r4, bg=stock_view.CARD); mf.pack(side="left", expand=True, fill="x", padx=5)
        mgf= tk.Frame(r4, bg=stock_view.CARD); mgf.pack(side="left", expand=True, fill="x", padx=(5,0))

        tk.Label(mf, text=f"MRP ({curr})", bg=stock_view.CARD, fg=stock_view.SEC_FG, font=("Arial", 9, "bold")).pack(anchor="w")
        me = tk.Entry(mf, textvariable=mrp_var, font=("Arial", 11), bg=stock_view.BG, fg=stock_view.FG, insertbackground=stock_view.FG, highlightbackground=stock_view.BORDER, highlightthickness=1)
        me.pack(fill="x", ipady=3); apply_focus(stock_view, me); me.bind("<FocusIn>", lambda a: me.delete('0','end') if me.get()=='0.0' else None, add="+"); me.bind("<Return>", focus_next)

        tk.Label(mgf, text="True Net Margin", bg=stock_view.CARD, fg=stock_view.SEC_FG, font=("Arial", 9, "bold")).pack(anchor="w")
        lbl_margin = tk.Label(mgf, text="0.0%", font=("Arial", 14, "bold"), bg=stock_view.CARD, fg=stock_view.SEC_FG)
        lbl_margin.pack(anchor="w")
        
        lbl_tax_breakdown = tk.Label(mgf, text="Base: 0.00 | Tax: 0.00", font=("Arial", 8, "italic"), bg=stock_view.CARD, fg=stock_view.SEC_FG)
        lbl_tax_breakdown.pack(anchor="w")

        def calc_margin(*args):
            try:
                c, m = float(price_var.get()), float(mrp_var.get())
                gst_str = gst_var.get().replace("%", "").strip()
                gst_pct = float(gst_str) if gst_str and gst_str.lower() != "exempt" else 0.0
                
                if m > 0:
                    base_revenue = m / (1 + (gst_pct / 100))
                    tax_amount = m - base_revenue
                    true_profit = base_revenue - c
                    
                    mg = (true_profit / base_revenue) * 100 if base_revenue > 0 else 0
                    
                    lbl_tax_breakdown.config(text=f"Base: {base_revenue:.2f} | Tax: {tax_amount:.2f}")
                    lbl_margin.config(text=f"{mg:.1f}%", fg=stock_view.GREEN if mg > 0 else stock_view.DANGER)
                else: 
                    lbl_margin.config(text="0.0%", fg=stock_view.SEC_FG)
                    lbl_tax_breakdown.config(text="Base: 0.00 | Tax: 0.00")
            except: 
                lbl_margin.config(text="0.0%", fg=stock_view.SEC_FG)
                lbl_tax_breakdown.config(text="Base: 0.00 | Tax: 0.00")
                
        price_var.trace("w", calc_margin)
        mrp_var.trace("w", calc_margin)
        gst_var.trace("w", calc_margin) 

    if not is_loss and has_gst:
        r5 = tk.Frame(form, bg=stock_view.CARD); r5.pack(fill="x", pady=5)
        hf = tk.Frame(r5, bg=stock_view.CARD); hf.pack(side="left", expand=True, fill="x", padx=(0,5))
        gf = tk.Frame(r5, bg=stock_view.CARD); gf.pack(side="left", expand=True, fill="x", padx=(5,0))

        tk.Label(hf, text="HSN/SAC Code", bg=stock_view.CARD, fg=stock_view.SEC_FG, font=("Arial", 9, "bold")).pack(anchor="w")
        he = tk.Entry(hf, textvariable=hsn_var, font=("Arial", 11), bg=stock_view.BG, fg=stock_view.FG, insertbackground=stock_view.FG, highlightbackground=stock_view.BORDER, highlightthickness=1)
        he.pack(fill="x", ipady=3); apply_focus(stock_view, he); he.bind("<Return>", focus_next)

        tk.Label(gf, text="GST % (Inclusive)" if not is_sales else "GST %", bg=stock_view.CARD, fg=stock_view.SEC_FG, font=("Arial", 9, "bold")).pack(anchor="w")
        gc = ttk.Combobox(gf, textvariable=gst_var, values=["0%", "5%", "12%", "18%", "28%", "Exempt"], state="readonly", style="Theme.TCombobox")
        gc.pack(fill="x", ipady=3); bind_combo_enter(gc); gc.bind("<Right>", focus_next)
        
        if not is_sales:
            lbl_tax_calc = tk.Label(gf, text="Base: 0.00 | Tax: 0.00", font=("Arial", 8, "italic"), bg=stock_view.CARD, fg=stock_view.SEC_FG)
            lbl_tax_calc.pack(anchor="e", pady=(2,0))

            def update_inclusive_tax(*args):
                try:
                    rate = float(price_var.get())
                    gst_str = gst_var.get().replace("%", "").strip()
                    gst_pct = float(gst_str) if gst_str and gst_str.lower() != "exempt" else 0.0
                    
                    if gst_pct > 0 and rate > 0:
                        base = rate / (1 + (gst_pct / 100))
                        tax = rate - base
                        lbl_tax_calc.config(text=f"Base: {base:.2f} | Tax: {tax:.2f}", fg=stock_view.GREEN)
                    else:
                        lbl_tax_calc.config(text="Base: 0.00 | Tax: 0.00", fg=stock_view.SEC_FG)
                except:
                    pass
            
            price_var.trace("w", update_inclusive_tax)
            gst_var.trace("w", update_inclusive_tax)

    if not is_loss:
        r6 = tk.Frame(form, bg=stock_view.CARD); r6.pack(fill="x", pady=5)
        vf = tk.Frame(r6, bg=stock_view.CARD); vf.pack(side="left", expand=True, fill="x", padx=(0, 5 if is_sales else 0))

        tk.Label(vf, text="Supplier / Vendor", bg=stock_view.CARD, fg=stock_view.SEC_FG, font=("Arial", 9, "bold")).pack(anchor="w")
        ve = tk.Entry(vf, textvariable=vendor_var, font=("Arial", 11), bg=stock_view.BG, fg=stock_view.FG, insertbackground=stock_view.FG, highlightbackground=stock_view.BORDER, highlightthickness=1)
        ve.pack(fill="x", ipady=3); apply_focus(stock_view, ve)
        
        vendor_lb = tk.Listbox(form, font=("Arial", 10), height=4, bg=stock_view.BG, fg=stock_view.FG, selectbackground=stock_view.BLUE, highlightbackground=stock_view.BORDER, highlightthickness=1, cursor="hand2")
        
        def update_vendor_list(*args):
            s = vendor_var.get().lower(); vendor_lb.delete(0, tk.END)
            m = [i for i in party_names if s in i.lower() and s != i.lower()]
            if s and m: 
                popup.update_idletasks()
                vx = r6.winfo_x() + vf.winfo_x() + ve.winfo_x()
                vy = r6.winfo_y() + vf.winfo_y() + ve.winfo_y() + ve.winfo_height() + 2
                vendor_lb.place(x=vx, y=vy, width=ve.winfo_width())
                [vendor_lb.insert(tk.END, x) for x in m]
                vendor_lb.lift()
            else: vendor_lb.place_forget()
            
        vendor_var.trace("w", update_vendor_list)
        ve.bind("<Down>", lambda e: (vendor_lb.focus(), vendor_lb.selection_set(0)) if vendor_lb.winfo_ismapped() else None)
        # --- THE FIX: Pressing Enter now accepts your typing, and clicking away hides the box! ---
        ve.bind("<Return>", lambda e: [vendor_lb.place_forget(), focus_next(e), "break"][1])
        vendor_lb.bind("<Return>", lambda e: [vendor_var.set(vendor_lb.get(vendor_lb.curselection()[0])), vendor_lb.place_forget(), focus_next(e), "break"][3] if vendor_lb.curselection() else None)
        vendor_lb.bind("<Double-Button-1>", lambda e: [vendor_var.set(vendor_lb.get(vendor_lb.curselection()[0])), vendor_lb.place_forget(), focus_next(e)])

        def hide_vendor_lb(e=None):
            fw = popup.focus_get()
            if fw != ve and fw != vendor_lb: vendor_lb.place_forget()
        ve.bind("<FocusOut>", lambda e: popup.after(150, hide_vendor_lb))
        # ---------------------------------------------------------------------------------------

        if is_sales:
            bf = tk.Frame(r6, bg=stock_view.CARD); bf.pack(side="left", expand=True, fill="x", padx=5)
            ef = tk.Frame(r6, bg=stock_view.CARD); ef.pack(side="left", expand=True, fill="x", padx=(5,0))

            tk.Label(bf, text="Batch No.", bg=stock_view.CARD, fg=stock_view.SEC_FG, font=("Arial", 9, "bold")).pack(anchor="w")
            be = tk.Entry(bf, textvariable=batch_var, font=("Arial", 11), bg=stock_view.BG, fg=stock_view.FG, insertbackground=stock_view.FG, highlightbackground=stock_view.BORDER, highlightthickness=1)
            be.pack(fill="x", ipady=3); apply_focus(stock_view, be); be.bind("<Return>", focus_next)

            tk.Label(ef, text="Expiry (YYYY-MM)", bg=stock_view.CARD, fg=stock_view.SEC_FG, font=("Arial", 9, "bold")).pack(anchor="w")
            ee = tk.Entry(ef, textvariable=exp_var, font=("Arial", 11), bg=stock_view.BG, fg=stock_view.FG, insertbackground=stock_view.FG, highlightbackground=stock_view.BORDER, highlightthickness=1)
            ee.pack(fill="x", ipady=3); apply_focus(stock_view, ee); ee.bind("<Return>", focus_next)

    tk.Label(form, text="Notes / Reason", bg=stock_view.CARD, fg=stock_view.SEC_FG, font=("Arial", 9, "bold")).pack(anchor="w", pady=(0, 2))
    nt = tk.Entry(form, font=("Arial", 11), bg=stock_view.BG, fg=stock_view.FG, insertbackground=stock_view.FG, highlightbackground=stock_view.BORDER, highlightthickness=1)
    nt.pack(fill="x", ipady=3); apply_focus(stock_view, nt); nt.bind("<Return>", lambda e: save_item())

    def save_item():
        if not name_var.get().strip(): messagebox.showerror("Error", "Item Name is required!", parent=popup); return
        
        unit_str = unit_var.get().strip()
        unit = unit_str.split("(")[-1].replace(")", "").strip() if "(" in unit_str else unit_str
        
        try: qty, price = float(qty_var.get()), float(price_var.get())
        except ValueError: qty, price = 0.0, 0.0
        
        try: mrp_val, reorder_val = float(mrp_var.get()), float(reorder_var.get())
        except: mrp_val, reorder_val = 0.0, 5.0
        
        # --- THE FIX: Parse and Save Depreciation ---
        try: dep_val = float(dep_var.get())
        except: dep_val = 0.0
        # ------------------------------------------

        if is_loss:
            notes_dict = {"notes": nt.get().strip()}
        else:
            notes_dict = {
                "notes": nt.get().strip(), 
                "mrp": mrp_val, 
                "gst": gst_var.get(), 
                "hsn": hsn_var.get().strip(), 
                "reorder_level": reorder_val,
                "depreciation": dep_val,
                "vendor": vendor_var.get().strip()
            }
            if is_sales:
                notes_dict.update({"sku": sku_var.get().strip(), "batch": batch_var.get().strip(), "expiry": exp_var.get().strip()})
        
        # --- THE FIX: Use safe helper to add stock instead of raw SQL! ---
        safe_name = name_var.get().strip()
        database.add_stock(safe_name, qty, unit, price, json.dumps(notes_dict), date_var.get().strip(), trans_type)
        
        act_str = "Recorded Loss" if is_loss else "Added Stock"
        database.log_audit("Stock", act_str, record_ref=safe_name, details=f"Quantity: {qty:g} {unit} • Notes: {nt.get().strip()}", amount=price, company_id=stock_view.comp_id)
        
        stock_view.load_data(); popup.destroy()
        # -----------------------------------------------------------------

    btn = tk.Button(form, text="Save Record", font=("Arial", 11, "bold"), bg=btn_color, fg="#ffffff", relief="flat", pady=8, cursor="hand2", command=save_item)
    btn.pack(fill="x", pady=(15, 15))
    
    popup.bind("<Escape>", lambda e: popup.destroy())
    popup.bind("<Control-Return>", lambda e: save_item())
    
    bind_focus_drop(popup)
    
    popup.update_idletasks()
    req_h = popup.winfo_reqheight() + 20
    center_popup(popup, 600 if (is_sales and not is_loss) else 500, req_h)

def open_audit_popup(stock_view):
    allowed, err_msg = database.check_stock_permission(action="adjust", company_id=stock_view.comp_id)
    if not allowed:
        messagebox.showerror("Access Denied", err_msg, parent=stock_view)
        return
        
    popup = tk.Toplevel(stock_view)
    popup.title("Stock Audit & Reconciliation")
    popup.configure(bg=stock_view.CARD); popup.grab_set()

    tk.Label(popup, text="Physical Stock Audit", font=("Arial", 16, "bold"), bg=stock_view.CARD, fg=stock_view.FG).pack(anchor="w", pady=(15, 5), padx=20)
    tk.Label(popup, text="Search item & enter physical count. System will auto-correct.", font=("Arial", 10), bg=stock_view.CARD, fg=stock_view.SEC_FG).pack(anchor="w", padx=20)
    
    form = tk.Frame(popup, bg=stock_view.CARD); form.pack(fill="both", expand=True, padx=20, pady=10)
    
    name_var = tk.StringVar(); count_var = tk.StringVar(value="0")
    parsed = stock_view.get_parsed_data(ignore_filters=True)

    tk.Label(form, text="Search & Select Item", bg=stock_view.CARD, fg=stock_view.SEC_FG, font=("Arial", 9, "bold")).pack(anchor="w")
    ne = tk.Entry(form, textvariable=name_var, font=("Arial", 12), bg=stock_view.BG, fg=stock_view.FG, insertbackground=stock_view.FG, highlightbackground=stock_view.BORDER, highlightthickness=1)
    ne.pack(fill="x", ipady=3, pady=(0, 15))

    sys_lbl = tk.Label(form, text="Current System Qty: --", font=("Arial", 12, "bold"), bg=stock_view.CARD, fg=stock_view.BLUE)
    sys_lbl.pack(anchor="w", pady=(0, 15))

    lb = tk.Listbox(form, font=("Arial", 10), height=4, bg=stock_view.BG, fg=stock_view.FG, selectbackground=stock_view.BLUE, highlightbackground=stock_view.BORDER, highlightthickness=1, cursor="hand2")
    
    target_item = []
    def update_audit_list(*args):
        s = name_var.get().strip().lower(); lb.delete(0, tk.END)
        m = [i[0] for i in parsed if s in i[0].lower() and s != i[0].lower()]
        if s and m: popup.update_idletasks(); lb.place(x=ne.winfo_x(), y=ne.winfo_y()+ne.winfo_height()+2, width=ne.winfo_width()); [lb.insert(tk.END, x) for x in m]; lb.lift()
        else: lb.place_forget()

        matches = [i for i in parsed if i[0].lower() == name_var.get().strip().lower()]
        if matches:
            target_item.clear(); target_item.extend(matches[0])
            sys_lbl.config(text=f"Current System Qty: {matches[0][4]:g} {matches[0][5]}")
        else: 
            target_item.clear()
            sys_lbl.config(text="Current System Qty: --")
            
    name_var.trace("w", update_audit_list)
    ne.bind("<Down>", lambda e: (lb.focus(), lb.selection_set(0)) if lb.winfo_ismapped() else None)
    lb.bind("<Return>", lambda e: [name_var.set(lb.get(lb.curselection()[0])), lb.place_forget(), "break"][1] if lb.curselection() else None)
    lb.bind("<Double-Button-1>", lambda e: [name_var.set(lb.get(lb.curselection()[0])), lb.place_forget()])

    tk.Label(form, text="Actual Physical Count", bg=stock_view.CARD, fg=stock_view.SEC_FG, font=("Arial", 9, "bold")).pack(anchor="w")
    ce = tk.Entry(form, textvariable=count_var, font=("Arial", 14, "bold"), bg=stock_view.BG, fg=stock_view.FG, insertbackground=stock_view.FG, highlightbackground=stock_view.BORDER, highlightthickness=1)
    ce.pack(fill="x", ipady=3)
    ce.bind("<FocusIn>", lambda a: ce.delete('0','end') if ce.get()=='0' else None, add="+")

    def save_audit():
        if not target_item: 
            messagebox.showerror("Selection Error", "Please search and select a valid item from the system before reconciling.", parent=popup)
            return
            
        try: physical = float(count_var.get())
        except: messagebox.showerror("Error", "Invalid Number", parent=popup); return

        sys_qty = target_item[4]; unit = target_item[5]
        diff = physical - sys_qty
        if diff == 0: messagebox.showinfo("Audit", "Stock matches perfectly!", parent=popup); popup.destroy(); return
        
        # --- THE FIX: The Zero-Dollar Audit Loophole ---
        # If the item was imported via CSV without a price, the system defaulted to 0.0. 
        # This calculates the true moving average cost directly from the ledger's net value!
        latest_p = database.get_latest_stock_info(target_item[0])
        price = float(latest_p[1]) if latest_p and latest_p[1] else 0.0
        
        if price <= 0.01:
            net_qty = float(target_item[4])
            net_val = float(target_item[6])
            if net_qty > 0.01:
                price = round(net_val / net_qty, 2)
        # -----------------------------------------------

        trans_type = "ADD" if diff > 0 else "LOSS"
        abs_diff = abs(diff)
        notes_str = json.dumps({"notes": f"Audit Discrepancy Auto-Correction ({'Found Extra' if diff > 0 else 'Missing'})"})
        
        # --- THE FIX: Use safe helper and global date format for Audit records ---
        database.add_stock(target_item[0], abs_diff, unit, price, notes_str, date.today().strftime(stock_view.date_fmt_code), trans_type)
        # -------------------------------------------------------------------------
        
        database.log_audit("Stock", "Audit Correction", record_ref=target_item[0], details=f"System auto-corrected discrepancy: {'Found Extra' if trans_type=='ADD' else 'Missing'} {abs_diff:g} {unit}", amount=price, company_id=stock_view.comp_id)
        
        stock_view.load_data(); popup.destroy()
        messagebox.showinfo("Reconciled", f"Adjusted {abs_diff:g} {unit} as {trans_type}.", parent=stock_view)

    tk.Button(form, text="Reconcile Ledger", font=("Arial", 11, "bold"), bg=stock_view.GREEN, fg="#ffffff", relief="flat", pady=8, cursor="hand2", command=save_audit).pack(fill="x", pady=(20, 0))

    popup.bind("<Escape>", lambda e: popup.destroy())
    popup.bind("<Control-Return>", lambda e: save_audit())

    def bind_focus_drop(container):
        container.bind("<ButtonPress-1>", lambda e: popup.focus_set() if e.widget.winfo_class() not in ('Entry', 'Text', 'TCombobox', 'Listbox', 'Button') else None, add="+")
        for child in container.winfo_children():
            if child.winfo_class() in ('Frame', 'Label', 'Canvas'):
                bind_focus_drop(child)
    bind_focus_drop(popup)

    popup.update_idletasks()
    req_h = popup.winfo_reqheight() + 20
    center_popup(popup, 500, req_h)