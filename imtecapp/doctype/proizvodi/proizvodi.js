// Client Script for syncing a single product to PrestaShop
frappe.ui.form.on('Proizvodi', {
    refresh: function(frm) {
        frm.add_custom_button(__('Sync to PrestaShop'), function() {
            // Call the backend method
            frappe.call({
                method: 'imtecapp.imtecapp.doctype.proizvodi.proizvodi.scripts.prestashop_sync.sync_product_to_prestashop_manual',
                args: { art_sifra: frm.doc.art_sifra },
                callback: function(response) {
                    if (!response.exc) {
                        frappe.msgprint(__('Product synced successfully.'));
                    } else {
                        frappe.msgprint(__('Failed to sync product.'));
                    }
                }
            });
        });
    }
});
