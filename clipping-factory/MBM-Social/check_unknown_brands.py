import json, glob
# Look for any packages with unknown brands
for f in glob.glob('publish_queue/*.json'):
    try:
        with open(f) as fh:
            d = json.load(fh)
            if d.get('status') == 'draft':
                brand = d.get('brand', '')
                if brand not in ['clippingfactorymbm','cutedosage','dontwatchthis','goalmachinez','twistsrevealed']:
                    print(f'{f}: brand={brand}, title={d.get("title","")[:50]}')
    except Exception as e:
        pass