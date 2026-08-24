import sys
sys.path.insert(0, ".")
from clipping_factory._resolve_pd_sources import search_identifiers, _best_file

for t in ["Dementia 13", "Nosferatu", "The Cabinet of Dr. Caligari"]:
    print("====", t)
    toks = [w for w in t.lower().replace("-", " ").replace(".", " ").split() if len(w) > 2]
    for ident in search_identifiers(t)[:10]:
        bf = _best_file(ident, toks)
        if bf:
            print("  %s -> %s (%dMB)" % (ident, bf["file"], bf["size_mb"]))
