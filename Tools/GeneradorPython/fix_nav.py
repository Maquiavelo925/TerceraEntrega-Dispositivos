import unreal, os
T=os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()),'Tools','GeneradorPython')
L=[]
unreal.EditorLoadingAndSavingUtils.load_map('/Game/XRFramework/Levels/L_XRTemplate')
for a in unreal.EditorLevelLibrary.get_all_level_actors():
    if a.get_class().get_name()=='RecastNavMesh':
        try:
            a.set_editor_property('runtime_generation', unreal.RuntimeGenerationType.DYNAMIC); L.append('nav dynamic OK')
        except Exception as e: L.append('nav ERR '+str(e))
unreal.EditorLoadingAndSavingUtils.save_current_level()
open(os.path.join(T,'fix_nav.txt'),'w').write('\n'.join(L))
