"""v8: agarre a distancia en el pawn VR (cerca: esfera 15 cm; si no hay nada, rayo de 4 m desde el mando)."""
import os
import sys
import traceback
import unreal

TOOLS = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()), 'Tools', 'GeneradorPython')
sys.path.insert(0, TOOLS)
import p3dsl  # noqa: E402
from p3dsl import BT  # noqa: E402

L = []
GRAB = '/Game/XRFramework/Blueprints/BP_GrabComponent.BP_GrabComponent_C'
p3dsl.CLASSES['BP_GrabComponent'] = GRAB


def bind_names(g, type_id, wanted):
    ni = BT.get_node_type_pins(g, type_id)
    order = [p.name for p in ni.output_pins if p.type_id != 'Exec']
    return '(' + ' '.join(wanted.get(p, '_' + p.lower().replace(' ', '')) for p in order) + ')'


try:
    bp = unreal.load_asset('/Game/XRFramework/Blueprints/BP_XRPawn')
    g = BT.get_graph(bp, 'GetGrabComponentNearMotionController')
    ed = unreal.BlueprintGraphEditor.get_graph_editor(g)
    ed.remove_nodes([n for n in ed.list_all_nodes() if not isinstance(n, (unreal.K2Node_FunctionEntry, unreal.K2Node_FunctionResult))])
    st = bind_names(g, 'Collision|SphereTraceByChannel', {'OutHit': 'h1', 'ReturnValue': 'ok1'})
    lt = bind_names(g, 'Collision|LineTraceByChannel', {'OutHit': 'h2', 'ReturnValue': 'ok2'})
    b1 = bind_names(g, 'Collision|BreakHitResult', {'HitActor': 'a1'})
    b2 = bind_names(g, 'Collision|BreakHitResult', {'HitActor': 'a2'})
    p3dsl.write(g, f'''
(fn GetGrabComponentNearMotionController (MotionController)
  (bind pos (Transformation|GetWorldLocation :self MotionController))
  (bind fwd (Transformation|GetForwardVector :self MotionController))
  (bind {st} (Collision|SphereTraceByChannel :Start pos :End (+ pos (* fwd 2.0)) :Radius (Get|GrabRadiusFromGripPosition) :TraceChannel "Visibility" :bIgnoreSelf true))
  (if ok1
    (bind {b1} (Collision|BreakHitResult :Hit h1))
    (bind c1 (Actor|GetComponentbyClass :self a1 :ComponentClass "{GRAB}"))
    (bind g1 (CastTo|BP_GrabComponent :Object c1)
      (:then (return g1))
      (:CastFailed)))
  (bind {lt} (Collision|LineTraceByChannel :Start pos :End (+ pos (* fwd 400.0)) :TraceChannel "Visibility" :bIgnoreSelf true))
  (if ok2
    (bind {b2} (Collision|BreakHitResult :Hit h2))
    (bind c2 (Actor|GetComponentbyClass :self a2 :ComponentClass "{GRAB}"))
    (bind g2 (CastTo|BP_GrabComponent :Object c2)
      (:then
        (Transformation|SetWorldLocation :self (Transformation|GetAttachParent :self g2) :NewLocation (+ pos (* fwd 8.0)) :bTeleport true)
        (return g2))
      (:CastFailed)))
  (return))''', 'XRPawn.Grab')
    p3dsl.compile_and_report(bp)
    unreal.EditorAssetLibrary.save_loaded_asset(bp)
    L.append('XRPawn OK')
    L.append(BT.read_graph_dsl(g))
except Exception:
    L.append('FAIL ' + traceback.format_exc())
L.append('ERRORES DSL: %d' % len(p3dsl.ERRORS))
L += p3dsl.ERRORS
open(os.path.join(TOOLS, 'fix_v8.txt'), 'w', encoding='utf-8').write(chr(10).join(L))
