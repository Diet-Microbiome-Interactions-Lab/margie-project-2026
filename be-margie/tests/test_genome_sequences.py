"""The maps name a genome's sequences only as its FASTA headers do (workflow_tools/viz/genome_fasta.py):
lengths come from the run's link to the genome's file, and without it the maps say the lengths run to
each sequence's last gene."""

import gzip
import json
import re
import sys
from unittest.mock import patch

from tests.test_viewer_trail import viewer
from tests.test_viewer_trail import VIEWER

sys.path.insert(0, str(VIEWER.parent))
import genome_fasta  # noqa: E402

HEAD = ['organism_name', 'gene_id', 'RAST_feature_id', 'RAST_start', 'RAST_end', 'RAST_strand', 'CONFIDENCE_TIER']
GENES = [['G--fa1:ab', 'chr_10+300', 'fig|1.1.peg.1', '10', '309', '+', 'high'],
         ['G--fa1:ab', 'p1_5+90', 'fig|1.1.peg.2', '5', '94', '-', 'low']]
FASTA = '>chr Bug strain X chromosome, complete genome\nACGTACGTAC\n' + 'A' * 990 + '\n>p1 Bug strain X plasmid pX1, complete sequence\n' + 'C' * 200 + '\n>c3 Bug contig 3\n' + 'G' * 50 + '\n'


def _run(tmp_path, fasta=FASTA, gz=False):
    run = tmp_path / 'run'
    final = run / 'G--fa1:ab' / 'scoring' / 'FINAL_ANNOTATION_WITH_CONFIDENCE.tsv'
    final.parent.mkdir(parents=True)
    final.write_text('\n'.join('\t'.join(r) for r in [HEAD, *GENES]) + '\n')
    if fasta is not None:
        (run / '.margie-input').mkdir()
        if gz:
            (run / '.margie-input' / 'G--fa1:ab.fna.gz').write_bytes(gzip.compress(fasta.encode()))
        else:
            (run / '.margie-input' / 'G--fa1:ab.fna').write_text(fasta)
    out = tmp_path / 'map.html'
    with patch.object(sys, 'argv', ['gen_genome_viewer.py', str(final), str(out)]):
        viewer.main()
    return json.loads(re.search(r'const D = (\{.*?\});\n', out.read_text()).group(1))


def test_only_the_headers_own_words_name_a_sequence():
    assert genome_fasta.kind_of('Bug strain X chromosome 1, complete sequence') == 'chromosome'
    assert genome_fasta.kind_of('Bug strain X plasmid pX1, complete sequence') == 'plasmid'
    assert genome_fasta.kind_of('Aeropyrum pernix K1, complete sequence') == ''
    assert genome_fasta.kind_of('Bug complete genome') == ''
    assert genome_fasta.kind_of('chromosome-borne plasmid remnant') == ''


def test_the_map_reads_lengths_and_kinds_from_the_runs_link_to_the_fasta(tmp_path):
    for gz in (False, True):
        d = _run(tmp_path / str(gz), gz=gz)
        assert d['exact'] is True and d['totLen'] == 1250
        assert [(c['name'], c['len'], c['kind']) for c in d['contigs']] == [('chr', 1000, 'chromosome'), ('p1', 200, 'plasmid'), ('c3', 50, '')]


def test_without_the_fasta_the_map_says_its_lengths_run_to_the_last_gene(tmp_path):
    d = _run(tmp_path, fasta=None)
    assert d['exact'] is False and d['totLen'] == 309 + 94
    assert all(c['kind'] == '' for c in d['contigs'])
    # A FASTA that does not name the sequences the genes are on is not used.
    d = _run(tmp_path / 'other', fasta='>other plasmid\nACGT\n')
    assert d['exact'] is False


def test_the_page_says_sequences_and_claims_no_replicons():
    t = viewer.TEMPLATE
    assert 'replicon' not in re.sub(r'//[^\n]*', '', t).lower()
    assert 'by their FASTA headers' in t and '(to the last gene of each sequence)' in t
