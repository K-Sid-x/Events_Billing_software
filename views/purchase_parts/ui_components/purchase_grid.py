import tkinter as tk
from tkinter import ttk
import os
import sys

# --- THE FIX: Bulletproof Executable Pathing ---
if getattr(sys, 'frozen', False):
    parent_dir = os.path.dirname(sys.executable)
    current_dir = os.path.join(parent_dir, "views")
else:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)

if parent_dir not in sys.path: sys.path.append(parent_dir)
# -----------------------------------------------

import database
from views.invoice_parts.helpers import format_currency

class ExpandingRichText(tk.Text):
    def __init__(self, master, textvariable, form_ctx, char_width, **kwargs):
        kwargs.setdefault("height", 1)
        kwargs.setdefault("bg", form_ctx.BG_COLOR)
        kwargs.setdefault("fg", form_ctx.TEXT_PRIMARY)
        kwargs.setdefault("insertbackground", form_ctx.TEXT_PRIMARY)
        kwargs.setdefault("highlightbackground", form_ctx.BORDER_COLOR)
        kwargs.setdefault("highlightthickness", 1)
        kwargs.setdefault("relief", "flat")
        kwargs.setdefault("wrap", "char")
        kwargs.setdefault("font", ("Segoe UI", 11))
        kwargs.setdefault("width", char_width)
        kwargs.setdefault("padx", 6)
        kwargs.setdefault("pady", 6)
        kwargs.setdefault("undo", True)
        kwargs.setdefault("maxundo", 50)
        
        super().__init__(master, **kwargs)
        from views.invoice_parts.helpers import enable_copy_paste
        enable_copy_paste(self)
        
        self.textvariable = textvariable
        self.form = form_ctx
        
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
        self.bind("<<Paste>>", self.custom_paste)
        self.bind("<Control-v>", self.custom_paste)
        
        self.textvariable.trace_add("write", self.on_var_changed)
        self._is_syncing = False

    def on_var_changed(self, *args):
        if self._is_syncing: return
        self.set_text(self.textvariable.get())

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
            clipboard_text = self.clipboard_get().rstrip('\n')
            self.edit_separator()
            try:
                if self.tag_ranges("sel"): self.delete("sel.first", "sel.last")
            except: pass
            self.insert(tk.INSERT, clipboard_text)
            self.edit_separator()
            self.sync_data()
            self.after(10, self.adjust_height)
            return "break"
        except: pass

    def custom_focus_next(self, event):
        nxt = self.tk_focusNext()
        if nxt: nxt.focus()
        return "break" 

    def custom_focus_prev(self, event):
        prv = self.tk_focusPrev()
        if prv: prv.focus()
        return "break"

    def queue_height_check(self, event=None):
        if event and hasattr(event, "keysym") and event.keysym in ('Up', 'Down', 'Left', 'Right', 'Return', 'Alt_L', 'Alt_R', 'Escape', 'Control_L', 'Control_R', 'Shift_L', 'Shift_R'): 
            return
        self.sync_data()
        self.after(10, self.adjust_height)

    def execute_newline(self, event):
        self.insert(tk.INSERT, "\n")
        self.sync_data()
        self.after(10, self.adjust_height)
        return "break"

    def adjust_height(self):
        self.update_idletasks()
        total_lines = 1
        if self.winfo_ismapped():
            try:
                lc = self.count("1.0", "end-1c", "displaylines")
                if lc: total_lines = (lc[0] if isinstance(lc, tuple) else lc) + 1
            except: pass
        if self.get("1.0", "end-1c").endswith("\n"): total_lines += 1
        self.config(height=max(1, total_lines))
        self.yview_moveto(0.0)
        self.see(tk.INSERT)

    def set_text(self, text_content):
        self._is_syncing = True
        self.delete("1.0", tk.END)
        if not text_content:
            self.adjust_height()
            self._is_syncing = False
            return

        import re
        parts = re.split(r'(\[B\]|\[/B\]|\[U\]|\[/U\])', text_content)
        is_b = False; is_u = False
        for part in parts:
            if part == "[B]": is_b = True
            elif part == "[/B]": is_b = False
            elif part == "[U]": is_u = True
            elif part == "[/U]": is_u = False
            elif part:
                s_idx = self.index(tk.INSERT)
                self.insert(tk.END, part)
                e_idx = self.index(tk.INSERT)
                if is_b and is_u: self.tag_add("bold_underline", s_idx, e_idx)
                elif is_b: self.tag_add("bold", s_idx, e_idx)
                elif is_u: self.tag_add("underline", s_idx, e_idx)
        self.adjust_height()
        self._is_syncing = False

    def sync_data(self):
        self._is_syncing = True
        raw_text = self.get("1.0", "end-1c")
        all_tags = self.tag_names()
        
        if "bold" not in all_tags and "underline" not in all_tags and "bold_underline" not in all_tags:
            if self.textvariable.get() != raw_text:
                self.textvariable.set(raw_text)
            self._is_syncing = False
            return
            
        res = ""; is_b = False; is_u = False
        for i in range(len(raw_text)):
            tags = self.tag_names(f"1.0+{i}c")
            c_b = "bold" in tags or "bold_underline" in tags
            c_u = "underline" in tags or "bold_underline" in tags
            if not is_b and c_b: res += "[B]"; is_b = True
            if is_b and not c_b: res += "[/B]"; is_b = False
            if not is_u and c_u: res += "[U]"; is_u = True
            if is_u and not c_u: res += "[/U]"; is_u = False
            res += raw_text[i]
        if is_b: res += "[/B]"
        if is_u: res += "[/U]"
        
        if self.textvariable.get() != res:
            self.textvariable.set(res)
        self._is_syncing = False

    def toggle_style(self, style_tag):
        try:
            start, end = self.index("sel.first"), self.index("sel.last")
            c_tags = self.tag_names(start)
            is_b = "bold" in c_tags or "bold_underline" in c_tags
            is_u = "underline" in c_tags or "bold_underline" in c_tags
            self.tag_remove("bold", start, end); self.tag_remove("underline", start, end); self.tag_remove("bold_underline", start, end)
            if style_tag == "bold": is_b = not is_b 
            elif style_tag == "underline": is_u = not is_u 
            if is_b and is_u: self.tag_add("bold_underline", start, end)
            elif is_b: self.tag_add("bold", start, end)
            elif is_u: self.tag_add("underline", start, end)
            self.sync_data()
        except: pass

    def trigger_formatting_menu(self, event):
        try:
            if not self.tag_ranges("sel"): return
        except: return
        menu = tk.Menu(self, tearoff=0, bg=self.form.CARD_BG, fg=self.form.TEXT_PRIMARY, activebackground=self.form.ACCENT_BLUE, activeforeground="#ffffff")
        menu.add_command(label="B  Bold", font=("Segoe UI", 11, "bold"), command=lambda: self.toggle_style("bold"))
        menu.add_command(label="U  Underline", font=("Segoe UI", 11, "underline"), command=lambda: self.toggle_style("underline"))
        menu.add_separator()
        menu.add_command(label="⎚ Clear Style", command=self.wipe_styles)
        menu.post(event.x_root, event.y_root)

    def wipe_styles(self):
        try:
            start, end = self.index("sel.first"), self.index("sel.last")
            self.tag_remove("bold", start, end); self.tag_remove("underline", start, end); self.tag_remove("bold_underline", start, end)
            self.sync_data()
        except: pass

class PurchaseGridEngine:
    def __init__(self, form_ctx, parent_frame):
        self.form = form_ctx
        self.parent = parent_frame
        self.rows_data = []
        self.vendor_state_code = ""

        # --- THE FIX: Cache company state code ONCE during init ---
        self.comp_state_code = ""
        try:
            comp_c = database.get_company(self.form.comp_id)
            if len(comp_c) > 18 and comp_c[18]:
                self.comp_state_code = str(comp_c[18]).strip()
            if not self.comp_state_code and len(comp_c) > 9 and comp_c[9]:
                comp_gstin = str(comp_c[9]).strip()
                if len(comp_gstin) >= 2:
                    self.comp_state_code = comp_gstin[:2]
        except: pass
        # ----------------------------------------------------------

        self.historical_items = {}
        self.load_historical_items()
        
        self.item_lb = tk.Listbox(self.form.pop, font=("Segoe UI", 11), bg=self.form.CARD_BG, fg=self.form.TEXT_PRIMARY, selectbackground=self.form.LIST_SEL, selectforeground=self.form.TEXT_PRIMARY, highlightthickness=1, highlightbackground=self.form.BORDER_COLOR, cursor="hand2")
        self.active_row_vars = None
        self.item_lb.bind("<<ListboxSelect>>", self.global_lb_select)
        
        self.grid_header_f = tk.Frame(self.parent, bg=self.form.CARD_BG)
        self.grid_header_f.pack(fill="x", padx=5, pady=(5, 0))
        
        btn_manage = tk.Button(self.grid_header_f, text="📋 Manage Items", font=("Segoe UI", 9, "bold"), bg=self.form.ACCENT_BLUE, fg="#ffffff", cursor="hand2", relief="flat", padx=10, pady=2, command=self.open_item_manager)
        btn_manage.pack(side="right")
        
        self.grid_container = tk.Frame(self.parent, bg=self.form.CARD_BG)
        self.grid_container.pack(fill="x", expand=True, padx=5, pady=(5, 5))
        self.grid_container.columnconfigure(1, weight=1)

        self.build_headers()
        self.add_row()

    def open_item_manager(self):
        mgr = tk.Toplevel(self.form.pop)
        mgr.title("Manage Purchase Items")
        mgr.configure(bg=self.form.BG_COLOR)
        mgr.transient(self.form.pop)
        mgr.grab_set()
        
        window_width = 550
        x = self.form.pop.winfo_rootx() + (self.form.pop.winfo_width() // 2) - (window_width // 2)
        y = self.form.pop.winfo_rooty() + 100
        mgr.geometry(f"{window_width}x450+{x}+{y}")

        header_f = tk.Frame(mgr, bg=self.form.BG_COLOR)
        header_f.pack(fill="x", padx=15, pady=10)
        
        tk.Label(header_f, text="Manage Saved Items", font=("Segoe UI", 12, "bold"), bg=self.form.BG_COLOR, fg=self.form.TEXT_PRIMARY).pack(side="left")
        lbl_count = tk.Label(header_f, text="Total Suggestions: 0", font=("Segoe UI", 10, "bold"), bg=self.form.BG_COLOR, fg=self.form.ACCENT_BLUE)
        lbl_count.pack(side="right")
        
        tk.Label(mgr, text="(Double-Click or Right-Click an item to edit/delete)", font=("Segoe UI", 9, "italic"), bg=self.form.BG_COLOR, fg=self.form.TEXT_SECONDARY).pack(pady=(0, 5))
        
        list_frame = tk.Frame(mgr, bg=self.form.BG_COLOR)
        list_frame.pack(fill="both", expand=True, padx=15, pady=5)
        
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side="right", fill="y")
        
        # --- THE FIX: Apply Theme Styles to the Treeview so it matches Dark/Light mode! ---
        style = ttk.Style(mgr)
        style.configure("ItemMgr.Treeview", font=("Segoe UI", 11), rowheight=28, background=self.form.CARD_BG, fieldbackground=self.form.CARD_BG, foreground=self.form.TEXT_PRIMARY, borderwidth=0)
        style.configure("ItemMgr.Treeview.Heading", font=("Segoe UI", 10, "bold"), background=self.form.BG_COLOR, foreground=self.form.TEXT_PRIMARY)
        style.map("ItemMgr.Treeview", background=[("selected", self.form.ACCENT_BLUE)], foreground=[("selected", "#ffffff")])
        
        tree = ttk.Treeview(list_frame, columns=("check", "sno", "item"), displaycolumns=("sno", "item"), show="headings", yscrollcommand=scrollbar.set, style="ItemMgr.Treeview")
        # ----------------------------------------------------------------------------------
        tree.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=tree.yview)
        
        tree.heading("check", text="[ ]")
        tree.heading("sno", text="SI No.")
        tree.heading("item", text="Item Name", anchor="w")
        
        tree.column("check", width=40, anchor="center", stretch=False)
        tree.column("sno", width=60, anchor="center", stretch=False)
        tree.column("item", width=400, anchor="w", stretch=True)
        
        tree.tag_configure("even", background=self.form.BG_COLOR, foreground=self.form.TEXT_PRIMARY)
        tree.tag_configure("odd", background=self.form.CARD_BG, foreground=self.form.TEXT_PRIMARY)
        
        is_bulk_mode = [False]
        selected_items = set()
        sorted_keys = []
        
        def refresh_list():
            for i in tree.get_children(): tree.delete(i)
            nonlocal sorted_keys
            sorted_keys = sorted(self.historical_items.keys(), key=str.lower)
            lbl_count.config(text=f"Total Suggestions: {len(sorted_keys)}")
            
            for idx, item_name in enumerate(sorted_keys):
                tag = "even" if idx % 2 == 0 else "odd"
                chk = "[✓]" if item_name in selected_items else "[ ]"
                tree.insert("", "end", iid=item_name, values=(chk, idx + 1, item_name), tags=(tag,))
                
            # --- THE FIX: Zebra Stripe all the way down using empty dummy rows! ---
            for i in range(len(sorted_keys), 12):
                tag = "even" if i % 2 == 0 else "odd"
                tree.insert("", "end", iid=f"dummy_{i}", values=("", "", ""), tags=(tag,))
            # ----------------------------------------------------------------------
                
        refresh_list()

        btn_f = tk.Frame(mgr, bg=self.form.BG_COLOR)
        btn_f.pack(fill="x", padx=15, pady=10)
        
        # Build buttons but DO NOT pack Bulk buttons yet
        btn_bulk_del = tk.Button(btn_f, text="🗑 Delete Selected (0)", bg=self.form.ERROR_COLOR, fg="#ffffff", font=("Segoe UI", 10, "bold"), relief="flat", cursor="hand2")
        btn_cancel_bulk = tk.Button(btn_f, text="✖ Cancel Bulk", bg=self.form.BORDER_COLOR, fg=self.form.TEXT_PRIMARY, font=("Segoe UI", 10, "bold"), relief="flat", cursor="hand2")
        btn_close = tk.Button(btn_f, text="Close", bg=self.form.BORDER_COLOR, fg=self.form.TEXT_PRIMARY, font=("Segoe UI", 10, "bold"), relief="flat", cursor="hand2", command=mgr.destroy)
        btn_close.pack(side="right")

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
            
            # --- THE FIX: Deselect dummy rows and empty space immediately! ---
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
        
        # --- THE FIX: Click anywhere else in the window to drop the selection ---
        mgr.bind("<Button-1>", lambda e: tree.selection_remove(tree.selection()) if e.widget not in (tree, scrollbar) else None)
        # ----------------------------------------------------------------------

        def start_inline_edit(old_name=None):
            if not old_name:
                sel = tree.selection()
                if not sel: return
                old_name = sel[0]
                
            # --- THE FIX: Block editing dummy rows! ---
            if str(old_name).startswith("dummy_"): return
                
            bbox = tree.bbox(old_name, "item") 
            if not bbox: return
            x_pos, y_pos, w_width, h_height = bbox
            
            edit_ent = tk.Text(tree, font=("Segoe UI", 11), bg=self.form.BG_COLOR, fg=self.form.TEXT_PRIMARY, insertbackground=self.form.TEXT_PRIMARY, highlightthickness=1, highlightcolor=self.form.ACCENT_BLUE, wrap="word")
            edit_ent.place(x=x_pos, y=y_pos, width=w_width, height=max(h_height * 2, 40))
            
            edit_ent.insert("1.0", old_name)
            edit_ent.focus_set()
            edit_ent.tag_add("sel", "1.0", "end")
            
            def save_edit(e=None):
                new_name = edit_ent.get("1.0", "end-1c").strip()
                if new_name and new_name != old_name:
                    try:
                        import sqlite3
                        conn = database.get_connection()
                        c = conn.cursor()
                        c.execute("UPDATE purchase_items SET item_name=? WHERE item_name=? AND purchase_id IN (SELECT id FROM purchases WHERE company_id=?)", (new_name, old_name, self.form.comp_id))
                        conn.commit()
                        conn.close()
                        
                        item_data = self.historical_items.pop(old_name)
                        self.historical_items[new_name] = item_data
                        if old_name in selected_items:
                            selected_items.remove(old_name)
                            selected_items.add(new_name)
                        refresh_list()
                    except Exception as err:
                        import tkinter.messagebox as messagebox
                        messagebox.showerror("Error", str(err), parent=mgr)
                        
                if edit_ent.winfo_exists(): edit_ent.destroy()
                return "break"
                
            def cancel_edit(e=None):
                if edit_ent.winfo_exists(): edit_ent.destroy()

            edit_ent.bind("<Return>", save_edit)
            edit_ent.bind("<Escape>", cancel_edit)
            edit_ent.bind("<FocusOut>", cancel_edit)

        tree.bind("<Double-Button-1>", lambda e: start_inline_edit() if tree.identify("region", e.x, e.y) == "cell" else None)

        def delete_single_item(target_name):
            import tkinter.messagebox as messagebox
            if messagebox.askyesno("Confirm Delete", f"Are you sure you want to permanently remove '{target_name}'?", parent=mgr):
                try:
                    conn = database.get_connection()
                    c = conn.cursor()
                    c.execute("UPDATE purchase_items SET item_name='' WHERE item_name=? AND purchase_id IN (SELECT id FROM purchases WHERE company_id=?)", (target_name, self.form.comp_id))
                    conn.commit()
                    conn.close()
                    self.historical_items.pop(target_name, None)
                    refresh_list()
                except Exception as err:
                    messagebox.showerror("Error", str(err), parent=mgr)

        ctx_menu = tk.Menu(mgr, tearoff=0, font=("Segoe UI", 10), bg=self.form.CARD_BG, fg=self.form.TEXT_PRIMARY, activebackground=self.form.ACCENT_BLUE, activeforeground="#ffffff")
        
        def show_ctx_menu(e):
            iid = tree.identify_row(e.y)
            ctx_menu.delete(0, "end")
            
            # --- THE FIX: Ignore dummy rows on Right-Click! ---
            if iid and not str(iid).startswith("dummy_"):
                tree.selection_set(iid)
                ctx_menu.add_command(label="✏️ Edit Name", command=lambda: start_inline_edit(iid))
                ctx_menu.add_command(label="❌ Delete Item", foreground=self.form.ERROR_COLOR, command=lambda: delete_single_item(iid))
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
                try:
                    conn = database.get_connection()
                    c = conn.cursor()
                    for target_name in selected_items:
                        c.execute("UPDATE purchase_items SET item_name='' WHERE item_name=? AND purchase_id IN (SELECT id FROM purchases WHERE company_id=?)", (target_name, self.form.comp_id))
                        self.historical_items.pop(target_name, None)
                    conn.commit()
                    conn.close()
                    toggle_bulk_mode() 
                except Exception as err:
                    messagebox.showerror("Error", str(err), parent=mgr)

        btn_bulk_del.config(command=execute_bulk_delete)

    def load_historical_items(self):
        try:
            conn = database.get_connection()
            c = conn.cursor()
            c.execute("""
                SELECT pi.item_name, pi.hsn, pi.gst_rate
                FROM purchase_items pi
                JOIN purchases p ON pi.purchase_id = p.id
                WHERE p.company_id = ? AND pi.item_name IS NOT NULL AND pi.item_name != ''
                ORDER BY pi.id ASC
            """, (self.form.comp_id,))
            for row in c.fetchall():
                i_name, i_hsn, i_gst = row
                
                # --- THE FIX: Scrubber to completely flatten text for the suggestion list! ---
                import re
                raw_name = str(i_name).strip()
                # 1. Remove all bold/underline tags
                clean_name = re.sub(r'\[/?(B|U)\]', '', raw_name)
                clean_name = clean_name.replace("@@B@@", "").replace("@@U@@", "")
                # 2. Replace all newlines with a single space so it fits beautifully on one line
                clean_name = re.sub(r'\s*\n\s*', ' ', clean_name).strip()
                
                if clean_name:
                    self.historical_items[clean_name] = {
                        "hsn": str(i_hsn).strip() if i_hsn else "",
                        "gst": str(int(i_gst)) if i_gst and float(i_gst).is_integer() else str(i_gst) if i_gst else "0"
                    }
                # ----------------------------------------------------------------------
            conn.close()
        except: pass

    def global_lb_select(self, e=None):
        if self.item_lb.winfo_ismapped() and self.item_lb.curselection():
            sel_item = self.item_lb.get(self.item_lb.curselection())
            if self.active_row_vars:
                iv, hv, gv, eqty, ehsn = self.active_row_vars
                iv.set(sel_item)
                
                data = self.historical_items.get(sel_item, {})
                if getattr(self.form, 'has_gst', True):
                    if data.get('hsn'): hv.set(data['hsn'])
                    if data.get('gst'): gv.set(data['gst'])
                
                self.item_lb.place_forget()
                
                # --- THE FIX: Eliminate the Focus Race Condition! ---
                if getattr(self.form, 'has_gst', True) and ehsn:
                    ehsn.focus_set()
                else:
                    eqty.focus_set()
                # ----------------------------------------------------
                
                self.update_totals()
            return "break"

    def build_headers(self):
        # --- THE FIX: Dynamically construct headers based on GST Status! ---
        if getattr(self.form, 'has_gst', True):
            headers = [
                ("SI No.", 6), ("Particulars / Item Name", 35), ("HSN/SAC", 10), 
                ("GST %", 6), ("Qnty", 8), ("Units", 6), 
                ("Rate(Inc.Tax)", 12), ("Base Rate", 12), ("Amount", 12), ("", 4)
            ]
        else:
            headers = [
                ("SI No.", 6), ("Particulars / Item Name", 40), 
                ("Qnty", 10), ("Units", 8), 
                ("Rate", 16), ("Amount", 16), ("", 4)
            ]
        
        for i, (text, width) in enumerate(headers):
            lbl = tk.Label(self.grid_container, text=text, font=("Segoe UI", 9, "bold"), bg=self.form.HEADER_BG, fg=self.form.TEXT_PRIMARY, width=width, anchor="w" if i==1 else "center", highlightthickness=1, highlightbackground=self.form.BORDER_COLOR)
            lbl.grid(row=0, column=i, padx=2, pady=(0, 10), sticky="ew", ipady=4)

    def format_num_string(self, num_val):
        try:
            s_val = f"{float(num_val):.2f}"
            parts = s_val.split(".")
            int_part = parts[0]
            if "Indian" in getattr(self.form, "curr_fmt", "Indian"):
                if len(int_part) > 3:
                    import re
                    int_part = re.sub(r"(\d)(?=(\d{2})+(?!\d))", r"\1,", int_part[:-3]) + "," + int_part[-3:]
            else:
                int_part = f"{int(int_part):,}"
            return f"{int_part}.{parts[1]}"
        except: return "0.00"

    def add_row(self, focus_new=False):
        row_idx = len(self.rows_data) + 1 
        has_gst = getattr(self.form, 'has_gst', True)
        
        sl_lbl = tk.Label(self.grid_container, text=str(row_idx), font=("Segoe UI", 10), bg=self.form.CARD_BG, fg=self.form.TEXT_PRIMARY, width=6)
        sl_lbl.grid(row=row_idx, column=0, padx=2, pady=3, sticky="nsew")

        def make_entry(w, var, justify="left"):
            return tk.Entry(self.grid_container, textvariable=var, font=("Segoe UI", 11), bg=self.form.BG_COLOR, fg=self.form.TEXT_PRIMARY, insertbackground=self.form.TEXT_PRIMARY, width=w, highlightthickness=1, highlightbackground=self.form.BORDER_COLOR, justify=justify)

        # We create all vars uniformly so the database save engine doesn't break
        item_var = tk.StringVar(); hsn_var = tk.StringVar(); gst_var = tk.StringVar(value="0")
        qty_var = tk.StringVar(value=""); unit_var = tk.StringVar(value="Nos")
        rate_inc_var = tk.StringVar(value="0.00"); rate_var = tk.StringVar(value="0.00")
        amt_var = tk.StringVar(value=format_currency(0.00, self.form.curr_fmt))
        in_stock_var = tk.BooleanVar(value=True) 

        # --- THE FIX: Cleanly route column indexes to pack seamlessly! ---
        i_frame = tk.Frame(self.grid_container, bg=self.form.CARD_BG)
        i_frame.grid(row=row_idx, column=1, padx=2, pady=3, sticky="ew")
        
        ent_item = ExpandingRichText(i_frame, item_var, self.form, char_width=35 if has_gst else 40)
        ent_item.pack(fill="x", expand=True, pady=2)
        
        c_idx = 2
        ent_hsn, cb_gst, ent_rate_inc = None, None, None
        
        if has_gst:
            ent_hsn = make_entry(10, hsn_var, "center")
            ent_hsn.grid(row=row_idx, column=c_idx, padx=2, pady=3, ipady=2, sticky="nsew"); c_idx += 1
            cb_gst = ttk.Combobox(self.grid_container, textvariable=gst_var, values=["0", "5", "12", "18", "28"], width=6, font=("Segoe UI", 11), justify="center")
            cb_gst.grid(row=row_idx, column=c_idx, padx=2, pady=3, ipady=2, sticky="nsew"); c_idx += 1

        ent_qty = make_entry(8 if has_gst else 10, qty_var, "center")
        ent_qty.grid(row=row_idx, column=c_idx, padx=2, pady=3, ipady=2, sticky="nsew"); c_idx += 1
        
        # --- THE FIX: Added Pkt, Trip, Rmt, Rft, Sq.ft., and Sq.mtr to the unit array ---
        cb_unit = ttk.Combobox(self.grid_container, textvariable=unit_var, values=["Nos", "Kg", "Pkt", "Ltr", "Pcs", "Mtr", "Box", "Roll", "Set", "Trip", "Rmt", "Rft", "Sq.ft.", "Sq.mtr"], width=8 if has_gst else 10, font=("Segoe UI", 11), justify="center")
        cb_unit.grid(row=row_idx, column=c_idx, padx=2, pady=3, ipady=2, sticky="nsew"); c_idx += 1
        # ---------------------------------------------------------------------------

        if has_gst:
            ent_rate_inc = make_entry(12, rate_inc_var, "right")
            ent_rate_inc.grid(row=row_idx, column=c_idx, padx=2, pady=3, ipady=2, sticky="nsew"); c_idx += 1
            
        ent_rate = make_entry(12 if has_gst else 16, rate_var, "right")
        ent_rate.grid(row=row_idx, column=c_idx, padx=2, pady=3, ipady=2, sticky="nsew"); c_idx += 1
        
        ent_amt = tk.Entry(self.grid_container, textvariable=amt_var, justify="right", font=("Segoe UI", 11, "bold"), bg=self.form.CARD_BG, fg=self.form.TEXT_PRIMARY, width=12 if has_gst else 16, state="readonly", readonlybackground=self.form.CARD_BG, highlightthickness=0, bd=0)
        ent_amt.grid(row=row_idx, column=c_idx, padx=2, pady=3, ipady=2, sticky="nsew"); c_idx += 1
        
        def on_item_type(e):
            if e.keysym in ('Up', 'Down', 'Left', 'Right', 'Return', 'Escape', 'Tab'): return
            
            # --- THE FIX: Read directly from the raw Text box to bypass the sync delay! ---
            val = ent_item.get("1.0", "end-1c").strip().lower()
            # ------------------------------------------------------------------------------
            
            self.item_lb.delete(0, tk.END)
            if not val:
                self.item_lb.place_forget()
                return

            # Smart Sort: Starts With first, then alphabetical
            matches = [k for k in self.historical_items.keys() if val in k.lower()]
            matches.sort(key=lambda x: (not x.lower().startswith(val), x.lower()))
            
            if matches:
                for m in matches: self.item_lb.insert(tk.END, m)
                x = ent_item.winfo_rootx() - self.form.pop.winfo_rootx()
                y = ent_item.winfo_rooty() - self.form.pop.winfo_rooty() + ent_item.winfo_height()
                self.item_lb.place(x=x, y=y, width=ent_item.winfo_width(), height=min(150, len(matches)*25))
                self.item_lb.lift()
                self.active_row_vars = (item_var, hsn_var, gst_var, ent_qty, ent_hsn)
            else:
                self.item_lb.place_forget()

        def hide_item_lb(*args):
            self.form.pop.after(150, lambda: self.item_lb.place_forget())

        def move_up(e):
            if self.item_lb.winfo_ismapped():
                sel = self.item_lb.curselection()
                if not sel: self.item_lb.selection_set(0)
                elif sel[0] > 0:
                    self.item_lb.selection_clear(sel[0])
                    self.item_lb.selection_set(sel[0]-1)
                    self.item_lb.see(sel[0]-1)
                return "break"

        def move_down(e):
            if self.item_lb.winfo_ismapped():
                sel = self.item_lb.curselection()
                if not sel: self.item_lb.selection_set(0)
                elif sel[0] < self.item_lb.size()-1:
                    self.item_lb.selection_clear(sel[0])
                    self.item_lb.selection_set(sel[0]+1)
                    self.item_lb.see(sel[0]+1)
                return "break"

        def item_return(e):
            if self.item_lb.winfo_ismapped() and self.item_lb.curselection():
                return self.global_lb_select(e)
            else:
                self.item_lb.place_forget()
                if has_gst: ent_hsn.focus_set()
                else: ent_qty.focus_set() # Skip directly to Quantity!
                return "break"

        ent_item.bind("<KeyRelease>", on_item_type, add="+")
        ent_item.bind("<FocusOut>", hide_item_lb, add="+")
        ent_item.bind("<Up>", move_up, add="+")
        ent_item.bind("<Down>", move_down, add="+")
        ent_item.bind("<Return>", item_return, add="+")

        if has_gst:
            ent_hsn.bind("<Return>", lambda e: [cb_gst.focus_set(), "break"])
            cb_gst.bind("<Return>", lambda e: [ent_qty.focus_set(), "break"])
            cb_unit.bind("<Return>", lambda e: [ent_rate_inc.focus_set(), "break"])
            ent_rate_inc.bind("<Return>", lambda e: [ent_rate.focus_set(), "break"])
        else:
            cb_unit.bind("<Return>", lambda e: [ent_rate.focus_set(), "break"]) # Skip directly to Rate!
            
        ent_qty.bind("<Return>", lambda e: [cb_unit.focus_set(), "break"])
        ent_rate.bind("<Return>", lambda e: [self.add_row(focus_new=True), "break"])

        def forward_scroll(e):
            self.form.master_canvas.yview_scroll(int(-1*(e.delta/120)), "units")
            return "break"
            
        if has_gst: cb_gst.bind("<MouseWheel>", forward_scroll)
        cb_unit.bind("<MouseWheel>", forward_scroll)

        widgets_list = [sl_lbl, i_frame, ent_item]
        if has_gst: widgets_list.extend([ent_hsn, cb_gst])
        widgets_list.extend([ent_qty, cb_unit])
        if has_gst: widgets_list.append(ent_rate_inc)
        widgets_list.extend([ent_rate, ent_amt])

        btn_del = tk.Button(self.grid_container, text="❌", font=("Segoe UI", 10), fg=self.form.ERROR_COLOR, bg=self.form.CARD_BG, relief="flat", cursor="hand2", width=4, command=lambda: self.delete_row(widgets_list))
        btn_del.grid(row=row_idx, column=c_idx, padx=2, pady=3, sticky="nsew")
        widgets_list.append(btn_del)

        # --- THE FIX: Force the cursor to the end of the number when focusing! ---
        def move_cursor_to_end_purch(e):
            e.widget.after(10, lambda: e.widget.icursor(tk.END))
            
        ent_qty.bind("<FocusIn>", move_cursor_to_end_purch, add="+")
        ent_rate.bind("<FocusIn>", move_cursor_to_end_purch, add="+")
        if has_gst:
            ent_hsn.bind("<FocusIn>", move_cursor_to_end_purch, add="+")
            ent_rate_inc.bind("<FocusIn>", move_cursor_to_end_purch, add="+")
        # -------------------------------------------------------------------------

        row_dict = {
            "widgets": widgets_list, "sl_lbl": sl_lbl, "item": item_var, "hsn": hsn_var, "gst": gst_var,
            "qty": qty_var, "unit": unit_var, "rate_inc": rate_inc_var, "rate": rate_var,
            "amt": amt_var, "in_stock": in_stock_var, "raw_amt": 0.0
        }
        self.rows_data.append(row_dict)

        def on_focus_in(e, var, default="0.00"):
            if var.get() == default: var.set("")
            
        def on_focus_out(e, var, default="0.00"):
            if var.get().strip() == "": var.set(default)

        if has_gst:
            cb_gst.bind("<FocusIn>", lambda e: on_focus_in(e, gst_var, "0"))
            cb_gst.bind("<FocusOut>", lambda e: on_focus_out(e, gst_var, "0"))
            ent_rate_inc.bind("<FocusIn>", lambda e: on_focus_in(e, rate_inc_var))
            ent_rate_inc.bind("<FocusOut>", lambda e: on_focus_out(e, rate_inc_var))

        ent_rate.bind("<FocusIn>", lambda e: on_focus_in(e, rate_var))
        ent_rate.bind("<FocusOut>", lambda e: on_focus_out(e, rate_var))

        def live_format(var, ent):
            val = var.get().replace(",", "")
            if not val or val == "." or val == "-": return
            parts = val.split(".")
            int_part = parts[0]
            try:
                if len(int_part) > 1 and int_part.startswith("0"):
                    int_part = str(int(int_part))
                if "Indian" in getattr(self.form, "curr_fmt", "Indian"):
                    if len(int_part) > 3:
                        import re
                        int_part = re.sub(r"(\d)(?=(\d{2})+(?!\d))", r"\1,", int_part[:-3]) + "," + int_part[-3:]
                else:
                    int_part = f"{int(int_part):,}"
                
                final = int_part
                if len(parts) > 1: final += "." + parts[1]
                if var.get() != final:
                    var.set(final)
                    ent.icursor("end")
            except: pass

        def calc_from_inc(*args):
            try:
                r_inc = float(rate_inc_var.get().replace(",", "") or 0); g = float(gst_var.get() or 0)
                r_base = r_inc / (1 + (g / 100))
                rate_var.set(self.format_num_string(r_base))
                self.update_row_amount(row_dict)
            except: pass

        def calc_from_base(*args):
            try:
                r_base = float(rate_var.get().replace(",", "") or 0); g = float(gst_var.get() or 0)
                r_inc = r_base * (1 + (g / 100))
                rate_inc_var.set(self.format_num_string(r_inc))
                self.update_row_amount(row_dict)
            except: pass

        ent_qty.bind("<FocusOut>", lambda e: self.update_row_amount(row_dict))
        ent_qty.bind("<KeyRelease>", lambda e: self.update_row_amount(row_dict))

        if has_gst:
            ent_hsn.bind("<KeyRelease>", lambda e: self.update_totals())
            ent_rate_inc.bind("<KeyRelease>", lambda e: [live_format(rate_inc_var, ent_rate_inc), calc_from_inc()])
            cb_gst.bind("<<ComboboxSelected>>", calc_from_base)
            cb_gst.bind("<KeyRelease>", calc_from_base)
            ent_rate.bind("<KeyRelease>", lambda e: [live_format(rate_var, ent_rate), calc_from_base()])
        else:
            # If no GST, base rate simply updates row amounts without reverse math!
            ent_rate.bind("<KeyRelease>", lambda e: [live_format(rate_var, ent_rate), self.update_row_amount(row_dict)])
            
        self.update_totals()
        
        if focus_new:
            def _jump_and_scroll():
                self.form.master_canvas.update_idletasks() 
                self.form.master_canvas.yview_moveto(1.0)  
                ent_item.focus_set()                       
            self.parent.after(20, _jump_and_scroll)

    def calculate_row(self, r):
        self.update_row_amount(r)

    def update_row_amount(self, r):
        try:
            raw_q = r["qty"].get().replace(",", "").strip()
            q = float(raw_q) if raw_q else 1.0
            
            base = float(r["rate"].get().replace(",", "") or 0)
            amt = q * base
            
            r["amt"].set(format_currency(amt, self.form.curr_fmt))
            r["raw_amt"] = amt 
            
            self.update_totals()
        except: pass

    def delete_row(self, widgets_list):
        if len(self.rows_data) <= 1:
            # --- THE FIX: Wipe out the single row instead of ignoring the click ---
            r = self.rows_data[0]
            r["item"].set("")
            if len(r["widgets"]) > 2 and hasattr(r["widgets"][2], 'set_text'):
                r["widgets"][2].set_text("")
            r["qty"].set("")
            r["unit"].set("Nos")
            r["rate"].set("")
            r["amt"].set(format_currency(0.00, self.form.curr_fmt))
            r["raw_amt"] = 0.0
            
            if getattr(self.form, 'has_gst', True):
                r["hsn"].set("")
                r["gst"].set("0")
                r["rate_inc"].set("")
            
            self.update_totals()
            return
            # ----------------------------------------------------------------------
            
        for i, r in enumerate(self.rows_data):
            if r["widgets"] == widgets_list:
                for w in widgets_list: w.destroy()
                self.rows_data.pop(i)
                break
        self.reindex_rows()
        self.update_totals()

    def reindex_rows(self):
        for i, r in enumerate(self.rows_data): r["sl_lbl"].config(text=str(i + 1))

    def check_interstate(self):
        self.update_totals()

    def update_totals(self):
        sub = 0.0; c_tax = 0.0; s_tax = 0.0; i_tax = 0.0
        is_interstate = False 
        
        # --- THE FIX: Use the cached state code instead of querying the DB on every keystroke! ---
        try:
            v_code = str(self.vendor_state_code).strip()
            if v_code and v_code != "N/A" and self.comp_state_code and self.comp_state_code != "N/A":
                if v_code != self.comp_state_code:
                    is_interstate = True
        except: pass
        # ---------------------------------------------------------------------------------------

        hsn_summary = {}

        for r in self.rows_data:
            try:
                amt = r.get("raw_amt", 0.0) 
                g_pct = float(r["gst"].get() or 0)
                hsn = r["hsn"].get().strip()
                sub += amt
                tax = amt * (g_pct / 100)
                
                if is_interstate: i_tax += tax
                else: c_tax += tax / 2; s_tax += tax / 2
                
                if amt > 0:
                    key = (hsn, g_pct)
                    hsn_summary[key] = hsn_summary.get(key, 0.0) + amt
            except: pass

        tot = sub + c_tax + s_tax + i_tax
        
        self.form.subtotal_var.set(f"{sub:.2f}")
        self.form.subtotal_disp.set(format_currency(sub, self.form.curr_fmt))
        
        self.form.cgst_var.set(f"{c_tax:.2f}")
        self.form.cgst_disp.set(format_currency(c_tax, self.form.curr_fmt))
        
        self.form.sgst_var.set(f"{s_tax:.2f}")
        self.form.sgst_disp.set(format_currency(s_tax, self.form.curr_fmt))
        
        self.form.igst_var.set(f"{i_tax:.2f}")
        self.form.igst_disp.set(format_currency(i_tax, self.form.curr_fmt))
        
        self.form.total_var.set(f"{round(tot):.2f}")
        self.form.total_disp.set(format_currency(round(tot), self.form.curr_fmt))
        
        if getattr(self.form, 'hsn_table', None):
            self.form.hsn_table.update_table(hsn_summary, is_interstate)
            
        if hasattr(self.form, 'row_cgst'):
            if is_interstate:
                self.form.row_cgst.pack_forget()
                self.form.row_sgst.pack_forget()
                self.form.row_igst.pack(fill="x", pady=3, before=self.form.grand_line)
            else:
                self.form.row_igst.pack_forget()
                self.form.row_cgst.pack(fill="x", pady=3, before=self.form.grand_line)
                self.form.row_sgst.pack(fill="x", pady=3, before=self.form.grand_line)