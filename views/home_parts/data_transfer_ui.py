import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import database
from views.home_parts.ui_components import get_theme

try:
    from utils import data_transfer
except ImportError:
    data_transfer = None

# --- THE FIX: Standalone Security Gatekeeper for Data Transfers ---
def verify_pin_and_execute(parent_pop, target_id, t, execute_callback):
    comp = database.get_company(target_id)
    comp_pin = comp[15] if comp and len(comp) > 15 else ""
    
    if not comp_pin:
        execute_callback()
        return
        
    pin_pop = tk.Toplevel(parent_pop)
    pin_pop.title("Security Check")
    pin_pop.geometry("300x200")
    pin_pop.configure(bg=t["card"])
    pin_pop.grab_set()
    
    tk.Label(pin_pop, text="🔒 Security Clearance Required", font=("Arial", 12, "bold"), bg=t["card"], fg=t["text"]).pack(pady=(20, 5))
    tk.Label(pin_pop, text="Enter PIN to authorize data transfer:", font=("Arial", 9), bg=t["card"], fg=t["sec"]).pack(pady=(0, 15))
    
    pin_var = tk.StringVar()
    ent = tk.Entry(pin_pop, textvariable=pin_var, font=("Arial", 16, "bold"), justify="center", width=8, show="●", bg=t["bg"], fg=t["text"], insertbackground=t["text"], highlightbackground=t["border"], highlightthickness=1)
    ent.pack(pady=5)
    
    pin_pop.after(50, lambda: [pin_pop.focus_force(), ent.focus_set()])
    
    def check(e=None):
        if pin_var.get() == comp_pin:
            pin_pop.destroy()
            execute_callback()
        else:
            messagebox.showerror("Access Denied", "Incorrect PIN.", parent=pin_pop)
            
    ent.bind("<Return>", check)
    tk.Button(pin_pop, text="Authorize", font=("Arial", 10, "bold"), bg=t["accent_blue"], fg="#ffffff", cursor="hand2", relief="flat", padx=15, pady=5, command=check).pack(pady=10)
# ------------------------------------------------------------------

def trigger_import(home_view):
    if getattr(home_view.app, "current_role", "") != "Admin":
        messagebox.showerror("Access Denied", "Only the Master Admin can import data.", parent=home_view)
        return
    if not data_transfer:
        messagebox.showerror("Error", "data_transfer.py module not found in utils folder!")
        return
    
    filepath = filedialog.askopenfilename(title="Select Backup File to Import", filetypes=[("BillX Backup", "*.billx"), ("JSON Files", "*.json")])
    if not filepath: return

    try:
        scan = data_transfer.scan_backup_file(filepath)
        if scan['has_profile']:
            if messagebox.askyesno("Clone Company Detected", "This file contains a full company profile.\n\nDo you want to clone this into a brand new company card on your Home screen?", parent=home_view):
                data_transfer.import_company_data(filepath, target_company_id=None)
                messagebox.showinfo("Success", "Company successfully cloned!", parent=home_view)
                home_view.load_companies()
        else:
            open_partial_import_popup(home_view, filepath)
    except Exception as e:
        messagebox.showerror("Import Failed", f"An error occurred reading the file:\n{str(e)}", parent=home_view)

def open_partial_import_popup(home_view, filepath):
    t = get_theme()  # Fetch dynamic theme
    pop = tk.Toplevel(home_view)
    pop.title("Merge Partial Data")
    pop.geometry("450x250")
    pop.configure(bg=t["card"])
    pop.grab_set()

    # Note: Hardcoded a specific yellow alert color for this label only, as requested by the UI design
    tk.Label(pop, text="Partial Data Detected", font=("Arial", 14, "bold"), bg=t["card"], fg="#f59e0b").pack(anchor="w", padx=30, pady=(25, 5))
    tk.Label(pop, text="Which company should this data be injected into?", font=("Arial", 9), bg=t["card"], fg=t["sec"]).pack(anchor="w", padx=30, pady=(0, 20))

    companies = database.get_all_companies()
    # --- THE FIX: Make the label mathematically unique to prevent Dictionary Overwrites! ---
    comp_dict = {f"{c[1]} (ID: {c[0]})": c[0] for c in companies}
    comp_names = list(comp_dict.keys())
    # -------------------------------------------------------------------------------------

    combo_var = tk.StringVar()
    cb = ttk.Combobox(pop, textvariable=combo_var, values=comp_names, state="readonly", font=("Arial", 11), width=40)
    cb.pack(padx=30, pady=5)
    if comp_names: cb.current(0)

    def confirm_merge():
        if not combo_var.get(): return
        target_id = comp_dict[combo_var.get()]
        
        def do_merge():
            try:
                data_transfer.import_company_data(filepath, target_company_id=target_id)
                messagebox.showinfo("Success", "Data successfully merged!", parent=pop)
                pop.destroy()
            except Exception as e:
                messagebox.showerror("Merge Failed", str(e), parent=pop)
                
        verify_pin_and_execute(pop, target_id, t, do_merge)

    tk.Button(pop, text="Inject Data", font=("Arial", 11, "bold"), bg=t["accent_blue"], fg="#ffffff", cursor="hand2", relief="flat", padx=20, pady=8, command=confirm_merge).pack(pady=(20, 0))

def open_export_popup(home_view):
    if getattr(home_view.app, "current_role", "") != "Admin":
        messagebox.showerror("Access Denied", "Only the Master Admin can export data.", parent=home_view)
        return
    if not data_transfer: return
    t = get_theme()  # Fetch dynamic theme
    pop = tk.Toplevel(home_view)
    pop.title("Export Company Data")
    pop.geometry("450x480")
    pop.configure(bg=t["card"])
    pop.grab_set()

    tk.Label(pop, text="1. Select Target Company", font=("Arial", 12, "bold"), bg=t["card"], fg=t["text"]).pack(anchor="w", padx=30, pady=(25, 5))
    
    companies = database.get_all_companies()
    if not companies: return

    # --- THE FIX: Apply the same unique naming convention to the export dropdown! ---
    comp_dict = {f"{c[1]} (ID: {c[0]})": c[0] for c in companies}
    comp_names = list(comp_dict.keys())
    # --------------------------------------------------------------------------------
    combo_var = tk.StringVar()
    cb = ttk.Combobox(pop, textvariable=combo_var, values=comp_names, state="readonly", font=("Arial", 11), width=35)
    cb.pack(anchor="w", padx=30, pady=(0, 20))
    cb.current(0)

    tk.Label(pop, text="2. Select Data to Export", font=("Arial", 12, "bold"), bg=t["card"], fg=t["text"]).pack(anchor="w", padx=30, pady=(10, 10))

    opts = [
        ("Company Profile & Settings", tk.BooleanVar(value=True)), 
        ("Customers & Clients", tk.BooleanVar(value=True)), 
        ("Employees & Payroll", tk.BooleanVar(value=True)), 
        ("Inventory & Stock", tk.BooleanVar(value=True)), 
        ("Invoices & Billing", tk.BooleanVar(value=True)),
        ("Purchases & Vendor Bills", tk.BooleanVar(value=True)),
        ("General Expenses", tk.BooleanVar(value=True))
    ]
    
    for text, var in opts:
        tk.Checkbutton(pop, text=text, variable=var, bg=t["card"], fg=t["text"], selectcolor=t["bg"], activebackground=t["card"], activeforeground=t["text"], font=("Arial", 11), cursor="hand2").pack(anchor="w", padx=40, pady=5)

    def confirm_export():
        target_id = comp_dict[combo_var.get()]
        
        def do_export():
            filepath = filedialog.asksaveasfilename(parent=pop, title="Save Export File", defaultextension=".billx", filetypes=[("BillX Backup", "*.billx")])
            if filepath:
                try:
                    selections = {
                        "settings": opts[0][1].get(), "customers": opts[1][1].get(), 
                        "employees": opts[2][1].get(), "inventory": opts[3][1].get(), 
                        "invoices": opts[4][1].get(), "purchases": opts[5][1].get(),
                        "expenses": opts[6][1].get()
                    }
                    data_transfer.export_company_data(filepath, target_id, selections)
                    messagebox.showinfo("Success", f"Data exported successfully to:\n{filepath}", parent=pop)
                    pop.destroy()
                except Exception as e:
                    messagebox.showerror("Export Failed", str(e), parent=pop)
                    
        verify_pin_and_execute(pop, target_id, t, do_export)

    tk.Button(pop, text="Confirm & Package File", font=("Arial", 11, "bold"), bg=t["accent_blue"], fg="#ffffff", cursor="hand2", relief="flat", padx=20, pady=8, command=confirm_export).pack(pady=(25, 0))