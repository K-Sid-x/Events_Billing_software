import tkinter as tk
import json
import os
import sys
import re

# --- THE FIX: Bulletproof Executable Pathing ---
if getattr(sys, 'frozen', False):
    parent_dir = os.path.dirname(sys.executable)
    current_dir = os.path.join(parent_dir, "views", "customers_parts")
else:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)

if parent_dir not in sys.path:
    sys.path.append(parent_dir)
# -----------------------------------------------

import database
from views.invoice_parts.helpers import format_currency, smart_date_formatter, fetch_global_settings, GST_STATE_CODES
from views.customers_parts.ledger_ui import build_ui
from views.customers_parts.ledger_core import execute_ledger_load



class LedgerWindow(tk.Toplevel):
    def __init__(self, parent_view, row_id):
        super().__init__(parent_view)
        self.parent_view = parent_view
        self.app = parent_view.app
        self.comp_id = getattr(self.app, "active_company_id", 1)
        
        self.curr_fmt, self.date_fmt_code = fetch_global_settings(self.comp_id)
        self.fmt = lambda amt: format_currency(amt, self.curr_fmt)
        self.fmt_date = lambda d_str: smart_date_formatter(d_str, self.date_fmt_code)

        from views.home_parts.ui_components import get_theme
        t = get_theme()
        self.colors = {"bg": t["bg"], "card": t["bg"], "border": t["border"], "text": t["text"], "text_sec": t["sec"], "accent_blue": t["accent_blue"], "accent_green": t["accent_green"], "error": t["error"], "header": t["card"], "stripe_even": t["bg"], "stripe_odd": t["card"]}

        # --- THE FIX: Direct Database ID lookup to support Alias Display Names ---
        c_data = database.get_customer(row_id)
        if not c_data:
            self.destroy(); return
            
        self.party_name = str(c_data[1]).strip()
        alias = str(c_data[8]).strip() if len(c_data) > 8 and c_data[8] else ""
        self.display_name = f"{self.party_name} ({alias})" if alias else self.party_name

        self.extract_data(c_data)
        
        self.title(f"Ledger: {self.display_name}")
        # -------------------------------------------------------------------------
        self.configure(bg=self.colors["bg"])
        self.geometry("1100x650")
        try: self.state("zoomed")
        except: self.attributes("-zoomed", True)

        self.sort_dirs = {"S": {}, "P": {}}
        self.undo_stack = []
        self.redo_stack = []
        
        build_ui(self)
        execute_ledger_load(self)

    def extract_data(self, c_data):
        self.cust_db_id = c_data[0]
        phone_str = str(c_data[2]) if c_data[2] and c_data[2] != "None" else "N/A"
        self.gstin_str = str(c_data[3]) if c_data[3] and c_data[3] != "None" else ""
        self.email_str = str(c_data[4]) if c_data[4] and c_data[4] != "None" else ""
        raw_addr = str(c_data[5]) if len(c_data) > 5 and c_data[5] else ""
        
        self.addr_text, self.pan_text, self.state_text = "N/A", "N/A", ""
        self.ob_val, self.ob_type = 0.0, "They Owe You (Dr)"
        self.advance_in = 0.0
        self.advance_out = 0.0
        
        if raw_addr.strip().startswith("{"):
            try:
                j = json.loads(raw_addr)
                self.addr_text = j.get("address", "N/A") or "N/A"
                self.pan_text = j.get("pan", "N/A") or "N/A"
                self.ob_val = float(j.get("opening_balance", 0.0))
                self.ob_type = j.get("ob_type", "They Owe You (Dr)")
                
                # --- THE FIX: Extract both wallets securely ---
                self.advance_in = float(j.get("advance_in", j.get("advance_wallet", 0.0)))
                self.advance_out = float(j.get("advance_out", 0.0))
            except: self.addr_text = raw_addr
        else: self.addr_text = raw_addr or "N/A"

        try:
            comp_data = database.get_company(self.comp_id)
            self.is_gst_company = (comp_data[8] == 1) if comp_data and len(comp_data) > 8 else False
        except: self.is_gst_company = False

        if self.is_gst_company and self.gstin_str and len(self.gstin_str) >= 2:
            st_code = self.gstin_str[:2]
            if st_code in GST_STATE_CODES:
                self.state_text = GST_STATE_CODES[st_code]
                state_name_only = self.state_text.split(',')[0].strip() 
                self.addr_text = re.sub(r'\b' + re.escape(state_name_only) + r'\b', '', self.addr_text, flags=re.IGNORECASE)
                self.addr_text = self.addr_text.replace(', ,', ',').replace(' ,', ',').replace('( )', '').replace('()', '').strip(', ')

        raw_clean = re.sub(r'Mobile:\s*', '', phone_str, flags=re.IGNORECASE).strip()
        self.phone_clean = " | ".join([p.strip() for p in raw_clean.split(',') if p.strip()])

def view_profile(customers_view, row_id):
    LedgerWindow(customers_view, row_id)