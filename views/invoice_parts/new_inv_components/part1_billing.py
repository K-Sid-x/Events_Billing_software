import tkinter as tk
from tkinter import ttk
import json
import os
import sys

# --- THE FIX: Bulletproof Executable Pathing ---
if getattr(sys, 'frozen', False):
    root_dir = os.path.dirname(sys.executable)
else:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parts_dir = os.path.dirname(current_dir)
    views_dir = os.path.dirname(parts_dir)
    root_dir = os.path.dirname(views_dir)

if root_dir not in sys.path: 
    sys.path.append(root_dir)
# -----------------------------------------------

import database
from views.invoice_parts.helpers import enable_copy_paste, get_date_format_str, smart_date_formatter
from views.invoice_parts.calendar_widget import NativeCalendar
from views.invoice_parts.new_inv_components.billing_modals import open_format_cells, open_invoice_add_party, GST_STATES

class SubjectRichText(tk.Text):
    def __init__(self, master, textvariable, state, char_width=40, **kwargs):
        theme = state.theme  
        kwargs.setdefault("height", 1)
        kwargs.setdefault("bg", theme["bg"])
        kwargs.setdefault("fg", theme["text"])
        kwargs.setdefault("insertbackground", theme["text"])
        kwargs.setdefault("highlightbackground", theme["border"])
        kwargs.setdefault("highlightthickness", 1)
        kwargs.setdefault("relief", "flat")
        
        # --- THE FIX: 'char' wrap fixes Pic 231/232, Font 11 makes it readable! ---
        kwargs.setdefault("wrap", "char")
        kwargs.setdefault("font", ("Arial", 11))
        # --------------------------------------------------------------------------
        
        kwargs.setdefault("width", char_width)
        kwargs.setdefault("padx", 6)
        kwargs.setdefault("pady", 6)
        kwargs.setdefault("spacing3", 3)
        super().__init__(master, **kwargs)
        
        self.textvariable = textvariable
        self.state = state
        self.char_width = char_width
        
        self.tag_configure("bold", font=("Arial", 11, "bold"))
        self.tag_configure("underline", font=("Arial", 11, "underline"))
        self.tag_configure("bold_underline", font=("Arial", 11, "bold underline"))
        
        self.tag_configure("left", justify="left")
        self.tag_configure("center", justify="center")
        self.tag_configure("right", justify="right")
        
        align = getattr(self.state, 'subj_align_var', None)
        self.current_alignment = align.get() if align else "center"
        self.tag_add(self.current_alignment, "1.0", "end")
        
        self.bind("<KeyPress>", self.queue_height_check)
        self.bind("<KeyRelease>", self.queue_height_check)
        self.bind("<Alt-Return>", self.execute_newline)
        self.bind("<Return>", self.bypass_native_return)
        self.bind("<Button-3>", self.trigger_context_menu)
        self.bind("<Tab>", self.custom_focus_next)
        self.bind("<Shift-Tab>", self.custom_focus_prev)
        
        # --- THE FIX: Toggle Shortcuts & Internal Scroll Neutralizer ---
        self.bind("<Control-b>", lambda e: [self.toggle_style("bold"), "break"][1])
        self.bind("<Control-B>", lambda e: [self.toggle_style("bold"), "break"][1])
        self.bind("<Control-u>", lambda e: [self.toggle_style("underline"), "break"][1])
        self.bind("<Control-U>", lambda e: [self.toggle_style("underline"), "break"][1])
        
        self.bind("<MouseWheel>", self.route_scroll_to_canvas)
        # ---------------------------------------------------------------
        
        # --- THE FIX: Listen to external changes (like loading a saved invoice) ---
        self._is_syncing = False
        if hasattr(self, "textvariable") and self.textvariable:
            self.textvariable.trace_add("write", self.on_var_changed)
            
    def on_var_changed(self, *args):
        if getattr(self, "_is_syncing", False): return
        if hasattr(self, "textvariable") and self.textvariable:
            self.set_text(self.textvariable.get())
        # --------------------------------------------------------------------------

    def route_scroll_to_canvas(self, event):
        widget = self.master
        while widget:
            if widget.winfo_class() == 'Canvas':
                widget.yview_scroll(int(-1 * (event.delta / 120)), "units")
                break
            widget = widget.master
        return "break"

    def custom_focus_next(self, event):
        nxt = self.tk_focusNext()
        if nxt: nxt.focus()
        return "break"

    def custom_focus_prev(self, event):
        prv = self.tk_focusPrev()
        if prv: prv.focus()
        return "break"

    def bypass_native_return(self, event):
        self.state.focus_next(event)
        return "break"

    def execute_newline(self, event):
        self.insert(tk.INSERT, "\n")
        self.after(10, self.adjust_height)
        return "break"

    def queue_height_check(self, event):
        if event.keysym in ('Up', 'Down', 'Left', 'Right', 'Alt_L', 'Alt_R', 'Escape', 'Control_L', 'Control_R', 'Shift_L', 'Shift_R'): 
            return
        # --- THE FIX: Wait for Tkinter to visually drop the text before math ---
        self.after(10, self.adjust_height)

    def adjust_height(self):
        self.update_idletasks()
        total_lines = 1
        if self.winfo_ismapped():
            try:
                line_count_data = self.count("1.0", "end-1c", "displaylines")
                if line_count_data is not None:
                    # --- THE FIX: Tkinter counts breaks, not lines. Add + 1! ---
                    count_val = line_count_data[0] if isinstance(line_count_data, tuple) else line_count_data
                    total_lines = count_val + 1
            except: pass
            
        # --- THE FIX: Catch the invisible blank line created by Alt+Enter ---
        if self.get("1.0", "end-1c").endswith("\n"):
            total_lines += 1
            
        self.config(height=max(1, total_lines))
        self.tag_add(self.current_alignment, "1.0", "end")
        self.yview_moveto(0.0)
        self.see(tk.INSERT)  # --- THE FIX: Keep cursor permanently locked in view! ---
        self.sync_data()
        self.after(10, self.refresh_parent_canvas)

    def refresh_parent_canvas(self):
        widget = self.master
        while widget:
            if widget.winfo_class() == 'Canvas':
                widget.update_idletasks()
                bbox = widget.bbox("all")
                if bbox: widget.configure(scrollregion=(0, 0, bbox[2] + 40, bbox[3] + 40))
                break
            widget = widget.master

    def set_text(self, text_content):
        self.delete("1.0", tk.END)
        has_bold = "@@B@@" in text_content
        has_under = "@@U@@" in text_content
        clean_text = text_content.replace("@@B@@", "").replace("@@U@@", "")
        self.insert("1.0", clean_text)
        
        if has_bold and has_under: self.tag_add("bold_underline", "1.0", tk.END)
        elif has_bold: self.tag_add("bold", "1.0", tk.END)
        elif has_under: self.tag_add("underline", "1.0", tk.END)
        self.adjust_height()

    def sync_data(self):
        raw_text = self.get("1.0", "end-1c")
        has_bold = False
        has_under = False
        
        for tag in self.tag_names():
            if tag in ("bold", "bold_underline") and self.tag_ranges(tag): has_bold = True
            if tag in ("underline", "bold_underline") and self.tag_ranges(tag): has_under = True
            
        prefix = ""
        if has_bold: prefix += "@@B@@"
        if has_under: prefix += "@@U@@"
        
        self.textvariable.set(prefix + raw_text)

    def trigger_context_menu(self, event):
        theme = self.state.theme
        menu = tk.Menu(self, tearoff=0, bg=theme["card"], fg=theme["text"], activebackground=theme["accent_blue"], activeforeground="#ffffff")
        has_selection = False
        try:
            if self.tag_ranges("sel"): has_selection = True
        except: pass

        if has_selection:
            menu.add_command(label="B  Bold", font=("Arial", 11, "bold"), command=lambda: self.toggle_style("bold"))
            menu.add_command(label="U  Underline", font=("Arial", 11, "underline"), command=lambda: self.toggle_style("underline"))
            menu.add_separator()
            menu.add_command(label="⎚ Clear Style", command=self.wipe_styles)
        menu.post(event.x_root, event.y_root)

    def toggle_style(self, style_tag):
        try:
            start, end = self.index("sel.first"), self.index("sel.last")
            current_tags = self.tag_names(start)
            
            # --- THE FIX: Smartly detect if they are active, even if combined! ---
            is_bold = "bold" in current_tags or "bold_underline" in current_tags
            is_under = "underline" in current_tags or "bold_underline" in current_tags
            
            # 1. Wipe the slate clean
            self.tag_remove("bold", start, end)
            self.tag_remove("underline", start, end)
            self.tag_remove("bold_underline", start, end)
            
            # 2. Toggle the specific switch they pressed
            if style_tag == "bold":
                is_bold = not is_bold 
            elif style_tag == "underline":
                is_under = not is_under 
                
            # 3. Re-apply the correct final state
            if is_bold and is_under:
                self.tag_add("bold_underline", start, end)
            elif is_bold:
                self.tag_add("bold", start, end)
            elif is_under:
                self.tag_add("underline", start, end)
                
            self.sync_data()
        except Exception: pass

    def wipe_styles(self):
        try:
            start, end = self.index("sel.first"), self.index("sel.last")
            self.tag_remove("bold", start, end)
            self.tag_remove("underline", start, end)
            self.tag_remove("bold_underline", start, end)
            self.sync_data()
        except: pass

    def set_alignment(self, align_mode):
        self.tag_remove("left", "1.0", "end")
        self.tag_remove("center", "1.0", "end")
        self.tag_remove("right", "1.0", "end")
        self.current_alignment = align_mode
        self.tag_add(align_mode, "1.0", "end")


def build_part_1(parent, state):
    theme = state.theme  

    global_date_fmt = get_date_format_str()
    state.date_fmt_code = global_date_fmt 

    # --- THE FIX: Point the New Invoice Screen at the correct Database Cabinet! ---
    comp_id = getattr(state.view.winfo_toplevel(), "active_company_id", 1)
    
    saved_fmt = ""
    saved_custom = "MSE/<FY>/000"
    
    # 1. Look inside the actual Company Profile JSON where the data is stored
    comp_data = database.get_company(comp_id)
    if comp_data and len(comp_data) > 14 and comp_data[14]:
        try:
            j_data = json.loads(comp_data[14])
            saved_fmt = j_data.get("invoice_format", "")
            saved_custom = j_data.get("custom_inv_format", "MSE/<FY>/000")
        except: pass

    # 2. Apply it flawlessly to the New Invoice State
    if saved_fmt:
        state.inv_format = saved_fmt
        state.saved_custom_format = saved_custom
        
        if not getattr(state, "is_edit_mode", False):
            state.current_inv_count = state.get_format_count(state.inv_format)
            state.inv_number = state.get_formatted_inv_num(state.inv_format, state.current_inv_count)
            state.inv_num_var.set(state.inv_number)
    # ------------------------------------------------------------------------------

    if hasattr(state, 'inv_date_var') and state.inv_date_var.get():
        state.inv_date_var.set(smart_date_formatter(state.inv_date_var.get(), global_date_fmt))

    def drop_focus(event):
        w_class = event.widget.winfo_class()
        if w_class not in ('Entry', 'Text', 'TCombobox', 'Listbox', 'Button'):
            state.popup.focus_set()
    state.popup.bind("<Button-1>", drop_focus, add="+")

    # --- THE FIX: Build Display Map for Alias in Billing Tab ---
    state.full_customers = database.get_all_customers()
    state.customers = []
    if not hasattr(state, 'cust_display_map'):
        state.cust_display_map = {}
        
    for c in state.full_customers:
        if len(c) > 1 and c[1]:
            db_name = str(c[1]).strip()
            alias = str(c[8]).strip() if len(c) > 8 and c[8] else ""
            
            if alias and f"({alias})" not in db_name:
                disp_name = f"{db_name} ({alias})"
            else:
                disp_name = db_name
                
            state.customers.append(disp_name)
            # --- THE FIX: Map the display name directly to its Database ID! ---
            state.cust_display_map[disp_name] = {"name": db_name, "id": c[0]}
            # ------------------------------------------------------------------
    # -----------------------------------------------------------

    state.existing_inv_nums = []
    state.historical_places = []
    try:
        conn = database.get_connection()
        cur = conn.cursor()
        comp_id = getattr(state.view.winfo_toplevel(), "active_company_id", 1)
        
        # --- THE FIX: Fetch old invoice numbers AND old Place of Service addresses for memory ---
        cur.execute("SELECT invoice_number, place_of_service FROM invoices WHERE is_deleted=0 AND status != 'Draft' AND company_id=?", (comp_id,))
        rows = cur.fetchall()
        
        state.existing_inv_nums = [str(r[0]).strip().lower() for r in rows if r[0]]
        
        # --- THE FIX: Load Blacklist, Custom Subjects, and Extract! ---
        state.subject_blacklist = []
        state.subject_custom = []
        state.place_blacklist = []
        state.place_custom = []
        
        try:
            with open(os.path.join(root_dir, f"subject_blacklist_{comp_id}.json"), "r") as f:
                state.subject_blacklist = json.load(f)
        except: pass
        try:
            with open(os.path.join(root_dir, f"subject_custom_{comp_id}.json"), "r") as f:
                state.subject_custom = json.load(f)
        except: pass
        
        try:
            with open(os.path.join(root_dir, f"place_blacklist_{comp_id}.json"), "r") as f:
                state.place_blacklist = json.load(f)
        except: pass
        try:
            with open(os.path.join(root_dir, f"place_custom_{comp_id}.json"), "r") as f:
                state.place_custom = json.load(f)
        except: pass

        places_set = set()
        subj_set = set()
        
        for r in rows:
            p_str = r[1]
            if p_str and "@@SERV@@" in p_str:
                import re
                m_serv = re.search(r'@@SERV@@(.*?)@@', p_str + "@@", re.DOTALL)
                if m_serv:
                    parts = m_serv.group(1).split('||')
                    if len(parts) > 1 and parts[1].strip():
                        clean_place = parts[1].strip()
                        if clean_place not in state.place_blacklist:
                            places_set.add(clean_place)
                
                m_subj = re.search(r'@@SUBJ@@(.*?)@@', p_str + "@@", re.DOTALL)
                if m_subj:
                    subj_parts = m_subj.group(1).split('||')
                    if len(subj_parts) > 0 and subj_parts[0].strip():
                        clean_subj = subj_parts[0].strip()
                        if clean_subj not in state.subject_blacklist:
                            subj_set.add(clean_subj)
            elif p_str and not p_str.startswith("@@"):
                clean_place = p_str.strip()
                if clean_place not in state.place_blacklist:
                    places_set.add(clean_place)
                
        for cs in state.subject_custom:
            if cs not in state.subject_blacklist:
                subj_set.add(cs)
                
        for cp in state.place_custom:
            if cp not in state.place_blacklist:
                places_set.add(cp)
                
        state.historical_places = sorted(list(places_set))
        state.historical_subjects = sorted(list(subj_set))
        # -----------------------------------------------------
        # ----------------------------------------------------------------------------------------
        
        state.original_inv_num_lower = ""
        if getattr(state, "is_edit_mode", False) and state.edit_inv_id:
            # --- THE FIX: Deny VIP Bypass for Drafts! ---
            cur.execute("SELECT status FROM invoices WHERE id=? AND company_id=?", (state.edit_inv_id, comp_id))
            status_row = cur.fetchone()
            is_draft = (status_row and status_row[0] == 'Draft')
            
            edit_inv = database.get_invoice_by_id(state.edit_inv_id)[0] if state.edit_inv_id else None
            if edit_inv and not is_draft:
                state.original_inv_num_lower = str(edit_inv[3]).strip().lower()
            # --------------------------------------------
                
        conn.close()
    except Exception as e: 
        print("Duplicate Engine Error:", e)

    if not hasattr(state, 'subj_align_var'):
        state.subj_align_var = tk.StringVar(value="center")

    header = tk.Frame(parent, bg=theme["bg"], padx=20, pady=15)
    header.pack(fill="x")
    tk.Label(header, text="New Tax Invoice", font=("Arial", 18, "bold"), bg=theme["bg"], fg=theme["text"]).pack(side="left")

    billing_frame = tk.Frame(parent, bg=theme["card"], highlightbackground=theme["border"], highlightthickness=1, padx=20, pady=15)
    billing_frame.pack(fill="x", padx=20)
    
    grid_frame = tk.Frame(billing_frame, bg=theme["card"])
    grid_frame.pack(fill="x", expand=True)
    
    grid_frame.columnconfigure(0, weight=1, uniform="col")
    grid_frame.columnconfigure(1, weight=1, uniform="col")
    grid_frame.columnconfigure(2, weight=1, uniform="col")
    
    col1 = tk.Frame(grid_frame, bg=theme["card"])
    col1.grid(row=0, column=0, sticky="nsew", padx=(0, 15))
    
    col2 = tk.Frame(grid_frame, bg=theme["card"])
    col2.grid(row=0, column=1, sticky="nsew", padx=15)
    
    col3 = tk.Frame(grid_frame, bg=theme["card"])
    col3.grid(row=0, column=2, sticky="nsew", padx=(15, 0))

    tk.Label(col1, text="Billed To (Customer) *", font=("Arial", 10, "bold"), bg=theme["card"], fg=theme["sec"]).pack(anchor="w", pady=(0, 5))

    entry_row = tk.Frame(col1, bg=theme["card"])
    entry_row.pack(fill="x", pady=(0, 15))
    
    btn_add_party = tk.Button(entry_row, text="+ Add Party", font=("Arial", 10, "bold"), bg=theme["border"], fg=theme["text"], cursor="hand2", relief="flat", command=lambda: open_invoice_add_party(state, lookup_customer))
    btn_add_party.pack(side="right", padx=(10, 0), ipady=3, ipadx=10)
    
    cust_ent = tk.Entry(entry_row, textvariable=state.cust_var, font=("Arial", 11), bg=theme["bg"], fg=theme["text"], insertbackground=theme["text"], highlightbackground=theme["border"], highlightthickness=1)
    cust_ent.pack(side="left", fill="x", expand=True, ipady=4)
    enable_copy_paste(cust_ent)
    
    info_card = tk.Frame(col1, bg=theme["card"])
    info_card.pack(anchor="nw", fill="x", pady=(5, 10))

    state.cust_addr_display_var = tk.StringVar(value="N/A")
    state.cust_state_display_var = tk.StringVar(value="N/A")
    state.cust_code_display_var = tk.StringVar(value="N/A")
    state.cust_phone_var = tk.StringVar(value="N/A")
    state.cust_gst_var = tk.StringVar(value="N/A")

    row_addr = tk.Frame(info_card, bg=theme["card"])
    row_addr.pack(fill="x", pady=4)
    tk.Label(row_addr, text="Address:", bg=theme["card"], fg=theme["sec"], font=("Arial", 11), width=7, anchor="nw").pack(side="left", anchor="nw", padx=(0,0))
    addr_val = tk.Label(row_addr, textvariable=state.cust_addr_display_var, bg=theme["card"], fg=theme["text"], font=("Arial", 11, "bold"), anchor="nw", justify="left")
    addr_val.pack(side="left", fill="x", expand=True)
    addr_val.bind("<Configure>", lambda e, l=addr_val: l.config(wraplength=e.width) if e.width > 10 else None)

    row_pg = tk.Frame(info_card, bg=theme["card"])
    row_pg.pack(fill="x", pady=4)
    tk.Label(row_pg, text="Phone:", bg=theme["card"], fg=theme["sec"], font=("Arial", 11), width=7, anchor="nw").pack(side="left", anchor="nw", padx=(0,0))
    tk.Label(row_pg, textvariable=state.cust_phone_var, bg=theme["card"], fg=theme["text"], font=("Arial", 11, "bold"), anchor="nw").pack(side="left", padx=(0, 15))
    
    # --- THE FIX: We dynamically hide the GSTIN, State, and Code for Non-GST companies ---
    if getattr(state, 'has_gst', True):
        tk.Label(row_pg, text="GSTIN:", bg=theme["card"], fg=theme["sec"], font=("Arial", 11)).pack(side="left", anchor="nw", padx=(0,5))
        tk.Label(row_pg, textvariable=state.cust_gst_var, bg=theme["card"], fg=theme["text"], font=("Arial", 11, "bold"), anchor="nw").pack(side="left")

        row_sc = tk.Frame(info_card, bg=theme["card"])
        row_sc.pack(fill="x", pady=4)
        tk.Label(row_sc, text="State:", bg=theme["card"], fg=theme["sec"], font=("Arial", 11), width=7, anchor="nw").pack(side="left", anchor="nw", padx=(0,0))
        tk.Label(row_sc, textvariable=state.cust_state_display_var, bg=theme["card"], fg=theme["text"], font=("Arial", 11, "bold"), anchor="nw").pack(side="left", padx=(0, 15))
        tk.Label(row_sc, text="Code:", bg=theme["card"], fg=theme["sec"], font=("Arial", 11)).pack(side="left", anchor="nw", padx=(0,5))
        tk.Label(row_sc, textvariable=state.cust_code_display_var, bg=theme["card"], fg=theme["text"], font=("Arial", 11, "bold"), anchor="nw").pack(side="left")

    cust_list = tk.Listbox(state.popup, font=("Arial", 11), bg=theme["bg"], fg=theme["text"], selectbackground=theme["accent_blue"], highlightthickness=1, highlightbackground=theme["border"])
    
    # --- THE FIX: Accept target_id and prioritize exact ID matches! ---
    def lookup_customer(name, target_id=None):
        state.cust_phone_var.set("N/A")
        state.cust_gst_var.set("N/A")
        state.cust_addr_display_var.set("N/A")
        state.cust_state_display_var.set("N/A")
        state.cust_code_display_var.set("N/A")
        state.cust_id = None 
        
        if not name.strip(): return
        
        for c in getattr(state, "full_customers", []):
            is_match = False
            # If we know the exact ID, strictly match it!
            if target_id and c[0] == target_id:
                is_match = True
            # Otherwise, fallback to the text name
            elif not target_id and len(c) > 1 and str(c[1]).strip().lower() == name.strip().lower():
                is_match = True
                
            if is_match:
                state.cust_id = c[0]
    # ------------------------------------------------------------------
                raw_p = str(c[2]).strip() if len(c) > 2 and c[2] else "" 
                phone = raw_p.split(",")[0].split(":")[-1].strip() if raw_p and raw_p != "None" else ""
                if phone.lower() in ["not provided", "none", "null", "-", ""]: phone = "N/A"
                state.cust_phone_var.set(phone)
                
                gst = str(c[3]).strip() if len(c) > 3 and c[3] else ""
                if gst.lower() in ["not provided", "none", "null", "-", ""]: gst = "N/A"
                state.cust_gst_var.set(gst)

                raw_addr = str(c[5]).strip() if len(c) > 5 and c[5] else ""
                
                cust_addr = raw_addr
                cust_state = "N/A"
                cust_code = "N/A"
                
                for idx in range(6, len(c)):
                    val = str(c[idx]).strip()
                    if val in GST_STATES.values(): cust_state = val
                    elif val in GST_STATES.keys(): cust_code = val
                
                if raw_addr.startswith("{"):
                    try:
                        j = json.loads(raw_addr)
                        cust_addr = j.get("address", "").strip()
                        if cust_state == "N/A" or not cust_state: cust_state = j.get("state", "N/A")
                        if cust_code == "N/A" or not cust_code: cust_code = j.get("state_code", j.get("code", "N/A"))
                    except: pass
                    
                if not cust_addr or cust_addr.lower() in ["none", "null"]: cust_addr = "N/A"
                state.cust_addr_display_var.set(cust_addr)
                
                if cust_code == "N/A" and gst != "N/A" and len(gst) >= 2:
                    cust_code = gst[:2]
                    for key, val in GST_STATES.items():
                        if key == cust_code:
                            cust_state = val.split(',')[0].strip()
                            break
                            
                state.cust_state_display_var.set(cust_state)
                state.cust_code_display_var.set(cust_code)

                comp_code = "N/A"
                if getattr(state, "comp", None) and len(state.comp) > 9 and state.comp[9]:
                    c_gst = str(state.comp[9]).strip()
                    if len(c_gst) >= 2 and c_gst[:2].isdigit():
                        comp_code = c_gst[:2]
                        
                if hasattr(state, "tax_type_var"):
                    if cust_code == "N/A" or comp_code == "N/A":
                        state.tax_type_var.set("Local (CGST + SGST)")
                    elif cust_code == comp_code:
                        state.tax_type_var.set("Local (CGST + SGST)")
                    else:
                        state.tax_type_var.set("Inter-State (IGST)")
                break

    state.lookup_customer_cb = lookup_customer

    def on_cust_key(e):
        if e.keysym in ('Up', 'Down', 'Left', 'Right', 'Return', 'Escape', 'Tab'): return
        val = state.cust_var.get().strip()
        hits = [c for c in state.customers if val.lower() in c.lower()] if val else state.customers
        if hits:
            cust_list.delete(0, tk.END)
            for h in hits: cust_list.insert(tk.END, h)
            lh = min(len(hits), 5) * 22
            cust_list.place(in_=cust_ent, x=0, rely=1.0, relwidth=1.0, height=lh)
            cust_list.lift()
        else:
            cust_list.place_forget()

    def on_cust_focus(e):
        val = state.cust_var.get().strip()
        if not val:
            hits = state.customers
            if hits:
                cust_list.delete(0, tk.END)
                for h in hits: cust_list.insert(tk.END, h)
                lh = min(len(hits), 5) * 22
                cust_list.place(in_=cust_ent, x=0, rely=1.0, relwidth=1.0, height=lh)
                cust_list.lift()

    def on_cust_up(e):
        if not cust_list.winfo_ismapped(): return
        sel = cust_list.curselection()
        if not sel: cust_list.selection_set(0)
        elif sel[0] > 0:
            cust_list.selection_clear(0, tk.END)
            cust_list.selection_set(sel[0]-1)
            cust_list.see(sel[0]-1)

    def on_cust_down(e):
        if not cust_list.winfo_ismapped(): return
        sel = cust_list.curselection()
        if not sel: cust_list.selection_set(0)
        elif sel[0] < cust_list.size()-1:
            cust_list.selection_clear(0, tk.END)
            cust_list.selection_set(sel[0]+1)
            cust_list.see(sel[0]+1)

    # --- THE FIX: Pass the precise ID to the lookup engine ---
    def on_cust_enter(e):
        if cust_list.winfo_ismapped() and cust_list.curselection():
            chosen_disp = cust_list.get(cust_list.curselection())
            map_data = state.cust_display_map.get(chosen_disp)
            if map_data:
                actual_name = map_data["name"]
                target_id = map_data["id"]
            else:
                actual_name = chosen_disp
                target_id = None
            state.cust_var.set(actual_name)
            cust_list.place_forget()
            cust_ent.icursor(tk.END)
            lookup_customer(actual_name, target_id)
            return "break"
        else:
            lookup_customer(state.cust_var.get(), getattr(state, "cust_id", None))
            state.focus_next(e)

    def on_cust_click(e):
        if cust_list.curselection():
            chosen_disp = cust_list.get(cust_list.curselection())
            map_data = state.cust_display_map.get(chosen_disp)
            if map_data:
                actual_name = map_data["name"]
                target_id = map_data["id"]
            else:
                actual_name = chosen_disp
                target_id = None
            state.cust_var.set(actual_name)
            cust_list.place_forget()
            cust_ent.icursor(tk.END)
            lookup_customer(actual_name, target_id)
    # ---------------------------------------------------------

    def hide_cust_list(e):
        state.popup.after(200, cust_list.place_forget)
        lookup_customer(state.cust_var.get(), getattr(state, "cust_id", None))

    cust_ent.bind("<KeyRelease>", on_cust_key)
    cust_ent.bind("<FocusIn>", on_cust_focus)
    cust_ent.bind("<FocusOut>", hide_cust_list)
    cust_ent.bind("<Up>", on_cust_up)
    cust_ent.bind("<Down>", on_cust_down)
    cust_ent.bind("<Return>", on_cust_enter)
    cust_ent.bind("<Tab>", lambda e: [cust_list.place_forget(), lookup_customer(state.cust_var.get()), "continue"])
    cust_list.bind("<ButtonRelease-1>", on_cust_click)


    # ==========================================
    # COLUMN 2: PLACE OF SERVICE (SHIPPING)
    # ==========================================
    tk.Label(col2, text="Place of Service (Details)", font=("Arial", 10, "bold"), bg=theme["card"], fg=theme["sec"]).pack(anchor="w", pady=(0, 5))
    
    def add_field(parent_frame, label, var, has_calendar=False, is_range=False, var_to=None):
        f = tk.Frame(parent_frame, bg=theme["card"])
        f.pack(anchor="w", fill="x", pady=(0, 10)) 
        
        tk.Label(f, text=label, bg=theme["card"], fg=theme["sec"], font=("Arial", 9, "bold")).pack(anchor="w", pady=(0,2))
        
        inp_f = tk.Frame(f, bg=theme["card"])
        inp_f.pack(anchor="w", fill="x")
        
        if not has_calendar and not is_range:
            ent = tk.Entry(inp_f, textvariable=var, font=("Arial", 11), bg=theme["bg"], fg=theme["text"], insertbackground=theme["text"], highlightbackground=theme["border"], highlightthickness=1)
            ent.pack(side="left", fill="x", expand=True, ipady=3)
        else:
            ent = tk.Entry(inp_f, textvariable=var, font=("Arial", 11), width=12, bg=theme["bg"], fg=theme["text"], insertbackground=theme["text"], highlightbackground=theme["border"], highlightthickness=1)
            ent.pack(side="left", ipady=3)
            
        enable_copy_paste(ent); ent.bind("<Return>", state.focus_next)
        
        if has_calendar:
            btn_cal1 = tk.Button(inp_f, text="📅", bg=theme["border"], fg=theme["text"], relief="flat", cursor="hand2")
            btn_cal1.pack(side="left", padx=5)
            btn_cal1.config(command=lambda b=btn_cal1: NativeCalendar(state.popup, var, anchor_widget=b))
        
        if is_range and var_to:
            tk.Label(inp_f, text="to", bg=theme["card"], fg=theme["text"]).pack(side="left", padx=(5, 5))
            ent2 = tk.Entry(inp_f, textvariable=var_to, font=("Arial", 11), width=12, bg=theme["bg"], fg=theme["text"], insertbackground=theme["text"], highlightbackground=theme["border"], highlightthickness=1)
            ent2.pack(side="left", ipady=3)
            enable_copy_paste(ent2); ent2.bind("<Return>", state.focus_next)
            
            btn_cal2 = tk.Button(inp_f, text="📅", bg=theme["border"], fg=theme["text"], relief="flat", cursor="hand2")
            btn_cal2.pack(side="left", padx=2)
            btn_cal2.config(command=lambda b=btn_cal2: NativeCalendar(state.popup, var_to, anchor_widget=b, ref_date_var=var))
            
            tk.Button(inp_f, text="Clear", bg=theme["bg"], fg=theme["text"], relief="flat", cursor="hand2", command=lambda: var_to.set("")).pack(side="left", padx=2)
            
        return ent 

    # --- THE FIX: Smart Memory Autocomplete for Place of Service ---
    addr_ent = add_field(col2, "Address:", state.serv_addr_var)
    add_field(col2, "Delivery Date:", state.serv_del_var, has_calendar=True)
    add_field(col2, "Bill Period:", state.serv_bill_from_var, has_calendar=True, is_range=True, var_to=state.serv_bill_to_var)
    
    place_list = tk.Listbox(state.popup, font=("Arial", 11), bg=theme["bg"], fg=theme["text"], selectbackground=theme["accent_blue"], highlightthickness=1, highlightbackground=theme["border"])
    
    def on_place_key(e):
        if e.keysym in ('Up', 'Down', 'Left', 'Right', 'Return', 'Escape', 'Tab'): return
        val = state.serv_addr_var.get().strip()
        hits = [p for p in state.historical_places if val.lower() in p.lower()] if val else state.historical_places
        if hits:
            place_list.delete(0, tk.END)
            for h in hits: place_list.insert(tk.END, h)
            lh = min(len(hits), 5) * 22
            place_list.place(in_=addr_ent, x=0, rely=1.0, relwidth=1.0, height=lh)
            place_list.lift()
        else:
            place_list.place_forget()

    def on_place_focus(e):
        val = state.serv_addr_var.get().strip()
        hits = [p for p in state.historical_places if val.lower() in p.lower()] if val else state.historical_places
        if hits:
            place_list.delete(0, tk.END)
            for h in hits: place_list.insert(tk.END, h)
            lh = min(len(hits), 5) * 22
            place_list.place(in_=addr_ent, x=0, rely=1.0, relwidth=1.0, height=lh)
            place_list.lift()

    def on_place_up(e):
        if not place_list.winfo_ismapped(): return
        sel = place_list.curselection()
        if not sel: place_list.selection_set(0)
        elif sel[0] > 0:
            place_list.selection_clear(0, tk.END)
            place_list.selection_set(sel[0]-1)
            place_list.see(sel[0]-1)

    def on_place_down(e):
        if not place_list.winfo_ismapped(): return
        sel = place_list.curselection()
        if not sel: place_list.selection_set(0)
        elif sel[0] < place_list.size()-1:
            place_list.selection_clear(0, tk.END)
            place_list.selection_set(sel[0]+1)
            place_list.see(sel[0]+1)

    def on_place_enter(e):
        if place_list.winfo_ismapped() and place_list.curselection():
            chosen = place_list.get(place_list.curselection())
            state.serv_addr_var.set(chosen)
            place_list.place_forget()
            addr_ent.icursor(tk.END)
            return "break"
        else:
            state.focus_next(e)
            return "break"

    def on_place_click(e):
        if place_list.curselection():
            chosen = place_list.get(place_list.curselection())
            state.serv_addr_var.set(chosen)
            place_list.place_forget()
            addr_ent.icursor(tk.END)

    def hide_place_list(e):
        state.popup.after(200, place_list.place_forget)

    addr_ent.bind("<KeyRelease>", on_place_key)
    addr_ent.bind("<FocusIn>", on_place_focus)
    addr_ent.bind("<FocusOut>", hide_place_list)
    addr_ent.bind("<Up>", on_place_up)
    addr_ent.bind("<Down>", on_place_down)
    addr_ent.bind("<Return>", on_place_enter)
    addr_ent.bind("<Tab>", lambda e: [place_list.place_forget(), "continue"])
    place_list.bind("<ButtonRelease-1>", on_place_click)
    # ---------------------------------------------------------------


    # ==========================================
    # COLUMN 3: INVOICE MASTER DATA
    # ==========================================
    col3_head = tk.Frame(col3, bg=theme["card"])
    col3_head.pack(anchor="w", fill="x", pady=(0, 5))
    tk.Label(col3_head, text="Invoice Details", font=("Arial", 10, "bold"), bg=theme["card"], fg=theme["sec"]).pack(side="left")

    # --- THE FIX: Manage Suggestions with Tabs (Invoice Safe - No SQL Drops) ---
    def open_suggestion_manager():
        mgr = tk.Toplevel(state.popup)
        mgr.title("Manage Suggestions")
        mgr.configure(bg=theme["bg"])
        mgr.transient(state.popup)
        mgr.grab_set()
        
        window_width = 550
        x = state.popup.winfo_rootx() + (state.popup.winfo_width() // 2) - (window_width // 2)
        y = state.popup.winfo_rooty() + 100
        mgr.geometry(f"{window_width}x450+{x}+{y}")

        header_f = tk.Frame(mgr, bg=theme["bg"])
        header_f.pack(fill="x", padx=15, pady=10)
        tk.Label(header_f, text="Manage Suggestions", font=("Segoe UI", 12, "bold"), bg=theme["bg"], fg=theme["text"]).pack(side="left")
        tk.Label(mgr, text="(Double-Click or Right-Click an item to edit/delete)", font=("Segoe UI", 9, "italic"), bg=theme["bg"], fg=theme["sec"]).pack(pady=(0, 5))

        style = ttk.Style(mgr)
        
        # --- THE FIX: Force tabs to respect your custom Dark/Light UI theme ---
        if os.name == 'nt': style.theme_use('default') 
        style.configure("SuggestMgr.TNotebook", background=theme["bg"], borderwidth=0)
        style.configure("SuggestMgr.TNotebook.Tab", font=("Segoe UI", 10, "bold"), padding=[10, 5], background=theme["card"], foreground=theme["text"], borderwidth=0)
        style.map("SuggestMgr.TNotebook.Tab", background=[("selected", theme["accent_blue"]), ("!selected", theme["card"])], foreground=[("selected", "#ffffff"), ("!selected", theme["text"])])
        
        style.configure("ItemMgr.Treeview", font=("Segoe UI", 11), rowheight=28, background=theme["card"], fieldbackground=theme["card"], foreground=theme["text"], borderwidth=0)
        style.configure("ItemMgr.Treeview.Heading", font=("Segoe UI", 10, "bold"), background=theme["bg"], foreground=theme["text"])
        style.map("ItemMgr.Treeview", background=[("selected", theme["accent_blue"])], foreground=[("selected", "#ffffff")])

        notebook = ttk.Notebook(mgr, style="SuggestMgr.TNotebook")
        notebook.pack(fill="both", expand=True, padx=15, pady=5)
        
        def build_tab(tab_name, data_list, blacklist, custom_list, is_subject):
            tab_frame = tk.Frame(notebook, bg=theme["bg"])
            notebook.add(tab_frame, text=tab_name)
            
            # --- THE FIX: Pack Buttons FIRST at the bottom so they NEVER get pushed offscreen! ---
            btn_f = tk.Frame(tab_frame, bg=theme["bg"])
            btn_f.pack(side="bottom", fill="x", pady=10)
            
            btn_bulk_del = tk.Button(btn_f, text="🗑 Delete Selected (0)", bg=theme.get("error", "#ef4444"), fg="#ffffff", font=("Segoe UI", 10, "bold"), relief="flat", cursor="hand2")
            btn_cancel_bulk = tk.Button(btn_f, text="✖ Cancel Bulk", bg=theme["border"], fg=theme["text"], font=("Segoe UI", 10, "bold"), relief="flat", cursor="hand2")
            # -------------------------------------------------------------------------------------

            # Pack the list explicitly AFTER the buttons so it fills the remaining space
            list_frame = tk.Frame(tab_frame, bg=theme["bg"])
            list_frame.pack(side="top", fill="both", expand=True)
            
            scrollbar = ttk.Scrollbar(list_frame)
            scrollbar.pack(side="right", fill="y")
            
            tree = ttk.Treeview(list_frame, columns=("check", "sno", "item"), displaycolumns=("sno", "item"), show="headings", yscrollcommand=scrollbar.set, style="ItemMgr.Treeview")
            tree.pack(side="left", fill="both", expand=True)
            scrollbar.config(command=tree.yview)
            
            tree.heading("check", text="[ ]")
            tree.heading("sno", text="SI No.")
            tree.heading("item", text="Name", anchor="w")
            
            tree.column("check", width=40, anchor="center", stretch=False)
            tree.column("sno", width=60, anchor="center", stretch=False)
            tree.column("item", width=400, anchor="w", stretch=True)
            
            tree.tag_configure("even", background=theme["bg"], foreground=theme["text"])
            tree.tag_configure("odd", background=theme["card"], foreground=theme["text"])
            
            is_bulk_mode = [False]
            selected_items = set()
            sorted_keys = []
            
            def refresh_list():
                for i in tree.get_children(): tree.delete(i)
                nonlocal sorted_keys
                sorted_keys = sorted(data_list, key=str.lower)
                
                for idx, item_name in enumerate(sorted_keys):
                    tag = "even" if idx % 2 == 0 else "odd"
                    chk = "[✓]" if item_name in selected_items else "[ ]"
                    tree.insert("", "end", iid=item_name, values=(chk, idx + 1, item_name.replace("@@B@@", "").replace("@@U@@", "")), tags=(tag,))
                    
                for i in range(len(sorted_keys), 12):
                    tag = "even" if i % 2 == 0 else "odd"
                    tree.insert("", "end", iid=f"dummy_{i}", values=("", "", ""), tags=(tag,))
                    
            refresh_list()

            def update_bulk_btn_text():
                btn_bulk_del.config(text=f"🗑 Delete Selected ({len(selected_items)})")

            def toggle_bulk_mode():
                if is_bulk_mode[0]:
                    is_bulk_mode[0] = False
                    selected_items.clear()
                    tree["displaycolumns"] = ("sno", "item")
                    btn_bulk_del.pack_forget()
                    btn_cancel_bulk.pack_forget()
                    refresh_list()
                else:
                    is_bulk_mode[0] = True
                    selected_items.clear()
                    tree["displaycolumns"] = ("check", "sno", "item")
                    btn_bulk_del.pack(side="left", padx=(0, 10))
                    btn_cancel_bulk.pack(side="left")
                    update_bulk_btn_text()
                    refresh_list()

            btn_cancel_bulk.config(command=toggle_bulk_mode)

            def toggle_select_all(e):
                if not is_bulk_mode[0]: return
                region = tree.identify("region", e.x, e.y)
                col = tree.identify_column(e.x)
                if region == "heading" and col == "#1":
                    if len(selected_items) == len(sorted_keys) and len(sorted_keys) > 0:
                        selected_items.clear()
                        tree.heading("check", text="[ ]")
                    else:
                        selected_items.update(sorted_keys)
                        tree.heading("check", text="[✓]")
                    refresh_list()
                    update_bulk_btn_text()

            def on_row_click(e):
                region = tree.identify("region", e.x, e.y)
                if region == "nothing":
                    tree.selection_remove(tree.selection())
                    return
                if region == "cell":
                    iid = tree.identify_row(e.y)
                    if not iid or str(iid).startswith("dummy_"):
                        tree.selection_remove(tree.selection())
                        return
                    if is_bulk_mode[0]:
                        if iid in selected_items: selected_items.remove(iid)
                        else: selected_items.add(iid)
                        refresh_list()
                        update_bulk_btn_text()

            tree.bind("<ButtonRelease-1>", lambda e: toggle_select_all(e) if tree.identify("region", e.x, e.y) == "heading" else on_row_click(e))
            tab_frame.bind("<Button-1>", lambda e: tree.selection_remove(tree.selection()) if e.widget not in (tree, scrollbar) else None)

            def save_lists():
                comp_id = getattr(state.view.winfo_toplevel(), "active_company_id", 1)
                try:
                    if is_subject:
                        with open(os.path.join(root_dir, f"subject_blacklist_{comp_id}.json"), "w") as f:
                            json.dump(blacklist, f)
                        with open(os.path.join(root_dir, f"subject_custom_{comp_id}.json"), "w") as f:
                            json.dump(custom_list, f)
                    else:
                        with open(os.path.join(root_dir, f"place_blacklist_{comp_id}.json"), "w") as f:
                            json.dump(blacklist, f)
                        with open(os.path.join(root_dir, f"place_custom_{comp_id}.json"), "w") as f:
                            json.dump(custom_list, f)
                except: pass

            def start_inline_edit(old_name=None):
                if not old_name:
                    sel = tree.selection()
                    if not sel: return
                    old_name = sel[0]
                if str(old_name).startswith("dummy_"): return
                    
                bbox = tree.bbox(old_name, "item") 
                if not bbox: return
                x_pos, y_pos, w_width, h_height = bbox
                
                edit_ent = tk.Text(tree, font=("Segoe UI", 11), bg=theme["bg"], fg=theme["text"], insertbackground=theme["text"], highlightthickness=1, highlightcolor=theme["accent_blue"], wrap="word")
                edit_ent.place(x=x_pos, y=y_pos, width=w_width, height=max(h_height * 2, 40))
                
                clean_old = old_name.replace("@@B@@", "").replace("@@U@@", "")
                edit_ent.insert("1.0", clean_old)
                edit_ent.focus_set()
                edit_ent.tag_add("sel", "1.0", "end")
                
                def save_edit(e=None):
                    new_name = edit_ent.get("1.0", "end-1c").strip()
                    if new_name and new_name != clean_old:
                        if old_name not in blacklist: blacklist.append(old_name)
                        if old_name in custom_list: custom_list.remove(old_name)
                        if new_name not in custom_list: custom_list.append(new_name)
                        
                        idx = data_list.index(old_name)
                        data_list[idx] = new_name
                        if old_name in selected_items:
                            selected_items.remove(old_name)
                            selected_items.add(new_name)
                        
                        refresh_list()
                        save_lists()
                        
                    if edit_ent.winfo_exists(): edit_ent.destroy()
                    return "break"
                    
                def cancel_edit(e=None):
                    if edit_ent.winfo_exists(): edit_ent.destroy()

                # --- THE FIX: Pushed in 4 spaces so it stays inside start_inline_edit! ---
                edit_ent.bind("<Return>", save_edit)
                edit_ent.bind("<Escape>", cancel_edit)
                edit_ent.bind("<FocusOut>", cancel_edit)

            tree.bind("<Double-Button-1>", lambda e: start_inline_edit() if tree.identify("region", e.x, e.y) == "cell" else None)

            def delete_single_item(target_name):
                import tkinter.messagebox as messagebox
                if messagebox.askyesno("Confirm Delete", f"Are you sure you want to permanently remove '{target_name}'?", parent=mgr):
                    if target_name not in blacklist: blacklist.append(target_name)
                    if target_name in custom_list: custom_list.remove(target_name)
                    data_list.remove(target_name)
                    if target_name in selected_items: selected_items.remove(target_name)
                    refresh_list()
                    save_lists()

            ctx_menu = tk.Menu(mgr, tearoff=0, font=("Segoe UI", 10), bg=theme["card"], fg=theme["text"], activebackground=theme["accent_blue"], activeforeground="#ffffff")
            
            def show_ctx_menu(e):
                iid = tree.identify_row(e.y)
                ctx_menu.delete(0, "end")
                if iid and not str(iid).startswith("dummy_"):
                    tree.selection_set(iid)
                    ctx_menu.add_command(label="✏️ Edit", command=lambda: start_inline_edit(iid))
                    ctx_menu.add_command(label="❌ Delete", foreground=theme.get("error", "#ef4444"), command=lambda: delete_single_item(iid))
                    ctx_menu.add_separator()
                    
                if not is_bulk_mode[0]:
                    ctx_menu.add_command(label="☑ Enable Bulk Delete Mode", command=toggle_bulk_mode)
                else:
                    ctx_menu.add_command(label="☒ Disable Bulk Delete Mode", command=toggle_bulk_mode)
                ctx_menu.tk_popup(e.x_root, e.y_root)
                    
            tree.bind("<Button-3>", show_ctx_menu)

            def execute_bulk_delete():
                if not selected_items: return
                import tkinter.messagebox as messagebox
                if messagebox.askyesno("Confirm Bulk Delete", f"Are you sure you want to permanently remove {len(selected_items)} item(s)?", parent=mgr):
                    for target_name in list(selected_items):
                        if target_name not in blacklist: blacklist.append(target_name)
                        if target_name in custom_list: custom_list.remove(target_name)
                        data_list.remove(target_name)
                    selected_items.clear()
                    toggle_bulk_mode()
                    save_lists()

            btn_bulk_del.config(command=execute_bulk_delete)

        build_tab("Subjects", state.historical_subjects, state.subject_blacklist, state.subject_custom, is_subject=True)
        build_tab("Places of Service", state.historical_places, state.place_blacklist, state.place_custom, is_subject=False)
        
        btn_bot_f = tk.Frame(mgr, bg=theme["bg"])
        btn_bot_f.pack(fill="x", padx=15, pady=10)
        tk.Button(btn_bot_f, text="Close", bg=theme["border"], fg=theme["text"], font=("Segoe UI", 10, "bold"), relief="flat", cursor="hand2", command=mgr.destroy).pack(side="right")

    btn_subj_mgr = tk.Button(col3_head, text="📋 Manage Suggestions", font=("Arial", 10, "bold"), bg=theme["accent_blue"], fg="#ffffff", cursor="hand2", relief="flat", padx=10, pady=2, command=open_suggestion_manager)
    btn_subj_mgr.pack(side="right")
    # ------------------------------------------
    # ------------------------------------------

    tk.Label(col3, text="Invoice No.", font=("Arial", 9, "bold"), bg=theme["card"], fg=theme["sec"]).pack(anchor="w", pady=(0,2))
    inv_f = tk.Frame(col3, bg=theme["card"])
    inv_f.pack(anchor="w", fill="x", pady=(0, 5))
    inv_ent = tk.Entry(inv_f, textvariable=state.inv_num_var, font=("Arial", 13, "bold"), fg=theme["accent_blue"], bg=theme["bg"], highlightbackground=theme["border"], highlightthickness=1, width=14)
    inv_ent.pack(side="left", ipady=3)
    enable_copy_paste(inv_ent)
    
    inv_warn_lbl = tk.Label(col3, text="", font=("Arial", 9, "bold"), bg=theme["card"], fg=theme["error"])
    inv_warn_lbl.pack(anchor="w", pady=(0, 5))
    
    def check_duplicate(*args):
        raw_val = state.inv_num_var.get().strip()
        current = raw_val.lower()
        # If the user typed plain digits (e.g. '12'), also check its formatted version (e.g. 'inv-012') immediately
        formatted_candidate = (
            state.get_formatted_inv_num(state.inv_format, int(raw_val)).strip().lower()
            if raw_val.isdigit() else current
        )
        orig_lower = getattr(state, "original_inv_num_lower", "")

        is_dup = False
        if current and current in state.existing_inv_nums and current != orig_lower:
            is_dup = True
        elif formatted_candidate and formatted_candidate in state.existing_inv_nums and formatted_candidate != orig_lower:
            is_dup = True

        if is_dup:
            inv_warn_lbl.config(text="⚠️ Invoice number already exists!")
        else:
            inv_warn_lbl.config(text="")

    state.inv_num_var.trace_add("write", check_duplicate)
    check_duplicate() # --- THE FIX: Force the initial check on boot! ---
    
    state.current_inv_val = state.inv_number
    def on_inv_focus_in(e):
        state.current_inv_val = state.inv_num_var.get()
        inv_ent.delete(0, 'end') 
    def on_inv_focus_out(e):
        val = state.inv_num_var.get().strip()

        if not val: 
            state.inv_num_var.set(state.current_inv_val) 
        elif val.isdigit():
            # Auto-format plain digits in both New and Edit mode using the active format!
            state.inv_num_var.set(state.get_formatted_inv_num(state.inv_format, int(val)))
        else:
            state.inv_num_var.set(val)
        check_duplicate()
            
    inv_ent.bind("<FocusIn>", on_inv_focus_in)
    inv_ent.bind("<FocusOut>", on_inv_focus_out)
    inv_ent.bind("<Return>", lambda e: [on_inv_focus_out(e), state.focus_next(e)])
    
    fmt_btn = tk.Button(inv_f, text="⚙ Format", font=("Arial", 9, "bold"), bg=theme["border"], fg=theme["text"], relief="flat", cursor="hand2")
    fmt_btn.config(command=lambda b=fmt_btn: open_format_cells(state, b))
    fmt_btn.pack(side="left", padx=(5, 0), ipady=3)

    id_f = tk.Frame(col3, bg=theme["card"]) 
    tk.Label(col3, text="Invoice Date:", font=("Arial", 9, "bold"), bg=theme["card"], fg=theme["sec"]).pack(anchor="w", pady=(0,2))
    id_f.pack(anchor="w", pady=(0, 10))
    id_ent = tk.Entry(id_f, textvariable=state.inv_date_var, font=("Arial", 11), width=15, bg=theme["bg"], fg=theme["text"], insertbackground=theme["text"], highlightbackground=theme["border"], highlightthickness=1)
    id_ent.pack(side="left", ipady=3)
    enable_copy_paste(id_ent)
    id_ent.bind("<Return>", state.focus_next)
    
    btn_id_cal = tk.Button(id_f, text="📅", bg=theme["border"], fg=theme["text"], relief="flat", cursor="hand2")
    btn_id_cal.pack(side="left", padx=5)
    btn_id_cal.config(command=lambda b=btn_id_cal: NativeCalendar(state.popup, state.inv_date_var, anchor_widget=b))
    tk.Button(id_f, text="Clear", bg=theme["bg"], fg=theme["text"], relief="flat", cursor="hand2", command=lambda: state.inv_date_var.set("")).pack(side="left", padx=2)

    tk.Label(col3, text="E-Way Bill:", font=("Arial", 9, "bold"), bg=theme["card"], fg=theme["sec"]).pack(anchor="w", pady=(0,2))
    f_eway = tk.Frame(col3, bg=theme["card"])
    f_eway.pack(anchor="w", fill="x")
    tk.Checkbutton(f_eway, text="Include E-Way Bill", variable=state.inc_eway_var, bg=theme["card"], fg=theme["text"], selectcolor=theme["bg"], activebackground=theme["card"], activeforeground=theme["text"]).pack(anchor="w", pady=(0, 5))
    eway_ent = tk.Entry(col3, textvariable=state.eway_var, font=("Arial", 11), bg=theme["bg"], fg=theme["text"], insertbackground=theme["text"], highlightbackground=theme["border"], highlightthickness=1)
    
    def toggle_eway(*args):
        if state.inc_eway_var.get() == 1: eway_ent.pack(fill="x", ipady=3)
        else: eway_ent.pack_forget(); state.eway_var.set("")
            
    state.inc_eway_var.trace("w", toggle_eway)
    toggle_eway()

    # ==========================================
    # BOTTOM BRIDGE: SUBJECT LINE
    # ==========================================
    f_subj_head = tk.Frame(billing_frame, bg=theme["card"])
    f_subj_head.pack(fill="x", pady=(15, 2))
    
    tk.Label(f_subj_head, text="Subject:", font=("Arial", 10, "bold"), bg=theme["card"], fg=theme["sec"]).pack(side="left")
    
    align_f = tk.Frame(f_subj_head, bg=theme["card"])
    align_f.pack(side="right")
    
    def update_align_btns(*args):
        mode = state.subj_align_var.get()
        btn_l.config(bg=theme["accent_blue"] if mode=="left" else theme["bg"], fg="#ffffff" if mode=="left" else theme["text"])
        btn_c.config(bg=theme["accent_blue"] if mode=="center" else theme["bg"], fg="#ffffff" if mode=="center" else theme["text"])
        btn_r.config(bg=theme["accent_blue"] if mode=="right" else theme["bg"], fg="#ffffff" if mode=="right" else theme["text"])
        if hasattr(state, 'subj_text_widget'): state.subj_text_widget.set_alignment(mode)

    btn_l = tk.Button(align_f, text="⫷", font=("Arial", 9), cursor="hand2", relief="solid", bd=1, highlightbackground=theme["border"], command=lambda: state.subj_align_var.set("left"))
    btn_l.pack(side="left", padx=2)
    btn_c = tk.Button(align_f, text="≣", font=("Arial", 9), cursor="hand2", relief="solid", bd=1, highlightbackground=theme["border"], command=lambda: state.subj_align_var.set("center"))
    btn_c.pack(side="left", padx=2)
    btn_r = tk.Button(align_f, text="⫸", font=("Arial", 9), cursor="hand2", relief="solid", bd=1, highlightbackground=theme["border"], command=lambda: state.subj_align_var.set("right"))
    btn_r.pack(side="left", padx=2)
    
    state.subj_align_var.trace_add("write", update_align_btns)

    subj_container = tk.Frame(billing_frame, bg=theme["card"])
    subj_container.pack(anchor="w", fill="x")
    
    subj_ent = SubjectRichText(subj_container, state.subj_var, state, char_width=40)
    subj_ent.pack(anchor="w", pady=(0, 5), fill="x", expand=True)
    state.subj_text_widget = subj_ent
    
    # --- THE FIX: Subject Autocomplete Logic ---
    subj_list = tk.Listbox(state.popup, font=("Arial", 11), bg=theme["bg"], fg=theme["text"], selectbackground=theme["accent_blue"], highlightthickness=1, highlightbackground=theme["border"])
    
    def on_subj_key(e):
        if e.keysym in ('Up', 'Down', 'Left', 'Right', 'Return', 'Escape', 'Tab', 'Alt_L', 'Alt_R'): return
        val = state.subj_var.get().replace("@@B@@", "").replace("@@U@@", "").strip()
        hits = [s for s in state.historical_subjects if val.lower() in s.lower()] if val else state.historical_subjects
        if hits:
            subj_list.delete(0, tk.END)
            for h in hits: subj_list.insert(tk.END, h.replace("@@B@@", "").replace("@@U@@", ""))
            lh = min(len(hits), 5) * 22
            subj_list.place(in_=subj_ent, x=0, rely=1.0, relwidth=1.0, height=lh)
            subj_list.lift()
        else:
            subj_list.place_forget()

    def on_subj_focus(e):
        val = state.subj_var.get().replace("@@B@@", "").replace("@@U@@", "").strip()
        
        # --- THE FIX: Only auto-drop the list if the subject box is completely empty! ---
        if not val:
            hits = state.historical_subjects
            if hits:
                subj_list.delete(0, tk.END)
                for h in hits: subj_list.insert(tk.END, h.replace("@@B@@", "").replace("@@U@@", ""))
                lh = min(len(hits), 5) * 22
                subj_list.place(in_=subj_ent, x=0, rely=1.0, relwidth=1.0, height=lh)
                subj_list.lift()
        # --------------------------------------------------------------------------------

    def on_subj_up(e):
        if not subj_list.winfo_ismapped(): return
        sel = subj_list.curselection()
        if not sel: subj_list.selection_set(0)
        elif sel[0] > 0:
            subj_list.selection_clear(0, tk.END); subj_list.selection_set(sel[0]-1); subj_list.see(sel[0]-1)

    def on_subj_down(e):
        if not subj_list.winfo_ismapped(): return
        sel = subj_list.curselection()
        if not sel: subj_list.selection_set(0)
        elif sel[0] < subj_list.size()-1:
            subj_list.selection_clear(0, tk.END); subj_list.selection_set(sel[0]+1); subj_list.see(sel[0]+1)

    subj_ent.unbind("<Return>")
    def on_subj_enter(e):
        if subj_list.winfo_ismapped() and subj_list.curselection():
            chosen_clean = subj_list.get(subj_list.curselection())
            original = next((s for s in state.historical_subjects if s.replace("@@B@@", "").replace("@@U@@", "") == chosen_clean), chosen_clean)
            subj_ent.set_text(original)
            subj_list.place_forget()
            return "break"
        else:
            state.focus_next(e)
            return "break"

    def on_subj_click(e):
        if subj_list.curselection():
            chosen_clean = subj_list.get(subj_list.curselection())
            original = next((s for s in state.historical_subjects if s.replace("@@B@@", "").replace("@@U@@", "") == chosen_clean), chosen_clean)
            subj_ent.set_text(original)
            subj_list.place_forget()
            subj_ent.focus_set()
            subj_ent.mark_set(tk.INSERT, "end")

    def hide_subj_list(e):
        state.popup.after(200, subj_list.place_forget)

    subj_ent.bind("<KeyRelease>", on_subj_key, add="+")
    subj_ent.bind("<FocusIn>", on_subj_focus, add="+")
    subj_ent.bind("<FocusOut>", hide_subj_list, add="+")
    subj_ent.bind("<Up>", on_subj_up, add="+")
    subj_ent.bind("<Down>", on_subj_down, add="+")
    subj_ent.bind("<Return>", on_subj_enter)
    subj_list.bind("<ButtonRelease-1>", on_subj_click)
    # -----------------------------------------------

    update_align_btns()