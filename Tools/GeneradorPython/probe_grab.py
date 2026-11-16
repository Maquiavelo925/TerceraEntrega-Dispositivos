import unreal, os
from editor_toolset.toolsets.blueprint import BlueprintTools as BT
OUT=os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()),'Tools','GeneradorPython','probe_grab.txt')
L=[]
bp=unreal.load_asset('/Game/XRFramework/Blueprints/BP_GrabComponent')
for f in BT.list_functions(bp): L.append('FN '+str(f.name))
for g in BT.list_graphs(bp):
    L.append('==== '+g.get_name())
    try: L.append(BT.read_graph_dsl(g)[:3000])
    except Exception as e: L.append('ERR '+str(e))
pw=unreal.load_asset('/Game/XRFramework/Blueprints/BP_XRPawn')
for g in BT.list_graphs(pw):
    n=g.get_name()
    if 'Grab' in n or 'Event' in n:
        L.append('#### PAWN '+n)
        try: L.append(BT.read_graph_dsl(g)[:4000])
        except Exception as e: L.append('ERR '+str(e))
open(OUT,'w',encoding='utf-8').write('\n'.join(L))
