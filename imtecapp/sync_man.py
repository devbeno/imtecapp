import frappe
from prestapyt import PrestaShopWebServiceDict

def get_prestashop_settings():
    """Retrieve PrestaShop API settings from the Frappe database."""
    settings = frappe.get_single("Generalne Postavke")
    return {
        "presta_url": settings.presta_url.rstrip("/"),
        "presta_key": settings.presta_key,
    }

def sync_prestashop_manufacturers():
    """Sync manufacturers between Frappe and PrestaShop, sorted by Proizvodjac."""
    try:
        print("Starting manufacturer sync...")
        settings = get_prestashop_settings()
        prestashop = PrestaShopWebServiceDict(settings['presta_url'], settings['presta_key'])

        frappe_manufacturers = frappe.db.sql("""
            SELECT name, proizvodjac, prestashop_man_id
            FROM `tabProizvodi`
            WHERE proizvodjac IS NOT NULL
            GROUP BY proizvodjac
            ORDER BY proizvodjac ASC
        """, as_dict=True)

        print(f"Found {len(frappe_manufacturers)} manufacturers")

        for manufacturer in frappe_manufacturers:
            manufacturer_name = manufacturer["proizvodjac"]
            prestashop_man_id = manufacturer["prestashop_man_id"]

            if prestashop_man_id:
                print(f"Manufacturer '{manufacturer_name}' already has PrestaShop ID: {prestashop_man_id}")
                continue

            existing_manufacturer = get_prestashop_manufacturer_by_name(prestashop, manufacturer_name)
            if existing_manufacturer:
                prestashop_man_id = existing_manufacturer['id']
                frappe.db.sql("""
                    UPDATE `tabProizvodi`
                    SET prestashop_man_id = %s
                    WHERE proizvodjac = %s
                """, (prestashop_man_id, manufacturer_name))
                frappe.db.commit()
                print(f"Manufacturer found by name: {manufacturer_name}, updated with ID {prestashop_man_id}")
            else:
                prestashop_man_id = create_prestashop_manufacturer(prestashop, manufacturer_name)
                if prestashop_man_id:
                    print(f"Created new manufacturer: {manufacturer_name} with ID {prestashop_man_id}")
                    frappe.db.sql("""
                        UPDATE `tabProizvodi`
                        SET prestashop_man_id = %s
                        WHERE proizvodjac = %s
                    """, (prestashop_man_id, manufacturer_name))
                    frappe.db.commit()
                else:
                    print(f"Failed to create manufacturer for: {manufacturer_name}")

    except Exception as e:
        frappe.logger().error(f"Error syncing manufacturers: {str(e)}")
        print(f"Error: {str(e)}")

def get_prestashop_manufacturer_by_name(prestashop, manufacturer_name):
    """Check if a manufacturer exists in PrestaShop by name."""
    try:
        search_query = {'filter[name]': manufacturer_name, 'display': 'full'}
        response = prestashop.search('manufacturers', options=search_query)
        if 'manufacturers' in response and response['manufacturers']:
            return response['manufacturers'][0]  # Return the first match
        return None
    except Exception as e:
        frappe.logger().error(f"Error fetching manufacturer from PrestaShop: {str(e)}")
        return None

def create_prestashop_manufacturer(prestashop, manufacturer_name):
    """Create a new manufacturer in PrestaShop and return the ID."""
    try:
        new_manufacturer = {
            'manufacturer': {
                'active': '1',
                'name': manufacturer_name
            }
        }
        response = prestashop.add('manufacturers', new_manufacturer)
        prestashop_man_id = response['prestashop']['manufacturer']['id']
        return prestashop_man_id
    except Exception as e:
        frappe.logger().error(f"Error creating manufacturer in PrestaShop: {str(e)}")
        return None
