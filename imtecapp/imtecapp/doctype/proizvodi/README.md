# PrestaShop and Frappe Integration

This repository contains code to integrate PrestaShop with Frappe, allowing for synchronization of products, categories, manufacturers, and stock availability between the two systems. This includes full synchronization of data between Frappe and PrestaShop.

## Features
- Fetch products from PrestaShop and sync them into Frappe.
- Sync products, categories, manufacturers, and stock availability from Frappe into PrestaShop.
- Supports Create (POST), Retrieve (GET), Update (PUT), and Delete (DELETE) operations for PrestaShop resources.
- Handle link rewrites for products and categories dynamically.

## Setup

### 1. Install Dependencies
Make sure you have all the required Python libraries:
```bash
pip install requests xmltodict
```

### 2. PrestaShop API Configuration in Frappe
You need to configure the `Generalne Postavke` doctype in Frappe with the following fields:
- **presta_url**: The base URL of your PrestaShop API (e.g., `https://your-shop.com/api`).
- **presta_key**: The API key for PrestaShop access.

This will be used to authenticate and interact with the PrestaShop API.

## Code Explanation

### Utility Functions
- `handle_none(value)`: Returns an empty string if the value is `None`.
- `clean_response(response_text)`: Cleans the BOM and whitespace from the response text.
- `generate_link_rewrite(name)`: Converts a product name into a URL-friendly link rewrite.
- `get_prestashop_settings()`: Fetches PrestaShop settings from the Frappe `Generalne Postavke` doctype.
- `get_prestashop_url(path)`: Constructs the full PrestaShop API URL for a given resource path.
- `check_prestashop_response(res, ret)`: Validates the PrestaShop API response and raises an exception for invalid statuses.
- `prestashop_request(method, path, params, data)`: General function to make requests to the PrestaShop API, supporting GET, POST, PUT, and DELETE.

### Sync Functions

- **Syncing PrestaShop to Frappe**
  - `sync_prestashop_product_data()`: Fetches all products from PrestaShop and syncs them into Frappe. It also optionally syncs stock availability, categories, and manufacturers.
  - `sync_stock_availability(product_id)`: Syncs the stock availability of a specific product from PrestaShop to Frappe.
  - `sync_prestashop_categories()`: Syncs all categories from PrestaShop to Frappe.
  - `sync_prestashop_manufacturers()`: Syncs all manufacturers from PrestaShop to Frappe.

- **Syncing Frappe to PrestaShop**
  - `sync_frappe_product_to_prestashop(product_reference)`: Syncs a specific product from Frappe into PrestaShop. If the product already exists in PrestaShop, it will be updated; otherwise, it will be created.

### Example Usage

To sync products from PrestaShop to Frappe, you can use:
```python
sync_prestashop_product_data()
```

To sync a product from Frappe to PrestaShop, you can use:
```python
sync_frappe_product_to_prestashop('your_product_reference')
```

### API Interaction Functions
- `prestashop_add(path, data)`: Adds (POST) a resource to PrestaShop.
- `prestashop_get(path, params)`: Retrieves (GET) a resource from PrestaShop.
- `prestashop_edit(path, data)`: Edits (PUT) a resource in PrestaShop.
- `prestashop_delete(path)`: Deletes (DELETE) a resource from PrestaShop.

### License
This project is licensed under the MIT License.
"""



ako artikal izmjeni/doda kategoriju
### Insert new Eline data from 0%

```
from imtecapp.imtecapp.doctype.proizvodi.eline.insert_new_data import fetch_and_insert_current_eline_data
fetch_and_insert_current_eline_data()
```

### First import prestashop - categories
```
from imtecapp.imtecapp.doctype.proizvodi.sync_categorie import sync_categories_to_prestashop
sync_categories_to_prestashop()
```

### First import prestashop - manufacturer
```
from imtecapp.imtecapp.doctype.proizvodi.sync_manufacturer import sync_manufacturers_to_prestashop
sync_manufacturers_to_prestashop()
```

### First import prestashop
```
from imtecapp.imtecapp.doctype.proizvodi.sync import sync_products_to_prestashop
sync_products_to_prestashop()

from imtecapp.imtecapp.doctype.proizvodi.proizvodi import sync_active_products_to_prestashop
sync_active_products_to_prestashop()
```

