"""v5: piñata 'dormida' (cae al golpearla) y Sky Light sin captura en tiempo real."""
import os
import unreal
OUT = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()), 'Tools', 'GeneradorPython', 'fix_v5.txt')
L = []
SUB = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
pin = unreal.load_asset('/Game/Practica3/Blueprints/BP_Pinata')
for h in SUB.k2_gather_subobject_data_for_blueprint(pin):
    o = unreal.SubobjectDataBlueprintFunctionLibrary.get_object(SUB.k2_find_subobject_data_from_handle(h))
    if isinstance(o, unreal.GeometryCollectionComponent):
        o.set_editor_property('object_type', unreal.ObjectStateTypeEnum.CHAOS_OBJECT_SLEEPING)
        L.append('pinata sleeping')
unreal.BlueprintEditorLibrary.compile_blueprint(pin)
unreal.EditorAssetLibrary.save_loaded_asset(pin)
for m in ['/Game/Practica3/L_Practica3_VR', '/Game/Practica3/L_Practica3_PC']:
    unreal.EditorLoadingAndSavingUtils.load_map(m)
    for a in unreal.EditorLevelLibrary.get_all_level_actors():
        if isinstance(a, unreal.SkyLight):
            a.modify()
            a.light_component.set_editor_property('real_time_capture', False)
            L.append(f'{m}: skylight sin captura en tiempo real')
        for c in a.get_components_by_class(unreal.GeometryCollectionComponent):
            a.modify()
            c.set_editor_property('object_type', unreal.ObjectStateTypeEnum.CHAOS_OBJECT_SLEEPING)
            L.append(f'{m}: {a.get_actor_label()} sleeping')
    unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
open(OUT, 'w', encoding='utf-8').write(chr(10).join(L))
