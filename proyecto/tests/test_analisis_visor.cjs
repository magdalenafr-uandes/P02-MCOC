const {test}=require('node:test'),assert=require('node:assert/strict');
const A=require('../visor_e08/analisis.js');
function resultado(){return {ifc_sha256:'a',pasos_m:[.5,.5,.05],caso_ejecutado:{simulacion:{inicio:'2026-11-27T04:00'},ambiente:{T_C:16},hormigones:{M1:{k:2.22}},vertidas:{1:{inicio_h:0,T_colocacion_C:18}}},indicadores:{version:1,
 resumen:{pico:{valor_C:60},diferencial_maximo:{valor_C:30},duracion_h:336,ventana_colocaciones_h:24,observacion_ultima_vertida_h:312},
 series:{tiempos_h:[0,24,48],maxima_global_C:[18,60,55],por_vertida:[{vertida_id:1,inicio_h:24,maxima_C:[null,18,40],delta_C:[null,0,20]}]},
 sondas:[{vertida_id:1,tipo:'nucleo',tiempos_h:[0,24,48],temperatura_C:[null,18,40]}]}};}
test('el pico es de toda la serie, no su último valor',()=>{assert.deepEqual(A.pico([18,60,55],[0,24,48]),{valor_C:60,tiempo_h:24});});
test('edad local y ausencia de datos antes de colocar',()=>{const r=resultado();assert.deepEqual(A.seriesPorVertida(r.indicadores,'maxima_C',true)[0].puntos,[[0,18],[24,40]]);assert.deepEqual(A.seriesSondas(r.indicadores,1,true)[0].puntos,[[0,18],[24,40]]);});
test('referencia independiente del resultado y cambios absolutos',()=>{const r=resultado(),ref=JSON.parse(JSON.stringify(A.referenciaCompacta(r,'base')));r.indicadores.resumen.pico.valor_C=55;const actual=A.referenciaCompacta(r,'actual');assert.equal(A.filasComparacion(actual,ref)[0].cambio,-5);assert.ok(!('fotogramas' in ref));assert.equal(ref.nombre,'base');});
test('advierte mallas, horizontes, edades y variables confundidas',()=>{const ref=A.referenciaCompacta(resultado(),'base'),r=resultado();r.pasos_m=[1,1,.05];r.indicadores.resumen.duracion_h=168;r.indicadores.resumen.observacion_ultima_vertida_h=144;r.caso_ejecutado.ambiente.T_C=25;const avisos=A.advertenciasComparacion(A.referenciaCompacta(r,'variante'),ref);assert.equal(avisos.length,4);});
test('cambiar solo los inicios no se confunde con cambiar el material',()=>{const ref=A.referenciaCompacta(resultado(),'base'),r=resultado();r.caso_ejecutado.vertidas[1].inicio_h=24;assert.equal(A.advertenciasComparacion(A.referenciaCompacta(r,'variante'),ref).length,0);});
test('rechaza una referencia antigua sin indicadores',()=>{assert.throws(()=>A.referenciaCompacta({fotogramas:[]},'antiguo'),/indicadores nuevos/);});
test('el diferencial comparado se toma por pieza, no cruzando piezas distintas',()=>{const r=resultado();assert.deepEqual(A.serieComparacion(r.indicadores,'delta'),[[0,null],[24,0],[48,20]]);});
