extends Control
## Shared shell for screens whose features land in later milestones
## (collection, deck builder, shop). Provides only the back navigation;
## each scene sets its own labels.


func _ready() -> void:
	%BackButton.pressed.connect(SceneRouter.back)
