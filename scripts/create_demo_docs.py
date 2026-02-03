#!/usr/bin/env python3
"""Generate realistic sample customs documents for demo scenarios."""

import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from PIL import Image, ImageDraw, ImageFont

# Ensure output directories exist
OUTPUT_DIR = Path(__file__).parent.parent / "samples"
for scenario in ["docs_happy_path", "docs_fraudish", "docs_missing_docs"]:
    (OUTPUT_DIR / scenario).mkdir(parents=True, exist_ok=True)

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GRAY = (100, 100, 100)


def get_font(size: int = 20) -> ImageFont.FreeTypeFont:
    """Get a font for text rendering."""
    try:
        return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", size)
    except:
        try:
            return ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", size)
        except:
            return ImageFont.load_default()


def create_invoice(data: dict, output_path: Path) -> None:
    """Create a commercial invoice document."""
    img = Image.new('RGB', (850, 1100), color=WHITE)
    draw = ImageDraw.Draw(img)

    # Fonts
    title_font = get_font(28)
    header_font = get_font(22)
    normal_font = get_font(18)
    small_font = get_font(14)

    # Header
    draw.text((50, 40), "COMMERCIAL INVOICE", fill=BLACK, font=title_font)
    draw.text((50, 80), f"Invoice Number: {data['invoice_number']}", fill=BLACK, font=header_font)
    draw.text((50, 110), f"Date: {data['invoice_date']}", fill=BLACK, font=normal_font)
    draw.text((450, 80), f"Currency: {data['currency']}", fill=BLACK, font=header_font)

    # From/To
    draw.text((50, 160), "FROM:", fill=GRAY, font=small_font)
    draw.text((50, 180), data['supplier_name'], fill=BLACK, font=normal_font)
    draw.text((50, 205), data['supplier_address'], fill=BLACK, font=normal_font)
    draw.text((50, 230), f"Tax ID: {data['supplier_tax_id']}", fill=BLACK, font=normal_font)

    draw.text((450, 160), "TO:", fill=GRAY, font=small_font)
    draw.text((450, 180), data['buyer_name'], fill=BLACK, font=normal_font)
    draw.text((450, 205), data['buyer_address'], fill=BLACK, font=normal_font)
    draw.text((450, 230), f"Tax ID: {data['buyer_tax_id']}", fill=BLACK, font=normal_font)

    # Shipment info
    y = 290
    draw.text((50, y), "SHIPMENT DETAILS:", fill=GRAY, font=small_font)
    y += 25
    draw.text((50, y), f"Shipment ID: {data['shipment_id']}", fill=BLACK, font=normal_font)
    y += 25
    draw.text((50, y), f"Origin: {data['origin_country']}", fill=BLACK, font=normal_font)
    y += 25
    draw.text((50, y), f"Destination: {data['destination_country']}", fill=BLACK, font=normal_font)
    y += 25
    draw.text((50, y), f"HS Code: {data['hs_code']}", fill=BLACK, font=normal_font)

    # Line items header
    y = 400
    draw.line([(50, y), (800, y)], fill=BLACK, width=2)
    y += 10
    draw.text((50, y), "Description", fill=BLACK, font=header_font)
    draw.text((350, y), "Quantity", fill=BLACK, font=header_font)
    draw.text((500, y), "Unit Price", fill=BLACK, font=header_font)
    draw.text((650, y), "Amount", fill=BLACK, font=header_font)
    y += 35
    draw.line([(50, y), (800, y)], fill=BLACK, width=1)

    # Line items
    y += 15
    for item in data['items']:
        draw.text((60, y), item['description'], fill=BLACK, font=normal_font)
        draw.text((360, y), str(item['quantity']), fill=BLACK, font=normal_font)
        draw.text((510, y), f"{item['unit_price']:.2f}", fill=BLACK, font=normal_font)
        draw.text((660, y), f"{item['amount']:.2f}", fill=BLACK, font=normal_font)
        y += 30

    # Total
    y += 20
    draw.line([(50, y), (800, y)], fill=BLACK, width=2)
    y += 35
    draw.text((550, y), f"TOTAL: {data['total_amount']:.2f}", fill=BLACK, font=title_font)

    # Footer
    y = 1050
    draw.text((50, y), f"Terms: {data.get('terms', 'Net 30')}", fill=GRAY, font=small_font)
    draw.text((500, y), f"Authorized Signature: {data.get('signature', 'Electronics Ltd')}", fill=GRAY, font=small_font)

    img.save(output_path)
    print(f"Created: {output_path}")


def create_bill_of_lading(data: dict, output_path: Path) -> None:
    """Create a bill of lading document."""
    img = Image.new('RGB', (850, 1100), color=WHITE)
    draw = ImageDraw.Draw(img)

    title_font = get_font(28)
    header_font = get_font(20)
    normal_font = get_font(18)
    small_font = get_font(14)

    # Header
    draw.text((50, 40), "BILL OF LADING", fill=BLACK, font=title_font)

    # Carrier info
    draw.text((50, 90), "CARRIER: GLOBAL SHIPPING LINES", fill=BLACK, font=header_font)
    draw.text((50, 120), f"B/L Number: {data['bl_number']}", fill=BLACK, font=normal_font)
    draw.text((450, 90), f"Date: {data['bl_date']}", fill=BLACK, font=normal_font)
    draw.text((450, 120), f"Vessel: {data['vessel']}", fill=BLACK, font=normal_font)

    # Parties
    y = 180
    draw.text((50, y), "SHIPPER:", fill=GRAY, font=small_font)
    y += 20
    draw.text((50, y), data['shipper_name'], fill=BLACK, font=normal_font)
    y += 25
    draw.text((50, y), data['shipper_address'], fill=BLACK, font=normal_font)

    draw.text((450, y - 45), "CONSIGNEE:", fill=GRAY, font=small_font)
    draw.text((450, y - 20), data['consignee_name'], fill=BLACK, font=normal_font)
    draw.text((450, y + 5), data['consignee_address'], fill=BLACK, font=normal_font)

    # Route
    y = 320
    draw.text((50, y), "ROUTE:", fill=GRAY, font=small_font)
    y += 25
    draw.text((50, y), f"Port of Loading: {data['port_of_loading']}", fill=BLACK, font=normal_font)
    y += 25
    draw.text((50, y), f"Port of Discharge: {data['port_of_discharge']}", fill=BLACK, font=normal_font)
    y += 25
    draw.text((50, y), f"Final Destination: {data['final_destination']}", fill=BLACK, font=normal_font)

    # Shipment details
    y = 450
    draw.text((50, y), "SHIPMENT DETAILS:", fill=GRAY, font=small_font)
    y += 25
    draw.text((50, y), f"Shipment ID: {data['shipment_id']}", fill=BLACK, font=normal_font)
    y += 25
    draw.text((50, y), f"Number of Packages: {data['packages']}", fill=BLACK, font=normal_font)
    y += 25
    draw.text((50, y), f"Gross Weight: {data['weight']}", fill=BLACK, font=normal_font)
    y += 25
    draw.text((50, y), f"Volume: {data['volume']}", fill=BLACK, font=normal_font)

    # Goods description
    y = 600
    draw.line([(50, y), (800, y)], fill=BLACK, width=2)
    y += 20
    draw.text((50, y), "DESCRIPTION OF GOODS:", fill=GRAY, font=small_font)
    y += 25
    words = data['goods_description'].split()
    line = ""
    for word in words:
        test_line = line + word + " "
        if normal_font.getlength(test_line) > 700:
            draw.text((60, y), line, fill=BLACK, font=normal_font)
            y += 25
            line = word + " "
        else:
            line = test_line
    draw.text((60, y), line, fill=BLACK, font=normal_font)

    # Marks and numbers
    y = 750
    draw.text((50, y), f"Marks & Numbers: {data['marks_numbers']}", fill=BLACK, font=normal_font)

    # Footer
    y = 1000
    draw.text((50, y), f"Freight: {data['freight_terms']}", fill=BLACK, font=normal_font)
    draw.text((450, y), f"Place of Issue: {data['place_of_issue']}", fill=BLACK, font=normal_font)

    img.save(output_path)
    print(f"Created: {output_path}")


def create_packing_list(data: dict, output_path: Path) -> None:
    """Create a packing list document."""
    img = Image.new('RGB', (850, 1100), color=WHITE)
    draw = ImageDraw.Draw(img)

    title_font = get_font(28)
    header_font = get_font(20)
    normal_font = get_font(18)
    small_font = get_font(14)

    # Header
    draw.text((50, 40), "PACKING LIST", fill=BLACK, font=title_font)

    # Reference info
    draw.text((50, 90), f"Packing List No: {data['packing_list_no']}", fill=BLACK, font=header_font)
    draw.text((50, 120), f"Date: {data['packing_date']}", fill=BLACK, font=normal_font)
    draw.text((450, 90), f"Invoice No: {data['invoice_number']}", fill=BLACK, font=normal_font)
    draw.text((450, 120), f"Shipment ID: {data['shipment_id']}", fill=BLACK, font=normal_font)

    # Shipper/Consignee
    y = 180
    draw.text((50, y), "SHIPPER:", fill=GRAY, font=small_font)
    y += 20
    draw.text((50, y), data['shipper_name'], fill=BLACK, font=normal_font)

    draw.text((450, y - 20), "CONSIGNEE:", fill=GRAY, font=small_font)
    draw.text((450, y + 5), data['consignee_name'], fill=BLACK, font=normal_font)

    # Shipping info
    y = 270
    draw.text((50, y), "SHIPPING INFORMATION:", fill=GRAY, font=small_font)
    y += 25
    draw.text((50, y), f"From: {data['from_location']}", fill=BLACK, font=normal_font)
    y += 25
    draw.text((50, y), f"To: {data['to_location']}", fill=BLACK, font=normal_font)
    y += 25
    draw.text((50, y), f"Vessel/Voyage: {data['vessel_voyage']}", fill=BLACK, font=normal_font)

    # Package details header
    y = 420
    draw.line([(50, y), (800, y)], fill=BLACK, width=2)
    y += 10
    draw.text((50, y), "Package", fill=BLACK, font=header_font)
    draw.text((200, y), "Description", fill=BLACK, font=header_font)
    draw.text((450, y), "Quantity", fill=BLACK, font=header_font)
    draw.text((600, y), "Weight (kg)", fill=BLACK, font=header_font)
    draw.text((700, y), "Volume (m³)", fill=BLACK, font=header_font)
    y += 35
    draw.line([(50, y), (800, y)], fill=BLACK, width=1)

    # Package items
    y += 15
    total_packages = 0
    total_weight = 0
    total_volume = 0
    for pkg in data['packages']:
        draw.text((60, y), str(pkg['package_no']), fill=BLACK, font=normal_font)
        draw.text((200, y), pkg['description'][:40], fill=BLACK, font=normal_font)
        draw.text((460, y), str(pkg['quantity']), fill=BLACK, font=normal_font)
        draw.text((610, y), str(pkg['weight']), fill=BLACK, font=normal_font)
        draw.text((720, y), str(pkg['volume']), fill=BLACK, font=normal_font)
        y += 30
        total_packages += pkg['quantity']
        total_weight += pkg['weight']
        total_volume += pkg['volume']

    # Totals
    y += 20
    draw.line([(50, y), (800, y)], fill=BLACK, width=2)
    y += 35
    draw.text((450, y), f"Total Packages: {total_packages}", fill=BLACK, font=header_font)
    y += 30
    draw.text((450, y), f"Total Weight: {total_weight} kg", fill=BLACK, font=header_font)
    y += 30
    draw.text((450, y), f"Total Volume: {total_volume} m³", fill=BLACK, font=header_font)

    img.save(output_path)
    print(f"Created: {output_path}")


def create_customs_declaration(data: dict, output_path: Path) -> None:
    """Create a customs declaration document."""
    img = Image.new('RGB', (850, 1200), color=WHITE)
    draw = ImageDraw.Draw(img)

    title_font = get_font(26)
    header_font = get_font(20)
    normal_font = get_font(18)
    small_font = get_font(14)

    # Header
    draw.text((50, 30), "CUSTOMS DECLARATION", fill=BLACK, font=title_font)
    draw.text((50, 65), f"Declaration No: {data['declaration_no']}", fill=BLACK, font=header_font)
    draw.text((450, 30), f"Date: {data['declaration_date']}", fill=BLACK, font=normal_font)
    draw.text((450, 65), f"Office: {data['customs_office']}", fill=BLACK, font=normal_font)

    # Importer
    y = 120
    draw.text((50, y), "IMPORTER OF RECORD:", fill=GRAY, font=small_font)
    y += 20
    draw.text((50, y), data['importer_name'], fill=BLACK, font=normal_font)
    y += 25
    draw.text((50, y), f"Tax ID: {data['importer_tax_id']}", fill=BLACK, font=normal_font)
    y += 25
    draw.text((50, y), data['importer_address'], fill=BLACK, font=normal_font)

    # Declaration details
    y = 240
    draw.text((50, y), "DECLARATION DETAILS:", fill=GRAY, font=small_font)
    y += 25
    draw.text((50, y), f"Procedure: {data['procedure']}", fill=BLACK, font=normal_font)
    y += 25
    draw.text((50, y), f"Shipment ID: {data['shipment_id']}", fill=BLACK, font=normal_font)
    y += 25
    draw.text((50, y), f"Bill of Lading: {data['bl_number']}", fill=BLACK, font=normal_font)
    y += 25
    draw.text((50, y), f"Origin Country: {data['origin_country']}", fill=BLACK, font=normal_font)
    y += 25
    draw.text((50, y), f"Declared Value: {data['declared_value']:.2f} {data['currency']}", fill=BLACK, font=normal_font)

    # Goods header
    y = 420
    draw.line([(50, y), (800, y)], fill=BLACK, width=2)
    y += 10
    draw.text((50, y), "HS Code", fill=BLACK, font=header_font)
    draw.text((150, y), "Description", fill=BLACK, font=header_font)
    draw.text((450, y), "Quantity", fill=BLACK, font=header_font)
    draw.text((550, y), "Unit Value", fill=BLACK, font=header_font)
    draw.text((680, y), "Total Value", fill=BLACK, font=header_font)
    y += 35
    draw.line([(50, y), (800, y)], fill=BLACK, width=1)

    # Goods items
    y += 15
    total_declared = 0
    for item in data['goods']:
        draw.text((60, y), item['hs_code'], fill=BLACK, font=normal_font)
        draw.text((150, y), item['description'][:35], fill=BLACK, font=normal_font)
        draw.text((460, y), str(item['quantity']), fill=BLACK, font=normal_font)
        draw.text((560, y), f"{item['unit_value']:.2f}", fill=BLACK, font=normal_font)
        draw.text((690, y), f"{item['total_value']:.2f}", fill=BLACK, font=normal_font)
        y += 30
        total_declared += item['total_value']

    # Totals
    y += 20
    draw.line([(50, y), (800, y)], fill=BLACK, width=2)
    y += 35
    draw.text((550, y), f"TOTAL DECLARED: {total_declared:.2f}", fill=BLACK, font=title_font)

    # Certifications
    y = 1050
    draw.text((50, y), "I hereby declare that the information above is true and correct.", fill=BLACK, font=small_font)
    y += 25
    draw.text((50, y), f"Declarant: {data['declarant_name']}", fill=BLACK, font=normal_font)
    draw.text((450, y), f"Signature: _________________  Date: {data['declaration_date']}", fill=BLACK, font=normal_font)

    img.save(output_path)
    print(f"Created: {output_path}")


# =============================================================================
# SCENARIO 1: HAPPY PATH (Clean documents, everything matches)
# =============================================================================

happy_invoice = {
    'invoice_number': 'INV-2024-0892',
    'invoice_date': '2024-12-15',
    'supplier_name': 'Shenzhen Electronics Ltd',
    'supplier_address': '123 Tech Park, Nanshan District, Shenzhen, Guangdong, China',
    'supplier_tax_id': '91440300MA5DXX1234',
    'buyer_name': 'Peru Importer SAC',
    'buyer_address': 'Av. Republica de Panama 3455, San Isidro, Lima, Peru',
    'buyer_tax_id': '20601234567',
    'currency': 'USD',
    'shipment_id': 'BL-2024-HK-78234',
    'origin_country': 'China',
    'destination_country': 'Peru',
    'hs_code': '8471.30.00',
    'items': [
        {'description': 'Laptop Computers Model X1', 'quantity': 50, 'unit_price': 450.00, 'amount': 22500.00},
        {'description': 'Computer Monitors 24 inch', 'quantity': 100, 'unit_price': 120.00, 'amount': 12000.00},
    ],
    'total_amount': 34500.00,
    'terms': 'Net 30',
    'signature': 'Approved by Chen Wei'
}

happy_bl = {
    'bl_number': 'BL-2024-HK-78234',
    'bl_date': '2024-12-18',
    'vessel': 'COSCO STAR V.234',
    'shipper_name': 'Shenzhen Electronics Ltd',
    'shipper_address': '123 Tech Park, Nanshan District, Shenzhen, China',
    'consignee_name': 'Peru Importer SAC',
    'consignee_address': 'Av. Republica de Panama 3455, San Isidro, Lima, Peru',
    'port_of_loading': 'Yantian, Shenzhen, China',
    'port_of_discharge': 'Callao, Peru',
    'final_destination': 'Lima, Peru',
    'shipment_id': 'BL-2024-HK-78234',
    'packages': '25 CARTONS',
    'weight': '1250 KG',
    'volume': '18.5 CBM',
    'goods_description': 'Laptop computers and computer monitors, new, packed in cartons, FOB Yantian',
    'marks_numbers': 'PERU IMP - CARTONS 1-25',
    'freight_terms': 'FREIGHT PREPAID',
    'place_of_issue': 'Shenzhen, China'
}

happy_packing = {
    'packing_list_no': 'PL-2024-HK-78234',
    'packing_date': '2024-12-16',
    'invoice_number': 'INV-2024-0892',
    'shipment_id': 'BL-2024-HK-78234',
    'shipper_name': 'Shenzhen Electronics Ltd',
    'consignee_name': 'Peru Importer SAC',
    'from_location': 'Yantian Port, Shenzhen, China',
    'to_location': 'Callao Port, Lima, Peru',
    'vessel_voyage': 'COSCO STAR V.234',
    'packages': [
        {'package_no': '1-10', 'description': 'Laptop Computers Model X1', 'quantity': 10, 'weight': 500, 'volume': 7.5},
        {'package_no': '11-25', 'description': 'Computer Monitors 24 inch', 'quantity': 15, 'weight': 750, 'volume': 11.0},
    ]
}

happy_declaration = {
    'declaration_no': 'DEC-2024-PE-45123',
    'declaration_date': '2024-12-20',
    'customs_office': 'Callao Customs Office',
    'importer_name': 'Peru Importer SAC',
    'importer_tax_id': '20601234567',
    'importer_address': 'Av. Republica de Panama 3455, San Isidro, Lima, Peru',
    'procedure': 'Regular Import (Importación Regular)',
    'shipment_id': 'BL-2024-HK-78234',
    'bl_number': 'BL-2024-HK-78234',
    'origin_country': 'China',
    'declared_value': 34500.00,
    'currency': 'USD',
    'goods': [
        {'hs_code': '8471.30.00', 'description': 'Laptop Computers', 'quantity': 50, 'unit_value': 450.00, 'total_value': 22500.00},
        {'hs_code': '8528.52.00', 'description': 'LCD Monitors', 'quantity': 100, 'unit_value': 120.00, 'total_value': 12000.00},
    ],
    'declarant_name': 'Carlos Mendoza Peru Importer SAC'
}

# =============================================================================
# SCENARIO 2: FRAUDISH (Suspicious patterns)
# =============================================================================

fraud_invoice = {
    'invoice_number': 'INV-2024-FD-999',
    'invoice_date': '2024-12-10',
    'supplier_name': 'Quick Trade HK Limited',
    'supplier_address': 'Unit 8, 15th Floor, Nathan Tower, Kowloon, Hong Kong',
    'supplier_tax_id': 'HK123456789',
    'buyer_name': 'Global Trading Peru SAC',
    'buyer_address': 'Calle Comercio 123, Lima, Peru',
    'buyer_tax_id': '20599887766',
    'currency': 'USD',
    'shipment_id': 'BL-FD-2024-11223',
    'origin_country': 'Hong Kong',
    'destination_country': 'Peru',
    'hs_code': '6403.99.00',
    'items': [
        {'description': 'Leather Shoes', 'quantity': 500, 'unit_price': 25.00, 'amount': 12500.00},
    ],
    'total_amount': 12500.00,  # Understated value
    'terms': 'Cash in Advance',
    'signature': 'Auto-generated'
}

fraud_bl = {
    'bl_number': 'BL-FD-2024-11223',  # Same as invoice shipment
    'bl_date': '2024-11-28',  # Date before invoice - suspicious
    'vessel': 'ASIA EXPRESS V.88',
    'shipper_name': 'Quick Trade HK Limited',
    'shipper_address': 'Unit 8, 15th Floor, Nathan Tower, Kowloon, Hong Kong',
    'consignee_name': 'Global Trading Peru SAC',
    'consignee_address': 'Calle Comercio 123, Lima, Peru',
    'port_of_loading': 'Hong Kong',
    'port_of_discharge': 'Callao, Peru',
    'final_destination': 'Lima, Peru',
    'shipment_id': 'BL-FD-2024-11223',
    'packages': '50 CARTONS',
    'weight': '800 KG',
    'volume': '12.0 CBM',
    'goods_description': 'Footwear and leather goods, assorted types, mixed shipment',
    'marks_numbers': 'GT-PERU-1',
    'freight_terms': 'FREIGHT COLLECT',
    'place_of_issue': 'Hong Kong'
}

fraud_packing = {
    'packing_list_no': 'PL-FD-2024-999',
    'packing_date': '2024-12-05',
    'invoice_number': 'INV-2024-FD-999',
    'shipment_id': 'BL-FD-2024-11223',
    'shipper_name': 'Quick Trade HK Limited',
    'consignee_name': 'Global Trading Peru SAC',
    'from_location': 'Hong Kong Port',
    'to_location': 'Callao Port, Peru',
    'vessel_voyage': 'ASIA EXPRESS V.88',
    'packages': [
        {'package_no': '1-50', 'description': 'Leather shoes and footwear', 'quantity': 50, 'weight': 800, 'volume': 12.0},
    ]
}

fraud_declaration = {
    'declaration_no': 'DEC-2024-PE-FD001',
    'declaration_date': '2024-12-15',
    'customs_office': 'Callao Customs Office',
    'importer_name': 'Global Trading Peru SAC',
    'importer_tax_id': '20599887766',
    'importer_address': 'Calle Comercio 123, Lima, Peru',
    'procedure': 'Regular Import',
    'shipment_id': 'BL-FD-2024-XX44',  # MISMATCH - different from BL!
    'bl_number': 'BL-FD-2024-11223',
    'origin_country': 'Hong Kong',
    'declared_value': 12500.00,  # Matches invoice but both understated
    'currency': 'USD',
    'goods': [
        {'hs_code': '6403.99.00', 'description': 'Leather footwear', 'quantity': 500, 'unit_value': 25.00, 'total_value': 12500.00},
    ],
    'declarant_name': 'Agent for Global Trading'
}

# =============================================================================
# SCENARIO 3: MISSING DOCS (Incomplete documentation)
# =============================================================================

missing_invoice = {
    'invoice_number': 'INV-2024-MD-333',
    'invoice_date': '2024-12-12',
    'supplier_name': 'Taiwan Parts Export Co Ltd',
    'supplier_address': 'Section 4, Taipei, Taiwan',
    'supplier_tax_id': 'TW987654321',
    'buyer_name': 'Andes Parts SAC',
    'buyer_address': 'Jr. de la Union 567, Cusco, Peru',
    'buyer_tax_id': '20605554444',
    'currency': 'USD',
    'shipment_id': 'BL-MD-2024-44556',
    'origin_country': 'Taiwan',
    'destination_country': 'Peru',
    'hs_code': '8481.80.00',
    'items': [
        {'description': 'Industrial Machinery Parts', 'quantity': 200, 'unit_price': 75.00, 'amount': 15000.00},
    ],
    'total_amount': 15000.00,
    'terms': 'Net 30',
    'signature': 'Taiwan Export'
}

missing_packing = {
    'packing_list_no': 'PL-MD-2024-333',
    'packing_date': '2024-12-11',
    'invoice_number': 'INV-2024-MD-333',
    'shipment_id': 'BL-MD-2024-44556',
    'shipper_name': 'Taiwan Parts Export Co Ltd',
    'consignee_name': 'Andes Parts SAC',
    'from_location': 'Kaohsiung Port, Taiwan',
    'to_location': 'Callao Port, Peru',
    'vessel_voyage': 'EVER GLORY V.156',
    'packages': [
        {'package_no': '1-20', 'description': 'Machinery parts and components', 'quantity': 20, 'weight': 450, 'volume': 8.0},
    ]
}


def main():
    print("Generating demo documents...")
    print("=" * 60)

    # Scenario 1: Happy Path
    print("\n[1/3] Creating HAPPY PATH documents...")
    happy_dir = OUTPUT_DIR / "docs_happy_path"
    create_invoice(happy_invoice, happy_dir / "invoice.png")
    create_bill_of_lading(happy_bl, happy_dir / "bill_of_lading.png")
    create_packing_list(happy_packing, happy_dir / "packing_list.png")
    create_customs_declaration(happy_declaration, happy_dir / "declaration.png")

    # Scenario 2: Fraudish
    print("\n[2/3] Creating FRAUDISH documents...")
    fraud_dir = OUTPUT_DIR / "docs_fraudish"
    create_invoice(fraud_invoice, fraud_dir / "invoice.png")
    create_bill_of_lading(fraud_bl, fraud_dir / "bill_of_lading.png")
    create_packing_list(fraud_packing, fraud_dir / "packing_list.png")
    create_customs_declaration(fraud_declaration, fraud_dir / "declaration.png")

    # Scenario 3: Missing Docs
    print("\n[3/3] Creating MISSING DOCS documents...")
    missing_dir = OUTPUT_DIR / "docs_missing_docs"
    create_invoice(missing_invoice, missing_dir / "invoice.png")
    create_packing_list(missing_packing, missing_dir / "packing_list.png")
    # No BL or declaration - simulating missing docs

    print("\n" + "=" * 60)
    print("Demo documents created successfully!")
    print(f"\nOutput directory: {OUTPUT_DIR}")
    print("\nScenarios:")
    print("  1. docs_happy_path/     - 4 documents (clean, matching)")
    print("  2. docs_fraudish/        - 4 documents (suspicious patterns)")
    print("  3. docs_missing_docs/    - 2 documents (incomplete)")


if __name__ == "__main__":
    main()
