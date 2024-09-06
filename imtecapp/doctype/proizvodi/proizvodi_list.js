// proizvodi_list.js

frappe.listview_settings['Proizvodi'] = {
    onload: function(listview) {
        // Add a button to fetch data from the Eline API
        listview.page.add_menu_item(__('Fetch Data from Eline API'), function() {
            fetch_data_from_eline();
        });

        // Add a button to update the selected products on PrestaShop
        listview.page.add_menu_item(__('Update Selected Products on PrestaShop'), function() {
            update_selected_products_on_prestashop(listview);
        });

        // Add a button to manually update a product
        listview.page.add_menu_item(__('Manually Update Product'), function() {
            manually_update_product(listview);
        });

        // Add a button to activate the selected products
        listview.page.add_menu_item(__('Activate Selected Products'), function() {
            change_selected_products_status(listview, 'activate');
        });

        // Add a button to deactivate the selected products
        listview.page.add_menu_item(__('Deactivate Selected Products'), function() {
            change_selected_products_status(listview, 'deactivate');
        });
    }
};

// Function to fetch data from the Eline API
function fetch_data_from_eline() {
    frappe.call({
        method: 'imtecapp.imtecapp.doctype.proizvodi.scripts.data_sync.fetch_and_insert_current_eline_data',
        callback: function(response) {
            if (!response.exc) {
                frappe.msgprint(__('Data successfully fetched and inserted.'));
                frappe.listview.refresh();
            } else {
                frappe.msgprint({
                    title: __('Error'),
                    message: __('Failed to fetch data from Eline API. Please check the logs for more details.'),
                    indicator: 'red'
                });
            }
        }
    });
}

// Function to update selected products on PrestaShop
function update_selected_products_on_prestashop(listview) {
    let selected_products = listview.get_checked_items();
    if (selected_products.length === 0) {
        frappe.msgprint(__('Please select at least one product.'));
        return;
    }

    frappe.call({
        method: 'imtecapp.imtecapp.doctype.proizvodi.scripts.prestashop_sync.sync_product_to_prestashop_manual',
        args: { art_sifra: selected_products.map(product => product.name) },
        callback: function(response) {
            if (!response.exc) {
                frappe.msgprint(__('Selected product(s) successfully updated on PrestaShop.'));
                frappe.listview.refresh();
            } else {
                frappe.msgprint({
                    title: __('Error'),
                    message: __('Failed to update product(s) on PrestaShop. Please check the logs for more details.'),
                    indicator: 'red'
                });
            }
        }
    });
}

// Function to manually update a product
function manually_update_product(listview) {
    let selected_products = listview.get_checked_items();
    if (selected_products.length !== 1) {
        frappe.msgprint(__('Please select exactly one product to manually update.'));
        return;
    }

    let art_sifra = selected_products[0].name;

    frappe.prompt(
        {
            fieldtype: 'Data',
            label: __('New Art Sifra'),
            fieldname: 'new_art_sifra',
            reqd: 1
        },
        function(values) {
            frappe.call({
                method: 'imtecapp.imtecapp.doctype.proizvodi.scripts.data_sync.manual_insert_product_from_json',
                args: { art_sifra: art_sifra, new_art_sifra: values.new_art_sifra },
                callback: function(response) {
                    if (!response.exc) {
                        frappe.msgprint(__('Product manually updated successfully.'));
                        frappe.listview.refresh();
                    } else {
                        frappe.msgprint({
                            title: __('Error'),
                            message: __('Failed to manually update product. Please check the logs for more details.'),
                            indicator: 'red'
                        });
                    }
                }
            });
        },
        __('Enter New Art Sifra'),
        __('Update')
    );
}

// Function to change the status of selected products to activate or deactivate
function change_selected_products_status(listview, action) {
    let selected_products = listview.get_checked_items();
    if (selected_products.length === 0) {
        frappe.msgprint(__('Please select at least one product.'));
        return;
    }

    let new_status = (action === 'activate') ? 1 : 0;

    frappe.call({
        method: 'imtecapp.imtecapp.doctype.proizvodi.scripts.prestashop_sync.update_product_status',
        args: { product_ids: selected_products.map(product => product.name), status: new_status },
        callback: function(response) {
            if (!response.exc) {
                let message = (action === 'activate') ? __('Selected product(s) activated.') : __('Selected product(s) deactivated.');
                frappe.msgprint(message);
                frappe.listview.refresh();
            } else {
                frappe.msgprint({
                    title: __('Error'),
                    message: __('Failed to change the status of selected product(s). Please check the logs for more details.'),
                    indicator: 'red'
                });
            }
        }
    });
}
