# Práctica 3: Salón recreativo VR

Proyecto de Unreal Engine 5.8 con el Meta XR Plugin y el Meta XR Simulator. Es un salón recreativo en realidad virtual con los cuatro minijuegos del enunciado: bolos, Rompe-Ralph, Mr. Potato y dardos. Todo está hecho con **Blueprints**, sin C++, así que abre en cualquier UE 5.8 sin compilar.

## Cómo abrirlo

1. Doble clic en `LanzarConSimulador.bat`. Abre UE 5.8 con el Meta XR Simulator portable activado solo para esa sesión.
2. Se abre el mapa de inicio, `Content/Practica3/L_Practica3_VR`.
3. **Play → VR Preview**. Se abre la ventana del simulador.

Para probar sin VR hay un mapa gemelo, `Content/Practica3/L_Practica3_PC`, que se juega con teclado y ratón con el **Play** normal.

## Controles

### VR (Meta XR Simulator o gafas Quest)
| Acción | Control |
|---|---|
| Agarrar / soltar | **Grip o gatillo** del mando. Si no hay nada al alcance de la mano, se coge el objeto al que apunta el mando (hasta 4 m) |
| Lanzar | Soltar mientras mueves la mano |
| Teletransporte | Stick derecho hacia delante, apuntar y soltar |
| Reiniciar un minijuego | Acercar la mano a la seta roja **REINICIAR** de cada estación |

En el simulador: haz clic dentro de la vista 3D para darle el foco, elige el mando con **[ / ]**, apunta y haz clic. La altura de los ojos la marca el visor (panel *Inputs → Headset*).

### PC (mapa `L_Practica3_PC`)
| Acción | Control |
|---|---|
| Andar / saltar / mirar | WASD / Espacio / ratón |
| Agarrar / soltar | Clic izquierdo apuntando con la cruz |
| Lanzar | Clic derecho mientras sostienes algo |
| Reiniciar un minijuego | Clic sobre el botón REINICIAR |

## Minijuegos

Cada estación tiene un **marcador** (widget UMG `WBP_Marcador` en un WidgetComponent) que muestra puntos y mensajes, y un **botón físico de reinicio** que devuelve todos sus objetos a su sitio.

### Bolera (sala cubierta, lado norte)
- 10 bolos (`BP_Bolo`, malla `mesh/bolos/bowling_pin_ball`) en triángulo, con la separación reglamentaria de 30,5 cm y física.
- Bola (`BP_BolaBolos`, malla `mesh/bolos/bowling`) con el **componente Grab** de la plantilla.
- `BP_Bolera` detecta el lanzamiento, cuenta los bolos derribados y lleva una partida de 10 frames con 2 tiradas: retira los caídos, recoloca los bolos y devuelve la bola.

### Dardos (sala cubierta, pared del fondo)
- Diana (`mesh/dardos`) a 1,73 m de altura, con línea de lanzamiento a 2,37 m.
- 3 dardos (`BP_Dardo`) con componente Grab. En vuelo apuntan según la trayectoria y, si entran de frente, **se quedan clavados (attach)** en la diana.
- Puntuación real: sectores, dobles, triples, 25 y bull. Las rondas son de 3 dardos.

### Mr. Potato (patio, sur)
- Cuerpo central (`BP_MrPotato`) sobre un pedestal y 23 piezas (`BP_PiezaPotato`) en el mostrador.
- Si sueltas una pieza **tocando el cuerpo, se queda pegada (attach)**. El cuerpo se ilumina mientras la pieza lo toca.

### Rompe-Ralph (patio, norte)
- Piñata convertida en **Geometry Collection** (`Fractura/GC_Pinata`) con fractura Voronoi en dos niveles. La genera el grafo Dataflow `Fractura/DF_Pinata`.
- Martillo (`BP_Martillo`) con componente Grab. Si su cabeza golpea la piñata a suficiente velocidad, aplica un campo de deformación y rompe la piñata en trozos que caen con física.
- La piñata está "dormida" (quieta) hasta el primer golpe. El reinicio la regenera intacta.

### Lanzamiento con inercia
Los objetos guardan la velocidad de la mano mientras están agarrados y la aplican al soltarlos. La plantilla, por sí sola, los dejaría caer a plomo.

## Entorno personalizado
Las salas de la plantilla se han convertido en un salón recreativo: moqueta, paredes azul noche, tiras de neón, rótulos para cada juego, iluminación de colores en tiempo real (Lumen) y postproceso para que no deslumbre en VR. El navmesh se genera en tiempo de ejecución, así que el teletransporte funciona sobre la geometría nueva.

## Organización
```
Content/Practica3/
  L_Practica3_VR, L_Practica3_PC   mapas
  Blueprints/   estaciones, objetos, jugador y modo de juego de PC
  UI/           WBP_Marcador, WBP_Mira
  Fractura/     DF_Pinata (Dataflow), GC_Pinata (Geometry Collection)
  Materiales/   materiales del entorno y neones
Tools/GeneradorPython/   scripts de Python del editor que generaron todo lo anterior
```
