"""Corrige la iluminación: las luces puntuales de UE 5 van en candelas (valores típicos 5-30)."""
import os
import unreal

OUT = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()), 'Tools', 'GeneradorPython', 'fix_luz.txt')
L = []

# Intensidad (cd) y radio por prefijo de etiqueta
REGLAS = [
    ('Entorno_Luz_B', 12.0, 1100),
    ('Entorno_Luz_A', 6.0, 900),
    ('Bolera_Luz', 15.0, 600),
    ('Dardos_Foco', 15.0, 500),
    ('MrPotato_Foco', 10.0, 500),
    ('RompeRalph_Foco', 10.0, 500),
]

unreal.EditorLoadingAndSavingUtils.load_map('/Game/XRFramework/Levels/L_XRTemplate')
for a in unreal.EditorLevelLibrary.get_all_level_actors():
    if not isinstance(a, unreal.PointLight):
        continue
    lbl = a.get_actor_label()
    for pref, cd, rad in REGLAS:
        if lbl.startswith(pref):
            lc = a.point_light_component
            lc.set_editor_property('intensity_units', unreal.LightUnits.CANDELAS)
            lc.set_intensity(cd)
            lc.set_attenuation_radius(rad)
            L.append(f'{lbl}: {cd} cd')
unreal.EditorLoadingAndSavingUtils.save_current_level()

# Neones: brillo x2 en lugar de x6
m = unreal.load_asset('/Game/Practica3/Materiales/M_P3_Neon')
for node in [unreal.MaterialEditingLibrary.get_material_property_input_node(m, unreal.MaterialProperty.MP_EMISSIVE_COLOR)]:
    if isinstance(node, unreal.MaterialExpressionMultiply):
        node.set_editor_property('const_b', 2.0)
        L.append('neon x2')
unreal.MaterialEditingLibrary.recompile_material(m)
unreal.EditorAssetLibrary.save_loaded_asset(m)
open(OUT, 'w', encoding='utf-8').write('\n'.join(L))
