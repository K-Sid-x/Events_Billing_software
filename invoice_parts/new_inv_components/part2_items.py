import tkinter as tk
from tkinter import ttk
from datetime import datetime
import re
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

from views.invoice_parts.helpers import enable_copy_paste, get_date_format_str

class ExpandingRichText(tk.Text):
    def __init__(self, master, textvariable, state, on_change, char_width, **kwargs):
        theme = state.theme  
        kwargs.setdefault("height", 1)
        kwargs.setdefault("bg", theme["bg"])
        kwargs.setdefault("fg", theme["text"])
        kwargs.setdefault("insertbackground", theme["text"])
        kwargs.setdefault("highlightbackground", theme["border"])
        kwargs.setdefault("highlightthickness", 1)
        kwargs.setdefault("relief", "flat")
        
        # --- PREVIOUS FIXES INCLUDED: Char wrap and readable font! ---
        kwargs.setdefault("wrap", "char")
        kwargs.setdefault("font", ("Segoe UI", 11))
        
        kwargs.setdefault("width", char_width)
        kwargs.setdefault("padx", 6)
        kwargs.setdefault("pady", 6)
        kwargs.setdefault("spacing3", 3)
        kwargs.setdefault("exportselection", False) 
        kwargs.setdefault("undo", True)
        kwargs.setdefault("maxundo", 50)
        
        super().__init__(master, **kwargs)
        enable_copy_paste(self)
        
        self.textvariable = textvariable
        self.state = state
        self.on_change = on_change
        self.char_width = char_width
        
        self.tag_configure("bold", font=("Segoe UI", 11, "bold"))
        self.tag_configure("underline", font=("Segoe UI", 11, "underline"))
        self.tag_configure("bold_underline", font=("Segoe UI", 11, "bold underline"))
        
        self.bind("<KeyPress>", self.queue_height_check)
        self.bind("<KeyRelease>", self.queue_height_check)
        self.bind("<Alt-Return>", self.execute_newline)
        self.bind("<Button-3>", self.trigger_formatting_menu)
        
        self.bind("<Tab>", self.custom_focus_next)
        self.bind("<Shift-Tab>", self.custom_focus_prev)
        
        self.bind("<Control-b>", lambda e: [self.toggle_style("bold"), "break"][1])
        self.bind("<Control-B>", lambda e: [self.toggle_style("bold"), "break"][1])
        self.bind("<Control-u>", lambda e: [self.toggle_style("underline"), "break"][1])
        self.bind("<Control-U>", lambda e: [self.toggle_style("underline"), "break"][1])
        
        self.bind("<MouseWheel>", self.route_scroll_to_canvas)
        
        self.bind("<Map>", self.queue_height_check)
        self.bind("<<Paste>>", self.custom_paste)
        self.bind("<Control-v>", self.custom_paste)

    def route_scroll_to_canvas(self, event):
        widget = self.master
        while widget:
            if widget.winfo_class() == 'Canvas':
                widget.yview_scroll(int(-1 * (event.delta / 120)), "units")
                break
            widget = widget.master
        return "break"

    def custom_paste(self, event):
        try:
            clipboard_text = self.clipboard_get()
            clean_text = clipboard_text.rstrip('\n')
            self.edit_separator()
            
            # --- THE FIX: Check for highlighted text and delete it first! ---
            try:
                if self.tag_ranges("sel"):
                    self.delete("sel.first", "sel.last")
            except Exception: pass
            # ----------------------------------------------------------------
            
            self.insert(tk.INSERT, clean_text)
            self.edit_separator()
            self.after(10, self.adjust_height)
            return "break"
        except Exception:
            pass

    def custom_focus_next(self, event):
        nxt = self.tk_focusNext()
        if nxt: nxt.focus()
        return "break" 

    def custom_focus_prev(self, event):
        prv = self.tk_focusPrev()
        if prv: prv.focus()
        return "break"

    def yview(self, *args):
        return "break"
        
    def queue_height_check(self, event=None):
        if event and hasattr(event, "keysym") and event.keysym in ('Up', 'Down', 'Left', 'Right', 'Return', 'Alt_L', 'Alt_R', 'Escape', 'Control_L', 'Control_R', 'Shift_L', 'Shift_R'): 
            return
        self.after(10, self.adjust_height)

    def execute_newline(self, event):
        self.insert(tk.INSERT, "\n")
        self.after(10, self.adjust_height)
        return "break"

    def adjust_height(self):
        self.update_idletasks()
        total_lines = 1
        if self.winfo_ismapped():
            try:
                line_count_data = self.count("1.0", "end-1c", "displaylines")
                if line_count_data is not None:
                    count_val = line_count_data[0] if isinstance(line_count_data, tuple) else line_count_data
                    total_lines = count_val + 1
            except: pass
            
        if self.get("1.0", "end-1c").endswith("\n"):
            total_lines += 1
            
        self.config(height=max(1, total_lines))
        self.yview_moveto(0.0)
        self.see(tk.INSERT)
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
        if hasattr(self, 'on_change') and self.on_change: 
            self.on_change()

    def toggle_style(self, style_tag):
        try:
            start, end = self.index("sel.first"), self.index("sel.last")
            current_tags = self.tag_names(start)
            
            # --- NEW FIX: Smartly detect if they are active, even if combined! ---
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

    def trigger_formatting_menu(self, event):
        try:
            if not self.tag_ranges("sel"): return
        except Exception: return
        
        theme = self.state.theme  
        menu = tk.Menu(self, tearoff=0, bg=theme["card"], fg=theme["text"], activebackground=theme["accent_blue"], activeforeground="#ffffff")
        menu.add_command(label="B  Bold", font=("Segoe UI", 11, "bold"), command=lambda: self.toggle_style("bold"))
        menu.add_command(label="U  Underline", font=("Segoe UI", 11, "underline"), command=lambda: self.toggle_style("underline"))
        menu.add_separator()
        menu.add_command(label="⎚ Clear Style", command=self.wipe_styles)
        menu.post(event.x_root, event.y_root)

    def wipe_styles(self):
        try:
            start, end = self.index("sel.first"), self.index("sel.last")
            self.tag_remove("bold", start, end)
            self.tag_remove("underline", start, end)
            self.tag_remove("bold_underline", start, end)
            self.sync_data()
        except Exception: pass

def build_part_2(parent, state):
    theme = state.theme  

    items_frame = tk.Frame(parent, bg=theme["card"], highlightbackground=theme["border"], highlightthickness=1, padx=20, pady=15)
    items_frame.pack(fill="x", padx=20, pady=10)
    
    items_frame.columnconfigure(1, weight=1)
    
    has_gst = getattr(state, 'has_gst', True)
    
    if has_gst:
        headers = ["Sl. No.", "Particulars", "Qnty", "Unit", "Hsn/sac", "Rate", "Days", "Amount", ""]
        widths = [6, 33, 10, 10, 10, 11, 9, 14, 6]
    else:
        headers = ["Sl. No.", "Particulars", "Qnty", "Unit", "Rate", "Days", "Amount", ""]
        widths = [6, 37, 10, 10, 13, 10, 16, 6]
    
    for c, text in enumerate(headers): 
        tk.Label(items_frame, text=text, font=("Segoe UI", 10, "bold"), bg=theme["border"], fg=theme["text"], borderwidth=1, relief="solid").grid(row=0, column=c, sticky="ew", ipady=8, pady=(0, 10))

    def reindex_rows():
        current_number = 1
        for row_dict in state.item_rows:
            if row_dict["sl_var"].get().strip() != "":
                row_dict["sl_var"].set(str(current_number))
                current_number += 1
        state.calculate_totals()

    def extract_number_from_string(val_str, default_val=1.0):
        if not val_str: return default_val
        try:
            # --- THE FIX: Upgraded Regex to flawlessly capture standalone negative signs like -100 ---
            match = re.search(r'[-+]?\d*\.?\d+', str(val_str))
            return float(match.group()) if match else default_val
        except:
            return default_val

    def add_item_row():
        if not hasattr(state, "last_row_idx"): state.last_row_idx = 0
        state.last_row_idx += 1
        row_idx = state.last_row_idx
        
        next_num = 1
        for r in state.item_rows:
            if r["sl_var"].get().strip() != "": next_num += 1
            
        sl_var = tk.StringVar(value=str(next_num))
        qty_var = tk.StringVar(value="") 
        unit_var = tk.StringVar(value="")
        item_var = tk.StringVar()
        sac_var = tk.StringVar()
        rate_var = tk.StringVar(value="")
        days_var = tk.StringVar(value="")
        amt_var = tk.StringVar(value="0.00")

        def calculate_date_delta_local():
            # --- THE FIX: Prevent populating days if unit is 'None' or '--Select--' ---
            if unit_var.get().strip().lower() in ["none", "--select--", ""]:
                return
                
            f_str = state.serv_bill_from_var.get().strip()
            t_str = state.serv_bill_to_var.get().strip()
            
            if f_str and not t_str:
                days_var.set("1")
                return
            elif not f_str or not t_str:
                return
            
            d1, d2 = None, None
            primary_fmt = getattr(state, "date_fmt_code", get_date_format_str())
            
            for fmt in (primary_fmt, "%Y-%m-%d", "%d.%m.%Y", "%d-%m-%Y", "%d/%m/%Y", "%m/%d/%Y"):
                if not d1:
                    try: d1 = datetime.strptime(f_str, fmt).date()
                    except: pass
                if not d2:
                    try: d2 = datetime.strptime(t_str, fmt).date()
                    except: pass
                
            if d1 and d2:
                if d2 < d1:
                    state.serv_bill_to_var.set(f_str)
                    return 
                computed_days = (d2 - d1).days + 1
                if computed_days > 0: days_var.set(str(computed_days))

        def on_sl_change(*args):
            if getattr(state, "is_swapping", False): return
            if not sl_var.get().strip():
                qty_var.set("")
                unit_var.set("")
                sac_var.set("")
                rate_var.set("")
                amt_var.set("0.00")
                days_var.set("") 
                    
        sl_var.trace_add("write", on_sl_change)
        calculate_date_delta_local()

        def on_item_select(selected_text):
            if selected_text in state.inventory_data: 
                r_val = float(state.inventory_data[selected_text]["rate"])
                if r_val.is_integer():
                    rate_var.set(str(int(r_val)))
                else:
                    rate_var.set(str(r_val))
                    
                sac_var.set(str(state.inventory_data[selected_text]["hsn"]))
                
                # --- THE FIX: Handle 'None' or '--Select--' units to auto-clear Qty and Days ---
                u_val = str(state.inventory_data[selected_text].get("unit", ""))
                
                if u_val.lower() in ["none", "--select--", ""]:
                    unit_var.set("")
                    qty_var.set("")
                    days_var.set("")
                else:
                    unit_var.set(u_val)
                    if not days_var.get().strip():
                        calculate_date_delta_local()
                # ---------------------------------------------------------------
            state.calculate_totals()

        def calc_line(*args):
            if getattr(state, "is_swapping", False): return
            
            rate_text = rate_var.get().strip()
            qty_text = qty_var.get().strip()
            days_text = days_var.get().strip()
            
            r = extract_number_from_string(rate_text, 0.0)
            q = extract_number_from_string(qty_text, 1.0)
            d = extract_number_from_string(days_text, 1.0)
            
            if not rate_text:
                amt_var.set("0.00")
            else:
                amt_var.set(f"{r * q * d:.2f}")
                
            state.calculate_totals()

        rate_var.trace_add("write", calc_line)
        qty_var.trace_add("write", calc_line)
        days_var.trace_add("write", calc_line)

        def wipe_entry(e):
            e.widget.delete(0, tk.END)
            reindex_rows()

        widgets_pool = []

        if has_gst:
            w_qty, w_unit, w_sac, w_rate, w_days = widths[2], widths[3], widths[4], widths[5], widths[6]
        else:
            w_qty, w_unit, w_sac, w_rate, w_days = widths[2], widths[3], 10, widths[4], widths[5]

        sl_ent = tk.Entry(items_frame, textvariable=sl_var, font=("Segoe UI", 10), width=widths[0], justify="center", bg=theme["bg"], fg=theme["text"], insertbackground=theme["text"], highlightbackground=theme["border"], highlightthickness=1)
        sl_ent.grid(row=row_idx, column=0, padx=2, pady=4, ipady=3, sticky="nsew")
        enable_copy_paste(sl_ent)
        sl_ent.bind("<KeyRelease>", lambda e: reindex_rows())
        sl_ent.bind("<FocusOut>", lambda e: reindex_rows())
        sl_ent.bind("<Delete>", wipe_entry)
        widgets_pool.append(sl_ent)
        
        i_frame = tk.Frame(items_frame, bg=theme["card"])
        i_frame.grid(row=row_idx, column=1, padx=2, pady=4, sticky="ew")
        
        i_ent = ExpandingRichText(i_frame, item_var, state, calc_line, char_width=widths[1])
        i_ent.pack(fill="x", expand=True, pady=2)
        widgets_pool.append(i_ent) 
        
        q_ent = tk.Entry(items_frame, textvariable=qty_var, font=("Segoe UI", 10), width=w_qty, justify="center", bg=theme["bg"], fg=theme["text"], insertbackground=theme["text"], highlightbackground=theme["border"], highlightthickness=1)
        q_ent.grid(row=row_idx, column=2, padx=2, pady=4, ipady=3, sticky="nsew")
        q_ent.bind("<Return>", state.focus_next)
        q_ent.bind("<Delete>", wipe_entry)
        enable_copy_paste(q_ent)
        widgets_pool.append(q_ent)

        u_ent = tk.Entry(items_frame, textvariable=unit_var, font=("Segoe UI", 10), width=w_unit, justify="center", bg=theme["bg"], fg=theme["text"], insertbackground=theme["text"], highlightbackground=theme["border"], highlightthickness=1)
        u_ent.grid(row=row_idx, column=3, padx=2, pady=4, ipady=3, sticky="nsew")
        u_ent.bind("<Return>", state.focus_next)
        u_ent.bind("<Delete>", wipe_entry)
        enable_copy_paste(u_ent)
        widgets_pool.append(u_ent)

        i_list = tk.Listbox(state.popup, font=("Segoe UI", 10), bg=theme["bg"], fg=theme["text"], selectbackground=theme["accent_blue"], highlightthickness=1, highlightbackground=theme["border"])

        def on_i_up(e):
            if not i_list.winfo_ismapped(): return "continue"
            sel = i_list.curselection()
            if not sel: i_list.selection_set(0)
            elif sel[0] > 0:
                i_list.selection_clear(0, tk.END); i_list.selection_set(sel[0]-1); i_list.see(sel[0]-1)
            return "break"

        def on_i_down(e):
            if not i_list.winfo_ismapped(): return "continue"
            sel = i_list.curselection()
            if not sel: i_list.selection_set(0)
            elif sel[0] < i_list.size()-1:
                i_list.selection_clear(0, tk.END); i_list.selection_set(sel[0]+1); i_list.see(sel[0]+1)
            return "break"

        i_ent.bind("<Up>", on_i_up); i_ent.bind("<Down>", on_i_down)

        def on_i_key(e):
            if e.keysym in ('Up', 'Down', 'Left', 'Right', 'Return', 'Tab', 'Escape'): return
            val = item_var.get().replace("@@B@@", "").replace("@@U@@", "")
            all_items = list(state.inventory_data.keys())
            
            # --- THE FIX: Smart Sort - "Starts With" gets priority, then alphabetized! ---
            if val:
                val_lower = val.lower()
                hits = [i for i in all_items if val_lower in i.lower()]
                hits.sort(key=lambda x: (not x.lower().startswith(val_lower), x.lower()))
            else:
                hits = sorted(all_items, key=lambda x: x.lower())
            # -----------------------------------------------------------------------------
            
            if hits:
                i_list.delete(0, tk.END)
                for h in hits: i_list.insert(tk.END, h)
                lh = min(len(hits), 5) * 20
                i_list.place(in_=i_ent, x=0, rely=1.0, relwidth=1.0, height=lh); i_list.lift()
            else: i_list.place_forget()

        def on_i_enter(e):
            if i_list.winfo_ismapped() and i_list.curselection():
                chosen = i_list.get(i_list.curselection())
                i_ent.set_text(chosen); i_list.place_forget(); on_item_select(chosen)
                return "break"
            else:
                state.focus_next(e); return "break"

        def hide_i_list(e): state.popup.after(200, i_list.place_forget)

        def on_list_click(e):
            if not i_list.curselection(): return
            chosen = i_list.get(i_list.curselection())
            i_ent.set_text(chosen)
            i_list.place_forget()
            on_item_select(item_var.get())
            reindex_rows()
            # --- THE FIX: Force focus back to the text box and put the cursor at the end ---
            i_ent.focus_set()
            i_ent.mark_set(tk.INSERT, "end")

        i_ent.bind("<KeyRelease>", on_i_key, add="+"); i_ent.bind("<Return>", on_i_enter, add="+"); i_ent.bind("<FocusOut>", hide_i_list, add="+")
        i_list.bind("<ButtonRelease-1>", on_list_click)

        s_ent = tk.Entry(items_frame, textvariable=sac_var, font=("Segoe UI", 10), width=w_sac, justify="center", bg=theme["bg"], fg=theme["text"], insertbackground=theme["text"], highlightbackground=theme["border"], highlightthickness=1)
        s_ent.bind("<Return>", state.focus_next); enable_copy_paste(s_ent)
        s_ent.bind("<Delete>", wipe_entry)
        widgets_pool.append(s_ent)

        r_ent = tk.Entry(items_frame, textvariable=rate_var, font=("Segoe UI", 10), width=w_rate, justify="right", bg=theme["bg"], fg=theme["text"], insertbackground=theme["text"], highlightbackground=theme["border"], highlightthickness=1)
        r_ent.bind("<Return>", state.focus_next); enable_copy_paste(r_ent)
        r_ent.bind("<Delete>", wipe_entry)
        widgets_pool.append(r_ent)

        d_ent = tk.Entry(items_frame, textvariable=days_var, font=("Segoe UI", 10), width=w_days, justify="center", bg=theme["bg"], fg=theme["text"], insertbackground=theme["text"], highlightbackground=theme["border"], highlightthickness=1)
        enable_copy_paste(d_ent)
        d_ent.bind("<Delete>", wipe_entry)
        widgets_pool.append(d_ent)

        lbl_amt = tk.Label(items_frame, textvariable=amt_var, font=("Segoe UI", 10, "bold"), bg=theme["card"], fg=theme["accent_blue"], anchor="e", width=14)
        widgets_pool.append(lbl_amt)

        def move_cursor_to_end(e):
            e.widget.after(10, lambda: e.widget.icursor(tk.END))
            
        q_ent.bind("<FocusIn>", move_cursor_to_end, add="+")
        u_ent.bind("<FocusIn>", move_cursor_to_end, add="+")
        s_ent.bind("<FocusIn>", move_cursor_to_end, add="+")
        r_ent.bind("<FocusIn>", move_cursor_to_end, add="+")
        d_ent.bind("<FocusIn>", move_cursor_to_end, add="+")

        current_row_payload = {
            "sl_var": sl_var, "item": item_var, "qty": qty_var, "unit": unit_var, 
            "sac": sac_var, "rate": rate_var, "days": days_var, 
            "amt": amt_var, "widgets": widgets_pool
        }

        action_f = tk.Frame(items_frame, bg=theme["card"])
        
        arrows_f = tk.Frame(action_f, bg=theme["card"])
        arrows_f.pack(side="left", fill="y", padx=(0, 2))
        
        def move_row(dir_val, current_payload=current_row_payload):
            idx = state.item_rows.index(current_payload)
            target = idx + dir_val
            if 0 <= target < len(state.item_rows):
                state.is_swapping = True
                r1 = state.item_rows[idx]
                r2 = state.item_rows[target]
                
                t1 = r1["widgets"][1].get("1.0", "end-1c")
                t2 = r2["widgets"][1].get("1.0", "end-1c")
                r1["widgets"][1].set_text(t2)
                r2["widgets"][1].set_text(t1)
                
                # --- THE FIX: Include 'sl_var' so the blank box travels, and auto-reindex! ---
                for key in ["sl_var", "qty", "unit", "sac", "rate", "days", "amt"]:
                    v1 = r1[key].get()
                    v2 = r2[key].get()
                    r1[key].set(v2)
                    r2[key].set(v1)
                    
                state.is_swapping = False
                reindex_rows()
                # ------------------------------------------------------------------------------

        tk.Button(arrows_f, text="▲", font=("Segoe UI", 7), bg=theme["card"], fg=theme["sec"], relief="flat", cursor="hand2", takefocus=0, command=lambda: move_row(-1)).pack(side="top", fill="x", expand=True)
        tk.Button(arrows_f, text="▼", font=("Segoe UI", 7), bg=theme["card"], fg=theme["sec"], relief="flat", cursor="hand2", takefocus=0, command=lambda: move_row(1)).pack(side="bottom", fill="x", expand=True)

        def delete_this_row():
            if len(state.item_rows) > 1:
                sl_ent.destroy(); i_frame.destroy(); q_ent.destroy(); u_ent.destroy()
                s_ent.destroy(); r_ent.destroy(); d_ent.destroy(); lbl_amt.destroy()
                action_f.destroy()
                state.item_rows.remove(current_row_payload)
            else:
                sl_var.set("1")
                item_var.set(""); i_ent.set_text(""); qty_var.set("")
                unit_var.set(""); sac_var.set(""); rate_var.set("") 
                amt_var.set("0.00"); days_var.set("")
            reindex_rows()

        tk.Button(action_f, text="❌", font=("Segoe UI", 9), bg=theme["card"], fg=theme.get("error", "#ef4444"), relief="flat", cursor="hand2", takefocus=0, command=delete_this_row).pack(side="right", fill="y")

        col_offset = 4
        if has_gst:
            s_ent.grid(row=row_idx, column=col_offset, padx=2, pady=4, ipady=3, sticky="nsew")
            col_offset += 1
            
        r_ent.grid(row=row_idx, column=col_offset, padx=2, pady=4, ipady=3, sticky="nsew")
        col_offset += 1
        d_ent.grid(row=row_idx, column=col_offset, padx=2, pady=4, ipady=3, sticky="nsew")
        col_offset += 1
        lbl_amt.grid(row=row_idx, column=col_offset, padx=2, pady=4, sticky="nsew")
        col_offset += 1
        action_f.grid(row=row_idx, column=col_offset, padx=2, pady=4, sticky="nsew")

        def handle_last_field_tab(event, current_row=current_row_payload):
            if state.item_rows[-1] == current_row:
                add_item_row()
                
                new_part_widget = state.item_rows[-1]["widgets"][1]
                new_part_widget.focus_set() 
                
                def force_scroll():
                    widget = items_frame
                    while widget:
                        if widget.winfo_class() == 'Canvas':
                            widget.update_idletasks()
                            widget.configure(scrollregion=widget.bbox("all"))
                            widget.yview_scroll(4, "units")
                            break
                        widget = widget.master
                        
                items_frame.after(10, force_scroll)
                return "break"
            else:
                idx = state.item_rows.index(current_row)
                next_row = state.item_rows[idx + 1]
                
                nr_item = next_row["widgets"][1].get("1.0", "end-1c").strip()
                nr_qty = next_row["qty"].get().strip()
                
                if not nr_item and not nr_qty:
                    next_row["widgets"][1].focus_set()
                    return "break"
                
                add_item_row()
                state.is_swapping = True
                
                for i in range(len(state.item_rows)-1, idx+1, -1):
                    r_curr = state.item_rows[i]
                    r_prev = state.item_rows[i-1]
                    
                    t_prev = r_prev["widgets"][1].get("1.0", "end-1c")
                    r_curr["widgets"][1].set_text(t_prev)
                    
                    for key in ["qty", "unit", "sac", "rate", "days", "amt"]:
                        r_curr[key].set(r_prev[key].get())
                        
                state.is_swapping = False
                
                new_row = state.item_rows[idx+1]
                new_row["widgets"][1].set_text("")
                new_row["qty"].set("")
                new_row["unit"].set("")
                new_row["sac"].set("")
                new_row["rate"].set("")
                new_row["days"].set("")
                new_row["amt"].set("0.00")
                
                reindex_rows()
                state.calculate_totals()
                
                new_row["widgets"][1].focus_set()
                return "break"

        d_ent.bind("<Tab>", handle_last_field_tab)
        d_ent.bind("<Return>", handle_last_field_tab)

        state.item_rows.append(current_row_payload)
        item_var.trace_add("write", lambda *a: reindex_rows())

    def calculate_date_delta(target_days_var=None):
        f_str = state.serv_bill_from_var.get().strip()
        t_str = state.serv_bill_to_var.get().strip()

        if f_str and not t_str:
            if target_days_var: target_days_var.set("1")
            else:
                for row in state.item_rows:
                    if row["sl_var"].get().strip() != "" and row["unit"].get().strip().lower() not in ["none", "--select--", ""]:
                        row["days"].set("1")
            return
            
        if not f_str or not t_str: return

        d1, d2 = None, None
        primary_fmt = getattr(state, "date_fmt_code", get_date_format_str())

        for fmt in (primary_fmt, "%Y-%m-%d", "%d.%m.%Y", "%d-%m-%Y", "%d/%m/%Y", "%m/%d/%Y"):
            if not d1:
                try: d1 = datetime.strptime(f_str, fmt).date()
                except: pass
            if not d2:
                try: d2 = datetime.strptime(t_str, fmt).date()
                except: pass

        if d1 and d2:
            if d2 < d1:
                state.serv_bill_to_var.set(f_str)
                return
            
            computed_days = (d2 - d1).days + 1
            if computed_days > 0:
                if target_days_var: target_days_var.set(str(computed_days))
                else:
                    for row in state.item_rows: 
                        if row["sl_var"].get().strip() != "":
                            if row["unit"].get().strip().lower() not in ["none", "--select--", ""]:
                                row["days"].set(str(computed_days))

    state.serv_bill_from_var.trace_add("write", lambda *a: calculate_date_delta())
    state.serv_bill_to_var.trace_add("write", lambda *a: calculate_date_delta())

    state.add_row_func = add_item_row

    add_item_row()