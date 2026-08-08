/**
 * Curated encyclopedic knowledge base.
 *
 * Authored, fact-checked content that the open datasets don't provide:
 * famous destinations, notable inventions, signature foods, major festivals,
 * and a BCE/CE historical timeline (including ancient civilizations). Keyed by
 * ISO 3166-1 alpha-3 code. Countries without a curated entry fall back to
 * data-derived content in the generator — nothing here is fabricated.
 *
 * Images use Wikimedia Commons `Special:FilePath`, which 301-redirects to the
 * current thumbnail on upload.wikimedia.org. These load directly in the
 * visitor's browser; the UI hides any that fail to resolve.
 */

export type Destination = { name: string; blurb: string; image?: string; lat?: number; lng?: number };
export type Invention = { name: string; blurb: string; year?: string };
export type Food = { name: string; blurb: string; image?: string };
export type Festival = { name: string; blurb: string; when?: string };
export type TimelineItem = { when: string; era: "BCE" | "CE"; title: string; description: string };

export type CountryKnowledge = {
  hero?: string;
  destinations?: Destination[];
  inventions?: Invention[];
  foods?: Food[];
  festivals?: Festival[];
  timeline?: TimelineItem[];
};

/** Build a stable Wikimedia Commons image URL from an exact file name. */
export function commons(filename: string, width = 1200): string {
  return `https://commons.wikimedia.org/wiki/Special:FilePath/${encodeURIComponent(filename)}?width=${width}`;
}

// ─────────────────────────────────────────────────────────────────────────────
// Per-country curated knowledge. Blurbs are concise, factual summaries.
// ─────────────────────────────────────────────────────────────────────────────

export const KNOWLEDGE: Record<string, CountryKnowledge> = {
  /* ── EUROPE ────────────────────────────────────────────────────────────── */
  FRA: {
    hero: "Tour Eiffel Wikimedia Commons.jpg",
    destinations: [
      { name: "Eiffel Tower", blurb: "The 330 m wrought-iron tower on the Champ de Mars, built for the 1889 World's Fair, is the most-visited paid monument on Earth and the enduring symbol of Paris.", image: "Tour Eiffel Wikimedia Commons.jpg" },
      { name: "Palace of Versailles", blurb: "Louis XIV's vast royal château with its Hall of Mirrors and formal gardens, a benchmark of absolutist grandeur and a UNESCO World Heritage Site.", image: "Chateau Versailles Galerie des Glaces.jpg" },
      { name: "Mont-Saint-Michel", blurb: "A medieval abbey crowning a tidal island off Normandy, ringed by some of Europe's highest tides.", image: "Mont Saint-Michel 3, Normandy, France - July 2011.jpg" },
      { name: "French Riviera (Côte d'Azur)", blurb: "The Mediterranean coastline around Nice, Cannes and Saint-Tropez, celebrated for its light, beaches and film festival." },
    ],
    inventions: [
      { name: "Photography (daguerreotype)", blurb: "Louis Daguerre announced the first practical photographic process.", year: "1839" },
      { name: "Pasteurization", blurb: "Louis Pasteur developed heat treatment to kill pathogens, transforming food safety and medicine.", year: "1864" },
      { name: "Cinema", blurb: "The Lumière brothers held the first public film screening with their Cinématographe.", year: "1895" },
      { name: "Braille", blurb: "Louis Braille devised the tactile reading system for the blind.", year: "1824" },
    ],
    foods: [
      { name: "Baguette", blurb: "The slender crusty loaf, protected by law and inscribed on UNESCO's cultural heritage list in 2022." },
      { name: "Coq au vin", blurb: "Chicken braised slowly in red wine with mushrooms, lardons and onions." },
      { name: "Croissant", blurb: "A buttery, laminated viennoiserie now synonymous with the French breakfast." },
      { name: "Ratatouille", blurb: "A Provençal stew of summer vegetables — courgette, aubergine, pepper and tomato." },
    ],
    festivals: [
      { name: "Bastille Day", blurb: "The national day marking the 1789 storming of the Bastille, with a military parade on the Champs-Élysées and fireworks at the Eiffel Tower.", when: "14 July" },
      { name: "Cannes Film Festival", blurb: "The world's most prestigious film festival, awarding the Palme d'Or on the Riviera.", when: "May" },
      { name: "Fête de la Musique", blurb: "A nationwide free music festival on the summer solstice, now copied worldwide.", when: "21 June" },
    ],
    timeline: [
      { when: "c. 600 BCE", era: "BCE", title: "Greeks found Massalia", description: "Greek colonists establish Massalia (Marseille), the oldest city in France." },
      { when: "58–51 BCE", era: "BCE", title: "Roman conquest of Gaul", description: "Julius Caesar defeats Vercingetorix at Alesia, bringing Gaul into the Roman world." },
      { when: "486 CE", era: "CE", title: "Frankish kingdom", description: "Clovis I unites the Franks, founding the Merovingian dynasty and Christian Frankish rule." },
      { when: "800 CE", era: "CE", title: "Charlemagne crowned emperor", description: "The Frankish king is crowned Emperor of the Romans, uniting much of Western Europe." },
      { when: "1789 CE", era: "CE", title: "French Revolution", description: "The storming of the Bastille begins a revolution that topples the monarchy and proclaims the Rights of Man." },
      { when: "1804 CE", era: "CE", title: "Napoleonic Empire", description: "Napoleon Bonaparte crowns himself emperor; his legal code reshapes law across Europe." },
      { when: "1958 CE", era: "CE", title: "Fifth Republic", description: "Charles de Gaulle inaugurates the current French Republic." },
    ],
  },
  ITA: {
    hero: "Colosseo 2020.jpg",
    destinations: [
      { name: "Colosseum", blurb: "Rome's colossal 1st-century amphitheatre, which once seated 50,000 spectators for gladiatorial games.", image: "Colosseo 2020.jpg" },
      { name: "Venice & its canals", blurb: "A city built across 118 islands in a lagoon, laced by canals and crowned by St Mark's Basilica.", image: "Canal Grande Chiesa della Salute e Dogana dal ponte dell Accademia.jpg" },
      { name: "Florence & the Duomo", blurb: "Cradle of the Renaissance, home to Brunelleschi's dome, the Uffizi and Michelangelo's David." },
      { name: "Pompeii", blurb: "The Roman city frozen by the 79 CE eruption of Vesuvius, the world's most complete ancient townscape." },
    ],
    inventions: [
      { name: "Concrete (opus caementicium)", blurb: "Roman hydraulic concrete enabled domes and aqueducts that still stand." },
      { name: "The battery", blurb: "Alessandro Volta built the first electrochemical cell, the voltaic pile.", year: "1800" },
      { name: "The radio", blurb: "Guglielmo Marconi pioneered long-distance wireless telegraphy.", year: "1895" },
      { name: "Double-entry bookkeeping", blurb: "Luca Pacioli codified modern accounting.", year: "1494" },
    ],
    foods: [
      { name: "Pizza Napoletana", blurb: "The Neapolitan wood-fired pizza, a UNESCO-recognised craft." },
      { name: "Pasta", blurb: "Hundreds of regional shapes and sauces, from carbonara to ragù alla bolognese." },
      { name: "Espresso & gelato", blurb: "Italy's coffee culture and dense, silky ice cream, both exported worldwide." },
    ],
    festivals: [
      { name: "Venice Carnival", blurb: "Elaborate masked balls and costumes in the weeks before Lent.", when: "February" },
      { name: "Palio di Siena", blurb: "A bareback horse race around Siena's medieval square, run since the 17th century.", when: "July & August" },
    ],
    timeline: [
      { when: "753 BCE", era: "BCE", title: "Founding of Rome", description: "Traditional date for the founding of the city of Rome on the Palatine Hill." },
      { when: "509 BCE", era: "BCE", title: "Roman Republic", description: "The Romans overthrow their kings and establish a republic governed by a senate." },
      { when: "27 BCE", era: "BCE", title: "Roman Empire", description: "Augustus becomes the first Roman emperor, beginning two centuries of Pax Romana." },
      { when: "476 CE", era: "CE", title: "Fall of the Western Empire", description: "The last Western Roman emperor is deposed, ending classical antiquity in the West." },
      { when: "1300s–1500s CE", era: "CE", title: "The Renaissance", description: "Florence, Rome and Venice drive a rebirth of art, science and humanism." },
      { when: "1861 CE", era: "CE", title: "Unification of Italy", description: "The Risorgimento unites the peninsula into the Kingdom of Italy." },
      { when: "1946 CE", era: "CE", title: "Italian Republic", description: "Italians vote to abolish the monarchy and found the modern republic." },
    ],
  },
  GRC: {
    hero: "Attica 06-13 Athens 50 View from Philopappos - Acropolis Hill.jpg",
    destinations: [
      { name: "Acropolis of Athens", blurb: "The marble citadel crowned by the 5th-century BCE Parthenon, the defining monument of classical Greece.", image: "The Parthenon in Athens.jpg" },
      { name: "Santorini", blurb: "A whitewashed island perched on the caldera of a drowned volcano, famed for its sunsets." },
      { name: "Delphi", blurb: "The mountainside sanctuary of Apollo, seat of the ancient world's most famous oracle." },
      { name: "Meteora", blurb: "Byzantine monasteries built atop sheer sandstone pillars in central Greece." },
    ],
    inventions: [
      { name: "Democracy", blurb: "Athens developed the first direct citizen democracy.", year: "c. 508 BCE" },
      { name: "Formal geometry", blurb: "Euclid's Elements systematised mathematics for two millennia.", year: "c. 300 BCE" },
      { name: "The Antikythera mechanism", blurb: "An astonishing geared analogue computer for astronomical prediction.", year: "c. 100 BCE" },
      { name: "Western philosophy & theatre", blurb: "Socrates, Plato and Aristotle founded philosophy; Athens invented drama." },
    ],
    foods: [
      { name: "Moussaka", blurb: "Layered aubergine, spiced lamb and béchamel baked golden." },
      { name: "Souvlaki & gyros", blurb: "Grilled skewered meat and shaved rotisserie meat in pita." },
      { name: "Greek salad (horiatiki)", blurb: "Tomato, cucumber, olives and a slab of feta with olive oil and oregano." },
    ],
    festivals: [
      { name: "Greek Orthodox Easter", blurb: "The country's most important religious holiday, with midnight candle processions and roast lamb.", when: "Spring" },
      { name: "Athens & Epidaurus Festival", blurb: "Ancient dramas staged in antique theatres each summer.", when: "Summer" },
    ],
    timeline: [
      { when: "c. 3000 BCE", era: "BCE", title: "Minoan civilization", description: "Europe's first advanced civilization flourishes on Crete, building the palace of Knossos." },
      { when: "c. 1200 BCE", era: "BCE", title: "Mycenaean age", description: "The warrior kingdoms of the Trojan War era; Linear B is the earliest Greek writing." },
      { when: "508 BCE", era: "BCE", title: "Athenian democracy", description: "Cleisthenes' reforms establish rule by the citizen assembly." },
      { when: "480 BCE", era: "BCE", title: "Persian Wars", description: "Greek city-states repel Persian invasions at Salamis and Plataea." },
      { when: "336 BCE", era: "BCE", title: "Alexander the Great", description: "Alexander of Macedon spreads Greek culture from Egypt to India." },
      { when: "1453 CE", era: "CE", title: "Fall of Constantinople", description: "The Ottoman conquest ends the Greek-speaking Byzantine Empire." },
      { when: "1821 CE", era: "CE", title: "War of Independence", description: "Greeks rise against Ottoman rule and win a modern nation-state." },
    ],
  },
  ESP: {
    hero: "Sagrada Familia 01.jpg",
    destinations: [
      { name: "Sagrada Família", blurb: "Gaudí's still-unfinished Barcelona basilica, under construction since 1882.", image: "Sagrada Familia 01.jpg" },
      { name: "Alhambra", blurb: "A hilltop palace-fortress in Granada, the crowning glory of Moorish Spain." },
      { name: "Prado & Madrid", blurb: "One of the world's great art museums, holding Velázquez and Goya, in the vibrant capital." },
      { name: "Camino de Santiago", blurb: "The medieval pilgrimage network converging on Santiago de Compostela." },
    ],
    inventions: [
      { name: "The mop and bucket", blurb: "Manuel Jalón Corominas patented the modern wringer mop.", year: "1956" },
      { name: "The stapler (early form)", blurb: "An 18th-century device for King Louis XV is often traced to Spanish craftsmen." },
      { name: "The submarine (Peral)", blurb: "Isaac Peral built an early electric-powered military submarine.", year: "1888" },
    ],
    foods: [
      { name: "Paella", blurb: "Valencia's saffron rice cooked in a wide pan with rabbit, beans or seafood." },
      { name: "Jamón ibérico", blurb: "Acorn-fed cured ham, aged for years." },
      { name: "Tapas", blurb: "The social tradition of small shared plates, from patatas bravas to gambas." },
    ],
    festivals: [
      { name: "La Tomatina", blurb: "A giant tomato fight in Buñol every August.", when: "Last Wednesday of August" },
      { name: "San Fermín (Running of the Bulls)", blurb: "Pamplona's week-long fiesta with the famous bull run.", when: "July" },
      { name: "Semana Santa", blurb: "Solemn Holy Week processions, most famous in Seville.", when: "Spring" },
    ],
    timeline: [
      { when: "c. 1100 BCE", era: "BCE", title: "Phoenicians found Cádiz", description: "Traders establish Gadir, one of Western Europe's oldest cities." },
      { when: "218 BCE", era: "BCE", title: "Roman Hispania", description: "Rome takes Iberia during the Punic Wars, ruling for six centuries." },
      { when: "711 CE", era: "CE", title: "Moorish conquest", description: "Muslim armies cross from Africa and establish Al-Andalus." },
      { when: "1492 CE", era: "CE", title: "Reconquista & Columbus", description: "Granada falls, completing the Reconquista, and Columbus reaches the Americas under Spanish flag." },
      { when: "1516 CE", era: "CE", title: "Global empire", description: "The Habsburgs build an empire on which 'the sun never set'." },
      { when: "1975 CE", era: "CE", title: "Return to democracy", description: "After Franco's death, Spain transitions to a constitutional monarchy." },
    ],
  },
  GBR: {
    hero: "Palace of Westminster from the dome on Methodist Central Hall.jpg",
    destinations: [
      { name: "Tower of London & Big Ben", blurb: "A 1,000-year-old fortress guarding the Crown Jewels, and the clock tower of the Houses of Parliament." },
      { name: "Stonehenge", blurb: "A prehistoric ring of standing stones raised on Salisbury Plain around 2500 BCE.", image: "Stonehenge2007 07 30.jpg" },
      { name: "Edinburgh", blurb: "Scotland's capital, crowned by a castle on an extinct volcano." },
      { name: "The Lake District", blurb: "Glacial lakes and fells that inspired Wordsworth and Beatrix Potter." },
    ],
    inventions: [
      { name: "The steam engine & railways", blurb: "Watt, Trevithick and Stephenson powered the Industrial Revolution.", year: "1700s–1800s" },
      { name: "The World Wide Web", blurb: "Tim Berners-Lee invented the Web at CERN.", year: "1989" },
      { name: "Penicillin", blurb: "Alexander Fleming discovered the first antibiotic.", year: "1928" },
      { name: "The telephone & television", blurb: "Bell (Scots-born) and Baird pioneered voice and picture transmission." },
    ],
    foods: [
      { name: "Fish and chips", blurb: "Battered fish with thick-cut fried potatoes, the classic seaside meal." },
      { name: "Sunday roast", blurb: "Roast meat with potatoes, vegetables and Yorkshire pudding." },
      { name: "Afternoon tea", blurb: "Tea with scones, clotted cream and finger sandwiches." },
    ],
    festivals: [
      { name: "Edinburgh Festival Fringe", blurb: "The world's largest arts festival, filling Edinburgh each August.", when: "August" },
      { name: "Notting Hill Carnival", blurb: "Europe's biggest street festival, celebrating Caribbean culture in London.", when: "August" },
    ],
    timeline: [
      { when: "c. 2500 BCE", era: "BCE", title: "Stonehenge", description: "Neolithic Britons raise the great stone circle on Salisbury Plain." },
      { when: "43 CE", era: "CE", title: "Roman Britain", description: "Emperor Claudius conquers southern Britain; Londinium is founded." },
      { when: "1066 CE", era: "CE", title: "Norman Conquest", description: "William of Normandy defeats Harold at Hastings, reshaping England." },
      { when: "1215 CE", era: "CE", title: "Magna Carta", description: "Barons force King John to accept limits on royal power." },
      { when: "1707 CE", era: "CE", title: "Union of Great Britain", description: "England and Scotland unite under a single parliament." },
      { when: "1760s CE", era: "CE", title: "Industrial Revolution", description: "Britain pioneers mechanised industry, transforming the modern world." },
    ],
  },
  DEU: {
    hero: "Schloss Neuschwanstein 2013.jpg",
    destinations: [
      { name: "Neuschwanstein Castle", blurb: "Ludwig II's fairy-tale Bavarian castle that inspired Disney's.", image: "Schloss Neuschwanstein 2013.jpg" },
      { name: "Brandenburg Gate", blurb: "Berlin's neoclassical triumphal arch, a symbol of German reunification." },
      { name: "Cologne Cathedral", blurb: "A Gothic masterpiece that took over 600 years to complete." },
      { name: "The Black Forest", blurb: "Dense wooded highlands famed for cuckoo clocks and spa towns." },
    ],
    inventions: [
      { name: "The printing press", blurb: "Johannes Gutenberg's movable type launched the age of mass communication.", year: "c. 1440" },
      { name: "The automobile", blurb: "Carl Benz built the first practical petrol-driven car.", year: "1885" },
      { name: "Aspirin", blurb: "Bayer chemists synthesised acetylsalicylic acid as a mass medicine.", year: "1897" },
      { name: "Relativity", blurb: "Albert Einstein reformulated physics with special and general relativity.", year: "1905–1915" },
    ],
    foods: [
      { name: "Bratwurst", blurb: "Grilled sausages, a street-food and beer-garden staple." },
      { name: "Pretzel (Brezel)", blurb: "The knotted, salted baked bread of southern Germany." },
      { name: "Schwarzwälder Kirschtorte", blurb: "Black Forest cherry-and-cream chocolate gateau." },
    ],
    festivals: [
      { name: "Oktoberfest", blurb: "Munich's giant beer festival, drawing six million visitors a year.", when: "Late September" },
      { name: "Christmas markets", blurb: "Illuminated Weihnachtsmärkte with mulled wine and crafts in every city.", when: "December" },
    ],
    timeline: [
      { when: "9 CE", era: "CE", title: "Battle of the Teutoburg Forest", description: "Germanic tribes annihilate three Roman legions, halting Rome at the Rhine." },
      { when: "800 CE", era: "CE", title: "Carolingian Empire", description: "Charlemagne's realm forms the seed of German statehood." },
      { when: "1517 CE", era: "CE", title: "The Reformation", description: "Martin Luther's 95 Theses split Western Christianity." },
      { when: "1871 CE", era: "CE", title: "German unification", description: "Bismarck forges the German Empire under Prussia." },
      { when: "1939–1945 CE", era: "CE", title: "Second World War", description: "Nazi Germany's aggression and the Holocaust end in defeat and division." },
      { when: "1990 CE", era: "CE", title: "Reunification", description: "East and West Germany reunite a year after the Berlin Wall falls." },
    ],
  },
  NLD: {
    destinations: [
      { name: "Amsterdam canals", blurb: "The 17th-century ring of canals, a UNESCO site best seen by boat or bike." },
      { name: "Keukenhof", blurb: "The world's largest flower garden, blazing with tulips each spring." },
      { name: "Rijksmuseum", blurb: "Home to Rembrandt's Night Watch and the Dutch Golden Age masters." },
    ],
    inventions: [
      { name: "The telescope & microscope", blurb: "Dutch lens-makers (Lippershey, Van Leeuwenhoek) opened the very large and very small.", year: "1600s" },
      { name: "Wi-Fi", blurb: "Key patents behind wireless networking trace to Dutch engineers at NXP/CSIRO collaborations." },
      { name: "The stock exchange", blurb: "The Amsterdam bourse (1602) was the first modern securities market." },
    ],
    foods: [
      { name: "Stroopwafel", blurb: "Two thin waffles glued with caramel syrup." },
      { name: "Haring", blurb: "Raw brined herring eaten with onions, a street classic." },
      { name: "Gouda & Edam cheese", blurb: "World-famous cheeses sold at historic markets." },
    ],
    festivals: [
      { name: "King's Day", blurb: "The whole country dresses in orange for street parties and flea markets.", when: "27 April" },
    ],
    timeline: [
      { when: "1602 CE", era: "CE", title: "Dutch East India Company", description: "The world's first multinational and stock-issuing company is founded." },
      { when: "1600s CE", era: "CE", title: "Dutch Golden Age", description: "Trade, science and painting (Rembrandt, Vermeer) flourish." },
      { when: "1815 CE", era: "CE", title: "Kingdom of the Netherlands", description: "The modern kingdom is established after the Napoleonic wars." },
    ],
  },
  PRT: {
    destinations: [
      { name: "Lisbon & Belém Tower", blurb: "A hilly capital of tiled façades, trams and Age-of-Discovery monuments." },
      { name: "Porto & the Douro", blurb: "Riverside cellars of port wine below terraced vineyards." },
      { name: "Sintra", blurb: "Romantic palaces and gardens in forested hills near Lisbon." },
    ],
    inventions: [
      { name: "Ocean navigation", blurb: "Portugal pioneered the caravel and open-ocean exploration.", year: "1400s" },
    ],
    foods: [
      { name: "Pastel de nata", blurb: "Caramelised custard tart in flaky pastry." },
      { name: "Bacalhau", blurb: "Salt cod, said to have 365 recipes — one for every day." },
    ],
    festivals: [
      { name: "Festas de Lisboa (Santo António)", blurb: "June street parties with grilled sardines and marchas populares.", when: "June" },
    ],
    timeline: [
      { when: "1143 CE", era: "CE", title: "Kingdom of Portugal", description: "Afonso Henriques wins recognition as king; Portugal's borders are Europe's oldest." },
      { when: "1498 CE", era: "CE", title: "Sea route to India", description: "Vasco da Gama reaches India, opening the maritime spice trade." },
      { when: "1974 CE", era: "CE", title: "Carnation Revolution", description: "A near-bloodless coup ends dictatorship and begins democracy." },
    ],
  },
  RUS: {
    hero: "Moscow July 2011-7a.jpg",
    destinations: [
      { name: "Red Square & the Kremlin", blurb: "Moscow's historic heart, ringed by St Basil's onion domes and the seat of power.", image: "Moscow July 2011-7a.jpg" },
      { name: "Hermitage, St Petersburg", blurb: "One of the world's largest art museums, in the tsars' Winter Palace." },
      { name: "Trans-Siberian Railway", blurb: "The 9,289 km line from Moscow to the Pacific, the longest on Earth." },
    ],
    inventions: [
      { name: "The periodic table", blurb: "Dmitri Mendeleev arranged the elements and predicted new ones.", year: "1869" },
      { name: "Artificial satellite", blurb: "Sputnik 1 became the first human-made object to orbit Earth.", year: "1957" },
      { name: "Human spaceflight", blurb: "Yuri Gagarin became the first person in space.", year: "1961" },
    ],
    foods: [
      { name: "Borscht", blurb: "Beetroot soup served with sour cream." },
      { name: "Pelmeni", blurb: "Siberian meat dumplings." },
      { name: "Blini", blurb: "Thin pancakes served with caviar, jam or sour cream." },
    ],
    festivals: [
      { name: "Maslenitsa", blurb: "A pre-Lenten 'pancake week' with bonfires and folk games.", when: "Late winter" },
    ],
    timeline: [
      { when: "882 CE", era: "CE", title: "Kievan Rus'", description: "The first East Slavic state coalesces around Kiev and Novgorod." },
      { when: "988 CE", era: "CE", title: "Christianization", description: "Vladimir the Great adopts Orthodox Christianity." },
      { when: "1547 CE", era: "CE", title: "Tsardom of Russia", description: "Ivan the Terrible is crowned the first tsar." },
      { when: "1917 CE", era: "CE", title: "Russian Revolution", description: "The Bolsheviks overthrow the monarchy and found the Soviet state." },
      { when: "1991 CE", era: "CE", title: "End of the USSR", description: "The Soviet Union dissolves into fifteen independent republics." },
    ],
  },

  /* ── ASIA ──────────────────────────────────────────────────────────────── */
  CHN: {
    hero: "The Great Wall of China at Jinshanling-edit.jpg",
    destinations: [
      { name: "Great Wall of China", blurb: "Over 21,000 km of walls built across two millennia to guard the northern frontier.", image: "The Great Wall of China at Jinshanling-edit.jpg" },
      { name: "Forbidden City", blurb: "Beijing's vast Ming-Qing imperial palace, the largest in the world." },
      { name: "Terracotta Army", blurb: "Thousands of life-size clay soldiers guarding the first emperor's tomb at Xi'an.", image: "Terracotta Army Pit 1 - 2.jpg" },
      { name: "Li River, Guilin", blurb: "Karst peaks mirrored in the river, a scene from Chinese ink painting." },
    ],
    inventions: [
      { name: "Papermaking", blurb: "Cai Lun standardised paper from pulp.", year: "105 CE" },
      { name: "Gunpowder", blurb: "Alchemists discovered the explosive mixture, revolutionising warfare.", year: "9th c. CE" },
      { name: "The compass", blurb: "Lodestone navigation transformed seafaring.", year: "Han–Song" },
      { name: "Printing", blurb: "Woodblock and later movable type predate Gutenberg by centuries.", year: "7th–11th c. CE" },
    ],
    foods: [
      { name: "Peking duck", blurb: "Lacquered roast duck carved into crisp skin, served with pancakes." },
      { name: "Dim sum", blurb: "Cantonese small plates — dumplings, buns and rolls — with tea." },
      { name: "Hot pot", blurb: "A shared simmering broth for cooking meat and vegetables at the table." },
    ],
    festivals: [
      { name: "Chinese New Year", blurb: "The Spring Festival, the world's largest annual human migration, with lanterns and fireworks.", when: "Jan–Feb" },
      { name: "Mid-Autumn Festival", blurb: "Families reunite to admire the full moon and share mooncakes.", when: "Autumn" },
    ],
    timeline: [
      { when: "c. 1600 BCE", era: "BCE", title: "Shang dynasty", description: "China's first historically documented dynasty; earliest Chinese writing on oracle bones." },
      { when: "551 BCE", era: "BCE", title: "Confucius", description: "The philosopher whose ethics would shape East Asian civilization is born." },
      { when: "221 BCE", era: "BCE", title: "Unification under Qin", description: "Qin Shi Huang unifies China as its first emperor and links the Great Wall." },
      { when: "618 CE", era: "CE", title: "Tang golden age", description: "The cosmopolitan Tang dynasty makes China a cultural and economic superpower." },
      { when: "1271 CE", era: "CE", title: "Mongol Yuan dynasty", description: "Kublai Khan rules China as part of the Mongol Empire." },
      { when: "1912 CE", era: "CE", title: "End of empire", description: "The Qing dynasty falls and the Republic of China is proclaimed." },
      { when: "1949 CE", era: "CE", title: "People's Republic", description: "Mao Zedong proclaims the People's Republic of China." },
    ],
  },
  JPN: {
    hero: "080103 hakone lake ashi.jpg",
    destinations: [
      { name: "Mount Fuji", blurb: "The sacred, symmetrical volcano, Japan's highest peak and a national icon.", image: "080103 hakone lake ashi.jpg" },
      { name: "Kyoto's temples", blurb: "The former imperial capital, with 1,600 Buddhist temples including golden Kinkaku-ji.", image: "Kinkaku-ji 2.jpg" },
      { name: "Tokyo", blurb: "A hyper-modern megacity of neon, ancient shrines and Michelin-starred dining." },
      { name: "Hiroshima Peace Memorial", blurb: "The A-Bomb Dome preserved as a monument to peace." },
    ],
    inventions: [
      { name: "The pocket calculator & LCD", blurb: "Japanese firms drove portable electronics and flat displays." },
      { name: "Bullet train (Shinkansen)", blurb: "The first high-speed rail network opened for the 1964 Olympics.", year: "1964" },
      { name: "Lithium-ion battery", blurb: "Akira Yoshino developed the rechargeable battery behind modern devices.", year: "1985" },
      { name: "QR code", blurb: "Denso Wave invented the two-dimensional barcode.", year: "1994" },
    ],
    foods: [
      { name: "Sushi", blurb: "Vinegared rice with raw fish, now a global cuisine." },
      { name: "Ramen", blurb: "Wheat noodles in rich broth, with endless regional styles." },
      { name: "Tempura", blurb: "Seafood and vegetables in a light, crisp batter." },
    ],
    festivals: [
      { name: "Hanami (cherry blossom)", blurb: "Nationwide picnics under blooming sakura each spring.", when: "Late March–April" },
      { name: "Gion Matsuri", blurb: "Kyoto's month-long festival with grand float processions.", when: "July" },
    ],
    timeline: [
      { when: "c. 300 BCE", era: "BCE", title: "Yayoi period", description: "Wet-rice farming and metalworking arrive, reshaping early Japan." },
      { when: "538 CE", era: "CE", title: "Buddhism arrives", description: "Buddhism enters Japan from Korea, transforming art and the state." },
      { when: "794 CE", era: "CE", title: "Heian court", description: "The imperial capital moves to Kyoto; classical court culture flowers." },
      { when: "1192 CE", era: "CE", title: "Age of the shogun", description: "The Kamakura shogunate begins seven centuries of samurai rule." },
      { when: "1868 CE", era: "CE", title: "Meiji Restoration", description: "Japan rapidly modernises into an industrial power." },
      { when: "1945 CE", era: "CE", title: "Post-war Japan", description: "Defeat in WWII gives way to a pacifist constitution and an economic miracle." },
    ],
  },
  IND: {
    hero: "Taj Mahal (Edited).jpeg",
    destinations: [
      { name: "Taj Mahal", blurb: "The white-marble mausoleum built by Shah Jahan for his wife, a peak of Mughal architecture.", image: "Taj Mahal (Edited).jpeg" },
      { name: "Jaipur & the Amber Fort", blurb: "The 'Pink City' of Rajasthan with hilltop forts and palaces." },
      { name: "Varanasi", blurb: "One of the world's oldest living cities, where pilgrims bathe in the Ganges." },
      { name: "Kerala backwaters", blurb: "A tranquil network of lagoons and canals plied by houseboats." },
    ],
    inventions: [
      { name: "The concept of zero", blurb: "Indian mathematicians (Brahmagupta) formalised zero and the decimal system.", year: "c. 628 CE" },
      { name: "Chess (chaturanga)", blurb: "The ancestor of modern chess emerged in India.", year: "c. 6th c. CE" },
      { name: "Cataract surgery & Ayurveda", blurb: "Sushruta described surgery and medicine over two millennia ago." },
      { name: "Fibre-optic pioneering & USB", blurb: "Narinder Singh Kapany advanced fibre optics; Ajay Bhatt co-invented USB." },
    ],
    foods: [
      { name: "Biryani", blurb: "Fragrant layered rice with spiced meat or vegetables." },
      { name: "Masala dosa", blurb: "A crisp fermented crepe filled with spiced potato." },
      { name: "Butter chicken & curries", blurb: "Endlessly varied regional curries, from creamy to fiery." },
    ],
    festivals: [
      { name: "Diwali", blurb: "The festival of lights, celebrated with lamps, sweets and fireworks.", when: "Oct–Nov" },
      { name: "Holi", blurb: "The exuberant spring festival of coloured powders.", when: "March" },
      { name: "Kumbh Mela", blurb: "The largest religious gathering on Earth, drawing tens of millions of pilgrims." },
    ],
    timeline: [
      { when: "c. 2600 BCE", era: "BCE", title: "Indus Valley Civilization", description: "Harappa and Mohenjo-daro build planned cities with drainage and standardised weights." },
      { when: "c. 1500 BCE", era: "BCE", title: "Vedic period", description: "The Vedas are composed; foundations of Hindu thought and Sanskrit are laid." },
      { when: "c. 563 BCE", era: "BCE", title: "The Buddha", description: "Siddhartha Gautama founds Buddhism in the Gangetic plain." },
      { when: "322 BCE", era: "BCE", title: "Maurya Empire", description: "Chandragupta and later Ashoka unite most of the subcontinent." },
      { when: "1526 CE", era: "CE", title: "Mughal Empire", description: "Babur founds an empire that builds the Taj Mahal and a rich composite culture." },
      { when: "1858 CE", era: "CE", title: "British Raj", description: "The British Crown assumes direct rule over India." },
      { when: "1947 CE", era: "CE", title: "Independence", description: "India wins independence and becomes the world's largest democracy." },
    ],
  },
  IRQ: {
    destinations: [
      { name: "Babylon", blurb: "The ruins of the ancient Mesopotamian capital, home of the Ishtar Gate and Hanging Gardens legend." },
      { name: "Ur", blurb: "A Sumerian city with a great ziggurat, among humanity's oldest urban sites." },
      { name: "Erbil Citadel", blurb: "A tell continuously inhabited for perhaps 6,000 years." },
    ],
    inventions: [
      { name: "Writing (cuneiform)", blurb: "Sumerians invented the first known writing system on clay tablets.", year: "c. 3200 BCE" },
      { name: "The wheel", blurb: "Mesopotamia gave the world the wheel and the potter's wheel.", year: "c. 3500 BCE" },
      { name: "The sexagesimal system", blurb: "Babylonians based time and angles on 60 — still used for minutes and degrees." },
      { name: "Written law", blurb: "The Code of Hammurabi is one of the earliest legal codes.", year: "c. 1754 BCE" },
    ],
    foods: [
      { name: "Masgouf", blurb: "Iraq's national dish: grilled river carp, an ancient Mesopotamian recipe." },
      { name: "Dolma", blurb: "Vine leaves and vegetables stuffed with spiced rice." },
    ],
    festivals: [
      { name: "Nowruz", blurb: "The Persian/Kurdish new year, welcomed with fire and feasting in the north.", when: "21 March" },
    ],
    timeline: [
      { when: "c. 4000 BCE", era: "BCE", title: "Sumer", description: "In Mesopotamia — 'the land between the rivers' — humanity builds its first cities." },
      { when: "c. 3200 BCE", era: "BCE", title: "Invention of writing", description: "Cuneiform on clay tablets begins recorded history." },
      { when: "c. 1792 BCE", era: "BCE", title: "Babylon of Hammurabi", description: "Hammurabi unifies Mesopotamia and issues his famous law code." },
      { when: "c. 700 BCE", era: "BCE", title: "Assyrian Empire", description: "Nineveh rules the Near East from the Tigris." },
      { when: "762 CE", era: "CE", title: "Baghdad founded", description: "The Abbasid capital becomes the centre of a golden age of science and learning." },
      { when: "1258 CE", era: "CE", title: "Mongol sack of Baghdad", description: "The city falls to the Mongols, ending the Abbasid caliphate." },
      { when: "1932 CE", era: "CE", title: "Modern Iraq", description: "The Kingdom of Iraq gains independence from British mandate." },
    ],
  },
  IRN: {
    destinations: [
      { name: "Persepolis", blurb: "The ceremonial capital of the Achaemenid Persian Empire, burned by Alexander in 330 BCE." },
      { name: "Isfahan", blurb: "'Half the world', famed for its blue-tiled mosques and grand Naqsh-e Jahan Square." },
      { name: "Yazd", blurb: "A desert city of wind-catchers and Zoroastrian fire temples." },
    ],
    inventions: [
      { name: "The qanat", blurb: "Underground aqueducts that made desert agriculture possible for millennia." },
      { name: "Algebra's roots & the postal system", blurb: "Persia advanced mathematics, and the Achaemenids ran an imperial courier road." },
      { name: "Windmills", blurb: "Vertical-axis windmills were used in eastern Persia by the 9th century." },
    ],
    foods: [
      { name: "Chelo kabab", blurb: "Iran's national dish: saffron rice with grilled kebab." },
      { name: "Ghormeh sabzi", blurb: "A herb, bean and lamb stew, deeply aromatic." },
    ],
    festivals: [
      { name: "Nowruz", blurb: "The 3,000-year-old Persian New Year at the spring equinox.", when: "21 March" },
      { name: "Yalda Night", blurb: "The winter solstice celebrated with poetry, pomegranates and family.", when: "December" },
    ],
    timeline: [
      { when: "550 BCE", era: "BCE", title: "Achaemenid Empire", description: "Cyrus the Great founds the first Persian Empire, the largest the world had yet seen." },
      { when: "330 BCE", era: "BCE", title: "Alexander's conquest", description: "Alexander the Great overthrows Darius III and burns Persepolis." },
      { when: "224 CE", era: "CE", title: "Sasanian Empire", description: "A revived Persian empire rivals Rome for four centuries." },
      { when: "651 CE", era: "CE", title: "Islamic conquest", description: "Arab armies end the Sasanian empire; Persia becomes Muslim." },
      { when: "1979 CE", era: "CE", title: "Islamic Revolution", description: "The monarchy is overthrown and an Islamic republic is founded." },
    ],
  },
  TUR: {
    hero: "Hagia Sophia Mars 2013.jpg",
    destinations: [
      { name: "Hagia Sophia", blurb: "A 6th-century Byzantine cathedral turned mosque, museum and mosque again, in Istanbul.", image: "Hagia Sophia Mars 2013.jpg" },
      { name: "Cappadocia", blurb: "Fairy-chimney rock formations, cave churches and dawn hot-air balloons." },
      { name: "Ephesus", blurb: "One of the best-preserved classical cities, with the Library of Celsus." },
      { name: "Pamukkale", blurb: "Cascading white travertine terraces of mineral springs." },
    ],
    inventions: [
      { name: "Göbekli Tepe", blurb: "The world's oldest known monumental temple predates agriculture.", year: "c. 9500 BCE" },
      { name: "Coinage (nearby Lydia)", blurb: "Some of the first stamped coins were minted in ancient Anatolia.", year: "c. 600 BCE" },
    ],
    foods: [
      { name: "Kebab", blurb: "Grilled and skewered meats in countless regional forms." },
      { name: "Baklava", blurb: "Layered filo pastry with nuts and syrup." },
      { name: "Meze", blurb: "An array of small cold and hot appetisers." },
    ],
    festivals: [
      { name: "Mevlana (Whirling Dervishes)", blurb: "Sufi commemoration in Konya with the famous whirling ceremony.", when: "December" },
    ],
    timeline: [
      { when: "c. 9500 BCE", era: "BCE", title: "Göbekli Tepe", description: "Hunter-gatherers in Anatolia build the earliest known temple." },
      { when: "c. 1650 BCE", era: "BCE", title: "Hittite Empire", description: "A great Bronze Age power rules Anatolia from Hattusa." },
      { when: "330 CE", era: "CE", title: "Constantinople", description: "Constantine makes Byzantium the capital of the Roman/Byzantine Empire." },
      { when: "1453 CE", era: "CE", title: "Ottoman conquest", description: "Mehmed II takes Constantinople, and the Ottoman Empire rises." },
      { when: "1923 CE", era: "CE", title: "Republic of Turkey", description: "Atatürk founds a secular modern republic." },
    ],
  },
  THA: {
    hero: "Wat Arun Bangkok.jpg",
    destinations: [
      { name: "Grand Palace & Wat Arun", blurb: "Bangkok's dazzling royal complex and the riverside Temple of Dawn." },
      { name: "Ayutthaya", blurb: "The ruined former capital, a UNESCO site of temple spires and Buddha heads." },
      { name: "Phuket & the Andaman coast", blurb: "Turquoise seas, limestone karsts and island beaches." },
    ],
    inventions: [
      { name: "Muay Thai", blurb: "The martial art of 'eight limbs', a national sport and global discipline." },
    ],
    foods: [
      { name: "Pad thai", blurb: "Stir-fried rice noodles with tamarind, peanuts and lime." },
      { name: "Tom yum goong", blurb: "Hot-and-sour prawn soup with lemongrass and chilli." },
      { name: "Green curry", blurb: "Coconut curry with green chilli paste and Thai basil." },
    ],
    festivals: [
      { name: "Songkran", blurb: "The Thai New Year, celebrated with nationwide water fights.", when: "13–15 April" },
      { name: "Loy Krathong", blurb: "Floating lotus-shaped offerings and sky lanterns on rivers.", when: "November" },
    ],
    timeline: [
      { when: "1238 CE", era: "CE", title: "Sukhothai Kingdom", description: "The first Thai kingdom emerges; the Thai alphabet is created." },
      { when: "1350 CE", era: "CE", title: "Ayutthaya", description: "A powerful, cosmopolitan kingdom trades across Asia for four centuries." },
      { when: "1782 CE", era: "CE", title: "Bangkok & the Chakri dynasty", description: "The current royal dynasty founds Bangkok as capital." },
      { when: "1932 CE", era: "CE", title: "Constitutional monarchy", description: "A revolution ends absolute monarchy." },
    ],
  },
  KHM: {
    hero: "Angkor Wat.jpg",
    destinations: [
      { name: "Angkor Wat", blurb: "The largest religious monument on Earth, the 12th-century temple-city of the Khmer Empire.", image: "Angkor Wat.jpg" },
      { name: "Bayon", blurb: "A temple of enigmatic giant stone faces at Angkor Thom." },
      { name: "Phnom Penh", blurb: "The riverside capital with its Royal Palace and Silver Pagoda." },
    ],
    foods: [
      { name: "Fish amok", blurb: "A mousse-like coconut fish curry steamed in banana leaf." },
      { name: "Nom banh chok", blurb: "Rice noodles with a green fish gravy, eaten for breakfast." },
    ],
    festivals: [
      { name: "Water Festival (Bon Om Touk)", blurb: "Boat races on the Tonlé Sap celebrating the river's reversal.", when: "November" },
    ],
    timeline: [
      { when: "802 CE", era: "CE", title: "Khmer Empire", description: "Jayavarman II founds an empire that dominates mainland Southeast Asia." },
      { when: "1113 CE", era: "CE", title: "Angkor Wat built", description: "Suryavarman II raises the great temple to Vishnu." },
      { when: "1975 CE", era: "CE", title: "Khmer Rouge", description: "A brutal regime causes the deaths of some two million people before its fall in 1979." },
    ],
  },
  IDN: {
    destinations: [
      { name: "Borobudur", blurb: "The world's largest Buddhist temple, a 9th-century stone mandala in Java." },
      { name: "Bali", blurb: "The 'Island of the Gods', with rice terraces, temples and surf." },
      { name: "Komodo National Park", blurb: "Home of the Komodo dragon, the largest living lizard." },
    ],
    inventions: [
      { name: "Batik", blurb: "The wax-resist textile dyeing art, recognised by UNESCO." },
    ],
    foods: [
      { name: "Nasi goreng", blurb: "Indonesia's beloved fried rice, often topped with a fried egg." },
      { name: "Rendang", blurb: "Slow-cooked spiced beef, frequently voted among the world's tastiest dishes." },
      { name: "Satay", blurb: "Grilled meat skewers with peanut sauce." },
    ],
    festivals: [
      { name: "Nyepi", blurb: "Bali's Day of Silence, when the whole island stops for reflection.", when: "March" },
    ],
    timeline: [
      { when: "c. 800 CE", era: "CE", title: "Borobudur & Srivijaya", description: "Buddhist and Hindu kingdoms build great monuments and trade across the seas." },
      { when: "1293 CE", era: "CE", title: "Majapahit Empire", description: "A powerful Hindu-Buddhist maritime empire dominates the archipelago." },
      { when: "1945 CE", era: "CE", title: "Independence", description: "Indonesia declares independence from the Dutch after WWII." },
    ],
  },
  VNM: {
    destinations: [
      { name: "Ha Long Bay", blurb: "Thousands of limestone islets rising from emerald waters." },
      { name: "Hội An", blurb: "A lantern-lit former trading port with preserved old town." },
      { name: "Hanoi & the Old Quarter", blurb: "The capital's tangle of ancient streets, lakes and French colonial architecture." },
    ],
    foods: [
      { name: "Phở", blurb: "Aromatic beef or chicken noodle soup, Vietnam's national dish." },
      { name: "Bánh mì", blurb: "A crisp baguette sandwich blending French and Vietnamese flavours." },
    ],
    festivals: [
      { name: "Tết", blurb: "The Vietnamese Lunar New Year, the biggest holiday of the year.", when: "Jan–Feb" },
    ],
    timeline: [
      { when: "111 BCE", era: "BCE", title: "Chinese rule begins", description: "Han China annexes northern Vietnam for a millennium of influence." },
      { when: "938 CE", era: "CE", title: "Independence", description: "Ngô Quyền defeats the Chinese fleet at Bạch Đằng, winning independence." },
      { when: "1975 CE", era: "CE", title: "Reunification", description: "The Vietnam War ends and the country is reunified." },
    ],
  },
  KOR: {
    destinations: [
      { name: "Gyeongbokgung, Seoul", blurb: "The grand Joseon-dynasty royal palace with changing-of-guard ceremonies." },
      { name: "Bulguksa & Seokguram", blurb: "Masterpieces of Silla Buddhist art near Gyeongju." },
      { name: "Jeju Island", blurb: "A volcanic island of craters, lava tubes and waterfalls." },
    ],
    inventions: [
      { name: "Movable metal type", blurb: "Korea printed with movable metal type decades before Gutenberg.", year: "1234" },
      { name: "Hangul alphabet", blurb: "King Sejong created a uniquely scientific writing system.", year: "1443" },
      { name: "The turtle ship", blurb: "Admiral Yi Sun-sin's ironclad warships helped repel invasion.", year: "1590s" },
    ],
    foods: [
      { name: "Kimchi", blurb: "Fermented, spiced napa cabbage, served at nearly every meal." },
      { name: "Bibimbap", blurb: "A bowl of rice topped with vegetables, egg and gochujang." },
      { name: "Korean BBQ", blurb: "Grill-at-the-table meats wrapped in lettuce." },
    ],
    festivals: [
      { name: "Chuseok", blurb: "The autumn harvest thanksgiving, honouring ancestors.", when: "Autumn" },
    ],
    timeline: [
      { when: "57 BCE", era: "BCE", title: "Three Kingdoms", description: "Goguryeo, Baekje and Silla vie for the peninsula." },
      { when: "668 CE", era: "CE", title: "Unified Silla", description: "Silla unifies most of Korea and Buddhism flourishes." },
      { when: "1392 CE", era: "CE", title: "Joseon dynasty", description: "A Confucian dynasty rules for five centuries." },
      { when: "1948 CE", era: "CE", title: "Republic of Korea", description: "After division, South Korea is established and later becomes an economic powerhouse." },
    ],
  },
  ISR: {
    destinations: [
      { name: "Jerusalem's Old City", blurb: "Sacred to Judaism, Christianity and Islam, with the Western Wall and Dome of the Rock." },
      { name: "Dead Sea", blurb: "The lowest point on Earth's land surface, so salty you float." },
      { name: "Masada", blurb: "A desert fortress where Jewish rebels made a famous last stand against Rome." },
    ],
    inventions: [
      { name: "Drip irrigation", blurb: "Netafim's system transformed farming in arid lands.", year: "1960s" },
      { name: "USB flash drive & instant messaging", blurb: "Israeli engineers pioneered portable storage and ICQ chat." },
    ],
    foods: [
      { name: "Hummus & falafel", blurb: "Chickpea staples central to the national table." },
      { name: "Shakshuka", blurb: "Eggs poached in a spiced tomato-pepper sauce." },
    ],
    festivals: [
      { name: "Passover", blurb: "The spring festival commemorating the Exodus from Egypt.", when: "Spring" },
    ],
    timeline: [
      { when: "c. 1000 BCE", era: "BCE", title: "Kingdom of Israel", description: "According to tradition, David and Solomon rule from Jerusalem." },
      { when: "70 CE", era: "CE", title: "Destruction of the Temple", description: "Rome sacks Jerusalem, beginning the long Jewish diaspora." },
      { when: "1948 CE", era: "CE", title: "State of Israel", description: "The modern State of Israel is established." },
    ],
  },
  SAU: {
    destinations: [
      { name: "Mecca", blurb: "Islam's holiest city, destination of the Hajj pilgrimage (open to Muslims)." },
      { name: "Hegra (Mada'in Salih)", blurb: "Nabataean rock-cut tombs, Saudi Arabia's first UNESCO site." },
      { name: "Diriyah & Riyadh", blurb: "The mud-brick birthplace of the Saudi state beside the modern capital." },
    ],
    foods: [
      { name: "Kabsa", blurb: "The national dish: spiced rice with meat, often lamb or chicken." },
      { name: "Dates & Arabic coffee", blurb: "The traditional gesture of hospitality." },
    ],
    festivals: [
      { name: "Hajj", blurb: "The annual pilgrimage to Mecca, one of Islam's five pillars.", when: "Dhu al-Hijjah" },
    ],
    timeline: [
      { when: "570 CE", era: "CE", title: "Birth of the Prophet Muhammad", description: "The founder of Islam is born in Mecca." },
      { when: "622 CE", era: "CE", title: "The Hijra", description: "Muhammad's migration to Medina marks year one of the Islamic calendar." },
      { when: "1932 CE", era: "CE", title: "Kingdom founded", description: "Ibn Saud unifies the peninsula into the Kingdom of Saudi Arabia." },
    ],
  },
  ARE: {
    destinations: [
      { name: "Burj Khalifa", blurb: "The world's tallest building at 828 m, soaring over Dubai.", image: "Burj Khalifa.jpg" },
      { name: "Sheikh Zayed Grand Mosque", blurb: "A gleaming white marble mosque in Abu Dhabi holding tens of thousands." },
      { name: "Louvre Abu Dhabi", blurb: "A domed art museum designed by Jean Nouvel on Saadiyat Island." },
    ],
    foods: [
      { name: "Al harees", blurb: "A slow-cooked wheat-and-meat porridge for celebrations." },
      { name: "Shawarma", blurb: "Spit-roasted meat in flatbread, a street favourite." },
    ],
    festivals: [
      { name: "Eid al-Fitr", blurb: "Marking the end of Ramadan with feasts and fireworks.", when: "After Ramadan" },
    ],
    timeline: [
      { when: "1971 CE", era: "CE", title: "Federation formed", description: "Seven emirates unite to form the United Arab Emirates." },
      { when: "2010 CE", era: "CE", title: "Burj Khalifa opens", description: "Dubai completes the tallest structure ever built." },
    ],
  },
  NPL: {
    destinations: [
      { name: "Mount Everest", blurb: "Earth's highest peak at 8,849 m, on the Nepal–China border." },
      { name: "Kathmandu Valley", blurb: "Seven UNESCO monument zones of Hindu and Buddhist temples." },
      { name: "Lumbini", blurb: "The birthplace of the Buddha." },
    ],
    foods: [
      { name: "Dal bhat", blurb: "Lentil soup with rice, the everyday meal that fuels Himalayan trekkers." },
      { name: "Momo", blurb: "Steamed dumplings adopted from Tibet." },
    ],
    festivals: [
      { name: "Dashain", blurb: "The longest and most important Hindu festival in Nepal.", when: "Autumn" },
    ],
    timeline: [
      { when: "c. 563 BCE", era: "BCE", title: "Birth of the Buddha", description: "Siddhartha Gautama is born at Lumbini." },
      { when: "1768 CE", era: "CE", title: "Unification", description: "Prithvi Narayan Shah unifies Nepal into a kingdom." },
      { when: "2008 CE", era: "CE", title: "Federal republic", description: "Nepal abolishes its monarchy and becomes a republic." },
    ],
  },

  /* ── AFRICA ────────────────────────────────────────────────────────────── */
  EGY: {
    hero: "Kheops-Pyramid.jpg",
    destinations: [
      { name: "Pyramids of Giza & the Sphinx", blurb: "The last surviving wonder of the ancient world, built c. 2560 BCE.", image: "Kheops-Pyramid.jpg" },
      { name: "Karnak & Luxor", blurb: "Vast temple complexes of ancient Thebes on the Nile." },
      { name: "Valley of the Kings", blurb: "Rock-cut royal tombs including Tutankhamun's." },
      { name: "Abu Simbel", blurb: "Ramesses II's colossal rock temples, relocated to escape Lake Nasser." },
    ],
    inventions: [
      { name: "Papyrus & the 365-day calendar", blurb: "Egyptians created paper-like writing material and a solar calendar." },
      { name: "Monumental stone architecture", blurb: "The pyramids pioneered large-scale engineering and geometry." },
      { name: "Advanced medicine", blurb: "Papyri record surgery, dentistry and pharmacology." },
    ],
    foods: [
      { name: "Koshari", blurb: "Egypt's national street dish of rice, lentils, pasta and spiced tomato." },
      { name: "Ful medames", blurb: "Stewed fava beans, an ancient breakfast staple." },
    ],
    festivals: [
      { name: "Abu Simbel Sun Festival", blurb: "Twice a year the sun illuminates the inner sanctuary of Ramesses II.", when: "22 Feb & 22 Oct" },
    ],
    timeline: [
      { when: "c. 3100 BCE", era: "BCE", title: "Unification of Egypt", description: "Narmer unites Upper and Lower Egypt, founding the first dynasty." },
      { when: "c. 2560 BCE", era: "BCE", title: "Great Pyramid", description: "Khufu's pyramid rises at Giza, the tallest structure for 3,800 years." },
      { when: "c. 1332 BCE", era: "BCE", title: "Tutankhamun", description: "The boy-king reigns; his intact tomb is found in 1922." },
      { when: "332 BCE", era: "BCE", title: "Alexander & the Ptolemies", description: "Alexander founds Alexandria; a Greek dynasty rules, ending with Cleopatra." },
      { when: "641 CE", era: "CE", title: "Arab conquest", description: "Egypt becomes part of the Islamic world; Cairo is founded in 969." },
      { when: "1922 CE", era: "CE", title: "Modern independence", description: "Egypt gains independence from Britain." },
    ],
  },
  MAR: {
    hero: "Marrakech - Jemaa el Fna.jpg",
    destinations: [
      { name: "Marrakech medina", blurb: "The 'Red City' with its labyrinthine souks and the Jemaa el-Fnaa square.", image: "Marrakech - Jemaa el Fna.jpg" },
      { name: "Fes el Bali", blurb: "The world's largest car-free urban area and oldest university." },
      { name: "Sahara at Merzouga", blurb: "Golden dunes reached by camel from desert kasbahs." },
      { name: "Chefchaouen", blurb: "A mountain town washed entirely in shades of blue." },
    ],
    foods: [
      { name: "Tagine", blurb: "Slow-cooked stew named for its conical clay pot." },
      { name: "Couscous", blurb: "Steamed semolina with vegetables and meat, the Friday dish." },
      { name: "Mint tea", blurb: "Sweet green tea poured from a height, the drink of hospitality." },
    ],
    festivals: [
      { name: "Fes Festival of World Sacred Music", blurb: "An international gathering of spiritual music.", when: "June" },
    ],
    timeline: [
      { when: "c. 1100 BCE", era: "BCE", title: "Phoenician trading posts", description: "Phoenicians settle the Atlantic and Mediterranean coasts." },
      { when: "788 CE", era: "CE", title: "Idrisid dynasty", description: "The first Moroccan Muslim state is founded; Fes becomes a center of learning." },
      { when: "1062 CE", era: "CE", title: "Almoravids", description: "A Berber empire founds Marrakech and rules from Spain to Senegal." },
      { when: "1956 CE", era: "CE", title: "Independence", description: "Morocco regains independence from France and Spain." },
    ],
  },
  ZAF: {
    hero: "Table Mountain DanieVDM.jpg",
    destinations: [
      { name: "Table Mountain & Cape Town", blurb: "A flat-topped massif above one of the world's most scenic cities.", image: "Table Mountain DanieVDM.jpg" },
      { name: "Kruger National Park", blurb: "A vast reserve where the Big Five roam." },
      { name: "Robben Island", blurb: "The prison island where Nelson Mandela was held for 18 years." },
      { name: "The Garden Route", blurb: "A coastal drive of forests, lagoons and beaches." },
    ],
    inventions: [
      { name: "The CAT scan (co-developed)", blurb: "Allan Cormack shared the Nobel for computed tomography." },
      { name: "First human heart transplant", blurb: "Christiaan Barnard performed it in Cape Town.", year: "1967" },
    ],
    foods: [
      { name: "Braai", blurb: "The South African barbecue, a national social ritual." },
      { name: "Bobotie", blurb: "Spiced minced meat baked under an egg custard." },
      { name: "Biltong", blurb: "Air-dried, cured meat, a beloved snack." },
    ],
    festivals: [
      { name: "Cape Town Minstrel Carnival", blurb: "A vibrant New Year street parade with music and costume.", when: "January" },
    ],
    timeline: [
      { when: "c. 100,000 BCE", era: "BCE", title: "Early modern humans", description: "Some of the earliest evidence of Homo sapiens comes from South African caves." },
      { when: "1652 CE", era: "CE", title: "Cape colony", description: "The Dutch establish a supply station at the Cape." },
      { when: "1910 CE", era: "CE", title: "Union of South Africa", description: "British colonies and Boer republics unite." },
      { when: "1994 CE", era: "CE", title: "End of apartheid", description: "Nelson Mandela is elected in the first fully democratic election." },
    ],
  },
  KEN: {
    destinations: [
      { name: "Maasai Mara", blurb: "The stage for the Great Migration of wildebeest and zebra." },
      { name: "Mount Kenya", blurb: "Africa's second-highest peak, glaciated on the equator." },
      { name: "Diani & the Swahili Coast", blurb: "White-sand Indian Ocean beaches and coral reefs." },
    ],
    foods: [
      { name: "Nyama choma", blurb: "Roasted meat, the centerpiece of social gatherings." },
      { name: "Ugali", blurb: "A stiff maize porridge eaten with stews and greens." },
    ],
    festivals: [
      { name: "Lamu Cultural Festival", blurb: "Swahili dhow races, poetry and crafts on Lamu Island.", when: "November" },
    ],
    timeline: [
      { when: "c. 3.3 million BCE", era: "BCE", title: "Cradle of humankind", description: "The Turkana Basin holds some of the oldest human ancestor fossils and stone tools." },
      { when: "c. 800 CE", era: "CE", title: "Swahili city-states", description: "Coastal trading cities link Africa to Arabia, India and China." },
      { when: "1963 CE", era: "CE", title: "Independence", description: "Kenya gains independence from Britain under Jomo Kenyatta." },
    ],
  },
  TZA: {
    destinations: [
      { name: "Mount Kilimanjaro", blurb: "Africa's highest peak at 5,895 m, a free-standing snow-capped volcano." },
      { name: "Serengeti", blurb: "Endless plains hosting the world's greatest wildlife migration." },
      { name: "Zanzibar", blurb: "A spice island with Stone Town's Swahili-Arab heritage and turquoise seas." },
    ],
    foods: [
      { name: "Ugali & nyama", blurb: "Maize porridge with grilled or stewed meat." },
      { name: "Zanzibar pilau & biryani", blurb: "Spiced rice dishes reflecting Indian Ocean trade." },
    ],
    festivals: [
      { name: "Sauti za Busara", blurb: "A major pan-African music festival in Zanzibar.", when: "February" },
    ],
    timeline: [
      { when: "c. 1.8 million BCE", era: "BCE", title: "Olduvai Gorge", description: "Early hominins leave tools and footprints in the Rift Valley." },
      { when: "c. 1000 CE", era: "CE", title: "Kilwa & the gold trade", description: "Swahili Kilwa becomes a wealthy Indian Ocean trading power." },
      { when: "1964 CE", era: "CE", title: "Union of Tanzania", description: "Tanganyika and Zanzibar unite to form Tanzania." },
    ],
  },
  ETH: {
    destinations: [
      { name: "Rock-hewn churches of Lalibela", blurb: "Eleven medieval churches carved down into the rock, a place of pilgrimage." },
      { name: "Simien Mountains", blurb: "Dramatic escarpments home to gelada baboons and walia ibex." },
      { name: "Danakil Depression", blurb: "One of the hottest, lowest and most alien landscapes on Earth." },
    ],
    inventions: [
      { name: "Coffee", blurb: "Coffee originates in the Ethiopian highlands, per the legend of Kaldi." },
    ],
    foods: [
      { name: "Injera with wot", blurb: "A spongy sourdough flatbread served with spiced stews." },
      { name: "Coffee ceremony", blurb: "Beans roasted, ground and brewed as a social ritual." },
    ],
    festivals: [
      { name: "Timkat", blurb: "Ethiopian Orthodox Epiphany, with colourful processions and blessings of water.", when: "January" },
    ],
    timeline: [
      { when: "c. 3.2 million BCE", era: "BCE", title: "'Lucy'", description: "The famous Australopithecus fossil is found in the Afar region." },
      { when: "c. 100 CE", era: "CE", title: "Kingdom of Aksum", description: "A powerful trading empire mints its own coins and adopts Christianity early." },
      { when: "1896 CE", era: "CE", title: "Battle of Adwa", description: "Ethiopia defeats Italy, remaining uncolonised — a symbol for Africa." },
    ],
  },
  NGA: {
    destinations: [
      { name: "Lagos", blurb: "Africa's largest city, a booming hub of business, music and film (Nollywood)." },
      { name: "Zuma Rock", blurb: "A monolith near Abuja, a national landmark." },
      { name: "Osun-Osogbo Sacred Grove", blurb: "A forest sanctuary of Yoruba deities and shrines." },
    ],
    foods: [
      { name: "Jollof rice", blurb: "Tomato-and-pepper rice at the center of a friendly West African rivalry." },
      { name: "Egusi soup", blurb: "A melon-seed stew eaten with pounded yam." },
    ],
    festivals: [
      { name: "Eyo & Durbar festivals", blurb: "Masquerade parades and horseback pageantry across the country." },
    ],
    timeline: [
      { when: "c. 500 BCE", era: "BCE", title: "Nok culture", description: "West Africa's earliest known culture produces remarkable terracotta sculpture." },
      { when: "c. 1100 CE", era: "CE", title: "Ife & Benin", description: "The Yoruba and Edo kingdoms create bronze and brass masterpieces." },
      { when: "1960 CE", era: "CE", title: "Independence", description: "Nigeria gains independence from Britain." },
    ],
  },
  GHA: {
    destinations: [
      { name: "Cape Coast Castle", blurb: "A sobering slave-trade fortress and UNESCO memorial site." },
      { name: "Kakum National Park", blurb: "Rainforest explored via a canopy walkway." },
    ],
    foods: [
      { name: "Fufu with light soup", blurb: "Pounded cassava and plantain dipped in a spiced broth." },
      { name: "Jollof rice", blurb: "Ghana's proud entry in the West African jollof debate." },
    ],
    festivals: [
      { name: "Homowo", blurb: "A Ga harvest festival 'hooting at hunger' with feasting.", when: "August" },
    ],
    timeline: [
      { when: "c. 300 CE", era: "CE", title: "Ghana Empire (to the north)", description: "The medieval Ghana Empire, from which the country takes its name, grows rich on gold." },
      { when: "1400s–1500s CE", era: "CE", title: "Ashanti & the gold coast", description: "The Ashanti kingdom rises; Europeans build coastal forts." },
      { when: "1957 CE", era: "CE", title: "First to independence", description: "Ghana becomes the first sub-Saharan colony to gain independence." },
    ],
  },
  MLI: {
    destinations: [
      { name: "Djenné's Great Mosque", blurb: "The largest mud-brick building in the world, re-plastered each year." },
      { name: "Timbuktu", blurb: "A fabled desert city of ancient manuscripts and Islamic scholarship." },
    ],
    foods: [
      { name: "Tô with sauce", blurb: "A millet or sorghum paste eaten with leaf sauces." },
    ],
    festivals: [
      { name: "Festival au Désert (historic)", blurb: "A celebrated Tuareg music festival near Timbuktu." },
    ],
    timeline: [
      { when: "1235 CE", era: "CE", title: "Mali Empire", description: "Sundiata Keita founds an empire that becomes one of the world's richest." },
      { when: "1324 CE", era: "CE", title: "Mansa Musa's pilgrimage", description: "The emperor's gold-laden hajj makes Mali legendary; Timbuktu becomes a center of learning." },
      { when: "1960 CE", era: "CE", title: "Independence", description: "Mali gains independence from France." },
    ],
  },

  /* ── AMERICAS ──────────────────────────────────────────────────────────── */
  USA: {
    hero: "Grand Canyon view from Pima Point 2010.jpg",
    destinations: [
      { name: "Grand Canyon", blurb: "A mile-deep chasm carved by the Colorado River over millions of years.", image: "Grand Canyon view from Pima Point 2010.jpg" },
      { name: "Statue of Liberty & New York City", blurb: "The gift from France welcoming immigrants, beside the world capital of finance and culture." },
      { name: "Yellowstone", blurb: "The first national park, with geysers, hot springs and roaming bison." },
      { name: "Walt Disney World & the theme parks", blurb: "The world's most visited resort, in Florida." },
    ],
    inventions: [
      { name: "The light bulb & phonograph", blurb: "Edison's lab industrialised invention itself.", year: "1879" },
      { name: "Powered flight", blurb: "The Wright brothers achieved the first controlled aeroplane flight.", year: "1903" },
      { name: "The internet & transistor", blurb: "US labs and universities created the transistor and the ARPANET that became the internet." },
      { name: "The Moon landing", blurb: "Apollo 11 put the first humans on the Moon.", year: "1969" },
    ],
    foods: [
      { name: "Hamburger", blurb: "The quintessential American sandwich, globalised by diners and chains." },
      { name: "Barbecue", blurb: "Slow-smoked regional styles from Texas brisket to Carolina pork." },
      { name: "Apple pie", blurb: "The dessert synonymous with American identity." },
    ],
    festivals: [
      { name: "Independence Day", blurb: "Fireworks, parades and cookouts marking the 1776 Declaration.", when: "4 July" },
      { name: "Thanksgiving", blurb: "A national harvest feast centered on turkey.", when: "November" },
    ],
    timeline: [
      { when: "c. 13,000 BCE", era: "BCE", title: "First peoples", description: "Ancestors of Native Americans populate the continent." },
      { when: "1492 CE", era: "CE", title: "European contact", description: "Columbus reaches the Americas, beginning colonisation." },
      { when: "1776 CE", era: "CE", title: "Declaration of Independence", description: "Thirteen colonies declare independence from Britain." },
      { when: "1861–1865 CE", era: "CE", title: "Civil War", description: "The Union prevails and slavery is abolished." },
      { when: "1969 CE", era: "CE", title: "Apollo 11", description: "The United States lands the first humans on the Moon." },
    ],
  },
  MEX: {
    hero: "Chichen Itza 3.jpg",
    destinations: [
      { name: "Chichén Itzá", blurb: "The Maya-Toltec city crowned by the pyramid of Kukulcán.", image: "Chichen Itza 3.jpg" },
      { name: "Teotihuacan", blurb: "The vast ancient city of the Pyramids of the Sun and Moon near Mexico City." },
      { name: "Cancún & the Riviera Maya", blurb: "Caribbean beaches, cenotes and coral reefs." },
      { name: "Mexico City's historic center", blurb: "Built atop the Aztec capital Tenochtitlan, around the Zócalo." },
    ],
    inventions: [
      { name: "Chocolate", blurb: "Mesoamericans first cultivated cacao and drank chocolate." },
      { name: "The concept of zero (Maya)", blurb: "The Maya independently developed zero and a precise calendar." },
      { name: "Colour television (Guillermo González Camarena)", blurb: "A Mexican engineer patented an early colour TV system.", year: "1940" },
    ],
    foods: [
      { name: "Tacos", blurb: "Corn or wheat tortillas with endless fillings, Mexico's culinary ambassador." },
      { name: "Mole", blurb: "A complex sauce of chillies, spices and sometimes chocolate." },
      { name: "Guacamole & tamales", blurb: "Avocado dip and steamed corn-dough parcels of pre-Hispanic origin." },
    ],
    festivals: [
      { name: "Día de los Muertos", blurb: "The Day of the Dead, honouring ancestors with marigolds and altars — a UNESCO tradition.", when: "1–2 November" },
    ],
    timeline: [
      { when: "c. 1200 BCE", era: "BCE", title: "Olmec civilization", description: "Mesoamerica's 'mother culture' carves colossal stone heads." },
      { when: "c. 250 CE", era: "CE", title: "Classic Maya", description: "Maya city-states flourish in mathematics, astronomy and writing." },
      { when: "1325 CE", era: "CE", title: "Aztec Tenochtitlan", description: "The Mexica found their island capital, one of the world's largest cities." },
      { when: "1521 CE", era: "CE", title: "Spanish conquest", description: "Hernán Cortés and native allies topple the Aztec Empire." },
      { when: "1810 CE", era: "CE", title: "Independence", description: "The 'Grito de Dolores' begins the war for independence from Spain." },
    ],
  },
  BRA: {
    hero: "Cristo Redentor - Rio de Janeiro, Brasil.jpg",
    destinations: [
      { name: "Christ the Redeemer & Rio", blurb: "The 38 m Art-Deco statue over Rio de Janeiro's beaches and Sugarloaf.", image: "Cristo Redentor - Rio de Janeiro, Brasil.jpg" },
      { name: "Iguaçu Falls", blurb: "A thundering system of 275 waterfalls on the Argentine border." },
      { name: "Amazon rainforest", blurb: "The largest tropical forest on Earth, home to unmatched biodiversity." },
      { name: "Salvador & Pelourinho", blurb: "The Afro-Brazilian heart of the country, rich in music and colonial architecture." },
    ],
    inventions: [
      { name: "Aircraft pioneer Santos-Dumont", blurb: "Alberto Santos-Dumont flew the 14-bis, an early powered aeroplane.", year: "1906" },
      { name: "Ethanol biofuel economy", blurb: "Brazil pioneered large-scale sugarcane ethanol for cars." },
    ],
    foods: [
      { name: "Feijoada", blurb: "A hearty black-bean and pork stew, the national dish." },
      { name: "Pão de queijo", blurb: "Chewy cheese bread from Minas Gerais." },
      { name: "Churrasco", blurb: "Brazilian barbecue served rodízio-style." },
    ],
    festivals: [
      { name: "Rio Carnival", blurb: "The world's largest carnival, with samba-school parades in the Sambadrome.", when: "Feb–Mar" },
    ],
    timeline: [
      { when: "1500 CE", era: "CE", title: "Portuguese arrival", description: "Pedro Álvares Cabral claims Brazil for Portugal." },
      { when: "1822 CE", era: "CE", title: "Independence", description: "Dom Pedro I declares independence, founding the Empire of Brazil." },
      { when: "1888 CE", era: "CE", title: "Abolition of slavery", description: "Brazil is the last country in the Americas to abolish slavery." },
      { when: "1889 CE", era: "CE", title: "Republic", description: "The monarchy is overthrown and a republic proclaimed." },
    ],
  },
  PER: {
    hero: "Machu Picchu, Peru.jpg",
    destinations: [
      { name: "Machu Picchu", blurb: "The 15th-century Inca citadel on a cloud-forest ridge, rediscovered in 1911.", image: "Machu Picchu, Peru.jpg" },
      { name: "Cusco", blurb: "The Inca capital, blending Andean and Spanish colonial architecture." },
      { name: "Nazca Lines", blurb: "Giant geoglyphs etched into the desert, visible only from the air." },
      { name: "Lake Titicaca", blurb: "The highest navigable lake, with reed islands of the Uros people." },
    ],
    inventions: [
      { name: "Quipu", blurb: "The Inca knotted-cord system for recording data and accounts." },
      { name: "Freeze-drying (chuño)", blurb: "Andean peoples freeze-dried potatoes centuries ago." },
      { name: "Terrace farming", blurb: "Inca engineers built vast agricultural terraces and irrigation." },
    ],
    foods: [
      { name: "Ceviche", blurb: "Fresh fish cured in citrus with chilli and onion, the national dish." },
      { name: "Lomo saltado", blurb: "Stir-fried beef with a Chinese-Peruvian (chifa) twist." },
      { name: "Potatoes", blurb: "Peru is the potato's homeland, with thousands of native varieties." },
    ],
    festivals: [
      { name: "Inti Raymi", blurb: "The Inca festival of the sun, re-enacted in Cusco.", when: "24 June" },
    ],
    timeline: [
      { when: "c. 3000 BCE", era: "BCE", title: "Caral", description: "The Americas' oldest known city rises on the Peruvian coast." },
      { when: "c. 100 CE", era: "CE", title: "Moche & Nazca", description: "Coastal cultures create fine pottery and the Nazca Lines." },
      { when: "1438 CE", era: "CE", title: "Inca Empire", description: "The Inca build the largest empire in pre-Columbian America from Cusco." },
      { when: "1533 CE", era: "CE", title: "Spanish conquest", description: "Francisco Pizarro conquers the Inca Empire." },
      { when: "1821 CE", era: "CE", title: "Independence", description: "Peru declares independence from Spain." },
    ],
  },
  ARG: {
    destinations: [
      { name: "Buenos Aires", blurb: "The 'Paris of South America', birthplace of tango." },
      { name: "Perito Moreno Glacier", blurb: "A giant advancing glacier in Patagonia that calves into a lake." },
      { name: "Iguazú Falls", blurb: "The Argentine side of the great waterfall system." },
    ],
    inventions: [
      { name: "The ballpoint pen (Biró)", blurb: "László Bíró perfected the ballpoint while living in Argentina.", year: "1938" },
      { name: "Fingerprint identification", blurb: "Juan Vucetich created the first system of criminal fingerprinting." },
    ],
    foods: [
      { name: "Asado", blurb: "The Argentine barbecue, a weekend institution." },
      { name: "Empanadas", blurb: "Stuffed baked or fried pastries." },
      { name: "Dulce de leche", blurb: "Caramelised milk spread found in countless desserts." },
    ],
    festivals: [
      { name: "Tango Festival & World Cup", blurb: "Buenos Aires hosts the global championship of tango dance.", when: "August" },
    ],
    timeline: [
      { when: "1536 CE", era: "CE", title: "Buenos Aires founded", description: "Spanish settlers establish the port city (refounded 1580)." },
      { when: "1816 CE", era: "CE", title: "Independence", description: "The United Provinces declare independence from Spain." },
      { when: "1853 CE", era: "CE", title: "Constitution", description: "Argentina adopts its founding constitution." },
    ],
  },
  CAN: {
    hero: "Moraine Lake 17092005.jpg",
    destinations: [
      { name: "Banff & Lake Louise", blurb: "Turquoise glacial lakes beneath the Rocky Mountains.", image: "Moraine Lake 17092005.jpg" },
      { name: "Niagara Falls", blurb: "The famous horseshoe falls on the US border." },
      { name: "Old Québec", blurb: "A walled French-colonial city, the only one north of Mexico." },
    ],
    inventions: [
      { name: "Insulin", blurb: "Banting and Best isolated insulin, saving millions with diabetes.", year: "1921" },
      { name: "The telephone (Bell in Canada)", blurb: "Alexander Graham Bell conceived the telephone at Brantford, Ontario." },
      { name: "Basketball", blurb: "James Naismith, a Canadian, invented the game.", year: "1891" },
    ],
    foods: [
      { name: "Poutine", blurb: "Fries topped with cheese curds and gravy, born in Québec." },
      { name: "Maple syrup", blurb: "Canada produces most of the world's supply." },
    ],
    festivals: [
      { name: "Winterlude & Calgary Stampede", blurb: "A winter carnival in Ottawa and 'the greatest outdoor show on earth' in Calgary." },
    ],
    timeline: [
      { when: "c. 1000 CE", era: "CE", title: "Norse at L'Anse aux Meadows", description: "Vikings establish the first known European settlement in the Americas." },
      { when: "1608 CE", era: "CE", title: "New France", description: "Champlain founds Québec City." },
      { when: "1867 CE", era: "CE", title: "Confederation", description: "The Dominion of Canada is formed." },
    ],
  },
  CUB: {
    destinations: [
      { name: "Old Havana", blurb: "Colourful Spanish-colonial streets, vintage cars and live son music." },
      { name: "Viñales Valley", blurb: "Tobacco fields among dramatic limestone mogotes." },
      { name: "Trinidad", blurb: "A perfectly preserved colonial town near Caribbean beaches." },
    ],
    foods: [
      { name: "Ropa vieja", blurb: "Shredded beef stewed in tomato and peppers, the national dish." },
      { name: "Moros y cristianos", blurb: "Black beans and rice cooked together." },
    ],
    festivals: [
      { name: "Carnaval de Santiago", blurb: "Cuba's most vibrant carnival, with conga and comparsas.", when: "July" },
    ],
    timeline: [
      { when: "1492 CE", era: "CE", title: "Columbus lands", description: "Columbus claims Cuba for Spain." },
      { when: "1902 CE", era: "CE", title: "Independence", description: "Cuba becomes a republic after Spanish and US involvement." },
      { when: "1959 CE", era: "CE", title: "Cuban Revolution", description: "Fidel Castro's revolution overthrows the government." },
    ],
  },
  CHL: {
    destinations: [
      { name: "Torres del Paine", blurb: "Granite spires, glaciers and lakes in Patagonia." },
      { name: "Atacama Desert", blurb: "The driest place on Earth, with lunar landscapes and clear skies." },
      { name: "Easter Island (Rapa Nui)", blurb: "Remote Pacific island of the giant moai statues." },
    ],
    foods: [
      { name: "Empanada de pino", blurb: "Baked pastry filled with beef, onion, egg and olive." },
      { name: "Pastel de choclo", blurb: "A sweet-corn and meat pie." },
    ],
    festivals: [
      { name: "Fiestas Patrias", blurb: "Independence celebrations with cueca dancing and asados.", when: "18 September" },
    ],
    timeline: [
      { when: "c. 1400 CE", era: "CE", title: "Inca & Mapuche", description: "The Inca reach central Chile; the Mapuche resist in the south." },
      { when: "1818 CE", era: "CE", title: "Independence", description: "Chile declares independence from Spain." },
    ],
  },

  /* ── OCEANIA ───────────────────────────────────────────────────────────── */
  AUS: {
    hero: "Sydney Opera House Sails edit02.jpg",
    destinations: [
      { name: "Sydney Opera House & Harbour", blurb: "The sail-shaped icon on one of the world's great natural harbours.", image: "Sydney Opera House Sails edit02.jpg" },
      { name: "Great Barrier Reef", blurb: "The largest coral reef system on Earth, visible from space." },
      { name: "Uluru", blurb: "A vast sacred sandstone monolith in the Red Centre." },
      { name: "The Great Ocean Road", blurb: "A coastal drive past the Twelve Apostles sea stacks." },
    ],
    inventions: [
      { name: "Wi-Fi", blurb: "CSIRO scientists developed core wireless-LAN technology.", year: "1990s" },
      { name: "The cochlear implant", blurb: "The 'bionic ear' was developed in Melbourne." },
      { name: "Black-box flight recorder", blurb: "David Warren invented the aviation recorder.", year: "1958" },
    ],
    foods: [
      { name: "Meat pie", blurb: "A handheld pastry of minced meat and gravy." },
      { name: "Vegemite", blurb: "A dark, salty yeast spread beloved (and puzzling to visitors)." },
      { name: "Barbecue & lamingtons", blurb: "The backyard 'barbie' and sponge cakes in chocolate and coconut." },
    ],
    festivals: [
      { name: "Vivid Sydney", blurb: "A festival of light, music and ideas illuminating the harbour.", when: "May–June" },
    ],
    timeline: [
      { when: "c. 65,000 BCE", era: "BCE", title: "First Australians", description: "Aboriginal peoples arrive, sustaining the world's oldest continuous cultures." },
      { when: "1770 CE", era: "CE", title: "European charting", description: "James Cook charts the east coast for Britain." },
      { when: "1788 CE", era: "CE", title: "First Fleet", description: "The first British penal colony is established at Sydney Cove." },
      { when: "1901 CE", era: "CE", title: "Federation", description: "The colonies unite as the Commonwealth of Australia." },
    ],
  },
  NZL: {
    hero: "Mount Cook - Aoraki.jpg",
    destinations: [
      { name: "Fiordland & Milford Sound", blurb: "Sheer cliffs and waterfalls plunging into deep glacial fjords." },
      { name: "Rotorua", blurb: "Geothermal geysers, mud pools and living Māori culture." },
      { name: "Hobbiton", blurb: "The film set of the Shire in rolling Waikato farmland." },
    ],
    inventions: [
      { name: "Splitting the atom", blurb: "Ernest Rutherford, born in NZ, first split the atom." },
      { name: "The electric fence & jet boat", blurb: "Practical Kiwi inventions now used worldwide." },
    ],
    foods: [
      { name: "Hāngī", blurb: "A Māori feast cooked in an earth oven." },
      { name: "Pavlova", blurb: "A meringue dessert (also claimed by Australia) topped with cream and fruit." },
    ],
    festivals: [
      { name: "Matariki", blurb: "The Māori New Year, marked by the rising of the Pleiades — now a public holiday.", when: "June–July" },
    ],
    timeline: [
      { when: "c. 1300 CE", era: "CE", title: "Māori settlement", description: "Polynesian voyagers settle Aotearoa, the last major landmass humans reached." },
      { when: "1840 CE", era: "CE", title: "Treaty of Waitangi", description: "Māori chiefs and the British Crown sign the founding document." },
      { when: "1893 CE", era: "CE", title: "Women's suffrage", description: "New Zealand becomes the first country to give women the vote." },
    ],
  },
};

// ─────────────────────────────────────────────────────────────────────────────
// Continent-level history (BCE/CE), used on the country page's History section
// to place a nation within the broader story of its continent.
// ─────────────────────────────────────────────────────────────────────────────

export const CONTINENT_HISTORY: Record<string, TimelineItem[]> = {
  Africa: [
    { when: "c. 300,000 BCE", era: "BCE", title: "Origin of humankind", description: "Homo sapiens evolves in Africa, the cradle of humanity, before spreading worldwide." },
    { when: "c. 3100 BCE", era: "BCE", title: "Ancient Egypt", description: "One of the earliest civilizations rises along the Nile, building the pyramids." },
    { when: "c. 300–1600 CE", era: "CE", title: "Great African empires", description: "Aksum, Ghana, Mali, Songhai and Great Zimbabwe grow wealthy on gold, salt and trade." },
    { when: "1400s–1800s CE", era: "CE", title: "Slave trade & colonisation", description: "The transatlantic slave trade and later the 'Scramble for Africa' devastate the continent." },
    { when: "1950s–1990s CE", era: "CE", title: "Independence", description: "A wave of decolonisation sweeps Africa, ending with the fall of apartheid in 1994." },
  ],
  Americas: [
    { when: "c. 13,000 BCE", era: "BCE", title: "First peoples", description: "Humans migrate into the Americas, developing diverse cultures over millennia." },
    { when: "c. 1200 BCE – 1500 CE", era: "CE", title: "Great civilizations", description: "The Olmec, Maya, Aztec and Inca build cities, pyramids and empires." },
    { when: "1492 CE", era: "CE", title: "European contact", description: "Columbus's voyages begin conquest, colonisation and the Columbian Exchange." },
    { when: "1776–1826 CE", era: "CE", title: "Age of independence", description: "The United States, then Latin American nations, win independence." },
  ],
  Asia: [
    { when: "c. 3300 BCE", era: "BCE", title: "First cities", description: "Mesopotamia and the Indus Valley build humanity's earliest urban civilizations." },
    { when: "c. 1600 BCE", era: "BCE", title: "Chinese dynasties", description: "The Shang dynasty leaves China's earliest writing; empires follow for millennia." },
    { when: "6th–5th c. BCE", era: "BCE", title: "Great teachers", description: "The Buddha, Confucius and Laozi reshape Asian thought." },
    { when: "7th c. CE", era: "CE", title: "Rise of Islam", description: "Islam spreads rapidly across the Middle East and beyond." },
    { when: "1900s CE", era: "CE", title: "Modern nations", description: "Empires fall and independent Asian states rise, now home to most of humanity." },
  ],
  Europe: [
    { when: "c. 2000 BCE", era: "BCE", title: "Aegean civilizations", description: "Minoans and Mycenaeans lay the foundations of European culture." },
    { when: "8th c. BCE – 476 CE", era: "CE", title: "Greece & Rome", description: "Classical Greece invents democracy and philosophy; Rome builds a Mediterranean empire." },
    { when: "5th–15th c. CE", era: "CE", title: "The Middle Ages", description: "Christian kingdoms, feudalism and later the Renaissance transform Europe." },
    { when: "1500s–1900s CE", era: "CE", title: "Empires & revolutions", description: "Exploration, the Enlightenment, industrialisation and two world wars remake the continent." },
    { when: "1993 CE", era: "CE", title: "European Union", description: "Integration binds former rivals into a single market and community." },
  ],
  Oceania: [
    { when: "c. 65,000 BCE", era: "BCE", title: "First Australians", description: "Aboriginal Australians establish the world's oldest continuous living cultures." },
    { when: "c. 1500 BCE – 1300 CE", era: "CE", title: "Pacific voyaging", description: "Austronesian navigators settle the vast Pacific, reaching New Zealand last." },
    { when: "1600s–1800s CE", era: "CE", title: "European exploration", description: "Dutch and British explorers chart the region; colonisation follows." },
    { when: "1900s CE", era: "CE", title: "Independent nations", description: "Pacific states gain independence through the 20th century." },
  ],
  Antarctic: [
    { when: "1820 CE", era: "CE", title: "First sighting", description: "Antarctica is first sighted by Russian, British and American expeditions." },
    { when: "1911 CE", era: "CE", title: "South Pole reached", description: "Roald Amundsen's team is the first to reach the geographic South Pole." },
    { when: "1959 CE", era: "CE", title: "Antarctic Treaty", description: "Nations agree to reserve the continent for peaceful, scientific use." },
  ],
};

export function knowledgeFor(cca3: string): CountryKnowledge {
  return KNOWLEDGE[cca3] ?? {};
}
