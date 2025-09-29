import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from data_loader import load_properties, parse_price, extract_postcode

def run_data_loader_test():
    """Tests the functionality of the data loader and parsers."""
    print("\n--- Running Test 2: CSV Data Loading and Parsing ---")

    # Test price parsing
    print("\nTesting price parser...")
    price1 = parse_price("£1,250 pcm")
    price2 = parse_price("£900pcm")
    price3 = parse_price("POA")
    print(f"'£1,250 pcm' -> {price1} (Expected: 1250.0) {'✅' if price1 == 1250.0 else '❌'}")
    print(f"'£900pcm' -> {price2} (Expected: 900.0) {'✅' if price2 == 900.0 else '❌'}")
    print(f"'POA' -> {price3} (Expected: None) {'✅' if price3 is None else '❌'}")

    # Test postcode extraction
    print("\nTesting postcode extractor...")
    addr1 = "Flat 5, 123 Example Street, London, NW1 2DB"
    addr2 = "Apartment Block, Islington, N19AA"
    postcode1 = extract_postcode(addr1)
    postcode2 = extract_postcode(addr2)
    print(f"'{addr1}' -> '{postcode1}' (Expected: 'NW1 2DB') {'✅' if postcode1 == 'NW1 2DB' else '❌'}")
    print(f"'{addr2}' -> '{postcode2}' (Expected: 'N1 9AA') {'✅' if postcode2 == 'N1 9AA' else '❌'}")

    # Test loading properties from CSV
    print("\nTesting property loading from CSV...")
    properties = load_properties()
    if properties:
        print(f"✅ Successfully loaded {len(properties)} properties.")
        sample_prop = properties[0]
        print("Sample property check:")
        print(f"  - Address: {sample_prop.get('Address')}")
        print(f"  - Parsed Price: {sample_prop.get('parsed_price')}")
        print(f"  - Extracted Postcode: {sample_prop.get('postcode')}")
        if sample_prop.get('parsed_price') is not None:
             print("  - ✅ Parsed Price looks good.")
        else:
             print("  - ❌ Parsed Price is missing.")
        if sample_prop.get('postcode') is not None:
             print("  - ✅ Extracted Postcode looks good.")
        else:
             print("  - ⚠️  Extracted Postcode is missing. (This is expected if the address in the CSV does not have a postcode).")
    else:
        print("❌ FAILED to load properties. Check CSV file path and content.")

    print("\n--- Test 2 Finished ---")

if __name__ == "__main__":
    run_data_loader_test()