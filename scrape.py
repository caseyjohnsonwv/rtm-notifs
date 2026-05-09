import argparse
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

from search import DB_PATH, rebuild_index

BASE_URL = "https://cdn5.editmysite.com/app/store/api/v28/editor/users/152199704/sites/171034537763690384/products"
PER_PAGE = 100
PARALLEL_PAGES = 5


def fetch_page(page):
    resp = requests.get(BASE_URL, params={"page": page, "per_page": PER_PAGE})
    resp.raise_for_status()
    return page, resp.json()


def extract(body):
    return [
        {
            "id": item.get("id"),
            "name": item.get("name"),
            "description": item.get("short_description"),
            "absolute_site_link": item.get("absolute_site_link"),
            "price": item.get("price", {}).get("high"),
            "created_date": item.get("created_date"),
            "updated_date": item.get("updated_date"),
        }
        for item in body["data"]
    ]


def run_scrape(write_json: bool = False, json_path: str = "temp.json") -> int:
    print("Fetching page 1...")
    _, body = fetch_page(1)
    pagination = body["meta"]["pagination"]
    total_pages = pagination["total_pages"]
    print(
        f"Page 1/{total_pages} done - {pagination['total']} total products across {total_pages} pages"
    )

    all_products = extract(body)

    remaining = list(range(2, total_pages + 1))
    for i in range(0, len(remaining), PARALLEL_PAGES):
        batch = remaining[i : i + PARALLEL_PAGES]
        results = {}
        with ThreadPoolExecutor(max_workers=PARALLEL_PAGES) as executor:
            futures = {executor.submit(fetch_page, p): p for p in batch}
            for future in as_completed(futures):
                page, page_body = future.result()
                results[page] = extract(page_body)
                print(f"Fetched page {page}/{total_pages}")

        for page in sorted(results):
            all_products.extend(results[page])

    print(f"Done. Total fetched products: {len(all_products)}")

    indexed = rebuild_index(all_products)
    print(f"Indexed products: {indexed}")
    print(f"DB path: {DB_PATH}")

    if write_json:
        with open(json_path, "w") as f:
            json.dump(all_products, f)
        print(f"Wrote debug JSON: {json_path}")

    return indexed


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape products and rebuild local search index")
    parser.add_argument("--write-json", action="store_true", help="Write temp.json debug artifact")
    parser.add_argument("--json-path", default="temp.json", help="Debug JSON output path")
    args = parser.parse_args()

    run_scrape(write_json=args.write_json, json_path=args.json_path)


if __name__ == "__main__":
    main()
