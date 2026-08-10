# 3D dinosaur models on cards

Yes — a card can carry a real 3D model that stands on top of its face.
`Card3D` is a plain `Node3D`, so the model is just another child alongside
the card quad; it inherits every slot move, hover raise, attack lunge and
knockout animation without any extra code.

## How to add one

1. Drop a `.glb`, `.gltf` or `.tscn` into this folder, e.g.
   `res://assets/models/tyrannosaur.glb`.
2. Point the card at it in `godot/database/cards.json`:

   ```json
   {
     "id": "dino-tyrannosaur",
     "name": "Tyrannosaur",
     "model": "res://assets/models/tyrannosaur.glb",
     "model_scale": 0.35
   }
   ```

3. That's it. `Card3D._sync_model()` loads the scene, parents it above the
   card face at `MODEL_LIFT`, applies `model_scale` and starts a slow idle
   bob. Cards without a `model` key keep rendering as flat faces, so models
   can be added one dinosaur at a time.

## Authoring guidance

- **Orientation.** The card lies flat, face up, with the camera looking down
  the `-Z` axis from `+Y`. Author the model standing on the XZ plane with
  its origin at the feet and facing `+Z`, and it will face the player.
- **Size.** A card is `0.9 × 1.26` world units. A model roughly `0.5` units
  tall reads well without covering the neighbouring slots — pick
  `model_scale` so the exported mesh lands near that.
- **Budget.** Up to eight dinosaurs are on the table at once. The renderer
  is set to `mobile`, so aim for a few thousand triangles and one material
  per model; skinned idle animations are fine at that count, but avoid
  per-model lights.
- **Materials.** The scene lights the table with one `DirectionalLight3D`
  plus ambient. Unshaded or lightly-shaded materials read cleanly against
  the dark table; fully unlit models look flat next to the card face.
- **The card face is unaffected.** It renders through a `SubViewport` with
  `own_world_3d = true`, so the model never appears in — or interferes
  with — the 2D face texture.
