import frappe
import json
import requests
import xml.etree.ElementTree as ET
import base64
from .req_utils import make_get_request, make_post_request, create_request_log


def get_prestashop_settings():
    """Retrieve PrestaShop API settings from the Frappe database."""
    settings = frappe.get_single("Generalne Postavke")
    return {
        "presta_url": settings.presta_url.rstrip("/"),  # Ensure no trailing slash
        "presta_key": settings.presta_key,
    }


def sync_prestashop_categories():
    """Sync categories between Frappe and PrestaShop, sorted by Grupanaziv."""
    try:
        print("Starting category sync...")  # Confirm function starts
        settings = get_prestashop_settings()
        print("Fetched settings")  # Confirm settings are fetched

        # Fetch and sort categories from Frappe
        frappe_categories = frappe.db.sql(
            """
            SELECT DISTINCT(grupanaziv)
            FROM `tabProizvodi`
            WHERE grupanaziv IS NOT NULL
            ORDER BY grupanaziv ASC
            """,
            as_dict=True,
        )
        print(f"Found {len(frappe_categories)} categories")  # Confirm data retrieval

        for category in frappe_categories:
            category_name = category["grupanaziv"]
            print(f"Processing category: {category_name}")

            # Check if the category exists in PrestaShop
            existing_category = get_prestashop_category_by_name(category_name, settings)
            print(f"Existing Category: {existing_category}")

            if existing_category:
                prestashop_cat_id = existing_category["id"]
                update_prestashop_category(prestashop_cat_id, category_name, settings)
                print(f"Updated category: {category_name} with ID {prestashop_cat_id}")
            else:
                prestashop_cat_id = create_prestashop_category(category_name, settings)
                print(
                    f"Created new category: {category_name} with ID {prestashop_cat_id}"
                )

            # Update the Proizvodi doctype with the PrestaShop category ID
            if prestashop_cat_id:
                frappe.db.sql(
                    """
                    UPDATE `tabProizvodi`
                    SET prestashop_cat_id = %s
                    WHERE grupanaziv = %s
                    """,
                    (prestashop_cat_id, category_name),
                )
                frappe.db.commit()
                print(f"Committed changes for: {category_name}")
            else:
                print(f"Failed to get prestashop_cat_id for {category_name}")

    except Exception as e:
        frappe.logger().error(f"Error syncing categories: {str(e)}")
        print(f"Error: {str(e)}")  # Print the error immediately
        frappe.throw(f"Error syncing categories: {str(e)}")


def get_prestashop_category_by_name(category_name, settings):
    """Check if a category exists in PrestaShop by name."""
    try:
        url = f"{settings['presta_url']}/categories"
        params = {
            "filter[name]": category_name,
            "display": "full",
            "ws_key": settings["presta_key"],
            "output_format": "JSON",
        }
        response = make_get_request(url, params=params)
        if response and response.get("categories"):
            return response["categories"][0]  # Return the first match
        return None
    except Exception as e:
        frappe.logger().error(f"Error fetching category from PrestaShop: {str(e)}")
        return None


def create_prestashop_category(category_name, settings):
    """Create a new category in PrestaShop and return the ID."""
    try:
        data = f"""
        <?xml version="1.0" encoding="UTF-8"?>
        <prestashop xmlns:xlink="http://www.w3.org/1999/xlink">
            <category>
                <name>
                    <language id="1"><![CDATA[{category_name}]]></language>
                    <language id="2"><![CDATA[{category_name}]]></language>
                </name>
                <link_rewrite>
                    <language id="1"><![CDATA[{category_name.lower().replace(" ", "-")}]]></language>
                    <language id="2"><![CDATA[{category_name.lower().replace(" ", "-")}]]></language>
                </link_rewrite>
                <active>1</active>
                <id_parent>2</id_parent>
            </category>
        </prestashop>
        """
        headers = {
            "Content-Type": "application/xml",
            "Authorization": f"Basic {base64.b64encode(settings['presta_key'].encode()).decode()}",
        }
        url = f"{settings['presta_url']}/categories"
        response = make_post_request(url, data=data, headers=headers)

        # Log the raw response for debugging
        print(f"Raw response from PrestaShop: {response}")

        # Parse the response and get the ID
        response_xml = ET.fromstring(response)
        prestashop_cat_id = (
            response_xml.find(".//id").text
            if response_xml.find(".//id") is not None
            else None
        )

        # Log the parsed ID for debugging
        print(f"Extracted category ID: {prestashop_cat_id}")

        return prestashop_cat_id
    except Exception as e:
        frappe.logger().error(f"Error creating category in PrestaShop: {str(e)}")
        return None


def update_prestashop_category(category_id, category_name, settings):
    """Update an existing category in PrestaShop."""
    try:
        data = f"""
        <?xml version="1.0" encoding="UTF-8"?>
        <prestashop xmlns:xlink="http://www.w3.org/1999/xlink">
            <category>
                <id><![CDATA[{category_id}]]></id>
                <name><![CDATA[{category_name}]]></name>
                <link_rewrite>
                    <language id="1"><![CDATA[{category_name.lower().replace(" ", "-")}]]></language>
                    <language id="2"><![CDATA[{category_name.lower().replace(" ", "-")}]]></language>
                </link_rewrite>
                <active>1</active>
            </category>
        </prestashop>
        """
        headers = {
            "Content-Type": "application/xml",
            "Authorization": f"Basic {base64.b64encode(settings['presta_key'].encode()).decode()}",
        }
        url = f"{settings['presta_url']}/categories/{category_id}"
        response = make_post_request(url, data=data, headers=headers, method="PUT")
        return response
    except Exception as e:
        frappe.logger().error(f"Error updating category in PrestaShop: {str(e)}")
        return None
