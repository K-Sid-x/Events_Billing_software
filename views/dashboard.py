import tkinter as tk
from tkinter import ttk, messagebox
import json
import os
import sys
from datetime import date, datetime
import traceback
import calendar

# --- THE FIX: Bulletproof Executable Pathing ---
if getattr(sys, 'frozen', False):
    parent_dir = os.path.dirname(sys.executable)
else:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)

if parent_dir not in sys.path:
    sys.path.append(parent_dir)
# -----------------------------------------------

import database
from views.invoice_parts.helpers import format_currency, fetch_global_settings, enable_copy_paste
from views.invoice_parts.calendar_widget import NativeCalendar
from views.home_parts.ui_components import get_theme # --- THE FIX: Imported Dynamic Theme Engine! ---

def add_hover(widget, default_bg, hover_bg):
    widget.bind("<Enter>", lambda e: widget.config(bg=hover_bg))
    widget.bind("<Leave>", lambda e: widget.config(bg=default_bg))

class DashboardView(tk.Frame):
    def __init__(self, parent):
        self.t = get_theme() # Pre-load theme colors
        super().__init__(parent, bg=self.t["bg"])

        try:
            self.init_dashboard(parent)
        except Exception as e:
            err_msg = f"Dashboard Initialisation Error:\n\n{str(e)}\n\n{traceback.format_exc()}"
            tk.Label(self, text=err_msg, font=("Arial", 10), fg=self.t.get("error", "#ef4444"), bg=self.t["bg"], justify="left").pack(fill="both", expand=True, padx=20, pady=20)

    def init_dashboard(self, parent):
        try:
            self.app = self.winfo_toplevel()
            comp_id = getattr(self.app, "active_company_id", 1)
            self.curr_fmt, self.date_fmt_code = fetch_global_settings(comp_id)
        except:
            self.curr_fmt, self.date_fmt_code = "Indian Rupees (₹)", "%Y-%m-%d"
            comp_id = 1
        
        # --- THE FIX: Dynamic Theme Engine Integration ---
        self.t = get_theme()
        self.BG = self.t["bg"]
        self.CARD = self.t["card"]
        self.BORDER = self.t["border"]
        self.FG = self.t["text"]
        self.SEC_FG = self.t["sec"]
        self.BLUE = self.t["accent_blue"]
        self.RED = self.t["error"]
        self.GREEN = self.t["accent_green"]
        self.YELLOW = "#f59e0b" 
        
        # Determine muted colors based on whether it is dark mode
        if self.BG == "#0f172a":
            self.MUTED_BLUE = "#1e3a8a"
            self.MUTED_RED = "#7f1d1d"
        else:
            self.MUTED_BLUE = "#90CAF9"
            self.MUTED_RED = "#EF9A9A"
        # -------------------------------------------------

        self.config(bg=self.BG)

        try:
            parent.config(bg=self.BG)
        except: pass

        now = datetime.now()
        self.month_var = tk.StringVar(value=now.strftime("%B"))
        self.year_var = tk.StringVar(value=str(now.year))

        self.month_var.trace_add("write", lambda *args: self.refresh_dashboard())
        self.year_var.trace_add("write", lambda *args: self.refresh_dashboard())

        style = ttk.Style(self)
        style.theme_use("default")
        
        # --- THE FIX: Custom thick, flat scrollbars matching Stock & P&L ---
        style.configure("Dark.Vertical.TScrollbar", background=self.SEC_FG, troughcolor=self.BG, bordercolor=self.BG, arrowcolor=self.FG, relief="flat")
        style.map("Dark.Vertical.TScrollbar", background=[("active", self.BLUE)])
        # -------------------------------------------------------------------

        self.app.option_add("*TCombobox*Listbox.background", self.CARD)
        self.app.option_add("*TCombobox*Listbox.foreground", self.FG)
        self.app.option_add("*TCombobox*Listbox.selectBackground", self.BLUE)
        self.app.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")
        
        style.configure("Dark.TCombobox", fieldbackground=self.BG, background=self.CARD, foreground=self.FG, arrowcolor=self.FG, bordercolor=self.BORDER, lightcolor=self.BORDER, darkcolor=self.BORDER)
        style.map("Dark.TCombobox", fieldbackground=[("readonly", self.BG)], selectbackground=[("readonly", self.BG)], selectforeground=[("readonly", self.FG)])

        self.canvas = tk.Canvas(self, bg=self.BG, highlightthickness=0)
        self.scroll_y = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview, style="Dark.Vertical.TScrollbar")
        
        # --- THE FIX: Tell the canvas to report its height to the scrollbar so the thumb shrinks! ---
        self.canvas.configure(yscrollcommand=self.scroll_y.set)
        # --------------------------------------------------------------------------------------------
        
        self.scrollable_frame = tk.Frame(self.canvas, bg=self.BG)

        self.scrollable_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas_frame_id = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfig(self.canvas_frame_id, width=e.width))

        # --- THE FIX: Pack the scrollbar FIRST so it stakes its claim on the right edge! ---
        self.scroll_y.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        # -----------------------------------------------------------------------------------

        # --- THE FIX: BULLETPROOF SCROLL BINDING ---
        def _on_mousewheel(event):
            try:
                # Check if mouse is actually hovering over the dashboard before scrolling
                widget = self.winfo_containing(event.x_root, event.y_root)
                if not widget or not str(widget).startswith(str(self)): return
                if isinstance(widget, (tk.Listbox, ttk.Combobox)): return
                if self.canvas.winfo_exists():
                    self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")
            except Exception: pass

        def _bind_mouse(e=None):
            self.canvas.bind_all("<MouseWheel>", _on_mousewheel)
            
        def _unbind_mouse(e=None):
            self.canvas.unbind_all("<MouseWheel>")

        self.bind("<Enter>", _bind_mouse)
        self.bind("<Leave>", _unbind_mouse)
        self.bind("<Destroy>", lambda e: _unbind_mouse() if e.widget == self else None)
        
        _bind_mouse() # Bind immediately on load
        # ---------------------------------------------

        self.refresh_dashboard()

    def refresh_dashboard(self):
        self.fetch_live_data()
        self.build_ui()

    def fetch_live_data(self):
        self.tm_revenue = 0.0
        self.tm_expense = 0.0
        self.tm_payroll = 0.0
        self.tm_outstanding = 0.0
        
        self.lm_revenue = 0.0
        self.lm_expense = 0.0

        self.total_customers = 0
        self.active_employees = 0
        self.tm_invoices_count = 0

        self.alerts_list = []
        self.activity_feed = []

        try:
            target_year = int(self.year_var.get())
        except:
            target_year = datetime.now().year

        month_str = self.month_var.get()
        self.is_all_months = (month_str == "All Months")

        if not self.is_all_months:
            try:
                target_month = datetime.strptime(month_str, "%B").month
                if target_month == 1:
                    prev_month = 12
                    prev_year = target_year - 1
                else:
                    prev_month = target_month - 1
                    prev_year = target_year
            except:
                target_month = datetime.now().month
                prev_month = target_month
                prev_year = target_year
        else:
            target_month = None
            prev_month = None
            prev_year = target_year - 1

        # --- THE FIX: Universal Date Parser (Stops data from vanishing) ---
        def safe_date_parse(date_str):
            if not date_str or str(date_str).strip() in ("None", ""): return datetime.min
            raw = str(date_str).strip()[:10]
            for f in ("%Y-%m-%d", "%d-%m-%Y", "%d.%m.%Y", "%d/%m/%Y", "%m/%d/%Y", self.date_fmt_code):
                try: return datetime.strptime(raw, f)
                except: pass
            return datetime.min
        # ------------------------------------------------------------------

        try:
            raw_data = database.get_balance_sheet_raw_data()
            
            for inv in raw_data.get("invoices", []):
                inv_date, inv_num, cust_name, total, bal_due, status = inv
                
                try:
                    bal = float(bal_due)
                    if bal > 0: self.alerts_list.append({"cust": cust_name, "inv": inv_num, "amt": bal})
                except: pass

                dt = safe_date_parse(inv_date)
                if dt != datetime.min:
                    self.activity_feed.append({"dt": dt, "text": f"Generated Invoice {inv_num} for {cust_name} ({format_currency(float(total), self.curr_fmt)})", "color": self.BLUE})
                    
                    if self.is_all_months:
                        if dt.year == target_year:
                            self.tm_invoices_count += 1
                            self.tm_revenue += float(total)
                            self.tm_outstanding += float(bal_due)
                        elif dt.year == prev_year:
                            self.lm_revenue += float(total)
                    else:
                        if dt.month == target_month and dt.year == target_year:
                            self.tm_invoices_count += 1
                            self.tm_revenue += float(total)
                            self.tm_outstanding += float(bal_due)
                        elif dt.month == prev_month and dt.year == prev_year:
                            self.lm_revenue += float(total)

            for exp in raw_data.get("expenses", []):
                exp_date, title, cat, amt, notes = exp
                dt = safe_date_parse(exp_date)
                if dt != datetime.min:
                    self.activity_feed.append({"dt": dt, "text": f"Logged Expense: {title} ({format_currency(float(amt), self.curr_fmt)})", "color": self.RED})
                    
                    if self.is_all_months:
                        if dt.year == target_year:
                            self.tm_expense += float(amt)
                        elif dt.year == prev_year:
                            self.lm_expense += float(amt)
                    else:
                        if dt.month == target_month and dt.year == target_year:
                            self.tm_expense += float(amt)
                        elif dt.month == prev_month and dt.year == prev_year:
                            self.lm_expense += float(amt)

            for sal in raw_data.get("salaries", []):
                # --- THE FIX: Extract the Entity Tag (Employee, Labour, Vendor, Client) ---
                pay_date, pay_type, amt, notes, emp_name = sal[0], sal[1], sal[2], sal[3], sal[4]
                entity_tag = sal[6] if len(sal) > 6 else "Employee"
                # --------------------------------------------------------------------------
                
                dt = safe_date_parse(pay_date)
                if dt != datetime.min:
                    # --- THE FIX: Smart Activity Feed Text ---
                    if entity_tag == "Employee": 
                        feed_text = f"Employee Payment: {pay_type} to {emp_name}"
                    elif entity_tag == "Labour": 
                        feed_text = f"Labour Payment: {pay_type} to {emp_name}"
                    elif entity_tag == "Client": 
                        if "refund" in str(notes).lower():
                            feed_text = f"Client Refund: {emp_name}"
                        else:
                            feed_text = f"Client Advance: {emp_name}"
                    else: 
                        if "refund" in str(notes).lower():
                            feed_text = f"Vendor Refund: {emp_name}"
                        elif "advance" in str(notes).lower():
                            feed_text = f"Vendor Advance: {emp_name}"
                        else:
                            feed_text = f"Vendor Payment: {emp_name}"
                            
                    self.activity_feed.append({"dt": dt, "text": f"{feed_text} ({format_currency(abs(float(amt)), self.curr_fmt)})", "color": self.YELLOW})
                    # -----------------------------------------
                    
                    if self.is_all_months:
                        if dt.year == target_year:
                            if entity_tag in ("Employee", "Labour"): self.tm_payroll += abs(float(amt))
                            self.tm_expense += float(amt) # amt handles positives/negatives natively from DB
                        elif dt.year == prev_year:
                            self.lm_expense += float(amt)
                    else:
                        if dt.month == target_month and dt.year == target_year:
                            if entity_tag in ("Employee", "Labour"): self.tm_payroll += abs(float(amt))
                            self.tm_expense += float(amt)
                        elif dt.month == prev_month and dt.year == prev_year:
                            self.lm_expense += float(amt)

            self.tm_profit = self.tm_revenue - self.tm_expense

            self.alerts_list.sort(key=lambda x: x["amt"], reverse=True)
            self.alerts_list = self.alerts_list[:5] 

            # --- THE FIX: Reverse the feed before sorting so newest DB rows jump to the top! ---
            self.activity_feed.reverse()
            self.activity_feed.sort(key=lambda x: x["dt"], reverse=True)
            self.activity_feed = self.activity_feed[:8] 
            # ---------------------------------------------------------------------------------- 

            self.total_customers = len(database.get_all_customers())
            try:
                stats = database.get_employee_dashboard_stats()
                if stats and len(stats) >= 4:
                    self.active_employees = stats[3]
            except: pass

        except Exception as e:
            print(f"Data Fetch Warning: {e}")

    def navigate_to(self, view_name):
        if hasattr(self.app, 'sidebar') and hasattr(self.app.sidebar, 'on_click'):
            self.app.sidebar.on_click(view_name)
        elif hasattr(self.app, 'switch_view'):
            self.app.switch_view(view_name)

    def trigger_invoice_engine(self):
        messagebox.showinfo("Next Major Module", "The Invoice Creation Engine is our next massive target!\n\nIt will feature:\n- Auto-fetching Inventory items\n- Smart GST Calculations\n- PDF Generation & Printing\n- Real-time Balance tracking", parent=self)

    def quick_add_expense(self):
        pop = tk.Toplevel(self)
        pop.title("Quick Add Expense")
        pop.geometry("450x480")
        pop.configure(bg=self.BG)
        pop.grab_set()

        past_titles = database.get_distinct_expense_titles()

        title_var = tk.StringVar()
        category_var = tk.StringVar(value="General")
        amount_var = tk.StringVar(value="0")
        date_var = tk.StringVar(value=date.today().strftime(self.date_fmt_code))
        notes_var = tk.StringVar()

        tk.Label(pop, text="Quick Add Expense", font=("Arial", 16, "bold"), bg=self.BG, fg=self.FG).pack(anchor="w", padx=20, pady=(20, 15))

        f = tk.Frame(pop, bg=self.BG)
        f.pack(fill="both", expand=True, padx=20)

        def focus_next(event): event.widget.tk_focusNext().focus(); return "break"

        tk.Label(f, text="Expense Title *", font=("Arial", 9, "bold"), bg=self.BG, fg=self.SEC_FG).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 2))
        
        t_ent = tk.Entry(f, textvariable=title_var, font=("Arial", 11), width=45, bg=self.CARD, fg=self.FG, insertbackground=self.FG, highlightbackground=self.BORDER, highlightthickness=1)
        t_ent.grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 15), ipady=5)
        enable_copy_paste(t_ent)

        suggestion_box = tk.Listbox(pop, font=("Arial", 11), bg=self.CARD, fg=self.FG, selectbackground=self.BLUE, selectforeground="#ffffff", relief="solid", bd=1, highlightthickness=0)
        
        ignore_trace = [False]
        current_selection = [-1]

        def update_suggestions(*args):
            if ignore_trace[0]: return
            typed = title_var.get().lower()
            suggestion_box.delete(0, tk.END)
            current_selection[0] = -1
            if not typed:
                suggestion_box.place_forget()
                return
            matches = [t for t in past_titles if typed in t.lower()]
            if matches:
                suggestion_box.config(height=min(5, len(matches)))
                for m in matches: suggestion_box.insert(tk.END, m)
                x = t_ent.winfo_rootx() - pop.winfo_rootx()
                y = t_ent.winfo_rooty() - pop.winfo_rooty() + t_ent.winfo_height()
                suggestion_box.place(x=x, y=y, width=t_ent.winfo_width())
                suggestion_box.lift()
            else:
                suggestion_box.place_forget()

        title_var.trace_add("write", update_suggestions)

        def set_active_item(idx):
            suggestion_box.selection_clear(0, tk.END)
            if 0 <= idx < suggestion_box.size():
                suggestion_box.selection_set(idx)
                suggestion_box.activate(idx)
                suggestion_box.see(idx)

        def on_entry_keydown(event):
            if event.keysym == "Down" and suggestion_box.winfo_ismapped():
                current_selection[0] = min(current_selection[0] + 1, suggestion_box.size() - 1)
                set_active_item(current_selection[0])
                return "break"
            elif event.keysym == "Up" and suggestion_box.winfo_ismapped():
                current_selection[0] = max(current_selection[0] - 1, -1)
                set_active_item(current_selection[0])
                return "break"
            elif event.keysym == "Return":
                if suggestion_box.winfo_ismapped() and current_selection[0] >= 0:
                    ignore_trace[0] = True
                    title_var.set(suggestion_box.get(current_selection[0]))
                    ignore_trace[0] = False
                    suggestion_box.place_forget()
                    cat_combo.focus_set()
                    return "break"
                else:
                    focus_next(event)
                    return "break"

        t_ent.bind("<KeyPress>", on_entry_keydown)

        def on_listbox_click(event):
            idx = suggestion_box.nearest(event.y)
            if idx >= 0:
                ignore_trace[0] = True
                title_var.set(suggestion_box.get(idx))
                ignore_trace[0] = False
                suggestion_box.place_forget()
                cat_combo.focus_set()

        suggestion_box.bind("<ButtonRelease-1>", on_listbox_click)

        def hide_box(event):
            if event.widget != t_ent and event.widget != suggestion_box:
                suggestion_box.place_forget()
                
        pop.bind("<Button-1>", hide_box, add="+")
        
        tk.Label(f, text="Category", font=("Arial", 9, "bold"), bg=self.BG, fg=self.SEC_FG).grid(row=2, column=0, sticky="w", pady=(0, 2))
        categories = ["General", "Purchase", "Transport", "Utilities", "Rent", "Supplies", "Maintenance", "Meals & Ent.", "Marketing"]
        cat_combo = ttk.Combobox(f, textvariable=category_var, values=categories, font=("Arial", 10), state="readonly", width=18, style="Dark.TCombobox")
        cat_combo.grid(row=3, column=0, sticky="w", pady=(0, 15), padx=(0, 15), ipady=4)
        cat_combo.bind("<Return>", focus_next)

        tk.Label(f, text="Amount *", font=("Arial", 9, "bold"), bg=self.BG, fg=self.SEC_FG).grid(row=2, column=1, sticky="w", pady=(0, 2))
        a_ent = tk.Entry(f, textvariable=amount_var, font=("Arial", 11), width=18, bg=self.CARD, fg=self.FG, insertbackground=self.FG, highlightbackground=self.BORDER, highlightthickness=1)
        a_ent.grid(row=3, column=1, sticky="w", pady=(0, 15), ipady=5)
        enable_copy_paste(a_ent); a_ent.bind("<Return>", focus_next)

        tk.Label(f, text="Date", font=("Arial", 9, "bold"), bg=self.BG, fg=self.SEC_FG).grid(row=4, column=0, columnspan=2, sticky="w", pady=(0, 2))
        d_f = tk.Frame(f, bg=self.BG)
        d_f.grid(row=5, column=0, columnspan=2, sticky="w", pady=(0, 15))
        d_ent = tk.Entry(d_f, textvariable=date_var, font=("Arial", 11), width=20, bg=self.CARD, fg=self.FG, insertbackground=self.FG, highlightbackground=self.BORDER, highlightthickness=1)
        d_ent.pack(side="left", ipady=5); enable_copy_paste(d_ent); d_ent.bind("<Return>", focus_next)
        tk.Button(d_f, text="📅", bg=self.CARD, fg=self.FG, relief="flat", cursor="hand2", command=lambda: NativeCalendar(pop, date_var)).pack(side="left", padx=5)

        tk.Label(f, text="Notes", font=("Arial", 9, "bold"), bg=self.BG, fg=self.SEC_FG).grid(row=6, column=0, columnspan=2, sticky="w", pady=(0, 2))
        n_ent = tk.Entry(f, textvariable=notes_var, font=("Arial", 11), width=45, bg=self.CARD, fg=self.FG, insertbackground=self.FG, highlightbackground=self.BORDER, highlightthickness=1)
        n_ent.grid(row=7, column=0, columnspan=2, sticky="w", pady=(0, 25), ipady=5)
        enable_copy_paste(n_ent); n_ent.bind("<Return>", focus_next)

        def save_expense():
            title = title_var.get().strip()
            try: amt = float(amount_var.get())
            except: messagebox.showerror("Error", "Amount must be a valid number.", parent=pop); return
            if not title: messagebox.showerror("Error", "Title is required.", parent=pop); return
            if amt <= 0: messagebox.showerror("Error", "Amount must be greater than zero.", parent=pop); return

            database.add_general_expense(date_var.get(), title, category_var.get(), amt, notes_var.get().strip())
            
            self.refresh_dashboard()
            pop.destroy()
            messagebox.showinfo("Success", "Expense added and Dashboard updated!", parent=self.winfo_toplevel())

        btn_save = tk.Button(pop, text="Save Expense", font=("Arial", 11, "bold"), bg=self.BLUE, fg="#ffffff", relief="flat", cursor="hand2", padx=30, pady=8, command=save_expense)
        btn_save.pack(side="right", padx=20, pady=(0, 20))

    def build_ui(self):
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        header_f = tk.Frame(self.scrollable_frame, bg=self.BG)
        header_f.pack(fill="x", padx=30, pady=(30, 20))
        
        title_f = tk.Frame(header_f, bg=self.BG)
        title_f.pack(side="left")
        tk.Label(title_f, text="Overview", font=("Arial", 10), bg=self.BG, fg=self.SEC_FG).pack(anchor="w")
        tk.Label(title_f, text="Financial Dashboard", font=("Arial", 26, "bold"), bg=self.BG, fg=self.FG).pack(anchor="w")
        tk.Label(title_f, text="Live financial overview. Track revenue, monitor expenses, and manage operations.", font=("Arial", 11), bg=self.BG, fg=self.SEC_FG).pack(anchor="w", pady=(5,0))

        btn_f = tk.Frame(header_f, bg=self.BG)
        btn_f.pack(side="right", anchor="s")

        time_f = tk.Frame(btn_f, bg=self.BG)
        time_f.pack(side="left", padx=(0, 15))
        
        tk.Label(time_f, text="📅 Year:", font=("Arial", 9, "bold"), bg=self.BG, fg=self.SEC_FG).pack(side="left", padx=(0, 5))
        years = [str(y) for y in range(datetime.now().year - 5, datetime.now().year + 5)]
        year_cb = ttk.Combobox(time_f, textvariable=self.year_var, values=years, state="readonly", width=8, style="Dark.TCombobox", cursor="hand2")
        year_cb.pack(side="left", padx=(0, 10))

        tk.Label(time_f, text="Month:", font=("Arial", 9, "bold"), bg=self.BG, fg=self.SEC_FG).pack(side="left", padx=(0, 5))
        months = ["All Months", "January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
        month_cb = ttk.Combobox(time_f, textvariable=self.month_var, values=months, state="readonly", width=12, style="Dark.TCombobox", cursor="hand2")
        month_cb.pack(side="left")

        btn_exp = tk.Button(btn_f, text="⊕ Add Expense", font=("Arial", 10, "bold"), bg=self.CARD, fg=self.FG, relief="flat", cursor="hand2", padx=15, pady=8, highlightbackground=self.BORDER, highlightthickness=1)
        btn_exp.config(command=self.quick_add_expense)
        btn_exp.pack(side="left", padx=5)
        add_hover(btn_exp, self.CARD, self.BORDER)

        btn_inv = tk.Button(btn_f, text="⊕ Create Invoice", font=("Arial", 10, "bold"), bg=self.BLUE, fg="#ffffff", relief="flat", cursor="hand2", padx=15, pady=8)
        btn_inv.config(command=self.trigger_invoice_engine)
        btn_inv.pack(side="left", padx=5)
        add_hover(btn_inv, self.BLUE, "#2563eb")

        lbl_suffix = f"({self.year_var.get()})" if self.is_all_months else f"({self.month_var.get()[:3].upper()})"

        row1 = tk.Frame(self.scrollable_frame, bg=self.BG)
        row1.pack(fill="x", padx=20, pady=(10, 5))
        
        self.create_stat_card(row1, f"REVENUE {lbl_suffix}", format_currency(self.tm_revenue, self.curr_fmt), self.BLUE, "Invoices").pack(side="left", expand=True, fill="both", padx=10)
        self.create_stat_card(row1, f"EXPENSE {lbl_suffix}", format_currency(self.tm_expense, self.curr_fmt), self.RED, "Employees/Expense").pack(side="left", expand=True, fill="both", padx=10)
        
        profit_color = self.GREEN if self.tm_profit >= 0 else self.RED
        profit_label = f"PROFIT {lbl_suffix}" if self.tm_profit >= 0 else f"LOSS {lbl_suffix}"
        self.create_stat_card(row1, profit_label, format_currency(abs(self.tm_profit), self.curr_fmt), profit_color, "Profit & Loss").pack(side="left", expand=True, fill="both", padx=10)
        
        self.create_stat_card(row1, f"OUTSTANDING A/R {lbl_suffix}", format_currency(self.tm_outstanding, self.curr_fmt), self.YELLOW, "Customers").pack(side="left", expand=True, fill="both", padx=10)

        row2 = tk.Frame(self.scrollable_frame, bg=self.BG)
        row2.pack(fill="x", padx=20, pady=(10, 10))

        self.create_stat_card(row2, "TOTAL CUSTOMERS", str(self.total_customers), self.FG, "Customers").pack(side="left", expand=True, fill="both", padx=10)
        self.create_stat_card(row2, f"NEW INVOICES {lbl_suffix}", str(self.tm_invoices_count), self.FG, "Invoices").pack(side="left", expand=True, fill="both", padx=10)
        self.create_stat_card(row2, "ACTIVE EMPLOYEES", str(self.active_employees), self.FG, "Employees/Expense").pack(side="left", expand=True, fill="both", padx=10)
        self.create_stat_card(row2, f"PAYROLL DISBURSED {lbl_suffix}", format_currency(self.tm_payroll, self.curr_fmt), self.FG, "Employees/Expense").pack(side="left", expand=True, fill="both", padx=10)

        row3 = tk.Frame(self.scrollable_frame, bg=self.BG)
        row3.pack(fill="both", expand=True, padx=20, pady=10)
        
        graph1 = tk.Frame(row3, bg=self.CARD, highlightbackground=self.BORDER, highlightthickness=1)
        graph1.pack(side="left", expand=True, fill="both", padx=10)
        self.lbl_growth_title = tk.Label(graph1, text="", font=("Arial", 14, "bold"), bg=self.CARD, fg=self.FG)
        self.lbl_growth_title.pack(anchor="nw", pady=20, padx=20)
        self.draw_mom_growth_chart(graph1)

        graph2 = tk.Frame(row3, bg=self.CARD, highlightbackground=self.BORDER, highlightthickness=1)
        graph2.pack(side="left", expand=True, fill="both", padx=10)
        tk.Label(graph2, text="Expense Distribution", font=("Arial", 14, "bold"), bg=self.CARD, fg=self.FG).pack(anchor="nw", pady=20, padx=20)
        self.draw_donut_chart(graph2)

        row4 = tk.Frame(self.scrollable_frame, bg=self.BG)
        row4.pack(fill="both", expand=True, padx=20, pady=(10, 30))

        alert_f = tk.Frame(row4, bg=self.CARD, highlightbackground=self.BORDER, highlightthickness=1)
        alert_f.pack(side="left", expand=True, fill="both", padx=10)
        tk.Label(alert_f, text="⚠️ Requires Attention (Top Unpaid)", font=("Arial", 14, "bold"), bg=self.CARD, fg=self.RED).pack(anchor="nw", pady=20, padx=20)
        
        if not self.alerts_list:
            tk.Label(alert_f, text="All invoices are fully paid! Great job.", font=("Arial", 11), bg=self.CARD, fg=self.GREEN).pack(pady=20)
        else:
            for al in self.alerts_list:
                item_f = tk.Frame(alert_f, bg=self.BG, pady=10, padx=15, highlightbackground=self.BORDER, highlightthickness=1)
                item_f.pack(fill="x", padx=20, pady=5)
                tk.Label(item_f, text=al["cust"], font=("Arial", 11, "bold"), bg=self.BG, fg=self.FG).pack(side="left")
                tk.Label(item_f, text=f"(Inv: {al['inv']})", font=("Arial", 9), bg=self.BG, fg=self.SEC_FG).pack(side="left", padx=10)
                tk.Label(item_f, text=format_currency(al["amt"], self.curr_fmt), font=("Arial", 11, "bold"), bg=self.BG, fg=self.RED).pack(side="right")

        feed_f = tk.Frame(row4, bg=self.CARD, highlightbackground=self.BORDER, highlightthickness=1)
        feed_f.pack(side="left", expand=True, fill="both", padx=10)
        tk.Label(feed_f, text="⚡ Live Activity Feed", font=("Arial", 14, "bold"), bg=self.CARD, fg=self.BLUE).pack(anchor="nw", pady=20, padx=20)

        if not self.activity_feed:
            tk.Label(feed_f, text="No recent activity logged.", font=("Arial", 11), bg=self.CARD, fg=self.SEC_FG).pack(pady=20)
        else:
            for act in self.activity_feed:
                act_f = tk.Frame(feed_f, bg=self.CARD)
                act_f.pack(fill="x", padx=20, pady=6)
                
                dot = tk.Label(act_f, text="●", font=("Arial", 14), bg=self.CARD, fg=act["color"])
                dot.pack(side="left", padx=(0, 10))
                
                date_str = act["dt"].strftime(self.date_fmt_code)
                tk.Label(act_f, text=date_str, font=("Arial", 9, "bold"), bg=self.CARD, fg=self.SEC_FG, width=12, anchor="w").pack(side="left")
                tk.Label(act_f, text=act["text"], font=("Arial", 10), bg=self.CARD, fg=self.FG).pack(side="left", fill="x", expand=True)

        tk.Frame(self.scrollable_frame, bg=self.BG, height=40).pack(fill="x")

    def create_stat_card(self, parent, title, value, value_color, target_view):
        card = tk.Frame(parent, bg=self.CARD, highlightbackground=self.BORDER, highlightthickness=1, padx=25, pady=25, cursor="hand2")
        lbl_title = tk.Label(card, text=title, font=("Arial", 9, "bold"), bg=self.CARD, fg=self.SEC_FG, anchor="w", cursor="hand2")
        lbl_title.pack(fill="x")
        lbl_val = tk.Label(card, text=value, font=("Arial", 20, "bold"), bg=self.CARD, fg=value_color, anchor="w", cursor="hand2")
        lbl_val.pack(fill="x", pady=(8, 0))
        
        for w in (card, lbl_title, lbl_val):
            w.bind("<Button-1>", lambda e, mod=target_view: self.navigate_to(mod))
            w.bind("<Enter>", lambda e: card.config(bg=self.BORDER))
            w.bind("<Leave>", lambda e: card.config(bg=self.CARD))
            
        return card

    def draw_mom_growth_chart(self, parent):
        canvas = tk.Canvas(parent, bg=self.CARD, highlightthickness=0, height=350)
        canvas.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        
        title_text = "YoY Growth (Last Year vs This Year)" if self.is_all_months else "MoM Growth (Last Month vs This Month)"
        self.lbl_growth_title.config(text=title_text)

        lbl_tm = "TY " if self.is_all_months else "TM "
        lbl_lm = "LY " if self.is_all_months else "LM "

        def render_chart(event=None):
            canvas.delete("all")
            w = canvas.winfo_width()
            h = canvas.winfo_height()
            
            if w <= 10 or h <= 10: return 
            
            max_val = max(self.tm_revenue, self.tm_expense, self.lm_revenue, self.lm_expense)
            if max_val == 0: max_val = 1 
            
            baseline = h - 45 
            
            for i in range(1, 5):
                y = baseline - (baseline * (i / 5.0))
                canvas.create_line(0, y, w, y, fill=self.BORDER, dash=(2, 4))
            
            canvas.create_line(0, baseline, w, baseline, fill=self.SEC_FG)

            lm_rev_h = (self.lm_revenue / max_val) * (baseline * 0.8)
            lm_exp_h = (self.lm_expense / max_val) * (baseline * 0.8)
            tm_rev_h = (self.tm_revenue / max_val) * (baseline * 0.8)
            tm_exp_h = (self.tm_expense / max_val) * (baseline * 0.8)
            
            bar_width = w * 0.12
            group_gap = w * 0.1
            inner_gap = w * 0.02
            
            total_width = (bar_width * 4) + (inner_gap * 2) + group_gap
            start_x = (w - total_width) / 2
            
            def draw_flat_bar(x, height_val, color, title, val_num):
                if height_val > 5:
                    canvas.create_rectangle(x, baseline, x + bar_width, baseline - height_val, fill=color, outline="")
                else:
                    canvas.create_rectangle(x, baseline - 2, x + bar_width, baseline, fill=self.SEC_FG, outline="")
                
                val_str = format_currency(val_num, self.curr_fmt).split(' ')[-1]
                canvas.create_text(x + (bar_width/2), baseline - height_val - 12, text=val_str, fill=self.FG, font=("Arial", 10, "bold"))
                canvas.create_text(x + (bar_width/2), baseline + 18, text=title, fill=self.SEC_FG, font=("Arial", 9, "bold"))

            draw_flat_bar(start_x, lm_rev_h, self.MUTED_BLUE, f"{lbl_lm}Rev", self.lm_revenue)
            draw_flat_bar(start_x + bar_width + inner_gap, lm_exp_h, self.MUTED_RED, f"{lbl_lm}Exp", self.lm_expense)
            
            tm_x = start_x + (bar_width * 2) + inner_gap + group_gap
            draw_flat_bar(tm_x, tm_rev_h, self.BLUE, f"{lbl_tm}Rev", self.tm_revenue)
            draw_flat_bar(tm_x + bar_width + inner_gap, tm_exp_h, self.RED, f"{lbl_tm}Exp", self.tm_expense)

            if self.lm_revenue > 0:
                growth = ((self.tm_revenue - self.lm_revenue) / self.lm_revenue) * 100
                g_color = self.GREEN if growth >= 0 else self.RED
                sign = "+" if growth >= 0 else ""
                canvas.create_text(w/2, 10, text=f"Revenue Growth: {sign}{growth:.1f}%", font=("Arial", 12, "bold"), fill=g_color)

        canvas.bind("<Configure>", render_chart)

    def draw_donut_chart(self, parent):
        canvas = tk.Canvas(parent, bg=self.CARD, highlightthickness=0, height=350)
        canvas.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        
        def render_donut(event=None):
            canvas.delete("all")
            w = canvas.winfo_width()
            h = canvas.winfo_height()
            
            if w <= 10 or h <= 10: return
            
            total_for_chart = float(self.tm_expense)
            if total_for_chart <= 0:
                canvas.create_text(w/2, h/2, text="No Expenses For This Period", fill=self.SEC_FG, font=("Arial", 12))
                return
                
            tm_misc_expense = total_for_chart - self.tm_payroll
            if tm_misc_expense < 0: tm_misc_expense = 0.0

            payroll_pct = float(self.tm_payroll) / total_for_chart
            misc_pct = tm_misc_expense / total_for_chart
            
            payroll_deg = payroll_pct * 360.0
            misc_deg = 360.0 - payroll_deg 
            
            # --- SPLIT LAYOUT: Chart on Left, Legend on Right ---
            cx = w * 0.35 
            cy = h * 0.5
            size = min(w * 0.6, h * 0.8) * 0.8
            x0, y0 = cx - size/2, cy - size/2
            x1, y1 = cx + size/2, cy + size/2
            
            start_angle = 90
            
            # Smooth clockwise drawing
            if self.tm_payroll > 0:
                if payroll_deg >= 359.9:
                    canvas.create_oval(x0, y0, x1, y1, fill=self.BLUE, outline="")
                else:
                    canvas.create_arc(x0, y0, x1, y1, start=start_angle, extent=-payroll_deg, style=tk.PIESLICE, fill=self.BLUE, outline="")
            
            if tm_misc_expense > 0:
                if misc_deg >= 359.9:
                    canvas.create_oval(x0, y0, x1, y1, fill=self.RED, outline="")
                else:
                    canvas.create_arc(x0, y0, x1, y1, start=start_angle - payroll_deg, extent=-misc_deg, style=tk.PIESLICE, fill=self.RED, outline="")
            
            # Donut Cutout
            hole_size = size * 0.65
            hx0, hy0 = cx - hole_size/2, cy - hole_size/2
            hx1, hy1 = cx + hole_size/2, cy + hole_size/2
            canvas.create_oval(hx0, hy0, hx1, hy1, fill=self.CARD, outline="")
            
            # Center Text
            canvas.create_text(cx, cy - 12, text="Total Expenses", fill=self.SEC_FG, font=("Arial", 10))
            canvas.create_text(cx, cy + 12, text=format_currency(total_for_chart, self.curr_fmt).split(' ')[-1], fill=self.FG, font=("Arial", 16, "bold"))

            # --- THE "VALUE POINTERS" (Side-by-Side Key Legend) ---
            legend_x = cx + (size/2) + 60
            start_y = cy - 45
            
            # Payroll Legend Key
            canvas.create_oval(legend_x, start_y, legend_x + 15, start_y + 15, fill=self.BLUE, outline="")
            canvas.create_text(legend_x + 30, start_y + 7, text="Payroll Salaries", fill=self.SEC_FG, font=("Arial", 11, "bold"), anchor="w")
            canvas.create_text(legend_x + 30, start_y + 30, text=format_currency(self.tm_payroll, self.curr_fmt), fill=self.FG, font=("Arial", 16, "bold"), anchor="w")
            canvas.create_text(legend_x + 30, start_y + 52, text=f"{payroll_pct*100:.1f}% of total", fill=self.BLUE, font=("Arial", 10, "bold"), anchor="w")
            
            # Misc Legend Key
            start_y += 100
            canvas.create_oval(legend_x, start_y, legend_x + 15, start_y + 15, fill=self.RED, outline="")
            canvas.create_text(legend_x + 30, start_y + 7, text="Misc Expenses", fill=self.SEC_FG, font=("Arial", 11, "bold"), anchor="w")
            canvas.create_text(legend_x + 30, start_y + 30, text=format_currency(tm_misc_expense, self.curr_fmt), fill=self.FG, font=("Arial", 16, "bold"), anchor="w")
            canvas.create_text(legend_x + 30, start_y + 52, text=f"{misc_pct*100:.1f}% of total", fill=self.RED, font=("Arial", 10, "bold"), anchor="w")

        canvas.bind("<Configure>", render_donut)