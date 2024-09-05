
import frappe
from prestapyt import PrestaShopWebServiceDict
from .utils import log_message, generate_link_rewrite
from .db_operations import create_sync_log, update_sync_log

@frappe.whitelist()
def sync_categories_to_prestashop():
    categories = frappe.db.sql(
        """
        SELECT DISTINCT grupanaziv, prestashop_category_id
        FROM `tabProizvodi`
        WHERE grupanaziv IS NOT NULL AND grupanaziv != ''
        """,
        as_dict=True,
    )
    for category in categories:
        group_name = category.get("grupanaziv")
        prestashop_category_id = category.get("prestashop_category_id")
        if prestashop_category_id:
            existing_category_name = find_prestashop_category_name_by_id(prestashop_category_id)
            if existing_category_name and existing_category_name != group_name:
                updated = update_prestashop_category_name(prestashop_category_id, group_name)
                if updated:
                    print(f"Updated PrestaShop category '{prestashop_category_id}' with new name '{group_name}'.")
                else:
                    print(f"Failed to update category name for '{group_name}' in PrestaShop.")
            else:
                print(f"Category '{group_name}' already synced with PrestaShop ID {prestashop_category_id}")
        else:
            prestashop_category_id = find_prestashop_category_by_name(group_name)
            if not prestashop_category_id:
                prestashop_category_id = create_prestashop_category({"grupanaziv": group_name})
            if prestashop_category_id:
                frappe.db.sql(
                    """
                    UPDATE `tabProizvodi`
                    SET prestashop_category_id = %s
                    WHERE grupanaziv = %s
                    """,
                    (prestashop_category_id, group_name),
                )
                frappe.db.commit()

@frappe.whitelist()
def sync_manufacturers_to_prestashop():
    manufacturers = frappe.db.sql(
        """
        SELECT DISTINCT proizvodjac, prestashop_manufacturer_id
        FROM `tabProizvodi`
        WHERE proizvodjac IS NOT NULL AND proizvodjac != ''
        """,
        as_dict=True,
    )
    for manufacturer in manufacturers:
        manufacturer_name = manufacturer.get("proizvodjac")
        prestashop_manufacturer_id = manufacturer.get("prestashop_manufacturer_id")
        if prestashop_manufacturer_id:
            existing_manufacturer_name = find_prestashop_manufacturer_name_by_id(prestashop_manufacturer_id)
            if existing_manufacturer_name and existing_manufacturer_name != manufacturer_name:
                updated = update_prestashop_manufacturer_name(prestashop_manufacturer_id, manufacturer_name)
                if updated:
                    print(f"Updated PrestaShop manufacturer '{prestashop_manufacturer_id}' with new name '{manufacturer_name}'.")
                else:
                    print(f"Failed to update manufacturer name for '{manufacturer_name}' in PrestaShop.")
            else:
                print(f"Manufacturer '{manufacturer_name}' already synced with PrestaShop ID {prestashop_manufacturer_id}")
        else:
            prestashop_manufacturer_id = find_prestashop_manufacturer_by_name(manufacturer_name)
            if not prestashop_manufacturer_id:
                prestashop_manufacturer_id = create_prestashop_manufacturer({"proizvodjac": manufacturer_name})
            if prestashop_manufacturer_id:
                frappe.db.sql(
                    """
                    UPDATE `tabProizvodi`
                    SET prestashop_manufacturer_id = %s
                    WHERE proizvodjac = %s
                    """,
                    (prestashop_manufacturer_id, manufacturer_name),
                )
                frappe.db.commit()
