
from frappe.utils.background_jobs import enqueue
import frappe
from imtecapp.sync_operations import sync_product_to_prestashop_insert

def enqueue_sync_all_active_products():
    """Enqueue the task to sync all active products to PrestaShop in the background."""
    sync_progress = frappe.get_doc({
        "doctype": "Sync Progress",
        "total_records": frappe.db.count(
            "Proizvodi",
            {
                "aktivan": 1,
                "agp_id": ["!=", ""],
                "sifra": ["!=", ""],
            },
        ),
        "processed_records": 0,
        "status": "In Progress",
    })
    sync_progress.insert()
    frappe.db.commit()

    enqueue(
        method=sync_all_active_products,
        queue="long",
        timeout=2500,
        job_name="Sync All Active Products",
        sync_progress_name=sync_progress.name,
    )
    frappe.msgprint(_("The sync operation has been started in the background."))

def sync_all_active_products(sync_progress_name=None):
    """Sync all active products to PrestaShop."""
    try:
        active_products = frappe.get_all(
            "Proizvodi",
            filters={
                "aktivan": 1,
                "status": ["!=", "on_presta"],
                "agp_id": ["is", "set"],
                "sifra": ["is", "set"],
            },
            fields=["art_sifra"],
        )

        total_records = len(active_products)
        processed_count = 0

        sync_progress = frappe.get_doc("Sync Progress", sync_progress_name)
        sync_progress.total_records = total_records
        sync_progress.processed_records = processed_count
        sync_progress.status = "In Progress"
        sync_progress.save()

        for product in active_products:
            try:
                sync_product_to_prestashop_insert(product["art_sifra"])
                frappe.db.set_value("Proizvodi", product["art_sifra"], "status", "on_presta")
                processed_count += 1
                sync_progress.processed_records = processed_count
                sync_progress.save()
            except Exception as e:
                frappe.log_error(f"Sync failed for product {product['art_sifra']}: {str(e)}", "Product Sync Error")

        sync_progress.status = "Completed"
        sync_progress.save()

    except frappe.DoesNotExistError as e:
        frappe.log_error(f"Sync Progress document not found: {str(e)}", "Sync Progress Error")
        frappe.throw(_("Sync Progress document not found. Please check the progress name."))

    except Exception as e:
        sync_progress.status = "Failed"
        sync_progress.save()
        frappe.log_error(f"Sync failed: {str(e)}", "Sync All Active Products Error")
        frappe.throw(_("Failed to sync some products. Please check the logs for more details."))

def sync_all_products_for_update():
    """Sync all products that need updating to PrestaShop."""
    sync_log = create_sync_log("Sync All Products for Update")

    try:
        insert_data_from_for_insert_eline_data()

        products_for_update = frappe.get_all(
            "Proizvodi",
            filters={"status": "for_update"},
            fields=["art_sifra"]
        )

        for product in products_for_update:
            try:
                sync_product_to_prestashop_manual(product["art_sifra"])
            except Exception as e:
                frappe.log_error(f"Failed to sync product {product['art_sifra']}: {str(e)}", "Product Sync Error")

        update_sync_log(sync_log, "All products updated successfully.", status="Success")

    except Exception as e:
        update_sync_log(sync_log, f"Error updating products: {str(e)}", status="Failed")
