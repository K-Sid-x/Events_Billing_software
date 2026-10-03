import tkinter as tk
import database

def get_theme():
    """Master Theme Dictionary - Single Source of Truth for the entire app."""
    is_dark = database.get_ui_setting("dark_mode", "1") == "1"
    if is_dark:
        return {
            "bg": "#0f172a", "card": "#1e293b", "card_hover": "#334155", 
            "border": "#64748b", "text": "#f8fafc", "text_sec": "#94a3b8", 
            "sec": "#94a3b8", "btn": "#1e293b", "btn_hover": "#334155", 
            "accent_blue": "#3b82f6", "accent_green": "#10b981", "error": "#ef4444", 
            "header": "#475569", "bulk_sel": "#2563eb", "scroll_thumb": "#94a3b8", 
            "scroll_hover": "#cbd5e1", "stripe_even": "#1e293b", "stripe_odd": "#162233"
        }
    else:
        return {
            "bg": "#f0f9ff", "card": "#ffffff", "card_hover": "#e0f2fe", 
            "border": "#bae6fd", "text": "#0f172a", "text_sec": "#0284c7", 
            "sec": "#0284c7", "btn": "#ffffff", "btn_hover": "#e0f2fe", 
            "accent_blue": "#0ea5e9", "accent_green": "#10b981", "error": "#ef4444", 
            "header": "#bae6fd", "bulk_sel": "#bae6fd", "scroll_thumb": "#64748b", 
            "scroll_hover": "#475569", "stripe_even": "#ffffff", "stripe_odd": "#f3f8fb"
        }

def add_hover(widget, default_bg, hover_bg):
    """Standard hover effect for simple widgets."""
    widget.bind("<Enter>", lambda e: widget.config(bg=hover_bg))
    widget.bind("<Leave>", lambda e: widget.config(bg=default_bg))

def add_card_hover(card, elements, default_bg, hover_bg):
    """Advanced anti-flicker hover effect for compound widgets (cards)."""
    def on_enter(e):
        card.config(bg=hover_bg)
        for el in elements:
            try: el.config(bg=hover_bg)
            except: pass
            
    def on_leave(e):
        x, y = e.x_root, e.y_root
        cx, cy = card.winfo_rootx(), card.winfo_rooty()
        cw, ch = card.winfo_width(), card.winfo_height()
        if not (cx <= x <= cx + cw and cy <= y <= cy + ch):
            card.config(bg=default_bg)
            for el in elements:
                try: el.config(bg=default_bg)
                except: pass
                
    card.bind("<Enter>", on_enter)
    card.bind("<Leave>", on_leave)
    for el in elements:
        el.bind("<Enter>", on_enter)
        el.bind("<Leave>", on_leave)

def create_perfect_button(parent, text, font, fg, bg, hover_bg, border_color, command):
    """Bypasses Windows OS button styling to create a perfect 1-pixel flat border."""
    frame = tk.Frame(parent, bg=border_color, padx=1, pady=1)
    btn = tk.Button(frame, text=text, font=font, bg=bg, fg=fg, relief="flat", bd=0, cursor="hand2", padx=14, pady=4, command=command)
    btn.pack(expand=True, fill="both")
    add_hover(btn, bg, hover_bg)
    return frame, btn