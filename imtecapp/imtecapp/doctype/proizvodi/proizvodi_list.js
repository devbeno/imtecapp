frappe.listview_settings['Proizvodi'] = {
    onload: function(listview) {
        listview.page.add_inner_button(__('Sync Selected with PrestaShop'), function() {
            let selected = listview.get_checked_items();

            if (selected.length === 0) {
                frappe.msgprint(__('Please select at least one product to sync.'));
                return;
            }

            let docnames = selected.map(item => item.name);

            // Show progress bar
            frappe.show_progress(__('Syncing with PrestaShop'), 0, 100, __('Syncing...'));

            frappe.call({
                method:'imtecapp.imtecapp.doctype.proizvodi.proizvodi.sync_products_to_prestashop',
                args: {
                    docnames: docnames
                },
                callback: function(response) {
                    // Hide the progress bar
                    frappe.hide_progress();
                    frappe.msgprint(__('Selected products successfully synced with PrestaShop.'));
                    listview.refresh();
                },
                error: function(error) {
                    // Hide the progress bar
                    frappe.hide_progress();
                    frappe.msgprint(__('An error occurred during synchronization. Please check the console for more details.'));
                    console.log("Error occurred:", error);
                }
            });
        });
    }
};
