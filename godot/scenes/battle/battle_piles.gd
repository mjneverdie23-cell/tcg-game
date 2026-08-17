class_name BattlePiles
extends Node3D
## The four card piles standing on the table: a deck and a used pile for
## each player, the way they would sit in a real game — a slab that grows
## with the cards in it and a floating count.
##
## Addressed by table side rather than by player: side 0 is the near half,
## always the local player's, whichever seat they hold in the engine. Only
## the near used pile is clickable — an opponent's discard is public in most
## card games, but showing it here would clutter the board without giving
## the player anything to act on.

## Somebody clicked their own used pile and wants to see what is in it.
signal used_pile_clicked

## How far right the piles stand. Solved against the projected pile bounds
## rather than eyeballed: it is the furthest right they can sit while still
## clearing the HUD at 4:3, where the narrower horizontal FOV throws the
## table's edges outward. Also clears the widest bench slot.
const PILE_X := 2.40
## Piles flank the rows on the right: the deck level with the bench, the
## used pile level with the Active.
const DECK_DEPTH := 2.15
const USED_DEPTH := 0.7

## "deck0" / "used0" / "deck1" / "used1" -> CardPile3D.
var _piles: Dictionary = {}


func build() -> void:
	for side in range(2):
		for kind: String in ["deck", "used"]:
			var pile := CardPile3D.new()
			add_child(pile)
			var depth := DECK_DEPTH if kind == "deck" else USED_DEPTH
			pile.transform = Transform3D(Basis.IDENTITY, Vector3(
				PILE_X, 0.155, depth * (1.0 if side == 0 else -1.0)))
			var mine := side == 0 and kind == "used"
			pile.setup(
				"DECK" if kind == "deck" else "USED",
				Color("16224a") if kind == "deck" else Color("3a1f2a"),
				mine)
			if mine:
				pile.clicked.connect(func(_p: CardPile3D) -> void: used_pile_clicked.emit())
			_piles["%s%d" % [kind, side]] = pile


## One pile, so the battle screen can fly cards to and from it.
func pile(side: int, kind: String) -> CardPile3D:
	return _piles["%s%d" % [kind, side]]


func set_counts(side: int, deck: int, used: int) -> void:
	pile(side, "deck").set_count(deck)
	pile(side, "used").set_count(used)
