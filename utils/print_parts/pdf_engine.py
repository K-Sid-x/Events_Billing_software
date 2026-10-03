import os
import tempfile
import webbrowser
from tkinter import messagebox
from utils.print_parts.pdf_calculator import build_pdf_context
from utils.print_parts.pdf_builder import build_html

def perform_print(studio):
    try: p_from = int(studio.e_from.get()); p_to = int(studio.e_to.get())
    except: p_from, p_to = 1, studio.total_pages

    if p_from < 1 or p_to > studio.total_pages or p_from > p_to:
        messagebox.showerror("Error", "Invalid page range.", parent=studio)
        return

    try:
        ctx = build_pdf_context(studio, p_from, p_to)
        html_content = build_html(ctx)

        inv_num_clean = studio.inv_data.get('inv_num', 'Invoice').replace('/', '_')
        
        # --- THE FIX: Added the 'Print_Studio_Voucher_' tag for the Sweeper! ---
        save_path = os.path.join(tempfile.gettempdir(), f"Print_Studio_Voucher_{inv_num_clean}.html")
        # -----------------------------------------------------------------------

        with open(save_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        webbrowser.open(f"file://{os.path.abspath(save_path)}")
        
    except Exception as e:
        messagebox.showerror("Error", f"Print Failed: {e}", parent=studio)

def send_to_whatsapp(studio):
    import urllib.parse
    import re
    
    phone = studio.inv_data.get("cust_phone", "")
    phone = re.sub(r'Mobile:\s*', '', phone, flags=re.IGNORECASE).split(',')[0].strip()
    
    # --- THE FIX: Retain the '+' symbol for international country codes! ---
    phone = ''.join(c for c in str(phone) if c.isdigit() or c == '+')
    # -----------------------------------------------------------------------
        
    inv_num = studio.inv_data.get("inv_num", "Invoice")
    total_amt = studio.inv_data.get("total", "0.00")
    
    msg = f"Hello!\n\nHere are the details for your recent transaction:\n*Invoice/Bill No:* {inv_num}\n*Amount Due:* {total_amt}\n\nPlease let us know if you need the formal PDF document.\n\nThank you for your business!"
    safe_msg = urllib.parse.quote(msg)
    
    # THE FIX: Directing straight to the Web App interface to bypass the "wa.me" prompt screen!
    if phone and len(phone) >= 10:
        # --- THE FIX: Only inject '91' if it's exactly 10 digits and has no '+' sign! ---
        if len(phone) == 10 and not phone.startswith('+'): 
            phone = "91" + phone
        # --------------------------------------------------------------------------------
        direct_web_url = f"https://web.whatsapp.com/send?phone={phone}&text={safe_msg}"
    else:
        # If no valid phone is found, it will open your contact list to let you choose who to send it to!
        direct_web_url = f"https://web.whatsapp.com/send?text={safe_msg}"
    
    try:
        webbrowser.open(direct_web_url)
    except Exception as e:
        messagebox.showerror("Error", f"Could not launch WhatsApp: {e}", parent=studio)