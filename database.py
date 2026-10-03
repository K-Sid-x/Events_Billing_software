import sqlite3
import datetime
import json
import re
import os
import sys

# --- THE FIX: Bulletproof Executable Pathing ---
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DB_PATH = os.path.join(BASE_DIR, "ledger_events_v13.db")
# -----------------------------------------------
ACTIVE_COMPANY_ID = 1 
ACTIVE_USER_ID = 1

def set_active_company(company_id):
    global ACTIVE_COMPANY_ID
    ACTIVE_COMPANY_ID = int(company_id)

def set_active_user(user_id):
    global ACTIVE_USER_ID
    ACTIVE_USER_ID = int(user_id) if user_id else 1

def get_connection(): 
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    conn = get_connection(); cursor = conn.cursor()
    
    # --- NEW: Secure User Table for RBAC ---
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL,
            profile_pic TEXT
        )
    ''')
    # ---------------------------------------

    cursor.execute('''CREATE TABLE IF NOT EXISTS company (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, name_secondary TEXT, address TEXT, phone TEXT, phone2 TEXT, phone3 TEXT, email TEXT, gst_toggle INTEGER, gstin TEXT, logo_path TEXT, header_layout TEXT DEFAULT 'Classic', logo_size INTEGER DEFAULT 120, logo_shape TEXT DEFAULT 'Square', template_json TEXT)''')
    
    try: cursor.execute("ALTER TABLE company ADD COLUMN security_pin TEXT DEFAULT ''")
    except: pass
    try: cursor.execute("ALTER TABLE company ADD COLUMN is_pinned INTEGER DEFAULT 0")
    except: pass
    try: cursor.execute("ALTER TABLE company ADD COLUMN state TEXT DEFAULT ''")
    except: pass
    try: cursor.execute("ALTER TABLE company ADD COLUMN state_code TEXT DEFAULT ''")
    except: pass
    try: cursor.execute("ALTER TABLE company ADD COLUMN business_type TEXT DEFAULT 'Sales'")
    except: pass
    try: cursor.execute("ALTER TABLE company ADD COLUMN purchase_template_json TEXT")
    except: pass

    cursor.execute('''CREATE TABLE IF NOT EXISTS customers (id INTEGER PRIMARY KEY AUTOINCREMENT, company_id INTEGER DEFAULT 1, name TEXT NOT NULL, phone TEXT, gstin TEXT, email TEXT, address TEXT)''')
    
    try: cursor.execute("ALTER TABLE customers ADD COLUMN state TEXT DEFAULT ''")
    except: pass
    try: cursor.execute("ALTER TABLE customers ADD COLUMN state_code TEXT DEFAULT ''")
    except: pass
    try: cursor.execute("ALTER TABLE customers ADD COLUMN alias TEXT DEFAULT ''")
    except: pass

    cursor.execute('''CREATE TABLE IF NOT EXISTS inventory (id INTEGER PRIMARY KEY AUTOINCREMENT, company_id INTEGER DEFAULT 1, item_name TEXT NOT NULL, unit TEXT, rate REAL, description TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS stock (id INTEGER PRIMARY KEY AUTOINCREMENT, company_id INTEGER DEFAULT 1, item_name TEXT NOT NULL, quantity REAL, unit TEXT, market_price REAL, notes TEXT, added_date TEXT, transaction_type TEXT DEFAULT 'ADD')''')
    
    try: cursor.execute("ALTER TABLE stock ADD COLUMN is_deleted INTEGER DEFAULT 0")
    except: pass
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS invoices (id INTEGER PRIMARY KEY AUTOINCREMENT, company_id INTEGER DEFAULT 1, invoice_date TEXT, delivery_date TEXT, invoice_number TEXT, customer_name TEXT, place_of_service TEXT, subtotal REAL, cgst REAL, sgst REAL, igst REAL, total REAL, amount_paid REAL DEFAULT 0.0, balance_due REAL DEFAULT 0.0, status TEXT DEFAULT 'Unpaid', write_off REAL DEFAULT 0.0)''')
    
    try: cursor.execute("ALTER TABLE invoices ADD COLUMN is_deleted INTEGER DEFAULT 0")
    except: pass
    try: cursor.execute("ALTER TABLE invoices ADD COLUMN refund_mode TEXT DEFAULT 'none'")
    except: pass
    try: cursor.execute("ALTER TABLE invoices ADD COLUMN ca_submitted INTEGER DEFAULT 0")
    except: pass
    try: cursor.execute("ALTER TABLE invoices ADD COLUMN write_off REAL DEFAULT 0.0")
    except: pass
    try: cursor.execute("ALTER TABLE invoices ADD COLUMN ca_submission_date TEXT DEFAULT ''")
    except: pass

    cursor.execute('''CREATE TABLE IF NOT EXISTS invoice_items (id INTEGER PRIMARY KEY AUTOINCREMENT, invoice_id INTEGER, item_name TEXT, sac TEXT, rate REAL, quantity REAL, days REAL, amount REAL, FOREIGN KEY(invoice_id) REFERENCES invoices(id) ON DELETE CASCADE)''')
    
    try: cursor.execute("ALTER TABLE invoice_items ADD COLUMN days REAL DEFAULT 1.0")
    except: pass
    try: cursor.execute("ALTER TABLE invoice_items ADD COLUMN unit TEXT DEFAULT ''")
    except: pass

    cursor.execute('''CREATE TABLE IF NOT EXISTS purchases (id INTEGER PRIMARY KEY AUTOINCREMENT, company_id INTEGER DEFAULT 1, purchase_date TEXT, bill_number TEXT, vendor_name TEXT, subtotal REAL, cgst REAL, sgst REAL, igst REAL, total REAL, amount_paid REAL DEFAULT 0.0, balance_due REAL DEFAULT 0.0, status TEXT DEFAULT 'Unpaid', receipt_path TEXT, write_off REAL DEFAULT 0.0)''')
    
    try: cursor.execute("ALTER TABLE purchases ADD COLUMN is_deleted INTEGER DEFAULT 0")
    except: pass
    try: cursor.execute("ALTER TABLE purchases ADD COLUMN is_draft INTEGER DEFAULT 0")
    except: pass
    try: cursor.execute("ALTER TABLE purchases ADD COLUMN refund_mode TEXT DEFAULT 'none'")
    except: pass
    try: cursor.execute("ALTER TABLE purchases ADD COLUMN ca_submitted INTEGER DEFAULT 0")
    except: pass
    try: cursor.execute("ALTER TABLE purchases ADD COLUMN write_off REAL DEFAULT 0.0")
    except: pass
    try: cursor.execute("ALTER TABLE purchases ADD COLUMN ca_submission_date TEXT DEFAULT ''")
    except: pass

    cursor.execute('''CREATE TABLE IF NOT EXISTS purchase_items (id INTEGER PRIMARY KEY AUTOINCREMENT, purchase_id INTEGER, item_name TEXT, hsn TEXT, rate REAL, quantity REAL, amount REAL, FOREIGN KEY(purchase_id) REFERENCES purchases(id) ON DELETE CASCADE)''')
    
    try: cursor.execute("ALTER TABLE purchase_items ADD COLUMN destination TEXT")
    except: pass
    try: cursor.execute("ALTER TABLE purchase_items ADD COLUMN unit TEXT")
    except: pass
    try: cursor.execute("ALTER TABLE purchase_items ADD COLUMN gst_rate REAL")
    except: pass
    try: cursor.execute("ALTER TABLE purchase_items ADD COLUMN rate_inc_tax REAL")
    except: pass

    cursor.execute('''CREATE TABLE IF NOT EXISTS employees (id INTEGER PRIMARY KEY AUTOINCREMENT, company_id INTEGER DEFAULT 1, name TEXT, phone TEXT, alt_phone TEXT, role TEXT, salary REAL, join_date TEXT, photo_path TEXT)''')
    
    try: cursor.execute("ALTER TABLE employees ADD COLUMN document_path TEXT")
    except: pass
    try: cursor.execute("ALTER TABLE employees ADD COLUMN dob TEXT")
    except: pass
    try: cursor.execute("ALTER TABLE employees ADD COLUMN docs_json TEXT")
    except: pass
    try: cursor.execute("ALTER TABLE employees ADD COLUMN resign_date TEXT")
    except: pass
    try: cursor.execute("ALTER TABLE employees ADD COLUMN rejoin_date TEXT")
    except: pass
    try: cursor.execute("ALTER TABLE employees ADD COLUMN salary_history TEXT")
    except: pass
    try: cursor.execute("ALTER TABLE employees ADD COLUMN is_deleted INTEGER DEFAULT 0")
    except: pass
    try: cursor.execute("ALTER TABLE employees ADD COLUMN is_pinned INTEGER DEFAULT 0")
    except: pass

    cursor.execute('''CREATE TABLE IF NOT EXISTS employee_payments (id INTEGER PRIMARY KEY AUTOINCREMENT, emp_id INTEGER, pay_type TEXT, amount REAL, pay_date TEXT, notes TEXT)''')
    
    try: cursor.execute("ALTER TABLE employee_payments ADD COLUMN mode TEXT DEFAULT 'Cash'")
    except: pass
    try: cursor.execute("ALTER TABLE employee_payments ADD COLUMN attachment_path TEXT DEFAULT ''")
    except: pass

    cursor.execute('''CREATE TABLE IF NOT EXISTS general_expenses (id INTEGER PRIMARY KEY AUTOINCREMENT, company_id INTEGER DEFAULT 1, expense_date TEXT, title TEXT, category TEXT, amount REAL, notes TEXT)''')
    
    try: cursor.execute("ALTER TABLE general_expenses ADD COLUMN pay_method TEXT DEFAULT 'Cash'")
    except: pass
    try: cursor.execute("ALTER TABLE general_expenses ADD COLUMN status TEXT DEFAULT 'Paid'")
    except: pass
    try: cursor.execute("ALTER TABLE general_expenses ADD COLUMN receipt_path TEXT DEFAULT ''")
    except: pass
    
    # --- THE FIX: Eradicate the JSON Trap & Auto-Migrate Old Data ---
    try:
        cursor.execute("SELECT id, notes FROM general_expenses WHERE notes LIKE '{%'")
        for exp_id, notes_str in cursor.fetchall():
            try:
                j = json.loads(notes_str)
                pm = j.get("pay_method", "Cash")
                st = j.get("status", "Paid")
                rp = j.get("receipt", "")
                clean_note = j.get("note", "")
                cursor.execute("UPDATE general_expenses SET notes=?, pay_method=?, status=?, receipt_path=? WHERE id=?", (clean_note, pm, st, rp, exp_id))
            except: pass
    except: pass
    # -----------------------------------------------------------------

    cursor.execute("CREATE TABLE IF NOT EXISTS ui_settings (setting_key TEXT PRIMARY KEY, setting_value TEXT, company_id INTEGER DEFAULT 1)")
    try: cursor.execute("ALTER TABLE ui_settings ADD COLUMN company_id INTEGER DEFAULT 1")
    except: pass
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS party_payments (id INTEGER PRIMARY KEY AUTOINCREMENT, company_id INTEGER DEFAULT 1, party_name TEXT, pay_type TEXT, pay_date TEXT, amount REAL, mode TEXT, ref TEXT, notes TEXT, attachment_path TEXT)''')

    tables_to_patch = ['customers', 'inventory', 'stock', 'invoices', 'employees', 'general_expenses', 'purchases', 'party_payments', 'employee_payments', 'labour_attendance', 'labour_ledger']
    for table in tables_to_patch:
        try: cursor.execute(f"ALTER TABLE {table} ADD COLUMN company_id INTEGER DEFAULT 1")
        except: pass
        
    try: cursor.execute("ALTER TABLE party_payments ADD COLUMN attachment_path TEXT")
    except: pass

    cursor.execute('''CREATE TABLE IF NOT EXISTS labours (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        company_id INTEGER DEFAULT 1, 
        name TEXT NOT NULL, 
        phone TEXT, 
        address TEXT, 
        blood_type TEXT, 
        role TEXT, 
        photo_path TEXT, 
        doc_path TEXT,
        profile_type TEXT DEFAULT 'Individual',
        daily_rate REAL DEFAULT 0.0,
        skilled_rate REAL DEFAULT 0.0,
        unskilled_rate REAL DEFAULT 0.0,
        emergency_contact TEXT DEFAULT '',
        worker_id_str TEXT DEFAULT '',
        dob TEXT DEFAULT '',
        is_deleted INTEGER DEFAULT 0
    )''')
    try: cursor.execute("ALTER TABLE labours ADD COLUMN is_deleted INTEGER DEFAULT 0")
    except: pass
    try: cursor.execute("ALTER TABLE labours ADD COLUMN is_pinned INTEGER DEFAULT 0")
    except: pass

    cursor.execute('''CREATE TABLE IF NOT EXISTS labour_attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        labour_id INTEGER,
        date TEXT,
        hajira_count REAL DEFAULT 1.0,
        skilled_count REAL DEFAULT 0.0,
        unskilled_count REAL DEFAULT 0.0,
        notes TEXT,
        FOREIGN KEY(labour_id) REFERENCES labours(id) ON DELETE CASCADE
    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS labour_ledger (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        labour_id INTEGER,
        date TEXT,
        type TEXT, 
        amount REAL,
        description TEXT,
        FOREIGN KEY(labour_id) REFERENCES labours(id) ON DELETE CASCADE
    )''')
    
    try: cursor.execute("ALTER TABLE labour_ledger ADD COLUMN mode TEXT DEFAULT 'Cash'")
    except: pass
    try: cursor.execute("ALTER TABLE labour_ledger ADD COLUMN attachment_path TEXT DEFAULT ''")
    except: pass

    # --- THE FIX: Auto-Heal Historical Payment Vocabulary & Fix Inverted Sales Advances ---
    try:
        cursor.execute("UPDATE party_payments SET ref = 'Advance Wallet' WHERE ref IN ('Advance Credit (In)', 'Advance Debit (Out)')")
        cursor.execute("UPDATE party_payments SET ref = 'Refunded from Vendor' WHERE ref = 'Refunded from Supplier'")
        
        # Flips Sales Advances from 'make' back to 'receive', and Sales Refunds from 'receive' back to 'make'
        cursor.execute("UPDATE party_payments SET pay_type = 'receive' WHERE ref = 'Advance Wallet' AND pay_type = 'make' AND party_id IN (SELECT id FROM customers)")
        cursor.execute("UPDATE party_payments SET pay_type = 'make' WHERE ref = 'Refunded to Customer' AND pay_type = 'receive' AND party_id IN (SELECT id FROM customers)")
    except: pass

    # --- THE FIX: Option B Database Overhaul & Auto-Migration (Heals Existing Data) ---
    try: cursor.execute("ALTER TABLE invoices ADD COLUMN customer_id INTEGER")
    except: pass
    try: cursor.execute("ALTER TABLE purchases ADD COLUMN vendor_id INTEGER")
    except: pass
    try: cursor.execute("ALTER TABLE purchases ADD COLUMN internal_voucher TEXT")
    except: pass
    try: cursor.execute("ALTER TABLE purchases ADD COLUMN internal_date TEXT DEFAULT ''")
    except: pass
    try: cursor.execute("ALTER TABLE purchases ADD COLUMN eway_bill TEXT DEFAULT ''")
    except: pass
    try: cursor.execute("ALTER TABLE party_payments ADD COLUMN party_id INTEGER")
    except: pass

    try:
        # 1. Backfill missing internal_date on existing purchase bills from purchase_date
        cursor.execute("UPDATE purchases SET internal_date = purchase_date WHERE (internal_date IS NULL OR internal_date = '') AND purchase_date IS NOT NULL")

        # 2. Heal existing purchases where vendor_id was NULL or corrupted with text name (Bug 1)
        cursor.execute("SELECT id, company_id, vendor_name, receipt_path, vendor_id FROM purchases WHERE vendor_id IS NULL OR typeof(vendor_id) = 'text'")
        for p_id, c_id, v_name, r_path, raw_vid in cursor.fetchall():
            healed_vid = None
            if r_path:
                m = re.search(r'_ID_(\d+)', str(r_path))
                if m:
                    healed_vid = int(m.group(1))
            if not healed_vid and v_name:
                cursor.execute("SELECT id FROM customers WHERE LOWER(name)=LOWER(?) AND company_id=? LIMIT 1", (str(v_name).strip(), c_id))
                crow = cursor.fetchone()
                if crow:
                    healed_vid = int(crow[0])
            if healed_vid:
                cursor.execute("UPDATE purchases SET vendor_id=? WHERE id=?", (healed_vid, p_id))

        # 3. Heal existing invoices & party_payments where customer_id / party_id is NULL or text
        cursor.execute("UPDATE invoices SET customer_id = (SELECT id FROM customers WHERE LOWER(customers.name) = LOWER(invoices.customer_name) AND customers.company_id = invoices.company_id LIMIT 1) WHERE (customer_id IS NULL OR typeof(customer_id) = 'text') AND customer_name IS NOT NULL")
        cursor.execute("UPDATE party_payments SET party_id = (SELECT id FROM customers WHERE LOWER(customers.name) = LOWER(party_payments.party_name) AND customers.company_id = party_payments.company_id LIMIT 1) WHERE (party_id IS NULL OR typeof(party_id) = 'text') AND party_name IS NOT NULL")

        # 4. Heal existing customers created via Purchase 'Add Party' modal (Bug 5 JSON keys)
        cursor.execute("SELECT id, address FROM customers WHERE address LIKE '{%'")
        for cid_row, raw_addr in cursor.fetchall():
            try:
                j = json.loads(raw_addr)
                changed = False
                if "opening_balance_type" in j and "ob_type" not in j:
                    j["ob_type"] = "They Owe You (Dr)" if j["opening_balance_type"] == "Dr" else "You Owe Them (Cr)"
                    changed = True
                if "payable_days" in j and "payable_terms" not in j:
                    j["payable_terms"] = str(j["payable_days"])
                    changed = True
                if "receivable_days" in j and "receivable_terms" not in j:
                    j["receivable_terms"] = str(j["receivable_days"])
                    changed = True
                if changed:
                    cursor.execute("UPDATE customers SET address=? WHERE id=?", (json.dumps(j), cid_row))
            except Exception:
                pass
    except Exception:
        pass
    # ----------------------------------------------------------------------------------

    conn.commit(); conn.close()

def add_labour(name, phone, address, blood_type, role, photo_path, doc_path, profile_type="Individual", daily_rate=0.0, skilled_rate=0.0, unskilled_rate=0.0, emergency_contact="", worker_id_str="", dob=""):
    conn = get_connection(); cursor = conn.cursor()
    cursor.execute('INSERT INTO labours (company_id, name, phone, address, blood_type, role, photo_path, doc_path, profile_type, daily_rate, skilled_rate, unskilled_rate, emergency_contact, worker_id_str, dob) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', (ACTIVE_COMPANY_ID, name, phone, address, blood_type, role, photo_path, doc_path, profile_type, daily_rate, skilled_rate, unskilled_rate, emergency_contact, worker_id_str, dob))
    new_id = cursor.lastrowid
    conn.commit(); conn.close()
    return new_id

def update_labour(labour_id, name, phone, address, blood_type, role, photo_path, doc_path, profile_type="Individual", daily_rate=0.0, skilled_rate=0.0, unskilled_rate=0.0, emergency_contact="", worker_id_str="", dob=""):
    conn = get_connection(); cursor = conn.cursor()
    cursor.execute('UPDATE labours SET name=?, phone=?, address=?, blood_type=?, role=?, photo_path=?, doc_path=?, profile_type=?, daily_rate=?, skilled_rate=?, unskilled_rate=?, emergency_contact=?, worker_id_str=?, dob=? WHERE id=? AND company_id=?', (name, phone, address, blood_type, role, photo_path, doc_path, profile_type, daily_rate, skilled_rate, unskilled_rate, emergency_contact, worker_id_str, dob, labour_id, ACTIVE_COMPANY_ID))
    conn.commit(); conn.close()

def update_labour_daily_rate(labour_id, daily_rate):
    conn = get_connection(); cursor = conn.cursor()
    cursor.execute('UPDATE labours SET daily_rate=? WHERE id=? AND company_id=?', (daily_rate, labour_id, ACTIVE_COMPANY_ID))
    conn.commit(); conn.close()

def get_all_labours():
    conn = get_connection(); cursor = conn.cursor()
    cursor.execute('SELECT * FROM labours WHERE company_id = ? AND COALESCE(is_deleted, 0) = 0 ORDER BY name ASC', (ACTIVE_COMPANY_ID,))
    rows = cursor.fetchall(); conn.close(); return rows

def get_labour(labour_id):
    conn = get_connection(); cursor = conn.cursor()
    cursor.execute('SELECT * FROM labours WHERE id = ? AND company_id = ?', (labour_id, ACTIVE_COMPANY_ID))
    row = cursor.fetchone(); conn.close(); return row

def get_labour_dict(labour_id):
    conn = get_connection(); cursor = conn.cursor()
    cursor.execute("SELECT * FROM labours WHERE id=? AND company_id=?", (labour_id, ACTIVE_COMPANY_ID))
    row = cursor.fetchone()
    if not row: 
        conn.close()
        return None
    cols = [col[0] for col in cursor.description]
    conn.close()
    return dict(zip(cols, row))

def delete_labour(labour_id):
    conn = get_connection(); cursor = conn.cursor()
    cursor.execute('UPDATE labours SET is_deleted=1 WHERE id = ? AND company_id = ?', (labour_id, ACTIVE_COMPANY_ID))
    conn.commit(); conn.close()

def restore_deleted_labour(labour_id):
    conn = get_connection(); c = conn.cursor()
    c.execute("UPDATE labours SET is_deleted=0 WHERE id=? AND company_id=?", (labour_id, ACTIVE_COMPANY_ID))
    conn.commit(); c.close()

def get_all_labour_id_strings():
    conn = get_connection(); c = conn.cursor()
    c.execute("SELECT id, worker_id_str FROM labours WHERE company_id=? AND COALESCE(is_deleted, 0) = 0", (ACTIVE_COMPANY_ID,))
    existing = []
    for r in c.fetchall():
        eff_id = str(r[1]).strip() if str(r[1]).strip() else f"LAB-{int(r[0]):04d}"
        existing.append((r[0], eff_id.lower()))
    conn.close()
    return existing

def check_labour_attendance_exists(labour_id, check_date):
    conn = get_connection(); c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM labour_attendance WHERE labour_id=? AND date=? AND labour_id IN (SELECT id FROM labours WHERE company_id=?)", (labour_id, check_date, ACTIVE_COMPANY_ID))
    count = c.fetchone()[0]
    conn.close(); return count > 0

def add_labour_attendance(labour_id, date, hajira_count, skilled_count, unskilled_count, notes):
    conn = get_connection(); cursor = conn.cursor()
    cursor.execute('INSERT INTO labour_attendance (labour_id, date, hajira_count, skilled_count, unskilled_count, notes, company_id) VALUES (?, ?, ?, ?, ?, ?, ?)', (labour_id, date, hajira_count, skilled_count, unskilled_count, notes, ACTIVE_COMPANY_ID))
    new_id = cursor.lastrowid
    conn.commit(); conn.close()
    return new_id
    
def delete_labour_attendance(att_id):
    conn = get_connection(); cursor = conn.cursor()
    cursor.execute('DELETE FROM labour_attendance WHERE id = ? AND labour_id IN (SELECT id FROM labours WHERE company_id = ?)', (att_id, ACTIVE_COMPANY_ID))
    conn.commit(); conn.close()

def get_all_labour_payments_with_names():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT ll.id, ll.date, l.name, ll.type, ll.amount, ll.description 
        FROM labour_ledger ll 
        LEFT JOIN labours l ON ll.labour_id = l.id 
        WHERE l.company_id = ? AND ll.type IN ('Payment', 'Advance', 'Bonus')
    ''', (ACTIVE_COMPANY_ID,))
    rows = cursor.fetchall()
    conn.close()
    return rows

def add_labour_ledger_entry(labour_id, date, entry_type, amount, description, mode="Cash", attachment_path=""):
    conn = get_connection(); cursor = conn.cursor()
    cursor.execute('INSERT INTO labour_ledger (labour_id, date, type, amount, description, mode, attachment_path, company_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)', (labour_id, date, entry_type, amount, description, mode, attachment_path, ACTIVE_COMPANY_ID))
    new_id = cursor.lastrowid
    conn.commit(); conn.close()
    return new_id

def get_labour_ledger(labour_id):
    conn = get_connection(); cursor = conn.cursor()
    cursor.execute('SELECT id, date, type, amount, description FROM labour_ledger WHERE labour_id = ? ORDER BY date ASC, id ASC', (labour_id,))
    rows = cursor.fetchall(); conn.close(); return rows

def get_labour_ledger_record(entry_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, labour_id, date, type, amount, description, mode, attachment_path FROM labour_ledger WHERE id = ?', (entry_id,))
    row = cursor.fetchone()
    conn.close()
    return row

# --- THE FIX: Secure MVC Wrappers for Labour UI Files ---
def get_labour_daily_rate(labour_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT daily_rate FROM labours WHERE id=? AND company_id=?", (labour_id, ACTIVE_COMPANY_ID))
    res = c.fetchone()
    conn.close()
    return float(res[0]) if res and res[0] else 0.0

def get_labour_attendance_history(labour_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT date, hajira_count FROM labour_attendance WHERE labour_id IN (SELECT id FROM labours WHERE id=? AND company_id=?)", (labour_id, ACTIVE_COMPANY_ID))
    rows = c.fetchall()
    conn.close()
    return rows

def get_labour_payment_history(labour_id):
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute("SELECT id, date, type, amount, description, mode, attachment_path FROM labour_ledger WHERE labour_id IN (SELECT id FROM labours WHERE id=? AND company_id=?) AND type IN ('Payment', 'Advance', 'Bonus') ORDER BY id DESC", (labour_id, ACTIVE_COMPANY_ID))
        rows = c.fetchall()
    except Exception:
        c.execute("SELECT id, date, type, amount, description FROM labour_ledger WHERE labour_id IN (SELECT id FROM labours WHERE id=? AND company_id=?) AND type IN ('Payment', 'Advance', 'Bonus') ORDER BY id DESC", (labour_id, ACTIVE_COMPANY_ID))
        temp_rows = c.fetchall()
        rows = []
        import re
        for r in temp_rows:
            m = "Cash"
            m_m = re.search(r'\((.*?)\)', str(r[4]))
            if m_m: m = m_m.group(1)
            rows.append((r[0], r[1], r[2], r[3], r[4], m, ""))
    conn.close()
    return rows
# --------------------------------------------------------

def restore_labour_ledger_record(row_data):
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT id FROM labours WHERE id=? AND company_id=?", (row_data[1], ACTIVE_COMPANY_ID))
    if cursor.fetchone():
        cursor.execute('INSERT INTO labour_ledger (id, labour_id, date, type, amount, description, mode, attachment_path, company_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)', list(row_data[:8]) + [ACTIVE_COMPANY_ID])
        
        # --- THE FIX: Cleaned up ghost math for purely Individual shifts ---
        if row_data[3] == 'Wage':
            desc = str(row_data[5])
            h_val = 0.0
            
            import re
            m1 = re.search(r'([\d\.]+)\s*Nos\.\s*Day Shift', desc)
            m2 = re.search(r'([\d\.]+)\s*Nos\.\s*Night Shift', desc)
            if m1: h_val += float(m1.group(1))
            if m2: h_val += float(m2.group(1))
            
            m_hajira = re.search(r'Auto-Wage:\s*([\d\.]+)\s*Hajira', desc)
            if m_hajira: h_val += float(m_hajira.group(1))
            
            if h_val == 0.0: h_val = 1.0 
                
            base_desc = re.sub(r'\s*\([^)]*\)$', '', desc).strip()
            cursor.execute('INSERT INTO labour_attendance (labour_id, date, hajira_count, skilled_count, unskilled_count, notes, company_id) VALUES (?, ?, ?, ?, ?, ?, ?)', (row_data[1], row_data[2], h_val, 0.0, 0.0, base_desc, ACTIVE_COMPANY_ID))
        # ---------------------------------------------------------
        conn.commit()
    conn.close()

# --- THE FIX: Deep Math Update for Wage Entries ---
def update_labour_wage_entry(ledg_id, labour_id, old_date, new_date, new_amt, new_desc, new_base_desc, new_hajira):
    conn = get_connection(); cursor = conn.cursor()
    
    # 1. Update Financial Ledger
    cursor.execute("UPDATE labour_ledger SET date=?, amount=?, description=? WHERE id=? AND labour_id IN (SELECT id FROM labours WHERE id=? AND company_id=?)", (new_date, new_amt, new_desc, ledg_id, labour_id, ACTIVE_COMPANY_ID))
    
    # 2. Update Attendance Log (Finds the most recent shift on the OLD date and moves it to the NEW date)
    cursor.execute("SELECT id FROM labour_attendance WHERE labour_id=? AND date=? ORDER BY id DESC LIMIT 1", (labour_id, old_date))
    att_row = cursor.fetchone()
    if att_row:
        cursor.execute("UPDATE labour_attendance SET date=?, hajira_count=?, notes=? WHERE id=?", (new_date, new_hajira, new_base_desc, att_row[0]))
    else:
        # Recreate it if it was accidentally deleted
        cursor.execute('INSERT INTO labour_attendance (labour_id, date, hajira_count, skilled_count, unskilled_count, notes, company_id) VALUES (?, ?, ?, ?, ?, ?, ?)', (labour_id, new_date, new_hajira, 0.0, 0.0, new_base_desc, ACTIVE_COMPANY_ID))
        
    conn.commit(); conn.close()
# --------------------------------------------------

def delete_labour_ledger_entry(entry_id):
    conn = get_connection()
    cursor = conn.cursor()
    
    # --- THE FIX: Sync Attendance Deletion ---
    cursor.execute("SELECT type, date, description, labour_id FROM labour_ledger WHERE id=?", (entry_id,))
    ledg_row = cursor.fetchone()
    if ledg_row and ledg_row[0] == 'Wage':
        cursor.execute("DELETE FROM labour_attendance WHERE id = (SELECT id FROM labour_attendance WHERE labour_id=? AND date=? AND notes=? ORDER BY id DESC LIMIT 1)", (ledg_row[3], ledg_row[1], ledg_row[2]))
    # -----------------------------------------
    
    cursor.execute("SELECT attachment_path FROM labour_ledger WHERE id = ? AND labour_id IN (SELECT id FROM labours WHERE company_id = ?)", (entry_id, ACTIVE_COMPANY_ID))
    row = cursor.fetchone()
    
    if row and row[0] and os.path.exists(row[0]):
        try:
            os.remove(row[0])
        except Exception:
            pass
            
    cursor.execute('DELETE FROM labour_ledger WHERE id = ? AND labour_id IN (SELECT id FROM labours WHERE company_id = ?)', (entry_id, ACTIVE_COMPANY_ID))
    conn.commit()
    conn.close()
    
def update_labour_payment_proof(pay_id, attachment_path):
    conn = get_connection(); c = conn.cursor()
    c.execute("UPDATE labour_ledger SET attachment_path=? WHERE id=? AND labour_id IN (SELECT id FROM labours WHERE company_id = ?)", (attachment_path, pay_id, ACTIVE_COMPANY_ID))
    conn.commit(); conn.close()

# --- THE FIX: O(1) Bulk Ledger Calculator ---
def get_all_labour_balances():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT labour_id, type, amount, description FROM labour_ledger WHERE labour_id IN (SELECT id FROM labours WHERE company_id=?) ORDER BY labour_id, date ASC, id ASC", (ACTIVE_COMPANY_ID,))
    rows = cursor.fetchall()
    conn.close()
    
    balances = {}
    for l_id, e_type, e_amt, e_desc in rows:
        if l_id not in balances:
            balances[l_id] = {"wallet": 0.0, "payable": 0.0}
            
        b = balances[l_id]
        if e_type == 'Wage':
            b["payable"] += e_amt
        elif e_type == 'Advance':
            if e_amt < 0: b["wallet"] += abs(e_amt)
            else:
                b["wallet"] -= abs(e_amt)
                if b["wallet"] < 0: b["wallet"] = 0.0
        elif e_type == 'Payment':
            if e_desc and ("Wallet" in e_desc or "(Out)" in e_desc or "Advance Out" in e_desc):
                b["wallet"] += e_amt
                b["payable"] += e_amt
                if b["wallet"] < 0:
                    b["wallet"] = 0.0
            else:
                b["payable"] += e_amt
                
    return balances
# --------------------------------------------

def get_company(company_id): 
    conn = get_connection(); cursor = conn.cursor()
    cursor.execute('SELECT id, name, name_secondary, address, phone, phone2, phone3, email, gst_toggle, gstin, logo_path, header_layout, logo_size, logo_shape, template_json, security_pin, is_pinned, state, state_code, business_type, purchase_template_json FROM company WHERE id = ?', (company_id,))
    row = cursor.fetchone(); conn.close(); return row

def add_company(name, name_sec, address, phone, phone2, phone3, email, gst_toggle, gstin, logo_path, layout, size, shape, template_json, security_pin=""):
    conn = get_connection(); cursor = conn.cursor()
    cursor.execute('INSERT INTO company (name, name_secondary, address, phone, phone2, phone3, email, gst_toggle, gstin, logo_path, header_layout, logo_size, logo_shape, template_json, security_pin) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', (name, name_sec, address, phone, phone2, phone3, email, gst_toggle, gstin, logo_path, layout, size, shape, template_json, security_pin))
    new_id = cursor.lastrowid
    conn.commit(); conn.close()
    return new_id
    
def update_company(company_id, name, name_sec, address, phone, phone2, phone3, email, gst_toggle, gstin, logo_path, layout, size, shape, template_json, security_pin=""):
    conn = get_connection(); cursor = conn.cursor()
    cursor.execute('UPDATE company SET name=?, name_secondary=?, address=?, phone=?, phone2=?, phone3=?, email=?, gst_toggle=?, gstin=?, logo_path=?, header_layout=?, logo_size=?, logo_shape=?, template_json=?, security_pin=? WHERE id=?', (name, name_sec, address, phone, phone2, phone3, email, gst_toggle, gstin, logo_path, layout, size, shape, template_json, security_pin, company_id))
    conn.commit(); conn.close()

def update_company_tax_profile(company_id, state, state_code, business_type):
    conn = get_connection(); cursor = conn.cursor()
    cursor.execute('UPDATE company SET state=?, state_code=?, business_type=? WHERE id=?', (state, state_code, business_type, company_id))
    conn.commit(); conn.close()

def update_customer_tax_profile(customer_id, state, state_code):
    conn = get_connection(); cursor = conn.cursor()
    cursor.execute('UPDATE customers SET state=?, state_code=? WHERE id=? AND company_id=?', (state, state_code, customer_id, ACTIVE_COMPANY_ID))
    conn.commit(); conn.close()

def delete_company(company_id):
    conn = get_connection(); cursor = conn.cursor()
    cursor.execute('PRAGMA foreign_keys = ON')
    
    try:
        import shutil
        import re
        cursor.execute('SELECT name FROM company WHERE id = ?', (company_id,))
        comp_row = cursor.fetchone()
        comp_name = comp_row[0] if comp_row else f"Company_{company_id}"
        safe_comp = re.sub(r'[\\/*?:"<>|]', "", comp_name).strip()
        
        # --- THE FIX: Check if another company shares this exact name before deleting folders! ---
        cursor.execute('SELECT COUNT(id) FROM company WHERE name = ? AND id != ?', (comp_name, company_id))
        twin_count = cursor.fetchone()[0]
        
        if twin_count == 0:
            vault_dir = os.path.join(BASE_DIR, "Vault", safe_comp)
            purch_dir = os.path.join(BASE_DIR, "purchase_payment_receipts", safe_comp)
            inv_dir = os.path.join(BASE_DIR, "invoice_payment_receipts", safe_comp)
            vendor_dir = os.path.join(BASE_DIR, "vendor_bills", safe_comp)
            emp_dir = os.path.join(BASE_DIR, "Employees", safe_comp)
            lab_dir = os.path.join(BASE_DIR, "Labours", safe_comp)
            
            for d in [vault_dir, purch_dir, inv_dir, vendor_dir, emp_dir, lab_dir]:
                if os.path.exists(d): shutil.rmtree(d, ignore_errors=True)
                
        # (These JSON files use company_id, so they never overlap and are always safe to delete)
        subj_cust = os.path.join(BASE_DIR, f"subject_custom_{company_id}.json")
        subj_bl = os.path.join(BASE_DIR, f"subject_blacklist_{company_id}.json")
        for f in [subj_cust, subj_bl]:
            if os.path.exists(f): os.remove(f)
        # ---------------------------------------------------------------------------------------
    except: pass

    # --- THE FIX: Explicitly delete child items to prevent SQLite orphans ---
    cursor.execute('DELETE FROM invoice_items WHERE invoice_id IN (SELECT id FROM invoices WHERE company_id = ?)', (company_id,))
    cursor.execute('DELETE FROM purchase_items WHERE purchase_id IN (SELECT id FROM purchases WHERE company_id = ?)', (company_id,))
    cursor.execute('DELETE FROM employee_payments WHERE emp_id IN (SELECT id FROM employees WHERE company_id = ?)', (company_id,))
    cursor.execute('DELETE FROM labour_attendance WHERE labour_id IN (SELECT id FROM labours WHERE company_id = ?)', (company_id,))
    cursor.execute('DELETE FROM labour_ledger WHERE labour_id IN (SELECT id FROM labours WHERE company_id = ?)', (company_id,))
    
    tables = ['customers', 'inventory', 'stock', 'invoices', 'purchases', 'employees', 'general_expenses', 'party_payments', 'labours', 'ui_settings', 'company']
    for table in tables:
        cursor.execute(f'DELETE FROM {table} WHERE {"id" if table == "company" else "company_id"} = ?', (company_id,))
    
    conn.commit(); conn.close()

def toggle_company_pin_status(company_id, is_pinned):
    conn = get_connection(); cursor = conn.cursor()
    cursor.execute('UPDATE company SET is_pinned=? WHERE id=?', (is_pinned, company_id))
    conn.commit(); conn.close()

def get_all_companies(sort_by="name ASC", ignore_permissions=False): 
    conn = get_connection(); cursor = conn.cursor()
    cursor.execute(f'SELECT id, name, name_secondary, address, phone, phone2, phone3, email, gst_toggle, gstin, logo_path, header_layout, logo_size, logo_shape, template_json, security_pin, is_pinned, state, state_code, business_type, purchase_template_json FROM company ORDER BY is_pinned DESC, {sort_by}')
    rows = cursor.fetchall(); conn.close()
    
    if not ignore_permissions and str(ACTIVE_USER_ID) != "1":
        perms = get_user_permissions(ACTIVE_USER_ID)
        allowed_comps = perms.get("companies", "all")
        if isinstance(allowed_comps, list):
            allowed_set = {int(cid) for cid in allowed_comps}
            rows = [r for r in rows if int(r[0]) in allowed_set]
            
    return rows

def add_customer(name, alias, phone, gstin, email, address): conn = get_connection(); cursor = conn.cursor(); cursor.execute('INSERT INTO customers (company_id, name, alias, phone, gstin, email, address) VALUES (?, ?, ?, ?, ?, ?, ?)', (ACTIVE_COMPANY_ID, name, alias, phone, gstin, email, address)); conn.commit(); conn.close()
def update_customer(customer_id, name, alias, phone, gstin, email, address):
    conn = get_connection(); cursor = conn.cursor()
    
    # --- THE FIX: Relational Name-Change Fracture ---
    cursor.execute('SELECT name FROM customers WHERE id=? AND company_id=?', (customer_id, ACTIVE_COMPANY_ID))
    old_row = cursor.fetchone()
    old_name = old_row[0] if old_row else None
    
    cursor.execute('UPDATE customers SET name=?, alias=?, phone=?, gstin=?, email=?, address=? WHERE id=? AND company_id=?', (name, alias, phone, gstin, email, address, customer_id, ACTIVE_COMPANY_ID))
    
    if old_name and old_name != name:
        # --- THE FIX: Visual updates now rely strictly on the ID instead of text mapping! ---
        cursor.execute('UPDATE invoices SET customer_name=? WHERE customer_id=? AND company_id=?', (name, customer_id, ACTIVE_COMPANY_ID))
        cursor.execute('UPDATE purchases SET vendor_name=? WHERE vendor_id=? AND company_id=?', (name, customer_id, ACTIVE_COMPANY_ID))
        cursor.execute('UPDATE party_payments SET party_name=? WHERE party_id=? AND company_id=?', (name, customer_id, ACTIVE_COMPANY_ID))
        # ------------------------------------------------------------------------------------
        
    conn.commit(); conn.close()

def get_all_customers(): conn = get_connection(); cursor = conn.cursor(); cursor.execute('SELECT id, name, phone, gstin, email, address, state, state_code, alias, company_id FROM customers WHERE company_id = ?', (ACTIVE_COMPANY_ID,)); rows = cursor.fetchall(); conn.close(); return rows
def get_customer(customer_id): conn = get_connection(); cursor = conn.cursor(); cursor.execute('SELECT id, name, phone, gstin, email, address, state, state_code, alias, company_id FROM customers WHERE id = ? AND company_id = ?', (customer_id, ACTIVE_COMPANY_ID)); row = cursor.fetchone(); conn.close(); return row
def get_customer_by_name(name): conn = get_connection(); cursor = conn.cursor(); cursor.execute('SELECT id, name, phone, gstin, email, address, state, state_code, alias, company_id FROM customers WHERE name = ? AND company_id = ?', (name, ACTIVE_COMPANY_ID)); row = cursor.fetchone(); conn.close(); return row
def delete_customer(customer_id): conn = get_connection(); cursor = conn.cursor(); cursor.execute('DELETE FROM customers WHERE id = ? AND company_id = ?', (customer_id, ACTIVE_COMPANY_ID)); conn.commit(); conn.close()

def add_inventory(item_name, unit, rate, description): 
    conn = get_connection(); cursor = conn.cursor()
    cursor.execute('INSERT INTO inventory (company_id, item_name, unit, rate, description) VALUES (?, ?, ?, ?, ?)', (ACTIVE_COMPANY_ID, item_name, unit, rate, description))
    last_id = cursor.lastrowid
    conn.commit(); conn.close()
    return last_id

def upsert_inventory(name, unit, rate, description, item_id=None):
    try:
        conn = get_connection(); c = conn.cursor()
        c.execute("SELECT id FROM inventory WHERE LOWER(item_name)=LOWER(?) AND company_id=?", (name.strip(), ACTIVE_COMPANY_ID))
        existing = c.fetchone()
        
        if existing:
            existing_id = existing[0]
            if item_id and str(item_id) != str(existing_id):
                c.execute("UPDATE inventory SET item_name=?, unit=?, rate=?, description=? WHERE id=? AND company_id=?", (name.strip(), unit, rate, description, existing_id, ACTIVE_COMPANY_ID))
                c.execute("DELETE FROM inventory WHERE id=? AND company_id=?", (item_id, ACTIVE_COMPANY_ID))
            else:
                c.execute("UPDATE inventory SET item_name=?, unit=?, rate=?, description=? WHERE id=? AND company_id=?", (name.strip(), unit, rate, description, existing_id, ACTIVE_COMPANY_ID))
        else:
            if item_id:
                c.execute("UPDATE inventory SET item_name=?, unit=?, rate=?, description=? WHERE id=? AND company_id=?", (name.strip(), unit, rate, description, item_id, ACTIVE_COMPANY_ID))
            else:
                c.execute("INSERT INTO inventory (company_id, item_name, unit, rate, description) VALUES (?, ?, ?, ?, ?)", (ACTIVE_COMPANY_ID, name.strip(), unit, rate, description))
        
        conn.commit(); conn.close()
        return True
    except Exception as e:
        print(e)
        return False

def get_all_inventory(): conn = get_connection(); cursor = conn.cursor(); cursor.execute('SELECT id, item_name, unit, rate, description, company_id FROM inventory WHERE company_id = ?', (ACTIVE_COMPANY_ID,)); rows = cursor.fetchall(); conn.close(); return rows
def delete_inventory(item_id): conn = get_connection(); cursor = conn.cursor(); cursor.execute('DELETE FROM inventory WHERE id = ? AND company_id = ?', (item_id, ACTIVE_COMPANY_ID)); conn.commit(); conn.close()

def add_stock(item_name, quantity, unit, market_price, notes, added_date, transaction_type='ADD'): 
    conn = get_connection(); cursor = conn.cursor()
    cursor.execute('INSERT INTO stock (company_id, item_name, quantity, unit, market_price, notes, added_date, transaction_type) VALUES (?, ?, ?, ?, ?, ?, ?, ?)', (ACTIVE_COMPANY_ID, item_name, quantity, unit, market_price, notes, added_date, transaction_type))
    conn.commit(); conn.close()

def update_stock_item_details(old_name, new_name, new_unit):
    conn = get_connection(); cursor = conn.cursor()
    cursor.execute("UPDATE stock SET item_name=?, unit=? WHERE item_name=? AND company_id=?", (new_name, new_unit, old_name, ACTIVE_COMPANY_ID))
    conn.commit(); conn.close()

def update_stock_notes(record_id, notes):
    conn = get_connection(); cursor = conn.cursor()
    cursor.execute("UPDATE stock SET notes=? WHERE id=? AND company_id=?", (notes, record_id, ACTIVE_COMPANY_ID))
    conn.commit(); conn.close()

def check_stock_name_exists(item_name):
    conn = get_connection(); cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM stock WHERE LOWER(item_name)=LOWER(?) AND company_id=? LIMIT 1", (item_name, ACTIVE_COMPANY_ID))
    exists = cursor.fetchone() is not None
    conn.close(); return exists

def get_stock_record(record_id):
    conn = get_connection(); cursor = conn.cursor()
    cursor.execute("SELECT id, company_id, item_name, quantity, unit, market_price, notes, added_date, transaction_type FROM stock WHERE id=? AND company_id=?", (record_id, ACTIVE_COMPANY_ID))
    row = cursor.fetchone(); conn.close(); return row

def get_stock_records_by_name(item_name):
    conn = get_connection(); cursor = conn.cursor()
    cursor.execute("SELECT id, company_id, item_name, quantity, unit, market_price, notes, added_date, transaction_type FROM stock WHERE item_name=? AND company_id=?", (item_name, ACTIVE_COMPANY_ID))
    rows = cursor.fetchall(); conn.close(); return rows

def restore_stock_records(records):
    conn = get_connection(); cursor = conn.cursor()
    for r in records:
        # --- THE FIX: Soft-restore instead of crashing on duplicate Primary Key IDs ---
        cursor.execute("UPDATE stock SET is_deleted=0 WHERE id=? AND company_id=?", (r[0], ACTIVE_COMPANY_ID))
    conn.commit(); conn.close()

def get_grouped_stock(): 
    conn = get_connection(); cursor = conn.cursor()
    cursor.execute('SELECT item_name, SUM(CASE WHEN transaction_type="ADD" THEN quantity ELSE 0 END) as added_qty, SUM(CASE WHEN transaction_type="LOSS" THEN quantity ELSE 0 END) as loss_qty, SUM(CASE WHEN transaction_type="SOLD" THEN quantity ELSE 0 END) as sold_qty, SUM(CASE WHEN transaction_type="ADD" THEN quantity WHEN transaction_type="LOSS" THEN -quantity WHEN transaction_type="SOLD" THEN -quantity ELSE 0 END) as net_qty, unit, SUM(CASE WHEN transaction_type="ADD" THEN quantity * market_price WHEN transaction_type="LOSS" THEN -(quantity * market_price) WHEN transaction_type="SOLD" THEN -(quantity * market_price) ELSE 0 END) as net_val, SUM(CASE WHEN transaction_type="LOSS" THEN quantity * market_price ELSE 0 END) as loss_val, SUM(CASE WHEN transaction_type="SOLD" THEN quantity * market_price ELSE 0 END) as sold_val FROM stock WHERE company_id = ? AND COALESCE(is_deleted, 0) = 0 GROUP BY item_name, unit', (ACTIVE_COMPANY_ID,))
    rows = cursor.fetchall(); conn.close(); return rows

def get_all_stock_records_raw():
    conn = get_connection(); cursor = conn.cursor()
    cursor.execute('SELECT item_name, quantity, unit, market_price, transaction_type, notes FROM stock WHERE company_id = ? AND COALESCE(is_deleted, 0) = 0 ORDER BY id ASC', (ACTIVE_COMPANY_ID,))
    rows = cursor.fetchall(); conn.close(); return rows

def get_stock_history(item_name): 
    conn = get_connection(); cursor = conn.cursor()
    cursor.execute('SELECT id, quantity, market_price, added_date, notes, transaction_type FROM stock WHERE item_name = ? AND company_id = ? AND COALESCE(is_deleted, 0) = 0 ORDER BY id DESC', (item_name, ACTIVE_COMPANY_ID))
    rows = cursor.fetchall(); conn.close(); return rows

def get_stock_history_asc(item_name):
    conn = get_connection(); cursor = conn.cursor()
    cursor.execute('SELECT id, quantity, market_price, added_date, notes, transaction_type FROM stock WHERE item_name = ? AND company_id = ? AND COALESCE(is_deleted, 0) = 0 ORDER BY id ASC', (item_name, ACTIVE_COMPANY_ID))
    rows = cursor.fetchall(); conn.close(); return rows

def get_latest_stock_info(item_name): 
    conn = get_connection(); cursor = conn.cursor()
    cursor.execute('SELECT unit, market_price, notes FROM stock WHERE item_name = ? AND transaction_type="ADD" AND company_id = ? AND COALESCE(is_deleted, 0) = 0 ORDER BY id DESC LIMIT 1', (item_name, ACTIVE_COMPANY_ID))
    row = cursor.fetchone(); conn.close(); return row

def delete_stock_by_name(item_name): conn = get_connection(); cursor = conn.cursor(); cursor.execute('UPDATE stock SET is_deleted=1 WHERE item_name = ? AND company_id = ?', (item_name, ACTIVE_COMPANY_ID)); conn.commit(); conn.close()
def delete_single_stock_record(record_id): conn = get_connection(); cursor = conn.cursor(); cursor.execute('UPDATE stock SET is_deleted=1 WHERE id = ? AND company_id = ?', (record_id, ACTIVE_COMPANY_ID)); conn.commit(); conn.close()



def generate_invoice_number(): conn = get_connection(); cursor = conn.cursor(); year = datetime.datetime.now().year; cursor.execute('SELECT COUNT(*) FROM invoices WHERE invoice_number LIKE ? AND company_id = ? AND is_deleted = 0', (f'INV-{year}-%', ACTIVE_COMPANY_ID)); count = cursor.fetchone()[0] + 1; conn.close(); return f"INV-{year}-{count:04d}"

# --- THE FIX: Inject cust_id into the Save Engine ---
def save_invoice(inv_date, del_date, inv_num, cust_name, place, sub, cgst, sgst, igst, total, items, status='Unpaid', cust_id=None):
    conn = get_connection(); cursor = conn.cursor()
    if status != 'Draft':
        cursor.execute("DELETE FROM invoices WHERE invoice_number = ? AND company_id = ? AND is_deleted = 1", (inv_num, ACTIVE_COMPANY_ID))
    cursor.execute('''INSERT INTO invoices (company_id, invoice_date, delivery_date, invoice_number, customer_name, customer_id, place_of_service, subtotal, cgst, sgst, igst, total, amount_paid, balance_due, status, write_off, is_deleted) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0.0, ?, ?, 0.0, 0)''', (ACTIVE_COMPANY_ID, inv_date, del_date, inv_num, cust_name, cust_id, place, sub, cgst, sgst, igst, total, total, status))
    invoice_id = cursor.lastrowid
    for item in items: 
        unit_val = item[6] if len(item) > 6 else ""
        cursor.execute('INSERT INTO invoice_items (invoice_id, item_name, sac, rate, quantity, days, amount, unit) VALUES (?, ?, ?, ?, ?, ?, ?, ?)', (invoice_id, item[0], item[1], item[2], item[3], item[4], item[5], unit_val))
    conn.commit(); conn.close()
# ----------------------------------------------------

def internal_update_wallet(cursor, company_id, name, amount_change, wallet_type="advance_in", cust_id=None):
    if amount_change == 0: return
    
    # --- THE FIX: Use ID if provided, fallback to name ---
    if cust_id:
        cursor.execute("SELECT id, address FROM customers WHERE id=? AND company_id=?", (cust_id, company_id))
    else:
        cursor.execute("SELECT id, address FROM customers WHERE name=? AND company_id=?", (name, company_id))
    # -----------------------------------------------------
        
    row = cursor.fetchone()
    if row:
        c_id, raw_addr = row[0], row[1]
        try: j_data = json.loads(raw_addr)
        except: j_data = {"address": raw_addr if raw_addr else ""}
        curr = float(j_data.get(wallet_type, j_data.get("advance_wallet", 0.0)))
        j_data[wallet_type] = max(0.0, curr + amount_change)
        cursor.execute("UPDATE customers SET address=? WHERE id=?", (json.dumps(j_data), c_id))
    else:
        j_data = {"address": "", wallet_type: max(0.0, amount_change)}
        cursor.execute("INSERT INTO customers (company_id, name, address) VALUES (?, ?, ?)", (company_id, name, json.dumps(j_data)))

# --- THE FIX: Unified Invoice Edit Engine (with cust_id) ---
def update_invoice_full(inv_id, inv_date, del_date, inv_num, cust_name, place, sub, cgst, sgst, igst, total, items, status=None, cust_id=None):
    conn = get_connection(); cursor = conn.cursor()
    if status != 'Draft':
        cursor.execute("DELETE FROM invoices WHERE invoice_number = ? AND company_id = ? AND is_deleted = 1 AND id != ?", (inv_num, ACTIVE_COMPANY_ID, inv_id))
    
    cursor.execute('SELECT amount_paid, write_off FROM invoices WHERE id=? AND company_id=?', (inv_id, ACTIVE_COMPANY_ID))
    row = cursor.fetchone()
    amt_paid = float(row[0]) if (row and row[0]) else 0.0
    woff = float(row[1]) if (row and len(row) > 1 and row[1]) else 0.0
    
    new_tot = float(total)
    excess = (amt_paid + woff) - new_tot
    refund_cash = 0.0
    
    if excess > 0:
        if woff >= excess:
            woff -= excess
            excess = 0.0
        else:
            excess -= woff
            woff = 0.0
        
        if excess > 0:
            refund_cash = excess
            amt_paid -= excess
    
    new_bal = max(0.0, new_tot - amt_paid - woff)
    
    if status == 'Draft': stat = 'Draft'
    else:
        if new_bal <= 0.01: stat = 'Paid'
        elif amt_paid > 0 or woff > 0: stat = 'Partial'
        else: stat = 'Unpaid'
        
    cursor.execute('''UPDATE invoices SET invoice_date=?, delivery_date=?, invoice_number=?, customer_name=?, customer_id=?, place_of_service=?, subtotal=?, cgst=?, sgst=?, igst=?, total=?, balance_due=?, amount_paid=?, write_off=?, status=? WHERE id=? AND company_id=?''',
        (inv_date, del_date, inv_num, cust_name, cust_id, place, sub, cgst, sgst, igst, new_tot, new_bal, amt_paid, woff, stat, inv_id, ACTIVE_COMPANY_ID))
        
    if refund_cash > 0:
        import datetime
        today_str = datetime.datetime.now().strftime("%Y-%m-%d")
        
        internal_update_wallet(cursor, ACTIVE_COMPANY_ID, cust_name, refund_cash, "advance_in", cust_id)
        note = f"Invoice #{inv_num} Edited: Overpayment automatically transferred to Advance Wallet."
        
        # --- THE FIX: Stamp the ledger with today's date instead of the original invoice date! ---
        cursor.execute("INSERT INTO party_payments (company_id, party_name, party_id, pay_type, pay_date, amount, mode, ref, notes) VALUES (?, ?, ?, 'receive', ?, ?, 'System Reversal', 'Advance Wallet', ?)",
                      (ACTIVE_COMPANY_ID, cust_name, cust_id, today_str, refund_cash, note))
        # -----------------------------------------------------------------------------------------

    cursor.execute("DELETE FROM invoice_items WHERE invoice_id=?", (inv_id,))
    for item in items: 
        unit_val = item[6] if len(item) > 6 else ""
        cursor.execute('INSERT INTO invoice_items (invoice_id, item_name, sac, rate, quantity, days, amount, unit) VALUES (?, ?, ?, ?, ?, ?, ?, ?)', (inv_id, item[0], item[1], item[2], item[3], item[4], item[5], unit_val))
        
    conn.commit(); conn.close()
# -----------------------------------------------------------

# --- THE FIX: Advance Peel-Off Engine for Edits ---
def clear_invoice_generation_advance(inv_num, comp_id):
    conn = get_connection()
    c = conn.cursor()
    # Find the specific advance applied during creation
    c.execute("SELECT id, amount, mode, party_name, party_id FROM party_payments WHERE company_id=? AND ref LIKE ? AND notes='Advance received during invoice generation.'", (comp_id, f"{inv_num} (%"))
    rows = c.fetchall()
    
    total_adv_removed = 0.0
    for r in rows:
        p_id, p_amt, p_mode, p_party, p_party_id = r
        # If it was paid via Wallet, securely refund the wallet first
        if "Wallet" in p_mode:
            internal_update_wallet(c, comp_id, p_party, p_amt, "advance_in", p_party_id)
        total_adv_removed += p_amt
        c.execute("DELETE FROM party_payments WHERE id=?", (p_id,))
        
    # Deduct the removed advance from the invoice's 'amount_paid' so the baseline is pure again
    if total_adv_removed > 0:
        c.execute("SELECT id, amount_paid FROM invoices WHERE invoice_number=? AND company_id=?", (inv_num, comp_id))
        inv_row = c.fetchone()
        if inv_row:
            new_paid = max(0.0, float(inv_row[1] or 0.0) - total_adv_removed)
            c.execute("UPDATE invoices SET amount_paid=? WHERE id=?", (new_paid, inv_row[0]))
            
    conn.commit()
    conn.close()
# --------------------------------------------------

def get_all_invoices(): conn = get_connection(); cursor = conn.cursor(); cursor.execute('SELECT id, invoice_date, invoice_number, customer_name, subtotal, (cgst+sgst+igst) as total_gst, total, status, balance_due, amount_paid FROM invoices WHERE company_id = ? AND is_deleted = 0 ORDER BY id DESC', (ACTIVE_COMPANY_ID,)); rows = cursor.fetchall(); conn.close(); return rows
def get_invoices_by_customer(customer_name): conn = get_connection(); cursor = conn.cursor(); cursor.execute('SELECT id, invoice_date, invoice_number, total, amount_paid, balance_due, status, write_off FROM invoices WHERE customer_name = ? AND company_id = ? AND is_deleted = 0 ORDER BY invoice_date ASC', (customer_name, ACTIVE_COMPANY_ID)); rows = cursor.fetchall(); conn.close(); return rows

# --- THE FIX: Include customer_id in the fetch ---
def get_invoice_by_id(inv_id): 
    conn = get_connection(); cursor = conn.cursor()
    cursor.execute('''SELECT id, invoice_date, delivery_date, invoice_number, customer_name, place_of_service, subtotal, cgst, sgst, igst, total, amount_paid, balance_due, status, write_off, is_deleted, company_id, customer_id FROM invoices WHERE id = ? AND company_id = ?''', (inv_id, ACTIVE_COMPANY_ID))
    inv = cursor.fetchone()
    cursor.execute('SELECT item_name, sac, rate, quantity, days, amount, unit FROM invoice_items WHERE invoice_id = ?', (inv_id,))
    items = cursor.fetchall()
    conn.close(); return inv, items
# -------------------------------------------------

def update_invoice_payment(inv_id, amount_paid, balance_due, status, write_off): conn = get_connection(); cursor = conn.cursor(); cursor.execute('UPDATE invoices SET amount_paid = ?, balance_due = ?, status = ?, write_off = ? WHERE id = ? AND company_id = ?', (amount_paid, balance_due, status, write_off, inv_id, ACTIVE_COMPANY_ID)); conn.commit(); conn.close()
def update_invoice_status(inv_id, status): conn = get_connection(); cursor = conn.cursor(); cursor.execute('UPDATE invoices SET status = ? WHERE id = ? AND company_id = ?', (status, inv_id, ACTIVE_COMPANY_ID)); conn.commit(); conn.close()

def get_deleted_invoices():
    conn = get_connection(); cursor = conn.cursor()
    cursor.execute('SELECT id, invoice_date, invoice_number, customer_name, total FROM invoices WHERE company_id = ? AND is_deleted = 1 ORDER BY id DESC', (ACTIVE_COMPANY_ID,))
    rows = cursor.fetchall(); conn.close(); return rows

def soft_delete_invoice(inv_id, refund_mode='none'):
    conn = get_connection(); cursor = conn.cursor(); cursor.execute('PRAGMA foreign_keys = ON')
    cursor.execute('SELECT invoice_number, invoice_date, customer_name, amount_paid, total, status, customer_id FROM invoices WHERE id=? AND company_id=?', (inv_id, ACTIVE_COMPANY_ID))
    inv_row = cursor.fetchone()
    
    if inv_row:
        inv_num, inv_date, c_name = inv_row[0], inv_row[1], inv_row[2]
        amt_paid, tot, stat = float(inv_row[3] or 0.0), float(inv_row[4] or 0.0), inv_row[5]
        c_id = inv_row[6]
        
        cursor.execute('SELECT template_json FROM company WHERE id=?', (ACTIVE_COMPANY_ID,))
        comp_row = cursor.fetchone()
        if comp_row and comp_row[0]:
            try:
                t_json = json.loads(comp_row[0])
                if t_json.get("business_type") == "Sales":
                    cursor.execute('SELECT item_name, quantity, rate, sac FROM invoice_items WHERE invoice_id=?', (inv_id,))
                    for item in cursor.fetchall():
                        item_name, qty, rate, sac = item[0], item[1], item[2], item[3]
                        cursor.execute('SELECT unit FROM stock WHERE item_name=? AND company_id=? LIMIT 1', (item_name, ACTIVE_COMPANY_ID))
                        u_row = cursor.fetchone()
                        unit = u_row[0] if u_row else "Nos."
                        notes_dict = {"notes": f"Auto-restored from deleted Invoice: {inv_num}", "mrp": "", "gst": "", "hsn": sac}
                        cursor.execute('INSERT INTO stock (company_id, item_name, quantity, unit, market_price, notes, added_date, transaction_type) VALUES (?, ?, ?, ?, ?, ?, ?, ?)', (ACTIVE_COMPANY_ID, item_name, qty, unit, rate, json.dumps(notes_dict), inv_date, 'ADD'))
            except Exception: pass

        # --- THE FIX: Unified Master Deletion Engine for Invoice Soft-Deletes ---
        # 1. Isolate only the pure Cash/Bank portions of the payment (Ignore Wallet Deductions)
        cursor.execute("SELECT mode, ref FROM party_payments WHERE company_id=? AND pay_type='receive' AND ref LIKE ?", (ACTIVE_COMPANY_ID, f"%{inv_num} (%"))
        total_cash_portion = 0.0
        for mode, ref_str in cursor.fetchall():
            if mode and "Wallet Deduction" in mode: continue
            parts = ref_str.split(" | ")
            for part in parts:
                if part.startswith(f"{inv_num} ("):
                    amt_str = part.replace(f"{inv_num} (", "").replace(")", "").strip()
                    try: total_cash_portion += float(re.sub(r'[^\d\.]', '', amt_str))
                    except: pass

        # 2. Run all linked payments through the Master Deletion Engine (This perfectly refunds Wallet Deductions natively)
        cursor.execute("SELECT id FROM party_payments WHERE company_id=? AND pay_type='receive' AND ref LIKE ?", (ACTIVE_COMPANY_ID, f"%{inv_num} (%"))
        for pid_row in cursor.fetchall():
            delete_party_payment(pid_row[0], ACTIVE_COMPANY_ID, bypass_rules=True)

        # 3. If "Move to Wallet" was selected, credit ONLY the cash portion to the Advance Wallet
        if refund_mode == 'wallet' and total_cash_portion > 0.01:
            note = f"System Reversal: Invoice #{inv_num} Soft-Deleted. Cash converted to Advance."
            cursor.execute("INSERT INTO party_payments (company_id, party_name, party_id, pay_type, pay_date, amount, mode, ref, notes) VALUES (?, ?, ?, 'receive', ?, ?, 'System Reversal', 'Advance Wallet', ?)", 
                           (ACTIVE_COMPANY_ID, c_name, c_id, inv_date, total_cash_portion, note))
            internal_update_wallet(cursor, ACTIVE_COMPANY_ID, c_name, total_cash_portion, "advance_in", c_id)
            
        cursor.execute("UPDATE invoices SET amount_paid=0.0, balance_due=?, write_off=0.0, status='Unpaid' WHERE id=?", (tot, inv_id))
        # ------------------------------------------------------------------------

    cursor.execute('UPDATE invoices SET is_deleted = 1, refund_mode = ? WHERE id = ? AND company_id = ?', (refund_mode, inv_id, ACTIVE_COMPANY_ID))
    conn.commit(); conn.close()

def restore_invoice(inv_id):
    conn = get_connection(); cursor = conn.cursor(); cursor.execute('PRAGMA foreign_keys = ON')
    
    cursor.execute('SELECT invoice_number, invoice_date, customer_name, amount_paid, total, status, refund_mode, write_off, customer_id FROM invoices WHERE id=? AND company_id=?', (inv_id, ACTIVE_COMPANY_ID))
    inv_row = cursor.fetchone()
    
    if inv_row:
        inv_num, inv_date, c_name = inv_row[0], inv_row[1], inv_row[2]
        amt_paid, tot = float(inv_row[3] or 0.0), float(inv_row[4] or 0.0)
        stat, refund_mode = inv_row[5], inv_row[6]
        woff = float(inv_row[7] or 0.0) if len(inv_row) > 7 else 0.0
        c_id = inv_row[8]
        
        cursor.execute('SELECT template_json FROM company WHERE id=?', (ACTIVE_COMPANY_ID,))
        comp_row = cursor.fetchone()
        if comp_row and comp_row[0]:
            try:
                t_json = json.loads(comp_row[0])
                if t_json.get("business_type") == "Sales":
                    cursor.execute('SELECT item_name, quantity, rate, sac FROM invoice_items WHERE invoice_id=?', (inv_id,))
                    for item in cursor.fetchall():
                        item_name, qty, rate, sac = item[0], item[1], item[2], item[3]
                        cursor.execute('SELECT unit FROM stock WHERE item_name=? AND company_id=? LIMIT 1', (item_name, ACTIVE_COMPANY_ID))
                        u_row = cursor.fetchone()
                        unit = u_row[0] if u_row else "Nos."
                        notes_dict = {"notes": f"Auto-deducted for restored Inv: {inv_num}", "mrp": "", "gst": "", "hsn": sac}
                        cursor.execute('INSERT INTO stock (company_id, item_name, quantity, unit, market_price, notes, added_date, transaction_type) VALUES (?, ?, ?, ?, ?, ?, ?, ?)', (ACTIVE_COMPANY_ID, item_name, qty, unit, rate, json.dumps(notes_dict), inv_date, 'LOSS'))
            except Exception: pass
        
        if refund_mode == 'wallet':
            if amt_paid > 0:
                note = f"System Reversal: Invoice #{inv_num} Restored. Cash deducted from Advance."
                cursor.execute("INSERT INTO party_payments (company_id, party_name, party_id, pay_type, pay_date, amount, mode, ref, notes) VALUES (?, ?, ?, 'receive', ?, ?, 'System Reversal', 'Advance Wallet', ?)", 
                               (ACTIVE_COMPANY_ID, c_name, c_id, inv_date, -amt_paid, note))
                internal_update_wallet(cursor, ACTIVE_COMPANY_ID, c_name, -amt_paid, "advance_in", c_id)
            
            if woff > 0:
                woff_ref = f"{inv_num} ({woff})"
                note_woff = f"System Reversal: Invoice #{inv_num} Restored. Write-Off Re-applied."
                cursor.execute("INSERT INTO party_payments (company_id, party_name, party_id, pay_type, pay_date, amount, mode, ref, notes) VALUES (?, ?, ?, 'receive', ?, ?, 'System Reversal', ?, ?)", 
                               (ACTIVE_COMPANY_ID, c_name, c_id, inv_date, woff, woff_ref, note_woff))

    cursor.execute('UPDATE invoices SET is_deleted = 0, refund_mode="none" WHERE id = ? AND company_id = ?', (inv_id, ACTIVE_COMPANY_ID))
    conn.commit(); conn.close()

def hard_delete_invoice(inv_id):
    conn = get_connection(); cursor = conn.cursor()
    cursor.execute('PRAGMA foreign_keys = ON')
    
    # --- THE FIX: Obliterate Orphaned Payments & Recalculate Wallet safely ---
    cursor.execute("SELECT invoice_number FROM invoices WHERE id=? AND company_id=?", (inv_id, ACTIVE_COMPANY_ID))
    row = cursor.fetchone()
    if row:
        inv_num = row[0]
        # Route ALL connected payments through the master engine so advance wallets are refunded properly
        cursor.execute("SELECT id FROM party_payments WHERE company_id=? AND ref LIKE ?", (ACTIVE_COMPANY_ID, f"%{inv_num} (%"))
        for pid_row in cursor.fetchall():
            delete_party_payment(pid_row[0], ACTIVE_COMPANY_ID, bypass_rules=True)
    # -------------------------------------------------------------------------
    
    cursor.execute('DELETE FROM invoices WHERE id = ? AND company_id = ?', (inv_id, ACTIVE_COMPANY_ID))
    conn.commit(); conn.close()

def check_invoice_number_status(inv_num):
    conn = get_connection(); cursor = conn.cursor()
    cursor.execute('SELECT id, is_deleted FROM invoices WHERE invoice_number = ? AND company_id = ?', (inv_num, ACTIVE_COMPANY_ID))
    rows = cursor.fetchall(); conn.close()
    return rows

def soft_delete_purchase(p_id, refund_mode='none'):
    conn = get_connection(); cursor = conn.cursor(); cursor.execute('PRAGMA foreign_keys = ON')
    cursor.execute('SELECT bill_number, purchase_date, vendor_name, amount_paid, total, status, is_draft, vendor_id FROM purchases WHERE id=? AND company_id=?', (p_id, ACTIVE_COMPANY_ID))
    p_row = cursor.fetchone()
    
    if p_row:
        b_num, p_date, v_name, amt_paid, tot, stat, is_draft = p_row[0], p_row[1], p_row[2], float(p_row[3] or 0.0), float(p_row[4] or 0.0), p_row[5], p_row[6]
        v_id = p_row[7]
        
        if not is_draft:
            # --- THE FIX: Unified Master Deletion Engine for Purchase Soft-Deletes ---
            cursor.execute("SELECT mode, ref FROM party_payments WHERE company_id=? AND pay_type='make' AND ref LIKE ?", (ACTIVE_COMPANY_ID, f"%{b_num} (%"))
            total_cash_portion = 0.0
            for mode, ref_str in cursor.fetchall():
                if mode and "Wallet Deduction" in mode: continue 
                parts = ref_str.split(" | ")
                for part in parts:
                    if part.startswith(f"{b_num} ("):
                        amt_str = part.replace(f"{b_num} (", "").replace(")", "").strip()
                        try: total_cash_portion += float(re.sub(r'[^\d\.]', '', amt_str))
                        except: pass

            cursor.execute("SELECT id FROM party_payments WHERE company_id=? AND pay_type='make' AND ref LIKE ?", (ACTIVE_COMPANY_ID, f"%{b_num} (%"))
            for pid_row in cursor.fetchall():
                delete_party_payment(pid_row[0], ACTIVE_COMPANY_ID, bypass_rules=True)

            if refund_mode == 'wallet' and total_cash_portion > 0.01:
                note = f"System Reversal: Bill #{b_num} Soft-Deleted. Cash converted to Advance."
                cursor.execute("INSERT INTO party_payments (company_id, party_name, party_id, pay_type, pay_date, amount, mode, ref, notes) VALUES (?, ?, ?, 'make', ?, ?, 'System Reversal', 'Advance Wallet', ?)", 
                               (ACTIVE_COMPANY_ID, v_name, v_id, p_date, -total_cash_portion, note))
                internal_update_wallet(cursor, ACTIVE_COMPANY_ID, v_name, total_cash_portion, "advance_out", v_id)
                
            cursor.execute("UPDATE purchases SET amount_paid=0.0, balance_due=?, write_off=0.0, status='Unpaid' WHERE id=?", (tot, p_id))
            # ------------------------------------------------------------------------

    cursor.execute('UPDATE purchases SET is_deleted = 1, refund_mode = ? WHERE id = ? AND company_id = ?', (refund_mode, p_id, ACTIVE_COMPANY_ID))
    conn.commit(); conn.close()

def restore_purchase(p_id):
    conn = get_connection(); cursor = conn.cursor(); cursor.execute('PRAGMA foreign_keys = ON')
    
    cursor.execute('SELECT bill_number, purchase_date, vendor_name, amount_paid, total, status, refund_mode, is_draft, write_off, vendor_id FROM purchases WHERE id=? AND company_id=?', (p_id, ACTIVE_COMPANY_ID))
    p_row = cursor.fetchone()
    
    if p_row:
        b_num, p_date, v_name = p_row[0], p_row[1], p_row[2]
        amt_paid = float(p_row[3] or 0.0)
        tot = float(p_row[4] or 0.0)
        stat, refund_mode, is_draft = p_row[5], p_row[6], p_row[7]
        woff = float(p_row[8] or 0.0)
        v_id = p_row[9]
        
        if not is_draft:
            if refund_mode == 'wallet':
                if amt_paid > 0:
                    note = f"System Reversal: Bill #{b_num} Restored. Cash deducted from Advance."
                    cursor.execute("INSERT INTO party_payments (company_id, party_name, party_id, pay_type, pay_date, amount, mode, ref, notes) VALUES (?, ?, ?, 'make', ?, ?, 'System Reversal', 'Advance Wallet', ?)", 
                                   (ACTIVE_COMPANY_ID, v_name, v_id, p_date, amt_paid, note))
                    internal_update_wallet(cursor, ACTIVE_COMPANY_ID, v_name, -amt_paid, "advance_out", v_id)
                
                if woff > 0:
                    woff_ref = f"{b_num} ({woff})"
                    note_woff = f"System Reversal: Bill #{b_num} Restored. Write-Off Re-applied."
                    cursor.execute("INSERT INTO party_payments (company_id, party_name, party_id, pay_type, pay_date, amount, mode, ref, notes) VALUES (?, ?, ?, 'make', ?, ?, 'System Reversal', ?, ?)", 
                                   (ACTIVE_COMPANY_ID, v_name, v_id, p_date, -woff, woff_ref, note_woff))
            
    cursor.execute('UPDATE purchases SET is_deleted = 0, refund_mode="none" WHERE id = ? AND company_id = ?', (p_id, ACTIVE_COMPANY_ID))
    conn.commit(); conn.close()

def hard_delete_purchase(p_id):
    conn = get_connection(); cursor = conn.cursor()
    cursor.execute('PRAGMA foreign_keys = ON')
    
    # --- THE FIX: Obliterate Orphaned Payments & Recalculate Wallet safely ---
    cursor.execute("SELECT bill_number FROM purchases WHERE id=? AND company_id=?", (p_id, ACTIVE_COMPANY_ID))
    row = cursor.fetchone()
    if row:
        b_num = row[0]
        
        # 1. Fetch all connected payments and run them through the proper deletion engine 
        # so the wallet balance is securely refunded and logged.
        cursor.execute("SELECT id FROM party_payments WHERE company_id=? AND ref LIKE ?", (ACTIVE_COMPANY_ID, f"%{b_num} (%"))
        payment_ids = cursor.fetchall()
        for pid_row in payment_ids:
            delete_party_payment(pid_row[0], ACTIVE_COMPANY_ID, bypass_rules=True)
            
        # 2. Wipe Phantom General Expenses generated by Debit Notes/Returns
        cursor.execute("DELETE FROM general_expenses WHERE company_id=? AND notes LIKE ?", (ACTIVE_COMPANY_ID, f'%\"source_id\": {p_id}%'))
    # -------------------------------------------------------------------------
    
    cursor.execute('DELETE FROM purchases WHERE id = ? AND company_id = ?', (p_id, ACTIVE_COMPANY_ID))
    conn.commit(); conn.close()

def get_deleted_purchases():
    conn = get_connection(); cursor = conn.cursor()
    cursor.execute('SELECT id, purchase_date, bill_number, vendor_name, total FROM purchases WHERE company_id = ? AND is_deleted = 1 ORDER BY id DESC', (ACTIVE_COMPANY_ID,))
    rows = cursor.fetchall(); conn.close(); return rows

def check_purchase_bill_status(bill_num, vendor_name):
    conn = get_connection(); cursor = conn.cursor()
    cursor.execute('SELECT id, is_deleted FROM purchases WHERE bill_number = ? AND vendor_name = ? AND company_id = ?', (bill_num, vendor_name, ACTIVE_COMPANY_ID))
    rows = cursor.fetchall(); conn.close()
    return rows

def get_balance_sheet_raw_data():
    conn = get_connection(); c = conn.cursor()
    salaries, expenses, invoices, stock, purchases = [], [], [], [], []
    try:
        c.execute("SELECT p.pay_date, p.pay_type, p.amount, COALESCE(p.notes, '') || ' [Mode: ' || COALESCE(p.mode, '') || ']', e.name, COALESCE(e.is_deleted, 0), 'Employee' FROM employee_payments p LEFT JOIN employees e ON p.emp_id = e.id WHERE p.pay_type IN ('Salary', 'Bonus', 'Advance') AND e.company_id = ?", (ACTIVE_COMPANY_ID,))
        salaries = c.fetchall()
        
        # --- THE FIX: Block 'Wage' from bleeding into the P&L and simply invert actual cash flow! ---
        c.execute("SELECT ll.date, ll.type, -ll.amount, COALESCE(ll.description, '') || ' [Mode: ' || COALESCE(ll.mode, '') || ']', l.name, COALESCE(l.is_deleted, 0), 'Labour' FROM labour_ledger ll LEFT JOIN labours l ON ll.labour_id = l.id WHERE ll.type IN ('Payment', 'Advance', 'Bonus') AND l.company_id = ?", (ACTIVE_COMPANY_ID,))
        # --------------------------------------------------------------------------------------------
        labour_pays = c.fetchall()
        salaries.extend(labour_pays)
    except: pass
    try:
        c.execute("SELECT expense_date, title, category, amount, notes FROM general_expenses WHERE company_id = ?", (ACTIVE_COMPANY_ID,))
        expenses = c.fetchall()
        
        # --- THE FIX: Quarantine TDS Deductions from Dashboard Cash Flow ---
        c.execute("SELECT pay_date, party_name, amount, notes, mode, ref, pay_type FROM party_payments WHERE company_id = ? AND pay_type IN ('make', 'receive') AND mode != 'TDS Deduction' AND EXISTS (SELECT 1 FROM customers WHERE customers.id = party_payments.party_id AND customers.company_id = party_payments.company_id)", (ACTIVE_COMPANY_ID,))
        # --------------------------------------------------------------------
        import re
        for p_row in c.fetchall():
            try:
                p_date, p_name, p_amt, p_notes, p_mode, p_ref, p_type = p_row
                
                p_amt_safe = float(p_amt or 0.0)
                p_notes_safe = str(p_notes or "")
                p_mode_safe = str(p_mode or "")
                p_ref_safe = str(p_ref or "")
                p_name_safe = str(p_name or "Unknown Party")
                
                note_lower = p_notes_safe.lower()
                ref_lower = p_ref_safe.lower()
                mode_lower = p_mode_safe.lower()
                
                is_wallet_deduction = 'wallet deduction' in mode_lower
                is_client_refund = "refunded to customer" in ref_lower
                is_vendor_refund = "refunded from vendor" in ref_lower
                is_advance_wallet = "advance wallet" in ref_lower
                is_offset = "offset wallet" in ref_lower
    
                # Allow Offsets to bypass the system adjustment block
                if p_mode_safe in ('Write-Off', 'Adjustment', 'System Adjustment') and not is_offset:
                    continue
    
                if p_type == 'make':
                    # --- THE FIX: Correctly intercept Client Refunds and Wallet Offsets ---
                    if is_client_refund:
                        salaries.append((p_date, 'Client Advance', -abs(p_amt_safe), f"Refunded to Client - {p_notes_safe} [Mode: {p_mode_safe}]", p_name_safe, 0, "Client"))
                        continue
                    if is_offset:
                        salaries.append((p_date, 'Advance', -abs(p_amt_safe), f"Wallet Offset - {p_notes_safe}", p_name_safe, 0, "Vendor"))
                        continue
                    # ----------------------------------------------------------------------
                    if is_advance_wallet:
                        salaries.append((p_date, 'Advance', abs(p_amt_safe), f"Vendor Advance Paid - {p_notes_safe} [Mode: {p_mode_safe}]", p_name_safe, 0, "Vendor"))
                        continue
                    if is_wallet_deduction:
                        salaries.append((p_date, 'Advance', -abs(p_amt_safe), f"Wallet Deduction - {p_notes_safe} [Mode: {p_mode_safe}]", p_name_safe, 0, "Vendor"))
                        continue
                        
                    bill_label = "Vendor Payment"
                    clean_ref = re.sub(r'\s*\([^)]*\)', '', p_ref_safe).strip()
                    if clean_ref and clean_ref not in ("Advance Wallet", "Offset Wallet", "None"):
                        bill_label = f"Bill: {clean_ref}"
                    display_name = f"{p_name_safe} ({bill_label})"
                    expenses.append((p_date, display_name, "Inventory/Purchases", abs(p_amt_safe), p_notes_safe))
                    
                elif p_type == 'receive':
                    if is_vendor_refund:
                        salaries.append((p_date, 'Advance', -abs(p_amt_safe), f"Refunded from Vendor - {p_notes_safe} [Mode: {p_mode_safe}]", p_name_safe, 0, "Vendor"))
                        continue
                    if is_client_refund:
                        salaries.append((p_date, 'Client Advance', -abs(p_amt_safe), f"Refunded to Client - {p_notes_safe} [Mode: {p_mode_safe}]", p_name_safe, 0, "Client"))
                        continue
                    # --- THE FIX: Intercept Wallet Offsets for Clients ---
                    if is_offset:
                        salaries.append((p_date, 'Client Advance', -abs(p_amt_safe), f"Wallet Offset - {p_notes_safe}", p_name_safe, 0, "Client"))
                        continue
                    # -----------------------------------------------------
                    if is_advance_wallet:
                        salaries.append((p_date, 'Client Advance', abs(p_amt_safe), f"Client Advance Received - {p_notes_safe} [Mode: {p_mode_safe}]", p_name_safe, 0, "Client"))
                        continue
                    if is_wallet_deduction:
                        salaries.append((p_date, 'Client Advance', -abs(p_amt_safe), f"Wallet Deduction - {p_notes_safe} [Mode: {p_mode_safe}]", p_name_safe, 0, "Client"))
            except Exception as e:
                print(f"Skipped Corrupt Payment Row: {e}")
                continue
    except: pass
    try:
        c.execute("SELECT invoice_date, invoice_number, customer_name, total, balance_due, status FROM invoices WHERE company_id = ? AND is_deleted=0 AND status != 'Draft'", (ACTIVE_COMPANY_ID,))
        invoices = c.fetchall()
    except: pass
    try:
        c.execute("SELECT purchase_date, bill_number, vendor_name, total, balance_due, status FROM purchases WHERE company_id = ? AND is_deleted=0 AND is_draft=0", (ACTIVE_COMPANY_ID,))
        purchases = c.fetchall()
    except: pass
    try:
        c.execute("SELECT added_date, item_name, quantity, market_price, transaction_type FROM stock WHERE company_id = ? AND COALESCE(is_deleted, 0) = 0 ORDER BY id ASC", (ACTIVE_COMPANY_ID,))
        stock = c.fetchall()
    except: pass
    conn.close()
    return {"salaries": salaries, "expenses": expenses, "invoices": invoices, "stock": stock, "purchases": purchases}

def save_ui_setting(key, value):
    conn = get_connection(); cursor = conn.cursor()
    target_cid = 0 if key == "dark_mode" else ACTIVE_COMPANY_ID
    # --- THE FIX: Enforce absolute Company Isolation for all UI keys! ---
    safe_key = key if key == "dark_mode" or str(target_cid) in key else f"{key}_cid_{target_cid}"
    cursor.execute("REPLACE INTO ui_settings (setting_key, setting_value, company_id) VALUES (?, ?, ?)", (safe_key, value, target_cid))
    conn.commit(); conn.close()

def get_ui_setting(key, default="{}"):
    conn = get_connection(); cursor = conn.cursor()
    target_cid = 0 if key == "dark_mode" else ACTIVE_COMPANY_ID
    safe_key = key if key == "dark_mode" or str(target_cid) in key else f"{key}_cid_{target_cid}"
    
    cursor.execute("SELECT setting_value FROM ui_settings WHERE setting_key=?", (safe_key,))
    res = cursor.fetchone()
    if not res and key != "dark_mode": # Fallback for old un-isolated keys
        cursor.execute("SELECT setting_value FROM ui_settings WHERE setting_key=?", (key,))
        res = cursor.fetchone()
    conn.close()
    return res[0] if res else default

def get_employee_dashboard_stats():
    conn = get_connection(); cursor = conn.cursor()
    cursor.execute("SELECT p.pay_type, SUM(p.amount) FROM employee_payments p LEFT JOIN employees e ON p.emp_id = e.id WHERE e.company_id = ? AND COALESCE(e.is_deleted, 0) = 0 GROUP BY p.pay_type", (ACTIVE_COMPANY_ID,))
    pay_data = dict(cursor.fetchall())
    cursor.execute("SELECT COUNT(*) FROM employees WHERE company_id = ? AND COALESCE(is_deleted, 0) = 0 AND ((resign_date = '' OR resign_date IS NULL) OR (rejoin_date != '' AND rejoin_date IS NOT NULL))", (ACTIVE_COMPANY_ID,))
    try: active_count = cursor.fetchone()[0]
    except: active_count = 0
    conn.close()
    return pay_data.get("Salary", 0), pay_data.get("Bonus", 0), pay_data.get("Advance", 0), active_count

def get_all_general_expenses():
    conn = get_connection(); cursor = conn.cursor()
    cursor.execute("SELECT * FROM general_expenses WHERE company_id = ? ORDER BY expense_date DESC, id DESC", (ACTIVE_COMPANY_ID,))
    rows = cursor.fetchall(); conn.close()
    return rows

def get_general_expense_record(exp_id):
    conn = get_connection(); cursor = conn.cursor()
    cursor.execute("SELECT * FROM general_expenses WHERE id=? AND company_id=?", (exp_id, ACTIVE_COMPANY_ID))
    row = cursor.fetchone(); conn.close()
    return row

def add_general_expense(exp_date, title, category, amount, notes, pay_method="Cash", status="Paid", receipt_path=""):
    conn = get_connection(); cursor = conn.cursor()
    cursor.execute("INSERT INTO general_expenses (company_id, expense_date, title, category, amount, notes, pay_method, status, receipt_path) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (ACTIVE_COMPANY_ID, exp_date, title, category, amount, notes, pay_method, status, receipt_path))
    new_id = cursor.lastrowid
    conn.commit(); conn.close()
    return new_id

def update_general_expense(exp_id, exp_date, title, category, amount, notes, pay_method="Cash", status="Paid", receipt_path=""):
    conn = get_connection(); cursor = conn.cursor()
    cursor.execute("UPDATE general_expenses SET expense_date=?, title=?, category=?, amount=?, notes=?, pay_method=?, status=?, receipt_path=? WHERE id=? AND company_id=?", (exp_date, title, category, amount, notes, pay_method, status, receipt_path, exp_id, ACTIVE_COMPANY_ID))
    conn.commit(); conn.close()

def delete_general_expense_and_rollback(exp_id):
    conn = get_connection(); cursor = conn.cursor()
    cursor.execute("SELECT * FROM general_expenses WHERE id=? AND company_id=?", (exp_id, ACTIVE_COMPANY_ID))
    row = cursor.fetchone()
    if row:
        # Receipt file is intentionally kept on disk for 24h so 'Undo' restores the receipt intact;
        # main.py's 24-hour Garbage Collector automatically sweeps unreferenced receipt files.
        cursor.execute("DELETE FROM general_expenses WHERE id=? AND company_id=?", (exp_id, ACTIVE_COMPANY_ID))
        conn.commit()
    conn.close()
    return row

def restore_general_expense_record(row_data):
    conn = get_connection(); cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(general_expenses)")
    cols = [r[1] for r in cursor.fetchall()]
    placeholders = ",".join(["?"] * len(cols))
    safe_data = list(row_data[:len(cols)])
    while len(safe_data) < len(cols): safe_data.append(None)
    cursor.execute(f"INSERT INTO general_expenses ({','.join(cols)}) VALUES ({placeholders})", safe_data)
    conn.commit(); conn.close()

def bulk_reassign_general_expenses(exp_ids, new_cat):
    conn = get_connection(); cursor = conn.cursor()
    placeholders = ",".join(["?"] * len(exp_ids))
    params = [new_cat] + list(exp_ids) + [ACTIVE_COMPANY_ID]
    cursor.execute(f"UPDATE general_expenses SET category=? WHERE id IN ({placeholders}) AND company_id=?", params)
    conn.commit(); conn.close()

def get_distinct_expense_titles():
    conn = get_connection(); cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT title FROM general_expenses WHERE title IS NOT NULL AND title != '' AND company_id = ? ORDER BY title ASC", (ACTIVE_COMPANY_ID,))
    rows = [r[0] for r in cursor.fetchall()]; conn.close()
    return rows

def get_pl_vendor_payments():
    conn = get_connection(); cursor = conn.cursor()
    # --- THE FIX: Quarantine TDS Deductions from P&L calculations ---
    cursor.execute("SELECT pay_date, party_name, amount, notes, mode FROM party_payments WHERE company_id = ? AND pay_type = 'make' AND mode NOT IN ('Write-Off', 'Adjustment', 'System Adjustment', 'TDS Deduction') AND LOWER(COALESCE(notes, '')) NOT LIKE '%advance%' AND LOWER(COALESCE(ref, '')) NOT LIKE '%advance%' AND EXISTS (SELECT 1 FROM customers WHERE customers.id = party_payments.party_id AND customers.company_id = party_payments.company_id)", (ACTIVE_COMPANY_ID,))
    # --------------------------------------------------------------------
    rows = cursor.fetchall(); conn.close()
    return rows

def get_all_employees(order_by="name ASC"):
    conn = get_connection(); c = conn.cursor()
    c.execute(f"SELECT id, name, phone, alt_phone, role, salary, join_date, photo_path, document_path, dob, docs_json, resign_date, rejoin_date, salary_history, company_id, is_pinned FROM employees WHERE company_id = ? AND COALESCE(is_deleted, 0) = 0 ORDER BY {order_by}", (ACTIVE_COMPANY_ID,))
    rows = c.fetchall(); conn.close()
    return rows

def delete_employee(emp_id):
    conn = get_connection(); c = conn.cursor()
    c.execute("UPDATE employees SET is_deleted=1 WHERE id=? AND company_id=?", (emp_id, ACTIVE_COMPANY_ID))
    conn.commit(); conn.close()

def get_employee_dict(emp_id):
    conn = get_connection(); cursor = conn.cursor()
    cursor.execute("SELECT id, company_id, name, phone, alt_phone, role, salary, join_date, photo_path, document_path, dob, docs_json, resign_date, rejoin_date, salary_history, is_pinned FROM employees WHERE id=? AND company_id=?", (emp_id, ACTIVE_COMPANY_ID))
    row = cursor.fetchone()
    if not row: return None
    cols = ["id", "company_id", "name", "phone", "alt_phone", "role", "salary", "join_date", "photo_path", "document_path", "dob", "docs_json", "resign_date", "rejoin_date", "salary_history", "is_pinned"]
    conn.close()
    return dict(zip(cols, row))

def insert_employee_full(name, phone, alt_phone, role, salary, join_date, photo_path, doc_path, dob, docs_json, salary_history):
    conn = get_connection(); c = conn.cursor()
    c.execute('''INSERT INTO employees (company_id, name, phone, alt_phone, role, salary, join_date, photo_path, document_path, dob, docs_json, salary_history) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', (ACTIVE_COMPANY_ID, name, phone, alt_phone, role, salary, join_date, photo_path, doc_path, dob, docs_json, salary_history))
    new_id = c.lastrowid
    conn.commit(); conn.close()
    return new_id

def update_employee_full(emp_id, name, phone, alt_phone, role, salary, join_date, photo_path, dob, docs_json):
    conn = get_connection(); c = conn.cursor()
    c.execute('''UPDATE employees SET name=?, phone=?, alt_phone=?, role=?, salary=?, join_date=?, photo_path=?, dob=?, docs_json=? WHERE id=? AND company_id=?''', (name, phone, alt_phone, role, salary, join_date, photo_path, dob, docs_json, emp_id, ACTIVE_COMPANY_ID))
    conn.commit(); conn.close()

def update_employee_salary(emp_id, new_salary, salary_history_json):
    conn = get_connection(); c = conn.cursor()
    c.execute("UPDATE employees SET salary=?, salary_history=? WHERE id=? AND company_id=?", (new_salary, salary_history_json, emp_id, ACTIVE_COMPANY_ID))
    conn.commit(); conn.close()

def update_employee_leave_allocation(emp_id, year_str, allocated_days):
    conn = get_connection(); c = conn.cursor()
    c.execute("SELECT docs_json FROM employees WHERE id=? AND company_id=?", (emp_id, ACTIVE_COMPANY_ID))
    row = c.fetchone()
    
    j_data = {}
    if row and row[0]:
        try: j_data = json.loads(row[0])
        except: pass
        
    if "leave_allocations" not in j_data:
        j_data["leave_allocations"] = {}
        
    j_data["leave_allocations"][str(year_str)] = float(allocated_days)
    
    c.execute("UPDATE employees SET docs_json=? WHERE id=?", (json.dumps(j_data), emp_id))
    conn.commit(); conn.close()

def get_all_employee_payments_with_names():
    conn = get_connection(); cursor = conn.cursor()
    cursor.execute("SELECT ep.id, ep.pay_date, e.name, ep.pay_type, ep.amount, ep.notes FROM employee_payments ep LEFT JOIN employees e ON ep.emp_id = e.id WHERE e.company_id = ?", (ACTIVE_COMPANY_ID,))
    rows = cursor.fetchall(); conn.close()
    return rows

def get_employee_payments(emp_id):
    conn = get_connection(); c = conn.cursor()
    c.execute("SELECT id, pay_date, pay_type, amount, notes FROM employee_payments WHERE emp_id=? AND company_id=?", (emp_id, ACTIVE_COMPANY_ID))
    rows = c.fetchall(); conn.close()
    return rows

def add_employee_payment(emp_id, pay_type, amount, pay_date, notes, mode="Cash", attachment_path=""):
    conn = get_connection(); c = conn.cursor()
    c.execute("INSERT INTO employee_payments (emp_id, pay_type, amount, pay_date, notes, mode, attachment_path, company_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (emp_id, pay_type, amount, pay_date, notes, mode, attachment_path, ACTIVE_COMPANY_ID))
    new_id = c.lastrowid
    conn.commit(); conn.close()
    return new_id

def get_employee_full_record(emp_id):
    conn = get_connection(); c = conn.cursor()
    c.execute("SELECT * FROM employees WHERE id=? AND company_id=?", (emp_id, ACTIVE_COMPANY_ID))
    row = c.fetchone(); conn.close(); return row

def restore_deleted_employee(emp_id):
    conn = get_connection(); c = conn.cursor()
    c.execute("UPDATE employees SET is_deleted=0 WHERE id=? AND company_id=?", (emp_id, ACTIVE_COMPANY_ID))
    conn.commit(); conn.close()

def restore_employee_record_full(row_data):
    conn = get_connection(); c = conn.cursor()
    c.execute("PRAGMA table_info(employees)")
    cols = [r[1] for r in c.fetchall()]
    
    # --- THE FIX: Dynamically pad or trim the snapshot to match the modern schema! ---
    safe_data = list(row_data[:len(cols)])
    while len(safe_data) < len(cols): safe_data.append(None)
    # ---------------------------------------------------------------------------------
    
    placeholders = ",".join(["?"] * len(cols))
    c.execute(f"INSERT INTO employees ({','.join(cols)}) VALUES ({placeholders})", safe_data)
    conn.commit(); conn.close()
    
def update_employee_record_full(row_data):
    conn = get_connection(); c = conn.cursor()
    c.execute("PRAGMA table_info(employees)")
    cols = [r[1] for r in c.fetchall()]
    
    # --- THE FIX: Dynamically pad or trim the snapshot to match the modern schema! ---
    safe_data = list(row_data[:len(cols)])
    while len(safe_data) < len(cols): safe_data.append(None)
    # ---------------------------------------------------------------------------------
    
    set_clause = ", ".join([f"{col}=?" for col in cols])
    params = safe_data + [safe_data[0]]
    c.execute(f"UPDATE employees SET {set_clause} WHERE id=?", params)
    conn.commit(); conn.close()

def get_employee_payment_record(pay_id):
    conn = get_connection(); c = conn.cursor()
    c.execute("SELECT * FROM employee_payments WHERE id=? AND company_id=?", (pay_id, ACTIVE_COMPANY_ID))
    row = c.fetchone(); conn.close(); return row

def update_employee_payment_proof(pay_id, attachment_path):
    conn = get_connection(); c = conn.cursor()
    c.execute("UPDATE employee_payments SET attachment_path=? WHERE id=? AND emp_id IN (SELECT id FROM employees WHERE company_id = ?)", (attachment_path, pay_id, ACTIVE_COMPANY_ID))
    conn.commit(); conn.close()

def check_employee_leave_exists(emp_id, leave_date):
    conn = get_connection(); c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM employee_payments WHERE emp_id=? AND pay_date=? AND pay_type IN ('Paid Leave', 'Unpaid Leave', 'Absent')", (emp_id, leave_date))
    count = c.fetchone()[0]
    conn.close(); return count > 0

def restore_employee_payment_record(row_data):
    conn = get_connection(); c = conn.cursor()
    c.execute("INSERT INTO employee_payments (id, emp_id, pay_type, amount, pay_date, notes, mode, attachment_path, company_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", list(row_data[:8]) + [ACTIVE_COMPANY_ID])
    conn.commit(); conn.close()

def get_all_employee_id_strings():
    conn = get_connection(); c = conn.cursor()
    c.execute("SELECT id, docs_json FROM employees WHERE company_id=? AND COALESCE(is_deleted, 0) = 0", (ACTIVE_COMPANY_ID,))
    existing = []
    for r in c.fetchall():
        r_id, d_j = r[0], r[1]
        e_str = ""
        if d_j:
            try:
                p = json.loads(d_j)
                if isinstance(p, dict): e_str = p.get("emp_id_str", "")
            except: pass
        if not e_str: e_str = f"EMP-{int(r_id):04d}"
        existing.append((r_id, e_str.lower()))
    conn.close()
    return existing

def mark_employee_status(emp_id, status, status_date):
    conn = get_connection(); c = conn.cursor()
    if status == "Resigned": c.execute("UPDATE employees SET resign_date=?, rejoin_date='' WHERE id=? AND company_id=?", (status_date, emp_id, ACTIVE_COMPANY_ID))
    else: c.execute("UPDATE employees SET rejoin_date=? WHERE id=? AND company_id=?", (status_date, emp_id, ACTIVE_COMPANY_ID))
    c.execute("INSERT INTO employee_payments (emp_id, pay_type, amount, pay_date, notes) VALUES (?, ?, 0.0, ?, ?)", (emp_id, status, status_date, f"Status changed to {status}"))
    conn.commit(); conn.close()

def sync_employee_status(emp_id):
    conn = get_connection(); cursor = conn.cursor()
    cursor.execute("SELECT pay_type, pay_date FROM employee_payments WHERE emp_id=? AND pay_type IN ('Resigned', 'Rejoined') ORDER BY id DESC", (emp_id,))
    statuses = cursor.fetchall()
    res_val, rej_val = "" , ""
    if statuses:
        if statuses[0][0] == 'Resigned': res_val = statuses[0][1]
        elif statuses[0][0] == 'Rejoined':
            rej_val = statuses[0][1]
            for s in statuses[1:]:
                if s[0] == 'Resigned':
                    res_val = s[1]; break
    cursor.execute("UPDATE employees SET resign_date=?, rejoin_date=? WHERE id=? AND company_id=?", (res_val, rej_val, emp_id, ACTIVE_COMPANY_ID))
    conn.commit(); conn.close()

def sync_all_employee_statuses():
    conn = get_connection(); cursor = conn.cursor()
    cursor.execute("SELECT id FROM employees WHERE company_id=?", (ACTIVE_COMPANY_ID,))
    for e in cursor.fetchall(): sync_employee_status(e[0])
    conn.close()

def delete_employee_payment_and_rollback(pay_id):
    conn = get_connection(); cursor = conn.cursor()
    cursor.execute("SELECT emp_id, attachment_path, pay_type, amount FROM employee_payments WHERE id=? AND emp_id IN (SELECT id FROM employees WHERE company_id=?)", (pay_id, ACTIVE_COMPANY_ID))
    p_row = cursor.fetchone()
    if p_row:
        e_id, a_path, p_type, p_amt = p_row[0], p_row[1], p_row[2], p_row[3]
        
        # --- THE FIX: Timeline Exception Safety Net for Employee Advances ---
        if p_type == 'Advance' and p_amt > 0:
            cursor.execute("SELECT pay_type, amount, mode FROM employee_payments WHERE emp_id=?", (e_id,))
            curr_wallet = 0.0
            for r_type, r_amt, r_mode in cursor.fetchall():
                if r_type == 'Advance':
                    curr_wallet += r_amt
                elif r_type == 'Salary' and r_mode and "wallet deduction" in str(r_mode).lower():
                    curr_wallet -= r_amt
            
            curr_wallet = max(0.0, curr_wallet)
            
            if p_amt > curr_wallet + 0.01:
                conn.close()
                raise ValueError("Timeline Exception: Cannot delete this Advance Payment.\n\nThese funds have already been utilized. The current wallet balance is lower than the amount you are trying to delete.\n\nPlease delete the newer salary deductions or refunds that spent this money first.")
        # ------------------------------------------------------------------
        
        if a_path and os.path.exists(a_path):
            try: os.remove(a_path)
            except: pass
        cursor.execute("DELETE FROM employee_payments WHERE id=?", (pay_id,))
        conn.commit(); conn.close()
        sync_employee_status(e_id)
    else:
        conn.close()

# --- THE FIX: Secure MVC Wrappers for Employee UI Files ---
def get_employee_last_payment_id(emp_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT id FROM employee_payments WHERE emp_id IN (SELECT id FROM employees WHERE id=? AND company_id=?) ORDER BY id DESC LIMIT 1", (emp_id, ACTIVE_COMPANY_ID))
    res = c.fetchone()
    conn.close()
    return res[0] if res else None

def get_employee_wallet_payments(emp_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT pay_type, amount, mode FROM employee_payments WHERE emp_id IN (SELECT id FROM employees WHERE id=? AND company_id=?)", (emp_id, ACTIVE_COMPANY_ID))
    rows = c.fetchall()
    conn.close()
    return rows

def get_employee_payment_history_filtered(emp_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT id, pay_date, pay_type, mode, amount, notes, attachment_path FROM employee_payments WHERE emp_id IN (SELECT id FROM employees WHERE id=? AND company_id=?) AND pay_type NOT IN ('Unpaid Leave', 'Absent', 'Resigned', 'Rejoined') ORDER BY id DESC", (emp_id, ACTIVE_COMPANY_ID))
    rows = c.fetchall()
    conn.close()
    return rows

def get_employee_ledger_payments(emp_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT id, pay_date, pay_type, amount, notes, mode, attachment_path FROM employee_payments WHERE emp_id IN (SELECT id FROM employees WHERE id=? AND company_id=?)", (emp_id, ACTIVE_COMPANY_ID))
    rows = c.fetchall()
    conn.close()
    return rows
# ----------------------------------------------------------

def delete_party_payment(pay_id, company_id, bypass_rules=False, is_twin_deletion=False):
    conn = get_connection(); cursor = conn.cursor()
    # --- THE FIX: Added party_id and pay_date to the fetch ---
    cursor.execute("SELECT amount, ref, party_name, mode, pay_type, notes, party_id, pay_date FROM party_payments WHERE id=? AND company_id=?", (pay_id, company_id))
    p_row = cursor.fetchone()
    if not p_row:
        conn.close(); return

    p_amt, p_ref, p_party, p_mode, p_type, p_notes, p_party_id, p_date = p_row
    p_amt_abs = abs(p_amt)

    # --- Enforce "Lock Past Days' Payment Deletions" for Non-Admin Users ---
    if not bypass_rules:
        uid = int(ACTIVE_USER_ID or 1)
        if str(uid) != "1":
            u_row = get_user_by_id(uid)
            if not (u_row and u_row[3] == "Admin"):
                perms = get_user_permissions(uid)
                inv_rules = perms.get("invoice_rules", {}) if isinstance(perms.get("invoice_rules"), dict) else {}
                party_rules = perms.get("party_rules", {}) if isinstance(perms.get("party_rules"), dict) else {}
                if inv_rules.get("lock_past_payments", False) or party_rules.get("lock_past_payments", False):
                    today_date = datetime.datetime.now().date()
                    pay_dt = None
                    raw_pdate = str(p_date or "").strip()[:10]
                    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d-%m-%Y", "%d/%m/%Y", "%m/%d/%Y"):
                        try:
                            pay_dt = datetime.datetime.strptime(raw_pdate, fmt).date()
                            break
                        except Exception:
                            pass
                    if pay_dt is not None and pay_dt != today_date:
                        conn.close()
                        raise ValueError(
                            f"Access Denied: This payment entry is from a previous date ({p_date}).\n\n"
                            f"Deleting past days' payment entries is locked for your account.\n"
                            f"Please contact the Admin."
                        )
    
    is_client_refund = ("Refunded to Customer" in p_ref)
    is_vendor_refund = ("Refunded from Vendor" in p_ref)
    is_direct_adv = ("Advance Wallet" in p_ref)
    is_wallet_deduction = ("Wallet Deduction" in p_mode)

    if is_client_refund or is_vendor_refund or is_direct_adv or is_wallet_deduction:
        # --- THE FIX: Refund strictly by Database ID, with a Legacy Fallback for old data! ---
        if p_party_id:
            cursor.execute("SELECT id, address FROM customers WHERE id=? AND company_id=?", (p_party_id, company_id))
        else:
            cursor.execute("SELECT id, address FROM customers WHERE name=? AND company_id=?", (p_party, company_id))
        c_row = cursor.fetchone()
        # -------------------------------------------------------------------------------------
        if c_row:
            c_id, raw_addr = c_row[0], c_row[1]
            try: j_data = json.loads(raw_addr)
            except: j_data = {"address": raw_addr if raw_addr else ""}
            
            # --- THE FIX: Accurately route pockets regardless of inverted pay types ---
            if is_client_refund: pocket = "advance_in"
            elif is_vendor_refund: pocket = "advance_out"
            elif p_type == 'receive': pocket = "advance_in"
            else: pocket = "advance_out"
            # ------------------------------------------------------------------------
            
            curr_adv = float(j_data.get(pocket, j_data.get("advance_wallet", 0.0)))
            
            if is_client_refund or is_vendor_refund or is_wallet_deduction:
                j_data[pocket] = curr_adv + p_amt_abs
            elif is_direct_adv:
                if (curr_adv - p_amt_abs) < -0.01:
                    conn.close()
                    raise ValueError("Timeline Exception: Cannot delete this Advance Payment.\n\nThese funds have already been utilized. The current wallet balance is lower than the amount you are trying to delete.\n\nPlease delete the newer refunds or invoice payments that spent this money first.")
                j_data[pocket] = max(0.0, curr_adv - p_amt_abs)
                
            cursor.execute("UPDATE customers SET address=? WHERE id=?", (json.dumps(j_data), c_id))

    parts = p_ref.split(" | ")
    for part in parts:
        if "Advance Wallet" in part or "Refunded" in part: continue
        
        bill_no = part.split(" (")[0].strip()
        import re
        amt_match = re.search(r'\((.*?)\)', part)
        if amt_match:
            raw_val = re.sub(r'[^\d\.]', '', amt_match.group(1))
            try: bill_amt = float(raw_val)
            except: continue
            is_woff = ("Write-Off" in p_mode or "Write-Off" in part)

            if p_type == 'receive':
                cursor.execute("SELECT id, amount_paid, total, write_off, place_of_service FROM invoices WHERE invoice_number=? AND customer_name=? AND company_id=? AND is_deleted=0", (bill_no, p_party, company_id))
                b_row = cursor.fetchone()
                if b_row:
                    b_id, b_paid, b_tot, b_woff, b_place = b_row
                    b_paid, b_tot, b_woff = float(b_paid or 0.0), float(b_tot or 0.0), float(b_woff or 0.0)
                    
                    if p_mode in ("System Reversal", "System Adjustment"):
                        new_tot = b_tot + bill_amt
                        new_woff = b_woff
                        new_paid = b_paid
                    elif is_woff:
                        new_woff = max(0.0, b_woff - bill_amt)
                        new_paid = b_paid
                        new_tot = b_tot
                    else:
                        new_paid = max(0.0, b_paid - bill_amt)
                        new_woff = b_woff
                        new_tot = b_tot
                        
                    new_bal = max(0.0, new_tot - new_paid - new_woff)
                    new_stat = 'Paid' if new_bal <= 0.01 else ('Partial' if new_paid > 0 or new_woff > 0 else 'Unpaid')
                    
                    # --- THE FIX: Bulletproof Math-Based Ghost Eradication[cite: 5] ---
                    import re
                    adv_match = re.search(r'@@ADV@@1\|\|([\d\.]+)', str(b_place))
                    if adv_match:
                        adv_val = float(adv_match.group(1) or 0.0)
                        # If the deleted payment matches the advance exactly, OR the invoice is now empty, scrub it!
                        if abs(bill_amt - adv_val) < 0.01 or new_paid < adv_val:
                            b_place = re.sub(r'@@ADV@@1\|\|[\d\.]+', '@@ADV@@0||', str(b_place))
                    # -------------------------------------------------------------------
                    
                    cursor.execute("UPDATE invoices SET amount_paid=?, balance_due=?, status=?, write_off=?, total=?, place_of_service=? WHERE id=?", (new_paid, new_bal, new_stat, new_woff, new_tot, b_place, b_id))
            else:
                if p_party_id and str(p_party_id).isdigit():
                    cursor.execute("SELECT id, amount_paid, total, write_off FROM purchases WHERE bill_number=? AND (vendor_id=? OR (vendor_id IS NULL AND vendor_name=?)) AND company_id=? AND is_deleted=0", (bill_no, int(p_party_id), p_party, company_id))
                else:
                    cursor.execute("SELECT id, amount_paid, total, write_off FROM purchases WHERE bill_number=? AND vendor_name=? AND company_id=? AND is_deleted=0", (bill_no, p_party, company_id))
                b_row = cursor.fetchone()
                if b_row:
                    b_id, b_paid, b_tot, b_woff = b_row
                    b_paid, b_tot, b_woff = float(b_paid or 0.0), float(b_tot or 0.0), float(b_woff or 0.0)
                    
                    if p_mode in ("System Reversal", "System Adjustment"):
                        new_tot = b_tot + bill_amt
                        new_woff = b_woff
                        new_paid = b_paid
                    elif is_woff:
                        new_woff = max(0.0, b_woff - bill_amt)
                        new_paid = b_paid
                        new_tot = b_tot
                    else:
                        new_paid = max(0.0, b_paid - bill_amt)
                        new_woff = b_woff
                        new_tot = b_tot
                        
                    new_bal = max(0.0, new_tot - new_paid - new_woff)
                    new_stat = 'Paid' if new_bal <= 0.01 else ('Partial' if new_paid > 0 or new_woff > 0 else 'Unpaid')
                    cursor.execute("UPDATE purchases SET amount_paid=?, balance_due=?, status=?, write_off=?, total=? WHERE id=?", (new_paid, new_bal, new_stat, new_woff, new_tot, b_id))

    if p_mode in ("System Reversal", "System Adjustment"):
        extracted_bill = p_ref.split(" | ")[-1].split(" (")[0].strip()
        cursor.execute("DELETE FROM general_expenses WHERE company_id=? AND notes LIKE ?", (company_id, f'%{extracted_bill}%'))

    # --- THE FIX: Find the Twin ID before deleting this one! ---
    twin_ids = []
    if not is_twin_deletion and p_mode == "Contra / Bill Offset":
        cursor.execute("SELECT id FROM party_payments WHERE company_id=? AND party_id=? AND mode=? AND pay_date=? AND id != ?", (company_id, p_party_id, p_mode, p_date, pay_id))
        twin_ids = [r[0] for r in cursor.fetchall()]
    # -----------------------------------------------------------

    cursor.execute("DELETE FROM party_payments WHERE id=? AND company_id=?", (pay_id, company_id))
    conn.commit()
    conn.close()

    # --- THE FIX: Automatically vaporize the twin to keep math perfect! ---
    for t_id in twin_ids:
        delete_party_payment(t_id, company_id, bypass_rules=True, is_twin_deletion=True)
    # ----------------------------------------------------------------------

    # Only log the deletion once to keep the audit trail clean
    if not bypass_rules and not is_twin_deletion:
        target_tab = "Invoices" if p_type == "receive" else "Purchases"
        log_audit(
            target_tab,
            "Payment Deleted",
            record_ref=str(p_party or ""),
            details=f"Deleted payment ({p_mode}) of @@CURR:{p_amt_abs}@@ dated @@DATE:{p_date}@@ • Applied: {p_ref}",
            amount=p_amt_abs,
            company_id=company_id
        )

    # --- THE FIX: Secure CA Status Toggle (MVC Compliant) ---
def toggle_ca_status(doc_type, doc_id, new_status, submission_date, comp_id):
    conn = get_connection()
    c = conn.cursor()
    if "OUTPUT" in doc_type:
        c.execute("UPDATE invoices SET ca_submitted=?, ca_submission_date=? WHERE id=? AND company_id=?", (new_status, submission_date, doc_id, comp_id))
    else:
        c.execute("UPDATE purchases SET ca_submitted=?, ca_submission_date=? WHERE id=? AND company_id=?", (new_status, submission_date, doc_id, comp_id))
    conn.commit()
    conn.close()
# --------------------------------------------------------

def delete_labour_ledger_and_attendance_rollback(ledg_id):
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM labour_ledger WHERE id=? AND labour_id IN (SELECT id FROM labours WHERE company_id=?)", (ledg_id, ACTIVE_COMPANY_ID))
    row = cursor.fetchone()
    
    if row:
        l_id = row[1]
        l_date = row[2]
        l_type = row[3]
        l_amt = row[4]
        a_path = row[7] if len(row) > 7 else None
        
        # --- THE FIX: Timeline Exception Safety Net for Labour Advances ---
        if l_type == 'Advance' and l_amt < 0:
            cursor.execute("SELECT type, amount, description FROM labour_ledger WHERE labour_id=?", (l_id,))
            curr_wallet = 0.0
            for r_type, r_amt, r_desc in cursor.fetchall():
                if r_type == 'Advance':
                    if r_amt < 0: curr_wallet += abs(r_amt)
                    else: curr_wallet -= abs(r_amt)
                elif r_type == 'Payment':
                    if r_desc and ("Wallet" in r_desc or "(Out)" in r_desc or "Advance Out" in r_desc):
                        curr_wallet -= abs(r_amt)
                if curr_wallet < 0: curr_wallet = 0.0
            
            if abs(l_amt) > curr_wallet + 0.01:
                conn.close()
                raise ValueError("Timeline Exception: Cannot delete this Advance Payment.\n\nThese funds have already been utilized. The current wallet balance is lower than the amount you are trying to delete.\n\nPlease delete the newer refunds or wage payments that spent this money first.")
        # ------------------------------------------------------------------
        
        if a_path and os.path.exists(a_path):
            try: os.remove(a_path)
            except Exception: pass
            
        if l_type == 'Wage':
            # --- THE FIX: Safely delete exactly ONE attendance shift for this date to keep counts perfectly balanced ---
            try:
                cursor.execute("""
                    DELETE FROM labour_attendance 
                    WHERE id = (
                        SELECT id FROM labour_attendance 
                        WHERE labour_id=? AND date=?
                        ORDER BY id DESC LIMIT 1
                    )
                """, (l_id, l_date))
            except Exception: pass
            
        cursor.execute("DELETE FROM labour_ledger WHERE id=? AND labour_id IN (SELECT id FROM labours WHERE company_id=?)", (ledg_id, ACTIVE_COMPANY_ID))
        conn.commit()
        
    conn.close()

def clean_orphan_attendances(labour_id):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # 1. Count exact Wage ledger entries per date
        cursor.execute("SELECT date, COUNT(*) FROM labour_ledger WHERE labour_id=? AND type='Wage' GROUP BY date", (labour_id,))
        wage_counts = dict(cursor.fetchall())

        # 2. Count exact Attendance shifts per date
        cursor.execute("SELECT id, date FROM labour_attendance WHERE labour_id=?", (labour_id,))
        attendances = cursor.fetchall()

        att_by_date = {}
        for a_id, a_date in attendances:
            if a_date not in att_by_date: att_by_date[a_date] = []
            att_by_date[a_date].append(a_id)

        # 3. Destroy ghosts (Delete excess attendances if there are more than Wages)
        ids_to_delete = []
        for a_date, a_ids in att_by_date.items():
            expected_count = wage_counts.get(a_date, 0)
            if len(a_ids) > expected_count:
                excess = len(a_ids) - expected_count
                ids_to_delete.extend(a_ids[-excess:])
        
        if ids_to_delete:
            placeholders = ",".join(["?"] * len(ids_to_delete))
            cursor.execute(f"DELETE FROM labour_attendance WHERE id IN ({placeholders})", ids_to_delete)
            
        # 4. THE AUTO-HEALER (Rebuild accidentally deleted attendances)
        for w_date, expected_count in wage_counts.items():
            actual_count = len(att_by_date.get(w_date, []))
            if w_date in att_by_date:
                actual_count -= len([x for x in att_by_date[w_date] if x in ids_to_delete])

            if expected_count > actual_count:
                # Wipe any remaining broken attendances for this specific date
                if w_date in att_by_date:
                    surviving_ids = [x for x in att_by_date[w_date] if x not in ids_to_delete]
                    if surviving_ids:
                        placeholders = ",".join(["?"] * len(surviving_ids))
                        cursor.execute(f"DELETE FROM labour_attendance WHERE id IN ({placeholders})", surviving_ids)
                
                # Fetch company ID
                cursor.execute("SELECT company_id FROM labours WHERE id=?", (labour_id,))
                c_id_row = cursor.fetchone()
                c_id = c_id_row[0] if c_id_row else 1
                
                # Rebuild perfectly from the ledger
                cursor.execute("SELECT description FROM labour_ledger WHERE labour_id=? AND type='Wage' AND date=?", (labour_id, w_date))
                for w_desc_tuple in cursor.fetchall():
                    # --- THE FIX: Cleaned up ghost math for purely Individual shifts ---
                    desc = str(w_desc_tuple[0] if isinstance(w_desc_tuple, tuple) else w_desc_tuple)
                    h_val = 0.0
                    
                    import re
                    m1 = re.search(r'([\d\.]+)\s*Nos\.\s*Day Shift', desc)
                    m2 = re.search(r'([\d\.]+)\s*Nos\.\s*Night Shift', desc)
                    if m1: h_val += float(m1.group(1))
                    if m2: h_val += float(m2.group(1))
                    
                    m_hajira = re.search(r'Auto-Wage:\s*([\d\.]+)\s*Hajira', desc)
                    if m_hajira: h_val += float(m_hajira.group(1))
                    
                    if h_val == 0.0: h_val = 1.0 
                        
                    base_desc = re.sub(r'\s*\([^)]*\)$', '', desc).strip()
                    # We pass 0.0 for the abandoned skilled/unskilled columns
                    cursor.execute('INSERT INTO labour_attendance (labour_id, date, hajira_count, skilled_count, unskilled_count, notes, company_id) VALUES (?, ?, ?, ?, ?, ?, ?)', (labour_id, w_date, h_val, 0.0, 0.0, base_desc, c_id))
        
        conn.commit()
    except Exception as e:
        print(f"Healer Error: {e}")
    conn.close()
    # --- NEW MVC WRAPPERS FOR STOCK UI ---
def get_company_business_type(comp_id):
    conn = get_connection(); c = conn.cursor()
    c.execute("SELECT template_json FROM company WHERE id=?", (comp_id,))
    row = c.fetchone(); conn.close()
    if row and row[0]:
        try: return json.loads(row[0]).get("business_type", "Service")
        except: pass
    return "Service"

def get_company_gst_toggle(comp_id):
    conn = get_connection(); c = conn.cursor()
    c.execute("SELECT gst_toggle FROM company WHERE id=?", (comp_id,))
    row = c.fetchone(); conn.close()
    return (row[0] == 1) if row else False

def get_unique_stock_names(comp_id):
    conn = get_connection(); c = conn.cursor()
    # --- THE FIX: Filter out soft-deleted ghost items from suggestions! ---
    c.execute("SELECT item_name FROM stock WHERE company_id=? AND COALESCE(is_deleted, 0) = 0 GROUP BY item_name", (comp_id,))
    rows = [r[0] for r in c.fetchall()]; conn.close()
    return rows

def get_unique_customer_names(comp_id):
    conn = get_connection(); c = conn.cursor()
    c.execute("SELECT name FROM customers WHERE company_id=? GROUP BY name", (comp_id,))
    rows = [r[0] for r in c.fetchall()]; conn.close()
    return rows

def get_stock_reorder_level(item_name, comp_id):
    conn = get_connection(); c = conn.cursor()
    c.execute("SELECT notes FROM stock WHERE item_name=? AND company_id=? AND COALESCE(is_deleted, 0) = 0 ORDER BY id DESC", (item_name, comp_id))
    for r in c.fetchall():
        try:
            j = json.loads(r[0])
            if "reorder_level" in j:
                conn.close()
                return float(j["reorder_level"])
        except: pass
    conn.close()
    return 5.0

def bulk_update_stock_depreciation(item_name, new_dep, comp_id):
    conn = get_connection(); c = conn.cursor()
    c.execute("SELECT id, notes FROM stock WHERE item_name=? AND company_id=?", (item_name, comp_id))
    for r in c.fetchall():
        try:
            j = json.loads(r[1])
            j["depreciation"] = new_dep
            c.execute("UPDATE stock SET notes=? WHERE id=?", (json.dumps(j), r[0]))
        except: pass
    conn.commit(); conn.close()


def auto_heal_file_paths():
    """Silently fixes absolute paths for ALL images, PDFs, and deeply nested JSON docs."""
    conn = get_connection()
    c = conn.cursor()
    
    def fix_path(old_path):
        if not isinstance(old_path, str): return old_path
        for folder in ["Vault", "company_logos", "expense_receipts", "purchase_payment_receipts", "invoice_payment_receipts", "vendor_bills", "Employees", "Labours"]:
            if folder in old_path:
                sub = old_path.split(folder, 1)[-1].lstrip("\\/")
                return os.path.normpath(os.path.join(BASE_DIR, folder, sub))
        return old_path

    def heal_standard(table, column):
        try:
            c.execute(f"SELECT id, {column} FROM {table} WHERE {column} IS NOT NULL AND {column} != ''")
            for row in c.fetchall():
                new_val = fix_path(row[1])
                if row[1] != new_val:
                    c.execute(f"UPDATE {table} SET {column}=? WHERE id=?", (new_val, row[0]))
        except: pass

    # 1. Standard Flat Paths
    for t, col in [("company", "logo_path"), ("employees", "photo_path"), ("employees", "document_path"), 
                   ("labours", "photo_path"), ("employee_payments", "attachment_path"), 
                   ("labour_ledger", "attachment_path"), ("party_payments", "attachment_path"), 
                   ("purchases", "receipt_path"), ("general_expenses", "receipt_path")]:
        heal_standard(t, col)

    # 2. Labour Docs (JSON Array of Strings)
    try:
        c.execute("SELECT id, doc_path FROM labours WHERE doc_path IS NOT NULL AND doc_path != ''")
        for row in c.fetchall():
            try:
                paths = json.loads(row[1])
                if isinstance(paths, list):
                    new_paths = [fix_path(p) for p in paths]
                    if new_paths != paths:
                        c.execute("UPDATE labours SET doc_path=? WHERE id=?", (json.dumps(new_paths), row[0]))
                else:
                    new_val = fix_path(row[1])
                    if row[1] != new_val:
                        c.execute("UPDATE labours SET doc_path=? WHERE id=?", (new_val, row[0]))
            except: pass
    except: pass

    # 3. Employee Docs (Nested JSON Dicts & Legacy Lists)
    try:
        c.execute("SELECT id, docs_json FROM employees WHERE docs_json IS NOT NULL AND docs_json != ''")
        for row in c.fetchall():
            try:
                j_data = json.loads(row[1])
                updated = False
                
                # Case A: Modern Dictionary Format
                if isinstance(j_data, dict) and "docs" in j_data and isinstance(j_data["docs"], list):
                    for i in range(len(j_data["docs"])):
                        doc = j_data["docs"][i]
                        if isinstance(doc, dict) and "path" in doc:
                            new_p = fix_path(doc["path"])
                            if new_p != doc["path"]:
                                j_data["docs"][i]["path"] = new_p
                                updated = True
                        elif isinstance(doc, str):
                            new_p = fix_path(doc)
                            if new_p != doc:
                                j_data["docs"][i] = new_p
                                updated = True
                                
                # Case B: Legacy List Format
                elif isinstance(j_data, list):
                    for i in range(len(j_data)):
                        doc = j_data[i]
                        if isinstance(doc, dict) and "path" in doc:
                            new_p = fix_path(doc["path"])
                            if new_p != doc["path"]:
                                j_data[i]["path"] = new_p
                                updated = True
                        elif isinstance(doc, str):
                            new_p = fix_path(doc)
                            if new_p != doc:
                                j_data[i] = new_p
                                updated = True
                                
                if updated:
                    c.execute("UPDATE employees SET docs_json=? WHERE id=?", (json.dumps(j_data), row[0]))
            except: pass
    except: pass

    # 4. Catalog Images (Nested JSON Dicts)
    try:
        c.execute("SELECT id, description FROM inventory WHERE description LIKE '%pics%'")
        for row in c.fetchall():
            try:
                j_data = json.loads(row[1])
                updated = False
                if "pics" in j_data and isinstance(j_data["pics"], list):
                    for i in range(len(j_data["pics"])):
                        pic = j_data["pics"][i]
                        if isinstance(pic, dict) and "path" in pic:
                            new_p = fix_path(pic["path"])
                            if new_p != pic["path"]:
                                j_data["pics"][i]["path"] = new_p
                                updated = True
                if updated:
                    c.execute("UPDATE inventory SET description=? WHERE id=?", (json.dumps(j_data), row[0]))
            except: pass
    except: pass

    # 5. General Expenses (Nested JSON Dicts)
    try:
        c.execute("SELECT id, notes FROM general_expenses WHERE notes LIKE '%receipt%'")
        for row in c.fetchall():
            try:
                j_data = json.loads(row[1])
                if "receipt" in j_data:
                    new_p = fix_path(j_data["receipt"])
                    if new_p != j_data["receipt"]:
                        j_data["receipt"] = new_p
                        c.execute("UPDATE general_expenses SET notes=? WHERE id=?", (json.dumps(j_data), row[0]))
            except: pass
    except: pass

    conn.commit()
    conn.close()

def toggle_labour_pin_status(labour_id, is_pinned):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE labours SET is_pinned=? WHERE id=? AND company_id=?", (is_pinned, labour_id, ACTIVE_COMPANY_ID))
    conn.commit()
    conn.close()

def toggle_employee_pin_status(emp_id, is_pinned):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE employees SET is_pinned=? WHERE id=? AND company_id=?", (is_pinned, emp_id, ACTIVE_COMPANY_ID))
    conn.commit()
    conn.close()    

    # --- THE FIX: MVC Compliant Stock Data & Fast Bulk Reorder ---
def get_company_stock_raw(company_id):
    """Fetches all undeleted stock transactions for a specific company."""
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "SELECT id, item_name, quantity, unit, market_price, transaction_type, notes, added_date "
        "FROM stock WHERE company_id=? AND COALESCE(is_deleted, 0) = 0 ORDER BY id ASC",
        (company_id,)
    )
    rows = c.fetchall()
    conn.close()
    return rows

def bulk_update_stock_reorder_level(item_name, new_level, company_id=None):
    """High-speed batch update that avoids UI freezes and isolates by company."""
    cid = company_id if company_id is not None else ACTIVE_COMPANY_ID
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, notes FROM stock WHERE item_name=? AND company_id=?", (item_name, cid))
    
    updates = []
    for rec_id, raw_json in cursor.fetchall():
        try:
            j = json.loads(raw_json) if raw_json else {}
        except Exception:
            j = {"notes": raw_json if raw_json else ""}
        
        # Only stage an update if the level actually changed
        if j.get("reorder_level") != new_level:
            j["reorder_level"] = new_level
            updates.append((json.dumps(j), rec_id))
            
    if updates:
        cursor.executemany("UPDATE stock SET notes=? WHERE id=?", updates)
        conn.commit()
    conn.close()
# -------------------------------------------------------------


# --- NEW: User Auth Helper Functions ---
def _remove_username_unique_lock(conn, c):
    """Removes the old UNIQUE lock on username and ensures permissions_json column exists."""
    c.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='users'")
    row = c.fetchone()
    if row and "UNIQUE" in row[0].upper():
        c.execute("CREATE TABLE users_new (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL, password_hash TEXT NOT NULL, role TEXT NOT NULL, profile_pic TEXT, permissions_json TEXT DEFAULT '{}')")
        c.execute("INSERT INTO users_new (id, username, password_hash, role, profile_pic) SELECT id, username, password_hash, role, profile_pic FROM users")
        c.execute("DROP TABLE users")
        c.execute("ALTER TABLE users_new RENAME TO users")
        conn.commit()
    try:
        c.execute("ALTER TABLE users ADD COLUMN permissions_json TEXT DEFAULT '{}'")
        conn.commit()
    except Exception:
        pass

def has_users():
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    count = c.fetchone()[0]
    conn.close()
    return count > 0

def add_user(username, password_hash, role, profile_pic="", permissions_json="{}"):
    conn = get_connection()
    c = conn.cursor()
    _remove_username_unique_lock(conn, c)
    
    c.execute("SELECT id FROM users ORDER BY id ASC")
    existing_ids = {int(row[0]) for row in c.fetchall()}
    next_id = 1
    while next_id in existing_ids:
        next_id += 1
        
    c.execute("INSERT INTO users (id, username, password_hash, role, profile_pic, permissions_json) VALUES (?, ?, ?, ?, ?, ?)",
              (next_id, username, password_hash, role, profile_pic, permissions_json))
    conn.commit()
    conn.close()
    return next_id

def update_user_details(user_id, username, role, profile_pic, new_password_hash=None, permissions_json=None):
    conn = get_connection()
    c = conn.cursor()
    _remove_username_unique_lock(conn, c)
    if str(user_id) == "1":
        role = "Admin"
        
    if new_password_hash and permissions_json is not None:
        c.execute("UPDATE users SET username=?, password_hash=?, role=?, profile_pic=?, permissions_json=? WHERE id=?",
                  (username, new_password_hash, role, profile_pic, permissions_json, user_id))
    elif new_password_hash:
        c.execute("UPDATE users SET username=?, password_hash=?, role=?, profile_pic=? WHERE id=?",
                  (username, new_password_hash, role, profile_pic, user_id))
    elif permissions_json is not None:
        c.execute("UPDATE users SET username=?, role=?, profile_pic=?, permissions_json=? WHERE id=?",
                  (username, role, profile_pic, permissions_json, user_id))
    else:
        c.execute("UPDATE users SET username=?, role=?, profile_pic=? WHERE id=?",
                  (username, role, profile_pic, user_id))
    conn.commit()
    conn.close()

def get_user_by_id(user_id):
    conn = get_connection()
    c = conn.cursor()
    _remove_username_unique_lock(conn, c)
    c.execute("SELECT id, username, password_hash, role, profile_pic, COALESCE(permissions_json, '{}') FROM users WHERE id=?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row

def get_user_permissions(user_id):
    if not user_id or str(user_id) == "1":
        return {"companies": "all", "sidebars": "all"}
    row = get_user_by_id(user_id)
    if row and len(row) > 5 and row[5]:
        try:
            data = json.loads(row[5])
            if isinstance(data, dict):
                return data
        except Exception:
            pass
    return {"companies": "all", "sidebars": "all"}

def get_user_by_username(username):
    conn = get_connection()
    c = conn.cursor()
    _remove_username_unique_lock(conn, c)
    c.execute("SELECT id, username, password_hash, role, profile_pic, COALESCE(permissions_json, '{}') FROM users WHERE username=?", (username,))
    row = c.fetchone()
    conn.close()
    return row

def get_all_users():
    conn = get_connection()
    c = conn.cursor()
    _remove_username_unique_lock(conn, c)
    c.execute("SELECT id, username, role, profile_pic, COALESCE(permissions_json, '{}') FROM users ORDER BY id ASC")
    rows = c.fetchall()
    conn.close()
    return rows

def update_user_picture(user_id, pic_path):
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE users SET profile_pic=? WHERE id=?", (pic_path, user_id))
    conn.commit()
    conn.close()

def delete_user(user_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM users WHERE id=? AND id != 1", (user_id,))
    conn.commit()
    conn.close()
# ---------------------------------------

# --- NEW: Global Audit Trail Engine ---
def _ensure_audit_table(conn, c):
    c.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER,
            user_id INTEGER,
            username TEXT,
            user_role TEXT,
            tab_name TEXT,
            action TEXT,
            record_ref TEXT,
            details TEXT,
            amount REAL DEFAULT 0,
            raw_date TEXT,
            exact_time TEXT,
            is_seen INTEGER DEFAULT 0
        )
    """)
    try:
        c.execute("ALTER TABLE audit_logs ADD COLUMN is_seen INTEGER DEFAULT 0")
        c.execute("UPDATE audit_logs SET is_seen = 1 WHERE user_role = 'Admin' OR user_id = 1")
        conn.commit()
    except Exception:
        pass

def log_audit(tab_name, action, record_ref="", details="", amount=0.0, company_id=None, user_id=None):
    """Silently records who did what, in which tab, on what date and exact time."""
    from datetime import datetime
    try:
        cid = int(company_id) if company_id is not None else int(ACTIVE_COMPANY_ID or 1)
        uid = int(user_id) if user_id is not None else int(ACTIVE_USER_ID or 1)
        u_row = get_user_by_id(uid)
        uname = u_row[1] if u_row else "Admin"
        urole = u_row[3] if u_row else "Admin"

        # Admin's own actions are automatically marked seen (1); non-Admin actions are unseen (0)
        is_seen_val = 1 if (urole == "Admin" or str(uid) == "1") else 0

        now = datetime.now()
        raw_date = now.strftime("%Y-%m-%d")
        exact_time = now.strftime("%I:%M:%S %p")

        try:
            amt_val = float(amount) if amount is not None and str(amount).strip() != "" else 0.0
        except Exception:
            amt_val = 0.0

        conn = get_connection()
        c = conn.cursor()
        _ensure_audit_table(conn, c)
        c.execute("""
            INSERT INTO audit_logs 
            (company_id, user_id, username, user_role, tab_name, action, record_ref, details, amount, raw_date, exact_time, is_seen)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (cid, uid, uname, urole, tab_name, action, str(record_ref), str(details), amt_val, raw_date, exact_time, is_seen_val))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Audit Log Error: {e}")

def get_unseen_audit_counts(company_id=None):
    """Returns a dict of unseen non-Admin audit counts per tab and total ('All Tabs')."""
    conn = get_connection()
    c = conn.cursor()
    _ensure_audit_table(conn, c)
    cid = int(company_id) if company_id is not None else int(ACTIVE_COMPANY_ID or 1)
    c.execute(
        "SELECT tab_name, COUNT(*) FROM audit_logs "
        "WHERE company_id=? AND COALESCE(is_seen, 0) = 0 AND user_role != 'Admin' AND user_id != 1 "
        "GROUP BY tab_name",
        (cid,)
    )
    counts = {row[0]: int(row[1]) for row in c.fetchall() if row[0]}
    counts["All Tabs"] = sum(counts.values())
    conn.close()
    return counts

def mark_audit_logs_seen(company_id=None, tab_name=None):
    """Marks unseen non-Admin logs as seen for a specific tab (or all tabs)."""
    conn = get_connection()
    c = conn.cursor()
    _ensure_audit_table(conn, c)
    cid = int(company_id) if company_id is not None else int(ACTIVE_COMPANY_ID or 1)
    if tab_name and tab_name != "All Tabs":
        c.execute("UPDATE audit_logs SET is_seen = 1 WHERE company_id=? AND tab_name=? AND COALESCE(is_seen, 0) = 0", (cid, tab_name))
    else:
        c.execute("UPDATE audit_logs SET is_seen = 1 WHERE company_id=? AND COALESCE(is_seen, 0) = 0", (cid,))
    conn.commit()
    conn.close()

def get_audit_logs(company_id=None, user_id=None, tab_name=None, search_query=""):
    conn = get_connection()
    c = conn.cursor()
    _ensure_audit_table(conn, c)

    cid = int(company_id) if company_id is not None else int(ACTIVE_COMPANY_ID or 1)
    query = "SELECT id, user_id, username, user_role, tab_name, action, record_ref, details, amount, raw_date, exact_time, COALESCE(is_seen, 1) FROM audit_logs WHERE company_id=?"
    params = [cid]

    if user_id and str(user_id) != "All":
        query += " AND user_id=?"
        params.append(int(user_id))

    if tab_name and tab_name != "All Tabs":
        query += " AND tab_name=?"
        params.append(tab_name)

    if search_query and search_query.strip():
        q = f"%{search_query.strip()}%"
        query += " AND (record_ref LIKE ? OR details LIKE ? OR action LIKE ? OR username LIKE ?)"
        params.extend([q, q, q, q])

    query += " ORDER BY id DESC LIMIT 500"
    c.execute(query, params)
    rows = c.fetchall()
    conn.close()
    return rows

def check_invoice_permission(inv_id, action="edit", company_id=None, user_id=None):
    """Enforces per-user Invoice Rules (Past Bill Edit Limit, Today's Bill Edit Limit, Delete Lock)."""
    from datetime import datetime
    uid = int(user_id) if user_id is not None else int(ACTIVE_USER_ID or 1)
    if str(uid) == "1":
        return True, ""

    u_row = get_user_by_id(uid)
    if u_row and u_row[3] == "Admin":
        return True, ""

    perms = get_user_permissions(uid)
    rules = perms.get("invoice_rules", {})
    if not isinstance(rules, dict) or not rules:
        return True, ""

    cid = int(company_id) if company_id is not None else int(ACTIVE_COMPANY_ID or 1)
    conn = get_connection()
    c = conn.cursor()
    _ensure_audit_table(conn, c)

    c.execute("SELECT invoice_number, invoice_date, status FROM invoices WHERE id=? AND company_id=?", (inv_id, cid))
    inv_row = c.fetchone()
    if not inv_row:
        conn.close()
        return True, ""

    inv_num, inv_date, status = str(inv_row[0] or "").strip(), str(inv_row[1] or "").strip(), str(inv_row[2] or "")
    # Drafts are not finalized bills yet, so allow editing/posting them freely
    if status == "Draft":
        conn.close()
        return True, ""

    # Determine if this invoice is a Today's Bill or a Past Day's Bill
    today_date = datetime.now().date()
    today_raw = today_date.strftime("%Y-%m-%d")
    inv_dt = None
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d-%m-%Y", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            inv_dt = datetime.strptime(inv_date[:10], fmt).date()
            break
        except Exception:
            pass

    c.execute(
        "SELECT raw_date FROM audit_logs WHERE company_id=? AND tab_name='Invoices' "
        "AND action IN ('Created', 'Cloned') AND record_ref=? ORDER BY id ASC LIMIT 1",
        (cid, inv_num)
    )
    created_row = c.fetchone()
    created_raw_date = created_row[0] if created_row else (inv_dt.strftime("%Y-%m-%d") if inv_dt else "")
    is_past_bill = (inv_dt is not None and inv_dt != today_date) and (created_raw_date != today_raw)

    # 1. Recycle Bin Check: Allow today's bills freely, but protect past bills when Past Bill Rules are active
    if action == "delete":
        if is_past_bill and rules.get("same_day_only", False):
            conn.close()
            return False, (
                f"Invoice {inv_num} is from a previous date ({inv_date}).\n\n"
                f"Moving past days' invoices to the Recycle Bin is locked for your account.\n"
                f"Please contact the Admin."
            )
        conn.close()
        return True, ""

    # 2. If it's a Past Day's Bill, check Past Bill Edit Limit
    if is_past_bill and rules.get("same_day_only", False):
        if action == "edit":
            try:
                max_past_edits = int(rules.get("max_past_edits", 1))
            except Exception:
                max_past_edits = 1

            if max_past_edits <= 0:
                conn.close()
                return False, (
                    f"Invoice {inv_num} is from a previous date ({inv_date}).\n\n"
                    f"Editing past invoices is locked (0 edits allowed) for your account. Please contact the Admin."
                )

            c.execute(
                "SELECT COUNT(*) FROM audit_logs WHERE company_id=? AND tab_name='Invoices' "
                "AND action='Edited' AND record_ref=? AND raw_date != ? AND user_role != 'Admin'",
                (cid, inv_num, created_raw_date)
            )
            past_edits_used = c.fetchone()[0]
            if past_edits_used >= max_past_edits:
                conn.close()
                return False, (
                    f"Past Invoice Edit Limit Reached ({past_edits_used}/{max_past_edits} edits used)!\n\n"
                    f"Invoice {inv_num} ({inv_date}) cannot be edited any further by non-Admin users.\n"
                    f"Please contact the Admin."
                )

    # 3. Check Daily Edit Count Limit Per Invoice (for Today's Bills or when daily limit is active)
    if action == "edit" and rules.get("limit_edits", False):
        try:
            max_edits = int(rules.get("max_edits", 2))
        except Exception:
            max_edits = 2

        if max_edits <= 0:
            conn.close()
            return False, (
                f"Editing saved invoices is disabled for your account (Max Edits: 0).\n\n"
                f"Please contact the Admin to modify Invoice {inv_num}."
            )

        c.execute(
            "SELECT COUNT(*) FROM audit_logs WHERE company_id=? AND tab_name='Invoices' "
            "AND action='Edited' AND record_ref=? AND raw_date=? AND user_role != 'Admin'",
            (cid, inv_num, today_raw)
        )
        edits_today = c.fetchone()[0]
        if edits_today >= max_edits:
            conn.close()
            return False, (
                f"Daily Edit Limit Reached ({edits_today}/{max_edits} edits used today)!\n\n"
                f"Invoice {inv_num} cannot be edited any further today by non-Admin users.\n"
                f"Please contact the Admin."
            )

    conn.close()
    return True, ""


def check_expense_permission(exp_id, action="edit", company_id=None, user_id=None):
    """Enforces per-user Expense Rules (Past Expense Edit/Delete Limit, Today's Expense Edit Limit, Delete Lock)."""
    from datetime import datetime
    uid = int(user_id) if user_id is not None else int(ACTIVE_USER_ID or 1)
    if str(uid) == "1":
        return True, ""

    u_row = get_user_by_id(uid)
    if u_row and u_row[3] == "Admin":
        return True, ""

    perms = get_user_permissions(uid)
    rules = perms.get("expense_rules", {})
    if not isinstance(rules, dict) or not rules:
        return True, ""

    cid = int(company_id) if company_id is not None else int(ACTIVE_COMPANY_ID or 1)
    conn = get_connection()
    c = conn.cursor()
    _ensure_audit_table(conn, c)

    c.execute("SELECT title, expense_date FROM general_expenses WHERE id=? AND company_id=?", (int(exp_id), cid))
    exp_row = c.fetchone()
    if not exp_row:
        conn.close()
        return True, ""

    exp_title, exp_date = str(exp_row[0] or "").strip(), str(exp_row[1] or "").strip()
    ref_prefix = f"#{int(exp_id)} •%"

    today_date = datetime.now().date()
    today_raw = today_date.strftime("%Y-%m-%d")
    exp_dt = None
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d-%m-%Y", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            exp_dt = datetime.strptime(exp_date[:10], fmt).date()
            break
        except Exception:
            pass

    c.execute(
        "SELECT raw_date FROM audit_logs WHERE company_id=? AND tab_name='Expenses' "
        "AND action IN ('Created', 'Cloned') AND record_ref LIKE ? ORDER BY id ASC LIMIT 1",
        (cid, ref_prefix)
    )
    created_row = c.fetchone()
    created_raw_date = created_row[0] if created_row else (exp_dt.strftime("%Y-%m-%d") if exp_dt else "")
    is_past_exp = (exp_dt is not None and exp_dt != today_date) and (created_raw_date != today_raw)

    # 1. Check Delete Lock
    if action == "delete":
        if rules.get("block_delete", False):
            conn.close()
            return False, (
                f"Deleting expenses is locked for your account.\n\n"
                f"Please contact the Admin to delete '{exp_title}'."
            )
        if is_past_exp and rules.get("same_day_only", False):
            conn.close()
            return False, (
                f"Expense '{exp_title}' is from a previous date ({exp_date}).\n\n"
                f"Deleting past days' expenses is locked for your account.\n"
                f"Please contact the Admin."
            )
        conn.close()
        return True, ""

    # 2. Check Past Expense Edit / Reassign Limit
    if is_past_exp and rules.get("same_day_only", False):
        if action in ("edit", "reassign"):
            try:
                max_past_edits = int(rules.get("max_past_edits", 1))
            except Exception:
                max_past_edits = 1

            if max_past_edits <= 0 or action == "reassign":
                conn.close()
                return False, (
                    f"Expense '{exp_title}' is from a previous date ({exp_date}).\n\n"
                    f"Modifying past days' expenses is locked for your account. Please contact the Admin."
                )

            c.execute(
                "SELECT COUNT(*) FROM audit_logs WHERE company_id=? AND tab_name='Expenses' "
                "AND action IN ('Edited', 'Marked Paid') AND record_ref LIKE ? AND raw_date != ? AND user_role != 'Admin'",
                (cid, ref_prefix, created_raw_date)
            )
            past_edits_used = c.fetchone()[0]
            if past_edits_used >= max_past_edits:
                conn.close()
                return False, (
                    f"Past Expense Edit Limit Reached ({past_edits_used}/{max_past_edits} edits used)!\n\n"
                    f"Expense '{exp_title}' ({exp_date}) cannot be edited any further by non-Admin users.\n"
                    f"Please contact the Admin."
                )

    # 3. Check Today's Expense Edit Limit
    if action == "edit" and rules.get("limit_edits", False):
        try:
            max_edits = int(rules.get("max_edits", 2))
        except Exception:
            max_edits = 2

        if max_edits <= 0:
            conn.close()
            return False, (
                f"Editing saved expenses is disabled for your account (Max Edits: 0).\n\n"
                f"Please contact the Admin to modify '{exp_title}'."
            )

        c.execute(
            "SELECT COUNT(*) FROM audit_logs WHERE company_id=? AND tab_name='Expenses' "
            "AND action IN ('Edited', 'Marked Paid') AND record_ref LIKE ? AND raw_date=? AND user_role != 'Admin'",
            (cid, ref_prefix, today_raw)
        )
        edits_today = c.fetchone()[0]
        if edits_today >= max_edits:
            conn.close()
            return False, (
                f"Daily Edit Limit Reached ({edits_today}/{max_edits} edits used today)!\n\n"
                f"Expense '{exp_title}' cannot be edited any further today by non-Admin users.\n"
                f"Please contact the Admin."
            )

    conn.close()
    return True, ""


def check_purchase_permission(p_id, action="edit", company_id=None, user_id=None):
    """Enforces per-user Purchase Rules (Past Bill Edit/Delete Limit, Today's Bill Edit Limit, Delete Lock)."""
    from datetime import datetime
    uid = int(user_id) if user_id is not None else int(ACTIVE_USER_ID or 1)
    if str(uid) == "1":
        return True, ""

    u_row = get_user_by_id(uid)
    if u_row and u_row[3] == "Admin":
        return True, ""

    perms = get_user_permissions(uid)
    rules = perms.get("purchase_rules", {})
    if not isinstance(rules, dict) or not rules:
        return True, ""

    cid = int(company_id) if company_id is not None else int(ACTIVE_COMPANY_ID or 1)
    conn = get_connection()
    c = conn.cursor()
    _ensure_audit_table(conn, c)

    c.execute("SELECT bill_number, purchase_date, status, is_draft FROM purchases WHERE id=? AND company_id=?", (p_id, cid))
    p_row = c.fetchone()
    if not p_row:
        conn.close()
        return True, ""

    b_num, p_date = str(p_row[0] or "").strip(), str(p_row[1] or "").strip()
    status = str(p_row[2] or "")
    is_draft = p_row[3] == 1

    if is_draft or status == "Draft":
        conn.close()
        return True, ""

    today_date = datetime.now().date()
    today_raw = today_date.strftime("%Y-%m-%d")
    p_dt = None
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d-%m-%Y", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            p_dt = datetime.strptime(p_date[:10], fmt).date()
            break
        except Exception:
            pass

    c.execute(
        "SELECT raw_date FROM audit_logs WHERE company_id=? AND tab_name='Purchases' "
        "AND action IN ('Created', 'Cloned') AND record_ref=? ORDER BY id ASC LIMIT 1",
        (cid, b_num)
    )
    created_row = c.fetchone()
    created_raw_date = created_row[0] if created_row else (p_dt.strftime("%Y-%m-%d") if p_dt else "")
    is_past_bill = (p_dt is not None and p_dt != today_date) and (created_raw_date != today_raw)

    # 1. Check Delete Lock
    if action == "delete":
        if rules.get("block_delete", False):
            conn.close()
            return False, (
                f"Moving purchase bills to the Recycle Bin is locked for your account.\n\n"
                f"Please contact the Admin to delete Bill #{b_num}."
            )
        if is_past_bill and rules.get("same_day_only", False):
            conn.close()
            return False, (
                f"Purchase Bill #{b_num} is from a previous date ({p_date}).\n\n"
                f"Deleting past days' bills is locked for your account.\n"
                f"Please contact the Admin."
            )
        conn.close()
        return True, ""

    # 2. Check Past Bill Edit / Debit Note Limit
    if is_past_bill and rules.get("same_day_only", False):
        if action in ("edit", "return"):
            try:
                max_past_edits = int(rules.get("max_past_edits", 1))
            except Exception:
                max_past_edits = 1

            if max_past_edits <= 0 or action == "return":
                conn.close()
                act_lbl = "Modifying" if action == "edit" else "Recording returns for"
                return False, (
                    f"Purchase Bill #{b_num} is from a previous date ({p_date}).\n\n"
                    f"{act_lbl} past days' bills is locked for your account. Please contact the Admin."
                )

            c.execute(
                "SELECT COUNT(*) FROM audit_logs WHERE company_id=? AND tab_name='Purchases' "
                "AND action='Edited' AND record_ref=? AND raw_date != ? AND user_role != 'Admin'",
                (cid, b_num, created_raw_date)
            )
            past_edits_used = c.fetchone()[0]
            if past_edits_used >= max_past_edits:
                conn.close()
                return False, (
                    f"Past Bill Edit Limit Reached ({past_edits_used}/{max_past_edits} edits used)!\n\n"
                    f"Purchase Bill #{b_num} ({p_date}) cannot be edited any further by non-Admin users.\n"
                    f"Please contact the Admin."
                )

    # 3. Check Today's Bill Edit Limit
    if action == "edit" and rules.get("limit_edits", False):
        try:
            max_edits = int(rules.get("max_edits", 2))
        except Exception:
            max_edits = 2

        if max_edits <= 0:
            conn.close()
            return False, (
                f"Editing saved purchase bills is disabled for your account (Max Edits: 0).\n\n"
                f"Please contact the Admin to modify Bill #{b_num}."
            )

        c.execute(
            "SELECT COUNT(*) FROM audit_logs WHERE company_id=? AND tab_name='Purchases' "
            "AND action='Edited' AND record_ref=? AND raw_date=? AND user_role != 'Admin'",
            (cid, b_num, today_raw)
        )
        edits_today = c.fetchone()[0]
        if edits_today >= max_edits:
            conn.close()
            return False, (
                f"Daily Edit Limit Reached ({edits_today}/{max_edits} edits used today)!\n\n"
                f"Purchase Bill #{b_num} cannot be edited any further today by non-Admin users.\n"
                f"Please contact the Admin."
            )

    conn.close()
    return True, ""


def check_catalog_permission(action="edit", company_id=None, user_id=None):
    """Enforces per-user Catalog Rules (Lock Add/Edit, Lock Delete/Bulk Import)."""
    uid = int(user_id) if user_id is not None else int(ACTIVE_USER_ID or 1)
    if str(uid) == "1":
        return True, ""

    u_row = get_user_by_id(uid)
    if u_row and u_row[3] == "Admin":
        return True, ""

    perms = get_user_permissions(uid)
    rules = perms.get("catalog_rules", {})
    if not isinstance(rules, dict) or not rules:
        return True, ""

    if action == "edit":
        if rules.get("lock_edit", False):
            return False, "Adding and editing Catalog items is locked for your account.\n\nPlease contact the Admin."
    elif action == "delete":
        if rules.get("lock_delete", False):
            return False, "Deleting and bulk importing Catalog items is locked for your account.\n\nPlease contact the Admin."

    return True, ""


def check_stock_permission(action="adjust", company_id=None, user_id=None):
    """Enforces per-user Stock Rules (Lock Manual Adjustments, Lock Deletions & History Edits, Hide Financials)."""
    uid = int(user_id) if user_id is not None else int(ACTIVE_USER_ID or 1)
    if str(uid) == "1":
        return True, ""

    u_row = get_user_by_id(uid)
    if u_row and u_row[3] == "Admin":
        return True, ""

    perms = get_user_permissions(uid)
    rules = perms.get("stock_rules", {})
    if not isinstance(rules, dict) or not rules:
        return True, ""

    if action == "adjust":
        if rules.get("lock_adjustments", False):
            return False, "Manual stock adjustments (Add/Loss/Audit) are locked for your account.\n\nPlease use Purchase Bills or Sales Invoices to move stock, or contact the Admin."
    elif action in ("delete", "history_edit", "import"):
        if rules.get("lock_delete", False):
            return False, "Deleting stock items, rewriting ledger history, and bulk importing are locked for your account.\n\nPlease contact the Admin."
    elif action == "view_financials":
        if rules.get("hide_financials", False):
            return False, ""

    return True, ""

def check_employee_permission(action="pay", company_id=None, user_id=None):
    """Enforces per-user Employee Rules (Lock Payroll, Lock Deletions)."""
    uid = int(user_id) if user_id is not None else int(ACTIVE_USER_ID or 1)
    if str(uid) == "1":
        return True, ""

    u_row = get_user_by_id(uid)
    if u_row and u_row[3] == "Admin":
        return True, ""

    perms = get_user_permissions(uid)
    rules = perms.get("employee_rules", {})
    if not isinstance(rules, dict) or not rules:
        return True, ""

    if action == "pay":
        if rules.get("lock_payroll", False):
            return False, "Processing payroll, recording advances, and changing base salaries are locked for your account.\n\nPlease contact the Admin."
    elif action == "delete":
        if rules.get("lock_delete", False):
            return False, "Deleting employees and reversing payment records are locked for your account.\n\nPlease contact the Admin."
    elif action == "view_financials":
        if rules.get("hide_financials", False):
            return False, ""

    return True, ""

def check_labour_permission(action="pay", company_id=None, user_id=None):
    """Enforces per-user Labour Rules (Lock Payroll, Lock Deletions)."""
    uid = int(user_id) if user_id is not None else int(ACTIVE_USER_ID or 1)
    if str(uid) == "1":
        return True, ""

    u_row = get_user_by_id(uid)
    if u_row and u_row[3] == "Admin":
        return True, ""

    perms = get_user_permissions(uid)
    rules = perms.get("labour_rules", {})
    if not isinstance(rules, dict) or not rules:
        return True, ""

    if action == "pay":
        if rules.get("lock_payroll", False):
            return False, "Logging work, recording advances, and making payments are locked for your account.\n\nPlease contact the Admin."
    elif action == "delete":
        if rules.get("lock_delete", False):
            return False, "Deleting workers and reversing payment records are locked for your account.\n\nPlease contact the Admin."
    elif action == "view_financials":
        if rules.get("hide_financials", False):
            return False, ""

    return True, ""
# --------------------------------------

# ==============================================================================
# MASTER BOOT SEQUENCE (ALWAYS KEEP AT THE ABSOLUTE BOTTOM OF THIS FILE)
# ==============================================================================
