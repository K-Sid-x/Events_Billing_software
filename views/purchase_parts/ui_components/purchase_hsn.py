import tkinter as tk
from tkinter import ttk
import sys
import os

# --- THE FIX: Bulletproof Executable Pathing ---
if getattr(sys, 'frozen', False):
    ROOT_DIR = os.path.dirname(sys.executable)
else:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parts_dir = os.path.dirname(current_dir)
    views_dir = os.path.dirname(parts_dir)
    ROOT_DIR = os.path.dirname(views_dir)

if ROOT_DIR not in sys.path: 
    sys.path.insert(0, ROOT_DIR)
# -----------------------------------------------

from views.invoice_parts.helpers import format_currency

class HSNSummaryTable:
    def __init__(self, parent, form_ctx):
        self.parent = parent
        self.form = form_ctx
        
        self.current_state_is_interstate = False
        
        self.container = tk.Frame(self.parent, bg=self.form.CARD_BG, highlightbackground=self.form.BORDER_COLOR, highlightthickness=1)
        self.container.pack(fill="both", expand=True)

        tk.Label(self.container, text="Tax Summary", font=("Segoe UI", 10, "bold"), bg=self.form.CARD_BG, fg=self.form.TEXT_SECONDARY).pack(anchor="w", padx=10, pady=(10, 5))

        style = ttk.Style()
        style.configure("HSN.Treeview.Heading", font=("Segoe UI", 9, "bold"), background=self.form.HEADER_BG, foreground=self.form.TEXT_PRIMARY)
        style.configure("HSN.Treeview", font=("Segoe UI", 10), rowheight=25, background=self.form.CARD_BG, fieldbackground=self.form.CARD_BG, foreground=self.form.TEXT_PRIMARY)

        def fixed_map(option):
            return [elm for elm in style.map("Treeview", query_opt=option) if elm[:2] != ("!disabled", "!selected")]
        try: style.map("HSN.Treeview", foreground=fixed_map("foreground"), background=fixed_map("background"))
        except: style.map("HSN.Treeview", background=[('selected', self.form.LIST_SEL)])

        self.tree_frame = tk.Frame(self.container, bg=self.form.CARD_BG)
        self.tree_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.tree_frame.columnconfigure(0, weight=1)

        self.scroll_y = ttk.Scrollbar(self.tree_frame, orient="vertical")
        self.scroll_y.grid(row=0, column=1, sticky="ns")

        self.tree = ttk.Treeview(self.tree_frame, columns=("sl_no", "hsn", "taxable", "cgst_r", "cgst_a", "sgst_r", "sgst_a", "igst_r", "igst_a", "tot"), show="headings", style="HSN.Treeview", height=4, yscrollcommand=self.scroll_y.set)
        self.scroll_y.config(command=self.tree.yview)
        self.tree.grid(row=0, column=0, sticky="nsew")

        self.footer_tree = ttk.Treeview(self.tree_frame, columns=("sl_no", "hsn", "taxable", "cgst_r", "cgst_a", "sgst_r", "sgst_a", "igst_r", "igst_a", "tot"), show="", style="HSN.Treeview", height=1)
        self.footer_tree.grid(row=1, column=0, sticky="nsew")

        self.tree.tag_configure("stripe_even", background=self.form.CARD_BG)
        self.tree.tag_configure("stripe_odd", background=self.form.BG_COLOR)
        self.footer_tree.tag_configure("bold", font=("Segoe UI", 10, "bold"), background=self.form.HEADER_BG)

        headers = [
            ("sl_no", "SI No.", 60), 
            ("hsn", "HSN/SAC", 100), 
            ("taxable", "Taxable Value", 120),
            ("cgst_r", "CGST %", 70), 
            ("cgst_a", "Amount", 100),
            ("sgst_r", "SGST %", 70), 
            ("sgst_a", "Amount", 100),
            ("igst_r", "IGST %", 70), 
            ("igst_a", "Amount", 100),
            ("tot", "Total Tax", 120)
        ]

        for col, text, width in headers:
            self.tree.heading(col, text=text)
            self.tree.column(col, width=width, minwidth=10, anchor="center", stretch=False)
            self.footer_tree.column(col, width=width, minwidth=10, anchor="center", stretch=False)

        # --- THE FIX: Stop Scroll Event Leakage via return "break" ---
        def isolate_scroll(event):
            self.tree.yview_scroll(int(-1 * (event.delta / 120)), "units")
            return "break"

        self.tree.bind("<MouseWheel>", isolate_scroll)
        self.footer_tree.bind("<MouseWheel>", lambda e: "break")

        def prevent_resize(event):
            if self.tree.identify_region(event.x, event.y) == "separator":
                return "break"
                
        self.tree.bind('<Button-1>', prevent_resize)
        self.tree.bind('<B1-Motion>', prevent_resize)
        self.tree.bind('<Motion>', prevent_resize)

        self.tree.bind("<Configure>", lambda e: self.parent.after(10, self.adjust_columns))

    def adjust_columns(self):
        total_w = self.tree.winfo_width()
        if total_w < 50: return 

        safe_w = total_w - 5 

        if self.current_state_is_interstate:
            fixed_w = 230
            rem_w = safe_w - fixed_w
            if rem_w > 0:
                part = int(rem_w / 3)
                for t in [self.tree, self.footer_tree]:
                    t.column("hsn", width=part)
                    t.column("taxable", width=part)
                    t.column("tot", width=rem_w - (part * 2))
        else:
            fixed_w = 400
            rem_w = safe_w - fixed_w
            if rem_w > 0:
                part = int(rem_w / 3)
                for t in [self.tree, self.footer_tree]:
                    t.column("hsn", width=part)
                    t.column("taxable", width=part)
                    t.column("tot", width=rem_w - (part * 2))

    def update_table(self, summary_dict, is_interstate):
        self.current_state_is_interstate = is_interstate
        
        disp = ("sl_no", "hsn", "taxable", "igst_r", "igst_a", "tot") if is_interstate else ("sl_no", "hsn", "taxable", "cgst_r", "cgst_a", "sgst_r", "sgst_a", "tot")
        
        self.tree["displaycolumns"] = disp
        self.footer_tree["displaycolumns"] = disp

        for item in self.tree.get_children(): self.tree.delete(item)
        for item in self.footer_tree.get_children(): self.footer_tree.delete(item)

        total_taxable = 0.0
        total_cgst = 0.0; total_sgst = 0.0; total_igst = 0.0; grand_tax = 0.0

        row_idx = 0
        for (hsn, gst_pct), taxable in summary_dict.items():
            # --- THE FIX: Defensive float cast parsing for zeroing bug safety ---
            try: g_pct = float(gst_pct)
            except: g_pct = 0.0

            t_tax = taxable * (g_pct / 100)
            
            if is_interstate:
                cg_r = "-"; cg_a = "0.00"; sg_r = "-"; sg_a = "0.00"
                ig_r = f"{g_pct if g_pct % 1 != 0 else int(g_pct)}%"
                ig_a = format_currency(t_tax, self.form.curr_fmt)
                total_igst += t_tax
            else:
                half = g_pct / 2
                cg_r = f"{half if half % 1 != 0 else int(half)}%"
                cg_a = format_currency(t_tax/2, self.form.curr_fmt)
                sg_r = f"{half if half % 1 != 0 else int(half)}%"
                sg_a = format_currency(t_tax/2, self.form.curr_fmt)
                ig_r = "-"; ig_a = "0.00"
                total_cgst += t_tax/2
                total_sgst += t_tax/2

            total_taxable += taxable
            grand_tax += t_tax
            
            tag = "stripe_even" if row_idx % 2 == 0 else "stripe_odd"
            self.tree.insert("", "end", iid=f"tax_row_{row_idx}", values=(row_idx + 1, hsn, format_currency(taxable, self.form.curr_fmt), cg_r, cg_a, sg_r, sg_a, ig_r, ig_a, format_currency(t_tax, self.form.curr_fmt)), tags=(tag,))
            row_idx += 1

        MIN_DATA_ROWS = 4
        while row_idx < MIN_DATA_ROWS:
            tag = "stripe_even" if row_idx % 2 == 0 else "stripe_odd"
            self.tree.insert("", "end", values=(" ", " ", " ", " ", " ", " ", " ", " ", " ", " "), tags=(tag,))
            row_idx += 1

        self.footer_tree.insert("", "end", values=("", "TOTAL", format_currency(total_taxable, self.form.curr_fmt), "-", format_currency(total_cgst, self.form.curr_fmt), "-", format_currency(total_sgst, self.form.curr_fmt), "-", format_currency(total_igst, self.form.curr_fmt), format_currency(grand_tax, self.form.curr_fmt)), tags=("bold",))
        
        self.parent.after(50, self.adjust_columns)