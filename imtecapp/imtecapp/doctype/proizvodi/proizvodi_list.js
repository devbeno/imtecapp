frappe.listview_settings['Proizvodi'] = {
    onload: function(listview) {
        // Button to Sync All Products for Update
        listview.page.add_button(__('Sync All Products for Update'), function() {
            frappe.call({
                method: 'imtecapp.imtecapp.doctype.proizvodi.proizvodi.sync_all_products_for_update',
                callback: function(response) {
                    if (!response.exc) {
                        frappe.msgprint(__('All products marked for update have been synced successfully.'));
                    } else {
                        frappe.msgprint(__('Failed to sync some products. Please check the logs for more details.'));
                    }
                }
            });
        });

        // Action to Sync Selected Products to PrestaShop
        listview.page.add_actions_menu_item(__('Sync to PrestaShop'), function() {
            let selected = listview.get_checked_items();
            if (selected.length === 0) {
                frappe.msgprint(__('Please select at least one product.'));
                return;
            }

            selected.forEach(function(product) {
                frappe.call({
                    method: 'imtecapp.imtecapp.doctype.proizvodi.proizvodi.sync_product_to_prestashop_manual',
                    args: { art_sifra: product.art_sifra },
                    callback: function(response) {
                        if (!response.exc) {
                            frappe.msgprint(__('Product {0} synced successfully.', [product.art_sifra]));
                        } else {
                            frappe.msgprint(__('Failed to sync product {0}.', [product.art_sifra]));
                        }
                    }
                });
            });
        });

        // Action to Insert Products from JSON with Input Dialog
        listview.page.add_actions_menu_item(__('Insert from JSON'), function() {
            let d = new frappe.ui.Dialog({
                title: __('Enter art_sifra to Fetch and Insert'),
                fields: [
                    {
                        label: __('art_sifra'),
                        fieldname: 'art_sifra',
                        fieldtype: 'Data',
                        reqd: 1,
                        description: __('Enter the art_sifra to fetch and insert the product from JSON.')
                    }
                ],
                primary_action_label: __('Fetch and Insert'),
                primary_action(values) {
                    if (values.art_sifra) {
                        frappe.call({
                            method: 'imtecapp.imtecapp.doctype.proizvodi.proizvodi.manual_insert_product_from_json',
                            args: { art_sifra: values.art_sifra },
                            callback: function(response) {
                                if (!response.exc) {
                                    frappe.msgprint(__('Product with art_sifra {0} inserted or updated successfully.', [values.art_sifra]));
                                } else {
                                    frappe.msgprint(__('Failed to insert or update product with art_sifra {0}.', [values.art_sifra]));
                                }
                            }
                        });
                        d.hide();
                    }
                }
            });

            d.show();
        });
        // New Button to Reset Products Status with Confirmation
        listview.page.add_button(__('Reset Products Status'), function() {
            frappe.confirm(__('Are you sure you want to reset the status of all products?'), 
                function() {
                    frappe.call({
                        method: 'imtecapp.imtecapp.doctype.proizvodi.proizvodi.reset_products_status',
                        callback: function(response) {
                            if (!response.exc) {
                                frappe.msgprint(__('Products status has been reset successfully.'));
                            } else {
                                frappe.msgprint(__('Failed to reset products status. Please check the logs for more details.'));
                            }
                        }
                    });
                }
            );
        });
    }
};
