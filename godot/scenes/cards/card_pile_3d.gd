class_name CardPile3D
extends Node3D
## A deck or used-card pile as a physical stack on the table: a slab whose
## height grows with the number of cards in it, a floating count, and an
## optional click target.
##
## Deliberately not built from Card3D nodes — a pile only ever shows its
## depth and its size, so one box beats twenty SubViewports.

signal clicked(pile: CardPile3D)

const WIDTH := Card3D.WIDTH
const DEPTH := Card3D.HEIGHT
## Thickness one card adds to the stack, and the floor under an empty pile.
const CARD_THICKNESS := 0.005
const EMPTY_HEIGHT := 0.012
## A full deck would otherwise stand taller than the dinosaurs beside it.
const MAX_HEIGHT := 0.16
## The footprint drawn under the pile, so its place on the table is marked
## even when there is nothing in it. Sits low enough that the slab hides it
## as soon as the pile has cards.
const FOOTPRINT_HEIGHT := 0.002

var count: int = 0
var pile_name: String = ""

var _slab: MeshInstance3D
var _footprint: MeshInstance3D
var _box: BoxMesh
var _label: Label3D
var _area: Area3D
var _material: StandardMaterial3D
## setup() may run before _ready(); these hold its arguments until _build().
var _tint := Color("111a33")
var _clickable := false


func _ready() -> void:
	_build()
	_apply_count()


## `tint` colours the slab (deck backs vs discarded cards); `clickable` adds
## the picking area that emits `clicked`.
func setup(new_name: String, tint: Color, clickable: bool) -> void:
	pile_name = new_name
	_tint = tint
	_clickable = clickable
	if _material != null:
		_material.albedo_color = tint
	if _area != null:
		_area.input_ray_pickable = clickable


func set_count(new_count: int) -> void:
	count = new_count
	if is_inside_tree():
		_apply_count()


func _build() -> void:
	_box = BoxMesh.new()
	_box.size = Vector3(WIDTH, EMPTY_HEIGHT, DEPTH)
	_material = StandardMaterial3D.new()
	_material.albedo_color = _tint
	_material.roughness = 0.7
	_slab = MeshInstance3D.new()
	_slab.mesh = _box
	_slab.material_override = _material
	add_child(_slab)

	# The same frame that marks an empty slot, so an empty pile still shows
	# where it belongs — including over an Environment's terrain, which a
	# plain translucent wash would disappear into.
	var outline := QuadMesh.new()
	outline.size = Vector2(WIDTH, DEPTH)
	_footprint = MeshInstance3D.new()
	_footprint.mesh = outline
	_footprint.material_override = SlotFrame.material(outline.size)
	_footprint.position.y = FOOTPRINT_HEIGHT
	_footprint.rotate_object_local(Vector3.RIGHT, -PI / 2)
	add_child(_footprint)

	_label = Label3D.new()
	_label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	_label.font_size = 34
	_label.pixel_size = 0.004
	_label.outline_size = 10
	_label.no_depth_test = true
	_label.position = Vector3(0, 0.3, 0)
	add_child(_label)

	_area = Area3D.new()
	var shape := CollisionShape3D.new()
	var box := BoxShape3D.new()
	box.size = Vector3(WIDTH, 0.24, DEPTH)
	shape.shape = box
	shape.position.y = 0.12
	_area.add_child(shape)
	_area.input_ray_pickable = _clickable
	_area.input_event.connect(_on_area_input)
	add_child(_area)


func _apply_count() -> void:
	var height := maxf(EMPTY_HEIGHT, minf(MAX_HEIGHT, count * CARD_THICKNESS))
	_box.size = Vector3(WIDTH, height, DEPTH)
	_slab.position.y = height * 0.5
	_slab.visible = count > 0
	_label.text = "%s\n%d" % [pile_name, count]
	_label.modulate = Color.WHITE if count > 0 else Color("6f7891")


func _on_area_input(
		_camera: Node, event: InputEvent, _pos: Vector3, _normal: Vector3, _shape: int) -> void:
	if event is InputEventMouseButton and event.pressed \
			and event.button_index == MOUSE_BUTTON_LEFT:
		clicked.emit(self)
