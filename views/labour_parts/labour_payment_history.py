import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import sys
import tempfile
import webbrowser
import csv
import re
from datetime import datetime

# --- Bulletproof Executable Pathing ---
if getattr(sys, 'frozen', False):
    ROOT_DIR = os.path.dirname(sys.executable)
else:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parts_dir = os.path.dirname(current_dir)
    ROOT_DIR = os.path.dirname(parts_dir)
if ROOT_DIR not in sys.path: sys.path.append(ROOT_DIR)

import database
from views.invoice_parts.helpers import format_currency, smart_date_formatter
from views.invoice_parts.calendar_widget import NativeCalendar

class LabourPaymentHistoryPopup(tk.Toplevel):
    def __init__(self, parent, labour_id, worker_name, curr_fmt, date_fmt_code, theme_colors):
        super().__init__(parent)
        
        self.labour_id = labour_id
        self.worker_name = worker_name
        self.curr_fmt = curr_fmt
        self.date_fmt_code = date_fmt_code
        self.t = theme_colors
        
        self.title(f"Payment History: {worker_name}")
        self.geometry("950x700")
        self.configure(bg=self.t["bg"])
        self.grab_set()

        self.update_idletasks()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        x, y = int((sw/2) - (950/2)), int((sh/2) - (700/2))
        self.geometry(f"+{max(0,x)}+{max(0,y)}")

        self.search_var = tk.StringVar()
        self.from_var = tk.StringVar()
        self.to_var = tk.StringVar()

        self.search_var.trace_add("write", lambda *a: self.load_data())
        self.from_var.trace_add("write", lambda *a: self.load_data())
        self.to_var.trace_add("write", lambda *a: self.load_data())

        self.build_ui()
        self.load_data()

        def clear_focus(event):
            # --- THE FIX: Stop if the window is already closed! ---
            if not self.winfo_exists(): return
            # ------------------------------------------------------
            if str(event.widget).startswith(str(self)):
                if hasattr(event.widget, 'winfo_class'):
                    w_class = event.widget.winfo_class()
                    if w_class not in ('Entry', 'TCombobox', 'Text', 'Treeview', 'Button'):
                        self.focus_set()
                        if hasattr(self, 'h_tree') and self.h_tree.selection():
                            self.h_tree.selection_remove(self.h_tree.selection())
        self.bind_all("<ButtonPress-1>", clear_focus, add="+")

    def build_ui(self):
        h_header_f = tk.Frame(self, bg=self.t["bg"])
        h_header_f.pack(fill="x", padx=20, pady=(15, 5))

        tk.Label(h_header_f, text=f"Payment History: {self.worker_name}", font=("Segoe UI", 14, "bold"), bg=self.t["bg"], fg=self.t["text"]).pack(side="left")
        
        btn_export = tk.Button(h_header_f, text="📥 Export ▼", font=("Segoe UI", 9, "bold"), bg=self.t["card"], fg=self.t["text"], relief="solid", highlightbackground=self.t["border"], bd=1, cursor="hand2", padx=8, pady=2)
        btn_export.pack(side="right")
        
        export_menu = tk.Menu(btn_export, tearoff=0, font=("Segoe UI", 10), bg=self.t["card"], fg=self.t["text"])
        export_menu.add_command(label="⭳ Export as CSV", command=self.export_csv)
        export_menu.add_command(label="🖨️ Export as PDF", command=self.export_pdf)
        btn_export.config(command=lambda: export_menu.tk_popup(btn_export.winfo_rootx(), btn_export.winfo_rooty() + btn_export.winfo_height()))

        filter_f = tk.Frame(self, bg=self.t["card"], highlightbackground=self.t["border"], highlightthickness=1)
        filter_f.pack(fill="x", padx=20, pady=(0, 15))
        
        inner_f = tk.Frame(filter_f, bg=self.t["card"], pady=10, padx=10)
        inner_f.pack(fill="x")

        tk.Label(inner_f, text="🔍 Search:", font=("Segoe UI", 9, "bold"), bg=self.t["card"], fg=self.t["text_sec"]).pack(side="left", padx=(5, 5))
        tk.Entry(inner_f, textvariable=self.search_var, font=("Segoe UI", 10), width=25, bg=self.t["bg"], fg=self.t["text"], insertbackground=self.t["text"], highlightbackground=self.t["border"], highlightthickness=1).pack(side="left", ipady=3)

        # --- THE FIX: Compact '✖' button right next to the search box ---
        btn_clear_search = tk.Button(inner_f, text="✖", font=("Arial", 10, "bold"), bg=self.t["card"], fg=self.t["error"], relief="flat", cursor="hand2", command=lambda: self.search_var.set(""))
        btn_clear_search.pack(side="left", padx=(5, 10))
        # ----------------------------------------------------------------

        # --- THE FIX: Added '✖' clear button and enabled yellow 'ref_date_var' highlighting! ---
        def clear_custom_dates():
            self.from_var.set("")
            self.to_var.set("")
            
        btn_clear_dates = tk.Button(inner_f, text="✖", font=("Arial", 10, "bold"), bg=self.t["card"], fg=self.t["error"], relief="flat", cursor="hand2", command=clear_custom_dates)
        btn_clear_dates.pack(side="right", padx=(5, 10))

        to_f = tk.Frame(inner_f, bg=self.t["bg"], highlightbackground=self.t["border"], highlightthickness=1)
        to_f.pack(side="right", padx=(5, 0))
        to_btn = tk.Button(to_f, text="▼", bg=self.t["card"], fg=self.t["text"], relief="flat", cursor="hand2")
        to_btn.pack(side="right", ipadx=4, ipady=3)
        tk.Entry(to_f, textvariable=self.to_var, font=("Segoe UI", 10), width=10, bg=self.t["bg"], fg=self.t["text"], bd=0, insertbackground=self.t["text"]).pack(side="left", ipady=4, padx=5)
        
        # Passed ref_date_var=self.from_var to trigger the yellow marker!
        to_btn.config(command=lambda b=to_btn: NativeCalendar(self, self.to_var, anchor_widget=b, ref_date_var=self.from_var))
        
        tk.Label(inner_f, text="To:", font=("Segoe UI", 9, "bold"), bg=self.t["card"], fg=self.t["text_sec"]).pack(side="right", padx=(10, 0))
        
        from_f = tk.Frame(inner_f, bg=self.t["bg"], highlightbackground=self.t["border"], highlightthickness=1)
        from_f.pack(side="right", padx=(5, 0))
        from_btn = tk.Button(from_f, text="▼", bg=self.t["card"], fg=self.t["text"], relief="flat", cursor="hand2")
        from_btn.pack(side="right", ipadx=4, ipady=3)
        tk.Entry(from_f, textvariable=self.from_var, font=("Segoe UI", 10), width=10, bg=self.t["bg"], fg=self.t["text"], bd=0, insertbackground=self.t["text"]).pack(side="left", ipady=4, padx=5)
        from_btn.config(command=lambda b=from_btn: NativeCalendar(self, self.from_var, anchor_widget=b))
        
        tk.Label(inner_f, text="📅 From:", font=("Segoe UI", 9, "bold"), bg=self.t["card"], fg=self.t["text_sec"]).pack(side="right", padx=(10, 0))
        # ----------------------------------------------------------------------------------------

        table_f = tk.Frame(self, bg=self.t["card"], highlightbackground=self.t["border"], highlightthickness=1)
        table_f.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        
        style = ttk.Style(self)
        style.theme_use("default") # --- THE FIX: Unlock Custom Thick Scrollbars ---
        
        # --- THE FIX: Thick Isolated Scrollbar Styles ---
        style.configure("LabourHist.Vertical.TScrollbar", background=self.t["text_sec"], troughcolor=self.t["bg"], bordercolor=self.t["bg"], arrowcolor=self.t["text"], relief="flat")
        style.configure("LabourHist.Horizontal.TScrollbar", background=self.t["text_sec"], troughcolor=self.t["bg"], bordercolor=self.t["bg"], arrowcolor=self.t["text"], relief="flat")
        style.map("LabourHist.Vertical.TScrollbar", background=[("active", self.t["accent_blue"])])
        style.map("LabourHist.Horizontal.TScrollbar", background=[("active", self.t["accent_blue"])])
        # ------------------------------------------------

        scroll_y = ttk.Scrollbar(table_f, orient="vertical", style="LabourHist.Vertical.TScrollbar")
        scroll_y.pack(side="right", fill="y")
        
        scroll_x = ttk.Scrollbar(table_f, orient="horizontal", style="LabourHist.Horizontal.TScrollbar")
        scroll_x.pack(side="bottom", fill="x")
        
        style.configure("Hist.Treeview.Heading", font=("Segoe UI", 10, "bold"), background=self.t["header"], foreground=self.t["text"], relief="raised", borderwidth=3)
        style.configure("Hist.Treeview", font=("Segoe UI", 10), rowheight=35, background=self.t["bg"], fieldbackground=self.t["bg"], foreground=self.t["text"], borderwidth=0)
        style.map("Hist.Treeview", background=[("selected", self.t["border"])], foreground=[("selected", self.t["text"])])

        self.h_tree = ttk.Treeview(table_f, columns=("date", "type", "mode", "notes", "amount", "action", "ghost"), show="headings", yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set, style="Hist.Treeview")
        self.h_tree.pack(side="left", fill="both", expand=True)
        scroll_y.config(command=self.h_tree.yview)
        scroll_x.config(command=self.h_tree.xview)

        self.h_tree.heading("date", text="DATE", anchor="center")
        self.h_tree.heading("type", text="TYPE", anchor="center")
        self.h_tree.heading("mode", text="MODE", anchor="center")
        
        # --- THE FIX: Renamed Header ---
        self.h_tree.heading("notes", text="NOTES", anchor="w")
        # -------------------------------
        
        self.h_tree.heading("amount", text="AMOUNT", anchor="e")
        self.h_tree.heading("action", text="PROOF", anchor="center")

        # --- THE FIX: Locked all real columns, Stretch the Ghost ---
        self.h_tree.column("date", width=110, anchor="center", stretch=False)
        self.h_tree.column("type", width=120, anchor="center", stretch=False)
        self.h_tree.column("mode", width=120, anchor="center", stretch=False)
        self.h_tree.column("notes", width=250, anchor="w", stretch=False)
        self.h_tree.column("amount", width=120, anchor="e", stretch=False)
        self.h_tree.column("action", width=120, anchor="center", stretch=False)
        
        self.h_tree.heading("ghost", text="")
        self.h_tree.column("ghost", width=10, minwidth=10, stretch=True)
        # -----------------------------------------------------------
        
        self.h_tree.tag_configure("evenrow", background=self.t["bg"])
        self.h_tree.tag_configure("oddrow", background=self.t["card"])

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

        # --- THE FIX: Header Drag Misfire Block ---
        def on_h_press(event):
            self._h_press_region = self.h_tree.identify("region", event.x, event.y)
        self.h_tree.bind("<ButtonPress-1>", on_h_press, add="+")
        
        def safe_h_click(event):
            if getattr(self, "_h_press_region", "") != "cell": return
            self.on_h_click(event)
            
        self.h_tree.bind("<ButtonRelease-1>", safe_h_click, add="+")
        # ------------------------------------------
        
        def on_h_motion(e):
            row_id = self.h_tree.identify_row(e.y)
            col_id = self.h_tree.identify_column(e.x)
            if row_id and col_id == "#6" and not str(row_id).startswith("empty"):
                self.h_tree.config(cursor="hand2")
            else:
                self.h_tree.config(cursor="")
        self.h_tree.bind("<Motion>", on_h_motion)

    def clear_filters(self):
        self.search_var.set("")
        self.from_var.set("")
        self.to_var.set("")
        self.lift()
        self.focus_force()

    def load_data(self):
        for i in self.h_tree.get_children(): self.h_tree.delete(i)
        
        # --- THE FIX: MVC Compliant Payment History Fetch ---
        rows = database.get_labour_payment_history(self.labour_id)
        # ----------------------------------------------------

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

        self.export_cache = []
        idx = 0
        for r in rows:
            l_id, l_date, l_type, l_amount, l_desc, mode, attach_path = r
            
            dt = datetime.min
            for fmt in (self.date_fmt_code, "%Y-%m-%d", "%d-%m-%Y", "%d.%m.%Y", "%Y/%m/%d"):
                try:
                    dt = datetime.strptime(l_date[:10], fmt)
                    break
                except: pass
            
            if dt != datetime.min:
                if from_dt and dt < from_dt: continue
                if to_dt and dt > to_dt: continue

            # Parse Description into Mode and Notes
            db_mode = mode if mode else "Cash"
            
            # Extract Mode if embedded in description (legacy support)
            mode_match = re.search(rf'{l_type} \((.*?)\)', l_desc)
            if mode_match:
                db_mode = mode_match.group(1)
                
            # --- THE FIX: Smart Regex Scrubber for Notes ---
            notes = re.sub(rf'^{l_type}\s*\(.*?\)\s*-\s*', '', str(l_desc)).strip()
            # -----------------------------------------------
            
            if l_type == "Advance" and l_amount > 0 and "(In)" not in db_mode:
                db_mode = f"{db_mode} (In)"
                
            mode = db_mode

            amt_str = format_currency(abs(l_amount), self.curr_fmt)
            
            if search:
                full_text = f"{l_type} {mode} {notes} {amt_str}".lower()
                if search not in full_text: continue

            try: fmt_date = smart_date_formatter(l_date, self.date_fmt_code)
            except: fmt_date = l_date
            
            action_txt = "👁 View Proof" if attach_path and os.path.exists(attach_path) else "📎 Add Proof"
            tag = "evenrow" if idx % 2 == 0 else "oddrow"
            self.h_tree.insert("", "end", iid=str(l_id), values=(fmt_date, l_type, mode, notes, amt_str, action_txt), tags=(tag, attach_path or "NONE"))
            self.export_cache.append([fmt_date, l_type, mode, notes, amt_str])
            idx += 1

        while idx < 16:
            tag = "evenrow" if idx % 2 == 0 else "oddrow"
            self.h_tree.insert("", "end", iid=f"empty_{idx}", values=("", "", "", "", "", ""), tags=(tag, "empty"))
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
                        
                        # --- THE FIX: Master Vault Pathing ---
                        from views.invoice_parts.helpers import get_vault_path
                        safe_dir = get_vault_path(ROOT_DIR, comp_id, self.worker_name, "Labours", self.labour_id)
                        proof_dir = os.path.join(safe_dir, "payment_proofs")
                        os.makedirs(proof_dir, exist_ok=True)
                        
                        ext = os.path.splitext(path)[1] or ".png"
                        final_attach = os.path.join(proof_dir, f"proof_{int(time.time()*1000)}{ext}")
                        
                        try: shutil.copy2(path, final_attach)
                        except: final_attach = path
                        # -------------------------------------
                        
                        # --- THE FIX: Use secure helper instead of raw SQL ---
                        database.update_labour_payment_proof(int(iid), final_attach)
                        # ---------------------------------------------------
                        
                        new_vals = list(vals)
                        new_vals[5] = "👁 View Proof"
                        self.h_tree.item(iid, values=new_vals, tags=(tags[0], final_attach))
                        messagebox.showinfo("Success", "Payment Proof attached and saved successfully!", parent=self)
                        self.lift()

    def export_csv(self):
        if not self.export_cache:
            messagebox.showinfo("Empty", "No data to export.", parent=self)
            return
        file_path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")], title="Export Payment History CSV")
        if not file_path: return
        try:
            with open(file_path, mode='w', newline='', encoding='utf-8-sig') as file:
                writer = csv.writer(file)
                writer.writerow(["Date", "Type", "Mode", "Notes", "Amount"]) 
                writer.writerows(self.export_cache)
            messagebox.showinfo("Success", f"History exported to:\n{file_path}", parent=self)
        except Exception as e: messagebox.showerror("Export Failed", str(e), parent=self)

    def export_pdf(self):
        if not self.export_cache:
            messagebox.showinfo("Empty", "No data to export.", parent=self)
            return
        html_content = f"""
        <html>
        <head>
            <meta charset="utf-8">
            <title>Payment History - {self.worker_name}</title>
            <style>
                @media print {{ @page {{ margin: 0; size: auto; }} body {{ margin: 1.5cm; }} }}
                body {{ font-family: Arial, sans-serif; margin: 40px; color: #0f172a; }}
                h2 {{ color: #1e293b; margin-bottom: 20px; }}
                table {{ width: 100%; border-collapse: collapse; border-top: 2px solid #cbd5e1; border-bottom: 2px solid #cbd5e1; }}
                th, td {{ padding: 10px; text-align: left; font-size: 14px; border-bottom: 1px solid #e2e8f0; }}
                th {{ background-color: #f8fafc; font-weight: bold; color: #475569; border-bottom: 2px solid #cbd5e1; }}
                tr:nth-child(even) {{ background-color: #ffffff; }}
                tr:nth-child(odd) {{ background-color: #f8fafc; }}
            </style>
        </head>
        <body>
            <h2>Payment History: {self.worker_name}</h2>
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
        for r in self.export_cache:
            html_content += f"""
                <tr>
                    <td>{r[0]}</td>
                    <td>{r[1]}</td>
                    <td>{r[2]}</td>
                    <td>{r[3]}</td>
                    <td style="text-align: right;">{r[4]}</td>
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