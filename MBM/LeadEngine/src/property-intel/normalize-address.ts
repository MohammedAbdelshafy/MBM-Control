/**
 * Address Normalization — JARVIS Worker 1
 *
 * Deterministic US address normalization for property identity and
 * deduplication. Produces a canonical form plus a stable SHA-256
 * dedupe key: the same raw address always yields the same key, and
 * equivalent spellings ("123 Main Street" vs "123 MAIN ST.") collapse
 * to a single canonical identity.
 *
 * Pure module — no I/O, no framework deps, fully unit-testable.
 */

import crypto from 'node:crypto';

export interface NormalizedAddress {
  /** Canonical street line (number + directional + name + suffix). */
  line1: string;
  /** Canonical secondary designator (unit/suite), null when absent. */
  line2: string | null;
  city: string;
  /** Two-letter uppercase US state. */
  state: string;
  /** 5-digit or ZIP+4. */
  zip: string;
  /** Normalized county, null when absent. */
  county: string | null;
  /** Human-readable full canonical form. */
  full: string;
  /** Deterministic dedupe key — sha256 of canonical components. */
  dedupeKey: string;
  /** Deterministic dedupe key scoped WITH county (county-level dedupe). */
  dedupeKeyWithCounty: string;
}

export interface RawAddressInput {
  line1?: string | null;
  line2?: string | null;
  city?: string | null;
  state?: string | null;
  zip?: string | null;
  county?: string | null;
}

// ── USPS canonical abbreviation maps ─────────────────────────────

const STREET_SUFFIX_MAP: Record<string, string> = {
  alley: 'ALY', ally: 'ALY', anex: 'ANX', annex: 'ANX', arcade: 'ARC',
  avenue: 'AVE', ave: 'AVE', bayou: 'BYU', beach: 'BCH', bend: 'BND',
  bluff: 'BLF', bluffs: 'BLFS', bottom: 'BTM', boulevard: 'BLVD',
  branch: 'BR', bridge: 'BRG', brook: 'BRK', burg: 'BG',
  bypass: 'BYP', camp: 'CP', canyon: 'CYN', cape: 'CPE',
  causeway: 'CSWY', center: 'CTR', centers: 'CTRS', circle: 'CIR',
  circles: 'CIRS', circus: 'CIRC', cliff: 'CLF', club: 'CLB',
  common: 'CMN', corner: 'COR', corners: 'CORS', course: 'CRSE',
  court: 'CT', courts: 'CTS', cove: 'CV', coves: 'CVS',
  creek: 'CRK', crescent: 'CRES', crest: 'CRST', crossing: 'XING',
  crossroad: 'XRD', curve: 'CURV', dale: 'DL', dam: 'DM',
  divide: 'DV', drive: 'DR', drives: 'DRS', estate: 'EST',
  estates: 'ESTS', expressway: 'EXPY', extension: 'EXT',
  extensions: 'EXTS', fall: 'FALL', falls: 'FLS', ferry: 'FRY',
  field: 'FLD', fields: 'FLDS', flat: 'FLT', flats: 'FLTS',
  ford: 'FRD', forest: 'FRST', forge: 'FRG', fork: 'FRK',
  forks: 'FRKS', fort: 'FT', freeway: 'FWY', garden: 'GDN',
  gardens: 'GDNS', gateway: 'GTWY', glen: 'GLN', green: 'GRN',
  greens: 'GRNS', grove: 'GRV', groves: 'GRVS', harbor: 'HBR',
  harbors: 'HBRS', haven: 'HVN', heights: 'HTS', highway: 'HWY',
  hill: 'HL', hills: 'HLS', hollow: 'HOLW', inlet: 'INLT',
  island: 'IS', islands: 'ISS', isle: 'ISLE', junction: 'JCT',
  junctions: 'JCTS', key: 'KY', keys: 'KYS', knoll: 'KNL',
  knolls: 'KNLS', lake: 'LK', lakes: 'LKS', landing: 'LNDG',
  lane: 'LN', light: 'LGT', lights: 'LGTS', loch: 'LCK',
  lodge: 'LDG', loop: 'LOOP', mall: 'MALL', manor: 'MNR',
  manors: 'MNRS', meadow: 'MDW', meadows: 'MDWS', mews: 'MEWS',
  mill: 'ML', mills: 'MLS', mission: 'MSN', motorway: 'MTWY',
  mount: 'MT', mountain: 'MTN', mountains: 'MTNS', neck: 'NCK',
  orchard: 'ORCH', oval: 'OVAL', overpass: 'OPAS', park: 'PARK',
  parks: 'PARK', parkway: 'PKWY', parkways: 'PKWY', pass: 'PASS',
  passage: 'PSGE', path: 'PATH', pike: 'PIKE', pine: 'PNE',
  pines: 'PNES', plain: 'PLN', plains: 'PLNS', plaza: 'PLZ',
  point: 'PT', points: 'PTS', port: 'PRT', ports: 'PRTS',
  prairie: 'PR', radial: 'RADL', ramp: 'RAMP', ranch: 'RNCH',
  rapid: 'RPD', rapids: 'RPDS', rest: 'RST', ridge: 'RDG',
  ridges: 'RDGS', river: 'RIV', road: 'RD', roads: 'RDS',
  route: 'RTE', row: 'ROW', rue: 'RUE', run: 'RUN', shoal: 'SHL',
  shoals: 'SHLS', shore: 'SHR', shores: 'SHRS', skyway: 'SKWY',
  spring: 'SPG', springs: 'SPGS', spur: 'SPUR', spurs: 'SPURS',
  square: 'SQ', squares: 'SQS', station: 'STA', stravenue: 'STRA',
  stream: 'STRM', street: 'ST', streets: 'STS', summit: 'SMT',
  terrace: 'TER', throughway: 'TRWY', trace: 'TRCE', track: 'TRAK',
  trafficway: 'TRFY', trail: 'TRL', trailer: 'TRLR', tunnel: 'TUN',
  turnpike: 'TPKE', underpass: 'UPAS', union: 'UN', unions: 'UNS',
  valley: 'VLY', valleys: 'VLYS', viaduct: 'VIA', view: 'VW',
  views: 'VWS', village: 'VLG', villages: 'VLGS', ville: 'VL',
  vista: 'VIS', walk: 'WALK', walks: 'WALKS', wall: 'WALL',
  way: 'WAY', ways: 'WAYS', well: 'WL', wells: 'WLS',
};

const DIRECTIONAL_MAP: Record<string, string> = {
  north: 'N', south: 'S', east: 'E', west: 'W',
  northeast: 'NE', northwest: 'NW', southeast: 'SE', southwest: 'SW',
};

const UNIT_TOKEN_MAP: Record<string, string> = {
  apt: 'UNIT', apartment: 'UNIT', apartments: 'UNIT', unit: 'UNIT',
  suite: 'UNIT', ste: 'UNIT', '#' : 'UNIT', no: 'UNIT', number: 'UNIT',
  'no.': 'UNIT', bldg: 'UNIT', building: 'UNIT', rm: 'UNIT', room: 'UNIT',
  'po box': 'PO BOX', 'p.o. box': 'PO BOX', 'p o box': 'PO BOX',
  pbox: 'PO BOX', pmb: 'PMB',
};

const US_STATES: Record<string, string> = {
  AL: 'AL', AK: 'AK', AZ: 'AZ', AR: 'AR', CA: 'CA', CO: 'CO', CT: 'CT',
  DE: 'DE', FL: 'FL', GA: 'GA', HI: 'HI', ID: 'ID', IL: 'IL', IN: 'IN',
  IA: 'IA', KS: 'KS', KY: 'KY', LA: 'LA', ME: 'ME', MD: 'MD', MA: 'MA',
  MI: 'MI', MN: 'MN', MS: 'MS', MO: 'MO', MT: 'MT', NE: 'NE', NV: 'NV',
  NH: 'NH', NJ: 'NJ', NM: 'NM', NY: 'NY', NC: 'NC', ND: 'ND', OH: 'OH',
  OK: 'OK', OR: 'OR', PA: 'PA', RI: 'RI', SC: 'SC', SD: 'SD', TN: 'TN',
  TX: 'TX', UT: 'UT', VT: 'VT', VA: 'VA', WA: 'WA', WV: 'WV', WI: 'WI',
  WY: 'WY', DC: 'DC',
  alabama: 'AL', alaska: 'AK', arizona: 'AZ', arkansas: 'AR',
  california: 'CA', colorado: 'CO', connecticut: 'CT', delaware: 'DE',
  florida: 'FL', georgia: 'GA', hawaii: 'HI', idaho: 'ID', illinois: 'IL',
  indiana: 'IN', iowa: 'IA', kansas: 'KS', kentucky: 'KY',
  louisiana: 'LA', maine: 'ME', maryland: 'MD', massachusetts: 'MA',
  michigan: 'MI', minnesota: 'MN', mississippi: 'MS', missouri: 'MO',
  montana: 'MT', nebraska: 'NE', nevada: 'NV', 'new hampshire': 'NH',
  'new jersey': 'NJ', 'new mexico': 'NM', 'new york': 'NY',
  'north carolina': 'NC', 'north dakota': 'ND', ohio: 'OH',
  oklahoma: 'OK', oregon: 'OR', pennsylvania: 'PA', 'rhode island': 'RI',
  'south carolina': 'SC', 'south dakota': 'SD', tennessee: 'TN',
  texas: 'TX', utah: 'UT', vermont: 'VT', virginia: 'VA',
  washington: 'WA', 'west virginia': 'WV', wisconsin: 'WI', wyoming: 'WY',
};

function cleanToken(raw: string): string {
  return raw
    .replace(/[^a-z0-9#-]/gi, '')
    .trim()
    .toLowerCase();
}

function normalizeLine1(line1: string): string {
  const tokens = line1
    .replace(/[^a-zA-Z0-9\s.#-]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .toLowerCase()
    .split(' ');

  const out: string[] = [];
  let i = 0;
  while (i < tokens.length) {
    const token = cleanToken(tokens[i]);
    if (!token) {
      i++;
      continue;
    }

    // "PO BOX 123" — combine p.o. box
    if ((token === 'po' || token === 'p.o' || token === 'p.o.') && i + 1 < tokens.length) {
      const next = cleanToken(tokens[i + 1]);
      if (next === 'box') {
        out.push('PO', 'BOX');
        i += 2;
        continue;
      }
    }

    // "#12" attached unit designator
    if (token.startsWith('#')) {
      out.push('UNIT');
      const unitNumber = token.slice(1);
      if (unitNumber) out.push(unitNumber.toUpperCase());
      i++;
      continue;
    }

    // Directional
    const dir = DIRECTIONAL_MAP[token.replace(/\.$/, '')];
    if (dir) {
      out.push(dir);
      i++;
      continue;
    }

    // Street suffix — expanded when it is the LAST word, OR when the next
    // token is a unit designator (USPS: "1420 Oak Lane Apt 12" → 1420 OAK LN).
    const nextToken = i + 1 < tokens.length ? cleanToken(tokens[i + 1]) : '';
    const nextIsUnit = Boolean(UNIT_TOKEN_MAP[nextToken]) || nextToken.startsWith('#');
    if ((i === tokens.length - 1 || nextIsUnit) && STREET_SUFFIX_MAP[token]) {
      out.push(STREET_SUFFIX_MAP[token]);
      i++;
      continue;
    }

    // Unit designators
    const unitKey = token.replace(/\.$/, '');
    if (UNIT_TOKEN_MAP[unitKey]) {
      const replacement = UNIT_TOKEN_MAP[unitKey];
      if (replacement === 'PO BOX') {
        out.push('PO', 'BOX');
      } else {
        out.push('UNIT');
      }
      i++;
      continue;
    }

    out.push(token.toUpperCase());
    i++;
  }

  return out.join(' ');
}

function normalizeLine2(line2: string | null | undefined): string | null {
  if (!line2) return null;
  const norm = normalizeLine1(line2);
  return norm === '' ? null : norm;
}

export function normalizeState(state: string | null | undefined): string {
  if (!state) return 'XX';
  const key = state.trim().toLowerCase().replace(/[^a-z\s]/g, '');
  return (US_STATES[key] ?? US_STATES[key.replace(/\s+/g, ' ')] ?? state.trim().toUpperCase().slice(0, 2)) || 'XX';
}

export function normalizeZip(zip: string | null | undefined): string {
  if (!zip) return '00000';
  const digits = zip.replace(/\D/g, '');
  if (digits.length >= 9) return `${digits.slice(0, 5)}-${digits.slice(5, 9)}`;
  if (digits.length >= 5) return digits.slice(0, 5);
  return digits.padEnd(5, '0');
}

export function normalizeCity(city: string | null | undefined): string {
  if (!city) return 'UNKNOWN';
  return city.replace(/[^a-zA-Z\s]/g, '').replace(/\s+/g, ' ').trim().toUpperCase() || 'UNKNOWN';
}

export function normalizeCounty(county: string | null | undefined): string | null {
  if (!county) return null;
  const clean = county
    .replace(/\s+/g, ' ')
    .trim()
    .toUpperCase()
    .replace(/\bCOUNTY\b/g, '')
    .replace(/\bPARISH\b/g, '')
    .replace(/\bBOROUGH\b/g, '')
    .replace(/\s+/g, ' ')
    .trim();
  return clean || null;
}

function sha256(input: string): string {
  return crypto.createHash('sha256').update(input).digest('hex');
}

/**
 * Normalize a raw address into canonical components and deterministic keys.
 */
export function normalizeAddress(input: RawAddressInput): NormalizedAddress {
  const line1 = normalizeLine1(input.line1 ?? '');
  const line2 = normalizeLine2(input.line2);
  const city = normalizeCity(input.city);
  const state = normalizeState(input.state);
  const zip = normalizeZip(input.zip);
  const county = normalizeCounty(input.county);

  const coreParts = [line1, line2, city, state, zip].filter(Boolean);
  const full = coreParts.join(', ');

  // Deterministic key WITHOUT county — collapses "Dallas" / "Dallas County"
  // synonyms and allows cross-source dedupe.
  const dedupeKey = sha256(coreParts.join('|'));

  // Deterministic key WITH county — for county-scoped registries.
  const countyKey = county ? [line1, line2, city, state, zip, county].filter(Boolean).join('|') : coreParts.join('|');
  const dedupeKeyWithCounty = sha256(countyKey);

  return { line1, line2, city, state, zip, county, full, dedupeKey, dedupeKeyWithCounty };
}

/**
 * Cheap deterministic key for a possibly-partial address. Used by the
 * rejection ledger so a bad lead can be blocked even when only a phone
 * or parcel is known.
 */
export function canonicalFragmentKey(
  parts: Array<string | null | undefined>,
): string {
  const clean = parts
    .map((p) => (p ?? '').trim())
    .filter(Boolean)
    .map(normalizeFragment)
    .join('|');
  return sha256(clean);
}

/**
 * Normalize a single identity fragment so equivalent spellings collapse:
 *  - US phone ("+1 (214) 555-1234", "2145551234") → 10-digit national form
 *  - parcel/APN and address fragments → uppercase alphanumerics only
 */
function normalizeFragment(part: string): string {
  const digits = part.replace(/\D/g, '');
  if (digits.length >= 10) {
    return digits.length === 11 && digits.startsWith('1') ? digits.slice(1) : digits;
  }
  return part.toUpperCase().replace(/[^A-Z0-9]/g, '');
}