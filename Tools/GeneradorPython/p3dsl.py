"""Utilidades para generar Blueprints con el DSL de EditorToolset desde un commandlet.

En modo commandlet la base de datos de acciones no ve las variables/funciones de los
Blueprints recién creados, así que se interceptan unos prefijos propios:

    (Get|Var)                    variable miembro propia
    (Set|Var valor)              asignar variable miembro propia
    (GetOf|Clase|Var :self obj)  variable de otro Blueprint
    (SetOf|Clase|Var :self obj v)
    (Call|Func args...)          función propia
    (CallOf|Clase|Func :self obj args...)
    (CastTo|Clase :Object x (:then ...) (:CastFailed ...))
Y si un ID de nodo no existe se busca por el último segmento (tolerante a mayúsculas).
"""
import unreal
from editor_toolset.toolsets import blueprint as bpmod
from editor_toolset.toolsets import blueprint_dsl
from editor_toolset.toolsets.blueprint import BlueprintTools as BT

CLASSES = {}   # nombre corto -> ruta de la clase generada ("/Game/..../BP_X.BP_X_C")
ERRORS = []

_orig_create = BT.create_node


def _cls(name):
    path = CLASSES.get(name, name)
    c = unreal.load_class(None, path)
    assert c, f'Clase no encontrada: {name} ({path})'
    return c, path


def _self_class_path(graph):
    bp = unreal.Blueprint.cast(graph.get_outer()) or graph.get_typed_outer(unreal.Blueprint)
    gen = unreal.BlueprintEditorLibrary.generated_class(bp)
    return gen.get_path_name()


def _create(graph, type_id, pos, declaring_class=None):
    ed = unreal.BlueprintGraphEditor.get_graph_editor(graph)
    parts = type_id.split('|')
    node = None
    head = parts[0]
    if head == 'Get' and len(parts) == 2:
        node = ed.add_get_member_variable_node(parts[1], '')
    elif head == 'Set' and len(parts) == 2:
        node = ed.add_set_member_variable_node(parts[1], '')
    elif head == 'GetOf' and len(parts) == 3:
        node = ed.add_get_member_variable_node(parts[2], _cls(parts[1])[1])
    elif head == 'SetOf' and len(parts) == 3:
        node = ed.add_set_member_variable_node(parts[2], _cls(parts[1])[1])
    elif head == 'Call' and len(parts) == 2:
        node = ed.add_call_function_node(f'{_self_class_path(graph)}:{parts[1]}')
    elif head == 'CallOf' and len(parts) == 3:
        node = ed.add_call_function_node(f'{_cls(parts[1])[1]}:{parts[2]}')
    elif head == 'Fn' and len(parts) == 2:
        node = ed.add_call_function_node(parts[1])
    elif head == 'CastTo' and len(parts) == 2:
        target, _ = _cls(parts[1])
        if unreal.MathLibrary.class_is_child_of(target, unreal.UserWidget.static_class()):
            base, base_cls = 'Utilities|Casting|CastToUserWidget', unreal.UserWidget.static_class()
        elif unreal.MathLibrary.class_is_child_of(target, unreal.SceneComponent.static_class()):
            base, base_cls = 'Utilities|Casting|CastToSceneComponent', unreal.SceneComponent.static_class()
        else:
            base, base_cls = 'Utilities|Casting|CastToActor', unreal.Actor.static_class()
        node = _orig_create(graph, base, pos, declaring_class)
        BT.retarget_node_class(node, base_cls, target)
    if node is not None:
        assert isinstance(node, unreal.EdGraphNode), f'No se pudo crear {type_id}'
        node.set_node_pos(pos)
        return node
    try:
        return _orig_create(graph, type_id, pos, declaring_class)
    except Exception:
        last = parts[-1].lower().replace(' ', '')
        cands = [t for t in BT.find_node_types(graph, parts[-1]) if t.split('|')[-1].lower().replace(' ', '') == last]
        if len(parts) > 1:
            pref = [t for t in cands if t.lower().startswith(parts[0].lower())]
            cands = pref or cands
        if not cands:
            raise
        return _orig_create(graph, cands[0], pos, declaring_class)


BT.create_node = staticmethod(_create)


def write(graph, code, label=''):
    """Transpila el DSL sin capturar excepciones (para ver los errores)."""
    try:
        blueprint_dsl.Transpiler(
            graph,
            BT.create_node,
            BT.connect_pins,
            BT._get_node_info,
            BT.set_pin_value,
            lambda g: BT.find_nodes(g),
            delete_node_fn=BT.delete_node,
            find_node_types_fn=lambda f: BT.find_node_types(graph, f),
        ).transpile(code)
        return True
    except Exception as e:  # noqa
        ERRORS.append(f'[{label or graph.get_path_name()}] {e}')
        return False


def compile_and_report(bp):
    try:
        unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    except Exception as e:  # noqa
        ERRORS.append(f'[compile {bp.get_name()}] {e}')
    for g in unreal.BlueprintEditorLibrary.list_graphs(bp):
        ed = unreal.BlueprintGraphEditor.get_graph_editor(g)
        if not ed:
            continue
        try:
            bad = ed.list_nodes_with_errors()
        except Exception:
            bad = []
        for n in bad or []:
            try:
                msg = n.get_editor_property('error_msg')
            except Exception:
                msg = '?'
            ERRORS.append(f'[node error {bp.get_name()}/{g.get_name()}] {unreal.BlueprintEditorLibrary.get_node_title(n)}: {msg}')
