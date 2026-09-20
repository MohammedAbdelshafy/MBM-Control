"""Material taxonomy and buyer-search vocabulary for footwear factory waste."""

from __future__ import annotations

MATERIAL_ALIASES: dict[str, set[str]] = {
    "eva_foam": {
        "eva", "eva foam", "ethylene vinyl acetate", "foam", "foam scrap",
        "foam offcut", "eva scrap", "eva waste",
    },
    "rubber": {
        "rubber", "rubber scrap", "rubber waste", "sole rubber", "tpr rubber",
    },
    "pvc_pu": {
        "pvc", "pu", "pvc pu", "pvc/pu", "polyurethane", "pvc scrap", "pu scrap",
        "synthetic pvc", "synthetic leather",
    },
    "textile_mesh": {
        "textile", "fabric", "mesh", "textile waste", "fabric scrap",
        "mesh scrap", "polyester fabric",
    },
    "sole_upper_mixed": {
        "soles", "sole", "uppers", "upper", "shoe components", "mixed footwear",
    },
    "cardboard": {
        "cardboard", "carton", "cartons", "corrugated cardboard", "paperboard",
    },
    "plastic_film": {
        "plastic film", "ldpe film", "poly film", "shrink film", "plastic wrap",
    },
    "finished_defect": {
        "defective shoes", "reject shoes", "finished rejects", "defect pairs",
    },
}

BUYER_CATEGORIES: dict[str, tuple[str, ...]] = {
    "eva_foam": (
        "EVA recycler", "foam granulator", "rubber/plastic compounder",
        "recycled EVA manufacturer", "industrial scrap trader",
    ),
    "rubber": (
        "rubber recycler", "crumb rubber processor", "rubber compounder",
        "industrial scrap trader",
    ),
    "pvc_pu": (
        "PVC recycler", "PU recycler", "polymer compounder",
        "synthetic leather recycler", "industrial scrap trader",
    ),
    "textile_mesh": (
        "textile recycler", "fiber recycler", "nonwoven manufacturer",
        "polyester fiber processor", "industrial textile waste trader",
    ),
    "sole_upper_mixed": (
        "footwear component recycler", "mixed-material recycler",
        "industrial scrap trader",
    ),
    "cardboard": (
        "paper recycler", "cardboard recycler", "packaging waste trader",
    ),
    "plastic_film": (
        "LDPE film recycler", "plastic film recycler", "plastic waste trader",
    ),
    "finished_defect": (
        "secondary footwear materials buyer", "rework/parts buyer",
        "authorized destruction/recycling operator",
    ),
}


def normalize_material(value: str) -> str:
    clean = (
        " ".join(
            value.lower()
            .replace("_", " ")
            .replace("-", " ")
            .replace("/", " ")
            .split()
        )
    )
    for canonical, aliases in MATERIAL_ALIASES.items():
        normalized_aliases = {
            " ".join(
                alias.lower()
                .replace("_", " ")
                .replace("-", " ")
                .replace("/", " ")
                .split()
            )
            for alias in aliases
        }
        if clean == canonical.replace("_", " ") or clean in normalized_aliases:
            return canonical
    return clean


def buyer_categories_for(material: str) -> tuple[str, ...]:
    return BUYER_CATEGORIES.get(
        normalize_material(material),
        ("industrial recycler", "industrial scrap trader"),
    )
