import tkinter as tk
from tkinter import ttk, messagebox
import sys
import os
import json
import shutil
import glob
import time
import traceback
from datetime import datetime
import database

from views.sidebar import Sidebar
from views.dashboard import DashboardView
from views.customers import CustomersView
from views.home import HomeView
from views.settings import SettingsView
from views.inventory import InventoryView
from views.stock import StockView
from views.invoices import InvoicesView
from views.expenses import ExpensesView  
from views.employees import EmployeesView  
from views.balance_sheet import BalanceSheetView  
from views.gst_report import GSTReportView
from views.profit_loss import ProfitLossView 
from views.purchases import PurchasesView
from views.labours import LaboursView 

class ScrollableFrame(tk.Frame):
    def __init__(self, container, bg_color, show_scrollbars=False, *args, **kwargs):
        super().__init__(container, bg=bg_color, highlightthickness=0, bd=0, *args, **kwargs)
        self.canvas = tk.Canvas(self, bg=bg_color, highlightthickness=0, bd=0, relief="flat")
        self.v_scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.h_scrollbar = ttk.Scrollbar(self, orient="horizontal", command=self.canvas.xview)
        self.inner_frame = tk.Frame(self.canvas, bg=bg_color, highlightthickness=0, bd=0)
        self.canvas_window = self.canvas.create_window((0, 0), window=self.inner_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.v_scrollbar.set, xscrollcommand=self.h_scrollbar.set)
        
        if show_scrollbars:
            self.v_scrollbar.pack(side="right", fill="y")
            self.h_scrollbar.pack(side="bottom", fill="x")
            
        self.canvas.pack(side="left", fill="both", expand=True)

        self.inner_frame.bind("<Configure>", self._on_frame_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)

    def _on_frame_configure(self, event=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        
    def _on_canvas_configure(self, event):
        canvas_width = event.width
        canvas_height = event.height
        req_width = self.inner_frame.winfo_reqwidth()
        req_height = self.inner_frame.winfo_reqheight()
        self.canvas.itemconfig(self.canvas_window, width=max(canvas_width, req_width), height=max(canvas_height, req_height))


class LedgerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("LEDGER.EVENTS - Billing App")
        self.geometry("1300x800") 
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        try:
            self.state('zoomed') 
        except tk.TclError:
            self.attributes('-zoomed', True)

        self.active_company_id = None 

        self.container = tk.Frame(self, highlightthickness=0, bd=0)
        self.container.pack(fill="both", expand=True)

        # --- THE FIX: Removed outer wrapper. Sidebar is now autonomous. ---
        self.sidebar = Sidebar(self.container, self.switch_view)
        self.page_separator = tk.Frame(self.container, width=1, bg="#334155")
        
        # NOTE: Sidebar and Separator are intentionally NOT packed here so they remain hidden on boot!
        # ------------------------------------------------------------------

        self.content_area = tk.Frame(self.container, highlightthickness=0, bd=0)
        self.content_area.pack(side="left", fill="both", expand=True)

        self.bind_all("<MouseWheel>", self._on_mousewheel)
        self.bind_all("<Control-l>", self.lock_screen)
        self.bind_all("<Control-L>", self.lock_screen)

        self.apply_global_theme()
        
        # --- THE FIX: Plug in the Radio Signal Listener ---
        self.bind("<<CompanyChanged>>", self._handle_company_change)
        # --------------------------------------------------
        
        # Delay the heavy garbage collection by 2 seconds so the UI loads instantly!
        self.after(2000, self.cleanup_temp_files)
        
        # --- THE FIX: Master Universal Focus Dropper ---
        self.bind_all("<Button-1>", self._on_global_click, add="+")
        # -----------------------------------------------
        
        # --- BOOT SEQUENCE ---
        self.after(50, self.boot_app)
        # ---------------------

    def boot_app(self):
        """Bypasses licensing for the Open Source version and boots straight to Login"""
        import database
        if database.has_users():
            self.show_login_screen()
        else:
            self.show_admin_setup_screen()

    # --- NEW: The Security Gatekeepers ---
    def show_admin_setup_screen(self):
        self.container.pack_forget()
        colors = self.get_global_theme_colors()
        
        self.auth_frame = tk.Frame(self, bg=colors["bg"])
        self.auth_frame.pack(fill="both", expand=True)
        
        import auth_window
        def on_success(username, role):
            # Save the logged-in user globally to the app instance!
            self.current_user = username
            self.current_role = role
            self.auth_frame.destroy()
            self.container.pack(fill="both", expand=True)
            self.switch_view("Home")
            
        auth_window.build_admin_setup_screen(self.auth_frame, colors, on_success)

    def show_login_screen(self):
        self.container.pack_forget()
        colors = self.get_global_theme_colors()
        
        self.auth_frame = tk.Frame(self, bg=colors["bg"])
        self.auth_frame.pack(fill="both", expand=True)
        
        import auth_window
        def on_success(username, role):
            # Save the logged-in user globally to the app instance!
            self.current_user = username
            self.current_role = role
            self.auth_frame.destroy()
            self.container.pack(fill="both", expand=True)
            self.switch_view("Home")
            
        auth_window.build_login_screen(self.auth_frame, colors, on_success)
    # -------------------------------------

    def _on_global_click(self, event):
        try:
            # --- THE FIX: Stop the main window from burying popups! ---
            if event.widget.winfo_toplevel() != self:
                return
                
            w_class = event.widget.winfo_class()
            if w_class not in ('Entry', 'TCombobox', 'Text', 'Button', 'Treeview', 'Scrollbar', 'TScrollbar', 'Spinbox', 'Radiobutton', 'Checkbutton'):
                self.focus_set()
        except: pass

    def _handle_company_change(self, event=None):
        """Listens for the company switch broadcast and updates navigation states."""
        if hasattr(self, "sidebar") and self.sidebar:
            if hasattr(self.sidebar, "sync_visibility"):
                self.sidebar.sync_visibility()

    def cleanup_temp_files(self):
        import tempfile
        temp_dir = tempfile.gettempdir()
        # --- THE FIX: Added 'proof_*' to wipe orphaned payment attachments! ---
        prefixes = [
            "Parties_Ledger_*", "Ledger_Stmt_*", "Invoice_Report_*", "Purchase_Report_*", 
            "Purchase_Payment_Hist_*", "Purch_Print_Studio_*", "Sales_Payment_Hist_*", 
            "Inventory_Report_*", "Stock_Report_*", "Purchase_Orders_*", "Stock_Ledger_Report_*", 
            "Labour_ID_Card_*", "Bulk_Labour_ID_Cards_*", "Labour_Report_*", "Labour_Ledger_Print_*", 
            "Print_Studio_Voucher_*", "GST_Report_*", "Emp_ID_Card_*", "Bulk_Emp_ID_Cards_*", 
            "Emp_Ledger_*", "Emp_Payroll_*", "Expense_Report_*", "PL_Statement_*", 
            "Balance_Sheet_*", "Payment_Hist_*", "Labour_Payment_Export_*", "proof_*"
        ]
        # ----------------------------------------------------------------------
        
        for prefix in prefixes:
            for ext in [".html", ".pdf", ".csv", ".billx", ".json"]:
                for file_path in glob.glob(os.path.join(temp_dir, f"{prefix}{ext}")):
                    try: os.remove(file_path)
                    except: pass
                
        try:
            if getattr(sys, 'frozen', False):
                base_dir = os.path.dirname(sys.executable)
            else:
                base_dir = os.path.dirname(os.path.abspath(__file__))
                
            for stray_img in glob.glob(os.path.join(base_dir, "cropped_*temp*.png")):
                try: os.remove(stray_img)
                except: pass
                
            # --- THE FIX: Smart Garbage Collector for Vault Orphans ---
            # Scans physical Vault and deletes payment proofs not logged in the database.
            try:
                import database
                conn = database.get_connection()
                c = conn.cursor()
                
                valid_files = set()
                for table in ["party_payments", "employee_payments", "labour_ledger"]:
                    try:
                        c.execute(f"SELECT attachment_path FROM {table} WHERE attachment_path IS NOT NULL AND attachment_path != ''")
                        for row in c.fetchall():
                            # Only save the file name, ignoring the computer's folder path
                            valid_files.add(os.path.basename(os.path.normpath(row[0])))
                    except: pass

                try:
                    c.execute("SELECT receipt_path FROM general_expenses WHERE receipt_path IS NOT NULL AND receipt_path != ''")
                    for row in c.fetchall():
                        valid_files.add(os.path.basename(os.path.normpath(row[0])))
                except: pass

                try:
                    c.execute("SELECT notes FROM general_expenses WHERE notes LIKE '%receipt%'")
                    for row in c.fetchall():
                        try:
                            j = json.loads(row[0])
                            if j.get("receipt"): valid_files.add(os.path.basename(os.path.normpath(j["receipt"])))
                        except: pass
                except: pass
                
                try:
                    c.execute("SELECT logo_path FROM company WHERE logo_path IS NOT NULL AND logo_path != ''")
                    for row in c.fetchall():
                        valid_files.add(os.path.basename(os.path.normpath(row[0])))
                except: pass

                try:
                    c.execute("SELECT profile_pic FROM users WHERE profile_pic IS NOT NULL AND profile_pic != ''")
                    for row in c.fetchall():
                        valid_files.add(os.path.basename(os.path.normpath(row[0])))
                except: pass

                # --- THE FIX: Teach GC to read Catalog Images ---
                try:
                    c.execute("SELECT description FROM inventory WHERE description IS NOT NULL AND description != ''")
                    for r in c.fetchall():
                        try:
                            j = json.loads(r[0])
                            if isinstance(j, dict) and "pics" in j:
                                for pic in j["pics"]:
                                    if isinstance(pic, dict) and "path" in pic:
                                        valid_files.add(os.path.basename(os.path.normpath(pic["path"])))
                        except: pass
                except: pass

                # --- THE FIX: Teach GC to read Employee & Labour files ---
                try:
                    c.execute("SELECT photo_path, document_path, docs_json FROM employees WHERE is_deleted=0")
                    for r in c.fetchall():
                        if r[0]: valid_files.add(os.path.basename(os.path.normpath(r[0])))
                        if r[1]: valid_files.add(os.path.basename(os.path.normpath(r[1])))
                        if r[2]:
                            try:
                                j = json.loads(r[2])
                                if isinstance(j, dict) and "docs" in j:
                                    for doc in j["docs"]:
                                        if isinstance(doc, dict) and "path" in doc:
                                            valid_files.add(os.path.basename(os.path.normpath(doc["path"])))
                            except: pass
                except: pass

                try:
                    c.execute("SELECT photo_path, doc_path FROM labours WHERE is_deleted=0")
                    for r in c.fetchall():
                        if r[0]: valid_files.add(os.path.basename(os.path.normpath(r[0])))
                        if r[1]:
                            try:
                                paths = json.loads(r[1])
                                if isinstance(paths, list):
                                    for p in paths: valid_files.add(os.path.basename(os.path.normpath(p)))
                            except: pass
                except: pass
                # ---------------------------------------------------------
                conn.close()
                
                vault_path = os.path.join(base_dir, "Vault")
                exp_path = os.path.join(base_dir, "expense_receipts")
                logo_path_dir = os.path.join(base_dir, "company_logos")
                avatar_path_dir = os.path.join(base_dir, "user_avatars")
                
                for target_dir in [vault_path, exp_path, logo_path_dir, avatar_path_dir]:
                    if os.path.exists(target_dir):
                        for root, dirs, files in os.walk(target_dir):
                            for file in files:
                                # --- THE FIX: Included 'item_' and 'avatar_' files in the vault sweep ---
                                if file.startswith(("payment_", "bulk_payment_", "advance_", "receipt_", "logo_", "photo_", "doc_", "proof_", "item_", "avatar_")):
                                    # Compare against the file name instead of the absolute path
                                    if file not in valid_files:
                                        full_path = os.path.normpath(os.path.join(root, file))
                                        try: 
                                            # --- THE FIX: Wait 24 hours before deleting orphaned files to protect the Undo Stack! ---
                                            if (time.time() - os.path.getmtime(full_path)) > 86400:
                                                os.remove(full_path)
                                            # ----------------------------------------------------------------------------------------
                                        except: pass
            except Exception as e:
                print(f"Garbage Collector Error: {e}")
            # ------------------------------------------------------------------------
            
        except: pass

    def get_global_theme_colors(self):
        from views.home_parts.ui_components import get_theme
        return get_theme() # Passes the entire color palette to the login screen!

    def apply_global_theme(self):
        colors = self.get_global_theme_colors()
        self.configure(bg=colors["bg"])
        self.container.configure(bg=colors["bg"])
        self.content_area.configure(bg=colors["bg"])
        self.page_separator.configure(bg=colors["border"])

        # --- THE FIX: Removed legacy wrapper theme application ---
        pass
        # ---------------------------------------------------------

        for widget in self.content_area.winfo_children():
            self.recolor_container_node(widget, colors["bg"])

        if hasattr(self.sidebar, "apply_theme"):
            self.sidebar.apply_theme()

    def recolor_container_node(self, widget, bg_color):
        widget_type = str(type(widget))
        if "HomeView" in widget_type or "InvoicesView" in widget_type or "PurchasesView" in widget_type:
            return
            
        try:
            if isinstance(widget, (tk.Frame, tk.Canvas)):
                widget.configure(bg=bg_color)
        except: pass

        if hasattr(widget, "canvas") and widget.canvas:
            try: widget.canvas.configure(bg=bg_color)
            except: pass
        if hasattr(widget, "inner_frame") and widget.inner_frame:
            try: widget.inner_frame.configure(bg=bg_color)
            except: pass

        for child in widget.winfo_children():
            self.recolor_container_node(child, bg_color)

    def on_closing(self):
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            
        db_filename = os.path.join(base_dir, "ledger_events_v13.db")
        backup_dir = os.path.join(base_dir, "Backups")

        try:
            if os.path.exists(db_filename):
                os.makedirs(backup_dir, exist_ok=True)
                timestamp = datetime.now().strftime("%d-%b-%Y_%I-%M-%S_%p")
                shutil.copy2(db_filename, os.path.join(backup_dir, f"backup_{timestamp}.db"))
                current_time = time.time()
                for file_path in glob.glob(os.path.join(backup_dir, "*.db")):
                    if os.path.isfile(file_path):
                        if (current_time - os.path.getmtime(file_path)) > (15 * 24 * 60 * 60):
                            try: os.remove(file_path)
                            except: pass 
        except: pass
        finally: self.destroy()

    def _on_mousewheel(self, event):
        widget = self.winfo_containing(event.x_root, event.y_root)
        if not widget: return
        if isinstance(widget, ttk.Treeview) or "treeview" in str(widget).lower(): return
        canvas = widget
        while canvas and not isinstance(canvas, tk.Canvas): canvas = canvas.master
        if isinstance(canvas, tk.Canvas):
            steps = int(-1 * (event.delta / 120)) if event.delta != 0 else 0
            canvas.yview_scroll(steps, "units")

    def lock_screen(self, event=None):
        """Instantly locks the session (Ctrl+L) and returns to the profile login screen."""
        if not getattr(self, "current_user", None):
            return
        # Close any open popups so nothing floats over the lock screen
        for widget in list(self.winfo_children()):
            if isinstance(widget, tk.Toplevel):
                try:
                    widget.destroy()
                except Exception:
                    pass

        self.current_user = None
        self.current_role = None
        self.current_user_id = None
        self.active_company_id = None
        database.set_active_user(1)

        if hasattr(self, 'sidebar') and self.sidebar:
            self.sidebar.pack_forget()
        if hasattr(self, 'page_separator') and self.page_separator:
            self.page_separator.pack_forget()
        for widget in self.content_area.winfo_children():
            widget.destroy()

        self.show_login_screen()

    def switch_view(self, view_name):
        # --- THE FIX: Seamless User Switching / Log Out ---
        if view_name == "Logout":
            if messagebox.askyesno("Switch User", "Are you sure you want to log out?"):
                self.lock_screen()
            return
        # --------------------------------------------------

        if view_name != "Home" and not self.active_company_id:
            messagebox.showwarning("Access Denied", "Please select a Company from the Home tab first.")
            return

        # --- THE FIX: Universal Database Firewall ---
        # Force the database engine to securely lock onto the active company 
        # EVERY single time a tab is clicked. This prevents multi-company data leaks!
        if self.active_company_id:
            database.set_active_company(self.active_company_id)
        # --------------------------------------------

        # --- THE FIX: Removed the heavy Sweeper from the Home button ---
        # The Garbage Collector now strictly runs once on startup, 
        # ensuring lightning-fast tab switching no matter how large the vault gets.
        # ---------------------------------------------------------------

        if hasattr(self, 'sidebar'): 
            # --- THE FIX: "Ghost" Sidebar Logic ---
            if self.active_company_id:
                # Unpack and repack to force correct left-to-right ordering
                self.content_area.pack_forget()
                self.sidebar.pack(side="left", fill="y")
                self.page_separator.pack(side="left", fill="y")
                self.content_area.pack(side="left", fill="both", expand=True)
            else:
                self.sidebar.pack_forget()
                self.page_separator.pack_forget()
            # --------------------------------------
            
            if hasattr(self.sidebar, 'sync_visibility'):
                self.sidebar.sync_visibility()
            if hasattr(self.sidebar, 'sync_active_button'):
                self.sidebar.sync_active_button(view_name)
            self.sidebar.update_idletasks()

        colors = self.get_global_theme_colors()

        new_page_layer = tk.Frame(self.content_area, bg=colors["bg"], highlightthickness=0, bd=0)

        if view_name in ["Dashboard", "Expenses", "Employees", "Labours", "Balance Sheet", "GST Report", "Profit & Loss", "Purchases", "Stock"]:
            target_frame = tk.Frame(new_page_layer, bg=colors["bg"], highlightthickness=0, bd=0)
            target_frame.pack(fill="both", expand=True)
        else:
            scroller = ScrollableFrame(new_page_layer, bg_color=colors["bg"], show_scrollbars=False)
            scroller.pack(fill="both", expand=True)
            target_frame = scroller.inner_frame

        if view_name not in ["Dashboard", "Balance Sheet", "GST Report", "Profit & Loss", "Home", "Stock"]:
            header = tk.Frame(target_frame, bg=colors["bg"], highlightthickness=0, bd=0)
            header.pack(fill="x", pady=(30, 20), padx=30)
            tk.Label(header, text=view_name, font=("Arial", 24, "bold"), bg=colors["bg"], fg=colors["text"]).pack(side="left")
            from views.audit_ui import attach_audit_button
            attach_audit_button(header, default_tab=view_name)

        if view_name == "Dashboard": DashboardView(target_frame).pack(fill="both", expand=True, padx=0)
        elif view_name == "Parties": CustomersView(target_frame).pack(fill="both", expand=True, padx=30)
        elif view_name == "Purchases": PurchasesView(target_frame).pack(fill="both", expand=True, padx=30)
        elif view_name == "Catalog": InventoryView(target_frame).pack(fill="both", expand=True, padx=30)
        elif view_name == "Stock": StockView(target_frame).pack(fill="both", expand=True, padx=30)
        elif view_name == "Invoices": InvoicesView(target_frame).pack(fill="both", expand=True, padx=30)
        elif view_name == "Home": HomeView(target_frame).pack(fill="both", expand=True, padx=30)
        elif view_name == "Settings": SettingsView(target_frame).pack(fill="both", expand=True, padx=30)
        elif view_name == "Expenses": ExpensesView(target_frame).pack(fill="both", expand=True, padx=30)
        elif view_name == "Employees": EmployeesView(target_frame).pack(fill="both", expand=True, padx=30) 
        elif view_name == "Labours": LaboursView(target_frame).pack(fill="both", expand=True, padx=30)
        elif view_name == "Balance Sheet": BalanceSheetView(target_frame).pack(fill="both", expand=True, padx=0) 
        elif view_name == "GST Report": GSTReportView(target_frame).pack(fill="both", expand=True, padx=30)
        elif view_name == "Profit & Loss": ProfitLossView(target_frame).pack(fill="both", expand=True, padx=0)    

        new_page_layer.place(relwidth=1.0, relheight=1.0, x=0, y=0)
        new_page_layer.lift() 
        self.update_idletasks()

        for widget in self.content_area.winfo_children():
            if widget != new_page_layer:
                widget.destroy()

        new_page_layer.place_forget()
        new_page_layer.pack(fill="both", expand=True)

if __name__ == "__main__":
    try:
        # --- THE FIX: Initialize database strictly ONCE at startup to prevent lock crashes! ---
        database.init_db()
        database.auto_heal_file_paths()
        # ------------------------------------------------------------------------------------
        app = LedgerApp()
        app.mainloop()
    except Exception as e:
        root = tk.Tk()
        root.withdraw() 
        error_msg = f"CRITICAL BOOT ERROR:\n\n{traceback.format_exc()}"
        messagebox.showerror("Fatal Startup Error", error_msg)
        root.destroy()