/**
 * What MARGIE's tools, databases and software are, as their own pages state: each one's version,
 * licence (with the catalog's wording when the provider's page says otherwise), source code, data
 * sources and the papers it asks to be cited, with BibTeX taken from each paper's DOI. Checked on
 * 2026-10-25 against the providers' pages. Read by Acknowledgements, Contributors (the citations to
 * give with MARGIE's) and the methods paragraph on Results.
 */

export interface Cite {
	key: string;
	/** APA 7th. */
	apa: string;
	doi: string;
	bibtex: string;
}

export interface ToolCredit {
	id: string;
	name: string;
	role: string;
	phase: number;
	version: string;
	/** False when the record names a moving release ("current", a git HEAD). */
	versionExact: boolean;
	licence: string;
	licenceUrl: string;
	/** The licence catalog's wording (the licence gate's), when it differs from the provider's page. */
	catalogLicence: string;
	source: string;
	downloads: string[];
	/** The tool's own pages ask users to cite these papers (citeRule, on citeRuleUrl). */
	citeRequired: boolean;
	citeRule: string;
	citeRuleUrl: string;
	cite: Cite[];
}

export interface SoftwareCredit {
	name: string;
	group: string;
	listedAs: string;
	version: string;
	licence: string;
	licenceUrl: string;
	source: string;
	citeRequired: boolean;
	citeRule: string;
	citeRuleUrl: string;
	cite: Cite[];
}

export const TOOLS: ToolCredit[] = [
	{
		"id": "phobius",
		"name": "Phobius 1.01",
		"role": "transmembrane topology and signal peptide prediction",
		"phase": 7,
		"version": "1.01",
		"versionExact": true,
		"licence": "Academic use only (free for academic users; others contact the author)",
		"licenceUrl": "https://phobius.sbc.su.se/download",
		"catalogLicence": "",
		"source": "https://phobius.sbc.su.se/download",
		"downloads": [
			"http://phobius.sbc.su.se/ (register; tarball phobius101_linux.tgz)",
			"https://phobius.sbc.su.se/download"
		],
		"citeRequired": true,
		"citeRule": "Please cite Käll, Krogh & Sonnhammer, J Mol Biol 338:1027-1036 (2004).",
		"citeRuleUrl": "https://phobius.sbc.su.se/download",
		"cite": [
			{
				"key": "kall2004phobius",
				"apa": "Käll, L., Krogh, A., & Sonnhammer, E. L. L. (2004). A Combined Transmembrane Topology and Signal Peptide Prediction Method. Journal of Molecular Biology, 338(5), 1027–1036. https://doi.org/10.1016/j.jmb.2004.03.016",
				"doi": "10.1016/j.jmb.2004.03.016",
				"bibtex": "@article{kall2004phobius, title={A Combined Transmembrane Topology and Signal Peptide Prediction Method}, volume={338}, ISSN={0022-2836}, url={http://dx.doi.org/10.1016/j.jmb.2004.03.016}, DOI={10.1016/j.jmb.2004.03.016}, number={5}, journal={Journal of Molecular Biology}, publisher={Elsevier BV}, author={Käll, Lukas and Krogh, Anders and Sonnhammer, Erik L.L}, year={2004}, month=May, pages={1027–1036} }"
			}
		]
	},
	{
		"id": "signalp4",
		"name": "SignalP 4.0 / 4.1",
		"role": "signal peptide prediction (SignalP 4.1)",
		"phase": 7,
		"version": "4.1",
		"versionExact": true,
		"licence": "DTU Health Tech academic software licence (academic use only; no redistribution)",
		"licenceUrl": "https://services.healthtech.dtu.dk/cgi-bin/sw_request?software=signalp&version=4.1&packageversion=4.1g&platform=Linux",
		"catalogLicence": "",
		"source": "https://services.healthtech.dtu.dk/services/SignalP-4.1/",
		"downloads": [
			"https://services.healthtech.dtu.dk/services/SignalP-4.1/ (register)"
		],
		"citeRequired": true,
		"citeRule": "For publication of results, please cite:",
		"citeRuleUrl": "https://services.healthtech.dtu.dk/services/SignalP-4.1/",
		"cite": [
			{
				"key": "petersen2011signalp4",
				"apa": "Petersen, T. N., Brunak, S., von Heijne, G., & Nielsen, H. (2011). SignalP 4.0: discriminating signal peptides from transmembrane regions. Nature Methods, 8(10), 785–786. https://doi.org/10.1038/nmeth.1701",
				"doi": "10.1038/nmeth.1701",
				"bibtex": "@article{petersen2011signalp4, title={SignalP 4.0: discriminating signal peptides from transmembrane regions}, volume={8}, ISSN={1548-7105}, url={http://dx.doi.org/10.1038/nmeth.1701}, DOI={10.1038/nmeth.1701}, number={10}, journal={Nature Methods}, publisher={Springer Science and Business Media LLC}, author={Petersen, Thomas Nordahl and Brunak, Søren and von Heijne, Gunnar and Nielsen, Henrik}, year={2011}, month=Sept, pages={785–786} }"
			}
		]
	},
	{
		"id": "signalp6",
		"name": "SignalP 6.0",
		"role": "signal peptide prediction (SignalP 6.0)",
		"phase": 7,
		"version": "6.0 (fast model)",
		"versionExact": true,
		"licence": "DTU Health Tech academic software licence (academic use only; no redistribution); code on GitHub under CC BY-NC-ND 2.0",
		"licenceUrl": "https://services.healthtech.dtu.dk/cgi-bin/sw_request?software=signalp&version=6.0&packageversion=6.0i&platform=fast",
		"catalogLicence": "",
		"source": "https://github.com/fteufel/signalp-6.0",
		"downloads": [
			"https://services.healthtech.dtu.dk/services/SignalP-6.0/ (register)"
		],
		"citeRequired": false,
		"citeRule": "",
		"citeRuleUrl": "https://services.healthtech.dtu.dk/services/SignalP-6.0/",
		"cite": [
			{
				"key": "teufel2022signalp6",
				"apa": "Teufel, F., Almagro Armenteros, J. J., Johansen, A. R., Gíslason, M. H., Pihl, S. I., Tsirigos, K. D., Winther, O., Brunak, S., von Heijne, G., & Nielsen, H. (2022). SignalP 6.0 predicts all five types of signal peptides using protein language models. Nature Biotechnology, 40(7), 1023–1025. https://doi.org/10.1038/s41587-021-01156-3",
				"doi": "10.1038/s41587-021-01156-3",
				"bibtex": "@article{teufel2022signalp6, title={SignalP 6.0 predicts all five types of signal peptides using protein language models}, volume={40}, ISSN={1546-1696}, url={http://dx.doi.org/10.1038/s41587-021-01156-3}, DOI={10.1038/s41587-021-01156-3}, number={7}, journal={Nature Biotechnology}, publisher={Springer Science and Business Media LLC}, author={Teufel, Felix and Almagro Armenteros, José Juan and Johansen, Alexander Rosenberg and Gíslason, Magnús Halldór and Pihl, Silas Irby and Tsirigos, Konstantinos D. and Winther, Ole and Brunak, Søren and von Heijne, Gunnar and Nielsen, Henrik}, year={2022}, month=Jan, pages={1023–1025} }"
			}
		]
	},
	{
		"id": "merops",
		"name": "MEROPS (pepunit database)",
		"role": "peptidase (protease) annotation",
		"phase": 4,
		"version": "MEROPS 12.5",
		"versionExact": true,
		"licence": "GNU Library General Public License (LGPL-2.0), per the MEROPS availability page",
		"licenceUrl": "https://www.ebi.ac.uk/merops/about/availability.shtml",
		"catalogLicence": "Academic use only (no redistribution)",
		"source": "https://www.ebi.ac.uk/merops/download_list.shtml",
		"downloads": [
			"https://ftp.ebi.ac.uk/pub/databases/merops/current_release/pepunit.lib",
			"https://ftp.ebi.ac.uk/pub/databases/merops/current_release/merops_scan.lib",
			"register: https://www.ebi.ac.uk/merops/download_list.shtml",
			"https://www.ebi.ac.uk/merops/download_list.shtml"
		],
		"citeRequired": true,
		"citeRule": "If you include information that was obtained from MEROPS in your published work, please give us the fair credit with a citation.",
		"citeRuleUrl": "https://www.ebi.ac.uk/merops/about/citing.shtml",
		"cite": [
			{
				"key": "rawlings2014merops",
				"apa": "Rawlings, N. D., Waller, M., Barrett, A. J., & Bateman, A. (2013). MEROPS : the database of proteolytic enzymes, their substrates and inhibitors. Nucleic Acids Research, 42(D1), D503–D509. https://doi.org/10.1093/nar/gkt953",
				"doi": "10.1093/nar/gkt953",
				"bibtex": "@article{rawlings2014merops, title={MEROPS\n                    : the database of proteolytic enzymes, their substrates and inhibitors}, volume={42}, ISSN={1362-4962}, url={http://dx.doi.org/10.1093/nar/gkt953}, DOI={10.1093/nar/gkt953}, number={D1}, journal={Nucleic Acids Research}, publisher={Oxford University Press (OUP)}, author={Rawlings, Neil D. and Waller, Matthew and Barrett, Alan J. and Bateman, Alex}, year={2013}, month=Oct, pages={D503–D509} }"
			},
			{
				"key": "rawlings2018merops",
				"apa": "Rawlings, N. D., Barrett, A. J., Thomas, P. D., Huang, X., Bateman, A., & Finn, R. D. (2017). The MEROPS database of proteolytic enzymes, their substrates and inhibitors in 2017 and a comparison with peptidases in the PANTHER database. Nucleic Acids Research, 46(D1), D624–D632. https://doi.org/10.1093/nar/gkx1134",
				"doi": "10.1093/nar/gkx1134",
				"bibtex": "@article{rawlings2018merops, title={The MEROPS database of proteolytic enzymes, their substrates and inhibitors in 2017 and a comparison with peptidases in the PANTHER database}, volume={46}, ISSN={1362-4962}, url={http://dx.doi.org/10.1093/nar/gkx1134}, DOI={10.1093/nar/gkx1134}, number={D1}, journal={Nucleic Acids Research}, publisher={Oxford University Press (OUP)}, author={Rawlings, Neil D and Barrett, Alan J and Thomas, Paul D and Huang, Xiaosong and Bateman, Alex and Finn, Robert D}, year={2017}, month=Nov, pages={D624–D632} }"
			}
		]
	},
	{
		"id": "tmbed",
		"name": "TMbed / ProtT5-XL-U50 weights",
		"role": "transmembrane topology prediction from protein language model embeddings",
		"phase": 7,
		"version": "TMbed v1.0.0; ProtT5 = Rostlab/prot_t5_xl_half_uniref50-enc",
		"versionExact": true,
		"licence": "TMbed Apache-2.0; ProtT5 pretrained models Academic Free License v3.0 (per the ProtTrans README)",
		"licenceUrl": "https://github.com/BernhoferM/TMbed/blob/main/LICENSE",
		"catalogLicence": "TMbed code Apache-2.0; ProtT5-XL-U50 model weights CC-BY-NC-SA 4.0 (NonCommercial)",
		"source": "https://github.com/BernhoferM/TMbed",
		"downloads": [
			"https://github.com/BernhoferM/TMbed/releases/tag/v1.0.0",
			"https://huggingface.co/Rostlab/prot_t5_xl_half_uniref50-enc (model weights)"
		],
		"citeRequired": true,
		"citeRule": "If you use this code or our pretrained models for your publication, please cite the original paper:",
		"citeRuleUrl": "https://github.com/agemagician/ProtTrans/blob/master/README.md",
		"cite": [
			{
				"key": "bernhofer2022tmbed",
				"apa": "Bernhofer, M., & Rost, B. (2022). TMbed: transmembrane proteins predicted through language model embeddings. BMC Bioinformatics, 23(1). https://doi.org/10.1186/s12859-022-04873-x",
				"doi": "10.1186/s12859-022-04873-x",
				"bibtex": "@article{bernhofer2022tmbed, title={TMbed: transmembrane proteins predicted through language model embeddings}, volume={23}, ISSN={1471-2105}, url={http://dx.doi.org/10.1186/s12859-022-04873-x}, DOI={10.1186/s12859-022-04873-x}, number={1}, journal={BMC Bioinformatics}, publisher={Springer Science and Business Media LLC}, author={Bernhofer, Michael and Rost, Burkhard}, year={2022}, month=Aug }"
			},
			{
				"key": "elnaggar2022prottrans",
				"apa": "Elnaggar, A., Heinzinger, M., Dallago, C., Rehawi, G., Wang, Y., Jones, L., Gibbs, T., Feher, T., Angerer, C., Steinegger, M., Bhowmik, D., & Rost, B. (2022). ProtTrans: Toward Understanding the Language of Life Through Self-Supervised Learning. IEEE Transactions on Pattern Analysis and Machine Intelligence, 44(10), 7112–7127. https://doi.org/10.1109/tpami.2021.3095381",
				"doi": "10.1109/TPAMI.2021.3095381",
				"bibtex": "@article{elnaggar2022prottrans, title={ProtTrans: Toward Understanding the Language of Life Through Self-Supervised Learning}, volume={44}, ISSN={1939-3539}, url={http://dx.doi.org/10.1109/TPAMI.2021.3095381}, DOI={10.1109/tpami.2021.3095381}, number={10}, journal={IEEE Transactions on Pattern Analysis and Machine Intelligence}, publisher={Institute of Electrical and Electronics Engineers (IEEE)}, author={Elnaggar, Ahmed and Heinzinger, Michael and Dallago, Christian and Rehawi, Ghalia and Wang, Yu and Jones, Llion and Gibbs, Tom and Feher, Tamas and Angerer, Christoph and Steinegger, Martin and Bhowmik, Debsindhu and Rost, Burkhard}, year={2022}, month=Oct, pages={7112–7127} }"
			}
		]
	},
	{
		"id": "tcdb",
		"name": "TCDB (Transporter Classification Database)",
		"role": "transporter annotation",
		"phase": 4,
		"version": "TCDB 2024 / current",
		"versionExact": false,
		"licence": "CC BY-SA 3.0 Unported and GNU Free Documentation License (site footer: \"The text of this website ...\")",
		"licenceUrl": "https://www.tcdb.org/download.php",
		"catalogLicence": "Free for academic / non-profit; commercial use requires permission",
		"source": "https://www.tcdb.org/download.php",
		"downloads": [
			"https://www.tcdb.org/download.php",
			"https://www.tcdb.org/public/tcdb (FASTA)"
		],
		"citeRequired": false,
		"citeRule": "",
		"citeRuleUrl": "https://www.tcdb.org/",
		"cite": [
			{
				"key": "saier2021tcdb",
				"apa": "Saier, M. H., Reddy, V. S., Moreno-Hagelsieb, G., Hendargo, K. J., Zhang, Y., Iddamsetty, V., Lam, K., Tian, N., Russum, S., Wang, J., & Medrano-Soto, A. (2020). The Transporter Classification Database (TCDB): 2021 update. Nucleic Acids Research, 49(D1), D461–D467. https://doi.org/10.1093/nar/gkaa1004",
				"doi": "10.1093/nar/gkaa1004",
				"bibtex": "@article{saier2021tcdb, title={The Transporter Classification Database (TCDB): 2021 update}, volume={49}, ISSN={1362-4962}, url={http://dx.doi.org/10.1093/nar/gkaa1004}, DOI={10.1093/nar/gkaa1004}, number={D1}, journal={Nucleic Acids Research}, publisher={Oxford University Press (OUP)}, author={Saier, Milton H and Reddy, Vamsee S and Moreno-Hagelsieb, Gabriel and Hendargo, Kevin J and Zhang, Yichi and Iddamsetty, Vasu and Lam, Katie Jing Kay and Tian, Nuo and Russum, Steven and Wang, Jianing and Medrano-Soto, Arturo}, year={2020}, month=Nov, pages={D461–D467} }"
			}
		]
	},
	{
		"id": "kegg",
		"name": "KEGG / KofamScan (KOfam subset)",
		"role": "KEGG Orthology (KO) assignment",
		"phase": 4,
		"version": "KofamScan 1.3.0; KOfam (current)",
		"versionExact": false,
		"licence": "KofamScan MIT; KO definitions copyrighted by Kanehisa Laboratories under KEGG licensing terms (commercial users need authorization)",
		"licenceUrl": "https://github.com/takaram/kofam_scan/blob/master/LICENSE.txt",
		"catalogLicence": "",
		"source": "https://www.genome.jp/ftp/tools/kofam_scan/",
		"downloads": [
			"https://www.genome.jp/ftp/tools/kofam_scan/kofam_scan-1.3.0.tar.gz",
			"https://www.genome.jp/ftp/db/kofam/profiles.tar.gz",
			"https://www.genome.jp/ftp/db/kofam/ko_list.gz",
			"https://www.genome.jp/ftp/db/kofam/",
			"https://www.genome.jp/tools/kofamkoala/"
		],
		"citeRequired": true,
		"citeRule": "Please cite the following article(s) when using KEGG.",
		"citeRuleUrl": "https://www.kegg.jp/kegg/kegg1.html",
		"cite": [
			{
				"key": "aramaki2020kofamkoala",
				"apa": "Aramaki, T., Blanc-Mathieu, R., Endo, H., Ohkubo, K., Kanehisa, M., Goto, S., & Ogata, H. (2019). KofamKOALA: KEGG Ortholog assignment based on profile HMM and adaptive score threshold. Bioinformatics, 36(7), 2251–2252. https://doi.org/10.1093/bioinformatics/btz859",
				"doi": "10.1093/bioinformatics/btz859",
				"bibtex": "@article{aramaki2020kofamkoala, title={KofamKOALA: KEGG Ortholog assignment based on profile HMM and adaptive score threshold}, volume={36}, ISSN={1367-4811}, url={http://dx.doi.org/10.1093/bioinformatics/btz859}, DOI={10.1093/bioinformatics/btz859}, number={7}, journal={Bioinformatics}, publisher={Oxford University Press (OUP)}, author={Aramaki, Takuya and Blanc-Mathieu, Romain and Endo, Hisashi and Ohkubo, Koichi and Kanehisa, Minoru and Goto, Susumu and Ogata, Hiroyuki}, editor={Valencia, Alfonso}, year={2019}, month=Nov, pages={2251–2252} }"
			},
			{
				"key": "kanehisa2025kegg",
				"apa": "Kanehisa, M., Furumichi, M., Sato, Y., Matsuura, Y., & Ishiguro-Watanabe, M. (2024). KEGG: biological systems database as a model of the real world. Nucleic Acids Research, 53(D1), D672–D677. https://doi.org/10.1093/nar/gkae909",
				"doi": "10.1093/nar/gkae909",
				"bibtex": "@article{kanehisa2025kegg, title={KEGG: biological systems database as a model of the real world}, volume={53}, ISSN={1362-4962}, url={http://dx.doi.org/10.1093/nar/gkae909}, DOI={10.1093/nar/gkae909}, number={D1}, journal={Nucleic Acids Research}, publisher={Oxford University Press (OUP)}, author={Kanehisa, Minoru and Furumichi, Miho and Sato, Yoko and Matsuura, Yuriko and Ishiguro-Watanabe, Mari}, year={2024}, month=Oct, pages={D672–D677} }"
			},
			{
				"key": "kanehisa2019kegg",
				"apa": "Kanehisa, M. (2019). Toward understanding the origin and evolution of cellular organisms. Protein Science, 28(11), 1947–1951. https://doi.org/10.1002/pro.3715",
				"doi": "10.1002/pro.3715",
				"bibtex": "@article{kanehisa2019kegg, title={Toward understanding the origin and evolution of cellular organisms}, volume={28}, ISSN={1469-896X}, url={http://dx.doi.org/10.1002/pro.3715}, DOI={10.1002/pro.3715}, number={11}, journal={Protein Science}, publisher={Wiley}, author={Kanehisa, Minoru}, year={2019}, month=Sept, pages={1947–1951} }"
			},
			{
				"key": "kanehisa2000kegg",
				"apa": "Kanehisa, M., & Goto, S. (2000). KEGG: Kyoto Encyclopedia of Genes and Genomes. Nucleic Acids Research, 28(1), 27–30. https://doi.org/10.1093/nar/28.1.27",
				"doi": "10.1093/nar/28.1.27",
				"bibtex": "@article{kanehisa2000kegg, title={KEGG: Kyoto Encyclopedia of Genes and Genomes}, volume={28}, ISSN={1362-4962}, url={http://dx.doi.org/10.1093/nar/28.1.27}, DOI={10.1093/nar/28.1.27}, number={1}, journal={Nucleic Acids Research}, publisher={Oxford University Press (OUP)}, author={Kanehisa, M. and Goto, S.}, year={2000}, month=Jan, pages={27–30} }"
			}
		]
	},
	{
		"id": "geneprop",
		"name": "Genome Properties (GenProp)",
		"role": "genome property (pathway completeness) inference",
		"phase": 4,
		"version": "Genome Properties (git HEAD)",
		"versionExact": false,
		"licence": "GPL-3.0 (repository LICENSE)",
		"licenceUrl": "https://github.com/ebi-pf-team/genome-properties/blob/master/LICENSE",
		"catalogLicence": "Tooling: verify with upstream (likely permissive); flatfiles: free for academic and commercial use",
		"source": "https://github.com/ebi-pf-team/genome-properties",
		"downloads": [
			"https://github.com/ebi-pf-team/genome-properties.git (shallow clone)"
		],
		"citeRequired": false,
		"citeRule": "",
		"citeRuleUrl": "https://genome-properties.readthedocs.io/en/latest/",
		"cite": [
			{
				"key": "richardson2019genprop",
				"apa": "Richardson, L. J., Rawlings, N. D., Salazar, G. A., Almeida, A., Haft, D. R., Ducq, G., Sutton, G. G., & Finn, R. D. (2018). Genome properties in 2019: a new companion database to InterPro for the inference of complete functional attributes. Nucleic Acids Research, 47(D1), D564–D572. https://doi.org/10.1093/nar/gky1013",
				"doi": "10.1093/nar/gky1013",
				"bibtex": "@article{richardson2019genprop, title={Genome properties in 2019: a new companion database to InterPro for the inference of complete functional attributes}, volume={47}, ISSN={1362-4962}, url={http://dx.doi.org/10.1093/nar/gky1013}, DOI={10.1093/nar/gky1013}, number={D1}, journal={Nucleic Acids Research}, publisher={Oxford University Press (OUP)}, author={Richardson, Lorna J and Rawlings, Neil D and Salazar, Gustavo A and Almeida, Alexandre and Haft, David R and Ducq, Gregory and Sutton, Granger G and Finn, Robert D}, year={2018}, month=Oct, pages={D564–D572} }"
			}
		]
	},
	{
		"id": "interpro",
		"name": "InterProScan (member databases)",
		"role": "protein domain and signature annotation",
		"phase": 4,
		"version": "InterProScan 5.77-108.0",
		"versionExact": true,
		"licence": "InterProScan Apache-2.0; member databases under their own terms",
		"licenceUrl": "https://github.com/ebi-pf-team/interproscan/blob/master/LICENSE",
		"catalogLicence": "",
		"source": "https://github.com/ebi-pf-team/interproscan",
		"downloads": [
			"https://ftp.ebi.ac.uk/pub/software/unix/iprscan/5/5.77-108.0/interproscan-5.77-108.0-64-bit.tar.gz",
			"https://github.com/ebi-pf-team/interproscan",
			"https://interproscan-docs.readthedocs.io/en/v5/HowToDownload.html"
		],
		"citeRequired": true,
		"citeRule": "If you find InterPro useful for your research, please cite the following publications:",
		"citeRuleUrl": "https://interproscan-docs.readthedocs.io/en/v5/Citing.html",
		"cite": [
			{
				"key": "blum2021interpro",
				"apa": "Blum, M., Chang, H.-Y., Chuguransky, S., Grego, T., Kandasaamy, S., Mitchell, A., Nuka, G., Paysan-Lafosse, T., Qureshi, M., Raj, S., Richardson, L., Salazar, G. A., Williams, L., Bork, P., Bridge, A., Gough, J., Haft, D. H., Letunic, I., Marchler-Bauer, A., et al. (2020). The InterPro protein families and domains database: 20 years on. Nucleic Acids Research, 49(D1), D344–D354. https://doi.org/10.1093/nar/gkaa977",
				"doi": "10.1093/nar/gkaa977",
				"bibtex": "@article{blum2021interpro, title={The InterPro protein families and domains database: 20 years on}, volume={49}, ISSN={1362-4962}, url={http://dx.doi.org/10.1093/nar/gkaa977}, DOI={10.1093/nar/gkaa977}, number={D1}, journal={Nucleic Acids Research}, publisher={Oxford University Press (OUP)}, author={Blum, Matthias and Chang, Hsin-Yu and Chuguransky, Sara and Grego, Tiago and Kandasaamy, Swaathi and Mitchell, Alex and Nuka, Gift and Paysan-Lafosse, Typhaine and Qureshi, Matloob and Raj, Shriya and Richardson, Lorna and Salazar, Gustavo A and Williams, Lowri and Bork, Peer and Bridge, Alan and Gough, Julian and Haft, Daniel H and Letunic, Ivica and Marchler-Bauer, Aron and Mi, Huaiyu and Natale, Darren A and Necci, Marco and Orengo, Christine A and Pandurangan, Arun P and Rivoire, Catherine and Sigrist, Christian J A and Sillitoe, Ian and Thanki, Narmada and Thomas, Paul D and Tosatto, Silvio C E and Wu, Cathy H and Bateman, Alex and Finn, Robert D}, year={2020}, month=Nov, pages={D344–D354} }"
			},
			{
				"key": "jones2014interproscan",
				"apa": "Jones, P., Binns, D., Chang, H.-Y., Fraser, M., Li, W., McAnulla, C., McWilliam, H., Maslen, J., Mitchell, A., Nuka, G., Pesseat, S., Quinn, A. F., Sangrador-Vegas, A., Scheremetjew, M., Yong, S.-Y., Lopez, R., & Hunter, S. (2014). InterProScan 5: genome-scale protein function classification. Bioinformatics, 30(9), 1236–1240. https://doi.org/10.1093/bioinformatics/btu031",
				"doi": "10.1093/bioinformatics/btu031",
				"bibtex": "@article{jones2014interproscan, title={InterProScan 5: genome-scale protein function classification}, volume={30}, ISSN={1367-4803}, url={http://dx.doi.org/10.1093/bioinformatics/btu031}, DOI={10.1093/bioinformatics/btu031}, number={9}, journal={Bioinformatics}, publisher={Oxford University Press (OUP)}, author={Jones, Philip and Binns, David and Chang, Hsin-Yu and Fraser, Matthew and Li, Weizhong and McAnulla, Craig and McWilliam, Hamish and Maslen, John and Mitchell, Alex and Nuka, Gift and Pesseat, Sebastien and Quinn, Antony F. and Sangrador-Vegas, Amaia and Scheremetjew, Maxim and Yong, Siew-Yit and Lopez, Rodrigo and Hunter, Sarah}, year={2014}, month=Jan, pages={1236–1240} }"
			}
		]
	},
	{
		"id": "eggnog",
		"name": "eggNOG-mapper + eggNOG DB",
		"role": "orthology-based functional annotation",
		"phase": 4,
		"version": "eggNOG-mapper 2.1.12; eggNOG DB 5.0.2",
		"versionExact": true,
		"licence": "eggNOG-mapper AGPL-3.0; eggNOG 5.0 database licence not verified",
		"licenceUrl": "https://github.com/eggnogdb/eggnog-mapper/blob/2.1.12/LICENSE.txt",
		"catalogLicence": "",
		"source": "https://github.com/eggnogdb/eggnog-mapper",
		"downloads": [
			"https://pypi.org/project/eggnog-mapper/2.1.12/",
			"https://github.com/eggnogdb/eggnog-mapper (source)",
			"http://eggnog5.embl.de/download/emapperdb-5.0.2/ (eggnog.db.gz, eggnog.taxa.tar.gz, eggnog_proteins.dmnd.gz)"
		],
		"citeRequired": true,
		"citeRule": "If you use this software, please cite:",
		"citeRuleUrl": "https://github.com/eggnogdb/eggnog-mapper/blob/2.1.12/README.md",
		"cite": [
			{
				"key": "cantalapiedra2021eggnogmapper",
				"apa": "Cantalapiedra, C. P., Hernández-Plaza, A., Letunic, I., Bork, P., & Huerta-Cepas, J. (2021). eggNOG-mapper v2: Functional Annotation, Orthology Assignments, and Domain Prediction at the Metagenomic Scale. Molecular Biology and Evolution, 38(12), 5825–5829. https://doi.org/10.1093/molbev/msab293",
				"doi": "10.1093/molbev/msab293",
				"bibtex": "@article{cantalapiedra2021eggnogmapper, title={eggNOG-mapper v2: Functional Annotation, Orthology Assignments, and Domain Prediction at the Metagenomic Scale}, volume={38}, ISSN={1537-1719}, url={http://dx.doi.org/10.1093/molbev/msab293}, DOI={10.1093/molbev/msab293}, number={12}, journal={Molecular Biology and Evolution}, publisher={Oxford University Press (OUP)}, author={Cantalapiedra, Carlos P and Hernández-Plaza, Ana and Letunic, Ivica and Bork, Peer and Huerta-Cepas, Jaime}, editor={Tamura, Koichiro}, year={2021}, month=Oct, pages={5825–5829} }"
			},
			{
				"key": "huertacepas2019eggnog5",
				"apa": "Huerta-Cepas, J., Szklarczyk, D., Heller, D., Hernández-Plaza, A., Forslund, S. K., Cook, H., Mende, D. R., Letunic, I., Rattei, T., Jensen, L., von Mering, C., & Bork, P. (2018). eggNOG 5.0: a hierarchical, functionally and phylogenetically annotated orthology resource based on 5090 organisms and 2502 viruses. Nucleic Acids Research, 47(D1), D309–D314. https://doi.org/10.1093/nar/gky1085",
				"doi": "10.1093/nar/gky1085",
				"bibtex": "@article{huertacepas2019eggnog5, title={eggNOG 5.0: a hierarchical, functionally and phylogenetically annotated orthology resource based on 5090 organisms and 2502 viruses}, volume={47}, ISSN={1362-4962}, url={http://dx.doi.org/10.1093/nar/gky1085}, DOI={10.1093/nar/gky1085}, number={D1}, journal={Nucleic Acids Research}, publisher={Oxford University Press (OUP)}, author={Huerta-Cepas, Jaime and Szklarczyk, Damian and Heller, Davide and Hernández-Plaza, Ana and Forslund, Sofia K and Cook, Helen and Mende, Daniel R and Letunic, Ivica and Rattei, Thomas and Jensen, Lars J and von Mering, Christian and Bork, Peer}, year={2018}, month=Nov, pages={D309–D314} }"
			},
			{
				"key": "buchfink2021diamond",
				"apa": "Buchfink, B., Reuter, K., & Drost, H.-G. (2021). Sensitive protein alignments at tree-of-life scale using DIAMOND. Nature Methods, 18(4), 366–368. https://doi.org/10.1038/s41592-021-01101-x",
				"doi": "10.1038/s41592-021-01101-x",
				"bibtex": "@article{buchfink2021diamond, title={Sensitive protein alignments at tree-of-life scale using DIAMOND}, volume={18}, ISSN={1548-7105}, url={http://dx.doi.org/10.1038/s41592-021-01101-x}, DOI={10.1038/s41592-021-01101-x}, number={4}, journal={Nature Methods}, publisher={Springer Science and Business Media LLC}, author={Buchfink, Benjamin and Reuter, Klaus and Drost, Hajk-Georg}, year={2021}, month=Apr, pages={366–368} }"
			}
		]
	},
	{
		"id": "dbcan",
		"name": "dbCAN + HMM database",
		"role": "carbohydrate-active enzyme (CAZyme) annotation",
		"phase": 4,
		"version": "dbCAN 5.1.2; DB v13",
		"versionExact": true,
		"licence": "run_dbcan GPL-3.0; dbCAN database licence not verified",
		"licenceUrl": "https://github.com/bcb-unl/run_dbcan/blob/master/LICENSE",
		"catalogLicence": "",
		"source": "https://github.com/bcb-unl/run_dbcan",
		"downloads": [
			"https://pypi.org/project/dbcan/5.1.2/",
			"https://bcb.unl.edu/dbCAN2/download/Databases/"
		],
		"citeRequired": true,
		"citeRule": "Please cite the following `dbCAN` publications if you use `run_dbcan` in your research:",
		"citeRuleUrl": "https://github.com/bcb-unl/run_dbcan/blob/v5.1.2/README.md",
		"cite": [
			{
				"key": "zheng2023dbcan3",
				"apa": "Zheng, J., Ge, Q., Yan, Y., Zhang, X., Huang, L., & Yin, Y. (2023). dbCAN3: automated carbohydrate-active enzyme and substrate annotation. Nucleic Acids Research, 51(W1), W115–W121. https://doi.org/10.1093/nar/gkad328",
				"doi": "10.1093/nar/gkad328",
				"bibtex": "@article{zheng2023dbcan3, title={dbCAN3: automated carbohydrate-active enzyme and substrate annotation}, volume={51}, ISSN={1362-4962}, url={http://dx.doi.org/10.1093/nar/gkad328}, DOI={10.1093/nar/gkad328}, number={W1}, journal={Nucleic Acids Research}, publisher={Oxford University Press (OUP)}, author={Zheng, Jinfang and Ge, Qiwei and Yan, Yuchen and Zhang, Xinpeng and Huang, Le and Yin, Yanbin}, year={2023}, month=May, pages={W115–W121} }"
			},
			{
				"key": "zhang2018dbcan2",
				"apa": "Zhang, H., Yohe, T., Huang, L., Entwistle, S., Wu, P., Yang, Z., Busk, P. K., Xu, Y., & Yin, Y. (2018). dbCAN2: a meta server for automated carbohydrate-active enzyme annotation. Nucleic Acids Research, 46(W1), W95–W101. https://doi.org/10.1093/nar/gky418",
				"doi": "10.1093/nar/gky418",
				"bibtex": "@article{zhang2018dbcan2, title={dbCAN2: a meta server for automated carbohydrate-active enzyme annotation}, volume={46}, ISSN={1362-4962}, url={http://dx.doi.org/10.1093/nar/gky418}, DOI={10.1093/nar/gky418}, number={W1}, journal={Nucleic Acids Research}, publisher={Oxford University Press (OUP)}, author={Zhang, Han and Yohe, Tanner and Huang, Le and Entwistle, Sarah and Wu, Peizhi and Yang, Zhenglu and Busk, Peter K and Xu, Ying and Yin, Yanbin}, year={2018}, month=May, pages={W95–W101} }"
			},
			{
				"key": "huang2018dbcanseq",
				"apa": "Huang, L., Zhang, H., Wu, P., Entwistle, S., Li, X., Yohe, T., Yi, H., Yang, Z., & Yin, Y. (2017). dbCAN-seq: a database of carbohydrate-active enzyme (CAZyme) sequence and annotation. Nucleic Acids Research, 46(D1), D516–D521. https://doi.org/10.1093/nar/gkx894",
				"doi": "10.1093/nar/gkx894",
				"bibtex": "@article{huang2018dbcanseq, title={dbCAN-seq: a database of carbohydrate-active enzyme (CAZyme) sequence and annotation}, volume={46}, ISSN={1362-4962}, url={http://dx.doi.org/10.1093/nar/gkx894}, DOI={10.1093/nar/gkx894}, number={D1}, journal={Nucleic Acids Research}, publisher={Oxford University Press (OUP)}, author={Huang, Le and Zhang, Han and Wu, Peizhi and Entwistle, Sarah and Li, Xueqiong and Yohe, Tanner and Yi, Haidong and Yang, Zhenglu and Yin, Yanbin}, year={2017}, month=Oct, pages={D516–D521} }"
			}
		]
	},
	{
		"id": "tigrfam",
		"name": "TIGRFAMs",
		"role": "TIGRFAMs protein family annotation",
		"phase": 4,
		"version": "TIGRFAMs 15.0; HMMER 3.4",
		"versionExact": true,
		"licence": "TIGRFAMs: GNU Library General Public License (per RELEASE_NOTE_15.0); HMMER BSD-3-Clause",
		"licenceUrl": "https://ftp.ncbi.nlm.nih.gov/hmm/TIGRFAMs/release_15.0/RELEASE_NOTE_15.0",
		"catalogLicence": "HMMER BSD-3-Clause; TIGRFAMs 15.0 CC-BY-SA 4.0",
		"source": "https://ftp.ncbi.nlm.nih.gov/hmm/TIGRFAMs/release_15.0/",
		"downloads": [
			"https://ftp.ncbi.nlm.nih.gov/hmm/TIGRFAMs/release_15.0/TIGRFAMs_15.0_HMM.LIB.gz",
			"https://ftp.ncbi.nlm.nih.gov/hmm/TIGRFAMs/release_15.0/"
		],
		"citeRequired": false,
		"citeRule": "",
		"citeRuleUrl": "https://ftp.ncbi.nlm.nih.gov/hmm/TIGRFAMs/release_15.0/RELEASE_NOTE_15.0",
		"cite": [
			{
				"key": "haft2013tigrfams",
				"apa": "Haft, D. H., Selengut, J. D., Richter, R. A., Harkins, D., Basu, M. K., & Beck, E. (2012). TIGRFAMs and Genome Properties in 2013. Nucleic Acids Research, 41(D1), D387–D395. https://doi.org/10.1093/nar/gks1234",
				"doi": "10.1093/nar/gks1234",
				"bibtex": "@article{haft2013tigrfams, title={TIGRFAMs and Genome Properties in 2013}, volume={41}, ISSN={1362-4962}, url={http://dx.doi.org/10.1093/nar/gks1234}, DOI={10.1093/nar/gks1234}, number={D1}, journal={Nucleic Acids Research}, publisher={Oxford University Press (OUP)}, author={Haft, Daniel H. and Selengut, Jeremy D. and Richter, Roland A. and Harkins, Derek and Basu, Malay K. and Beck, Erin}, year={2012}, month=Nov, pages={D387–D395} }"
			},
			{
				"key": "eddy2011hmmer",
				"apa": "Eddy, S. R. (2011). Accelerated Profile HMM Searches. PLoS Computational Biology, 7(10), e1002195. https://doi.org/10.1371/journal.pcbi.1002195",
				"doi": "10.1371/journal.pcbi.1002195",
				"bibtex": "@article{eddy2011hmmer, title={Accelerated Profile HMM Searches}, volume={7}, ISSN={1553-7358}, url={http://dx.doi.org/10.1371/journal.pcbi.1002195}, DOI={10.1371/journal.pcbi.1002195}, number={10}, journal={PLoS Computational Biology}, publisher={Public Library of Science (PLoS)}, author={Eddy, Sean R.}, editor={Pearson, William R.}, year={2011}, month=Oct, pages={e1002195} }"
			}
		]
	},
	{
		"id": "uniprot",
		"name": "UniProt Swiss-Prot + DIAMOND",
		"role": "Swiss-Prot homology annotation",
		"phase": 4,
		"version": "Swiss-Prot 2025_05; DIAMOND 2.1.9",
		"versionExact": true,
		"licence": "UniProt CC BY 4.0; DIAMOND GPL-3.0",
		"licenceUrl": "https://ftp.uniprot.org/pub/databases/uniprot/current_release/knowledgebase/complete/LICENSE",
		"catalogLicence": "",
		"source": "https://github.com/bbuchfink/diamond",
		"downloads": [
			"https://ftp.uniprot.org/pub/databases/uniprot/current_release/knowledgebase/complete/uniprot_sprot.fasta.gz",
			"https://ftp.uniprot.org/pub/databases/uniprot/current_release/knowledgebase/complete/"
		],
		"citeRequired": true,
		"citeRule": "If you find UniProt useful, please consider citing our latest publication:",
		"citeRuleUrl": "https://www.uniprot.org/help/publications",
		"cite": [
			{
				"key": "uniprot2025",
				"apa": "The UniProt Consortium, Bateman, A., Martin, M.-J., Orchard, S., Magrane, M., Adesina, A., Ahmad, S., Bowler-Barnett, E. H., Bye-A-Jee, H., Carpentier, D., Denny, P., Fan, J., Garmiri, P., Gonzales, L. J. d. C., Hussein, A., Ignatchenko, A., Insana, G., Ishtiaq, R., Joshi, V., et al. (2024). UniProt: the Universal Protein Knowledgebase in 2025. Nucleic Acids Research, 53(D1), D609–D617. https://doi.org/10.1093/nar/gkae1010",
				"doi": "10.1093/nar/gkae1010",
				"bibtex": "@article{uniprot2025, title={UniProt: the Universal Protein Knowledgebase in 2025}, volume={53}, ISSN={1362-4962}, url={http://dx.doi.org/10.1093/nar/gkae1010}, DOI={10.1093/nar/gkae1010}, number={D1}, journal={Nucleic Acids Research}, publisher={Oxford University Press (OUP)}, author={{The UniProt Consortium} and Bateman, Alex and Martin, Maria-Jesus and Orchard, Sandra and Magrane, Michele and Adesina, Aduragbemi and Ahmad, Shadab and Bowler-Barnett, Emily H and Bye-A-Jee, Hema and Carpentier, David and Denny, Paul and Fan, Jun and Garmiri, Penelope and Gonzales, Leonardo Jose da Costa and Hussein, Abdulrahman and Ignatchenko, Alexandr and Insana, Giuseppe and Ishtiaq, Rizwan and Joshi, Vishal and Jyothi, Dushyanth and Kandasaamy, Swaathi and Lock, Antonia and Luciani, Aurelien and Luo, Jie and Lussi, Yvonne and Marin, Juan Sebastian Martinez and Raposo, Pedro and Rice, Daniel L and Santos, Rafael and Speretta, Elena and Stephenson, James and Totoo, Prabhat and Tyagi, Nidhi and Urakova, Nadya and Vasudev, Preethi and Warner, Kate and Wijerathne, Supun and Yu, Conny Wing-Heng and Zaru, Rossana and Bridge, Alan J and Aimo, Lucila and Argoud-Puy, Ghislaine and Auchincloss, Andrea H and Axelsen, Kristian B and Bansal, Parit and Baratin, Delphine and Batista Neto, Teresa M and Blatter, Marie-Claude and Bolleman, Jerven T and Boutet, Emmanuel and Breuza, Lionel and Gil, Blanca Cabrera and Casals-Casas, Cristina and Echioukh, Kamal Chikh and Coudert, Elisabeth and Cuche, Beatrice and de Castro, Edouard and Estreicher, Anne and Famiglietti, Maria L and Feuermann, Marc and Gasteiger, Elisabeth and Gaudet, Pascale and Gehant, Sebastien and Gerritsen, Vivienne and Gos, Arnaud and Gruaz, Nadine and Hulo, Chantal and Hyka-Nouspikel, Nevila and Jungo, Florence and Kerhornou, Arnaud and Mercier, Philippe Le and Lieberherr, Damien and Masson, Patrick and Morgat, Anne and Paesano, Salvo and Pedruzzi, Ivo and Pilbout, Sandrine and Pourcel, Lucille and Poux, Sylvain and Pozzato, Monica and Pruess, Manuela and Redaschi, Nicole and Rivoire, Catherine and Sigrist, Christian J A and Sonesson, Karin and Sundaram, Shyamala and Sveshnikova, Anastasia and Wu, Cathy H and Arighi, Cecilia N and Chen, Chuming and Chen, Yongxing and Huang, Hongzhan and Laiho, Kati and Lehvaslaiho, Minna and McGarvey, Peter and Natale, Darren A and Ross, Karen and Vinayaka, C R and Wang, Yuqi and Zhang, Jian}, year={2024}, month=Nov, pages={D609–D617} }"
			},
			{
				"key": "buchfink2021diamond",
				"apa": "Buchfink, B., Reuter, K., & Drost, H.-G. (2021). Sensitive protein alignments at tree-of-life scale using DIAMOND. Nature Methods, 18(4), 366–368. https://doi.org/10.1038/s41592-021-01101-x",
				"doi": "10.1038/s41592-021-01101-x",
				"bibtex": "@article{buchfink2021diamond, title={Sensitive protein alignments at tree-of-life scale using DIAMOND}, volume={18}, ISSN={1548-7105}, url={http://dx.doi.org/10.1038/s41592-021-01101-x}, DOI={10.1038/s41592-021-01101-x}, number={4}, journal={Nature Methods}, publisher={Springer Science and Business Media LLC}, author={Buchfink, Benjamin and Reuter, Klaus and Drost, Hajk-Georg}, year={2021}, month=Apr, pages={366–368} }"
			}
		]
	},
	{
		"id": "gtdbtk",
		"name": "GTDB-Tk",
		"role": "taxonomic classification",
		"phase": 2,
		"version": "GTDB-Tk 2.7.0; GTDB r232",
		"versionExact": true,
		"licence": "GTDB-Tk GPL-3.0; GTDB data CC BY-SA 4.0",
		"licenceUrl": "https://github.com/Ecogenomics/GTDBTk/blob/master/LICENSE",
		"catalogLicence": "",
		"source": "https://github.com/Ecogenomics/GTDBTk",
		"downloads": [
			"Bioconda gtdbtk=2.7.0",
			"https://data.ace.uq.edu.au/public/gtdb/data/releases/latest/auxillary_files/gtdbtk_package/full_package/gtdbtk_data.tar.gz",
			"https://gtdb.ecogenomic.org/downloads"
		],
		"citeRequired": true,
		"citeRule": "If you use the GTDB-Tk please cite:",
		"citeRuleUrl": "https://gtdb.ecogenomic.org/about",
		"cite": [
			{
				"key": "chaumeil2022gtdbtk2",
				"apa": "Chaumeil, P.-A., Mussig, A. J., Hugenholtz, P., & Parks, D. H. (2022). GTDB-Tk v2: memory friendly classification with the genome taxonomy database. Bioinformatics, 38(23), 5315–5316. https://doi.org/10.1093/bioinformatics/btac672",
				"doi": "10.1093/bioinformatics/btac672",
				"bibtex": "@article{chaumeil2022gtdbtk2, title={GTDB-Tk v2: memory friendly classification with the genome taxonomy database}, volume={38}, ISSN={1367-4811}, url={http://dx.doi.org/10.1093/bioinformatics/btac672}, DOI={10.1093/bioinformatics/btac672}, number={23}, journal={Bioinformatics}, publisher={Oxford University Press (OUP)}, author={Chaumeil, Pierre-Alain and Mussig, Aaron J and Hugenholtz, Philip and Parks, Donovan H}, editor={Borgwardt, Karsten}, year={2022}, month=Oct, pages={5315–5316} }"
			},
			{
				"key": "chaumeil2019gtdbtk",
				"apa": "Chaumeil, P.-A., Mussig, A. J., Hugenholtz, P., & Parks, D. H. (2019). GTDB-Tk: a toolkit to classify genomes with the Genome Taxonomy Database. Bioinformatics, 36(6), 1925–1927. https://doi.org/10.1093/bioinformatics/btz848",
				"doi": "10.1093/bioinformatics/btz848",
				"bibtex": "@article{chaumeil2019gtdbtk, title={GTDB-Tk: a toolkit to classify genomes with the Genome Taxonomy Database}, volume={36}, ISSN={1367-4811}, url={http://dx.doi.org/10.1093/bioinformatics/btz848}, DOI={10.1093/bioinformatics/btz848}, number={6}, journal={Bioinformatics}, publisher={Oxford University Press (OUP)}, author={Chaumeil, Pierre-Alain and Mussig, Aaron J and Hugenholtz, Philip and Parks, Donovan H}, editor={Hancock, John}, year={2019}, month=Nov, pages={1925–1927} }"
			},
			{
				"key": "parks2025gtdb10",
				"apa": "Parks, D. H., Chaumeil, P.-A., Mussig, A. J., Rinke, C., Chuvochina, M., & Hugenholtz, P. (2025). GTDB release 10: a complete and systematic taxonomy for 715 230 bacterial and 17 245 archaeal genomes. Nucleic Acids Research, 54(D1), D743–D754. https://doi.org/10.1093/nar/gkaf1040",
				"doi": "10.1093/nar/gkaf1040",
				"bibtex": "@article{parks2025gtdb10, title={GTDB release 10: a complete and systematic taxonomy for 715 230 bacterial and 17 245 archaeal genomes}, volume={54}, ISSN={1362-4962}, url={http://dx.doi.org/10.1093/nar/gkaf1040}, DOI={10.1093/nar/gkaf1040}, number={D1}, journal={Nucleic Acids Research}, publisher={Oxford University Press (OUP)}, author={Parks, Donovan H and Chaumeil, Pierre-Alain and Mussig, Aaron J and Rinke, Christian and Chuvochina, Maria and Hugenholtz, Philip}, year={2025}, month=Oct, pages={D743–D754} }"
			},
			{
				"key": "chuvochina2023gtdbnames",
				"apa": "Chuvochina, M., Mussig, A. J., Chaumeil, P.-A., Skarshewski, A., Rinke, C., Parks, D. H., & Hugenholtz, P. (2023). Proposal of names for 329 higher rank taxa defined in the Genome Taxonomy Database under two prokaryotic codes. FEMS Microbiology Letters, 370. https://doi.org/10.1093/femsle/fnad071",
				"doi": "10.1093/femsle/fnad071",
				"bibtex": "@article{chuvochina2023gtdbnames, title={Proposal of names for 329 higher rank taxa defined in the Genome Taxonomy Database under two prokaryotic codes}, volume={370}, ISSN={1574-6968}, url={http://dx.doi.org/10.1093/femsle/fnad071}, DOI={10.1093/femsle/fnad071}, journal={FEMS Microbiology Letters}, publisher={Oxford University Press (OUP)}, author={Chuvochina, Maria and Mussig, Aaron J and Chaumeil, Pierre-Alain and Skarshewski, Adam and Rinke, Christian and Parks, Donovan H and Hugenholtz, Philip}, year={2023} }"
			},
			{
				"key": "parks2022gtdb",
				"apa": "Parks, D. H., Chuvochina, M., Rinke, C., Mussig, A. J., Chaumeil, P.-A., & Hugenholtz, P. (2021). GTDB: an ongoing census of bacterial and archaeal diversity through a phylogenetically consistent, rank normalized and complete genome-based taxonomy. Nucleic Acids Research, 50(D1), D785–D794. https://doi.org/10.1093/nar/gkab776",
				"doi": "10.1093/nar/gkab776",
				"bibtex": "@article{parks2022gtdb, title={GTDB: an ongoing census of bacterial and archaeal diversity through a phylogenetically consistent, rank normalized and complete genome-based taxonomy}, volume={50}, ISSN={1362-4962}, url={http://dx.doi.org/10.1093/nar/gkab776}, DOI={10.1093/nar/gkab776}, number={D1}, journal={Nucleic Acids Research}, publisher={Oxford University Press (OUP)}, author={Parks, Donovan H and Chuvochina, Maria and Rinke, Christian and Mussig, Aaron J and Chaumeil, Pierre-Alain and Hugenholtz, Philip}, year={2021}, month=Sept, pages={D785–D794} }"
			},
			{
				"key": "rinke2021gtdbarchaea",
				"apa": "Rinke, C., Chuvochina, M., Mussig, A. J., Chaumeil, P.-A., Davín, A. A., Waite, D. W., Whitman, W. B., Parks, D. H., & Hugenholtz, P. (2021). A standardized archaeal taxonomy for the Genome Taxonomy Database. Nature Microbiology, 6(7), 946–959. https://doi.org/10.1038/s41564-021-00918-8",
				"doi": "10.1038/s41564-021-00918-8",
				"bibtex": "@article{rinke2021gtdbarchaea, title={A standardized archaeal taxonomy for the Genome Taxonomy Database}, volume={6}, ISSN={2058-5276}, url={http://dx.doi.org/10.1038/s41564-021-00918-8}, DOI={10.1038/s41564-021-00918-8}, number={7}, journal={Nature Microbiology}, publisher={Springer Science and Business Media LLC}, author={Rinke, Christian and Chuvochina, Maria and Mussig, Aaron J. and Chaumeil, Pierre-Alain and Davín, Adrián A. and Waite, David W. and Whitman, William B. and Parks, Donovan H. and Hugenholtz, Philip}, year={2021}, month=June, pages={946–959} }"
			},
			{
				"key": "parks2020gtdbspecies",
				"apa": "Parks, D. H., Chuvochina, M., Chaumeil, P.-A., Rinke, C., Mussig, A. J., & Hugenholtz, P. (2020). A complete domain-to-species taxonomy for Bacteria and Archaea. Nature Biotechnology, 38(9), 1079–1086. https://doi.org/10.1038/s41587-020-0501-8",
				"doi": "10.1038/s41587-020-0501-8",
				"bibtex": "@article{parks2020gtdbspecies, title={A complete domain-to-species taxonomy for Bacteria and Archaea}, volume={38}, ISSN={1546-1696}, url={http://dx.doi.org/10.1038/s41587-020-0501-8}, DOI={10.1038/s41587-020-0501-8}, number={9}, journal={Nature Biotechnology}, publisher={Springer Science and Business Media LLC}, author={Parks, Donovan H. and Chuvochina, Maria and Chaumeil, Pierre-Alain and Rinke, Christian and Mussig, Aaron J. and Hugenholtz, Philip}, year={2020}, month=Apr, pages={1079–1086} }"
			},
			{
				"key": "parks2018gtdb",
				"apa": "Parks, D. H., Chuvochina, M., Waite, D. W., Rinke, C., Skarshewski, A., Chaumeil, P.-A., & Hugenholtz, P. (2018). A standardized bacterial taxonomy based on genome phylogeny substantially revises the tree of life. Nature Biotechnology, 36(10), 996–1004. https://doi.org/10.1038/nbt.4229",
				"doi": "10.1038/nbt.4229",
				"bibtex": "@article{parks2018gtdb, title={A standardized bacterial taxonomy based on genome phylogeny substantially revises the tree of life}, volume={36}, ISSN={1546-1696}, url={http://dx.doi.org/10.1038/nbt.4229}, DOI={10.1038/nbt.4229}, number={10}, journal={Nature Biotechnology}, publisher={Springer Science and Business Media LLC}, author={Parks, Donovan H and Chuvochina, Maria and Waite, David W and Rinke, Christian and Skarshewski, Adam and Chaumeil, Pierre-Alain and Hugenholtz, Philip}, year={2018}, month=Aug, pages={996–1004} }"
			},
			{
				"key": "matsen2010pplacer",
				"apa": "Matsen, F. A., Kodner, R. B., & Armbrust, E. V. (2010). pplacer: linear time maximum-likelihood and Bayesian phylogenetic placement of sequences onto a fixed reference tree. BMC Bioinformatics, 11(1). https://doi.org/10.1186/1471-2105-11-538",
				"doi": "10.1186/1471-2105-11-538",
				"bibtex": "@article{matsen2010pplacer, title={pplacer: linear time maximum-likelihood and Bayesian phylogenetic placement of sequences onto a fixed reference tree}, volume={11}, ISSN={1471-2105}, url={http://dx.doi.org/10.1186/1471-2105-11-538}, DOI={10.1186/1471-2105-11-538}, number={1}, journal={BMC Bioinformatics}, publisher={Springer Science and Business Media LLC}, author={Matsen, Frederick A and Kodner, Robin B and Armbrust, E Virginia}, year={2010}, month=Oct }"
			},
			{
				"key": "shaw2023skani",
				"apa": "Shaw, J., & Yu, Y. W. (2023). Fast and robust metagenomic sequence comparison through sparse chaining with skani. Nature Methods, 20(11), 1661–1665. https://doi.org/10.1038/s41592-023-02018-3",
				"doi": "10.1038/s41592-023-02018-3",
				"bibtex": "@article{shaw2023skani, title={Fast and robust metagenomic sequence comparison through sparse chaining with skani}, volume={20}, ISSN={1548-7105}, url={http://dx.doi.org/10.1038/s41592-023-02018-3}, DOI={10.1038/s41592-023-02018-3}, number={11}, journal={Nature Methods}, publisher={Springer Science and Business Media LLC}, author={Shaw, Jim and Yu, Yun William}, year={2023}, month=Sept, pages={1661–1665} }"
			},
			{
				"key": "hyatt2010prodigal",
				"apa": "Hyatt, D., Chen, G.-L., LoCascio, P. F., Land, M. L., Larimer, F. W., & Hauser, L. J. (2010). Prodigal: prokaryotic gene recognition and translation initiation site identification. BMC Bioinformatics, 11(1). https://doi.org/10.1186/1471-2105-11-119",
				"doi": "10.1186/1471-2105-11-119",
				"bibtex": "@article{hyatt2010prodigal, title={Prodigal: prokaryotic gene recognition and translation initiation site identification}, volume={11}, ISSN={1471-2105}, url={http://dx.doi.org/10.1186/1471-2105-11-119}, DOI={10.1186/1471-2105-11-119}, number={1}, journal={BMC Bioinformatics}, publisher={Springer Science and Business Media LLC}, author={Hyatt, Doug and Chen, Gwo-Liang and LoCascio, Philip F and Land, Miriam L and Larimer, Frank W and Hauser, Loren J}, year={2010}, month=Mar }"
			},
			{
				"key": "price2010fasttree2",
				"apa": "Price, M. N., Dehal, P. S., & Arkin, A. P. (2010). FastTree 2 – Approximately Maximum-Likelihood Trees for Large Alignments. PLoS ONE, 5(3), e9490. https://doi.org/10.1371/journal.pone.0009490",
				"doi": "10.1371/journal.pone.0009490",
				"bibtex": "@article{price2010fasttree2, title={FastTree 2 – Approximately Maximum-Likelihood Trees for Large Alignments}, volume={5}, ISSN={1932-6203}, url={http://dx.doi.org/10.1371/journal.pone.0009490}, DOI={10.1371/journal.pone.0009490}, number={3}, journal={PLoS ONE}, publisher={Public Library of Science (PLoS)}, author={Price, Morgan N. and Dehal, Paramvir S. and Arkin, Adam P.}, editor={Poon, Art F. Y.}, year={2010}, month=Mar, pages={e9490} }"
			},
			{
				"key": "eddy2011hmmer",
				"apa": "Eddy, S. R. (2011). Accelerated Profile HMM Searches. PLoS Computational Biology, 7(10), e1002195. https://doi.org/10.1371/journal.pcbi.1002195",
				"doi": "10.1371/journal.pcbi.1002195",
				"bibtex": "@article{eddy2011hmmer, title={Accelerated Profile HMM Searches}, volume={7}, ISSN={1553-7358}, url={http://dx.doi.org/10.1371/journal.pcbi.1002195}, DOI={10.1371/journal.pcbi.1002195}, number={10}, journal={PLoS Computational Biology}, publisher={Public Library of Science (PLoS)}, author={Eddy, Sean R.}, editor={Pearson, William R.}, year={2011}, month=Oct, pages={e1002195} }"
			}
		]
	},
	{
		"id": "deepsig",
		"name": "DeepSig",
		"role": "signal peptide prediction (DeepSig)",
		"phase": 7,
		"version": "DeepSig (bolognabiocomp pinned digest)",
		"versionExact": false,
		"licence": "GPL-3.0",
		"licenceUrl": "https://github.com/BolognaBiocomp/deepsig/blob/master/LICENSE",
		"catalogLicence": "",
		"source": "https://github.com/BolognaBiocomp/deepsig",
		"downloads": [
			"https://github.com/BolognaBiocomp/deepsig",
			"docker: bolognabiocomp/deepsig (pinned sha256)"
		],
		"citeRequired": false,
		"citeRule": "",
		"citeRuleUrl": "https://github.com/BolognaBiocomp/deepsig/blob/master/README.md",
		"cite": [
			{
				"key": "savojardo2018deepsig",
				"apa": "Savojardo, C., Martelli, P. L., Fariselli, P., & Casadio, R. (2017). DeepSig: deep learning improves signal peptide detection in proteins. Bioinformatics, 34(10), 1690–1696. https://doi.org/10.1093/bioinformatics/btx818",
				"doi": "10.1093/bioinformatics/btx818",
				"bibtex": "@article{savojardo2018deepsig, title={DeepSig: deep learning improves signal peptide detection in proteins}, volume={34}, ISSN={1367-4811}, url={http://dx.doi.org/10.1093/bioinformatics/btx818}, DOI={10.1093/bioinformatics/btx818}, number={10}, journal={Bioinformatics}, publisher={Oxford University Press (OUP)}, author={Savojardo, Castrense and Martelli, Pier Luigi and Fariselli, Piero and Casadio, Rita}, editor={Valencia, Alfonso}, year={2017}, month=Dec, pages={1690–1696} }"
			}
		]
	},
	{
		"id": "psortb",
		"name": "PSORTb",
		"role": "subcellular localization prediction",
		"phase": 7,
		"version": "PSORTb 3.0 (brinkmanlab/psortb_commandline:1.0.2)",
		"versionExact": true,
		"licence": "GPL-3.0 (psortb_commandline_docker README); PSORTb 3.0 source COPYING GPL-2.0-or-later per the catalog, not verified",
		"licenceUrl": "https://github.com/brinkmanlab/psortb_commandline_docker/blob/master/README.md",
		"catalogLicence": "",
		"source": "https://github.com/brinkmanlab/psortb_commandline_docker",
		"downloads": [
			"https://github.com/brinkmanlab/psortb_commandline_docker",
			"docker: brinkmanlab/psortb_commandline:1.0.2"
		],
		"citeRequired": false,
		"citeRule": "",
		"citeRuleUrl": "https://www.psort.org/psortb/",
		"cite": [
			{
				"key": "yu2010psortb",
				"apa": "Yu, N. Y., Wagner, J. R., Laird, M. R., Melli, G., Rey, S., Lo, R., Dao, P., Sahinalp, S. C., Ester, M., Foster, L. J., & Brinkman, F. S. L. (2010). PSORTb 3.0: improved protein subcellular localization prediction with refined localization subcategories and predictive capabilities for all prokaryotes. Bioinformatics, 26(13), 1608–1615. https://doi.org/10.1093/bioinformatics/btq249",
				"doi": "10.1093/bioinformatics/btq249",
				"bibtex": "@article{yu2010psortb, title={PSORTb 3.0: improved protein subcellular localization prediction with refined localization subcategories and predictive capabilities for all prokaryotes}, volume={26}, ISSN={1367-4803}, url={http://dx.doi.org/10.1093/bioinformatics/btq249}, DOI={10.1093/bioinformatics/btq249}, number={13}, journal={Bioinformatics}, publisher={Oxford University Press (OUP)}, author={Yu, Nancy Y. and Wagner, James R. and Laird, Matthew R. and Melli, Gabor and Rey, Sébastien and Lo, Raymond and Dao, Phuong and Sahinalp, S. Cenk and Ester, Martin and Foster, Leonard J. and Brinkman, Fiona S. L.}, year={2010}, month=May, pages={1608–1615} }"
			}
		]
	},
	{
		"id": "rasttk",
		"name": "RASTtk / SEED",
		"role": "gene calling and core annotation",
		"phase": 3,
		"version": "BV-BRC CLI 1.040; SEED (margie-annotation latest)",
		"versionExact": false,
		"licence": "BV-BRC CLI MIT; SEED subsystems terms not verified",
		"licenceUrl": "https://github.com/BV-BRC/BV-BRC-CLI/blob/master/LICENSE.md",
		"catalogLicence": "BSD-3-Clause-style; SEED subsystems free for academic and commercial use",
		"source": "https://github.com/BV-BRC/BV-BRC-CLI",
		"downloads": [
			"https://github.com/BV-BRC/BV-BRC-CLI/releases/tag/1.040 (bvbrc-cli-1.040.deb)"
		],
		"citeRequired": true,
		"citeRule": "If you use BV-BRC web resources to assist in research publications or proposals, please cite as:",
		"citeRuleUrl": "https://www.bv-brc.org/citation",
		"cite": [
			{
				"key": "olson2023bvbrc",
				"apa": "Olson, R. D., Assaf, R., Brettin, T., Conrad, N., Cucinell, C., Davis, J., Dempsey, D., Dickerman, A., Dietrich, E., Kenyon, R., Kuscuoglu, M., Lefkowitz, E., Lu, J., Machi, D., Macken, C., Mao, C., Niewiadomska, A., Nguyen, M., Olsen, G., et al. (2022). Introducing the Bacterial and Viral Bioinformatics Resource Center (BV-BRC): a resource combining PATRIC, IRD and ViPR. Nucleic Acids Research, 51(D1), D678–D689. https://doi.org/10.1093/nar/gkac1003",
				"doi": "10.1093/nar/gkac1003",
				"bibtex": "@article{olson2023bvbrc, title={Introducing the Bacterial and Viral Bioinformatics Resource Center (BV-BRC): a resource combining PATRIC, IRD and ViPR}, volume={51}, ISSN={1362-4962}, url={http://dx.doi.org/10.1093/nar/gkac1003}, DOI={10.1093/nar/gkac1003}, number={D1}, journal={Nucleic Acids Research}, publisher={Oxford University Press (OUP)}, author={Olson, Robert D and Assaf, Rida and Brettin, Thomas and Conrad, Neal and Cucinell, Clark and Davis, James J and Dempsey, Donald M and Dickerman, Allan and Dietrich, Emily M and Kenyon, Ronald W and Kuscuoglu, Mehmet and Lefkowitz, Elliot J and Lu, Jian and Machi, Dustin and Macken, Catherine and Mao, Chunhong and Niewiadomska, Anna and Nguyen, Marcus and Olsen, Gary J and Overbeek, Jamie C and Parrello, Bruce and Parrello, Victoria and Porter, Jacob S and Pusch, Gordon D and Shukla, Maulik and Singh, Indresh and Stewart, Lucy and Tan, Gene and Thomas, Chris and VanOeffelen, Margo and Vonstein, Veronika and Wallace, Zachary S and Warren, Andrew S and Wattam, Alice R and Xia, Fangfang and Yoo, Hyunseung and Zhang, Yun and Zmasek, Christian M and Scheuermann, Richard H and Stevens, Rick L}, year={2022}, month=Nov, pages={D678–D689} }"
			},
			{
				"key": "brettin2015rasttk",
				"apa": "Brettin, T., Davis, J. J., Disz, T., Edwards, R. A., Gerdes, S., Olsen, G. J., Olson, R., Overbeek, R., Parrello, B., Pusch, G. D., Shukla, M., Thomason, J. A., Stevens, R., Vonstein, V., Wattam, A. R., & Xia, F. (2015). RASTtk: A modular and extensible implementation of the RAST algorithm for building custom annotation pipelines and annotating batches of genomes. Scientific Reports, 5(1). https://doi.org/10.1038/srep08365",
				"doi": "10.1038/srep08365",
				"bibtex": "@article{brettin2015rasttk, title={RASTtk: A modular and extensible implementation of the RAST algorithm for building custom annotation pipelines and annotating batches of genomes}, volume={5}, ISSN={2045-2322}, url={http://dx.doi.org/10.1038/srep08365}, DOI={10.1038/srep08365}, number={1}, journal={Scientific Reports}, publisher={Springer Science and Business Media LLC}, author={Brettin, Thomas and Davis, James J. and Disz, Terry and Edwards, Robert A. and Gerdes, Svetlana and Olsen, Gary J. and Olson, Robert and Overbeek, Ross and Parrello, Bruce and Pusch, Gordon D. and Shukla, Maulik and Thomason, James A. and Stevens, Rick and Vonstein, Veronika and Wattam, Alice R. and Xia, Fangfang}, year={2015}, month=Feb }"
			}
		]
	},
	{
		"id": "pfam",
		"name": "Pfam + HMMER",
		"role": "protein family (domain) annotation",
		"phase": 4,
		"version": "HMMER 3.4; Pfam-A 37.0",
		"versionExact": true,
		"licence": "Pfam CC0 1.0; HMMER BSD-3-Clause",
		"licenceUrl": "https://ftp.ebi.ac.uk/pub/databases/Pfam/releases/Pfam37.0/relnotes.txt",
		"catalogLicence": "",
		"source": "https://github.com/EddyRivasLab/hmmer",
		"downloads": [
			"http://eddylab.org/software/hmmer/hmmer-3.4.tar.gz",
			"https://ftp.ebi.ac.uk/pub/databases/Pfam/releases/Pfam37.0/Pfam-A.hmm.gz",
			"https://ftp.ebi.ac.uk/pub/databases/Pfam/releases/Pfam37.0/"
		],
		"citeRequired": false,
		"citeRule": "",
		"citeRuleUrl": "https://pfam-docs.readthedocs.io/en/latest/citing-pfam.html",
		"cite": [
			{
				"key": "paysanlafosse2025pfam",
				"apa": "Paysan-Lafosse, T., Andreeva, A., Blum, M., Chuguransky, S., Grego, T., Pinto, B., Salazar, G., Bileschi, M., Llinares-López, F., Meng-Papaxanthos, L., Colwell, L., Grishin, N., Schaeffer, R. D., Clementel, D., Tosatto, S. E., Sonnhammer, E., Wood, V., & Bateman, A. (2024). The Pfam protein families database: embracing AI/ML. Nucleic Acids Research, 53(D1), D523–D534. https://doi.org/10.1093/nar/gkae997",
				"doi": "10.1093/nar/gkae997",
				"bibtex": "@article{paysanlafosse2025pfam, title={The Pfam protein families database: embracing AI/ML}, volume={53}, ISSN={1362-4962}, url={http://dx.doi.org/10.1093/nar/gkae997}, DOI={10.1093/nar/gkae997}, number={D1}, journal={Nucleic Acids Research}, publisher={Oxford University Press (OUP)}, author={Paysan-Lafosse, Typhaine and Andreeva, Antonina and Blum, Matthias and Chuguransky, Sara Rocio and Grego, Tiago and Pinto, Beatriz Lazaro and Salazar, Gustavo A and Bileschi, Maxwell L and Llinares-López, Felipe and Meng-Papaxanthos, Laetitia and Colwell, Lucy J and Grishin, Nick V and Schaeffer, R Dustin and Clementel, Damiano and Tosatto, Silvio C E and Sonnhammer, Erik and Wood, Valerie and Bateman, Alex}, year={2024}, month=Nov, pages={D523–D534} }"
			},
			{
				"key": "mistry2021pfam",
				"apa": "Mistry, J., Chuguransky, S., Williams, L., Qureshi, M., Salazar, G., Sonnhammer, E. L. L., Tosatto, S. C. E., Paladin, L., Raj, S., Richardson, L. J., Finn, R. D., & Bateman, A. (2020). Pfam: The protein families database in 2021. Nucleic Acids Research, 49(D1), D412–D419. https://doi.org/10.1093/nar/gkaa913",
				"doi": "10.1093/nar/gkaa913",
				"bibtex": "@article{mistry2021pfam, title={Pfam: The protein families database in 2021}, volume={49}, ISSN={1362-4962}, url={http://dx.doi.org/10.1093/nar/gkaa913}, DOI={10.1093/nar/gkaa913}, number={D1}, journal={Nucleic Acids Research}, publisher={Oxford University Press (OUP)}, author={Mistry, Jaina and Chuguransky, Sara and Williams, Lowri and Qureshi, Matloob and Salazar, Gustavo A and Sonnhammer, Erik L L and Tosatto, Silvio C E and Paladin, Lisanna and Raj, Shriya and Richardson, Lorna J and Finn, Robert D and Bateman, Alex}, year={2020}, month=Oct, pages={D412–D419} }"
			},
			{
				"key": "eddy2011hmmer",
				"apa": "Eddy, S. R. (2011). Accelerated Profile HMM Searches. PLoS Computational Biology, 7(10), e1002195. https://doi.org/10.1371/journal.pcbi.1002195",
				"doi": "10.1371/journal.pcbi.1002195",
				"bibtex": "@article{eddy2011hmmer, title={Accelerated Profile HMM Searches}, volume={7}, ISSN={1553-7358}, url={http://dx.doi.org/10.1371/journal.pcbi.1002195}, DOI={10.1371/journal.pcbi.1002195}, number={10}, journal={PLoS Computational Biology}, publisher={Public Library of Science (PLoS)}, author={Eddy, Sean R.}, editor={Pearson, William R.}, year={2011}, month=Oct, pages={e1002195} }"
			}
		]
	},
	{
		"id": "cog",
		"name": "COG (NCBI CDD)",
		"role": "COG functional category annotation",
		"phase": 4,
		"version": "BLAST+ 2.16.0; cogclassifier 2.0.0; COG 2024",
		"versionExact": true,
		"licence": "COG/CDD: NCBI places no restrictions on use (U.S. Government); cogclassifier MIT; BLAST+ public domain notice",
		"licenceUrl": "https://www.ncbi.nlm.nih.gov/home/about/policies/",
		"catalogLicence": "",
		"source": "https://github.com/moshi4/COGclassifier",
		"downloads": [
			"https://ftp.ncbi.nlm.nih.gov/blast/executables/blast+/2.16.0/ncbi-blast-2.16.0+-x64-linux.tar.gz",
			"https://pypi.org/project/cogclassifier/2.0.0/",
			"https://ftp.ncbi.nlm.nih.gov/pub/COG/COG2024/data/",
			"https://ftp.ncbi.nlm.nih.gov/pub/mmdb/cdd/little_endian/Cog_LE.tar.gz"
		],
		"citeRequired": true,
		"citeRule": "Please cite the authors in any work or product based on this material.",
		"citeRuleUrl": "https://github.com/ncbi/ncbi-cxx-toolkit-public/blob/main/LICENSE",
		"cite": [
			{
				"key": "galperin2025cog",
				"apa": "Galperin, M. Y., Vera Alvarez, R., Karamycheva, S., Makarova, K. S., Wolf, Y., Landsman, D., & Koonin, E. V. (2024). COG database update 2024. Nucleic Acids Research, 53(D1), D356–D363. https://doi.org/10.1093/nar/gkae983",
				"doi": "10.1093/nar/gkae983",
				"bibtex": "@article{galperin2025cog, title={COG database update 2024}, volume={53}, ISSN={1362-4962}, url={http://dx.doi.org/10.1093/nar/gkae983}, DOI={10.1093/nar/gkae983}, number={D1}, journal={Nucleic Acids Research}, publisher={Oxford University Press (OUP)}, author={Galperin, Michael Y and Vera Alvarez, Roberto and Karamycheva, Svetlana and Makarova, Kira S and Wolf, Yuri I and Landsman, David and Koonin, Eugene V}, year={2024}, month=Nov, pages={D356–D363} }"
			},
			{
				"key": "galperin2021cog",
				"apa": "Galperin, M. Y., Wolf, Y. I., Makarova, K. S., Vera Alvarez, R., Landsman, D., & Koonin, E. V. (2020). COG database update: focus on microbial diversity, model organisms, and widespread pathogens. Nucleic Acids Research, 49(D1), D274–D281. https://doi.org/10.1093/nar/gkaa1018",
				"doi": "10.1093/nar/gkaa1018",
				"bibtex": "@article{galperin2021cog, title={COG database update: focus on microbial diversity, model organisms, and widespread pathogens}, volume={49}, ISSN={1362-4962}, url={http://dx.doi.org/10.1093/nar/gkaa1018}, DOI={10.1093/nar/gkaa1018}, number={D1}, journal={Nucleic Acids Research}, publisher={Oxford University Press (OUP)}, author={Galperin, Michael Y and Wolf, Yuri I and Makarova, Kira S and Vera Alvarez, Roberto and Landsman, David and Koonin, Eugene V}, year={2020}, month=Nov, pages={D274–D281} }"
			},
			{
				"key": "camacho2009blastplus",
				"apa": "Camacho, C., Coulouris, G., Avagyan, V., Ma, N., Papadopoulos, J., Bealer, K., & Madden, T. L. (2009). BLAST+: architecture and applications. BMC Bioinformatics, 10(1). https://doi.org/10.1186/1471-2105-10-421",
				"doi": "10.1186/1471-2105-10-421",
				"bibtex": "@article{camacho2009blastplus, title={BLAST+: architecture and applications}, volume={10}, ISSN={1471-2105}, url={http://dx.doi.org/10.1186/1471-2105-10-421}, DOI={10.1186/1471-2105-10-421}, number={1}, journal={BMC Bioinformatics}, publisher={Springer Science and Business Media LLC}, author={Camacho, Christiam and Coulouris, George and Avagyan, Vahram and Ma, Ning and Papadopoulos, Jason and Bealer, Kevin and Madden, Thomas L}, year={2009}, month=Dec }"
			}
		]
	},
	{
		"id": "pgap",
		"name": "NCBI PGAP HMM library",
		"role": "NCBI protein family (PGAP) HMM annotation",
		"phase": 4,
		"version": "HMMER 3.4; hmm_PGAP 15.0",
		"versionExact": true,
		"licence": "U.S. Government Work (no copyright; NCBI places no restrictions); HMMER BSD-3-Clause",
		"licenceUrl": "https://github.com/ncbi/pgap/blob/master/LICENSE.md",
		"catalogLicence": "",
		"source": "https://github.com/ncbi/pgap",
		"downloads": [
			"http://eddylab.org/software/hmmer/hmmer-3.4.tar.gz",
			"https://ftp.ncbi.nlm.nih.gov/hmm/current/hmm_PGAP.LIB",
			"https://ftp.ncbi.nlm.nih.gov/hmm/15.0/"
		],
		"citeRequired": true,
		"citeRule": "When using this collection of HMMs, please cite:",
		"citeRuleUrl": "https://ftp.ncbi.nlm.nih.gov/hmm/README.txt",
		"cite": [
			{
				"key": "li2021pgap",
				"apa": "Li, W., O’Neill, K. R., Haft, D. H., DiCuccio, M., Chetvernin, V., Badretdin, A., Coulouris, G., Chitsaz, F., Derbyshire, M., Durkin, A. S., Gonzales, N. R., Gwadz, M., Lanczycki, C., Song, J. S., Thanki, N., Wang, J., Yamashita, R., Yang, M., Zheng, C., et al. (2020). RefSeq: expanding the Prokaryotic Genome Annotation Pipeline reach with protein family model curation. Nucleic Acids Research, 49(D1), D1020–D1028. https://doi.org/10.1093/nar/gkaa1105",
				"doi": "10.1093/nar/gkaa1105",
				"bibtex": "@article{li2021pgap, title={RefSeq: expanding the Prokaryotic Genome Annotation Pipeline reach with protein family model curation}, volume={49}, ISSN={1362-4962}, url={http://dx.doi.org/10.1093/nar/gkaa1105}, DOI={10.1093/nar/gkaa1105}, number={D1}, journal={Nucleic Acids Research}, publisher={Oxford University Press (OUP)}, author={Li, Wenjun and O’Neill, Kathleen R and Haft, Daniel H and DiCuccio, Michael and Chetvernin, Vyacheslav and Badretdin, Azat and Coulouris, George and Chitsaz, Farideh and Derbyshire, Myra K and Durkin, A Scott and Gonzales, Noreen R and Gwadz, Marc and Lanczycki, Christopher J and Song, James S and Thanki, Narmada and Wang, Jiyao and Yamashita, Roxanne A and Yang, Mingzhang and Zheng, Chanjuan and Marchler-Bauer, Aron and Thibaud-Nissen, Françoise}, year={2020}, month=Dec, pages={D1020–D1028} }"
			},
			{
				"key": "tatusova2016pgap",
				"apa": "Tatusova, T., DiCuccio, M., Badretdin, A., Chetvernin, V., Nawrocki, E. P., Zaslavsky, L., Lomsadze, A., Pruitt, K. D., Borodovsky, M., & Ostell, J. (2016). NCBI prokaryotic genome annotation pipeline. Nucleic Acids Research, 44(14), 6614–6624. https://doi.org/10.1093/nar/gkw569",
				"doi": "10.1093/nar/gkw569",
				"bibtex": "@article{tatusova2016pgap, title={NCBI prokaryotic genome annotation pipeline}, volume={44}, ISSN={1362-4962}, url={http://dx.doi.org/10.1093/nar/gkw569}, DOI={10.1093/nar/gkw569}, number={14}, journal={Nucleic Acids Research}, publisher={Oxford University Press (OUP)}, author={Tatusova, Tatiana and DiCuccio, Michael and Badretdin, Azat and Chetvernin, Vyacheslav and Nawrocki, Eric P. and Zaslavsky, Leonid and Lomsadze, Alexandre and Pruitt, Kim D. and Borodovsky, Mark and Ostell, James}, year={2016}, month=June, pages={6614–6624} }"
			},
			{
				"key": "eddy2011hmmer",
				"apa": "Eddy, S. R. (2011). Accelerated Profile HMM Searches. PLoS Computational Biology, 7(10), e1002195. https://doi.org/10.1371/journal.pcbi.1002195",
				"doi": "10.1371/journal.pcbi.1002195",
				"bibtex": "@article{eddy2011hmmer, title={Accelerated Profile HMM Searches}, volume={7}, ISSN={1553-7358}, url={http://dx.doi.org/10.1371/journal.pcbi.1002195}, DOI={10.1371/journal.pcbi.1002195}, number={10}, journal={PLoS Computational Biology}, publisher={Public Library of Science (PLoS)}, author={Eddy, Sean R.}, editor={Pearson, William R.}, year={2011}, month=Oct, pages={e1002195} }"
			}
		]
	},
	{
		"id": "operon",
		"name": "Operon layer (UniOP)",
		"role": "operon prediction",
		"phase": 5,
		"version": "UniOP (commit 68c55d2, 2025-05-30); Prodigal 2.6.3",
		"versionExact": true,
		"licence": "UniOP: no licence stated upstream (catalog records MIT); Prodigal GPL-3.0",
		"licenceUrl": "https://github.com/hongsua/UniOP",
		"catalogLicence": "UniOP MIT; Prodigal GPL-3.0; numpy/pandas/scipy BSD",
		"source": "https://github.com/hongsua/UniOP",
		"downloads": [
			"https://github.com/hongsua/UniOP (commit 68c55d2f8b890bd645f1fb0768137f6c09ba00e5)",
			"Debian 12 apt: prodigal 2.6.3"
		],
		"citeRequired": true,
		"citeRule": "If you use UniOP in your research, please cite the preprint:",
		"citeRuleUrl": "https://github.com/hongsua/UniOP/blob/main/README.md",
		"cite": [
			{
				"key": "su2024uniop",
				"apa": "Su, H., Zhang, R., & Söding, J. (2024). UniOP: a universal operon prediction for high-throughput prokaryotic (meta-)genomic data using intergenic distance. https://doi.org/10.1101/2024.11.11.623000",
				"doi": "10.1101/2024.11.11.623000",
				"bibtex": "@article{su2024uniop, title={UniOP: a universal operon prediction for high-throughput prokaryotic (meta-)genomic data using intergenic distance}, url={http://dx.doi.org/10.1101/2024.11.11.623000}, DOI={10.1101/2024.11.11.623000}, publisher={openRxiv}, author={Su, Hong and Zhang, Ruoshi and Söding, Johannes}, year={2024}, month=Nov }"
			},
			{
				"key": "hyatt2010prodigal",
				"apa": "Hyatt, D., Chen, G.-L., LoCascio, P. F., Land, M. L., Larimer, F. W., & Hauser, L. J. (2010). Prodigal: prokaryotic gene recognition and translation initiation site identification. BMC Bioinformatics, 11(1). https://doi.org/10.1186/1471-2105-11-119",
				"doi": "10.1186/1471-2105-11-119",
				"bibtex": "@article{hyatt2010prodigal, title={Prodigal: prokaryotic gene recognition and translation initiation site identification}, volume={11}, ISSN={1471-2105}, url={http://dx.doi.org/10.1186/1471-2105-11-119}, DOI={10.1186/1471-2105-11-119}, number={1}, journal={BMC Bioinformatics}, publisher={Springer Science and Business Media LLC}, author={Hyatt, Doug and Chen, Gwo-Liang and LoCascio, Philip F and Land, Miriam L and Larimer, Frank W and Hauser, Loren J}, year={2010}, month=Mar }"
			}
		]
	},
	{
		"id": "quast",
		"name": "QUAST",
		"role": "assembly quality metrics",
		"phase": 1,
		"version": "QUAST 5.3.0",
		"versionExact": true,
		"licence": "GPL-2.0",
		"licenceUrl": "https://github.com/ablab/quast/blob/master/LICENSE.txt",
		"catalogLicence": "",
		"source": "https://github.com/ablab/quast",
		"downloads": [
			"https://github.com/ablab/quast",
			"https://github.com/ablab/quast/releases/tag/quast_5.3.0"
		],
		"citeRequired": true,
		"citeRule": "If you use the latest QUAST version or WebQUAST, please include our latest paper, Mikheenko et al., 2023, into your reference list:",
		"citeRuleUrl": "https://github.com/ablab/quast/blob/master/LICENSE.txt",
		"cite": [
			{
				"key": "mikheenko2023webquast",
				"apa": "Mikheenko, A., Saveliev, V., Hirsch, P., & Gurevich, A. (2023). WebQUAST: online evaluation of genome assemblies. Nucleic Acids Research, 51(W1), W601–W606. https://doi.org/10.1093/nar/gkad406",
				"doi": "10.1093/nar/gkad406",
				"bibtex": "@article{mikheenko2023webquast, title={WebQUAST: online evaluation of genome assemblies}, volume={51}, ISSN={1362-4962}, url={http://dx.doi.org/10.1093/nar/gkad406}, DOI={10.1093/nar/gkad406}, number={W1}, journal={Nucleic Acids Research}, publisher={Oxford University Press (OUP)}, author={Mikheenko, Alla and Saveliev, Vladislav and Hirsch, Pascal and Gurevich, Alexey}, year={2023}, month=May, pages={W601–W606} }"
			},
			{
				"key": "gurevich2013quast",
				"apa": "Gurevich, A., Saveliev, V., Vyahhi, N., & Tesler, G. (2013). QUAST: quality assessment tool for genome assemblies. Bioinformatics, 29(8), 1072–1075. https://doi.org/10.1093/bioinformatics/btt086",
				"doi": "10.1093/bioinformatics/btt086",
				"bibtex": "@article{gurevich2013quast, title={QUAST: quality assessment tool for genome assemblies}, volume={29}, ISSN={1367-4803}, url={http://dx.doi.org/10.1093/bioinformatics/btt086}, DOI={10.1093/bioinformatics/btt086}, number={8}, journal={Bioinformatics}, publisher={Oxford University Press (OUP)}, author={Gurevich, Alexey and Saveliev, Vladislav and Vyahhi, Nikolay and Tesler, Glenn}, year={2013}, month=Feb, pages={1072–1075} }"
			}
		]
	},
	{
		"id": "ani",
		"name": "ANI (skani)",
		"role": "average nucleotide identity",
		"phase": 13,
		"version": "skani 0.2.1",
		"versionExact": true,
		"licence": "MIT",
		"licenceUrl": "https://github.com/bluenote-1577/skani/blob/main/LICENSE",
		"catalogLicence": "",
		"source": "https://github.com/bluenote-1577/skani",
		"downloads": [
			"https://crates.io/crates/skani",
			"https://github.com/bluenote-1577/skani/releases/tag/v0.2.1"
		],
		"citeRequired": false,
		"citeRule": "",
		"citeRuleUrl": "https://github.com/bluenote-1577/skani/blob/main/README.md",
		"cite": [
			{
				"key": "shaw2023skani",
				"apa": "Shaw, J., & Yu, Y. W. (2023). Fast and robust metagenomic sequence comparison through sparse chaining with skani. Nature Methods, 20(11), 1661–1665. https://doi.org/10.1038/s41592-023-02018-3",
				"doi": "10.1038/s41592-023-02018-3",
				"bibtex": "@article{shaw2023skani, title={Fast and robust metagenomic sequence comparison through sparse chaining with skani}, volume={20}, ISSN={1548-7105}, url={http://dx.doi.org/10.1038/s41592-023-02018-3}, DOI={10.1038/s41592-023-02018-3}, number={11}, journal={Nature Methods}, publisher={Springer Science and Business Media LLC}, author={Shaw, Jim and Yu, Yun William}, year={2023}, month=Sept, pages={1661–1665} }"
			}
		]
	},
	{
		"id": "aai",
		"name": "AAI (EzAAI + DIAMOND)",
		"role": "average amino acid identity",
		"phase": 13,
		"version": "DIAMOND 2.1.9 (+ CompareM 0.1.2 per VERSIONS / EzAAI 1.2.2 per LICENSE.md)",
		"versionExact": false,
		"licence": "EzAAI GPL-3.0; CompareM GPL-3.0 (PyPI metadata \"GPL3\"); DIAMOND GPL-3.0",
		"licenceUrl": "https://github.com/endixk/ezaai/blob/main/LICENSE.md",
		"catalogLicence": "",
		"source": "https://github.com/endixk/ezaai",
		"downloads": [
			"https://github.com/bbuchfink/diamond/releases/download/v2.1.9/diamond-linux64.tar.gz",
			"https://pypi.org/project/comparem/",
			"https://github.com/endixk/ezaai"
		],
		"citeRequired": false,
		"citeRule": "",
		"citeRuleUrl": "https://github.com/endixk/ezaai/blob/main/README.md",
		"cite": [
			{
				"key": "kim2021ezaai",
				"apa": "Kim, D., Park, S., & Chun, J. (2021). Introducing EzAAI: a pipeline for high throughput calculations of prokaryotic average amino acid identity. Journal of Microbiology, 59(5), 476–480. https://doi.org/10.1007/s12275-021-1154-0",
				"doi": "10.1007/s12275-021-1154-0",
				"bibtex": "@article{kim2021ezaai, title={Introducing EzAAI: a pipeline for high throughput calculations of prokaryotic average amino acid identity}, volume={59}, ISSN={1976-3794}, url={http://dx.doi.org/10.1007/s12275-021-1154-0}, DOI={10.1007/s12275-021-1154-0}, number={5}, journal={Journal of Microbiology}, publisher={The Microbiological Society of Korea}, author={Kim, Dongwook and Park, Sein and Chun, Jongsik}, year={2021}, month=Apr, pages={476–480} }"
			},
			{
				"key": "buchfink2021diamond",
				"apa": "Buchfink, B., Reuter, K., & Drost, H.-G. (2021). Sensitive protein alignments at tree-of-life scale using DIAMOND. Nature Methods, 18(4), 366–368. https://doi.org/10.1038/s41592-021-01101-x",
				"doi": "10.1038/s41592-021-01101-x",
				"bibtex": "@article{buchfink2021diamond, title={Sensitive protein alignments at tree-of-life scale using DIAMOND}, volume={18}, ISSN={1548-7105}, url={http://dx.doi.org/10.1038/s41592-021-01101-x}, DOI={10.1038/s41592-021-01101-x}, number={4}, journal={Nature Methods}, publisher={Springer Science and Business Media LLC}, author={Buchfink, Benjamin and Reuter, Klaus and Drost, Hajk-Georg}, year={2021}, month=Apr, pages={366–368} }"
			}
		]
	},
	{
		"id": "synteny",
		"name": "Synteny (Liftoff + minimap2)",
		"role": "annotation lift-over and synteny",
		"phase": 13,
		"version": "Liftoff 1.6.3.2; minimap2 2.28",
		"versionExact": true,
		"licence": "Liftoff GPL-3.0; minimap2 MIT",
		"licenceUrl": "https://github.com/agshumate/Liftoff/blob/master/LICENSE.md",
		"catalogLicence": "",
		"source": "https://github.com/agshumate/Liftoff",
		"downloads": [
			"https://pypi.org/project/liftoff/1.6.3.2/",
			"https://github.com/lh3/minimap2/archive/refs/tags/v2.28.tar.gz"
		],
		"citeRequired": true,
		"citeRule": "If you use Liftoff in your work please cite",
		"citeRuleUrl": "https://github.com/agshumate/Liftoff/blob/master/README.md",
		"cite": [
			{
				"key": "shumate2021liftoff",
				"apa": "Shumate, A., & Salzberg, S. L. (2021). Liftoff: accurate mapping of gene annotations. Bioinformatics, 37(12), 1639–1643. https://doi.org/10.1093/bioinformatics/btaa1016",
				"doi": "10.1093/bioinformatics/btaa1016",
				"bibtex": "@article{shumate2021liftoff, title={Liftoff: accurate mapping of gene annotations}, volume={37}, ISSN={1367-4811}, url={http://dx.doi.org/10.1093/bioinformatics/btaa1016}, DOI={10.1093/bioinformatics/btaa1016}, number={12}, journal={Bioinformatics}, publisher={Oxford University Press (OUP)}, author={Shumate, Alaina and Salzberg, Steven L}, editor={Valencia, Alfonso}, year={2021}, month=May, pages={1639–1643} }"
			},
			{
				"key": "li2018minimap2",
				"apa": "Li, H. (2018). Minimap2: pairwise alignment for nucleotide sequences. Bioinformatics, 34(18), 3094–3100. https://doi.org/10.1093/bioinformatics/bty191",
				"doi": "10.1093/bioinformatics/bty191",
				"bibtex": "@article{li2018minimap2, title={Minimap2: pairwise alignment for nucleotide sequences}, volume={34}, ISSN={1367-4811}, url={http://dx.doi.org/10.1093/bioinformatics/bty191}, DOI={10.1093/bioinformatics/bty191}, number={18}, journal={Bioinformatics}, publisher={Oxford University Press (OUP)}, author={Li, Heng}, editor={Birol, Inanc}, year={2018}, month=May, pages={3094–3100} }"
			},
			{
				"key": "li2021minimap2",
				"apa": "Li, H. (2021). New strategies to improve minimap2 alignment accuracy. Bioinformatics, 37(23), 4572–4574. https://doi.org/10.1093/bioinformatics/btab705",
				"doi": "10.1093/bioinformatics/btab705",
				"bibtex": "@article{li2021minimap2, title={New strategies to improve minimap2 alignment accuracy}, volume={37}, ISSN={1367-4811}, url={http://dx.doi.org/10.1093/bioinformatics/btab705}, DOI={10.1093/bioinformatics/btab705}, number={23}, journal={Bioinformatics}, publisher={Oxford University Press (OUP)}, author={Li, Heng}, editor={Alkan, Can}, year={2021}, month=Oct, pages={4572–4574} }"
			}
		]
	},
	{
		"id": "closest-organisms",
		"name": "Closest organisms",
		"role": "closest-genome ranking",
		"phase": 13,
		"version": "rank_closest 1.0.0 (first-party)",
		"versionExact": true,
		"licence": "MARGIE's own step",
		"licenceUrl": "",
		"catalogLicence": "",
		"source": "https://github.com/Diet-Microbiome-Interactions-Lab/margie-project-2026",
		"downloads": [],
		"citeRequired": false,
		"citeRule": "",
		"citeRuleUrl": "",
		"cite": [
			{
				"key": "bhattarai2026margie",
				"apa": "Bhattarai, S. (2026). MOSTLY AUTOMATED RAPID GENOME INFERENCE ENVIRONMENT (Version 1) [Purdue University Graduate School]. https://doi.org/10.25394/PGS.33103682.V1",
				"doi": "10.25394/PGS.33103682.v1",
				"bibtex": "@phdthesis{bhattarai2026margie,\n  doi = {10.25394/PGS.33103682.V1},\n  url = {https://hammer.purdue.edu/articles/thesis/_b_MOSTLY_AUTOMATED_RAPID_GENOME_INFERENCE_ENVIRONMENT_b_/33103682/1},\n  author = {Bhattarai, Sajal},\n  keywords = {Microbial genetics, Microbial ecology, Bioinformatic methods development},\n  title = {MOSTLY AUTOMATED RAPID GENOME INFERENCE ENVIRONMENT},\n  publisher = {Purdue University Graduate School},\n  year = {2026},\n  copyright = {Creative Commons Attribution 4.0 International}\n}"
			}
		]
	},
	{
		"id": "envelope",
		"name": "Envelope inference",
		"role": "cell envelope (Gram type) inference",
		"phase": 6,
		"version": "envelope 0.1.0 (first-party)",
		"versionExact": true,
		"licence": "MARGIE's own step",
		"licenceUrl": "",
		"catalogLicence": "",
		"source": "https://github.com/Diet-Microbiome-Interactions-Lab/margie-project-2026",
		"downloads": [],
		"citeRequired": false,
		"citeRule": "",
		"citeRuleUrl": "",
		"cite": [
			{
				"key": "bhattarai2026margie",
				"apa": "Bhattarai, S. (2026). MOSTLY AUTOMATED RAPID GENOME INFERENCE ENVIRONMENT (Version 1) [Purdue University Graduate School]. https://doi.org/10.25394/PGS.33103682.V1",
				"doi": "10.25394/PGS.33103682.v1",
				"bibtex": "@phdthesis{bhattarai2026margie,\n  doi = {10.25394/PGS.33103682.V1},\n  url = {https://hammer.purdue.edu/articles/thesis/_b_MOSTLY_AUTOMATED_RAPID_GENOME_INFERENCE_ENVIRONMENT_b_/33103682/1},\n  author = {Bhattarai, Sajal},\n  keywords = {Microbial genetics, Microbial ecology, Bioinformatic methods development},\n  title = {MOSTLY AUTOMATED RAPID GENOME INFERENCE ENVIRONMENT},\n  publisher = {Purdue University Graduate School},\n  year = {2026},\n  copyright = {Creative Commons Attribution 4.0 International}\n}"
			}
		]
	}
];

export const SOFTWARE_CREDITS: SoftwareCredit[] = [
	{
		"name": "Snakemake",
		"group": "Workflow and computing",
		"listedAs": "Snakemake",
		"version": "9.17.3",
		"licence": "MIT",
		"licenceUrl": "https://github.com/snakemake/snakemake/blob/main/LICENSE.md",
		"source": "https://github.com/snakemake/snakemake",
		"citeRequired": true,
		"citeRule": "When using Snakemake for a publication, please cite the following article in you paper:",
		"citeRuleUrl": "https://snakemake.readthedocs.io/en/stable/project_info/citations.html",
		"cite": [
			{
				"key": "molder2021snakemake",
				"apa": "Mölder, F., Jablonski, K. P., Letcher, B., Hall, M. B., Tomkins-Tinch, C. H., Sochat, V., Forster, J., Lee, S., Twardziok, S. O., Kanitz, A., Wilm, A., Holtgrewe, M., Rahmann, S., Nahnsen, S., & Köster, J. (2021). Sustainable data analysis with Snakemake. F1000Research, 10, 33. https://doi.org/10.12688/f1000research.29032.1",
				"doi": "10.12688/f1000research.29032.1",
				"bibtex": "@article{molder2021snakemake, title={Sustainable data analysis with Snakemake}, volume={10}, ISSN={2046-1402}, url={http://dx.doi.org/10.12688/f1000research.29032.1}, DOI={10.12688/f1000research.29032.1}, journal={F1000Research}, publisher={F1000 Research Ltd}, author={Mölder, Felix and Jablonski, Kim Philipp and Letcher, Brice and Hall, Michael B. and Tomkins-Tinch, Christopher H. and Sochat, Vanessa and Forster, Jan and Lee, Soohyun and Twardziok, Sven O. and Kanitz, Alexander and Wilm, Andreas and Holtgrewe, Manuel and Rahmann, Sven and Nahnsen, Sven and Köster, Johannes}, year={2021}, month=Jan, pages={33} }"
			}
		]
	},
	{
		"name": "Snakemake executor plugin for SLURM (snakemake-executor-plugin-slurm)",
		"group": "Workflow and computing",
		"listedAs": "Snakemake",
		"version": "2.6.1",
		"licence": "MIT",
		"licenceUrl": "https://github.com/snakemake/snakemake-executor-plugin-slurm/blob/main/LICENSE",
		"source": "https://github.com/snakemake/snakemake-executor-plugin-slurm",
		"citeRequired": false,
		"citeRule": "",
		"citeRuleUrl": "",
		"cite": []
	},
	{
		"name": "Apptainer",
		"group": "Workflow and computing",
		"listedAs": "Apptainer",
		"version": "",
		"licence": "BSD-3-Clause (with an LBNL licence section)",
		"licenceUrl": "https://github.com/apptainer/apptainer/blob/main/LICENSE.md",
		"source": "https://github.com/apptainer/apptainer",
		"citeRequired": true,
		"citeRule": "Please also consider citing the original publication describing Singularity:",
		"citeRuleUrl": "https://github.com/apptainer/apptainer/blob/main/README.md",
		"cite": [
			{
				"key": "kurtzer2017singularity",
				"apa": "Kurtzer, G. M., Sochat, V., & Bauer, M. W. (2017). Singularity: Scientific containers for mobility of compute. Plos One, 12(5), e0177459. https://doi.org/10.1371/journal.pone.0177459",
				"doi": "10.1371/journal.pone.0177459",
				"bibtex": "@article{kurtzer2017singularity, title={Singularity: Scientific containers for mobility of compute}, volume={12}, ISSN={1932-6203}, url={http://dx.doi.org/10.1371/journal.pone.0177459}, DOI={10.1371/journal.pone.0177459}, number={5}, journal={PLOS ONE}, publisher={Public Library of Science (PLoS)}, author={Kurtzer, Gregory M. and Sochat, Vanessa and Bauer, Michael W.}, editor={Gursoy, Attila}, year={2017}, month=May, pages={e0177459} }"
			},
			{
				"key": "singularity2021zenodo",
				"apa": "Kurtzer, G. M., Cclerget, Bauer, M., Kaneshiro, I., Trudgian, D., & Godlove, D. (2021). hpcng/singularity: Singularity 3.7.3 (Version v3.7.3) [Computer software]. Zenodo. https://doi.org/10.5281/ZENODO.1310023",
				"doi": "10.5281/zenodo.1310023",
				"bibtex": "@misc{singularity2021zenodo,\n  doi = {10.5281/ZENODO.1310023},\n  url = {https://zenodo.org/record/1310023},\n  author = {Kurtzer, Gregory M. and {Cclerget} and Bauer, Michael and Kaneshiro, Ian and Trudgian, David and Godlove, David},\n  title = {hpcng/singularity: Singularity 3.7.3},\n  publisher = {Zenodo},\n  year = {2021},\n  copyright = {Open Access}\n}"
			}
		]
	},
	{
		"name": "Slurm",
		"group": "Workflow and computing",
		"listedAs": "Slurm",
		"version": "",
		"licence": "GPL-2.0 (with an OpenSSL linking exception)",
		"licenceUrl": "https://github.com/SchedMD/slurm/blob/master/COPYING",
		"source": "https://github.com/SchedMD/slurm",
		"citeRequired": false,
		"citeRule": "",
		"citeRuleUrl": "",
		"cite": []
	},
	{
		"name": "Python",
		"group": "Workflow and computing",
		"listedAs": "Python",
		"version": "3.11",
		"licence": "PSF-2.0 (Python Software Foundation License Version 2)",
		"licenceUrl": "https://docs.python.org/3/license.html",
		"source": "https://github.com/python/cpython",
		"citeRequired": false,
		"citeRule": "",
		"citeRuleUrl": "",
		"cite": []
	},
	{
		"name": "uv",
		"group": "Workflow and computing",
		"listedAs": "uv",
		"version": "",
		"licence": "MIT OR Apache-2.0",
		"licenceUrl": "https://github.com/astral-sh/uv/blob/main/LICENSE-MIT",
		"source": "https://github.com/astral-sh/uv",
		"citeRequired": false,
		"citeRule": "",
		"citeRuleUrl": "",
		"cite": []
	},
	{
		"name": "Biopython",
		"group": "Science",
		"listedAs": "Biopython",
		"version": "1.88",
		"licence": "Biopython License Agreement (some files also BSD-3-Clause)",
		"licenceUrl": "https://github.com/biopython/biopython/blob/master/LICENSE.rst",
		"source": "https://github.com/biopython/biopython",
		"citeRequired": false,
		"citeRule": "",
		"citeRuleUrl": "",
		"cite": []
	},
	{
		"name": "NumPy",
		"group": "Science",
		"listedAs": "NumPy",
		"version": "2.4.6",
		"licence": "BSD-3-Clause",
		"licenceUrl": "https://github.com/numpy/numpy/blob/main/LICENSE.txt",
		"source": "https://github.com/numpy/numpy",
		"citeRequired": false,
		"citeRule": "",
		"citeRuleUrl": "",
		"cite": []
	},
	{
		"name": "pandas",
		"group": "Science",
		"listedAs": "pandas",
		"version": "2.3.3",
		"licence": "BSD-3-Clause",
		"licenceUrl": "https://github.com/pandas-dev/pandas/blob/main/LICENSE",
		"source": "https://github.com/pandas-dev/pandas",
		"citeRequired": false,
		"citeRule": "",
		"citeRuleUrl": "",
		"cite": []
	},
	{
		"name": "SciPy",
		"group": "Science",
		"listedAs": "SciPy",
		"version": "1.17.1",
		"licence": "BSD-3-Clause",
		"licenceUrl": "https://github.com/scipy/scipy/blob/main/LICENSE.txt",
		"source": "https://github.com/scipy/scipy",
		"citeRequired": false,
		"citeRule": "",
		"citeRuleUrl": "",
		"cite": []
	},
	{
		"name": "Matplotlib",
		"group": "Science",
		"listedAs": "Matplotlib",
		"version": "3.11.2",
		"licence": "Matplotlib License (PSF-based)",
		"licenceUrl": "https://github.com/matplotlib/matplotlib/blob/main/LICENSE/LICENSE",
		"source": "https://github.com/matplotlib/matplotlib",
		"citeRequired": false,
		"citeRule": "",
		"citeRuleUrl": "",
		"cite": []
	},
	{
		"name": "openpyxl",
		"group": "Science",
		"listedAs": "openpyxl",
		"version": "3.1.5",
		"licence": "MIT",
		"licenceUrl": "https://foss.heptapod.net/openpyxl/openpyxl/-/blob/branch/default/LICENCE.rst",
		"source": "https://foss.heptapod.net/openpyxl/openpyxl",
		"citeRequired": false,
		"citeRule": "",
		"citeRuleUrl": "",
		"cite": []
	},
	{
		"name": "FastAPI",
		"group": "Server",
		"listedAs": "FastAPI",
		"version": "0.162.0",
		"licence": "MIT",
		"licenceUrl": "https://github.com/fastapi/fastapi/blob/master/LICENSE",
		"source": "https://github.com/fastapi/fastapi",
		"citeRequired": false,
		"citeRule": "",
		"citeRuleUrl": "",
		"cite": []
	},
	{
		"name": "Uvicorn",
		"group": "Server",
		"listedAs": "Uvicorn",
		"version": "0.54.0",
		"licence": "BSD-3-Clause",
		"licenceUrl": "https://github.com/Kludex/uvicorn/blob/main/LICENSE.md",
		"source": "https://github.com/Kludex/uvicorn",
		"citeRequired": false,
		"citeRule": "",
		"citeRuleUrl": "",
		"cite": []
	},
	{
		"name": "Pydantic",
		"group": "Server",
		"listedAs": "Pydantic",
		"version": "2.14.1",
		"licence": "MIT",
		"licenceUrl": "https://github.com/pydantic/pydantic/blob/main/LICENSE",
		"source": "https://github.com/pydantic/pydantic",
		"citeRequired": false,
		"citeRule": "",
		"citeRuleUrl": "",
		"cite": []
	},
	{
		"name": "Paramiko",
		"group": "Server",
		"listedAs": "Paramiko",
		"version": "5.1.0",
		"licence": "LGPL-2.1",
		"licenceUrl": "https://github.com/paramiko/paramiko/blob/main/LICENSE",
		"source": "https://github.com/paramiko/paramiko",
		"citeRequired": false,
		"citeRule": "",
		"citeRuleUrl": "",
		"cite": []
	},
	{
		"name": "PyJWT",
		"group": "Server",
		"listedAs": "PyJWT, bcrypt and cryptography",
		"version": "2.15.1",
		"licence": "MIT",
		"licenceUrl": "https://github.com/jpadilla/pyjwt/blob/master/LICENSE",
		"source": "https://github.com/jpadilla/pyjwt",
		"citeRequired": false,
		"citeRule": "",
		"citeRuleUrl": "",
		"cite": []
	},
	{
		"name": "bcrypt",
		"group": "Server",
		"listedAs": "PyJWT, bcrypt and cryptography",
		"version": "5.0.0",
		"licence": "Apache-2.0",
		"licenceUrl": "https://github.com/pyca/bcrypt/blob/main/LICENSE",
		"source": "https://github.com/pyca/bcrypt",
		"citeRequired": false,
		"citeRule": "",
		"citeRuleUrl": "",
		"cite": []
	},
	{
		"name": "cryptography",
		"group": "Server",
		"listedAs": "PyJWT, bcrypt and cryptography",
		"version": "44.0.3",
		"licence": "Apache-2.0 OR BSD-3-Clause",
		"licenceUrl": "https://github.com/pyca/cryptography/blob/main/LICENSE",
		"source": "https://github.com/pyca/cryptography",
		"citeRequired": false,
		"citeRule": "",
		"citeRuleUrl": "",
		"cite": []
	},
	{
		"name": "Typer",
		"group": "Server",
		"listedAs": "Typer",
		"version": "0.27.3",
		"licence": "MIT",
		"licenceUrl": "https://github.com/fastapi/typer/blob/master/LICENSE",
		"source": "https://github.com/fastapi/typer",
		"citeRequired": false,
		"citeRule": "",
		"citeRuleUrl": "",
		"cite": []
	},
	{
		"name": "PyYAML",
		"group": "Server",
		"listedAs": "PyYAML",
		"version": "6.0.3",
		"licence": "MIT",
		"licenceUrl": "https://github.com/yaml/pyyaml/blob/main/LICENSE",
		"source": "https://github.com/yaml/pyyaml",
		"citeRequired": false,
		"citeRule": "",
		"citeRuleUrl": "",
		"cite": []
	},
	{
		"name": "websockets",
		"group": "Server",
		"listedAs": "websockets",
		"version": "17.3",
		"licence": "BSD-3-Clause",
		"licenceUrl": "https://github.com/python-websockets/websockets/blob/main/LICENSE",
		"source": "https://github.com/python-websockets/websockets",
		"citeRequired": false,
		"citeRule": "",
		"citeRuleUrl": "",
		"cite": []
	},
	{
		"name": "Svelte",
		"group": "Website",
		"listedAs": "Svelte and SvelteKit",
		"version": "5.46.0",
		"licence": "MIT",
		"licenceUrl": "https://github.com/sveltejs/svelte/blob/main/LICENSE.md",
		"source": "https://github.com/sveltejs/svelte",
		"citeRequired": false,
		"citeRule": "",
		"citeRuleUrl": "",
		"cite": []
	},
	{
		"name": "SvelteKit (@sveltejs/kit)",
		"group": "Website",
		"listedAs": "Svelte and SvelteKit",
		"version": "2.49.2",
		"licence": "MIT",
		"licenceUrl": "https://github.com/sveltejs/kit/blob/main/LICENSE",
		"source": "https://github.com/sveltejs/kit",
		"citeRequired": false,
		"citeRule": "",
		"citeRuleUrl": "",
		"cite": []
	},
	{
		"name": "TypeScript",
		"group": "Website",
		"listedAs": "TypeScript",
		"version": "5.9.3",
		"licence": "Apache-2.0",
		"licenceUrl": "https://github.com/microsoft/TypeScript/blob/main/LICENSE.txt",
		"source": "https://github.com/microsoft/TypeScript",
		"citeRequired": false,
		"citeRule": "",
		"citeRuleUrl": "",
		"cite": []
	},
	{
		"name": "Vite",
		"group": "Website",
		"listedAs": "Vite",
		"version": "7.3.0",
		"licence": "MIT",
		"licenceUrl": "https://github.com/vitejs/vite/blob/main/LICENSE",
		"source": "https://github.com/vitejs/vite",
		"citeRequired": false,
		"citeRule": "",
		"citeRuleUrl": "",
		"cite": []
	},
	{
		"name": "Tailwind CSS",
		"group": "Website",
		"listedAs": "Tailwind CSS",
		"version": "4.1.18",
		"licence": "MIT",
		"licenceUrl": "https://github.com/tailwindlabs/tailwindcss/blob/main/LICENSE",
		"source": "https://github.com/tailwindlabs/tailwindcss",
		"citeRequired": false,
		"citeRule": "",
		"citeRuleUrl": "",
		"cite": []
	},
	{
		"name": "Skeleton (@skeletonlabs/skeleton, @skeletonlabs/skeleton-svelte)",
		"group": "Website",
		"listedAs": "Skeleton",
		"version": "4.8.0",
		"licence": "MIT",
		"licenceUrl": "https://github.com/skeletonlabs/skeleton/blob/main/LICENSE",
		"source": "https://github.com/skeletonlabs/skeleton",
		"citeRequired": false,
		"citeRule": "",
		"citeRuleUrl": "",
		"cite": []
	},
	{
		"name": "Flowbite Svelte",
		"group": "Website",
		"listedAs": "Flowbite Svelte",
		"version": "1.31.0",
		"licence": "MIT",
		"licenceUrl": "https://github.com/themesberg/flowbite-svelte/blob/main/LICENSE",
		"source": "https://github.com/themesberg/flowbite-svelte",
		"citeRequired": false,
		"citeRule": "",
		"citeRuleUrl": "",
		"cite": []
	},
	{
		"name": "Lucide (lucide-svelte)",
		"group": "Website",
		"listedAs": "Lucide",
		"version": "0.562.0",
		"licence": "ISC (icons derived from Feather under MIT)",
		"licenceUrl": "https://github.com/lucide-icons/lucide/blob/main/LICENSE",
		"source": "https://github.com/lucide-icons/lucide",
		"citeRequired": false,
		"citeRule": "",
		"citeRuleUrl": "",
		"cite": []
	},
	{
		"name": "xterm.js (@xterm/xterm)",
		"group": "Website",
		"listedAs": "xterm.js",
		"version": "5.5.0",
		"licence": "MIT",
		"licenceUrl": "https://github.com/xtermjs/xterm.js/blob/master/LICENSE",
		"source": "https://github.com/xtermjs/xterm.js",
		"citeRequired": false,
		"citeRule": "",
		"citeRuleUrl": "",
		"cite": []
	},
	{
		"name": "marked",
		"group": "Website",
		"listedAs": "marked and DOMPurify",
		"version": "18.0.14",
		"licence": "MIT",
		"licenceUrl": "https://github.com/markedjs/marked/blob/master/LICENSE",
		"source": "https://github.com/markedjs/marked",
		"citeRequired": false,
		"citeRule": "",
		"citeRuleUrl": "",
		"cite": []
	},
	{
		"name": "DOMPurify",
		"group": "Website",
		"listedAs": "marked and DOMPurify",
		"version": "3.4.16",
		"licence": "MPL-2.0 OR Apache-2.0",
		"licenceUrl": "https://github.com/cure53/DOMPurify/blob/main/LICENSE",
		"source": "https://github.com/cure53/DOMPurify",
		"citeRequired": false,
		"citeRule": "",
		"citeRuleUrl": "",
		"cite": []
	},
	{
		"name": "ExcelJS",
		"group": "Website",
		"listedAs": "ExcelJS",
		"version": "4.4.0",
		"licence": "MIT",
		"licenceUrl": "https://github.com/exceljs/exceljs/blob/master/LICENSE",
		"source": "https://github.com/exceljs/exceljs",
		"citeRequired": false,
		"citeRule": "",
		"citeRuleUrl": "",
		"cite": []
	},
	{
		"name": "Anthropic TypeScript SDK (@anthropic-ai/sdk)",
		"group": "Website",
		"listedAs": "Anthropic SDK",
		"version": "0.128.0",
		"licence": "MIT",
		"licenceUrl": "https://github.com/anthropics/anthropic-sdk-typescript/blob/sdk-v0.128.0/LICENSE",
		"source": "https://github.com/anthropics/anthropic-sdk-typescript",
		"citeRequired": false,
		"citeRule": "",
		"citeRuleUrl": "",
		"cite": []
	},
	{
		"name": "Bricolage Grotesque (@fontsource-variable/bricolage-grotesque)",
		"group": "Website",
		"listedAs": "Fontsource",
		"version": "5.3.0",
		"licence": "OFL-1.1",
		"licenceUrl": "https://github.com/fontsource/font-files/blob/main/fonts/variable/bricolage-grotesque/LICENSE",
		"source": "https://github.com/fontsource/font-files",
		"citeRequired": false,
		"citeRule": "",
		"citeRuleUrl": "",
		"cite": []
	},
	{
		"name": "IBM Plex Sans (@fontsource/ibm-plex-sans)",
		"group": "Website",
		"listedAs": "Fontsource",
		"version": "5.3.0",
		"licence": "OFL-1.1",
		"licenceUrl": "https://github.com/fontsource/font-files/blob/main/fonts/google/ibm-plex-sans/LICENSE",
		"source": "https://github.com/fontsource/font-files",
		"citeRequired": false,
		"citeRule": "",
		"citeRuleUrl": "",
		"cite": []
	},
	{
		"name": "IBM Plex Mono (@fontsource/ibm-plex-mono)",
		"group": "Website",
		"listedAs": "Fontsource",
		"version": "5.3.0",
		"licence": "OFL-1.1",
		"licenceUrl": "https://github.com/fontsource/font-files/blob/main/fonts/google/ibm-plex-mono/LICENSE",
		"source": "https://github.com/fontsource/font-files",
		"citeRequired": false,
		"citeRule": "",
		"citeRuleUrl": "",
		"cite": []
	},
	{
		"name": "MkDocs",
		"group": "Documentation",
		"listedAs": "MkDocs and Material for MkDocs",
		"version": "",
		"licence": "BSD-2-Clause",
		"licenceUrl": "https://github.com/mkdocs/mkdocs/blob/master/LICENSE",
		"source": "https://github.com/mkdocs/mkdocs",
		"citeRequired": false,
		"citeRule": "",
		"citeRuleUrl": "",
		"cite": []
	},
	{
		"name": "Material for MkDocs",
		"group": "Documentation",
		"listedAs": "MkDocs and Material for MkDocs",
		"version": "",
		"licence": "MIT",
		"licenceUrl": "https://github.com/squidfunk/mkdocs-material/blob/master/LICENSE",
		"source": "https://github.com/squidfunk/mkdocs-material",
		"citeRequired": false,
		"citeRule": "",
		"citeRuleUrl": "",
		"cite": []
	},
	{
		"name": "Read the Docs",
		"group": "Documentation",
		"listedAs": "Read the Docs",
		"version": "",
		"licence": "MIT (readthedocs.org code)",
		"licenceUrl": "https://github.com/readthedocs/readthedocs.org/blob/main/LICENSE",
		"source": "https://github.com/readthedocs/readthedocs.org",
		"citeRequired": false,
		"citeRule": "",
		"citeRuleUrl": "",
		"cite": []
	}
];
