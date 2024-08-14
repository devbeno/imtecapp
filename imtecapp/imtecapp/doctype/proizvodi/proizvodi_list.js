frappe.ui.form.on('Proizvodi', {
    refresh: function(frm) {
        console.log("Proizvodi form loaded");
        frm.add_custom_button(__('Sync Proizvodi'), function() {
            frappe.call({
                method: 'imtecapp.imtecapp.doctype.proizvodi.eline.sync_proizvodi.sync_proizvodi',
                callback: function(r) {
                    frappe.msgprint(__('Sync process has started in the background. You will be notified once it is complete.'));
                }
            });
        });
    }
});
