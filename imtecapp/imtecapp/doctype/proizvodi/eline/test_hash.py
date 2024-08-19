import hashlib
import json
import os
import frappe


def generate_item_hash(item):
    """Generate a hash for the given item based on its critical fields."""
    hash_input = (
        f"{item.get('art_sifra', '')}{item.get('vpc', 0)}{item.get('aktivan', 0)}{item.get('stanje', 0)}"
        f"{item.get('art_naziv', '')}{item.get('kataloski', '')}{item.get('grupanaziv', '')}{item.get('proizvodjac', '')}"
    )
    return hashlib.md5(hash_input.encode()).hexdigest()


def update_hashes_in_chunks(file_name, chunk_size=1000):
    """Read a large JSON file in chunks, update hashes, and write back to a new file with proper formatting."""
    directory_path = frappe.get_module_path("imtecapp", "data")
    file_path = os.path.join(directory_path, file_name)
    temp_file_path = os.path.join(directory_path, "temp_" + file_name)

    if not os.path.exists(file_path):
        print(f"File {file_path} does not exist.")
        return

    try:
        with open(file_path, "r") as file:
            data = json.load(file)
    except json.JSONDecodeError as e:
        print(f"Error reading JSON file: {e}")
        return

    total_items = len(data)
    processed_items = 0

    with open(temp_file_path, "w") as temp_file:
        temp_file.write("[\n")
        for i in range(0, total_items, chunk_size):
            chunk = data[i : i + chunk_size]
            for index, item in enumerate(chunk):
                new_hash = generate_item_hash(item)
                if item["hash"] != new_hash:
                    print(f"Updating hash for item with art_sifra {item['art_sifra']}.")
                    item["hash"] = new_hash
                json.dump(item, temp_file, indent=4)
                processed_items += 1
                if processed_items < total_items:
                    temp_file.write(",\n")
                elif index < len(chunk) - 1:
                    temp_file.write(",\n")
        temp_file.write("\n]")

    os.replace(temp_file_path, file_path)
    print(f"Updated hashes saved back to {file_path}.")


# Example usage:
def run_update_for_large_test_eline():
    update_hashes_in_chunks("new_eline_data.json")



