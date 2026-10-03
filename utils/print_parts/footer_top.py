import database
from utils.print_parts.helpers import format_currency

def get_top_blocks(ctx, get_css, curr_format):
    studio = ctx["studio"]
    words_val = ctx["words_val"]
    
    css_amt_lbl = get_css("amt_words_lbl"); css_amt_val = get_css("amt_words_val")
    css_bank_lbl = get_css("bank_lbl"); css_bank_val = get_css("bank_val")
    css_totals = get_css("totals")

    # --- LEFT SIDE: AMOUNT IN WORDS & BANK ---
    top_left_html = f'<div><div style="{css_amt_lbl} margin-bottom: 2px;">Amount in Words:</div>'
    top_left_html += f'<div style="{css_amt_val} word-break: break-word; overflow-wrap: break-word;">{words_val}</div></div>'
    
    bank_html = ""
    if studio.banks_data:
        b_data = studio.banks_data[0]
        bank_str = f"Bank: {b_data.get('name', '')}<br>A/C Name: {b_data.get('ac_name') or ctx['c_name']}<br>A/C No: {b_data.get('ac', '')}<br>IFSC: {b_data.get('ifsc', '')}<br>Branch: {b_data.get('branch', '')}"
        if b_data.get('pan'): bank_str += f"<br>PAN: {b_data.get('pan', '')}"
        if ctx.get("qr_b64"):
            # --- THE FIX: Increased width and height to 100px ---
            bank_html += f'<table style="display: inline-table; width: auto; border: none; margin: 0; padding: 0; border-collapse: collapse;"><tr><td style="{css_bank_val} border: none; padding: 0; padding-right: 20px; vertical-align: top; word-break: break-word; overflow-wrap: break-word;"><div style="{css_bank_lbl} margin-bottom: 2px;">Bank Details:</div>{bank_str}</td><td style="border: none; padding: 0; vertical-align: top; text-align: right; width: 100px;"><img src="{ctx["qr_b64"]}" style="width: 100px; height: 100px; object-fit: contain; margin-top: 2px;"></td></tr></table>'
            # ----------------------------------------------------
        else:
            bank_html += f'<div style="{css_bank_lbl} margin-bottom: 2px;">Bank Details:</div><div style="{css_bank_val} word-break: break-word; overflow-wrap: break-word;">{bank_str}</div>'
    
    bank_section = f'<div style="margin-top: 10px; border-top: 1px solid #000; width: 320px; padding-top: 8px;">{bank_html}</div>' if bank_html else ""
    
    left_block = f"""
        <div>
            {top_left_html}
            {bank_section}
        </div>
    """

    # --- THE FIX: Securely read GST status from memory (Prevents DB lock & cross-company leaks!) ---
    has_gst = ctx.get("has_gst", True)
    # -----------------------------------------------------------------------------------------------

    # --- RIGHT SIDE: TOTALS TABLE ---
    show_discount = ctx["inc_discount"] == 1
    show_advance = ctx["inc_advance"] == 1
    totals_html = f'<table style="width: 100%; border-collapse: collapse; border: none; line-height: 1.1;">'
    totals_html += f'<tr><td style="border: none; {css_totals} text-align: right; padding-right: 15px; padding-top: 1px; padding-bottom: 1px;">Sub Total :</td><td style="border: none; {css_totals} text-align: right; width: 120px; padding-top: 1px; padding-bottom: 1px;">{format_currency(ctx["sub"], curr_format)}</td></tr>'
    
    if show_discount:
        totals_html += f'<tr><td style="border: none; {css_totals} text-align: right; padding-right: 15px; padding-top: 1px; padding-bottom: 1px;">Discount :</td><td style="border: none; {css_totals} text-align: right; padding-top: 1px; padding-bottom: 1px;">- {format_currency(ctx["discount_amt"], curr_format)}</td></tr>'
        totals_html += f'<tr><td style="border: none; {css_totals} text-align: right; padding-right: 15px; padding-top: 1px; padding-bottom: 1px;">Taxable Amt :</td><td style="border: none; {css_totals} text-align: right; padding-top: 1px; padding-bottom: 1px;">{format_currency(ctx["taxable_amt"], curr_format)}</td></tr>'
    
    if has_gst:
        inv = studio.inv_data
        if ctx["is_igst"]:
            ig_r = inv.get("igst_rate", "18")
            totals_html += f'<tr><td style="border: none; {css_totals} text-align: right; padding-right: 15px; padding-top: 1px; padding-bottom: 1px;">IGST @ {ig_r}% :</td><td style="border: none; {css_totals} text-align: right; padding-top: 1px; padding-bottom: 1px;">{format_currency(ctx["ig"], curr_format)}</td></tr>'
        else:
            cg_r = inv.get("cgst_rate", "9")
            sg_r = inv.get("sgst_rate", "9")
            totals_html += f'<tr><td style="border: none; {css_totals} text-align: right; padding-right: 15px; padding-top: 1px; padding-bottom: 1px;">CGST @ {cg_r}% :</td><td style="border: none; {css_totals} text-align: right; padding-top: 1px; padding-bottom: 1px;">{format_currency(ctx["cg"], curr_format)}</td></tr>'
            totals_html += f'<tr><td style="border: none; {css_totals} text-align: right; padding-right: 15px; padding-top: 1px; padding-bottom: 1px;">SGST @ {sg_r}% :</td><td style="border: none; {css_totals} text-align: right; padding-top: 1px; padding-bottom: 1px;">{format_currency(ctx["sg"], curr_format)}</td></tr>'
    
    totals_html += f'<tr><td style="border: none; {css_totals} text-align: right; padding-right: 15px; padding-top: 1px; padding-bottom: 1px;">Round Off +/- :</td><td style="border: none; {css_totals} text-align: right; padding-top: 1px; padding-bottom: 1px;">{format_currency(ctx["round_off"], curr_format)}</td></tr>'
    totals_html += f'<tr><td colspan="2" style="border: none; padding: 0;"><div style="border-top: 1px solid #000; margin: 3px 0 4px 30%;"></div></td></tr>'
    
    if show_advance:
        totals_html += f'<tr><td style="border: none; {css_totals} text-align: right; padding-right: 15px; padding-top: 1px; padding-bottom: 1px;">Total Amount :</td><td style="border: none; {css_totals} text-align: right; padding-top: 1px; padding-bottom: 1px;">{format_currency(ctx["tot"], curr_format)}</td></tr>'
        totals_html += f'<tr><td style="border: none; {css_totals} text-align: right; padding-right: 15px; padding-top: 1px; padding-bottom: 1px;">Advance Paid :</td><td style="border: none; {css_totals} text-align: right; padding-top: 1px; padding-bottom: 1px;">- {format_currency(ctx["advance_val"], curr_format)}</td></tr>'
        totals_html += f'<tr><td colspan="2" style="border: none; padding: 0;"><div style="border-top: 1px solid #000; margin: 4px 0 6px 30%;"></div></td></tr>'
        totals_html += f'<tr><td style="border: none; {css_totals} text-align: right; padding-right: 15px; font-weight: bold;">Balance Due :</td><td style="border: none; {css_totals} text-align: right; font-weight: bold;">{format_currency(ctx["tot"] - ctx["advance_val"], curr_format)}</td></tr>'
    else:
        totals_html += f'<tr><td style="border: none; {css_totals} text-align: right; padding-right: 15px; font-weight: bold;">Grand Total :</td><td style="border: none; {css_totals} text-align: right; font-weight: bold;">{format_currency(ctx["tot"], curr_format)}</td></tr>'
    
    totals_html += '</table>'

    return left_block, totals_html