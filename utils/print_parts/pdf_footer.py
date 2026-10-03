from utils.print_parts.helpers import format_currency
from utils.print_parts.footer_top import get_top_blocks
from utils.print_parts.footer_bottom import get_bottom_blocks

def build_footer(ctx, get_css, pg_num, is_last, curr_page_disp, running_total):
    studio = ctx["studio"]
    curr_format = studio.settings.get("currency_format", "Indian Rupees (₹)")
    dynamic_bottom_px = ctx.get("dynamic_bottom_px", 300) + 40
    cw_amt = float(studio.settings.get("col_widths", {}).get("amt", 14))
    
    css_tr_part = get_css('tr_part')
    css_tr_amt = get_css('tr_amt')
    css_page_no = get_css("page_no")

    html = ""
    
    if not is_last:
        f_tot = format_currency(running_total, curr_format)
        html += f"""
        <table class="invoice-table" style="border-top: 0.75pt solid #000; border-bottom: 0.75pt solid #000;">
            <tr>
                <td style="text-align: right; {css_tr_part} font-weight: bold; padding-right: 15px;">Total :</td>
                <td class="shrink-fit" style="text-align: right; {css_tr_amt} font-weight: bold; width: {cw_amt}%; border-left: 0.75pt solid #000;">{f_tot}</td>
            </tr>
        </table>
        </div> <!-- CLOSES table-wrapper -->
        
        <div class="footer-section" style="flex-shrink: 0; position: relative; min-height: 25px; margin-top: 5px;">
            <div style="position: absolute; bottom: 0; left: 0; right: 0; text-align: center;">
                <span style="{css_page_no} line-height: 1; margin: 0; padding: 0;">Page {curr_page_disp}</span>
            </div>
            <div style="position: absolute; bottom: 0; right: 0; text-align: right; font-style: italic; {css_tr_part}">
                continued ...
            </div>
        </div>
        """
        return html

    html += f"""
    </div> <!-- CLOSES table-wrapper -->
    """

    top_left_html, totals_html = get_top_blocks(ctx, get_css, curr_format)
    terms_html, page_no_html, sig_html = get_bottom_blocks(ctx, get_css, curr_page_disp)

    # THE FIX: Secure footer section. Provides the top-border (horizontal line) and anchors to bottom.
    html += f"""
    <div class="footer-section" style="flex-shrink: 0; position: relative; height: {int(dynamic_bottom_px)}px; background-color: #ffffff; box-sizing: border-box; border-top: 0.75pt solid #000;">
        
        <div style="position: absolute; top: 5px; left: 0; right: 0;">
            <div style="display: flex; justify-content: space-between; width: 100%;">
                <div style="width: 55%; margin: 0; padding: 0;">
                    {top_left_html}
                </div>
                <div style="width: 45%; margin: 0; padding: 0;">
                    {totals_html}
                </div>
            </div>
        </div>

        <div style="position: absolute; bottom: 0; left: 0; right: 0; text-align: center; z-index: 0;">
            {page_no_html}
        </div>

        <div style="position: absolute; bottom: 0; left: 0; width: 45%; margin: 0; padding: 0; z-index: 1;">
            {terms_html}
        </div>

        <div style="position: absolute; bottom: 0; right: 0; width: 45%; display: flex; justify-content: flex-end; margin: 0; padding: 0; z-index: 1;">
            {sig_html}
        </div>
        
    </div>
    """
    return html