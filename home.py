import tkinter as tk
import os
import sys
import time
import database

# --- THE FIX: Bulletproof Executable Pathing ---
if getattr(sys, 'frozen', False):
    parent_dir = os.path.dirname(sys.executable)
else:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)

if parent_dir not in sys.path:
    sys.path.append(parent_dir)
# -----------------------------------------------

from views.home_parts.data_transfer_ui import trigger_import, open_export_popup
from views.home_parts.company_forms import open_create_popup, open_edit_popup
from utils.smart_alerts import get_system_alerts

# THE FIX: Imported the centralized theme engine!
from views.home_parts.ui_components import add_hover, create_perfect_button, get_theme
from views.home_parts.alerts_manager import AlertsManager
from views.home_parts.company_grid import CompanyGridManager
from views.home_parts.tab_users import open_security_manager

class HomeView(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, highlightthickness=0, bd=0)
        self.app = self.winfo_toplevel()
        
        self.sort_var = tk.StringVar(value="Alphabetical (A-Z)")
        self.sort_window = None
        self.last_sort_close = 0
        
        self.grid_manager = CompanyGridManager(self)
        self.alerts_manager = AlertsManager(self)
        
        self.app.bind("<Control-n>", lambda e: open_create_popup(self) if getattr(self.app, "current_role", "") == "Admin" else None)
        
        self.nav_zone = "grid" 
        self.header_idx = 0
        self.header_elements = []

        self.config(takefocus=True)
        self.bind("<Up>", self.nav_up)
        self.bind("<Down>", self.nav_down)
        self.bind("<Left>", self.nav_left)
        self.bind("<Right>", self.nav_right)
        self.bind("<Return>", self.nav_enter)
        self.bind("<Escape>", self.nav_escape) 
        self.bind("<Button-1>", lambda e: self.focus_set())

        self.build_ui()

    def build_ui(self):
        for widget in self.winfo_children(): widget.destroy()
            
        # THE FIX: Calling the universal theme engine
        self.colors = get_theme()
        self.config(bg=self.colors["bg"])
        
        title_frame = tk.Frame(self, bg=self.colors["bg"], highlightthickness=0)
        title_frame.pack(fill="x", pady=(30, 0))
        title_frame.bind("<Button-1>", lambda e: self.focus_set())
        tk.Label(title_frame, text="Home", font=("Segoe UI", 24, "bold"), bg=self.colors["bg"], fg=self.colors["text"]).pack(side="left")

        self.header = tk.Frame(self, bg=self.colors["bg"], highlightthickness=0)
        self.header.pack(fill="x", pady=(20, 10))
        self.header.bind("<Button-1>", lambda e: self.focus_set())
        tk.Label(self.header, text="Command Center", font=("Segoe UI", 16, "bold"), bg=self.colors["bg"], fg=self.colors["text"]).pack(side="left")
        
        self.sort_outer = tk.Frame(self.header, bg=self.colors["border"], padx=1, pady=1, cursor="hand2")
        self.sort_outer.pack(side="left", padx=20)
        
        self.sort_inner = tk.Frame(self.sort_outer, bg=self.colors["btn"], cursor="hand2")
        self.sort_inner.pack(fill="both", expand=True)

        self.lbl_sort = tk.Label(self.sort_inner, textvariable=self.sort_var, bg=self.colors["btn"], fg=self.colors["text"], font=("Segoe UI", 10, "bold"), width=18, anchor="w", cursor="hand2")
        self.lbl_sort.pack(side="left", padx=(10, 5), pady=4)
        self.lbl_arrow = tk.Label(self.sort_inner, text="▼", bg=self.colors["btn"], fg=self.colors["text_sec"], font=("Segoe UI", 8), cursor="hand2")
        self.lbl_arrow.pack(side="right", padx=(0, 10))
        
        def on_sort_enter(e):
            if self.nav_zone == "header" and self.header_idx == 0: return
            self.sort_inner.config(bg=self.colors["btn_hover"]); self.lbl_sort.config(bg=self.colors["btn_hover"]); self.lbl_arrow.config(bg=self.colors["btn_hover"])
        def on_sort_leave(e):
            if self.nav_zone == "header" and self.header_idx == 0: return
            self.sort_inner.config(bg=self.colors["btn"]); self.lbl_sort.config(bg=self.colors["btn"]); self.lbl_arrow.config(bg=self.colors["btn"])
            
        self.sort_outer.bind("<Enter>", on_sort_enter); self.sort_outer.bind("<Leave>", on_sort_leave)
        self.lbl_sort.bind("<Enter>", on_sort_enter); self.lbl_arrow.bind("<Enter>", on_sort_enter)
        self.lbl_sort.bind("<Button-1>", self.toggle_custom_sort_menu); self.lbl_arrow.bind("<Button-1>", self.toggle_custom_sort_menu); self.sort_inner.bind("<Button-1>", self.toggle_custom_sort_menu)

        self.alerts = get_system_alerts()
        bell_text = "🔔" if not self.alerts else f"🔔 ({len(self.alerts)})"
        bell_fg = self.colors["text_sec"] if not self.alerts else "#ef4444"
        
        bell_frame, self.btn_bell = create_perfect_button(self.header, bell_text, ("Segoe UI", 10, "bold"), bell_fg, self.colors["btn"], self.colors["btn_hover"], self.colors["border"], self.alerts_manager.toggle_panel)
        bell_frame.pack(side="right", padx=(10, 0))

        is_dark = database.get_ui_setting("dark_mode", "1") == "1"
        theme_txt = "☾ Dark Mode" if is_dark else "☀ Light Mode"
        theme_color = "#60a5fa" if is_dark else "#0ea5e9" 
        
        is_admin = getattr(self.app, "current_role", "") == "Admin"

        # --- THE FIX: Crisp Vector Exit Icon ([➔) for Log Out ---
        logout_frame, self.btn_logout = create_perfect_button(self.header, "⏻ Log Out", ("Segoe UI", 10, "bold"), self.colors["error"], self.colors["btn"], self.colors["btn_hover"], self.colors["border"], lambda: self.app.switch_view("Logout"))
        try:
            from PIL import Image, ImageTk, ImageDraw
            scale = 4
            sz = 16 * scale
            img = Image.new("RGBA", (sz, sz), (0, 0, 0, 0))
            d = ImageDraw.Draw(img)
            c = self.colors["error"]
            w = 7
            # 1. Left door bracket [
            d.line([(22, 8), (8, 8), (8, 56), (22, 56)], fill=c, width=w, joint="curve")
            # 2. Horizontal exit arrow shaft ─
            d.line([(20, 32), (54, 32)], fill=c, width=w)
            # 3. Arrowhead ❯
            d.line([(40, 18), (56, 32), (40, 46)], fill=c, width=w, joint="curve")
            resamp = Image.Resampling.LANCZOS if hasattr(Image, "Resampling") else Image.LANCZOS
            self.logout_icon_img = ImageTk.PhotoImage(img.resize((16, 16), resamp))
            self.btn_logout.config(text="  Log Out", image=self.logout_icon_img, compound="left")
        except Exception:
            pass
        logout_frame.pack(side="right", padx=(10, 0))

        # --- Active User Profile Pill Aligned with "Home" Label (Read-Only) ---
        uid = getattr(self.app, "current_user_id", 1) or 1
        u_row = database.get_user_by_id(uid)
        u_name = u_row[1] if u_row else (getattr(self.app, "current_user", "Admin") or "Admin")
        u_role = u_row[3] if u_row else (getattr(self.app, "current_role", "Admin") or "Admin")
        u_pic = u_row[4] if (u_row and len(u_row) > 4 and u_row[4]) else ""

        home_font = ("Segoe UI", 24, "bold")
        home_padx = self.header.pack_info().get("padx", 0)
        home_pady = (20, 10)
        for w in list(self.winfo_children()):
            if isinstance(w, tk.Label) and "Home" in str(w.cget("text")):
                home_font = w.cget("font")
                p_info = w.pack_info()
                home_padx = p_info.get("padx", home_padx)
                home_pady = p_info.get("pady", home_pady)
                w.destroy()
                break
            elif isinstance(w, tk.Frame) and w != self.header:
                for child in list(w.winfo_children()):
                    if isinstance(child, tk.Label) and "Home" in str(child.cget("text")):
                        home_font = child.cget("font")
                        p_info = w.pack_info()
                        home_padx = p_info.get("padx", home_padx)
                        home_pady = p_info.get("pady", home_pady)
                        w.destroy()
                        break

        title_row = tk.Frame(self, bg=self.colors["bg"])
        title_row.pack(before=self.header, fill="x", padx=home_padx, pady=home_pady)

        tk.Label(title_row, text="Home", font=home_font, bg=self.colors["bg"], fg=self.colors["text"]).pack(side="left", anchor="w")

        user_frame = tk.Frame(title_row, bg=self.colors["border"], padx=1, pady=1)
        self.btn_user_badge = tk.Label(
            user_frame, text=f"👤 {u_name} • {u_role}", font=("Segoe UI", 10, "bold"),
            bg=self.colors["btn"], fg=self.colors["accent_blue"], padx=14, pady=4
        )
        self.btn_user_badge.pack(expand=True, fill="both")
        try:
            from PIL import Image, ImageTk, ImageDraw
            scale = 4
            sz = 20
            resamp = Image.Resampling.LANCZOS if hasattr(Image, "Resampling") else Image.LANCZOS
            if u_pic and os.path.exists(u_pic):
                im = Image.open(u_pic).convert("RGBA").resize((sz, sz), resamp)
                mask = Image.new("L", (sz * scale, sz * scale), 0)
                ImageDraw.Draw(mask).ellipse((0, 0, sz * scale - 1, sz * scale - 1), fill=255)
                mask = mask.resize((sz, sz), resamp)
                out = Image.new("RGBA", (sz, sz), (0, 0, 0, 0))
                out.paste(im, (0, 0), mask)
                self.user_pill_img = ImageTk.PhotoImage(out)
                self.btn_user_badge.config(text=f"  {u_name} • {u_role}", image=self.user_pill_img, compound="left")
        except Exception:
            pass
        user_frame.pack(side="right", anchor="e")
        
        if is_admin:
            security_frame, self.btn_security = create_perfect_button(self.header, "⚙️ Users & Security", ("Segoe UI", 10, "bold"), self.colors["text"], self.colors["btn"], self.colors["btn_hover"], self.colors["border"], lambda: open_security_manager(self))
            security_frame.pack(side="right", padx=(10, 0))
        # --------------------------------------------------------------------

        theme_frame, self.btn_theme = create_perfect_button(self.header, theme_txt, ("Segoe UI", 10, "bold"), theme_color, self.colors["btn"], self.colors["btn_hover"], self.colors["border"], self.toggle_theme)
        theme_frame.pack(side="right", padx=(10, 0))

        if is_admin:
            add_frame, self.btn_add = create_perfect_button(self.header, "+ Create Company", ("Segoe UI", 10, "bold"), "#ffffff", "#10b981", "#059669", "#10b981", lambda: open_create_popup(self))
            add_frame.pack(side="right", padx=(10, 0))

            export_frame, self.btn_export = create_perfect_button(self.header, "⭱ Export", ("Segoe UI", 10, "bold"), self.colors["text"], self.colors["btn"], self.colors["btn_hover"], self.colors["border"], lambda: open_export_popup(self))
            export_frame.pack(side="right", padx=(10, 0))

            import_frame, self.btn_import = create_perfect_button(self.header, "⭳ Import", ("Segoe UI", 10, "bold"), self.colors["text"], self.colors["btn"], self.colors["btn_hover"], self.colors["border"], lambda: trigger_import(self))
            import_frame.pack(side="right", padx=(10, 0))

        self.divider = tk.Frame(self, bg=self.colors["border"], height=1)
        self.divider.pack(fill="x", padx=20, pady=(0, 20)) 

        self.header_elements = [
            {
                "hl": lambda: [self.sort_inner.config(bg=self.colors["btn_hover"]), self.lbl_sort.config(bg=self.colors["btn_hover"]), self.lbl_arrow.config(bg=self.colors["btn_hover"])],
                "uhl": lambda: [self.sort_inner.config(bg=self.colors["btn"]), self.lbl_sort.config(bg=self.colors["btn"]), self.lbl_arrow.config(bg=self.colors["btn"])],
                "action": self.toggle_custom_sort_menu
            }
        ]
        if is_admin:
            self.header_elements.extend([
                {"hl": lambda: self.btn_import.config(bg=self.colors["btn_hover"]), "uhl": lambda: self.btn_import.config(bg=self.colors["btn"]), "action": lambda: trigger_import(self)},
                {"hl": lambda: self.btn_export.config(bg=self.colors["btn_hover"]), "uhl": lambda: self.btn_export.config(bg=self.colors["btn"]), "action": lambda: open_export_popup(self)},
                {"hl": lambda: self.btn_add.config(bg="#059669"), "uhl": lambda: self.btn_add.config(bg="#10b981"), "action": lambda: open_create_popup(self)},
            ])
        self.header_elements.append(
            {"hl": lambda: self.btn_theme.config(bg=self.colors["btn_hover"]), "uhl": lambda: self.btn_theme.config(bg=self.colors["btn"]), "action": self.toggle_theme}
        )
        if is_admin:
            self.header_elements.append(
                {"hl": lambda: self.btn_security.config(bg=self.colors["btn_hover"]), "uhl": lambda: self.btn_security.config(bg=self.colors["btn"]), "action": lambda: open_security_manager(self)}
            )
        self.header_elements.extend([
            {"hl": lambda: self.btn_logout.config(bg=self.colors["btn_hover"]), "uhl": lambda: self.btn_logout.config(bg=self.colors["btn"]), "action": lambda: self.app.switch_view("Logout")},
            {"hl": lambda: self.btn_bell.config(bg=self.colors["btn_hover"]), "uhl": lambda: self.btn_bell.config(bg=self.colors["btn"]), "action": self.alerts_manager.toggle_panel}
        ])
        self.header_idx = min(self.header_idx, len(self.header_elements) - 1)

        self.grid_frame = tk.Frame(self, bg=self.colors["bg"], highlightthickness=0)
        self.grid_frame.pack(fill="both", expand=True)
        self.grid_frame.bind("<Button-1>", lambda e: self.focus_set())

        self.grid_manager.load_companies()
        self.focus_set() 

    def nav_up(self, e):
        if self.nav_zone == "grid":
            if self.grid_manager.selected_grid_idx < 3: 
                self.nav_zone = "header"
                self.grid_manager.clear_selection()
                self.header_elements[self.header_idx]["hl"]()
            else:
                self.grid_manager.move_grid_focus(0, -1)

    def nav_down(self, e):
        if self.nav_zone == "header":
            self.header_elements[self.header_idx]["uhl"]()
            self.nav_zone = "grid"
            self.grid_manager.restore_selection()
        elif self.nav_zone == "grid":
            self.grid_manager.move_grid_focus(0, 1)

    def nav_left(self, e):
        if self.nav_zone == "header":
            self.header_elements[self.header_idx]["uhl"]()
            self.header_idx = max(0, self.header_idx - 1)
            self.header_elements[self.header_idx]["hl"]()
        elif self.nav_zone == "grid":
            self.grid_manager.move_grid_focus(-1, 0)

    def nav_right(self, e):
        if self.nav_zone == "header":
            self.header_elements[self.header_idx]["uhl"]()
            self.header_idx = min(len(self.header_elements) - 1, self.header_idx + 1)
            self.header_elements[self.header_idx]["hl"]()
        elif self.nav_zone == "grid":
            self.grid_manager.move_grid_focus(1, 0)

    def nav_enter(self, e):
        if self.nav_zone == "header":
            self.header_elements[self.header_idx]["action"]()
        elif self.nav_zone == "grid":
            self.grid_manager.enter_grid_focus()

    def nav_escape(self, e):
        if self.nav_zone == "header":
            self.header_elements[self.header_idx]["uhl"]()
            self.nav_zone = "grid"
            self.grid_manager.restore_selection()

    def toggle_custom_sort_menu(self, event=None):
        now = time.time()
        if now - self.last_sort_close < 0.2: return 
            
        if self.sort_window and self.sort_window.winfo_exists():
            self.sort_window.destroy()
            return

        self.sort_window = tk.Toplevel(self)
        self.sort_window.overrideredirect(True)
        self.sort_window.configure(bg=self.colors["border"], highlightthickness=1, highlightbackground=self.colors["border"])
        
        self.update_idletasks()
        x = self.sort_outer.winfo_rootx()
        y = self.sort_outer.winfo_rooty() + self.sort_outer.winfo_height() + 2
        width = self.sort_outer.winfo_width()
        self.sort_window.geometry(f"{width}x65+{x}+{y}")
        
        def on_sort_focus_out(e):
            mx, my = self.sort_window.winfo_pointerxy()
            bx, by = self.sort_outer.winfo_rootx(), self.sort_outer.winfo_rooty()
            bw, bh = self.sort_outer.winfo_width(), self.sort_outer.winfo_height()
            if bx <= mx <= bx + bw and by <= my <= by + bh: return 
            self.last_sort_close = time.time()
            self.sort_window.destroy()
            
        self.sort_window.bind("<FocusOut>", on_sort_focus_out)

        inner = tk.Frame(self.sort_window, bg=self.colors["btn"])
        inner.pack(fill="both", expand=True, padx=1, pady=1)

        self.sort_options_ref = []
        self.current_sort_idx = 0 
        options = ["Alphabetical (A-Z)", "Recently Added"]

        for i, opt in enumerate(options):
            lbl = tk.Label(inner, text=opt, font=("Segoe UI", 10), bg=self.colors["btn"], fg=self.colors["text"], anchor="w", cursor="hand2", padx=10, pady=5)
            lbl.pack(fill="x")
            self.sort_options_ref.append((lbl, opt))
            
            def make_hover(idx):
                def _on_enter(e):
                    self.current_sort_idx = idx
                    update_sort_selection()
                return _on_enter
                
            lbl.bind("<Enter>", make_hover(i))
            lbl.bind("<Button-1>", lambda e, o=opt: select_sort_opt(o))

        def update_sort_selection():
            for i, (lbl, _) in enumerate(self.sort_options_ref):
                bg_color = self.colors["btn_hover"] if i == self.current_sort_idx else self.colors["btn"]
                lbl.config(bg=bg_color)
                
        def select_sort_opt(chosen_opt=None):
            if chosen_opt is None and 0 <= self.current_sort_idx < len(self.sort_options_ref):
                chosen_opt = self.sort_options_ref[self.current_sort_idx][1]
            if chosen_opt:
                self.sort_var.set(chosen_opt)
                self.grid_manager.load_companies()
                self.sort_window.destroy()
                self.focus_set()

        update_sort_selection()
        self.sort_window.bind("<Up>", lambda e: [setattr(self, 'current_sort_idx', max(0, self.current_sort_idx - 1)), update_sort_selection()])
        self.sort_window.bind("<Down>", lambda e: [setattr(self, 'current_sort_idx', min(len(self.sort_options_ref) - 1, self.current_sort_idx + 1)), update_sort_selection()])
        self.sort_window.bind("<Return>", lambda e: select_sort_opt())
        self.sort_window.bind("<Escape>", lambda e: [self.sort_window.destroy(), self.focus_set()])
        self.sort_window.focus_force()

    def toggle_theme(self):
        current = database.get_ui_setting("dark_mode", "1")
        new_val = "0" if current == "1" else "1"
        database.save_ui_setting("dark_mode", new_val)
        self.app.apply_global_theme() 
        self.build_ui()

    # =========================================================
    # --- BULLETPROOF BRIDGE METHODS FOR SECURITY.PY ---
    # =========================================================
    def load_companies(self):
        self.grid_manager.load_companies()

    def execute_card_click(self, cid, pin, target_tab="Dashboard"):
        uid = getattr(self.app, "current_user_id", 1)
        if str(uid) != "1":
            perms = database.get_user_permissions(uid)
            allowed_tabs = perms.get("sidebars", "all")
            if isinstance(allowed_tabs, list) and target_tab not in allowed_tabs:
                non_home = [t for t in allowed_tabs if t != "Home"]
                target_tab = non_home[0] if non_home else "Home"
        self.grid_manager.execute_card_click(cid, pin, target_tab)
        
    def edit_company(self, cid, pin):
        if getattr(self.app, "current_role", "") != "Admin":
            return
        self.grid_manager.edit_company(cid, pin)
        
    def delete_company(self, cid, pin):
        if getattr(self.app, "current_role", "") != "Admin":
            return
        self.grid_manager.delete_company(cid, pin)

    def open_edit_popup(self, comp_id):
        """Bridge method: Safely catches security.py edit requests."""
        if getattr(self.app, "current_role", "") != "Admin":
            return
        open_edit_popup(self, comp_id)

    def _execute_delete(self, comp_id):
        """Bridge method: Safely catches security.py delete requests."""
        if getattr(self.app, "current_role", "") != "Admin":
            return
        self.grid_manager._execute_delete(comp_id)