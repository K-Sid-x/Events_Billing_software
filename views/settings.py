import tkinter as tk
from tkinter import ttk, messagebox, filedialog, colorchooser
import json
import os
import sys
import re

# --- THE FIX: Bulletproof Executable Pathing (MUST be above database import) ---
if getattr(sys, 'frozen', False):
    parent_dir = os.path.dirname(sys.executable)
    current_dir = os.path.join(parent_dir, "views")
else:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)

if parent_dir not in sys.path:
    sys.path.append(parent_dir)
# ------------------------------------------------------------------------------

import database
from settings_parts.part1_header import build_part_1
from settings_parts.part2_details import build_part_2
from settings_parts.part3_table import build_part_3
from settings_parts.part4_footer import build_part_4
from settings_parts.tab_bank import build_bank_tab
from settings_parts.tab_config import build_config_tab

from settings_parts.interactive_cropper import InteractiveCropper
from settings_parts.preview_renderer import render_preview
from settings_parts.constants import RAW_FONTS, BOLD_DEFAULTS, UNDERLINE_DEFAULTS

class SettingsView(tk.Frame):
    def get_theme_colors(self):
        _is_dark = database.get_ui_setting("dark_mode", "1") == "1"
        return {
            "BG_COLOR": "#0f172a" if _is_dark else "#f0f9ff",
            "CARD_BG": "#1e293b" if _is_dark else "#ffffff",
            "BORDER_COLOR": "#334155" if _is_dark else "#bae6fd",
            "TEXT_PRIMARY": "#f8fafc" if _is_dark else "#0f172a",
            "TEXT_SECONDARY": "#94a3b8" if _is_dark else "#0284c7",
            "ACCENT_GREEN": "#10b981" if _is_dark else "#059669",
            "ACCENT_BLUE": "#3b82f6" if _is_dark else "#0ea5e9",
            "ACCENT_RED": "#ef4444" if _is_dark else "#dc2626",
            "ACCENT_YELLOW": "#f59e0b" if _is_dark else "#d97706",
            "HEADER_BG": "#475569" if _is_dark else "#e0f2fe"
        }

    def __init__(self, parent):
        self.theme = self.get_theme_colors()
        super().__init__(parent, bg=self.theme["BG_COLOR"])
        self.app = self.winfo_toplevel()
        
        self.history = []
        self.history_idx = -1
        self._is_restoring = False
        self.snapshot_timer = None
        self.preview_timer = None
        
        self.setup_variables()
        
        self.comp_id = self.app.active_company_id if hasattr(self.app, "active_company_id") and self.app.active_company_id else 1
        comp = database.get_company(self.comp_id)
        self.has_gst = (comp[8] == 1) if comp and len(comp) > 8 else True
        self.comp_pin = comp[15] if comp and len(comp) > 15 else ""
        
        self.build_ui()
        
        self._is_restoring = True
        self.load_data() 
        self._is_restoring = False
        
        self.bind("<Enter>", self._bind_mousewheel)
        self._bind_mousewheel()
        self.after(300, self.focus_set)
        
        self.after(200, self.draw_preview)
        
        try:
            self.app.unbind_class("Scale", "<MouseWheel>")
            self.app.unbind_class("Scale", "<Button-4>")
            self.app.unbind_class("Scale", "<Button-5>")
            self.app.unbind_class("TCombobox", "<MouseWheel>")
            self.app.unbind_class("TCombobox", "<Button-4>")
            self.app.unbind_class("TCombobox", "<Button-5>")
        except: pass

    def browse_sig(self):
        path = filedialog.askopenfilename(filetypes=[("Image Files", "*.png;*.jpg;*.jpeg")])
        if path:
            self.sig_path_var.set(path)

    def save_sig(self):
        role = self.sig_role_var.get().strip()
        if not role:
            messagebox.showerror("Required", "Designation / Role is required.")
            return
            
        s_data = {
            "role": role,
            "path": self.sig_path_var.get().strip(),
            "is_default": (len(self.signatures_list) == 0)
        }
        self.signatures_list.append(s_data)
        self.sig_role_var.set("Authorized Signatory")
        self.sig_path_var.set("")
        self.refresh_sig_tree()
        self._save_to_db("Signature Saved!")
        self.schedule_preview()

    def delete_sig(self):
        selected = self.sig_tree.selection()
        if not selected: return
        idx = self.sig_tree.index(selected[0])
        del self.signatures_list[idx]
        self.refresh_sig_tree()
        self._save_to_db()
        self.schedule_preview()

    def set_default_sig(self):
        selected = self.sig_tree.selection()
        if not selected: return
        idx = self.sig_tree.index(selected[0])
        for s in self.signatures_list: s["is_default"] = False
        self.signatures_list[idx]["is_default"] = True
        self.refresh_sig_tree()
        self._save_to_db()
        self.schedule_preview()

    def refresh_sig_tree(self):
        if not hasattr(self, 'sig_tree'): return
        for item in self.sig_tree.get_children(): self.sig_tree.delete(item)
        for s in self.signatures_list:
            def_val = "★ Yes" if s.get("is_default") else ""
            self.sig_tree.insert("", "end", values=(def_val, s.get("role", ""), s.get("path", "")))

    def browse_bank_qr(self):
        path = filedialog.askopenfilename(filetypes=[("Image Files", "*.png;*.jpg;*.jpeg")])
        if path:
            self.bank_qr_var.set(path)
            self.update_qr_preview(path)

    def update_qr_preview(self, path=""):
        if not hasattr(self, 'qr_preview_cvs'): return
        self.qr_preview_cvs.delete("all")
        if path and os.path.exists(path):
            try:
                from PIL import Image, ImageTk
                img = Image.open(path)
                resample_filter = Image.Resampling.LANCZOS if hasattr(Image, 'Resampling') else Image.ANTIALIAS
                img = img.resize((60, 60), resample_filter)
                self._cached_qr_preview = ImageTk.PhotoImage(img)
                self.qr_preview_cvs.create_image(30, 30, image=self._cached_qr_preview, anchor="center")
            except:
                self.qr_preview_cvs.create_text(30, 30, text="Error", fill="red")
        else:
            self.qr_preview_cvs.create_text(30, 30, text="Preview", font=("Arial", 8), fill=self.theme["TEXT_SECONDARY"])

    def apply_color_theme(self, theme_name):
        if theme_name not in self.predefined_themes: return
        t = self.predefined_themes[theme_name]
        
        primary_keys = ["name", "doc_title", "bill_title", "serv_title", "inv_no_lbl", "inv_dt_lbl", "eway_lbl", "subj_label", "th_slno", "th_part", "th_hsn", "th_qty", "th_rate", "th_days", "th_amt", "terms_lbl", "bank_lbl", "amt_words_lbl"]
        
        for k in self.colors:
            if k in ["tab_head_bg", "meta_head_bg"]:
                val = t["bg"]
            elif k in primary_keys:
                val = t["primary"]
            else:
                val = t["secondary"]
                
            self.colors[k].set(val)
            if k in self.color_btns:
                self.color_btns[k].config(bg=val)
                
        self.schedule_preview()

    def export_backup(self):
        data = self.get_snapshot()
        filepath = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON Files", "*.json")], title="Export Layout Settings")
        if filepath:
            try:
                with open(filepath, 'w') as f:
                    json.dump(data, f, indent=4)
                messagebox.showinfo("Success", "Settings backed up successfully!")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to export: {e}")

    def import_backup(self):
        filepath = filedialog.askopenfilename(filetypes=[("JSON Files", "*.json")], title="Import Layout Settings")
        if filepath:
            try:
                with open(filepath, 'r') as f:
                    data = json.load(f)
                self.apply_snapshot(data)
                self._save_to_db("Settings restored successfully!")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to import: {e}")

    def set_default_bank(self):
        if not hasattr(self, 'bank_tree'): return
        selected = self.bank_tree.selection()
        if not selected:
            messagebox.showinfo("Info", "Please select a bank from the list below first.")
            return
        idx = self.bank_tree.index(selected[0])
        for b in self.banks_list: b["is_default"] = False
        self.banks_list[idx]["is_default"] = True
        self._save_to_db("Default bank updated!")
        self.refresh_bank_tree()
        self.schedule_preview()

    def _bind_mousewheel(self, event=None):
        self.bind_all("<MouseWheel>", self._on_mousewheel)
        self.bind_all("<Button-4>", self._on_mousewheel)
        self.bind_all("<Button-5>", self._on_mousewheel)
        
        self.bind_all("<Shift-MouseWheel>", self._on_shift_mousewheel)
        self.bind_all("<Shift-Button-4>", self._on_shift_mousewheel)
        self.bind_all("<Shift-Button-5>", self._on_shift_mousewheel)
        
        try:
            self.bind_all("<MouseHWheel>", self._on_mousehwheel) 
        except Exception:
            pass

    # THE FIX: Perfect scroll handling for the newly injected Config Canvas!
    def _on_mousewheel(self, event):
        if not self.winfo_exists(): return    # <--- ADD THIS LINE
        if not self.winfo_ismapped(): return  
        # ... rest of your code ... 
        try:
            widget = self.winfo_containing(event.x_root, event.y_root)
            if not widget: return
            if isinstance(widget, (ttk.Treeview, tk.Listbox)) or widget.winfo_class() == 'TComboboxListbox': return
            if not str(widget).startswith(str(self)): return

            is_shift = (event.state & 0x0001) != 0 if hasattr(event, 'state') else False

            delta = 0
            if hasattr(event, 'num'):
                if event.num == 4: delta = -1
                elif event.num == 5: delta = 1
            if hasattr(event, 'delta') and event.delta != 0:
                delta = -1 if event.delta > 0 else 1
            if delta == 0: return

            if is_shift:
                self.cvs.xview_scroll(delta, "units")
                return

            parent = widget
            while parent:
                if parent == getattr(self, 'left_canvas', None) or parent == getattr(self, 'left_panel', None):
                    self.left_canvas.yview_scroll(delta, "units")
                    return
                elif parent == getattr(self, 'cvs', None):
                    self.cvs.yview_scroll(delta, "units")
                    return
                elif parent == getattr(self, 'config_cvs', None):
                    self.config_cvs.yview_scroll(delta, "units")
                    return
                parent = parent.master
                    
            root_x = self.winfo_rootx()
            relative_x = event.x_root - root_x
            try: sash_x = self.split.sash_coord(0)[0]
            except Exception: sash_x = self.winfo_width() / 2
            
            if relative_x < sash_x: self.left_canvas.yview_scroll(delta, "units")
            else: self.cvs.yview_scroll(delta, "units")
        except: pass

    def _on_shift_mousewheel(self, event):
        if not self.winfo_exists(): return    # <--- ADD THIS LINE
        if not self.winfo_ismapped(): return 
        try:
            widget = self.winfo_containing(event.x_root, event.y_root)
            if not widget or not str(widget).startswith(str(self)): return
            delta = 0
            if hasattr(event, 'num'):
                if event.num == 4: delta = -1
                elif event.num == 5: delta = 1
            if hasattr(event, 'delta') and event.delta != 0:
                delta = -1 if event.delta > 0 else 1
            if delta == 0: return
            self.cvs.xview_scroll(delta, "units")
        except: pass

    def _on_mousehwheel(self, event):
        if not self.winfo_exists(): return    # <--- ADD THIS LINE
        if not self.winfo_ismapped(): return 
        try:
            widget = self.winfo_containing(event.x_root, event.y_root)
            if not widget or not str(widget).startswith(str(self)): return
            delta = -1 if event.delta > 0 else 1
            self.cvs.xview_scroll(delta, "units")
        except: pass

    def protect_scroll(self, widget, target_canvas=None):
        pass 

    def reset_fonts_colors(self, cat):
        keys = []
        def_b = []
        def_u = []
        target_size = "10" 
        
        if cat == 0:
            keys = ["name", "sec", "addr", "contact", "gst", "doc_title"]
            def_b = ["name", "doc_title"]
        elif cat == 1:
            keys = ["bill_title", "bill_prefix", "bill_name", "bill_addr", "bill_phone", "bill_gst"]
            def_b = [] 
            def_u = [] 
            target_size = "11" 
        elif cat == 2:
            keys = ["serv_title", "serv_prefix", "serv_name", "serv_addr", "serv_del", "serv_bill"]
            def_b = [] 
            def_u = [] 
            target_size = "11" 
            self.colors["meta_head_bg"].set("#ffffff")
            if "meta_head_bg" in self.color_btns: self.color_btns["meta_head_bg"].config(bg="#ffffff")
        elif cat == 3:
            keys = ["inv_no_lbl", "inv_no_val", "inv_dt_lbl", "inv_dt_val", "eway_lbl", "eway_val", "subj_label", "subj_val"]
            def_b = [] 
            def_u = [] 
            target_size = "11" 
        elif cat == 4:
            self.w_slno.set(6); self.w_hsn.set(12); self.w_qty.set(8)
            self.w_rate.set(12); self.w_days.set(8); self.w_amt.set(14)
            self.schedule_preview()
            return
        elif cat == 5:
            keys = ["th_slno", "th_part", "th_hsn", "th_qty", "th_rate", "th_days", "th_amt"]
            def_b = [] 
            def_u = [] 
            target_size = "11" 
            self.colors["tab_head_bg"].set("#ffffff") 
            if "tab_head_bg" in self.color_btns: self.color_btns["tab_head_bg"].config(bg="#ffffff")
        elif cat == 6:
            keys = ["tr_slno", "tr_part", "tr_hsn", "tr_qty", "tr_rate", "tr_days", "tr_amt"]
            def_b = [] 
            def_u = [] 
            target_size = "11" 
            self.master_scale_var.set(0)
            self.last_master_scale = 0
        elif cat == 7:
            keys = ["terms", "bank", "amt_words", "totals", "signature", "page_no"]
            def_b = ["totals", "signature"]
            def_u = []
            target_size = "11"
        elif cat == 9:
            # THE FIX: Ensuring esign_lbl is hooked into the mass reset!
            keys = ["terms_lbl", "terms_val", "bank_lbl", "bank_val", "amt_words_lbl", "amt_words_val", "totals", "signature", "page_no", "esign_lbl"]
            def_b = ["totals", "signature", "esign_lbl"]
            def_u = []
            target_size = "10"

        for k in keys:
            if k in self.fonts: self.fonts[k].set(target_size)
            if k in self.colors: self.colors[k].set("#000000")
            if k in self.color_btns: self.color_btns[k].config(bg="#000000")
            if k in self.bolds: self.bolds[k].set(k in def_b)
            if k in self.underlines: self.underlines[k].set(k in def_u)
            
        self.schedule_preview()

    def setup_variables(self):
        if not hasattr(self, 'comp_id'): self.comp_id = 1
        if not hasattr(self, 'has_gst'): self.has_gst = True
        
        self.name_var = tk.StringVar(); self.sec_var = tk.StringVar(); self.addr_var = tk.StringVar()
        self.p1_var = tk.StringVar(); self.p2_var = tk.StringVar(); self.p3_var = tk.StringVar()
        self.email_var = tk.StringVar(); self.gst_var = tk.StringVar()
        
        self.swap_title_order_var = tk.IntVar(value=0) 
        self.paper_size_var = tk.StringVar(value="A4 (210*297mm)")
        self.logo_path_var = tk.StringVar(); self.logo_size_var = tk.StringVar(value="120")
        self.logo_shape_var = tk.StringVar(value="Original"); self.layout_var = tk.StringVar(value="Classic")
        self.header_spacing_var = tk.StringVar(value="20") 
        
        self.lbl_billed_to_var = tk.StringVar(value="BILLED TO:")
        self.swap_boxes_var = tk.IntVar(value=0)
        
        self.terms_vars = [tk.StringVar(value="Goods once sold will not be taken back."), tk.StringVar(value="Interest @ 18% p.a. will be charged if not paid within due date.")]
        for t in self.terms_vars: t.trace_add("write", lambda *args: self.schedule_preview())
        self.refresh_terms_ui = None 
        
        self.w_slno = tk.IntVar(value=6); self.w_hsn = tk.IntVar(value=12); self.w_qty = tk.IntVar(value=8)
        self.w_rate = tk.IntVar(value=12); self.w_days = tk.IntVar(value=8); self.w_amt = tk.IntVar(value=14)
        
        self.date_format_var = tk.StringVar(value="DD.MM.YYYY")
        self.currency_var = tk.StringVar(value="Indian Rupees (₹ 10,00,000.00)")
        
        self.master_scale_var = tk.IntVar(value=0)
        self.last_master_scale = 0
        
        self.show_subject_var = tk.IntVar(value=1)
        self.prev_split_var = tk.IntVar(value=0)
        self.show_discount_var = tk.IntVar(value=1)
        self.show_advance_var = tk.IntVar(value=1)
        self.prev_bank_var = tk.IntVar(value=1)
        self.prev_terms_var = tk.IntVar(value=1)
        
        self.show_subject_var.trace_add("write", lambda *args: self.schedule_preview())
        self.prev_split_var.trace_add("write", lambda *args: self.schedule_preview())
        self.show_discount_var.trace_add("write", lambda *args: self.schedule_preview())
        self.show_advance_var.trace_add("write", lambda *args: self.schedule_preview())
        self.prev_bank_var.trace_add("write", lambda *args: self.schedule_preview())
        self.prev_terms_var.trace_add("write", lambda *args: self.schedule_preview())

        self.fonts = {k: tk.StringVar(value=str(v)) for k, v in RAW_FONTS.items()}
        self.colors = {k: tk.StringVar(value="#000000") for k in RAW_FONTS.keys()}
        self.bolds = {k: tk.BooleanVar(value=(k in BOLD_DEFAULTS)) for k in RAW_FONTS.keys()}
        self.underlines = {k: tk.BooleanVar(value=(k in UNDERLINE_DEFAULTS)) for k in RAW_FONTS.keys()}
        
        self.colors["tab_head_bg"] = tk.StringVar(value="#ffffff") 
        self.colors["meta_head_bg"] = tk.StringVar(value="#ffffff") 
        
        # THE FIX: Ensuring the esign_lbl dict structure exists before UI draws!
        if "esign_lbl" not in self.fonts:
            self.fonts["esign_lbl"] = tk.StringVar(value="10")
            self.colors["esign_lbl"] = tk.StringVar(value="#000000")
            self.bolds["esign_lbl"] = tk.BooleanVar(value=True)
            self.underlines["esign_lbl"] = tk.BooleanVar(value=False)
            
        if "page_no" not in self.fonts:
            self.fonts["page_no"] = tk.StringVar(value="10")
            self.colors["page_no"] = tk.StringVar(value="#000000")
            self.bolds["page_no"] = tk.BooleanVar(value=False)
            self.underlines["page_no"] = tk.BooleanVar(value=False)

        self.color_btns = {}
        self.banks_list = []
        self.editing_bank_idx = -1 
        self.bank_alias_var = tk.StringVar(); self.bank_name_var = tk.StringVar()
        self.bank_acname_var = tk.StringVar(); self.bank_ac_var = tk.StringVar()
        self.bank_ifsc_var = tk.StringVar(); self.bank_branch_var = tk.StringVar()
        self.bank_pan_var = tk.StringVar()
        self.bank_qr_var = tk.StringVar()
        
        self.signatures_list = []
        self.sig_role_var = tk.StringVar(value="Authorized Signatory")
        self.sig_path_var = tk.StringVar()
        
        # THE FIX: New Signature Toggle & Scale Variables
        self.show_esign_var = tk.IntVar(value=1)
        self.sig_scale_var = tk.IntVar(value=100)
        self.sig_nudge_var = tk.IntVar(value=0)
        
        def _capitalize_bank(*args):
            val = self.bank_name_var.get()
            if val != val.upper(): self.bank_name_var.set(val.upper())
            
        def _capitalize_ifsc(*args):
            val = self.bank_ifsc_var.get()
            if val != val.upper(): self.bank_ifsc_var.set(val.upper())
            
        def _capitalize_pan(*args):
            val = self.bank_pan_var.get()
            if val != val.upper(): self.bank_pan_var.set(val.upper())
            
        def _numbers_only_ac(*args):
            val = self.bank_ac_var.get()
            cleaned = ''.join(filter(str.isdigit, val))
            if val != cleaned: self.bank_ac_var.set(cleaned)
            
        def _format_ph(var):
            raw = "".join(filter(str.isdigit, var.get()))
            if len(raw) > 5: formatted = f"{raw[:5]}-{raw[5:10]}"
            else: formatted = raw
            if var.get() != formatted: 
                var.set(formatted)
                # Force the blinking cursor to jump back to the end after formatting!
                try:
                    focused = self.focus_get()
                    if isinstance(focused, tk.Entry):
                        focused.after(1, lambda: focused.icursor("end"))
                except: pass

        self.bank_name_var.trace_add("write", _capitalize_bank)
        self.bank_ifsc_var.trace_add("write", _capitalize_ifsc)
        self.bank_pan_var.trace_add("write", _capitalize_pan)
        self.bank_ac_var.trace_add("write", _numbers_only_ac)
        
        # Actively format phone numbers to 00000-00000 as you type
        self.p1_var.trace_add("write", lambda *a: _format_ph(self.p1_var))
        self.p2_var.trace_add("write", lambda *a: _format_ph(self.p2_var))
        self.p3_var.trace_add("write", lambda *a: _format_ph(self.p3_var))

        all_vars = [self.swap_title_order_var, self.header_spacing_var, self.name_var, self.sec_var, self.addr_var, self.p1_var, self.p2_var, self.p3_var, self.email_var, self.gst_var, self.paper_size_var, self.logo_size_var, self.logo_shape_var, self.layout_var, self.lbl_billed_to_var, self.swap_boxes_var, self.w_slno, self.w_hsn, self.w_qty, self.w_rate, self.w_days, self.w_amt, self.date_format_var, self.currency_var, self.show_esign_var, self.sig_scale_var, self.sig_nudge_var] + list(self.fonts.values()) + list(self.colors.values()) + list(self.bolds.values()) + list(self.underlines.values())
        for v in all_vars:
            v.trace_add("write", lambda *args: self.schedule_preview())
            
        self.cached_pos = {} 

    def init_history(self):
        self.history = [self.get_snapshot()]
        self.history_idx = 0
        self.update_undo_redo_btns()

    def get_snapshot(self):
        return {
            "name": self.name_var.get(), "sec": self.sec_var.get(), "addr": self.addr_var.get(),
            "p1": self.p1_var.get(), "p2": self.p2_var.get(), "p3": self.p3_var.get(),
            "email": self.email_var.get(), "gst": self.gst_var.get(),
            "paper": self.paper_size_var.get(), "layout": self.layout_var.get(),
            "logo_shape": self.logo_shape_var.get(), "logo_size": self.logo_size_var.get(),
            "header_spacing": self.header_spacing_var.get(), "lbl_billed": self.lbl_billed_to_var.get(),
            "swap_title": self.swap_title_order_var.get(), "swap_boxes": self.swap_boxes_var.get(),
            "date_fmt": self.date_format_var.get(), "currency": self.currency_var.get(),
            "show_subj": self.show_subject_var.get(), "w_slno": self.w_slno.get(),
            "w_hsn": self.w_hsn.get(), "w_qty": self.w_qty.get(), "w_rate": self.w_rate.get(),
            "w_days": self.w_days.get(), "w_amt": self.w_amt.get(),
            "master_scale": self.master_scale_var.get(),
            "terms": [t.get() for t in self.terms_vars],
            "fonts": {k: v.get() for k,v in self.fonts.items()},
            "colors": {k: v.get() for k,v in self.colors.items()},
            "bolds": {k: v.get() for k,v in self.bolds.items()},
            "underlines": {k: v.get() for k,v in self.underlines.items()},
            "pos": dict(self.cached_pos), "logo_path": self.logo_path_var.get(),
            "signatures": self.signatures_list,
            "show_esign": self.show_esign_var.get(),
            "sig_scale": self.sig_scale_var.get(),
            "sig_nudge": self.sig_nudge_var.get()
        }

    def apply_snapshot(self, state):
        self._is_restoring = True
        
        self.name_var.set(state.get("name", ""))
        self.sec_var.set(state.get("sec", ""))
        self.addr_var.set(state.get("addr", ""))
        self.p1_var.set(state.get("p1", ""))
        self.p2_var.set(state.get("p2", ""))
        self.p3_var.set(state.get("p3", ""))
        self.email_var.set(state.get("email", ""))
        self.gst_var.set(state.get("gst", ""))
        self.paper_size_var.set(state.get("paper", "A4 (210*297mm)"))
        self.layout_var.set(state.get("layout", "Classic"))
        self.logo_shape_var.set(state.get("logo_shape", "Square"))
        self.logo_size_var.set(state.get("logo_size", "120"))
        self.header_spacing_var.set(state.get("header_spacing", "20"))
        self.lbl_billed_to_var.set(state.get("lbl_billed", "BILLED TO:"))
        self.swap_title_order_var.set(state.get("swap_title", 0))
        self.swap_boxes_var.set(state.get("swap_boxes", 0))
        self.show_subject_var.set(state.get("show_subj", 1))
        self.date_format_var.set(state.get("date_fmt", "DD.MM.YYYY"))
        
        old_to_new_curr = {
            "Indian Rupees (₹)": "Indian Rupees (₹ 10,00,000.00)",
            "US Dollar ($)": "US Dollar ($ 1,000,000.00)",
            "Euro (€)": "Euro (€ 1.000.000,00)",
            "British Pound (£)": "British Pound (£ 1,000,000.00)",
            "Generic Number": "Generic Number (1,000,000.00)"
        }
        loaded_curr = state.get("currency", "Indian Rupees (₹ 10,00,000.00)")
        self.currency_var.set(old_to_new_curr.get(loaded_curr, loaded_curr))

        self.w_slno.set(state.get("w_slno", 6))
        self.w_hsn.set(state.get("w_hsn", 12))
        self.w_qty.set(state.get("w_qty", 8))
        self.w_rate.set(state.get("w_rate", 12))
        self.w_days.set(state.get("w_days", 8))
        self.w_amt.set(state.get("w_amt", 14))
        
        target_ms = state.get("master_scale", 0)
        self.last_master_scale = target_ms
        self.master_scale_var.set(target_ms)
        
        saved_terms = state.get("terms", [])
        while len(self.terms_vars) < len(saved_terms):
            new_var = tk.StringVar()
            new_var.trace_add("write", lambda *args: self.schedule_preview())
            self.terms_vars.append(new_var)
        while len(self.terms_vars) > len(saved_terms):
            self.terms_vars.pop()
        for i, t_val in enumerate(saved_terms):
            self.terms_vars[i].set(t_val)
        if self.refresh_terms_ui: self.refresh_terms_ui()
        
        for k, v in state.get("fonts", {}).items():
            if k in self.fonts: self.fonts[k].set(v)
        for k, v in state.get("colors", {}).items():
            if k in self.colors: 
                self.colors[k].set(v)
                if k in self.color_btns: self.color_btns[k].config(bg=v)
        for k, v in state.get("bolds", {}).items():
            if k in self.bolds: self.bolds[k].set(v)
        for k, v in state.get("underlines", {}).items():
            if k in self.underlines: self.underlines[k].set(v)
            
        self.cached_pos = dict(state.get("pos", {}))
        self.logo_path_var.set(state.get("logo_path", ""))
        self.signatures_list = state.get("signatures", [])
        self.refresh_sig_tree()
        
        self.show_esign_var.set(state.get("show_esign", 1))
        self.sig_scale_var.set(state.get("sig_scale", 100))
        self.sig_nudge_var.set(state.get("sig_nudge", 0))
        
        self.update_undo_redo_btns()
        self.draw_preview() 
        self.after(50, lambda: setattr(self, '_is_restoring', False))

    def save_history_snapshot(self):
        if not hasattr(self, 'history'): return
        new_state = self.get_snapshot()
        if not self.history or new_state != self.history[self.history_idx]:
            self.history = self.history[:self.history_idx+1]
            self.history.append(new_state)
            if len(self.history) > 30: 
                self.history.pop(0)
            else:
                self.history_idx += 1
            self.update_undo_redo_btns()

    def do_undo(self):
        if self.history_idx > 0:
            self.history_idx -= 1
            self.apply_snapshot(self.history[self.history_idx])
            
    def do_redo(self):
        if self.history_idx < len(self.history) - 1:
            self.history_idx += 1
            self.apply_snapshot(self.history[self.history_idx])

    def update_undo_redo_btns(self):
        if not hasattr(self, 'btn_undo'): return
        
        if self.history_idx > 0:
            self.btn_undo.config(state="normal", fg=self.theme["TEXT_PRIMARY"])
        else:
            self.btn_undo.config(state="disabled", fg=self.theme["TEXT_SECONDARY"])
            
        if self.history_idx < len(self.history) - 1:
            self.btn_redo.config(state="normal", fg=self.theme["TEXT_PRIMARY"])
        else:
            self.btn_redo.config(state="disabled", fg=self.theme["TEXT_SECONDARY"])

    def schedule_preview(self):
        if getattr(self, '_is_restoring', False): return
        
        if getattr(self, 'snapshot_timer', None):
            self.after_cancel(self.snapshot_timer)
        self.snapshot_timer = self.after(600, self.save_history_snapshot)
        
        if getattr(self, 'preview_timer', None): 
            self.after_cancel(self.preview_timer)
        self.preview_timer = self.after(150, self.draw_preview)

    def build_ui(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        
        style.configure("TNotebook", background=self.theme["BG_COLOR"], borderwidth=0)
        style.configure("TNotebook.Tab", background=self.theme["CARD_BG"], foreground=self.theme["TEXT_SECONDARY"], padding=[15, 8], font=("Arial", 10, "bold"), borderwidth=0)
        style.map("TNotebook.Tab", background=[("selected", self.theme["ACCENT_BLUE"])], foreground=[("selected", "#ffffff")])
        
        self.app.option_add("*TCombobox*Listbox.background", self.theme["CARD_BG"])
        self.app.option_add("*TCombobox*Listbox.foreground", self.theme["TEXT_PRIMARY"])
        self.app.option_add("*TCombobox*Listbox.selectBackground", self.theme["ACCENT_BLUE"])
        self.app.option_add("*TCombobox*Listbox.selectForeground", self.theme["TEXT_PRIMARY"])
        
        style.configure("TCombobox", fieldbackground=self.theme["BG_COLOR"], background=self.theme["CARD_BG"], foreground=self.theme["TEXT_PRIMARY"], arrowcolor=self.theme["TEXT_PRIMARY"], bordercolor=self.theme["BORDER_COLOR"], lightcolor=self.theme["BORDER_COLOR"], darkcolor=self.theme["BORDER_COLOR"])
        style.map("TCombobox", fieldbackground=[("readonly", self.theme["BG_COLOR"])], selectbackground=[("readonly", self.theme["BG_COLOR"])], selectforeground=[("readonly", self.theme["TEXT_PRIMARY"])], foreground=[("readonly", self.theme["TEXT_PRIMARY"])])

        thumb_color = "#475569" if self.theme["BG_COLOR"] == "#0f172a" else "#94a3b8"
        trough_color = self.theme["BG_COLOR"]
        
        style.configure("Vertical.TScrollbar", background=thumb_color, troughcolor=trough_color, bordercolor=self.theme["BORDER_COLOR"], arrowcolor=self.theme["TEXT_PRIMARY"], relief="flat")
        style.configure("Horizontal.TScrollbar", background=thumb_color, troughcolor=trough_color, bordercolor=self.theme["BORDER_COLOR"], arrowcolor=self.theme["TEXT_PRIMARY"], relief="flat")
        style.map("Vertical.TScrollbar", background=[("active", self.theme["ACCENT_BLUE"])])
        style.map("Horizontal.TScrollbar", background=[("active", self.theme["ACCENT_BLUE"])])

        header = tk.Frame(self, bg=self.theme["CARD_BG"], pady=10, padx=20, highlightbackground=self.theme["BORDER_COLOR"], highlightthickness=1)
        header.pack(fill="x", pady=(0, 10))
        tk.Label(header, text="⚙️ Master Settings", font=("Arial", 16, "bold"), bg=self.theme["CARD_BG"], fg=self.theme["TEXT_PRIMARY"]).pack(side="left")

        btn_import = tk.Button(header, text="⭱ Import", font=("Arial", 10, "bold"), bg=self.theme["CARD_BG"], fg=self.theme["TEXT_SECONDARY"], relief="flat", cursor="hand2", command=self.import_backup)
        btn_import.pack(side="right", padx=(5, 0))
        btn_export = tk.Button(header, text="⭳ Backup", font=("Arial", 10, "bold"), bg=self.theme["CARD_BG"], fg=self.theme["TEXT_SECONDARY"], relief="flat", cursor="hand2", command=self.export_backup)
        btn_export.pack(side="right", padx=5)

        self.btn_redo = tk.Button(header, text="⮎ Redo", font=("Arial", 10, "bold"), bg=self.theme["CARD_BG"], fg=self.theme["TEXT_SECONDARY"], relief="flat", cursor="hand2", command=self.do_redo, state="disabled")
        self.btn_redo.pack(side="right", padx=(5, 0))
        
        self.btn_undo = tk.Button(header, text="⮌ Undo", font=("Arial", 10, "bold"), bg=self.theme["CARD_BG"], fg=self.theme["TEXT_SECONDARY"], relief="flat", cursor="hand2", command=self.do_undo, state="disabled")
        self.btn_undo.pack(side="right", padx=5)

        def on_btn_enter(e):
            if e.widget['state'] != 'disabled': e.widget.config(bg=self.theme["BORDER_COLOR"])
        def on_btn_leave(e):
            e.widget.config(bg=self.theme["CARD_BG"])
            
        for btn in [self.btn_undo, self.btn_redo, btn_import, btn_export]:
            btn.bind("<Enter>", on_btn_enter)
            btn.bind("<Leave>", on_btn_leave)

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=0)

        self.tab_inv = tk.Frame(self.notebook, bg=self.theme["BG_COLOR"])
        self.tab_bank = tk.Frame(self.notebook, bg=self.theme["BG_COLOR"])
        self.tab_config = tk.Frame(self.notebook, bg=self.theme["BG_COLOR"])
        
        self.notebook.add(self.tab_inv, text=" Invoice Customization ")
        self.notebook.add(self.tab_bank, text=" Bank Details ")
        self.notebook.add(self.tab_config, text=" Configuration ")

        self.build_invoice_tab()
        build_bank_tab(self.tab_bank, self)     
        build_config_tab(self.tab_config, self) 

    def build_invoice_tab(self):
        tile_f = tk.Frame(self.tab_inv, bg=self.theme["BG_COLOR"], pady=10)
        tile_f.pack(fill="x")
        
        self.btn_p1 = tk.Button(tile_f, text="Part 1: Header", font=("Arial", 10, "bold"), bg=self.theme["ACCENT_BLUE"], fg="white", relief="flat", width=15, cursor="hand2", command=lambda: self.show_part(1))
        self.btn_p2 = tk.Button(tile_f, text="Part 2: Details", font=("Arial", 10, "bold"), bg=self.theme["CARD_BG"], fg=self.theme["TEXT_PRIMARY"], relief="flat", width=15, cursor="hand2", command=lambda: self.show_part(2))
        self.btn_p3 = tk.Button(tile_f, text="Part 3: Table", font=("Arial", 10, "bold"), bg=self.theme["CARD_BG"], fg=self.theme["TEXT_PRIMARY"], relief="flat", width=15, cursor="hand2", command=lambda: self.show_part(3))
        self.btn_p4 = tk.Button(tile_f, text="Part 4: Footer", font=("Arial", 10, "bold"), bg=self.theme["CARD_BG"], fg=self.theme["TEXT_PRIMARY"], relief="flat", width=15, cursor="hand2", command=lambda: self.show_part(4))
        
        self.btn_p1.pack(side="left", padx=(20, 5)); self.btn_p2.pack(side="left", padx=5)
        self.btn_p3.pack(side="left", padx=5); self.btn_p4.pack(side="left", padx=5)

        btn_save_inv = tk.Button(tile_f, text="💾 Save Invoice Settings", font=("Arial", 10, "bold"), bg=self.theme["ACCENT_GREEN"], fg="#ffffff", relief="flat", cursor="hand2", padx=15, command=lambda: self._save_to_db("Invoice Settings & Template Saved!"))
        btn_save_inv.pack(side="right", padx=20)

        self.theme_var = tk.StringVar(value="Select Theme...")
        self.predefined_themes = {
            "Classic Black": {"primary": "#000000", "secondary": "#000000", "bg": "#ffffff"},
            "Corporate Navy": {"primary": "#1A237E", "secondary": "#212121", "bg": "#E8EAF6"},
            "Emerald Green": {"primary": "#1B5E20", "secondary": "#212121", "bg": "#E8F5E9"},
            "Deep Maroon": {"primary": "#B71C1C", "secondary": "#212121", "bg": "#FFEBEE"},
            "Modern Slate": {"primary": "#37474F", "secondary": "#263238", "bg": "#ECEFF1"}
        }
        cb_theme = ttk.Combobox(tile_f, textvariable=self.theme_var, values=list(self.predefined_themes.keys()), state="readonly", width=15)
        cb_theme.pack(side="right", padx=(0, 20))
        cb_theme.bind("<<ComboboxSelected>>", lambda e: self.apply_color_theme(self.theme_var.get()))
        tk.Label(tile_f, text="🎨 Color Theme:", bg=self.theme["BG_COLOR"], font=("Arial", 9, "bold"), fg=self.theme["TEXT_SECONDARY"]).pack(side="right", padx=(10, 5))

        self.split = tk.PanedWindow(self.tab_inv, orient="horizontal", sashwidth=5, bg=self.theme["BORDER_COLOR"])
        self.split.pack(fill="both", expand=True, padx=20, pady=(0, 10))

        # THE FIX: Expanded Minimum Width to 460 to comfortably hold all sliders!
        left_container = tk.Frame(self.split, bg=self.theme["CARD_BG"], width=460)
        self.split.add(left_container, minsize=460) 

        self.left_canvas = tk.Canvas(left_container, bg=self.theme["CARD_BG"], highlightthickness=0)
        left_scroll = ttk.Scrollbar(left_container, orient="vertical", command=self.left_canvas.yview)
        self.left_panel = tk.Frame(self.left_canvas, bg=self.theme["CARD_BG"])

        self.left_panel.bind("<Configure>", lambda e: self.left_canvas.configure(scrollregion=self.left_canvas.bbox("all")))
        self.left_canvas.create_window((0, 0), window=self.left_panel, anchor="nw")
        self.left_canvas.configure(yscrollcommand=left_scroll.set)

        self.left_canvas.pack(side="left", fill="both", expand=True)
        left_scroll.pack(side="right", fill="y")
        
        self.right_panel = tk.Frame(self.split, bg=self.theme["BG_COLOR"])
        self.split.add(self.right_panel, minsize=400)

        prev_ctrl = tk.Frame(self.right_panel, bg=self.theme["BG_COLOR"])
        prev_ctrl.pack(fill="x", padx=10, pady=(10, 0))
        tk.Label(prev_ctrl, text="Live Preview Data:", font=("Arial", 9, "bold"), bg=self.theme["BG_COLOR"], fg=self.theme["TEXT_SECONDARY"]).pack(side="left")
        
        chk_split = tk.Checkbutton(prev_ctrl, text="Multi-Page (Split)", variable=self.prev_split_var, bg=self.theme["BG_COLOR"], fg=self.theme["TEXT_PRIMARY"], selectcolor=self.theme["CARD_BG"], activebackground=self.theme["BG_COLOR"], activeforeground=self.theme["TEXT_PRIMARY"], font=("Arial", 9, "bold"), cursor="hand2")
        chk_split.pack(side="left", padx=(10, 5))
        
        chk_subject = tk.Checkbutton(prev_ctrl, text="Subject", variable=self.show_subject_var, bg=self.theme["BG_COLOR"], fg=self.theme["TEXT_PRIMARY"], selectcolor=self.theme["CARD_BG"], activebackground=self.theme["BG_COLOR"], activeforeground=self.theme["TEXT_PRIMARY"], font=("Arial", 9, "bold"), cursor="hand2")
        chk_subject.pack(side="left", padx=5)

        chk_discount = tk.Checkbutton(prev_ctrl, text="Discount", variable=self.show_discount_var, bg=self.theme["BG_COLOR"], fg=self.theme["TEXT_PRIMARY"], selectcolor=self.theme["CARD_BG"], activebackground=self.theme["BG_COLOR"], activeforeground=self.theme["TEXT_PRIMARY"], font=("Arial", 9, "bold"), cursor="hand2")
        chk_discount.pack(side="left", padx=5)
        
        chk_advance = tk.Checkbutton(prev_ctrl, text="Advance", variable=self.show_advance_var, bg=self.theme["BG_COLOR"], fg=self.theme["TEXT_PRIMARY"], selectcolor=self.theme["CARD_BG"], activebackground=self.theme["BG_COLOR"], activeforeground=self.theme["TEXT_PRIMARY"], font=("Arial", 9, "bold"), cursor="hand2")
        chk_advance.pack(side="left", padx=5)
        
        chk_bank = tk.Checkbutton(prev_ctrl, text="Bank Details", variable=self.prev_bank_var, bg=self.theme["BG_COLOR"], fg=self.theme["TEXT_PRIMARY"], selectcolor=self.theme["CARD_BG"], activebackground=self.theme["BG_COLOR"], activeforeground=self.theme["TEXT_PRIMARY"], font=("Arial", 9, "bold"), cursor="hand2")
        chk_bank.pack(side="left", padx=5)
        
        chk_terms = tk.Checkbutton(prev_ctrl, text="Terms", variable=self.prev_terms_var, bg=self.theme["BG_COLOR"], fg=self.theme["TEXT_PRIMARY"], selectcolor=self.theme["CARD_BG"], activebackground=self.theme["BG_COLOR"], activeforeground=self.theme["TEXT_PRIMARY"], font=("Arial", 9, "bold"), cursor="hand2")
        chk_terms.pack(side="left", padx=5)

        self.f_p1 = tk.Frame(self.left_panel, bg=self.theme["CARD_BG"], padx=15, pady=15)
        self.f_p2 = tk.Frame(self.left_panel, bg=self.theme["CARD_BG"], padx=15, pady=15)
        self.f_p3 = tk.Frame(self.left_panel, bg=self.theme["CARD_BG"], padx=15, pady=15)
        self.f_p4 = tk.Frame(self.left_panel, bg=self.theme["CARD_BG"], padx=15, pady=15)

        build_part_1(self.f_p1, self)
        build_part_2(self.f_p2, self)
        build_part_3(self.f_p3, self)
        build_part_4(self.f_p4, self)

        self.cvs_frame = tk.Frame(self.right_panel, bg=self.theme["BG_COLOR"])
        self.cvs_frame.pack(fill="both", expand=True, padx=10, pady=(10, 10))
        
        self.cvs = tk.Canvas(self.cvs_frame, bg=self.theme["BG_COLOR"], highlightthickness=0)
        self.scroll_y = ttk.Scrollbar(self.cvs_frame, orient="vertical", command=self.cvs.yview)
        self.scroll_x = ttk.Scrollbar(self.cvs_frame, orient="horizontal", command=self.cvs.xview)
        
        self.cvs.configure(yscrollcommand=self.scroll_y.set, xscrollcommand=self.scroll_x.set)
        
        self.scroll_y.pack(side="right", fill="y")
        self.scroll_x.pack(side="bottom", fill="x")
        self.cvs.pack(side="left", fill="both", expand=True)
        
        self.cvs.bind("<Configure>", lambda e: self.draw_preview())
        
        self.drag_item = None
        self.drag_start_x = 0; self.drag_start_y = 0

        def on_drag_press(event):
            if self.layout_var.get() != "Custom (Drag & Drop)": return
            
            canvas_x = self.cvs.canvasx(event.x)
            canvas_y = self.cvs.canvasy(event.y)
            
            items = self.cvs.find_withtag("current")
            if items:
                tags = self.cvs.gettags(items[0])
                for t in tags:
                    if t.startswith("drag_"): 
                        self.drag_item = t
                        self.drag_start_x = event.x; self.drag_start_y = event.y
                        self.cvs.tag_raise(t)
                        break

        def on_drag_motion(event):
            if not self.drag_item: return
            dx = event.x - self.drag_start_x; dy = event.y - self.drag_start_y
            self.cvs.move(self.drag_item, dx, dy)
            self.drag_start_x = event.x; self.drag_start_y = event.y

        def on_drag_release(event):
            if not self.drag_item: return
            bbox = self.cvs.bbox(self.drag_item)
            if bbox:
                if self.drag_item == "drag_logo":
                    self.cached_pos["logo_x"] = bbox[0]; self.cached_pos["logo_y"] = bbox[1]
                else: 
                    self.cached_pos[self.drag_item + "_x"] = (bbox[0] + bbox[2]) / 2 
                    self.cached_pos[self.drag_item + "_y"] = bbox[1]
            self.schedule_preview()
            self._save_to_db() 
            self.drag_item = None

        self.cvs.bind("<ButtonPress-1>", on_drag_press)
        self.cvs.bind("<B1-Motion>", on_drag_motion)
        self.cvs.bind("<ButtonRelease-1>", on_drag_release)

        self.show_part(1)
        self.after(500, self.init_history)

    def save_bank(self):
        name = self.bank_name_var.get().strip()
        ac = self.bank_ac_var.get().strip()
        if not name or not ac:
            messagebox.showerror("Required", "Bank Name and Account Number are required.")
            return
            
        b_data = {
            "alias": self.bank_alias_var.get().strip() or name,
            "name": name,
            "ac_name": self.bank_acname_var.get().strip(),
            "ac": ac,
            "ifsc": self.bank_ifsc_var.get().strip(),
            "branch": self.bank_branch_var.get().strip(),
            "pan": self.bank_pan_var.get().strip(),
            "qr_path": self.bank_qr_var.get().strip()
        }
        
        if self.editing_bank_idx >= 0:
            b_data["is_default"] = self.banks_list[self.editing_bank_idx].get("is_default", False)
            self.banks_list[self.editing_bank_idx].update(b_data)
            self.cancel_bank_edit()
        else:
            b_data["is_default"] = (len(self.banks_list) == 0)
            self.banks_list.append(b_data)
            self.clear_bank_form()
            
        if hasattr(self, 'bank_tree'): self.refresh_bank_tree()
        self.schedule_preview()
        self._save_to_db("Bank Account Saved Successfully!")

    def edit_bank(self):
        selected = self.bank_tree.selection()
        if not selected: return
        self.editing_bank_idx = self.bank_tree.index(selected[0])
        
        b = self.banks_list[self.editing_bank_idx]
        self.bank_alias_var.set(b.get("alias", ""))
        self.bank_name_var.set(b.get("name", ""))
        self.bank_acname_var.set(b.get("ac_name", ""))
        self.bank_ac_var.set(b.get("ac", ""))
        self.bank_ifsc_var.set(b.get("ifsc", ""))
        self.bank_branch_var.set(b.get("branch", ""))
        self.bank_pan_var.set(b.get("pan", ""))
        self.bank_qr_var.set(b.get("qr_path", ""))
        self.update_qr_preview(b.get("qr_path", ""))
        
        self.btn_bank_save.config(text="Update Bank Account", bg=self.theme["ACCENT_YELLOW"], fg=self.theme["BG_COLOR"])
        self.btn_bank_cancel.pack(side="left", padx=10)

    def cancel_bank_edit(self):
        self.editing_bank_idx = -1
        self.btn_bank_save.config(text="Add Bank Account", bg=self.theme["ACCENT_BLUE"], fg="#ffffff")
        self.btn_bank_cancel.pack_forget()
        self.clear_bank_form()

    def delete_bank(self):
        selected = self.bank_tree.selection()
        if not selected: return
        if not messagebox.askyesno("Confirm Delete", "Are you sure you want to delete this bank account?", parent=self): return
            
        idx = self.bank_tree.index(selected[0])
        if self.editing_bank_idx == idx: self.cancel_bank_edit()
            
        del self.banks_list[idx]
        self.refresh_bank_tree()
        self.schedule_preview()
        self._save_to_db("Bank Account Deleted!")

    def clear_bank_form(self):
        self.bank_alias_var.set(""); self.bank_name_var.set(""); self.bank_acname_var.set("")
        self.bank_ac_var.set(""); self.bank_ifsc_var.set(""); self.bank_branch_var.set("")
        self.bank_pan_var.set("")
        self.bank_qr_var.set("")
        self.update_qr_preview("")

    def refresh_bank_tree(self):
        for item in self.bank_tree.get_children(): self.bank_tree.delete(item)
        for b in self.banks_list:
            def_val = "★ Yes" if b.get("is_default") else ""
            qr_val = "✅" if b.get("qr_path") else ""
            self.bank_tree.insert("", "end", values=(def_val, b.get("alias", ""), b.get("name", ""), b.get("ac_name", ""), b.get("ac", ""), b.get("ifsc", ""), b.get("branch", ""), qr_val))

    def show_part(self, p):
        for btn in [self.btn_p1, self.btn_p2, self.btn_p3, self.btn_p4]: btn.config(bg=self.theme["CARD_BG"], fg=self.theme["TEXT_PRIMARY"])
        for f in [self.f_p1, self.f_p2, self.f_p3, self.f_p4]: f.pack_forget()
            
        if p == 1: self.btn_p1.config(bg=self.theme["ACCENT_BLUE"], fg="white"); self.f_p1.pack(fill="both", expand=True)
        elif p == 2: self.btn_p2.config(bg=self.theme["ACCENT_BLUE"], fg="white"); self.f_p2.pack(fill="both", expand=True)
        elif p == 3: self.btn_p3.config(bg=self.theme["ACCENT_BLUE"], fg="white"); self.f_p3.pack(fill="both", expand=True)
        elif p == 4: self.btn_p4.config(bg=self.theme["ACCENT_BLUE"], fg="white"); self.f_p4.pack(fill="both", expand=True)

        self.update_idletasks()
        self.left_canvas.yview_moveto(0)
        self.left_canvas.configure(scrollregion=self.left_canvas.bbox("all"))

    def _create_font_color_row(self, parent, label, key, row):
        tk.Label(parent, text=label, font=("Arial", 9), bg=self.theme["CARD_BG"], fg=self.theme["TEXT_SECONDARY"]).grid(row=row, column=0, sticky="w", pady=(15, 0))
        slider = tk.Scale(parent, from_=6, to=40, orient="horizontal", variable=self.fonts[key], bg=self.theme["CARD_BG"], fg=self.theme["TEXT_PRIMARY"], bd=0, highlightthickness=0, length=120, sliderlength=15)
        slider.grid(row=row, column=1, padx=10)
        btn = tk.Button(parent, width=3, bg=self.colors[key].get(), relief="solid", bd=1, highlightbackground=self.theme["BORDER_COLOR"], cursor="hand2")
        btn.config(command=lambda k=key, b=btn: self.pick_color(k, b))
        btn.grid(row=row, column=2, padx=5, pady=(15, 0))
        self.color_btns[key] = btn

    def _create_full_font_row(self, parent, label, key, row):
        tk.Label(parent, text=label, font=("Arial", 9), bg=self.theme["CARD_BG"], fg=self.theme["TEXT_SECONDARY"], width=17, anchor="w").grid(row=row, column=0, sticky="w", pady=(15, 0))
        
        slider = tk.Scale(parent, from_=6, to=40, orient="horizontal", variable=self.fonts[key], bg=self.theme["CARD_BG"], fg=self.theme["TEXT_PRIMARY"], bd=0, highlightthickness=0, length=80, sliderlength=15)
        slider.grid(row=row, column=1, padx=(5,5))
        
        btn_c = tk.Button(parent, width=2, bg=self.colors[key].get(), relief="solid", bd=1, highlightbackground=self.theme["BORDER_COLOR"], cursor="hand2")
        btn_c.config(command=lambda k=key, b=btn_c: self.pick_color(k, b))
        btn_c.grid(row=row, column=2, padx=2, pady=(15, 0))
        
        btn_b = tk.Checkbutton(parent, text="B", variable=self.bolds[key], font=("Arial", 9, "bold"), indicatoron=False, width=2, bg=self.theme["BG_COLOR"], fg=self.theme["TEXT_PRIMARY"], selectcolor=self.theme["ACCENT_BLUE"], cursor="hand2")
        btn_b.grid(row=row, column=3, padx=2, pady=(15, 0))
        
        btn_u = tk.Checkbutton(parent, text="U", variable=self.underlines[key], font=("Arial", 9, "underline"), indicatoron=False, width=2, bg=self.theme["BG_COLOR"], fg=self.theme["TEXT_PRIMARY"], selectcolor=self.theme["ACCENT_BLUE"], cursor="hand2")
        btn_u.grid(row=row, column=4, padx=2, pady=(15, 0))
        
        self.color_btns[key] = btn_c

    def pick_color(self, key, btn):
        # 1. Safely grab the current color and ensure it is a valid string
        current_color = str(self.colors[key].get()).strip()
        if not current_color:
            current_color = "#000000" # Fallback to black if empty
            
        # 2. parent=self.winfo_toplevel() forces it to center exactly over the main app window!
        color = colorchooser.askcolor(title="Choose color", initialcolor=current_color, parent=self.winfo_toplevel())[1]
        
        if color:
            self.colors[key].set(color)
            btn.config(bg=color)

    def browse_logo(self):
        path = filedialog.askopenfilename(filetypes=[("Image Files", "*.png;*.jpg;*.jpeg")])
        if path: InteractiveCropper(self, path, self.on_logo_cropped)
            
    def on_logo_cropped(self, final_path):
        self.logo_path_var.set(final_path)
        self.schedule_preview() 

    def draw_preview(self):
        render_preview(self)

    def load_data(self):
        comp = database.get_company(self.comp_id) 
        if not comp: return

        self.name_var.set(comp[1] if comp[1] else "")
        self.sec_var.set(comp[2] if comp[2] else ""); self.addr_var.set(comp[3] if comp[3] else "")
        self.p1_var.set(comp[4] if comp[4] else "")
        self.p2_var.set(comp[5] if len(comp) > 5 and comp[5] else "")
        self.p3_var.set(comp[6] if len(comp) > 6 and comp[6] else "")
        self.email_var.set(comp[7] if len(comp) > 7 and comp[7] else "")
        self.gst_var.set(comp[9] if len(comp) > 9 and comp[9] else ""); self.logo_path_var.set(comp[10] if len(comp) > 10 and comp[10] else "")
        self.layout_var.set(comp[11] if len(comp) > 11 and comp[11] else "Classic"); self.logo_size_var.set(str(comp[12]) if len(comp) > 12 and comp[12] else "120")
        self.logo_shape_var.set(comp[13] if len(comp)>13 and comp[13] else "Original") 

        if len(comp) > 14 and comp[14]:
            try:
                data = json.loads(comp[14])
                self.paper_size_var.set(data.get("page_size", "A4 (210*297mm)"))
                self.swap_title_order_var.set(data.get("swap_title_order", 0)) 
                self.header_spacing_var.set(data.get("header_spacing", "20"))
                self.lbl_billed_to_var.set(data.get("lbl_billed_to", "BILLED TO:"))
                self.swap_boxes_var.set(data.get("swap_boxes", 0))
                self.date_format_var.set(data.get("date_format", "DD.MM.YYYY"))
                
                old_to_new_curr = {
                    "Indian Rupees (₹)": "Indian Rupees (₹ 10,00,000.00)",
                    "US Dollar ($)": "US Dollar ($ 1,000,000.00)",
                    "Euro (€)": "Euro (€ 1.000.000,00)",
                    "British Pound (£)": "British Pound (£ 1,000,000.00)",
                    "Generic Number": "Generic Number (1,000,000.00)"
                }
                loaded_curr = data.get("currency_format", "Indian Rupees (₹ 10,00,000.00)")
                self.currency_var.set(old_to_new_curr.get(loaded_curr, loaded_curr))
                
                terms_list = data.get("terms_list")
                if terms_list: 
                    self.terms_vars = [tk.StringVar(value=re.sub(r'^\d+\.\s*', '', t)) for t in terms_list]
                else: 
                    t1 = re.sub(r'^\d+\.\s*', '', data.get("term1", "Goods once sold will not be taken back."))
                    t2 = re.sub(r'^\d+\.\s*', '', data.get("term2", "Interest @ 18% p.a. will be charged if not paid within due date."))
                    self.terms_vars = [tk.StringVar(value=t1), tk.StringVar(value=t2)]
                    
                for t in self.terms_vars: t.trace_add("write", lambda *args: self.schedule_preview())
                if self.refresh_terms_ui: self.refresh_terms_ui()
                
                self.banks_list = data.get("banks", [])
                if hasattr(self, 'bank_tree'):
                    self.refresh_bank_tree()
                
                fonts = data.get("fonts", {})
                for k in self.fonts: 
                    if k in fonts: self.fonts[k].set(str(fonts.get(k)))
                
                cols = data.get("colors", {})
                for k in self.colors:
                    c_val = cols.get(k, self.colors[k].get())
                    legacy_map = {"Black": "#000000", "Navy": "#1A237E", "Dark Red": "#B71C1C", "Dark Green": "#1B5E20"}
                    if c_val in legacy_map: c_val = legacy_map[c_val]
                    self.colors[k].set(c_val)
                    if k in self.color_btns: self.color_btns[k].config(bg=c_val)
                
                bolds = data.get("bolds", {}); unders = data.get("underlines", {})
                for k in self.bolds: 
                    if k in bolds: self.bolds[k].set(bolds.get(k))
                for k in self.underlines: 
                    if k in unders: self.underlines[k].set(unders.get(k))
                
                widths = data.get("col_widths", {})
                self.w_slno.set(widths.get("slno", 6)); self.w_hsn.set(widths.get("hsn", 12))
                self.w_qty.set(widths.get("qty", 8)); self.w_rate.set(widths.get("rate", 12))
                self.w_days.set(widths.get("days", 8)); self.w_amt.set(widths.get("amt", 14))

                self.cached_pos = data.get("pos", {})
                
                target_ms = data.get("master_scale", 0)
                self.last_master_scale = target_ms
                self.master_scale_var.set(target_ms)

                self.signatures_list = data.get("signatures", [])
                if hasattr(self, 'sig_tree'): self.refresh_sig_tree()
                
                self.show_esign_var.set(data.get("show_esign", 1))
                self.sig_scale_var.set(data.get("sig_scale", 100))
                self.sig_nudge_var.set(data.get("sig_nudge", 0))

            except Exception as e:
                print(f"Error loading saved customizations: {e}")

    def _save_to_db(self, success_msg=None):
        try: l_size = int(float(self.logo_size_var.get()))
        except: l_size = 120

        clean_fonts = {}
        for k, v in self.fonts.items():
            try: clean_fonts[k] = int(float(v.get() or 10))
            except: clean_fonts[k] = 10

        data = {
            "page_size": self.paper_size_var.get(), "swap_title_order": self.swap_title_order_var.get(), 
            "header_spacing": self.header_spacing_var.get(), "lbl_billed_to": self.lbl_billed_to_var.get(),
            "swap_boxes": self.swap_boxes_var.get(), 
            "terms_list": [t.get() for t in self.terms_vars], 
            "term1": self.terms_vars[0].get() if len(self.terms_vars) > 0 else "", 
            "term2": self.terms_vars[1].get() if len(self.terms_vars) > 1 else "",
            "date_format": self.date_format_var.get(), "currency_format": self.currency_var.get(),
            "banks": self.banks_list, "fonts": clean_fonts,
            "colors": {k: v.get() for k, v in self.colors.items()},
            "bolds": {k: v.get() for k, v in self.bolds.items()},
            "underlines": {k: v.get() for k, v in self.underlines.items()},
            "col_widths": {"slno": self.w_slno.get(), "hsn": self.w_hsn.get(), "qty": self.w_qty.get(), "rate": self.w_rate.get(), "days": self.w_days.get(), "amt": self.w_amt.get()},
            "pos": getattr(self, "cached_pos", {}),
            "master_scale": self.master_scale_var.get(),
            "signatures": getattr(self, "signatures_list", []),
            "show_esign": self.show_esign_var.get(),
            "sig_scale": self.sig_scale_var.get(),
            "sig_nudge": self.sig_nudge_var.get()
        }

        gst_status = 1 if getattr(self, 'has_gst', True) else 0

        try:
            database.update_company(
                self.comp_id, self.name_var.get(), self.sec_var.get(), self.addr_var.get(), 
                self.p1_var.get(), self.p2_var.get(), self.p3_var.get(), self.email_var.get(), 
                gst_status, self.gst_var.get(), self.logo_path_var.get(), self.layout_var.get(), 
                l_size, self.logo_shape_var.get(), json.dumps(data), self.comp_pin
            )
            if success_msg: messagebox.showinfo("Success", success_msg)
            return True
        except Exception as e:
            if success_msg: messagebox.showerror("Error", f"Could not save settings:\n{e}")
            return False

    def save_template(self):
        self._save_to_db("Template saved.")