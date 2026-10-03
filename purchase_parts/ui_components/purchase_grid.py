import tkinter as tk
from tkinter import ttk
import os
import sys

# --- THE FIX: Bulletproof Executable Pathing ---
if getattr(sys, 'frozen', False):
    parent_dir = os.path.dirname(sys.executable)
    current_dir = os.path.join(parent_dir, "views")
else:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)

if parent_dir not in sys.path: sys.path.append(parent_dir)
# -----------------------------------------------

import database
from views.invoice_parts.helpers import format_currency

class PurchaseGridEngine:
    def __init__(self, form_ctx, parent_frame):
        self.form = form_ctx
        self.parent = parent_frame
        self.rows_data = []
        self.vendor_state_code = ""

        # --- THE FIX: Cache company state code ONCE during init ---
        self.comp_state_code = ""
        try:
            comp_c = database.get_company(self.form.comp_id)
            if len(comp_c) > 18 and comp_c[18]:
                self.comp_state_code = str(comp_c[18]).strip()
            if not self.comp_state_code and len(comp_c) > 9 and comp_c[9]:
                comp_gstin = str(comp_c[9]).strip()
                if len(comp_gstin) >= 2:
                    self.comp_state_code = comp_gstin[:2]
        except: pass
        # ----------------------------------------------------------

        self.historical_items = {}
        self.load_historical_items()
        
        self.item_lb = tk.Listbox(self.form.pop, font=("Segoe UI", 11), bg=self.form.CARD_BG, fg=self.form.TEXT_PRIMARY, selectbackground=self.form.LIST_SEL, selectforeground=self.form.TEXT_PRIMARY, highlightthickness=1, highlightbackground=self.form.BORDER_COLOR, cursor="hand2")
        self.active_row_vars = None
        self.item_lb.bind("<<ListboxSelect>>", self.global_lb_select)
        
        self.grid_container = tk.Frame(self.parent, bg=self.form.CARD_BG)
        self.grid_container.pack(fill="x", expand=True, padx=5, pady=5)
        self.grid_container.columnconfigure(1, weight=1)

        self.build_headers()
        self.add_row()

    def load_historical_items(self):
        try:
            conn = database.get_connection()
            c = conn.cursor()
            c.execute("""
                SELECT pi.item_name, pi.hsn, pi.gst_rate
                FROM purchase_items pi
                JOIN purchases p ON pi.purchase_id = p.id
                WHERE p.company_id = ? AND pi.item_name IS NOT NULL AND pi.item_name != ''
                ORDER BY pi.id ASC
            """, (self.form.comp_id,))
            for row in c.fetchall():
                i_name, i_hsn, i_gst = row
                self.historical_items[str(i_name).strip()] = {
                    "hsn": str(i_hsn).strip() if i_hsn else "",
                    "gst": str(int(i_gst)) if i_gst and float(i_gst).is_integer() else str(i_gst) if i_gst else "0"
                }
            conn.close()
        except: pass

    def global_lb_select(self, e=None):
        if self.item_lb.winfo_ismapped() and self.item_lb.curselection():
            sel_item = self.item_lb.get(self.item_lb.curselection())
            if self.active_row_vars:
                iv, hv, gv, eqty, ehsn = self.active_row_vars
                iv.set(sel_item)
                
                data = self.historical_items.get(sel_item, {})
                if getattr(self.form, 'has_gst', True):
                    if data.get('hsn'): hv.set(data['hsn'])
                    if data.get('gst'): gv.set(data['gst'])
                
                self.item_lb.place_forget()
                
                # --- THE FIX: Eliminate the Focus Race Condition! ---
                if getattr(self.form, 'has_gst', True) and ehsn:
                    ehsn.focus_set()
                else:
                    eqty.focus_set()
                # ----------------------------------------------------
                
                self.update_totals()
            return "break"

    def build_headers(self):
        # --- THE FIX: Dynamically construct headers based on GST Status! ---
        if getattr(self.form, 'has_gst', True):
            headers = [
                ("SI No.", 6), ("Particulars / Item Name", 35), ("HSN/SAC", 10), 
                ("GST %", 6), ("Qnty", 8), ("Units", 6), 
                ("Rate(Inc.Tax)", 12), ("Base Rate", 12), ("Amount", 12), ("", 4)
            ]
        else:
            headers = [
                ("SI No.", 6), ("Particulars / Item Name", 40), 
                ("Qnty", 10), ("Units", 8), 
                ("Rate", 16), ("Amount", 16), ("", 4)
            ]
        
        for i, (text, width) in enumerate(headers):
            lbl = tk.Label(self.grid_container, text=text, font=("Segoe UI", 9, "bold"), bg=self.form.HEADER_BG, fg=self.form.TEXT_PRIMARY, width=width, anchor="w" if i==1 else "center", highlightthickness=1, highlightbackground=self.form.BORDER_COLOR)
            lbl.grid(row=0, column=i, padx=2, pady=(0, 10), sticky="ew", ipady=4)

    def format_num_string(self, num_val):
        try:
            s_val = f"{float(num_val):.2f}"
            parts = s_val.split(".")
            int_part = parts[0]
            if "Indian" in getattr(self.form, "curr_fmt", "Indian"):
                if len(int_part) > 3:
                    import re
                    int_part = re.sub(r"(\d)(?=(\d{2})+(?!\d))", r"\1,", int_part[:-3]) + "," + int_part[-3:]
            else:
                int_part = f"{int(int_part):,}"
            return f"{int_part}.{parts[1]}"
        except: return "0.00"

    def add_row(self, focus_new=False):
        row_idx = len(self.rows_data) + 1 
        has_gst = getattr(self.form, 'has_gst', True)
        
        sl_lbl = tk.Label(self.grid_container, text=str(row_idx), font=("Segoe UI", 10), bg=self.form.CARD_BG, fg=self.form.TEXT_PRIMARY, width=6)
        sl_lbl.grid(row=row_idx, column=0, padx=2, pady=3)

        def make_entry(w, var, justify="left"):
            return tk.Entry(self.grid_container, textvariable=var, font=("Segoe UI", 11), bg=self.form.BG_COLOR, fg=self.form.TEXT_PRIMARY, insertbackground=self.form.TEXT_PRIMARY, width=w, highlightthickness=1, highlightbackground=self.form.BORDER_COLOR, justify=justify)

        # We create all vars uniformly so the database save engine doesn't break
        item_var = tk.StringVar(); hsn_var = tk.StringVar(); gst_var = tk.StringVar(value="0")
        qty_var = tk.StringVar(value="1"); unit_var = tk.StringVar(value="Nos")
        rate_inc_var = tk.StringVar(value="0.00"); rate_var = tk.StringVar(value="0.00")
        amt_var = tk.StringVar(value=format_currency(0.00, self.form.curr_fmt))
        in_stock_var = tk.BooleanVar(value=True) 

        # --- THE FIX: Cleanly route column indexes to pack seamlessly! ---
        ent_item = make_entry(35 if has_gst else 40, item_var, "left")
        ent_item.grid(row=row_idx, column=1, padx=2, pady=3, sticky="ew", ipady=2)
        
        c_idx = 2
        ent_hsn, cb_gst, ent_rate_inc = None, None, None
        
        if has_gst:
            ent_hsn = make_entry(10, hsn_var, "center")
            ent_hsn.grid(row=row_idx, column=c_idx, padx=2, pady=3, ipady=2); c_idx += 1
            cb_gst = ttk.Combobox(self.grid_container, textvariable=gst_var, values=["0", "5", "12", "18", "28"], width=6, font=("Segoe UI", 11), justify="center")
            cb_gst.grid(row=row_idx, column=c_idx, padx=2, pady=3, ipady=2); c_idx += 1

        ent_qty = make_entry(8 if has_gst else 10, qty_var, "center")
        ent_qty.grid(row=row_idx, column=c_idx, padx=2, pady=3, ipady=2); c_idx += 1
        
        # --- THE FIX: Added Trip, Rmt, Rft, Sq.ft., and Sq.mtr to the unit array ---
        cb_unit = ttk.Combobox(self.grid_container, textvariable=unit_var, values=["Nos", "Kg", "Ltr", "Pcs", "Mtr", "Box", "Roll", "Set", "Trip", "Rmt", "Rft", "Sq.ft.", "Sq.mtr"], width=8 if has_gst else 10, font=("Segoe UI", 11), justify="center")
        cb_unit.grid(row=row_idx, column=c_idx, padx=2, pady=3, ipady=2); c_idx += 1
        # ---------------------------------------------------------------------------

        if has_gst:
            ent_rate_inc = make_entry(12, rate_inc_var, "right")
            ent_rate_inc.grid(row=row_idx, column=c_idx, padx=2, pady=3, ipady=2); c_idx += 1
            
        ent_rate = make_entry(12 if has_gst else 16, rate_var, "right")
        ent_rate.grid(row=row_idx, column=c_idx, padx=2, pady=3, ipady=2); c_idx += 1
        
        ent_amt = tk.Entry(self.grid_container, textvariable=amt_var, justify="right", font=("Segoe UI", 11, "bold"), bg=self.form.CARD_BG, fg=self.form.TEXT_PRIMARY, width=12 if has_gst else 16, state="readonly", readonlybackground=self.form.CARD_BG, highlightthickness=0, bd=0)
        ent_amt.grid(row=row_idx, column=c_idx, padx=2, pady=3, ipady=2); c_idx += 1
        
        def on_item_type(e):
            if e.keysym in ('Up', 'Down', 'Return', 'Escape'): return
            val = item_var.get().lower()
            self.item_lb.delete(0, tk.END)
            if not val:
                self.item_lb.place_forget()
                return

            matches = [k for k in self.historical_items.keys() if val in k.lower()]
            if matches:
                for m in matches: self.item_lb.insert(tk.END, m)
                x = ent_item.winfo_rootx() - self.form.pop.winfo_rootx()
                y = ent_item.winfo_rooty() - self.form.pop.winfo_rooty() + ent_item.winfo_height()
                self.item_lb.place(x=x, y=y, width=ent_item.winfo_width(), height=min(150, len(matches)*25))
                self.item_lb.lift()
                self.active_row_vars = (item_var, hsn_var, gst_var, ent_qty, ent_hsn)
            else:
                self.item_lb.place_forget()

        def hide_item_lb(*args):
            self.form.pop.after(150, lambda: self.item_lb.place_forget())

        def move_up(e):
            if self.item_lb.winfo_ismapped():
                sel = self.item_lb.curselection()
                if not sel: self.item_lb.selection_set(0)
                elif sel[0] > 0:
                    self.item_lb.selection_clear(sel[0])
                    self.item_lb.selection_set(sel[0]-1)
                    self.item_lb.see(sel[0]-1)
                return "break"

        def move_down(e):
            if self.item_lb.winfo_ismapped():
                sel = self.item_lb.curselection()
                if not sel: self.item_lb.selection_set(0)
                elif sel[0] < self.item_lb.size()-1:
                    self.item_lb.selection_clear(sel[0])
                    self.item_lb.selection_set(sel[0]+1)
                    self.item_lb.see(sel[0]+1)
                return "break"

        def item_return(e):
            if self.item_lb.winfo_ismapped() and self.item_lb.curselection():
                return self.global_lb_select(e)
            else:
                self.item_lb.place_forget()
                if has_gst: ent_hsn.focus_set()
                else: ent_qty.focus_set() # Skip directly to Quantity!
                return "break"

        ent_item.bind("<KeyRelease>", on_item_type)
        ent_item.bind("<FocusOut>", hide_item_lb)
        ent_item.bind("<Up>", move_up)
        ent_item.bind("<Down>", move_down)
        ent_item.bind("<Return>", item_return)

        if has_gst:
            ent_hsn.bind("<Return>", lambda e: [cb_gst.focus_set(), "break"])
            cb_gst.bind("<Return>", lambda e: [ent_qty.focus_set(), "break"])
            cb_unit.bind("<Return>", lambda e: [ent_rate_inc.focus_set(), "break"])
            ent_rate_inc.bind("<Return>", lambda e: [ent_rate.focus_set(), "break"])
        else:
            cb_unit.bind("<Return>", lambda e: [ent_rate.focus_set(), "break"]) # Skip directly to Rate!
            
        ent_qty.bind("<Return>", lambda e: [cb_unit.focus_set(), "break"])
        ent_rate.bind("<Return>", lambda e: [self.add_row(focus_new=True), "break"])

        def forward_scroll(e):
            self.form.master_canvas.yview_scroll(int(-1*(e.delta/120)), "units")
            return "break"
            
        if has_gst: cb_gst.bind("<MouseWheel>", forward_scroll)
        cb_unit.bind("<MouseWheel>", forward_scroll)

        widgets_list = [sl_lbl, ent_item]
        if has_gst: widgets_list.extend([ent_hsn, cb_gst])
        widgets_list.extend([ent_qty, cb_unit])
        if has_gst: widgets_list.append(ent_rate_inc)
        widgets_list.extend([ent_rate, ent_amt])

        btn_del = tk.Button(self.grid_container, text="❌", font=("Segoe UI", 10), fg=self.form.ERROR_COLOR, bg=self.form.CARD_BG, relief="flat", cursor="hand2", width=4, command=lambda: self.delete_row(widgets_list))
        btn_del.grid(row=row_idx, column=c_idx, padx=2, pady=3)
        widgets_list.append(btn_del)

        # --- THE FIX: Force the cursor to the end of the number when focusing! ---
        def move_cursor_to_end_purch(e):
            e.widget.after(10, lambda: e.widget.icursor(tk.END))
            
        ent_qty.bind("<FocusIn>", move_cursor_to_end_purch, add="+")
        ent_rate.bind("<FocusIn>", move_cursor_to_end_purch, add="+")
        if has_gst:
            ent_hsn.bind("<FocusIn>", move_cursor_to_end_purch, add="+")
            ent_rate_inc.bind("<FocusIn>", move_cursor_to_end_purch, add="+")
        # -------------------------------------------------------------------------

        row_dict = {
            "widgets": widgets_list, "sl_lbl": sl_lbl, "item": item_var, "hsn": hsn_var, "gst": gst_var,
            "qty": qty_var, "unit": unit_var, "rate_inc": rate_inc_var, "rate": rate_var,
            "amt": amt_var, "in_stock": in_stock_var, "raw_amt": 0.0
        }
        self.rows_data.append(row_dict)

        def on_focus_in(e, var, default="0.00"):
            if var.get() == default: var.set("")
            
        def on_focus_out(e, var, default="0.00"):
            if var.get().strip() == "": var.set(default)

        if has_gst:
            cb_gst.bind("<FocusIn>", lambda e: on_focus_in(e, gst_var, "0"))
            cb_gst.bind("<FocusOut>", lambda e: on_focus_out(e, gst_var, "0"))
            ent_rate_inc.bind("<FocusIn>", lambda e: on_focus_in(e, rate_inc_var))
            ent_rate_inc.bind("<FocusOut>", lambda e: on_focus_out(e, rate_inc_var))

        ent_rate.bind("<FocusIn>", lambda e: on_focus_in(e, rate_var))
        ent_rate.bind("<FocusOut>", lambda e: on_focus_out(e, rate_var))

        def live_format(var, ent):
            val = var.get().replace(",", "")
            if not val or val == "." or val == "-": return
            parts = val.split(".")
            int_part = parts[0]
            try:
                if len(int_part) > 1 and int_part.startswith("0"):
                    int_part = str(int(int_part))
                if "Indian" in getattr(self.form, "curr_fmt", "Indian"):
                    if len(int_part) > 3:
                        import re
                        int_part = re.sub(r"(\d)(?=(\d{2})+(?!\d))", r"\1,", int_part[:-3]) + "," + int_part[-3:]
                else:
                    int_part = f"{int(int_part):,}"
                
                final = int_part
                if len(parts) > 1: final += "." + parts[1]
                if var.get() != final:
                    var.set(final)
                    ent.icursor("end")
            except: pass

        def calc_from_inc(*args):
            try:
                r_inc = float(rate_inc_var.get().replace(",", "") or 0); g = float(gst_var.get() or 0)
                r_base = r_inc / (1 + (g / 100))
                rate_var.set(self.format_num_string(r_base))
                self.update_row_amount(row_dict)
            except: pass

        def calc_from_base(*args):
            try:
                r_base = float(rate_var.get().replace(",", "") or 0); g = float(gst_var.get() or 0)
                r_inc = r_base * (1 + (g / 100))
                rate_inc_var.set(self.format_num_string(r_inc))
                self.update_row_amount(row_dict)
            except: pass

        ent_qty.bind("<FocusOut>", lambda e: [on_focus_out(e, qty_var, "1"), self.update_row_amount(row_dict)])
        ent_qty.bind("<KeyRelease>", lambda e: self.update_row_amount(row_dict))

        if has_gst:
            ent_hsn.bind("<KeyRelease>", lambda e: self.update_totals())
            ent_rate_inc.bind("<KeyRelease>", lambda e: [live_format(rate_inc_var, ent_rate_inc), calc_from_inc()])
            cb_gst.bind("<<ComboboxSelected>>", calc_from_base)
            cb_gst.bind("<KeyRelease>", calc_from_base)
            ent_rate.bind("<KeyRelease>", lambda e: [live_format(rate_var, ent_rate), calc_from_base()])
        else:
            # If no GST, base rate simply updates row amounts without reverse math!
            ent_rate.bind("<KeyRelease>", lambda e: [live_format(rate_var, ent_rate), self.update_row_amount(row_dict)])
            
        self.update_totals()
        
        if focus_new:
            def _jump_and_scroll():
                self.form.master_canvas.update_idletasks() 
                self.form.master_canvas.yview_moveto(1.0)  
                ent_item.focus_set()                       
            self.parent.after(20, _jump_and_scroll)

    def calculate_row(self, r):
        self.update_row_amount(r)

    def update_row_amount(self, r):
        try:
            q = float(r["qty"].get().replace(",", "") or 0)
            base = float(r["rate"].get().replace(",", "") or 0)
            amt = q * base
            
            r["amt"].set(format_currency(amt, self.form.curr_fmt))
            r["raw_amt"] = amt 
            
            self.update_totals()
        except: pass

    def delete_row(self, widgets_list):
        if len(self.rows_data) <= 1: return
        for i, r in enumerate(self.rows_data):
            if r["widgets"] == widgets_list:
                for w in widgets_list: w.destroy()
                self.rows_data.pop(i)
                break
        self.reindex_rows()
        self.update_totals()

    def reindex_rows(self):
        for i, r in enumerate(self.rows_data): r["sl_lbl"].config(text=str(i + 1))

    def check_interstate(self):
        self.update_totals()

    def update_totals(self):
        sub = 0.0; c_tax = 0.0; s_tax = 0.0; i_tax = 0.0
        is_interstate = False 
        
        # --- THE FIX: Use the cached state code instead of querying the DB on every keystroke! ---
        try:
            v_code = str(self.vendor_state_code).strip()
            if v_code and v_code != "N/A" and self.comp_state_code and self.comp_state_code != "N/A":
                if v_code != self.comp_state_code:
                    is_interstate = True
        except: pass
        # ---------------------------------------------------------------------------------------

        hsn_summary = {}

        for r in self.rows_data:
            try:
                amt = r.get("raw_amt", 0.0) 
                g_pct = float(r["gst"].get() or 0)
                hsn = r["hsn"].get().strip()
                sub += amt
                tax = amt * (g_pct / 100)
                
                if is_interstate: i_tax += tax
                else: c_tax += tax / 2; s_tax += tax / 2
                
                if amt > 0:
                    key = (hsn, g_pct)
                    hsn_summary[key] = hsn_summary.get(key, 0.0) + amt
            except: pass

        tot = sub + c_tax + s_tax + i_tax
        
        self.form.subtotal_var.set(f"{sub:.2f}")
        self.form.subtotal_disp.set(format_currency(sub, self.form.curr_fmt))
        
        self.form.cgst_var.set(f"{c_tax:.2f}")
        self.form.cgst_disp.set(format_currency(c_tax, self.form.curr_fmt))
        
        self.form.sgst_var.set(f"{s_tax:.2f}")
        self.form.sgst_disp.set(format_currency(s_tax, self.form.curr_fmt))
        
        self.form.igst_var.set(f"{i_tax:.2f}")
        self.form.igst_disp.set(format_currency(i_tax, self.form.curr_fmt))
        
        self.form.total_var.set(f"{round(tot):.2f}")
        self.form.total_disp.set(format_currency(round(tot), self.form.curr_fmt))
        
        if getattr(self.form, 'hsn_table', None):
            self.form.hsn_table.update_table(hsn_summary, is_interstate)
            
        if hasattr(self.form, 'row_cgst'):
            if is_interstate:
                self.form.row_cgst.pack_forget()
                self.form.row_sgst.pack_forget()
                self.form.row_igst.pack(fill="x", pady=3, before=self.form.grand_line)
            else:
                self.form.row_igst.pack_forget()
                self.form.row_cgst.pack(fill="x", pady=3, before=self.form.grand_line)
                self.form.row_sgst.pack(fill="x", pady=3, before=self.form.grand_line)