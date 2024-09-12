import re
import requests
import frappe

PRESTASHOP_API_URL = "https://test2.imtec.ba/api/"
PRESTASHOP_WS_KEY = "APXHV1BE9ZISZQMDFEYVE6HKXPXJIGBH"

def validate_is_catalog_name(name: str) -> bool:
    """
    Validate if the name follows the isCatalogName pattern.
    
    :param name: The category name to validate.
    :return: True if the name is valid, False otherwise.
    """
    pattern = r"^[^<>;=+{}]*$"  # This is the pattern for isCatalogName
    return re.match(pattern, name) is not None

def get_all_frappe_categories():
    """
    Fetch distinct categories from the Proizvodi table where status is 'for_update'.
    
    :return: List of distinct 'grupanaziv', 'status', and 'prestashop_category_id' from Frappe.
    """
    # Query to fetch distinct 'grupanaziv', 'status', and 'prestashop_category_id'
    categories = frappe.db.sql(
        """
        SELECT DISTINCT grupanaziv, status
        FROM `tabProizvodi`
        WHERE grupanaziv IS NOT NULL 
        AND grupanaziv != ''
        """,
        as_dict=True,
    )
    
    # Return the fetched categories
    return categories

def get_prestashop_category_by_name(grupanaziv: str):
    """
    Fetch PrestaShop category by grupanaziv and fetch full category details.
    
    :param grupanaziv: The category name to search for in PrestaShop.
    :return: Dictionary containing the PrestaShop category data if found, else None.
    """
    if not validate_is_catalog_name(grupanaziv):
        print(f"Error: The PrestaShop category name '{grupanaziv}' does not conform to the isCatalogName format.")
        return None

    url = f"{PRESTASHOP_API_URL}categories?ws_key={PRESTASHOP_WS_KEY}&output_format=JSON&filter[name]={grupanaziv}&display=full"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        category_data = response.json()
        if category_data and "categories" in category_data:
            return category_data["categories"][0]  # Return the first matching category
        else:
            return None
    except requests.exceptions.RequestException as e:
        print(f"Error fetching category details from PrestaShop: {e}")
        return None

def match_categories_from_frappe():
    """
    Iterate over all Frappe categories where status is 'for_update' and find matching categories in PrestaShop.
    
    :return: List of dictionaries containing matched categories from both Frappe and PrestaShop.
    """
    matched_categories = []
    
    # Step 1: Get all categories from Frappe where status is 'for_update'
    frappe_categories = get_all_frappe_categories()
    
    # Step 2: Loop through each Frappe category and find a match in PrestaShop
    for category in frappe_categories:
        grupanaziv = category.get("grupanaziv")
        prestashop_category = get_prestashop_category_by_name(grupanaziv)
        
        # Step 3: If a match is found, add it to the results
        if prestashop_category:
            matched_categories.append({
                "NameFromFrappe": grupanaziv,
                "NameFromPrestashop": prestashop_category["name"]
            })
        else:
            print(f"No match found for Frappe category: {grupanaziv}")
    
    return matched_categories

# Example usage
matched_categories = match_categories_from_frappe()
if matched_categories:
    print(f"Matched Categories: {matched_categories}")
else:
    print("No matched categories found.")
