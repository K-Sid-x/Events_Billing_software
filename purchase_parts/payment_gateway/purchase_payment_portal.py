import tkinter as tk
from tkinter import ttk, messagebox
import json
import os
import sys
import tempfile
import webbrowser
import re

# --- THE FIX: Bulletproof Executable Pathing for Attachments ---
if getattr(sys, 'frozen', False):
    ROOT_DIR = os.path.dirname(sys.executable)
else:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parts_dir = os.path.dirname(current_dir)
    views_dir = os.path.dirname(parts_dir)
    ROOT_DIR = os.path.dirname(views_dir)

if ROOT_DIR not in sys.path: 
    sys.path.insert(0, ROOT_DIR)
# ---------------------------------------------------------------

import database
from views.invoice_parts.helpers import format_currency, fetch_global_settings, smart_date_formatter
from views.purchase_parts.payment_gateway.purchase_portal_popups import open_partial_payment_dialog, open_auto_payment_dialog, get_wallet_balance, open_manage_advance_dialog

try:
    from views.purchase_parts.print_studio.purchase_preview_window import open_purchase_preview
except ImportError:
    pass

# --- THE FIX: Pass the exact vendor_id into the Portal ---
def open_purchase_payment_portal(view, p_id):
    try:
        conn = database.get_connection()
        c = conn.cursor()
        c.execute("SELECT vendor_name, vendor_id FROM purchases WHERE id=? AND company_id=?", (p_id, view.comp_id))
        row = c.fetchone()
        conn.close()
        if row:
            PurchasePaymentPortal(view, row[0], row[1])
    except Exception as e:
        print("Portal Error:", e)

class PurchasePaymentPortal:
    def __init__(self, parent_view, vendor_name, vend_id=None):
        self.parent_view = parent_view
        self.vendor_name = vendor_name
        self.vend_id = int(vend_id) if (vend_id is not None and str(vend_id).isdigit()) else None
# ---------------------------------------------------------
        self.comp_id = parent_view.comp_id
        self.curr_fmt, self.date_fmt = fetch_global_settings(self.comp_id)
        self.colors = parent_view.colors
        
        self.is_dark = database.get_ui_setting("dark_mode", "1") == "1"
        
        try:
            conn = database.get_connection()
            conn.cursor().execute("ALTER TABLE purchases ADD COLUMN write_off REAL DEFAULT 0.0")
            conn.commit()
            conn.close()
        except: pass
        
        self.pop = tk.Toplevel(parent_view)
        self.pop.title(f"Payment Gateway: {vendor_name}")
        self.pop.geometry("1100x650")
        self.pop.configure(bg=self.colors["bg"])
        self.pop.grab_set()

        self.pop.update_idletasks()
        x = parent_view.winfo_rootx() + (parent_view.winfo_width()//2) - (1100//2)
        y = parent_view.winfo_rooty() + (parent_view.winfo_height()//2) - (650//2)
        
        screen_h = parent_view.winfo_screenheight()
        if y + 650 > screen_h - 130:
            y = screen_h - 650 - 130
            
        self.pop.geometry(f"+{max(0, x)}+{max(0, y)}")
        
        # Memory Stacks for Undo/Redo
        self.undo_stack = []
        self.redo_stack = []
        
        self.build_ui()
        self.load_data()

    def apply_smooth_scroll(self, widget):
        def _on_shift_mouse(event):
            widget.xview_scroll(int(-1 * (event.delta / 120)), "units")
        widget.bind("<Shift-MouseWheel>", _on_shift_mouse)

    def build_ui(self):
        style = ttk.Style(self.pop)
        style.configure("Portal.Treeview.Heading", font=("Segoe UI", 10, "bold"), background=self.colors["header"], foreground=self.colors["text"], borderwidth=1, bordercolor=self.colors["border"])
        style.configure("Portal.Treeview", font=("Segoe UI", 11, "bold"), rowheight=38, background=self.colors["card"], fieldbackground=self.colors["card"], foreground=self.colors["text"], borderwidth=0)
        style.map("Portal.Treeview", background=[("selected", self.colors["border"])], foreground=[("selected", self.colors["text"])])

        main_frame = tk.Frame(self.pop, bg=self.colors["bg"], padx=30, pady=20)
        main_frame.pack(fill="both", expand=True)

        header_container = tk.Frame(main_frame, bg=self.colors["bg"])
        header_container.pack(fill="x", pady=(0, 15))
        
        tk.Label(header_container, text=f"Billing Ledger: {self.vendor_name}", font=("Segoe UI", 20, "bold"), bg=self.colors["bg"], fg=self.colors["text"]).pack(anchor="w")
        
        try:
            conn = database.get_connection()
            c = conn.cursor()
            if self.vend_id:
                c.execute("SELECT alias FROM customers WHERE id=? AND company_id=?", (self.vend_id, self.comp_id))
            else:
                c.execute("SELECT alias FROM customers WHERE name=? AND company_id=?", (self.vendor_name, self.comp_id))
            row = c.fetchone()
            conn.close()
            if row and row[0] and str(row[0]).strip():
                tk.Label(header_container, text=f"({str(row[0]).strip()})", font=("Segoe UI", 12, "italic"), bg=self.colors["bg"], fg=self.colors["text_sec"]).pack(anchor="w", pady=(0, 5))
        except: pass

        metrics_f = tk.Frame(main_frame, bg=self.colors["card"], highlightbackground=self.colors["border"], highlightthickness=1, pady=15)
        metrics_f.pack(fill="x", pady=(0, 20))
        
        metrics_f.columnconfigure(0, weight=1)
        metrics_f.columnconfigure(1, weight=1)
        metrics_f.columnconfigure(2, weight=1)
        metrics_f.columnconfigure(3, weight=1)

        self.lbl_billed = tk.Label(metrics_f, text="Total Billed: 0.00", font=("Segoe UI", 12, "bold"), bg=self.colors["card"], fg=self.colors["text"])
        self.lbl_billed.grid(row=0, column=0)

        self.lbl_paid = tk.Label(metrics_f, text="Total Paid: 0.00", font=("Segoe UI", 12, "bold"), bg=self.colors["card"], fg=self.colors["accent_green"])
        self.lbl_paid.grid(row=0, column=1)

        self.lbl_due = tk.Label(metrics_f, text="Balance Due: 0.00", font=("Segoe UI", 12, "bold"), bg=self.colors["card"], fg=self.colors["error"])
        self.lbl_due.grid(row=0, column=2)
        
        self.lbl_wallet = tk.Label(metrics_f, text="Advance (Out): 0.00", font=("Segoe UI", 12, "bold"), bg=self.colors["card"], fg=self.colors["accent_blue"])
        self.lbl_wallet.grid(row=0, column=3)

        toolbar_f = tk.Frame(main_frame, bg=self.colors["bg"])
        toolbar_f.pack(fill="x", pady=(0, 15))

        tk.Label(toolbar_f, text="Search:", font=("Segoe UI", 10, "bold"), bg=self.colors["bg"], fg=self.colors["text_sec"]).pack(side="left", padx=(0, 5))
        self.search_var = tk.StringVar()
        search_entry = tk.Entry(toolbar_f, textvariable=self.search_var, font=("Segoe UI", 10), width=25, bg=self.colors["bg"], fg=self.colors["text"], insertbackground=self.colors["text"], highlightbackground=self.colors["border"], highlightthickness=1)
        search_entry.pack(side="left", ipady=3)
        self.search_var.trace_add("write", lambda *args: self.load_data())

        btn_hist = tk.Button(toolbar_f, text="📜 View Payment History", font=("Segoe UI", 10, "bold"), bg=self.colors["card"], fg=self.colors["text"], cursor="hand2", relief="solid", bd=1, highlightbackground=self.colors["border"], padx=15, pady=4)
        btn_hist.config(command=self.open_payment_history)
        btn_hist.pack(side="left", padx=(20, 10))

        btn_auto = tk.Button(toolbar_f, text="Apply Auto-Payment", font=("Segoe UI", 10, "bold"), bg=self.colors["accent_green"], fg="#ffffff", cursor="hand2", relief="flat", padx=15, pady=5)
        btn_auto.config(command=lambda: open_auto_payment_dialog(self, self.pop, self.vendor_name, self.load_data, self.push_undo))
        btn_auto.pack(side="left")

        btn_adv = tk.Button(toolbar_f, text="Manage Advance", font=("Segoe UI", 10, "bold"), bg=self.colors["accent_blue"], fg="#ffffff", cursor="hand2", relief="flat", padx=15, pady=5)
        btn_adv.config(command=lambda: open_manage_advance_dialog(self, self.pop, self.vendor_name, self.load_data, self.push_undo))
        btn_adv.pack(side="left", padx=(10, 0))

        # Memory Undo/Redo Engine
        btn_group = tk.Frame(toolbar_f, bg=self.colors["card"], highlightbackground=self.colors["border"], highlightthickness=1)
        btn_group.pack(side="right", padx=(10, 0))

        self.btn_undo = tk.Button(btn_group, text="↺ Undo", font=("Segoe UI", 10, "bold"), bg=self.colors["card"], fg=self.colors["text_sec"], relief="flat", padx=10, pady=3, command=self.perform_undo, state="disabled")
        self.btn_undo.pack(side="left")

        tk.Frame(btn_group, width=1, bg=self.colors["border"]).pack(side="left", fill="y")

        self.btn_redo = tk.Button(btn_group, text="↻ Redo", font=("Segoe UI", 10, "bold"), bg=self.colors["card"], fg=self.colors["text_sec"], relief="flat", padx=10, pady=3, command=self.perform_redo, state="disabled")
        self.btn_redo.pack(side="left")

        tk.Label(main_frame, text="Click on a 'Paid' or 'Unpaid' status below to record partial payments or write-offs:", font=("Segoe UI", 10), bg=self.colors["bg"], fg=self.colors["text_sec"]).pack(anchor="w", pady=(0, 5))

        table_f = tk.Frame(main_frame, bg=self.colors["card"], highlightbackground=self.colors["border"], highlightthickness=1)
        table_f.pack(fill="both", expand=True)

        scroll_y = ttk.Scrollbar(table_f, orient="vertical")
        
        self.tree = ttk.Treeview(table_f, columns=("date", "bill", "total", "paid", "due", "woff", "status"), show="headings", yscrollcommand=scroll_y.set, style="Portal.Treeview")
        scroll_y.config(command=self.tree.yview)
        
        scroll_y.pack(side="right", fill="y")
        self.tree.pack(side="left", fill="both", expand=True)

        try:
            conn = database.get_connection()
            c = conn.cursor()
            c.execute("SELECT setting_value FROM ui_settings WHERE setting_key=?", (f"purch_portal_main_cols_{self.comp_id}",))
            res = c.fetchone()
            conn.close()
            w_dict = json.loads(res[0]) if res and res[0] else {}
        except:
            w_dict = {}

        cols = [
            ("date", "DATE", w_dict.get("date", 120), "center", False), 
            ("bill", "BILL NO.", w_dict.get("bill", 120), "w", True), 
            ("total", "TOTAL", w_dict.get("total", 150), "center", False), 
            ("paid", "PAID", w_dict.get("paid", 150), "center", False), 
            ("due", "BALANCE", w_dict.get("due", 150), "center", False), 
            ("woff", "WRITTEN OFF", w_dict.get("woff", 150), "center", False), 
            ("status", "STATUS", w_dict.get("status", 180), "center", False)
        ]
        
        for c, t, w, a, stretch in cols:
            self.tree.heading(c, text=t, anchor=a)
            self.tree.column(c, width=w, anchor=a, stretch=stretch)

        self.tree.tag_configure("stripe_even", background=self.colors["stripe_even"])
        self.tree.tag_configure("stripe_odd", background=self.colors["stripe_odd"])
        self.tree.tag_configure("status_paid", foreground=self.colors["accent_green"])
        self.tree.tag_configure("status_unpaid", foreground="#ffffff" if self.is_dark else "#b91c1c")
        self.tree.tag_configure("status_partial", foreground="#d97706")

        def save_main_widths():
            new_w = {c: self.tree.column(c, "width") for c in self.tree["columns"] if c != "bill"}
            try:
                database.save_ui_setting(f"purch_portal_main_cols_{self.comp_id}", json.dumps(new_w))
            except: pass

        def on_sep_drag(event):
            if self.tree.identify_region(event.x, event.y) == "separator":
                self.pop.after(50, save_main_widths)

        self.tree.bind("<B1-Motion>", on_sep_drag, add="+")
        self.tree.bind("<Motion>", self.on_motion)
        self.tree.bind("<ButtonRelease-1>", lambda e: [self.pop.after(50, save_main_widths), self.on_click(e)])
        self.tree.bind("<Double-1>", self.on_double_click)

    def on_motion(self, event):
        region = self.tree.identify("region", event.x, event.y)
        col = self.tree.identify_column(event.x)
        if region == "cell" and col in ("#2", "#7"): 
            self.tree.config(cursor="hand2")
        else: 
            self.tree.config(cursor="")

    def on_click(self, event):
        region = self.tree.identify("region", event.x, event.y)
        col = self.tree.identify_column(event.x)
        if region == "cell":
            item = self.tree.selection()
            if not item or "empty" in self.tree.item(item[0], "tags"): return
            b_id = item[0]
            
            if col == "#7":
                for r in self.raw_bills:
                    if str(r[0]) == b_id:
                        try:
                            conn = database.get_connection()
                            c = conn.cursor()
                            c.execute("SELECT COALESCE(ca_submitted, 0) FROM purchases WHERE id=? AND company_id=?", (b_id, self.comp_id))
                            locked = c.fetchone()
                            conn.close()
                            if locked and locked[0] == 1:
                                messagebox.showwarning("Locked", "This bill is GST Filed.\n\nFinancial alterations are locked.", parent=self.pop)
                                return
                        except: pass
                        
                        tot = float(r[3] or 0.0)
                        paid = float(r[4] or 0.0)
                        woff = float(r[6] or 0.0)
                        if max(0.0, tot - paid - woff) <= 0.01:
                            messagebox.showinfo("Fully Paid", f"Bill #{r[2]} is already fully paid.", parent=self.pop)
                        else:
                            open_partial_payment_dialog(self, self.pop, r, self.load_data, self.vendor_name, self.push_undo)
                        break

    def on_double_click(self, event):
        region = self.tree.identify("region", event.x, event.y)
        col = self.tree.identify_column(event.x)
        if region == "cell":
            item = self.tree.selection()
            if not item or "empty" in self.tree.item(item[0], "tags"): return
            b_id = item[0]
            
            if col == "#2":
                try: open_purchase_preview(self.parent_view, b_id)
                except NameError: pass

    def load_data(self):
        for child in self.tree.get_children(): self.tree.delete(child)
        search_q = self.search_var.get().lower()
        
        try:
            conn = database.get_connection()
            c = conn.cursor()
            # --- THE FIX: Fetch bills by ID to prevent twin mixing! ---
            if self.vend_id:
                c.execute("SELECT id, purchase_date, bill_number, total, amount_paid, balance_due, write_off, status FROM purchases WHERE vendor_id=? AND company_id=? AND is_deleted=0 AND is_draft=0 ORDER BY purchase_date ASC", (self.vend_id, self.comp_id))
            else:
                c.execute("SELECT id, purchase_date, bill_number, total, amount_paid, balance_due, write_off, status FROM purchases WHERE vendor_name=? AND company_id=? AND is_deleted=0 AND is_draft=0 ORDER BY purchase_date ASC", (self.vendor_name, self.comp_id))
            self.raw_bills = c.fetchall()
            conn.close()
            # ----------------------------------------------------------
            
            tot_billed = 0.0
            tot_paid = 0.0
            tot_due = 0.0
            running_bal = 0.0 
            idx = 0
            
            for r in self.raw_bills:
                b_id, p_date, b_num, tot, paid, due, woff, stat = r
                woff = woff if woff else 0.0
                
                tot_billed += tot
                tot_paid += paid
                tot_due += due
                
                running_bal += due
                
                if search_q and search_q not in b_num.lower() and search_q not in str(tot).lower():
                    continue
                
                bg_tag = "stripe_even" if idx % 2 == 0 else "stripe_odd"
                
                if due <= 0:
                    stat_txt = "Paid"
                    stat_tag = "status_paid"
                elif paid > 0:
                    stat_txt = f"Partial ({format_currency(due, self.curr_fmt)} due)"
                    stat_tag = "status_partial"
                else:
                    stat_txt = "Unpaid"
                    stat_tag = "status_unpaid"
                
                fmt_date = smart_date_formatter(p_date, self.date_fmt)
                
                self.tree.insert("", "end", iid=str(b_id), values=(fmt_date, b_num, format_currency(tot, self.curr_fmt), format_currency(paid, self.curr_fmt), format_currency(running_bal, self.curr_fmt), format_currency(woff, self.curr_fmt), stat_txt), tags=(bg_tag, stat_tag))
                idx += 1
                
            for j in range(idx, 15):
                bg_tag = "stripe_even" if j % 2 == 0 else "stripe_odd"
                self.tree.insert("", "end", values=("", "", "", "", "", "", ""), tags=(bg_tag, "empty"))
                
            self.lbl_billed.config(text=f"Total Billed: {format_currency(tot_billed, self.curr_fmt)}")
            self.lbl_paid.config(text=f"Total Paid: {format_currency(tot_paid, self.curr_fmt)}")
            self.lbl_due.config(text=f"Balance Due: {format_currency(tot_due, self.curr_fmt)}")
            
            # --- THE BULLETPROOF FIX: Auto-Heal the Advance Wallet by vendor_id ---
            conn_w = database.get_connection()
            cw = conn_w.cursor()
            
            # 1. Recalculate the true wallet balance from actual existing payment logs
            if self.vend_id:
                cw.execute("SELECT amount, pay_type, mode, ref FROM party_payments WHERE (party_id=? OR (party_id IS NULL AND party_name=?)) AND company_id=?", (self.vend_id, self.vendor_name, self.comp_id))
            else:
                cw.execute("SELECT amount, pay_type, mode, ref FROM party_payments WHERE party_name=? AND company_id=?", (self.vendor_name, self.comp_id))
            actual_adv = 0.0
            for p_amt, p_type, p_mode, p_ref in cw.fetchall():
                amt_val = abs(float(p_amt or 0.0))
                mode_str = str(p_mode or "")
                ref_str = str(p_ref or "")
                
                if "Wallet Deduction" in mode_str:
                    actual_adv -= amt_val
                elif "Advance Wallet" in ref_str:
                    actual_adv += amt_val if p_type == 'make' else -amt_val
                elif "Refunded" in ref_str:
                    actual_adv -= amt_val
                    
            actual_adv = max(0.0, actual_adv)
            
            # 2. Force sync the customer profile to the true calculated balance (wipes out ghosts!)
            if self.vend_id:
                cw.execute("SELECT id, address FROM customers WHERE id=? AND company_id=?", (self.vend_id, self.comp_id))
            else:
                cw.execute("SELECT id, address FROM customers WHERE name=? AND company_id=?", (self.vendor_name, self.comp_id))
            w_row = cw.fetchone()
            if w_row:
                try: 
                    j_data = json.loads(w_row[1])
                    if float(j_data.get("advance_out", 0.0)) != actual_adv:
                        j_data["advance_out"] = actual_adv
                        cw.execute("UPDATE customers SET address=? WHERE id=?", (json.dumps(j_data), w_row[0]))
                        conn_w.commit()
                except: pass
            conn_w.close()
            
            if actual_adv > 0:
                self.lbl_wallet.config(text=f"Advance (Out): {format_currency(actual_adv, self.curr_fmt)}")
            else:
                self.lbl_wallet.config(text=f"Advance (Out): {format_currency(0, self.curr_fmt)}")
            # ---------------------------------------------------------
                
            if hasattr(self.parent_view, 'load_data'): self.parent_view.load_data()
            
        except Exception as e:
            print("Portal Data Error:", e)

    def push_undo(self, payload):
        self.undo_stack.append(payload)
        self.redo_stack.clear()
        self.update_memory_buttons()

    def update_memory_buttons(self):
        if self.undo_stack: 
            self.btn_undo.config(state="normal", bg=self.colors["accent_blue"], fg="#ffffff", cursor="hand2")
        else: 
            self.btn_undo.config(state="disabled", bg=self.colors["card"], fg=self.colors["text_sec"], cursor="arrow")
            
        if self.redo_stack: 
            self.btn_redo.config(state="normal", bg=self.colors["accent_blue"], fg="#ffffff", cursor="hand2")
        else: 
            self.btn_redo.config(state="disabled", bg=self.colors["card"], fg=self.colors["text_sec"], cursor="arrow")

    def perform_undo(self):
        if not self.undo_stack: return
        payload = self.undo_stack.pop()
        self.redo_stack.append(payload)
        
        try:
            conn = database.get_connection()
            c = conn.cursor()
            
            for inv in payload.get("inv_states", []):
                c.execute("UPDATE purchases SET amount_paid=?, balance_due=?, write_off=?, status=? WHERE id=?", (inv["paid"], inv["bal"], inv["woff"], inv["status"], inv["id"]))
            
            if payload.get("wallet_change"):
                from views.purchase_parts.payment_gateway.purchase_portal_popups import update_wallet_balance
                update_wallet_balance(c, self.comp_id, self.vendor_name, -payload["wallet_change"], self.vend_id)
                
            for pid in payload.get("payment_ids", []):
                c.execute("DELETE FROM party_payments WHERE id=?", (pid,))
                
            conn.commit()
            conn.close()
            database.log_audit("Purchases", "Undo Payment", record_ref=self.vendor_name, details="Reverted a recent payment, advance, or allocation.", company_id=self.comp_id)
            self.load_data()
            self.update_memory_buttons()
        except Exception as e: print("Undo Error:", e)

    def perform_redo(self):
        if not self.redo_stack: return
        payload = self.redo_stack.pop()
        self.undo_stack.append(payload)
        
        try:
            conn = database.get_connection()
            c = conn.cursor()
            
            for inv in payload.get("new_inv_states", []):
                c.execute("UPDATE purchases SET amount_paid=?, balance_due=?, write_off=?, status=? WHERE id=?", (inv["paid"], inv["bal"], inv["woff"], inv["status"], inv["id"]))
            
            if payload.get("wallet_change"):
                from views.purchase_parts.payment_gateway.purchase_portal_popups import update_wallet_balance
                update_wallet_balance(c, self.comp_id, self.vendor_name, payload["wallet_change"], self.vend_id)
                
            for pay_row in payload.get("payment_rows", []):
                # --- THE FIX: Pass all 11 columns including party_id during Redo! ---
                c.execute("INSERT INTO party_payments (id, company_id, party_name, party_id, pay_type, pay_date, amount, mode, ref, notes, attachment_path) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", pay_row)
                # --------------------------------------------------------------------
                
            conn.commit()
            conn.close()
            database.log_audit("Purchases", "Redo Payment", record_ref=self.vendor_name, details="Redid a reverted payment, advance, or allocation.", company_id=self.comp_id)
            self.load_data()
            self.update_memory_buttons()
        except Exception as e: print("Redo Error:", e)

    def open_payment_history(self):
        h_pop = tk.Toplevel(self.pop)
        h_pop.title(f"Payment History: {self.vendor_name}")
        h_pop.geometry("1050x500")
        h_pop.configure(bg=self.colors["bg"])
        h_pop.grab_set()

        header_f = tk.Frame(h_pop, bg=self.colors["bg"])
        header_f.pack(fill="x", padx=20, pady=(15, 10))

        tk.Label(header_f, text=f"Payment Log: {self.vendor_name}", font=("Segoe UI", 14, "bold"), bg=self.colors["bg"], fg=self.colors["text"]).pack(side="left")

        btn_print = tk.Button(header_f, text="⎙ Print Record", font=("Segoe UI", 10, "bold"), bg=self.colors["card"], fg=self.colors["text"], cursor="hand2", relief="solid", bd=1, highlightbackground=self.colors["border"], padx=15, pady=4)
        btn_print.pack(side="right", padx=(10, 0))

        search_var = tk.StringVar()
        search_ent = tk.Entry(header_f, textvariable=search_var, font=("Segoe UI", 10), width=25, bg=self.colors["bg"], fg=self.colors["text"], insertbackground=self.colors["text"], highlightbackground=self.colors["border"], highlightthickness=1)
        search_ent.pack(side="right", ipady=3)
        tk.Label(header_f, text="Search:", font=("Segoe UI", 10, "bold"), bg=self.colors["bg"], fg=self.colors["text_sec"]).pack(side="right", padx=(0, 5))

        table_f = tk.Frame(h_pop, bg=self.colors["card"], highlightbackground=self.colors["border"], highlightthickness=1)
        table_f.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        
        scroll_y = ttk.Scrollbar(table_f, orient="vertical")
        h_tree = ttk.Treeview(table_f, columns=("date", "mode", "ref", "notes", "amount", "action"), show="headings", yscrollcommand=scroll_y.set, style="Portal.Treeview")
        
        scroll_y.config(command=h_tree.yview)
        scroll_y.pack(side="right", fill="y")
        h_tree.pack(side="left", fill="both", expand=True)

        h_tree.heading("date", text="DATE", anchor="center")
        h_tree.heading("mode", text="PAYMENT MODE", anchor="center")
        h_tree.heading("ref", text="APPLIED TO", anchor="w")
        h_tree.heading("notes", text="NOTES", anchor="w")
        h_tree.heading("amount", text="AMOUNT", anchor="e")
        h_tree.heading("action", text="PROOF", anchor="center")
        
        try:
            conn = database.get_connection()
            c = conn.cursor()
            c.execute("SELECT setting_value FROM ui_settings WHERE setting_key=?", (f"purch_portal_hist_cols_{self.comp_id}",))
            res = c.fetchone()
            conn.close()
            h_w_dict = json.loads(res[0]) if res and res[0] else {}
        except:
            h_w_dict = {}

        h_tree.column("date", width=h_w_dict.get("date", 110), anchor="center", stretch=False)
        h_tree.column("mode", width=h_w_dict.get("mode", 140), anchor="center", stretch=False)
        h_tree.column("ref", width=h_w_dict.get("ref", 200), anchor="w", stretch=True)
        h_tree.column("notes", width=h_w_dict.get("notes", 230), anchor="w", stretch=True)
        h_tree.column("amount", width=h_w_dict.get("amount", 130), anchor="e", stretch=False)
        h_tree.column("action", width=h_w_dict.get("action", 120), anchor="center", stretch=False)

        h_tree.tag_configure("stripe_even", background=self.colors["stripe_even"])
        h_tree.tag_configure("stripe_odd", background=self.colors["stripe_odd"])

        def save_hist_widths():
            new_w = {c: h_tree.column(c, "width") for c in h_tree["columns"] if c not in ("ref", "notes")}
            try:
                database.save_ui_setting(f"purch_portal_hist_cols_{self.comp_id}", json.dumps(new_w))
            except: pass

        def on_hist_sep_drag(event):
            if h_tree.identify_region(event.x, event.y) == "separator":
                h_pop.after(50, save_hist_widths)

        h_tree.bind("<B1-Motion>", on_hist_sep_drag, add="+") 

        self.h_tooltip = tk.Toplevel(h_pop)
        self.h_tooltip.wm_overrideredirect(True)
        self.h_tooltip.wm_geometry("+0+0")
        self.h_tooltip.configure(bg="#fef08a", highlightbackground="#ca8a04", highlightthickness=1)
        self.h_tooltip_lbl = tk.Label(self.h_tooltip, text="", font=("Segoe UI", 10), bg="#fef08a", fg="#854d0e", justify="left", wraplength=400)
        self.h_tooltip_lbl.pack(padx=8, pady=4)
        self.h_tooltip.withdraw()

        def on_h_motion(event):
            region = h_tree.identify("region", event.x, event.y)
            if region == "cell":
                col = h_tree.identify_column(event.x)
                if col in ("#3", "#4", "#6"): 
                    h_tree.config(cursor="hand2")
                    if col in ("#3", "#4"):
                        iid = h_tree.identify_row(event.y)
                        if iid:
                            vals = h_tree.item(iid, "values")
                            tags = h_tree.item(iid, "tags")
                            if "empty" not in tags and vals:
                                idx = 2 if col == "#3" else 3
                                text = vals[idx]
                                if text and len(text) > 25: 
                                    self.h_tooltip_lbl.config(text=text)
                                    x = event.x_root + 15
                                    y = event.y_root + 15
                                    self.h_tooltip.wm_geometry(f"+{x}+{y}")
                                    self.h_tooltip.deiconify()
                                    return
                else:
                    h_tree.config(cursor="")
            else:
                h_tree.config(cursor="")
            self.h_tooltip.withdraw()

        def on_h_leave(event):
            self.h_tooltip.withdraw()

        h_tree.bind("<Motion>", on_h_motion)
        h_tree.bind("<Leave>", on_h_leave)

        def format_ref(raw_ref):
            if not raw_ref: return ""
            try:
                def repl(match):
                    try:
                        raw_val = re.sub(r'[^\d\.]', '', match.group(1))
                        if not raw_val: return match.group(0)
                        val = float(raw_val)
                        return f"({format_currency(val, self.curr_fmt)})"
                    except:
                        return match.group(0)
                return re.sub(r'\(([^)]+)\)', repl, str(raw_ref))
            except:
                return str(raw_ref)

        def load_history_data(*args):
            for child in h_tree.get_children(): h_tree.delete(child)
            q = search_var.get().lower()
            try:
                conn = database.get_connection()
                c = conn.cursor()
                try: c.execute("ALTER TABLE party_payments ADD COLUMN attachment_path TEXT")
                except: pass
                
                # --- THE FIX: Fetch BOTH Payments and Refunds isolated by vendor_id! ---
                if self.vend_id:
                    c.execute("SELECT id, pay_date, mode, ref, amount, notes, attachment_path, pay_type FROM party_payments WHERE (party_id=? OR (party_id IS NULL AND party_name=?)) AND company_id=? AND pay_type IN ('make', 'receive') ORDER BY id DESC", (self.vend_id, self.vendor_name, self.comp_id))
                else:
                    c.execute("SELECT id, pay_date, mode, ref, amount, notes, attachment_path, pay_type FROM party_payments WHERE party_name=? AND company_id=? AND pay_type IN ('make', 'receive') ORDER BY id DESC", (self.vendor_name, self.comp_id))
                rows = c.fetchall()
                conn.close()
                
                idx = 0
                for r in rows:
                    log_id = r[0]
                    p_date = smart_date_formatter(r[1], self.date_fmt)
                    mode = r[2]
                    ref = format_ref(r[3])
                    
                    raw_amt = float(r[4] or 0.0)
                    p_type = r[7]
                    
                    # --- THE FIX: Handle visual polarity based on pay_type ---
                    if p_type == 'receive':
                        amt_str = f"+ {format_currency(abs(raw_amt), self.curr_fmt)} (Refund)"
                    elif raw_amt < 0:
                        amt_str = f"- {format_currency(abs(raw_amt), self.curr_fmt)}"
                    else:
                        amt_str = f"+ {format_currency(abs(raw_amt), self.curr_fmt)}"
                        
                    notes = r[5] if r[5] else ""
                    attach_path = r[6] if len(r) > 6 and r[6] else ""
                    
                    if q:
                        search_str = f"{p_date} {mode} {ref} {notes} {amt_str}".lower()
                        if q not in search_str: continue
                        
                    tag = "stripe_even" if idx % 2 == 0 else "stripe_odd"
                    
                    if attach_path and os.path.exists(attach_path):
                        action_txt = "👁 View Proof"
                    elif mode in ("System Reversal", "Write-Off", "Adjustment", "System Adjustment"):
                        action_txt = "—"
                    else:
                        action_txt = "📎 Attach Proof"
                    
                    h_tree.insert("", "end", iid=str(log_id), values=(p_date, mode, ref, notes, amt_str, action_txt), tags=(tag, "paid_out", attach_path or "NONE"))
                    idx += 1
                    
                for j in range(idx, 15):
                    tag = "stripe_even" if j % 2 == 0 else "stripe_odd"
                    h_tree.insert("", "end", values=("", "", "", "", "", ""), tags=(tag, "empty"))
            except Exception as e:
                print("History Error:", e)

        def on_h_click(event):
            region = h_tree.identify("region", event.x, event.y)
            if region == "cell":
                col = h_tree.identify_column(event.x)
                if col == "#6":
                    iid = h_tree.identify_row(event.y)
                    if iid and "empty" not in h_tree.item(iid, "tags"):
                        row_vals = h_tree.item(iid, "values")
                        row_tags = h_tree.item(iid, "tags")
                        action_text = row_vals[5]
                        
                        if action_text == "—": return
                        
                        attach_path = row_tags[2] if len(row_tags) > 2 else "NONE"
                        
                        if "View" in action_text:
                            if attach_path != "NONE" and os.path.exists(attach_path):
                                try: os.startfile(attach_path)
                                except: webbrowser.open(attach_path)
                            else:
                                messagebox.showerror("Error", "File could not be located on this device.", parent=h_pop)
                        else:
                            from tkinter import filedialog
                            import shutil
                            import time
                            
                            path = filedialog.askopenfilename(parent=h_pop, title="Select Payment Proof", filetypes=[("Image Files", "*.png *.jpg *.jpeg"), ("PDF Files", "*.pdf")])
                            if path:
                                import re
                                conn = database.get_connection()
                                c = conn.cursor()
                                c.execute("SELECT name FROM company WHERE id=?", (self.comp_id,))
                                comp_row = c.fetchone()
                                c.execute("SELECT id FROM customers WHERE name=? AND company_id=?", (self.vendor_name, self.comp_id))
                                vend_row = c.fetchone()
                                vend_id = vend_row[0] if vend_row else "0"
                                conn.close()
                                
                                comp_name = comp_row[0] if comp_row else f"Company_{self.comp_id}"
                                safe_comp = re.sub(r'[\\/*?:"<>|]', "", comp_name).strip()
                                safe_cust_name = re.sub(r'[\\/*?:"<>|]', "", self.vendor_name).strip()
                                safe_cust = f"{safe_cust_name}_ID_{vend_id}"
                                
                                safe_dir = os.path.join(ROOT_DIR, "purchase_payment_receipts", safe_comp, safe_cust)
                                os.makedirs(safe_dir, exist_ok=True)
                                
                                ext = os.path.splitext(path)[1] or ".png"
                                ref_str = row_vals[2]
                                if "Advance" in ref_str: prefix = "advance"
                                elif "(" in ref_str and " | " not in ref_str:
                                    bill_no = ref_str.split("(")[0].strip()
                                    prefix = f"payment_{re.sub(r'[\\/*?:\"<>|]', '_', bill_no)}"
                                else: prefix = "bulk_payment"
                                
                                final_attach = os.path.join(safe_dir, f"{prefix}_{int(time.time()*1000)}{ext}")
                                try: shutil.copy2(path, final_attach)
                                except: final_attach = path
                                
                                try:
                                    conn = database.get_connection()
                                    c = conn.cursor()
                                    c.execute("UPDATE party_payments SET attachment_path=? WHERE id=?", (final_attach, iid))
                                    conn.commit()
                                    conn.close()
                                    load_history_data()
                                except Exception as e:
                                    messagebox.showerror("Save Error", str(e), parent=h_pop)
        
        h_tree.bind("<ButtonRelease-1>", lambda e: [h_pop.after(50, save_hist_widths), on_h_click(e)])

        def print_filtered_history():
            html = f"""
            <html><head><title>Payment History - {self.vendor_name}</title>
            <style>
                @page {{ size: landscape; }}
                body {{ font-family: 'Segoe UI', Arial, sans-serif; padding: 20px; }}
                h2 {{ color: #333; }}
                table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; white-space: nowrap; }}
                th {{ background-color: #f2f2f2; }}
                .amt {{ text-align: right; color: #10b981; font-weight: bold; }}
                .center {{ text-align: center; }}
            </style>
            </head><body>
            <h2>Payment History: {self.vendor_name}</h2>
            <table>
                <tr>
                    <th class="center">DATE</th>
                    <th class="center">PAYMENT MODE</th>
                    <th>APPLIED TO</th>
                    <th>NOTES</th>
                    <th class="amt">AMOUNT</th>
                </tr>
            """
            has_data = False
            for child in h_tree.get_children():
                vals = h_tree.item(child, "values")
                tags = h_tree.item(child, "tags")
                if "empty" in tags: continue
                has_data = True
                
                html += f"""
                <tr>
                    <td class="center">{vals[0]}</td>
                    <td class="center">{vals[1]}</td>
                    <td>{vals[2]}</td>
                    <td>{vals[3]}</td>
                    <td class="amt">{vals[4]}</td>
                </tr>
                """
            html += "</table>"
            if not has_data:
                html += "<p>No records found for the current filter.</p>"
            html += "<script>window.onload = function() { window.print(); }</script></body></html>"
            
            fd, path = tempfile.mkstemp(suffix=".html", prefix="Purchase_Payment_Hist_")
            with os.fdopen(fd, 'w', encoding='utf-8') as f: f.write(html)
            webbrowser.open('file://' + os.path.realpath(path))

        btn_print.config(command=print_filtered_history)
        search_var.trace_add("write", load_history_data)
        load_history_data()