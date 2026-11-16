"""v7: el gatillo de los mandos Meta también agarra/suelta (útil en el simulador)."""
import os
import unreal
OUT = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()), 'Tools', 'GeneradorPython', 'fix_v7.txt')
L = []
imc = unreal.load_asset('/Game/XRFramework/Input/IMC_Default')
dkm = imc.get_editor_property('default_key_mappings')
maps = list(dkm.get_editor_property('mappings'))
extra = {'OculusTouch_Left_Grip_Axis': 'OculusTouch_Left_Trigger_Axis', 'OculusTouch_Right_Grip_Axis': 'OculusTouch_Right_Trigger_Axis'}
existing = {(m.get_editor_property('action').get_name(), str(m.get_editor_property('key').get_editor_property('key_name'))) for m in maps if m.get_editor_property('action')}
new = []
for m in maps:
    a = m.get_editor_property('action')
    k = str(m.get_editor_property('key').get_editor_property('key_name'))
    if a and k in extra and a.get_name().startswith('IA_Grab') and (a.get_name(), extra[k]) not in existing:
        n = unreal.EnhancedActionKeyMapping()
        n.set_editor_property('action', a)
        key = unreal.Key()
        key.set_editor_property('key_name', extra[k])
        n.set_editor_property('key', key)
        n.set_editor_property('triggers', list(m.get_editor_property('triggers')))
        n.set_editor_property('modifiers', list(m.get_editor_property('modifiers')))
        new.append(n)
        L.append(f'{a.get_name()} <- {extra[k]} (copiando {len(n.get_editor_property("triggers"))} triggers)')
dkm.set_editor_property('mappings', maps + new)
imc.set_editor_property('default_key_mappings', dkm)
unreal.EditorAssetLibrary.save_loaded_asset(imc, False)
check = unreal.load_asset('/Game/XRFramework/Input/IMC_Default').get_editor_property('default_key_mappings').get_editor_property('mappings')
L.append(f'total mapeos: {len(check)}')
open(OUT, 'w', encoding='utf-8').write(chr(10).join(L))
