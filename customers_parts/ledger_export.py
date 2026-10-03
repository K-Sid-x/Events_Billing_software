import os
import tempfile
import webbrowser
from datetime import datetime
import database

def export_ledger_statement(ledger):
    comp = database.get_company(ledger.comp_id)
    c_name = comp[1] if comp else "COMPANY NAME"
    c_addr = comp[3] if comp else "Address"
    p1 = comp[4] if comp else ""
    c_phone = p1 if p1 else "Phone"
    c_gst = comp[9] if comp else "GST Not Provided"
    
    grand_txt = ledger.lbl_grand.cget("text")
    
    def get_val(lbl):
        txt = lbl.cget('text')
        if '\n' in txt: return txt.split('\n')[-1]
        return txt
    
    # --- THE FIX: Advance Wallet added to the PDF summary safely ---
    try:
        adv_text = get_val(ledger.lbl_adv)
    except:
        adv_text = "Advance Wallet: 0.00"
    
    html = f"""
    <html><head><meta charset="utf-8"><style>
        body {{ font-family: Arial, sans-serif; margin: 40px; color: #333; }}
        .header {{ text-align: center; border-bottom: 2px solid #333; padding-bottom: 20px; margin-bottom: 20px; }}
        .header h1 {{ margin: 0; color: #1e3a8a; }}
        .header p {{ margin: 5px 0; color: #555; }}
        .details {{ display: flex; justify-content: space-between; margin-bottom: 20px; }}
        .party-box {{ border: 1px solid #ccc; padding: 15px; width: 45%; background: #f8fafc; border-radius: 5px; }}
        .summary {{ background: #f1f5f9; padding: 15px; margin-bottom: 20px; border-left: 4px solid #3b82f6; border-radius: 5px; }}
        .summary h3 {{ margin-top: 0; color: #1e293b; }}
        .summary table {{ width: 100%; border: none; font-size: 14px; margin-top: 10px; }}
        .summary td {{ padding: 5px 0; border: none; }}
        .grid {{ display: flex; gap: 20px; }}
        .col {{ flex: 1; }}
        h3 {{ color: #334155; border-bottom: 1px solid #ccc; padding-bottom: 5px; font-size: 16px; }}
        table {{ width: 100%; border-collapse: collapse; margin-bottom: 20px; font-size: 12px; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; white-space: nowrap; }}
        th {{ background-color: #e2e8f0; font-weight: bold; color: #334155; }}
        .right {{ text-align: right; }}
        .grand {{ text-align: right; font-size: 18px; font-weight: bold; margin-top: 20px; padding: 15px; background: #e0f2fe; border: 1px solid #bae6fd; border-radius: 5px; color: #0284c7; }}
        .wallet-row {{ background-color: #e2e8f0; font-weight: bold; color: #0f172a; text-align: center; }}
    </style></head><body>
    
        <div class="header">
            <h1>{c_name}</h1>
            <p>{c_addr} | 📞 {c_phone}</p>
            <p>GSTIN: {c_gst}</p>
        </div>
        
        <div class="details">
            <div class="party-box">
                <h3 style="border:none; margin:0 0 10px 0; color:#0f172a;">Ledger For:</h3>
                <strong>{ledger.party_name}</strong><br>
                📞 {ledger.phone_clean}<br>
                📍 {ledger.addr_text}<br>
                GSTIN: {ledger.gstin_str if ledger.gstin_str else "N/A"}
            </div>
            <div style="text-align:right;">
                <p><strong>Generated On:</strong> {datetime.now().strftime("%d %b %Y, %I:%M %p")}</p>
                <p><strong>Period:</strong> {ledger.filter_var.get()}</p>
            </div>
        </div>
        
        <div class="summary">
            <h3>Ledger Summary</h3>
            <table>
                <tr>
                    <td><strong>Invoiced:</strong> {get_val(ledger.lbl_s_inv)}</td>
                    <td><strong>Billed:</strong> {get_val(ledger.lbl_p_bill)}</td>
                </tr>
                <tr>
                    <td><strong>Received:</strong> {get_val(ledger.lbl_s_rec)}</td>
                    <td><strong>Paid:</strong> {get_val(ledger.lbl_p_paid)}</td>
                </tr>
                <tr>
                    <td><strong>Receivable:</strong> {get_val(ledger.lbl_s_pend)}</td>
                    <td><strong>Payable:</strong> {get_val(ledger.lbl_p_pend)}</td>
                </tr>
                <tr>
                    <td colspan="2" class="wallet-row" style="padding: 10px; border-top: 1px solid #ccc; margin-top: 5px;">
                        {adv_text}
                    </td>
                </tr>
            </table>
        </div>
        
        <div class="grid">
            <div class="col">
                <h3>Sales / Receivables (Debit)</h3>
                <table><tr><th>Date</th><th>Invoice No</th><th class="right">Amount</th><th class="right">TDS</th><th class="right">Balance</th><th>Status</th></tr>
    """
    
    for item in ledger.sales_tree.get_children():
        if not str(item).startswith("empty_"):
            v = ledger.sales_tree.item(item, "values")
            # --- THE FIX: Maps all 6 columns correctly (Date, Inv, Amount, TDS, Balance, Status) ---
            html += f"<tr><td>{v[0]}</td><td>{v[1]}</td><td class='right'>{v[2]}</td><td class='right'>{v[3]}</td><td class='right'>{v[4]}</td><td>{v[5]}</td></tr>"
            
    html += "</table></div><div class='col'><h3>Purchases / Payables (Credit)</h3><table><tr><th>Date</th><th>Bill No</th><th class='right'>Amount</th><th class='right'>TDS</th><th class='right'>Balance</th><th>Status</th></tr>"
    
    for item in ledger.purch_tree.get_children():
        if not str(item).startswith("empty_"):
            v = ledger.purch_tree.item(item, "values")
            # --- THE FIX: Maps all 6 columns correctly (Date, Inv, Amount, TDS, Balance, Status) ---
            html += f"<tr><td>{v[0]}</td><td>{v[1]}</td><td class='right'>{v[2]}</td><td class='right'>{v[3]}</td><td class='right'>{v[4]}</td><td>{v[5]}</td></tr>"
            
    html += f"""
                </table>
            </div>
        </div>
        <div class="grand">{grand_txt}</div>
        <script>window.onload=function(){{window.print();}}</script>
    </body></html>
    """
    
    try:
        # --- THE FIX: Added a prefix to easily identify junk files ---
        fd, path = tempfile.mkstemp(suffix=".html", prefix="Ledger_Stmt_")
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(html)
        # -------------------------------------------------------------
        webbrowser.open('file://' + os.path.realpath(path))
    except Exception as e:
        pass