import tkinter as tk
from tkinter import ttk, messagebox
import time
from utils.smart_alerts import get_system_alerts
from views.home_parts.security import prompt_company_pin

class AlertsManager:
    def __init__(self, home_view):
        self.home = home_view
        self.app = home_view.app
        self.window = None
        self.last_close = 0
        self.alert_cards_ref = []
        self.current_idx = -1
        self.alerts_data = []

    def toggle_panel(self):
        now = time.time()
        if now - self.last_close < 0.2:
            return 

        if self.window and self.window.winfo_exists():
            self.window.destroy()
            return

        raw_alerts = get_system_alerts()
        uid = getattr(self.app, "current_user_id", 1) or 1
        if str(uid) != "1":
            import database
            perms = database.get_user_permissions(uid)
            allowed_comps = perms.get("companies", "all")
            allowed_tabs = perms.get("sidebars", "all")
            allowed_comp_set = {int(x) for x in allowed_comps} if isinstance(allowed_comps, list) else None

            self.alerts_data = [
                a for a in raw_alerts
                if (allowed_comp_set is None or int(a.get("cid", 0)) in allowed_comp_set)
                and (allowed_tabs == "all" or a.get("target_tab") in allowed_tabs)
            ]
        else:
            self.alerts_data = raw_alerts

        if not self.alerts_data:
            messagebox.showinfo("All Clear!", "You have no system warnings right now.", parent=self.home)
            return

        colors = self.home.colors
        self.window = tk.Toplevel(self.home)
        self.window.overrideredirect(True) 
        self.window.configure(bg=colors["bg"], highlightthickness=1, highlightbackground=colors["border"])
        
        self.home.update_idletasks()
        btn_bell = self.home.btn_bell
        x = btn_bell.master.winfo_rootx() - 320 + btn_bell.master.winfo_width()
        y = btn_bell.master.winfo_rooty() + btn_bell.master.winfo_height() + 6
        self.window.geometry(f"340x420+{x}+{y}")
        
        self.window.bind("<Destroy>", lambda e: self.home.focus_set())
        
        def on_focus_out(e):
            mx, my = self.window.winfo_pointerxy()
            bx, by = btn_bell.master.winfo_rootx(), btn_bell.master.winfo_rooty()
            bw, bh = btn_bell.master.winfo_width(), btn_bell.master.winfo_height()
            if bx <= mx <= bx + bw and by <= my <= by + bh: return 
            self.window.destroy()
            
        self.window.bind("<FocusOut>", on_focus_out)

        tk.Label(self.window, text="Actionable Alerts", font=("Arial", 12, "bold"), bg=colors["bg"], fg=colors["text"]).pack(pady=10)
        
        style = ttk.Style()
        style.theme_use('default')
        style.configure("Alert.Vertical.TScrollbar", background=colors["sec"], troughcolor=colors["bg"], bordercolor=colors["bg"], arrowcolor=colors["text"], relief="flat")
        style.map("Alert.Vertical.TScrollbar", background=[("active", colors["accent_blue"])])
        
        canvas = tk.Canvas(self.window, bg=colors["bg"], highlightthickness=0)
        scroll = ttk.Scrollbar(self.window, orient="vertical", command=canvas.yview, style="Alert.Vertical.TScrollbar")
        frame = tk.Frame(canvas, bg=colors["bg"], highlightthickness=0)
        
        scroll.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        canvas.configure(yscrollcommand=scroll.set) 
        
        window_id = canvas.create_window((0, 0), window=frame, anchor="nw")
        def _configure_canvas(event):
            canvas.itemconfig(window_id, width=event.width)
            canvas.configure(scrollregion=canvas.bbox("all"))
        canvas.bind("<Configure>", _configure_canvas)
        frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        
        def _on_mousewheel(event): canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        self.window.bind("<Enter>", lambda e: self.window.bind_all("<MouseWheel>", _on_mousewheel))
        self.window.bind("<Leave>", lambda e: self.window.unbind_all("<MouseWheel>"))

        self.alert_cards_ref.clear()
        self.current_idx = -1

        def update_selection():
            for i, (c, i_lbl, m_lbl, _) in enumerate(self.alert_cards_ref):
                bg_color = colors["card_hover"] if i == self.current_idx else colors["card"]
                c.config(bg=bg_color)
                i_lbl.config(bg=bg_color)
                m_lbl.config(bg=bg_color)
                
                if i == self.current_idx:
                    frame.update_idletasks()
                    c_top = c.winfo_y()
                    c_bottom = c_top + c.winfo_height()
                    canvas_height = canvas.winfo_height()
                    bbox = canvas.bbox("all")
                    total_height = bbox[3] - bbox[1] if bbox else canvas_height
                    view_top = canvas.yview()[0] * total_height
                    view_bottom = canvas.yview()[1] * total_height
                    if c_top < view_top: canvas.yview_moveto(c_top / total_height)
                    elif c_bottom > view_bottom: canvas.yview_moveto((c_bottom - canvas_height) / total_height)

        def execute_alert(idx):
            if 0 <= idx < len(self.alert_cards_ref):
                _, _, _, alert = self.alert_cards_ref[idx]
                cid, pin, target, ref = alert['cid'], alert['cpin'], alert['target_tab'], alert.get('reference')
                self.window.destroy()
                self.app.pending_highlight = ref 
                self.home.grid_manager.execute_card_click(cid, pin, target) 

        self.window.bind("<Up>", lambda e: [setattr(self, 'current_idx', max(0, self.current_idx - 1)), update_selection()])
        self.window.bind("<Down>", lambda e: [setattr(self, 'current_idx', min(len(self.alert_cards_ref) - 1, self.current_idx + 1)), update_selection()])
        self.window.bind("<Return>", lambda e: execute_alert(self.current_idx) if self.current_idx >= 0 else None)
        
        # --- FIX: ESCAPE KEY CLOSES ALERT WINDOW SAFELY ---
        self.window.bind("<Escape>", lambda e: [self.window.destroy(), self.home.focus_set()])

        def on_window_leave(e):
            x, y = self.window.winfo_pointerxy()
            wx, wy = self.window.winfo_rootx(), self.window.winfo_rooty()
            ww, wh = self.window.winfo_width(), self.window.winfo_height()
            if not (wx <= x <= wx + ww and wy <= y <= wy + wh):
                self.current_idx = -1
                update_selection()
        self.window.bind("<Leave>", on_window_leave)

        for i, alert in enumerate(self.alerts_data):
            card = tk.Frame(frame, bg=colors["card"], padx=10, pady=10, cursor="hand2", highlightthickness=1, highlightbackground=colors["border"])
            card.pack(fill="x", padx=5, pady=(0, 10))
            
            lbl_icon = tk.Label(card, text=f"{alert['icon']} [{alert['cname']}]", font=("Arial", 9, "bold"), bg=colors["card"], fg="#3b82f6")
            lbl_icon.pack(anchor="w")
            lbl_msg = tk.Label(card, text=alert['msg'], font=("Arial", 9), bg=colors["card"], fg=colors["text"], wraplength=280, justify="left")
            lbl_msg.pack(anchor="w", pady=(5,0))
            
            self.alert_cards_ref.append((card, lbl_icon, lbl_msg, alert))
            
            def make_hover(idx):
                def on_enter(e):
                    self.current_idx = idx
                    update_selection()
                return on_enter
            
            enter_fn = make_hover(i)
            card.bind("<Enter>", enter_fn); lbl_icon.bind("<Enter>", enter_fn); lbl_msg.bind("<Enter>", enter_fn)
            click_fn = lambda e, idx=i: execute_alert(idx)
            card.bind("<Button-1>", click_fn); lbl_icon.bind("<Button-1>", click_fn); lbl_msg.bind("<Button-1>", click_fn)

        self.window.focus_force()