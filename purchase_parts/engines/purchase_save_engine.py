import tkinter as tk
from tkinter import ttk, messagebox
import json
import os
import time
import database
import shutil
from views.invoice_parts.helpers import format_currency

class PurchaseSaveEngine:
    def __init__(self, form_ctx):
        self.form = form_ctx

    def initiate_save(self, is_draft=False):
        if not self.form.check_internal_voucher() or not self.form.check_supplier_bill():
            messagebox.showerror("Validation Error", "Please fix duplicate Voucher or Bill numbers before saving.", parent=self.form.pop)
            return

        v = self.form.vendor_var.get().strip()
        b = self.form.bill_var.get().strip()
        
        # --- THE FIX: Drafts no longer require a Supplier Bill Number to be saved! ---
        if not is_draft and (not v or not b):
            messagebox.showerror("Error", "Vendor and Supplier Bill Number are mandatory.", parent=self.form.pop)
            return
        elif is_draft and not v:
            messagebox.showerror("Error", "Vendor is mandatory even for drafts.", parent=self.form.pop)
            return
        if not self.form.grid_engine.rows_data:
            messagebox.showerror("Error", "Add at least one line item.", parent=self.form.pop)
            return

        self.form.btn_post.config(state="disabled")
        self.form.btn_draft.config(state="disabled")
                
        self.execute_save(is_draft)

    def execute_save(self, is_draft):
        from views.purchase_parts.engines.purchase_forms import ROOT_DIR
        
        v = self.form.vendor_var.get().strip()
        
        # --- THE FIX: Fetch the vendor ID globally so it's available for ALL database transactions! ---
        vend_id = getattr(self.form, "target_vend_id", None)
        
        if not vend_id:
            conn_v = database.get_connection()
            c_v = conn_v.cursor()
            v_gst = self.form.lbl_v_gst.cget("text") if hasattr(self.form, "lbl_v_gst") else "N/A"
            if v_gst and v_gst != "N/A":
                c_v.execute("SELECT id FROM customers WHERE name=? AND gstin=? AND company_id=?", (v, v_gst, self.form.comp_id))
            else:
                c_v.execute("SELECT id FROM customers WHERE name=? AND company_id=?", (v, self.form.comp_id))
            vend_row = c_v.fetchone()
            vend_id = vend_row[0] if vend_row else None
            conn_v.close()
        # --------------------------------------------------------------------------------------------
        
        b = self.form.bill_var.get().strip()
        final_receipt = ""
        r_path = self.form.receipt_var.get()
        
        # --- THE FIX: Check if we are editing and the receipt path hasn't changed to prevent duplication ---
        old_receipt_path = ""
        if self.form.purchase_id:
            conn_chk = database.get_connection()
            c_chk = conn_chk.cursor()
            c_chk.execute("SELECT receipt_path FROM purchases WHERE id=? AND company_id=?", (self.form.purchase_id, self.form.comp_id))
            old_row = c_chk.fetchone()
            if old_row:
                old_receipt_path = old_row[0] or ""
            conn_chk.close()

        if r_path and r_path == old_receipt_path:
            final_receipt = old_receipt_path
        elif r_path and os.path.exists(r_path):
            import re
            conn = database.get_connection()
            c = conn.cursor()
            c.execute("SELECT name FROM company WHERE id=?", (self.form.comp_id,))
            comp_row = c.fetchone()
            conn.close()
            
            comp_name = comp_row[0] if comp_row else f"Company_{self.form.comp_id}"
            
            # Sanitize and build unique ID folder to prevent the "Two Rajas" collision for vendor bills!
            safe_comp = re.sub(r'[\\/*?:"<>|]', "", comp_name).strip()
            safe_cust_name = re.sub(r'[\\/*?:"<>|]', "", v).strip()
            safe_cust = f"{safe_cust_name}_ID_{vend_id}"
            
            # --- THE FIX: Extract Year and Month (in words) from the bill date for structured filing ---
            from datetime import datetime
            bill_date_str = self.form.date_var.get().strip()
            try:
                dt = datetime.strptime(bill_date_str, self.form.date_fmt_code)
                year_folder = dt.strftime("%Y")
                month_folder = dt.strftime("%B") # Stores as "January", "February", etc.
            except:
                dt = datetime.now()
                year_folder = dt.strftime("%Y")
                month_folder = dt.strftime("%B")
                
            safe_dir = os.path.join(ROOT_DIR, "vendor_bills", safe_comp, safe_cust, year_folder, month_folder)
            os.makedirs(safe_dir, exist_ok=True)
            # -------------------------------------------------------------------------------------------
            
            ext = os.path.splitext(r_path)[1] or ".png"
            safe_bill = re.sub(r'[\\/*?:"<>|]', "_", b).strip() if b else "draft"
            final_receipt = os.path.join(safe_dir, f"purchase_{safe_bill}_{int(time.time()*1000)}{ext}")
            try: shutil.copy2(r_path, final_receipt)
            except: final_receipt = r_path
        
        tot = float(self.form.total_var.get())
        subtotal = float(self.form.subtotal_var.get())
        cgst = float(self.form.cgst_var.get())
        sgst = float(self.form.sgst_var.get())
        igst = float(self.form.igst_var.get())

        conn = database.get_connection()
        c = conn.cursor()
        
        try:
            c.execute('PRAGMA foreign_keys = ON')
            
            old_amount_paid = 0.0
            if self.form.purchase_id:
                # --- THE FIX: Added company_id lock ---
                c.execute("SELECT amount_paid FROM purchases WHERE id=? AND company_id=?", (self.form.purchase_id, self.form.comp_id))
                row = c.fetchone()
                if row: old_amount_paid = float(row[0] or 0.0)

            if is_draft:
                amt_paid = 0.0
                bal_due = tot
                stat = "Unpaid"
            else:
                if old_amount_paid > 0:
                    if tot <= old_amount_paid:
                        amt_paid = tot
                        bal_due = 0.0
                        stat = "Paid"
                        overpayment = old_amount_paid - tot
                        
                        if overpayment > 0:
                            note = f"Bill #{b} edited. Excess {format_currency(overpayment, self.form.curr_fmt)} moved to Advance."
                            # --- THE FIX: Labeling the audit trail and securely injecting party_id ---
                            c.execute("INSERT INTO party_payments (company_id, party_name, party_id, pay_type, pay_date, amount, mode, ref, notes) VALUES (?, ?, ?, 'make', ?, ?, 'Adjustment', 'Advance Wallet', ?)", 
                                      (self.form.comp_id, v, vend_id, self.form.date_var.get(), -overpayment, note))
                            
                            c.execute("SELECT id, address FROM customers WHERE id=? AND company_id=?", (vend_id, self.form.comp_id))
                            c_row = c.fetchone()
                            if c_row:
                                c_id, raw_addr = c_row[0], c_row[1]
                                try: j_data = json.loads(raw_addr)
                                except: j_data = {"address": raw_addr if raw_addr else "", "advance_out": 0.0}
                                # --- THE FIX: Sync explicitly to the new supplier 'advance_out' wallet! ---
                                curr_adv = float(j_data.get("advance_out", j_data.get("advance_wallet", 0.0)))
                                j_data["advance_out"] = curr_adv + overpayment
                                c.execute("UPDATE customers SET address=? WHERE id=?", (json.dumps(j_data), c_id))
                            else:
                                j_data = {"address": "", "advance_out": overpayment}
                                c.execute("INSERT INTO customers (company_id, name, address) VALUES (?, ?, ?)", (self.form.comp_id, v, json.dumps(j_data)))
                    else:
                        amt_paid = old_amount_paid
                        bal_due = tot - amt_paid
                        stat = "Partial"
                else:
                    amt_paid = 0.0
                    bal_due = tot
                    stat = "Unpaid"

            int_v = self.form.internal_voucher_var.get().strip()
            if not is_draft:
                if self.form.purchase_id:
                    c.execute("DELETE FROM purchases WHERE LOWER(vendor_name)=LOWER(?) AND LOWER(bill_number)=LOWER(?) AND is_deleted=1 AND company_id=? AND id!=?", (v, b, self.form.comp_id, self.form.purchase_id))
                    if int_v:
                        c.execute("DELETE FROM purchases WHERE LOWER(internal_voucher)=LOWER(?) AND is_deleted=1 AND company_id=? AND id!=?", (int_v, self.form.comp_id, self.form.purchase_id))
                else:
                    c.execute("DELETE FROM purchases WHERE LOWER(vendor_name)=LOWER(?) AND LOWER(bill_number)=LOWER(?) AND is_deleted=1 AND company_id=?", (v, b, self.form.comp_id))
                    if int_v:
                        c.execute("DELETE FROM purchases WHERE LOWER(internal_voucher)=LOWER(?) AND is_deleted=1 AND company_id=?", (int_v, self.form.comp_id))
            
            was_draft = False
            int_d = self.form.internal_date_var.get().strip()
            eway_val = self.form.eway_var.get().strip()
            
            old_snapshot = None

            if self.form.purchase_id:
                c.execute("SELECT is_draft, bill_number, vendor_name, total, internal_voucher FROM purchases WHERE id=? AND company_id=?", (self.form.purchase_id, self.form.comp_id))
                old_row = c.fetchone()
                was_draft = (old_row[0] == 1) if old_row else False
                old_snapshot = old_row
                
                # --- THE FIX: Update the existing purchase row in-place so it never leaks into the Recycle Bin! ---
                p_id = int(self.form.purchase_id)
                c.execute(
                    "UPDATE purchases SET purchase_date=?, bill_number=?, vendor_name=?, vendor_id=?, "
                    "subtotal=?, cgst=?, sgst=?, igst=?, total=?, amount_paid=?, balance_due=?, status=?, "
                    "receipt_path=?, is_deleted=0, internal_voucher=?, internal_date=?, eway_bill=?, is_draft=? "
                    "WHERE id=? AND company_id=?",
                    (self.form.date_var.get(), b, v, vend_id, subtotal, cgst, sgst, igst, tot,
                     amt_paid, bal_due, stat, final_receipt, int_v, int_d, eway_val, 1 if is_draft else 0, p_id, self.form.comp_id)
                )
                c.execute("DELETE FROM purchase_items WHERE purchase_id=?", (p_id,))
                c.execute("DELETE FROM general_expenses WHERE notes LIKE ? AND company_id=?", (f'%\"source_id\": {p_id}%', self.form.comp_id))
                # --------------------------------------------------------------------------------------------------
            else:
                # --- THE FIX: Inject vendor_id, internal_date, and eway_bill securely into Purchases ---
                c.execute("INSERT INTO purchases (company_id, purchase_date, bill_number, vendor_name, vendor_id, subtotal, cgst, sgst, igst, total, amount_paid, balance_due, status, receipt_path, is_deleted, internal_voucher, internal_date, eway_bill, is_draft) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?)", 
                          (self.form.comp_id, self.form.date_var.get(), b, v, vend_id, subtotal, cgst, sgst, igst, tot, amt_paid, bal_due, stat, final_receipt, int_v, int_d, eway_val, 1 if is_draft else 0))
                # ---------------------------------------------------------------------------------------
                p_id = c.lastrowid
            
            for r in self.form.grid_engine.rows_data:
                item = r["item"].get().strip()
                if not item and not is_draft:
                    continue
                hsn = r["hsn"].get()
                unit = r["unit"].get()
                
                try: gst = float(str(r["gst"].get()).replace(",",""))
                except: gst = 0
                try: r_inc = float(str(r["rate_inc"].get()).replace(",",""))
                except: r_inc = 0
                try: qty = float(str(r["qty"].get()).replace(",",""))
                except: qty = 0
                try: rate = float(str(r["rate"].get()).replace(",",""))
                except: rate = 0
                
                amt = r.get("raw_amt", qty * rate)
                dest = "Expense"
                
                c.execute("INSERT INTO purchase_items (purchase_id, item_name, hsn, rate, quantity, amount, destination, unit, gst_rate, rate_inc_tax) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", 
                          (p_id, item, hsn, rate, qty, amt, dest, unit, gst, r_inc))
            
            # --- THE FIX: Option A (Cash Basis) ---
            # We no longer inject the overall Bill Total into General Expenses. 
            # The General Expenses tab will now strictly mirror actual outgoing cash payments!
            # --------------------------------------
            
            conn.commit()
            
            # --- THE FIX: Wire up the Audit Log Camera! ---
            if self.form.purchase_id and not was_draft:
                diffs = []
                if old_snapshot:
                    obill, ovend, otot, oint = old_snapshot[1], old_snapshot[2], old_snapshot[3], old_snapshot[4]
                    if obill != b: diffs.append(f"Bill No: '{obill}' ➔ '{b}'")
                    if ovend != v: diffs.append(f"Vendor: '{ovend}' ➔ '{v}'")
                    if abs((float(otot) if otot else 0.0) - tot) > 0.01: diffs.append(f"Total: @@CURR:{otot}@@ ➔ @@CURR:{tot}@@")
                    if oint != int_v: diffs.append(f"Internal No: '{oint}' ➔ '{int_v}'")
                
                diff_str = " | ".join(diffs) if diffs else "Line items or dates updated"
                database.log_audit("Purchases", "Edited", record_ref=b, details=diff_str, amount=tot, company_id=self.form.comp_id)
            else:
                act_lbl = "Draft Saved" if is_draft else ("Cloned" if getattr(self.form, "clone_id", None) else "Created")
                det = f"Vendor: {v} • Internal No: {int_v}"
                if final_receipt: det += " • Receipt Attached"
                database.log_audit("Purchases", act_lbl, record_ref=b or "DRAFT", details=det, amount=tot, company_id=self.form.comp_id)
            # ----------------------------------------------
            
            if self.form.undo_cb and not is_draft and (not self.form.purchase_id or was_draft): 
                self.form.undo_cb("ADD_PURCHASE", p_id)
            self.form.refresh_cb()
            self.form.pop.destroy()
        except Exception as e:
            messagebox.showerror("Database Error", str(e), parent=self.form.pop)
            self.form.btn_post.config(state="normal")
            self.form.btn_draft.config(state="normal")
        finally:
            conn.close()