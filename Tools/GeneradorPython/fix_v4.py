"""v4: en el mapa de PC, clic sobre un botón REINICIAR lo pulsa. Actualiza el texto de ayuda."""
import json
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
    bp = unreal.load_asset('/Game/Practica3/Blueprints/BP_PersonajePC')
    g = BT.get_graph(bp, 'Agarrar')
    ed = unreal.BlueprintGraphEditor.get_graph_editor(g)
    keep = []
    nodes = [n for n in ed.list_all_nodes() if not isinstance(n, unreal.K2Node_FunctionEntry)]
    ed.remove_nodes(nodes)
    lt = bind_names(g, 'Collision|LineTraceByChannel', {'OutHit': 'hit', 'ReturnValue': 'ok'})
    bh = bind_names(g, 'Collision|BreakHitResult', {'HitActor': 'actor', 'HitComponent': 'hcomp'})
    p3dsl.write(g, f'''
(fn Agarrar ()
  (bind start (Transformation|GetWorldLocation :self (Get|Camara)))
  (bind end (+ start (* (Transformation|GetForwardVector :self (Get|Camara)) 300.0)))
  (bind {lt} (Collision|LineTraceByChannel :Start start :End end :TraceChannel "Visibility" :bIgnoreSelf true))
  (if ok
    (bind {bh} (Collision|BreakHitResult :Hit hit))
    (if (Utilities|String|EqualExactly(String) :A (Utilities|GetObjectName :Object hcomp) :B "BotonBase")
      (Utilities|Time|SetTimerbyFunctionName :Object actor :FunctionName "PulsarBoton" :Time 0.01 :bLooping false)
      (else
        (bind comp (Actor|GetComponentbyClass :self actor :ComponentClass "{GRAB}"))
        (bind gr (CastTo|BP_GrabComponent :Object comp)
          (:then
            (bind okg (CallOf|BP_GrabComponent|TryGrab :self gr :MotionController (Get|Mano)))
            (if okg
              (Set|Sostenido gr)
              (Set|Sosteniendo true)
              (Set|ActorSostenido actor)
              (Fn|/Script/Engine.PrimitiveComponent:IgnoreActorWhenMoving :self (Get|CapsuleComponent) :Actor actor :bShouldIgnore true)
              (Transformation|SetWorldLocation :self (Transformation|GetAttachParent :self gr) :NewLocation (Transformation|GetWorldLocation :self (Get|Mano)) :bTeleport true)))
          (:CastFailed))))))''', 'PC.Agarrar')
    p3dsl.compile_and_report(bp)
    unreal.EditorAssetLibrary.save_loaded_asset(bp)
    L.append('Agarrar OK')
except Exception:
    L.append('FAIL ' + traceback.format_exc())

try:
    wbp = unreal.load_asset('/Game/Practica3/UI/WBP_Mira')
    r = unreal.ToolsetRegistry.execute_tool('UMGToolSet.UMGToolSet', 'GetWidgets', json.dumps({'widgetBlueprint': {'refPath': wbp.get_path_name()}}))
    txt = r.value if isinstance(r.value, str) else json.dumps(r.value)
    import re
    for path in set(re.findall(r'"refPath":\s*"([^"]*Ayuda[^"]*)"', txt)):
        w = unreal.load_object(None, path)
        if isinstance(w, unreal.TextBlock):
            w.set_editor_property('text', 'WASD: andar   |   Espacio: saltar   |   Raton: mirar\n'
                                  'Clic izquierdo: agarrar / soltar   |   Clic derecho: lanzar\n'
                                  'Clic en un boton REINICIAR para reiniciar ese juego   |   Martillo: muevelo rapido contra la pinata')
            L.append('ayuda actualizada')
    unreal.BlueprintEditorLibrary.compile_blueprint(wbp)
    unreal.EditorAssetLibrary.save_loaded_asset(wbp)
except Exception:
    L.append('WBP FAIL ' + traceback.format_exc())
L.append('ERRORES DSL: %d' % len(p3dsl.ERRORS))
L += p3dsl.ERRORS
open(os.path.join(TOOLS, 'fix_v4.txt'), 'w', encoding='utf-8').write(chr(10).join(L))
