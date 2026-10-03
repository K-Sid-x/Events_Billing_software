import os
import sys
from datetime import datetime

# --- THE FIX: Bulletproof Executable Pathing ---
if getattr(sys, 'frozen', False):
    parent_dir = os.path.dirname(sys.executable)
else:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)

if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
# -----------------------------------------------

import database

def get_system_alerts():
    alerts = []
    
    try:
        conn = database.get_connection()
        c = conn.cursor()
        
        # --- THE FIX: Isolate alerts to the ACTIVE company only! ---
        cid = database.ACTIVE_COMPANY_ID
        c.execute("SELECT name, security_pin FROM company WHERE id=?", (cid,))
        comp_row = c.fetchone()
        if not comp_row:
            conn.close()
            return []
            
        cname = comp_row[0]
        cpin = comp_row[1] if len(comp_row) > 1 and comp_row[1] else ""
        
        # 1. Check Invoices
        c.execute("SELECT id, invoice_date, invoice_number, customer_name, subtotal, (cgst+sgst+igst) as total_gst, total, status FROM invoices WHERE company_id = ? AND is_deleted = 0", (cid,))
        invoices = c.fetchall()
        
        for inv in invoices:
            if inv[7] == 'Unpaid':
                try:
                    dt = None
                    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d.%m.%Y"):
                        try:
                            dt = datetime.strptime(inv[1], fmt)
                            break
                        except ValueError: pass
                    
                    if dt and (datetime.now() - dt).days > 30:
                        alerts.append({
                            "cid": cid, "cname": cname, "cpin": cpin,
                            "type": "Invoice", "icon": "⚠️",
                            "msg": f"Invoice {inv[2]} is over 30 days overdue.",
                            "target_tab": "Invoices",
                            "reference": inv[2]
                        })
                except Exception: pass

        # 2. Check Stock
        c.execute('SELECT item_name, SUM(CASE WHEN transaction_type="ADD" THEN quantity ELSE -quantity END) as net_qty FROM stock WHERE company_id=? GROUP BY item_name', (cid,))
        stocks = c.fetchall()
        for st in stocks:
            if st[1] < 5:
                alerts.append({
                    "cid": cid, "cname": cname, "cpin": cpin,
                    "type": "Stock", "icon": "📦",
                    "msg": f"Low Stock: {st[0]} (Only {st[1]} left)",
                    "target_tab": "Stock",
                    "reference": st[0]
                })
                
        conn.close()
    except Exception: pass
        
    return alerts