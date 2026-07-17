"""
Seed campaigns into the Clipping Factory database so the pipeline has work to do.

Run:
    cd clipping-factory/backend
    .venv\\Scripts\\python.exe seed_campaigns.py

Behaviour:
- If real Clipping.com credentials are configured (CLIPPING_EMAIL/PASSWORD),
  the hunter scans the live site for campaigns.
- Otherwise it runs in DEMO mode and seeds realistic campaigns across Whop,
  Vyro, MuslimsClipping.com and Clipping.com (each with full clip requirements
  and a downloadable source video), so the rest of the pipeline can start working
  immediately. Set CLIPPING_EMAIL + CLIPPING_PASSWORD in backend/.env to pull
  real campaigns from the sites instead.
"""
from app.core.database import SyncSessionLocal
from app.agents.campaign_hunter import CampaignHunterAgent


def main():
    db = SyncSessionLocal()
    try:
        agent = CampaignHunterAgent(db=db)
        result = agent.run()
        print("Seed result:", result.data)
    finally:
        db.close()


if __name__ == "__main__":
    main()
