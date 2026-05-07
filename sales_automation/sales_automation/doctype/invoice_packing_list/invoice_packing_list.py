import frappe
from frappe.model.document import Document

class InvoicePackingList(Document):
    pass

@frappe.whitelist()
def get_invoice_items(sales_invoice):
    if not sales_invoice:
        return []
        
    doc = frappe.get_doc("Sales Invoice", sales_invoice)
    items = []
    
    for item in doc.items:
        items.append({
            "item_code": item.item_code,
            "item_name": item.item_name,
            "description": item.description,
            "qty": item.qty,
            "custom_cpn": item.get("custom_cpn", "")
        })
        
    return {
        "customer": doc.customer,
        "posting_date": doc.posting_date,
        "items": items
    }
