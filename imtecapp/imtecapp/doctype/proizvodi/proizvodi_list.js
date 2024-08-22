frappe.listview_settings['Proizvodi'] = {
    onload: function(listview) {
        // Button to sync all products with PrestaShop
        listview.page.add_inner_button(__('Sync All Products'), function() {
            // Notify user that sync process has started
            frappe.msgprint(__('Sync process started...'));
            console.log("Sync process started...");

            // Freeze the screen to prevent further actions during sync
            frappe.freeze(__('Syncing all products marked for update with PrestaShop...'));

            // Make the backend call to sync products
            frappe.call({
                method: 'imtecapp.imtecapp.doctype.proizvodi.proizvodi.sync_all_products_for_update',
                callback: function(response) {
                    console.log("Sync completed successfully:", response);
                    // Unfreeze the screen and show success message
                    frappe.unfreeze();
                    frappe.msgprint(__('All products marked for update successfully synced with PrestaShop.'));

                    // Refresh the list view to show updated statuses
                    listview.refresh();
                },
                error: function(error) {
                    console.log("Error during sync:", error);
                    // Unfreeze the screen and show error message
                    frappe.unfreeze();
                    frappe.msgprint(__('An error occurred during synchronization. Please check the console for more details.'));
                }
            });
        });

        // Button to reset product statuses
        listview.page.add_inner_button(__('Reset Product Statuses'), function() {
            frappe.confirm(
                __('Are you sure you want to reset the status of all products?'),
                function() {
                    frappe.msgprint(__('Resetting product statuses...'));
                    console.log("Resetting product statuses...");

                    // Make the backend call to reset product statuses
                    frappe.call({
                        method: 'imtecapp.imtecapp.doctype.proizvodi.proizvodi.reset_products_status',
                        callback: function(response) {
                            console.log("Product statuses reset successfully:", response);
                            frappe.msgprint(__('All product statuses have been reset successfully.'));

                            // Refresh the list view to show updated statuses
                            listview.refresh();
                        },
                        error: function(error) {
                            console.log("Error during reset:", error);
                            frappe.msgprint(__('An error occurred while resetting product statuses. Please check the console for more details.'));
                        }
                    });
                }
            );
        });
    }
};
