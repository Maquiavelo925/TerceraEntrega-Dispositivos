"""Deja el mapa VR idéntico al de PC: luces corregidas (candelas, Movable) y sin luz precalculada."""
import os
import unreal

OUT = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()), 'Tools', 'GeneradorPython', 'igualar_mapas.txt')
L = []
EAL = unreal.EditorAssetLibrary
VR = '/Game/XRFramework/Levels/L_XRTemplate'
PC = '/Game/Practica3/L_Practica3_PC'
LUCES = [('Entorno_Luz_B', 12.0, 1100), ('Entorno_Luz_A', 6.0, 900), ('Bolera_Luz', 15.0, 600),
         ('Dardos_Foco', 15.0, 500), ('MrPotato_Foco', 10.0, 500), ('RompeRalph_Foco', 10.0, 500)]

unreal.EditorLoadingAndSavingUtils.load_map(PC)
for a in unreal.EditorLevelLibrary.get_all_level_actors():
    for c in a.get_components_by_class(unreal.LightComponentBase):
        if c.get_editor_property('mobility') != unreal.ComponentMobility.MOVABLE:
            c.set_editor_property('mobility', unreal.ComponentMobility.MOVABLE)
            L.append(f'movable {a.get_actor_label()}')
    if isinstance(a, unreal.PointLight):
        for pref, cd, rad in LUCES:
            if a.get_actor_label().startswith(pref):
                c = a.point_light_component
                c.set_editor_property('intensity_units', unreal.LightUnits.CANDELAS)
                c.set_editor_property('intensity', cd)
                c.set_editor_property('attenuation_radius', rad)
                L.append(f'{a.get_actor_label()} = {c.get_editor_property("intensity")} cd')
ok = unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
L.append(f'guardado PC {ok}')

# Mapa VR = copia del de PC con el modo de juego del proyecto (VR)
unreal.EditorLoadingAndSavingUtils.new_blank_map(False)
for p in [VR, VR + '_BuiltData']:
    if EAL.does_asset_exist(p):
        L.append(f'borrar {p}: {EAL.delete_asset(p)}')
L.append(f'duplicar: {EAL.duplicate_asset(PC, VR) is not None}')
unreal.EditorLoadingAndSavingUtils.load_map(VR)
ws = unreal.EditorLevelLibrary.get_editor_world().get_world_settings()
ws.set_editor_property('default_game_mode', None)
unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
L.append('VR guardado')
open(OUT, 'w', encoding='utf-8').write('\n'.join(L))
