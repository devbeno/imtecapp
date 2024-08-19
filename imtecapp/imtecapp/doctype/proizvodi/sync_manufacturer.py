import frappe
from prestapyt import PrestaShopWebServiceDict


@frappe.whitelist()
def sync_manufacturers_to_prestashop():
    # Fetch unique manufacturers from Proizvodi
    manufacturers = frappe.db.sql(
        """
        SELECT DISTINCT proizvodjac
        FROM `tabProizvodi`
        WHERE proizvodjac IS NOT NULL AND proizvodjac != ''
        """,
        as_dict=True,
    )

    # Process manufacturers and sync with PrestaShop
    for manufacturer in manufacturers:
        manufacturer_name = manufacturer.get("proizvodjac")

        # Check if the manufacturer already has a PrestaShop ID
        existing_manufacturer_id = frappe.db.get_value(
            "Proizvodi",
            {
                "proizvodjac": manufacturer_name,
                "prestashop_manufacturer_id": ["is", "set"],
            },
            "prestashop_manufacturer_id",
        )

        if existing_manufacturer_id:
            print(
                f"Manufacturer '{manufacturer_name}' already has PrestaShop ID {existing_manufacturer_id}"
            )
        else:
            # Check if a manufacturer with the same name exists in PrestaShop
            prestashop_manufacturer_id = find_prestashop_manufacturer_by_name(
                manufacturer_name
            )
            if not prestashop_manufacturer_id:
                # Create a new manufacturer in PrestaShop if not found
                prestashop_manufacturer_id = create_prestashop_manufacturer(
                    {"proizvodjac": manufacturer_name}
                )

            if prestashop_manufacturer_id:
                # Update all Proizvodi with this manufacturer name to set the PrestaShop manufacturer ID
                frappe.db.sql(
                    """
                    UPDATE `tabProizvodi`
                    SET prestashop_manufacturer_id = %s
                    WHERE proizvodjac = %s
                    """,
                    (prestashop_manufacturer_id, manufacturer_name),
                )
                frappe.db.commit()
                print(
                    f"Updated manufacturer '{manufacturer_name}' with PrestaShop ID {prestashop_manufacturer_id}"
                )
            else:
                print(f"Failed to process manufacturer '{manufacturer_name}'")


def get_prestashop_settings():
    """Retrieve PrestaShop API settings from the Frappe database."""
    settings = frappe.get_single("Generalne Postavke")
    return {
        "presta_url": settings.presta_url.rstrip("/"),
        "presta_key": settings.presta_key,
    }


def find_prestashop_manufacturer_by_name(name):
    """Check if a manufacturer with the given name already exists in PrestaShop and return its ID."""
    try:
        settings = get_prestashop_settings()
        prestashop = PrestaShopWebServiceDict(
            settings["presta_url"], settings["presta_key"]
        )

        manufacturers = prestashop.get(
            "manufacturers", options={"filter[name]": name, "display": "full"}
        )

        if manufacturers and "manufacturers" in manufacturers:
            # Return the ID of the first matching manufacturer
            return manufacturers["manufacturers"][0]["id"]

        return None

    except Exception as e:
        frappe.logger().error(f"Error finding manufacturer in PrestaShop: {str(e)}")
        return None


def create_prestashop_manufacturer(manufacturer):
    """Create a new manufacturer in PrestaShop and return the ID."""
    try:
        settings = get_prestashop_settings()
        prestashop = PrestaShopWebServiceDict(
            settings["presta_url"], settings["presta_key"]
        )

        new_manufacturer = {
            "manufacturer": {
                "name": manufacturer.get("proizvodjac"),
                "active": 1,  # Assuming new manufacturers should be active by default
            }
        }
        response = prestashop.add("manufacturers", new_manufacturer)

        prestashop_manufacturer_id = response["prestashop"]["manufacturer"]["id"]
        print(f"Newly created PrestaShop manufacturer ID: {prestashop_manufacturer_id}")

        return prestashop_manufacturer_id
    except Exception as e:
        frappe.logger().error(f"Error creating manufacturer in PrestaShop: {str(e)}")
        return None
