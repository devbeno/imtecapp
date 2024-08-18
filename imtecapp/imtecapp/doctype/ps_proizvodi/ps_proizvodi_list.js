frappe.listview_settings['PS Proizvodi'] = {
    onload: function(listview) {
        listview.page.add_inner_button(__('Upload from PrestaShop'), function() {
            // Show progress bar
            frappe.show_progress('Uploading Data', 0, 100, 'Progress', true);

            // Start the server call
            frappe.call({
                method: "imtecapp.imtecapp.doctype.ps_proizvodi.ps_proizvodi.generate_and_upload_data",
                freeze: true,
                freeze_message: "Uploading data from PrestaShop...",
                callback: function(r) {
                    frappe.hide_progress();
                    frappe.msgprint(__('Data uploaded successfully.'));
                    listview.refresh();
                }
            });

            // Listen for progress updates
            frappe.realtime.on('upload_progress', function(data) {
                frappe.show_progress('Uploading Data', data.progress, 100, 'Progress', true);
            });
        });
        listview.page.add_inner_button(__('op'), function() {
            // Show progress bar
            frappe.call({
                method: 'imtecapp.imtecapp.doctype.ps_proizvodi.ps_proizvodi.call_generate_and_upload_data',
                args: {
                    docname: 'Proizvodi'
                },
                callback: function(response) {
                    if (response.message) {
                        frappe.msgprint("Data generated and uploaded successfully!");
                    }
                }
            });
            
            
            
        });
    }
};
