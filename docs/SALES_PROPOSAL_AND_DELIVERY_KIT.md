# MBM Content Engine: Sales Proposal & Client Delivery Kit

**Service Line:** Autonomous Podcast & Video Repurposing (Long-form to Short-form)  
**Deliverable Standard:** 1080x1920 (9:16) Vertical Video + Burned Animated Subtitles + Hook & Title Copy Pack  
**Verification Date:** September 3, 2026  
**Status:** Founder-Ready / Demo-First  

---

## 1. Service One-Pager (What We Sell)

### The Pitch in 3 Sentences
"You record the podcast. We turn every 45-minute episode into 5 viral-ready 9:16 vertical clips with animated captions, hook headlines, and complete publishing copy packs. Delivered to your Google Drive in 48 hours so you can dominate YouTube Shorts, Instagram Reels, and TikTok without spending 20 hours editing."

### Scope of Deliverables per Episode
- **5 High-Impact Short-Form Clips:** 30–60 seconds, framed in 1080x1920 (9:16) vertical HD.
- **Word-Pop Animated Subtitles:** Clean, eye-catching animated captions burned directly into the video.
- **Copy Pack per Clip:**
  - 3 Hook Headline variants (tested for initial 3-second viewer retention).
  - Optimized Video Title (under 70 characters).
  - Video Description with Call-to-Action.
  - 5–8 targeted hashtags.
- **Delivery Timeline:** Target turnaround within 48–72 hours from raw video submission.
- **Delivery Mechanism:** Private Google Drive folder organized by clip number + ready-to-copy text document.

---

## 2. Pricing Tiers (Recommended Initial Pricing)

| Tier | Price | Monthly Volume | Deliverables | Best For |
|---|---|---|---|---|
| **Starter (Paid Test)** | **$149 one-time** | 1 Episode | 5 vertical clips + burned captions + copy pack | Creators testing output quality with zero risk |
| **Growth (Monthly Retainer)** | **$497 / month** | 4 Episodes (1/wk) | 20 vertical clips (5/wk) + copy packs + YouTube Shorts auto-publish | Active podcasters & founders building personal brand |
| **Agency / White-Label** | **$1,250 / month** | 12 Episodes | 60 vertical clips + white-label folders | Marketing agencies reselling clipping to their clients |

*Note: Pricing is recommended initial market positioning based on manual/automated delivery economics, not historical transactional data.*

---

## 3. Client Discovery & Qualification Questions

Ask these 4 questions to qualify any prospect in 3 minutes:
1. *"How often do you record long-form video or audio (podcasts, webinars, YouTube videos)?"*
   - *Target answer:* At least once every 1–2 weeks.
2. *"Are you currently repurposing those recordings into 9:16 Shorts / Reels / TikToks?"*
   - *Target answer:* Either "No, we don't have the time" or "Yes, but it takes our team forever and costs too much."
3. *"If you could send us a raw link and get 5 polished vertical clips with animated subtitles back in 48–72 hours, would that solve your bottleneck?"*
4. *"Can I take a 2-minute snippet of your latest episode and render 1 free sample clip so you can see our caption quality?"*

---

## 4. Demo Instructions (How to Showcase the Capability)

The sales package includes a verified, broadcast-ready vertical sample asset:
- **Verified Proof Asset:** [`docs/samples/demo_clip.mp4`](file:///c:/Users/omare/OneDrive/Desktop/AI/docs/samples/demo_clip.mp4) (9.95 MB, 1080x1920, H.264/AAC, 18.9s).
- **Features Demonstrated:** Top hook banner (`★ PODCAST REPURPOSING SYSTEM ★`), word-pop highlighted captions, dark aesthetic motion backdrop, and normalized speech.

### Presentation Option A: Share Verified Sample Asset
1. **Send File Directly:** Attach `docs/samples/demo_clip.mp4` via email, LinkedIn, or DM.
2. **Key Talking Points:** Highlight the high-contrast yellow/green animated subtitles, safe-zone positioning (clear of TikTok/Reels UI buttons), and professional audio normalization.

### Presentation Option B: Tailored Spec Demo (Highest Conversion)
1. **Ingest 2 Minutes of Prospect's Public Content:** Take 1 public YouTube video from the target creator and extract a 30-second high-energy moment.
2. **Reframe & Burn Subtitles:** Run local ffmpeg 9:16 reframe centered on their face and burn animated word-pop captions in their brand color.
3. **Send Their Own Clip:** Send their own face and voice back to them with high-end subtitles.
4. **Offer the Starter Test:** "Send me your full episode link. We'll deliver the first complete 5-clip package with copy packs for $149."

---

## 5. Client Delivery Checklist (Internal Standard Operating Procedure)

For every client order:
- [ ] **Ingest**: Download raw MP4 or extract audio from client's YouTube link.
- [ ] **Timestamp Selection**: Identify the top 5 high-energy moments (30–60 seconds each) where a key lesson, story, or controversial insight begins.
- [ ] **ffmpeg Reframe**: Run local ffmpeg reframe to 1080x1920 vertical canvas.
- [ ] **Subtitle Generation**: Render animated `.ass` subtitle file with Outfit-Bold typography and primary color styling.
- [ ] **Subtitle Burn-in**: Execute `ffmpeg -vf subtitles=...` to generate final MP4.
- [ ] **QC Review**: Founder plays each clip to check:
  - Speaker's face is centered and not cut off.
  - Subtitles do not overlap platform UI buttons (bottom 250px and right 120px are clear).
  - Audio and video remain strictly synchronized.
- [ ] **Copy Pack**: Draft 3 hook titles, video description, and hashtags.
- [ ] **Handoff**: Upload MP4 files and `copy_pack.txt` into client's Google Drive folder. Notify client via email.

---

## 6. Proposal Draft (Copy-Paste for DMs / Email)

```
Subject: Quick idea for [Podcast Name] / 5 Shorts from your latest episode

Hi [First Name],

Loved your latest conversation on [topic from recent episode]. 

I noticed you're putting great insights into your 45-minute episodes, but you aren't posting daily short-form clips to YouTube Shorts, Reels, and TikTok to capture the organic algorithm.

We run a dedicated video repurposing pipeline for creators. We take your raw episode and deliver:
- 5 polished 9:16 vertical clips with animated word-pop captions
- 3 hook headlines and complete title/hashtag copy packs for every clip
- Turnaround in 48 hours straight to your Google Drive

Here is an exact 14-second sample of our vertical caption quality: [Attach demo_clip.mp4]

We're offering a 1-episode test (5 clips + full copy packs) for $149. If you love the engagement, we can handle all 4 monthly episodes for $497/mo.

Would you be open to testing 1 episode this week?

Best,
[Your Name]
MBM Media Studio
```

---

## 7. Common Objections & How to Handle Them

1. **"Can't I just use an AI tool like Opus Clip or Submagic myself?"**
   - *Response:* "You can, but those tools still require 3–5 hours of your time every week to review, adjust misaligned crop boxes, fix spelling mistakes in the AI transcription, and write hooks and hashtags. We provide a completely hands-off service: you send the link, we do the editing, caption QA, and copy drafting. Your time is worth more than $30/hour."
2. **"Do you auto-post to our social accounts?"**
   - *Response:* "We can schedule directly to your YouTube Shorts if you add us as a channel manager. For TikTok and Instagram, we deliver ready-to-post MP4s and formatted text copy directly to your Google Drive so you or your assistant can upload them with one click in 60 seconds."
3. **"What if I don't like the clips you pick?"**
   - *Response:* "Every batch includes 1 round of revisions. If you prefer a different segment, just give us the timestamp and we'll re-cut and caption it within 24 hours at no extra charge."

---

## 8. Verified Payment Instructions

To accept payment safely without dependencies on unverified Whop checkouts:
- **Primary Option (Direct Invoice / Bank Transfer / Neteller):**
  - Invoice the client via Neteller merchant transfer: `abdelshafyclapps@gmail.com` (Account ID: `4599228811`).
  - Or invoice via standard founder-led client billing (Stripe Invoice, Wise, or Direct Wire).
  - *(Public Merchant Receiving Identifiers only; zero private keys, API secrets, or sensitive credentials exposed).*
- **Fulfillment Rule:**
  - Payment is collected upfront for the Starter test ($149) or at the beginning of the monthly billing cycle ($497).
  - Delivery link is emailed within 48–72 hours of video submission.
