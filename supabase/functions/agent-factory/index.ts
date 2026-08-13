import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const RETELL_API_KEY = Deno.env.get("RETELL_API_KEY");
const RETELL_API = "https://api.retellai.com";

const VOICE_IDS = [
  "retell-Willa", "retell-Alejandro", "retell-Nico",
  "retell-Cimo", "retell-Cleo", "retell-Adam",
  "retell-Hailey", "retell-Brian"
];

const NICHES = [
  { name: "HVAC Repair", persona: "Friendly HVAC service coordinator", hook: "Hi! I'm calling about your heating and cooling system. Are you still experiencing issues?", close: "I'll have a technician call you within 30 minutes.", rate: 0.35 },
  { name: "Plumbing Emergency", persona: "Calm plumbing dispatcher", hook: "Hi! I see you submitted a plumbing request. Is this still an emergency?", close: "A licensed plumber will call you within 15 minutes.", rate: 0.35 },
  { name: "Solar Panel Sales", persona: "Energetic clean energy consultant", hook: "Hi! I'm calling about solar panels. Are you still interested in reducing your electricity bill?", close: "I'll send you a free solar estimate.", rate: 0.45 },
  { name: "Roofing Contractor", persona: "Professional roofing consultant", hook: "Hi! Are you still looking to get your roof inspected or repaired?", close: "We can schedule a free inspection this week.", rate: 0.40 },
  { name: "Insurance Claims", persona: "Empathetic insurance claim specialist", hook: "Hi! Are you still needing assistance with your insurance claim?", close: "I'll have an adjuster review your case within 24 hours.", rate: 0.50 },
  { name: "Legal Consultation", persona: "Professional legal intake specialist", hook: "Hi! You requested a consultation. Are you still looking for legal assistance?", close: "An attorney will call you within 2 hours.", rate: 0.55 },
  { name: "Dental Appointment", persona: "Warm dental receptionist", hook: "Hi! I'm calling about your dental appointment. Are you still able to make it?", close: "I'll confirm your appointment and send a reminder.", rate: 0.30 },
  { name: "Auto Detailing", persona: "Enthusiastic auto detailing coordinator", hook: "Hi! Are you still looking to get your vehicle detailed?", close: "I'll book your detail slot.", rate: 0.35 },
  { name: "Moving Company", persona: "Organized moving coordinator", hook: "Hi! Are you still planning to relocate?", close: "I'll prepare a custom quote.", rate: 0.40 },
  { name: "Pest Control", persona: "Knowledgeable pest control specialist", hook: "Hi! Are you still experiencing pest issues?", close: "We can treat your home this week.", rate: 0.35 },
  { name: "Landscaping", persona: "Creative landscaping consultant", hook: "Hi! Are you still looking to improve your outdoor space?", close: "I'll design a custom proposal.", rate: 0.40 },
  { name: "Pool Service", persona: "Friendly pool maintenance coordinator", hook: "Hi! Is your pool still needing maintenance or repair?", close: "A pool tech will call you within 1 hour.", rate: 0.35 },
  { name: "Window Cleaning", persona: "Efficient window cleaning dispatcher", hook: "Hi! Are you still looking to get your windows cleaned?", close: "I'll book your cleaning slot.", rate: 0.30 },
  { name: "Painting Contractor", persona: "Detail-oriented painting consultant", hook: "Hi! Are you still looking to get your space painted?", close: "I'll prepare a free estimate.", rate: 0.40 },
  { name: "Electrical Services", persona: "Licensed electrical coordinator", hook: "Hi! Are you still experiencing electrical problems?", close: "A licensed electrician will call you within 30 minutes.", rate: 0.45 },
  { name: "Concrete Foundation", persona: "Structural foundation specialist", hook: "Hi! Are you noticing any cracks or settling?", close: "We'll schedule a free inspection this week.", rate: 0.50 },
  { name: "Fence Installation", persona: "Friendly fencing coordinator", hook: "Hi! Are you still looking to install or repair a fence?", close: "I'll prepare a custom quote.", rate: 0.35 },
  { name: "Garage Door", persona: "Quick garage door specialist", hook: "Hi! Is your garage door still not working properly?", close: "A tech will call you within 20 minutes.", rate: 0.35 },
  { name: "Gutter Cleaning", persona: "Efficient gutter service coordinator", hook: "Hi! Are you still looking to get your gutters cleaned?", close: "I'll book your gutter cleaning this week.", rate: 0.30 },
  { name: "Handyman Services", persona: "Versatile handyman coordinator", hook: "Hi! What repairs or projects do you need help with?", close: "I'll match you with the right handyman.", rate: 0.35 },
  { name: "Carpet Cleaning", persona: "Professional carpet cleaning dispatcher", hook: "Hi! Are you still looking to get your carpets cleaned?", close: "I'll book your carpet cleaning.", rate: 0.30 },
  { name: "Appliance Repair", persona: "Knowledgeable appliance repair coordinator", hook: "Hi! Is your appliance still malfunctioning?", close: "A tech will call you within 1 hour.", rate: 0.40 },
  { name: "Home Inspection", persona: "Thorough home inspection coordinator", hook: "Hi! Are you still looking to schedule a home inspection?", close: "I'll book your inspection.", rate: 0.45 },
  { name: "Tree Service", persona: "Experienced tree care specialist", hook: "Hi! Do you still need tree work done?", close: "We can have a crew out this week.", rate: 0.40 },
  { name: "Pressure Washing", persona: "Energetic pressure washing coordinator", hook: "Hi! Are you still looking to get your property pressure washed?", close: "I'll book your pressure wash this week.", rate: 0.30 },
  { name: "Flooring Installation", persona: "Professional flooring consultant", hook: "Hi! Are you still looking to install new flooring?", close: "I'll prepare a custom estimate.", rate: 0.45 },
  { name: "Smart Home Setup", persona: "Tech-savvy smart home specialist", hook: "Hi! Are you still interested in home automation?", close: "I'll design a custom setup.", rate: 0.50 },
  { name: "Water Heater", persona: "Quick water heater specialist", hook: "Hi! Is your water heater still not working properly?", close: "We can install a new unit tomorrow.", rate: 0.40 },
  { name: "Attic Insulation", persona: "Energy efficiency specialist", hook: "Hi! Are you still looking to improve your home's energy efficiency?", close: "We can insulate your attic this week.", rate: 0.40 },
  { name: "Commercial Roofing", persona: "Professional commercial roofing estimator", hook: "Hi! Are you still interested in scheduling a commercial roof inspection?", close: "I'll have our estimator call you within 1 hour.", rate: 0.55 },
  { name: "Commercial HVAC Maintenance", persona: "Experienced commercial HVAC account manager", hook: "Hi! Are you still looking for a commercial HVAC maintenance plan?", close: "I'll send over a preventative maintenance quote today.", rate: 0.55 },
  { name: "Medical Billing Services", persona: "Knowledgeable medical billing consultant", hook: "Hi! Are you still looking to improve your claim approval rates?", close: "I'll schedule a free revenue cycle review.", rate: 0.60 },
  { name: "Dental Practice Growth", persona: "Dental practice growth specialist", hook: "Hi! Are you still looking to fill more appointments?", close: "I'll put together a growth plan for your practice.", rate: 0.60 },
  { name: "Commercial Janitorial Contracts", persona: "Facilities services account executive", hook: "Hi! Are you still looking for a commercial janitorial provider?", close: "I'll prepare a custom cleaning proposal today.", rate: 0.55 },
  { name: "IT Managed Services", persona: "IT solutions consultant", hook: "Hi! Are you still looking for managed IT services?", close: "I'll schedule a free IT assessment.", rate: 0.65 },
  { name: "Industrial Recycling & Waste", persona: "Industrial waste management specialist", hook: "Hi! Are you still looking to reduce waste disposal costs?", close: "I'll put together a savings estimate.", rate: 0.65 },
  { name: "Freight & Logistics Brokerage", persona: "Freight brokerage account manager", hook: "Hi! Are you still looking for reliable freight carriers?", close: "I'll match you with vetted carriers this week.", rate: 0.65 },
  { name: "Restaurant Equipment Repair", persona: "Commercial kitchen service coordinator", hook: "Hi! Are you still looking for commercial kitchen repair service?", close: "A certified tech will call you within 30 minutes.", rate: 0.55 },
  { name: "Commercial Refrigeration", persona: "Commercial refrigeration specialist", hook: "Hi! Are you still having temperature issues?", close: "I'll dispatch a tech today.", rate: 0.60 },
  { name: "Warehouse Staffing", persona: "Staffing agency account manager", hook: "Hi! Are you still looking to fill warehouse positions?", close: "I'll send over qualified candidates this week.", rate: 0.55 },
  { name: "Fulfillment & 3PL Services", persona: "E-commerce fulfillment consultant", hook: "Hi! Are you still looking for a 3PL partner?", close: "I'll prepare a fulfillment rate sheet today.", rate: 0.60 },
  { name: "Merchant Services & Payments", persona: "Payments solutions advisor", hook: "Hi! Are you still looking to lower your card processing fees?", close: "I'll run a no-obligation rate comparison.", rate: 0.65 },
  { name: "Payroll & HR Services", persona: "Payroll services consultant", hook: "Hi! Are you still looking to streamline payroll and HR?", close: "I'll schedule a free payroll audit.", rate: 0.65 },
  { name: "Fire & Life Safety Inspection", persona: "Fire safety compliance specialist", hook: "Hi! Are you still looking to schedule a fire and life safety inspection?", close: "I'll book your inspection this week.", rate: 0.60 },
  { name: "Commercial Security Systems", persona: "Commercial security consultant", hook: "Hi! Are you still looking to upgrade your surveillance?", close: "I'll prepare a security proposal today.", rate: 0.60 },
  { name: "Parking Lot Maintenance", persona: "Parking lot maintenance coordinator", hook: "Hi! Are you still looking for striping and sealcoating services?", close: "I'll send over a quote this week.", rate: 0.55 },
  { name: "Water Damage Restoration", persona: "Emergency restoration coordinator", hook: "Hi! Is the water damage situation still active?", close: "A restoration crew can be dispatched today.", rate: 0.55 },
  { name: "Mold Remediation", persona: "Mold remediation specialist", hook: "Hi! Are you still looking to get the mold remediated?", close: "I'll schedule a free inspection this week.", rate: 0.60 },
  { name: "Elevator & Escalator Maintenance", persona: "Vertical transportation service manager", hook: "Hi! Are you still looking for an elevator maintenance contract?", close: "I'll prepare a maintenance proposal.", rate: 0.65 },
  { name: "Off-Market Real Estate Acquisition", persona: "Real estate acquisitions specialist", hook: "Hi! Are you still looking to sell your property?", close: "We can make a cash offer this week.", rate: 0.75 },
  { name: "Business Working Capital", persona: "Business funding advisor", hook: "Hi! Are you still looking for working capital?", close: "I'll check today's pre-qualification rates.", rate: 0.70 },
  { name: "Commercial Solar", persona: "Commercial solar development consultant", hook: "Hi! Are you still exploring solar for your facility?", close: "I'll prepare a commercial solar savings model.", rate: 0.65 },
  { name: "Home Warranty Claims", persona: "Home warranty claims coordinator", hook: "Hi! Are you still needing service on your covered system?", close: "I'll escalate your claim for faster service.", rate: 0.50 },
];

async function createLLM(prompt) {
  const r = await fetch(`${RETELL_API}/create-retell-llm`, {
    method: "POST",
    headers: { "Authorization": `Bearer ${RETELL_API_KEY}`, "Content-Type": "application/json" },
    body: JSON.stringify({ model: "gemini-2.0-flash", general_prompt: prompt })
  });
  if (!r.ok) throw new Error(`LLM failed: ${r.status}`);
  return (await r.json()).llm_id;
}

async function createAgent(name, voiceId, llmId) {
  const r = await fetch(`${RETELL_API}/create-agent`, {
    method: "POST",
    headers: { "Authorization": `Bearer ${RETELL_API_KEY}`, "Content-Type": "application/json" },
    body: JSON.stringify({ agent_name: name, voice_id: voiceId, response_engine: { type: "retell-llm", llm_id: llmId } })
  });
  if (!r.ok) throw new Error(`Agent failed: ${r.status}`);
  return (await r.json()).agent_id;
}

serve(async (req) => {
  try {
    const supabase = createClient(Deno.env.get("SUPABASE_URL"), Deno.env.get("SUPABASE_SERVICE_ROLE_KEY"));

    // Pick a random niche
    const niche = NICHES[Math.floor(Math.random() * NICHES.length)];
    const voiceId = VOICE_IDS[Math.floor(Math.random() * VOICE_IDS.length)];

    const prompt = `You are ${niche.persona}. Opening: "${niche.hook}" Closing: "${niche.close}" Be natural, empathetic, and professional.`;

    const llmId = await createLLM(prompt);
    const agentId = await createAgent(`MBM-${niche.name}-${Date.now()}`, voiceId, llmId);

    // Log to Supabase
    await supabase.from("voice_agents").insert({
      niche: niche.name,
      agent_id: agentId,
      llm_id: llmId,
      voice_id: voiceId,
      rate_per_min: niche.rate,
      status: "deployed"
    });

    return new Response(JSON.stringify({ success: true, agent_id: agentId, niche: niche.name }), { status: 200 });
  } catch (e) {
    return new Response(JSON.stringify({ error: e.message }), { status: 500 });
  }
});
