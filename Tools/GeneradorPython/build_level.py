"""Monta el nivel L_XRTemplate con los cuatro minijuegos y el entorno de salón recreativo.

Sala A (x -500..500, patio abierto): Mr. Potato (oeste) y Rompe-Ralph (este).
Sala B (x 525..1500, cubierta):      Bolera (lado norte, y>0) y Dardos (lado sur, pared este).
"""
import math
import os
import traceback

import unreal

TOOLS = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()), 'Tools', 'GeneradorPython')
LOG = []


def log(*a):
    LOG.append(' '.join(str(x) for x in a))


EAS = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
MAP = '/Game/XRFramework/Levels/L_XRTemplate'
BP = '/Game/Practica3/Blueprints/'
MAT = '/Game/Practica3/Materiales/'
CUBE = unreal.load_asset('/Game/LevelPrototyping/Meshes/SM_Cube')
CYL = unreal.load_asset('/Game/LevelPrototyping/Meshes/SM_Cylinder')


def mat(n):
    return unreal.load_asset(MAT + n)


def cls(n):
    return unreal.load_class(None, f'{BP}{n}.{n}_C')


def folder(a, f):
    try:
        a.set_folder_path(f)
    except Exception:
        pass


def sm_actor(mesh, loc):
    a = EAS.spawn_actor_from_class(unreal.StaticMeshActor, loc, unreal.Rotator(0, 0, 0))
    if a is None:
        a = unreal.EditorLevelLibrary.spawn_actor_from_class(unreal.StaticMeshActor, loc, unreal.Rotator(0, 0, 0))
    if a is None:
        raise RuntimeError('No se pudo crear StaticMeshActor')
    a.static_mesh_component.set_mobility(unreal.ComponentMobility.MOVABLE)
    a.static_mesh_component.set_static_mesh(mesh)
    return a


def box(label, center, size, material, fold, collide=True):
    """Caja con SM_Cube (pivote en la esquina) centrada en `center` con tamaño `size` (cm)."""
    loc = unreal.Vector(center[0] - size[0] / 2, center[1] - size[1] / 2, center[2] - size[2] / 2)
    a = sm_actor(CUBE, loc)
    a.set_actor_scale3d(unreal.Vector(size[0] / 100, size[1] / 100, size[2] / 100))
    a.set_actor_label(label)
    c = a.static_mesh_component
    c.set_mobility(unreal.ComponentMobility.MOVABLE)
    c.set_material(0, mat(material))
    if not collide:
        c.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
    folder(a, fold)
    return a


def cylinder(label, base, radius, height, material, fold):
    a = sm_actor(CYL, unreal.Vector(*base))
    a.set_actor_scale3d(unreal.Vector(radius / 50, radius / 50, height / 100))
    a.set_actor_label(label)
    a.static_mesh_component.set_mobility(unreal.ComponentMobility.MOVABLE)
    a.static_mesh_component.set_material(0, mat(material))
    folder(a, fold)
    return a


def light(label, loc, color, intensity=8000, radius=900, fold='Entorno/Luces'):
    a = EAS.spawn_actor_from_class(unreal.PointLight, unreal.Vector(*loc), unreal.Rotator(0, 0, 0))
    a.set_actor_label(label)
    lc = a.point_light_component
    lc.set_mobility(unreal.ComponentMobility.MOVABLE)
    lc.set_intensity(intensity)
    lc.set_light_color(unreal.LinearColor(*color))
    lc.set_attenuation_radius(radius)
    lc.set_cast_shadows(False)
    folder(a, fold)
    return a


def sign(label, text, loc, yaw, size, color, fold='Entorno/Rotulos'):
    a = EAS.spawn_actor_from_class(unreal.TextRenderActor, unreal.Vector(*loc), unreal.Rotator(0, 0, yaw))
    a.set_actor_label(label)
    t = a.text_render
    t.set_text(text)
    t.set_world_size(size)
    t.set_horizontal_alignment(unreal.HorizTextAligment.EHTA_CENTER)
    t.set_vertical_alignment(unreal.VerticalTextAligment.EVRTA_TEXT_CENTER)
    t.set_text_render_color(unreal.Color(*color))
    folder(a, fold)
    return a


def spawn(n, loc, yaw=0.0, label=None, fold=None, rot=None):
    a = EAS.spawn_actor_from_class(cls(n), unreal.Vector(*loc), rot or unreal.Rotator(0, 0, yaw))
    if label:
        a.set_actor_label(label)
    if fold:
        folder(a, fold)
    return a


def comp(actor, name):
    for c in actor.get_components_by_class(unreal.SceneComponent):
        if c.get_name() == name:
            return c
    raise RuntimeError(f'{actor.get_actor_label()} no tiene {name}')


def setp(actor, name, value):
    try:
        actor.set_editor_property(name, value)
    except Exception as e:  # noqa
        log('SETP FAIL', actor.get_actor_label(), name, e)


def mesh_bounds(path):
    b = unreal.load_asset(path).get_bounding_box()
    return b.min, b.max


# ---------------------------------------------------------------- limpieza


def clean():
    remove_prefix = ('Cube', 'SM_Ball', 'GrabActor_', 'BP_Pistol', 'Fire_Cue', 'NavModifier_NoTeleport', 'Table', 'TextRenderActor')
    keep_exact = set()
    n = 0
    for a in EAS.get_all_level_actors():
        lbl = a.get_actor_label()
        if lbl.startswith(remove_prefix) and lbl not in keep_exact:
            EAS.destroy_actor(a)
            n += 1
        elif lbl.startswith(('P3_', 'Bolera', 'Dardos', 'MrPotato', 'RompeRalph', 'Entorno')):
            EAS.destroy_actor(a)
            n += 1
    # Borrar también lo generado en ejecuciones anteriores (por carpeta)
    for a in EAS.get_all_level_actors():
        try:
            fp = str(a.get_folder_path())
        except Exception:
            fp = ''
        if fp.split('/')[0] in ('Bolera', 'Dardos', 'MrPotato', 'RompeRalph', 'Entorno'):
            EAS.destroy_actor(a)
            n += 1
    log('borrados', n)


# ---------------------------------------------------------------- entorno


def environment():
    # Paredes, suelo y techo con materiales del salón
    for a in EAS.get_all_level_actors():
        lbl = a.get_actor_label()
        if isinstance(a, unreal.StaticMeshActor):
            if lbl.startswith('Wall'):
                a.static_mesh_component.set_material(0, mat('MI_Pared'))
            elif lbl == 'Floor':
                a.static_mesh_component.set_material(0, mat('MI_Moqueta'))
            elif lbl == 'Roof':
                a.static_mesh_component.set_material(0, mat('MI_Negro'))
        if isinstance(a, unreal.PointLight) and lbl in ('PointLight4', 'PointLight5'):
            EAS.destroy_actor(a)

    F = 'Entorno'
    # Tiras de neón a lo largo de las paredes (a 3,4 m de altura)
    neons = [('MI_Neon_Cian', (0, -497, 340), (1000, 4, 6)), ('MI_Neon_Rosa', (0, 497, 340), (1000, 4, 6)),
             ('MI_Neon_Violeta', (-497, 0, 340), (4, 1000, 6)),
             ('MI_Neon_Naranja', (1012, -497, 340), (975, 4, 6)), ('MI_Neon_Cian', (1012, 497, 340), (975, 4, 6)),
             ('MI_Neon_Rosa', (1497, 0, 340), (4, 1000, 6)),
             ('MI_Neon_Violeta', (1012, -497, 20), (975, 4, 4)), ('MI_Neon_Violeta', (1012, 497, 20), (975, 4, 4))]
    for i, (m, c, s) in enumerate(neons):
        box(f'Entorno_Neon{i}', c, s, m, F + '/Neon', collide=False)
    # Marco de neón de la puerta entre salas
    box('Entorno_PuertaNeon_A', (512, -103, 112), (30, 4, 225), 'MI_Neon_Rosa', F + '/Neon', collide=False)
    box('Entorno_PuertaNeon_B', (512, 103, 112), (30, 4, 225), 'MI_Neon_Rosa', F + '/Neon', collide=False)
    box('Entorno_PuertaNeon_C', (512, 0, 227), (30, 210, 4), 'MI_Neon_Rosa', F + '/Neon', collide=False)

    # Rótulos
    sign('Entorno_Rotulo_Salon', 'SALON RECREATIVO P3', (497, 0, 300), 180, 40, (255, 60, 200, 255))
    sign('Entorno_Rotulo_Salon2', 'SALA DE JUEGOS', (528, 0, 300), 0, 30, (60, 220, 255, 255))
    # Luces de ambiente sala B (cubierta)
    light('Entorno_Luz_B1', (800, 0, 360), (0.8, 0.3, 1.0), 12000, 1100)
    light('Entorno_Luz_B2', (1250, 0, 360), (0.3, 0.7, 1.0), 12000, 1100)
    light('Entorno_Luz_A1', (-250, -250, 300), (1.0, 0.4, 0.9), 6000, 900)
    light('Entorno_Luz_A2', (250, 250, 300), (0.4, 0.8, 1.0), 6000, 900)
    # Sofá / zona de descanso junto al spawn (decoración)
    box('Entorno_Sofa_Base', (-430, 0, 20), (80, 220, 40), 'MI_Rojo', F + '/Mobiliario')
    box('Entorno_Sofa_Respaldo', (-475, 0, 60), (20, 220, 80), 'MI_Rojo', F + '/Mobiliario')
    box('Entorno_Alfombra', (-100, 0, 0.6), (300, 300, 1), 'MI_Neon_Violeta', F + '/Mobiliario', collide=False)
    log('entorno OK')


# ---------------------------------------------------------------- bolera


def bowling():
    F = 'Bolera'
    y0 = 280.0           # eje de la pista
    x0 = 600.0           # línea de falta
    head = 700.0         # distancia al bolo delantero
    lane_len = 1500 - x0
    box('Bolera_Pista', (x0 + lane_len / 2, y0, 1), (lane_len, 106, 2), 'MI_MaderaPista', F)
    for s in (-1, 1):
        box(f'Bolera_Canal{"I" if s < 0 else "D"}', (x0 + lane_len / 2, y0 + s * 66, 0.5), (lane_len, 24, 1), 'MI_Negro', F)
        box(f'Bolera_Barrera{"I" if s < 0 else "D"}', (x0 + lane_len / 2, y0 + s * 82, 6), (lane_len, 6, 12), 'MI_Neon_Cian', F)
    box('Bolera_LineaFalta', (x0, y0, 2.2), (2, 106, 0.4), 'MI_Neon_Rojo', F, collide=False)
    # Flechas guía
    for i, dy in enumerate([-30, -15, 0, 15, 30]):
        box(f'Bolera_Flecha{i}', (x0 + 450 - abs(dy) * 1.5, y0 + dy, 2.2), (8, 3, 0.4), 'MI_Neon_Naranja', F, collide=False)
    box('Bolera_Foso', (1490, y0, 30), (20, 220, 60), 'MI_Negro', F)
    sign('Bolera_Rotulo', 'BOLERA', (1497, y0, 180), 180, 50, (60, 220, 255, 255), F)
    light('Bolera_Luz_Bolos', (1330, y0, 250), (1.0, 0.95, 0.85), 15000, 600, F)

    # Bolos en triángulo (separación reglamentaria 30,5 cm)
    pmin, pmax = mesh_bounds('/Game/mesh/bolos/bowling_pin_ball')
    z_pin = 2 - pmin.z + 0.3
    pins = []
    sp = 30.5
    for r in range(4):
        for j in range(r + 1):
            x = x0 + head + r * sp * 0.866
            y = y0 + (j - r / 2.0) * sp
            pins.append(spawn('BP_Bolo', (x, y, z_pin), 0, f'Bolera_Bolo{len(pins) + 1}', F + '/Bolos'))
    # Bola en su soporte junto a la línea de falta
    box('Bolera_Soporte', (x0 - 20, y0 + 115, 35), (40, 40, 70), 'MI_Metal', F)
    bmin, bmax = mesh_bounds('/Game/mesh/bolos/bowling')
    ball = spawn('BP_BolaBolos', (x0 - 20, y0 + 115, 70 - bmin.z + 0.5), 0, 'Bolera_Bola', F)

    st = spawn('BP_Bolera', (x0, y0, 0), 0, 'Bolera_Estacion', F)
    setp(st, 'Bolos', pins)
    setp(st, 'Bola', ball)
    setp(st, 'Objetos', [ball])
    setp(st, 'DistBolos', head)
    # Marcador encima de los bolos mirando al jugador y botón a la izquierda de la línea de falta
    mk = comp(st, 'Marcador')
    mk.set_relative_location(unreal.Vector(head + 60, 0, 190), False, False)
    mk.set_relative_rotation(unreal.Rotator(0, 180, 0), False, False)
    mk.set_relative_scale3d(unreal.Vector(0.2, 0.2, 0.2))
    comp(st, 'BotonBase').set_relative_location(unreal.Vector(-40, -150, 0), False, False)
    comp(st, 'BotonTexto').set_relative_location(unreal.Vector(-40, -150, 112), False, False)
    comp(st, 'BotonTexto').set_relative_rotation(unreal.Rotator(0, 180, 0), False, False)
    log('bolera OK')


# ---------------------------------------------------------------- dardos


def darts():
    F = 'Dardos'
    wall_x = 1500.0
    yb = -300.0
    zc = 173.0
    # Placa de corcho detrás de la diana
    box('Dardos_Placa', (wall_x - 1, yb, zc), (2, 90, 90), 'MI_Corcho', F)
    # Diana: la cara (+Y local de la malla) mira hacia -X (yaw 90). Grosor 4,5 cm.
    st = spawn('BP_Diana', (wall_x - 4 - 0.6, yb, zc), 90, 'Dardos_Diana', F)
    # Componentes de la estación recolocados respecto a la diana (ejes locales: X→+Y mundo, Y→-X mundo)
    mk = comp(st, 'Marcador')
    mk.set_relative_location(unreal.Vector(0, 0, 75), False, False)
    mk.set_relative_rotation(unreal.Rotator(0, 90, 0), False, False)
    comp(st, 'BotonBase').set_relative_location(unreal.Vector(130, 215, -zc), False, False)
    comp(st, 'BotonTexto').set_relative_location(unreal.Vector(130, 215, -zc + 112), False, False)
    comp(st, 'BotonTexto').set_relative_rotation(unreal.Rotator(0, 90, 0), False, False)
    # Línea de lanzamiento a 2,37 m
    throw_x = wall_x - 237
    box('Dardos_LineaLanzamiento', (throw_x, yb, 0.5), (4, 120, 1), 'MI_Neon_Rojo', F, collide=False)
    # Mesa con los dardos
    box('Dardos_Mesa', (throw_x - 40, yb - 90, 45), (50, 40, 90), 'MI_Madera', F)
    dmin, dmax = mesh_bounds('/Game/mesh/dardos/SM_DartboardDarts_Cylinder_001')
    ds = []
    for i in range(3):
        d = spawn('BP_Dardo', (throw_x - 40 + (i - 1) * 12, yb - 90, 90 - dmin.z + 0.5), 0, f'Dardos_Dardo{i + 1}', F)
        ds.append(d)
    setp(st, 'Dardos', ds)
    setp(st, 'Objetos', ds)
    sign('Dardos_Rotulo', 'DARDOS', (wall_x - 3, yb, 290), 180, 45, (255, 80, 60, 255), F)
    light('Dardos_Foco', (wall_x - 150, yb, 300), (1, 0.95, 0.85), 12000, 500, F)
    log('dardos OK')


# ---------------------------------------------------------------- Mr Potato

POTATO_PARTS = ['Bigote', 'Boca1', 'Boca2', 'Brazo1', 'Brazo2', 'Cejas', 'Gorra', 'Nariz', 'Nariz_2', 'Nariz_3',
                'Ojo1', 'Ojo2', 'Ojo3', 'Oreja1', 'Oreja2', 'Oreja3', 'Oreja4', 'Párpado_der', 'Párpado_izq',
                'Sombrero', 'Zapatos1', 'Zapatos2', 'Zapatos3']


def potato():
    F = 'MrPotato'
    cx, cy = -150.0, -330.0
    ped_h = 80.0
    cylinder('MrPotato_Pedestal', (cx, cy, 0), 35, ped_h, 'MI_Neon_Naranja', F)
    st = spawn('BP_MrPotato', (cx, cy, 0), 90, 'MrPotato_Estacion', F)
    comp(st, 'Patata').set_relative_location(unreal.Vector(0, 0, ped_h + 28.3 + 0.5), False, False)
    comp(st, 'BotonTexto').set_relative_rotation(unreal.Rotator(0, 0, 0), False, False)

    # Mostrador con las piezas, contra la pared sur (y=-500)
    counter_y = -455.0
    counter_h = 80.0
    x_start, x_end = -480.0, 480.0
    box('MrPotato_Mostrador', ((x_start + x_end) / 2, counter_y, counter_h / 2), (x_end - x_start + 20, 80, counter_h), 'MI_Madera', F)
    parts = []
    rows = [counter_y, counter_y]
    row_x = [x_start + 5, x_start + 5]
    row = 0
    for name in POTATO_PARTS:
        path = f'/Game/mesh/Mr_Potato/Señor_potato_29_{name}'
        m = unreal.load_asset(path)
        if not m:
            log('falta pieza', name)
            continue
        mn, mx = m.get_bounding_box().min, m.get_bounding_box().max
        w = (mx.x - mn.x)
        if row_x[row] + w > x_end:
            row = 1 - row
            if row_x[row] + w > x_end:
                log('sin sitio', name)
                continue
        px = row_x[row] - mn.x
        p = spawn('BP_PiezaPotato', (px, rows[row], counter_h - mn.z + 0.5), 0, f'MrPotato_{name}', F + '/Piezas')
        comp(p, 'Mesh').set_static_mesh(m)
        setp(p, 'Cuerpo', st)
        parts.append(p)
        row_x[row] += w + 4
        row_x[1 - row] = row_x[row]
    setp(st, 'Piezas', parts)
    setp(st, 'Objetos', parts)
    sign('MrPotato_Rotulo', 'MR. POTATO', (cx, -497, 300), 90, 45, (255, 150, 40, 255), F)
    light('MrPotato_Foco', (cx, cy + 60, 260), (1, 0.85, 0.6), 9000, 500, F)
    log('potato OK', len(parts), 'piezas')


# ---------------------------------------------------------------- Rompe-Ralph


def smash():
    F = 'RompeRalph'
    cx, cy = 250.0, 330.0
    box('RompeRalph_Pedestal', (cx, cy, 20), (110, 60, 40), 'MI_Metal', F)
    scale = 0.3
    pmin, pmax = mesh_bounds('/Game/mesh/pinata/pinata_mesh')
    px = cx - (pmin.x + pmax.x) / 2 * scale
    pz = 40 - pmin.z * scale + 1
    pin = spawn('BP_Pinata', (px, cy, pz), 0, 'RompeRalph_Pinata', F)
    pin.set_actor_scale3d(unreal.Vector(scale, scale, scale))
    st = spawn('BP_RompeRalph', (cx, cy - 10, 0), -90, 'RompeRalph_Estacion', F)
    comp(st, 'Marcador').set_relative_location(unreal.Vector(0, 0, 230), False, False)
    # Mesa del martillo
    box('RompeRalph_Mesa', (cx - 170, cy - 80, 40), (60, 40, 80), 'MI_Madera', F)
    ham = spawn('BP_Martillo', (cx - 190, cy - 80, 86), label='RompeRalph_Martillo', fold=F, rot=unreal.Rotator(0, 0, -90))
    setp(ham, 'Estacion', st)
    setp(st, 'Objetivo', pin)
    setp(st, 'Objetos', [ham])
    sign('RompeRalph_Rotulo', 'ROMPE-RALPH', (cx, 497, 300), -90, 45, (190, 90, 255, 255), F)
    light('RompeRalph_Foco', (cx, cy - 80, 260), (0.9, 0.7, 1.0), 9000, 500, F)
    log('rompe-ralph OK')


def main():
    try:
        unreal.EditorLoadingAndSavingUtils.load_map(MAP)
        clean()
        environment()
        bowling()
        darts()
        potato()
        smash()
        unreal.EditorLoadingAndSavingUtils.save_current_level()
        log('nivel guardado')
    except Exception:
        log('FATAL', traceback.format_exc())
    open(os.path.join(TOOLS, 'build_level.txt'), 'w', encoding='utf-8').write('\n'.join(LOG))


main()
