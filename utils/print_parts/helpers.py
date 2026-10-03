import tkinter as tk
import json
import os
import sys
from datetime import datetime

# =====================================================================================
# THE FIX: GLOBAL TKINTER MONKEY PATCH
# This safely neutralizes the notorious "KeyError: 'popdown'" bug across the entire app
# without ever needing to touch or alter main.py!
# =====================================================================================
_original_winfo_containing = tk.Misc.winfo_containing

def _safe_winfo_containing(self, rootX, rootY, displayof=0):
    try:
        return _original_winfo_containing(self, rootX, rootY, displayof)
    except KeyError:
        return None

tk.Misc.winfo_containing = _safe_winfo_containing
# =====================================================================================

# --- THE FIX: Bulletproof Executable Pathing ---
if getattr(sys, 'frozen', False):
    root_dir = os.path.dirname(sys.executable)
else:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    views_dir = os.path.dirname(current_dir)
    root_dir = os.path.dirname(views_dir)

if root_dir not in sys.path:
    sys.path.append(root_dir)
# -----------------------------------------------

try:
    import database
except ImportError:
    pass 

def fetch_global_settings(company_id=None):
    curr_fmt = "Indian Rupees (₹)"
    date_fmt_code = "%d.%m.%Y"
    try:
        if company_id is None:
            company_id = getattr(database, 'ACTIVE_COMPANY_ID', 1)
            
        comp = database.get_company(company_id)
        if comp and len(comp) > 14 and comp[14]:
            data = json.loads(comp[14])
            curr_fmt = data.get("currency_format", "Indian Rupees (₹)")
            raw_df = data.get("date_format", "DD.MM.YYYY")
            
            if raw_df == "DD.MM.YYYY": date_fmt_code = "%d.%m.%Y"
            elif raw_df == "DD-MM-YYYY": date_fmt_code = "%d-%m-%Y"
            elif raw_df == "DD/MM/YYYY": date_fmt_code = "%d/%m/%Y"
            elif raw_df == "YYYY-MM-DD": date_fmt_code = "%Y-%m-%d"
            elif raw_df == "MM/DD/YYYY": date_fmt_code = "%m/%d/%Y"
    except: pass
    return curr_fmt, date_fmt_code

def get_date_format_str(arg=None):
    if arg is None:
        try: return fetch_global_settings()[1]
        except: return "%d.%m.%Y"
        
    arg_str = str(arg)
    if "YYYY" in arg_str or "MM" in arg_str:
        if arg_str == "DD.MM.YYYY": return "%d.%m.%Y"
        elif arg_str == "DD-MM-YYYY": return "%d-%m-%Y"
        elif arg_str == "DD/MM/YYYY": return "%d/%m/%Y"
        elif arg_str == "YYYY-MM-DD": return "%Y-%m-%d"
        elif arg_str == "MM/DD/YYYY": return "%m/%d/%Y"
        return "%d.%m.%Y"
    
    try: return fetch_global_settings(int(arg))[1]
    except: return "%d.%m.%Y"

def smart_date_formatter(date_str, target_fmt_code=None):
    if not date_str or str(date_str).strip() == "None": return ""
    
    if target_fmt_code is None:
        try: target_fmt_code = fetch_global_settings()[1]
        except: target_fmt_code = "%d.%m.%Y"
        
    for fmt in ("%d.%m.%Y", "%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            dt = datetime.strptime(str(date_str).strip(), fmt)
            return dt.strftime(target_fmt_code)
        except: pass
    return date_str

def enable_copy_paste(widget):
    # 1. Native Select All (Ctrl+A)
    def select_all(e):
        try:
            if isinstance(widget, tk.Text):
                widget.tag_add("sel", "1.0", "end")
            else:
                widget.select_range(0, tk.END)
                widget.icursor(tk.END)
        except: pass
        return "break"

    widget.bind("<Control-a>", select_all)
    widget.bind("<Control-A>", select_all)

    # 2. Text Widget Native Undo/Redo
    if isinstance(widget, tk.Text):
        try: widget.config(undo=True, maxundo=50)
        except: pass
        
        def text_undo(e):
            try: widget.edit_undo()
            except: pass
            return "break"
            
        def text_redo(e):
            try: widget.edit_redo()
            except: pass
            return "break"
            
        widget.bind("<Control-z>", text_undo)
        widget.bind("<Control-y>", text_redo)
        
    # 3. Entry Widget Custom Undo/Redo Engine
    else:
        if not hasattr(widget, '_undo_stack'):
            widget._undo_stack = [""]
            widget._redo_stack = []

        def save_state(event=None):
            try:
                curr = widget.get()
                if not widget._undo_stack or widget._undo_stack[-1] != curr:
                    widget._undo_stack.append(curr)
                    if len(widget._undo_stack) > 50: widget._undo_stack.pop(0)
                    widget._redo_stack.clear()
            except: pass

        def on_paste(event=None):
            save_state() 
            widget.after(10, save_state) 

        def do_undo(event=None):
            try:
                curr = widget.get()
                if widget._undo_stack:
                    if widget._undo_stack[-1] == curr:
                        widget._undo_stack.pop()
                    prev = widget._undo_stack[-1] if widget._undo_stack else ""
                    widget._redo_stack.append(curr)
                    widget.delete(0, tk.END)
                    widget.insert(0, prev)
            except: pass
            return "break"

        def do_redo(event=None):
            try:
                if widget._redo_stack:
                    curr = widget.get()
                    if not widget._undo_stack or widget._undo_stack[-1] != curr:
                        widget._undo_stack.append(curr)
                    nxt = widget._redo_stack.pop()
                    widget.delete(0, tk.END)
                    widget.insert(0, nxt)
            except: pass
            return "break"

        widget.bind("<FocusIn>", save_state, add="+")
        widget.bind("<FocusOut>", save_state, add="+")
        widget.bind("<<Paste>>", on_paste, add="+")
        widget.bind("<Control-v>", on_paste, add="+")
        widget.bind("<<Cut>>", on_paste, add="+")
        widget.bind("<Control-x>", on_paste, add="+")
        widget.bind("<KeyRelease-space>", save_state, add="+")
        widget.bind("<Control-z>", do_undo)
        widget.bind("<Control-y>", do_redo)

def add_hover(widget, default_bg, hover_bg):
    widget.bind("<Enter>", lambda e: widget.config(bg=hover_bg))
    widget.bind("<Leave>", lambda e: widget.config(bg=default_bg))

def on_tree_hover(tree, hover_bg="#334155"):
    tree.tag_configure("hover", background=hover_bg)
    
    def motion(event):
        item = tree.identify_row(event.y)
        last_hovered = getattr(tree, "_last_hovered", None)
        
        if item == last_hovered: return
            
        if last_hovered:
            try:
                tags = list(tree.item(last_hovered, "tags"))
                if "hover" in tags:
                    tags.remove("hover")
                    tree.item(last_hovered, tags=tags)
            except: pass
                
        tree._last_hovered = item
        
        if item:
            try:
                tags = list(tree.item(item, "tags"))
                if "hover" not in tags:
                    tags.append("hover")
                    tree.item(item, tags=tags)
            except: pass
                
    def leave(event):
        last_hovered = getattr(tree, "_last_hovered", None)
        if last_hovered:
            try:
                tags = list(tree.item(last_hovered, "tags"))
                if "hover" in tags:
                    tags.remove("hover")
                    tree.item(last_hovered, tags=tags)
            except: pass
        tree._last_hovered = None

    tree.bind("<Motion>", motion)
    tree.bind("<Leave>", leave)

def number_to_words(n, format_type=None):
    if format_type is None:
        try: format_type = fetch_global_settings()[0]
        except: format_type = "Indian Rupees (₹)"
        
    try: 
        raw_n = float(n)
        main_part = int(raw_n)
        # --- THE FIX: Capture the decimal part accurately! ---
        dec_part = int(round((raw_n - main_part) * 100))
    except: return ""
    
    if main_part == 0 and dec_part == 0: 
        if "Dollar" in format_type: return "Zero Dollars Only"
        elif "Euro" in format_type: return "Zero Euros Only"
        elif "Pound" in format_type: return "Zero Pounds Only"
        else: return "Zero Rupees Only"

    words = {0:"", 1:"One", 2:"Two", 3:"Three", 4:"Four", 5:"Five", 6:"Six", 7:"Seven", 8:"Eight", 9:"Nine", 10:"Ten", 11:"Eleven", 12:"Twelve", 13:"Thirteen", 14:"Fourteen", 15:"Fifteen", 16:"Sixteen", 17:"Seventeen", 18:"Eighteen", 19:"Nineteen", 20:"Twenty", 30:"Thirty", 40:"Forty", 50:"Fifty", 60:"Sixty", 70:"Seventy", 80:"Eighty", 90:"Ninety"}
    
    def get_words(num):
        if num == 0: return ""
        elif num < 20: return words[num] + " "
        elif num < 100: return words[(num//10)*10] + (" " + words[num%10] if num%10 != 0 else "") + " "
        else: return words[num//100] + " Hundred " + get_words(num%100)
        
    res = ""
    
    if format_type in ["US Dollar ($)", "Euro (€)", "British Pound (£)", "Generic Number"]:
        n_temp = main_part
        if n_temp >= 1000000000: 
            res += get_words(n_temp // 1000000000) + "Billion "
            n_temp %= 1000000000
        if n_temp >= 1000000: 
            res += get_words(n_temp // 1000000) + "Million "
            n_temp %= 1000000
        if n_temp >= 1000: 
            res += get_words(n_temp // 1000) + "Thousand "
            n_temp %= 1000
        res += get_words(n_temp)
        
        suffix = ""
        dec_name = "Cents"
        if "Dollar" in format_type: suffix = " Dollars"
        elif "Euro" in format_type: suffix = " Euros"
        elif "Pound" in format_type: 
            suffix = " Pounds"
            dec_name = "Pence"
            
        final_str = res.strip() + suffix
        if dec_part > 0:
            if final_str: final_str += " and "
            final_str += f"{get_words(dec_part).strip()} {dec_name}"
        return final_str.strip() + " Only"

    else:
        n_temp = main_part
        if n_temp >= 10000000: 
            res += get_words(n_temp // 10000000) + "Crore "
            n_temp %= 10000000
        if n_temp >= 100000: 
            res += get_words(n_temp // 100000) + "Lakh "
            n_temp %= 100000
        if n_temp >= 1000: 
            res += get_words(n_temp // 1000) + "Thousand "
            n_temp %= 1000
        res += get_words(n_temp)
        
        final_str = res.strip() + " Rupees"
        if main_part == 0:
            final_str = "" # Handle edge case where value is < ₹1
        if dec_part > 0:
            if final_str: final_str += " and "
            final_str += f"{get_words(dec_part).strip()} Paise"
            
        return final_str.strip() + " Only"

def format_currency(num, format_type=None):
    if format_type is None:
        try: format_type = fetch_global_settings()[0]
        except: format_type = "Indian Rupees (₹)"
        
    try: num = float(num)
    except: num = 0.0
    is_negative = num < 0
    num = abs(num)
    s, *d = str(f"{num:.2f}").split('.')
    dec = "." + d[0] if d else ".00"
    
    if "Indian" in format_type:
        if len(s) <= 3: res = s
        else:
            res = s[-3:]
            s = s[:-3]
            while len(s) > 2:
                res = s[-2:] + "," + res
                s = s[:-2]
            res = s + "," + res
        prefix = "₹ "
    elif "Dollar" in format_type or "Generic" in format_type:
        res = f"{int(s):,}"
        prefix = "$ " if "Dollar" in format_type else ""
    elif "Euro" in format_type:
        res = f"{int(s):,}".replace(",", ".")
        dec = "," + d[0] if d else ",00"
        prefix = "€ "
    elif "Pound" in format_type:
        res = f"{int(s):,}"
        prefix = "£ "
    else:
        if len(s) <= 3: res = s
        else:
            res = s[-3:]
            s = s[:-3]
            while len(s) > 2:
                res = s[-2:] + "," + res
                s = s[:-2]
            res = s + "," + res
        prefix = "₹ "
    sign = "-" if is_negative else ""
    return f"{sign}{prefix}{res}{dec}"

def safe_color(color):
    if not color or str(color).strip() == "": return "#000000"
    return color

def calculate_pagination(settings, items, page_h, top_space, sf, w, dynamic_bottom_px=290):
    bottom_space_last = int(dynamic_bottom_px * sf) 
    bottom_space_normal = int(65 * sf) 
    top_space_page2 = int(85 * sf)
    
    f = settings.get("fonts", {})
    try: font_sz = max(6, int(float(f.get("tr_part", 10)) * sf))
    except: font_sz = int(10 * sf)
    
    cw_slno = settings.get("col_widths", {}).get("slno", 6) / 100.0
    cw_qty = settings.get("col_widths", {}).get("qty", 8) / 100.0
    cw_hsn = settings.get("col_widths", {}).get("hsn", 12) / 100.0
    cw_rate = settings.get("col_widths", {}).get("rate", 12) / 100.0
    cw_days = settings.get("col_widths", {}).get("days", 8) / 100.0
    cw_amt = settings.get("col_widths", {}).get("amt", 14) / 100.0
    cw_part = max(0.05, 1.0 - (cw_slno + cw_qty + cw_hsn + cw_rate + cw_days + cw_amt))
    
    pad = int(20 * sf)
    part_px_w = (cw_part * (w - 2 * pad)) - int(10 * sf)
    chars_per_line = max(1, int(part_px_w / (font_sz * 0.55)))
    
    pages = []
    current_page = []
    current_y = top_space
    
    for idx, item in enumerate(items, 1):
        it = item.get("data", {})
        name = str(it.get("name", ""))
        clean_name = name.replace("@@B@@", "").replace("@@U@@", "")
        
        lines = 0
        for seg in clean_name.split('\n'):
            seg_len = len(seg)
            if seg_len == 0: lines += 1
            else: lines += max(1, seg_len // chars_per_line + (1 if seg_len % chars_per_line > 0 else 0))
            
        item_h = max(int(18 * sf), int(lines * font_sz * 1.2) + int(4 * sf))
        
        req_space = current_y + item_h + int(6 * sf) + bottom_space_normal
        
        if req_space > page_h:
            if not current_page: 
                current_page.append(item)
                pages.append(current_page)
                current_page = []
                current_y = top_space_page2
            else:
                pages.append(current_page)
                current_page = [item] 
                current_y = top_space_page2 + item_h + int(6 * sf)
        else:
            current_page.append(item)
            current_y += item_h + int(6 * sf)
            
    if current_page:
        if current_y + bottom_space_last + int(25 * sf) > page_h:
            pages.append(current_page)
            pages.append([]) 
        else:
            pages.append(current_page)
            
    return pages if pages else [[]]

def enable_safe_scrolling(canvas, window):
    def _on_mousewheel(event):
        w_class = event.widget.winfo_class()
        if w_class in ('Text', 'Listbox', 'ComboboxPopdown'):
            return
        canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        return "break"

    window.bind("<MouseWheel>", _on_mousewheel)

    def _armor_comboboxes(parent):
        for child in parent.winfo_children():
            if child.winfo_class() == 'TCombobox':
                child.bind("<MouseWheel>", _on_mousewheel)
            _armor_comboboxes(child) 

    window.after(50, lambda: _armor_comboboxes(window))

# =====================================================================================
# THE FIX: UNIVERSAL GLOBAL SCROLL LOCK
# Extracts the scroll-lag out of the main files. Use this for the "Death Will" pass-back.
# =====================================================================================
def grab_global_scroll(window, canvas):
    def _on_mousewheel(event):
        try:
            if window.grab_current() and window.grab_current() != window: 
                return
            w_class = event.widget.winfo_class()
            if w_class in ('Text', 'Listbox', 'ComboboxPopdown'): 
                return
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        except: pass
        return "break"
        
    window.bind_all("<MouseWheel>", _on_mousewheel)

# =====================================================================================
# THE FIX: TREEVIEW SCROLL ISOLATION & FREEZE
# Safely traps scroll events within tables so they do not leak into the master canvas.
# =====================================================================================
def isolate_tree_scroll(tree):
    """Binds mouse wheel scrolling securely inside a treeview, breaking event bubbling."""
    def _isolate(event):
        tree.yview_scroll(int(-1 * (event.delta / 120)), "units")
        return "break"
    tree.bind("<MouseWheel>", _isolate)

def freeze_widget_scroll(widget):
    """Completely kills all scroll wheel inputs for a specific widget (e.g. Pinned Footers)."""
    widget.bind("<MouseWheel>", lambda e: "break")