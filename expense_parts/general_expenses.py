import tkinter as tk
from tkinter import ttk, messagebox
import os
import sys
import json
import traceback
from datetime import date, datetime, timedelta
import webbrowser

# --- THE FIX: Bulletproof Executable Pathing ---
if getattr(sys, 'frozen', False):
    ROOT_DIR = os.path.dirname(sys.executable)
else:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parts_dir = os.path.dirname(current_dir)
    ROOT_DIR = os.path.dirname(parts_dir)

if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
# -----------------------------------------------

import database
from views.invoice_parts.helpers import format_currency, fetch_global_settings, smart_date_formatter
from views.invoice_parts.calendar_widget import NativeCalendar

from views.expense_parts.expense_exports import export_expenses_csv, print_expenses_pdf
from views.expense_parts.expense_forms import open_expense_form

class GeneralExpensesTab(tk.Frame):
    def __init__(self, parent):
        self.is_dark = database.get_ui_setting("dark_mode", "1") == "1"
        self.BG_COLOR = "#0f172a" if self.is_dark else "#e0f2fe"
        self.CARD_BG = "#1e293b" if self.is_dark else "#f0f9ff"
        self.BORDER_COLOR = "#334155" if self.is_dark else "#7dd3fc"
        self.TEXT_PRIMARY = "#f8fafc" if self.is_dark else "#0f172a"
        self.TEXT_SECONDARY = "#94a3b8" if self.is_dark else "#0284c7"
        self.ACCENT_GREEN = "#10b981"
        self.ACCENT_RED = "#ef4444"
        self.ACCENT_YELLOW = "#f59e0b"
        self.ACCENT_BLUE = "#3b82f6" if self.is_dark else "#0ea5e9"
        self.HEADER_BG = "#475569" if self.is_dark else "#bae6fd"
        self.HOVER_ROW = "#334155" if self.is_dark else "#bae6fd"
        self.PENDING_ROW = "#422006" if self.is_dark else "#fef3c7"

        super().__init__(parent, bg=self.BG_COLOR)
        self.valid_rows_cache = []
        self._last_hovered = None
        
        self.current_page = 1
        self.items_per_page = 50
        self.is_bulk_mode = False
        self.selected_items = set()
        self.current_filtered_rows = []
        self.cols_cache = []
        
        self.undo_stack = []
        self.redo_stack = []
        
        # --- THE FIX: Custom Sorted Expense Categories ---
        self.rental_cats = [
            "All Categories", 
            "General", 
            "Purchase Voucher", 
            "Fuel & Tolls", 
            "Labor/Worker", 
            "Vehicle Maintenance", 
            "Tea/Meals", 
            "Inventory Repair & Cleaning", 
            "Warehouse/Office Rent", 
            "Recharge & Subscriptions", 
            "Payroll",
            "New Inventory Assets", 
            "Event Consumables", 
            "Permits & Venue Fees", 
            "Freelancer", 
            "Insurance", 
            "Marketing"
        ]
        # -------------------------------------------------
        
        try:
            self.app = self.winfo_toplevel()
            comp_id = getattr(self.app, "active_company_id", 1)
            self.curr_fmt, self.date_fmt_code = fetch_global_settings(comp_id)
            
            def force_combo_jump(event):
                try:
                    w = event.widget
                    if not ("listbox" in str(w).lower() or isinstance(w, tk.Listbox)):
                        return
                    char = event.char
                    if char and char.isprintable() and len(char) == 1:
                        char = char.lower()
                        items = w.get(0, tk.END)
                        if not items: return
                        
                        sel = w.curselection()
                        start = sel[0] + 1 if sel else 0
                        
                        for i in range(start, len(items)):
                            if str(items[i]).lower().startswith(char):
                                w.selection_clear(0, tk.END)
                                w.selection_set(i)
                                w.activate(i)
                                w.see(i)
                                return "break"
                        for i in range(0, start):
                            if str(items[i]).lower().startswith(char):
                                w.selection_clear(0, tk.END)
                                w.selection_set(i)
                                w.activate(i)
                                w.see(i)
                                return "break"
                except: pass
            
            self.app.bind_class('TComboboxListbox', '<KeyPress>', force_combo_jump)
            self.app.bind_class('Listbox', '<KeyPress>', force_combo_jump)
            self.app.bind_all('<KeyPress>', force_combo_jump)

            # --- THE FIX: Added winfo_exists() to prevent crashing if the user switches tabs! ---
            self.app.bind("<Control-z>", lambda e: self.perform_undo() if self.winfo_exists() and self.winfo_ismapped() else None)
            self.app.bind("<Control-y>", lambda e: self.perform_redo() if self.winfo_exists() and self.winfo_ismapped() else None)
            # ------------------------------------------------------------------------------------
            
            self.build_ui()
            self.load_expenses()
        except Exception as e:
            err_msg = f"Failed to load General Expenses:\n\n{str(e)}\n\n{traceback.format_exc()}"
            tk.Label(self, text=err_msg, font=("Arial", 10), fg=self.ACCENT_RED, bg=self.BG_COLOR, justify="left").pack(fill="both", expand=True, padx=20, pady=20)

    def add_hover(self, widget, default_bg, hover_bg):
        widget.bind("<Enter>", lambda e: widget.config(bg=hover_bg))
        widget.bind("<Leave>", lambda e: widget.config(bg=default_bg))

    def make_smart_combo(self, cb_widget):
        cb_widget.bind("<Return>", lambda e: [e.widget.tk_focusNext().focus(), "break"])

    def push_undo(self, action_type, data):
        self.undo_stack.append((action_type, data))
        self.redo_stack.clear()
        self.update_undo_redo_btns()

    def perform_undo(self, event=None):
        if not self.undo_stack: return
        action, data = self.undo_stack.pop()
        comp_id = getattr(self.app, "active_company_id", 1)
        d_idx = self.cols_cache.index("expense_date") if "expense_date" in self.cols_cache else (self.cols_cache.index("date") if "date" in self.cols_cache else 1)
        t_idx = self.cols_cache.index("title") if "title" in self.cols_cache else 2
        c_idx = self.cols_cache.index("category") if "category" in self.cols_cache else 3
        a_idx = self.cols_cache.index("amount") if "amount" in self.cols_cache else 4
        n_idx = self.cols_cache.index("notes") if "notes" in self.cols_cache else 5
        p_idx = self.cols_cache.index("pay_method") if "pay_method" in self.cols_cache else 7
        s_idx = self.cols_cache.index("status") if "status" in self.cols_cache else 8
        rp_idx = self.cols_cache.index("receipt_path") if "receipt_path" in self.cols_cache else 9
        
        try:
            if action == "DELETE":
                database.restore_general_expense_record(data)
                self.redo_stack.append(("DELETE", data))
                database.log_audit("Expenses", "Undo Delete", record_ref=f"#{data[0]} • {data[t_idx]}", details=f"Restored deleted expense '{data[t_idx]}' ({data[c_idx]})", amount=float(data[a_idx] or 0.0), company_id=comp_id)
            elif action == "ADD":
                full_row = database.delete_general_expense_and_rollback(data)
                self.redo_stack.append(("ADD", full_row))
                if full_row:
                    database.log_audit("Expenses", "Undo Create", record_ref=f"#{full_row[0]} • {full_row[t_idx]}", details=f"Undid creation of expense '{full_row[t_idx]}'", amount=float(full_row[a_idx] or 0.0), company_id=comp_id)
            elif action == "EDIT":
                old_row, new_row = data
                database.update_general_expense(old_row[0], old_row[d_idx], old_row[t_idx], old_row[c_idx], old_row[a_idx], old_row[n_idx], old_row[p_idx], old_row[s_idx], old_row[rp_idx] if len(old_row) > rp_idx else "")
                self.redo_stack.append(("EDIT", (new_row, old_row)))
                database.log_audit("Expenses", "Undo Edit", record_ref=f"#{old_row[0]} • {old_row[t_idx]}", details=f"Reverted edits on expense '{old_row[t_idx]}'", amount=float(old_row[a_idx] or 0.0), company_id=comp_id)
            elif action == "BULK_DELETE":
                tot_restored = 0.0
                for row in data:
                    database.restore_general_expense_record(row)
                    tot_restored += float(row[a_idx] or 0.0)
                self.redo_stack.append(("BULK_DELETE", data))
                database.log_audit("Expenses", "Undo Bulk Delete", record_ref=f"{len(data)} Expenses", details=f"Restored {len(data)} bulk-deleted expenses", amount=tot_restored, company_id=comp_id)
            elif action == "BULK_REASSIGN":
                revert_data = []
                for exp_id, old_cat, new_cat in data:
                    conn = database.get_connection()
                    c = conn.cursor()
                    c.execute("UPDATE general_expenses SET category=? WHERE id=? AND company_id=?", (old_cat, int(exp_id), comp_id))
                    conn.commit()
                    conn.close()
                    revert_data.append((exp_id, new_cat, old_cat))
                self.redo_stack.append(("BULK_REASSIGN", revert_data))
                database.log_audit("Expenses", "Undo Reassign", record_ref=f"{len(data)} Expenses", details=f"Reverted category reassignment on {len(data)} expenses", amount=0.0, company_id=comp_id)
        except Exception as e:
            messagebox.showerror("Undo Error", str(e))
            
        self.update_undo_redo_btns()
        self.load_expenses()

    def perform_redo(self, event=None):
        if not self.redo_stack: return
        action, data = self.redo_stack.pop()
        comp_id = getattr(self.app, "active_company_id", 1)
        d_idx = self.cols_cache.index("expense_date") if "expense_date" in self.cols_cache else (self.cols_cache.index("date") if "date" in self.cols_cache else 1)
        t_idx = self.cols_cache.index("title") if "title" in self.cols_cache else 2
        c_idx = self.cols_cache.index("category") if "category" in self.cols_cache else 3
        a_idx = self.cols_cache.index("amount") if "amount" in self.cols_cache else 4
        n_idx = self.cols_cache.index("notes") if "notes" in self.cols_cache else 5
        p_idx = self.cols_cache.index("pay_method") if "pay_method" in self.cols_cache else 7
        s_idx = self.cols_cache.index("status") if "status" in self.cols_cache else 8
        rp_idx = self.cols_cache.index("receipt_path") if "receipt_path" in self.cols_cache else 9
        
        try:
            if action == "DELETE":
                database.delete_general_expense_and_rollback(data[0])
                self.undo_stack.append(("DELETE", data))
                database.log_audit("Expenses", "Redo Delete", record_ref=f"#{data[0]} • {data[t_idx]}", details=f"Redid deletion of expense '{data[t_idx]}'", amount=float(data[a_idx] or 0.0), company_id=comp_id)
            elif action == "ADD":
                database.restore_general_expense_record(data)
                self.undo_stack.append(("ADD", data[0]))
                database.log_audit("Expenses", "Redo Create", record_ref=f"#{data[0]} • {data[t_idx]}", details=f"Redid creation of expense '{data[t_idx]}'", amount=float(data[a_idx] or 0.0), company_id=comp_id)
            elif action == "EDIT":
                new_row, old_row = data
                database.update_general_expense(new_row[0], new_row[d_idx], new_row[t_idx], new_row[c_idx], new_row[a_idx], new_row[n_idx], new_row[p_idx], new_row[s_idx], new_row[rp_idx] if len(new_row) > rp_idx else "")
                self.undo_stack.append(("EDIT", (old_row, new_row)))
                database.log_audit("Expenses", "Redo Edit", record_ref=f"#{new_row[0]} • {new_row[t_idx]}", details=f"Re-applied edits on expense '{new_row[t_idx]}'", amount=float(new_row[a_idx] or 0.0), company_id=comp_id)
            elif action == "BULK_DELETE":
                tot_deleted = 0.0
                for row in data:
                    database.delete_general_expense_and_rollback(row[0])
                    tot_deleted += float(row[a_idx] or 0.0)
                self.undo_stack.append(("BULK_DELETE", data))
                database.log_audit("Expenses", "Redo Bulk Delete", record_ref=f"{len(data)} Expenses", details=f"Redid bulk deletion of {len(data)} expenses", amount=tot_deleted, company_id=comp_id)
            elif action == "BULK_REASSIGN":
                forward_data = []
                for exp_id, old_cat, new_cat in data:
                    conn = database.get_connection()
                    c = conn.cursor()
                    c.execute("UPDATE general_expenses SET category=? WHERE id=? AND company_id=?", (new_cat, int(exp_id), comp_id))
                    conn.commit()
                    conn.close()
                    forward_data.append((exp_id, new_cat, old_cat))
                self.undo_stack.append(("BULK_REASSIGN", forward_data))
                database.log_audit("Expenses", "Redo Reassign", record_ref=f"{len(data)} Expenses", details=f"Re-applied category reassignment on {len(data)} expenses", amount=0.0, company_id=comp_id)
        except Exception as e:
            messagebox.showerror("Redo Error", str(e))
            
        self.update_undo_redo_btns()
        self.load_expenses()

    def update_undo_redo_btns(self):
        if hasattr(self, 'btn_undo'):
            if self.undo_stack: self.btn_undo.config(fg=self.ACCENT_GREEN, state="normal")
            else: self.btn_undo.config(fg=self.TEXT_SECONDARY, state="disabled")
                
            if self.redo_stack: self.btn_redo.config(fg=self.ACCENT_BLUE, state="normal")
            else: self.btn_redo.config(fg=self.TEXT_SECONDARY, state="disabled")

    def trigger_add_dialog(self, target_id=None, is_clone=False):
        cats = [c for c in self.rental_cats if c != "All Categories"]
        comp_id = getattr(self.app, "active_company_id", 1)
        open_expense_form(self.winfo_toplevel(), comp_id, self.date_fmt_code, cats, self.load_expenses, self.push_undo, target_id, is_clone)

    def get_export_data(self, bulk=False):
        headers = ["DATE", "TITLE", "CATEGORY", "AMOUNT", "PAY METHOD", "NOTES"]
        data_rows = []
        
        current_month = ""
        for dt, r in self.current_filtered_rows:
            exp_id = str(r[0])
            if bulk and exp_id not in self.selected_items:
                continue
                
            date_idx = self.cols_cache.index("expense_date") if "expense_date" in self.cols_cache else (self.cols_cache.index("date") if "date" in self.cols_cache else 1)
            title_idx = self.cols_cache.index("title") if "title" in self.cols_cache else 2
            cat_idx = self.cols_cache.index("category") if "category" in self.cols_cache else 3
            amt_idx = self.cols_cache.index("amount") if "amount" in self.cols_cache else 4
            notes_idx = self.cols_cache.index("notes") if "notes" in self.cols_cache else 5

            e_date = r[date_idx]
            e_title = r[title_idx]
            e_cat = r[cat_idx]
            e_amt = float(r[amt_idx]) if r[amt_idx] else 0.0
            e_notes = r[notes_idx]

            m_group = dt.strftime("%B %Y") if dt != datetime.min else "Unknown Date"
            if m_group != current_month:
                current_month = m_group
                data_rows.append([f"📅 {m_group}"])
                
            display_note = e_notes if e_notes else ""
            pay_method = "—"
            
            # --- THE FIX: Pull dynamically from the native columns! ---
            if not str(exp_id).startswith(("EMP_PAY_", "LAB_PAY_", "VEND_PAY_")):
                n_idx = self.cols_cache.index("notes") if "notes" in self.cols_cache else 6
                p_idx = self.cols_cache.index("pay_method") if "pay_method" in self.cols_cache else 7
                s_idx = self.cols_cache.index("status") if "status" in self.cols_cache else 8
                
                display_note = r[n_idx] if len(r) > n_idx and r[n_idx] else ""
                pay_method = r[p_idx] if len(r) > p_idx and r[p_idx] else "Cash"
                status = r[s_idx] if len(r) > s_idx and r[s_idx] else "Paid"
                
                if status == "Pending (Unpaid)":
                    pay_method = f"⏳ {pay_method}"
            elif e_notes and e_notes.strip().startswith("{"):
                # Fallback for Auto-Synced Payroll Records
                try:
                    j = json.loads(e_notes)
                    display_note = j.get("note", "")
                    pay_method = j.get("pay_method", "—")
                    if j.get("status") == "Pending (Unpaid)":
                        pay_method = f"⏳ {pay_method}"
                except: pass
                
            formatted_date = smart_date_formatter(e_date, self.date_fmt_code)
            formatted_amt = format_currency(e_amt, self.curr_fmt)
            
            data_rows.append([formatted_date, e_title, e_cat, formatted_amt, pay_method, display_note])
            
        return headers, data_rows

    def trigger_export_csv(self, bulk=False):
        headers, data = self.get_export_data(bulk)
        if not data or (len(data) == 1 and str(data[0][0]).startswith("📅")):
            messagebox.showinfo("Empty", "No data to export.")
            return
        cb = self.cancel_bulk_mode if bulk else None
        export_expenses_csv(headers, data, cb)

    def trigger_export_pdf(self, bulk=False):
        headers, data = self.get_export_data(bulk)
        if not data or (len(data) == 1 and str(data[0][0]).startswith("📅")):
            messagebox.showinfo("Empty", "No data to export.")
            return
        cb = self.cancel_bulk_mode if bulk else None
        
        total = 0.0
        for dt, r in self.current_filtered_rows:
            if bulk and str(r[0]) not in self.selected_items: continue
            amt_idx = self.cols_cache.index("amount") if "amount" in self.cols_cache else 4
            total += float(r[amt_idx]) if r[amt_idx] else 0.0
            
        total_str = f"{format_currency(total, self.curr_fmt)}   (Exported Data)"
        print_expenses_pdf(headers, data, total_str, cb)

    def toggle_pending_filter(self):
        if self.pending_var.get():
            self.pending_var.set(False)
            self.btn_pending.config(bg=self.CARD_BG, fg=self.ACCENT_YELLOW)
        else:
            self.pending_var.set(True)
            self.btn_pending.config(bg=self.ACCENT_YELLOW, fg="#0f172a" if self.is_dark else "#ffffff")
        self.reset_page_and_load()

    def clear_filters(self):
        self.search_var.set("")
        self.filter_cat_var.set("All Categories")
        self.date_filter_var.set("All Time")
        self.filter_from_var.set("")
        self.filter_to_var.set("")
        if hasattr(self, 'pending_var') and self.pending_var.get():
            self.pending_var.set(False)
            self.btn_pending.config(bg=self.CARD_BG, fg=self.ACCENT_YELLOW)
        self.custom_date_f.pack_forget()
        self.reset_page_and_load()

    def build_ui(self):
        # --- THE FIX: Safe Local Event Binding (Prevents Memory Leak) ---
        def clear_focus(event):
            try:
                w_class = event.widget.winfo_class()
                if w_class not in ('Entry', 'TCombobox', 'Text', 'Treeview', 'Button'):
                    self.focus_set()
                    if hasattr(self, 'tree') and self.tree.selection() and not getattr(self, 'is_bulk_mode', False):
                        self.tree.selection_remove(self.tree.selection())
            except: pass
        self.bind("<ButtonPress-1>", clear_focus)
        # ----------------------------------------------------------------

        style = ttk.Style(self)
        style.theme_use("default")
        
        self.app.option_add("*TCombobox*Listbox.background", self.CARD_BG)
        self.app.option_add("*TCombobox*Listbox.foreground", self.TEXT_PRIMARY)
        self.app.option_add("*TCombobox*Listbox.selectBackground", self.ACCENT_BLUE)
        self.app.option_add("*TCombobox*Listbox.selectForeground", self.TEXT_PRIMARY)
        
        style.configure("TCombobox", fieldbackground=self.BG_COLOR, background=self.CARD_BG, foreground=self.TEXT_PRIMARY, arrowcolor=self.TEXT_PRIMARY, bordercolor=self.BORDER_COLOR, lightcolor=self.BORDER_COLOR, darkcolor=self.BORDER_COLOR)
        style.map("TCombobox", fieldbackground=[("readonly", self.BG_COLOR)], selectbackground=[("readonly", self.BG_COLOR)], selectforeground=[("readonly", self.TEXT_PRIMARY)])

        # --- THE FIX: Isolated Noticeable Scrollbars (Stops color flashing) ---
        style.configure("GenExp.Vertical.TScrollbar", background=self.TEXT_SECONDARY, troughcolor=self.BG_COLOR, bordercolor=self.BG_COLOR, arrowcolor=self.TEXT_PRIMARY, relief="flat")
        style.configure("GenExp.Horizontal.TScrollbar", background=self.TEXT_SECONDARY, troughcolor=self.BG_COLOR, bordercolor=self.BG_COLOR, arrowcolor=self.TEXT_PRIMARY, relief="flat")
        style.map("GenExp.Vertical.TScrollbar", background=[("active", self.ACCENT_BLUE)])
        style.map("GenExp.Horizontal.TScrollbar", background=[("active", self.ACCENT_BLUE)])
        # ----------------------------------------------------------------------

        top_f = tk.Frame(self, bg=self.BG_COLOR)
        top_f.pack(fill="x", pady=(0, 15))

        curr_role = getattr(self.app, "current_role", "Admin")
        curr_uid = getattr(self.app, "current_user_id", None) or getattr(database, "ACTIVE_USER_ID", 1)
        is_admin = (curr_role == "Admin" or str(curr_uid) == "1")

        if is_admin:
            totals_f = tk.Frame(top_f, bg=self.BG_COLOR)
            totals_f.pack(side="left")
            
            tk.Label(totals_f, text="TOTAL EXPENSES (FILTERED)", font=("Arial", 9, "bold"), bg=self.BG_COLOR, fg=self.TEXT_SECONDARY).pack(anchor="w")
            self.lbl_total = tk.Label(totals_f, text=format_currency(0, self.curr_fmt), font=("Arial", 22, "bold"), bg=self.BG_COLOR, fg=self.ACCENT_RED)
            self.lbl_total.pack(anchor="w", pady=(2, 0))

        self.tool_bar = tk.Frame(top_f, bg=self.BG_COLOR)
        self.tool_bar.pack(side="right", anchor="s")

        self.std_tools = tk.Frame(self.tool_bar, bg=self.BG_COLOR)
        self.std_tools.pack(fill="both", expand=True)

        self.btn_undo = tk.Button(self.std_tools, text="↺ Undo", font=("Arial", 11, "bold"), bg=self.CARD_BG, fg=self.TEXT_SECONDARY, state="disabled", relief="solid", highlightbackground=self.BORDER_COLOR, bd=1, cursor="hand2", padx=12, pady=6, command=self.perform_undo)
        self.btn_undo.pack(side="left", padx=(0, 5))
        
        self.btn_redo = tk.Button(self.std_tools, text="↻ Redo", font=("Arial", 11, "bold"), bg=self.CARD_BG, fg=self.TEXT_SECONDARY, state="disabled", relief="solid", highlightbackground=self.BORDER_COLOR, bd=1, cursor="hand2", padx=12, pady=6, command=self.perform_redo)
        self.btn_redo.pack(side="left", padx=(0, 20))

        btn_add = tk.Button(self.std_tools, text="+ Add Expense", font=("Arial", 10, "bold"), bg=self.ACCENT_BLUE, fg="#ffffff", relief="flat", cursor="hand2", padx=20, pady=8, command=self.trigger_add_dialog)
        btn_add.pack(side="right")

        btn_print = tk.Button(self.std_tools, text="🖨️ Export PDF", font=("Arial", 10, "bold"), bg=self.CARD_BG, fg=self.TEXT_PRIMARY, relief="solid", highlightbackground=self.BORDER_COLOR, bd=1, cursor="hand2", padx=15, pady=7, command=lambda: self.trigger_export_pdf(bulk=False))
        btn_print.pack(side="right", padx=(0, 10))

        btn_export = tk.Button(self.std_tools, text="📥 Export CSV", font=("Arial", 10, "bold"), bg=self.CARD_BG, fg=self.TEXT_PRIMARY, relief="solid", highlightbackground=self.BORDER_COLOR, bd=1, cursor="hand2", padx=15, pady=7, command=lambda: self.trigger_export_csv(bulk=False))
        btn_export.pack(side="right", padx=(0, 10))

        self.bulk_tools = tk.Frame(self.tool_bar, bg=self.BG_COLOR)
        self.lbl_bulk_mode = tk.Label(self.bulk_tools, text="Selection Mode Active", font=("Arial", 11, "bold"), bg=self.BG_COLOR, fg=self.ACCENT_RED)
        self.lbl_bulk_mode.pack(side="left", padx=(0, 15))
        
        self.btn_select_page = tk.Button(self.bulk_tools, text="☑ Select Visible", font=("Arial", 10, "bold"), bg=self.CARD_BG, fg=self.TEXT_PRIMARY, relief="flat", cursor="hand2", padx=10, pady=5, command=self.toggle_select_page)
        self.btn_select_page.pack(side="left", padx=(0, 5))
        self.add_hover(self.btn_select_page, self.CARD_BG, self.BORDER_COLOR)

        self.btn_select_all_filter = tk.Button(self.bulk_tools, text="☑ Select All", font=("Arial", 10, "bold"), bg=self.CARD_BG, fg=self.TEXT_PRIMARY, relief="flat", cursor="hand2", padx=10, pady=5, command=self.select_all_filtered)
        self.btn_select_all_filter.pack(side="left", padx=(0, 10))
        self.add_hover(self.btn_select_all_filter, self.CARD_BG, self.BORDER_COLOR)

        self.btn_cancel_bulk = tk.Button(self.bulk_tools, text="Cancel", font=("Arial", 10, "bold"), bg=self.CARD_BG, fg=self.TEXT_PRIMARY, relief="flat", cursor="hand2", padx=15, pady=5, command=self.cancel_bulk_mode)
        self.add_hover(self.btn_cancel_bulk, self.CARD_BG, self.BORDER_COLOR)
        
        self.btn_bulk_delete = tk.Button(self.bulk_tools, text="🗑 Delete Selected", font=("Arial", 10, "bold"), bg=self.ACCENT_RED, fg="#ffffff", relief="flat", cursor="hand2", padx=15, pady=5, command=self.confirm_bulk_delete)
        
        self.btn_bulk_export_csv = tk.Button(self.bulk_tools, text="⭳ Export CSV", font=("Arial", 10, "bold"), bg=self.CARD_BG, fg=self.TEXT_PRIMARY, relief="flat", cursor="hand2", padx=10, pady=5, command=lambda: self.trigger_export_csv(bulk=True))
        self.add_hover(self.btn_bulk_export_csv, self.CARD_BG, self.BORDER_COLOR)
        
        self.btn_bulk_export_pdf = tk.Button(self.bulk_tools, text="🖨️ Export PDF", font=("Arial", 10, "bold"), bg=self.CARD_BG, fg=self.TEXT_PRIMARY, relief="flat", cursor="hand2", padx=10, pady=5, command=lambda: self.trigger_export_pdf(bulk=True))
        self.add_hover(self.btn_bulk_export_pdf, self.CARD_BG, self.BORDER_COLOR)
        
        self.btn_bulk_reassign_exec = tk.Button(self.bulk_tools, text="Execute Reassign", font=("Arial", 10, "bold"), bg=self.ACCENT_BLUE, fg="#ffffff", relief="flat", cursor="hand2", padx=15, pady=5, command=self.confirm_bulk_reassign)
        
        self.bulk_cat_var = tk.StringVar(value="Select Category...")
        self.cb_bulk_cat = ttk.Combobox(self.bulk_tools, textvariable=self.bulk_cat_var, values=[c for c in self.rental_cats if c != "All Categories"], font=("Arial", 10), state="readonly", width=28)
        self.make_smart_combo(self.cb_bulk_cat)

        filter_f = tk.Frame(self, bg=self.CARD_BG, highlightbackground=self.BORDER_COLOR, highlightthickness=1)
        filter_f.pack(fill="x", pady=(0, 10))

        self.search_var = tk.StringVar()
        self.filter_cat_var = tk.StringVar(value="All Categories")
        self.date_filter_var = tk.StringVar(value="All Time")
        
        self.filter_from_var = tk.StringVar(value="")
        self.filter_to_var = tk.StringVar(value="")

        self.search_var.trace_add("write", lambda *args: self.reset_page_and_load())

        left_filter = tk.Frame(filter_f, bg=self.CARD_BG)
        left_filter.pack(side="left", padx=10, pady=10)

        tk.Label(left_filter, text="Search:", font=("Arial", 9, "bold"), bg=self.CARD_BG, fg=self.TEXT_PRIMARY).pack(side="left", padx=(5, 5))
        s_ent = tk.Entry(left_filter, textvariable=self.search_var, font=("Arial", 10), width=18, bg=self.BG_COLOR, fg=self.TEXT_PRIMARY, insertbackground=self.TEXT_PRIMARY, highlightbackground=self.BORDER_COLOR, highlightthickness=1)
        s_ent.pack(side="left", ipady=4, padx=(0, 0))
        
        # --- THE FIX: Perfectly Sized Red 'X' Clear Button ---
        btn_clear_search = tk.Button(left_filter, text="✖", font=("Arial", 9), bg=self.BORDER_COLOR, fg=self.ACCENT_RED, activebackground=self.BORDER_COLOR, activeforeground=self.ACCENT_RED, relief="solid", bd=1, pady=0, padx=0, cursor="hand2", command=lambda: self.search_var.set(""))
        btn_clear_search.pack(side="left", padx=(2, 10), ipady=1, ipadx=3)
        # -----------------------------------------------------

        tk.Label(left_filter, text="Category:", font=("Arial", 9, "bold"), bg=self.CARD_BG, fg=self.TEXT_PRIMARY).pack(side="left", padx=(0, 5))
        
        c_cb = ttk.Combobox(left_filter, textvariable=self.filter_cat_var, values=self.rental_cats, font=("Arial", 10), state="readonly", width=30)
        c_cb.pack(side="left", ipady=3, padx=(0, 15))
        c_cb.bind("<<ComboboxSelected>>", lambda e: self.reset_page_and_load())
        self.make_smart_combo(c_cb)

        self.pending_var = tk.BooleanVar(value=False)
        self.btn_pending = tk.Button(left_filter, text="⏳ Pending", font=("Arial", 9, "bold"), bg=self.CARD_BG, fg=self.ACCENT_YELLOW, relief="solid", bd=1, highlightbackground=self.BORDER_COLOR, cursor="hand2", padx=10, command=self.toggle_pending_filter)
        self.btn_pending.pack(side="left", padx=(0, 15), ipady=2)

        # --- THE FIX: Moved Filter & Date Combobox next to Pending ---
        lbl_filter = tk.Label(left_filter, text="Date Filter:", font=("Arial", 9, "bold"), bg=self.CARD_BG, fg=self.TEXT_PRIMARY)
        lbl_filter.pack(side="left", padx=(0, 5))
        
        date_cb = ttk.Combobox(left_filter, textvariable=self.date_filter_var, values=["All Time", "Today", "This Week", "This Month", "Last Month", "Custom Range"], state="readonly", width=14, font=("Arial", 10))
        date_cb.pack(side="left")
        self.make_smart_combo(date_cb)

        self.custom_date_f = tk.Frame(left_filter, bg=self.CARD_BG)
        
        tk.Label(self.custom_date_f, text="From:", font=("Arial", 9, "bold"), bg=self.CARD_BG, fg=self.TEXT_PRIMARY).pack(side="left", padx=(15, 5))
        tk.Entry(self.custom_date_f, textvariable=self.filter_from_var, font=("Arial", 10), width=10, bg=self.BG_COLOR, fg=self.TEXT_PRIMARY, insertbackground=self.TEXT_PRIMARY, highlightbackground=self.BORDER_COLOR, highlightthickness=1).pack(side="left", ipady=3)
        tk.Button(self.custom_date_f, text="📅", bg=self.CARD_BG, fg=self.TEXT_PRIMARY, relief="flat", cursor="hand2", command=lambda: NativeCalendar(self.winfo_toplevel(), self.filter_from_var)).pack(side="left", padx=(2, 8))

        tk.Label(self.custom_date_f, text="To:", font=("Arial", 9, "bold"), bg=self.CARD_BG, fg=self.TEXT_PRIMARY).pack(side="left", padx=(0, 5))
        tk.Entry(self.custom_date_f, textvariable=self.filter_to_var, font=("Arial", 10), width=10, bg=self.BG_COLOR, fg=self.TEXT_PRIMARY, insertbackground=self.TEXT_PRIMARY, highlightbackground=self.BORDER_COLOR, highlightthickness=1).pack(side="left", ipady=3)
        tk.Button(self.custom_date_f, text="📅", bg=self.CARD_BG, fg=self.TEXT_PRIMARY, relief="flat", cursor="hand2", command=lambda: NativeCalendar(self.winfo_toplevel(), self.filter_to_var)).pack(side="left", padx=(2, 8))

        def clear_custom_filter():
            self.date_filter_var.set("All Time")
            toggle_custom_date()

        tk.Button(self.custom_date_f, text="✖", font=("Arial", 9, "bold"), bg=self.ACCENT_RED, fg="#ffffff", relief="flat", cursor="hand2", command=clear_custom_filter, padx=5).pack(side="left", padx=(5, 0))

        def toggle_custom_date(*args):
            val = self.date_filter_var.get()
            if val == "Custom Range":
                self.custom_date_f.pack(side="left")
            else:
                self.custom_date_f.pack_forget()
            if hasattr(self, 'tree'): self.reset_page_and_load()
                
        date_cb.bind("<<ComboboxSelected>>", toggle_custom_date)
        self.custom_date_f.pack_forget()
        
        self.filter_from_var.trace_add("write", lambda *args: self.reset_page_and_load() if self.date_filter_var.get() == "Custom Range" else None)
        self.filter_to_var.trace_add("write", lambda *args: self.reset_page_and_load() if self.date_filter_var.get() == "Custom Range" else None)
        # ---------------------------------------------------------------------

        pag_frame = tk.Frame(self, bg=self.BG_COLOR)
        pag_frame.pack(side="bottom", fill="x", pady=(10, 0))
        center_pag = tk.Frame(pag_frame, bg=self.BG_COLOR)
        center_pag.pack(anchor="center") 
        self.btn_prev = tk.Button(center_pag, text="< Previous", font=("Arial", 10, "bold"), bg=self.CARD_BG, fg=self.TEXT_PRIMARY, relief="flat", cursor="hand2", command=self.prev_page, padx=12, pady=3)
        self.btn_prev.pack(side="left", padx=5)
        self.lbl_page = tk.Label(center_pag, text="Page 1 of 1", font=("Arial", 10, "bold"), bg=self.BG_COLOR, fg=self.TEXT_SECONDARY)
        self.lbl_page.pack(side="left", padx=15)
        self.btn_next = tk.Button(center_pag, text="Next >", font=("Arial", 10, "bold"), bg=self.CARD_BG, fg=self.TEXT_PRIMARY, relief="flat", cursor="hand2", command=self.next_page, padx=12, pady=3)
        self.btn_next.pack(side="left", padx=5)

        table_f = tk.Frame(self, bg=self.BG_COLOR, highlightbackground=self.BORDER_COLOR, highlightthickness=1)
        table_f.pack(fill="both", expand=True)

        # --- THE FIX: Apply the isolated scrollbar styles ---
        scroll_y = ttk.Scrollbar(table_f, orient="vertical", style="GenExp.Vertical.TScrollbar")
        scroll_x = ttk.Scrollbar(table_f, orient="horizontal", style="GenExp.Horizontal.TScrollbar")
        # ----------------------------------------------------
        
        style.configure("GenExp.Treeview.Heading", font=("Arial", 9, "bold"), background=self.HEADER_BG, foreground=self.TEXT_PRIMARY, relief="raised", borderwidth=3)
        style.map("GenExp.Treeview.Heading", background=[('active', '#64748b' if self.is_dark else self.BORDER_COLOR)])
        style.configure("GenExp.Treeview", font=("Arial", 10), rowheight=40, background=self.BG_COLOR, fieldbackground=self.BG_COLOR, foreground=self.TEXT_PRIMARY, borderwidth=0)
        style.map("GenExp.Treeview", background=[("selected", self.BORDER_COLOR)], foreground=[("selected", "#ffffff" if self.is_dark else self.TEXT_PRIMARY)])

        cols = ("sno_sel", "date", "title", "category", "amount", "pay_method", "notes", "receipt", "action")
        self.tree = ttk.Treeview(table_f, columns=cols, show="headings", style="GenExp.Treeview", height=self.items_per_page, yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)
        
        scroll_y.config(command=self.tree.yview)
        scroll_x.config(command=self.tree.xview)
        
        scroll_x.pack(side="bottom", fill="x")
        scroll_y.pack(side="right", fill="y")
        self.tree.pack(side="left", fill="both", expand=True)

        # --- THE FIX: Buttery Smooth Horizontal & Vertical Scrolling ---
        def _fast_scroll(event, direction):
            delta = -1 * (event.delta / 120) if os.name == 'nt' else -1 * event.delta
            if direction == "y":
                self.tree.yview_moveto(self.tree.yview()[0] + (delta * 0.008))
            else:
                self.tree.xview_moveto(self.tree.xview()[0] + (delta * 0.02))
        # ---------------------------------------------------------------
            
        self.tree.bind("<MouseWheel>", lambda e: _fast_scroll(e, "y"))
        self.tree.bind("<Shift-MouseWheel>", lambda e: _fast_scroll(e, "x"))

        self.tree.heading("sno_sel", text="S.NO", anchor="center")
        self.tree.heading("date", text="DATE", anchor="center")
        self.tree.heading("title", text="TITLE", anchor="center")
        self.tree.heading("category", text="CATEGORY", anchor="center")
        self.tree.heading("amount", text="AMOUNT", anchor="center") 
        self.tree.heading("pay_method", text="PAY METHOD", anchor="center")
        self.tree.heading("notes", text="NOTES", anchor="center")
        self.tree.heading("receipt", text="RECEIPT", anchor="center")
        self.tree.heading("action", text="ACTION", anchor="center")

        # --- THE FIX: Excel-Style Widths + Inventory Real-Time Saving Engine ---
        comp_id = getattr(self.app, "active_company_id", 1)
        try:
            w_dict = json.loads(database.get_ui_setting(f"gen_exp_widths_{comp_id}", "{}"))
        except:
            w_dict = {}

        self.tree.column("sno_sel", width=w_dict.get("sno_sel", 60), minwidth=30, anchor="center", stretch=False)
        self.tree.column("date", width=w_dict.get("date", 120), minwidth=60, anchor="center", stretch=False)
        self.tree.column("title", width=w_dict.get("title", 300), minwidth=100, anchor="center", stretch=False)
        self.tree.column("category", width=w_dict.get("category", 150), minwidth=80, anchor="center", stretch=False)
        self.tree.column("amount", width=w_dict.get("amount", 120), minwidth=80, anchor="center", stretch=False)
        self.tree.column("pay_method", width=w_dict.get("pay_method", 150), minwidth=80, anchor="center", stretch=False)
        self.tree.column("notes", width=w_dict.get("notes", 400), minwidth=150, anchor="center", stretch=False) 
        self.tree.column("receipt", width=w_dict.get("receipt", 100), minwidth=60, anchor="center", stretch=False) 
        
        # --- THE FIX: Hardcode 'action' width so it doesn't stretch-loop on boot ---
        self.tree.column("action", width=100, minwidth=80, anchor="center", stretch=True)
        # ---------------------------------------------------------------------------

        def save_widths():
            # --- THE FIX: Stop saving the 'action' column width ---
            new_w = {c: self.tree.column(c, "width") for c in cols if c != "action"}
            try:
                current_comp = getattr(self.app, "active_company_id", 1)
                conn = database.get_connection()
                c = conn.cursor()
                key = f"gen_exp_widths_{current_comp}"
                c.execute("REPLACE INTO ui_settings (setting_key, setting_value) VALUES (?, ?)", (key, json.dumps(new_w)))
                conn.commit()
                conn.close()
            except: pass

        def on_sep_drag(event):
            if self.tree.identify_region(event.x, event.y) == "separator":
                self.after(50, save_widths)
                
        self.tree.bind("<B1-Motion>", on_sep_drag, add="+")
        self.tree.bind("<ButtonRelease-1>", lambda e: self.after(50, save_widths) if self.tree.identify_region(e.x, e.y) == "separator" else None, add="+")
        # -----------------------------------------------------------------------

        self.tree.tag_configure('month_header', background=self.HEADER_BG, foreground=self.TEXT_PRIMARY, font=("Arial", 12, "bold"))
        
        self.tree.tag_configure("evenrow", background=self.BG_COLOR, foreground=self.TEXT_PRIMARY)
        self.tree.tag_configure("oddrow", background=self.CARD_BG, foreground=self.TEXT_PRIMARY)
        self.tree.tag_configure("empty_row", background=self.BG_COLOR)
        
        self.tree.tag_configure('selected_row', background=self.BORDER_COLOR, foreground=self.TEXT_PRIMARY)
        self.tree.tag_configure("hover", background=self.HOVER_ROW)
        self.tree.tag_configure("pending_row", foreground=self.ACCENT_YELLOW)

        # --- THE FIX: Block Actions if Click Started in the Header/Separator ---
        def on_exp_press(event):
            self._exp_press_region = self.tree.identify("region", event.x, event.y)
        self.tree.bind("<ButtonPress-1>", on_exp_press, add="+")

        def safe_exp_click(event):
            if getattr(self, "_exp_press_region", "") != "cell": return
            self.on_left_click(event)
            
        self.tree.bind("<ButtonRelease-1>", safe_exp_click, add="+")
        self.tree.bind("<Button-3>", self.on_right_click)
        self.tree.bind("<Double-1>", self.on_double_click)
        # -----------------------------------------------------------------------

        def on_exp_motion(event):
            region = self.tree.identify("region", event.x, event.y)
            col = self.tree.identify_column(event.x)
            if region == "separator": return
            
            item = self.tree.identify_row(event.y)
            if item != self._last_hovered:
                if self._last_hovered and self.tree.exists(self._last_hovered):
                    tags = list(self.tree.item(self._last_hovered, "tags"))
                    if "hover" in tags: tags.remove("hover"); self.tree.item(self._last_hovered, tags=tuple(tags))
                if item and not str(item).startswith("month_") and not str(item).startswith("empty_"):
                    tags = list(self.tree.item(item, "tags"))
                    if "hover" not in tags: tags.append("hover"); self.tree.item(item, tags=tuple(tags))
                self._last_hovered = item
            
            if region == "cell" and col in ('#8', '#9') and not str(item).startswith("month_") and not str(item).startswith("empty_") and not self.is_bulk_mode:
                self.tree.config(cursor="hand2")
            else:
                self.tree.config(cursor="")
                
        self.tree.bind("<Motion>", on_exp_motion)
        
        def on_exp_leave(event):
            if self._last_hovered and self.tree.exists(self._last_hovered):
                tags = list(self.tree.item(self._last_hovered, "tags"))
                if "hover" in tags: tags.remove("hover"); self.tree.item(self._last_hovered, tags=tuple(tags))
            self._last_hovered = None
            
        self.tree.bind("<Leave>", on_exp_leave)

    def prev_page(self):
        if self.current_page > 1: self.current_page -= 1; self.load_expenses()
    def next_page(self):
        if hasattr(self, 'total_pages') and self.current_page < self.total_pages: self.current_page += 1; self.load_expenses()
    def reset_page_and_load(self):
        self.current_page = 1
        self.load_expenses()

    def enable_bulk_mode(self, mode_type, initial_item=None):
        if mode_type == "delete":
            curr_role = getattr(self.app, "current_role", "Admin")
            curr_uid = getattr(self.app, "current_user_id", None) or getattr(database, "ACTIVE_USER_ID", 1)
            if curr_role != "Admin" and str(curr_uid) != "1":
                u_perms = database.get_user_permissions(curr_uid)
                exp_rules = u_perms.get("expense_rules", {}) if isinstance(u_perms.get("expense_rules"), dict) else {}
                if exp_rules.get("block_delete", False):
                    messagebox.showerror("Access Denied", "Deleting expenses is locked for your account.\n\nPlease contact the Admin.", parent=self)
                    return

        self.is_bulk_mode = True
        self.selected_items.clear()
        if initial_item: self.selected_items.add(str(initial_item))
        
        self.std_tools.pack_forget()
        self.bulk_tools.pack(fill="both", expand=True)
        
        self.btn_bulk_delete.pack_forget()
        self.btn_bulk_export_csv.pack_forget()
        self.btn_bulk_export_pdf.pack_forget()
        self.cb_bulk_cat.pack_forget()
        self.btn_bulk_reassign_exec.pack_forget()
        self.btn_cancel_bulk.pack_forget()
        
        self.btn_cancel_bulk.pack(side="right", padx=(10, 0))
        
        if mode_type == "delete":
            self.lbl_bulk_mode.config(text="Delete Mode Active", fg=self.ACCENT_RED)
            self.btn_bulk_delete.pack(side="right")
        elif mode_type == "export":
            self.lbl_bulk_mode.config(text="Export Mode Active", fg=self.TEXT_PRIMARY)
            self.btn_bulk_export_pdf.pack(side="right", padx=(0,0))
            self.btn_bulk_export_csv.pack(side="right", padx=(0,5))
        elif mode_type == "reassign":
            self.lbl_bulk_mode.config(text="Reassign Category Active", fg=self.ACCENT_BLUE)
            self.btn_bulk_reassign_exec.pack(side="right")
            self.cb_bulk_cat.pack(side="right", padx=(0, 10))

        self.tree.heading("sno_sel", text="☑")
        self.update_bulk_action_btns()
        self.load_expenses()

    def cancel_bulk_mode(self):
        self.is_bulk_mode = False
        self.selected_items.clear()
        self.bulk_tools.pack_forget()
        self.std_tools.pack(fill="both", expand=True)
        self.tree.heading("sno_sel", text="S.NO")
        self.load_expenses()

    def toggle_select_page(self):
        visible_ids = set()
        for item in self.tree.get_children():
            tags = self.tree.item(item, "tags")
            if "month_header" not in tags: visible_ids.add(str(item))
            
        if not visible_ids: return
        if visible_ids.issubset(self.selected_items): self.selected_items -= visible_ids
        else: self.selected_items |= visible_ids
        self.update_bulk_action_btns(); self.load_expenses()

    def select_all_filtered(self):
        if hasattr(self, 'current_filtered_rows'):
            for dt, r in self.current_filtered_rows:
                self.selected_items.add(str(r[0]))
        self.update_bulk_action_btns()
        self.load_expenses()

    def update_bulk_action_btns(self):
        count = len(self.selected_items)
        self.btn_bulk_delete.config(text=f"🗑 Delete ({count})")
        self.btn_bulk_export_csv.config(text=f"⭳ CSV ({count})")
        self.btn_bulk_export_pdf.config(text=f"🖨️ PDF ({count})")
        self.btn_bulk_reassign_exec.config(text=f"Reassign ({count})")

    def confirm_bulk_delete(self):
        if not self.selected_items: self.cancel_bulk_mode(); return
        
        # --- THE FIX: Guard Auto-Synced Payroll & Vendor Records ---
        deletable_items = [i for i in self.selected_items if not str(i).startswith(("EMP_PAY_", "LAB_PAY_", "VEND_PAY_"))]
        if not deletable_items:
            messagebox.showinfo("Locked", "The selected items are auto-synced Payroll records and cannot be deleted from here.", parent=self)
            self.cancel_bulk_mode()
            return
            
        if messagebox.askyesno("Confirm Delete", f"Permanently delete {len(deletable_items)} selected expense records?\n(Auto-synced payroll records will be skipped)"):
            try:
                comp_id = getattr(self.app, "active_company_id", 1)
                database.set_active_company(comp_id)
                t_idx = self.cols_cache.index("title") if "title" in self.cols_cache else 2
                a_idx = self.cols_cache.index("amount") if "amount" in self.cols_cache else 4

                deleted_rows = []
                deleted_titles = []
                total_del_amt = 0.0
                skipped_locked = 0

                for exp_id_str in deletable_items:
                    exp_id = int(exp_id_str)
                    allowed, _ = database.check_expense_permission(exp_id, action="delete", company_id=comp_id)
                    if not allowed:
                        skipped_locked += 1
                        continue
                    r = database.delete_general_expense_and_rollback(exp_id)
                    if r:
                        deleted_rows.append(r)
                        deleted_titles.append(str(r[t_idx]))
                        total_del_amt += float(r[a_idx] or 0.0)
                
                if deleted_rows:
                    self.push_undo("BULK_DELETE", deleted_rows)
                    database.log_audit(
                        "Expenses", "Bulk Deleted",
                        record_ref=f"{len(deleted_rows)} Expenses",
                        details=f"Deleted expenses: {', '.join(deleted_titles[:8])}" + ("..." if len(deleted_titles) > 8 else ""),
                        amount=total_del_amt, company_id=comp_id
                    )
                if skipped_locked > 0:
                    messagebox.showwarning(
                        "Partial Deletion",
                        f"Deleted {len(deleted_rows)} expenses.\n\n{skipped_locked} past-date or locked expense(s) were skipped due to your account permissions.",
                        parent=self
                    )
                self.cancel_bulk_mode()
            except Exception as e:
                messagebox.showerror("Database Error", f"Failed to perform bulk delete:\n{str(e)}")

    def confirm_bulk_reassign(self):
        if not self.selected_items: self.cancel_bulk_mode(); return
        new_cat = self.bulk_cat_var.get()
        if new_cat == "Select Category...":
            messagebox.showerror("Error", "Please select a valid category from the dropdown.")
            return
            
        # --- THE FIX: Guard Auto-Synced Payroll & Vendor Records ---
        reassignable_items = [i for i in self.selected_items if not str(i).startswith(("EMP_PAY_", "LAB_PAY_", "VEND_PAY_"))]
        if not reassignable_items:
            messagebox.showinfo("Locked", "The selected items are auto-synced Payroll records and cannot be reassigned.", parent=self)
            self.cancel_bulk_mode()
            return
            
        if messagebox.askyesno("Confirm", f"Reassign {len(reassignable_items)} expenses to '{new_cat}'?\n(Auto-synced payroll records will be skipped)"):
            try:
                comp_id = getattr(self.app, "active_company_id", 1)
                database.set_active_company(comp_id)
                c_idx = self.cols_cache.index("category") if "category" in self.cols_cache else 3
                t_idx = self.cols_cache.index("title") if "title" in self.cols_cache else 2
                a_idx = self.cols_cache.index("amount") if "amount" in self.cols_cache else 4

                reassign_data = []
                allowed_ids = []
                reassigned_titles = []
                total_reassigned_amt = 0.0
                skipped_locked = 0
                
                for exp_id_str in reassignable_items:
                    exp_id = int(exp_id_str)
                    allowed, _ = database.check_expense_permission(exp_id, action="reassign", company_id=comp_id)
                    if not allowed:
                        skipped_locked += 1
                        continue
                    r = database.get_general_expense_record(exp_id)
                    if r:
                        old_cat = r[c_idx]
                        if old_cat != new_cat:
                            reassign_data.append((exp_id, old_cat, new_cat))
                            allowed_ids.append(exp_id)
                            reassigned_titles.append(f"{r[t_idx]} ({old_cat} ➔ {new_cat})")
                            total_reassigned_amt += float(r[a_idx] or 0.0)
                
                if allowed_ids:
                    database.bulk_reassign_general_expenses(allowed_ids, new_cat)
                    self.push_undo("BULK_REASSIGN", reassign_data)
                    database.log_audit(
                        "Expenses", "Updated (Reassigned)",
                        record_ref=f"{len(allowed_ids)} Expenses",
                        details=f"Reassigned to '{new_cat}': {', '.join(reassigned_titles[:6])}" + ("..." if len(reassigned_titles) > 6 else ""),
                        amount=total_reassigned_amt, company_id=comp_id
                    )
                if skipped_locked > 0:
                    messagebox.showwarning(
                        "Partial Reassign",
                        f"Reassigned {len(allowed_ids)} expenses.\n\n{skipped_locked} past-date expense(s) were skipped due to your account permissions.",
                        parent=self
                    )
                self.cancel_bulk_mode()
            except Exception as e:
                messagebox.showerror("Database Error", f"Failed to reassign category:\n{str(e)}")

    def show_row_menu(self, exp_id, x, y):
        # --- THE FIX: Smart Context Menu for Auto-Synced Records ---
        exp_id_str = str(exp_id)
        if exp_id_str.startswith(("EMP_PAY_", "LAB_PAY_", "VEND_PAY_")):
            menu = tk.Menu(self, tearoff=0, font=("Arial", 10), bg=self.CARD_BG, fg=self.TEXT_PRIMARY)
            
            # Dynamically change the text based on where the record came from!
            if exp_id_str.startswith("EMP_PAY_"):
                lbl_title = "🔒 Auto-Synced Payroll Record"
                lbl_tab = "Go to Employees Tab to Edit"
            elif exp_id_str.startswith("LAB_PAY_"):
                lbl_title = "🔒 Auto-Synced Wage Record"
                lbl_tab = "Go to Labours Tab to Edit"
            else:
                lbl_title = "🔒 Auto-Synced Vendor Payment"
                lbl_tab = "Go to Purchases Tab to Edit"
                
            menu.add_command(label=lbl_title, foreground=self.TEXT_SECONDARY)
            menu.add_separator()
            menu.add_command(label="⭳ Bulk Export", command=lambda: self.enable_bulk_mode("export", exp_id))
            menu.add_separator()
            menu.add_command(label=lbl_tab, foreground=self.TEXT_SECONDARY)
            menu.tk_popup(x, y)
            return
        # -----------------------------------------------------------

        menu = tk.Menu(self, tearoff=0, font=("Arial", 10), bg=self.CARD_BG, fg=self.TEXT_PRIMARY)
        
        menu.add_command(label="✏️ Edit Expense", command=lambda: self.trigger_add_dialog(target_id=exp_id))
        menu.add_command(label="📑 Duplicate Record", command=lambda: self.trigger_add_dialog(target_id=exp_id, is_clone=True))
        
        is_pending = False
        for dt, r in self.valid_rows_cache:
            if str(r[0]) == str(exp_id):
                # --- THE FIX: Read native status for Context Menu ---
                if not str(exp_id).startswith(("EMP_PAY_", "LAB_PAY_", "VEND_PAY_")):
                    s_idx = self.cols_cache.index("status") if "status" in self.cols_cache else 8
                    if len(r) > s_idx and r[s_idx] == "Pending (Unpaid)":
                        is_pending = True
                else:
                    try: 
                        notes_idx = self.cols_cache.index("notes") if "notes" in self.cols_cache else 5
                        notes_str = r[notes_idx]
                        j = json.loads(notes_str)
                        if j.get("status") == "Pending (Unpaid)": is_pending = True
                    except: pass
                break
        
        if is_pending:
            menu.add_separator()
            menu.add_command(label="💰 Mark as Paid", command=lambda: self.mark_expense_paid(exp_id), foreground=self.ACCENT_GREEN)
            
        can_delete = True
        curr_role = getattr(self.app, "current_role", "Admin")
        curr_uid = getattr(self.app, "current_user_id", None) or getattr(database, "ACTIVE_USER_ID", 1)
        if curr_role != "Admin" and str(curr_uid) != "1":
            u_perms = database.get_user_permissions(curr_uid)
            exp_rules = u_perms.get("expense_rules", {}) if isinstance(u_perms.get("expense_rules"), dict) else {}
            if exp_rules.get("block_delete", False):
                can_delete = False

        menu.add_separator()
        menu.add_command(label="⭳ Bulk Export", command=lambda: self.enable_bulk_mode("export", exp_id))
        menu.add_command(label="↻ Bulk Reassign", command=lambda: self.enable_bulk_mode("reassign", exp_id))
        if can_delete:
            menu.add_command(label="🗑 Bulk Delete", command=lambda: self.enable_bulk_mode("delete", exp_id), foreground=self.ACCENT_RED)
            menu.add_separator()
            menu.add_command(label="❌ Delete Single Record", command=lambda: self.confirm_single_delete(exp_id), foreground=self.ACCENT_RED)
        menu.tk_popup(x, y)

    def mark_expense_paid(self, exp_id):
        try:
            comp_id = getattr(self.app, "active_company_id", 1)
            allowed, err_msg = database.check_expense_permission(int(exp_id), action="edit", company_id=comp_id)
            if not allowed:
                messagebox.showerror("Access Denied", err_msg, parent=self)
                return

            database.set_active_company(comp_id)
            old_row = database.get_general_expense_record(int(exp_id))
            if old_row:
                # --- THE FIX: Dynamic mapping prevents data scrambling! ---
                d_idx = self.cols_cache.index("expense_date") if "expense_date" in self.cols_cache else (self.cols_cache.index("date") if "date" in self.cols_cache else 1)
                t_idx = self.cols_cache.index("title") if "title" in self.cols_cache else 2
                c_idx = self.cols_cache.index("category") if "category" in self.cols_cache else 3
                a_idx = self.cols_cache.index("amount") if "amount" in self.cols_cache else 4
                n_idx = self.cols_cache.index("notes") if "notes" in self.cols_cache else 5
                p_idx = self.cols_cache.index("pay_method") if "pay_method" in self.cols_cache else 7
                rp_idx = self.cols_cache.index("receipt_path") if "receipt_path" in self.cols_cache else 9
                
                database.update_general_expense(int(exp_id), old_row[d_idx], old_row[t_idx], old_row[c_idx], old_row[a_idx], old_row[n_idx], old_row[p_idx], 'Paid', old_row[rp_idx] if len(old_row) > rp_idx else "")
                
                new_row = database.get_general_expense_record(int(exp_id))
                self.push_undo("EDIT", (old_row, new_row))
                database.log_audit(
                    "Expenses", "Marked Paid",
                    record_ref=f"#{int(exp_id)} • {old_row[t_idx]}",
                    details=f"Status: 'Pending (Unpaid)' ➔ 'Paid' • Mode: {old_row[p_idx]}",
                    amount=float(old_row[a_idx] or 0.0), company_id=comp_id
                )
                
            self.load_expenses()
        except Exception as e: 
            print(f"Error marking paid: {e}")

    def open_receipt(self, exp_id):
        receipt_path = ""
        for dt, r in self.valid_rows_cache:
            if str(r[0]) == str(exp_id):
                if not str(exp_id).startswith(("EMP_PAY_", "LAB_PAY_", "VEND_PAY_")):
                    r_idx = self.cols_cache.index("receipt_path") if "receipt_path" in self.cols_cache else 9
                    if len(r) > r_idx and r[r_idx]:
                        receipt_path = str(r[r_idx]).strip()
                if not receipt_path:
                    try:
                        notes_idx = self.cols_cache.index("notes") if "notes" in self.cols_cache else 5
                        notes_str = r[notes_idx]
                        if notes_str and str(notes_str).strip().startswith("{"):
                            j = json.loads(notes_str)
                            receipt_path = j.get("receipt", "")
                    except Exception:
                        pass
                break
        if receipt_path and os.path.exists(receipt_path):
            try:
                os.startfile(os.path.realpath(receipt_path))
            except Exception:
                webbrowser.open('file://' + os.path.realpath(receipt_path))
        else:
            messagebox.showerror("File Not Found", "The attached receipt file could not be located on this device.", parent=self)

    def on_left_click(self, event):
        if self.tree.identify("region", event.x, event.y) == "cell":
            col = self.tree.identify_column(event.x)
            exp_id = self.tree.identify_row(event.y)
            if not exp_id or str(exp_id).startswith("month_") or str(exp_id).startswith("empty_"): return

            if self.is_bulk_mode:
                exp_id_str = str(exp_id)
                if exp_id_str in self.selected_items: self.selected_items.remove(exp_id_str)
                else: self.selected_items.add(exp_id_str)
                
                vals = list(self.tree.item(exp_id, "values"))
                vals[0] = "☑" if exp_id_str in self.selected_items else "☐"
                
                tags = list(self.tree.item(exp_id, "tags"))
                if "selected_row" in tags: tags.remove("selected_row")
                if exp_id_str in self.selected_items: tags.append("selected_row")
                
                self.tree.item(exp_id, values=vals, tags=tuple(tags))
                self.update_bulk_action_btns()
                
            elif not self.is_bulk_mode:
                if col == '#8': 
                    vals = self.tree.item(exp_id, "values")
                    if "📄" in vals[7]: self.open_receipt(exp_id)
                elif col == '#9': 
                    self.show_row_menu(exp_id, event.x_root, event.y_root)

    def on_right_click(self, event):
        exp_id = self.tree.identify_row(event.y)
        if not exp_id or str(exp_id).startswith("month_") or str(exp_id).startswith("empty_"): return
        self.tree.selection_set(exp_id)
        
        if self.is_bulk_mode:
            menu = tk.Menu(self, tearoff=0, font=("Arial", 10), bg=self.CARD_BG, fg=self.TEXT_PRIMARY)
            menu.add_command(label="Cancel Selection", command=self.cancel_bulk_mode)
            menu.tk_popup(event.x_root, event.y_root)
        else:
            self.show_row_menu(exp_id, event.x_root, event.y_root)

    def confirm_single_delete(self, exp_id):
        comp_id = getattr(self.app, "active_company_id", 1)
        allowed, err_msg = database.check_expense_permission(int(exp_id), action="delete", company_id=comp_id)
        if not allowed:
            messagebox.showerror("Access Denied", err_msg, parent=self)
            return

        if messagebox.askyesno("Confirm", "Delete this expense record?"):
            database.set_active_company(comp_id)
            row = database.delete_general_expense_and_rollback(int(exp_id))
            if row:
                self.push_undo("DELETE", row)
                d_idx = self.cols_cache.index("expense_date") if "expense_date" in self.cols_cache else (self.cols_cache.index("date") if "date" in self.cols_cache else 1)
                t_idx = self.cols_cache.index("title") if "title" in self.cols_cache else 2
                c_idx = self.cols_cache.index("category") if "category" in self.cols_cache else 3
                a_idx = self.cols_cache.index("amount") if "amount" in self.cols_cache else 4
                database.log_audit(
                    "Expenses", "Deleted",
                    record_ref=f"#{int(exp_id)} • {row[t_idx]}",
                    details=f"Deleted expense '{row[t_idx]}' ({row[c_idx]}) dated @@DATE:{row[d_idx]}@@",
                    amount=float(row[a_idx] or 0.0), company_id=comp_id
                )
            self.load_expenses()

    def on_double_click(self, event):
        exp_id = self.tree.identify_row(event.y)
        if not exp_id or str(exp_id).startswith("month_") or str(exp_id).startswith("empty_") or self.is_bulk_mode: return
        
        # --- THE FIX: Block Edit Dialog on Auto-Synced Records ---
        if str(exp_id).startswith(("EMP_PAY_", "LAB_PAY_", "VEND_PAY_")):
            messagebox.showinfo("Locked Record", "This is an auto-synced transaction.\n\nPlease edit or delete it from its original source tab.", parent=self)
            return
        # ---------------------------------------------
        
        self.trigger_add_dialog(target_id=exp_id)

    def get_date_bounds(self):
        val = self.date_filter_var.get()
        today = date.today()
        
        if val == "Today":
            return today, today
        elif val == "This Week":
            start = today - timedelta(days=today.weekday())
            return start, today
        elif val == "This Month":
            start = today.replace(day=1)
            return start, today
        elif val == "Last Month":
            first_of_this_month = today.replace(day=1)
            last_month_end = first_of_this_month - timedelta(days=1)
            last_month_start = last_month_end.replace(day=1)
            return last_month_start, last_month_end
        elif val == "Custom Range":
            try: start = datetime.strptime(self.filter_from_var.get().strip(), self.date_fmt_code).date()
            except: start = None
            try: end = datetime.strptime(self.filter_to_var.get().strip(), self.date_fmt_code).date()
            except: end = None
            return start, end
            
        return None, None 

    def load_expenses(self):
        for item in self.tree.get_children(): self.tree.delete(item)
        
        database.set_active_company(getattr(self.app, "active_company_id", 1))
        rows = list(database.get_all_general_expenses())
        
        # --- THE FIX: Restore Dynamic Schema Scanning (Immune to Column Shifts) ---
        conn = database.get_connection()
        c = conn.cursor()
        c.execute("PRAGMA table_info(general_expenses)")
        self.cols_cache = [r[1] for r in c.fetchall()]
        # --------------------------------------------------------------------------
        
        # --- THE FIX: UI Mirror Engine for Employee Payments ---
        try:
            comp_id = getattr(self.app, "active_company_id", 1)
            
            # THE FIX: Force schema upgrade to prevent silent SQL crashes!
            try: c.execute("ALTER TABLE employee_payments ADD COLUMN mode TEXT DEFAULT 'Cash'")
            except: pass
            try: c.execute("ALTER TABLE employee_payments ADD COLUMN attachment_path TEXT DEFAULT ''")
            except: pass
            
            c.execute('''
                SELECT ep.id, ep.pay_date, e.name, ep.pay_type, ep.amount, ep.notes, ep.mode, ep.attachment_path
                FROM employee_payments ep
                LEFT JOIN employees e ON ep.emp_id = e.id
                WHERE e.company_id = ? AND ep.pay_type IN ('Salary', 'Advance', 'Bonus')
            ''', (comp_id,))
            emp_pays = c.fetchall()
            
            date_idx = self.cols_cache.index("expense_date") if "expense_date" in self.cols_cache else (self.cols_cache.index("date") if "date" in self.cols_cache else 1)
            title_idx = self.cols_cache.index("title") if "title" in self.cols_cache else 2
            cat_idx = self.cols_cache.index("category") if "category" in self.cols_cache else 3
            amt_idx = self.cols_cache.index("amount") if "amount" in self.cols_cache else 4
            notes_idx = self.cols_cache.index("notes") if "notes" in self.cols_cache else 5

            for ep in emp_pays:
                ep_id, ep_date, ep_name, ep_type, ep_amt, ep_notes, ep_mode, ep_attach = ep
                
                amt = float(ep_amt) if ep_amt else 0.0
                
                # --- THE FIX: Exclude Refunds (money coming back in) ---
                if amt < 0:
                    continue
                    
                faux_row = [None] * len(self.cols_cache)
                faux_row[0] = f"EMP_PAY_{ep_id}"
                faux_row[date_idx] = ep_date
                # --- THE FIX: Clean Title and Payment Mode ---
                faux_row[title_idx] = ep_name 
                faux_row[cat_idx] = "Payroll" 
                faux_row[amt_idx] = abs(amt)
                
                clean_mode = ep_mode or "—"
                if "(Available:" in clean_mode: clean_mode = clean_mode.split("(Available:")[0].strip()
                
                # --- THE FIX: Scrub Target Dues/Current from displaying in Expenses! ---
                clean_ep_notes = str(ep_notes or "").replace('[Target: Dues]', '').replace('[Target: Current]', '').replace('[Target: All]', '').strip()
                
                notes_dict = {
                    "note": clean_ep_notes,
                    "pay_method": clean_mode,
                    "status": "Paid",
                    "receipt": ep_attach or ""
                }
                # ---------------------------------------------
                faux_row[notes_idx] = json.dumps(notes_dict)
                rows.append(tuple(faux_row))
        except Exception as e: pass
        
        # --- THE FIX: UI Mirror Engine for Labour Payments ---
        try:
            # THE FIX: Force schema upgrade to prevent silent SQL crashes!
            try: c.execute("ALTER TABLE labour_ledger ADD COLUMN mode TEXT DEFAULT 'Cash'")
            except: pass
            try: c.execute("ALTER TABLE labour_ledger ADD COLUMN attachment_path TEXT DEFAULT ''")
            except: pass
            
            c.execute('''
                SELECT ll.id, ll.date, l.name, ll.type, ll.amount, ll.description, ll.mode, ll.attachment_path
                FROM labour_ledger ll
                LEFT JOIN labours l ON ll.labour_id = l.id
                WHERE l.company_id = ? AND ll.type IN ('Payment', 'Advance', 'Bonus')
            ''', (comp_id,))
            labour_pays = c.fetchall()

            for lp in labour_pays:
                lp_id, lp_date, lp_name, lp_type, lp_amt, lp_desc, lp_mode, lp_attach = lp
                amt = float(lp_amt) if lp_amt else 0.0
                
                # Exclude Refunds (in labour ledger, money coming IN is positive)
                if amt > 0:
                    continue
                    
                faux_row = [None] * len(self.cols_cache)
                faux_row[0] = f"LAB_PAY_{lp_id}"
                faux_row[date_idx] = lp_date
                
                # --- THE FIX: Clean Title and Payment Mode ---
                faux_row[title_idx] = lp_name 
                faux_row[cat_idx] = "Labor/Worker" 
                faux_row[amt_idx] = abs(amt)
                
                # Clean up description notes
                notes_str = lp_desc
                if lp_type == 'Payment' and " - " in lp_desc: notes_str = lp_desc.split(" - ", 1)[1].strip()
                elif lp_type == 'Advance': 
                    notes_str = lp_desc.replace("Advance - ", "").strip()
                    if "(" in notes_str and ")" in notes_str: notes_str = notes_str.split(" - ", 1)[-1].strip()
                elif lp_type == 'Bonus':
                    notes_str = lp_desc.replace("Bonus - ", "").strip()
                    if "(" in notes_str and ")" in notes_str: notes_str = notes_str.split(" - ", 1)[-1].strip()
                
                # --- THE FIX: Scrub Target Dues/Current from displaying in Expenses! ---
                notes_str = str(notes_str).replace('[Target: Dues]', '').replace('[Target: Current]', '').replace('[Target: All]', '').strip()
                
                clean_mode = lp_mode or "Cash"
                if "(Available:" in clean_mode: clean_mode = clean_mode.split("(Available:")[0].strip()
                
                notes_dict = {
                    "note": notes_str,
                    "pay_method": clean_mode,
                    "status": "Paid",
                    "receipt": lp_attach or ""
                }
                # ---------------------------------------------
                faux_row[notes_idx] = json.dumps(notes_dict)
                rows.append(tuple(faux_row))
        except Exception as e: pass
        
        # --- THE FIX: UI Mirror Engine for Vendor Payments ---
        try:
            # THE FIX: Force schema upgrade to prevent silent SQL crashes!
            try: c.execute("ALTER TABLE party_payments ADD COLUMN attachment_path TEXT DEFAULT ''")
            except: pass
            
            c.execute('''
                SELECT id, pay_date, party_name, mode, amount, notes, attachment_path, ref
                FROM party_payments 
                WHERE company_id = ? AND pay_type = 'make'
            ''', (comp_id,))
            vend_pays = c.fetchall()

            for vp in vend_pays:
                vp_id, vp_date, vp_name, vp_mode, vp_amt, vp_notes, vp_attach, vp_ref = vp
                amt = float(vp_amt) if vp_amt else 0.0
                
                # --- THE FIX: Exclude standard refunds, BUT allow System Adjustments (Debit Notes) to mirror! ---
                if amt > 0 and vp_mode != "System Adjustment": 
                    continue 

                # --- THE FIX: Explicitly block 'Write-Off' from appearing in Expenses! ---
                if vp_mode == "Write-Off":
                    continue
                # -------------------------------------------------------------------------
                    
                faux_row = [None] * len(self.cols_cache)
                faux_row[0] = f"VEND_PAY_{vp_id}"
                faux_row[date_idx] = vp_date
                
                # If it's a Debit Note, label it and make it a Negative Expense (Refund)
                if vp_mode == "System Adjustment":
                    faux_row[title_idx] = f"{vp_name} (Debit Note / Return)"
                    faux_row[amt_idx] = -abs(amt)
                else:
                    # --- THE FIX: Removed "(Payment)" string ---
                    faux_row[title_idx] = f"{vp_name}"
                    faux_row[amt_idx] = abs(amt)
                    
                # --- THE FIX: Renamed Category ---
                faux_row[cat_idx] = "Purchase Voucher"
                
                clean_mode = vp_mode or "Cash"
                
                # --- THE FIX: Regex string manipulation strips out the raw (amount) from the visual Notes! ---
                import re
                clean_ref = re.sub(r'\s*\([^)]*\)', '', str(vp_ref)).strip()
                clean_notes = str(vp_notes).strip()
                combined_note = (clean_ref + (" - " + clean_notes if clean_notes else ""))[:100]
                
                notes_dict = {
                    "note": combined_note,
                    "pay_method": clean_mode,
                    "status": "Paid",
                    "receipt": vp_attach or ""
                }
                faux_row[notes_idx] = json.dumps(notes_dict)
                rows.append(tuple(faux_row))
        except Exception as e: pass
        # -----------------------------------------------------
        
        conn.close()

        self.valid_rows_cache = []

        for r in rows:
            date_idx = self.cols_cache.index("expense_date") if "expense_date" in self.cols_cache else (self.cols_cache.index("date") if "date" in self.cols_cache else 1)
            dt = datetime.min
            for fmt in (self.date_fmt_code, "%Y-%m-%d", "%d-%m-%Y", "%d.%m.%Y", "%Y/%m/%d", "%m/%d/%Y"):
                try:
                    dt = datetime.strptime(r[date_idx], fmt)
                    break
                except:
                    pass
            self.valid_rows_cache.append((dt, r))
                
        # --- THE FIX: Convert IDs to strings so Python doesn't crash when sorting mixed types! ---
        self.valid_rows_cache.sort(key=lambda x: (x[0], str(x[1][0])), reverse=True)
        # -----------------------------------------------------------------------------------------

        search_term = self.search_var.get().strip().lower()
        selected_cat = self.filter_cat_var.get()
        start_date, end_date = self.get_date_bounds()
        show_pending = hasattr(self, 'pending_var') and self.pending_var.get()

        self.current_filtered_rows = []
        total_expense = 0.0

        for dt, r in self.valid_rows_cache:
            date_idx = self.cols_cache.index("expense_date") if "expense_date" in self.cols_cache else (self.cols_cache.index("date") if "date" in self.cols_cache else 1)
            title_idx = self.cols_cache.index("title") if "title" in self.cols_cache else 2
            cat_idx = self.cols_cache.index("category") if "category" in self.cols_cache else 3
            amt_idx = self.cols_cache.index("amount") if "amount" in self.cols_cache else 4
            notes_idx = self.cols_cache.index("notes") if "notes" in self.cols_cache else 5
            
            e_title = r[title_idx]
            e_cat = r[cat_idx]
            e_amt = r[amt_idx]
            e_notes = r[notes_idx]
            
            if dt != datetime.min:
                d_obj = dt.date()
                if start_date and d_obj < start_date: continue
                if end_date and d_obj > end_date: continue

            if selected_cat and selected_cat != "All Categories" and e_cat != selected_cat: continue

            if search_term:
                full_text = f"{e_title} {e_cat} {e_notes} {e_amt}".lower()
                if search_term not in full_text: continue

            if show_pending:
                is_pending = False
                exp_id = r[0]
                
                # --- THE FIX: Check the new native status column first! ---
                if not str(exp_id).startswith(("EMP_PAY_", "LAB_PAY_", "VEND_PAY_")):
                    s_idx = self.cols_cache.index("status") if "status" in self.cols_cache else 8
                    if len(r) > s_idx and r[s_idx] == "Pending (Unpaid)":
                        is_pending = True
                # Fallback for auto-synced Payroll records
                elif e_notes and e_notes.strip().startswith("{"):
                    try:
                        j = json.loads(e_notes)
                        if j.get("status") == "Pending (Unpaid)":
                            is_pending = True
                    except: pass
                    
                if not is_pending:
                    continue

            self.current_filtered_rows.append((dt, r))
            amt = float(e_amt) if e_amt else 0.0
            total_expense += amt

        self.total_pages = max(1, (len(self.current_filtered_rows) + self.items_per_page - 1) // self.items_per_page)
        if self.current_page > self.total_pages: self.current_page = max(1, self.total_pages)

        start_idx = (self.current_page - 1) * self.items_per_page
        page_items = self.current_filtered_rows[start_idx : start_idx + self.items_per_page]

        self.lbl_page.config(text=f"Page {self.current_page} of {self.total_pages}")
        self.btn_prev.config(state="normal" if self.current_page > 1 else "disabled", bg=self.CARD_BG if self.current_page > 1 else self.BG_COLOR)
        self.btn_next.config(state="normal" if self.current_page < self.total_pages else "disabled", bg=self.CARD_BG if self.current_page < self.total_pages else self.BG_COLOR)

        if hasattr(self, 'lbl_total') and self.lbl_total:
            self.lbl_total.config(text=f"{format_currency(total_expense, self.curr_fmt)}")

        current_month_group = ""
        row_counter = 0 
        
        for index, (dt, r) in enumerate(page_items):
            date_idx = self.cols_cache.index("expense_date") if "expense_date" in self.cols_cache else (self.cols_cache.index("date") if "date" in self.cols_cache else 1)
            title_idx = self.cols_cache.index("title") if "title" in self.cols_cache else 2
            cat_idx = self.cols_cache.index("category") if "category" in self.cols_cache else 3
            amt_idx = self.cols_cache.index("amount") if "amount" in self.cols_cache else 4
            notes_idx = self.cols_cache.index("notes") if "notes" in self.cols_cache else 5
            
            exp_id = r[0]
            e_date = r[date_idx]
            e_title = r[title_idx]
            e_cat = r[cat_idx]
            e_amt = r[amt_idx]
            e_notes = r[notes_idx]
            
            amt = float(e_amt) if e_amt else 0.0
            
            m_group = dt.strftime("%B %Y") if dt != datetime.min else "Unknown Date"
            if m_group != current_month_group:
                current_month_group = m_group
                self.tree.insert("", "end", iid=f"month_{m_group}_{index}", values=("", f"📅 {m_group}", "", "", "", "", "", "", ""), tags=("month_header",))
                row_counter += 1
                
            display_note = e_notes if e_notes else ""
            pay_method = "—"
            has_receipt = False
            status = "Paid"
            
            # Native extraction directly from columns if it's a real expense record
            if not str(exp_id).startswith(("EMP_PAY_", "LAB_PAY_", "VEND_PAY_")):
                n_idx = self.cols_cache.index("notes") if "notes" in self.cols_cache else 6
                p_idx = self.cols_cache.index("pay_method") if "pay_method" in self.cols_cache else 7
                s_idx = self.cols_cache.index("status") if "status" in self.cols_cache else 8
                r_idx = self.cols_cache.index("receipt_path") if "receipt_path" in self.cols_cache else 9
                
                display_note = r[n_idx] if len(r) > n_idx and r[n_idx] else ""
                pay_method = r[p_idx] if len(r) > p_idx and r[p_idx] else "Cash"
                status = r[s_idx] if len(r) > s_idx and r[s_idx] else "Paid"
                if len(r) > r_idx and r[r_idx]: has_receipt = True
            elif e_notes and e_notes.strip().startswith("{"):
                # Fallback for Auto-Synced JSON Wrappers
                try:
                    j = json.loads(e_notes)
                    display_note = j.get("note", "")
                    pay_method = j.get("pay_method", "—")
                    status = j.get("status", "Paid")
                    if j.get("receipt"): has_receipt = True
                except: pass
                
            formatted_date = smart_date_formatter(e_date, self.date_fmt_code)
            receipt_icon = "📄 View" if has_receipt else "—"
            
            if status == "Pending (Unpaid)":
                pay_method = f"⏳ {pay_method}"
            
            is_sel = str(exp_id) in self.selected_items
            col1 = ("☑" if is_sel else "☐") if self.is_bulk_mode else (start_idx + index + 1)
            
            bg_tag = "evenrow" if row_counter % 2 == 0 else "oddrow"
            
            if is_sel and self.is_bulk_mode:
                tag_tuple = ("selected_row",)
            elif status == "Pending (Unpaid)":
                tag_tuple = (bg_tag, "pending_row")
            else:
                tag_tuple = (bg_tag,)

            self.tree.insert("", "end", iid=str(exp_id), values=(col1, formatted_date, e_title, f"{e_cat}", format_currency(amt, self.curr_fmt), pay_method, display_note, receipt_icon, "⚙️ Action"), tags=tag_tuple)
            row_counter += 1

        empty_vals = ("", "", "", "", "", "", "", "", "")
        while row_counter < self.items_per_page + 2:
            bg_tag = "evenrow" if row_counter % 2 == 0 else "oddrow"
            self.tree.insert("", "end", iid=f"empty_pad_{row_counter}", values=empty_vals, tags=(bg_tag, "empty_row"))
            row_counter += 1