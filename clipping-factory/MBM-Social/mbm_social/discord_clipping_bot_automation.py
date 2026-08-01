"""
Discord Clipping Bot Automation & Slash Command Generator
Mission: Automates account linking, payout address setup, post link submission (/upload, /bounty-upload),
and view stats tracking for Discord-based Clipping Marketplaces (Clipping.net, ClipAffiliates, Whop).
"""
import os
import sys
import json
import time

class DiscordClippingBotAutomation:
    def __init__(self, master_email: str = "abdelshafyclapps@gmail.com"):
        self.master_email = master_email
        self.paypal_email = master_email
        self.payout_first_name = "Mohammed"
        self.payout_last_name = "Abdelshafy"
        self.sol_usdc_wallet = "MBMSolanaUsdcWalletAddressPlaceholder11111111"
        self.eth_usdc_wallet = "0xMBMEthereusUsdcWalletAddressPlaceholder11111"
        
        self.registered_accounts = {
            "youtube": ["@DONTWATCHTHIS1", "@Goalmachinez", "@CuteDosage", "@ClippingFactoryMBM", "@TwistsRevealed"],
            "tiktok": ["@dontwatchthis_official", "@cutedosage_official"],
            "instagram": ["@twistsrevealed_reels", "@cutenessoverload"]
        }

    def generate_account_link_commands(self) -> list:
        """Generates /add-account slash commands for all active brand channels."""
        commands = []
        for platform, handles in self.registered_accounts.items():
            for handle in handles:
                commands.append(f"/add-account platform:{platform} username:{handle}")
        return commands

    def generate_payment_commands(self) -> list:
        """Generates payment setup slash commands for PayPal and USDC."""
        return [
            f"/add-paypal email:{self.paypal_email} first_name:{self.payout_first_name} last_name:{self.payout_last_name}",
            f"/add-usdc address:{self.eth_usdc_wallet}",
            f"/add-sol-usdc address:{self.sol_usdc_wallet}"
        ]

    def format_upload_command(self, post_urls: list, tag: str = None) -> str:
        """Formats /upload or /bounty-upload command (up to 10 URLs comma-separated)."""
        clean_urls = post_urls[:10]  # Max 10 URLs per Discord command limit
        urls_str = ",".join(clean_urls)
        
        if tag:
            return f"/bounty-upload link:{urls_str} tag:{tag}"
        return f"/upload link:{urls_str}"

    def format_remove_video_command(self, post_urls: list) -> str:
        """Formats /remove-video command."""
        urls_str = ",".join(post_urls[:10])
        return f"/remove-video link:{urls_str}"

    def get_stats_commands(self) -> list:
        """Returns stats and leaderboard tracking commands."""
        return ["/stats", "/leaderboard", "/account-info", "/payment-details"]

if __name__ == "__main__":
    bot = DiscordClippingBotAutomation()
    print("=== DISCORD CLIPPING BOT AUTOMATION GENERATOR ===")
    print("\n1. Account Linking Commands:")
    for cmd in bot.generate_account_link_commands()[:4]:
        print(f"  {cmd}")

    print("\n2. Payment Setup Commands:")
    for cmd in bot.generate_payment_commands():
        print(f"  {cmd}")

    sample_urls = [
        "https://www.youtube.com/shorts/v12345",
        "https://www.youtube.com/shorts/v67890"
    ]
    print("\n3. Sample Video Upload Commands:")
    print(f"  Normal Upload: {bot.format_upload_command(sample_urls)}")
    print(f"  Bounty Upload: {bot.format_upload_command(sample_urls, tag='StakeBounty')}")
