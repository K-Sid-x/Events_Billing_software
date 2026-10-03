import tkinter as tk
from tkinter import ttk, messagebox
import database
from views.invoice_parts.invoice_actions import show_preview_from_db

def open_recycle_bin(view):
    comp_id = getattr(view.winfo_toplevel(), "active_company_id", 1)
    pop = tk.Toplevel(view)
    pop.title("Deleted Invoices") 
    
    pop.geometry("460x500") 
    pop.configure(bg=view.BG)
    pop.transient(view.winfo_toplevel())
    pop.focus_force()
    pop.grab_set()
    
    tk.Label(pop, text="Deleted Invoices", font=("Arial", 16, "bold"), bg=view.BG, fg=view.FG).pack(pady=(20, 5))
    
    tk.Label(pop, text="Restoring an invoice will automatically re-deduct its items from inventory.", font=("Arial", 10), bg=view.BG, fg=view.SEC_FG, wraplength=420, justify="center").pack(pady=(0, 20))
    
    list_f = tk.Frame(pop, bg=view.CARD, highlightbackground=view.BORDER, highlightthickness=1)
    list_f.pack(fill="both", expand=True, padx=20, pady=(0, 20))
    
    # --- THE FIX: Thick Solid Scrollbar Styles! ---
    style = ttk.Style(pop)
    style.theme_use("default")
    style.configure("Recycle.Vertical.TScrollbar", background=view.SEC_FG, troughcolor=view.BG, bordercolor=view.BG, arrowcolor=view.FG, relief="flat")
    style.map("Recycle.Vertical.TScrollbar", background=[("active", view.BLUE)])
    # ----------------------------------------------
    
    # --- THE FIX: Ghost Column Architecture ---
    columns = ("inv_num", "actions", "ghost")
    tree = ttk.Treeview(list_f, columns=columns, show="headings", height=10, style="Theme.Treeview")
    
    tree.heading("inv_num", text="INVOICE NO.", anchor="center")
    tree.heading("actions", text="ACTIONS", anchor="center")
    tree.heading("ghost", text="")

    try:
        import json
        del_w_raw = database.get_ui_setting("inv_del_cols", "{}")
        del_w = json.loads(del_w_raw) if del_w_raw else {}
    except:
        del_w = {}

    tree.column("inv_num", width=del_w.get("inv_num", 120), anchor="center", stretch=False)
    tree.column("actions", width=del_w.get("actions", 260), anchor="center", stretch=False) 
    tree.column("ghost", width=10, minwidth=10, stretch=True)

    def save_del_widths():
        new_w = {c: tree.column(c, "width") for c in ("inv_num", "actions")}
        try: database.save_ui_setting("inv_del_cols", json.dumps(new_w))
        except: pass
    # ---------------------------------------------------

    def on_del_sep_drag(event):
        if tree.identify_region(event.x, event.y) == "separator":
            pop.after(50, save_del_widths)

    tree.bind("<B1-Motion>", on_del_sep_drag, add="+")
    tree.bind("<ButtonRelease-1>", lambda e: pop.after(50, save_del_widths), add="+")
    
    # --- THE FIX: Apply the isolated thick scrollbar style ---
    scroll = ttk.Scrollbar(list_f, orient="vertical", command=tree.yview, style="Recycle.Vertical.TScrollbar")
    # ---------------------------------------------------------
    tree.configure(yscrollcommand=scroll.set)
    scroll.pack(side="right", fill="y")
    tree.pack(side="left", fill="both", expand=True)
    
    is_admin = getattr(view.winfo_toplevel(), "current_role", "") == "Admin"

    def load_cleared_items():
        for item in tree.get_children(): tree.delete(item)
        
        # --- THE FIX: Engage Company Firewall before fetching deleted items! ---
        database.set_active_company(comp_id)
        cleared = database.get_deleted_invoices()
        # -----------------------------------------------------------------------
        
        if not cleared:
            view.stat_deleted_var.set("0")
            for idx in range(1, 11):
                stripe = "even" if idx % 2 == 0 else "odd"
                # --- THE FIX: Pad with Ghost value ---
                tree.insert("", "end", iid=f"dummy_{idx}", values=("", "", ""), tags=(stripe, 'dummy'))
            tree.tag_configure("even", background=view.STRIPE_EVEN)
            tree.tag_configure("odd", background=view.STRIPE_ODD)
            return
            
        view.stat_deleted_var.set(str(len(cleared)))
        action_label = "⟲ Restore   |   ❌ Delete" if is_admin else "⟲ Restore"
        for idx, i in enumerate(cleared, 1):
            stripe = "even" if idx % 2 == 0 else "odd"
            tree.insert("", "end", iid=str(i[0]), values=(i[2], action_label, ""), tags=(stripe,))
            
        current_rows = len(cleared)
        if current_rows < 10:
            for idx in range(current_rows + 1, 11):
                stripe = "even" if idx % 2 == 0 else "odd"
                tree.insert("", "end", iid=f"dummy_{idx}", values=("", "", ""), tags=(stripe, 'dummy'))
                
        tree.tag_configure("even", background=view.STRIPE_EVEN)
        tree.tag_configure("odd", background=view.STRIPE_ODD)

    def on_right_click(event):
        region = tree.identify("region", event.x, event.y)
        if region == "cell":
            row_id = tree.identify_row(event.y)
            if not row_id or 'dummy' in tree.item(row_id, 'tags'): return
            
            # THE FIX: Context menu strictly on Right-Click (Hard Delete restricted to Admin)
            tree.selection_set(row_id)
            menu = tk.Menu(pop, tearoff=0, font=("Arial", 10), bg=view.CARD, fg=view.FG, activebackground=view.BLUE, activeforeground="#ffffff")
            menu.add_command(label="⟲ Restore Invoice", command=lambda: restore_inv(row_id))
            if is_admin:
                menu.add_separator()
                menu.add_command(label="❌ Clear Permanently", foreground=view.RED, command=lambda: hard_clear_inv(row_id))
            menu.tk_popup(event.x_root, event.y_root)

    def on_left_click(event):
        region = tree.identify("region", event.x, event.y)
        if region == "cell":
            col = tree.identify_column(event.x)
            row_id = tree.identify_row(event.y)
            if not row_id or 'dummy' in tree.item(row_id, 'tags'): return
            
            if col == "#2":
                if not is_admin:
                    restore_inv(row_id)
                    return
                # THE FIX: Trigger exact action based on where Admin clicks in the cell
                try:
                    x_rel = event.x - tree.bbox(row_id, col)[0]
                    if x_rel < 130:  # Clicked on the left side (Restore)
                        restore_inv(row_id)
                    elif x_rel > 140: # Clicked on the right side (Delete)
                        hard_clear_inv(row_id)
                except: pass

    def on_double_click(event):
        region = tree.identify("region", event.x, event.y)
        if region == "cell":
            col = tree.identify_column(event.x)
            row_id = tree.identify_row(event.y)
            if not row_id or 'dummy' in tree.item(row_id, 'tags'): return
            
            # THE FIX: Double clicking Invoice No. opens Live Preview
            if col == "#1":
                show_preview_from_db(view, row_id)

    def restore_inv(inv_id):
        if messagebox.askyesno("Restore", "Restore this invoice to the active ledger?", parent=pop):
            inv_r, _ = database.get_invoice_by_id(inv_id)
            database.restore_invoice(inv_id)
            if inv_r:
                database.log_audit(
                    "Invoices", "Restored", inv_r[3],
                    f"Restored from Recycle Bin • Customer: {inv_r[4]}",
                    inv_r[10], company_id=comp_id
                )
            load_cleared_items()
            view.load_data()
            messagebox.showinfo("Restored", "Invoice successfully restored.", parent=pop)

    def hard_clear_inv(inv_id):
        if not is_admin:
            messagebox.showerror("Access Denied", "Only the Master Admin can permanently delete invoices from the Recycle Bin.", parent=pop)
            return
        if messagebox.askyesno("Confirm", "Permanently clear this invoice? This action cannot be undone.", parent=pop):
            inv_r, _ = database.get_invoice_by_id(inv_id)
            database.hard_delete_invoice(inv_id)
            if inv_r:
                database.log_audit(
                    "Invoices", "Hard Deleted", inv_r[3],
                    f"Permanently erased from Recycle Bin • Customer: {inv_r[4]}",
                    inv_r[10], company_id=comp_id
                )
            load_cleared_items()
            view.load_data()

    # THE FIX: Bind the Left, Right, and Double click events correctly
    tree.bind("<ButtonRelease-1>", on_left_click)
    tree.bind("<Button-3>", on_right_click)
    tree.bind("<Double-1>", on_double_click)
    
    # THE FIX: Hand cursor triggers over BOTH Invoice No. (#1) and Actions (#2)
    tree.bind("<Motion>", lambda e: tree.config(cursor="hand2") if tree.identify_column(e.x) in ("#1", "#2") and tree.identify_row(e.y) and 'dummy' not in tree.item(tree.identify_row(e.y), 'tags') else tree.config(cursor=""))
    
    pop.update_idletasks()
    try:
        main_x = view.winfo_rootx()
        main_y = view.winfo_rooty()
        main_w = view.winfo_width()
        main_h = view.winfo_height()
        
        x = main_x + (main_w // 2) - (460 // 2)
        y = main_y + (main_h // 2) - (500 // 2)
        pop.geometry(f"+{max(0, x)}+{max(0, y)}")
    except Exception:
        pass
        
    load_cleared_items()