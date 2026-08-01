"""
Automated Affiliate Link Injector
Mission: Automatically matches and appends targeted affiliate links (OpusClip, Invideo,
Dynamiq, Synthflow, Whop, Vyro) to video descriptions before publishing.
"""
import os
import sys
import json
import io

# Force UTF-8 output for Windows console terminals
if hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

class AffiliateLinkInjector:
    def __init__(self):
        self.affiliate_links = {
            "tech_automation": [
                "🚀 Repurpose long videos into viral clips with OpusClip (25% Off): https://opus.pro/?via=mbm",
                "🤖 Automate high-converting AI Voice Agents with Dynamiq: https://dynamiq.ai/?ref=mbm",
                "📹 Generate faceless channel videos instantly with InVideo AI: https://invideo.io/?ref=mbm"
            ],
            "business_finance": [
                "💰 Launch your automated digital agency on Whop: https://whop.com/?a=mbmclipping",
                "📞 Automate business calls with Synthflow AI: https://synthflow.ai/?via=mbm"
            ],
            "islamic_content": [
                "📖 Join the MuslimsClipping Community & Earn: https://muslimsclipping.com/?ref=mbm"
            ],
            "general_gaming": [
                "🎮 Earn $3 per 1k views clipping gaming videos on Vyro: https://vyro.com/?ref=mbm"
            ]
        }

    def inject_affiliate_links(self, description: str, profile_name: str = "tech_automation") -> str:
        """Appends relevant affiliate callouts to the bottom of a video description."""
        category_links = self.affiliate_links.get(profile_name, self.affiliate_links["tech_automation"])
        
        affiliate_block = "\n\n--- 🔗 TOP RESOURCES & TOOLS ---\n" + "\n".join(category_links)
        
        # Avoid duplicate injection
        if "TOP RESOURCES & TOOLS" in description:
            return description

        return description + affiliate_block

if __name__ == "__main__":
    injector = AffiliateLinkInjector()
    desc = "Watch how AI is replacing manual clip editing! #ai #automation"
    enhanced_desc = injector.inject_affiliate_links(desc, "tech_automation")
    print("=== AFFILIATE LINK INJECTOR VERIFIED ===")
    print("Original Description:")
    print(desc)
    print("\nEnhanced Description with Injected Links:")
    print(enhanced_desc)
