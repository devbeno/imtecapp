# path: imtecapp/imtecapp/imtecapp/doctype/proizvodi/start_sync.py
# path of proizvodi: imtecapp/imtecapp/imtecapp/doctype/proizvodi/proizvodi.py

import frappe
from imtecapp.imtecapp.doctype.proizvodi.proizvodi import (
    sync_product_to_prestashop,
    synchronize_all_products_for_update,
    manual_json_product_insert,
    reset_all_product_statuses,
    insert_product_to_prestashop,
    rename_prestashop_product_by_reference,
    sync_all_products_with_stock,
    sync_active_products_to_prestashop
)

def check_permissions():
    """Ensure the user is logged in and has the correct permissions."""
    if frappe.session.user == "Guest":
        frappe.throw("You must be logged in to perform this action.", frappe.PermissionError)

    # Optionally, check if the user has a specific role or permission
    if not frappe.has_permission("Proizvodi", "write"):
        frappe.throw("You do not have permission to perform this action.", frappe.PermissionError)


@frappe.whitelist()
def sync_active_products():
    """Synchronize a product to PrestaShop by its art_sifra."""
    check_permissions()  # Ensure permissions are checked
    sync_active_products_to_prestashop()
    print(f"Product with art_sifra synchronized to PrestaShop.")
    ### old function name sync_product_to_prestashop_manual()

@frappe.whitelist()
def sync_product(art_sifra):
    """Synchronize a product to PrestaShop by its art_sifra."""
    check_permissions()  # Ensure permissions are checked
    sync_product_to_prestashop(art_sifra)
    print(f"Product with art_sifra {art_sifra} synchronized to PrestaShop.")
    ### old function name sync_product_to_prestashop_manual()

@frappe.whitelist()
def sync_all_products(witheline=True):
    """Synchronize all products marked for update to PrestaShop, with the option to include Eline data."""
    check_permissions()  # Ensure permissions are checked
    synchronize_all_products_for_update(witheline=True)  # Pass True to ensure Eline sync
    print("All Proizvodi and Prestashop were updated.")
    ### old function name sync_all_products_for_update()


@frappe.whitelist()
def sync_all_products_without_eline(witheline=False):
    """Synchronize all products marked for update to PrestaShop without Eline."""
    check_permissions()  # Ensure permissions are checked
    synchronize_all_products_for_update(witheline=False)  # Disable Eline sync by setting witheline to False
    print("All Proizvodi and Prestashop were updated without Eline.")
    ### old function name sync_all_products_for_update()

@frappe.whitelist()
def insert_product_from_json(art_sifra):
    """Manually insert a product to the system from JSON based on art_sifra."""
    check_permissions()  # Ensure permissions are checked
    manual_json_product_insert(art_sifra)
    print(f"Product with art_sifra {art_sifra} inserted from JSON.")
    ### old function name manual_insert_product_from_json()

@frappe.whitelist()
def reset_product_statuses():
    """Reset all product statuses in the Frappe system."""
    check_permissions()  # Ensure permissions are checked
    reset_all_product_statuses()
    print("All product statuses have been reset.")
    ### old function name reset_products_status()

@frappe.whitelist()
def insert_product(art_sifra):
    """Insert a product into PrestaShop based on its art_sifra."""
    check_permissions()  # Ensure permissions are checked
    insert_product_to_prestashop(art_sifra)
    print(f"Product with art_sifra {art_sifra} has been inserted into PrestaShop.")
    ### old function name sync_product_to_prestashop_insert()

@frappe.whitelist()
def rename_product(art_sifra):
    """Rename a product in PrestaShop based on its reference art_sifra."""
    check_permissions()  # Ensure permissions are checked
    rename_prestashop_product_by_reference(art_sifra)
    print(f"Product with art_sifra {art_sifra} renamed in PrestaShop.")
    ### old function name sync_product_to_prestashop_rename()

@frappe.whitelist()
def sync_products_with_stock():
    """Synchronize all products that have non-zero stock to PrestaShop."""
    check_permissions()  # Ensure permissions are checked
    sync_all_products_with_stock()
    print("All products with stock have been synchronized to PrestaShop.")
    ### old function name sync_all_stanje_products()