"""Correcciones v3: jugador de PC con gravedad, martillo/piñata, paneles de puntos y punto de aparición."""
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
SUB = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
BPDIR = '/Game/Practica3/Blueprints'
MAT = '/Game/Practica3/Materiales/'
GRAB = '/Game/XRFramework/Blueprints/BP_GrabComponent.BP_GrabComponent_C'
MAPS = ['/Game/Practica3/L_Practica3_VR', '/Game/Practica3/L_Practica3_PC']
p3dsl.CLASSES.update({
    'BP_GrabComponent': GRAB,
    'BP_Dardo': f'{BPDIR}/BP_Dardo.BP_Dardo_C',
    'BP_RompeRalph': f'{BPDIR}/BP_RompeRalph.BP_RompeRalph_C',
})


def obj_of(h):
    return unreal.SubobjectDataBlueprintFunctionLibrary.get_object(SUB.k2_find_subobject_data_from_handle(h))


def add_comp(bp, name, cls, parent, props):
    h, _ = SUB.add_new_subobject(unreal.AddNewSubobjectParams(parent_handle=parent, new_class=cls, blueprint_context=bp))
    SUB.rename_subobject(h, name)
    o = obj_of(h)
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


def clear_graph(g):
    ed = unreal.BlueprintGraphEditor.get_graph_editor(g)
    nodes = list(ed.list_all_nodes())
    if nodes:
        ed.remove_nodes(nodes)


# ---------------------------------------------------------------- jugador con gravedad

def build_player():
    for n in ['BP_PersonajePC', 'BP_ModoJuegoPC']:
        if EAL.does_asset_exist(f'{BPDIR}/{n}'):
            EAL.delete_asset(f'{BPDIR}/{n}')
    bp = unreal.BlueprintEditorLibrary.create_blueprint_asset_with_parent(f'{BPDIR}/BP_PersonajePC', unreal.Character.static_class())
    log('bp', bp)
    p3dsl.CLASSES['BP_PersonajePC'] = f'{BPDIR}/BP_PersonajePC.BP_PersonajePC_C'
    BT.compile_blueprint(bp)
    log('handles', len(SUB.k2_gather_subobject_data_for_blueprint(bp)))
    capsule = None
    F = unreal.SubobjectDataBlueprintFunctionLibrary
    for h in SUB.k2_gather_subobject_data_for_blueprint(bp):
        d = SUB.k2_find_subobject_data_from_handle(h)
        if F.is_root_component(d):
            capsule = h
    if capsule is None:
        capsule = SUB.k2_gather_subobject_data_for_blueprint(bp)[0]  # actor: cuelga de la raiz (capsula)
    log('root handle', capsule is not None)
    hc, _ = add_comp(bp, 'Camara', unreal.CameraComponent, capsule, {
        'relative_location': unreal.Vector(0, 0, 64), 'use_pawn_control_rotation': True})
    hm, _ = add_comp(bp, 'Mano', unreal.MotionControllerComponent, hc, {
        'relative_location': unreal.Vector(55, 15, -20), 'motion_source': 'Practica3PC'})
    _, vis = add_comp(bp, 'ManoVisual', unreal.StaticMeshComponent, hm, {
        'static_mesh': unreal.load_asset('/Engine/BasicShapes/Sphere'),
        'relative_scale3d': unreal.Vector(0.05, 0.05, 0.05)})
    vis.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
    vis.set_material(0, unreal.load_asset(MAT + 'MI_Neon_Cian'))

    BT.add_object_variable(bp, 'Sostenido', unreal.load_class(None, GRAB))
    BT.add_variable(bp, 'Sosteniendo', 'bool')
    BT.add_object_variable(bp, 'ActorLanzado', unreal.Actor.static_class())
    BT.add_object_variable(bp, 'ActorSostenido', unreal.Actor.static_class())
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
          (Set|ActorSostenido actor)
          (Fn|/Script/Engine.PrimitiveComponent:IgnoreActorWhenMoving :self (Get|CapsuleComponent) :Actor actor :bShouldIgnore true)
          (Transformation|SetWorldLocation :self (Transformation|GetAttachParent :self g) :NewLocation (Transformation|GetWorldLocation :self (Get|Mano)) :bTeleport true)))
      (:CastFailed))))''', 'PC.Agarrar')
    W(BT.get_graph(bp, 'Soltar'), '''
(fn Soltar ()
  (CallOf|BP_GrabComponent|TryRelease :self (Get|Sostenido))
  (Fn|/Script/Engine.PrimitiveComponent:IgnoreActorWhenMoving :self (Get|CapsuleComponent) :Actor (Get|ActorSostenido) :bShouldIgnore false)
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
    ge = BT.get_graph(bp, 'EventGraph')
    md = bind_names(ge, 'Game|Player|GetInputMouseDelta', {'DeltaX': 'mx', 'DeltaY': 'my'})
    W(ge, f'''
(event EventBeginPlay
  (bind w (UserInterface|CreateWidget :Class "/Game/Practica3/UI/WBP_Mira.WBP_Mira_C" :OwningPlayer (Game|GetPlayerController :PlayerIndex 0)))
  (UserInterface|Viewport|AddtoViewport :self w)
  (SetOf|/Script/Engine.CharacterMovementComponent|MaxWalkSpeed :self (Get|CharacterMovement) :MaxWalkSpeed 700.0))
(event EventTick (DeltaSeconds)
  (bind pc (Game|GetPlayerController :PlayerIndex 0))
  (bind ax (- (select (Game|Player|IsInputKeyDown :self pc :Key "W") 1.0 0.0) (select (Game|Player|IsInputKeyDown :self pc :Key "S") 1.0 0.0)))
  (bind ay (- (select (Game|Player|IsInputKeyDown :self pc :Key "D") 1.0 0.0) (select (Game|Player|IsInputKeyDown :self pc :Key "A") 1.0 0.0)))
  (Pawn|Input|AddMovementInput :WorldDirection (Transformation|GetActorForwardVector) :ScaleValue ax)
  (Pawn|Input|AddMovementInput :WorldDirection (Transformation|GetActorRightVector) :ScaleValue ay)
  (bind {md} (Game|Player|GetInputMouseDelta :self pc))
  (Pawn|Input|AddControllerYawInput :Val mx)
  (Pawn|Input|AddControllerPitchInput :Val (- my))
  (if (Game|Player|WasInputKeyJustPressed :self pc :Key "SpaceBar")
    (Character|Jump))
  (if (Game|Player|WasInputKeyJustPressed :self pc :Key "LeftMouseButton")
    (if (Get|Sosteniendo)
      (Call|Soltar)
      (else (Call|Agarrar))))
  (if (and (Get|Sosteniendo) (Game|Player|WasInputKeyJustPressed :self pc :Key "RightMouseButton"))
    (Set|ActorLanzado (Get|ActorSostenido))
    (Call|Soltar)
    (Utilities|Time|SetTimerbyFunctionName :Object self :FunctionName "AplicarLanzamiento" :Time 0.06 :bLooping false)))''', 'PC.Events')
    p3dsl.compile_and_report(bp)
    EAL.save_loaded_asset(bp)

    gm = unreal.BlueprintEditorLibrary.create_blueprint_asset_with_parent(f'{BPDIR}/BP_ModoJuegoPC', unreal.GameModeBase.static_class())
    BT.compile_blueprint(gm)
    cdo = unreal.get_default_object(unreal.BlueprintEditorLibrary.generated_class(gm))
    cdo.set_editor_property('default_pawn_class', unreal.BlueprintEditorLibrary.generated_class(bp))
    BT.compile_blueprint(gm)
    EAL.save_loaded_asset(gm)
    log('jugador PC (Character) OK')
    return gm


# ---------------------------------------------------------------- piñata y martillo

def fix_pinata_and_hammer():
    pin = unreal.load_asset(f'{BPDIR}/BP_Pinata')
    for h in SUB.k2_gather_subobject_data_for_blueprint(pin):
        o = obj_of(h)
        if isinstance(o, unreal.GeometryCollectionComponent):
            o.set_editor_property('object_type', unreal.ObjectStateTypeEnum.CHAOS_OBJECT_KINEMATIC)
            log('pinata kinematic')
    BT.compile_blueprint(pin)
    EAL.save_loaded_asset(pin)

    ma = unreal.load_asset(f'{BPDIR}/BP_Martillo')
    g = BT.get_graph(ma, 'EventGraph')
    clear_graph(g)
    bb = bind_names(g, 'Collision|GetComponentBounds', {'Origin': 'org', 'BoxExtent': 'ext', 'SphereRadius': 'rad'})
    p3dsl.write(g, f'''
(event EventTick (DeltaSeconds)
  (Call|ActualizarLanzamiento :DT DeltaSeconds)
  (bind hp (Transformation|GetWorldLocation :self (Get|Cabeza)))
  (bind hv (/ (- hp (Get|PosCabAnt)) (Math|Float|Max(Float) :A DeltaSeconds :B 0.001)))
  (Set|PosCabAnt hp)
  (bind spd (Math|Vector|VectorLength :A hv))
  (bind now (Utilities|Time|GetGameTimeinSeconds))
  (if (and (> spd 150.0) (> (- now (Get|TGolpe)) 0.25))
    (bind obj (GetOf|BP_RompeRalph|Objetivo :self (Get|Estacion)))
    (bind comp (Actor|GetComponentbyClass :self obj :ComponentClass "/Script/GeometryCollectionEngine.GeometryCollectionComponent"))
    (bind gc (Utilities|Casting|CastToGeometryCollectionComponent :Object comp)
      (:then
        (bind {bb} (Collision|GetComponentBounds :Component gc))
        (if (< (Math|Vector|Distance(Vector) :V1 hp :V2 org) (+ (* rad 0.8) 10.0))
          (Set|TGolpe now)
          (bind f (Math|Float|Clamp(Float) :Value (/ spd 400.0) :Min 0.5 :Max 3.0))
          (Field|SetDynamicState :self (Get|Campo) :Enabled true :Position org :Radius 250.0)
          (Field|ApplyExternalStrain :self (Get|Campo) :Enabled true :Position hp :Radius (* 40.0 f) :Magnitude (* 5000000.0 f) :Iterations 3)
          (ChaosPhysics|CrumbleActiveClusters :self gc)
          (Field|FalloffUniformForce :self (Get|Campo) :Enabled true :Position hp :Direction (Math|Vector|Normalize :A hv) :Radius 60.0 :Magnitude (* 4000.0 f))
          (CallOf|BP_RompeRalph|RegistrarGolpe :self (Get|Estacion) :Vel spd)))
      (:CastFailed))))''', 'Martillo.Tick')
    p3dsl.compile_and_report(ma)
    EAL.save_loaded_asset(ma)
    log('martillo OK')


# ---------------------------------------------------------------- mapas

def comp(actor, name):
    for c in actor.get_components_by_class(unreal.SceneComponent):
        if c.get_name() == name:
            return c
    return None


def fix_maps(gm_class):
    for m in MAPS:
        unreal.EditorLoadingAndSavingUtils.load_map(m)
        for a in unreal.EditorLevelLibrary.get_all_level_actors():
            lbl = a.get_actor_label()
            if isinstance(a, unreal.PlayerStart):
                a.modify()
                loc = a.get_actor_location()
                a.set_actor_location(unreal.Vector(loc.x, loc.y, 100.0), False, True)
                log(m, 'PlayerStart z=100')
            if lbl in ('Bolera_Estacion', 'Dardos_Diana'):
                mk = comp(a, 'Marcador')
                a.modify()
                mk.modify()
                if lbl == 'Bolera_Estacion':
                    loc, yaw = unreal.Vector(700, 140, 170), 137.0
                else:
                    loc, yaw = unreal.Vector(1380, -140, 170), -126.0
                mk.set_world_location_and_rotation(loc, unreal.Rotator(0, 0, yaw), False, True)
                mk.set_world_scale3d(unreal.Vector(0.12, 0.12, 0.12))
                log(m, lbl, 'marcador recolocado')
        if m.endswith('_PC') and gm_class:
            ws = unreal.EditorLevelLibrary.get_editor_world().get_world_settings()
            ws.set_editor_property('default_game_mode', gm_class)
        unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
        log(m, 'guardado')


def main_player_only():
    gm = build_player()
    unreal.EditorLoadingAndSavingUtils.load_map('/Game/Practica3/L_Practica3_PC')
    ws = unreal.EditorLevelLibrary.get_editor_world().get_world_settings()
    ws.set_editor_property('default_game_mode', unreal.BlueprintEditorLibrary.generated_class(gm))
    unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
    log('GM PC asignado')


def main():
    gm = None
    try:
        gm = build_player()
    except Exception:
        log('PLAYER FAIL', traceback.format_exc())
    try:
        fix_pinata_and_hammer()
    except Exception:
        log('HAMMER FAIL', traceback.format_exc())
    try:
        fix_maps(unreal.BlueprintEditorLibrary.generated_class(gm) if gm else None)
    except Exception:
        log('MAPS FAIL', traceback.format_exc())
    log('ERRORES DSL:', len(p3dsl.ERRORS))
    for e in p3dsl.ERRORS:
        log(e)
    open(os.path.join(TOOLS, 'fix_v3.txt'), 'w', encoding='utf-8').write('\n'.join(LOG))


if os.environ.get('P3_SOLO_JUGADOR'):
    try:
        main_player_only()
    except Exception:
        log('PLAYER FAIL', traceback.format_exc())
    log('ERRORES DSL:', len(p3dsl.ERRORS))
    for e in p3dsl.ERRORS:
        log(e)
    open(os.path.join(TOOLS, 'fix_v3.txt'), 'w', encoding='utf-8').write(chr(10).join(LOG))
else:
    main()
