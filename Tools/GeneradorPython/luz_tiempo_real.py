"""Pasa toda la iluminación de los dos mapas a tiempo real (Lumen) y quita la luz precalculada antigua."""
import os
import unreal

OUT = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()), 'Tools', 'GeneradorPython', 'luz_tiempo_real.txt')
L = []
EAL = unreal.EditorAssetLibrary

for m in ['/Game/XRFramework/Levels/L_XRTemplate', '/Game/Practica3/L_Practica3_PC']:
    unreal.EditorLoadingAndSavingUtils.load_map(m)
    n = 0
    for a in unreal.EditorLevelLibrary.get_all_level_actors():
        for c in a.get_components_by_class(unreal.LightComponentBase):
            if c.get_editor_property('mobility') != unreal.ComponentMobility.MOVABLE:
                c.set_mobility(unreal.ComponentMobility.MOVABLE)
                n += 1
                L.append(f'{m}: {a.get_actor_label()} -> Movable')
        if isinstance(a, unreal.SkyLight):
            try:
                a.light_component.set_editor_property('real_time_capture', True)
            except Exception as e:  # noqa
                L.append(f'skylight rt: {e}')
    unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
    L.append(f'{m}: {n} luces a Movable')

# La luz precalculada del mapa base ya no corresponde a la sala: se elimina para que se vea como el de PC.
for p in ['/Game/XRFramework/Levels/L_XRTemplate_BuiltData', '/Game/XRFramework/Levels/L_XRTemplate_Lighting_BuiltData']:
    if EAL.does_asset_exist(p):
        L.append(f'borrar {p}: {EAL.delete_asset(p)}')
unreal.EditorLoadingAndSavingUtils.load_map('/Game/XRFramework/Levels/L_XRTemplate')
unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
open(OUT, 'w', encoding='utf-8').write('\n'.join(L))
