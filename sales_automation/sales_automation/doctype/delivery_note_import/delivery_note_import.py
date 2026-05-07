import frappe
from frappe.model.document import Document
import pandas as pd
from frappe.utils.file_manager import get_file_path

class DeliveryNoteImport(Document):
    def on_submit(self):
        self.process_import()

    def process_import(self):
        if not self.excel_file:
            frappe.throw("Please attach an Excel file before submitting.")

        file_path = get_file_path(self.excel_file[1:] if self.excel_file.startswith("/") else self.excel_file)
        
        try:
            df = pd.read_excel(file_path)
        except Exception as e:
            frappe.throw(f"Error reading Excel file: {str(e)}")

        df.columns = df.columns.str.strip()
        
        errors = []
        parsed_data = []
        
        # Validations
        for index, row in df.iterrows():
            line_num = index + 2
            
            customer = str(row.get("Customer Name", "")).strip()
            item_code = str(row.get("Item Code", "")).strip()
            qty = float(row.get("Quantity", 0))
            rate = float(row.get("Rate", 0))
            
            if not customer or not item_code or qty <= 0:
                errors.append(f"Row {line_num}: Missing Customer, Item Code, or Quantity")
                continue
                
            # Fetch Item details (MSP and SPQ)
            item_data = frappe.db.get_value("Item", item_code, ["custom_msp", "custom_spq"], as_dict=True)
            if not item_data:
                item_data = frappe.db.get_value("Item", item_code, ["msp", "spq"], as_dict=True)
                
            if item_data:
                msp = float(item_data.get("custom_msp") or item_data.get("msp") or 0)
                spq = float(item_data.get("custom_spq") or item_data.get("spq") or 1)
                
                if msp > 0 and rate < msp:
                    errors.append(f"Row {line_num}: Item {item_code} Rate ({rate}) is below MSP ({msp})")
                    
                if spq > 0 and (qty % spq != 0):
                    errors.append(f"Row {line_num}: Item {item_code} Quantity ({qty}) is not a multiple of SPQ ({spq})")
            else:
                errors.append(f"Row {line_num}: Item {item_code} not found in system")
                

        if errors:
            self.db_set("import_log", "\n".join(errors))
            frappe.throw("Validation failed. Please check the Import Log for details.")
            
        # Grouping by Customer and PO No
        grouped = df.groupby(["Customer Name", "Customer's Purchase Order"])
        
        created_dns = []
        for (customer, po_no), group in grouped:
            # Find Submitted Sales Order for this customer and PO
            so_name = frappe.db.get_value("Sales Order", 
                                          {"customer": customer, "po_no": po_no, "docstatus": 1}, 
                                          "name")
            if not so_name:
                errors.append(f"Could not find a Submitted Sales Order for Customer '{customer}' with PO '{po_no}'")
                continue
                
            so_doc = frappe.get_doc("Sales Order", so_name)
            
            # Create Delivery Note
            dn = frappe.new_doc("Delivery Note")
            dn.customer = customer
            
            for _, row in group.iterrows():
                item_code = str(row.get("Item Code")).strip()
                qty = float(row.get("Quantity", 0))
                
                # Find the SO Item Detail to link against
                so_item = next((item for item in so_doc.items if item.item_code == item_code), None)
                if not so_item:
                    errors.append(f"Item '{item_code}' not found in Sales Order '{so_name}'")
                    continue
                
                dn.append("items", {
                    "item_code": item_code,
                    "qty": qty,
                    "uom": str(row.get("UOM", "")).strip(),
                    "rate": float(row.get("Rate", 0)),
                    "against_sales_order": so_name,
                    "so_detail": so_item.name,
                    "custom_cpn": str(row.get("CPN", "")).strip()
                })
                
            dn.flags.ignore_permissions = True
            try:
                dn.insert()
                created_dns.append(dn.name)
            except Exception as e:
                frappe.log_error(f"Error creating DN for {customer}: {str(e)}", "Delivery Note Import")
                errors.append(f"Failed to create DN for Customer {customer}, PO {po_no}: {str(e)}")
                
        if errors:
            self.db_set("import_log", "Created DNs:\n" + ", ".join(created_dns) + "\n\nErrors:\n" + "\n".join(errors))
        else:
            self.db_set("import_log", "Successfully created Draft Delivery Notes:\n" + "\n".join(created_dns))
            self.db_set("status", "Completed")
