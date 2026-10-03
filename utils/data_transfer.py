import json
import os
import sys
from datetime import datetime

# --- THE FIX: Bulletproof Executable Pathing ---
if getattr(sys, 'frozen', False):
    root_dir = os.path.dirname(sys.executable)
else:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(current_dir)

if root_dir not in sys.path:
    sys.path.insert(0, root_dir)
# -----------------------------------------------

import database

def dict_factory(cursor, row):
    """Converts SQLite rows into standard Python dictionaries for JSON export."""
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

def export_company_data(filepath, company_id, selections):
    """Extracts isolated data for a specific company and writes it to a .billx file."""
    conn = database.get_connection()
    conn.row_factory = dict_factory
    c = conn.cursor()

    payload = {"app": "LEDGER.EVENTS", "export_date": str(datetime.now()), "data": {}}

    if selections.get('settings'):
        c.execute("SELECT * FROM company WHERE id=?", (company_id,))
        payload["data"]["company"] = c.fetchone()

    if selections.get('customers'):
        c.execute("SELECT * FROM customers WHERE company_id=?", (company_id,))
        payload["data"]["customers"] = c.fetchall()

    if selections.get('employees'):
        c.execute("SELECT * FROM employees WHERE company_id=?", (company_id,))
        emps = c.fetchall()
        payload["data"]["employees"] = emps
        if emps:
            emp_ids = [str(e['id']) for e in emps]
            c.execute(f"SELECT * FROM employee_payments WHERE emp_id IN ({','.join(emp_ids)})")
            payload["data"]["employee_payments"] = c.fetchall()
            
        # --- THE FIX: Include the entire Labours Module in the Export! ---
        c.execute("SELECT * FROM labours WHERE company_id=?", (company_id,))
        labs = c.fetchall()
        payload["data"]["labours"] = labs
        if labs:
            lab_ids = [str(l['id']) for l in labs]
            c.execute(f"SELECT * FROM labour_attendance WHERE labour_id IN ({','.join(lab_ids)})")
            payload["data"]["labour_attendance"] = c.fetchall()
            c.execute(f"SELECT * FROM labour_ledger WHERE labour_id IN ({','.join(lab_ids)})")
            payload["data"]["labour_ledger"] = c.fetchall()
        # -----------------------------------------------------------------

    if selections.get('inventory'):
        c.execute("SELECT * FROM inventory WHERE company_id=?", (company_id,))
        payload["data"]["inventory"] = c.fetchall()
        c.execute("SELECT * FROM stock WHERE company_id=?", (company_id,))
        payload["data"]["stock"] = c.fetchall()

    if selections.get('invoices'):
        c.execute("SELECT * FROM invoices WHERE company_id=?", (company_id,))
        invs = c.fetchall()
        payload["data"]["invoices"] = invs
        if invs:
            inv_ids = [str(i['id']) for i in invs]
            c.execute(f"SELECT * FROM invoice_items WHERE invoice_id IN ({','.join(inv_ids)})")
            payload["data"]["invoice_items"] = c.fetchall()
            
        # --- THE FIX: Include Purchases, Expenses, and Payments in the Export! ---
        c.execute("SELECT * FROM purchases WHERE company_id=?", (company_id,))
        purchs = c.fetchall()
        payload["data"]["purchases"] = purchs
        if purchs:
            purch_ids = [str(p['id']) for p in purchs]
            c.execute(f"SELECT * FROM purchase_items WHERE purchase_id IN ({','.join(purch_ids)})")
            payload["data"]["purchase_items"] = c.fetchall()
            
        c.execute("SELECT * FROM general_expenses WHERE company_id=?", (company_id,))
        payload["data"]["general_expenses"] = c.fetchall()
        
        c.execute("SELECT * FROM party_payments WHERE company_id=?", (company_id,))
        payload["data"]["party_payments"] = c.fetchall()
        # -------------------------------------------------------------------------

    conn.close()

    os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(payload, f, indent=4)

def scan_backup_file(filepath):
    """Quickly peeks inside the .billx file to see if it contains a full company profile."""
    with open(filepath, 'r', encoding='utf-8') as f:
        payload = json.load(f)
    
    if payload.get("app") != "LEDGER.EVENTS":
        raise ValueError("Invalid Backup File format.")
        
    data = payload.get("data", {})
    return {
        "has_profile": "company" in data and data["company"] is not None,
        "is_valid": True
    }

def import_company_data(filepath, target_company_id=None):
    """
    If target_company_id is None -> Creates a brand new cloned company.
    If target_company_id is provided -> Merges data into the existing company.
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        payload = json.load(f)

    data = payload.get("data", {})
    conn = database.get_connection()
    c = conn.cursor()

    try:
        # --- PATH A: FULL CLONE (Creates a new company entirely) ---
        if target_company_id is None:
            if "company" not in data or not data["company"]:
                raise ValueError("Cannot clone: No company profile found in backup file.")
            
            comp = data["company"]
            new_name = comp.get('name', 'Cloned Company') + " (Imported)"
            
            c.execute('''INSERT INTO company (name, name_secondary, address, phone, phone2, phone3, email, gst_toggle, gstin, logo_path, header_layout, logo_size, logo_shape, template_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (new_name, comp.get('name_secondary'), comp.get('address'), comp.get('phone'), comp.get('phone2'), comp.get('phone3'), comp.get('email'), comp.get('gst_toggle'), comp.get('gstin'), comp.get('logo_path'), comp.get('header_layout'), comp.get('logo_size'), comp.get('logo_shape'), comp.get('template_json')))
            
            target_company_id = c.lastrowid # This is the ID of our newly created clone
            is_clone = True
        else:
            is_clone = False # We are safely merging into an existing company

        cid = target_company_id

        # --- DATA INJECTION (Works for both Clones and Merges) ---
        
        # 1. Customers
        if "customers" in data:
            for cust in data["customers"]:
                if not is_clone:
                    c.execute("SELECT id FROM customers WHERE company_id=? AND phone=? AND name=?", (cid, cust.get('phone'), cust.get('name')))
                    if c.fetchone(): continue # Skip existing in merge mode
                c.execute("INSERT INTO customers (company_id, name, phone, gstin, email, address) VALUES (?, ?, ?, ?, ?, ?)", (cid, cust.get('name'), cust.get('phone'), cust.get('gstin'), cust.get('email'), cust.get('address')))

        # 2. Inventory & Stock
        if "inventory" in data:
            for item in data["inventory"]:
                if not is_clone:
                    c.execute("SELECT id FROM inventory WHERE company_id=? AND item_name=?", (cid, item.get('item_name')))
                    if c.fetchone(): continue
                c.execute("INSERT INTO inventory (company_id, item_name, unit, rate, description) VALUES (?, ?, ?, ?, ?)", (cid, item.get('item_name'), item.get('unit'), item.get('rate'), item.get('description')))
        
        if "stock" in data:
            for st in data["stock"]:
                if not is_clone:
                    c.execute("SELECT id FROM stock WHERE company_id=? AND item_name=? AND quantity=? AND added_date=?", (cid, st.get('item_name'), st.get('quantity'), st.get('added_date')))
                    if c.fetchone(): continue
                c.execute("INSERT INTO stock (company_id, item_name, quantity, unit, market_price, notes, added_date, transaction_type) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (cid, st.get('item_name'), st.get('quantity'), st.get('unit'), st.get('market_price'), st.get('notes'), st.get('added_date'), st.get('transaction_type')))

        # 3. Employees & Payroll (Requires ID Mapping)
        if "employees" in data:
            emp_id_map = {}
            for emp in data["employees"]:
                if not is_clone:
                    c.execute("SELECT id FROM employees WHERE company_id=? AND phone=? AND name=?", (cid, emp.get('phone'), emp.get('name')))
                    existing = c.fetchone()
                    if existing:
                        emp_id_map[emp['id']] = existing[0]
                        continue
                
                c.execute("INSERT INTO employees (company_id, name, phone, alt_phone, role, salary, join_date, photo_path, document_path, dob, docs_json, resign_date, rejoin_date, salary_history) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (cid, emp.get('name'), emp.get('phone'), emp.get('alt_phone'), emp.get('role'), emp.get('salary'), emp.get('join_date'), emp.get('photo_path'), emp.get('document_path'), emp.get('dob'), emp.get('docs_json'), emp.get('resign_date'), emp.get('rejoin_date'), emp.get('salary_history')))
                emp_id_map[emp['id']] = c.lastrowid

            if "employee_payments" in data:
                for pay in data["employee_payments"]:
                    new_emp_id = emp_id_map.get(pay.get('emp_id'))
                    if new_emp_id:
                        if not is_clone:
                            c.execute("SELECT id FROM employee_payments WHERE emp_id=? AND pay_type=? AND amount=? AND pay_date=?", (new_emp_id, pay.get('pay_type'), pay.get('amount'), pay.get('pay_date')))
                            if c.fetchone(): continue
                        c.execute("INSERT INTO employee_payments (emp_id, pay_type, amount, pay_date, notes) VALUES (?, ?, ?, ?, ?)", (new_emp_id, pay.get('pay_type'), pay.get('amount'), pay.get('pay_date'), pay.get('notes')))

        # 4. Invoices & Items (Requires ID Mapping)
        if "invoices" in data:
            for inv in data["invoices"]:
                if not is_clone:
                    c.execute("SELECT id FROM invoices WHERE company_id=? AND invoice_number=?", (cid, inv.get('invoice_number')))
                    if c.fetchone(): continue # Protect existing invoices from being overwritten by accident
                
                # --- THE FIX: Include ALL columns including is_deleted, refund_mode, etc. so history doesn't break! ---
                c.execute("INSERT INTO invoices (company_id, invoice_date, delivery_date, invoice_number, customer_name, place_of_service, subtotal, cgst, sgst, igst, total, amount_paid, balance_due, status, write_off, is_deleted, refund_mode, ca_submitted, ca_submission_date) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", 
                          (cid, inv.get('invoice_date'), inv.get('delivery_date'), inv.get('invoice_number'), inv.get('customer_name'), inv.get('place_of_service'), inv.get('subtotal'), inv.get('cgst'), inv.get('sgst'), inv.get('igst'), inv.get('total'), inv.get('amount_paid'), inv.get('balance_due'), inv.get('status'), inv.get('write_off', 0.0), inv.get('is_deleted', 0), inv.get('refund_mode', 'none'), inv.get('ca_submitted', 0), inv.get('ca_submission_date', '')))
                new_inv_id = c.lastrowid

                if "invoice_items" in data:
                    items = [it for it in data["invoice_items"] if it['invoice_id'] == inv['id']]
                    for it in items:
                        c.execute("INSERT INTO invoice_items (invoice_id, item_name, sac, rate, quantity, days, amount, unit) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", 
                                  (new_inv_id, it.get('item_name'), it.get('sac'), it.get('rate'), it.get('quantity'), it.get('days', 1.0), it.get('amount'), it.get('unit', '')))

        # --- THE FIX: Import Purchases, Expenses, Party Payments, and Labours! ---
        if "purchases" in data:
            for purch in data["purchases"]:
                if not is_clone:
                    c.execute("SELECT id FROM purchases WHERE company_id=? AND bill_number=? AND vendor_name=?", (cid, purch.get('bill_number'), purch.get('vendor_name')))
                    if c.fetchone(): continue
                c.execute("INSERT INTO purchases (company_id, purchase_date, bill_number, vendor_name, subtotal, cgst, sgst, igst, total, amount_paid, balance_due, status, receipt_path, write_off, is_deleted, is_draft, refund_mode, ca_submitted, ca_submission_date) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", 
                          (cid, purch.get('purchase_date'), purch.get('bill_number'), purch.get('vendor_name'), purch.get('subtotal'), purch.get('cgst'), purch.get('sgst'), purch.get('igst'), purch.get('total'), purch.get('amount_paid'), purch.get('balance_due'), purch.get('status'), purch.get('receipt_path'), purch.get('write_off', 0.0), purch.get('is_deleted', 0), purch.get('is_draft', 0), purch.get('refund_mode', 'none'), purch.get('ca_submitted', 0), purch.get('ca_submission_date', '')))
                new_purch_id = c.lastrowid
                if "purchase_items" in data:
                    items = [it for it in data["purchase_items"] if it['purchase_id'] == purch['id']]
                    for it in items:
                        c.execute("INSERT INTO purchase_items (purchase_id, item_name, hsn, rate, quantity, amount, destination, unit, gst_rate, rate_inc_tax) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", 
                                  (new_purch_id, it.get('item_name'), it.get('hsn'), it.get('rate'), it.get('quantity'), it.get('amount'), it.get('destination', ''), it.get('unit', ''), it.get('gst_rate', 0.0), it.get('rate_inc_tax', 0.0)))

        if "general_expenses" in data:
            for exp in data["general_expenses"]:
                # --- THE FIX: Block Duplicate Expenses during Merge! ---
                if not is_clone:
                    c.execute("SELECT id FROM general_expenses WHERE company_id=? AND expense_date=? AND title=? AND amount=?", (cid, exp.get('expense_date'), exp.get('title'), exp.get('amount')))
                    if c.fetchone(): continue
                # -------------------------------------------------------
                c.execute("INSERT INTO general_expenses (company_id, expense_date, title, category, amount, notes) VALUES (?, ?, ?, ?, ?, ?)", 
                          (cid, exp.get('expense_date'), exp.get('title'), exp.get('category'), exp.get('amount'), exp.get('notes')))

        if "party_payments" in data:
            for pp in data["party_payments"]:
                # --- THE FIX: Block Duplicate Party Payments during Merge! ---
                if not is_clone:
                    c.execute("SELECT id FROM party_payments WHERE company_id=? AND party_name=? AND pay_type=? AND pay_date=? AND amount=? AND ref=?", (cid, pp.get('party_name'), pp.get('pay_type'), pp.get('pay_date'), pp.get('amount'), pp.get('ref')))
                    if c.fetchone(): continue
                # -------------------------------------------------------------
                c.execute("INSERT INTO party_payments (company_id, party_name, pay_type, pay_date, amount, mode, ref, notes, attachment_path) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", 
                          (cid, pp.get('party_name'), pp.get('pay_type'), pp.get('pay_date'), pp.get('amount'), pp.get('mode', 'Cash'), pp.get('ref'), pp.get('notes'), pp.get('attachment_path', '')))
                          
                # --- THE FIX: Re-sync the customer's wallet balance live during the import! ---
                ref_str = pp.get('ref', '')
                mode_str = pp.get('mode', 'Cash')
                p_amt = float(pp.get('amount', 0.0))
                p_type = pp.get('pay_type')
                party = pp.get('party_name')
                
                if "Advance Wallet" in ref_str:
                    pocket = "advance_in" if p_type == 'receive' else "advance_out"
                    database.internal_update_wallet(c, cid, party, p_amt, pocket)
                elif "Refunded" in ref_str:
                    pocket = "advance_in" if p_type == 'make' else "advance_out"
                    database.internal_update_wallet(c, cid, party, -p_amt, pocket)
                elif "Wallet Deduction" in mode_str:
                    pocket = "advance_in" if p_type == 'receive' else "advance_out"
                    database.internal_update_wallet(c, cid, party, -p_amt, pocket)
                # ------------------------------------------------------------------------------

        if "labours" in data:
            labour_id_map = {}
            for lab in data["labours"]:
                if not is_clone:
                    c.execute("SELECT id FROM labours WHERE company_id=? AND phone=? AND name=?", (cid, lab.get('phone'), lab.get('name')))
                    existing = c.fetchone()
                    if existing:
                        labour_id_map[lab['id']] = existing[0]
                        continue
                c.execute("INSERT INTO labours (company_id, name, phone, address, blood_type, role, photo_path, doc_path, profile_type, daily_rate, skilled_rate, unskilled_rate, emergency_contact, worker_id_str, dob, is_deleted) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", 
                          (cid, lab.get('name'), lab.get('phone'), lab.get('address'), lab.get('blood_type'), lab.get('role'), lab.get('photo_path'), lab.get('doc_path'), lab.get('profile_type', 'Individual'), lab.get('daily_rate', 0.0), lab.get('skilled_rate', 0.0), lab.get('unskilled_rate', 0.0), lab.get('emergency_contact', ''), lab.get('worker_id_str', ''), lab.get('dob', ''), lab.get('is_deleted', 0)))
                labour_id_map[lab['id']] = c.lastrowid

            if "labour_attendance" in data:
                for att in data["labour_attendance"]:
                    new_lab_id = labour_id_map.get(att.get('labour_id'))
                    if new_lab_id:
                        if not is_clone:
                            c.execute("SELECT id FROM labour_attendance WHERE labour_id=? AND date=?", (new_lab_id, att.get('date')))
                            if c.fetchone(): continue
                        c.execute("INSERT INTO labour_attendance (labour_id, date, hajira_count, skilled_count, unskilled_count, notes) VALUES (?, ?, ?, ?, ?, ?)", 
                                  (new_lab_id, att.get('date'), att.get('hajira_count', 1.0), att.get('skilled_count', 0.0), att.get('unskilled_count', 0.0), att.get('notes')))

            if "labour_ledger" in data:
                for ll in data["labour_ledger"]:
                    new_lab_id = labour_id_map.get(ll.get('labour_id'))
                    if new_lab_id:
                        # --- THE FIX: Block Duplicate Labour Ledgers during Merge! ---
                        if not is_clone:
                            c.execute("SELECT id FROM labour_ledger WHERE labour_id=? AND date=? AND type=? AND amount=? AND description=?", (new_lab_id, ll.get('date'), ll.get('type'), ll.get('amount'), ll.get('description')))
                            if c.fetchone(): continue
                        # -------------------------------------------------------------
                        c.execute("INSERT INTO labour_ledger (labour_id, date, type, amount, description, mode, attachment_path) VALUES (?, ?, ?, ?, ?, ?, ?)", 
                                  (new_lab_id, ll.get('date'), ll.get('type'), ll.get('amount'), ll.get('description'), ll.get('mode', 'Cash'), ll.get('attachment_path', '')))
        # ---------------------------------------------------------------------

        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()