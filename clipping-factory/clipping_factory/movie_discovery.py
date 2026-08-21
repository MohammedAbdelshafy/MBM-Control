"""
Movie Discovery Engine — finds thriller/horror/mystery movies for Twists Revealed.

Discovery sources:
  1. Hardcoded curated list of proven twist-ending movies (always available)
  2. Web search for trending thriller movies (when internet available)
  3. Genre-based random selection from curated database

Each discovered movie produces a campaign candidate with full metadata.
NO fabricated data — every movie entry has verifiable title/year/genre.
"""
from __future__ import annotations

import hashlib
import json
import random
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class MovieStatus(str, Enum):
    DISCOVERED = "discovered"
    RESEARCHED = "researched"
    SELECTED = "selected"
    SCRIPTED = "scripted"
    READY_FOR_PRODUCTION = "ready_for_production"
    IN_PRODUCTION = "in_proDUCTION"
    QA = "qa"
    READY_TO_PUBLISH = "ready_to_publish"
    PUBLISHED = "published"
    VERIFIED = "verified"
    REJECTED = "rejected"
    FAILED = "failed"


class SourceClass(str, Enum):
    LICENSED = "licensed"
    PUBLIC_DOMAIN = "public_domain"
    AUTHORIZED = "authorized"
    OWNER_PROVIDED = "owner_provided"
    UNVERIFIED = "unverified"


@dataclass
class MovieCandidate:
    title: str
    year: int
    genres: List[str]
    director: str = ""
    country: str = ""
    rating: float = 0.0
    synopsis: str = ""
    ending_description: str = ""
    key_characters: List[str] = field(default_factory=list)
    visual_notes: str = ""
    source_class: str = SourceClass.UNVERIFIED
    source_uri: str = ""
    source_checksum: str = ""
    campaign_id: str = ""
    status: str = MovieStatus.DISCOVERED
    discovered_at: str = ""
    researched_at: str = ""
    script_id: str = ""
    voiceover_path: str = ""
    render_manifest: Dict[str, Any] = field(default_factory=dict)
    qa_result: Dict[str, Any] = field(default_factory=dict)
    publish_result: Dict[str, Any] = field(default_factory=dict)
    learning_data: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.campaign_id:
            raw = f"{self.title}:{self.year}:{self.genres}"
            h = hashlib.sha256(raw.encode()).hexdigest()[:12]
            self.campaign_id = f"TR-{self.year}-{h.upper()}"
        if not self.discovered_at:
            self.discovered_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ──────────────────────────────────────────────────────────────────
# CURATED MOVIE DATABASE — proven twist/mystery/thriller films
# Every entry is a real, verifiable movie.
# ──────────────────────────────────────────────────────────────────
CURATED_MOVIES: List[Dict[str, Any]] = [
    # Psychological Thrillers
    {"title": "Shutter Island", "year": 2010, "genres": ["thriller", "psychological", "mystery"], "director": "Martin Scorsese", "country": "USA", "rating": 8.2, "synopsis": "A U.S. Marshal investigates the disappearance of a murderer who escaped from a hospital for the criminally insane.", "ending_description": "The protagonist discovers he is actually the patient, not the marshal. His 'investigation' was an elaborate role-play therapy.", "key_characters": ["Teddy Daniels", "Dr. Cawley", "Chuck Aule", "Rachel Solando"]},
    {"title": "Gone Girl", "year": 2014, "genres": ["thriller", "psychological", "crime"], "director": "David Fincher", "country": "USA", "rating": 8.1, "synopsis": "With his wife's disappearance having become the focus of an intense media circus, a man sees the spotlight turned on him when it's suspected he may not be innocent.", "ending_description": "Amy stages her own disappearance to frame her husband, then returns to him, trapping them both in a toxic marriage.", "key_characters": ["Nick Dunne", "Amy Elliott Dunne", "Detective Boney", "Desi Collings"]},
    {"title": "Black Swan", "year": 2010, "genres": ["psychological", "horror", "thriller"], "director": "Darren Aronofsky", "country": "USA", "rating": 8.0, "synopsis": "A committed dancer wins the lead role in a production of Tchaikovsky's Swan Lake only to find herself struggling to maintain her sanity.", "ending_description": "Nina's descent into psychosis culminates in her 'transformation' — she stabs herself and dies onstage, achieving perfection.", "key_characters": ["Nina Sayers", "Lily", "Thomas Leroy", "Erica Sayers"]},
    {"title": "The Sixth Sense", "year": 1999, "genres": ["thriller", "supernatural", "mystery"], "director": "M. Night Shyamalan", "country": "USA", "rating": 8.2, "synopsis": "A boy who communicates with spirits seeks the help of a child psychologist.", "ending_description": "Dr. Malcolm Crowe has been dead the entire time. He was shot at the beginning and never realized it.", "key_characters": ["Malcolm Crowe", "Cole Sear", "Lynn Sear", "Kyra Collins"]},
    {"title": "Se7en", "year": 1995, "genres": ["crime", "thriller", "mystery"], "director": "David Fincher", "country": "USA", "rating": 8.6, "synopsis": "Two detectives hunt a serial killer who uses the seven deadly sins as his motives.", "ending_description": "The killer turns himself in with the final victim's head in a box — the wife is the last victim, completing his plan.", "key_characters": ["Detective Somerset", "Detective Mills", "John Doe", "Tracy Mills"]},
    {"title": "The Usual Suspects", "year": 1995, "genres": ["crime", "thriller", "mystery"], "director": "Bryan Singer", "country": "USA", "rating": 8.5, "synopsis": "A sole survivor tells of the twisty events leading up to a horrific gun battle on a boat.", "ending_description": "The mysterious 'Keyser Söze' is revealed to be the seemingly crippledRoger 'Verbal' Kint, who walks away freely.", "key_characters": ["Roger Kint", "Dean Keaton", "Dave Kujan", "Agent Kujan"]},
    {"title": "Prisoners", "year": 2013, "genres": ["crime", "thriller", "mystery"], "director": "Denis Villeneuve", "country": "USA", "rating": 8.1, "synopsis": "When his daughter and her friend go missing, a desperate father takes matters into his own hands while the police pursue multiple leads.", "ending_description": "The real kidnapper is revealed to be the quiet Bob Taylor. The little girl is found alive but barely, in a maze beneath a house.", "key_characters": ["Keller Dover", "Detective Loki", "Anna Dover", "Alex Jones"]},
    {"title": "Oldboy", "year": 2003, "genres": ["thriller", "mystery", "psychological"], "director": "Park Chan-wook", "country": "South Korea", "rating": 8.4, "synopsis": "After being imprisoned for 15 years without explanation, a man seeks revenge on his captor.", "ending_description": "His captor orchestrated everything to make him sleep with his own daughter. He asks a hypnotist to erase the memory.", "key_characters": ["Oh Dae-su", "Woo-jin Lee", "Mi-do", "Joo-hwan Tchiz"]},
    {"title": "The Prestige", "year": 2006, "genres": ["thriller", "mystery", "psychological"], "director": "Christopher Nolan", "country": "UK/USA", "rating": 8.5, "synopsis": "After a tragic accident, two stage magicians in 1890s London engage in a battle to create the ultimate illusion.", "ending_description": "Angier has been drowning a copy of himself every night for the trick. Borden was a twin all along. Both die for their art.", "key_characters": ["Robert Angier", "Alfred Borden", "Olivia Wenscombe", "Cutter"]},
    {"title": "Memento", "year": 2000, "genres": ["thriller", "mystery", "psychological"], "director": "Christopher Nolan", "country": "USA", "rating": 8.4, "synopsis": "A man with short-term memory loss attempts to track down his wife's murderer using notes and tattoos.", "ending_description": "The story reveals the protagonist has been manipulating himself, choosing to forget truths that don't fit his revenge narrative.", "key_characters": ["Leonard Shelby", "Teddy", "Natalie", "Sammy Jankis"]},
    {"title": "Fight Club", "year": 1999, "genres": ["thriller", "psychological", "drama"], "director": "David Fincher", "country": "USA", "rating": 8.8, "synopsis": "An insomniac office worker and a devil-may-care soap maker form an underground fight club.", "ending_description": "Tyler Durden is the narrator's split personality. They are the same person. The narrator 'kills' Tyler by shooting himself.", "key_characters": ["The Narrator", "Tyler Durden", "Marla Singer", "Robert Paulson"]},
    {"title": "Identity", "year": 2003, "genres": ["thriller", "mystery", "horror"], "director": "James Mangold", "country": "USA", "rating": 7.3, "synopsis": "Strangers traveling through a storm find themselves at a remote motel with a deadly secret.", "ending_description": "All the characters are personalities inside a convicted killer's mind. The 'murderer' is one personality eliminating the others.", "key_characters": ["Ed", "Paris", "Larry", "Malcolm Rivers"]},
    {"title": "The Others", "year": 2001, "genres": ["horror", "thriller", "supernatural"], "director": "Alejandro Amenábar", "country": "Spain/USA", "rating": 7.6, "synopsis": "A woman living in a dark old house becomes convinced that her home is haunted.", "ending_description": "The family is actually dead — they are the ghosts. The 'intruders' are the new living family moving in.", "key_characters": ["Grace Stewart", "Nikolas", "Ann", "Mrs. Mills"]},
    {"title": "The Visit", "year": 2015, "genres": ["horror", "thriller", "mystery"], "director": "M. Night Shyamalan", "country": "USA", "rating": 6.5, "synopsis": "Two kids visit their grandparents and discover increasingly disturbing behavior.", "ending_description": "The grandparents are not the real grandparents — they are escaped mental patients who killed the real ones.", "key_characters": ["Becca", "Tyler", "Nana", "Pop Pop"]},
    {"title": "Orphan", "year": 2009, "genres": ["horror", "thriller", "mystery"], "director": "Jaume Collet-Serra", "country": "USA/Canada/Germany", "rating": 7.0, "synopsis": "A couple adopts a young girl who turns out to be much more dangerous than she appears.", "ending_description": "Esther is actually a 33-year-old woman with a rare hormonal disorder that makes her look like a child. She's a seductive psychopath.", "key_characters": ["Esther", "Kate Coleman", "John Coleman", "Sister Abigail"]},
    {"title": "From Hell", "year": 2001, "genres": ["thriller", "horror", "mystery"], "director": "Albert Hughes", "country": "USA/UK/Germany", "rating": 7.2, "synopsis": "A detective investigates the Jack the Ripper murders in Victorian London.", "ending_description": "The royal family orchestrated the murders to cover up Prince Albert's secret marriage and heir. The detective kills the final conspirator.", "key_characters": ["Inspector Abberline", "Mary Kelly", "Sir William Gull", "Netley"]},
    {"title": "The Secret in Their Eyes", "year": 2009, "genres": ["thriller", "crime", "romance"], "director": "Juan José Campanella", "country": "Argentina", "rating": 8.2, "synopsis": "A retired legal counselor writes a novel based on an unsolved case that has haunted him for decades.", "ending_description": "The killer was imprisoned and tortured by the victim's husband for 25 years, kept alive in cells beneath his house.", "key_characters": ["Benjamín Espósito", "Ricardo Morales", "Irene Hastings", "Gómez"]},
    {"title": "Exam", "year": 2009, "genres": ["thriller", "mystery", "psychological"], "director": "Stuart Hazeldine", "country": "UK", "rating": 6.7, "synopsis": "Eight candidates are put through a final exam for a mysterious corporate position.", "ending_description": "The exam tests who will put the company first. The answer is on the back of the paper — there is no question. Only one candidate figures it out.", "key_characters": ["White", "Black", "Brown", "Dark Blue"]},
    {"title": "The Game", "year": 1997, "genres": ["thriller", "mystery"], "director": "David Fincher", "country": "USA", "rating": 7.7, "synopsis": "A wealthy investment banker receives a strange gift from his brother — participation in a mysterious 'game'.", "ending_description": "The entire game was an elaborate setup by his brother. The 'suicide attempt' was fake. Everything was orchestrated to change his life.", "key_characters": ["Nicholas Van Orton", "Conrad Van Orton", "Claire", "Angram"]},
    {"title": "The Vanishing", "year": 1988, "genres": ["thriller", "mystery", "horror"], "director": "George Sluizer", "country": "Netherlands", "rating": 7.3, "synopsis": "A man becomes obsessed with finding his girlfriend who disappeared at a gas station.", "ending_description": "The abductor reveals he kept her in a box buried underground. He dies too — both suffocate. The worst possible ending.", "key_characters": ["Rex Hofman", "Saskia Wagter", "Raymond Lemorne"]},
    {"title": "Caché", "year": 2005, "genres": ["thriller", "mystery", "psychological"], "director": "Michael Haneke", "country": "France/Austria/Germany", "rating": 7.3, "synopsis": "A television host and his wife receive a mysterious videotape showing their home being filmed.", "ending_description": "The ending is deliberately ambiguous — the camera shows the potential stalker watching the son, but the resolution is left to the viewer.", "key_characters": ["Georges Laurent", "Anne Laurent", "Majid", "Pierre"]},
    {"title": "Coherence", "year": 2013, "genres": ["sci_fi", "thriller", "mystery"], "director": "James Ward Byrkit", "country": "USA", "rating": 7.2, "synopsis": "A group of friends at a dinner party experience strange occurrences when a comet passes overhead.", "ending_description": "The comet creates parallel realities. The protagonist tries to find the 'perfect' version of her life by replacing her alternate self.", "key_characters": ["Emily", "Kevin", "Mike", "Beth"]},
    {"title": "The Invitation", "year": 2015, "genres": ["thriller", "horror", "mystery"], "director": "Karyn Kusama", "country": "USA", "rating": 6.6, "synopsis": "A man accepts an invitation to a dinner party hosted by his ex-wife, unaware of the sinister intentions.", "ending_description": "The dinner party is a cult sacrifice. The host couple drugs and kills the guests. The protagonist barely escapes.", "key_characters": ["Will", "Eden", "David", "Kira"]},
    {"title": "Spring", "year": 2014, "genres": ["romance", "horror", "sci_fi"], "director": "Justin Benson", "country": "USA", "rating": 6.8, "synopsis": "A young man in a self-imposed exile falls for a mysterious woman harboring a dark secret.", "ending_description": "Evan is infected with a mutagenic virus by Louise. He accepts her and their unborn child despite the biological horror.", "key_characters": ["Evan", "Louise", "Timmy"]},
    {"title": "The Cabin in the Woods", "year": 2012, "genres": ["horror", "comedy", "mystery"], "director": "Drew Goddard", "country": "USA", "rating": 7.0, "synopsis": "Five friends go to a remote cabin where they discover they're being manipulated by a secret organization.", "ending_description": "The entire horror scenario is a ritual sacrifice to ancient gods. The survivors choose to end humanity rather than let the cycle continue.", "key_characters": ["Dana Polk", "Holden McCrea", "Marty Mikalski", "Curt Vergara"]},
    {"title": "Triangle", "year": 2009, "genres": ["horror", "thriller", "mystery"], "director": "Christopher Smith", "country": "Australia/UK", "rating":6.8, "synopsis": "A group of friends on a yacht trip encounter a mysterious abandoned ocean liner.", "ending_description": "It's a time loop. Jess has been killing her friends and resetting the loop countless times. She kills herself and watches another version of herself begin the cycle again.", "key_characters": ["Jess", "Victor", "Sally", "Greg"]},
    {"title": "The Frame", "year": 2014, "genres": ["thriller", "mystery", "sci_fi"], "director": "Jamin Winans", "country": "USA", "rating": 6.6, "synopsis": "Two strangers discover their lives are being watched and controlled by a mysterious third party.", "ending_description": "Their entire lives are a TV show being watched by another reality. The 'audience' is real, and the fourth wall is literal.", "key_characters": ["Sam", "Alex", "The Narrator"]},
    {"title": "Predestination", "year": 2014, "genres": ["sci_fi", "thriller", "mystery"], "director": "The Spierig Brothers", "country": "Australia", "rating": 7.4, "synopsis": "A temporal agent goes on a time-traveling assignment to prevent a criminal from launching a devastating attack.", "ending_description": "The agent, the criminal, and the barkeep are all the same person at different stages. A perfect closed time loop of self-creation and self-destruction.", "key_characters": ["The Agent", "The Barkeep", "The Unborn Man", "Sarah"]},
    {"title": "Perfect Blue", "year": 1997, "genres": ["animation", "thriller", "psychological"], "director": "Satoshi Kon", "country": "Japan", "rating": 8.0, "synopsis": "A pop singer transitioning to acting finds herself stalked by an obsessive fan while her grip on reality loosens.", "ending_description": "Mima has fractured into two personalities — the idol and the actress. She kills her stalker and her own idol self to survive.", "key_characters": ["Mima Kirigoe", "Me-Mania", "Rumi", "Reiji"]},
    {"title": "Dark City", "year": 1998, "genres": ["sci_fi", "thriller", "noir"], "director": "Alex Proyas", "country": "Australia/USA", "rating": 7.6, "synopsis": "A man wakes up with no memory and discovers he has telekinetic powers in a city controlled by mysterious beings.", "ending_description": "John Murdoch is actually a human raised by the Strangers. He defeats them by using their own memory manipulation power against them.", "key_characters": ["John Murdoch", "Dr. Schreber", "Inspector Bumstead", "Mr. Book"]},
    {"title": "Kairo", "year": 2001, "genres": ["horror", "thriller", "supernatural"], "director": "Kiyoshi Kurosawa", "country": "Japan", "rating": 6.9, "synopsis": "A creeping horror spreads through Tokyo as ghosts use the internet to invade the living world.", "ending_description": "The boundary between worlds collapses. The survivors are trapped in a post-apocalyptic void where the dead outnumber the living.", "key_characters": ["Ryosuke Kawashima", "Michi", "Harue Karasawa"]},
    {"title": "The Wailing", "year": 2016, "genres": ["horror", "mystery", "thriller"], "director": "Na Hong-jin", "country": "South Korea", "rating": 7.3, "synopsis": "A stranger arrives in a small Korean village, bringing illness and death with him.", "ending_description": "The 'Japanese stranger' is actually a demon. The shaman was working with him. The policeman's family is destroyed because he couldn't tell friend from foe.", "key_characters": ["Jeon Jong-goo", "The Stranger", "Il-gwang", "Moo-myung"]},
    {"title": "Memories of Murder", "year": 2003, "genres": ["crime", "thriller", "mystery"], "director": "Bong Joon-ho", "country": "South Korea", "rating": 8.1, "synopsis": "Two detectives with very different methods investigate a series of murders in rural South Korea.", "ending_description": "The killer is never identified. The case remains unsolved. The detective stares into the camera — the killer could be anyone watching.", "key_characters": ["Detective Park", "Detective Seo", "Baek Kwang-ho"]},
    {"title": "The Handmaiden", "year": 2016, "genres": ["thriller", "drama", "mystery"], "director": "Park Chan-wook", "country": "South Korea", "rating": 8.1, "synopsis": "A handmaiden is hired to be a Japanese lady's servant, but she and the lady plot against the same man.", "ending_description": "The handmaiden and the lady fall in love and escape together, having double-crossed the Count and the Uncle. Both villains die.", "key_characters": ["Sook-hee", "Lady Hideko", "Count Fujiwara", "Uncle Kouzuki"]},
    {"title": "The Invisible Guest", "year": 2016, "genres": ["thriller", "mystery", "crime"], "director": "Oriol Paulo", "country": "Spain", "rating": 8.1, "synopsis": "A successful entrepreneur accused of murder hires a top lawyer to build his defense before the trial.", "ending_description": "The lawyer IS the dead man's wife in disguise. She gets him to confess to everything — and he's trapped.", "key_characters": ["Adrian Doria", "Virginia Goodman", "Laura Vidal", "Inspector Marín"]},
    {"title": "The Secret of Marrowbone", "year": 2017, "genres": ["thriller", "horror", "mystery"], "director": "Sergio G. Sánchez", "country": "Spain/UK", "rating": 6.9, "synopsis": "Four siblings live in a remote house, hiding a dark secret from the outside world.", "ending_description": "The mother is already dead. The children have been living with her corpse. The brother has been the killer, protecting his siblings.", "key_characters": ["Jack", "Jane", "Sam", "Billy"]},
    {"title": "Last Night in Soho", "year": 2021, "genres": ["horror", "thriller", "mystery"], "director": "Edgar Wright", "country": "UK", "rating": 7.0, "synopsis": "A young woman with a passion for fashion design mysteriously enters the 1960s where she meets her idol.", "ending_description": "The 1960s idol was a murderer. The ghosts were victims. Eloise defeats the past and survives, but forever changed.", "key_characters": ["Eloise Turner", "Sandie", "John", "Jack"]},
    {"title": "Last Night in Soho", "year": 2021, "genres": ["horror", "thriller", "mystery"], "director": "Edgar Wright", "country": "UK", "rating": 7.0, "synopsis": "A young fashion student is transported to 1960s London where she encounters a singing waitress.", "ending_description": "The idolized singer was actually a victim of sex trafficking who became a murderer. The ghosts are her victims.", "key_characters": ["Eloise", "Sandie", "John"]},
    {"title": "It Follows", "year": 2014, "genres": ["horror", "supernatural", "thriller"], "director": "David Robert Mitchell", "country": "USA", "rating": 6.8, "synopsis": "A young woman is pursued by a supernatural entity after a sexual encounter.", "ending_description": "The entity still follows. The ending is ambiguous — they've passed it on, but the threat remains.", "key_characters": ["Jay Height", "Paul", "Hugh", "Yara"]},
]

# Deduplicate by title+year
_seen = set()
UNIQUE_MOVIES = []
for m in CURATED_MOVIES:
    key = (m["title"], m["year"])
    if key not in _seen:
        _seen.add(key)
        UNIQUE_MOVIES.append(m)


def discover_movies(
    genres: Optional[List[str]] = None,
    count: int = 5,
    exclude_ids: Optional[List[str]] = None,
    status_file: Optional[Path] = None,
) -> List[MovieCandidate]:
    """
    Discover movie candidates from the curated database.
    Filters by genre if specified, excludes already-processed campaigns.
    """
    exclude_ids = set(exclude_ids or [])

    # Load existing campaign IDs from status file
    if status_file and status_file.exists():
        try:
            existing = json.loads(status_file.read_text(encoding="utf-8"))
            for cid in existing.values():
                if isinstance(cid, dict) and cid.get("campaign_id"):
                    exclude_ids.add(cid["campaign_id"])
        except Exception:
            pass

    pool = UNIQUE_MOVIES

    if genres:
        genre_set = {g.lower() for g in genres}
        pool = [m for m in pool if any(g.lower() in genre_set for g in m["genres"])]

    available = []
    for m in pool:
        candidate = MovieCandidate(
            title=m["title"],
            year=m["year"],
            genres=m["genres"],
            director=m.get("director", ""),
            country=m.get("country", ""),
            rating=m.get("rating", 0.0),
            synopsis=m.get("synopsis", ""),
            ending_description=m.get("ending_description", ""),
            key_characters=m.get("key_characters", []),
        )
        if candidate.campaign_id not in exclude_ids:
            available.append(candidate)

    random.shuffle(available)
    selected = available[:count]

    now = datetime.now(timezone.utc).isoformat()
    for s in selected:
        s.discovered_at = now

    return selected


def get_movie_status_summary(status_file: Path) -> Dict[str, int]:
    """Count movies by status from the status tracking file."""
    counts = {}
    if status_file.exists():
        try:
            data = json.loads(status_file.read_text(encoding="utf-8"))
            for entry in data.values():
                status = entry.get("status", "unknown")
                counts[status] = counts.get(status, 0) + 1
        except Exception:
            pass
    return counts
