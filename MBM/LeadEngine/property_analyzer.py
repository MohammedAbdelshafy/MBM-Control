import os
import json
import re

class PropertyAnalyzer:
    def __init__(self):
        # Keywords that indicate a motivated seller, distressed property, or investment opportunity
        self.distressed_keywords = [
            r'\bauction\b',
            r'\bmodernisation\b',
            r'\bmodernization\b',
            r'\bneeds updating\b',
            r'\brefurbishment\b',
            r'\bproject\b',
            r'\binvestment opportunity\b',
            r'\bcash buyers only\b',
            r'\bno onward chain\b',
            r'\bmotivated seller\b',
            r'\bquick sale\b',
            r'\bprobate\b',
            r'\bstructural issues\b',
            r'\bderelict\b',
            r'\brepossession\b',
            r'\breforma integral\b',
            r'\bpara reformar\b',
            r'\bsubasta\b',
            r'\binversión\b',
            r'\bà rénover\b',
            r'\bprévoir travaux\b',
            r'\bvente rapide\b'
        ]
        
    def clean_price(self, price_str):
        if not price_str: return 0
        cleaned = re.sub(r'[^\d]', '', price_str)
        return int(cleaned) if cleaned else 0

    def analyze(self, properties):
        analyzed_leads = []
        
        for prop in properties:
            desc = prop.get('description', '').lower()
            flags = []
            
            # Check for distressed/investor keywords
            for kw in self.distressed_keywords:
                if re.search(kw, desc):
                    flags.append(kw.replace(r'\b', ''))
                    
            price_val = self.clean_price(prop.get('price'))
            
            # Determine priority score based on flags and price
            score = len(flags) * 10
            # Extra points for cash buyers only or auction
            if 'cash buyers only' in flags or 'auction' in flags:
                score += 20
                
            prop['is_lead'] = score > 0
            prop['lead_score'] = score
            prop['flagged_keywords'] = flags
            prop['price_value'] = price_val
            
            analyzed_leads.append(prop)
            
        # Sort so highest score is at the top
        analyzed_leads.sort(key=lambda x: x['lead_score'], reverse=True)
        return analyzed_leads

if __name__ == "__main__":
    input_path = os.path.join(os.path.dirname(__file__), 'raw_properties.json')
    output_path = os.path.join(os.path.dirname(__file__), 'hot_leads.json')
    
    if not os.path.exists(input_path):
        print(f"Error: {input_path} not found. Run scraper first.")
        exit(1)
        
    with open(input_path, 'r', encoding='utf-8') as f:
        properties = json.load(f)
        
    print(f"Analyzing {len(properties)} properties...")
    analyzer = PropertyAnalyzer()
    results = analyzer.analyze(properties)
    
    hot_leads = [p for p in results if p['is_lead']]
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(hot_leads, f, indent=2)
        
    print(f"Analysis complete! Found {len(hot_leads)} hot investment leads out of {len(properties)} properties.")
    print(f"Saved to {output_path}")
    
    if hot_leads:
        print("\nTop 3 Leads:")
        for lead in hot_leads[:3]:
            print(f"- {lead['price']} | {lead['address']} | Score: {lead['lead_score']}")
            print(f"  Keywords: {', '.join(lead['flagged_keywords'])}")
            print(f"  URL: {lead['url']}\n")
