import frappe
from frappe.integrations.utils import make_post_request, make_get_request
import re


def get_prestashop_settings():
    """Retrieve PrestaShop API settings from the Frappe database."""
    settings = frappe.get_single("Generalne Postavke")
    return {
        "presta_url": settings.presta_url.rstrip("/"),  # Ensure no trailing slash
        "presta_key": settings.presta_key,
    }


def get_prestashop_resource(
    resource_type, filters=None, display="full", output_format="JSON"
):
    """Generalized function to retrieve resources from PrestaShop API."""
    try:
        settings = get_prestashop_settings()
        prestashop_url = f"{settings['presta_url']}/{resource_type}"

        params = {
            "display": display,
            "ws_key": settings["presta_key"],
            "output_format": output_format,
        }

        if filters:
            for key, value in filters.items():
                params[f"filter[{key}]"] = value

        # Debugging: Print the URL and parameters
        print(f"Requesting PrestaShop API with URL: {prestashop_url}")
        print(f"Parameters: {params}")

        # Make the API request using frappe's make_get_request
        response = make_get_request(prestashop_url, params=params)

        # Debugging: Print the response
        if isinstance(response, dict):
            print("API Response:", response)
        else:
            print("API Response Text:", response)

        return response

    except Exception as e:
        frappe.logger().error(
            f"Error fetching {resource_type} from PrestaShop: {str(e)}"
        )
        return None


def update_stock_quantity(stock_id, quantity, settings):
    """Update the stock quantity for a given stock ID in PrestaShop."""
    try:
        presta_url = settings['presta_url'].rstrip("/")
        presta_key = settings['presta_key']

        # XML payload for updating stock
        data = f"""
        <prestashop xmlns:xlink="http://www.w3.org/1999/xlink">
            <stock_available>
                <id><![CDATA[{stock_id}]]></id>
                <quantity><![CDATA[{quantity}]]></quantity>
            </stock_available>
        </prestashop>
        """

        # Construct the URL for the PrestaShop API endpoint
        prestashop_url = f"{presta_url}/stock_availables/{stock_id}"

        # Prepare the headers, including authorization
        headers = {
            "Content-Type": "application/xml",
            "Authorization": f"Basic {presta_key}",
        }

        # Send the request to update the stock
        response = make_post_request(
            url=prestashop_url, data=data, headers=headers, method="PATCH"
        )

        # Check if the response was successful
        if response:
            print(f"Stock quantity updated for Stock ID {stock_id} to {quantity}.")
            return response
        else:
            print(f"Failed to update stock for Stock ID {stock_id}.")
            return None

    except Exception as e:
        frappe.logger().error(f"Error updating stock quantity: {str(e)}")
        return None



# from imtecapp.utils import get_prestashop_resource

# # Fetching product by reference directly
# product_161031 = get_prestashop_resource("products", filters={"reference": "161031"})
# product_100004 = get_prestashop_resource("products", filters={"reference": "100004"})

# # Print the raw responses
# print("Response for Product 161031:")
# print(product_161031)

# print("\nResponse for Product 100004:")
# print(product_100004)

# # Check if the responses contain the expected structure
# if product_161031 and "products" in product_161031:
#     stock_associations_161031 = product_161031["products"][0].get("associations", {}).get("stock_availables", [])
#     print("Stock Associations for 161031:", stock_associations_161031)
# else:
#     print("Product 161031 not found or structured unexpectedly.")

# if product_100004 and "products" in product_100004:
#     stock_associations_100004 = product_100004["products"][0].get("associations", {}).get("stock_availables", [])
#     print("Stock Associations for 100004:", stock_associations_100004)
# else:
#     print("Product 100004 not found or structured unexpectedly.")

# Example Usage
# Now, instead of creating a specific function for each resource type (e.g., products, categories, manufacturers), you can use get_prestashop_resource:

# def get_product_by_reference(reference):
#     """Retrieve a product by its reference code from PrestaShop."""
#     return get_prestashop_resource("products", filters={"reference": reference})

# def get_category_by_name(name):
#     """Retrieve a category by its name from PrestaShop."""
#     return get_prestashop_resource("categories", filters={"name": name})

# def get_stock_by_product_id(product_id):
#     """Retrieve stock information by product ID from PrestaShop."""
#     return get_prestashop_resource("stock_availables", filters={"id_product": product_id})


def clean_name(name, max_length=128):
    if not isinstance(name, str):
        return name
    name = name.strip().lower()
    name = re.sub(r"\s+", " ", name)
    name = re.sub(r"[^\w\s-]", "", name)
    name = name.capitalize()

    if len(name) > max_length:
        name = name[:max_length]
        if " " in name:
            name = name[: name.rfind(" ")]

    return name


def generate_link_rewrite(name, max_length=128):
    """Generate a URL-friendly version of the product name."""
    name = re.sub(r"[<>;=#{}]", "", name)
    link_rewrite = re.sub(r"\s+", "-", name.lower())
    link_rewrite = re.sub(r"[^\w-]", "", link_rewrite)
    return link_rewrite[:max_length]


def clean_product_name(name, max_length=128):
    # Function implementation
    if not isinstance(name, str):
        return name
    name = name.strip()
    name = re.sub(r"[^\w\s\-\+,.\(\)]+", "", name)

    if len(name) > max_length:
        name = name[:max_length]
        if " " in name:
            name = name[: name.rfind(" ")]

    return name
