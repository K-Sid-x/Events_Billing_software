import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import sys
import tempfile
import webbrowser
from datetime import datetime

# --- THE FIX: Bulletproof Executable Pathing ---
if getattr(sys, 'frozen', False):
    ROOT_DIR = os.path.dirname(sys.executable)
else:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parts_dir = os.path.dirname(current_dir)
    ROOT_DIR = os.path.dirname(parts_dir)
if ROOT_DIR not in sys.path: sys.path.append(ROOT_DIR)
# -----------------------------------------------

import database
from views.invoice_parts.helpers import format_currency, smart_date_formatter
from views.invoice_parts.calendar_widget import NativeCalendar

class EmployeePaymentHistoryPopup(tk.Toplevel):
    def __init__(self, parent, emp_id, emp_name, curr_fmt, date_fmt_code):
        super().__init__(parent)
        self.transient(parent)  # Locks popup on top of the Ledger
        
        self.emp_id = emp_id
        self.emp_name = emp_name
        self.curr_fmt = curr_fmt
        self.date_fmt_code = date_fmt_code
        
        from views.home_parts.ui_components import get_theme
        t = get_theme()
        self.BG = t["bg"]
        self.CARD = t["card"]
        self.BORDER = t["border"]
        self.TEXT = t["text"]
        self.TEXT_SEC = t["sec"]
        self.BLUE = t["accent_blue"]
        self.RED = t["error"]

        self.title(f"Payment History: {emp_name}")
        self.geometry("950x700")
        self.configure(bg=self.BG)
        self.grab_set()

        # Center Window
        self.update_idletasks()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        x, y = int((sw/2) - (950/2)), int((sh/2) - (700/2))
        self.geometry(f"+{max(0,x)}+{max(0,y)}")

        self.search_var = tk.StringVar()
        self.from_var = tk.StringVar()
        self.to_var = tk.StringVar()

        # Live data filtering
        self.search_var.trace_add("write", lambda *a: self.load_data())
        self.from_var.trace_add("write", lambda *a: self.load_data())
        self.to_var.trace_add("write", lambda *a: self.load_data())

        self.build_ui()
        self.load_data()

        # Drop focus when clicking blank space
        def clear_focus(event):
            if str(event.widget).startswith(str(self)):
                if hasattr(event.widget, 'winfo_class'):
                    w_class = event.widget.winfo_class()
                    if w_class not in ('Entry', 'TCombobox', 'Text', 'Treeview', 'Button'):
                        self.focus_set()
                        if hasattr(self, 'h_tree') and self.h_tree.selection():
                            self.h_tree.selection_remove(self.h_tree.selection())
        self.bind_all("<ButtonPress-1>", clear_focus, add="+")

    def build_ui(self):
        h_header_f = tk.Frame(self, bg=self.BG)
        h_header_f.pack(fill="x", padx=20, pady=(15, 5))

        tk.Label(h_header_f, text=f"Payment History: {self.emp_name}", font=("Segoe UI", 14, "bold"), bg=self.BG, fg=self.TEXT).pack(side="left")
        tk.Button(h_header_f, text="🖨️ Print History", font=("Arial", 10, "bold"), bg=self.CARD, fg=self.TEXT, relief="solid", bd=1, highlightbackground=self.BORDER, cursor="hand2", padx=15, pady=5, command=self.print_hist).pack(side="right")

        # --- NEW DEDICATED TOOLBAR ---
        filter_f = tk.Frame(self, bg=self.CARD, highlightbackground=self.BORDER, highlightthickness=1)
        filter_f.pack(fill="x", padx=20, pady=(0, 15))
        
        inner_f = tk.Frame(filter_f, bg=self.CARD, pady=10, padx=10)
        inner_f.pack(fill="x")

        tk.Label(inner_f, text="🔍 Search:", font=("Arial", 9, "bold"), bg=self.CARD, fg=self.TEXT_SEC).pack(side="left", padx=(5, 5))
        tk.Entry(inner_f, textvariable=self.search_var, font=("Arial", 10), width=25, bg=self.BG, fg=self.TEXT, insertbackground=self.TEXT, highlightbackground=self.BORDER, highlightthickness=1).pack(side="left", ipady=3)

        # --- THE FIX: Dialed back the brightness for the History Popup ---
        btn_clear_search = tk.Button(inner_f, text="✖", font=("Arial", 9), bg=self.CARD, fg=self.RED, activebackground=self.CARD, activeforeground=self.RED, relief="solid", bd=1, pady=0, padx=0, cursor="hand2", command=lambda: self.search_var.set(""))
        btn_clear_search.pack(side="left", padx=(2, 10), ipady=1, ipadx=3)
        # -----------------------------------------------------------------

        btn_clear = tk.Button(inner_f, text="✖ Clear", font=("Arial", 9, "bold"), bg=self.CARD, fg=self.RED, relief="flat", cursor="hand2", command=self.clear_filters)
        btn_clear.pack(side="right", padx=(10, 5))

        to_f = tk.Frame(inner_f, bg=self.BG, highlightbackground=self.BORDER, highlightthickness=1)
        to_f.pack(side="right", padx=(5, 0))
        to_btn = tk.Button(to_f, text="▼", bg=self.CARD, fg=self.TEXT, relief="flat", cursor="hand2")
        to_btn.pack(side="right", ipadx=4, ipady=3)
        tk.Entry(to_f, textvariable=self.to_var, font=("Arial", 10), width=10, bg=self.BG, fg=self.TEXT, bd=0, insertbackground=self.TEXT).pack(side="left", ipady=4, padx=5)
        to_btn.config(command=lambda b=to_btn: NativeCalendar(self, self.to_var, anchor_widget=b))
        
        tk.Label(inner_f, text="To:", font=("Arial", 9, "bold"), bg=self.CARD, fg=self.TEXT_SEC).pack(side="right", padx=(10, 0))
        
        from_f = tk.Frame(inner_f, bg=self.BG, highlightbackground=self.BORDER, highlightthickness=1)
        from_f.pack(side="right", padx=(5, 0))
        from_btn = tk.Button(from_f, text="▼", bg=self.CARD, fg=self.TEXT, relief="flat", cursor="hand2")
        from_btn.pack(side="right", ipadx=4, ipady=3)
        tk.Entry(from_f, textvariable=self.from_var, font=("Arial", 10), width=10, bg=self.BG, fg=self.TEXT, bd=0, insertbackground=self.TEXT).pack(side="left", ipady=4, padx=5)
        from_btn.config(command=lambda b=from_btn: NativeCalendar(self, self.from_var, anchor_widget=b))
        
        tk.Label(inner_f, text="📅 From:", font=("Arial", 9, "bold"), bg=self.CARD, fg=self.TEXT_SEC).pack(side="right", padx=(10, 0))
        # -----------------------------

        table_f = tk.Frame(self, bg=self.CARD, highlightbackground=self.BORDER, highlightthickness=1)
        table_f.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        
        style = ttk.Style(self)
        style.theme_use("default")
        
        # --- THE FIX: Thick Scrollbar Styles ---
        style.configure("EmpHist.Vertical.TScrollbar", background=self.TEXT_SEC, troughcolor=self.BG, bordercolor=self.BG, arrowcolor=self.TEXT, relief="flat")
        style.configure("EmpHist.Horizontal.TScrollbar", background=self.TEXT_SEC, troughcolor=self.BG, bordercolor=self.BG, arrowcolor=self.TEXT, relief="flat")
        style.map("EmpHist.Vertical.TScrollbar", background=[("active", self.BLUE)])
        style.map("EmpHist.Horizontal.TScrollbar", background=[("active", self.BLUE)])
        # ---------------------------------------

        # --- THE FIX: Apply isolated scrollbar styles & horizontal scrolling ---
        scroll_y = ttk.Scrollbar(table_f, orient="vertical", style="EmpHist.Vertical.TScrollbar")
        scroll_y.pack(side="right", fill="y")
        scroll_x = ttk.Scrollbar(table_f, orient="horizontal", style="EmpHist.Horizontal.TScrollbar")
        scroll_x.pack(side="bottom", fill="x")
        
        self.h_tree = ttk.Treeview(table_f, columns=("date", "type", "mode", "notes", "amount", "action", "ghost"), show="headings", yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set, style="Ledger.Treeview", height=13)
        self.h_tree.pack(side="left", fill="both", expand=True)
        scroll_y.config(command=self.h_tree.yview)
        scroll_x.config(command=self.h_tree.xview)
        # -----------------------------------------------------------------------

        self.h_tree.heading("date", text="DATE", anchor="center")
        self.h_tree.heading("type", text="TYPE", anchor="center")
        self.h_tree.heading("mode", text="MODE", anchor="center")
        self.h_tree.heading("notes", text="NOTES", anchor="w")
        self.h_tree.heading("amount", text="AMOUNT", anchor="e")
        self.h_tree.heading("action", text="PROOF", anchor="center")
        self.h_tree.heading("ghost", text="")

        # --- THE FIX: Real-time width saving & Ghost column logic ---
        try:
            import json
            comp_id = getattr(self.winfo_toplevel(), "active_company_id", 1)
            conn = database.get_connection()
            c = conn.cursor()
            c.execute("SELECT setting_value FROM ui_settings WHERE setting_key=?", (f"emp_hist_cols_{comp_id}",))
            res = c.fetchone()
            conn.close()
            w_dict = json.loads(res[0]) if res and res[0] else {}
        except:
            w_dict = {}

        self.h_tree.column("date", width=w_dict.get("date", 110), minwidth=60, anchor="center", stretch=False)
        self.h_tree.column("type", width=w_dict.get("type", 120), minwidth=60, anchor="center", stretch=False)
        self.h_tree.column("mode", width=w_dict.get("mode", 130), minwidth=60, anchor="center", stretch=False)
        self.h_tree.column("notes", width=w_dict.get("notes", 250), minwidth=100, anchor="w", stretch=False)
        self.h_tree.column("amount", width=w_dict.get("amount", 120), minwidth=80, anchor="e", stretch=False)
        self.h_tree.column("action", width=w_dict.get("action", 120), minwidth=80, anchor="center", stretch=False)
        self.h_tree.column("ghost", width=10, minwidth=10, stretch=True)

        def save_hist_widths():
            new_w = {c: self.h_tree.column(c, "width") for c in ("date", "type", "mode", "notes", "amount", "action")}
            try:
                comp_id = getattr(self.winfo_toplevel(), "active_company_id", 1)
                # --- THE FIX: Use safe helper to attach ACTIVE_COMPANY_ID and prevent ghost data! ---
                database.save_ui_setting(f"emp_hist_cols_{comp_id}", json.dumps(new_w))
                # ------------------------------------------------------------------------------------
            except: pass

        def on_hist_sep_drag(event):
            if self.h_tree.identify_region(event.x, event.y) == "separator":
                self.after(50, save_hist_widths)
                
        self.h_tree.bind("<B1-Motion>", on_hist_sep_drag, add="+")
        self.h_tree.bind("<ButtonRelease-1>", lambda e: self.after(50, save_hist_widths) if self.h_tree.identify_region(e.x, e.y) == "separator" else None, add="+")
        # ------------------------------------------------------------
        
        self.h_tree.tag_configure("evenrow", background=self.BG, foreground=self.TEXT)
        self.h_tree.tag_configure("oddrow", background=self.CARD, foreground=self.TEXT)

        # --- THE FIX: Buttery Smooth X/Y Scrolling ---
        def _h_fast_scroll(event, direction):
            delta = -1 * (event.delta / 120) if os.name == 'nt' else -1 * event.delta
            if direction == "y":
                self.h_tree.yview_moveto(self.h_tree.yview()[0] + (delta * 0.008))
            else:
                self.h_tree.xview_moveto(self.h_tree.xview()[0] + (delta * 0.02))

        self.h_tree.bind("<MouseWheel>", lambda e: _h_fast_scroll(e, "y"))
        self.h_tree.bind("<Shift-MouseWheel>", lambda e: _h_fast_scroll(e, "x"))
        # ---------------------------------------------

        self.h_tree.bind("<ButtonRelease-1>", self.on_h_click)
        
        def on_h_motion(e):
            row_id = self.h_tree.identify_row(e.y)
            col_id = self.h_tree.identify_column(e.x)
            if row_id and col_id == "#6" and not str(row_id).startswith("empty"):
                self.h_tree.config(cursor="hand2")
            else:
                self.h_tree.config(cursor="")
        self.h_tree.bind("<Motion>", on_h_motion)

    def clear_filters(self):
        # Search var reset removed so it doesn't interfere with the new search X button
        self.from_var.set("")
        self.to_var.set("")
        self.lift()
        self.focus_force()

    def load_data(self):
        for i in self.h_tree.get_children(): self.h_tree.delete(i)
        
        # --- THE FIX: MVC Compliant History Fetch ---
        rows = database.get_employee_payment_history_filtered(self.emp_id)
        # --------------------------------------------

        search = self.search_var.get().lower()
        from_dt, to_dt = None, None
        
        if self.from_var.get():
            for fmt in (self.date_fmt_code, "%Y-%m-%d", "%d-%m-%Y", "%d.%m.%Y", "%Y/%m/%d"):
                try: 
                    from_dt = datetime.strptime(self.from_var.get().strip(), fmt)
                    break
                except: pass
        if self.to_var.get():
            for fmt in (self.date_fmt_code, "%Y-%m-%d", "%d-%m-%Y", "%d.%m.%Y", "%Y/%m/%d"):
                try: 
                    # Force the 'To' date to the very end of the day to capture all records
                    to_dt = datetime.strptime(self.to_var.get().strip(), fmt).replace(hour=23, minute=59, second=59)
                    break
                except: pass

        idx = 0
        for r in rows:
            p_id, p_date, p_type, mode, amount, notes, attach_path = r
            
            # --- THE FIX: Scrub the backend Target tags from the UI display! ---
            if notes:
                notes = str(notes).replace('[Target: Dues]', '').replace('[Target: Current]', '').replace('[Target: All]', '').strip()
            # -------------------------------------------------------------------
            
            dt = datetime.min
            for fmt in (self.date_fmt_code, "%Y-%m-%d", "%d-%m-%Y", "%d.%m.%Y", "%Y/%m/%d"):
                try:
                    dt = datetime.strptime(p_date, fmt)
                    break
                except: pass
            
            if dt != datetime.min:
                if from_dt and dt < from_dt: continue
                if to_dt and dt > to_dt: continue

            amt_str = format_currency(amount, self.curr_fmt)
            
            if search:
                full_text = f"{p_type} {mode} {notes} {amt_str}".lower()
                if search not in full_text: continue

            try: fmt_date = smart_date_formatter(p_date, self.date_fmt_code)
            except: fmt_date = p_date
            
            action_txt = "👁 View Proof" if attach_path and os.path.exists(attach_path) else "📎 Add Proof"
            tag = "evenrow" if idx % 2 == 0 else "oddrow"
            self.h_tree.insert("", "end", iid=str(p_id), values=(fmt_date, p_type, mode, notes, amt_str, action_txt, ""), tags=(tag, attach_path or "NONE"))
            idx += 1

        while idx < 13:
            tag = "evenrow" if idx % 2 == 0 else "oddrow"
            self.h_tree.insert("", "end", iid=f"empty_{idx}", values=("", "", "", "", "", "", ""), tags=(tag, "empty"))
            idx += 1

    def on_h_click(self, event):
        region = self.h_tree.identify("region", event.x, event.y)
        if region == "cell" and self.h_tree.identify_column(event.x) == "#6":
            iid = self.h_tree.identify_row(event.y)
            if iid and not str(iid).startswith("empty"):
                vals = self.h_tree.item(iid, "values")
                tags = self.h_tree.item(iid, "tags")
                
                if vals[5] == "👁 View Proof":
                    if len(tags) > 1 and tags[1] != "NONE" and os.path.exists(tags[1]):
                        try: os.startfile(tags[1])
                        except: webbrowser.open(tags[1])
                        
                elif vals[5] == "📎 Add Proof":
                    path = filedialog.askopenfilename(parent=self, title="Select Payment Proof", filetypes=[("Image Files", "*.png *.jpg *.jpeg"), ("PDF Files", "*.pdf")])
                    if path:
                        import shutil, time
                        comp_id = getattr(self.winfo_toplevel(), "active_company_id", 1)
                        
                        # --- THE FIX: Master Vault Pathing for History Proofs ---
                        from views.invoice_parts.helpers import get_vault_path
                        safe_dir = get_vault_path(ROOT_DIR, comp_id, self.emp_name, "Employees", self.emp_id)
                        proof_dir = os.path.join(safe_dir, "payment_proofs")
                        os.makedirs(proof_dir, exist_ok=True)
                        
                        ext = os.path.splitext(path)[1] or ".png"
                        final_attach = os.path.join(proof_dir, f"proof_{int(time.time()*1000)}{ext}")
                        
                        try: shutil.copy2(path, final_attach)
                        except: final_attach = path
                        # --------------------------------------------------------
                        
                        # --- THE FIX: Use secure wrapper instead of raw SQL ---
                        database.update_employee_payment_proof(int(iid), final_attach)
                        database.log_audit("Employees", "Added Payment Proof", record_ref=self.emp_name, details="Uploaded a document/proof for an existing payment record.", company_id=comp_id)
                        # ------------------------------------------------------
                        
                        new_vals = list(vals)
                        new_vals[5] = "👁 View Proof"
                        self.h_tree.item(iid, values=new_vals, tags=(tags[0], final_attach))
                        messagebox.showinfo("Success", "Payment Proof attached and saved successfully!", parent=self)
                        self.lift()

    def print_hist(self):
        html_content = f"""
        <html>
        <head>
            <meta charset="utf-8">
            <title>Payment History - {self.emp_name}</title>
            <style>
                @media print {{ @page {{ margin: 0; size: auto; }} body {{ margin: 1.5cm; }} }}
                body {{ font-family: Arial, sans-serif; margin: 40px; color: #0f172a; }}
                h2 {{ color: #1e293b; margin-bottom: 20px; }}
                table {{ width: 100%; border-collapse: collapse; border-top: 2px solid #cbd5e1; border-bottom: 2px solid #cbd5e1; }}
                th, td {{ padding: 10px; text-align: left; font-size: 14px; border-bottom: 1px solid #e2e8f0; }}
                th {{ background-color: #f8fafc; font-weight: bold; color: #475569; border-bottom: 2px solid #cbd5e1; }}
                .evenrow td {{ background-color: #ffffff; }}
                .oddrow td {{ background-color: #f8fafc; }}
            </style>
        </head>
        <body>
            <h2>Payment History: {self.emp_name}</h2>
            <table>
                <thead>
                    <tr>
                        <th>Date</th>
                        <th>Type</th>
                        <th>Mode</th>
                        <th>Notes</th>
                        <th style="text-align: right;">Amount</th>
                    </tr>
                </thead>
                <tbody>
        """
        for item in self.h_tree.get_children():
            vals = self.h_tree.item(item, "values")
            tags = self.h_tree.item(item, "tags")
            if "empty" in tags: continue
            row_class = "evenrow" if "evenrow" in tags else "oddrow"
            html_content += f"""
                <tr class="{row_class}">
                    <td>{vals[0]}</td>
                    <td>{vals[1]}</td>
                    <td>{vals[2]}</td>
                    <td>{vals[3]}</td>
                    <td style="text-align: right;">{vals[4]}</td>
                </tr>
            """
        html_content += """
                </tbody>
            </table>
            <script> window.onload = function() { window.print(); } </script>
        </body>
        </html>
        """
        fd, path = tempfile.mkstemp(suffix=".html", prefix="Payment_Hist_")
        with os.fdopen(fd, 'w', encoding='utf-8') as f: f.write(html_content)
        webbrowser.open('file://' + os.path.realpath(path))