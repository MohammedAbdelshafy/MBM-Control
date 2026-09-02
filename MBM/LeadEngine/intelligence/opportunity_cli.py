"""
CLI tool for reviewing Intelligence Opportunities.
"""
import sys
import json
import logging
from typing import List

from .opportunity_queue import list_opportunities
from .human_approval import approve_opportunity, reject_opportunity
from .types import OpportunityStatus

def print_header(title: str):
    print(f"\n\033[1;36m{'=' * 50}\033[0m")
    print(f"\033[1;36m{title.center(50)}\033[0m")
    print(f"\033[1;36m{'=' * 50}\033[0m\n")

def print_field(name: str, value: str):
    print(f"\033[1m{name}:\033[0m {value}")

def review_loop(actor: str, dry_run: bool = False):
    try:
        all_opps = list_opportunities(limit=1000)
    except Exception as e:
        print(f"\033[1;31mError loading opportunities: {e}\033[0m")
        return
        
    review_queue = [opp for opp in all_opps if opp.get("status") == OpportunityStatus.REVIEW_REQUIRED.value]

    if not review_queue:
        print("\n\033[1;32mNo opportunities currently require review.\033[0m\n")
        return

    print_header(f"Opportunity Queue: {len(review_queue)} to review")

    for idx, opp in enumerate(review_queue):
        print(f"\n\033[1;33m--- Opportunity {idx + 1} of {len(review_queue)} ---\033[0m")
        print_field("ID", opp.get("opportunity_id", ""))
        print_field("Provider", opp.get("source_provider", ""))
        print_field("Title", opp.get("title", ""))
        print_field("Summary", opp.get("summary", ""))
        print_field("Score", str(opp.get("total_score", 0)))
        
        prov = opp.get("provenance", {})
        print_field("Provenance", f"URL: {prov.get('source_url', 'None')} | Hash: {prov.get('content_hash', 'None')}")
        
        while True:
            choice = input("\n\033[1;34mAction [(A)pprove / (R)eject / (S)kip / (Q)uit]:\033[0m ").strip().lower()
            if choice == 'a':
                reason = input("Reason for approval (min 5 chars): ").strip()
                try:
                    if dry_run:
                        print(f"\033[1;35m[DRY RUN] Would transition opp {opp.get('opportunity_id')} to APPROVED with actor '{actor}' and reason '{reason}'.\033[0m")
                    else:
                        approve_opportunity(opp["opportunity_id"], actor=actor, reason=reason)
                        print("\033[1;32m[APPROVED]\033[0m")
                    break
                except Exception as e:
                    print(f"\033[1;31mError: {e}\033[0m")
            elif choice == 'r':
                reason = input("Reason for rejection: ").strip()
                try:
                    if dry_run:
                        print(f"\033[1;35m[DRY RUN] Would transition opp {opp.get('opportunity_id')} to REJECTED with actor '{actor}' and reason '{reason}'.\033[0m")
                    else:
                        reject_opportunity(opp["opportunity_id"], actor=actor, reason=reason)
                        print("\033[1;31m[REJECTED]\033[0m")
                    break
                except Exception as e:
                    print(f"\033[1;31mError: {e}\033[0m")
            elif choice == 's':
                print("Skipped.")
                break
            elif choice == 'q':
                print("\nExiting review loop.")
                return
            else:
                print("Invalid choice.")

def main(args):
    actor = getattr(args, "actor", None)
    if not actor:
        print("\033[1;31mError: --actor is required for audit logging.\033[0m")
        return
    review_loop(actor=actor)
