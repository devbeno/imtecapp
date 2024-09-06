# prestashop_sync.py

import frappe
import requests
from .utils import log_message, create_sync_log
from .api_utils import get_erpimtec_settings, get_headers
from .data_sync import insert_data_from_for_insert_eline_data
from .categories import create_prestashop_category, find_prestashop_category_by_name
from .manufacturers import create_prestashop_manufacturer, find_prestashop_manufacturer_by_name

def sync_product_to_prestashop_manual(art_sifra, sync_log=None):
    log_details = ""  # Initialize log accumulation for individual sync

    try:
        # Fetch the product document
        product = frappe.get_doc("Proizvodi", {"art_sifra": art_sifra})

        # Prepare new product data for syncing
        new_product_data = {
            "art_sifra": product.art_sifra,
            "art_naziv": product.art_naziv,
            "prestashop_category_id": product.prestashop_category_id,
            "prestashop_manufacturer_id": product.prestashop_manufacturer_id,
            "vpc": product.vpc,
            "aktivan": product.aktivan,
            "stanje": product.stanje,
            "kataloski": product.kataloski,
            "prestashop_id": product.prestashop_id,
            "status": product.status,
        }

        # Sync product to PrestaShop
        settings = get_erpimtec_settings()
        prestashop_id = search_prestashop_product(
            settings, new_product_data["art_sifra"], sync_log=sync_log
        )

        if prestashop_id:
            existing_product_data = get_existing_product_data(settings, prestashop_id, sync_log=sync_log)
            if existing_product_data:
                xml_payload = generate_product_xml(new_product_data, prestashop_id)
                url = f"{settings['presta_url']}/products/{prestashop_id}"
                response = requests.put(
                    url, headers=get_headers(settings), data=xml_payload.encode("utf-8")
                )

                if response.status_code in [200, 201]:
                    log_details += f"Product {new_product_data['art_sifra']} synced successfully.\n"
                else:
                    log_details += (
                        f"Failed to sync product. Status Code: {response.status_code}\n"
                    )
                    log_details += f"Response: {response.text}\n"
            else:
                log_details += "Failed to retrieve existing product data.\n"

        else:
            log_details += f"Product with reference {new_product_data['art_sifra']} does not exist. Creating it.\n"
            prestashop_id = create_prestashop_product(settings, new_product_data, sync_log=sync_log)
            if prestashop_id:
                product.prestashop_id = prestashop_id
                product.save(ignore_permissions=True)
                frappe.db.commit()

    except frappe.DoesNotExistError:
        log_details += f"Product with art_sifra {art_sifra} does not exist.\n"
    except Exception as e:
        log_details += f"An unexpected error occurred: {str(e)}\n"

    log_message(sync_log, log_details)  # Log details for each product sync
    return log_details  # Return accumulated logs for each product sync

def sync_product_to_prestashop_insert(art_sifra, sync_log=None):
    """
    Insert a product into PrestaShop based on its art_sifra.
    """
    log_details = ""  # Initialize log accumulation for individual insert

    try:
        # Fetch the product document
        product = frappe.get_doc("Proizvodi", {"art_sifra": art_sifra})

        # Prepare new product data for inserting
        new_product_data = {
            "art_sifra": product.art_sifra,
            "art_naziv": product.art_naziv,
            "prestashop_category_id": product.prestashop_category_id,
            "prestashop_manufacturer_id": product.prestashop_manufacturer_id,
            "vpc": product.vpc,
            "aktivan": product.aktivan,
            "stanje": product.stanje,
            "kataloski": product.kataloski,
            "hash": product.hash,
        }

        # Check and create category if needed
        new_prestashop_category_id = check_and_create_category(product.grupanaziv, sync_log)
        new_product_data["prestashop_category_id"] = new_prestashop_category_id

        # Check and create manufacturer if needed
        new_prestashop_manufacturer_id = check_and_create_manufacturer(product.proizvodjac, sync_log)
        new_product_data["prestashop_manufacturer_id"] = new_prestashop_manufacturer_id

        # Update the Proizvodi document with the new category and manufacturer IDs if they have changed
        if (
            product.prestashop_category_id != new_prestashop_category_id
            or product.prestashop_manufacturer_id != new_prestashop_manufacturer_id
        ):
            product.prestashop_category_id = new_prestashop_category_id
            product.prestashop_manufacturer_id = new_prestashop_manufacturer_id
            product.save(ignore_permissions=True)
            frappe.db.commit()  # Commit changes to the database

        # Check if the product already exists in PrestaShop
        settings = get_prestashop_settings()
        prestashop_id = search_prestashop_product(settings, new_product_data["art_sifra"], sync_log=sync_log)

        if prestashop_id:
            # If product exists, update it instead of inserting
            log_details += f"Product {art_sifra} already exists in PrestaShop with ID {prestashop_id}. Updating product.\n"
            existing_product_data = get_existing_product_data(settings, prestashop_id, sync_log=sync_log)
            if existing_product_data:
                # Update the product in PrestaShop
                xml_payload = generate_product_xml(new_product_data, prestashop_id)
                url = f"{settings['presta_url']}/products/{prestashop_id}"
                response = requests.put(url, headers=get_headers(settings), data=xml_payload.encode("utf-8"))

                if response.status_code in [200, 201]:
                    log_details += f"Product {art_sifra} updated successfully in PrestaShop.\n"
                else:
                    log_details += f"Failed to update product {art_sifra}. Status Code: {response.status_code}, Response: {response.text}\n"
            else:
                log_details += f"Failed to retrieve existing product data for {art_sifra}.\n"
        else:
            # If product does not exist, insert it
            log_details += f"Product with reference {new_product_data['art_sifra']} does not exist. Creating it.\n"
            prestashop_id = create_prestashop_product(settings, new_product_data, sync_log=sync_log)
            if prestashop_id:
                product.prestashop_id = prestashop_id
                product.status = "on_presta"
                product.save(ignore_permissions=True)
                frappe.db.commit()  # Commit changes to the database
                log_details += f"Product {art_sifra} inserted successfully into PrestaShop with ID {prestashop_id}.\n"
            else:
                log_details += f"Failed to insert product {art_sifra} into PrestaShop. Check response and product data for issues.\n"

    except frappe.DoesNotExistError:
        log_details += f"Product with art_sifra {art_sifra} does not exist in ERPNext.\n"
    except Exception as e:
        log_details += f"An unexpected error occurred while inserting product {art_sifra}: {str(e)}\n"

    log_message(sync_log, log_details)  # Log details for each product insert
    return log_details  # Return accumulated logs for each product insert

def sync_product_to_prestashop_rename(art_sifra, sync_log="Rename Items"):
    """
    Rename a category or manufacturer in PrestaShop based on its art_sifra.
    """
    log_details = ""  # Initialize log accumulation for renaming operation

    try:
        # Fetch the product document
        product = frappe.get_doc("Proizvodi", {"art_sifra": art_sifra})

        # Prepare the new data for renaming
        new_name = product.grupanaziv or product.proizvodjac
        rename_type = "category" if product.grupanaziv else "manufacturer"

        settings = get_prestashop_settings()

        if rename_type == "category":
            link_rewrite = generate_link_rewrite(new_name)
            # Fetch existing PrestaShop category ID
            prestashop_category_id = product.prestashop_category_id
            xml_payload = f"""
            <?xml version="1.0" encoding="UTF-8"?>
            <prestashop xmlns:xlink="http://www.w3.org/1999/xlink">
                <category>
                    <id>{prestashop_category_id}</id>
                    <name>
                        <language id="1"><![CDATA[{new_name}]]></language>
                        <language id="2"><![CDATA[{new_name}]]></language>
                    </name>
            	    <link_rewrite>
                        <language id="1"><![CDATA[{link_rewrite}]]></language>
                        <language id="2"><![CDATA[{link_rewrite}]]></language>
                    </link_rewrite>
                    <active>1</active>
                    <id_shop_default>1</id_shop_default>
                    <id_parent>2</id_parent>
                </category>
            </prestashop>
            """.strip()
            url = f"{settings['presta_url']}/categories/{prestashop_category_id}"
            response = requests.put(url, headers=get_headers(settings), data=xml_payload.encode("utf-8"))

            if response.status_code in [200, 201]:
                log_details += f"Category renamed to {new_name} successfully in PrestaShop.\n"
            else:
                log_details += f"Failed to rename category. Status Code: {response.status_code}, Response: {response.text}\n"

        elif rename_type == "manufacturer":
            # Fetch existing PrestaShop manufacturer ID
            prestashop_manufacturer_id = product.prestashop_manufacturer_id
            xml_payload = f"""
            <?xml version="1.0" encoding="UTF-8"?>
            <prestashop xmlns:xlink="http://www.w3.org/1999/xlink">
                <manufacturer>
                    <id>{prestashop_manufacturer_id}</id>
                    <name><![CDATA[{new_name}]]></name>
                    <active>1</active>
                </manufacturer>
            </prestashop>
            """.strip()
            url = f"{settings['presta_url']}/manufacturers/{prestashop_manufacturer_id}"
            response = requests.put(url, headers=get_headers(settings), data=xml_payload.encode("utf-8"))

            if response.status_code in [200, 201]:
                log_details += f"Manufacturer renamed to {new_name} successfully in PrestaShop.\n"
            else:
                log_details += f"Failed to rename manufacturer. Status Code: {response.status_code}, Response: {response.text}\n"

    except frappe.DoesNotExistError:
        log_details += f"Product with art_sifra {art_sifra} does not exist in ERPNext.\n"
    except Exception as e:
        log_details += f"An unexpected error occurred while renaming product {art_sifra}: {str(e)}\n"

    log_message(sync_log, log_details)  # Log details for each rename operation
    return log_details  # Return accumulated logs for each rename operation



@frappe.whitelist()
def enqueue_sync_all_active_products():
    """
    Enqueue the task to sync all active products to PrestaShop in the background.
    """
    # Create a Sync Progress document to track the progress
    sync_progress = frappe.get_doc(
        {
            "doctype": "Sync Progress",
            "total_records": frappe.db.count(
                "Proizvodi",
                {
                    "aktivan": 1,
                    "agp_id": ["!=", ""],  # Check for non-empty string
                    "sifra": ["!=", ""],
                },
            ),
            "processed_records": 0,
            "status": "In Progress",
        }
    )
    sync_progress.insert()
    frappe.db.commit()  # Commit once after creating the Sync Progress document

    # Enqueue the background job without batch size
    enqueue(
        method=sync_all_active_products,
        queue="long",
        timeout=2500,
        job_name="Sync All Active Products",
        sync_progress_name=sync_progress.name
    )
    frappe.msgprint(_("The sync operation has been started in the background."))

@frappe.whitelist()
def sync_all_products_for_update():
    log_details = ""  # Initialize log accumulation for overall sync
    sync_log = create_sync_log("Sync All Products for Update")

    # Debugging print statement
    print(
        "Starting sync_all_products function...",
        file=open("/home/frappe/frappe-bench/logs/sync.debug.log", "a"),
    )

    try:
        # Insert or update products based on `for_insert_eline_data.json`
        try:
            log_details += "Inserting or updating data from for_insert_eline_data.json...\n"
            insert_data_from_for_insert_eline_data()
            log_details += "Data insertion or update completed.\n"
        except Exception as e:
            log_details += f"Error while inserting or updating data: {str(e)}\n"
            update_sync_log(sync_log, log_details, status="Failed")
            return  # Exit early since there was an error

        # Fetch products that are marked for update
        log_details += "Fetching products marked for update...\n"
        products_for_update = frappe.get_all(
            "Proizvodi", filters={"status": "for_update"}, fields=["art_sifra"]
        )

        log_details += f"Found {len(products_for_update)} products for update.\n"

        for product in products_for_update:
            try:
                result = sync_product_to_prestashop_manual(product["art_sifra"])
                log_details += f"Product {product['art_sifra']} sync result: {result}\n"
            except Exception as e:
                log_details += f"Failed to sync product {product['art_sifra']}: {str(e)}\n"
                frappe.log_error(f"Failed to sync product {product['art_sifra']}: {str(e)}", "Product Sync Error")

            # Debugging print statement
            print(
                f"Processed product {product['art_sifra']}",
                file=open("/home/frappe/frappe-bench/logs/sync.debug.log", "a"),
            )

        # Fetch products that are marked for insert
        log_details += "Fetching products marked for insert...\n"
        products_for_insert = frappe.get_all(
            "Proizvodi", filters={"status": "for_insert"}, fields=["art_sifra"]
        )

        log_details += f"Found {len(products_for_insert)} products for insert.\n"

        for product in products_for_insert:
            try:
                result = sync_product_to_prestashop_insert(product["art_sifra"], sync_log=sync_log)
                log_details += f"Product {product['art_sifra']} sync result: {result}\n"
            except Exception as e:
                log_details += f"Failed to insert product {product['art_sifra']}: {str(e)}\n"
                frappe.log_error(f"Failed to insert product {product['art_sifra']}: {str(e)}", "Product Insert Error")

            # Debugging print statement
            print(
                f"Processed product {product['art_sifra']} for insert",
                file=open("/home/frappe/frappe-bench/logs/sync.debug.log", "a"),
            )

        # Fetch products that are marked for rename
        log_details += "Fetching products marked for rename...\n"
        products_for_rename = frappe.get_all(
            "Proizvodi", filters={"status": "for_rename"}, fields=["art_sifra"]
        )

        log_details += f"Found {len(products_for_rename)} products for rename.\n"

        for product in products_for_rename:
            try:
                result = sync_product_to_prestashop_rename(product["art_sifra"], sync_log=sync_log)
                log_details += f"Product {product['art_sifra']} rename result: {result}\n"
            except Exception as e:
                log_details += f"Failed to rename product {product['art_sifra']}: {str(e)}\n"
                frappe.log_error(f"Failed to rename product {product['art_sifra']}: {str(e)}", "Product Rename Error")

            # Debugging print statement
            print(
                f"Processed product {product['art_sifra']} for rename",
                file=open("/home/frappe/frappe-bench/logs/sync.debug.log", "a"),
            )

        # Update log with the accumulated details after all products are processed
        update_sync_log(sync_log, log_details, status="Success")

    except Exception as e:
        log_details += f"An unexpected error occurred: {str(e)}\n"
        update_sync_log(sync_log, log_details, status="Failed")

        # Debugging print statement
        print(
            f"Error occurred: {str(e)}",
            file=open("/home/frappe/frappe-bench/logs/sync.debug.log", "a"),
        )

    print(
        "Completed sync_all_products function.",
        file=open("/home/frappe/frappe-bench/logs/sync.debug.log", "a"),
    )

@frappe.whitelist()
def sync_all_stanje_products(batch_size=500):
    log_details = ""
    sync_log = create_sync_log("Sync All Active Products")

    try:
        # Start index for batching
        start = 0
        # Count total active products
        total_records = frappe.db.count("Proizvodi", {"stanje": ["!=", 0]})

        while start < total_records:
            # Fetch the next batch of active products with limit and offset
            stanje_products = frappe.get_all(
                "Proizvodi",
                filters={"stanje": ["!=", 0]},
                fields=["art_sifra"],
                limit=batch_size,
                start=start,
            )

            # Process each product in the current batch
            for product in stanje_products:
                # Sync each product to PrestaShop and collect the log details
                result = sync_product_to_prestashop_manual(product["art_sifra"], sync_log=sync_log)
                log_details += result + "\n"

            # Update the sync log with the accumulated log details after each batch
            update_sync_log(sync_log, log_details, status="In Progress")

            # Increment the start index for the next batch
            start += batch_size

        # Final update to sync log after all products are processed
        update_sync_log(sync_log, log_details, status="Success")

    except Exception as e:
        log_details += f"An unexpected error occurred: {str(e)}\n"
        update_sync_log(sync_log, log_details, status="Failed")


@frappe.whitelist()
def get_sync_progress():
    # Fetch the latest sync progress document
    sync_progress = frappe.get_all(
        "Sync Progress",
        fields=["total_records", "processed_records", "status"],
        order_by="modified desc",
        limit=1,
    )
    if sync_progress:
        return sync_progress[0]
    else:
        return {"total_records": 0, "processed_records": 0, "status": "Not Started"}

def update_stock_quantity(
    settings, stock_available_id, product_id, quantity, sync_log=None
):
    url = f"{settings['presta_url']}/stock_availables/{stock_available_id}"

    payload = f"""
    <?xml version="1.0" encoding="UTF-8"?>
    <prestashop xmlns:xlink="http://www.w3.org/1999/xlink">
        <stock_available>
            <id>{stock_available_id}</id>
            <id_product>{product_id}</id_product>
            <id_product_attribute><![CDATA[0]]></id_product_attribute>
            <id_shop><![CDATA[1]]></id_shop>
            <id_shop_group><![CDATA[0]]></id_shop_group>
            <quantity><![CDATA[{quantity}]]></quantity>
            <depends_on_stock><![CDATA[0]]></depends_on_stock>
            <out_of_stock><![CDATA[2]]></out_of_stock>
        </stock_available>
    </prestashop>
    """.strip().encode(
        "utf-8"
    )

    headers = {
        "Content-Type": "application/xml",
        "Authorization": f"Basic {settings['presta_key']}",
    }

    response = requests.patch(url, headers=headers, data=payload)

    log_message(
        sync_log,
        f"Updating stock for stock_available ID {stock_available_id} to {quantity} using URL: {url}",
    )
    log_message(sync_log, f"Response Status Code: {response.status_code}")
    log_message(sync_log, f"Response Text: {response.text}")

    if response.status_code in [200, 201]:
        log_message(
            sync_log,
            f"Stock quantity for stock_available ID {stock_available_id} updated to {quantity}.",
        )
    else:
        log_message(
            sync_log,
            f"Failed to update stock quantity. Status Code: {response.status_code}",
        )



def get_stock_available_id(settings, prestashop_id, sync_log=None):
    url = f"{settings['presta_url']}/stock_availables"
    params = {"filter[id_product]": prestashop_id, "display": "full"}

    response = requests.get(url, params=params, headers=get_headers(settings))

    log_message(
        sync_log,
        f"Fetching stock_available for product ID {prestashop_id} using URL: {url}",
    )
    log_message(sync_log, f"Response Status Code: {response.status_code}")
    log_message(sync_log, f"Response Text: {response.text}")

    if response.status_code == 200:
        try:
            clean_response_text = clean_response(response.text)
            root = ET.fromstring(clean_response_text)
            stock_availables = root.findall(".//stock_available")

            for stock_available in stock_availables:
                id_product_attribute = stock_available.find("id_product_attribute")

                if (
                    id_product_attribute is not None
                    and id_product_attribute.text == "0"
                ):
                    stock_available_id = stock_available.find("id").text
                    log_message(
                        sync_log,
                        f"Found stock_available ID: {stock_available_id} for product ID: {prestashop_id}",
                    )
                    return stock_available_id

            log_message(
                sync_log, "No suitable stock_available found for the given product ID."
            )
            return None
        except ET.ParseError as e:
            log_message(sync_log, f"Failed to parse XML from response: {e}")
            return None
    else:
        log_message(
            sync_log,
            f"Failed to retrieve stock_available. Status Code: {response.status_code}",
        )
        return None

def create_prestashop_product(settings, product_data, sync_log=None):
    url = f"{settings['presta_url']}/products"
    payload = generate_product_xml(product_data)
    headers = {
        "Content-Type": "application/xml",
        "Authorization": f"Basic {settings['presta_key']}",
    }

    response = requests.post(url, headers=headers, data=payload.encode("utf-8"))

    if response.status_code in [200, 201]:
        log_message(
            sync_log, f"Product {product_data['art_sifra']} created successfully."
        )
        try:
            root = ET.fromstring(response.text)
            product_id = root.find(".//product").get("id")
            return product_id
        except ET.ParseError as e:
            log_message(sync_log, f"Failed to parse XML from response: {e}")
            return None
    else:
        log_message(
            sync_log, f"Failed to create product. Status Code: {response.status_code}"
        )
        return None

def sync_product(art_sifra, sync_log=None):
    """
    Sync a single product to PrestaShop.
    """
    try:
        sync_product_to_prestashop_manual(art_sifra, sync_log=sync_log)
        # Mark as synced
        frappe.db.set_value(
            "Proizvodi", {"art_sifra": art_sifra}, "status", "on_presta"
        )
    except Exception as e:
        frappe.log_error(
            f"Failed to sync product {art_sifra}: {str(e)}", "Product Sync Error"
        )

@frappe.whitelist()
def reset_products_status():
    frappe.db.sql("""UPDATE tabProizvodi SET status = ''""")
    frappe.db.commit()