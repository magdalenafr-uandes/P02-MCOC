// Pruebas de las caras renderizadas usando las funciones reales del visor.
// Ejecutar: node --test proyecto/tests/test_moldaje_visor.cjs
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const html = fs.readFileSync(path.join(__dirname, '../visor_e08/index.html'), 'utf8');
const script = html.split('<script>')[1].split('</script>')[0];
new vm.Script(script);
const funciones = script.slice(script.indexOf('function datosMoldajes'), script.indexOf('function prepararCanvas'));

function escenario(t=71) {
  const controles = {tiempo: {value: '0'}, modo: {value: 'temperatura'}, corte: {value: '10'},
    vermoldaje: {getAttribute: () => 'true'}};
  const resultado = {indices: [[0,0,0],[1,0,0]], vertida_id: [1,2], forma: [2,1,1],
    origen_m: [0,0,0], pasos_m: [1,1,1], paso_m: 1, fotogramas: [{tiempo_h: t}],
    moldajes: [{vertida_id:1,inicio_h:0,retiro_h:72,R:.12}, {vertida_id:2,inicio_h:6,retiro_h:78,R:.12}], mallas: []};
  const visibles = new Set([1,2]);
  const c = {$: id => controles[id], resultado, frames: [[30,32]], facesCache: null,
    visibles: () => visibles, base: {vertidas: [{id:1},{id:2}]}, colores: ['#ffffff','#cccccc'],
    colorT: () => [1,2,3], rgb: () => [4,5,6]};
  vm.createContext(c); vm.runInContext(funciones,c);
  return {c,controles,visibles};
}

test('retiro individual exacto y restauración al retroceder el reloj', () => {
  const {c} = escenario();
  assert.equal(c.caras().filter(f=>f.moldaje).length, 6);
  c.resultado.fotogramas[0].tiempo_h=72;c.facesCache=null;
  assert.equal(c.caras().filter(f=>f.moldaje).length, 3);
  c.resultado.fotogramas[0].tiempo_h=78;c.facesCache=null;
  assert.equal(c.caras().filter(f=>f.moldaje).length, 0);
  c.resultado.fotogramas[0].tiempo_h=71;c.facesCache=null;
  assert.equal(c.caras().filter(f=>f.moldaje).length, 6);
});

test('ocultar una vertida no inventa moldaje en la interfaz interior', () => {
  const {c,visibles} = escenario();visibles.delete(2);
  assert.equal(c.caras().filter(f=>f.moldaje).length, 3);
});

test('no se dibuja moldaje de vertidas futuras, cortes ni caras superiores', () => {
  const {c,controles} = escenario(0);c.frames[0][1]=NaN;
  const paneles = c.caras().filter(f=>f.moldaje);
  assert.equal(paneles.length,4);
  assert.ok(paneles.every(f=>new Set(f.v.map(p=>p[2])).size>1));
  controles.corte.value='-1';c.facesCache=null;
  assert.equal(c.caras().length,0);
});

test('el botón solo cambia la vista y el modo IFC también muestra moldaje', () => {
  const {c,controles} = escenario();
  controles.vermoldaje.getAttribute=()=>'false';
  assert.equal(c.caras().filter(f=>f.moldaje).length,0);
  controles.vermoldaje.getAttribute=()=>'true';controles.modo.value='ifc';c.facesCache=null;
  assert.equal(c.caras().filter(f=>f.moldaje).length,6);
  assert.deepEqual(c.frames[0],[30,32]);
});

test('resultados anteriores usan el caso ejecutado, no las entradas nuevas', () => {
  const {c} = escenario(72);delete c.resultado.moldajes;
  c.resultado.caso_ejecutado={vertidas:{defecto:{moldaje:'madera',retiro_moldaje_h:72}},
    protecciones:{madera:{espesor_m:.018,k_W_mK:.15}}};
  c.resultado.plan={vertidas:[{id:1,inicio_h:0},{id:2,inicio_h:6}]};
  assert.deepEqual(Array.from(c.moldajesActivos()),[2]);
});
