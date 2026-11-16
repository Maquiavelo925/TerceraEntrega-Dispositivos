import os
import unreal
OUT = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()), 'Tools', 'GeneradorPython', 'crear_mapa_vr.txt')
L = []
EAL = unreal.EditorAssetLibrary
PC = '/Game/Practica3/L_Practica3_PC'
VR = '/Game/Practica3/L_Practica3_VR'
if EAL.does_asset_exist(VR):
    EAL.delete_asset(VR)
d = EAL.duplicate_asset(PC, VR)
L.append(f'duplicado: {d}')
unreal.EditorLoadingAndSavingUtils.load_map(VR)
w = unreal.EditorLevelLibrary.get_editor_world()
ws = w.get_world_settings()
ws.set_editor_property('default_game_mode', None)
L.append(f'game mode: {ws.get_editor_property("default_game_mode")}')
n = 0
for a in unreal.EditorLevelLibrary.get_all_level_actors():
    if isinstance(a, unreal.PointLight) and a.get_actor_label().startswith(('Entorno_Luz', 'Bolera_Luz', 'Dardos_Foco', 'MrPotato_Foco', 'RompeRalph_Foco')):
        L.append(f'{a.get_actor_label()} {a.point_light_component.get_editor_property("intensity")}')
    n += 1
L.append(f'actores {n}')
L.append(f'guardado {unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)}')
open(OUT, 'w', encoding='utf-8').write('\n'.join(L))
