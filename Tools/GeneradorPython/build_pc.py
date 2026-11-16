"""Mapa gemelo para probar en PC (teclado + ratón) + corrección de luz y colores.

- Arregla las luces (candelas) y baja el brillo de los neones.
- Da color a paredes y suelo.
- Crea WBP_Mira, BP_JugadorPC (DefaultPawn con "mano" MotionController), BP_GameModePC.
- Duplica el mapa VR como /Game/Practica3/L_Practica3_PC con el modo de juego de PC.
El jugador de PC usa el mismo BP_GrabComponent de la plantilla (TryGrab / TryRelease).
"""
import json
import os
import sys
import traceback

import unreal

TOOLS = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()), 'Tools', 'GeneradorPython')
sys.path.insert(0, TOOLS)
import p3dsl  # noqa: E402
from p3dsl import BT  # noqa: E402

LOG = []


def log(*a):
    LOG.append(' '.join(str(x) for x in a))


EAL = unreal.EditorAssetLibrary
MEL = unreal.MaterialEditingLibrary
SUB = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
BPDIR = '/Game/Practica3/Blueprints'
MAT = '/Game/Practica3/Materiales/'
VR_MAP = '/Game/XRFramework/Levels/L_XRTemplate'
PC_MAP = '/Game/Practica3/L_Practica3_PC'
GRAB = '/Game/XRFramework/Blueprints/BP_GrabComponent.BP_GrabComponent_C'

p3dsl.CLASSES.update({
    'BP_GrabComponent': GRAB,
    'BP_Dardo': f'{BPDIR}/BP_Dardo.BP_Dardo_C',
    'WBP_Mira': '/Game/Practica3/UI/WBP_Mira.WBP_Mira_C',
})


def fresh(path):
    if EAL.does_asset_exist(path):
        EAL.delete_asset(path)


# ---------------------------------------------------------------- luz y color
LUCES = [
    ('Entorno_Luz_B', 12.0, 1100), ('Entorno_Luz_A', 6.0, 900), ('Bolera_Luz', 15.0, 600),
    ('Dardos_Foco', 15.0, 500), ('MrPotato_Foco', 10.0, 500), ('RompeRalph_Foco', 10.0, 500),
]


def fix_lights_in_current_level():
    n = 0
    for a in unreal.EditorLevelLibrary.get_all_level_actors():
        if not isinstance(a, unreal.PointLight):
            continue
        lbl = a.get_actor_label()
        for pref, cd, rad in LUCES:
            if lbl.startswith(pref):
                lc = a.point_light_component
                lc.set_editor_property('intensity_units', unreal.LightUnits.CANDELAS)
                lc.set_intensity(cd)
                lc.set_attenuation_radius(rad)
                n += 1
    log('luces corregidas', n)


def fix_materials():
    m = unreal.load_asset(MAT + 'M_P3_Neon')
    node = MEL.get_material_property_input_node(m, unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    if isinstance(node, unreal.MaterialExpressionMultiply):
        node.set_editor_property('const_b', 2.0)
    MEL.recompile_material(m)
    EAL.save_loaded_asset(m)
    colores = {
        'MI_Pared': ((0.03, 0.06, 0.22, 1), 0.8),     # azul noche
        'MI_Moqueta': ((0.22, 0.04, 0.16, 1), 0.95),  # moqueta granate
        'MI_Negro': ((0.02, 0.02, 0.04, 1), 0.7),
    }
    for n, (c, r) in colores.items():
        mi = unreal.load_asset(MAT + n)
        MEL.set_material_instance_vector_parameter_value(mi, 'Color', unreal.LinearColor(*c))
        MEL.set_material_instance_scalar_parameter_value(mi, 'Roughness', r)
        EAL.save_loaded_asset(mi)
    log('materiales OK')


# ---------------------------------------------------------------- mira (UMG)

def umg(tool, **kw):
    r = unreal.ToolsetRegistry.execute_tool('UMGToolSet.UMGToolSet', tool, json.dumps(kw))
    if r.error:
        raise RuntimeError(f'UMG {tool}: {r.error}')
    v = r.value
    return json.loads(v) if isinstance(v, str) and v else v


def ref(o):
    return {'refPath': o if isinstance(o, str) else o.get_path_name()}


def build_mira():
    fresh('/Game/Practica3/UI/WBP_Mira')
    umg('CreateWidgetBlueprint', folderPath='/Game/Practica3/UI', assetName='WBP_Mira', parentClass=ref('/Script/UMG.UserWidget'))
    wbp = unreal.load_asset('/Game/Practica3/UI/WBP_Mira')

    def add(cls, name, parent=None):
        kw = dict(widgetBlueprint=ref(wbp), widgetClass=ref(cls), widgetDisplayName=name)
        if parent is not None:
            kw['parentWidget'] = ref(parent)
        res = umg('AddWidget', **kw)
        info = res.get('returnValue', res)
        pw = lambda x: x.get('refPath') if isinstance(x, dict) else x  # noqa: E731
        w = unreal.load_object(None, pw(info['widget']))
        s = unreal.load_object(None, pw(info['slot'])) if pw(info.get('slot')) else None
        return w, s

    ov, _ = add('/Script/UMG.Overlay', 'Raiz')

    def text(name, txt, size, h, v, pad):
        t, s = add('/Script/UMG.TextBlock', name, ov)
        t.set_editor_property('text', txt)
        f = t.get_editor_property('font')
        f.set_editor_property('size', size)
        t.set_editor_property('font', f)
        t.set_editor_property('shadow_offset', unreal.Vector2D(2, 2))
        t.set_editor_property('shadow_color_and_opacity', unreal.LinearColor(0, 0, 0, 1))
        s.set_editor_property('horizontal_alignment', h)
        s.set_editor_property('vertical_alignment', v)
        s.set_editor_property('padding', pad)

    text('Mira', '+', 28, unreal.HorizontalAlignment.H_ALIGN_CENTER, unreal.VerticalAlignment.V_ALIGN_CENTER, unreal.Margin(0, 0, 0, 0))
    text('Ayuda', 'WASD + raton: moverse   |   E / Q: subir / bajar\n'
         'Clic izquierdo: agarrar / soltar   |   Clic derecho: lanzar lo que sostienes\n'
         'Botones REINICIAR: acerca la mano (la bolita cian) a la seta roja',
         14, unreal.HorizontalAlignment.H_ALIGN_LEFT, unreal.VerticalAlignment.V_ALIGN_BOTTOM, unreal.Margin(20, 0, 0, 20))
    umg('CompileWidgetBlueprint', widgetBlueprint=ref(wbp))
    EAL.save_loaded_asset(wbp)
    log('WBP_Mira OK')


# ---------------------------------------------------------------- jugador de PC

def add_comp(bp, name, cls, parent, props):
    h, fail = SUB.add_new_subobject(unreal.AddNewSubobjectParams(parent_handle=parent, new_class=cls, blueprint_context=bp))
    SUB.rename_subobject(h, name)
    o = unreal.SubobjectDataBlueprintFunctionLibrary.get_object(SUB.k2_find_subobject_data_from_handle(h))
    for k, v in props.items():
        try:
            o.set_editor_property(k, v)
        except Exception as e:  # noqa
            log('PROP FAIL', name, k, e)
    return h, o


def bind_names(g, type_id, wanted):
    ni = BT.get_node_type_pins(g, type_id)
    order = [p.name for p in ni.output_pins if p.type_id != 'Exec']
    return '(' + ' '.join(wanted.get(p, '_' + p.lower().replace(' ', '')) for p in order) + ')'


def build_player():
    for n in ['BP_JugadorPC', 'BP_GameModePC']:
        fresh(f'{BPDIR}/{n}')
    bp = BT.create(BPDIR, 'BP_JugadorPC', unreal.DefaultPawn.static_class())
    p3dsl.CLASSES['BP_JugadorPC'] = f'{BPDIR}/BP_JugadorPC.BP_JugadorPC_C'
    hs = SUB.k2_gather_subobject_data_for_blueprint(bp)
    root = hs[1] if len(hs) > 1 else hs[0]
    hc, cam = add_comp(bp, 'Camara', unreal.CameraComponent, root, {
        'relative_location': unreal.Vector(0, 0, 60), 'use_pawn_control_rotation': True})
    hm, mano = add_comp(bp, 'Mano', unreal.MotionControllerComponent, hc, {
        'relative_location': unreal.Vector(55, 15, -20), 'motion_source': 'Practica3PC'})
    _, vis = add_comp(bp, 'ManoVisual', unreal.StaticMeshComponent, hm, {
        'static_mesh': unreal.load_asset('/Engine/BasicShapes/Sphere'),
        'relative_scale3d': unreal.Vector(0.05, 0.05, 0.05)})
    vis.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
    vis.set_material(0, unreal.load_asset(MAT + 'MI_Neon_Cian'))

    BT.add_object_variable(bp, 'Sostenido', unreal.load_class(None, GRAB))
    BT.add_variable(bp, 'Sosteniendo', 'bool')
    BT.add_object_variable(bp, 'ActorLanzado', unreal.Actor.static_class())
    for f in ['Agarrar', 'Soltar', 'AplicarLanzamiento']:
        BT.add_function_graph(bp, f)
    BT.compile_blueprint(bp)

    W = p3dsl.write
    ga = BT.get_graph(bp, 'Agarrar')
    lt = bind_names(ga, 'Collision|LineTraceByChannel', {'OutHit': 'hit', 'ReturnValue': 'ok'})
    bh = bind_names(ga, 'Collision|BreakHitResult', {'HitActor': 'actor'})
    W(ga, f'''
(fn Agarrar ()
  (bind start (Transformation|GetWorldLocation :self (Get|Camara)))
  (bind end (+ start (* (Transformation|GetForwardVector :self (Get|Camara)) 300.0)))
  (bind {lt} (Collision|LineTraceByChannel :Start start :End end :TraceChannel "Visibility" :bIgnoreSelf true))
  (if ok
    (bind {bh} (Collision|BreakHitResult :Hit hit))
    (bind comp (Actor|GetComponentbyClass :self actor :ComponentClass "{GRAB}"))
    (bind g (CastTo|BP_GrabComponent :Object comp)
      (:then
        (bind okg (CallOf|BP_GrabComponent|TryGrab :self g :MotionController (Get|Mano)))
        (if okg
          (Set|Sostenido g)
          (Set|Sosteniendo true)
          (Transformation|SetWorldLocation :self (Transformation|GetAttachParent :self g) :NewLocation (Transformation|GetWorldLocation :self (Get|Mano)) :bTeleport true)))
      (:CastFailed))))''', 'PC.Agarrar')
    W(BT.get_graph(bp, 'Soltar'), '''
(fn Soltar ()
  (CallOf|BP_GrabComponent|TryRelease :self (Get|Sostenido))
  (Set|Sosteniendo false))''', 'PC.Soltar')
    W(BT.get_graph(bp, 'AplicarLanzamiento'), '''
(fn AplicarLanzamiento ()
  (bind root (Fn|/Script/Engine.Actor:K2_GetRootComponent :self (Get|ActorLanzado)))
  (bind p (Utilities|Casting|CastToPrimitiveComponent :Object root)
    (:then
      (Physics|SetSimulatePhysics :self p :bSimulate true)
      (Physics|SetPhysicsLinearVelocity :self p :NewVel (+ (* (Transformation|GetForwardVector :self (Get|Camara)) 900.0) (Math|Vector|MakeVector :X 0.0 :Y 0.0 :Z 80.0)))
      (bind d (CastTo|BP_Dardo :Object (Get|ActorLanzado))
        (:then
          (SetOf|BP_Dardo|Lanzado :self d :Lanzado true)
          (SetOf|BP_Dardo|TLanzado :self d :TLanzado (Utilities|Time|GetGameTimeinSeconds)))
        (:CastFailed)))
    (:CastFailed)))''', 'PC.Lanzar')
    md = bind_names(BT.get_graph(bp, 'EventGraph'), 'Game|Player|GetInputMouseDelta', {'DeltaX': 'mx', 'DeltaY': 'my'})
    log('mouse delta', md)
    W(BT.get_graph(bp, 'EventGraph'), '''
(event EventBeginPlay
  (bind w (UserInterface|CreateWidget :Class "/Game/Practica3/UI/WBP_Mira.WBP_Mira_C" :OwningPlayer (Game|GetPlayerController :PlayerIndex 0)))
  (UserInterface|Viewport|AddtoViewport :self w)
  (bind fm (Utilities|Casting|CastToFloatingPawnMovement :Object (Fn|/Script/Engine.Pawn:GetMovementComponent))
    (:then (SetOf|/Script/Engine.FloatingPawnMovement|MaxSpeed :self fm :MaxSpeed 900.0))
    (:CastFailed)))
(event EventTick (DeltaSeconds)
  (bind pc (Game|GetPlayerController :PlayerIndex 0))
  (bind fwd (Transformation|GetForwardVector :self (Get|Camara)))
  (bind rgt (Transformation|GetRightVector :self (Get|Camara)))
  (bind ax (- (select (Game|Player|IsInputKeyDown :self pc :Key "W") 1.0 0.0) (select (Game|Player|IsInputKeyDown :self pc :Key "S") 1.0 0.0)))
  (bind ay (- (select (Game|Player|IsInputKeyDown :self pc :Key "D") 1.0 0.0) (select (Game|Player|IsInputKeyDown :self pc :Key "A") 1.0 0.0)))
  (bind az (- (select (Game|Player|IsInputKeyDown :self pc :Key "E") 1.0 0.0) (select (Game|Player|IsInputKeyDown :self pc :Key "Q") 1.0 0.0)))
  (Pawn|Input|AddMovementInput :WorldDirection fwd :ScaleValue ax)
  (Pawn|Input|AddMovementInput :WorldDirection rgt :ScaleValue ay)
  (Pawn|Input|AddMovementInput :WorldDirection (Math|Vector|MakeVector :X 0.0 :Y 0.0 :Z 1.0) :ScaleValue az)
  (bind __MOUSE__ (Game|Player|GetInputMouseDelta :self pc))
  (Pawn|Input|AddControllerYawInput :Val mx)
  (Pawn|Input|AddControllerPitchInput :Val (- my))
  (if (Game|Player|WasInputKeyJustPressed :self pc :Key "LeftMouseButton")
    (if (Get|Sosteniendo)
      (Call|Soltar)
      (else (Call|Agarrar))))
  (if (and (Get|Sosteniendo) (Game|Player|WasInputKeyJustPressed :self pc :Key "RightMouseButton"))
    (Set|ActorLanzado (Fn|/Script/Engine.ActorComponent:GetOwner :self (Get|Sostenido)))
    (Call|Soltar)
    (Utilities|Time|SetTimerbyFunctionName :Object self :FunctionName "AplicarLanzamiento" :Time 0.06 :bLooping false)))'''.replace('__MOUSE__', md), 'PC.Events')
    p3dsl.compile_and_report(bp)
    pcdo = unreal.get_default_object(unreal.BlueprintEditorLibrary.generated_class(bp))
    try:
        pcdo.set_editor_property('add_default_movement_bindings', False)
    except Exception as e:  # noqa
        log('bindings', e)
    BT.compile_blueprint(bp)
    EAL.save_loaded_asset(bp)

    gm = BT.create(BPDIR, 'BP_GameModePC', unreal.GameModeBase.static_class())
    BT.compile_blueprint(gm)
    cdo = unreal.get_default_object(unreal.BlueprintEditorLibrary.generated_class(gm))
    cdo.set_editor_property('default_pawn_class', unreal.BlueprintEditorLibrary.generated_class(bp))
    BT.compile_blueprint(gm)
    EAL.save_loaded_asset(gm)
    log('jugador PC OK')
    return gm


def main():
    try:
        fix_materials()
    except Exception:
        log('MAT FAIL', traceback.format_exc())
    try:
        unreal.EditorLoadingAndSavingUtils.load_map(VR_MAP)
        fix_lights_in_current_level()
        unreal.EditorLoadingAndSavingUtils.save_current_level()
    except Exception:
        log('LUZ FAIL', traceback.format_exc())
    try:
        build_mira()
        gm = build_player()
        fresh(PC_MAP)
        if not EAL.duplicate_asset(VR_MAP, PC_MAP):
            log('DUPLICATE FAIL')
        unreal.EditorLoadingAndSavingUtils.load_map(PC_MAP)
        ws = unreal.EditorLevelLibrary.get_editor_world().get_world_settings()
        ws.set_editor_property('default_game_mode', unreal.BlueprintEditorLibrary.generated_class(gm))
        unreal.EditorLoadingAndSavingUtils.save_current_level()
        log('mapa PC OK')
    except Exception:
        log('PC FAIL', traceback.format_exc())
    log('ERRORES DSL:', len(p3dsl.ERRORS))
    for e in p3dsl.ERRORS:
        log(e)
    open(os.path.join(TOOLS, 'build_pc.txt'), 'w', encoding='utf-8').write('\n'.join(LOG))


main()
