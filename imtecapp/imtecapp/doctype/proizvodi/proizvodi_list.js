frappe.listview_settings['Proizvodi'] = {
    onload: function(listview) {
 	listview.page.add_button(__('Sync A'), function() {
            frappe.call({
                method: 'imtecapp.imtecapp.doctype.proizvodi.proizvodi.enqueue_sync_all_active_products',
                args: { batch_size: 100 },
                callback: function(response) {
                    if (!response.exc) {
                        frappe.msgprint(__('The sync operation has been started in the background.'));
                        // Start polling for updates
                        start_progress_polling();
                    } else {
                        frappe.msgprint(__('Failed to start the sync operation. Please check the logs for more details.'));
                    }
                },
                freeze: true,
                freeze_message: __("Starting sync operation..."),
                async: true
            });
        });

        // Function to poll for sync progress
        function start_progress_polling() {
            const interval = setInterval(() => {
                frappe.call({
                    method: 'imtecapp.imtecapp.doctype.proizvodi.proizvodi.get_sync_progress',
                    callback: function(response) {
                        if (!response.exc) {
                            let progress = response.message;
                            frappe.show_alert({
                                message: `Processed ${progress.processed_records} of ${progress.total_records} products.`,
                                indicator: 'blue'
                            });

                            // Stop polling if complete or failed
                            if (progress.status === 'Completed' || progress.status === 'Failed') {
                                clearInterval(interval);
                                if (progress.status === 'Completed') {
                                    frappe.msgprint(__('Sync operation completed successfully.'));
                                } else {
                                    frappe.msgprint(__('Sync operation failed. Please check the logs.'));
                                }
                            }
                        } else {
                            frappe.msgprint(__('Failed to fetch sync progress. Please check the logs.'));
                            clearInterval(interval);
                        }
                    }
                });
            }, 5000); // Poll every 5 seconds
        }




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

        // Button to Sync All Active Products with Progress Dialog
        listview.page.add_button(__('Sync All Active Products'), function() {
            // Initialize the progress dialog
            let progress_dialog = new frappe.ui.Dialog({
                title: __('Syncing Products to PrestaShop'),
                fields: [
                    {
                        fieldtype: 'HTML',
                        fieldname: 'progress_html',
                        options: '<div class="progress"><div class="progress-bar progress-bar-striped progress-bar-animated" style="width: 0%;"></div></div>'
                    }
                ]
            });

            // Show the progress dialog
            progress_dialog.show();

            let progress_bar = progress_dialog.fields_dict.progress_html.$wrapper.find('.progress-bar');

            // Function to sync products in batches
            function sync_in_batches(products, batch_size, start_index) {
                let batch = products.slice(start_index, start_index + batch_size);
                let total = products.length;
                let synced_count = start_index;

                // Function to process each product
                function process_product(index) {
                    if (index < batch.length) {
                        frappe.call({
                            method: 'imtecapp.imtecapp.doctype.proizvodi.proizvodi.sync_product_to_prestashop_manual',
                            args: { art_sifra: batch[index].art_sifra },
                            callback: function(response) {
                                synced_count++;
                                let progress_percent = (synced_count / total) * 100;
                                progress_bar.css('width', progress_percent + '%');

                                if (!response.exc) {
                                    console.log(__('Product {0} synced successfully.', [batch[index].art_sifra]));
                                } else {
                                    frappe.msgprint(__('Failed to sync product {0}.', [batch[index].art_sifra]));
                                }

                                process_product(index + 1); // Process next product
                            }
                        });
                    } else {
                        // Move to the next batch after the current batch is processed
                        let next_start = start_index + batch_size;
                        if (next_start < total) {
                            sync_in_batches(products, batch_size, next_start);
                        } else {
                            progress_dialog.hide();
                            frappe.msgprint(__('All products have been processed.'));
                        }
                    }
                }

                // Start processing the first product in the current batch
                process_product(0);
            }

            // Fetch all active products
            frappe.call({
                method: 'frappe.client.get_list',
                args: {
                    doctype: 'Proizvodi',
                    filters: {
                        'aktivan': 1  // Ensure we're fetching products with 'aktivan' set to 1
                    },
                    fields: ['name', 'art_sifra'],
                    limit_page_length: 0 // Fetch all records
                },
                callback: function(response) {
                    if (response.message) {
                        let all_products = response.message;
                        let batch_size = 100; // Adjust batch size if necessary

                        // Start syncing in batches
                        sync_in_batches(all_products, batch_size, 0);
                    } else {
                        frappe.msgprint(__('No active products found to sync.'));
                        progress_dialog.hide();
                    }
                },
                freeze: true,
                freeze_message: __("Fetching active products..."),
                async: true
            });
        });
    }
};
