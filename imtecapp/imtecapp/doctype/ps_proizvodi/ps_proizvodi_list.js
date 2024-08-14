frappe.listview_settings['PS Proizvodi'] = {
    onload: function(listview) {
        listview.page.add_menu_item(__('Sync with Proizvodi'), function() {
            frappe.call({
                method: "imtecapp.imtecapp.doctype.ps_proizvodi.ps_proizvodi.sync_with_proizvodi",
                callback: function(r) {
                    frappe.msgprint(__("Synchronization completed successfully"));
                },
                freeze: true,
                freeze_message: __("Synchronizing...")
            });
        });

        // Listen for the realtime progress updates
        frappe.realtime.on('sync_progress', (data) => {
            if (!listview.sync_progress_dialog) {
                listview.sync_progress_dialog = new frappe.ui.Dialog({
                    title: __('Synchronizing...'),
                    fields: [
                        {
                            label: __('Status'),
                            fieldname: 'status',
                            fieldtype: 'HTML',
                            options: `<div style="margin-bottom: 10px;" id="sync-status">${data.status}</div>`
                        },
                        {
                            fieldname: 'progress',
                            fieldtype: 'Progress',
                            label: __('Progress'),
                            default: 0,
                            max: data.total
                        }
                    ]
                });
                listview.sync_progress_dialog.show();
            }

            listview.sync_progress_dialog.get_field('progress').set_value(data.progress);
            document.getElementById('sync-status').innerText = data.status;

            if (data.progress >= data.total) {
                setTimeout(() => {
                    listview.sync_progress_dialog.hide();
                }, 1000);
            }
        });
        listview.page.add_menu_item(__('sync_products_with_logging'), function() {
            frappe.call({
                method: 'imtecapp.imtecapp.doctype.ps_proizvodi.ps_proizvodi.sync_all_to_prestashop',
                callback: function(r) {
                    frappe.msgprint(__("Synchronization completed successfully"));
                },
                freeze: true,
                freeze_message: __("Synchronizing...")
            });
        });
        listview.page.add_menu_item(__('sync_cat'), function() {
            frappe.call({
                method: 'imtecapp.imtecapp.doctype.ps_proizvodi.ps_proizvodi.sync_cat',
                callback: function(r) {
                    frappe.msgprint(__("Synchronization completed successfully"));
                },
                freeze: true,
                freeze_message: __("Synchronizing...")
            });
        });
        listview.page.add_menu_item(__('sync_man'), function() {
            frappe.call({
                method: 'imtecapp.imtecapp.doctype.ps_proizvodi.ps_proizvodi.sync_man',
                callback: function(r) {
                    frappe.msgprint(__("Synchronization completed successfully"));
                },
                freeze: true,
                freeze_message: __("Synchronizing...")
            });
        });
        
    }
};
