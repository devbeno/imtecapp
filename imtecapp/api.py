import frappe
from frappe import _

@frappe.whitelist()
def get_prestashop_mappings():
    """
    Fetch mappings of categories and manufacturers from ERPNext to PrestaShop.

    Returns:
        dict: A dictionary containing lists of category and manufacturer mappings.
              {'categories': [...], 'manufacturers': [...]}
    """
    try:
        # Fetch all unique mappings of agp_id to prestashop_category_id
        categories_mapping = frappe.db.sql("""
            SELECT DISTINCT agp_id, prestashop_category_id, grupanaziv
            FROM `tabProizvodi`
            WHERE agp_id IS NOT NULL AND prestashop_category_id IS NOT NULL
        """, as_dict=True)

        # Fetch all unique mappings of sifra to prestashop_manufacturer_id
        manufacturers_mapping = frappe.db.sql("""
            SELECT DISTINCT sifra as agp_id, prestashop_manufacturer_id, proizvodjac
            FROM `tabProizvodi`
            WHERE sifra IS NOT NULL AND prestashop_manufacturer_id IS NOT NULL
        """, as_dict=True)

        # Validate and log if mappings are empty or incomplete
        if not categories_mapping:
            frappe.log_error("No category mappings found in 'Proizvodi'.", "PrestaShop Mapping Error")
            frappe.msgprint(_("No category mappings found. Please check your 'Proizvodi' data."), alert=True)

        if not manufacturers_mapping:
            frappe.log_error("No manufacturer mappings found in 'Proizvodi'.", "PrestaShop Mapping Error")
            frappe.msgprint(_("No manufacturer mappings found. Please check your 'Proizvodi' data."), alert=True)

        return {
            "categories": categories_mapping,
            "manufacturers": manufacturers_mapping,
        }

    except Exception as e:
        frappe.log_error(f"Error fetching PrestaShop mappings: {str(e)}", "Database Error")
        frappe.throw(_("An error occurred while fetching PrestaShop mappings. Please check the logs for details."))
