import frappe
from frappe.model.document import Document
import pandas as pd
from frappe.utils.file_manager import get_file_path

class SalesOrderImport(Document):
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

        # Clean column names
        df.columns = df.columns.str.strip()
        
        errors = []
        parsed_data = []
        
        # Validations
        for index, row in df.iterrows():
            line_num = index + 2  # Excel row number (header is 1, 0-indexed pandas)
            
            customer = str(row.get("Customer Name", "")).strip()
            item_code = str(row.get("Item Code", "")).strip()
            qty = float(row.get("Quantity", 0))
            rate = float(row.get("Rate", 0))
            po_no = str(row.get("Customer's Purchase Order", "")).strip()
            
            if not customer or not item_code or qty <= 0:
                errors.append(f"Row {line_num}: Missing Customer, Item Code, or Quantity")
                continue
                
            # Fetch Item details (MSP and SPQ)
            # Assuming custom fields 'custom_msp' and 'custom_spq' or 'msp' and 'spq' exist on Item Doctype
            item_data = frappe.db.get_value("Item", item_code, ["custom_msp", "custom_spq"], as_dict=True)
            if not item_data:
                # Fallback to check without 'custom_' prefix if not found
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
                
            parsed_data.append(row)

        if errors:
            self.db_set("import_log", "\n".join(errors))
            frappe.throw("Validation failed. Please check the Import Log for details.")
            
        # Grouping by Customer and PO No
        grouped = df.groupby(["Customer Name", "Customer's Purchase Order"])
        
        created_sos = []
        for (customer, po_no), group in grouped:
            # Create Sales Order
            so = frappe.new_doc("Sales Order")
            so.customer = customer
            so.po_no = po_no
            
            # Use the first row for header dates
            first_row = group.iloc[0]
            so.transaction_date = first_row.get("Sales Order date")
            so.po_date = first_row.get("Customer's Purchase Order Date")
            so.delivery_date = first_row.get("Delivery Date")
            so.order_type = first_row.get("Order Type", "Sales")
            
            for _, row in group.iterrows():
                so.append("items", {
                    "item_code": str(row.get("Item Code")).strip(),
                    "qty": float(row.get("Quantity", 0)),
                    "rate": float(row.get("Rate", 0)),
                    "uom": str(row.get("UOM", "")).strip(),
                    "custom_cpn": str(row.get("CPN", "")).strip()  # Assuming custom field custom_cpn
                })
                
            so.flags.ignore_permissions = True
            try:
                so.insert()
                created_sos.append(so.name)
            except Exception as e:
                frappe.log_error(f"Error creating SO for {customer}: {str(e)}", "Sales Order Import")
                errors.append(f"Failed to create SO for Customer {customer}, PO {po_no}: {str(e)}")
                
        if errors:
            self.db_set("import_log", "Created SOs:\n" + ", ".join(created_sos) + "\n\nErrors:\n" + "\n".join(errors))
        else:
            self.db_set("import_log", "Successfully created Draft Sales Orders:\n" + "\n".join(created_sos))
            self.db_set("status", "Completed")
