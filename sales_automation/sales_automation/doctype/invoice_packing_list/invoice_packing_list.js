frappe.ui.form.on('Invoice Packing List', {
    sales_invoice: function(frm) {
        if (frm.doc.sales_invoice) {
            frappe.call({
                method: "sales_automation.sales_automation.doctype.invoice_packing_list.invoice_packing_list.get_invoice_items",
                args: {
                    sales_invoice: frm.doc.sales_invoice
                },
                callback: function(r) {
                    if (r.message) {
                        frm.set_value('customer_name', r.message.customer);
                        frm.set_value('sales_invoice_date', r.message.posting_date);
                        
                        frm.clear_table('items');
                        
                        $.each(r.message.items, function(i, d) {
                            var row = frm.add_child('items');
                            row.item_code = d.item_code;
                            row.item_name = d.item_name;
                            row.description = d.description;
                            row.quantity = d.qty;
                            row.cpn = d.custom_cpn;
                        });
                        
                        frm.refresh_field('items');
                    }
                }
            });
        }
    }
});

frappe.ui.form.on('Invoice Packing List Item', {
    item_code: function(frm, cdt, cdn) {
        // Automatically fetch item details if manually added
        var child = locals[cdt][cdn];
        if(child.item_code) {
            frappe.db.get_value('Item', child.item_code, ['item_name', 'description'], function(r) {
                if (r) {
                    frappe.model.set_value(cdt, cdn, 'item_name', r.item_name);
                    frappe.model.set_value(cdt, cdn, 'description', r.description);
                }
            });
        }
    }
});
