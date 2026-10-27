"""EC agreement (labeling/add-ec-consensus.py, read by C4) is the same whatever the hash seed: a
partial EC such as 1.1.1.- joins the class of each EC it contains but does not make 1.1.1.1 and
1.1.1.2 agree. The winning tool's partial EC counts as consistent with a consensus it contains.
The C4 formula and reason show the capped weight min(m, 5)/5 the score uses."""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

WT = Path(__file__).resolve().parents[1] / 'bioinformatics_tools' / 'workflow_tools'
EC_SCRIPT = WT / 'labeling' / 'add-ec-consensus.py'

_PROBE = """
import importlib.util, json, sys
spec = importlib.util.spec_from_file_location('ec', sys.argv[1])
ec = importlib.util.module_from_spec(spec); spec.loader.exec_module(ec)
cases = [
    {'EGGNOG': {'1.1.1.-'}, 'KEGG': {'1.1.1.1'}, 'RAST': {'1.1.1.2'}},
    {'RAST': {'1.2.3.-'}, 'KEGG': {'1.2.3.4'}, 'UNIPROT': {'1.2.3.5'}, 'COG': {'1.2.3.4'}},
    {'KEGG': {'2.7.1.1', '2.7.1.-'}, 'EGGNOG': {'2.7.1.-'}},
    {'KEGG': {'3.1.1.1'}, 'RAST': {'4.2.1.1'}},
]
print(json.dumps([list(ec.classify_ec_agreement(c)) for c in cases]))
"""


def _module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_ec_agreement_does_not_depend_on_the_hash_seed():
    answers = set()
    for seed in ('0', '1', '2', '3', '7', '42', '1234', '99999'):
        out = subprocess.run([sys.executable, '-c', _PROBE, str(EC_SCRIPT)], capture_output=True, text=True,
                             env={'PYTHONHASHSEED': seed, 'PATH': ''}, check=True).stdout
        answers.add(out)
    assert len(answers) == 1
    got = json.loads(answers.pop())
    assert got[0][0] == 'conflicting'
    # 1.2.3.- does not merge 1.2.3.4 and 1.2.3.5; the best-supported class is 1.2.3.4.
    assert got[1][:2] == ['conflicting', '1.2.3.4'] and got[1][4] == 'COG;KEGG;RAST'
    assert got[2][:2] == ['full_consensus', '2.7.1.1']
    # A tie of support goes to the first EC in sorted order.
    assert got[3][:2] == ['conflicting', '3.1.1.1']


def test_a_partial_ec_of_the_label_source_is_consistent():
    ec = _module('ec_t', EC_SCRIPT)
    evidence = {'RAST': {'1.2.3.-'}, 'KEGG': {'1.2.3.4'}}
    status, consensus, *_ = ec.classify_ec_agreement(evidence)
    assert (status, consensus) == ('full_consensus', '1.2.3.4')
    assert ec.check_label_consistency('RAST', evidence, consensus) == 'True'
    assert ec.check_label_consistency('RAST', {'RAST': {'1.2.4.-'}}, consensus) == 'False'


def test_the_c4_text_shows_the_capped_weight():
    c4 = _module('c4_t', WT / 'scoring' / 'score-c4-ec-agreement.py')
    assert c4.c4_formula(6, 0.6, 0.4) == 'c4_score = 1 - (min(m,5)/5)*R = 1 - (5/5)*0.6000 = 0.4000 (m=6)'
    assert c4.c4_formula(2, 1.0, 0.6) == 'c4_score = 1 - (min(m,5)/5)*R = 1 - (2/5)*1.0000 = 0.6000 (m=2)'
    reason = c4._build_c4_reasoning('conflicting', 'x', 0.6, 9, 15, 6, 0.4)
    assert '(5/5)·0.6000=0.6000' in reason and 'among 6 tools' in reason
    sys.path.insert(0, str(WT / 'scoring'))
    try:
        final = _module('mfawc_t', WT / 'scoring' / 'make-final-annotation-with-confidence.py')
    finally:
        sys.path.remove(str(WT / 'scoring'))
    pretty, reasoning = final._parse_c4_formula(c4.c4_formula(6, 0.6, 0.4), '6')
    assert pretty.endswith('= 1 - (5/5) * 0.6000') and reasoning.startswith('EC_reporting_tools_count = 6.')
    assert final._parse_c4_formula(c4.c4_formula(7, 0.5, 0.5))[1].startswith('EC_reporting_tools_count = 7.')
