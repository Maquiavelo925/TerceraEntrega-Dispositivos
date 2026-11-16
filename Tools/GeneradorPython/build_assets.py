"""Genera todos los assets de la Práctica 3 (materiales, widget, Blueprints, fractura).

Ejecutar con:
  UnrealEditor-Cmd.exe Practica3.uproject -run=pythonscript -script=build_assets.py -culture=en -NullRHI
"""
import json
import math
import os
import sys
import traceback

import unreal

TOOLS = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()), 'Tools', 'GeneradorPython')
sys.path.insert(0, TOOLS)
import p3dsl  # noqa: E402
from p3dsl import BT  # noqa: E402
from editor_toolset.toolsets.blueprint import ContainerType  # noqa: E402

LOG = []


def log(*a):
    LOG.append(' '.join(str(x) for x in a))
    unreal.log(' '.join(str(x) for x in a))


ROOT = '/Game/Practica3'
BPDIR = ROOT + '/Blueprints'
UIDIR = ROOT + '/UI'
MATDIR = ROOT + '/Materiales'
FXDIR = ROOT + '/Fractura'

EAL = unreal.EditorAssetLibrary
AT = unreal.AssetToolsHelpers.get_asset_tools()
SUB = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
MEL = unreal.MaterialEditingLibrary

GRAB_CLASS = unreal.load_asset('/Game/XRFramework/Blueprints/BP_GrabComponent').generated_class()
CYL = '/Game/LevelPrototyping/Meshes/SM_Cylinder'
CUBE = '/Game/LevelPrototyping/Meshes/SM_ChamferCube'

# ---------------------------------------------------------------- utilidades


def fresh(path):
    if EAL.does_asset_exist(path):
        EAL.delete_asset(path)


def cls_path(name, folder=BPDIR):
    return f'{folder}/{name}.{name}_C'


def new_bp(name, parent):
    fresh(f'{BPDIR}/{name}')
    bp = BT.create(BPDIR, name, parent.static_class() if hasattr(parent, 'static_class') else parent)
    p3dsl.CLASSES[name] = cls_path(name)
    return bp


def handles(bp):
    return SUB.k2_gather_subobject_data_for_blueprint(bp)


def root_handle(bp):
    return handles(bp)[0]


def comp_obj(h):
    data = SUB.k2_find_subobject_data_from_handle(h)
    return unreal.SubobjectDataBlueprintFunctionLibrary.get_object(data)


def add_comp(bp, name, cls, parent=None, props=None):
    parent = parent or root_handle(bp)
    h, fail = SUB.add_new_subobject(unreal.AddNewSubobjectParams(parent_handle=parent, new_class=cls, blueprint_context=bp))
    if str(fail):
        log('ADD COMP FAIL', bp.get_name(), name, fail)
    SUB.rename_subobject(h, name)
    obj = comp_obj(h)
    for k, v in (props or {}).items():
        try:
            obj.set_editor_property(k, v)
        except Exception as e:  # noqa
            log('PROP FAIL', bp.get_name(), name, k, e)
    return h, obj


def physics(obj, simulate=True, mass=0.0, ccd=False, notify=False, profile='PhysicsActor'):
    bi = obj.get_editor_property('body_instance')
    for k, v in [('simulate_physics', simulate), ('use_ccd', ccd), ('notify_rigid_body_collision', notify)]:
        try:
            bi.set_editor_property(k, v)
        except Exception as e:  # noqa
            log('BI FAIL', k, e)
    if mass > 0:
        for k, v in [('override_mass', True), ('mass_in_kg_override', mass)]:
            try:
                bi.set_editor_property(k, v)
            except Exception as e:  # noqa
                log('BI FAIL', k, e)
    try:
        bi.set_editor_property('collision_profile_name', profile)
    except Exception as e:  # noqa
        log('BI FAIL profile', e)
    obj.set_editor_property('body_instance', bi)
    try:
        obj.set_editor_property('mobility', unreal.ComponentMobility.MOVABLE)
    except Exception:
        pass


def var(bp, name, typ, editable=False, container=None):
    if container:
        BT.add_variable(bp, name, typ, None, container)
    else:
        BT.add_variable(bp, name, typ)
    if editable:
        unreal.BlueprintEditorLibrary.set_blueprint_variable_instance_editable(bp, name, True)


def ovar(bp, name, cls, editable=False, array=False):
    c = cls if isinstance(cls, unreal.Class) else unreal.load_class(None, cls)
    if array:
        BT.add_object_variable(bp, name, c, None, ContainerType.ARRAY)
    else:
        BT.add_object_variable(bp, name, c)
    if editable:
        unreal.BlueprintEditorLibrary.set_blueprint_variable_instance_editable(bp, name, True)


def fn(bp, name, inputs=(), outputs=()):
    g = BT.add_function_graph(bp, name)
    for pname, ptype in inputs:
        if isinstance(ptype, str) and ptype.startswith('/'):
            BT.add_object_function_param(g, pname, unreal.load_class(None, ptype), True)
        else:
            BT.add_function_param(g, pname, ptype, True)
    for pname, ptype in outputs:
        BT.add_function_param(g, pname, ptype, False)
    return g


def graph(bp, name):
    return BT.get_graph(bp, name)


def compile_bp(bp):
    try:
        BT.compile_blueprint(bp)
    except Exception as e:  # noqa
        log('COMPILE EXC', bp.get_name(), e)


def outs_order(g, type_id):
    ni = BT.get_node_type_pins(g, type_id)
    return [p.name for p in ni.output_pins if p.type_id != 'Exec']


def bind_names(g, type_id, wanted):
    """Devuelve '(a b c)' según el orden real de los pines de salida."""
    order = outs_order(g, type_id)
    names = []
    for pin in order:
        names.append(wanted.get(pin, '_' + pin.lower().replace(' ', '')))
    return '(' + ' '.join(names) + ')'


def set_cdo(bp, values):
    compile_bp(bp)
    cdo = unreal.get_default_object(unreal.BlueprintEditorLibrary.generated_class(bp))
    for k, v in values.items():
        try:
            cdo.set_editor_property(k, v)
        except Exception as e:  # noqa
            log('CDO FAIL', bp.get_name(), k, e)


# ---------------------------------------------------------------- materiales


def make_material(name, color_param=True, unlit=False, translucent=False, emissive_mult=1.0, opacity=1.0):
    path = f'{MATDIR}/{name}'
    fresh(path)
    m = AT.create_asset(name, MATDIR, unreal.Material, unreal.MaterialFactoryNew())
    if unlit:
        m.set_editor_property('shading_model', unreal.MaterialShadingModel.MSM_UNLIT)
    if translucent:
        m.set_editor_property('blend_mode', unreal.BlendMode.BLEND_TRANSLUCENT)
    col = MEL.create_material_expression(m, unreal.MaterialExpressionVectorParameter, -600, 0)
    col.set_editor_property('parameter_name', 'Color')
    col.set_editor_property('default_value', unreal.LinearColor(1, 1, 1, 1))
    if unlit:
        mul = MEL.create_material_expression(m, unreal.MaterialExpressionMultiply, -300, 0)
        mul.set_editor_property('const_b', emissive_mult)
        MEL.connect_material_expressions(col, '', mul, 'A')
        MEL.connect_material_property(mul, '', unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    else:
        MEL.connect_material_property(col, '', unreal.MaterialProperty.MP_BASE_COLOR)
        r = MEL.create_material_expression(m, unreal.MaterialExpressionScalarParameter, -600, 200)
        r.set_editor_property('parameter_name', 'Roughness')
        r.set_editor_property('default_value', 0.5)
        MEL.connect_material_property(r, '', unreal.MaterialProperty.MP_ROUGHNESS)
        me = MEL.create_material_expression(m, unreal.MaterialExpressionScalarParameter, -600, 300)
        me.set_editor_property('parameter_name', 'Metallic')
        me.set_editor_property('default_value', 0.0)
        MEL.connect_material_property(me, '', unreal.MaterialProperty.MP_METALLIC)
    if translucent:
        o = MEL.create_material_expression(m, unreal.MaterialExpressionConstant, -300, 300)
        o.set_editor_property('r', opacity)
        MEL.connect_material_property(o, '', unreal.MaterialProperty.MP_OPACITY)
    MEL.recompile_material(m)
    EAL.save_loaded_asset(m)
    return m


def make_mi(name, parent, color, rough=None, metal=None):
    path = f'{MATDIR}/{name}'
    fresh(path)
    mi = AT.create_asset(name, MATDIR, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
    MEL.set_material_instance_parent(mi, parent)
    MEL.set_material_instance_vector_parameter_value(mi, 'Color', unreal.LinearColor(*color))
    if rough is not None:
        MEL.set_material_instance_scalar_parameter_value(mi, 'Roughness', rough)
    if metal is not None:
        MEL.set_material_instance_scalar_parameter_value(mi, 'Metallic', metal)
    EAL.save_loaded_asset(mi)
    return mi


def build_materials():
    base = make_material('M_P3_Color')
    neon = make_material('M_P3_Neon', unlit=True, emissive_mult=6.0)
    make_material('M_P3_Resaltado', unlit=True, translucent=True, emissive_mult=2.0, opacity=0.35)
    mats = {
        'MI_Madera': (base, (0.36, 0.2, 0.09, 1), 0.6, 0.0),
        'MI_MaderaPista': (base, (0.75, 0.52, 0.3, 1), 0.25, 0.0),
        'MI_Metal': (base, (0.55, 0.57, 0.6, 1), 0.25, 1.0),
        'MI_Rojo': (base, (0.8, 0.03, 0.03, 1), 0.4, 0.0),
        'MI_Moqueta': (base, (0.06, 0.03, 0.12, 1), 0.95, 0.0),
        'MI_Pared': (base, (0.09, 0.08, 0.14, 1), 0.85, 0.0),
        'MI_Negro': (base, (0.02, 0.02, 0.025, 1), 0.7, 0.0),
        'MI_Corcho': (base, (0.45, 0.32, 0.18, 1), 0.9, 0.0),
    }
    for n, (p, c, r, me) in mats.items():
        make_mi(n, p, c, r, me)
    neons = {
        'MI_Neon_Cian': (0.1, 0.8, 1.0, 1),
        'MI_Neon_Rosa': (1.0, 0.1, 0.6, 1),
        'MI_Neon_Naranja': (1.0, 0.45, 0.05, 1),
        'MI_Neon_Violeta': (0.6, 0.2, 1.0, 1),
        'MI_Neon_Rojo': (1.0, 0.1, 0.05, 1),
        'MI_Neon_Verde': (0.2, 1.0, 0.3, 1),
    }
    for n, c in neons.items():
        make_mi(n, neon, c)
    log('materiales OK')


# ---------------------------------------------------------------- colisiones de mallas


def mesh_collisions():
    sml = unreal.EditorStaticMeshLibrary
    sub = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem) if hasattr(unreal, 'StaticMeshEditorSubsystem') else None

    def lib():
        return sub or sml

    def convex(path, hulls=4, verts=16, prec=100000):
        m = unreal.load_asset(path)
        try:
            lib().remove_collisions(m)
        except Exception:
            pass
        ok = lib().set_convex_decomposition_collisions(m, hulls, verts, prec)
        EAL.save_loaded_asset(m)
        return ok

    def simple(path, shape):
        m = unreal.load_asset(path)
        try:
            lib().remove_collisions(m)
        except Exception:
            pass
        lib().add_simple_collisions(m, shape)
        EAL.save_loaded_asset(m)

    simple('/Game/mesh/bolos/bowling', unreal.ScriptCollisionShapeType.SPHERE)
    convex('/Game/mesh/bolos/bowling_pin_ball', 4, 16)
    convex('/Game/mesh/dardos/SM_DartboardDarts_Cylinder_001', 2, 12)
    simple('/Game/mesh/dardos/SM_DartboardDarts_Cylinder', unreal.ScriptCollisionShapeType.BOX)
    simple('/Game/mesh/pinata/pinata_mesh', unreal.ScriptCollisionShapeType.BOX)
    for a in unreal.AssetRegistryHelpers.get_asset_registry().get_assets_by_path('/Game/mesh/Mr_Potato', recursive=False):
        if str(a.asset_class_path.asset_name) == 'StaticMesh':
            p = str(a.package_name)
            convex(p, 6 if 'Cuerpo' in p else 2, 16)
    log('colisiones OK')


# ---------------------------------------------------------------- widget


def umg(tool, **kw):
    r = unreal.ToolsetRegistry.execute_tool('UMGToolSet.UMGToolSet', tool, json.dumps(kw))
    if r.error:
        raise RuntimeError(f'UMG {tool}: {r.error}')
    v = r.value
    return json.loads(v) if isinstance(v, str) and v else v


def ref(obj_or_path):
    p = obj_or_path if isinstance(obj_or_path, str) else obj_or_path.get_path_name()
    return {'refPath': p}


def build_widget():
    fresh(f'{UIDIR}/WBP_Marcador')
    res = umg('CreateWidgetBlueprint', folderPath=UIDIR, assetName='WBP_Marcador', parentClass=ref('/Script/UMG.UserWidget'))
    wbp = unreal.load_asset(f'{UIDIR}/WBP_Marcador')
    p3dsl.CLASSES['WBP_Marcador'] = cls_path('WBP_Marcador', UIDIR)

    def add(cls, name, parent=None):
        kw = dict(widgetBlueprint=ref(wbp), widgetClass=ref(cls), widgetDisplayName=name)
        if parent is not None:
            kw['parentWidget'] = ref(parent)
        res = umg('AddWidget', **kw)
        info = res.get('returnValue', res) if isinstance(res, dict) else res

        def path_of(x):
            if isinstance(x, dict):
                return x.get('refPath')
            return x or None
        w = unreal.load_object(None, path_of(info['widget']))
        sp = path_of(info.get('slot'))
        slot = unreal.load_object(None, sp) if sp else None
        return w, slot

    fondo, _ = add('/Script/UMG.Border', 'Fondo')
    fondo.set_editor_property('brush_color', unreal.LinearColor(0.01, 0.01, 0.03, 0.88))
    fondo.set_editor_property('padding', unreal.Margin(28, 16, 28, 16))
    ov, _ = add('/Script/UMG.Overlay', 'Capas', fondo)
    vb, vslot = add('/Script/UMG.VerticalBox', 'Columna', ov)
    try:
        vslot.set_editor_property('horizontal_alignment', unreal.HorizontalAlignment.H_ALIGN_FILL)
        vslot.set_editor_property('vertical_alignment', unreal.VerticalAlignment.V_ALIGN_CENTER)
    except Exception as e:  # noqa
        log('slot', e)

    def text(name, parent, size, color, bold=True):
        t, s = add('/Script/UMG.TextBlock', name, parent)
        f = t.get_editor_property('font')
        f.set_editor_property('size', size)
        try:
            f.set_editor_property('typeface_font_name', 'Bold' if bold else 'Regular')
        except Exception:
            pass
        t.set_editor_property('font', f)
        t.set_editor_property('color_and_opacity', unreal.SlateColor(unreal.LinearColor(*color)))
        t.set_editor_property('justification', unreal.TextJustify.CENTER)
        t.set_editor_property('auto_wrap_text', True)
        if s is not None:
            try:
                s.set_editor_property('horizontal_alignment', unreal.HorizontalAlignment.H_ALIGN_FILL)
                s.set_editor_property('padding', unreal.Margin(0, 4, 0, 4))
            except Exception:
                pass
        umg('ToggleWidgetAsVariable', widgetBlueprint=ref(wbp), widget=ref(t), bIsVariable=True)
        return t, s

    t1, _ = text('TxtTitulo', vb, 34, (1, 1, 1, 1))
    t1.set_editor_property('text', 'TITULO')
    t2, _ = text('TxtPuntos', vb, 64, (1, 0.85, 0.2, 1))
    t2.set_editor_property('text', '0')
    t3, _ = text('TxtInfo', vb, 22, (0.8, 0.85, 1, 1), bold=False)
    t3.set_editor_property('text', '')
    t4, s4 = text('TxtDestello', ov, 96, (1, 0.3, 0.8, 1))
    t4.set_editor_property('text', '')
    t4.set_editor_property('visibility', unreal.SlateVisibility.COLLAPSED)
    try:
        s4.set_editor_property('horizontal_alignment', unreal.HorizontalAlignment.H_ALIGN_CENTER)
        s4.set_editor_property('vertical_alignment', unreal.VerticalAlignment.V_ALIGN_CENTER)
    except Exception:
        pass
    sh = t4.get_editor_property('shadow_offset')
    t4.set_editor_property('shadow_offset', unreal.Vector2D(4, 4))
    t4.set_editor_property('shadow_color_and_opacity', unreal.LinearColor(0, 0, 0, 0.9))

    umg('CompileWidgetBlueprint', widgetBlueprint=ref(wbp))

    g1 = fn(wbp, 'Actualizar', [('Titulo', 'text'), ('Puntos', 'text'), ('Info', 'text')])
    g2 = fn(wbp, 'Destello', [('Texto', 'text')])
    g3 = fn(wbp, 'OcultarDestello')
    compile_bp(wbp)
    p3dsl.write(g1, '''
(fn Actualizar (Titulo Puntos Info)
  (Widget|SetText(Text) :self (Get|TxtTitulo) :InText Titulo)
  (Widget|SetText(Text) :self (Get|TxtPuntos) :InText Puntos)
  (Widget|SetText(Text) :self (Get|TxtInfo) :InText Info))''', 'WBP.Actualizar')
    p3dsl.write(g2, '''
(fn Destello (Texto)
  (Widget|SetText(Text) :self (Get|TxtDestello) :InText Texto)
  (Widget|SetVisibility :self (Get|TxtDestello) :InVisibility "HitTestInvisible")
  (Utilities|Time|SetTimerbyFunctionName :Object self :FunctionName "OcultarDestello" :Time 1.6 :bLooping false))''', 'WBP.Destello')
    p3dsl.write(g3, '''
(fn OcultarDestello ()
  (Widget|SetVisibility :self (Get|TxtDestello) :InVisibility "Collapsed"))''', 'WBP.Ocultar')
    p3dsl.compile_and_report(wbp)
    EAL.save_loaded_asset(wbp)
    log('widget OK')
    return wbp


# ---------------------------------------------------------------- fractura (Dataflow)


def build_fracture():
    """Equivale a Fracture Mode → New + Uniform Voronoi, pero con un grafo Dataflow."""
    df_path = f'{FXDIR}/DF_Pinata'
    gc_path = f'{FXDIR}/GC_Pinata'
    fresh(df_path)
    fresh(gc_path)
    df = AT.create_asset('DF_Pinata', FXDIR, unreal.Dataflow, unreal.DataflowAssetFactory())
    DEL = unreal.DataflowEditorBlueprintLibrary

    def node(type_names, base):
        for t in type_names:
            try:
                n = DEL.add_dataflow_node(df, t, base, unreal.Vector2D(0, 0))
                if n and str(n) != 'None':
                    return str(n)
            except Exception as e:  # noqa
                log('df node', t, e)
        raise RuntimeError(f'No se pudo crear nodo {type_names}')

    sm = node(['FStaticMeshToCollectionDataflowNode_v2', 'FStaticMeshToCollectionDataflowNode', 'StaticMeshToCollection'], 'MallaAColeccion')
    uf = node(['FUniformFractureDataflowNode', 'UniformFracture'], 'FracturaUniforme')
    uf2 = node(['FUniformFractureDataflowNode', 'UniformFracture'], 'FracturaCluster')
    term = node(['FGeometryCollectionTerminalDataflowNode_v2', 'FGeometryCollectionTerminalDataflowNode', 'GeometryCollectionTerminal'], 'Terminal')
    log('df nodes', sm, uf, uf2, term)

    def prop(n, k, v):
        ok = DEL.set_dataflow_node_property(df, n, k, v)
        if not ok:
            log('df prop FAIL', n, k, v)

    prop(sm, 'StaticMesh', '/Game/mesh/pinata/pinata_mesh.pinata_mesh')
    prop(uf, 'MinVoronoiSites', '14')
    prop(uf, 'MaxVoronoiSites', '18')
    prop(uf, 'RandomSeed', '7')
    prop(uf2, 'MinVoronoiSites', '4')
    prop(uf2, 'MaxVoronoiSites', '6')
    prop(uf2, 'RandomSeed', '11')

    def conn(a, ao, b, bi):
        ok = DEL.connect_dataflow_nodes(df, a, ao, b, bi)
        if not ok:
            log('df conn FAIL', a, ao, b, bi)

    conn(sm, 'Collection', uf, 'Collection')
    conn(uf, 'Collection', uf2, 'Collection')
    conn(uf2, 'Collection', term, 'Collection')
    conn(sm, 'Materials', term, 'Materials')
    conn(sm, 'MaterialInstances', term, 'MaterialInstances')
    conn(sm, 'InstancedMeshes', term, 'InstancedMeshes')
    EAL.save_loaded_asset(df)

    gc = AT.create_asset('GC_Pinata', FXDIR, unreal.GeometryCollection, unreal.GeometryCollectionFactory())
    for k, v in [('dataflow_asset', df), ('dataflow_terminal', term)]:
        try:
            gc.set_editor_property(k, v)
        except Exception as e:  # noqa
            log('gc prop', k, e)
    try:
        inst = gc.get_editor_property('dataflow_instance')
        inst.set_editor_property('dataflow_asset', df)
        inst.set_editor_property('dataflow_terminal', term)
        gc.set_editor_property('dataflow_instance', inst)
    except Exception as e:  # noqa
        log('gc instance', e)
    ok = False
    try:
        ok = unreal.DataflowBlueprintLibrary.regenerate_asset_from_dataflow(gc, False)
    except Exception as e:  # noqa
        log('regen exc', e)
    if not ok:
        try:
            unreal.DataflowBlueprintLibrary.evaluate_terminal_node_by_name(df, term, gc)
            ok = True
        except Exception as e:  # noqa
            log('eval exc', e)
    # Umbrales de daño: que aguante caídas pero se rompa con el martillo.
    try:
        gc.set_editor_property('damage_threshold', [250000.0, 50000.0, 5000.0])
    except Exception as e:  # noqa
        log('gc dmg', e)
    EAL.save_loaded_asset(gc)
    log('fractura evaluada', ok)
    return gc


# ---------------------------------------------------------------- DSL compartido

COMMON_GRAB = '''
(fn EnMano ()
  (bind par (Transformation|GetAttachParent :self (Get|Mesh)))
  (Utilities|Casting|CastToMotionControllerComponent :Object par
    (:then (return true))
    (:CastFailed (return false))))
'''

COMMON_THROW = '''
(fn ActualizarLanzamiento (DT)
  (bind loc (Transformation|GetWorldLocation :self (Get|Mesh)))
  (bind held (Call|EnMano))
  (if held
    (if (> DT 0.0001)
      (Set|Vel (+ (* (/ (- loc (Get|PosAnt)) DT) 0.6) (* (Get|Vel) 0.4))))
    (if (not (Get|Agarrado))
      (Call|AlAgarrar))
    (else
      (if (Get|Agarrado)
        (Physics|SetSimulatePhysics :self (Get|Mesh) :bSimulate true)
        (Physics|SetPhysicsLinearVelocity :self (Get|Mesh) :NewVel (Math|Vector|ClampVectorSize :A (* (Get|Vel) (Get|Factor)) :Min 0.0 :Max 2500.0))
        (Call|AlSoltar))))
  (Set|Agarrado held)
  (Set|PosAnt loc))
'''


def setup_grabbable(bp, factor=1.2):
    var(bp, 'Agarrado', 'bool')
    var(bp, 'PosAnt', 'Vector')
    var(bp, 'Vel', 'Vector')
    var(bp, 'Factor', 'float', editable=True)
    fn(bp, 'EnMano', outputs=[('Res', 'bool')])
    fn(bp, 'ActualizarLanzamiento', [('DT', 'float')])
    fn(bp, 'AlSoltar')
    fn(bp, 'AlAgarrar')


def write_grabbable(bp, al_soltar='', al_agarrar=''):
    p3dsl.write(graph(bp, 'EnMano'), COMMON_GRAB, bp.get_name() + '.EnMano')
    p3dsl.write(graph(bp, 'ActualizarLanzamiento'), COMMON_THROW, bp.get_name() + '.Lanzamiento')
    p3dsl.write(graph(bp, 'AlSoltar'), f'(fn AlSoltar () {al_soltar})', bp.get_name() + '.AlSoltar')
    p3dsl.write(graph(bp, 'AlAgarrar'), f'(fn AlAgarrar () {al_agarrar})', bp.get_name() + '.AlAgarrar')


def add_grab(bp, parent_h):
    add_comp(bp, 'Grab', GRAB_CLASS, parent_h)


# -- estaciones

def setup_station(bp, titulo):
    h_w, w = add_comp(bp, 'Marcador', unreal.WidgetComponent, None, {
        'widget_class': unreal.load_class(None, p3dsl.CLASSES['WBP_Marcador']),
        'draw_size': unreal.IntPoint(800, 420),
        'relative_location': unreal.Vector(0, 0, 200),
        'relative_scale3d': unreal.Vector(0.12, 0.12, 0.12),
    })
    for f, a in [('set_widget_space', unreal.WidgetSpace.WORLD), ('set_two_sided', True),
                 ('set_collision_enabled', unreal.CollisionEnabled.NO_COLLISION)]:
        try:
            getattr(w, f)(a)
        except Exception as e:  # noqa
            log('widget comp', f, e)
    h_b, base = add_comp(bp, 'BotonBase', unreal.StaticMeshComponent, None, {
        'static_mesh': unreal.load_asset(CYL),
        'relative_location': unreal.Vector(0, 120, 0),
        'relative_scale3d': unreal.Vector(0.2, 0.2, 1.0),
    })
    base.set_material(0, unreal.load_asset(f'{MATDIR}/MI_Metal'))
    h_s, seta = add_comp(bp, 'BotonSeta', unreal.StaticMeshComponent, h_b, {
        'static_mesh': unreal.load_asset(CYL),
        'relative_location': unreal.Vector(0, 0, 100),
        'relative_scale3d': unreal.Vector(0.6, 0.6, 0.05),
    })
    seta.set_material(0, unreal.load_asset(f'{MATDIR}/MI_Neon_Rojo'))
    seta.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
    add_comp(bp, 'BotonTexto', unreal.TextRenderComponent, None, {
        'text': 'REINICIAR',
        'world_size': 6.0,
        'horizontal_alignment': unreal.HorizTextAligment.EHTA_CENTER,
        'text_render_color': unreal.Color(255, 90, 90, 255),
        'relative_location': unreal.Vector(0, 120, 112),
    })
    var(bp, 'Titulo', 'text', editable=True)
    ovar(bp, 'Objetos', unreal.Actor.static_class(), editable=True, array=True)
    var(bp, 'Iniciales', 'Transform', container=ContainerType.ARRAY)
    var(bp, 'TBoton', 'float')
    fn(bp, 'GuardarIniciales')
    fn(bp, 'EstaAgarrado', [('A', '/Script/Engine.Actor')], [('Res', 'bool')])
    fn(bp, 'RestaurarObjetos')
    fn(bp, 'Mostrar', [('Puntos', 'text'), ('Info', 'text')])
    fn(bp, 'Destellar', [('Texto', 'text')])
    fn(bp, 'ComprobarBoton')
    fn(bp, 'PulsarBoton')
    fn(bp, 'SubirBoton')
    fn(bp, 'Reiniciar')
    return titulo


def write_station(bp):
    n = bp.get_name()
    W = p3dsl.write
    W(graph(bp, 'GuardarIniciales'), '''
(fn GuardarIniciales ()
  (Utilities|Array|Clear :TargetArray (Get|Iniciales))
  (for a (Get|Objetos)
    (Utilities|Array|Add :TargetArray (Get|Iniciales) :NewItem (Transformation|GetActorTransform :self a))))''', n + '.Guardar')
    W(graph(bp, 'EstaAgarrado'), '''
(fn EstaAgarrado (A)
  (return (== (Actor|GetAttachParentActor :self A) (Game|GetPlayerPawn :PlayerIndex 0))))''', n + '.EstaAgarrado')
    W(graph(bp, 'RestaurarObjetos'), '''
(fn RestaurarObjetos ()
  (for i (range (Utilities|Array|Length :TargetArray (Get|Objetos)))
    (bind a (Utilities|Array|Get(acopy) (Get|Objetos) i))
    (bind t (Utilities|Array|Get(acopy) (Get|Iniciales) i))
    (if (not (Call|EstaAgarrado :A a))
      (Transformation|DetachFromActor :self a :LocationRule "KeepWorld" :RotationRule "KeepWorld" :ScaleRule "KeepWorld")
      (Rendering|SetActorHiddenInGame :self a :bNewHidden false)
      (Collision|SetActorEnableCollision :self a :bNewActorEnableCollision true)
      (bind root (Fn|/Script/Engine.Actor:K2_GetRootComponent :self a))
      (bind p (Utilities|Casting|CastToPrimitiveComponent :Object root)
        (:then
          (Physics|SetSimulatePhysics :self p :bSimulate false)
          (Transformation|SetActorTransform :self a :NewTransform t :bTeleport true)
          (Physics|SetSimulatePhysics :self p :bSimulate true)
          (Physics|SetPhysicsLinearVelocity :self p :NewVel (Math|Vector|MakeVector :X 0.0 :Y 0.0 :Z 0.0)))
        (:CastFailed
          (Transformation|SetActorTransform :self a :NewTransform t :bTeleport true))))))''', n + '.Restaurar')
    W(graph(bp, 'Mostrar'), '''
(fn Mostrar (Puntos Info)
  (bind wo (UserInterface|GetUserWidgetObject :self (Get|Marcador)))
  (bind m (CastTo|WBP_Marcador :Object wo)
    (:then (CallOf|WBP_Marcador|Actualizar :self m :Titulo (Get|Titulo) :Puntos Puntos :Info Info))
    (:CastFailed)))''', n + '.Mostrar')
    W(graph(bp, 'Destellar'), '''
(fn Destellar (Texto)
  (bind wo (UserInterface|GetUserWidgetObject :self (Get|Marcador)))
  (bind m (CastTo|WBP_Marcador :Object wo)
    (:then (CallOf|WBP_Marcador|Destello :self m :Texto Texto))
    (:CastFailed)))''', n + '.Destellar')
    W(graph(bp, 'ComprobarBoton'), '''
(fn ComprobarBoton ()
  (bind now (Utilities|Time|GetGameTimeinSeconds))
  (if (> (- now (Get|TBoton)) 1.5)
    (bind pawn (Game|GetPlayerPawn :PlayerIndex 0))
    (bind seta (Transformation|GetWorldLocation :self (Get|BotonSeta)))
    (bind comps (Actor|GetComponentsByClass :self pawn :ComponentClass "/Script/HeadMountedDisplay.MotionControllerComponent"))
    (for c comps
      (bind sc (Utilities|Casting|CastToSceneComponent :Object c)
        (:then
          (if (< (Math|Vector|Distance(Vector) :V1 (Transformation|GetWorldLocation :self sc) :V2 seta) 12.0)
            (Set|TBoton now)
            (Call|PulsarBoton)))
        (:CastFailed)))))''', n + '.ComprobarBoton')
    W(graph(bp, 'PulsarBoton'), '''
(fn PulsarBoton ()
  (Transformation|SetRelativeLocation :self (Get|BotonSeta) :NewLocation (Math|Vector|MakeVector :X 0.0 :Y 0.0 :Z 97.0))
  (Utilities|Time|SetTimerbyFunctionName :Object self :FunctionName "SubirBoton" :Time 0.35 :bLooping false)
  (Call|Reiniciar))''', n + '.Pulsar')
    W(graph(bp, 'SubirBoton'), '''
(fn SubirBoton ()
  (Transformation|SetRelativeLocation :self (Get|BotonSeta) :NewLocation (Math|Vector|MakeVector :X 0.0 :Y 0.0 :Z 100.0)))''', n + '.Subir')


# ---------------------------------------------------------------- Blueprints


def build_blueprints():
    A = unreal.Actor
    names = ['BP_Bolo', 'BP_BolaBolos', 'BP_Bolera', 'BP_Dardo', 'BP_Diana', 'BP_PiezaPotato', 'BP_MrPotato', 'BP_Martillo', 'BP_RompeRalph']
    bps = {n: new_bp(n, A) for n in names}
    for b in bps.values():
        compile_bp(b)

    # --- objetos físicos (raíz = malla) ---
    def physical_root(bp, mesh, mass, ccd=False, notify=False, scale=None):
        h, obj = add_comp(bp, 'Mesh', unreal.StaticMeshComponent, None, {'static_mesh': unreal.load_asset(mesh)})
        physics(obj, True, mass, ccd, notify)
        if scale:
            obj.set_editor_property('relative_scale3d', scale)
        if not SUB.make_new_scene_root(handles(bp)[0], h, bp):
            log('ROOT FAIL', bp.get_name())
        return h, obj

    hb, _ = physical_root(bps['BP_Bolo'], '/Game/mesh/bolos/bowling_pin_ball', 1.5, ccd=True)
    hb, _ = physical_root(bps['BP_BolaBolos'], '/Game/mesh/bolos/bowling', 6.0, ccd=True)
    add_grab(bps['BP_BolaBolos'], hb)
    hd, _ = physical_root(bps['BP_Dardo'], '/Game/mesh/dardos/SM_DartboardDarts_Cylinder_001', 0.1, ccd=True, notify=True)
    add_grab(bps['BP_Dardo'], hd)
    hp, _ = physical_root(bps['BP_PiezaPotato'], '/Game/mesh/Mr_Potato/Señor_potato_29_Nariz', 0.2)
    add_grab(bps['BP_PiezaPotato'], hp)
    hm, mango = physical_root(bps['BP_Martillo'], CYL, 1.2, scale=unreal.Vector(0.04, 0.04, 0.40))
    mango.set_material(0, unreal.load_asset(f'{MATDIR}/MI_Madera'))
    hc, cab = add_comp(bps['BP_Martillo'], 'Cabeza', unreal.StaticMeshComponent, hm, {
        'static_mesh': unreal.load_asset(CUBE),
        'relative_location': unreal.Vector(0, 0, 95),
        'relative_scale3d': unreal.Vector(0.20 / 0.04, 0.09 / 0.04, 0.09 / 0.40),
    })
    cab.set_material(0, unreal.load_asset(f'{MATDIR}/MI_Metal'))
    physics(cab, False, 0.0)
    add_grab(bps['BP_Martillo'], hm)
    add_comp(bps['BP_Martillo'], 'Campo', unreal.FieldSystemComponent, hm)

    # --- estaciones ---
    setup_station(bps['BP_Bolera'], 'BOLERA')
    setup_station(bps['BP_Diana'], 'DARDOS')
    setup_station(bps['BP_MrPotato'], 'MR. POTATO')
    setup_station(bps['BP_RompeRalph'], 'ROMPE-RALPH')

    _, board = add_comp(bps['BP_Diana'], 'Diana', unreal.StaticMeshComponent, None, {
        'static_mesh': unreal.load_asset('/Game/mesh/dardos/SM_DartboardDarts_Cylinder')})
    board.set_collision_profile_name('BlockAll')
    hdiana = [h for h in handles(bps['BP_Diana']) if comp_obj(h) == board][0]
    # Números del 1 al 20 alrededor de la diana (sobre el anillo negro).
    sectors = [20, 1, 18, 4, 13, 6, 10, 15, 2, 17, 3, 19, 7, 16, 8, 11, 14, 9, 12, 5]
    radius = (17.2 + 22.4) * 0.5
    for i, s in enumerate(sectors):
        a = math.radians(i * 18)
        x = -math.sin(a) * radius   # derecha del espectador = -X local
        z = math.cos(a) * radius - 0.2
        add_comp(bps['BP_Diana'], f'Num{s}', unreal.TextRenderComponent, hdiana, {
            'text': str(s), 'world_size': 2.6,
            'horizontal_alignment': unreal.HorizTextAligment.EHTA_CENTER,
            'vertical_alignment': unreal.VerticalTextAligment.EVRTA_TEXT_CENTER,
            'text_render_color': unreal.Color(255, 255, 255, 255),
            'relative_location': unreal.Vector(x, 1.2, z),
            'relative_rotation': unreal.Rotator(0, 90, 0),
        })
    _, patata = add_comp(bps['BP_MrPotato'], 'Patata', unreal.StaticMeshComponent, None, {
        'static_mesh': unreal.load_asset('/Game/mesh/Mr_Potato/Señor_potato_29_Cuerpo'),
        'relative_location': unreal.Vector(0, 0, 28.3)})
    patata.set_collision_profile_name('BlockAll')

    # --- variables ---
    B = bps
    setup_grabbable(B['BP_BolaBolos'], 1.25)
    var(B['BP_BolaBolos'], 'TSoltada', 'float')
    setup_grabbable(B['BP_Dardo'], 1.3)
    setup_grabbable(B['BP_PiezaPotato'], 1.0)
    setup_grabbable(B['BP_Martillo'], 1.0)
    for b in B.values():
        compile_bp(b)

    ovar(B['BP_Bolera'], 'Bolos', cls_path('BP_Bolo'), editable=True, array=True)
    ovar(B['BP_Bolera'], 'Bola', cls_path('BP_BolaBolos'), editable=True)
    var(B['BP_Bolera'], 'IniBolos', 'Transform', container=ContainerType.ARRAY)
    for v, t in [('Estado', 'int'), ('Frame', 'int'), ('Tirada', 'int'), ('Total', 'int'), ('DerribadosAntes', 'int'), ('Cnt', 'int'),
                 ('TEstado', 'float'), ('TQuieta', 'float')]:
        var(B['BP_Bolera'], v, t)
    var(B['BP_Bolera'], 'DistBolos', 'float', editable=True)

    ovar(B['BP_Diana'], 'Dardos', cls_path('BP_Dardo'), editable=True, array=True)
    for v, t in [('Total', 'int'), ('PuntosRonda', 'int'), ('Ronda', 'int'), ('Lanzados', 'int'), ('Puntos', 'int'),
                 ('TFinRonda', 'float'), ('Etiqueta', 'string')]:
        var(B['BP_Diana'], v, t)
    var(B['BP_Diana'], 'Centro', 'Vector', editable=True)
    var(B['BP_Diana'], 'Sectores', 'int', container=ContainerType.ARRAY)

    ovar(B['BP_Dardo'], 'Diana', cls_path('BP_Diana'))
    for v, t in [('Lanzado', 'bool'), ('TLanzado', 'float'), ('VelAnt', 'Vector')]:
        var(B['BP_Dardo'], v, t)

    ovar(B['BP_MrPotato'], 'Piezas', cls_path('BP_PiezaPotato'), editable=True, array=True)
    var(B['BP_MrPotato'], 'Pegadas', 'int')
    ovar(B['BP_MrPotato'], 'MatResaltado', unreal.MaterialInterface.static_class(), editable=True)
    ovar(B['BP_PiezaPotato'], 'Cuerpo', cls_path('BP_MrPotato'), editable=True)
    var(B['BP_PiezaPotato'], 'Pegada', 'bool')

    ovar(B['BP_RompeRalph'], 'Objetivo', unreal.Actor.static_class(), editable=True)
    var(B['BP_RompeRalph'], 'IniObjetivo', 'Transform')
    var(B['BP_RompeRalph'], 'Golpes', 'int')
    ovar(B['BP_Martillo'], 'Estacion', cls_path('BP_RompeRalph'), editable=True)
    var(B['BP_Martillo'], 'PosCabAnt', 'Vector')
    var(B['BP_Martillo'], 'TGolpe', 'float')

    # --- firmas de funciones específicas ---
    fn(B['BP_Bolera'], 'Derribado', [('B', '/Script/Engine.Actor'), ('Ini', 'Transform')], [('Res', 'bool')])
    fn(B['BP_Bolera'], 'ContarDerribados', outputs=[('N', 'int')])
    fn(B['BP_Bolera'], 'Recolocar')
    fn(B['BP_Bolera'], 'RetirarDerribados')
    fn(B['BP_Bolera'], 'DevolverBola')
    fn(B['BP_Bolera'], 'NuevaPartida')
    fn(B['BP_Bolera'], 'ActualizarMarcador', [('Extra', 'string')])
    fn(B['BP_Bolera'], 'FinTirada')

    fn(B['BP_Diana'], 'Puntuar', [('P', 'Vector')])
    fn(B['BP_Diana'], 'IntentarClavar', [('D', cls_path('BP_Dardo')), ('P', 'Vector'), ('V', 'Vector')], [('Ok', 'bool')])
    fn(B['BP_Diana'], 'RegistrarTiro', [('Pts', 'int')])
    fn(B['BP_Diana'], 'RegistrarFallo', [('D', cls_path('BP_Dardo'))])
    fn(B['BP_Diana'], 'Actualizar')

    fn(B['BP_MrPotato'], 'Toca', [('Pieza', '/Script/Engine.PrimitiveComponent')], [('Res', 'bool')])
    fn(B['BP_MrPotato'], 'Resaltar', [('On', 'bool')])
    fn(B['BP_MrPotato'], 'PiezaPegada')
    fn(B['BP_MrPotato'], 'PiezaQuitada')
    fn(B['BP_MrPotato'], 'Actualizar')

    fn(B['BP_RompeRalph'], 'RegistrarGolpe', [('Vel', 'float')])
    fn(B['BP_RompeRalph'], 'Actualizar')

    for b in B.values():
        compile_bp(b)

    # ================================================================ grafos
    W = p3dsl.write

    # ---- comunes
    write_grabbable(B['BP_BolaBolos'], al_soltar='(Set|TSoltada (Utilities|Time|GetGameTimeinSeconds))')
    write_grabbable(B['BP_Dardo'],
                    al_soltar='(Set|Lanzado (> (Math|Vector|VectorLength :A (Get|Vel)) 80.0)) (Set|TLanzado (Utilities|Time|GetGameTimeinSeconds))',
                    al_agarrar='(Set|Lanzado false)')
    write_grabbable(B['BP_PiezaPotato'], al_soltar='''
  (CallOf|BP_MrPotato|Resaltar :self (Get|Cuerpo) :On false)
  (if (CallOf|BP_MrPotato|Toca :self (Get|Cuerpo) :Pieza (Get|Mesh))
    (Physics|SetSimulatePhysics :self (Get|Mesh) :bSimulate false)
    (Transformation|AttachActorToComponent :self self :Parent (GetOf|BP_MrPotato|Patata :self (Get|Cuerpo)) :LocationRule "KeepWorld" :RotationRule "KeepWorld" :ScaleRule "KeepWorld" :bWeldSimulatedBodies false)
    (Set|Pegada true)
    (CallOf|BP_MrPotato|PiezaPegada :self (Get|Cuerpo)))''',
                    al_agarrar='(if (Get|Pegada) (Set|Pegada false) (CallOf|BP_MrPotato|PiezaQuitada :self (Get|Cuerpo)))')
    write_grabbable(B['BP_Martillo'])
    for s in ['BP_Bolera', 'BP_Diana', 'BP_MrPotato', 'BP_RompeRalph']:
        write_station(B[s])

    # ---- Bola / pieza: Tick
    W(graph(B['BP_BolaBolos'], 'EventGraph'), '''
(event EventTick (DeltaSeconds)
  (Call|ActualizarLanzamiento :DT DeltaSeconds))''', 'Bola.Tick')
    W(graph(B['BP_PiezaPotato'], 'EventGraph'), '''
(event EventTick (DeltaSeconds)
  (Call|ActualizarLanzamiento :DT DeltaSeconds)
  (if (Get|Agarrado)
    (CallOf|BP_MrPotato|Resaltar :self (Get|Cuerpo) :On (CallOf|BP_MrPotato|Toca :self (Get|Cuerpo) :Pieza (Get|Mesh)))))''', 'Pieza.Tick')

    # ---- Dardo
    W(graph(B['BP_Dardo'], 'EventGraph'), '''
(event EventTick (DeltaSeconds)
  (Call|ActualizarLanzamiento :DT DeltaSeconds)
  (if (Get|Lanzado)
    (bind v (Physics|GetPhysicsLinearVelocity :self (Get|Mesh)))
    (if (> (Math|Vector|VectorLength :A v) 200.0)
      (Set|VelAnt v)
      (Transformation|SetWorldRotation :self (Get|Mesh) :NewRotation (Math|Rotator|MakeRotfromYZ :Y (- v) :Z (Math|Vector|MakeVector :X 0.0 :Y 0.0 :Z 1.0)) :bTeleport true)
      (Physics|SetPhysicsAngularVelocityinDegrees :self (Get|Mesh) :NewAngVel (Math|Vector|MakeVector :X 0.0 :Y 0.0 :Z 0.0)))
    (if (> (- (Utilities|Time|GetGameTimeinSeconds) (Get|TLanzado)) 2.5)
      (Set|Lanzado false)
      (CallOf|BP_Diana|RegistrarFallo :self (Get|Diana) :D self))))
(event Collision|EventHit (MyComp Other OtherComp bSelfMoved HitLocation HitNormal NormalImpulse Hit)
  (if (Get|Lanzado)
    (if (== Other (Get|Diana))
      (bind ok (CallOf|BP_Diana|IntentarClavar :self (Get|Diana) :D self :P HitLocation :V (Get|VelAnt)))
      (if ok (Set|Lanzado false)))))''', 'Dardo.Events')

    # ---- Bolera
    bo = B['BP_Bolera']
    W(graph(bo, 'Derribado'), '''
(fn Derribado (B Ini)
  (bind up (Transformation|GetActorUpVector :self B))
  (bind iup (Math|Vector|GetUpVector :InRot (.rotation Ini)))
  (bind loc (Transformation|GetActorLocation :self B))
  (bind il (.location Ini))
  (bind tilt (< (Math|Vector|DotProduct :A up :B iup) 0.8))
  (bind moved (> (Math|Vector|VectorLengthXY :A (- loc il)) 15.0))
  (bind fell (< (.z loc) (- (.z il) 15.0)))
  (return (or (or tilt moved) fell)))''', 'Bolera.Derribado')
    W(graph(bo, 'ContarDerribados'), '''
(fn ContarDerribados ()
  (Set|Cnt 0)
  (for i (range (Utilities|Array|Length :TargetArray (Get|Bolos)))
    (if (Call|Derribado :B (Utilities|Array|Get(acopy) (Get|Bolos) i) :Ini (Utilities|Array|Get(acopy) (Get|IniBolos) i))
      (Set|Cnt (+ (Get|Cnt) 1))))
  (return (Get|Cnt)))''', 'Bolera.Contar')
    W(graph(bo, 'Recolocar'), '''
(fn Recolocar ()
  (for i (range (Utilities|Array|Length :TargetArray (Get|Bolos)))
    (bind b (Utilities|Array|Get(acopy) (Get|Bolos) i))
    (bind m (GetOf|BP_Bolo|Mesh :self b))
    (Rendering|SetActorHiddenInGame :self b :bNewHidden false)
    (Collision|SetActorEnableCollision :self b :bNewActorEnableCollision true)
    (Physics|SetSimulatePhysics :self m :bSimulate false)
    (Transformation|SetActorTransform :self b :NewTransform (Utilities|Array|Get(acopy) (Get|IniBolos) i) :bTeleport true)
    (Physics|SetSimulatePhysics :self m :bSimulate true)
    (Physics|PutRigidBodytoSleep :self m))
  (Set|DerribadosAntes 0))''', 'Bolera.Recolocar')
    W(graph(bo, 'RetirarDerribados'), '''
(fn RetirarDerribados ()
  (for i (range (Utilities|Array|Length :TargetArray (Get|Bolos)))
    (bind b (Utilities|Array|Get(acopy) (Get|Bolos) i))
    (if (Call|Derribado :B b :Ini (Utilities|Array|Get(acopy) (Get|IniBolos) i))
      (Physics|SetSimulatePhysics :self (GetOf|BP_Bolo|Mesh :self b) :bSimulate false)
      (Rendering|SetActorHiddenInGame :self b :bNewHidden true)
      (Collision|SetActorEnableCollision :self b :bNewActorEnableCollision false)
      (Transformation|SetActorLocation :self b :NewLocation (+ (Transformation|GetActorLocation :self b) (Math|Vector|MakeVector :X 0.0 :Y 0.0 :Z -500.0)) :bTeleport true))))''', 'Bolera.Retirar')
    W(graph(bo, 'DevolverBola'), '''
(fn DevolverBola ()
  (if (not (Call|EstaAgarrado :A (Get|Bola)))
    (bind m (GetOf|BP_BolaBolos|Mesh :self (Get|Bola)))
    (Physics|SetSimulatePhysics :self m :bSimulate false)
    (Transformation|SetActorTransform :self (Get|Bola) :NewTransform (Utilities|Array|Get(acopy) (Get|Iniciales) 0) :bTeleport true)
    (Physics|SetSimulatePhysics :self m :bSimulate true)
    (Physics|SetPhysicsLinearVelocity :self m :NewVel (Math|Vector|MakeVector :X 0.0 :Y 0.0 :Z 0.0))))''', 'Bolera.Devolver')
    W(graph(bo, 'ActualizarMarcador'), '''
(fn ActualizarMarcador (Extra)
  (bind pts (Utilities|Text|ToText(String) :InString (+ (Utilities|String|ToString(Integer) :InInt (Get|Total)) " pts")))
  (bind fr (Utilities|String|ToString(Integer) :InInt (Math|Integer|Min(Integer) :A (Get|Frame) :B 10)))
  (bind ti (Utilities|String|ToString(Integer) :InInt (+ (Get|Tirada) 1)))
  (bind info (+ (+ (+ (+ (+ "Frame " fr) "/10  -  Tirada ") ti) "  -  ") Extra))
  (Call|Mostrar :Puntos pts :Info (Utilities|Text|ToText(String) :InString info)))''', 'Bolera.Marcador')
    W(graph(bo, 'NuevaPartida'), '''
(fn NuevaPartida ()
  (Set|Frame 1)
  (Set|Tirada 0)
  (Set|Total 0)
  (Set|Estado 0)
  (Call|Recolocar)
  (Call|ActualizarMarcador :Extra "Coge la bola y lanzala hacia los bolos"))''', 'Bolera.Nueva')
    W(graph(bo, 'Reiniciar'), '''
(fn Reiniciar ()
  (Call|DevolverBola)
  (Call|NuevaPartida))''', 'Bolera.Reiniciar')
    W(graph(bo, 'FinTirada'), '''
(fn FinTirada ()
  (bind total (Call|ContarDerribados))
  (bind esta (- total (Get|DerribadosAntes)))
  (bind nb (Utilities|Array|Length :TargetArray (Get|Bolos)))
  (Set|Total (+ (Get|Total) esta))
  (Set|Tirada (+ (Get|Tirada) 1))
  (Set|Estado 0)
  (SetOf|BP_BolaBolos|TSoltada :self (Get|Bola) :TSoltada -1.0)
  (bind todos (>= total nb))
  (bind extra (+ "Ultima tirada: " (Utilities|String|ToString(Integer) :InInt esta)))
  (if todos
    (if (== (Get|Tirada) 1)
      (Call|Destellar :Texto "STRIKE!")
      (else (Call|Destellar :Texto "SPARE!")))
    (else
      (if (== esta 0) (Call|Destellar :Texto "CANAL!"))))
  (if (or todos (>= (Get|Tirada) 2))
    (Call|Recolocar)
    (Set|Tirada 0)
    (if (>= (Get|Frame) 10)
      (Set|Frame 11)
      (Call|ActualizarMarcador :Extra "Partida terminada! Lanza para jugar otra")
      (else
        (Set|Frame (+ (Get|Frame) 1))
        (Call|ActualizarMarcador :Extra extra)))
    (else
      (Call|RetirarDerribados)
      (Set|DerribadosAntes total)
      (Call|ActualizarMarcador :Extra extra)))
  (Call|DevolverBola))''', 'Bolera.Fin')
    W(graph(bo, 'EventGraph'), '''
(event EventBeginPlay
  (Call|GuardarIniciales)
  (Utilities|Array|Clear :TargetArray (Get|IniBolos))
  (for b (Get|Bolos)
    (Utilities|Array|Add :TargetArray (Get|IniBolos) :NewItem (Transformation|GetActorTransform :self b)))
  (Call|NuevaPartida))
(event EventTick (DeltaSeconds)
  (Call|ComprobarBoton)
  (bind now (Utilities|Time|GetGameTimeinSeconds))
  (bind local (Math|Transform|InverseTransformLocation :T (Transformation|GetActorTransform) :Location (Transformation|GetActorLocation :self (Get|Bola))))
  (bind vel (Math|Vector|VectorLength :A (Physics|GetPhysicsLinearVelocity :self (GetOf|BP_BolaBolos|Mesh :self (Get|Bola)))))
  (bind held (Call|EstaAgarrado :A (Get|Bola)))
  (switch int (Get|Estado)
    (:0
      (if (and (and (not held) (> (GetOf|BP_BolaBolos|TSoltada :self (Get|Bola)) 0.0)) (and (> (.x local) 50.0) (> vel 60.0)))
        (if (> (Get|Frame) 10) (Call|NuevaPartida))
        (Set|Estado 1)
        (Set|TEstado now)
        (Set|TQuieta 0.0)))
    (:1
      (if held
        (Set|Estado 0)
        (else
          (if (< vel 15.0)
            (Set|TQuieta (+ (Get|TQuieta) DeltaSeconds))
            (else (Set|TQuieta 0.0)))
          (if (or (or (> (.x local) (+ (Get|DistBolos) 120.0)) (< (.z local) -60.0)) (or (> (Get|TQuieta) 1.0) (> (- now (Get|TEstado)) 10.0)))
            (Set|Estado 2)
            (Set|TEstado now)))))
    (:2
      (if (> (- now (Get|TEstado)) 2.5)
        (Call|FinTirada)))))''', 'Bolera.Events')

    # ---- Diana
    di = B['BP_Diana']
    W(graph(di, 'Puntuar'), '''
(fn Puntuar (P)
  (bind loc (- (Math|Transform|InverseTransformLocation :T (Transformation|GetWorldTransform :self (Get|Diana)) :Location P) (Get|Centro)))
  (bind x (- (.x loc)))
  (bind y (.z loc))
  (bind r (Math|Float|Sqrt :A (+ (* x x) (* y y))))
  (bind ang (Math|Trig|Atan2(Degrees) :Y x :X y))
  (bind a2 (Math|Float|%(Float) :A (+ ang 369.0) :B 360.0))
  (bind idx (Math|Float|Floor :A (/ a2 18.0)))
  (bind sec (Utilities|Array|Get(acopy) (Get|Sectores) idx))
  (bind ss (Utilities|String|ToString(Integer) :InInt sec))
  (if (<= r 0.9)
    (Set|Puntos 50) (Set|Etiqueta "BULL")
    (elif (<= r 2.2)
      (Set|Puntos 25) (Set|Etiqueta "25")
      (elif (> r 17.2)
        (Set|Puntos 0) (Set|Etiqueta "FUERA")
        (elif (>= r 16.1)
          (Set|Puntos (* sec 2)) (Set|Etiqueta (+ "D" ss))
          (elif (and (>= r 9.7) (<= r 10.9))
            (Set|Puntos (* sec 3)) (Set|Etiqueta (+ "T" ss))
            (else (Set|Puntos sec) (Set|Etiqueta ss))))))))''', 'Diana.Puntuar')
    W(graph(di, 'IntentarClavar'), '''
(fn IntentarClavar (D P V)
  (bind n (Transformation|GetRightVector :self (Get|Diana)))
  (bind dir (Math|Vector|Normalize :A V))
  (bind dm (GetOf|BP_Dardo|Mesh :self D))
  (bind tip (- (Transformation|GetRightVector :self dm)))
  (bind frontal (< (Math|Vector|DotProduct :A dir :B n) -0.2))
  (bind punta (> (Math|Vector|DotProduct :A tip :B dir) 0.4))
  (if (and (and frontal punta) (> (Math|Vector|VectorLength :A V) 120.0))
    (Physics|SetSimulatePhysics :self dm :bSimulate false)
    (Transformation|SetWorldRotation :self dm :NewRotation (Math|Rotator|MakeRotfromYZ :Y (- dir) :Z (Math|Vector|MakeVector :X 0.0 :Y 0.0 :Z 1.0)) :bTeleport true)
    (Transformation|SetWorldLocation :self dm :NewLocation (- P (* dir 4.9)) :bTeleport true)
    (Transformation|AttachActorToComponent :self D :Parent (Get|Diana) :LocationRule "KeepWorld" :RotationRule "KeepWorld" :ScaleRule "KeepWorld" :bWeldSimulatedBodies false)
    (Call|Puntuar :P P)
    (Call|RegistrarTiro :Pts (Get|Puntos))
    (return true))
  (return false))''', 'Diana.Clavar')
    W(graph(di, 'RegistrarTiro'), '''
(fn RegistrarTiro (Pts)
  (Set|Lanzados (+ (Get|Lanzados) 1))
  (Set|Total (+ (Get|Total) Pts))
  (Set|PuntosRonda (+ (Get|PuntosRonda) Pts))
  (if (== Pts 50)
    (Call|Destellar :Texto "BULL!")
    (else (Call|Destellar :Texto (Utilities|Text|ToText(String) :InString (+ (+ (Get|Etiqueta) "  +") (Utilities|String|ToString(Integer) :InInt Pts))))))
  (Call|Actualizar))''', 'Diana.Tiro')
    W(graph(di, 'RegistrarFallo'), '''
(fn RegistrarFallo (D)
  (Set|Lanzados (+ (Get|Lanzados) 1))
  (Set|Etiqueta "fallo")
  (Call|Destellar :Texto "FALLO")
  (Call|Actualizar))''', 'Diana.Fallo')
    W(graph(di, 'Actualizar'), '''
(fn Actualizar ()
  (bind pts (Utilities|Text|ToText(String) :InString (+ (Utilities|String|ToString(Integer) :InInt (Get|Total)) " pts")))
  (bind a (+ (+ "Ronda " (Utilities|String|ToString(Integer) :InInt (Get|Ronda))) "  -  dardo "))
  (bind b (+ (+ a (Utilities|String|ToString(Integer) :InInt (Math|Integer|Min(Integer) :A (+ (Get|Lanzados) 1) :B 3))) "/3  -  ronda: "))
  (bind c (+ (+ (+ b (Utilities|String|ToString(Integer) :InInt (Get|PuntosRonda))) " pts  -  ultimo: ") (Get|Etiqueta)))
  (Call|Mostrar :Puntos pts :Info (Utilities|Text|ToText(String) :InString c)))''', 'Diana.Actualizar')
    W(graph(di, 'Reiniciar'), '''
(fn Reiniciar ()
  (Call|RestaurarObjetos)
  (Set|Total 0)
  (Set|PuntosRonda 0)
  (Set|Ronda 1)
  (Set|Lanzados 0)
  (Set|TFinRonda -1.0)
  (Set|Etiqueta "-")
  (Call|Actualizar))''', 'Diana.Reiniciar')
    W(graph(di, 'EventGraph'), '''
(event EventBeginPlay
  (for d (Get|Dardos)
    (SetOf|BP_Dardo|Diana :self d :Diana self))
  (Call|GuardarIniciales)
  (Set|Ronda 1)
  (Set|TFinRonda -1.0)
  (Set|Etiqueta "-")
  (Call|Actualizar))
(event EventTick (DeltaSeconds)
  (Call|ComprobarBoton)
  (bind now (Utilities|Time|GetGameTimeinSeconds))
  (if (>= (Get|Lanzados) 3)
    (if (< (Get|TFinRonda) 0.0)
      (Set|TFinRonda now)
      (Call|Destellar :Texto (Utilities|Text|ToText(String) :InString (+ "Ronda: " (Utilities|String|ToString(Integer) :InInt (Get|PuntosRonda)))))
      (else
        (if (> (- now (Get|TFinRonda)) 3.5)
          (Set|TFinRonda -1.0)
          (Set|Lanzados 0)
          (Set|PuntosRonda 0)
          (Set|Ronda (+ (Get|Ronda) 1))
          (Call|RestaurarObjetos)
          (Call|Actualizar))))))''', 'Diana.Events')

    # ---- Mr Potato
    mp = B['BP_MrPotato']
    gt = graph(mp, 'Toca')
    cp = 'Collision|GetClosestPointonCollision'
    b1 = bind_names(gt, cp, {'ReturnValue': 'd1', 'OutPointOnBody': 'p1'})
    b2 = bind_names(gt, cp, {'ReturnValue': 'd2', 'OutPointOnBody': 'p2'})
    log('orden GetClosestPoint', b1)
    W(gt, f'''
(fn Toca (Pieza)
  (bind c (Transformation|GetWorldLocation :self Pieza))
  (bind {b1} ({cp} :self (Get|Patata) :Point c))
  (bind {b2} ({cp} :self Pieza :Point p1))
  (return (and (>= d1 0.0) (and (>= d2 0.0) (<= d2 3.0)))))''', 'Potato.Toca')
    W(graph(mp, 'Resaltar'), '''
(fn Resaltar (On)
  (if On
    (Rendering|Material|SetOverlayMaterial :self (Get|Patata) :NewOverlayMaterial (Get|MatResaltado))
    (else (Rendering|Material|SetOverlayMaterial :self (Get|Patata)))))''', 'Potato.Resaltar')
    W(graph(mp, 'Actualizar'), '''
(fn Actualizar ()
  (bind t (+ (+ (Utilities|String|ToString(Integer) :InInt (Get|Pegadas)) " / ") (Utilities|String|ToString(Integer) :InInt (Utilities|Array|Length :TargetArray (Get|Piezas)))))
  (Call|Mostrar :Puntos (Utilities|Text|ToText(String) :InString t) :Info "Coge una pieza, apoyala en la patata y sueltala"))''', 'Potato.Actualizar')
    W(graph(mp, 'PiezaPegada'), '''
(fn PiezaPegada ()
  (Set|Pegadas (+ (Get|Pegadas) 1))
  (if (>= (Get|Pegadas) (Utilities|Array|Length :TargetArray (Get|Piezas)))
    (Call|Destellar :Texto "COMPLETO!")
    (else (Call|Destellar :Texto "CLIC!")))
  (Call|Actualizar))''', 'Potato.Pegada')
    W(graph(mp, 'PiezaQuitada'), '''
(fn PiezaQuitada ()
  (Set|Pegadas (Math|Integer|Max(Integer) :A (- (Get|Pegadas) 1) :B 0))
  (Call|Actualizar))''', 'Potato.Quitada')
    W(graph(mp, 'Reiniciar'), '''
(fn Reiniciar ()
  (for p (Get|Piezas)
    (SetOf|BP_PiezaPotato|Pegada :self p :Pegada false))
  (Call|RestaurarObjetos)
  (Set|Pegadas 0)
  (Call|Resaltar :On false)
  (Call|Actualizar))''', 'Potato.Reiniciar')
    W(graph(mp, 'EventGraph'), '''
(event EventBeginPlay
  (for p (Get|Piezas)
    (SetOf|BP_PiezaPotato|Cuerpo :self p :Cuerpo self))
  (Call|GuardarIniciales)
  (Call|Actualizar))
(event EventTick (DeltaSeconds)
  (Call|ComprobarBoton))''', 'Potato.Events')

    # ---- Rompe-Ralph y martillo
    rr = B['BP_RompeRalph']
    W(graph(rr, 'Actualizar'), '''
(fn Actualizar ()
  (Call|Mostrar :Puntos (Utilities|Text|ToText(String) :InString (+ (Utilities|String|ToString(Integer) :InInt (Get|Golpes)) " golpes")) :Info "Coge el martillo y golpea fuerte la pinata"))''', 'RR.Actualizar')
    W(graph(rr, 'RegistrarGolpe'), '''
(fn RegistrarGolpe (Vel)
  (Set|Golpes (+ (Get|Golpes) 1))
  (if (> Vel 600.0)
    (Call|Destellar :Texto "CRASH!")
    (else (Call|Destellar :Texto "PAM!")))
  (Call|Actualizar))''', 'RR.Golpe')
    W(graph(rr, 'Reiniciar'), f'''
(fn Reiniciar ()
  (Call|RestaurarObjetos)
  (Actor|DestroyActor :self (Get|Objetivo))
  (Set|Objetivo (Game|SpawnActorfromClass :Class "{cls_path('BP_Pinata')}" :SpawnTransform (Get|IniObjetivo) :CollisionHandlingOverride "AlwaysSpawn"))
  (Set|Golpes 0)
  (Call|Actualizar))''', 'RR.Reiniciar')
    W(graph(rr, 'EventGraph'), '''
(event EventBeginPlay
  (Call|GuardarIniciales)
  (Set|IniObjetivo (Transformation|GetActorTransform :self (Get|Objetivo)))
  (Call|Actualizar))
(event EventTick (DeltaSeconds)
  (Call|ComprobarBoton))''', 'RR.Events')

    ma = B['BP_Martillo']
    gm = graph(ma, 'EventGraph')
    bb = bind_names(gm, 'Collision|GetComponentBounds', {'Origin': 'org', 'BoxExtent': 'ext', 'SphereRadius': 'rad'})
    log('orden GetComponentBounds', bb)
    W(gm, f'''
(event EventTick (DeltaSeconds)
  (Call|ActualizarLanzamiento :DT DeltaSeconds)
  (bind hp (Transformation|GetWorldLocation :self (Get|Cabeza)))
  (bind hv (/ (- hp (Get|PosCabAnt)) (Math|Float|Max(Float) :A DeltaSeconds :B 0.001)))
  (Set|PosCabAnt hp)
  (bind spd (Math|Vector|VectorLength :A hv))
  (bind now (Utilities|Time|GetGameTimeinSeconds))
  (if (and (> spd 180.0) (> (- now (Get|TGolpe)) 0.2))
    (bind obj (GetOf|BP_RompeRalph|Objetivo :self (Get|Estacion)))
    (bind comp (Actor|GetComponentbyClass :self obj :ComponentClass "/Script/GeometryCollectionEngine.GeometryCollectionComponent"))
    (bind sc (Utilities|Casting|CastToSceneComponent :Object comp)
      (:then
        (bind {bb} (Collision|GetComponentBounds :Component sc))
        (if (< (Math|Vector|Distance(Vector) :V1 hp :V2 org) (+ (* rad 0.8) 8.0))
          (Set|TGolpe now)
          (bind f (Math|Float|Clamp(Float) :Value (/ spd 400.0) :Min 0.5 :Max 3.0))
          (Field|ApplyExternalStrain :self (Get|Campo) :Enabled true :Position hp :Radius (* 30.0 f) :Magnitude (* 5000000.0 f) :Iterations 3)
          (Field|FalloffUniformForce :self (Get|Campo) :Enabled true :Position hp :Direction (Math|Vector|Normalize :A hv) :Radius 45.0 :Magnitude (* 3000.0 f))
          (CallOf|BP_RompeRalph|RegistrarGolpe :self (Get|Estacion) :Vel spd)))
      (:CastFailed))))''', 'Martillo.Tick')

    # ---- valores por defecto
    set_cdo(B['BP_BolaBolos'], {'Factor': 1.25, 'TSoltada': -1.0})
    set_cdo(B['BP_Dardo'], {'Factor': 1.3})
    set_cdo(B['BP_PiezaPotato'], {'Factor': 1.0})
    set_cdo(B['BP_Martillo'], {'Factor': 1.0})
    set_cdo(B['BP_Bolera'], {'Titulo': 'BOLERA', 'DistBolos': 700.0})
    set_cdo(B['BP_Diana'], {'Titulo': 'DARDOS', 'Centro': unreal.Vector(0, 0.5, -0.2), 'Sectores': sectors})
    set_cdo(B['BP_MrPotato'], {'Titulo': 'MR. POTATO', 'MatResaltado': unreal.load_asset(f'{MATDIR}/M_P3_Resaltado')})
    set_cdo(B['BP_RompeRalph'], {'Titulo': 'ROMPE-RALPH'})

    for b in B.values():
        p3dsl.compile_and_report(b)
        EAL.save_loaded_asset(b)
    log('blueprints OK')
    return B


def build_pinata_bp(gc):
    fresh(f'{BPDIR}/BP_Pinata')
    bp = BT.create(BPDIR, 'BP_Pinata', unreal.GeometryCollectionActor.static_class())
    p3dsl.CLASSES['BP_Pinata'] = cls_path('BP_Pinata')
    for h in handles(bp):
        o = comp_obj(h)
        if isinstance(o, unreal.GeometryCollectionComponent):
            for k, v in [('rest_collection', gc), ('object_type', unreal.ObjectStateTypeEnum.CHAOS_OBJECT_DYNAMIC),
                         ('enable_damage_from_collision', False), ('notify_breaks', True)]:
                try:
                    o.set_editor_property(k, v)
                except Exception as e:  # noqa
                    log('pinata prop', k, e)
    compile_bp(bp)
    EAL.save_loaded_asset(bp)
    log('BP_Pinata OK')
    return bp


def main():
    steps = sys.argv[1:] if len(sys.argv) > 1 else []
    try:
        build_materials()
    except Exception:
        log('MATERIALS FAIL', traceback.format_exc())
    try:
        mesh_collisions()
    except Exception:
        log('COLLISIONS FAIL', traceback.format_exc())
    try:
        build_widget()
    except Exception:
        log('WIDGET FAIL', traceback.format_exc())
    gc = None
    try:
        gc = build_fracture()
    except Exception:
        log('FRACTURE FAIL', traceback.format_exc())
    try:
        build_pinata_bp(gc)
    except Exception:
        log('PINATA FAIL', traceback.format_exc())
    try:
        build_blueprints()
    except Exception:
        log('BP FAIL', traceback.format_exc())
    log('==== ERRORES DSL/COMPILACION:', len(p3dsl.ERRORS))
    for e in p3dsl.ERRORS:
        log(e)
    open(os.path.join(TOOLS, 'build_assets.txt'), 'w', encoding='utf-8').write('\n'.join(LOG))


main()
