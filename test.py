import requests

# API base URL and API key
BASE_URL = 'https://test2.imtec.ba/api/'
API_KEY = 'APXHV1BE9ZISZQMDFEYVE6HKXPXJIGBH'

# Set up headers for authentication
HEADERS = {
    'Authorization': f'Bearer {API_KEY}',
    'Content-Type': 'application/json'
}

def get_all_products():
    """Fetches all products from the API."""
    url = f'{BASE_URL}products'
    response = requests.get(url, headers=HEADERS)

    if response.status_code == 200:
        print("Fetched all products successfully.")
        return response.json()  # Parse JSON response
    else:
        print(f"Failed to fetch products: {response.status_code}")
        return None

def update_product_stock(product_id, new_stock_quantity):
    """Updates the stock of a given product."""
    url = f'{BASE_URL}products/{product_id}'
    payload = {
        'stock_quantity': new_stock_quantity
    }

    response = requests.put(url, headers=HEADERS, json=payload)

    if response.status_code == 200:
        print(f"Product {product_id} stock updated successfully.")
        return response.json()  # Parse JSON response
    else:
        print(f"Failed to update product stock: {response.status_code}")
        return None

def create_new_product(name, reference, price, stock_quantity):
    """Creates a new product in the API."""
    url = f'{BASE_URL}products'
    payload = {
        'name': name,
        'reference': reference,
        'price': price,
        'stock_quantity': stock_quantity
    }

    response = requests.post(url, headers=HEADERS, json=payload)

    if response.status_code == 201:
        print(f"Product {name} created successfully.")
        return response.json()  # Parse JSON response
    else:
        print(f"Failed to create product: {response.status_code}")
        return None

def find_product_by_reference(reference, products):
    """Finds a product in the list by its reference."""
    for product in products:
        if product['reference'] == reference:
            return product
    return None

def main_workflow():
    # Step 1: Get all products
    products = get_all_products()

    if products:
        # Define the reference to search for
        product_reference = 'EXAMPLE123'

        # Step 2: Find product by reference
        product = find_product_by_reference(product_reference, products)
        
        if product:
            # If product exists, update its stock
            update_product_stock(product['id'], 100)
        else:
            # If product doesn't exist, create a new one
            create_new_product(name='New Example Product', reference=product_reference, price=29.99, stock_quantity=50)

if __name__ == '__main__':
    main_workflow()
