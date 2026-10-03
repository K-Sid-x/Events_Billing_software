import csv
import tempfile
import webbrowser
import os
from tkinter import filedialog, messagebox

def export_expenses_csv(headers, data_rows, callback=None):
    file_path = filedialog.asksaveasfilename(
        defaultextension=".csv", 
        filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")], 
        title="Save Expenses as CSV"
    )
    if not file_path: return
        
    try:
        with open(file_path, mode='w', newline='', encoding='utf-8-sig') as file:
            writer = csv.writer(file)
            writer.writerow(headers)
            writer.writerows(data_rows)
                    
        messagebox.showinfo("Export Successful", f"Your expenses have been successfully exported to:\n{file_path}")
        if callback: callback()
    except Exception as e:
        messagebox.showerror("Export Failed", f"An error occurred while saving the file:\n{str(e)}")

def print_expenses_pdf(headers, data_rows, total_text, callback=None):
    html_content = f"""
    <html>
    <head>
        <meta charset="utf-8">
        <title>Expense Report</title>
        <style>
            @media print {{ @page {{ margin: 0; size: auto; }} body {{ margin: 2cm; }} }}
            body {{ font-family: Arial, sans-serif; margin: 40px; color: #0f172a; }}
            h2 {{ color: #1e293b; margin-bottom: 5px; }}
            .total-lbl {{ font-size: 18px; font-weight: bold; color: #e11d48; margin-bottom: 25px; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 10px; border-top: 2px solid #cbd5e1; border-bottom: 2px solid #cbd5e1; }}
            th, td {{ padding: 12px 10px; text-align: left; font-size: 14px; border-bottom: 1px solid #e2e8f0; }}
            th {{ background-color: #f8fafc; font-weight: bold; color: #475569; border-bottom: 2px solid #cbd5e1; }}
            .month-header td {{ background-color: #f1f5f9; font-weight: bold; font-size: 15px; color: #1e293b; border-bottom: 1px solid #cbd5e1; }}
        </style>
    </head>
    <body>
        <h2>Company Expense Report</h2>
        <div class="total-lbl">{total_text}</div>
        <table>
            <thead>
                <tr>
    """
    for h in headers:
        align = "text-align: right;" if h == "AMOUNT" else ""
        html_content += f'<th style="{align}">{h}</th>'
        
    html_content += """
                </tr>
            </thead>
            <tbody>
    """
    
    for row in data_rows:
        if len(row) == 1 and str(row[0]).startswith("📅"):
            html_content += f'<tr class="month-header"><td colspan="{len(headers)}">{row[0]}</td></tr>'
        else:
            html_content += "<tr>"
            for i, cell in enumerate(row):
                # --- THE FIX: Added white-space: nowrap to force the currency on one line ---
                align = ' style="text-align: right; font-weight: bold; white-space: nowrap;"' if headers[i] == "AMOUNT" else ''
                html_content += f'<td{align}>{cell}</td>'
            html_content += "</tr>"
            
    html_content += """
            </tbody>
        </table>
        <script> window.onload = function() { window.print(); } </script>
    </body>
    </html>
    """
    # --- THE FIX: Tagged prefix for the Sweeper ---
    fd, path = tempfile.mkstemp(suffix=".html", prefix="Expense_Report_")
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        f.write(html_content)
    webbrowser.open('file://' + os.path.realpath(path))
    if callback: callback()