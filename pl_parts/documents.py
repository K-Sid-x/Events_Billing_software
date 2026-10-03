import tkinter as tk
from tkinter import messagebox, filedialog
import os
import sys
import csv
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

if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)
# -----------------------------------------------

import database
from views.invoice_parts.helpers import format_currency

class PLDocumentManager:
    def __init__(self, view):
        self.view = view

    def print_pdf(self):
        try:
            comp_id = getattr(self.view.app, "active_company_id", 1)
            comp = database.get_company(comp_id) if comp_id else database.get_company(1)
            comp_name = comp[1] if comp else "COMPANY NAME"
        except: comp_name = "COMPANY NAME"

        period_text = "All Time"
        if self.view.filter_start_var.get() or self.view.filter_end_var.get():
            period_text = f"From: {self.view.filter_start_var.get()} To: {self.view.filter_end_var.get()}"
        elif self.view.filter_year_var.get() != "All Years":
            period_text = f"Period: {self.view.filter_month_var.get()} {self.view.filter_year_var.get()}"

        basis_text = f"Accounting Basis: {self.view.accounting_basis.get()}"

        html_content = f"""
        <html>
        <head>
            <meta charset="utf-8">
            <title>P&L Statement - {comp_name}</title>
            <style>
                @media print {{ 
                    @page {{ margin: 1cm; size: A4 portrait; }} 
                    .print-dark-bg {{ background-color: #1e293b !important; color: white !important; -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
                }}
                body {{ font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; color: #1e293b; padding: 20px; }}
                h1 {{ color: #0f172a; margin-bottom: 5px; font-size: 26px; }}
                .subtitle {{ font-size: 14px; color: #64748b; margin-bottom: 30px; }}
                
                .summary-grid {{ display: flex; justify-content: space-between; margin-bottom: 40px; }}
                .tile {{ background: #f8fafc; border: 1px solid #e2e8f0; padding: 15px; border-radius: 8px; width: 22%; text-align: center; }}
                .tile-title {{ font-size: 11px; font-weight: bold; color: #64748b; text-transform: uppercase; margin-bottom: 8px; }}
                .tile-val {{ font-size: 22px; font-weight: bold; color: #0f172a; }}
                .val-green {{ color: #10b981; }}
                .val-red {{ color: #ef4444; }}
                
                table {{ width: 100%; border-collapse: collapse; margin-bottom: 10px; font-size: 13px; }}
                th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #e2e8f0; }}
                .td-money {{ text-align: right; font-weight: bold; }}
            </style>
        </head>
        <body>
            <h1>Profit & Loss Statement</h1>
            <div class="subtitle">{comp_name} &nbsp;|&nbsp; {period_text} &nbsp;|&nbsp; {basis_text}</div>

            <div class="summary-grid">
                <div class="tile">
                    <div class="tile-title">Revenue (Sales)</div>
                    <div class="tile-val">{self.view.lbl_inc.cget("text")}</div>
                </div>
                <div class="tile">
                    <div class="tile-title">Direct Costs (Purchases)</div>
                    <div class="tile-val">{self.view.lbl_cogs.cget("text")}</div>
                </div>
                <div class="tile">
                    <div class="tile-title">Operating Expenses</div>
                    <div class="tile-val">{self.view.lbl_opex.cget("text")}</div>
                </div>
                <div class="tile">
                    <div class="tile-title">Net Profit</div>
                    <div class="tile-val { 'val-green' if self.view.lbl_net.cget('fg') == self.view.ACCENT_GREEN else 'val-red' }">{self.view.lbl_net.cget("text")}</div>
                </div>
            </div>
        """

        current_layout = self.view.layout_var.get() if hasattr(self.view, 'layout_var') else "T-Account (CA)"
        
        c_inc = sum(sum(i[3] for i in items) for items in getattr(self.view, 'inc_grouped', {}).values())
        c_cogs = sum(sum(i[3] for i in items) for items in getattr(self.view, 'cogs_grouped', {}).values())
        c_opex = sum(sum(i[3] for i in items) for items in getattr(self.view, 'opex_grouped', {}).values())
        gross_profit = c_inc - c_cogs
        c_net = gross_profit - c_opex
        t_total = max(c_inc, c_cogs + c_opex)

        net_color = "#10b981" if c_net >= 0 else "#ef4444"

        if current_layout == "Modern (Vertical)":
            html_content += f"""
            <table style="width: 100%;">
                <thead>
                    <tr><th colspan="2" class="print-dark-bg" style="background:#1e293b; color:white; font-size:15px; padding:12px;">📋 PROFIT & LOSS</th></tr>
                </thead>
                <tbody>
            """
            
            html_content += f'<tr><td colspan="2" style="color:#0f172a; font-size:15px; font-weight:bold; padding-top:20px; padding-bottom:5px; border-bottom: 2px solid #e2e8f0;">1. REVENUE (INCOME)</td></tr>'
            for cat, items in getattr(self.view, 'inc_grouped', {}).items():
                if not items: continue
                cat_total = sum(i[3] for i in items)
                html_content += f'<tr><td><span style="color:#64748b; font-size:12px; font-weight:bold; text-transform:uppercase;">{cat}</span></td><td class="td-money" style="color:#3b82f6; font-size:14px;">{format_currency(cat_total, self.view.curr_fmt)}</td></tr>'

            html_content += f'<tr><td colspan="2" style="color:#0f172a; font-size:15px; font-weight:bold; padding-top:20px; padding-bottom:5px; border-bottom: 2px solid #e2e8f0;">2. DIRECT COSTS (COGS)</td></tr>'
            for cat, items in getattr(self.view, 'cogs_grouped', {}).items():
                if not items: continue
                cat_total = sum(i[3] for i in items)
                html_content += f'<tr><td><span style="color:#64748b; font-size:12px; font-weight:bold; text-transform:uppercase;">{cat}</span></td><td class="td-money" style="color:#ef4444; font-size:14px;">{format_currency(cat_total, self.view.curr_fmt)}</td></tr>'

            html_content += f'<tr><td colspan="2"><hr style="border:0; border-top:1px solid #e2e8f0; margin:10px 0;"></td></tr>'
            html_content += f'<tr><td style="color:#0f172a; font-size:14px; font-weight:bold;">= GROSS PROFIT</td><td class="td-money" style="color:#0f172a; font-size:15px; font-weight:bold;">{format_currency(gross_profit, self.view.curr_fmt)}</td></tr>'

            html_content += f'<tr><td colspan="2" style="color:#0f172a; font-size:15px; font-weight:bold; padding-top:20px; padding-bottom:5px; border-bottom: 2px solid #e2e8f0;">3. OPERATING EXPENSES (OPEX)</td></tr>'
            for cat, items in sorted(getattr(self.view, 'opex_grouped', {}).items(), key=lambda x: sum(i[3] for i in x[1]), reverse=True):
                if not items: continue
                cat_total = sum(i[3] for i in items)
                html_content += f'<tr><td><span style="color:#64748b; font-size:12px; font-weight:bold; text-transform:uppercase;">{cat}</span></td><td class="td-money" style="color:#ef4444; font-size:14px;">{format_currency(cat_total, self.view.curr_fmt)}</td></tr>'

            html_content += f'<tr><td colspan="2"><hr style="border:0; border-top:1px solid #e2e8f0; margin:10px 0;"></td></tr>'
            html_content += f'<tr><td style="color:#0f172a; font-size:14px; font-weight:bold;">= TOTAL OPEX</td><td class="td-money" style="color:#0f172a; font-size:15px; font-weight:bold;">{format_currency(c_opex, self.view.curr_fmt)}</td></tr>'

            html_content += f"""
                </tbody>
            </table>
            <table style="width: 100%; margin-top: 20px;">
                <tbody>
                    <tr>
                        <td class="print-dark-bg" style="background:#0f172a; color:white; padding:15px; font-size:16px; font-weight:bold;">NET PROFIT / (LOSS)</td>
                        <td class="print-dark-bg td-money" style="background:#0f172a; padding:15px; color:{net_color}; font-size:18px; font-weight:bold;">{format_currency(c_net, self.view.curr_fmt)}</td>
                    </tr>
                </tbody>
            </table>
            """
        else:
            # T-ACCOUNT
            html_content += f"""
            <div style="display: flex; gap: 20px; align-items: stretch;">
                <!-- LEFT COLUMN: DEBIT -->
                <div style="flex: 1; display: flex; flex-direction: column;">
                    <div style="flex-grow: 1;">
                        <table style="width: 100%;">
                            <thead>
                                <tr><th colspan="2" class="print-dark-bg" style="background:#1e293b; color:white; font-size:15px; padding:12px;">📉 DEBIT (Expenses & Losses)</th></tr>
                            </thead>
                            <tbody>
                                <tr><td colspan="2" style="color:#0f172a; font-size:15px; font-weight:bold; padding-top:15px; padding-bottom:5px; border-bottom: 2px solid #e2e8f0;">DIRECT COSTS (COGS)</td></tr>
            """

            for cat, items in getattr(self.view, 'cogs_grouped', {}).items():
                if not items: continue
                cat_total = sum(i[3] for i in items)
                html_content += f'<tr><td><span style="color:#64748b; font-size:12px; font-weight:bold; text-transform:uppercase;">{cat}</span></td><td class="td-money" style="color:#ef4444; font-size:14px;">{format_currency(cat_total, self.view.curr_fmt)}</td></tr>'

            html_content += f'<tr><td colspan="2" style="color:#0f172a; font-size:15px; font-weight:bold; padding-top:20px; padding-bottom:5px; border-bottom: 2px solid #e2e8f0;">OPERATING EXPENSES (OPEX)</td></tr>'
            
            for cat, items in sorted(getattr(self.view, 'opex_grouped', {}).items(), key=lambda x: sum(i[3] for i in x[1]), reverse=True):
                if not items: continue
                cat_total = sum(i[3] for i in items)
                html_content += f'<tr><td><span style="color:#64748b; font-size:12px; font-weight:bold; text-transform:uppercase;">{cat}</span></td><td class="td-money" style="color:#ef4444; font-size:14px;">{format_currency(cat_total, self.view.curr_fmt)}</td></tr>'

            if c_net > 0:
                html_content += f'<tr><td colspan="2"><hr style="border:0; border-top:1px solid #e2e8f0; margin:15px 0;"></td></tr>'
                html_content += f'<tr><td style="color:#10b981; font-size:15px; font-weight:bold;">NET PROFIT<br><span style="font-size:11px; font-weight:normal; color:#64748b;">Transferred to Balance Sheet</span></td><td class="td-money" style="color:#10b981; font-size:16px; font-weight:bold;">{format_currency(c_net, self.view.curr_fmt)}</td></tr>'

            html_content += f"""
                            </tbody>
                        </table>
                    </div>
                    <!-- DEBIT TOTAL - Force dark text on light grey so it is ALWAYS readable even if backgrounds fail to print -->
                    <table style="width: 100%; margin-top: auto; border: 2px solid #0f172a;">
                        <tbody>
                            <tr>
                                <td style="background:#f1f5f9; color:#0f172a; padding:15px; font-size:15px; font-weight:bold;">TOTAL DEBIT</td>
                                <td class="td-money" style="background:#f1f5f9; color:#0f172a; padding:15px; font-size:16px; font-weight:bold;">{format_currency(t_total, self.view.curr_fmt)}</td>
                            </tr>
                        </tbody>
                    </table>
                </div>

                <!-- RIGHT COLUMN: CREDIT -->
                <div style="flex: 1; display: flex; flex-direction: column;">
                    <div style="flex-grow: 1;">
                        <table style="width: 100%;">
                            <thead>
                                <tr><th colspan="2" class="print-dark-bg" style="background:#1e293b; color:white; font-size:15px; padding:12px;">📈 CREDIT (Incomes & Gains)</th></tr>
                            </thead>
                            <tbody>
                                <tr><td colspan="2" style="color:#0f172a; font-size:15px; font-weight:bold; padding-top:15px; padding-bottom:5px; border-bottom: 2px solid #e2e8f0;">REVENUE (INCOME)</td></tr>
            """
            
            for cat, items in getattr(self.view, 'inc_grouped', {}).items():
                if not items: continue
                cat_total = sum(i[3] for i in items)
                html_content += f'<tr><td><span style="color:#64748b; font-size:12px; font-weight:bold; text-transform:uppercase;">{cat}</span></td><td class="td-money" style="color:#3b82f6; font-size:14px;">{format_currency(cat_total, self.view.curr_fmt)}</td></tr>'

            if c_net < 0:
                html_content += f'<tr><td colspan="2"><hr style="border:0; border-top:1px solid #e2e8f0; margin:15px 0;"></td></tr>'
                html_content += f'<tr><td style="color:#ef4444; font-size:15px; font-weight:bold;">NET LOSS<br><span style="font-size:11px; font-weight:normal; color:#64748b;">Transferred to Balance Sheet</span></td><td class="td-money" style="color:#ef4444; font-size:16px; font-weight:bold;">{format_currency(abs(c_net), self.view.curr_fmt)}</td></tr>'

            html_content += f"""
                            </tbody>
                        </table>
                    </div>
                    <!-- CREDIT TOTAL - Force dark text on light grey -->
                    <table style="width: 100%; margin-top: auto; border: 2px solid #0f172a;">
                        <tbody>
                            <tr>
                                <td style="background:#f1f5f9; color:#0f172a; padding:15px; font-size:15px; font-weight:bold;">TOTAL CREDIT</td>
                                <td class="td-money" style="background:#f1f5f9; color:#0f172a; padding:15px; font-size:16px; font-weight:bold;">{format_currency(t_total, self.view.curr_fmt)}</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>
            """

        html_content += """
            <script>window.onload = function() { window.print(); }</script>
        </body>
        </html>
        """

        fd, path = tempfile.mkstemp(suffix=".html", prefix="PL_Statement_")
        with os.fdopen(fd, 'w', encoding='utf-8') as f: f.write(html_content)
        webbrowser.open('file://' + os.path.realpath(path))

    def export_csv(self):
        file_path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV Files", "*.csv")], title="Export P&L")
        if not file_path: return
        try:
            with open(file_path, mode='w', newline='', encoding='utf-8-sig') as file:
                writer = csv.writer(file)
                writer.writerow(["PROFIT & LOSS STATEMENT"])
                writer.writerow(["Generated on", datetime.now().strftime(self.view.date_fmt_code)])
                writer.writerow(["Basis", self.view.accounting_basis.get()])
                writer.writerow([])
                
                writer.writerow(["SUMMARY"])
                writer.writerow(["Total Income", self.view.lbl_inc.cget("text")])
                writer.writerow(["Direct Costs", self.view.lbl_cogs.cget("text")])
                writer.writerow(["OPEX", self.view.lbl_opex.cget("text")])
                writer.writerow(["Net Profit", self.view.lbl_net.cget("text")])
                writer.writerow([])
                
                writer.writerow(["--- INCOME ---"])
                writer.writerow(["Date", "Description", "Type", "Amount"])
                
                # --- THE FIX: Isolate Closing Stock from standard Income! ---
                inc_dict = getattr(self.view, 'inc_grouped', {})
                for cat, items in inc_dict.items():
                    if "Closing Stock" in cat: continue
                    for i in sorted(items, key=lambda x: x[0], reverse=True):
                        writer.writerow([i[0].strftime(self.view.date_fmt_code), i[1], i[2], format_currency(i[3], self.view.curr_fmt)])
                
                # If we have Closing Stock, print it under its own distinct header
                has_stock = any("Closing Stock" in k for k in inc_dict.keys())
                if has_stock:
                    writer.writerow([])
                    writer.writerow(["--- ASSETS / CLOSING STOCK ---"])
                    writer.writerow(["Date", "Description", "Type", "Amount"])
                    for cat, items in inc_dict.items():
                        if "Closing Stock" in cat:
                            for i in sorted(items, key=lambda x: x[0], reverse=True):
                                writer.writerow([i[0].strftime(self.view.date_fmt_code), i[1], i[2], format_currency(i[3], self.view.curr_fmt)])
                # -------------------------------------------------------------
                
                writer.writerow([])
                writer.writerow(["--- DIRECT COSTS ---"])
                writer.writerow(["Date", "Description", "Type", "Amount"])
                for cat, items in getattr(self.view, 'cogs_grouped', {}).items():
                    for i in sorted(items, key=lambda x: x[0], reverse=True):
                        writer.writerow([i[0].strftime(self.view.date_fmt_code), i[1], i[2], format_currency(i[3], self.view.curr_fmt)])
                
                writer.writerow([])
                writer.writerow(["--- OPEX ---"])
                writer.writerow(["Date", "Description", "Type", "Amount"])
                for cat, items in getattr(self.view, 'opex_grouped', {}).items():
                    for i in sorted(items, key=lambda x: x[0], reverse=True):
                        writer.writerow([i[0].strftime(self.view.date_fmt_code), i[1], i[2], format_currency(i[3], self.view.curr_fmt)])

            messagebox.showinfo("Export Successful", f"P&L exported to:\n{file_path}")
        except Exception as e: messagebox.showerror("Export Failed", str(e))