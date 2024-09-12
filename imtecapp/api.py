import frappe

@frappe.whitelist()
def get_prestashop_mappings():
    # Fetch all unique mappings of agp_id to prestashop_category_id
    categories_mapping = frappe.db.sql("""
        SELECT DISTINCT agp_id, prestashop_category_id, grupanaziv
        FROM `tabProizvodi`
        WHERE agp_id IS NOT NULL AND prestashop_category_id IS NOT NULL
    """, as_dict=True)

    # Fetch all unique mappings of agp_id to prestashop_manufacturer_id
    manufacturers_mapping = frappe.db.sql("""
        SELECT DISTINCT sifra as agp_id, prestashop_manufacturer_id, proizvodjac
        FROM `tabProizvodi`
        WHERE sifra IS NOT NULL AND prestashop_manufacturer_id IS NOT NULL
    """, as_dict=True)

    return {
        "categories": categories_mapping,
        "manufacturers": manufacturers_mapping,
    }
