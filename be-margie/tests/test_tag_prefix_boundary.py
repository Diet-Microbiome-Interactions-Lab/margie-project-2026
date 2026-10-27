"""The DUF/UPF/ORF rules of labeling/descriptor_rules.py match the tag as a whole word: "Orfamide
synthetase" names a function, "DUF167 family protein", "UPF0145 protein" and "ORF1" do not."""

import importlib.util
from pathlib import Path

RULES = Path(__file__).resolve().parents[1] / 'bioinformatics_tools' / 'workflow_tools' / 'labeling' / 'descriptor_rules.py'
spec = importlib.util.spec_from_file_location('descriptor_rules_t', RULES)
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)


def test_tags_count_as_whole_words():
    for name in ('Orfamide synthetase', 'orfamide biosynthesis protein', 'Dufulin resistance protein',
                 'Upframe regulator'):
        assert not R.is_uninformative(name), name
    for name in ('DUF167 family protein', 'DUF', 'duf-containing protein', 'UPF0145 protein YbjQ',
                 'ORF1', 'orf_12', 'ORF3b protein', 'orf'):
        assert R.is_uninformative(name), name
