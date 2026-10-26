<script lang="ts">
	import ReadingPage from '$lib/crisp/ReadingPage.svelte';

	/**
	 * How to set up MARGIE: a first setup step by step, for one person or a whole lab, with the
	 * defaults and what to back up. Opened from Home (How to set up MARGIE) and from the working
	 * folder setup; not in the sidebar.
	 */

	/** The folders the working folder holds. */
	const INSIDE = [
		{ name: 'margie-input', holds: 'The genomes you add (FASTA files)' },
		{ name: 'margie-output', holds: 'The results of each run' },
		{ name: 'margie-databases', holds: "MARGIE's own databases: the MARGIE database (SQLite), the operon reference, the fingerprint databases and the genome pool" },
		{ name: 'sif', holds: "The tools' containers, when your account cannot read your group's" },
		{ name: 'reference-databases/db', holds: "The tools' reference databases, when your account cannot read your group's" }
	];

	/** Each default, and where it is changed. */
	const DEFAULTS = [
		{ what: 'Working folder', value: 'margie in your scratch: /scratch/<cluster>/<you>/margie', where: 'Settings → Folders' },
		{ what: 'Genomes', value: 'margie-input in the working folder', where: 'Settings → Folders' },
		{ what: 'Results', value: 'margie-output in the working folder', where: 'Settings → Folders' },
		{ what: "MARGIE's databases", value: 'margie-databases in the working folder', where: 'Settings → Folders' },
		{ what: 'Containers', value: "Your group's, else sif in the working folder", where: 'Settings → Folders' },
		{ what: 'Reference databases', value: "Your group's, else reference-databases/db in the working folder", where: 'Settings → Folders' },
		{ what: 'margie-build', value: "The folder you name, else your group's, else ~/margie-build", where: 'Settings → Folders' },
		{ what: "Base for MARGIE's databases", value: "Your group's base databases, else new ones", where: 'Settings → Databases' }
	];
</script>

<svelte:head><title>How to set up MARGIE | MARGIE</title></svelte:head>

<ReadingPage
	title="How to set up MARGIE"
	lede="A first setup, step by step, for you alone or for a whole lab: what to prepare, what MARGIE sets up on her own, and what to keep safe once it is done."
	shade="page-setup"
>
	<section class="rp-sec" id="before" data-toc="Before you begin">
		<h2>Before you begin</h2>
		<p class="rp-lead">
			MARGIE works in your account on an HPC cluster: she reaches it over SSH and sends each step of a run to SLURM. A first setup needs:
		</p>
		<ul>
			<li>An account on a cluster with SLURM and Apptainer, and a SLURM account (allocation) to run jobs under.</li>
			<li>Space for a working folder. Scratch suits it: it is fast, and large enough for genomes, results and MARGIE's databases.</li>
			<li>Room for the tools' containers and reference databases, which are large, unless your group already has them.</li>
			<li>A partition with large-memory nodes (about 400 GB) if GTDB-Tk works out each genome's domain and genetic code.</li>
			<li>Optionally, a shared folder for your group (a depot folder, for example), when your lab shares one setup.</li>
		</ul>
	</section>

	<section class="rp-sec" id="connect" data-toc="1. Connect your account">
		<h2>1. Connect your cluster account</h2>
		<p>
			On the sign-in page, choose Sign up and give your cluster's address and your username. Make a key for MARGIE with
			<code>ssh-keygen</code> and add its public half to <code>~/.ssh/authorized_keys</code> on the cluster; the sign-up page shows the commands.
			MARGIE keeps the private key encrypted. To take her access away, delete that key's line from <code>~/.ssh/authorized_keys</code>.
		</p>
	</section>

	<section class="rp-sec" id="working" data-toc="2. Working folder">
		<h2>2. Set up your working folder</h2>
		<p>
			The working folder is the first thing MARGIE asks for, on Analyze (under Genomes) and in Settings. By default it is margie in your scratch,
			<code>/scratch/&lt;cluster&gt;/&lt;you&gt;/margie</code>, and one button makes it with these folders inside:
		</p>
		<div class="rp-scroll">
			<table class="rp-table">
				<thead><tr><th>Folder</th><th>Holds</th></tr></thead>
				<tbody>
					{#each INSIDE as f (f.name)}
						<tr><td><code>{f.name}</code></td><td>{f.holds}</td></tr>
					{/each}
				</tbody>
			</table>
		</div>
		<p>
			You can point any of them elsewhere in Settings → Folders. A new working folder takes the folders that sit in it along; a folder you set
			yourself stays where it is, and so do the containers and reference databases. Files are not moved: the old folder keeps them.
		</p>
		<p class="rp-note">
			Scratch on many clusters deletes files that have not been used for a while. Copy out the results you need, and back up what takes long to
			make (see Keep what took long, below).
		</p>
	</section>

	<section class="rp-sec" id="tools" data-toc="3. Containers and databases">
		<h2>3. Containers and reference databases</h2>
		<p>
			Each annotation tool runs in an Apptainer container and searches its reference databases (Pfam, KEGG, COG, eggNOG, InterPro, GTDB-Tk's and
			the others). <a href="/install">Install</a> shows what a run needs and whether it is there. When your group keeps them in its shared folder
			and your account can read it, MARGIE uses them where they are. Otherwise Install sets them up in <code>sif</code> and <code>reference-databases/db</code> in your
			working folder: it copies what it can and builds the rest with margie-build.
		</p>
		<p>
			margie-build holds the recipes for the containers and databases. MARGIE looks for it in the folder named in Settings → Folders, then in your
			group's folder, then in <code>~/margie-build</code>, where Install puts a copy when the cluster has none. Building, and setting up
			margie-build, ask for the build password, which the MARGIE team gives out (see <a href="/contributors">Contributors</a>). InterProScan, MEROPS, TCDB, TMbed and Phobius also
			need their licences accepted on Install.
		</p>
		<p class="rp-note">
			<b>This is the long part.</b> Building the containers and downloading the reference databases takes many hours. Once they are set up, back
			them up, ideally in your group's shared space (a depot folder, for example), where the whole group can use them. When no group folder is
			given, or your account cannot read the default one, MARGIE sets them up in the working folder you gave.
		</p>
	</section>

	<section class="rp-sec" id="margie-databases" data-toc="4. MARGIE's databases">
		<h2>4. MARGIE's databases</h2>
		<p>
			Your first run sets up <code>margie-databases</code> as a short SLURM job before it starts. It copies your group's base databases there,
			so scoring has reference genomes to compare with from the first run. Where your account reads no base databases (in a lab outside the
			group, for example), it starts new ones instead: MARGIE's starter operon reference, of 29 genomes, and the others empty. These databases
			grow with each run. Settings → Databases can also start fresh, empty ones, and back yours up.
		</p>
	</section>

	<section class="rp-sec" id="slurm" data-toc="5. SLURM">
		<h2>5. SLURM account and partitions</h2>
		<p>
			In Settings → Cluster, set the SLURM account your jobs run under and the main partition. Give GTDB-Tk a large-memory partition under
			Phases, and any tool its own partition under Per tool.
		</p>
	</section>

	<section class="rp-sec" id="first-run" data-toc="6. Test, then run">
		<h2>6. Test, then run</h2>
		<p>
			Install's self-test sends a small job to SLURM and shows how it went. Then open <a href="/analyze">Analyze</a>: add your genomes (drop
			FASTA files on Genomes), check the gene calling and the tools, and start the run. Jobs follows it, and Results shows what came out.
		</p>
	</section>

	<section class="rp-sec" id="lab" data-toc="For a whole lab">
		<h2>Setting MARGIE up for a whole lab</h2>
		<p class="rp-lead">A lab can share one setup, so the long part is done once:</p>
		<ol>
			<li>
				One person sets up the containers, the reference databases and margie-build in the group's shared folder (a depot folder, for example),
				with the base MARGIE databases under it.
			</li>
			<li>They make that folder readable by the group, for example with <code>chmod -R g+rX</code> on it.</li>
			<li>
				Each member points the Containers folder and the Reference databases folder (Settings → Folders) there, and sets the Group folder
				(Settings → Databases), so their first run copies the base databases.
			</li>
			<li>Each member keeps their own working folder: genomes, results and MARGIE's databases stay per person.</li>
		</ol>
		<p>
			Individual setups are your choice: you can set up your own containers and databases in your working folder instead. That takes the hours
			and the space again, for each person who does.
		</p>
	</section>

	<section class="rp-sec" id="defaults" data-toc="Defaults">
		<h2>Defaults at a glance</h2>
		<div class="rp-scroll">
			<table class="rp-table">
				<thead><tr><th>What</th><th>Default</th><th>Changed in</th></tr></thead>
				<tbody>
					{#each DEFAULTS as d (d.what)}
						<tr><td>{d.what}</td><td>{d.value}</td><td>{d.where}</td></tr>
					{/each}
				</tbody>
			</table>
		</div>
	</section>

	<section class="rp-sec" id="keep" data-toc="Keep what took long">
		<h2>Keep what took long</h2>
		<ul>
			<li>Containers and reference databases: copy <code>sif</code> and <code>reference-databases/db</code> to your group's shared space, then point Settings → Folders at the copies.</li>
			<li>MARGIE's databases: back them up from Settings → Databases, since they grow with each run.</li>
			<li>Results: copy what you need out of scratch.</li>
		</ul>
	</section>
</ReadingPage>
