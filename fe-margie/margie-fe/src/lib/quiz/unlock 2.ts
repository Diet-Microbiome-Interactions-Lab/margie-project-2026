/**
 * The questions that open the quiz: one is asked at a time, picked afresh each session, and a right
 * answer opens the quiz for the account (ui.prefs.quizOpen). A few are just for fun.
 */

import type { Unlock } from './types';

export const UNLOCK: Unlock[] = [
	{
		id: 'u01',
		question: 'An Escherichia coli culture doubles every 20 minutes. Starting from one cell, about how many cells are there after 2 hours?',
		options: ['64', '120', '128', '12'],
		answer: 0,
		explain: 'Two hours hold six doublings of 20 minutes, and 2 to the power 6 is 64.'
	},
	{
		id: 'u02',
		question: 'Which of these gut microbes is an archaeon rather than a bacterium?',
		options: ['Bacteroides thetaiotaomicron', 'Faecalibacterium prausnitzii', 'Methanobrevibacter smithii', 'Escherichia coli'],
		answer: 2,
		explain: 'Methanobrevibacter smithii is a methanogenic archaeon; it uses hydrogen made by fermenting bacteria to make methane.'
	},
	{
		id: 'u03',
		question: 'The Gram in "Gram stain" honours what?',
		options: ['A unit of mass', 'A dye company', 'The staining time', 'A person, the Danish scientist Hans Christian Gram'],
		answer: 3,
		explain: 'Hans Christian Gram described the stain in 1884; it sorts bacteria by how their cell wall holds crystal violet.',
		fun: true
	},
	{
		id: 'u04',
		question: 'Which bacterium survives radiation doses many times higher than would kill a human, earning the nickname "Conan the Bacterium"?',
		options: ['Deinococcus radiodurans', 'Bacillus subtilis', 'Staphylococcus aureus', 'Vibrio cholerae'],
		answer: 0,
		explain: 'Deinococcus radiodurans repairs shattered chromosomes efficiently and protects its proteins from oxidative damage.',
		fun: true
	},
	{
		id: 'u05',
		question: 'Besides AUG, which codon most often starts bacterial genes?',
		options: ['UAA', 'GUG', 'UGA', 'AGG'],
		answer: 1,
		explain: 'GUG (and less often UUG) also serve as start codons in bacteria; they are read as formylmethionine at the start of a protein.'
	},
	{
		id: 'u06',
		question: 'In Mycoplasma, which use genetic code 4, the codon UGA is read as:',
		options: ['A stop signal', 'Selenocysteine', 'Methionine', 'Tryptophan'],
		answer: 3,
		explain: 'Code 4 reassigns UGA from stop to tryptophan, which is why gene callers need the right genetic code for these genomes.'
	},
	{
		id: 'u07',
		question: 'Which group has cell walls without peptidoglycan?',
		options: ['Archaea', 'Gram-positive bacteria', 'Gram-negative bacteria', 'Cyanobacteria'],
		answer: 0,
		explain: 'Archaea lack peptidoglycan; some have pseudomurein, and many rely on a protein S-layer.'
	},
	{
		id: 'u08',
		question: 'Nitrogenase, the enzyme that fixes N2, is quickly inactivated by:',
		options: ['Carbon dioxide', 'Hydrogen', 'Oxygen', 'Nitrogen'],
		answer: 2,
		explain: 'Its iron-sulfur and FeMo centres are damaged by O2, so nitrogen fixers protect it with heterocysts, high respiration or anaerobic niches.'
	},
	{
		id: 'u09',
		question: 'Which vitamin, made by some gut and soil bacteria, contains cobalt?',
		options: ['Vitamin C', 'Vitamin B12', 'Vitamin D', 'Vitamin A'],
		answer: 1,
		explain: 'Cobalamin (B12) has a cobalt ion at the centre of its corrin ring, and only some bacteria and archaea can make it.'
	},
	{
		id: 'u10',
		question: 'A BLAST hit has an E-value of 1e-50. What does that tell you?',
		options: [
			'The two sequences are 50% identical',
			'The alignment is 50 residues long',
			'A hit this good is expected by chance about 1e-50 times in a search of this size',
			'There is a 50% chance the proteins are unrelated'
		],
		answer: 2,
		explain: 'The E-value is the number of hits at least this good expected by chance; the smaller it is, the less likely the match is random.'
	},
	{
		id: 'u11',
		question: 'Two genomes share 97% average nucleotide identity (ANI). They most likely belong to:',
		options: ['Different phyla', 'Different genera', 'The same family but different genera', 'The same species'],
		answer: 3,
		explain: 'An ANI of about 95% or more is the widely used boundary for genomes of one species.'
	},
	{
		id: 'u12',
		question: 'Butyrate made by gut bacteria is the main energy source of which cells?',
		options: ['Colonocytes lining the colon', 'Red blood cells', 'Liver cells', 'Neurons'],
		answer: 0,
		explain: 'Colonocytes oxidise butyrate for much of their energy, which also keeps the gut lining close to the surface low in oxygen.'
	},
	{
		id: 'u13',
		question: 'If 1,000 E. coli cells, each about 2 µm long, were lined up end to end, how long would the line be?',
		options: ['2 µm', '2 cm', '2 m', '2 mm'],
		answer: 3,
		explain: '1,000 times 2 µm is 2,000 µm, which is 2 mm: about the thickness of a coin.',
		fun: true
	},
	{
		id: 'u14',
		question: 'What powers the rotation of a bacterial flagellum?',
		options: ['ATP hydrolysis by dynein', 'An ion gradient across the membrane (protons or sodium)', 'GTP hydrolysis', 'Light'],
		answer: 1,
		explain: 'The flagellar motor turns as protons (or sodium ions) flow through its stator proteins; dynein drives eukaryotic flagella instead.'
	},
	{
		id: 'u15',
		question: 'The natural inducer of the lac operon in E. coli is:',
		options: ['Lactose itself', 'Glucose', 'Allolactose', 'Galactose'],
		answer: 2,
		explain: 'Beta-galactosidase converts some lactose to allolactose, which binds the LacI repressor and releases it from the operator.'
	},
	{
		id: 'u16',
		question: 'A bacterial genome is 4.6 Mb, mostly coding, with genes about 1 kb long. About how many genes does it carry?',
		options: ['About 400', 'About 4,000', 'About 40,000', 'About 400,000'],
		answer: 1,
		explain: 'Bacterial genomes are densely packed, close to one gene per kilobase, so 4.6 Mb holds roughly four thousand genes (E. coli has about 4,300).'
	},
	{
		id: 'u17',
		question: 'Which order goes from smallest to largest?',
		options: [
			'Bacterium, virus, human red blood cell',
			'Virus, bacterium, human red blood cell',
			'Virus, human red blood cell, bacterium',
			'Human red blood cell, bacterium, virus'
		],
		answer: 1,
		explain: 'Typical viruses are tens to hundreds of nanometres, bacteria a micrometre or two, and red blood cells about 7 to 8 µm across.',
		fun: true
	},
	{
		id: 'u18',
		question: 'The Tat pathway exports proteins across the cytoplasmic membrane in which state?',
		options: ['Already folded', 'Unfolded, as a chain', 'Bound to DNA', 'As separate amino acids'],
		answer: 0,
		explain: 'Tat (twin-arginine translocation) moves folded proteins, often with their cofactors in place; Sec moves unfolded chains.'
	},
	{
		id: 'u19',
		question: 'A homofermentative Lactobacillus growing on glucose mainly makes:',
		options: ['Ethanol and CO2', 'Butyrate', 'Lactate', 'Acetate and hydrogen'],
		answer: 2,
		explain: 'Homofermenters run glycolysis and reduce pyruvate to lactate, giving about two lactate per glucose.'
	},
	{
		id: 'u20',
		question: 'Which sign best suggests that a genome assembly is contaminated with another organism?',
		options: ['A high N50', 'A low GC content', 'Many reads shorter than 100 bases', 'Many single-copy marker genes found twice'],
		answer: 3,
		explain: 'Marker genes expected once per genome that appear twice point to DNA from a second genome; CheckM reports this as contamination.'
	},
	{
		id: 'u21',
		question: 'Roughly how do the bacteria in a human body compare in number with the human cells?',
		options: ['About the same order: roughly as many bacteria as human cells', 'About ten times more bacteria', 'About a hundred times more bacteria', 'About a thousand times fewer bacteria'],
		answer: 0,
		explain: 'A 2016 estimate put them at roughly 38 trillion bacteria and 30 trillion human cells; the old "ten to one" figure did not hold up.',
		fun: true
	},
	{
		id: 'u22',
		question: 'Mitochondria descend from an ancestor in which group?',
		options: ['Archaea', 'Cyanobacteria', 'Alphaproteobacteria', 'Fungi'],
		answer: 2,
		explain: 'Mitochondria come from an alphaproteobacterial endosymbiont; chloroplasts come from cyanobacteria.'
	},
	{
		id: 'u23',
		question: 'Which bacterium glows inside the light organ of the Hawaiian bobtail squid?',
		options: ['Staphylococcus aureus', 'Aliivibrio fischeri', 'Bacillus subtilis', 'Escherichia coli'],
		answer: 1,
		explain: 'Aliivibrio (formerly Vibrio) fischeri switches on its lux genes by quorum sensing once dense enough in the light organ.',
		fun: true
	},
	{
		id: 'u24',
		question: 'Akkermansia muciniphila, a common gut bacterium, grows mainly on:',
		options: ['Dietary cellulose', 'Host mucin glycoproteins', 'Bile acids', 'Dietary fat'],
		answer: 1,
		explain: 'As its name says, it degrades the mucins of the gut mucus layer, a niche it can use even when dietary fibre is scarce.'
	},
	{
		id: 'u25',
		question: 'Bacteroides species bind and import dietary polysaccharides with outer membrane protein pairs named:',
		options: ['FtsZ and MreB', 'SusC and SusD', 'LacI and LacZ', 'OmpF and OmpC'],
		answer: 1,
		explain: 'Polysaccharide utilisation loci encode SusD-like glycan-binding and SusC-like transport proteins, named after the starch utilisation system.'
	}
];
