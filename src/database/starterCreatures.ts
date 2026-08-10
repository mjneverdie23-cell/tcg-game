import type { CreatureRecord } from './types';

/**
 * Built-in starter roster: the game is fully playable offline out of the box.
 * When `npm run scrape` produces creatures.json, the scraped roster (with
 * art) replaces this one — see src/database/index.ts. Until then card art
 * renders the class-emblem fallback.
 */
const c = (
  id: string,
  name: string,
  dinoClass: CreatureRecord['class'],
  rarity: CreatureRecord['rarity'],
  description: string,
): CreatureRecord => ({
  id,
  name,
  class: dinoClass,
  rarity,
  generation: 1,
  evolutionTier: 1,
  description,
  image: '',
});

export const STARTER_CREATURES: readonly CreatureRecord[] = [
  // ─── Carnivores ───────────────────────────────────────────────
  c('velociraptor', 'Velociraptor', 'carnivore', 'common', 'A cunning pack hunter with a lethal sickle claw on each foot.'),
  c('dilophosaurus', 'Dilophosaurus', 'carnivore', 'common', 'A crested Jurassic predator, fast and unpredictable.'),
  c('ceratosaurus', 'Ceratosaurus', 'carnivore', 'common', 'A horned carnivore that ambushes prey near riverbanks.'),
  c('herrerasaurus', 'Herrerasaurus', 'carnivore', 'common', 'One of the earliest dinosaurs — a Triassic pioneer of the hunt.'),
  c('ornitholestes', 'Ornitholestes', 'carnivore', 'common', 'A small, nimble thief that snatches prey and vanishes.'),
  c('allosaurus', 'Allosaurus', 'carnivore', 'rare', 'The lion of the Jurassic, striking with axe-like jaws.'),
  c('carnotaurus', 'Carnotaurus', 'carnivore', 'rare', 'The horned "meat-eating bull", built for terrifying sprints.'),
  c('baryonyx', 'Baryonyx', 'carnivore', 'rare', 'A fish-hooking riverside hunter with a crocodilian snout.'),
  c('spinosaurus', 'Spinosaurus', 'carnivore', 'epic', 'A sail-backed giant, at home in water and on land alike.'),
  c('giganotosaurus', 'Giganotosaurus', 'carnivore', 'epic', 'A southern colossus that hunted the largest prey ever known.'),
  c('acrocanthosaurus', 'Acrocanthosaurus', 'carnivore', 'legendary', 'A high-spined apex predator of Early Cretaceous floodplains.'),
  c('tyrannosaurus-rex', 'Tyrannosaurus rex', 'carnivore', 'mythic', 'The tyrant lizard king. Its bite could crush bone outright.'),

  // ─── Herbivores ───────────────────────────────────────────────
  c('gallimimus', 'Gallimimus', 'herbivore', 'common', 'An ostrich-like sprinter that outruns nearly everything.'),
  c('pachycephalosaurus', 'Pachycephalosaurus', 'herbivore', 'common', 'A dome-headed brawler that settles disputes head-first.'),
  c('iguanodon', 'Iguanodon', 'herbivore', 'common', 'A sturdy grazer whose thumb spikes double as daggers.'),
  c('parasaurolophus', 'Parasaurolophus', 'herbivore', 'common', 'Its swept-back crest trumpets calls across the herd.'),
  c('corythosaurus', 'Corythosaurus', 'herbivore', 'common', 'A helmet-crested duckbill with a chorus of low bellows.'),
  c('stegosaurus', 'Stegosaurus', 'herbivore', 'rare', 'Plated and patient — its thagomizer answers all arguments.'),
  c('ankylosaurus', 'Ankylosaurus', 'herbivore', 'rare', 'A living fortress swinging a bone-shattering tail club.'),
  c('styracosaurus', 'Styracosaurus', 'herbivore', 'rare', 'A spiked-frill charger with a temper to match its horns.'),
  c('triceratops', 'Triceratops', 'herbivore', 'epic', 'Three horns, one shield, zero retreat.'),
  c('therizinosaurus', 'Therizinosaurus', 'herbivore', 'epic', 'A towering leaf-eater wielding metre-long scythe claws.'),
  c('brachiosaurus', 'Brachiosaurus', 'herbivore', 'legendary', 'A long-necked giant grazing the forest canopy itself.'),
  c('argentinosaurus', 'Argentinosaurus', 'herbivore', 'mythic', 'Perhaps the largest land animal ever — the earth shakes.'),

  // ─── Pterosaurs ───────────────────────────────────────────────
  c('dimorphodon', 'Dimorphodon', 'pterosaur', 'common', 'A puffin-faced flapper darting through coastal cliffs.'),
  c('rhamphorhynchus', 'Rhamphorhynchus', 'pterosaur', 'common', 'A long-tailed fisher skimming waves with needle teeth.'),
  c('pterodactylus', 'Pterodactylus', 'pterosaur', 'common', 'The original "pterodactyl" — small, quick and curious.'),
  c('anhanguera', 'Anhanguera', 'pterosaur', 'common', 'A keel-snouted glider riding thermals over open sea.'),
  c('tapejara', 'Tapejara', 'pterosaur', 'common', 'A sail-crested show-off with dazzling display flights.'),
  c('tupandactylus', 'Tupandactylus', 'pterosaur', 'rare', 'Its towering crest is half banner, half rudder.'),
  c('dsungaripterus', 'Dsungaripterus', 'pterosaur', 'rare', 'Upturned jaws pry shellfish from tidal rocks.'),
  c('zhejiangopterus', 'Zhejiangopterus', 'pterosaur', 'rare', 'A silent, storky wanderer of Cretaceous wetlands.'),
  c('pteranodon', 'Pteranodon', 'pterosaur', 'epic', 'The iconic ocean soarer with a seven-metre wingspan.'),
  c('tropeognathus', 'Tropeognathus', 'pterosaur', 'epic', 'A keeled predator snapping fish from the wave crests.'),
  c('hatzegopteryx', 'Hatzegopteryx', 'pterosaur', 'legendary', 'An island giant that stalks prey on foot like a titan stork.'),
  c('quetzalcoatlus', 'Quetzalcoatlus', 'pterosaur', 'mythic', 'A giraffe-sized flier — the largest wings in history.'),

  // ─── Amphibians ───────────────────────────────────────────────
  c('diplocaulus', 'Diplocaulus', 'amphibian', 'common', 'A boomerang-headed lurker gliding through murky streams.'),
  c('metoposaurus', 'Metoposaurus', 'amphibian', 'common', 'A flat-headed ambusher buried in the Triassic mud.'),
  c('mastodonsaurus', 'Mastodonsaurus', 'amphibian', 'common', 'A giant salamander whose tusks pierce its own snout.'),
  c('champsosaurus', 'Champsosaurus', 'amphibian', 'common', 'A slender-jawed swimmer weaving through reed beds.'),
  c('rutiodon', 'Rutiodon', 'amphibian', 'common', 'A phytosaur that wears the river like armor.'),
  c('kaprosuchus', 'Kaprosuchus', 'amphibian', 'rare', 'The "boar croc" — tusked, fast and fearless on land.'),
  c('nothosaurus', 'Nothosaurus', 'amphibian', 'rare', 'A seal-like fisher sliding between rock and surf.'),
  c('koolasuchus', 'Koolasuchus', 'amphibian', 'rare', 'A cold-water survivor haunting polar rift valleys.'),
  c('prionosuchus', 'Prionosuchus', 'amphibian', 'epic', 'The largest amphibian ever — a nine-metre river dragon.'),
  c('deinosuchus', 'Deinosuchus', 'amphibian', 'epic', 'A bus-sized alligator that preys on dinosaurs at the shore.'),
  c('sarcosuchus', 'Sarcosuchus', 'amphibian', 'legendary', 'The super-croc: twelve metres of patient, armored death.'),
  c('purussaurus', 'Purussaurus', 'amphibian', 'mythic', 'A monstrous caiman with the strongest bite of any animal.'),
];
