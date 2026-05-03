import requests
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_URL = "https://cdn5.editmysite.com/app/store/api/v28/editor/users/152199704/sites/171034537763690384/products"
PER_PAGE = 100
BATCH_SIZE = 5

def fetch_page(page):
    resp = requests.get(BASE_URL, params={"page": page, "per_page": PER_PAGE})
    resp.raise_for_status()
    return page, resp.json()

def extract(body):
    return [{
        "id": item.get("id"),
        "name": item.get("name"),
        "absolute_site_link": item.get("absolute_site_link"),
        "price": item.get("price", {}).get("high"),
        "updated_date": item.get("updated_date"),
    } for item in body["data"]]

# Fetch page 1 first to find out total_pages
print("Fetching page 1...")
_, body = fetch_page(1)
pagination = body["meta"]["pagination"]
total_pages = pagination["total_pages"]
print(f"Page 1/{total_pages} done — {pagination['total']} total products across {total_pages} pages")

all_products = extract(body)

# Fetch remaining pages in batches of BATCH_SIZE
remaining = list(range(2, total_pages + 1))
for i in range(0, len(remaining), BATCH_SIZE):
    batch = remaining[i:i + BATCH_SIZE]
    results = {}
    with ThreadPoolExecutor(max_workers=BATCH_SIZE) as executor:
        futures = {executor.submit(fetch_page, p): p for p in batch}
        for future in as_completed(futures):
            page, body = future.result()
            results[page] = extract(body)
            print(f"Fetched page {page}/{total_pages}")

    # Append in order
    for page in sorted(results):
        all_products.extend(results[page])

print(f"\nDone! Total products: {len(all_products)}")
with open('temp.json', 'w') as f:
    json.dump(all_products, f)
    