<div align="center">

<img src="fe-margie/margie-fe/static/home/margie-logo.png" width="140" alt="MARGIE logo">

# MARGIE

**Mostly Automated Rapid Genome Inference Environment**

Annotates prokaryotic genomes with many tools at once, finds operons, and scores how much the
evidence agrees, gene by gene.

[![Built with Snakemake](https://img.shields.io/badge/Built_with-Snakemake-039475?style=for-the-badge)](https://snakemake.readthedocs.io/)

<img src="be-margie/docs/img/Sedimenticola_thiotaurini_GCF_001007875.1.png" width="820" alt="Sedimenticola_thiotaurini_GCF_001007875.1 circular genome map: Operon mode">

</div>

MARGIE runs on an HPC cluster with SLURM and Apptainer. Use it from the command line on the
cluster, or through its website, which you run yourself.

| Folder | What it is |
|---|---|
| [`be-margie/`](be-margie) | The MARGIE(SB) Snakemake pipeline, the `dane_wf` command line, and the API the website talks to. |
| [`fe-margie/`](fe-margie) | The website: MARGIE's interface. |

## Run it from the command line

On the cluster:

```bash
git clone https://github.com/Diet-Microbiome-Interactions-Lab/margie-project-2026.git ~/margie-project-2026
ln -s ~/margie-project-2026/be-margie ~/bioinformatics-tools
cd ~/bioinformatics-tools
uv sync
source .venv/bin/activate

dane_wf        # the first time: creates ~/.config/bioinformatics-tools/config.yaml
```

Set your folders and databases in that file (see [be-margie/README.md](be-margie/README.md#configure)),
then run:

```bash
dane_wf margie sb \
  input: path-to-input-folder-or-fasta \
  output_dir: path-to-output-folder
```

### Choosing the tools

Without a list, a run uses `margie_sb.default_selected_tools` from your config.yaml, or else
every tool up to scoring. To choose, list them by name, separated by commas:

```bash
dane_wf margie sb \
  input: path-to-input-folder-or-fasta \
  output_dir: path-to-output-folder \
  margie_sb.selected_tools: gtdbtk,rasttk,cog,kegg,eggnog,uniprot,pfam,tigrfam,dbcan,pgap,geneprop,interpro,operon,envelope,consolidation,labeling,fingerprint,scoring_heuristic,fingerprint_database
```

| Phase | Tools |
|---|---|
| 1. Assembly quality | `quast` |
| 2. Taxonomy | `gtdbtk`: each genome's domain and genetic code. Without it, give them in `margie_sb.genome_info`, or Prodigal calls that genome's genes. |
| 3. Gene calling | `rasttk` (keep it in the list) |
| 4. Annotation | `cog`, `kegg`, `eggnog`, `uniprot`, `pfam`, `tigrfam`, `merops`, `tcdb`, `dbcan`, `pgap`, `geneprop`, `interpro` |
| 5. Operons | `operon` |
| 6. Topology and signal peptides | `phobius`, `tmbed`, `signalp6` |
| 7. Cell envelope | `envelope` |
| 8. Localisation | `psortb`, `deepsig`, `signalp4` |
| 9 to 13. Consensus and confidence | `consolidation`, `labeling`, `fingerprint`, `scoring_heuristic`, `fingerprint_database` |

Keep phases 9 to 13 in the list to get each gene's confidence score.

On the first run, MARGIE shows the licence of every tool and database it uses and asks you to
accept them; tools you are not licensed for are turned off (Phobius, SignalP 4 and 6 and
MEROPS need your own licence; for commercial use, TMbed, TCDB and KEGG too). Configuration,
background runs and the full set of options: [be-margie/README.md](be-margie/README.md).

## Run the website

The website and its API run on a machine of yours that can reach the cluster's login node over
SSH. Each person signs in with their own cluster account and SSH key; the API runs everything
on the cluster as them.

**1. The API**

```bash
cd be-margie
uv sync
cp .env.example .env    # then set BSP_SECRET_KEY and BSP_ENCRYPTION_KEY (how to make them is in the file)
uv run dane-api         # listens on port 8000
```

**2. The website**

```bash
cd fe-margie/margie-fe
npm ci
VITE_PUBLIC_API_URL=http://localhost:8000 npm run dev
```

Open http://127.0.0.1:5173. To serve it instead, `npm run build` writes static files to
`build/`: serve them with any web server, and send `/v1` on the same address to the API.

**3. Sign in**

Create an account with your cluster's login address, your cluster username and an SSH key for
it. The first time, MARGIE clones this repository into your home folder on the cluster
(`~/margie-project-2026`) and builds the pipeline's environment there; every run uses that
copy. Then follow the pages in order: Install (licences and checks), Settings, Analyze, Jobs
and Results.

## Desktop app

A desktop app, for running MARGIE on your own computer, is coming soon.

## Acknowledgements

I (Sajal) gratefully acknowledge Dane Deemer ([wintermutant](https://github.com/wintermutant)) for his mentoring, and the design and development of the engine and GUI orchestration platform on which the MARGIE(SB) workflow was built.

Special thanks goes to Dr. Stephen R Lindemann for his vision, supervision and support throughout this development.
I also thank members of Diet-Microbiome-Interactions Laboratory for their feedbacks and intellectual inputs during this development.

We thank Purdue RCAC for providing the research computing environment that supports this work.

We also thank the developers and maintainers of the upstream tools, databases, and scientific software used throughout the pipeline. Their contributions make reproducible computational biology more powerful, more accessible, and more exciting to do.
