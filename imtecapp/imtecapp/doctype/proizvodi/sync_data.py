import frappe
import requests
import xmltodict
import re
import base64

# Constants
STATUSES = [200, 201, 204]

# Utility functions

def handle_none(value):
    return value if value is not None else ""


def clean_response(response_text):
    clean_text = re.sub(r"^.*?(<\?xml)", r"\1", response_text, flags=re.DOTALL)
    return clean_text

def truncate_string(input_string, max_length):
    """
    Truncate the input string to the specified maximum length.
    
    :param input_string: The string to truncate.
    :param max_length: Maximum length of the string.
    :return: Truncated string if the input string exceeds max_length.
    """
    return input_string[:max_length]

def generate_link_rewrite(name):
    name = name.lower()
    name = re.sub(r"[^a-z0-9]+", "-", name)
    name = name.strip("-")
    return name if name else "default-link-rewrite"

# PrestaShop API utility functions

def get_prestashop_settings():
    """
    Fetch PrestaShop settings from Frappe.
    """
    return frappe.get_single("Generalne Postavke")


def get_prestashop_url(path):
    """
    Builds the full PrestaShop API URL.
    """
    settings = get_prestashop_settings()
    return settings.presta_url + '/api/' + path


def check_prestashop_response(res, ret):
    """
    Validates the PrestaShop API response status.
    """
    if res.status_code not in STATUSES:
        raise Exception(f"Status {res.status_code}, {ret}")
    return ret


def prestashop_request(method, path, params=None, data=None):
    """
    General request function to interact with the PrestaShop API.

    :param method: HTTP method (GET, POST, PUT, DELETE)
    :param path: API resource path (e.g., 'products', 'categories')
    :param params: Optional query parameters
    :param data: Optional payload for POST/PUT requests
    :return: Parsed XML response from PrestaShop
    """
    settings = get_prestashop_settings()
    headers = {
        "Authorization": "Basic " + base64.b64encode(f"{settings.presta_key}:".encode()).decode(),
        "Content-Type": "application/xml"
    }

    if data is not None:
        data = xmltodict.unparse({'prestashop': data}).encode('utf-8')

    res = requests.request(method, get_prestashop_url(path), auth=(settings.presta_key, ''), params=params, data=data, headers=headers)
    return check_prestashop_response(res, xmltodict.parse(res.text)['prestashop'] if res.text else None)

# PrestaShop API interaction functions

def prestashop_add(path, data):
    """
    Add (POST) a resource to PrestaShop.
    """
    return prestashop_request('POST', path, data=data)


def prestashop_get(path, params=None):
    """
    Retrieve (GET) a resource from PrestaShop.
    """
    return prestashop_request('GET', path, params=params)


def prestashop_edit(path, data):
    """
    Edit (PUT) a resource in PrestaShop.
    """
    return prestashop_request('PUT', path, data=data)


def prestashop_delete(path):
    """
    Delete (DELETE) a resource from PrestaShop.
    """
    return prestashop_request('DELETE', path)

# Missing functions

def update_prestashop_category_name(category_id, new_name):
    settings = get_prestashop_settings()
    category_data = prestashop_get(f"categories/{category_id}")
    link_rewrite = generate_link_rewrite(new_name)

    category_data['category']['name']['language']['value'] = new_name
    category_data['category']['link_rewrite']['language']['value'] = link_rewrite

    prestashop_edit(f"categories/{category_id}", category_data)
    return True

def find_prestashop_category_name_by_id(category_id):
    settings = get_prestashop_settings()
    category = prestashop_get(f"categories/{category_id}")

    if category and 'category' in category:
        return category['category']['name']['language']['value']
    return None

def create_prestashop_category(category):
    """
    Create a new category in PrestaShop.

    :param category: Dictionary containing category information (e.g., 'grupanaziv')
    :return: ID of the newly created PrestaShop category
    """
    # Fetch PrestaShop settings
    settings = get_prestashop_settings()
    
    # Ensure 'grupanaziv' (category name) is provided
    group_name = handle_none(category.get("grupanaziv"))
    
    if not group_name:
        raise ValueError("Category name (grupanaziv) cannot be empty.")

    # Generate link rewrite for the category
    link_rewrite = generate_link_rewrite(group_name)

    # Construct the new category payload for PrestaShop API
    new_category = {
        "category": {
            "id_parent": "2",  # Assuming parent category ID is 2 (adjust as necessary)
            "name": {
                "language": [
                    {
                        "@id": "2",  # Language ID, assuming '1' is the default language (change if needed)
                        "#text": group_name
                    }
                ]
            },
            "link_rewrite": {
                "language": [
                    {
                        "@id": "2",  # Language ID
                        "#text": link_rewrite  # URL-friendly link rewrite
                    }
                ]
            },
            "active": 1  # Make category active by default
        }
    }

    # Log the payload for debugging purposes
    print(f"Creating category with payload: {new_category}")

    # Add the category to PrestaShop via POST request
    response = prestashop_add("categories", new_category)

    # Ensure we have a response before attempting to extract the ID
    if not response or 'category' not in response:
        raise Exception(f"Failed to create category. Response: {response}")

    # Return the ID of the newly created category
    return response['category']['id']




def update_prestashop_manufacturer_name(manufacturer_id, new_name):
    settings = get_prestashop_settings()
    manufacturer_data = prestashop_get(f"manufacturers/{manufacturer_id}")
    manufacturer_data['manufacturer']['name'] = new_name

    prestashop_edit(f"manufacturers/{manufacturer_id}", manufacturer_data)
    return True

def find_prestashop_manufacturer_name_by_id(manufacturer_id):
    settings = get_prestashop_settings()
    manufacturer = prestashop_get(f"manufacturers/{manufacturer_id}")

    if manufacturer and 'manufacturer' in manufacturer:
        return manufacturer['manufacturer']['name']
    return None

def create_prestashop_manufacturer(manufacturer):
    """
    Create a new manufacturer in PrestaShop and return the ID.
    """
    try:
        # Prepare the payload for the manufacturer
        new_manufacturer = {
            "manufacturer": {
                "name": manufacturer.get("proizvodjac"),
                "active": 1
            }
        }

        # Send request to PrestaShop
        response = prestashop_add("manufacturers", new_manufacturer)
        
        # Debugging: Print the response to see what PrestaShop returns
        print(f"Response from PrestaShop: {response}")

        # Check if 'prestashop' exists in response
        if 'manufacturer' in response:
            return response['manufacturer']['id']
        else:
            raise Exception(f"Error in PrestaShop response: {response}")

    except Exception as e:
        # Log error if something goes wrong
        frappe.logger().error(f"Error creating manufacturer in PrestaShop: {str(e)}")
        return None



def find_prestashop_category_by_name(name):
    """
    Check if a category with the given name already exists in PrestaShop and return its ID.

    :param name: Name of the category to search for
    :return: ID of the category if found, otherwise None
    """
    try:
        response = prestashop_get('categories', params={"filter[name]": name, "display": "full"})

        if response and "categories" in response:
            categories = response["categories"]["category"]
            if categories:
                return categories[0]["id"]
        return None  
    except Exception as e:
        frappe.logger().error(f"Error finding category '{name}' in PrestaShop: {str(e)}")
        return None


def find_prestashop_manufacturer_by_name(name):
    """
    Check if a manufacturer with the given name already exists in PrestaShop and return its ID.

    :param name: Name of the manufacturer to search for
    :return: ID of the manufacturer if found, otherwise None
    """
    try:
        response = prestashop_get('manufacturers', params={"filter[name]": name, "display": "full"})

        if response and "manufacturers" in response:
            manufacturers = response["manufacturers"]["manufacturer"]
            if manufacturers:
                return manufacturers[0]["id"]
        return None  
    except Exception as e:
        frappe.logger().error(f"Error finding manufacturer '{name}' in PrestaShop: {str(e)}")
        return None

# Sync Functions

def sync_categories_to_prestashop():
    """
    Sync all unique categories from the 'Proizvodi' doctype in Frappe to PrestaShop.
    """
    # Fetch all unique category names from Proizvodi
    categories = frappe.db.sql("""
        SELECT DISTINCT grupanaziv, prestashop_category_id
        FROM `tabProizvodi`
        WHERE grupanaziv IS NOT NULL AND grupanaziv != ''
    """, as_dict=True)

    # Process and sync each category
    for category in categories:
        group_name = handle_none(category.get("grupanaziv"))
        prestashop_category_id = category.get("prestashop_category_id")

        # If PrestaShop category ID already exists, check if name has changed
        if prestashop_category_id:
            existing_category_name = find_prestashop_category_name_by_id(prestashop_category_id)
            if existing_category_name and existing_category_name != group_name:
                update_prestashop_category_name(prestashop_category_id, group_name)
        else:
            # If not already synced, check if the category exists in PrestaShop
            prestashop_category_id = find_prestashop_category_by_name(group_name)
            if not prestashop_category_id:
                # Create the new category in PrestaShop
                prestashop_category_id = create_prestashop_category({"grupanaziv": group_name})

            # Sync PrestaShop category ID back to Frappe
            if prestashop_category_id:
                frappe.db.sql("""
                    UPDATE `tabProizvodi`
                    SET prestashop_category_id = %s
                    WHERE grupanaziv = %s
                """, (prestashop_category_id, group_name))
                frappe.db.commit()


def sync_manufacturers_to_prestashop():
    manufacturers = frappe.db.sql("""
        SELECT DISTINCT proizvodjac, prestashop_manufacturer_id
        FROM `tabProizvodi`
        WHERE proizvodjac IS NOT NULL AND proizvodjac != ''
        """, as_dict=True)

    for manufacturer in manufacturers:
        manufacturer_name = manufacturer.get("proizvodjac")
        prestashop_manufacturer_id = manufacturer.get("prestashop_manufacturer_id")

        if prestashop_manufacturer_id:
            existing_manufacturer_name = find_prestashop_manufacturer_name_by_id(prestashop_manufacturer_id)
            if existing_manufacturer_name and existing_manufacturer_name != manufacturer_name:
                update_prestashop_manufacturer_name(prestashop_manufacturer_id, manufacturer_name)
        else:
            prestashop_manufacturer_id = find_prestashop_manufacturer_by_name(manufacturer_name)
            if not prestashop_manufacturer_id:
                prestashop_manufacturer_id = create_prestashop_manufacturer({"proizvodjac": manufacturer_name})

            if prestashop_manufacturer_id:
                frappe.db.sql("""
                    UPDATE tabProizvodi
                    SET prestashop_manufacturer_id = %s
                    WHERE proizvodjac = %s
                    """, (prestashop_manufacturer_id, manufacturer_name))
                frappe.db.commit()


def sync_products_to_prestashop():
    """
    Syncs all products from the Frappe "Proizvodi" doctype to PrestaShop.
    """
    products = frappe.get_all("Proizvodi", filters={"aktivan": 1}, fields=["*"])

    for product in products:
        try:
            # Ensure critical fields are present and not None
            if not product.get('art_sifra'):
                frappe.log_error(f"Product {product} missing 'art_sifra'. Skipping...")
                continue

            if not product.get('art_naziv'):
                frappe.log_error(f"Product {product['art_sifra']} missing 'art_naziv'. Skipping...")
                continue

            # Fetch default category and additional categories for the product
            default_category_id = product.get("prestashop_category_id", "")  # Default to '2' if missing

            # Prepare categories XML structure
            categories_xml = f"""
            <category>
                <id>2</id>  <!-- Default parent category, adjust as needed -->
            </category>
            <category>
                <id>{default_category_id}</id>
            </category>
            """

            existing_categories = product.get("categories", [])
            if not isinstance(existing_categories, list):
                existing_categories = []

            for category_id in existing_categories:
                if category_id and category_id != "2" and category_id != str(default_category_id):
                    categories_xml += f"""
                    <category>
                        <id>{category_id}</id>
                    </category>
                    """

            # Prepare link rewrite (SEO-friendly URL)
            prname = product.get("art_naziv", "")
            link_rewrite = generate_link_rewrite(prname)
            
            # Prepare PrestaShop product payload with correct names and link_rewrite for both languages
            product_payload = {
                'product': {
                    'id': f"{product['prestashop_id']}" if product['prestashop_id'] else '',
                    'reference': product['art_sifra'],
                    'name': {
                        'language': [
                            {'attrs': {'id': 1}, 'value': product['art_naziv']},  # Language 1 (English)
                            {'attrs': {'id': 2}, 'value': product['art_naziv']}   # Language 2
                        ]
                    },
                    'price': product['vpc'],
                    'mpn': product['kataloski'],
                    'active': int(product['aktivan']),
                    'link_rewrite': {
                        'language': [
                            {'attrs': {'id': 1}, 'value': link_rewrite},  # Language 1 (English)
                            {'attrs': {'id': 2}, 'value': link_rewrite}   # Language 2
                        ]
                    },
                    'id_category_default': default_category_id,
                    'id_manufacturer': product.get('prestashop_manufacturer_id', ""),
                    'associations': {
                        'categories': categories_xml
                    },
                    'description': {
                        'language': [
                            {'attrs': {'id': 1}, 'value': handle_none(product.get('description', ""))},
                            {'attrs': {'id': 2}, 'value': handle_none(product.get('description', ""))}
                        ]
                    },
                    'description_short': handle_none(product.get('description_short', "")),
                    'meta_description': {
                        'language': [
                            {'attrs': {'id': 1}, 'value': handle_none(product.get('meta_description', ""))},
                            {'attrs': {'id': 2}, 'value': handle_none(product.get('meta_description', ""))}
                        ]
                    },
                    'meta_keywords': {
                        'language': [
                            {'attrs': {'id': 1}, 'value': handle_none(product.get('meta_keywords', ""))},
                            {'attrs': {'id': 2}, 'value': handle_none(product.get('meta_keywords', ""))}
                        ]
                    },
                    'meta_title': {
                        'language': [
                            {'attrs': {'id': 1}, 'value': handle_none(product.get('meta_title', ""))},
                            {'attrs': {'id': 2}, 'value': handle_none(product.get('meta_title', ""))}
                        ]
                    },
                    'state': '1',  # Set the state to '1' (published)
                    'minimal_quantity': '1',  # Set the minimal quantity
                }
            }

            # Check if product exists in PrestaShop by reference
            response = prestashop_get('products', params={"filter[reference]": product['art_sifra']})
            # Log and validate the response
            if response and 'products' in response and response['products']:
                # Update existing product in PrestaShop
                prestashop_edit(f"products/{response['products']['product'][0]['id']}", product_payload)
            else:
                # Create a new product in PrestaShop
                prestashop_add('products', product_payload)

        except Exception as e:
            # Log the error with the product details for debugging
            error_message = f"Error syncing product {product['art_sifra']}: {str(e)}"
            truncated_error = truncate_string(error_message, 140)
            frappe.log_error(truncated_error)




def sync_stocks_to_prestashop():
    """
    Syncs the stock availability for each product to PrestaShop.
    """
    products = frappe.get_all("Proizvodi", fields=["art_sifra", "stanje"])

    for product in products:
        response = prestashop_get('stock_availables', params={"filter[reference]": product['art_sifra']})
        
        if response and 'stock_availables' in response:
            stock_data = {
                'stock_available': {
                    'quantity': product['stanje']
                }
            }
            prestashop_edit(f"stock_availables/{response['stock_availables']['stock_available'][0]['id']}", stock_data)
        else:
            # Handle case where stock data does not exist
            frappe.log_error(f"Failed to sync stock for product {product['art_sifra']}")


