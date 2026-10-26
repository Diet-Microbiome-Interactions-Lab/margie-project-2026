/**
 * The FAQ page's questions and answers, with the papers each rests on and the code blocks that do
 * what it says (read from the server's pipeline when opened: routers/code.py, /v1/code/snippet).
 * A question marked `thesis` has a further panel drawn from the thesis, which is under embargo; it
 * opens with the password (locked page "faq", by question id).
 */

export interface FaqCode {
	/** Path under workflow_tools. */
	path: string;
	/** A top-level function, class or constant, or "rule:<name>" in margie_sb.smk. */
	symbol: string;
	why: string;
}

export interface Faq {
	id: string;
	group: string;
	q: string;
	/** Paragraphs of HTML. */
	a: string[];
	refs: string[];
	code: FaqCode[];
	thesis: boolean;
}

export interface Ref {
	id: string;
	/** APA 7th. */
	apa: string;
	url: string;
}

export const GROUPS: string[] = ["Running MARGIE", "Inside the pipeline", "Databases and provenance", "Scoring"];

export const FAQS: Faq[] = [
	{
		"id": "hpc",
		"group": "Running MARGIE",
		"q": "How does MARGIE connect with the HPC?",
		"a": [
			"<p>MARGIE runs on the cluster as you. You sign in to the site with your own cluster account, and a run starts the pipeline under that account, so the run uses your own SLURM account and storage, under the same rules as any job you submit yourself.</p>",
			"<p>The pipeline is a Snakemake workflow. Snakemake works out which steps each genome needs from the files each step reads and writes, and its SLURM executor plugin submits each step as its own SLURM job, with the threads, memory and run time set for that tool on Settings. A step starts once its input files exist; when one fails, only the steps that depend on it stop, and the rest of the run goes on. GTDB-Tk asks for a large-memory node, and RASTtk sends one genome at a time to the BV-BRC annotation service.</p>",
			"<p>Each annotation tool runs inside its own Apptainer container, which holds the tool at a recorded version and reads its reference database from your database folder. MARGIE's own steps, from consolidation to the fingerprint databases, are Python scripts that run as jobs beside them.</p>",
			"<p>Results, the MARGIE database and the shared operon and fingerprint databases stay in your own storage on the cluster; the site reads them from there for Jobs, Results and Files. Jobs also shows the command that ran, so the same run can be started again from a cluster shell.</p>",
			"<p>At Purdue, MARGIE's runs use the research computing of the Rosen Center for Advanced Computing (RCAC): the Negishi community cluster and the Geddes Community Composable Platform (McCartney et al., 2014; Smith et al., 2020). They are acknowledged on <a href=\"/acknowledgements\">Acknowledgements</a> and cited on <a href=\"/contributors#computing\">Contributors</a>.</p>"
		],
		"refs": [
			"koster2012",
			"molder2021",
			"snakemake_slurm",
			"yoo2003",
			"kurtzer2017",
			"apptainer",
			"chaumeil2022",
			"brettin2015",
			"olson2023",
			"mccartney2014",
			"smith2020geddes",
			"rcacnegishi"
		],
		"code": [],
		"thesis": true
	},
	{
		"id": "gene-calling",
		"group": "Running MARGIE",
		"q": "How does MARGIE call genes? What options are there, which is recommended, and why?",
		"a": [
			"<p>Phase 3 calls each genome's genes with one of two callers, chosen genome by genome. RASTtk needs the genome's domain and genetic code. MARGIE takes them from the genome table on Analyze or, when GTDB-Tk runs (phase 2), from its classification. A genome with both known goes to RASTtk; a genome missing either, with GTDB-Tk off, goes to Prodigal. Analyze shows how many genomes go to each caller, and filling in the table or turning on GTDB-Tk moves genomes to RASTtk.</p>",
			"<p><b>RASTtk is recommended.</b> It runs through the BV-BRC service, calls protein-coding and RNA genes with the genome's own genetic code, and names each product from the SEED subsystems. That description is one of the labeling sources (tier 5) and one of the seven C1 sources, and RASTtk's gene calls are what the genome-level cache stores, so a genome run before comes back from the MARGIE database. MARGIE sends one RASTtk job to BV-BRC at a time and stops the step when the genetic code is missing.</p>",
			"<p><b>Prodigal</b> 2.6.3 runs in the cluster job itself, takes the domain and genetic code when they are known (genetic code 11 otherwise) and is fast. It calls protein-coding genes only and leaves the naming to the other tools, so its genomes take their labels from them and C1 reaches at most 6/7. A genome whose sequence has RASTtk results in the MARGIE database takes them, gene calls included, in place of Prodigal, so Prodigal annotates novel genomes. A Prodigal genome's tools take the proteins the protein cache holds and run on the rest. Its results are loaded into the database and stay out of the MARGIE caches, which keep RASTtk-based results: a later RASTtk run of the genome replaces them, and a Prodigal run leaves RASTtk-based results in place. Prodigal writes its gene calls to <code>prodigal/</code> in RASTtk's columns, so phases 4 to 13 run the same way. Gene callers disagree from one organism to another, so genomes you compare are best called by one caller.</p>"
		],
		"refs": [
			"brettin2015",
			"aziz2008",
			"overbeek2014",
			"olson2023",
			"hyatt2010",
			"chaumeil2022",
			"dimonaco2022"
		],
		"code": [
			{
				"path": "workflow_helpers.py",
				"symbol": "genome_calls",
				"why": "Chooses RASTtk or Prodigal for each genome from its domain, genetic code and GTDB-Tk."
			},
			{
				"path": "margie_sb.smk",
				"symbol": "rule:run_rasttk",
				"why": "Runs RASTtk with the genome's domain and genetic code, one BV-BRC job at a time."
			},
			{
				"path": "margie_sb.smk",
				"symbol": "rule:run_prodigal",
				"why": "Runs Prodigal for the other genomes and writes its gene calls to prodigal/ in RASTtk's columns."
			}
		],
		"thesis": true
	},
	{
		"id": "outputs",
		"group": "Running MARGIE",
		"q": "What do we get from each step? Where are the files? Where do the raw and the processed data lie?",
		"a": [
			"<p>Each run writes to the output folder chosen on Analyze, in your own storage on the cluster. The <b>raw data</b> are each container's own output, kept under <code>original_container_outputs/&lt;genome&gt;/&lt;tool&gt;/</code>: <code>raw/</code> holds the files the tool writes, <code>processed/</code> the cleaned table MARGIE takes from them. The <b>processed data</b> are in the genome's own folder, one subfolder per step, and in the MARGIE database, which loads each step's table.</p>",
			"<ul><li>QUAST: assembly statistics. GTDB-Tk: the classification, with domain and genetic code in <code>genome_info/genome_info.tsv</code>.</li><li>Gene calling: <code>rasttk/rast.faa</code> | <code>rast.gff</code> | <code>rast.tsv</code>, or Prodigal's <code>prodigal/prodigal.faa</code> | <code>prodigal.gff</code> | <code>prodigal.tsv</code>.</li><li>Phases 4 to 8: one <code>&lt;tool&gt;/&lt;tool&gt;_results.tsv</code> per tool (InterPro adds one per member database), UniOP's operon table and the one-row envelope summary.</li><li>Consolidation: the merged and no-stat tables. Labeling: <code>labeled-genes.tsv</code> with EC consensus, operon information and tool-cluster agreement.</li><li>Scoring: C1 to C4, the confidence and tier, and <code>FINAL_ANNOTATION_WITH_CONFIDENCE.tsv</code>. Fingerprinting: gene and operon fingerprints and the final annotated tables.</li></ul>",
			"<p>When the run ends, each genome folder is tidied: <code>FINAL_ANNOTATION_WITH_CONFIDENCE.tsv</code> and its Excel copy, <code>FINAL_GENOME_VIEWER.html</code> and a <code>diagrams/</code> folder stay at the top, and the step folders move into <code>per-tool-phased-output/</code>. <code>cache-report.tsv</code> in the run folder says which steps ran and which came back from the cache. A copy of each final table also goes to your final-tables store, and Files on the site browses the folder.</p>"
		],
		"refs": [
			"gurevich2013",
			"chaumeil2022",
			"brettin2015",
			"hyatt2010",
			"jones2014",
			"su2024",
			"sqlite"
		],
		"code": [
			{
				"path": "workflow_helpers.py",
				"symbol": "get_container_outputs_prefix_for",
				"why": "Names the original_container_outputs folder that keeps each tool's raw output."
			},
			{
				"path": "margie_sb.smk",
				"symbol": "rule:run_cog",
				"why": "A typical tool rule: the container writes raw output, its processed table is copied to the genome folder."
			},
			{
				"path": "reorganize_outputs.py",
				"symbol": "reorganize_one",
				"why": "Tidies a genome folder at the end of the run."
			}
		],
		"thesis": false
	},
	{
		"id": "versions",
		"group": "Running MARGIE",
		"q": "Which versions of the reference databases does MARGIE use?",
		"a": [
			"<p>MARGIE records each tool and database version in her licence catalog (catalog version 2026-07-01), and the processed tables name the database each tool used in a <code>_database_used</code> column. The annotation databases are:</p>",
			"<ul><li>COG 2024 (COGclassifier 2.0.0 | BLAST+ 2.16.0)</li><li>KEGG KOfam profiles, recorded as \"current\" (KofamScan 1.3.0)</li><li>eggNOG database 5.0.2 (eggNOG-mapper 2.1.12)</li><li>UniProt Swiss-Prot 2025_05 (DIAMOND 2.1.9)</li><li>Pfam-A 37.0 | TIGRFAMs 15.0 | PGAP HMM library hmm_PGAP 15.0 (HMMER 3.4)</li><li>InterProScan 5.77-108.0 with its member databases</li><li>dbCAN database v13 (dbCAN 5.1.2)</li><li>MEROPS, recorded as \"12.5 / current_release\" | TCDB, recorded as \"2024 / current\"</li><li>Genome Properties, recorded as the repository's git HEAD</li></ul>",
			"<p>Taxonomy uses GTDB r232 with GTDB-Tk 2.7.0. Genes are called by RASTtk (BV-BRC CLI 1.040, with the SEED files marked \"latest\") or by Prodigal, and operons by UniOP at commit 68c55d2 (2025-05-30), with Prodigal 2.6.3 in its container. Where the catalog says \"current\", \"latest\" or git HEAD, it records the download source in place of a release number. MARGIE's own operon pool starts from <code>operon-db.pkl</code> (schema version 2), built on 2026-09-26 from 29 genomes, and grows as genomes are added.</p>",
			"<p>A protein's cached result is keyed to the tool's container, database file and settings, so a new database release means those proteins are annotated again. The full table, with the localisation tools, is on <a href=\"/acknowledgements\">Acknowledgements</a>.</p>"
		],
		"refs": [
			"galperin2025",
			"aramaki2020",
			"huertacepas2019",
			"cantalapiedra2021",
			"uniprot2025",
			"buchfink2021",
			"camacho2009",
			"mistry2021",
			"haft2013",
			"li2021",
			"eddy2011",
			"jones2014",
			"paysanlafosse2023",
			"zheng2023",
			"rawlings2018",
			"saier2021",
			"richardson2019",
			"parks2020",
			"chaumeil2022",
			"brettin2015",
			"overbeek2014",
			"hyatt2010",
			"su2024"
		],
		"code": [
			{
				"path": "protein_cache.py",
				"symbol": "tool_key",
				"why": "Hashes a tool's container, database and settings, so a new release re-annotates cached proteins."
			},
			{
				"path": "process_signalp6.py",
				"symbol": "main",
				"why": "Writes the tool_used, command_used and database_used columns onto each processed row."
			}
		],
		"thesis": false
	},
	{
		"id": "licensing",
		"group": "Running MARGIE",
		"q": "Why does licensing matter?",
		"a": [
			"<p>MARGIE runs third-party tools and databases, each under its own licence, and some of these licences limit who may use a tool or whether it may be passed on. The licence catalog puts each tool in a tier: <b>blocked</b> (academic use only, distributed by the provider alone) | <b>commercial_restricted</b> (free for academic or non-profit use, permission needed for commercial use) | <b>verify</b> | <b>attribution</b> | <b>permissive</b>. The first two tiers gate a run; the others carry citation or licence duties.</p>",
			"<p>Before a first run, a user reads the terms and each tool's licence details, accepts them, says whether their use is academic or commercial, and names the licence-required tools they hold a licence for. Phobius | SignalP 6.0 | the MEROPS database are blocked: their licences let only the provider distribute them, so a user obtains them from the provider. MARGIE runs them for a user who holds that licence and disables them for the run otherwise. For commercial use, TMbed's ProtT5 weights (CC-BY-NC-SA 4.0) | TCDB | the full KEGG database also need the user's own licence; she uses the public KOfam subset of KEGG.</p>",
			"<p>The terms ask users to cite MARGIE and the authors of each tool whose output they use, and offer eggNOG-mapper's source as its AGPL-3.0 licence requires. On the command line MARGIE saves the acceptance with the terms version, a SHA-256 hash of the terms and a copy of the catalog as shown, asks again when the terms change, and stops a non-interactive run that lacks a saved acceptance. Each tool's citation is on <a href=\"/contributors#cite-with\">Contributors</a>.</p>"
		],
		"refs": [
			"kall2004",
			"teufel2022",
			"rawlings2018",
			"bernhofer2022",
			"saier2021",
			"kanehisa2025",
			"aramaki2020",
			"cantalapiedra2021"
		],
		"code": [
			{
				"path": "license_gate.py",
				"symbol": "_print_license_disclosure",
				"why": "Shows each tool's licence, permitted uses and citation before acceptance."
			},
			{
				"path": "license_gate.py",
				"symbol": "LicenseError",
				"why": "Raised when the terms have not been accepted, which stops the run."
			}
		],
		"thesis": false
	},
	{
		"id": "hashing",
		"group": "Inside the pipeline",
		"q": "How does MARGIE hash the genomes and proteins, and at what stage?",
		"a": [
			"<p>MARGIE identifies genomes and proteins by SHA-256 hashes, so she recognises data she has seen before under any file name. Hashing happens at three points of a run.</p>",
			"<p><b>Genomes, before the steps start.</b> <code>genome_hash</code> reads the FASTA and hashes each record's name and its upper-case bases in file order, so a copy with other line breaks, letter case or file name gets the same hash. The result, marked <code>fa1:</code>, keys the genome's stored step outputs in the MARGIE database (the genome-level cache), its run log rows, and the check for a genome already finished at this pipeline version. An older hash of the file's bytes is still looked up, so earlier entries are found.</p>",
			"<p><b>Proteins, after gene calling.</b> Each protein's sequence is upper-cased, cleared of spaces and of a final stop <code>*</code>, and hashed. For each per-protein tool, MARGIE pairs this hash with a tool key: a hash of the tool's container, its database location and modification time, and the settings that change its answer. Proteins already stored under that key come back from the protein-level cache; only the rest go to the tool, and its new rows are stored once they load.</p>",
			"<p><b>MARGIE's own steps.</b> Consolidation and labeling are stored under a hash of their scripts and of the tool tables they merge, so a changed tool set merges again. Each results file is hashed before loading, so the same file loads once, and the operon reference names a genome by a hash of its sorted protein hashes, which lets scoring leave it out of its own reference.</p>"
		],
		"refs": [
			"fips180",
			"sqlite"
		],
		"code": [
			{
				"path": "genome_identity.py",
				"symbol": "genome_hash",
				"why": "Hashes each FASTA record's id and upper-case bases, independent of formatting."
			},
			{
				"path": "genome_identity.py",
				"symbol": "protein_hash",
				"why": "Hashes a protein sequence after removing spaces, case and the final stop."
			},
			{
				"path": "protein_cache.py",
				"symbol": "tool_key",
				"why": "Hashes the container, database and settings a tool's answer depends on."
			}
		],
		"thesis": false
	},
	{
		"id": "consolidation",
		"group": "Inside the pipeline",
		"q": "How does MARGIE consolidate the results from the various phases, and which phases?",
		"a": [
			"<p>Consolidation is phase 9. It joins the per-gene result tables of phases 3 to 8 into one table per genome, one row per gene, keyed by feature id. The tables come from the gene caller (RASTtk, or Prodigal in RASTtk's columns), the phase 4 annotation tools, with InterPro split into its member databases (HAMAP | NCBIfam | CDD | PIRSF), UniOP's operons, the topology tools (Phobius | TMbed | SignalP 6) and the localisation tools (PSORTb | DeepSig), which carry phase 7's envelope call as extra columns. QUAST and GTDB-Tk describe the whole genome, so they stay out; the domain comes from <code>genome_info.tsv</code>.</p>",
			"<p>Each tool's columns get the tool's prefix (<code>COG_</code>, <code>PFAM_</code> and so on), and the gene's coordinates, lengths and sequences come from the gene caller's row. When a tool reports several rows for one gene, they join into one cell as <code>key: value</code> pairs, keyed by accession for database hits or by start–end range for segment tools such as TMbed. A tool's columns are filled for the genes it hit and left empty for the rest, so each genome's table has the same shape. KEGG keeps only rows above KofamScan's threshold, and the merge stops when a tool's gene ids come from a different RASTtk submission.</p>",
			"<p>The step writes <code>consolidated-merged-all-columns.tsv</code> (each column kept) and <code>consolidated-no-stat.tsv</code> (identity, ids, descriptions and core topology and localisation calls, with the statistics left out), with the detected columns and a manifest of the tables read. Both tables load into the MARGIE database, and labeling reads the merged one. The scripts are on <a href=\"/code?file=consolidation/merge-all-columns.py\">Code</a>.</p>"
		],
		"refs": [
			"brettin2015",
			"hyatt2010",
			"jones2014",
			"pedruzzi2015",
			"li2021",
			"wang2023",
			"wu2004",
			"su2024",
			"kall2004",
			"bernhofer2022",
			"teufel2022",
			"yu2010",
			"savojardo2018",
			"aramaki2020",
			"gurevich2013",
			"chaumeil2022"
		],
		"code": [
			{
				"path": "margie_sb.smk",
				"symbol": "rule:run_consolidation",
				"why": "Runs the three consolidation scripts for one genome after phases 4 to 8."
			},
			{
				"path": "consolidation/_shared.py",
				"symbol": "discover_tool_tables",
				"why": "Finds each tool's results table in the genome folder and leaves out genome-level steps."
			},
			{
				"path": "consolidation/merge-all-columns.py",
				"symbol": "merge_rows_for_gene",
				"why": "Joins one tool's several rows for a gene into keyed cells."
			}
		],
		"thesis": true
	},
	{
		"id": "informative",
		"group": "Inside the pipeline",
		"q": "How does MARGIE decide whether a gene's description is informative or uninformative?",
		"a": [
			"<p>MARGIE asks of each description whether it names a function. One rule set, <code>is_uninformative</code>, serves labeling, C1 and the operon reference (each keeps a copy of the same lists). It lower-cases the text and calls it uninformative when one of these holds, checked in this order:</p>",
			"<table><thead><tr><th>Rule</th><th>Examples</th></tr></thead><tbody><tr><td>Empty or a placeholder</td><td>\"\" | - | . | NA | none | null</td></tr><tr><td>Exactly a boilerplate phrase</td><td>hypothetical protein | conserved hypothetical protein | conserved protein | predicted protein | putative | unknown | uncharacterized | function unknown | general function prediction only | poorly characterized | open reading frame</td></tr><tr><td>Starts with an unknown-function phrase</td><td>domain, protein, family, region, repeat or module of unknown function | DUF | UPF | uncharacteri… | hypothetical | unknown protein | ORF</td></tr><tr><td>Contains \"hypothetical\" or \"protein conserved in bacteria\"</td><td>FIG00001: hypothetical protein</td></tr><tr><td>Matches an unknown-function pattern</td><td>membrane protein of unknown function | Belongs to the UPF0234 family | eggNOG's Psort location … | a bare DUF4440 domain | protein containing domains DUF… | integral membrane protein (exactly)</td></tr><tr><td>Lacks a function word (…ase, transport, bind, synth, subunit, regulator and others) and contains \"of unknown function\" or \"uncharacterised\", or is \"conserved protein\" plus a locus tag</td><td>conserved protein YbgC</td></tr></tbody></table>",
			"<p>The operon reference first strips source tags such as <code>JCVI:</code> or <code>Pfam:</code> and keeps the readable side of a <code>raw ## readable</code> label. Anything else counts as informative.</p>",
			"<table><thead><tr><th>Step</th><th>What follows</th></tr></thead><tbody><tr><td>Labeling</td><td>Within a tool, an informative lower-ranked hit is preferred to an uninformative top hit. A tool sets the label only when its best hit is informative, except Pfam, whose DUF hits also qualify. Otherwise, the first description of any kind is used; a gene the tools leave undescribed is labelled \"No DB hits\".</td></tr><tr><td>Consolidation</td><td>Each hit stays in the merged table.</td></tr><tr><td>C1</td><td>A source counts only when its best-hit description is informative, so a gene known only as hypothetical scores 0/7.</td></tr><tr><td>Operon reference</td><td>Only informative labels enter; an operon counts only when informative members outnumber uninformative ones, and an adjacency pair with an uninformative member is skipped.</td></tr><tr><td>C3</td><td>An uninformative gene in an operon takes the operon's value; an operon made only of uninformative genes gets 0.5.</td></tr><tr><td>Fingerprints</td><td>Each gene gets one, informative or uninformative, with its label recorded.</td></tr></tbody></table>"
		],
		"refs": [
			"cantalapiedra2021",
			"mistry2021",
			"brettin2015"
		],
		"code": [
			{
				"path": "labeling/assign-canonical-label.py",
				"symbol": "is_uninformative",
				"why": "The word lists and patterns that mark a description as naming no function."
			},
			{
				"path": "scoring/score-c1-tool-coverage.py",
				"symbol": "compute_c1",
				"why": "Counts a C1 source only when its best-hit description is informative."
			},
			{
				"path": "scoring/c3_occ.py",
				"symbol": "_accumulate_organism",
				"why": "The informative-majority gate for operons entering the reference."
			}
		],
		"thesis": true
	},
	{
		"id": "labeling",
		"group": "Inside the pipeline",
		"q": "How is labeling done? What is the principle behind deriving the product descriptors?",
		"a": [
			"<p>Labeling is phase 10. It gives each gene one product descriptor, the <code>best_consensus_product_descriptor</code>, taken from what the annotation tools reported. The label is one tool's hit description, taken as the tool wrote it (the hit's accession when the description is empty), and the other tools' evidence stays beside it in the same row, so the label can be checked against them.</p>",
			"<p>The principle is a fixed trust hierarchy that runs from the most narrowly curated evidence down to the broadest: curated prokaryotic family models (PGAP | NCBIfam | TIGRFAM), then family rules, whole-protein families and reviewed proteins (HAMAP | PIRSF | UniProt Swiss-Prot), then orthology (KEGG | eggNOG), RASTtk's subsystem names, domain models (Pfam | CDD) and COG. The label comes from the first tool in that order whose best hit is informative and passes its gate. A description of unknown function, such as hypothetical protein or a DUF, is passed over, so a top-ranked tool that reports only an unnamed protein leaves the label to a lower-ranked tool with a real name.</p>",
			"<p>Only UniProt is gated at this step (identity at least 40%); the other tools applied their own cutoffs when they searched. MEROPS | TCDB | dbCAN cover narrow groups of proteins, so they confirm the label that the hierarchy sets. Labeling then adds the EC consensus across tools, the gene's operon context and the agreement within the TIGRFAM family cluster, which scoring reads. The steps are set out under how a label is derived, and on <a href=\"/methods\">Methods</a>.</p>"
		],
		"refs": [
			"li2021",
			"haft2013",
			"pedruzzi2015",
			"wu2004",
			"uniprot2025",
			"kanehisa2023",
			"aramaki2020",
			"huertacepas2019",
			"cantalapiedra2021",
			"brettin2015",
			"overbeek2014",
			"mistry2021",
			"wang2023",
			"galperin2025",
			"rawlings2018",
			"saier2021",
			"zheng2023",
			"jones2014",
			"paysanlafosse2023"
		],
		"code": [
			{
				"path": "labeling/assign-canonical-label.py",
				"symbol": "_EVALUATORS",
				"why": "The trust hierarchy: the tools in the order labeling tries them."
			},
			{
				"path": "labeling/assign-canonical-label.py",
				"symbol": "select_best_hit",
				"why": "Takes a tool's best-ranked informative hit over an uninformative top hit."
			},
			{
				"path": "labeling/assign-canonical-label.py",
				"symbol": "build_confirmatory_summary",
				"why": "Compares MEROPS, TCDB and dbCAN hits with the label without letting them set it."
			}
		],
		"thesis": true
	},
	{
		"id": "label-derivation",
		"group": "Inside the pipeline",
		"q": "How is a gene's label (best consensus product descriptor) derived, step by step?",
		"a": [
			"<p>Labeling reads the consolidated table and, for each gene, works through these steps:</p>",
			"<ol><li>Each decision tool's hits are read from the merged cells: ids, descriptions and the ranking statistic (the e-value; percent identity for UniProt).</li><li>Within each tool the hits are ranked and the best informative one is taken; when the top hit is of unknown function, a lower-ranked hit that names one is used, and the gate note records the swap.</li><li>The tool qualifies when that hit is informative and passes its gate.</li><li>Pass 1: the label comes from the first qualifying tool in the order below.</li><li>Pass 2: otherwise, the first tool with any description supplies it, and a gene the tools leave undescribed is labelled \"No DB hits\".</li><li>The label (up to 200 characters), its source and accession, the hierarchy walked and an audit trail tagging each tool (winner | no_hit | uninformative | gate_failed | available_but_lower_priority) are written to <code>labeled-genes.tsv</code>, with each tool's full and best hits.</li><li>MEROPS | TCDB | dbCAN are compared with the label by shared words and reported as possible agreement or as needing review.</li></ol>",
			"<table><thead><tr><th>Order</th><th>Source</th><th>What it contributes</th><th>When it is used</th></tr></thead><tbody><tr><td>1 (tier 1)</td><td>PGAP HMMs</td><td>curated prokaryotic family name (trusted cutoffs)</td><td>first informative hit</td></tr><tr><td>2 (tier 1)</td><td>NCBIfam, through InterPro</td><td>curated family name</td><td>next in line after 1</td></tr><tr><td>3 (tier 1)</td><td>TIGRFAM</td><td>curated family name (trusted cutoffs)</td><td>next in line after 1–2</td></tr><tr><td>4 (tier 2)</td><td>HAMAP, through InterPro</td><td>family rule name</td><td>next in line after tier 1</td></tr><tr><td>5 (tier 2)</td><td>PIRSF, through InterPro</td><td>whole-protein family name</td><td>next in line after 1–4</td></tr><tr><td>6 (tier 2)</td><td>UniProt Swiss-Prot</td><td>reviewed protein name, highest identity</td><td>identity at least 40%</td></tr><tr><td>7 (tier 3)</td><td>KEGG (KofamScan)</td><td>KEGG Orthology name, often with EC</td><td>rows above KofamScan's adaptive threshold</td></tr><tr><td>8 (tier 4)</td><td>eggNOG</td><td>orthologous group description</td><td>next in line after 1–7</td></tr><tr><td>9 (tier 5)</td><td>RASTtk</td><td>SEED subsystem product name</td><td>RASTtk genomes only</td></tr><tr><td>10 (tier 6)</td><td>Pfam</td><td>domain family name</td><td>qualifies even for a DUF hit</td></tr><tr><td>11 (tier 7)</td><td>CDD, through InterPro</td><td>conserved domain name</td><td>next in line after 1–10</td></tr><tr><td>12 (tier 8)</td><td>COG</td><td>COG description</td><td>next in line after 1–11</td></tr><tr><td>13 (tier 9)</td><td>Fallback</td><td>first description of any kind, else \"No DB hits\"</td><td>last, after 1–12</td></tr><tr><td>–</td><td>MEROPS | TCDB | dbCAN</td><td>peptidase, transporter and CAZyme evidence</td><td>reported beside the label to confirm it</td></tr></tbody></table>",
			"<p>The tiers match the <a href=\"/methods\">Methods</a> page; the code is <a href=\"/code?file=labeling/assign-canonical-label.py\">assign-canonical-label.py</a>.</p>"
		],
		"refs": [
			"li2021",
			"haft2013",
			"pedruzzi2015",
			"wu2004",
			"uniprot2025",
			"kanehisa2023",
			"aramaki2020",
			"huertacepas2019",
			"cantalapiedra2021",
			"brettin2015",
			"overbeek2014",
			"mistry2021",
			"wang2023",
			"galperin2025",
			"rawlings2018",
			"saier2021",
			"zheng2023",
			"jones2014",
			"paysanlafosse2023"
		],
		"code": [
			{
				"path": "labeling/assign-canonical-label.py",
				"symbol": "assign_label",
				"why": "Pass 1 takes the first qualifying tool; pass 2 the first with any description."
			},
			{
				"path": "labeling/assign-canonical-label.py",
				"symbol": "eval_uniprot",
				"why": "The one gate applied at labeling: UniProt identity of at least 40%."
			},
			{
				"path": "labeling/assign-canonical-label.py",
				"symbol": "build_audit_trail",
				"why": "Tags each tool's outcome for the gene's audit trail."
			}
		],
		"thesis": false
	},
	{
		"id": "envelope",
		"group": "Inside the pipeline",
		"q": "How does MARGIE infer the cell envelope type (monoderm or diderm), and how is it used?",
		"a": [
			"<p>Phase 7 infers one envelope type per genome, so that the localisation tools of phase 8 run with the right model. She reads the genome's TIGRFAM | PGAP | Pfam | UniProt results from phase 4 and looks in their descriptions and names for marker genes of each envelope architecture. Each hit counts towards the diderm or the monoderm side, a well-established marker more than a motif or a domain.</p>",
			"<table><thead><tr><th>Side</th><th>Marker group</th><th>Published basis</th></tr></thead><tbody><tr><td>Diderm</td><td>β-barrel assembly</td><td>Hagan et al., 2011; Konovalova et al., 2017</td></tr><tr><td>Diderm</td><td>lipid A and LPS synthesis</td><td>Raetz et al., 2007</td></tr><tr><td>Diderm</td><td>LPS transport</td><td>Okuda et al., 2016; Sperandeo et al., 2017</td></tr><tr><td>Diderm</td><td>lipoprotein trafficking</td><td>Grabowicz, 2018</td></tr><tr><td>Diderm</td><td>outer-membrane proteins</td><td>Silhavy et al., 2010</td></tr><tr><td>Monoderm</td><td>wall teichoic acid</td><td>Brown et al., 2013</td></tr><tr><td>Monoderm</td><td>lipoteichoic acid</td><td>Percy &amp; Gründling, 2014</td></tr><tr><td>Monoderm</td><td>D-alanylation</td><td>Neuhaus &amp; Baddiley, 2003</td></tr><tr><td>Monoderm</td><td>sortase anchoring</td><td>Mazmanian et al., 1999; Spirig et al., 2011</td></tr><tr><td>Monoderm</td><td>mycolic acid (actinobacteria)</td><td>Marrakchi et al., 2014; Portevin et al., 2004</td></tr><tr><td>Monoderm</td><td>pili and surface layer</td><td>–</td></tr></tbody></table>",
			"<p>The first rule that applies decides the type:</p><ol><li>A genome whose domain is Archaea (genome table or GTDB-Tk) is archaeal.</li><li>Several high-confidence markers of one side, with zero from the other, decide that side.</li><li>Otherwise the side with more weighted evidence wins.</li><li>A tie, or zero markers, gives the conservative default, diderm.</li></ol>",
			"<ol><li>Evidence: marker hits from TIGRFAM | PGAP | Pfam | UniProt, and the genome's domain.</li><li>Rule: the steps above, in order.</li><li>Envelope type: one row in <code>envelope_summary.tsv</code> with the type, its basis and the evidence.</li><li>Localisation model: PSORTb runs with <code>-k n | p | a</code> and DeepSig with <code>-k GRAM- | GRAM+ | ARCH</code>; an unknown type takes the diderm model.</li><li>The three <code>ENVELOPE_</code> columns are added to each localisation table before loading, and consolidation carries them into each gene's row.</li></ol>",
			"<p>Phobius | TMbed | SignalP 6 run with the same model for each genome, whatever its envelope. A genome with zero marker hits, such as a wall-less one, gets the diderm default with basis <code>default_no_evidence</code>, so its localisation calls can be read with that in mind.</p>"
		],
		"refs": [
			"hagan2011",
			"konovalova2017",
			"raetz2007",
			"okuda2016",
			"sperandeo2017",
			"grabowicz2018",
			"silhavy2010",
			"brown2013",
			"percy2014",
			"neuhaus2003",
			"mazmanian1999",
			"spirig2011",
			"marrakchi2014",
			"portevin2004",
			"albers2011",
			"li2021",
			"haft2013",
			"mistry2021",
			"uniprot2025",
			"chaumeil2022",
			"yu2010",
			"savojardo2018",
			"kall2004",
			"bernhofer2022",
			"teufel2022"
		],
		"code": [
			{
				"path": "margie_sb.smk",
				"symbol": "rule:run_envelope",
				"why": "Runs the envelope inference on the phase 4 marker tables and the genome's domain."
			},
			{
				"path": "margie_sb.smk",
				"symbol": "rule:run_psortb",
				"why": "Maps the envelope type to PSORTb's model (-k n, p or a)."
			},
			{
				"path": "enrich_with_envelope.py",
				"symbol": "main",
				"why": "Adds the genome's ENVELOPE_ columns to a localisation table before loading."
			}
		],
		"thesis": true
	},
	{
		"id": "operons",
		"group": "Inside the pipeline",
		"q": "How are operons called? Which tool, and is anything changed from the original tool?",
		"a": [
			"<p>Phase 5 predicts operons with UniOP, an unsupervised model that estimates, for each pair of neighbouring genes, the probability that they belong to one operon from the intergenic distance in the genome itself; it works from the gene positions alone. MARGIE runs it on the phase 3 gene calls (RASTtk's <code>rast.faa</code> and <code>rast.gff</code>, or Prodigal's <code>prodigal.faa</code> and <code>prodigal.gff</code>).</p>",
			"<p>MARGIE runs UniOP as published: the container holds the upstream code at a pinned commit (68c55d2, 30 May 2025), copied verbatim, as the licence catalogue records. MARGIE's changes sit around it. The gene calls are rewritten into the Prodigal-style protein headers (contig, start, end, strand) that UniOP reads, UniOP runs with its operon output on, and a post-processing step writes one row per gene: the operon id (<code>operon_XXXX</code> or <code>NOT_IN_AN_OPERON</code>), its size and the gene's position, the upstream and downstream partners with their pairwise probabilities, and an operon-level probability, the geometric mean of the adjacent-pair probabilities. UniOP reads protein-coding genes only, and RNA genes are marked <code>NOT_APPLICABLE_NON_CODING</code>.</p>",
			"<p>Labeling joins this table to each gene. C2 is the mean of the gene's one or two pairwise probabilities, with 0.5 for single genes, and the operons feed the operon reference that C3 scores against and the operon fingerprints.</p>"
		],
		"refs": [
			"su2024",
			"brettin2015",
			"hyatt2010"
		],
		"code": [
			{
				"path": "margie_sb.smk",
				"symbol": "rule:run_operon",
				"why": "Runs the UniOP container on the genome's gene calls."
			},
			{
				"path": "labeling/add-operon-info.py",
				"symbol": "parse_operon_probability",
				"why": "Reads the operon-level geometric mean from UniOP's processed table."
			},
			{
				"path": "scoring/score-c2-operon-probability.py",
				"symbol": "compute_c2",
				"why": "Turns a gene's pairwise UniOP probabilities into C2."
			}
		],
		"thesis": true
	},
	{
		"id": "fingerprints",
		"group": "Inside the pipeline",
		"q": "What is a fingerprint, how is it made, and what types are there?",
		"a": [
			"<p>A fingerprint is a short hash that stands for a gene's evidence pattern: which accessions and descriptions the tools reported for it. Genes with the same pattern, in one genome or in two, get the same fingerprint, so MARGIE can count how often a pattern, and the label it led to, recur across annotated genomes by comparing short hashes.</p>",
			"<p><b>Gene fingerprints.</b> After scoring, MARGIE writes for each gene a fixed list of slots joined by \" | \": the RASTtk description, then the id and description lists of 14 tools in the trust hierarchy's order (PGAP | TIGRFAM | HAMAP | NCBIfam | PIRSF | UniProt | Pfam | CDD | KEGG | eggNOG | COG | MEROPS | TCDB | dbCAN). Empty slots stay, so a slot's position keeps its meaning. The string is hashed with SHA-256 and the first 16 hex characters are the pattern hash. Five views are written: hash with pattern, hash with label, label with pattern, the full record, and the full record with C1 to C4 and the confidence.</p>",
			"<p><b>Operon fingerprints.</b> For each operon, the members' gene hashes and labels in genomic order give four hashes: by evidence, ordered | by evidence, composition | by label, ordered | by label, composition. Evidence hashes match operons with the same tool hits, label hashes match operons whose members carry the same labels across species, and composition hashes ignore gene order. Only genes in an operon get them. The final annotated table reports how often a gene's pattern, its label and its operon's label patterns occur in the fingerprint databases.</p>"
		],
		"refs": [
			"fips180",
			"li2021",
			"haft2013",
			"pedruzzi2015",
			"wu2004",
			"uniprot2025",
			"mistry2021",
			"wang2023",
			"aramaki2020",
			"cantalapiedra2021",
			"galperin2025",
			"rawlings2018",
			"saier2021",
			"zheng2023",
			"brettin2015"
		],
		"code": [
			{
				"path": "fingerprint/add-gene-fingerprint.py",
				"symbol": "build_fingerprint_values",
				"why": "Builds the fixed-slot evidence string for one gene."
			},
			{
				"path": "fingerprint/add-gene-fingerprint.py",
				"symbol": "_hash16",
				"why": "Hashes the string with SHA-256 and keeps the first 16 hex characters."
			},
			{
				"path": "fingerprint/add-operon-fingerprint.py",
				"symbol": "main",
				"why": "Builds the four operon hashes from the members' gene hashes and labels."
			}
		],
		"thesis": false
	},
	{
		"id": "pool-databases",
		"group": "Databases and provenance",
		"q": "How are the operon database and the fingerprint database created, and what does that imply?",
		"a": [
			"<p>MARGIE builds two shared pools from the genomes she annotates: the operon reference, which C3 scores against, and the fingerprint databases. Both sit in your store folder on the cluster and grow one genome at a time, each update under an exclusive file lock.</p>",
			"<p><b>Operon reference.</b> Before a genome is scored, its labeled operons are added. Only informative labels count, and only operons where informative members outnumber uninformative ones. MARGIE records which genomes carry each label, which label pairs share an operon (membership) and which are consecutive informative neighbours on one contig (adjacency). The counts are additive, so scoring subtracts the genome being scored, matched by a hash of its proteins, and works from the rest. A pair's reliability is the Jeffreys posterior mean (k + ½)/(n + 1), with k the genomes where the pair shares an operon and n the genomes carrying both labels, times an enrichment weight lift/(lift + 1) against the pairing expected from each label's abundance. A fresh install starts from a shipped reference of 29 genomes.</p>",
			"<p><b>Fingerprint databases.</b> <code>fingerprint-database.tsv</code> counts, for each gene pattern hash, its genes, genomes and label, numbering patterns as they first appear; four operon pools do the same for operon hashes, counting each distinct operon once.</p>",
			"<p>So C3 and the frequency columns depend on the pools at scoring time: scoring runs fresh each time, and an early genome can be scored again against a larger pool. Lineages new to the pools get little context, which is why C3 only raises a score, and since labels are the identity, the pools inherit labeling's choices. See <a href=\"/methods/scores\">Reading the scores</a>.</p>"
		],
		"refs": [
			"jeffreys1946",
			"newman2006",
			"su2024",
			"fips180"
		],
		"code": [
			{
				"path": "scoring/c3_occ.py",
				"symbol": "_accumulate_organism",
				"why": "Adds one genome's qualifying operons to the reference counts in both channels."
			},
			{
				"path": "scoring/c3_score_organism.py",
				"symbol": "rho_adj_mean",
				"why": "A pair's reliability: the Jeffreys posterior mean times the enrichment weight."
			},
			{
				"path": "fingerprint/update-fingerprint-database.py",
				"symbol": "_do_update",
				"why": "Merges one genome's gene patterns into the shared fingerprint database."
			}
		],
		"thesis": true
	},
	{
		"id": "growth",
		"group": "Databases and provenance",
		"q": "How does MARGIE grow with each genome annotated? Which databases grow? What are the MARGIE-generated databases?",
		"a": [
			"<p>MARGIE keeps what each genome adds, so later genomes cost less to annotate and are scored against more context. These stores grow:</p>",
			"<ul><li><b>The MARGIE database</b> (SQLite): each tool's result rows, the genome-level output cache, the protein-level cache and the run log.</li><li><b>The operon reference</b>: label and label-pair counts per genome, which C3 scores against.</li><li><b>The fingerprint databases</b>: one for gene fingerprints and four for operon fingerprints.</li><li><b>Records</b>: each run's scores in the scoring archive, the latest final table per genome in final-tables, and a copy of the MARGIE database for each pipeline version.</li></ul>",
			"<p>The MARGIE-generated databases are the operon reference and the fingerprint databases, with a genome pool kept for the genome-comparison phase being worked on. The tools' reference databases, such as Pfam or GTDB, are downloaded at a fixed release and stay at it. The operon reference ships as a starter built from 29 genomes; where a group keeps base copies in its shared folder, a new account starts from them and its own copies grow.</p>",
			"<p>In practice, a genome run again comes back from the genome-level cache; a new genome that shares proteins with earlier ones sends only its new proteins to each per-protein tool; and each scored genome adds operon pairs that later genomes can match. Scoring and fingerprinting run fresh each time because they read the pools as they stand, and the reference's size at scoring is recorded for Results.</p>"
		],
		"refs": [
			"sqlite",
			"fips180",
			"su2024",
			"mistry2021",
			"parks2020"
		],
		"code": [
			{
				"path": "scoring/update-occ-reference-depot.py",
				"symbol": "main",
				"why": "Adds one genome to the operon reference under a file lock, seeding it from the starter."
			},
			{
				"path": "protein_cache.py",
				"symbol": "store",
				"why": "Keeps a genome's newly annotated proteins for later genomes."
			},
			{
				"path": "output_cache.py",
				"symbol": "store",
				"why": "Stores a genome's step outputs in the MARGIE database under its genome hash."
			}
		],
		"thesis": true
	},
	{
		"id": "sqlite",
		"group": "Databases and provenance",
		"q": "How does the main SQLite MARGIE database work?",
		"a": [
			"<p>The MARGIE database is one SQLite file, named by <code>main_database</code> in your config (Settings) and kept in your own storage on the cluster. Results, caches and provenance share the file, so copying it carries them along.</p>",
			"<ul><li><b>Result tables</b>: one per tool and per MARGIE step (for example <code>cog</code>, <code>interpro_ncbifam</code>, <code>consolidation_merged</code>, <code>labeling_labeled</code>, <code>scoring_confidence_final</code>), loaded from each step's TSV with column types inferred from the first rows. New columns are added as tools change, and rows carry an indexed <code>organism_name</code>.</li><li><b>run_log</b>: one row per load (the results file's hash, tool, row count, genome hash, pipeline version) and one per genome run (rules completed, status).</li><li><b>output_cache</b>: a genome's step outputs stored as files, under genome hash, step and file name.</li><li><b>protein_cache</b>: each protein's result rows per tool, under protein hash and tool key.</li><li><b>api_jobs</b>: the site's job history.</li></ul>",
			"<p>Each load rule hashes its results file. If that genome and tool were already loaded at the current pipeline version, the load is skipped and its token written; otherwise the genome's earlier rows are deleted, under any name it was loaded as, and the new rows inserted. Scoring tables reload on each run. Loads within a run take turns, wait up to 120 seconds for the file's lock and retry, which suits SQLite on shared network storage. Once scoring is done, a SLURM job copies the file into a snapshot folder named by pipeline version.</p>"
		],
		"refs": [
			"sqlite",
			"fips180"
		],
		"code": [
			{
				"path": "load_to_db.py",
				"symbol": "load_csv_to_db",
				"why": "Creates or extends a tool's table from its TSV and inserts the rows."
			},
			{
				"path": "load_to_db.py",
				"symbol": "_already_loaded",
				"why": "Skips a load already recorded for this genome, tool and pipeline version."
			},
			{
				"path": "output_cache.py",
				"symbol": "CREATE_OUTPUT_CACHE_SQL",
				"why": "The table that keeps a genome's step outputs under its hash."
			}
		],
		"thesis": false
	},
	{
		"id": "provenance",
		"group": "Databases and provenance",
		"q": "How does MARGIE record provenance? What do the processed tables carry to trace it?",
		"a": [
			"<p>MARGIE keeps a <code>run_log</code> table in her database. Each load of a step's table adds a row: a run id | the table name | a SHA-256 hash of the file | the genome's sequence hash | the organism | the row count | the pipeline version | the UTC time | the status. The pipeline version (<code>PIPELINE_VERSION</code> in <code>load_to_db.py</code>) changes when a change to consolidation, labeling or scoring makes stored rows out of date, so a genome is loaded again and its older rows replaced. Scoring rows are replaced on each run, because the operon pool they are scored against grows.</p>",
			"<p>The processed tables carry their own trail. A tool's table has, on each row, <code>&lt;TOOL&gt;_tool_used</code> (the tool and its version) | <code>&lt;TOOL&gt;_command_used</code> (the command and its settings) | <code>&lt;TOOL&gt;_database_used</code> (the database and where it came from), and consolidation keeps these columns as they are. Labeling adds the label's source and accession (<code>product_descriptor_source</code> | <code>product_descriptor_source_id</code>), the tool chain it walked (<code>product_descriptor_hierarchy</code>) and an audit trail that tags each decision tool WINNER | no_hit | uninformative | gate_failed | available_but_lower_priority.</p>",
			"<p>Scoring writes a formula and a reason beside C1 to C4 and the final confidence, and notes how many genomes of the operon pool a genome was scored against and whether it was left out of the pool. For reused results, <b>cache-report.tsv</b> says, for each genome and step, whether it ran fresh or was restored, and from which cache level.</p>"
		],
		"refs": [
			"molder2021"
		],
		"code": [
			{
				"path": "load_to_db.py",
				"symbol": "CREATE_RUN_LOG_SQL",
				"why": "The run_log table that records each load."
			},
			{
				"path": "load_to_db.py",
				"symbol": "_record_load",
				"why": "Writes one run_log row with the file hash, genome hash, pipeline version and UTC time."
			},
			{
				"path": "labeling/assign-canonical-label.py",
				"symbol": "build_audit_trail",
				"why": "Builds the per-gene audit trail of each decision tool's outcome."
			}
		],
		"thesis": false
	},
	{
		"id": "scoring",
		"group": "Scoring",
		"q": "How does scoring work?",
		"a": [
			"<p>MARGIE gives each protein-coding gene's label a confidence from 0 to 1 in two stages. The first stage uses the gene's own evidence: how many independent sources give it an informative hit (C1), lowered only when the EC numbers from different tools conflict (C4). The second stage adds operon context: how likely the gene is to share an operon with its neighbours (C2, from UniOP), times how well its operon partnerships recur in other genomes (C3).</p>",
			"<pre>preliminary = C1 × C4\ncontext     = C2 × C3   for a gene in an operon of two or more, else 0\nfinal       = clip(preliminary + context, 0, 1)</pre>",
			"<p>Context only adds, so a gene outside an operon, or in an operon unique to its genome, keeps the score of its own evidence. The final score sets the tier: highest above 0.9 | high above 0.7 | medium above 0.5 | fair above 0.3 | low otherwise. A gene is flagged for review when its EC numbers conflict | its final score is below 0.5 | it sits in an operon with C2 below 0.5 | half or more of its operon's adjacent pairs involve an uncharacterised protein and context added 0. Scoring covers the protein-coding genes.</p>",
			"<p>Beside the default, MARGIE writes a second final score and tier from the hybrid C3. Each part comes with its formula and reasoning in <b>FINAL_ANNOTATION_WITH_CONFIDENCE.tsv</b>. Per-gene confidence from cross-genome and gene-neighbourhood evidence has earlier forms (Yang et al., 2010; Jun et al., 2017); she reports the four parts separately. See <a href=\"/methods\">Methods</a> and <a href=\"/methods/scores\">Reading the scores</a>.</p>"
		],
		"refs": [
			"yang2010",
			"jun2017",
			"su2024"
		],
		"code": [
			{
				"path": "margie_sb.smk",
				"symbol": "rule:run_scoring",
				"why": "Runs the scoring scripts in order for one genome."
			},
			{
				"path": "scoring/score-confidence-final.py",
				"symbol": "main",
				"why": "Computes the preliminary and final scores, the hybrid final and the review flags."
			},
			{
				"path": "scoring/score-confidence-final.py",
				"symbol": "confidence_score_tier",
				"why": "Maps the final score to its tier."
			}
		],
		"thesis": true
	},
	{
		"id": "components",
		"group": "Scoring",
		"q": "What are the components of the scoring system, and how are they wired together?",
		"a": [
			"<p>The <code>run_scoring</code> rule runs one script per component, and the final step joins them on each gene's feature id.</p>",
			"<ul><li><b>C1, tool coverage</b>: informative sources / 7, over RASTtk | COG | Pfam | KEGG | eggNOG | UniProt | one TIGRFAM slot that TIGRFAM, PGAP and NCBIfam share. A \"hypothetical protein\" hit counts for 0.</li><li><b>C2, operon probability</b>: the mean of the gene's UniOP pairwise probabilities to its upstream and downstream neighbours; 0.5 for a single gene or a member with a missing value.</li><li><b>C3, operon context</b>: how well the gene's operon partnerships recur across the operon pool, with its own genome left out; 0.5 for a single gene.</li><li><b>C4, EC agreement</b>: 1 − (m/5)·R, where m of the five EC sources (eggNOG | RASTtk | KEGG | dbCAN | TCDB) report an EC number and R is the share of their tool pairs whose EC sets conflict. A wildcard such as 1.2.3.- matches the numbers below it. Zero or one EC source gives 1.</li></ul>",
			"<p>Before C3 runs, a separate rule adds the genome to the operon pool. C1 × C4 is the preliminary score, the gene's own evidence; C2 then scales C3 into the context term, so conserved context lifts a gene only when it lies in an operon, in proportion to UniOP's probability. A categorical tier, from the label's place in the trust hierarchy and its EC agreement status, travels with C4 as provenance and stays out of the 0 to 1 score.</p>"
		],
		"refs": [
			"brettin2015",
			"galperin2025",
			"mistry2021",
			"aramaki2020",
			"cantalapiedra2021",
			"uniprot2025",
			"haft2013",
			"li2021",
			"su2024",
			"zheng2023",
			"saier2021"
		],
		"code": [
			{
				"path": "scoring/score-c1-tool-coverage.py",
				"symbol": "compute_c1",
				"why": "Counts the informative sources over seven slots."
			},
			{
				"path": "scoring/score-c2-operon-probability.py",
				"symbol": "compute_c2",
				"why": "Averages the UniOP pairwise probabilities, with the 0.5 fallback."
			},
			{
				"path": "scoring/score-c4-ec-agreement.py",
				"symbol": "c4_clearance",
				"why": "Turns the EC conflict fraction into C4 = 1 − (m/5)·R."
			}
		],
		"thesis": true
	},
	{
		"id": "c3",
		"group": "Scoring",
		"q": "How does C3 work, in detail?",
		"a": [
			"<p>C3 asks whether a gene's operon partnerships recur in other genomes. MARGIE keeps an operon pool of additive counts over the genomes annotated so far: which pairs of labels share an operon, and which sit side by side. She counts only qualifying operons, where informative members outnumber uninformative ones, and uses each gene's cleaned consensus label as its identity. The pool starts from a 29-genome reference shipped with MARGIE (<code>operon-db.pkl</code>), and a rule adds each annotated genome to it before scoring.</p>",
			"<p>For a pair of labels the pool gives n, the genomes in which both labels occur in qualifying operons, and k, the genomes in which the pair shares an operon (or is adjacent). The pair's reliability ρ is the Jeffreys posterior mean (k + ½)/(n + 1) (Jeffreys, 1946) times an enrichment weight that discounts chance pairings of common labels (Newman, 2006). The adjacency C3, the default, is the geometric mean of ρ over the operon's supported adjacent pairs, shared by its members; the hybrid C3 is a gene's strongest single partner, adjacent or anywhere in its operon.</p>",
			"<p>Before scoring, MARGIE subtracts the genome's own counts from the pool (leave-one-out), matched by a SHA-256 fingerprint of its proteins, so C3 is an out-of-sample estimate. A single gene, a non-coding feature or an operon made only of hypothetical proteins gets 0.5; an operon with zero supported pairs gets 0. The 95% Jeffreys lower bound (Brown et al., 2001) is written beside each score for reference only; see <a href=\"/code?file=scoring/c3_score_organism.py\">c3_score_organism.py</a>.</p>"
		],
		"refs": [
			"jeffreys1946",
			"bayes1763",
			"brown2001",
			"newman2006",
			"su2024"
		],
		"code": [
			{
				"path": "scoring/c3_score_organism.py",
				"symbol": "compute",
				"why": "Scores each gene's adjacency and hybrid C3, with the neutral and zero cases."
			},
			{
				"path": "scoring/c3_occ.py",
				"symbol": "_accumulate_organism",
				"why": "Adds one genome's qualifying operons to the pool counts."
			},
			{
				"path": "scoring/c3_occ.py",
				"symbol": "subtract_organism",
				"why": "Removes the scored genome's counts for leave-one-out."
			}
		],
		"thesis": true
	},
	{
		"id": "c3-channels",
		"group": "Scoring",
		"q": "What are the adjacency and co-occurrence (membership) metrics in C3?",
		"a": [
			"<p>MARGIE reads an operon in two ways. In the <b>membership</b> (co-occurrence) channel, two informative genes form a pair when they share a qualifying operon at any distance: an operon with s informative labels gives s(s − 1)/2 pairs, each counted once per operon. In the <b>adjacency</b> channel, they form a pair only when they are consecutive genes on the same contig and both informative, so a hypothetical gene between them breaks the link. An adjacent pair is also a membership pair, so k(adjacent) ≤ k(membership) ≤ n for any pair of labels.</p>",
			"<p>The channels keep separate counts, degrees and totals, and give two scores:</p>",
			"<pre>C3 adjacency = geometric mean of ρ_adj over the operon's supported adjacent pairs\nC3 hybrid    = max(best ρ_adj to an adjacent gene, best ρ_op to any co-member)</pre>",
			"<p>The adjacency score belongs to the operon: its members, hypothetical ones included, take the same value, and only pairs that UniOP links are used. The hybrid score belongs to the gene and is order-free, so it holds when gene order changes, which is common between prokaryotic genomes (Itoh et al., 1999; Tamames, 2001), or when a hypothetical gene breaks the chain. In the hybrid score an informative gene with zero supported partners gets 0, and a hypothetical member takes the mean of its operon's informative members. Adjacency is the default; the hybrid score and its tier are written beside it.</p>"
		],
		"refs": [
			"itoh1999",
			"tamames2001",
			"su2024"
		],
		"code": [
			{
				"path": "scoring/c3_occ.py",
				"symbol": "_accumulate_organism",
				"why": "Counts the membership and adjacency pairs of a genome's qualifying operons."
			},
			{
				"path": "scoring/c3_score_organism.py",
				"symbol": "compute",
				"why": "Builds the adjacency geometric mean and the hybrid per-gene maximum."
			},
			{
				"path": "scoring/c3_score_organism.py",
				"symbol": "geomean",
				"why": "The geometric mean used for the adjacency score."
			}
		],
		"thesis": true
	},
	{
		"id": "bayes",
		"group": "Scoring",
		"q": "What is the Bayesian analysis of operonic gene pairs? What is the Jeffreys posterior? How is Newman's network (configuration) model used?",
		"a": [
			"<p>For a pair of labels (a, b), the operon pool gives n, the genomes in which both labels occur in qualifying operons, and k, the genomes in which the pair shares an operon (or, in the adjacency channel, sits side by side). The raw share k/n is coarse when n is small: one genome gives only 0 or 1. MARGIE treats each genome as a yes/no trial with an unknown rate θ, starts from the Jeffreys prior Beta(½, ½) (Jeffreys, 1946) and updates it with the counts (Bayes, 1763; Laplace, 1812):</p>",
			"<pre>posterior   = Beta(k + ½, n − k + ½)\nmean        = (k + ½) / (n + 1)\nlower bound = 5% quantile of the posterior (reported for reference only)</pre>",
			"<p>One of one gives 0.75, nine of ten 0.86. Brown, Cai and DasGupta (2001) recommend the Jeffreys interval for small samples. A pair with k = 0 counts as zero evidence and is left out.</p>",
			"<p>Some functional classes, such as transcriptional regulators, are large and grow with genome size (Pérez-Rueda &amp; Collado-Vides, 2000; van Nimwegen, 2003), so their labels meet many partners by chance. MARGIE compares each pair's count with a configuration-model null, which keeps each label's number of partnerships (its degree) and joins them at random (Newman, 2006). With M partnerships in a channel:</p>",
			"<pre>expected E = deg(a) · deg(b) / 2M\nlift       = observed / E\nweight w   = lift / (lift + 1)\nρ          = mean × w</pre>",
			"<p>Here observed counts instances and k counts genomes. A pair seen as often as chance predicts gets w = 0.5; a pair of rare labels seen together gets w near 1.</p>"
		],
		"refs": [
			"jeffreys1946",
			"bayes1763",
			"laplace1812",
			"brown2001",
			"newman2006",
			"perezrueda2000",
			"vannimwegen2003"
		],
		"code": [
			{
				"path": "scoring/c3_score_organism.py",
				"symbol": "rho_adj_mean",
				"why": "The Jeffreys posterior mean (k+0.5)/(n+1) times the enrichment weight."
			},
			{
				"path": "scoring/c3_score_organism.py",
				"symbol": "_enrich_w",
				"why": "The configuration-null expectation, lift and weight lift/(lift+λ)."
			},
			{
				"path": "scoring/c3_occ.py",
				"symbol": "finalize_reference",
				"why": "Derives the Jeffreys lower bound times the weight for each pair."
			}
		],
		"thesis": true
	},
	{
		"id": "why-descriptors",
		"group": "Scoring",
		"q": "Why are only informative genes used? Why the descriptors and not amino-acid sequences?",
		"a": [
			"<p>C3 tests whether a gene's label sits in an operon context that recurs in other genomes, so it needs labels that name a function. A label such as \"hypothetical protein\" or \"domain of unknown function\" is shared by many unrelated proteins; counted as one identity, it would join genes of unrelated function. MARGIE marks a label uninformative with the same word lists and patterns that C1 uses (<code>is_uninformative</code>), builds the operon pool only from operons where informative members outnumber uninformative ones, and skips any pair with an uninformative member. Uninformative genes still get a C3: in the adjacency score they share their operon's value, in the hybrid score they take the mean of the operon's informative members, and an operon of hypothetical proteins only gets the neutral 0.5.</p>",
			"<p>C3 counts labels. A gene's identity in the pool is its consensus product descriptor from labeling, with leading source tags such as \"JCVI:\" or \"KEGG:\" removed and case ignored (<code>clean_descriptor</code>), so one function named through different sources groups together. The descriptor comes from the tools' best hits, picked by the trust hierarchy on <a href=\"/methods\">Methods</a>. Within C3, protein sequences serve only to recognise a genome for leave-one-out, through a SHA-256 fingerprint of its protein hashes. Earlier gene-neighbourhood studies grouped genes by sequence homology (Rogozin et al., 2002); C3 checks the label whose confidence it reports.</p>"
		],
		"refs": [
			"rogozin2002"
		],
		"code": [
			{
				"path": "scoring/c3_lib.py",
				"symbol": "is_uninformative",
				"why": "Decides whether a label names a function."
			},
			{
				"path": "scoring/c3_lib.py",
				"symbol": "clean_descriptor",
				"why": "Strips source tags so one function from different sources groups together."
			},
			{
				"path": "scoring/c3_occ.py",
				"symbol": "_accumulate_organism",
				"why": "Applies the informative-majority gate and skips pairs with an uninformative member."
			}
		],
		"thesis": true
	},
	{
		"id": "ecocyc",
		"group": "Scoring",
		"q": "How was MARGIE compared with EcoCyc?",
		"a": [
			"<p>EcoCyc is a curated database of <i>Escherichia coli</i> K-12 MG1655 that gathers the experimental knowledge of its genes, gene products, pathways and regulation (Keseler et al., 2017; Karp et al., 2023).</p>",
			"<p>MARGIE's confidence, the final 0 to 1 score and its tier described on <a href=\"/methods\">Methods</a>, was checked against EcoCyc's curated characterisation of the MG1655 genes. The comparison and its results are part of a thesis that is under embargo. They are in the locked part of this answer and on <a href=\"/methods/scores\">Reading the scores</a>, which opens with a password the lab gives on request.</p>"
		],
		"refs": [
			"keseler2017",
			"karp2023",
			"fawcett2006",
			"mann1947",
			"hanley1982"
		],
		"code": [
			{
				"path": "scoring/score-confidence-final.py",
				"symbol": "confidence_score_tier",
				"why": "The tiers the comparison counts genes by."
			}
		],
		"thesis": true
	}
];

export const REFS: Record<string, Ref> = {
	"albers2011": {
		"id": "albers2011",
		"apa": "Albers, S. V., & Meyer, B. H. (2011). The archaeal cell envelope. Nature Reviews Microbiology, 9(6), 414–426. https://doi.org/10.1038/nrmicro2576",
		"url": "https://doi.org/10.1038/nrmicro2576"
	},
	"apptainer": {
		"id": "apptainer",
		"apa": "Apptainer [Computer software]. (n.d.). Retrieved October 25, 2026, from https://apptainer.org/",
		"url": "https://apptainer.org/"
	},
	"aramaki2020": {
		"id": "aramaki2020",
		"apa": "Aramaki, T., Blanc-Mathieu, R., Endo, H., Ohkubo, K., Kanehisa, M., Goto, S., & Ogata, H. (2020). KofamKOALA: KEGG Ortholog assignment based on profile HMM and adaptive score threshold. Bioinformatics, 36(7), 2251–2252. https://doi.org/10.1093/bioinformatics/btz859",
		"url": "https://doi.org/10.1093/bioinformatics/btz859"
	},
	"aziz2008": {
		"id": "aziz2008",
		"apa": "Aziz, R. K., Bartels, D., Best, A. A., DeJongh, M., Disz, T., Edwards, R. A., Formsma, K., Gerdes, S., Glass, E. M., Kubal, M., Meyer, F., Olsen, G. J., Olson, R., Osterman, A. L., Overbeek, R. A., McNeil, L. K., Paarmann, D., Paczian, T., Parrello, B., … Zagnitko, O. (2008). The RAST Server: Rapid annotations using subsystems technology. BMC Genomics, 9, 75. https://doi.org/10.1186/1471-2164-9-75",
		"url": "https://doi.org/10.1186/1471-2164-9-75"
	},
	"bayes1763": {
		"id": "bayes1763",
		"apa": "Bayes, T. (1763). LII. An essay towards solving a problem in the doctrine of chances. By the late Rev. Mr. Bayes, F. R. S. communicated by Mr. Price, in a letter to John Canton, A. M. F. R. S. Philosophical Transactions of the Royal Society of London, 53, 370–418. https://doi.org/10.1098/rstl.1763.0053",
		"url": "https://doi.org/10.1098/rstl.1763.0053"
	},
	"bernhofer2022": {
		"id": "bernhofer2022",
		"apa": "Bernhofer, M., & Rost, B. (2022). TMbed: Transmembrane proteins predicted through language model embeddings. BMC Bioinformatics, 23, 326. https://doi.org/10.1186/s12859-022-04873-x",
		"url": "https://doi.org/10.1186/s12859-022-04873-x"
	},
	"brettin2015": {
		"id": "brettin2015",
		"apa": "Brettin, T., Davis, J. J., Disz, T., Edwards, R. A., Gerdes, S., Olsen, G. J., Olson, R., Overbeek, R., Parrello, B., Pusch, G. D., Shukla, M., Thomason, J. A., Stevens, R., Vonstein, V., Wattam, A. R., & Xia, F. (2015). RASTtk: A modular and extensible implementation of the RAST algorithm for building custom annotation pipelines and annotating batches of genomes. Scientific Reports, 5, 8365. https://doi.org/10.1038/srep08365",
		"url": "https://doi.org/10.1038/srep08365"
	},
	"brown2001": {
		"id": "brown2001",
		"apa": "Brown, L. D., Cai, T. T., & DasGupta, A. (2001). Interval estimation for a binomial proportion. Statistical Science, 16(2), 101–117. https://doi.org/10.1214/ss/1009213286",
		"url": "https://doi.org/10.1214/ss/1009213286"
	},
	"brown2013": {
		"id": "brown2013",
		"apa": "Brown, S., Santa Maria, J. P., & Walker, S. (2013). Wall teichoic acids of gram-positive bacteria. Annual Review of Microbiology, 67, 313–336. https://doi.org/10.1146/annurev-micro-092412-155620",
		"url": "https://doi.org/10.1146/annurev-micro-092412-155620"
	},
	"buchfink2021": {
		"id": "buchfink2021",
		"apa": "Buchfink, B., Reuter, K., & Drost, H.-G. (2021). Sensitive protein alignments at tree-of-life scale using DIAMOND. Nature Methods, 18(4), 366–368. https://doi.org/10.1038/s41592-021-01101-x",
		"url": "https://doi.org/10.1038/s41592-021-01101-x"
	},
	"camacho2009": {
		"id": "camacho2009",
		"apa": "Camacho, C., Coulouris, G., Avagyan, V., Ma, N., Papadopoulos, J., Bealer, K., & Madden, T. L. (2009). BLAST+: Architecture and applications. BMC Bioinformatics, 10, 421. https://doi.org/10.1186/1471-2105-10-421",
		"url": "https://doi.org/10.1186/1471-2105-10-421"
	},
	"cantalapiedra2021": {
		"id": "cantalapiedra2021",
		"apa": "Cantalapiedra, C. P., Hernández-Plaza, A., Letunic, I., Bork, P., & Huerta-Cepas, J. (2021). eggNOG-mapper v2: Functional annotation, orthology assignments, and domain prediction at the metagenomic scale. Molecular Biology and Evolution, 38(12), 5825–5829. https://doi.org/10.1093/molbev/msab293",
		"url": "https://doi.org/10.1093/molbev/msab293"
	},
	"chaumeil2022": {
		"id": "chaumeil2022",
		"apa": "Chaumeil, P. A., Mussig, A. J., Hugenholtz, P., & Parks, D. H. (2022). GTDB-Tk v2: Memory friendly classification with the genome taxonomy database. Bioinformatics, 38(23), 5315–5316. https://doi.org/10.1093/bioinformatics/btac672",
		"url": "https://doi.org/10.1093/bioinformatics/btac672"
	},
	"dimonaco2022": {
		"id": "dimonaco2022",
		"apa": "Dimonaco, N. J., Aubrey, W., Kenobi, K., Clare, A., & Creevey, C. J. (2022). No one tool to rule them all: prokaryotic gene prediction tool annotations are highly dependent on the organism of study. Bioinformatics, 38(5), 1198–1207. https://doi.org/10.1093/bioinformatics/btab827",
		"url": "https://doi.org/10.1093/bioinformatics/btab827"
	},
	"eddy2011": {
		"id": "eddy2011",
		"apa": "Eddy, S. R. (2011). Accelerated profile HMM searches. PLoS Computational Biology, 7(10), e1002195. https://doi.org/10.1371/journal.pcbi.1002195",
		"url": "https://doi.org/10.1371/journal.pcbi.1002195"
	},
	"fawcett2006": {
		"id": "fawcett2006",
		"apa": "Fawcett, T. (2006). An introduction to ROC analysis. Pattern Recognition Letters, 27(8), 861–874. https://doi.org/10.1016/j.patrec.2005.10.010",
		"url": "https://doi.org/10.1016/j.patrec.2005.10.010"
	},
	"fips180": {
		"id": "fips180",
		"apa": "National Institute of Standards and Technology. (2015). Secure hash standard (SHS) (Federal Information Processing Standards Publication 180-4). U.S. Department of Commerce. https://doi.org/10.6028/NIST.FIPS.180-4",
		"url": "https://doi.org/10.6028/NIST.FIPS.180-4"
	},
	"galperin2025": {
		"id": "galperin2025",
		"apa": "Galperin, M. Y., Vera Alvarez, R., Karamycheva, S., Makarova, K. S., Wolf, Y. I., Landsman, D., & Koonin, E. V. (2025). COG database update 2024. Nucleic Acids Research, 53(D1), D356–D363. https://doi.org/10.1093/nar/gkae983",
		"url": "https://doi.org/10.1093/nar/gkae983"
	},
	"grabowicz2018": {
		"id": "grabowicz2018",
		"apa": "Grabowicz, M. (2018). Lipoprotein Transport: Greasing the Machines of Outer Membrane Biogenesis: Re-Examining Lipoprotein Transport Mechanisms Among Diverse Gram-Negative Bacteria While Exploring New Discoveries and Questions. BioEssays, 40(4). https://doi.org/10.1002/bies.201700187",
		"url": "https://doi.org/10.1002/bies.201700187"
	},
	"gurevich2013": {
		"id": "gurevich2013",
		"apa": "Gurevich, A., Saveliev, V., Vyahhi, N., & Tesler, G. (2013). QUAST: Quality assessment tool for genome assemblies. Bioinformatics, 29(8), 1072–1075. https://doi.org/10.1093/bioinformatics/btt086",
		"url": "https://doi.org/10.1093/bioinformatics/btt086"
	},
	"haft2013": {
		"id": "haft2013",
		"apa": "Haft, D. H., Selengut, J. D., Richter, R. A., Harkins, D., Basu, M. K., & Beck, E. (2013). TIGRFAMs and Genome Properties in 2013. Nucleic Acids Research, 41(D1), D387–D395. https://doi.org/10.1093/nar/gks1234",
		"url": "https://doi.org/10.1093/nar/gks1234"
	},
	"hagan2011": {
		"id": "hagan2011",
		"apa": "Hagan, C. L., Silhavy, T. J., & Kahne, D. (2011). β-Barrel membrane protein assembly by the Bam complex. Annual Review of Biochemistry, 80, 189–210. https://doi.org/10.1146/annurev-biochem-061408-144611",
		"url": "https://doi.org/10.1146/annurev-biochem-061408-144611"
	},
	"hanley1982": {
		"id": "hanley1982",
		"apa": "Hanley, J. A., & McNeil, B. J. (1982). The meaning and use of the area under a receiver operating characteristic (ROC) curve. Radiology, 143(1), 29–36. https://doi.org/10.1148/radiology.143.1.7063747",
		"url": "https://doi.org/10.1148/radiology.143.1.7063747"
	},
	"huertacepas2019": {
		"id": "huertacepas2019",
		"apa": "Huerta-Cepas, J., Szklarczyk, D., Heller, D., Hernández-Plaza, A., Forslund, S. K., Cook, H., Mende, D. R., Letunic, I., Rattei, T., Jensen, L. J., von Mering, C., & Bork, P. (2019). eggNOG 5.0: A hierarchical, functionally and phylogenetically annotated orthology resource based on 5090 organisms and 2502 viruses. Nucleic Acids Research, 47(D1), D309–D314. https://doi.org/10.1093/nar/gky1085",
		"url": "https://doi.org/10.1093/nar/gky1085"
	},
	"hyatt2010": {
		"id": "hyatt2010",
		"apa": "Hyatt, D., Chen, G.-L., Locascio, P. F., Land, M. L., Larimer, F. W., & Hauser, L. J. (2010). Prodigal: Prokaryotic gene recognition and translation initiation site identification. BMC Bioinformatics, 11, 119. https://doi.org/10.1186/1471-2105-11-119",
		"url": "https://doi.org/10.1186/1471-2105-11-119"
	},
	"itoh1999": {
		"id": "itoh1999",
		"apa": "Itoh, T., Takemoto, K., Mori, H., & Gojobori, T. (1999). Evolutionary instability of operon structures disclosed by sequence comparisons of complete microbial genomes. Molecular Biology and Evolution, 16(3), 332–346. https://doi.org/10.1093/oxfordjournals.molbev.a026114",
		"url": "https://doi.org/10.1093/oxfordjournals.molbev.a026114"
	},
	"jeffreys1946": {
		"id": "jeffreys1946",
		"apa": "Jeffreys, H. (1946). An invariant form for the prior probability in estimation problems. Proceedings of the Royal Society of London. Series A, Mathematical and Physical Sciences, 186(1007), 453–461. https://doi.org/10.1098/rspa.1946.0056",
		"url": "https://doi.org/10.1098/rspa.1946.0056"
	},
	"jones2014": {
		"id": "jones2014",
		"apa": "Jones, P., Binns, D., Chang, H. Y., Fraser, M., Li, W., McAnulla, C., McWilliam, H., Maslen, J., Mitchell, A., Nuka, G., Pesseat, S., Quinn, A. F., Sangrador-Vegas, A., Scheremetjew, M., Yong, S. Y., Lopez, R., & Hunter, S. (2014). InterProScan 5: Genome-scale protein function classification. Bioinformatics, 30(9), 1236–1240. https://doi.org/10.1093/bioinformatics/btu031",
		"url": "https://doi.org/10.1093/bioinformatics/btu031"
	},
	"jun2017": {
		"id": "jun2017",
		"apa": "Jun, S.-R., Nookaew, I., Hauser, L., & Gorin, A. (2017). Assessment of genome annotation using gene function similarity within the gene neighborhood. BMC Bioinformatics, 18, 345. https://doi.org/10.1186/s12859-017-1761-2",
		"url": "https://doi.org/10.1186/s12859-017-1761-2"
	},
	"kall2004": {
		"id": "kall2004",
		"apa": "Käll, L., Krogh, A., & Sonnhammer, E. L. L. (2004). A combined transmembrane topology and signal peptide prediction method. Journal of Molecular Biology, 338(5), 1027–1036. https://doi.org/10.1016/j.jmb.2004.03.016",
		"url": "https://doi.org/10.1016/j.jmb.2004.03.016"
	},
	"kanehisa2023": {
		"id": "kanehisa2023",
		"apa": "Kanehisa, M., Furumichi, M., Sato, Y., Kawashima, M., & Ishiguro-Watanabe, M. (2023). KEGG for taxonomy-based analysis of pathways and genomes. Nucleic Acids Research, 51(D1), D587–D592. https://doi.org/10.1093/nar/gkac963",
		"url": "https://doi.org/10.1093/nar/gkac963"
	},
	"kanehisa2025": {
		"id": "kanehisa2025",
		"apa": "Kanehisa, M., Furumichi, M., Sato, Y., Matsuura, Y., & Ishiguro-Watanabe, M. (2025). KEGG: Biological systems database as a model of the real world. Nucleic Acids Research, 53(D1), D672–D677. https://doi.org/10.1093/nar/gkae909",
		"url": "https://doi.org/10.1093/nar/gkae909"
	},
	"karp2023": {
		"id": "karp2023",
		"apa": "Karp, P. D., Paley, S., Caspi, R., Kothari, A., Krummenacker, M., Midford, P. E., Moore, L. R., Subhraveti, P., Gama-Castro, S., Tierrafria, V. H., Lara, P., Muñiz-Rascado, L., Bonavides-Martinez, C., Santos-Zavaleta, A., Mackie, A., Sun, G., Ahn-Horst, T. A., Choi, H., Covert, M. W., … Paulsen, I. (2023). The EcoCyc database (2023). EcoSal Plus, 11(1), eesp00022023. https://doi.org/10.1128/ecosalplus.esp-0002-2023",
		"url": "https://doi.org/10.1128/ecosalplus.esp-0002-2023"
	},
	"keseler2017": {
		"id": "keseler2017",
		"apa": "Keseler, I. M., Mackie, A., Santos-Zavaleta, A., Billington, R., Bonavides-Martínez, C., Caspi, R., Fulcher, C., Gama-Castro, S., Kothari, A., Krummenacker, M., Latendresse, M., Muñiz-Rascado, L., Ong, Q., Paley, S., Peralta-Gil, M., Subhraveti, P., Velázquez-Ramírez, D. A., Weaver, D., Collado-Vides, J., … Karp, P. D. (2017). The EcoCyc database: Reflecting new knowledge about Escherichia coli K-12. Nucleic Acids Research, 45(D1), D543–D550. https://doi.org/10.1093/nar/gkw1003",
		"url": "https://doi.org/10.1093/nar/gkw1003"
	},
	"konovalova2017": {
		"id": "konovalova2017",
		"apa": "Konovalova, A., Kahne, D. E., & Silhavy, T. J. (2017). Outer Membrane Biogenesis. Annual Review of Microbiology, 71, 539–556. https://doi.org/10.1146/annurev-micro-090816-093754",
		"url": "https://doi.org/10.1146/annurev-micro-090816-093754"
	},
	"koster2012": {
		"id": "koster2012",
		"apa": "Köster, J., & Rahmann, S. (2012). Snakemake—a scalable bioinformatics workflow engine. Bioinformatics, 28(19), 2520–2522. https://doi.org/10.1093/bioinformatics/bts480",
		"url": "https://doi.org/10.1093/bioinformatics/bts480"
	},
	"kurtzer2017": {
		"id": "kurtzer2017",
		"apa": "Kurtzer, G. M., Sochat, V., & Bauer, M. W. (2017). Singularity: Scientific containers for mobility of compute. PLoS ONE, 12(5), e0177459. https://doi.org/10.1371/journal.pone.0177459",
		"url": "https://doi.org/10.1371/journal.pone.0177459"
	},
	"laplace1812": {
		"id": "laplace1812",
		"apa": "Laplace, P. S. (1812). Théorie analytique des probabilités. Ve. Courcier. https://archive.org/details/thorieanalytiqu01laplgoog",
		"url": "https://archive.org/details/thorieanalytiqu01laplgoog"
	},
	"li2021": {
		"id": "li2021",
		"apa": "Li, W., O'Neill, K. R., Haft, D. H., DiCuccio, M., Chetvernin, V., Badretdin, A., Coulouris, G., Chitsaz, F., Derbyshire, M. K., Durkin, A. S., Gonzales, N. R., Gwadz, M., Lanczycki, C. J., Song, J. S., Thanki, N., Wang, J., Yamashita, R. A., Yang, M., Zheng, C., … Thibaud-Nissen, F. (2021). RefSeq: Expanding the Prokaryotic Genome Annotation Pipeline reach with protein family model curation. Nucleic Acids Research, 49(D1), D1020–D1028. https://doi.org/10.1093/nar/gkaa1105",
		"url": "https://doi.org/10.1093/nar/gkaa1105"
	},
	"mann1947": {
		"id": "mann1947",
		"apa": "Mann, H. B., & Whitney, D. R. (1947). On a test of whether one of two random variables is stochastically larger than the other. The Annals of Mathematical Statistics, 18(1), 50–60. https://doi.org/10.1214/aoms/1177730491",
		"url": "https://doi.org/10.1214/aoms/1177730491"
	},
	"marrakchi2014": {
		"id": "marrakchi2014",
		"apa": "Marrakchi, H., Lanéelle, M. A., & Daffé, M. (2014). Mycolic acids: Structures, biosynthesis, and beyond. Chemistry and Biology, 21(1), 67–85. https://doi.org/10.1016/j.chembiol.2013.11.011",
		"url": "https://doi.org/10.1016/j.chembiol.2013.11.011"
	},
	"mazmanian1999": {
		"id": "mazmanian1999",
		"apa": "Mazmanian, S. K., Liu, G., Ton-That, H., & Schneewind, O. (1999). Staphylococcus aureus sortase, an enzyme that anchors surface proteins to the cell wall. Science, 285(5428), 760–763. https://doi.org/10.1126/science.285.5428.760",
		"url": "https://doi.org/10.1126/science.285.5428.760"
	},
	"mccartney2014": {
		"id": "mccartney2014",
		"apa": "McCartney, G., Hacker, T., & Yang, B. (2014). Empowering faculty: A campus cyberinfrastructure strategy for research communities. EDUCAUSE Review.",
		"url": "https://er.educause.edu/articles/2014/7/empowering-faculty-a-campus-cyberinfrastructure-strategy-for-research-communities"
	},
	"mistry2021": {
		"id": "mistry2021",
		"apa": "Mistry, J., Chuguransky, S., Williams, L., Qureshi, M., Salazar, G., Sonnhammer, E. L. L., Tosatto, S. C. E., Paladin, L., Raj, S., Richardson, L. J., Finn, R. D., & Bateman, A. (2021). Pfam: The protein families database in 2021. Nucleic Acids Research, 49(D1), D412–D419. https://doi.org/10.1093/nar/gkaa913",
		"url": "https://doi.org/10.1093/nar/gkaa913"
	},
	"molder2021": {
		"id": "molder2021",
		"apa": "Mölder, F., Jablonski, K. P., Letcher, B., Hall, M. B., Tomkins-Tinch, C. H., Sochat, V., Forster, J., Lee, S., Twardziok, S. O., Kanitz, A., Wilm, A., Holtgrewe, M., Rahmann, S., Nahnsen, S., & Köster, J. (2021). Sustainable data analysis with Snakemake. F1000Research, 10, 33. https://doi.org/10.12688/f1000research.29032.2",
		"url": "https://doi.org/10.12688/f1000research.29032.2"
	},
	"neuhaus2003": {
		"id": "neuhaus2003",
		"apa": "Neuhaus, F. C., & Baddiley, J. (2003). A Continuum of Anionic Charge: Structures and Functions of d-Alanyl-Teichoic Acids in Gram-Positive Bacteria. Microbiology and Molecular Biology Reviews, 67(4), 686–723. https://doi.org/10.1128/mmbr.67.4.686-723.2003",
		"url": "https://doi.org/10.1128/mmbr.67.4.686-723.2003"
	},
	"newman2006": {
		"id": "newman2006",
		"apa": "Newman, M. E. J. (2006). Modularity and community structure in networks. Proceedings of the National Academy of Sciences of the United States of America, 103(23), 8577–8582. https://doi.org/10.1073/pnas.0601602103",
		"url": "https://doi.org/10.1073/pnas.0601602103"
	},
	"okuda2016": {
		"id": "okuda2016",
		"apa": "Okuda, S., Sherman, D. J., Silhavy, T. J., Ruiz, N., & Kahne, D. (2016). Lipopolysaccharide transport and assembly at the outer membrane: The PEZ model. Nature Reviews Microbiology, 14(6), 337–345. https://doi.org/10.1038/nrmicro.2016.25",
		"url": "https://doi.org/10.1038/nrmicro.2016.25"
	},
	"olson2023": {
		"id": "olson2023",
		"apa": "Olson, R. D., Assaf, R., Brettin, T., Conrad, N., Cucinell, C., Davis, J. J., Dempsey, D. M., Dickerman, A., Dietrich, E. M., Kenyon, R. W., Kuscuoglu, M., Lefkowitz, E. J., Lu, J., Machi, D., Macken, C., Mao, C., Niewiadomska, A., Nguyen, M., Olsen, G. J., … Stevens, R. L. (2023). Introducing the Bacterial and Viral Bioinformatics Resource Center (BV-BRC): A resource combining PATRIC, IRD and ViPR. Nucleic Acids Research, 51(D1), D678–D689. https://doi.org/10.1093/nar/gkac1003",
		"url": "https://doi.org/10.1093/nar/gkac1003"
	},
	"overbeek2014": {
		"id": "overbeek2014",
		"apa": "Overbeek, R., Olson, R., Pusch, G. D., Olsen, G. J., Davis, J. J., Disz, T., Edwards, R. A., Gerdes, S., Parrello, B., Shukla, M., Vonstein, V., Wattam, A. R., Xia, F., & Stevens, R. (2014). The SEED and the Rapid Annotation of microbial genomes using Subsystems Technology (RAST). Nucleic Acids Research, 42(D1), D206–D214. https://doi.org/10.1093/nar/gkt1226",
		"url": "https://doi.org/10.1093/nar/gkt1226"
	},
	"parks2020": {
		"id": "parks2020",
		"apa": "Parks, D. H., Chuvochina, M., Chaumeil, P. A., Rinke, C., Mussig, A. J., & Hugenholtz, P. (2020). A complete domain-to-species taxonomy for Bacteria and Archaea. Nature Biotechnology, 38(9), 1079–1086. https://doi.org/10.1038/s41587-020-0501-8",
		"url": "https://doi.org/10.1038/s41587-020-0501-8"
	},
	"paysanlafosse2023": {
		"id": "paysanlafosse2023",
		"apa": "Paysan-Lafosse, T., Blum, M., Chuguransky, S., Grego, T., Pinto, B. L., Salazar, G. A., Bileschi, M. L., Bork, P., Bridge, A., Colwell, L., Gough, J., Haft, D. H., Letunić, I., Marchler-Bauer, A., Mi, H., Natale, D. A., Orengo, C. A., Pandurangan, A. P., Rivoire, C., … Bateman, A. (2023). InterPro in 2022. Nucleic Acids Research, 51(D1), D418–D427. https://doi.org/10.1093/nar/gkac993",
		"url": "https://doi.org/10.1093/nar/gkac993"
	},
	"pedruzzi2015": {
		"id": "pedruzzi2015",
		"apa": "Pedruzzi, I., Rivoire, C., Auchincloss, A. H., Coudert, E., Keller, G., de Castro, E., Baratin, D., Cuche, B. A., Bougueleret, L., Poux, S., Redaschi, N., Xenarios, I., & Bridge, A. (2015). HAMAP in 2015: Updates to the protein family classification and annotation system. Nucleic Acids Research, 43(D1), D1064–D1070. https://doi.org/10.1093/nar/gku1002",
		"url": "https://doi.org/10.1093/nar/gku1002"
	},
	"percy2014": {
		"id": "percy2014",
		"apa": "Percy, M. G., & Gründling, A. (2014). Lipoteichoic acid synthesis and function in gram-positive bacteria. Annual Review of Microbiology, 68, 81–100. https://doi.org/10.1146/annurev-micro-091213-112949",
		"url": "https://doi.org/10.1146/annurev-micro-091213-112949"
	},
	"perezrueda2000": {
		"id": "perezrueda2000",
		"apa": "Pérez-Rueda, E., & Collado-Vides, J. (2000). The repertoire of DNA-binding transcriptional regulators in Escherichia coli K-12. Nucleic Acids Research, 28(8), 1838–1847. https://doi.org/10.1093/nar/28.8.1838",
		"url": "https://doi.org/10.1093/nar/28.8.1838"
	},
	"portevin2004": {
		"id": "portevin2004",
		"apa": "Portevin, D., De Sousa-D'Auria, C., Houssin, C., Grimaldi, C., Chami, M., Daffé, M., & Guilhot, C. (2004). A polyketide synthase catalyzes the last condensation step of mycolic acid biosynthesis in mycobacteria and related organisms. Proceedings of the National Academy of Sciences of the United States of America, 101(1), 314–319. https://doi.org/10.1073/pnas.0305439101",
		"url": "https://doi.org/10.1073/pnas.0305439101"
	},
	"raetz2007": {
		"id": "raetz2007",
		"apa": "Raetz, C. R. H., Reynolds, C. M., Trent, M. S., & Bishop, R. E. (2007). Lipid A modification systems in gram-negative bacteria. Annual Review of Biochemistry, 76, 295–329. https://doi.org/10.1146/annurev.biochem.76.010307.145803",
		"url": "https://doi.org/10.1146/annurev.biochem.76.010307.145803"
	},
	"rawlings2018": {
		"id": "rawlings2018",
		"apa": "Rawlings, N. D., Barrett, A. J., Thomas, P. D., Huang, X., Bateman, A., & Finn, R. D. (2018). The MEROPS database of proteolytic enzymes, their substrates and inhibitors in 2017 and a comparison with peptidases in the PANTHER database. Nucleic Acids Research, 46(D1), D624–D632. https://doi.org/10.1093/nar/gkx1134",
		"url": "https://doi.org/10.1093/nar/gkx1134"
	},
	"rcacnegishi": {
		"id": "rcacnegishi",
		"apa": "Rosen Center for Advanced Computing. (n.d.). Negishi [Community cluster]. Purdue University. Retrieved October 25, 2026, from",
		"url": "https://www.rcac.purdue.edu/compute/negishi"
	},
	"richardson2019": {
		"id": "richardson2019",
		"apa": "Richardson, L. J., Rawlings, N. D., Salazar, G. A., Almeida, A., Haft, D. R., Ducq, G., Sutton, G. G., & Finn, R. D. (2019). Genome properties in 2019: A new companion database to InterPro for the inference of complete functional attributes. Nucleic Acids Research, 47(D1), D564–D572. https://doi.org/10.1093/nar/gky1013",
		"url": "https://doi.org/10.1093/nar/gky1013"
	},
	"rogozin2002": {
		"id": "rogozin2002",
		"apa": "Rogozin, I. B., Makarova, K. S., Murvai, J., Czabarka, E., Wolf, Y. I., Tatusov, R. L., Szekely, L. A., & Koonin, E. V. (2002). Connected gene neighborhoods in prokaryotic genomes. Nucleic Acids Research, 30(10), 2212–2223. https://doi.org/10.1093/nar/30.10.2212",
		"url": "https://doi.org/10.1093/nar/30.10.2212"
	},
	"saier2021": {
		"id": "saier2021",
		"apa": "Saier, M. H., Reddy, V. S., Moreno-Hagelsieb, G., Hendargo, K. J., Zhang, Y., Iddamsetty, V., Lam, K. J. K., Tian, N., Russum, S., Wang, J., & Medrano-Soto, A. (2021). The Transporter Classification Database (TCDB): 2021 update. Nucleic Acids Research, 49(D1), D461–D467. https://doi.org/10.1093/nar/gkaa1004",
		"url": "https://doi.org/10.1093/nar/gkaa1004"
	},
	"savojardo2018": {
		"id": "savojardo2018",
		"apa": "Savojardo, C., Martelli, P. L., Fariselli, P., & Casadio, R. (2018). DeepSig: Deep learning improves signal peptide detection in proteins. Bioinformatics, 34(10), 1690–1696. https://doi.org/10.1093/bioinformatics/btx818",
		"url": "https://doi.org/10.1093/bioinformatics/btx818"
	},
	"silhavy2010": {
		"id": "silhavy2010",
		"apa": "Silhavy, T. J., Kahne, D., & Walker, S. (2010). The bacterial cell envelope. Cold Spring Harbor Perspectives in Biology, 2(5), a000414. https://doi.org/10.1101/cshperspect.a000414",
		"url": "https://doi.org/10.1101/cshperspect.a000414"
	},
	"smith2020geddes": {
		"id": "smith2020geddes",
		"apa": "Smith, P. M., Gough, E., Younts, A., Werts, B., Hacker, T. J., Neumeister, N., & Wisecaver, J. (2020). The “Geddes” composable platform: An evolution of community clusters for a composable world. 2020 IEEE/ACM International Workshop on Interoperability of Supercomputing and Cloud Technologies (SuperCompCloud), 33–38.",
		"url": "https://doi.org/10.1109/SuperCompCloud51944.2020.00011"
	},
	"snakemake_slurm": {
		"id": "snakemake_slurm",
		"apa": "Snakemake executor plugin: slurm [Computer software]. (n.d.). Snakemake plugin catalog. Retrieved October 25, 2026, from https://snakemake.github.io/snakemake-plugin-catalog/plugins/executor/slurm.html",
		"url": "https://snakemake.github.io/snakemake-plugin-catalog/plugins/executor/slurm.html"
	},
	"sperandeo2017": {
		"id": "sperandeo2017",
		"apa": "Sperandeo, P., Martorana, A. M., & Polissi, A. (2017). The lipopolysaccharide transport (Lpt) machinery: A nonconventional transporter for lipopolysaccharide assembly at the outer membrane of Gram-negative bacteria. Journal of Biological Chemistry, 292(44), 17981–17990. https://doi.org/10.1074/jbc.r117.802512",
		"url": "https://doi.org/10.1074/jbc.r117.802512"
	},
	"spirig2011": {
		"id": "spirig2011",
		"apa": "Spirig, T., Weiner, E. M., & Clubb, R. T. (2011). Sortase enzymes in Gram-positive bacteria. Molecular Microbiology, 82(5), 1044–1059. https://doi.org/10.1111/j.1365-2958.2011.07887.x",
		"url": "https://doi.org/10.1111/j.1365-2958.2011.07887.x"
	},
	"sqlite": {
		"id": "sqlite",
		"apa": "SQLite [Computer software]. (n.d.). Retrieved October 25, 2026, from https://www.sqlite.org/",
		"url": "https://www.sqlite.org/"
	},
	"su2024": {
		"id": "su2024",
		"apa": "Su, H., Zhang, R., & Söding, J. (2024). UniOP: A universal operon prediction for high-throughput prokaryotic (meta-)genomic data using intergenic distance [Preprint]. bioRxiv. https://doi.org/10.1101/2024.11.11.623000",
		"url": "https://doi.org/10.1101/2024.11.11.623000"
	},
	"tamames2001": {
		"id": "tamames2001",
		"apa": "Tamames, J. (2001). Evolution of gene order conservation in prokaryotes. Genome Biology, 2(6), research0020. https://doi.org/10.1186/gb-2001-2-6-research0020",
		"url": "https://doi.org/10.1186/gb-2001-2-6-research0020"
	},
	"teufel2022": {
		"id": "teufel2022",
		"apa": "Teufel, F., Almagro Armenteros, J. J., Johansen, A. R., Gíslason, M. H., Pihl, S. I., Tsirigos, K. D., Winther, O., Brunak, S., von Heijne, G., & Nielsen, H. (2022). SignalP 6.0 predicts all five types of signal peptides using protein language models. Nature Biotechnology, 40, 1023–1025. https://doi.org/10.1038/s41587-021-01156-3",
		"url": "https://doi.org/10.1038/s41587-021-01156-3"
	},
	"uniprot2025": {
		"id": "uniprot2025",
		"apa": "UniProt Consortium. (2025). UniProt: The Universal Protein Knowledgebase in 2025. Nucleic Acids Research, 53(D1), D609–D617. https://doi.org/10.1093/nar/gkae1010",
		"url": "https://doi.org/10.1093/nar/gkae1010"
	},
	"vannimwegen2003": {
		"id": "vannimwegen2003",
		"apa": "van Nimwegen, E. (2003). Scaling laws in the functional content of genomes. Trends in Genetics, 19(9), 479–484. https://doi.org/10.1016/S0168-9525(03)00203-8",
		"url": "https://doi.org/10.1016/S0168-9525(03)00203-8"
	},
	"wang2023": {
		"id": "wang2023",
		"apa": "Wang, J., Chitsaz, F., Derbyshire, M. K., Gonzales, N. R., Gwadz, M., Lu, S., Marchler, G. H., Song, J. S., Thanki, N., Yamashita, R. A., Yang, M., Zhang, D., Zheng, C., Lanczycki, C. J., & Marchler-Bauer, A. (2023). The conserved domain database in 2023. Nucleic Acids Research, 51(D1), D384–D388. https://doi.org/10.1093/nar/gkac1096",
		"url": "https://doi.org/10.1093/nar/gkac1096"
	},
	"wu2004": {
		"id": "wu2004",
		"apa": "Wu, C. H., Nikolskaya, A., Huang, H., Yeh, L.-S. L., Natale, D. A., Vinayaka, C. R., Hu, Z.-Z., Mazumder, R., Kumar, S., Kourtesis, P., Ledley, R. S., Suzek, B. E., Arminski, L., Chen, Y., Zhang, J., Cardenas, J. L., Chung, S., Castro-Alvear, J., Dinkov, G., & Barker, W. C. (2004). PIRSF: Family classification system at the Protein Information Resource. Nucleic Acids Research, 32(Database issue), D112–D114. https://doi.org/10.1093/nar/gkh097",
		"url": "https://doi.org/10.1093/nar/gkh097"
	},
	"yang2010": {
		"id": "yang2010",
		"apa": "Yang, Y., Gilbert, D., & Kim, S. (2010). Annotation confidence score for genome annotation: A genome comparison approach. Bioinformatics, 26(1), 22–29. https://doi.org/10.1093/bioinformatics/btp613",
		"url": "https://doi.org/10.1093/bioinformatics/btp613"
	},
	"yoo2003": {
		"id": "yoo2003",
		"apa": "Yoo, A. B., Jette, M. A., & Grondona, M. (2003). SLURM: Simple Linux utility for resource management. In Job scheduling strategies for parallel processing (pp. 44–60). Springer. https://doi.org/10.1007/10968987_3",
		"url": "https://doi.org/10.1007/10968987_3"
	},
	"yu2010": {
		"id": "yu2010",
		"apa": "Yu, N. Y., Wagner, J. R., Laird, M. R., Melli, G., Rey, S., Lo, R., Dao, P., Sahinalp, S. C., Ester, M., Foster, L. J., & Brinkman, F. S. L. (2010). PSORTb 3.0: Improved protein subcellular localization prediction with refined localization subcategories and predictive capabilities for all prokaryotes. Bioinformatics, 26(13), 1608–1615. https://doi.org/10.1093/bioinformatics/btq249",
		"url": "https://doi.org/10.1093/bioinformatics/btq249"
	},
	"zheng2023": {
		"id": "zheng2023",
		"apa": "Zheng, J., Ge, Q., Yan, Y., Zhang, X., Huang, L., & Yin, Y. (2023). dbCAN3: Automated carbohydrate-active enzyme and substrate annotation. Nucleic Acids Research, 51(W1), W115–W121. https://doi.org/10.1093/nar/gkad328",
		"url": "https://doi.org/10.1093/nar/gkad328"
	}
};
