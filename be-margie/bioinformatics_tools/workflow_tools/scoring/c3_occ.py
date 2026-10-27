"""c3_occ.py - Operon Context Confidence (OCC) engine.

Scores how well a gene's operon neighbourhood is conserved across genomes, from
pan-genome co-occurrence of clean descriptors in qualifying operons (informative
members outnumber uninformative ones). The reference holds additive counts and
each genome's own contribution, so a genome is subtracted (leave-one-out) or
replaced exactly; finalize_reference() derives per-pair reliabilities before scoring.
"""
import csv
import os
import re
import secrets
import stat
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy.stats import beta as _beta

csv.field_size_limit(10_000_000)

DEFAULTS = dict(
    delta=0.05,          # Jeffreys lower-bound quantile
    lam=1.0,             # enrichment saturation constant
    use_enrichment=True,  # apply the by-chance safeguard w
    link_floor=0.0,      # ignore links with rho below this (0 = keep all)
)


def _norm(d):
    """Returns the descriptor stripped and lower-cased."""
    return (d or "").strip().lower()


def build_contig_map(run_root, organisms):
    """Maps (organism, feature_id) to its contig id, parsed from gene_id by regex."""
    rx = re.compile(r"^(.*)_(\d+)([+-])(\d+)$")
    m = {}
    for org in organisms:
        path = run_root / org / "labeling" / "labeled-genes.tsv"
        if not path.is_file():
            continue
        with open(path, newline="") as fh:
            rd = csv.reader(fh, delimiter="\t")
            header = next(rd)
            iF = header.index("feature_id")
            iG = header.index("gene_id")
            for row in rd:
                if len(row) > max(iF, iG):
                    hit = rx.match(row[iG] or "")
                    m[(org, row[iF])] = hit.group(1) if hit else None
    return m


def _key(a, b):
    """Returns the descriptor pair in sorted order."""
    return (a, b) if a < b else (b, a)


REF_VERSION = 2   # bump when the counts schema changes; "contrib" is optional within version 2


def new_reference(params=None):
    """Creates an empty OCC reference of additive pan-genome counts.

    rho_adj / rho_op are derived later by finalize_reference(). contrib holds each
    genome's own counts (organism_contribution()), so it is subtracted exactly.
    """
    p = dict(DEFAULTS)
    if params:
        p.update(params)
    return dict(
        version=REF_VERSION,
        # --- additive counts (the persistent database) --------------------
        present=defaultdict(set),      # descriptor -> {organisms present}
        adj_org=defaultdict(set),      # pair -> {organisms adjacent}
        coop_org=defaultdict(set),     # pair -> {organisms same-operon}
        adj_inst=defaultdict(int),     # pair -> # adjacency instances
        coop_inst=defaultdict(int),    # pair -> # same-operon instances
        deg_adj=defaultdict(int),      # descriptor -> adjacency incidence
        deg_op=defaultdict(int),       # descriptor -> same-operon incidence
        M_adj=0, M_op=0,               # totals for the enrichment null
        n_qualifying_operons=0,
        organisms_added=set(),         # guards against double-counting
        contrib={},                    # organism -> its counts as added
        # --- derived (filled by finalize_reference) -----------------------
        rho_adj={}, rho_op={},
        params=p, finalized=False,
    )


def organism_contribution(org, org_genes, contig, canon=None):
    """Returns one organism's counts from its qualifying operons as a compact record (pandas groupby per operon).

    present: its descriptors in qualifying operons; adj / coop: {pair: instances}
    for same-contig adjacent and same-operon informative pairs; n_op: qualifying
    operons. deg_adj, deg_op, M_adj and M_op follow from adj / coop, as each
    instance adds 1 to both descriptors' degree and to M. canon maps descriptors
    to the string objects the reference already holds, so a pickle stores each once.
    """
    canon = {} if canon is None else canon
    uninf = {f: bool(u) for f, u in
             zip(org_genes["feature_id"], org_genes["uninformative"])}
    cln = {}
    for f, c in zip(org_genes["feature_id"], org_genes["clean_descriptor"]):
        d = _norm(c)
        cln[f] = canon.setdefault(d, d)

    present, adj, coop = set(), defaultdict(int), defaultdict(int)
    n_op = 0
    for oid, sub in org_genes.groupby("operon_id"):
        if not str(oid).startswith("operon_"):
            continue
        recs = sub.sort_values("start").to_dict("records")
        # informative-majority gate
        inf_recs = [r for r in recs if not uninf[r["feature_id"]]
                    and cln[r["feature_id"]]]
        n_inf = len(inf_recs)
        n_unf = len(recs) - n_inf
        if n_inf <= n_unf or n_inf == 0:
            continue
        n_op += 1

        # present (informative members of a qualifying operon)
        inf_descs = {cln[r["feature_id"]] for r in inf_recs}
        present |= inf_descs

        # --- co-operon channel: unique informative descriptor pairs ---------
        dl = sorted(inf_descs)
        for i in range(len(dl)):
            for j in range(i + 1, len(dl)):
                coop[(dl[i], dl[j])] += 1

        # --- adjacency channel: consecutive informative genes (same contig) -
        for a, b in zip(recs[:-1], recs[1:]):
            fa, fb = a["feature_id"], b["feature_id"]
            if contig.get((org, fa)) != contig.get((org, fb)):
                continue
            if uninf[fa] or uninf[fb]:
                continue
            da, db = cln[fa], cln[fb]
            if not da or not db or da == db:
                continue
            adj[_key(da, db)] += 1
    return dict(present=tuple(sorted(present)), adj=dict(adj), coop=dict(coop), n_op=n_op)


# (membership, instances, degree, total) buckets of each channel, with its contribution key
_CHANNELS = (("adj", "adj_org", "adj_inst", "deg_adj", "M_adj"),
             ("coop", "coop_org", "coop_inst", "deg_op", "M_op"))


def _add_contribution(ref, tok, c):
    """Adds a contribution record to the reference counts under tok, in place."""
    for d in c["present"]:
        ref["present"][d].add(tok)
    for ck, org_b, inst_b, deg_b, m in _CHANNELS:
        for k, n in c[ck].items():
            ref[org_b][k].add(tok)
            ref[inst_b][k] += n
            ref[deg_b][k[0]] += n
            ref[deg_b][k[1]] += n
            ref[m] += n
    ref["n_qualifying_operons"] += c["n_op"]


def _remove_contribution(ref, tok, c):
    """Subtracts a contribution record from the reference counts under tok in place, pruning emptied keys."""
    for d in c["present"]:
        s = ref["present"].get(d)
        if s is not None:
            s.discard(tok)
            if not s:
                del ref["present"][d]
    for ck, org_b, inst_b, deg_b, m in _CHANNELS:
        for k, n in c[ck].items():
            s = ref[org_b].get(k)
            if s is not None:
                s.discard(tok)
                if not s:
                    del ref[org_b][k]
            for bucket, key in ((inst_b, k), (deg_b, k[0]), (deg_b, k[1])):
                if key in ref[bucket]:
                    ref[bucket][key] -= n
                    if ref[bucket][key] <= 0:
                        del ref[bucket][key]
            ref[m] -= n
    ref["n_qualifying_operons"] -= c["n_op"]


def _canon(ref):
    """Returns {descriptor: the reference's own string object} for organism_contribution()."""
    return {d: d for d in ref["present"]}


def _accumulate_organism(ref, org, org_genes, contig):
    """Adds one organism's qualifying operons to the reference counts and returns its contribution.

    Counts descriptor presence, same-operon pairs and same-contig adjacent pairs.
    """
    c = organism_contribution(org, org_genes, contig, canon=_canon(ref))
    _add_contribution(ref, org, c)
    return c


def update_reference(ref, genes, run_root, organisms=None, skip_existing=True):
    """Adds organisms from a genes DataFrame to the reference in place and returns it.

    organisms limits which are added (default: all new ones); already-added
    organisms are skipped, or raise when skip_existing is False. Each added
    organism's contribution is stored in ref["contrib"]. Leaves the reference
    un-finalized.
    """
    all_orgs = sorted(genes["organism"].unique())
    if organisms is not None:
        all_orgs = [o for o in all_orgs if o in set(organisms)]
    to_add = []
    for org in all_orgs:
        if org in ref["organisms_added"]:
            if skip_existing:
                continue
            raise ValueError("organism already in OCC reference: %s" % org)
        to_add.append(org)
    if not to_add:
        return ref

    contig = build_contig_map(run_root, to_add)
    gg = genes[genes["organism"].isin(to_add)]
    contrib = ref.setdefault("contrib", {})
    for org in to_add:
        contrib[org] = _accumulate_organism(ref, org, gg[gg["organism"] == org], contig)
        ref["organisms_added"].add(org)
    ref["finalized"] = False
    return ref


def replace_organism(ref, genes, run_root, organism, token=None):
    """Replaces one genome's counts in ref, in place, with its contribution from its current files.

    The counts under ``token`` (its name in the reference, default ``organism``)
    are removed with its stored contribution, or, for a genome added before
    contributions were stored, with one recomputed from its current files. Returns
    'stored', 'recomputed' or 'added' (token was absent). Leaves ref un-finalized.
    """
    tok = token if token is not None else organism
    contig = build_contig_map(run_root, [organism])
    new = organism_contribution(organism, genes[genes["organism"] == organism], contig,
                                canon=_canon(ref))
    contrib = ref.setdefault("contrib", {})
    how = "added"
    if tok in ref["organisms_added"]:
        old = contrib.get(tok)
        how = "stored" if old is not None else "recomputed"
        _remove_contribution(ref, tok, old if old is not None else new)
    _add_contribution(ref, tok, new)
    ref["organisms_added"].add(tok)
    contrib[tok] = new
    ref["finalized"] = False
    return how


def _copy_counts(ref):
    """Returns a deep copy of the reference's additive counts with empty rho tables.

    Contribution records are shared with ref, which replaces them rather than changing them.
    """
    return dict(
        version=ref["version"],
        present=defaultdict(set, {d: set(s) for d, s in ref["present"].items()}),
        adj_org=defaultdict(set, {k: set(s) for k, s in ref["adj_org"].items()}),
        coop_org=defaultdict(set, {k: set(s) for k, s in ref["coop_org"].items()}),
        adj_inst=defaultdict(int, dict(ref["adj_inst"])),
        coop_inst=defaultdict(int, dict(ref["coop_inst"])),
        deg_adj=defaultdict(int, dict(ref["deg_adj"])),
        deg_op=defaultdict(int, dict(ref["deg_op"])),
        M_adj=ref["M_adj"], M_op=ref["M_op"],
        n_qualifying_operons=ref["n_qualifying_operons"],
        organisms_added=set(ref["organisms_added"]),
        contrib=dict(ref.get("contrib") or {}),
        rho_adj={}, rho_op={},
        params=dict(ref["params"]), finalized=False,
    )


def subtract_organism(ref, genes, run_root, organism, token=None,
                      require_present=True):
    """Returns an un-finalized copy of ref with one genome's counts subtracted (leave-one-out).

    The genome's stored contribution under ``token`` (its stored name, default
    ``organism``) is removed; a reference without one (added before contributions
    were stored) has it recomputed from the files under ``organism``, which can
    differ from what was added. Emptied keys are pruned. Prints which was used.
    Raises when token is absent unless require_present is False.
    """
    tok = token if token is not None else organism
    if tok not in ref["organisms_added"]:
        if require_present:
            raise ValueError("organism not in OCC reference: %s" % tok)
        return _copy_counts(ref)

    c = (ref.get("contrib") or {}).get(tok)
    if c is not None:
        print(f"[c3-occ] leave-one-out: subtracted '{tok}' with its stored contribution (exact)")
    else:
        contig = build_contig_map(run_root, [organism])
        c = organism_contribution(organism, genes[genes["organism"] == organism], contig)
        print(f"[c3-occ] leave-one-out: '{tok}' has no stored contribution (added before they were "
              f"stored); subtracted one recomputed from its current files")

    out = _copy_counts(ref)
    _remove_contribution(out, tok, c)
    out["organisms_added"].discard(tok)
    out["contrib"].pop(tok, None)
    out["finalized"] = False
    return out


def leave_one_out(ref, genes, run_root, organism, token=None,
                  require_present=True):
    """Returns a finalized copy of ref without the genome (subtract_organism + finalize_reference)."""
    loo = subtract_organism(ref, genes, run_root, organism, token=token,
                            require_present=require_present)
    finalize_reference(loo)
    return loo


def finalize_reference(ref):
    """Derives per-pair reliabilities rho_adj / rho_op from the counts and returns ref.

    rho = Jeffreys lower bound BetaInv(delta; k + 1/2, copres - k + 1/2) (scipy.stats.beta)
    times the enrichment weight lift / (lift + lambda), lift = observed / (deg_a*deg_b / 2M).
    """
    delta = ref["params"]["delta"]
    lam = ref["params"]["lam"]
    use_w = ref["params"]["use_enrichment"]
    present = ref["present"]

    _lb_cache = {}

    def _lb(k, n):
        """Returns the cached Jeffreys lower bound for k successes in n."""
        if n <= 0:
            return 0.0
        k = min(k, n)
        ck = (k, n)
        v = _lb_cache.get(ck)
        if v is None:
            v = float(_beta.ppf(delta, k + 0.5, n - k + 0.5))
            _lb_cache[ck] = v
        return v

    def _w(inst, da, db, deg, M):
        """Returns the enrichment weight against the configuration-null expectation."""
        if not use_w or M <= 0:
            return 1.0
        E = deg[da] * deg[db] / (2.0 * M)
        if E <= 0:
            return 1.0
        lift = inst / E
        return lift / (lift + lam)

    rho_adj = {}
    for k, orgs in ref["adj_org"].items():
        a, b = k
        copres = len(present[a] & present[b])
        rho_adj[k] = _lb(len(orgs), copres) * _w(ref["adj_inst"][k], a, b,
                                                 ref["deg_adj"], ref["M_adj"])
    rho_op = {}
    for k, orgs in ref["coop_org"].items():
        a, b = k
        copres = len(present[a] & present[b])
        rho_op[k] = _lb(len(orgs), copres) * _w(ref["coop_inst"][k], a, b,
                                                ref["deg_op"], ref["M_op"])
    ref["rho_adj"] = rho_adj
    ref["rho_op"] = rho_op
    ref["finalized"] = True
    return ref


def write_atomic(path, write, binary=False):
    """Writes through write(fh) to a temporary file beside path, then os.replace()s it into place.

    Readers see the old file or the new one, not a partial write; the new file keeps the old one's
    permission bits. Returns the path.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.{secrets.token_hex(4)}.tmp")
    try:
        with (open(tmp, "xb") if binary else open(tmp, "x", newline="")) as fh:
            write(fh)
            fh.flush()
            os.fsync(fh.fileno())
        try:
            os.chmod(tmp, stat.S_IMODE(os.stat(path).st_mode))
        except FileNotFoundError:
            pass
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return path


def write_text_atomic(path, text):
    """Writes text to path with write_atomic()."""
    return write_atomic(path, lambda fh: fh.write(text))


def save_reference(ref, path):
    """Writes the reference (counts and derived tables) to disk with pickle, atomically."""
    import pickle
    return write_atomic(path, lambda fh: pickle.dump(ref, fh, protocol=pickle.HIGHEST_PROTOCOL),
                        binary=True)


def load_reference(path):
    """Loads a pickled reference and checks its schema version."""
    import pickle
    with open(path, "rb") as fh:
        ref = pickle.load(fh)
    if ref.get("version") != REF_VERSION:
        raise ValueError("OCC reference version %r != expected %r; rebuild it"
                         % (ref.get("version"), REF_VERSION))
    return ref


# ---- Members sidecar: genome fingerprint -> organism token (leave-one-out) ----
def members_sidecar_path(reference_path):
    """Returns the members sidecar path, <reference>.members.tsv."""
    return Path(str(reference_path) + ".members.tsv")


def load_members(reference_path):
    """Reads the members sidecar with csv into {genome_fingerprint: organism_token}."""
    p = members_sidecar_path(reference_path)
    out = {}
    if p.is_file():
        with open(p, newline="") as fh:
            for row in csv.reader(fh, delimiter="\t"):
                if len(row) >= 2 and row[0]:
                    out[row[0]] = row[1]
    return out


def record_member(reference_path, fingerprint, organism):
    """Upserts fingerprint -> organism in the members sidecar (atomic write); the caller holds the reference lock."""
    if not fingerprint:
        return
    members = load_members(reference_path)
    if members.get(fingerprint) == organism:
        return
    members[fingerprint] = organism

    def _write(fh):
        w = csv.writer(fh, delimiter="\t")
        for fp, org in sorted(members.items(), key=lambda x: (x[1], x[0])):
            w.writerow([fp, org])
    write_atomic(members_sidecar_path(reference_path), _write)


# ---- Pool-stats sidecar: per-genome tallies keyed by organism token ----
POOL_STAT_COLS = ("total_genes", "operonic_genes", "singleton_genes",
                  "n_operons", "n_informative_operons", "n_uninformative_operons")


def pool_stats_sidecar_path(reference_path):
    """Returns the pool-stats sidecar path, <reference>.genome_stats.tsv."""
    return Path(str(reference_path) + ".genome_stats.tsv")


def load_pool_stats(reference_path):
    """Reads the pool-stats sidecar with csv into {organism_token: {stat: int}}."""
    p = pool_stats_sidecar_path(reference_path)
    out = {}
    if p.is_file():
        with open(p, newline="") as fh:
            rd = csv.DictReader(fh, delimiter="\t")
            for row in rd:
                org = (row.get("organism") or "").strip()
                if not org:
                    continue
                out[org] = {c: int(float(row.get(c, 0) or 0)) for c in POOL_STAT_COLS}
    return out


def record_pool_stats(reference_path, fingerprint, organism, stats):
    """Upserts one genome's POOL_STAT_COLS stats in the pool-stats sidecar (atomic write)."""
    if not organism:
        return
    p = pool_stats_sidecar_path(reference_path)
    existing = {}
    if p.is_file():
        with open(p, newline="") as fh:
            for row in csv.DictReader(fh, delimiter="\t"):
                o = (row.get("organism") or "").strip()
                if o:
                    existing[o] = row
    existing[organism] = dict(fingerprint=fingerprint or "", organism=organism,
                              **{c: int(stats.get(c, 0)) for c in POOL_STAT_COLS})

    def _write(fh):
        w = csv.writer(fh, delimiter="\t")
        w.writerow(("fingerprint", "organism") + POOL_STAT_COLS)
        for o in sorted(existing):
            r = existing[o]
            w.writerow([r.get("fingerprint", ""), o]
                       + [int(float(r.get(c, 0) or 0)) for c in POOL_STAT_COLS])
    write_atomic(p, _write)


def build_reference(genes, run_root, params=None):
    """Builds and finalizes a reference from all organisms in genes."""
    ref = new_reference(params)
    update_reference(ref, genes, run_root)
    finalize_reference(ref)
    return ref


def rho_adj(a, b, ref):
    """Returns the adjacency reliability of a descriptor pair, 0 when unknown."""
    if not a or not b or a == b:
        return 0.0
    return ref["rho_adj"].get(_key(_norm(a), _norm(b)), 0.0)


def rho_op(a, b, ref):
    """Returns the same-operon reliability of a descriptor pair, 0 when unknown."""
    if not a or not b or a == b:
        return 0.0
    return ref["rho_op"].get(_key(_norm(a), _norm(b)), 0.0)


def occ_for_gene(descriptor, adjacent_descs, cooperon_descs, ref, detail=False):
    """Returns OCC for one informative gene as a noisy-OR over its partners.

    OCC = 1 - prod(1 - rho_adj) over adjacent descriptors * prod(1 - rho_op) over
    other co-members. With detail=True returns a dict with partner count and best link.
    """
    d = _norm(descriptor)
    if not d:
        return (dict(occ=float("nan"), n_partners=0, best_partner="",
                     best_rho=0.0, best_channel="") if detail else float("nan"))
    floor = ref["params"]["link_floor"]
    prod = 1.0
    used = 0
    best_rho = 0.0
    best_partner = ""
    best_channel = ""
    for n in adjacent_descs:
        nn = _norm(n)
        if not nn or nn == d:
            continue
        r = rho_adj(d, nn, ref)
        if r >= floor and r > 0.0:
            prod *= (1.0 - r)
            used += 1
            if r > best_rho:
                best_rho, best_partner, best_channel = r, nn, "adj"
    for c in cooperon_descs:
        cc = _norm(c)
        if not cc or cc == d:
            continue
        r = rho_op(d, cc, ref)
        if r >= floor and r > 0.0:
            prod *= (1.0 - r)
            used += 1
            if r > best_rho:
                best_rho, best_partner, best_channel = r, cc, "op"
    occ = 0.0 if used == 0 else 1.0 - prod
    if detail:
        return dict(occ=occ, n_partners=used, best_partner=best_partner,
                    best_rho=best_rho, best_channel=best_channel)
    return occ


def compute_all_genes(genes, run_root, params=None, ref=None):
    """Computes OCC for every gene in a qualifying operon and returns a pandas DataFrame.

    Uninformative members inherit the operon's mean informative OCC; the median
    informative OCC is stored in .attrs["occ0"]. A prebuilt ref may be passed.
    """
    import pandas as pd
    if ref is None:
        ref = build_reference(genes, run_root, params)
    elif not ref.get("finalized"):
        finalize_reference(ref)

    g = genes.copy()
    organisms = sorted(g["organism"].unique())
    contig = build_contig_map(run_root, organisms)
    g["contig"] = [contig.get((o, f)) for o, f in zip(g["organism"], g["feature_id"])]
    uninf = {(o, f): bool(u) for o, f, u in
             zip(g["organism"], g["feature_id"], g["uninformative"])}
    cln = {(o, f): _norm(c) for o, f, c in
           zip(g["organism"], g["feature_id"], g["clean_descriptor"])}

    rows = []
    for (org, oid), sub in g.groupby(["organism", "operon_id"]):
        if not str(oid).startswith("operon_"):
            continue
        recs = sub.sort_values("start").to_dict("records")
        inf_recs = [r for r in recs if not uninf[(org, r["feature_id"])]
                    and cln[(org, r["feature_id"])]]
        n_inf = len(inf_recs)
        n_unf = len(recs) - n_inf
        if n_inf <= n_unf or n_inf == 0:
            continue  # operon does not qualify

        member_occ = {}
        for idx, r in enumerate(recs):
            fid = r["feature_id"]
            d = cln[(org, fid)]
            if uninf[(org, fid)] or not d:
                continue
            # immediate informative neighbours
            adj = []
            for nb in (recs[idx - 1] if idx > 0 else None,
                       recs[idx + 1] if idx + 1 < len(recs) else None):
                if nb is None:
                    continue
                if nb["contig"] != r["contig"]:
                    continue
                nd = cln[(org, nb["feature_id"])]
                if not uninf[(org, nb["feature_id"])] and nd and nd != d:
                    adj.append(nd)
            adj_set = set(adj)
            coop = [cln[(org, rr["feature_id"])] for k, rr in enumerate(recs)
                    if k != idx and not uninf[(org, rr["feature_id"])]
                    and cln[(org, rr["feature_id"])]
                    and cln[(org, rr["feature_id"])] != d
                    and cln[(org, rr["feature_id"])] not in adj_set]
            det = occ_for_gene(d, adj, coop, ref, detail=True)
            member_occ[fid] = det["occ"]
            rows.append(dict(organism=org, feature_id=fid, clean_descriptor=d,
                             operon_id=oid, uninformative=False,
                             n_inf_context=n_inf - 1, n_partners=det["n_partners"],
                             best_partner=det["best_partner"], best_rho=det["best_rho"],
                             best_channel=det["best_channel"], occ=det["occ"]))

        # Uninformative members inherit the mean informative OCC (numpy)
        coherence = float(np.mean(list(member_occ.values()))) if member_occ else 0.0
        for r in recs:
            fid = r["feature_id"]
            if uninf[(org, fid)]:
                rows.append(dict(organism=org, feature_id=fid,
                                 clean_descriptor=cln[(org, fid)],
                                 operon_id=oid, uninformative=True,
                                 n_inf_context=n_inf, n_partners=0,
                                 best_partner="", best_rho=0.0,
                                 best_channel="inherited", occ=coherence))

    df = pd.DataFrame(rows)
    if len(df):
        df.attrs["occ0"] = float(df.loc[~df["uninformative"], "occ"].median())
    df.attrs["ref"] = ref
    return df


def apply_occ(base_prob, occ, occ0, beta=1.0):
    """Shifts base_prob in log-odds by beta*(occ - occ0) with numpy and returns the probability."""
    p = min(max(float(base_prob), 1e-6), 1 - 1e-6)
    logit = np.log(p / (1 - p)) + beta * (float(occ) - float(occ0))
    return 1.0 / (1.0 + np.exp(-logit))
