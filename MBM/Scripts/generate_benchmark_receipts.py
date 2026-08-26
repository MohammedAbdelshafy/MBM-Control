import os
import json
import random
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import arabic_reshaper
from bidi.algorithm import get_display

def apply_arabic(text):
    if any("\u0600" <= c <= "\u06FF" for c in text):
        reshaped_text = arabic_reshaper.reshape(text)
        return get_display(reshaped_text)
    return text

def generate_noise(image):
    # Add simple gaussian noise
    img_array = np.array(image)
    noise = np.random.normal(0, 5, img_array.shape)
    img_array = img_array + noise
    img_array = np.clip(img_array, 0, 255).astype(np.uint8)
    # Apply a light blur occasionally
    if random.choice([True, False]):
        img_array = cv2.GaussianBlur(img_array, (3,3), 0)
    return Image.fromarray(img_array)

def rotate_image(image, angle):
    return image.rotate(angle, resample=Image.BICUBIC, fillcolor=(255,255,255))

def generate_receipts(num_receipts=30):
    images_dir = "benchmark_data/images"
    gt_dir = "benchmark_data/ground_truth"
    os.makedirs(images_dir, exist_ok=True)
    os.makedirs(gt_dir, exist_ok=True)

    # Try to load a font that supports Arabic
    font_path = "C:\\Windows\\Fonts\\arial.ttf"
    try:
        font_large = ImageFont.truetype(font_path, 24)
        font_medium = ImageFont.truetype(font_path, 18)
    except IOError:
        font_large = ImageFont.load_default()
        font_medium = ImageFont.load_default()

    vendors = [
        {"name": "شركة الحمد للمقاولات", "lang": "ar"},
        {"name": "مورد أسمنت المتحدة", "lang": "ar"},
        {"name": "Delta Construction Supplies", "lang": "en"},
        {"name": "El-Sewedy Cables", "lang": "en"},
        {"name": "ورشة الحدادة - Ali Brothers", "lang": "mixed"},
    ]
    currencies = ["EGP", "USD", "ج.م"]
    methods = ["CASH", "VISA", "نقدا", "تحويل بنكي"]

    for i in range(1, num_receipts + 1):
        print(f"Generating receipt {i}")
        vendor = random.choice(vendors)
        lang = vendor["lang"]
        
        date = f"2026-08-{random.randint(1,28):02d}"
        doc_num = f"INV-{random.randint(1000,9999)}"
        subtotal = round(random.uniform(500, 10000), 2)
        vat = round(subtotal * 0.14, 2)
        total = round(subtotal + vat, 2)
        method = random.choice(methods)
        currency = random.choice(currencies)

        # Build ground truth
        gt = {
            "vendor": vendor["name"],
            "date": date,
            "document_number": doc_num,
            "subtotal": subtotal,
            "VAT": vat,
            "total": total,
            "payment_method": method,
            "currency": currency
        }

        with open(f"{gt_dir}/doc_{i:03d}.json", "w", encoding="utf-8") as f:
            json.dump(gt, f, ensure_ascii=False, indent=2)

        print(f"Drawing image {i}")
        # Draw image
        img = Image.new('RGB', (600, 800), color='white')
        draw = ImageDraw.Draw(img)

        # Format texts
        header = apply_arabic(f"{vendor['name']}")
        date_str = apply_arabic(f"Date: {date}")
        doc_str = apply_arabic(f"Invoice #: {doc_num}")
        sub_str = apply_arabic(f"Subtotal: {subtotal} {currency}")
        vat_str = apply_arabic(f"VAT (14%): {vat} {currency}")
        total_str = apply_arabic(f"TOTAL: {total} {currency}")
        method_str = apply_arabic(f"Payment: {method}")

        # Draw layout
        y = 50
        draw.text((300, y), header, font=font_large, fill='black', anchor="mm")
        y += 60
        draw.text((50, y), date_str, font=font_medium, fill='black')
        draw.text((400, y), doc_str, font=font_medium, fill='black')
        y += 100
        
        # Draw some mock items
        for _ in range(random.randint(2, 5)):
            item_text = apply_arabic(f"Item {_} x {random.randint(1,10)}")
            draw.text((50, y), item_text, font=font_medium, fill='black')
            y += 30

        y += 50
        draw.line([(50, y), (550, y)], fill='black', width=2)
        y += 20
        draw.text((300, y), sub_str, font=font_medium, fill='black')
        y += 30
        draw.text((300, y), vat_str, font=font_medium, fill='black')
        y += 30
        draw.text((300, y), total_str, font=font_large, fill='black')
        y += 50
        draw.text((50, y), method_str, font=font_medium, fill='black')

        # Apply noise/rotation
        img = generate_noise(img)
        # Random rotation between -3 and 3 degrees to simulate scanning
        angle = random.uniform(-3, 3)
        img = rotate_image(img, angle)

        img.save(f"{images_dir}/doc_{i:03d}.png")
        print(f"Saved {i}")

    print(f"Generated {num_receipts} documents in {images_dir}")

if __name__ == "__main__":
    generate_receipts(30)
