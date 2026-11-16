"""v6 (VR): radio de agarre 15 cm, neones más suaves, postproceso anti-deslumbramiento, PlayerStart VR a ras de suelo."""
import os
import unreal
OUT = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()), 'Tools', 'GeneradorPython', 'fix_v6.txt')
L = []
EAL = unreal.EditorAssetLibrary
MEL = unreal.MaterialEditingLibrary

# 1) Radio de agarre del pawn VR
pawn = unreal.load_asset('/Game/XRFramework/Blueprints/BP_XRPawn')
cdo = unreal.get_default_object(unreal.BlueprintEditorLibrary.generated_class(pawn))
L.append(f'radio antes: {cdo.get_editor_property("GrabRadiusFromGripPosition")}')
cdo.set_editor_property('GrabRadiusFromGripPosition', 15.0)
unreal.BlueprintEditorLibrary.compile_blueprint(pawn)
EAL.save_loaded_asset(pawn)
L.append(f'radio ahora: {unreal.get_default_object(unreal.BlueprintEditorLibrary.generated_class(pawn)).get_editor_property("GrabRadiusFromGripPosition")}')

# 2) Neones más suaves (x0.8) y metal menos espejo
m = unreal.load_asset('/Game/Practica3/Materiales/M_P3_Neon')
node = MEL.get_material_property_input_node(m, unreal.MaterialProperty.MP_EMISSIVE_COLOR)
if isinstance(node, unreal.MaterialExpressionMultiply):
    node.set_editor_property('const_b', 0.8)
MEL.recompile_material(m)
EAL.save_loaded_asset(m)
mi = unreal.load_asset('/Game/Practica3/Materiales/MI_Metal')
MEL.set_material_instance_scalar_parameter_value(mi, 'Roughness', 0.55)
EAL.save_loaded_asset(mi)
L.append('neon 0.8, metal rugosidad 0.55')

# 3) Postproceso global en ambos mapas; PlayerStart del mapa VR a ras de suelo
for mp in ['/Game/Practica3/L_Practica3_VR', '/Game/Practica3/L_Practica3_PC']:
    unreal.EditorLoadingAndSavingUtils.load_map(mp)
    for a in unreal.EditorLevelLibrary.get_all_level_actors():
        if a.get_actor_label() == 'Entorno_PostProceso':
            unreal.get_editor_subsystem(unreal.EditorActorSubsystem).destroy_actor(a)
    ppv = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).spawn_actor_from_class(unreal.PostProcessVolume, unreal.Vector(500, 0, 200), unreal.Rotator(0, 0, 0))
    ppv.set_actor_label('Entorno_PostProceso')
    ppv.set_editor_property('unbound', True)
    s = ppv.get_editor_property('settings')
    for k, v in [('override_bloom_intensity', True), ('bloom_intensity', 0.15),
                 ('override_auto_exposure_bias', True), ('auto_exposure_bias', -0.7)]:
        try:
            s.set_editor_property(k, v)
        except Exception as e:  # noqa
            L.append(f'pp {k}: {e}')
    ppv.set_editor_property('settings', s)
    try:
        ppv.set_folder_path('Entorno')
    except Exception:
        pass
    if mp.endswith('_VR'):
        for a in unreal.EditorLevelLibrary.get_all_level_actors():
            if isinstance(a, unreal.PlayerStart):
                a.modify()
                loc = a.get_actor_location()
                a.set_actor_location(unreal.Vector(loc.x, loc.y, 0.0), False, True)
                L.append('PlayerStart VR z=0')
    unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
    L.append(f'{mp}: postproceso añadido')
open(OUT, 'w', encoding='utf-8').write(chr(10).join(L))
