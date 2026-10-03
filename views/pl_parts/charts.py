import tkinter as tk
from datetime import datetime
import sys
import os

# --- THE FIX: Bulletproof Executable Pathing ---
if getattr(sys, 'frozen', False):
    parent_dir = os.path.dirname(sys.executable)
else:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(os.path.dirname(current_dir))

if parent_dir not in sys.path:
    sys.path.append(parent_dir)
# -----------------------------------------------

import database
from views.invoice_parts.helpers import format_currency

class PLChartManager:
    def __init__(self, view):
        self.view = view
        self.chart_data = view.chart_data
        self.curr_fmt = view.curr_fmt
        
        # --- THE FIX: Live Theme Injection ---
        self.is_dark = database.get_ui_setting("dark_mode", "1") == "1"
        self.BG_COLOR = "#0f172a" if self.is_dark else "#e0f2fe"
        self.CARD_BG = "#1e293b" if self.is_dark else "#f0f9ff"
        self.BORDER_COLOR = "#334155" if self.is_dark else "#7dd3fc"
        self.TEXT_PRIMARY = "#f8fafc" if self.is_dark else "#0f172a"
        self.TEXT_SECONDARY = "#94a3b8" if self.is_dark else "#0284c7"
        self.ACCENT_BLUE = "#3b82f6" if self.is_dark else "#0ea5e9"
        self.ACCENT_YELLOW = "#f59e0b"
        self.ACCENT_RED = "#ef4444"
        self.ACCENT_GREEN = "#10b981"
        
        self.pop = tk.Toplevel(view)
        self.pop.title("Financial Visualizer")
        self.pop.geometry("850x650")
        self.pop.configure(bg=self.BG_COLOR)
        self.pop.grab_set()

        nav_f = tk.Frame(self.pop, bg=self.BG_COLOR)
        nav_f.pack(fill="x", padx=20, pady=(20, 10))

        # Main Tabs (Left side)
        tabs_f = tk.Frame(nav_f, bg=self.CARD_BG, highlightbackground=self.BORDER_COLOR, highlightthickness=1)
        tabs_f.pack(side="left")

        self.btn_exp = tk.Button(tabs_f, text="Expenses", font=("Arial", 10, "bold"), bg=self.BORDER_COLOR, fg=self.TEXT_PRIMARY, relief="flat", bd=0, padx=15, pady=6, cursor="hand2", command=lambda: self.switch_main("Expenses"))
        self.btn_rev = tk.Button(tabs_f, text="Revenue", font=("Arial", 10), bg=self.CARD_BG, fg=self.TEXT_SECONDARY, relief="flat", bd=0, padx=15, pady=6, cursor="hand2", command=lambda: self.switch_main("Revenue"))
        self.btn_trend = tk.Button(tabs_f, text="Profit Trend", font=("Arial", 10), bg=self.CARD_BG, fg=self.TEXT_SECONDARY, relief="flat", bd=0, padx=15, pady=6, cursor="hand2", command=lambda: self.switch_main("Trend"))

        self.btn_exp.pack(side="left")
        self.btn_rev.pack(side="left")
        self.btn_trend.pack(side="left")

        # Dynamic Sub-Toggle (Right side)
        self.toggle_f = tk.Frame(nav_f, bg=self.CARD_BG, highlightbackground=self.BORDER_COLOR, highlightthickness=1)
        
        self.btn_sub1 = tk.Button(self.toggle_f, font=("Arial", 10, "bold"), bg=self.BORDER_COLOR, fg=self.TEXT_PRIMARY, relief="flat", bd=0, padx=12, pady=6, cursor="hand2")
        self.btn_sub2 = tk.Button(self.toggle_f, font=("Arial", 10), bg=self.CARD_BG, fg=self.TEXT_SECONDARY, relief="flat", bd=0, padx=12, pady=6, cursor="hand2")

        self.btn_sub1.pack(side="left")
        self.btn_sub2.pack(side="left")

        self.canvas_f = tk.Frame(self.pop, bg=self.BG_COLOR)
        self.canvas_f.pack(fill="both", expand=True, padx=20, pady=10)

        self.colors = ["#ef4444", "#f59e0b", "#3b82f6", "#10b981", "#8b5cf6", "#ec4899", "#14b8a6", "#6366f1", "#f97316", "#0ea5e9", "#f43f5e"]

        self.active_tab = "Expenses"
        self.sub_mode = "Option1"
        self.switch_main("Expenses")

    def switch_main(self, tab):
        self.active_tab = tab
        for b in [self.btn_exp, self.btn_rev, self.btn_trend]:
            b.config(bg=self.CARD_BG, fg=self.TEXT_SECONDARY, font=("Arial", 10))
            
        # --- THE FIX: Removed corrupted Unicode characters from the buttons! ---
        if tab == "Expenses":
            self.btn_exp.config(bg=self.BORDER_COLOR, fg=self.TEXT_PRIMARY, font=("Arial", 10, "bold"))
            self.btn_sub1.config(text="🍩 Donut", command=lambda: self.switch_sub("Option1"))
            self.btn_sub2.config(text="📊 Bar", command=lambda: self.switch_sub("Option2"))
            self.toggle_f.pack(side="right")
            
        elif tab == "Revenue":
            self.btn_rev.config(bg=self.BORDER_COLOR, fg=self.TEXT_PRIMARY, font=("Arial", 10, "bold"))
            self.btn_sub1.config(text="🍩 Donut", command=lambda: self.switch_sub("Option1"))
            self.btn_sub2.config(text="📊 Bar", command=lambda: self.switch_sub("Option2"))
            self.toggle_f.pack(side="right")
            
        elif tab == "Trend":
            self.btn_trend.config(bg=self.BORDER_COLOR, fg=self.TEXT_PRIMARY, font=("Arial", 10, "bold"))
            self.btn_sub1.config(text="📈 Line", command=lambda: self.switch_sub("Option1"))
            self.btn_sub2.config(text="📊 Bar", command=lambda: self.switch_sub("Option2"))
            self.toggle_f.pack(side="right")
        # -----------------------------------------------------------------------

        self.switch_sub("Option1") 

    def switch_sub(self, mode):
        self.sub_mode = mode
        if mode == "Option1":
            self.btn_sub1.config(bg=self.BORDER_COLOR, fg=self.TEXT_PRIMARY, font=("Arial", 10, "bold"))
            self.btn_sub2.config(bg=self.CARD_BG, fg=self.TEXT_SECONDARY, font=("Arial", 10))
        else:
            self.btn_sub2.config(bg=self.BORDER_COLOR, fg=self.TEXT_PRIMARY, font=("Arial", 10, "bold"))
            self.btn_sub1.config(bg=self.CARD_BG, fg=self.TEXT_SECONDARY, font=("Arial", 10))
        self.draw_active_chart()

    def clear_canvas(self):
        for widget in self.canvas_f.winfo_children():
            widget.destroy()

    def draw_active_chart(self):
        self.clear_canvas()
        
        if self.active_tab == "Expenses":
            data = {}
            if self.chart_data.get("COGS", 0) > 0: data["Direct Costs (COGS)"] = self.chart_data["COGS"]
            for cat, amt in self.chart_data.get("OPEX", {}).items():
                if amt > 0: data[cat] = amt
            if not data:
                tk.Label(self.canvas_f, text="No expense data available.", font=("Arial", 12), bg=self.BG_COLOR, fg=self.TEXT_SECONDARY).pack(pady=50)
                return
            if self.sub_mode == "Option1": self.draw_donut(data, "Total\nCosts")
            else: self.draw_bar(data, "Expense Breakdown")

        elif self.active_tab == "Revenue":
            raw_data = self.chart_data.get("REVENUE", {})
            if not raw_data:
                tk.Label(self.canvas_f, text="No revenue data available.", font=("Arial", 12), bg=self.BG_COLOR, fg=self.TEXT_SECONDARY).pack(pady=50)
                return
            
            sorted_rev = sorted(raw_data.items(), key=lambda i: i[1], reverse=True)
            data = {}
            if len(sorted_rev) > 10:
                for k, v in sorted_rev[:9]: data[k] = v
                data["Other Clients"] = sum(i[1] for i in sorted_rev[9:])
            else:
                for k, v in sorted_rev: data[k] = v

            if self.sub_mode == "Option1": self.draw_donut(data, "Total\nRevenue")
            else: self.draw_bar(data, "Top Revenue Sources")

        elif self.active_tab == "Trend":
            trends = self.chart_data.get("TREND", {})
            if len(trends) < 2:
                tk.Label(self.canvas_f, text="Not enough months to plot a trend.\nTry selecting 'All Years' in the filter.", font=("Arial", 12), bg=self.BG_COLOR, fg=self.TEXT_SECONDARY).pack(pady=50)
                return
            
            if self.sub_mode == "Option1": self.draw_trend_line(trends)
            else: self.draw_trend_bar(trends)

    def draw_donut(self, data, center_text):
        total_val = sum(data.values())
        sorted_data = sorted(data.items(), key=lambda i: i[1], reverse=True)

        c = tk.Canvas(self.canvas_f, width=320, height=320, bg=self.BG_COLOR, highlightthickness=0)
        c.pack(side="left", padx=20)
        legend_f = tk.Frame(self.canvas_f, bg=self.BG_COLOR)
        legend_f.pack(side="left", fill="both", expand=True, padx=20, pady=20)
        
        start_angle = 0
        for idx, (cat, amt) in enumerate(sorted_data):
            pct = (amt / total_val) * 100
            extent = (amt / total_val) * 360
            color = self.colors[idx % len(self.colors)]
            
            if extent >= 359.9: c.create_oval(10, 10, 310, 310, fill=color, outline="")
            else: c.create_arc(10, 10, 310, 310, start=start_angle, extent=extent, fill=color, outline="", style=tk.PIESLICE)
            start_angle += extent
            
            row = tk.Frame(legend_f, bg=self.BG_COLOR)
            row.pack(fill="x", pady=5)
            # --- THE FIX: Cleaned up the corrupted legend bullet point! ---
            tk.Label(row, text="●", font=("Arial", 16), fg=color, bg=self.BG_COLOR).pack(side="left")
            # --------------------------------------------------------------
            tk.Label(row, text=f"{str(cat)[:20]} ({pct:.1f}%)", font=("Arial", 11, "bold"), fg=self.TEXT_PRIMARY, bg=self.BG_COLOR).pack(side="left", padx=5)
            tk.Label(row, text=format_currency(amt, self.curr_fmt), font=("Arial", 11), fg=self.TEXT_SECONDARY, bg=self.BG_COLOR).pack(side="right")
            
        c.create_oval(100, 100, 220, 220, fill=self.BG_COLOR, outline=self.BG_COLOR)
        c.create_text(160, 150, text=center_text, font=("Arial", 12, "bold"), fill=self.TEXT_SECONDARY, justify="center")

    def draw_bar(self, data, title):
        total_val = sum(data.values())
        sorted_data = sorted(data.items(), key=lambda i: i[1], reverse=True)
        max_val = sorted_data[0][1]

        tk.Label(self.canvas_f, text=title, font=("Arial", 14, "bold"), bg=self.BG_COLOR, fg=self.TEXT_PRIMARY).pack(anchor="w", pady=(0, 10))

        scroll_f = tk.Frame(self.canvas_f, bg=self.BG_COLOR)
        scroll_f.pack(fill="both", expand=True)
        c = tk.Canvas(scroll_f, width=700, height=max(300, len(sorted_data)*45+50), bg=self.BG_COLOR, highlightthickness=0)
        c.pack(fill="both", expand=True)

        y_offset = 20
        for idx, (cat, amt) in enumerate(sorted_data):
            color = self.colors[idx % len(self.colors)]
            pct = (amt / total_val) * 100
            c.create_text(220, y_offset+10, text=f"{str(cat)[:25]} ({pct:.1f}%)", fill=self.TEXT_PRIMARY, font=("Arial", 10, "bold"), anchor="e")
            bar_width = (amt / max_val) * 300
            c.create_rectangle(235, y_offset, 235 + bar_width, y_offset + 20, fill=color, outline="")
            c.create_text(245 + bar_width, y_offset+10, text=format_currency(amt, self.curr_fmt), fill=self.TEXT_SECONDARY, font=("Arial", 10), anchor="w")
            y_offset += 40

    def draw_trend_line(self, trends):
        sorted_months = sorted(trends.keys())
        profits = []
        for m in sorted_months:
            profits.append((m, trends[m]["Inc"] - trends[m]["Exp"]))

        max_p = max(p[1] for p in profits)
        min_p = min(0, min(p[1] for p in profits)) 
        spread = max_p - min_p
        if spread == 0: spread = 1
        
        c_width, c_height = 700, 400
        margin_x, margin_y = 60, 40

        tk.Label(self.canvas_f, text="Net Profit Trend (Line)", font=("Arial", 14, "bold"), bg=self.BG_COLOR, fg=self.TEXT_PRIMARY).pack(anchor="w", pady=(0, 10))
        
        c = tk.Canvas(self.canvas_f, width=c_width, height=c_height, bg=self.BG_COLOR, highlightthickness=0)
        c.pack(fill="both", expand=True, pady=10)

        zero_y = c_height - margin_y - ((0 - min_p) / spread) * (c_height - margin_y * 2)
        c.create_line(margin_x, zero_y, c_width-margin_x, zero_y, fill=self.BORDER_COLOR, dash=(4,4))

        points = []
        x_step = (c_width - margin_x * 2) / (len(profits) - 1)
        
        for i, (m_key, net) in enumerate(profits):
            x = margin_x + (i * x_step)
            y = c_height - margin_y - ((net - min_p) / spread) * (c_height - margin_y * 2)
            points.append((x, y))
            
            try: m_lbl = datetime.strptime(m_key, "%Y-%m").strftime("%b '%y")
            except: m_lbl = m_key
            c.create_text(x, c_height - margin_y + 15, text=m_lbl, fill=self.TEXT_SECONDARY, font=("Arial", 9))
            
            val_color = self.ACCENT_GREEN if net >= 0 else self.ACCENT_RED
            c.create_text(x, y - 15, text=format_currency(net, self.curr_fmt), fill=val_color, font=("Arial", 9, "bold"))
            c.create_oval(x-5, y-5, x+5, y+5, fill=val_color, outline=self.BG_COLOR, width=2)

        for i in range(len(points)-1):
            x1, y1 = points[i]
            x2, y2 = points[i+1]
            c.create_line(x1, y1, x2, y2, fill=self.ACCENT_BLUE, width=3)

    def draw_trend_bar(self, trends):
        sorted_months = sorted(trends.keys())
        profits = []
        for m in sorted_months:
            profits.append((m, trends[m]["Inc"] - trends[m]["Exp"]))

        max_p = max(abs(p[1]) for p in profits) 
        if max_p == 0: max_p = 1
        
        c_width, c_height = 700, 400
        margin_x, margin_y = 60, 40
        
        tk.Label(self.canvas_f, text="Net Profit Trend (Bar)", font=("Arial", 14, "bold"), bg=self.BG_COLOR, fg=self.TEXT_PRIMARY).pack(anchor="w", pady=(0, 10))
        
        c = tk.Canvas(self.canvas_f, width=c_width, height=c_height, bg=self.BG_COLOR, highlightthickness=0)
        c.pack(fill="both", expand=True, pady=10)

        zero_y = c_height / 2
        c.create_line(margin_x, zero_y, c_width-margin_x, zero_y, fill=self.BORDER_COLOR, dash=(4,4))

        x_step = (c_width - margin_x * 2) / len(profits)
        bar_w = min(x_step * 0.6, 40) 
        
        for i, (m_key, net) in enumerate(profits):
            x_center = margin_x + (i * x_step) + (x_step / 2)
            bar_h = (abs(net) / max_p) * ((c_height/2) - margin_y)
            
            val_color = self.ACCENT_GREEN if net >= 0 else self.ACCENT_RED
            
            if net >= 0:
                y1 = zero_y - bar_h
                y2 = zero_y
                lbl_y = y1 - 10
            else:
                y1 = zero_y
                y2 = zero_y + bar_h
                lbl_y = y2 + 10
                
            c.create_rectangle(x_center - bar_w/2, y1, x_center + bar_w/2, y2, fill=val_color, outline="")
            
            try: m_lbl = datetime.strptime(m_key, "%Y-%m").strftime("%b '%y")
            except: m_lbl = m_key
            
            c.create_text(x_center, c_height - 15, text=m_lbl, fill=self.TEXT_SECONDARY, font=("Arial", 9))
            c.create_text(x_center, lbl_y, text=format_currency(net, self.curr_fmt), fill=val_color, font=("Arial", 8, "bold"))