import frappe
from prestapyt import PrestaShopWebServiceDict
import re


@frappe.whitelist()
def sync_categories_to_prestashop():
    """
    Sync Frappe categories (grupanaziv) with PrestaShop.
    """
    # Fetch unique group names from Proizvodi
    categories = frappe.db.sql(
        """
        SELECT DISTINCT grupanaziv, prestashop_category_id
        FROM `tabProizvodi`
        WHERE grupanaziv IS NOT NULL AND grupanaziv != ''
        """,
        as_dict=True,
    )

    # Process categories and sync with PrestaShop
    for category in categories:
        group_name = category.get("grupanaziv")
        prestashop_category_id = category.get("prestashop_category_id")

        # If the category already has a PrestaShop ID, check if the name has changed
        if prestashop_category_id:
            # Step 1: Try to match the category in PrestaShop using the ID
            existing_category_name = find_prestashop_category_name_by_id(prestashop_category_id)
            
            if existing_category_name and existing_category_name != group_name:
                # Update the category name in PrestaShop if the name has changed
                updated = update_prestashop_category_name(prestashop_category_id, group_name)
                if updated:
                    print(f"Updated PrestaShop category '{prestashop_category_id}' with new name '{group_name}'.")
                else:
                    print(f"Failed to update category name for '{group_name}' in PrestaShop.")
            else:
                print(f"Category '{group_name}' already synced with PrestaShop ID {prestashop_category_id}")
        else:
            # If no PrestaShop ID exists, try to find the category by name in PrestaShop
            prestashop_category_id = find_prestashop_category_by_name(group_name)
            
            if not prestashop_category_id:
                # If no match is found, create a new category in PrestaShop
                prestashop_category_id = create_prestashop_category({"grupanaziv": group_name})

            # If a PrestaShop category ID is found or created, update the Frappe records
            if prestashop_category_id:
                # Update all Proizvodi records with this group name to set the PrestaShop category ID
                frappe.db.sql(
                    """
                    UPDATE `tabProizvodi`
                    SET prestashop_category_id = %s
                    WHERE grupanaziv = %s
                    """,
                    (prestashop_category_id, group_name),
                )
                frappe.db.commit()
                print(f"Updated category '{group_name}' with PrestaShop ID {prestashop_category_id}")
            else:
                print(f"Failed to process category '{group_name}'")



def update_prestashop_category_name(category_id: str, new_name: str):
    """Update the category name in PrestaShop for multiple languages and update the related records in Frappe."""
    try:
        settings = get_prestashop_settings()
        prestashop = PrestaShopWebServiceDict(settings["presta_url"], settings["presta_key"])

        # Fetch the existing category data from PrestaShop
        category_data = prestashop.get(f"categories/{category_id}")
        link_rewrite = generate_link_rewrite(new_name)

        # Update the category name and link rewrite for multiple languages
        languages = ['1', '2']  # Assuming '1' and '2' are the language IDs for your store
        category_data['category']['name']['language'] = [
            {'attrs': {'id': lang_id}, 'value': new_name} for lang_id in languages
        ]
        category_data['category']['link_rewrite']['language'] = [
            {'attrs': {'id': lang_id}, 'value': link_rewrite} for lang_id in languages
        ]

        # Ensure the 'id' field is present
        category_data['category']['id'] = str(category_id)

        # Remove non-writable fields from the payload
        non_writable_fields = ['level_depth', 'nb_products_recursive', 'date_add', 'date_upd', 'position']
        for field in non_writable_fields:
            if field in category_data['category']:
                del category_data['category'][field]

        # Log the payload being sent to PrestaShop
        print(f"Updating category ID {category_id} with new name '{new_name}' and link_rewrite '{link_rewrite}'")
        print(f"Payload being sent: {category_data}")

        # Send the update request to PrestaShop
        response = prestashop.edit(f"categories/{category_id}", category_data)

        # Check if the response is successful
        if 'category' in response:
            print(f"Category {category_id} successfully updated in PrestaShop.")

            # Update all Proizvodi records with this group name to set the PrestaShop category ID
            frappe.db.sql(
                """
                UPDATE `tabProizvodi`
                SET prestashop_category_id = %s
                WHERE grupanaziv = %s
                """,
                (category_id, new_name),
            )
            frappe.db.commit()

            print(f"Updated Proizvodi records with group name '{new_name}' to have PrestaShop category ID {category_id}")
            return True
        else:
            print(f"Failed to update category {category_id} in PrestaShop. Response: {response}")
            return False

    except Exception as e:
        frappe.logger().error(f"Error updating category name in PrestaShop: {str(e)}")
        print(f"Error updating category name in PrestaShop: {str(e)}")
        return False







def find_prestashop_category_name_by_id(category_id):
    """Fetch the name of a category from PrestaShop by its ID."""
    try:
        settings = get_prestashop_settings()
        prestashop = PrestaShopWebServiceDict(settings["presta_url"], settings["presta_key"])

        category = prestashop.get(f"categories/{category_id}")

        if category and 'category' in category:
            return category['category']['name']['language']['value']

        return None

    except Exception as e:
        frappe.logger().error(f"Error finding category by ID in PrestaShop: {str(e)}")
        return None


def get_prestashop_settings():
    """Retrieve PrestaShop API settings from the Frappe database."""
    settings = frappe.get_single("Generalne Postavke")
    return {
        "presta_url": settings.presta_url.rstrip("/"),
        "presta_key": settings.presta_key,
    }


def generate_link_rewrite(name):
    """Generate a URL-friendly version of the category name for PrestaShop."""
    link_rewrite = re.sub(r"\W+", "-", name.lower()).strip("-")
    return link_rewrite


def find_prestashop_category_by_name(name):
    """Check if a category with the given name already exists in PrestaShop and return its ID."""
    try:
        settings = get_prestashop_settings()
        prestashop = PrestaShopWebServiceDict(
            settings["presta_url"], settings["presta_key"]
        )

        categories = prestashop.get(
            "categories", options={"filter[name]": name, "display": "full"}
        )

        if (
            categories
            and "categories" in categories
            and len(categories["categories"]) > 0
        ):
            # Return the ID of the first matching category
            return categories["categories"][0]["id"]

        return None

    except Exception as e:
        frappe.logger().error(f"Error finding category in PrestaShop: {str(e)}")
        return None


def create_prestashop_category(category):
    """Create a new category in PrestaShop and return the ID."""
    try:
        settings = get_prestashop_settings()
        prestashop = PrestaShopWebServiceDict(
            settings["presta_url"], settings["presta_key"]
        )

        link_rewrite = generate_link_rewrite(category.get("grupanaziv"))

        new_category = {
            "category": {
                "id_parent": "2",  # Set the parent category ID
                "name": {
                    "language": {
                        "attrs": {"id": "2"},
                        "value": category.get("grupanaziv"),
                    }
                },  # Using lang 2
                "link_rewrite": {
                    "language": {"attrs": {"id": "2"}, "value": link_rewrite}
                },  # Using lang 2
                "active": 1,  # Assuming new categories should be active by default
            }
        }
        response = prestashop.add("categories", new_category)

        prestashop_category_id = response["prestashop"]["category"]["id"]
        print(f"Newly created PrestaShop category ID: {prestashop_category_id}")

        return prestashop_category_id
    except Exception as e:
        frappe.logger().error(f"Error creating category in PrestaShop: {str(e)}")
        return None
