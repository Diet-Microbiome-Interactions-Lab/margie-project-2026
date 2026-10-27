"""Shared descriptor rules for labeling, C1 and C3.

is_uninformative() says whether a description names no function;
hit_is_informative() says whether a tool's chosen hit, as labeled-genes.tsv
records it, counts: its own description (not the accession standing in for a
missing one) that names a function, and for UniProt an identity of at least
UNIPROT_PIDENT_MIN. assign-canonical-label.py, scoring/score-c1-tool-coverage.py
and scoring/c3_lib.py import these, so the three agree. Not run directly.
"""
from __future__ import annotations

import re

# Group 1 — exact null / boilerplate tokens.
UNINFORMATIVE = frozenset({
    "", "-", ".", "na", "n/a", "none", "null",
    "unknown", "uncharacterized", "uncharacterised", "putative", "predicted",
    "hypothetical protein",
    "conserved hypothetical protein",
    "conserved protein",
    "conserved domain protein",
    "predicted protein",
    "function unknown",
    "domain of unknown function",
    "general function prediction only",
    "poorly characterized",
    "open reading frame",
})
# Null tokens: a hit with one of these has no description of its own.
NULLISH = frozenset({"", "-", ".", "na", "n/a", "none", "null"})

# Group 2 — leading-phrase families (unknown-function nouns, DUF/UPF, ORF, …).
UNINFORMATIVE_PREFIXES = (
    "domain of unknown function",
    "protein of unknown function",
    "family of unknown function",
    "region of unknown function",
    "repeat of unknown function",
    "module of unknown function",
    "uncharacteri",
    "putative uncharacteri",
    "conserved hypothetical",
    "hypothetical",
    "unknown protein",
    "unknown function",
    "pfam uncharacteri",
)
# Group 2 tags as whole words: "DUF167 family protein", "UPF0145 protein", "ORF1", "orf_12",
# and not "Orfamide synthetase".
_TAG_PREFIX_RE = re.compile(r'^(?:duf|upf|orf)(?:_?\d+[a-z]?)?\b', re.IGNORECASE)
# Group 9 — an accession and nothing else: an eggNOG seed ortholog (taxid.locus, "504832.OCAR_7106")
# or a database accession ("K00845", "COG0001", "PF00001.21", "TIGR00001", "NF000001.1",
# "IPR000001", "MF_00001", "PIRSF000001", "cd00001", "WP_000001.1", "FIG00001", "GO:0000001",
# a UniProt accession). A bare EC number ("1.1.1.1") is not one.
_ACCESSION_ONLY_RE = re.compile(
    r'^(?:\d+\.(?=[\w.\-]*[a-z])[\w.\-]+'
    r'|k\d{5}|cog\d{4}|arcog\d{5}|enog\w+|pf\d{5}|tigr\d{5}|nf\d{6}|ipr\d{6}|mf_\d{5}|pirsf\d{6}'
    r'|(?:cd|cl|sm)\d{5}|smart\d{5}|[anwxyz]p_\d+|fig\d+|go:\d{7}'
    r'|[opq]\d[a-z0-9]{3}\d|[a-nr-z]\d(?:[a-z][a-z0-9]{2}\d){1,2})(?:\.\d+)?$',
    re.IGNORECASE,
)

_UNKNOWN_FUNC_RE = re.compile(
    r'^\s*(?:(?:bacterial|viral|archaeal|eukaryotic|fungal|plant|marine|'
    r'transmembrane|integral membrane|membrane)\s+)?'
    r'(?:domain|protein|family|repeat|region|module)\s+of\s+unknown\s+function',
    re.IGNORECASE,
)
# Group 8 — DB-id-prefixed hypothetical ("FIG####: … hypothetical").
_DB_ID_HYPOTHETICAL_RE = re.compile(
    r'^(?:fig\d+|tigr\d+)[:\s].*(?:hypothetical|conserved hypothetical)', re.IGNORECASE,
)
# Group 4 — eggNOG "Belongs to the UPF#### family" (Uncharacterized Protein Family).
_UPF_ONLY_RE = re.compile(r'^\s*belongs to the upf\d+', re.IGNORECASE)
# eggNOG "Psort location ..." descriptions give localisation only, not a product.
_PSORT_ONLY_RE = re.compile(r'^\s*psort location\b', re.IGNORECASE)
# Group 5 — a description that is nothing but a DUF tag ("Pfam:DUF955", "DUF955 family").
_BARE_DUF_RE = re.compile(r'^\s*(?:pfam:)?\(?duf\d+\)?(?:\s+(?:family|domain))?\s*$', re.IGNORECASE)
# Group 6 — "protein containing domains DUF###" (RAST multi-DUF stubs).
_PROTEIN_DOMAINS_DUF_RE = re.compile(r'^\s*protein containing domains?\s+duf', re.IGNORECASE)
_HYPOTHETICAL_ANYWHERE_RE = re.compile(r'\bhypothetical\b', re.IGNORECASE)
_PROTEIN_CONSERVED_IN_BACTERIA_RE = re.compile(r'\bprotein\s+conserved\s+in\s+bacteria\b', re.IGNORECASE)
_INTEGRAL_MEMBRANE_PROTEIN_RE = re.compile(r'^\s*integral\s+membrane\s+protein\s*$', re.IGNORECASE)
# Function-word guard for Groups 3 & 7 (activity words, not location words).
_FUNCTION_SIGNAL_RE = re.compile(
    r'(ase\b|transport|permease|pump|export|import|channel|carrier|symport|antiport|'
    r'bind|synth|kinas|reductas|hydrolas|transferas|isomeras|ligas|lyas|mutas|oxidas|'
    r'dehydrogen|regulat|repressor|activator|\bfactor\b|receptor|sensor|subunit|ribosom|'
    r'polymeras|oxidoreduct|enzyme|proteas|peptidas|nucleas|phosphatas|efflux|resistance|'
    r'virulence|toxin|flippase|homeostasis|assembly|motility|adhesin|chaperone|'
    r'helicas|topoisomeras|gyrase|recombinas|integras|transposas|methylas|glycosyl|'
    r'dismutas|catalas|peroxidas|cytochrome|ferredoxin|cytoskelet|cell division|'
    r'degradation|tolerance|translation|utilization)', re.IGNORECASE,
)
_UNCHARACTERIZED_RE = re.compile(r'\buncharacteri[sz]ed\b', re.IGNORECASE)
# Group 7 helper: a bare locus tag or DUF/UPF tag after "conserved protein".
_LOCUS_OR_TAG_RE = re.compile(r'^\(?(?:duf\d+|upf\d+|[a-z]{1,5}\d{0,4}[a-z]?\d{0,4})\)?$', re.IGNORECASE)


# Leading source tags ("JCVI: ", "NCBI Protein Cluster (PRK): ", "FIG00001: "), which the rules
# look past; the reported descriptor keeps them.
SOURCE_TAG_RE = re.compile(
    r'^(?:'
    r'JCVI|NCBIFAM|NCBI Protein Cluster \(PRK\)|PRK|TIGR|TIGRFAM|PGAP|HAMAP|'
    r'PIRSF|UniProt|UNIPROT|KEGG|EGGNOG|eggNOG|PFAM|Pfam|CDD|COG|RAST|MEROPS|'
    r'TCDB|DBCAN|SwissProt|FIG\d+'
    r')\s*:\s*',
    re.IGNORECASE,
)


def strip_source_tags(desc: str) -> str:
    """Returns the description without its leading SOURCE: tags, removed until none remain (regex)."""
    d = (desc or "").strip()
    prev = None
    while prev != d:
        prev = d
        d = SOURCE_TAG_RE.sub("", d).strip()
    return d


def is_uninformative(val: str) -> bool:
    """Returns True when a description names no function, using the word lists and regexes above.

    Leading source tags are stripped first, so "JCVI: DUF167 family protein" is a DUF.
    """
    v = strip_source_tags(val).lower()
    # Group 1
    if not v or v in UNINFORMATIVE:
        return True
    # Group 2
    for prefix in UNINFORMATIVE_PREFIXES:
        if v.startswith(prefix):
            return True
    if _TAG_PREFIX_RE.match(v) or _ACCESSION_ONLY_RE.match(v):
        return True
    # Groups 8, 4, 5, 6
    if (_UNKNOWN_FUNC_RE.match(v) or _DB_ID_HYPOTHETICAL_RE.match(v)
            or _UPF_ONLY_RE.match(v) or _PSORT_ONLY_RE.match(v) or _BARE_DUF_RE.match(v)
            or _HYPOTHETICAL_ANYWHERE_RE.search(v)
            or _PROTEIN_CONSERVED_IN_BACTERIA_RE.search(v)
            or _INTEGRAL_MEMBRANE_PROTEIN_RE.match(v)
            or _PROTEIN_DOMAINS_DUF_RE.match(v)):
        return True
    # Groups 3 & 7 — unknown-function markers without a function word.
    if not _FUNCTION_SIGNAL_RE.search(v):
        if "of unknown function" in v:
            return True
        if _UNCHARACTERIZED_RE.search(v):
            return True
        if v.startswith("conserved protein"):
            rest = v[len("conserved protein"):].strip(" ,.;:-")
            if not rest or _BARE_DUF_RE.match(rest) or _LOCUS_OR_TAG_RE.match(rest):
                return True
    return False


# ─── Tool gates ───────────────────────────────────────────────────────────────
# UniProt hits count at identity >= 40%; the other tools are thresholded upstream.
UNIPROT_PIDENT_MIN = 40.0


def _to_float(s, default: float) -> float:
    """Returns float(s), or default when it cannot be parsed."""
    try:
        return float(s)
    except (TypeError, ValueError):
        return default


def uniprot_gate_passed(stat) -> bool:
    """Returns True when a UniProt identity is unavailable or at least UNIPROT_PIDENT_MIN."""
    pident = _to_float(stat, -1.0)
    return pident < 0 or pident >= UNIPROT_PIDENT_MIN


def has_own_description(hit_id: str, description: str) -> bool:
    """Returns True when a hit's description is its own: not a null token and not the hit's accession."""
    desc = (description or "").strip()
    if desc.lower() in NULLISH:
        return False
    return not (hit_id and desc == hit_id.strip())


def names_a_protein(hit_id: str, description: str) -> bool:
    """Returns True when a description is the hit's own and is neither an accession nor a
    localisation-only text ("Psort location ..."); "hypothetical protein" names one."""
    if not has_own_description(hit_id, description):
        return False
    v = strip_source_tags(description).lower()
    return bool(v) and not (_ACCESSION_ONLY_RE.match(v) or _PSORT_ONLY_RE.match(v))


def hit_is_informative(tool_name: str, hit_id: str, description: str, stat: str = "") -> bool:
    """Returns True when a tool's chosen hit counts as informative evidence.

    Its description is its own (has_own_description), names a function
    (is_uninformative is False), and for UNIPROT the identity passes
    uniprot_gate_passed(). This is labeling's first-pass test without PFAM's
    keep-anyway exception.
    """
    if not has_own_description(hit_id, description) or is_uninformative(description):
        return False
    return tool_name != "UNIPROT" or uniprot_gate_passed(stat)
