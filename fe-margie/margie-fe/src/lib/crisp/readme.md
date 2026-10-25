# MARGIE

**Mostly Automated Rapid Genome Inference Environment**

A product of the Diet-Microbiome Interactions Lab, Purdue University. PI: Stephen R Lindemann (lindems@purdue.edu).

MARGIE annotates prokaryotic genomes with many tools at once and scores how much their evidence agrees, gene by gene. It is a Snakemake pipeline housed, among other tools, within the Bioinformatics Supercomputing Platform (BSP) developed by Dane Deemer. This website runs it on Purdue's clusters: you sign in, point it at your genomes, and follow the run; nothing is installed on your computer.

## Getting an account

- **At Purdue:** under **Create account**, give a MARGIE username and password, your cluster's login address, your cluster username, and an SSH key for it. The sign-in page shows how to make a key.
- **Outside Purdue** (reviewers, collaborators): ask the lab for a username and password at lindems@purdue.edu; the sign-in page's **Outside Purdue** tab opens an email to the lab in your mail app with what you type there.

## A first run

1. **Install**: type the install statement once, after reading the licences it refers to. Check that the cluster, SLURM account and partition are ready, and accept the licence terms.
2. **Settings**: the one place for what a run reads: folders, databases, SLURM resources per phase and per tool. Changes apply to the next run.
3. **Analyze**:
   1. *Genomes*: the folder they are in, or drop FASTA files; give each its domain and genetic code if you know them.
   2. *Gene calling*: QUAST, GTDB-Tk (if domain and genetic code are not known), then RASTtk or Prodigal for each genome.
   3. *Annotation tools*: the phase 4 tools are recommended; tools with licence terms stay off until you accept them.
   4. Start. On a first run your databases are copied to your scratch folder once.
4. **Jobs**: progress by genome and tool, the log, and the exact command that ran, to run again from a shell.
5. **Results**: the annotation with its confidence, per genome, an interactive genome map, and every file in **Files**.

How a run annotates and scores is set out under **Methods**.

## What comes out

- `FINAL_ANNOTATION_WITH_CONFIDENCE.tsv`: every gene's label, its source, location and topology, the four scoring measures with their reasoning, its 0 to 1 confidence and tier.
- A GFF of the annotation, each tool's own results, gene and operon fingerprints, and a genome map.

## The desktop app

MARGIE also runs as a desktop app that looks and works like this site, on your own computer or against a cluster. Download it from the [releases](https://github.com/Diet-Microbiome-Interactions-Lab/margie-project-2026/releases).

## How to cite

This pipeline:

Bhattarai, S., Deemer, D., & Lindemann, S. R. (2026). *MARGIE: Mostly Automated Rapid Genome Inference Environment* [Computer software]. Purdue University. https://github.com/Diet-Microbiome-Interactions-Lab/margie-project-2026

Thesis, in which MARGIE was first built:

Bhattarai, S. (2026). *Mostly Automated Rapid Genome Inference Environment* [Thesis, Purdue University]. Purdue University Graduate School. https://doi.org/10.25394/PGS.33103682.v1

```bibtex
@article{Bhattarai2026,
author = "Sajal Bhattarai",
title = "{MOSTLY AUTOMATED RAPID GENOME INFERENCE ENVIRONMENT}",
year = "2026",
month = "7",
url = "https://hammer.purdue.edu/articles/thesis/_b_MOSTLY_AUTOMATED_RAPID_GENOME_INFERENCE_ENVIRONMENT_b_/33103682",
doi = "10.25394/PGS.33103682.v1"
}
```

Base architecture on which MARGIE was built, by Dane Deemer:

- Deemer, D. (2020). *bioinformatics-tools* [Computer software]. GitHub. https://github.com/wintermutant/bioinformatics-tools (the backend that be-margie grew from: API, command line and workflow engine)
- Deemer, D. (2025). *biolab-fe* [Computer software]. GitHub. https://github.com/wintermutant/biolab-fe (the web interface that fe-margie grew from)

```bibtex
@software{Deemer2020,
author = "Dane Deemer",
title = "{bioinformatics-tools}",
year = "2020",
publisher = "GitHub",
url = "https://github.com/wintermutant/bioinformatics-tools"
}
@software{Deemer2025,
author = "Dane Deemer",
title = "{biolab-fe}",
year = "2025",
publisher = "GitHub",
url = "https://github.com/wintermutant/biolab-fe"
}
```

Cite the version you ran, and each tool and database MARGIE ran for you; their references are under **Acknowledgements**.

## Licences

MARGIE is released under the MIT licence. The tools and databases it runs keep their own licences; several are for academic use only. Install lists every one, with links, and MARGIE turns off any tool whose terms you have not accepted.

## Contact

Diet-Microbiome Interactions Lab, Purdue University: lindems@purdue.edu
