import tkinter as tk
from tkinter import messagebox
import re
import json
from datetime import datetime
import calendar
import database
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
parts_dir = os.path.dirname(current_dir)
views_dir = os.path.dirname(parts_dir)
ROOT_DIR = os.path.dirname(views_dir)


def parse_raw_db_date(date_str):
    if not date_str or str(date_str).strip() == "None": return None
    raw = str(date_str).strip()[:10]
    for f in ("%Y-%m-%d", "%d-%m-%Y", "%d.%m.%Y", "%d/%m/%Y", "%m/%d/%Y"):
        try: return datetime.strptime(raw, f)
        except: pass
    return None

def execute_ledger_load(ledger):
    for i in ledger.sales_tree.get_children(): ledger.sales_tree.delete(i)
    for i in ledger.purch_tree.get_children(): ledger.purch_tree.delete(i)
    
    now = datetime.now()
    conn = database.get_connection()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS party_payments (id INTEGER PRIMARY KEY AUTOINCREMENT, company_id INTEGER, party_name TEXT, pay_type TEXT, pay_date TEXT, amount REAL, mode TEXT, ref TEXT)''')
    
    c.execute("PRAGMA table_info(party_payments)")
    cols = [col[1] for col in c.fetchall()]
    if "notes" not in cols: c.execute("ALTER TABLE party_payments ADD COLUMN notes TEXT DEFAULT ''")
    conn.commit()
    
    c.execute("SELECT address FROM customers WHERE id=?", (ledger.cust_db_id,))
    addr_raw = c.fetchone()[0]
    try: 
        j_data = json.loads(addr_raw)
        ledger.advance_in = float(j_data.get("advance_in", j_data.get("advance_wallet", 0.0)))
        ledger.advance_out = float(j_data.get("advance_out", 0.0))
        ledger.ob_paid = float(j_data.get("ob_paid", 0.0))
    except: 
        ledger.advance_in = 0.0
        ledger.advance_out = 0.0
        ledger.ob_paid = 0.0

    custom_start, custom_end = None, None
    start_date = None
    if ledger.filter_var.get() == "This Month":
        start_date = datetime(now.year, now.month, 1)
    elif ledger.filter_var.get() == "This Financial Year":
        start_year = now.year if now.month >= 4 else now.year - 1
        start_date = datetime(start_year, 4, 1)
    elif ledger.filter_var.get() == "Custom Range...":
        try:
            custom_start = datetime.strptime(ledger.from_var.get().strip(), ledger.date_fmt_code)
            custom_end = datetime.strptime(ledger.to_var.get().strip(), ledger.date_fmt_code)
            start_date = custom_start
        except: pass

    search_q = ledger.search_var.get().strip().lower()
    if search_q == "bill no / amount...": search_q = ""

    s_inv, s_rec, s_pend = 0.0, 0.0, 0.0
    hidden_s_pend = 0.0
    visible_sales = []

    # --- THE FIX: Fetch invoices by customer_id instead of text name ---
    c.execute("SELECT id, invoice_date, invoice_number, total, amount_paid, balance_due, status FROM invoices WHERE customer_id=? AND company_id=? AND is_deleted=0 AND status != 'Draft' ORDER BY invoice_date ASC, id ASC", (ledger.cust_db_id, ledger.comp_id))
    for r in c.fetchall():
    # -------------------------------------------------------------------
        dt = parse_raw_db_date(r[1])
        is_visible = True
        
        if ledger.filter_var.get() != "All Time" and dt:
            if start_date and dt < start_date:
                hidden_s_pend += r[5]
                is_visible = False
            elif ledger.filter_var.get() == "This Month" and (dt.year != now.year or dt.month != now.month):
                is_visible = False
            elif ledger.filter_var.get() == "Custom Range..." and custom_end and dt > custom_end:
                is_visible = False

        if search_q and search_q not in str(r[2]).lower() and search_q not in str(r[3]).lower(): 
            is_visible = False

        if is_visible:
            visible_sales.append(r)
            s_inv += r[3]; s_rec += r[4]; s_pend += r[5]

    p_bill, p_paid, p_pend = 0.0, 0.0, 0.0
    hidden_p_pend = 0.0
    visible_purch = []

    try:
        # --- THE FIX: Fetch purchases by vendor_id instead of text name ---
        c.execute("SELECT id, purchase_date, bill_number, total, amount_paid, balance_due, status FROM purchases WHERE vendor_id=? AND company_id=? AND is_deleted=0 AND is_draft=0 ORDER BY purchase_date ASC, id ASC", (ledger.cust_db_id, ledger.comp_id))
        for r in c.fetchall():
        # ------------------------------------------------------------------
            dt = parse_raw_db_date(r[1])
            is_visible = True
            
            if ledger.filter_var.get() != "All Time" and dt:
                if start_date and dt < start_date:
                    hidden_p_pend += r[5]
                    is_visible = False
                elif ledger.filter_var.get() == "This Month" and (dt.year != now.year or dt.month != now.month):
                    is_visible = False
                elif ledger.filter_var.get() == "Custom Range..." and custom_end and dt > custom_end:
                    is_visible = False

            if search_q and search_q not in str(r[2]).lower() and search_q not in str(r[3]).lower(): 
                is_visible = False

            if is_visible:
                visible_purch.append(r)
                p_bill += r[3]; p_paid += r[4]; p_pend += r[5]
    except: pass

    # --- THE FIX: Map TDS data across the entire Ledger! ---
    c.execute("SELECT ref, amount FROM party_payments WHERE company_id=? AND party_id=? AND mode='TDS Deduction'", (ledger.comp_id, ledger.cust_db_id))
    tds_map = {}
    for ref_str, amt in c.fetchall():
        if ref_str:
            bill_no = ref_str.split(" (")[0].strip()
            tds_map[bill_no] = tds_map.get(bill_no, 0.0) + float(amt or 0.0)
    # -------------------------------------------------------
    conn.close()

    s_idx, p_idx = 0, 0
    
    s_ob_orig = ledger.ob_val if "Dr" in ledger.ob_type else 0.0
    p_ob_orig = ledger.ob_val if "Cr" in ledger.ob_type else 0.0

    ob_due = max(0.0, ledger.ob_val - ledger.ob_paid)
    s_ob_due = ob_due if "Dr" in ledger.ob_type else 0.0
    p_ob_due = ob_due if "Cr" in ledger.ob_type else 0.0
    
    net_s_bf = s_ob_due + hidden_s_pend
    net_p_bf = p_ob_due + hidden_p_pend
    
    running_s_bal = net_s_bf
    running_p_bal = net_p_bf

    bf_date_str = start_date.strftime(ledger.date_fmt_code) if start_date else "Opening"

    if s_ob_orig > 0 or hidden_s_pend > 0:
        amt_str = ledger.fmt(s_ob_orig) if s_ob_orig > 0 else "-"
        status_str = "Paid" if net_s_bf <= 0.01 else ("Partial" if ledger.ob_paid > 0 and s_ob_orig > 0 else "Unpaid")
        
        # --- THE FIX: Add Empty TDS Column for B/F ---
        ledger.sales_tree.insert("", "end", iid="S_BF", values=(bf_date_str, "Brought Forward (B/F)", amt_str, "-", ledger.fmt(running_s_bal), status_str, ""), tags=("stripe_even",))
        s_pend += net_s_bf
        s_idx += 1
        
    if p_ob_orig > 0 or hidden_p_pend > 0:
        amt_str = ledger.fmt(p_ob_orig) if p_ob_orig > 0 else "-"
        status_str = "Paid" if net_p_bf <= 0.01 else ("Partial" if ledger.ob_paid > 0 and p_ob_orig > 0 else "Unpaid")

        # --- THE FIX: Add Empty TDS Column for B/F ---
        ledger.purch_tree.insert("", "end", iid="P_BF", values=(bf_date_str, "Brought Forward (B/F)", amt_str, "-", ledger.fmt(running_p_bal), status_str, ""), tags=("stripe_even",))
        p_pend += net_p_bf
        p_idx += 1

    for r in visible_sales:
        tag = "stripe_even" if s_idx % 2 == 0 else "stripe_odd"
        total_amt = r[3]
        paid_amt = r[4]
        due_amt = r[5]
        
        status_str = r[6]
        if status_str != "Paid" and paid_amt > 0:
            status_str = f"Partial ({ledger.fmt(due_amt)})"
            
        running_s_bal += due_amt
        tds_val = tds_map.get(r[2], 0.0)
        
        # --- THE FIX: Inject TDS Value into Sales Ledger ---
        ledger.sales_tree.insert("", "end", iid=f"S_{r[0]}", values=(ledger.fmt_date(r[1]), r[2], ledger.fmt(total_amt), ledger.fmt(tds_val), ledger.fmt(running_s_bal), status_str, ""), tags=(tag,))
        s_idx += 1
        
    for r in visible_purch:
        tag = "stripe_even" if p_idx % 2 == 0 else "stripe_odd"
        total_amt = r[3]
        paid_amt = r[4]
        due_amt = r[5]
        
        status_str = r[6]
        if status_str != "Paid" and paid_amt > 0:
            status_str = f"Partial ({ledger.fmt(due_amt)})"
            
        running_p_bal += due_amt
        tds_val = tds_map.get(r[2], 0.0)
        
        # --- THE FIX: Inject TDS Value into Purchase Ledger ---
        ledger.purch_tree.insert("", "end", iid=f"P_{r[0]}", values=(ledger.fmt_date(r[1]), r[2], ledger.fmt(total_amt), ledger.fmt(tds_val), ledger.fmt(running_p_bal), status_str, ""), tags=(tag,))
        p_idx += 1

    for j in range(len(ledger.sales_tree.get_children()), 16):
        tag = "stripe_even" if j % 2 == 0 else "stripe_odd"
        ledger.sales_tree.insert("", "end", values=("", "", "", "", "", "", ""), tags=(tag, "empty"))

    for j in range(len(ledger.purch_tree.get_children()), 16):
        tag = "stripe_even" if j % 2 == 0 else "stripe_odd"
        ledger.purch_tree.insert("", "end", values=("", "", "", "", "", "", ""), tags=(tag, "empty"))

    ledger.lbl_s_inv.config(text=f"Total Invoiced\n{ledger.fmt(s_inv)}")
    ledger.lbl_s_rec.config(text=f"Total Received\n{ledger.fmt(s_rec)}")
    ledger.lbl_s_pend.config(text=f"Total Receivable\n{ledger.fmt(s_pend)}")
    ledger.lbl_p_bill.config(text=f"Total Billed\n{ledger.fmt(p_bill)}")
    ledger.lbl_p_paid.config(text=f"Total Paid\n{ledger.fmt(p_paid)}")
    ledger.lbl_p_pend.config(text=f"Total Payable\n{ledger.fmt(p_pend)}")
    
    ledger.net_s_pend = s_pend
    ledger.net_p_pend = p_pend
    
    net_val = (s_pend - p_pend) - ledger.advance_in + ledger.advance_out
    
    if net_val > 0:
        sum_txt = f"Total Net Balance: + {ledger.fmt(net_val)} (Receivable / They Owe You)"
        sum_col = ledger.colors["error"]
    elif net_val < 0:
        sum_txt = f"Total Net Balance: - {ledger.fmt(abs(net_val))} (Payable / You Owe Them)"
        sum_col = ledger.colors["accent_blue"]
    else:
        sum_txt = "Total Net Balance: 0.00 (Fully Settled)"
        sum_col = ledger.colors["accent_green"]
        
    ledger.lbl_grand.config(text=sum_txt, fg=sum_col)
    
    # --- THE FIX: Match Undo/Redo active styling to the Main Table (Blue bg, White fg) ---
    if ledger.undo_stack: 
        ledger.btn_undo.config(state="normal", bg=ledger.colors["accent_blue"], fg="#ffffff", cursor="hand2")
    else: 
        ledger.btn_undo.config(state="disabled", bg=ledger.colors["card"], fg=ledger.colors["text_sec"], cursor="arrow")
        
    if ledger.redo_stack: 
        ledger.btn_redo.config(state="normal", bg=ledger.colors["accent_blue"], fg="#ffffff", cursor="hand2")
    else: 
        ledger.btn_redo.config(state="disabled", bg=ledger.colors["card"], fg=ledger.colors["text_sec"], cursor="arrow")
    # -------------------------------------------------------------------------------------

    if hasattr(ledger, 'lbl_adv_in'):
        ledger.lbl_adv_in.config(text=f"Advance (In): {ledger.fmt(ledger.advance_in)}", fg=ledger.colors["accent_green"] if ledger.advance_in > 0 else ledger.colors["text_sec"])
    if hasattr(ledger, 'lbl_adv_out'):
        ledger.lbl_adv_out.config(text=f"Advance (Out): {ledger.fmt(ledger.advance_out)}", fg=ledger.colors["accent_blue"] if ledger.advance_out > 0 else ledger.colors["text_sec"])

    # --- THE FIX: Force the History UI to re-render if it is open! ---
    if hasattr(ledger, 'refresh_history_ui') and ledger.refresh_history_ui:
        try: ledger.refresh_history_ui()
        except: pass
    # -----------------------------------------------------------------

def show_net_balance_breakdown(ledger):
    pop = tk.Toplevel(ledger)
    pop.title("Net Balance Breakdown")
    pop.geometry("450x380")
    pop.configure(bg=ledger.colors["bg"])
    pop.grab_set()
    
    pop.update_idletasks()
    x = ledger.winfo_rootx() + (ledger.winfo_width()//2) - (450//2)
    y = ledger.winfo_rooty() + (ledger.winfo_height()//2) - (380//2)
    pop.geometry(f"+{x}+{y}")
    
    tk.Label(pop, text="Mathematical Breakdown", font=("Segoe UI", 16, "bold"), bg=ledger.colors["bg"], fg=ledger.colors["text"]).pack(pady=(15, 10))
    
    f = tk.Frame(pop, bg=ledger.colors["card"], highlightbackground=ledger.colors["border"], highlightthickness=1, padx=20, pady=20)
    f.pack(fill="both", expand=True, padx=20, pady=(0, 20))
    
    def add_row(parent, label, amount, color):
        row = tk.Frame(parent, bg=ledger.colors["card"])
        row.pack(fill="x", pady=5)
        tk.Label(row, text=label, font=("Segoe UI", 11), bg=ledger.colors["card"], fg=ledger.colors["text_sec"]).pack(side="left")
        tk.Label(row, text=amount, font=("Segoe UI", 11, "bold"), bg=ledger.colors["card"], fg=color).pack(side="right")
        
    add_row(f, "Total Receivable (Invoices + OB):", f"+ {ledger.fmt(ledger.net_s_pend)}", ledger.colors["text"])
    add_row(f, "Total Payable (Bills + OB):", f"- {ledger.fmt(ledger.net_p_pend)}", ledger.colors["text"])
    
    tk.Frame(f, height=1, bg=ledger.colors["border"]).pack(fill="x", pady=8)
    
    add_row(f, "Advance Received (In):", f"- {ledger.fmt(ledger.advance_in)}", ledger.colors["text"])
    add_row(f, "Advance Given (Out):", f"+ {ledger.fmt(ledger.advance_out)}", ledger.colors["text"])
    
    tk.Frame(f, height=1, bg=ledger.colors["border"]).pack(fill="x", pady=8)
    
    net_val = (ledger.net_s_pend - ledger.net_p_pend) - ledger.advance_in + ledger.advance_out
    color = ledger.colors["error"] if net_val > 0 else (ledger.colors["accent_blue"] if net_val < 0 else ledger.colors["accent_green"])
    
    add_row(f, "FINAL NET BALANCE:", ledger.fmt(abs(net_val)), color)


def treeview_sort_column(tree, col, tree_type, ledger):
    reverse = ledger.sort_dirs[tree_type].get(col, False)
    l = [(tree.set(k, col), k) for k in tree.get_children('') if not str(k).startswith("empty_") and "BF" not in str(k)]
    
    def safe_convert(val):
        v_str = str(val).strip()
        if col in ("amount", "balance"):
            m = re.search(r'[-+]?\d*\.?\d+', v_str.replace(',', ''))
            return float(m.group()) if m else 0.0
        elif col == "date":
            for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d.%m.%Y", "%d/%m/%Y", "%m/%d/%Y", ledger.date_fmt_code):
                try: return datetime.strptime(v_str, fmt).timestamp()
                except: pass
            return 0.0
        return v_str.lower()

    try: l.sort(key=lambda t: safe_convert(t[0]), reverse=reverse)
    except: pass

    start_idx = 0
    for k in tree.get_children(''):
        if "BF" in str(k):
            start_idx = 1
            break

    for index, (val, k) in enumerate(l):
        tree.move(k, '', index + start_idx)
        tag = "stripe_even" if (index + start_idx) % 2 == 0 else "stripe_odd"
        tree.item(k, tags=(tag,))

    empty_items = [k for k in tree.get_children('') if str(k).startswith("empty_")]
    for idx, k in enumerate(empty_items):
        tree.move(k, '', 'end')
        tag = "stripe_even" if (len(l) + start_idx + idx) % 2 == 0 else "stripe_odd"
        tree.item(k, tags=(tag, "empty"))

    ledger.sort_dirs[tree_type][col] = not reverse

def set_ledger_cursor(e, tree):
    row_id = tree.identify_row(e.y)
    if row_id and not str(row_id).startswith("empty"): tree.config(cursor="hand2")
    else: tree.config(cursor="")

def on_sale_double_click(e, ledger):
    item = ledger.sales_tree.selection()
    if not item or "empty" in ledger.sales_tree.item(item[0], "tags") or "BF" in str(item[0]): return
    iid = item[0].replace("S_", "")
    try:
        from views.invoice_parts.invoice_actions import show_preview_from_db
        show_preview_from_db(ledger.parent_view, iid)
    except Exception as err: 
        messagebox.showinfo("Error", f"Could not open Live Preview: {err}", parent=ledger)

def on_purch_double_click(e, ledger):
    item = ledger.purch_tree.selection()
    if not item or "empty" in ledger.purch_tree.item(item[0], "tags") or "BF" in str(item[0]): return
    iid = item[0].replace("P_", "")
    
    try:
        from views.purchase_parts.print_studio.purchase_preview_window import open_purchase_preview
        open_purchase_preview(ledger.parent_view, iid)
    except Exception as err: 
        messagebox.showinfo("Error", f"Could not open Live Preview: {err}", parent=ledger)

def process_history_action(ledger, action, is_undo=True):
    conn = database.get_connection()
    c = conn.cursor()
    
    table = "invoices" if action["pay_type"] == "receive" else "purchases"
    
    c.execute(f"PRAGMA table_info({table})")
    has_woff = "written_off" in [col[1] for col in c.fetchall()]
    
    for item in action["invoices_changed"]:
        if has_woff and len(item) > 4:
            inv_id, prev_paid, prev_due, prev_status, prev_woff = item
            # --- THE FIX: Added company_id locks to Undo/Redo Engine ---
            c.execute(f"UPDATE {table} SET amount_paid=?, balance_due=?, status=?, written_off=? WHERE id=? AND company_id=?", (prev_paid, prev_due, prev_status, prev_woff, inv_id, ledger.comp_id))
        else:
            inv_id, prev_paid, prev_due, prev_status = item[0], item[1], item[2], item[3]
            c.execute(f"UPDATE {table} SET amount_paid=?, balance_due=?, status=? WHERE id=? AND company_id=?", (prev_paid, prev_due, prev_status, inv_id, ledger.comp_id))

    c.execute("SELECT address FROM customers WHERE id=? AND company_id=?", (ledger.cust_db_id, ledger.comp_id))
    addr_raw = c.fetchone()[0]
    try:
        j_data = json.loads(addr_raw)
        if "old_adv_in" in action: j_data["advance_in"] = action["old_adv_in"]
        if "old_adv_out" in action: j_data["advance_out"] = action["old_adv_out"]
        if "old_advance" in action: j_data["advance_wallet"] = action["old_advance"]
        if "old_ob_paid" in action: j_data["ob_paid"] = action["old_ob_paid"]
        c.execute("UPDATE customers SET address=? WHERE id=? AND company_id=?", (json.dumps(j_data), ledger.cust_db_id, ledger.comp_id))
    except: pass

    if is_undo:
        for pid in action.get("pay_ids", []):
            c.execute("DELETE FROM party_payments WHERE id=?", (pid,))
    else:
        action["pay_ids"] = []
        for h_row in action.get("history_rows", []):
            attach_val = h_row[4] if len(h_row) > 4 else ""
            # --- THE FIX: Inject party_id for Redo/Undo creations ---
            c.execute("INSERT INTO party_payments (company_id, party_name, party_id, pay_type, pay_date, amount, mode, ref, notes, attachment_path) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                      (ledger.comp_id, ledger.party_name, ledger.cust_db_id, action["pay_type"], action["pay_date"], h_row[0], h_row[1], h_row[2], h_row[3], attach_val))
            action["pay_ids"].append(c.lastrowid)
            # --------------------------------------------------------
        
    conn.commit()
    conn.close()

def undo_last_payment(ledger):
    if not ledger.undo_stack: return
    action = ledger.undo_stack.pop()
    
    conn = database.get_connection()
    c = conn.cursor()

    # --- THE FIX: Undo Engine for Contra Bills ---
    if action["pay_type"] == "contra":
        redo_action = dict(action)
        redo_action["inv_changes"] = []
        redo_action["purch_changes"] = []

        c.execute("PRAGMA table_info(invoices)")
        has_woff_inv = "written_off" in [col[1] for col in c.fetchall()]
        for item in action["inv_changes"]:
            inv_id = item[0]
            if has_woff_inv:
                c.execute("SELECT amount_paid, balance_due, status, written_off FROM invoices WHERE id=?", (inv_id,))
                r = c.fetchone()
                redo_action["inv_changes"].append((inv_id, r[0], r[1], r[2], r[3]))
                c.execute("UPDATE invoices SET amount_paid=?, balance_due=?, status=?, written_off=? WHERE id=? AND company_id=?", (item[1], item[2], item[3], item[4], inv_id, ledger.comp_id))
            else:
                c.execute("SELECT amount_paid, balance_due, status FROM invoices WHERE id=?", (inv_id,))
                r = c.fetchone()
                redo_action["inv_changes"].append((inv_id, r[0], r[1], r[2], 0.0))
                c.execute("UPDATE invoices SET amount_paid=?, balance_due=?, status=? WHERE id=? AND company_id=?", (item[1], item[2], item[3], inv_id, ledger.comp_id))

        c.execute("PRAGMA table_info(purchases)")
        has_woff_purch = "written_off" in [col[1] for col in c.fetchall()]
        for item in action["purch_changes"]:
            purch_id = item[0]
            if has_woff_purch:
                c.execute("SELECT amount_paid, balance_due, status, written_off FROM purchases WHERE id=?", (purch_id,))
                r = c.fetchone()
                redo_action["purch_changes"].append((purch_id, r[0], r[1], r[2], r[3]))
                c.execute("UPDATE purchases SET amount_paid=?, balance_due=?, status=?, written_off=? WHERE id=? AND company_id=?", (item[1], item[2], item[3], item[4], purch_id, ledger.comp_id))
            else:
                c.execute("SELECT amount_paid, balance_due, status FROM purchases WHERE id=?", (purch_id,))
                r = c.fetchone()
                redo_action["purch_changes"].append((purch_id, r[0], r[1], r[2], 0.0))
                c.execute("UPDATE purchases SET amount_paid=?, balance_due=?, status=? WHERE id=? AND company_id=?", (item[1], item[2], item[3], purch_id, ledger.comp_id))

        for pid in action["pay_ids"]:
            c.execute("DELETE FROM party_payments WHERE id=?", (pid,))

        conn.commit()
        conn.close()

        database.log_audit("Parties", "Undo Contra Settlement", record_ref=ledger.party_name, details=f"Undid Bill Settlement of @@CURR:{action['offset_amt']}@@", amount=action['offset_amt'], company_id=ledger.comp_id)
        ledger.redo_stack.append(redo_action)
        execute_ledger_load(ledger)
        if hasattr(ledger.parent_view, 'load_data'): ledger.parent_view.load_data()
        return
    # ---------------------------------------------
    
    if action["pay_type"] == "offset":
        redo_action = dict(action)
        
        c.execute("SELECT address FROM customers WHERE id=? AND company_id=?", (ledger.cust_db_id, ledger.comp_id))
        j_data = json.loads(c.fetchone()[0])
        j_data["advance_in"] = action["old_adv_in"]
        j_data["advance_out"] = action["old_adv_out"]
        c.execute("UPDATE customers SET address=? WHERE id=? AND company_id=?", (json.dumps(j_data), ledger.cust_db_id, ledger.comp_id))
        
        for pid in action["pay_ids"]:
            c.execute("DELETE FROM party_payments WHERE id=?", (pid,))
            
        conn.commit()
        conn.close()
        database.log_audit("Parties", "Undo Offset", record_ref=ledger.party_name, details=f"Undid wallet offset of @@CURR:{action.get('offset_amt', 0.0)}@@", amount=action.get("offset_amt", 0.0), company_id=ledger.comp_id)
        ledger.redo_stack.append(redo_action)
        execute_ledger_load(ledger)
        if hasattr(ledger.parent_view, 'load_data'): ledger.parent_view.load_data()
        return

    redo_action = dict(action)
    redo_action["invoices_changed"] = []
    table = "invoices" if action["pay_type"] == "receive" else "purchases"
    
    c.execute(f"PRAGMA table_info({table})")
    has_woff = "written_off" in [col[1] for col in c.fetchall()]
    
    for item in action["invoices_changed"]:
        if has_woff:
            c.execute(f"SELECT amount_paid, balance_due, status, written_off FROM {table} WHERE id=?", (item[0],))
            r = c.fetchone()
            redo_action["invoices_changed"].append((item[0], r[0], r[1], r[2], r[3]))
        else:
            c.execute(f"SELECT amount_paid, balance_due, status FROM {table} WHERE id=?", (item[0],))
            r = c.fetchone()
            redo_action["invoices_changed"].append((item[0], r[0], r[1], r[2], 0.0))
    
    c.execute("SELECT address FROM customers WHERE id=? AND company_id=?", (ledger.cust_db_id, ledger.comp_id))
    try: 
        j = json.loads(c.fetchone()[0])
        redo_action["old_adv_in"] = float(j.get("advance_in", j.get("advance_wallet", 0.0)))
        redo_action["old_adv_out"] = float(j.get("advance_out", 0.0))
        redo_action["old_ob_paid"] = float(j.get("ob_paid", 0.0))
    except: 
        redo_action["old_adv_in"] = 0.0
        redo_action["old_adv_out"] = 0.0
        redo_action["old_ob_paid"] = 0.0
    conn.close()

    ledger.redo_stack.append(redo_action)
    process_history_action(ledger, action, is_undo=True)
    tot_undone = sum(abs(float(r[0] or 0.0)) for r in action.get("history_rows", []))
    database.log_audit("Parties", "Undo Payment", record_ref=ledger.party_name, details=f"Undid {action.get('pay_type', 'ledger')} payment ({action.get('mode', '')})", amount=tot_undone, company_id=ledger.comp_id)
    execute_ledger_load(ledger)
    if hasattr(ledger.parent_view, 'load_data'): ledger.parent_view.load_data() 

def redo_last_payment(ledger):
    if not ledger.redo_stack: return
    action = ledger.redo_stack.pop()
    
    conn = database.get_connection()
    c = conn.cursor()

    # --- THE FIX: Redo Engine for Contra Bills ---
    if action["pay_type"] == "contra":
        undo_action = dict(action)
        undo_action["inv_changes"] = []
        undo_action["purch_changes"] = []

        c.execute("PRAGMA table_info(invoices)")
        has_woff_inv = "written_off" in [col[1] for col in c.fetchall()]
        for item in action["inv_changes"]:
            inv_id = item[0]
            if has_woff_inv:
                c.execute("SELECT amount_paid, balance_due, status, written_off FROM invoices WHERE id=?", (inv_id,))
                r = c.fetchone()
                undo_action["inv_changes"].append((inv_id, r[0], r[1], r[2], r[3]))
                c.execute("UPDATE invoices SET amount_paid=?, balance_due=?, status=?, written_off=? WHERE id=? AND company_id=?", (item[1], item[2], item[3], item[4], inv_id, ledger.comp_id))
            else:
                c.execute("SELECT amount_paid, balance_due, status FROM invoices WHERE id=?", (inv_id,))
                r = c.fetchone()
                undo_action["inv_changes"].append((inv_id, r[0], r[1], r[2], 0.0))
                c.execute("UPDATE invoices SET amount_paid=?, balance_due=?, status=? WHERE id=? AND company_id=?", (item[1], item[2], item[3], inv_id, ledger.comp_id))

        c.execute("PRAGMA table_info(purchases)")
        has_woff_purch = "written_off" in [col[1] for col in c.fetchall()]
        for item in action["purch_changes"]:
            purch_id = item[0]
            if has_woff_purch:
                c.execute("SELECT amount_paid, balance_due, status, written_off FROM purchases WHERE id=?", (purch_id,))
                r = c.fetchone()
                undo_action["purch_changes"].append((purch_id, r[0], r[1], r[2], r[3]))
                c.execute("UPDATE purchases SET amount_paid=?, balance_due=?, status=?, written_off=? WHERE id=? AND company_id=?", (item[1], item[2], item[3], item[4], purch_id, ledger.comp_id))
            else:
                c.execute("SELECT amount_paid, balance_due, status FROM purchases WHERE id=?", (purch_id,))
                r = c.fetchone()
                undo_action["purch_changes"].append((purch_id, r[0], r[1], r[2], 0.0))
                c.execute("UPDATE purchases SET amount_paid=?, balance_due=?, status=? WHERE id=? AND company_id=?", (item[1], item[2], item[3], purch_id, ledger.comp_id))

        new_ids = []
        for h in action["history_rows"]:
            c.execute("INSERT INTO party_payments (company_id, party_name, party_id, pay_type, pay_date, amount, mode, ref, notes, attachment_path) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                      (ledger.comp_id, ledger.party_name, ledger.cust_db_id, h[0], h[1], h[2], h[3], h[4], h[5], ""))
            new_ids.append(c.lastrowid)
        undo_action["pay_ids"] = new_ids

        conn.commit()
        conn.close()

        database.log_audit("Parties", "Redo Contra Settlement", record_ref=ledger.party_name, details=f"Redid Bill Settlement of @@CURR:{action['offset_amt']}@@", amount=action['offset_amt'], company_id=ledger.comp_id)
        ledger.undo_stack.append(undo_action)
        execute_ledger_load(ledger)
        if hasattr(ledger.parent_view, 'load_data'): ledger.parent_view.load_data()
        return
    # ---------------------------------------------
    
    if action["pay_type"] == "offset":
        undo_action = dict(action)
        
        c.execute("SELECT address FROM customers WHERE id=? AND company_id=?", (ledger.cust_db_id, ledger.comp_id))
        j_data = json.loads(c.fetchone()[0])
        
        offset_amt = action["offset_amt"]
        j_data["advance_in"] = max(0.0, j_data.get("advance_in", 0) - offset_amt)
        j_data["advance_out"] = max(0.0, j_data.get("advance_out", 0) - offset_amt)
        c.execute("UPDATE customers SET address=? WHERE id=? AND company_id=?", (json.dumps(j_data), ledger.cust_db_id, ledger.comp_id))
        
        today_db = datetime.now().strftime("%Y-%m-%d")
        note = "System Adjustment: Wallets Offset"
        
        new_ids = []
        # --- THE FIX: Inject party_id into Wallet Offsets (Redo) ---
        c.execute("INSERT INTO party_payments (company_id, party_name, party_id, pay_type, pay_date, amount, mode, ref, notes) VALUES (?, ?, ?, 'receive', ?, ?, 'Adjustment', 'Offset Wallet', ?)",
                  (ledger.comp_id, ledger.party_name, ledger.cust_db_id, today_db, -offset_amt, note))
        new_ids.append(c.lastrowid)
        c.execute("INSERT INTO party_payments (company_id, party_name, party_id, pay_type, pay_date, amount, mode, ref, notes) VALUES (?, ?, ?, 'make', ?, ?, 'Adjustment', 'Offset Wallet', ?)",
                  (ledger.comp_id, ledger.party_name, ledger.cust_db_id, today_db, -offset_amt, note))
        new_ids.append(c.lastrowid)
        # -----------------------------------------------------------
        
        undo_action["pay_ids"] = new_ids
        
        conn.commit()
        conn.close()
        database.log_audit("Parties", "Redo Offset", record_ref=ledger.party_name, details=f"Redid wallet offset of @@CURR:{offset_amt}@@", amount=offset_amt, company_id=ledger.comp_id)
        ledger.undo_stack.append(undo_action)
        execute_ledger_load(ledger)
        if hasattr(ledger.parent_view, 'load_data'): ledger.parent_view.load_data()
        return

    undo_action = dict(action)
    undo_action["invoices_changed"] = []
    table = "invoices" if action["pay_type"] == "receive" else "purchases"
    
    c.execute(f"PRAGMA table_info({table})")
    has_woff = "written_off" in [col[1] for col in c.fetchall()]
    
    for item in action["invoices_changed"]:
        if has_woff:
            c.execute(f"SELECT amount_paid, balance_due, status, written_off FROM {table} WHERE id=?", (item[0],))
            r = c.fetchone()
            undo_action["invoices_changed"].append((item[0], r[0], r[1], r[2], r[3]))
        else:
            c.execute(f"SELECT amount_paid, balance_due, status FROM {table} WHERE id=?", (item[0],))
            r = c.fetchone()
            undo_action["invoices_changed"].append((item[0], r[0], r[1], r[2], 0.0))
        
    c.execute("SELECT address FROM customers WHERE id=? AND company_id=?", (ledger.cust_db_id, ledger.comp_id))
    try: 
        j = json.loads(c.fetchone()[0])
        undo_action["old_adv_in"] = float(j.get("advance_in", j.get("advance_wallet", 0.0)))
        undo_action["old_adv_out"] = float(j.get("advance_out", 0.0))
        undo_action["old_ob_paid"] = float(j.get("ob_paid", 0.0))
    except: 
        undo_action["old_adv_in"] = 0.0
        undo_action["old_adv_out"] = 0.0
        undo_action["old_ob_paid"] = 0.0
    conn.close()

    ledger.undo_stack.append(undo_action)
    process_history_action(ledger, action, is_undo=False)
    tot_redone = sum(abs(float(r[0] or 0.0)) for r in action.get("history_rows", []))
    database.log_audit("Parties", "Redo Payment", record_ref=ledger.party_name, details=f"Redid {action.get('pay_type', 'ledger')} payment ({action.get('mode', '')})", amount=tot_redone, company_id=ledger.comp_id)
    execute_ledger_load(ledger)
    if hasattr(ledger.parent_view, 'load_data'): ledger.parent_view.load_data()

def perform_offset(ledger):
    if ledger.advance_in <= 0 or ledger.advance_out <= 0: 
        return

    offset_amt = min(ledger.advance_in, ledger.advance_out)
    
    msg = f"Are you sure you want to offset {ledger.fmt(offset_amt)}?\n\nThis will permanently cancel out Advance (In) against Advance (Out) to settle debts."
    if not messagebox.askyesno("Confirm Offset", msg, parent=ledger):
        return

    conn = database.get_connection()
    c = conn.cursor()

    c.execute("SELECT address FROM customers WHERE id=? AND company_id=?", (ledger.cust_db_id, ledger.comp_id))
    addr_raw = c.fetchone()[0]
    j_data = json.loads(addr_raw)
    
    old_adv_in = ledger.advance_in
    old_adv_out = ledger.advance_out
    
    j_data["advance_in"] = max(0.0, ledger.advance_in - offset_amt)
    j_data["advance_out"] = max(0.0, ledger.advance_out - offset_amt)
    
    c.execute("UPDATE customers SET address=? WHERE id=? AND company_id=?", (json.dumps(j_data), ledger.cust_db_id, ledger.comp_id))

    today_db = datetime.now().strftime("%Y-%m-%d")
    note = "System Adjustment: Wallets Offset"
    
    # --- THE FIX: Inject party_id into Wallet Offsets (Manual Creation) ---
    c.execute("INSERT INTO party_payments (company_id, party_name, party_id, pay_type, pay_date, amount, mode, ref, notes) VALUES (?, ?, ?, 'receive', ?, ?, 'Adjustment', 'Offset Wallet', ?)",
              (ledger.comp_id, ledger.party_name, ledger.cust_db_id, today_db, -offset_amt, note))
    id1 = c.lastrowid
    
    c.execute("INSERT INTO party_payments (company_id, party_name, party_id, pay_type, pay_date, amount, mode, ref, notes) VALUES (?, ?, ?, 'make', ?, ?, 'Adjustment', 'Offset Wallet', ?)",
              (ledger.comp_id, ledger.party_name, ledger.cust_db_id, today_db, -offset_amt, note))
    id2 = c.lastrowid
    # ----------------------------------------------------------------------

    action_log = {
        "pay_type": "offset",
        "old_adv_in": old_adv_in,
        "old_adv_out": old_adv_out,
        "offset_amt": offset_amt,
        "pay_ids": [id1, id2]
    }
    ledger.undo_stack.append(action_log)
    ledger.redo_stack.clear()

    conn.commit()
    conn.close()

    database.log_audit("Parties", "Wallet Offset", record_ref=ledger.party_name, details=f"Offset Advance (In) against Advance (Out): @@CURR:{offset_amt}@@", amount=offset_amt, company_id=ledger.comp_id)
    execute_ledger_load(ledger)
    if hasattr(ledger.parent_view, 'load_data'): ledger.parent_view.load_data()