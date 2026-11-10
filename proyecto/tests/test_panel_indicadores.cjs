// Prueba de integración del panel con DOM/canvas simulados, sin navegador ni paquetes externos.
const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const A=require('../visor_e08/analisis.js');
const html=fs.readFileSync(path.join(__dirname,'../visor_e08/index.html'),'utf8');
const principal=html.split('<script>')[1].split('</script>')[0];new vm.Script(principal);
const fuente=principal.slice(principal.indexOf('const numeroAnalisis='),principal.indexOf('function visibles()'));
class Elemento{
 constructor(){this.value='';this.children=[];this.style={};this.textContent='';this.hidden=false;}
 append(...nodos){this.children.push(...nodos);}
 replaceChildren(...nodos){this.children=[...nodos];}
 getBoundingClientRect(){return {width:600,height:255};}
 getContext(){return new Proxy({},{get:(obj,key)=>obj[key]??(()=>{}),set:(obj,key,value)=>(obj[key]=value,true)});}
}
function muestra(){const serie={vertida_id:1,inicio_h:0,maxima_C:[18,60,50],superficie_min_C:[18,20,20],delta_C:[0,40,30],pico:{valor_C:60,tiempo_h:24},diferencial_maximo:{valor_C:40,tiempo_h:24}};return {
 ifc_sha256:'geometria',pasos_m:[.5,.5,.05],vertida_id:[1],fotogramas:[{tiempo_h:0},{tiempo_h:24},{tiempo_h:48}],
 indicadores:{version:1,resumen:{pico:{valor_C:60,tiempo_h:24,vertida_id:1},diferencial_maximo:{valor_C:40,tiempo_h:24,vertida_id:1},numero_vertidas:1,ventana_colocaciones_h:0,ultima_colocacion_h:0,duracion_h:48,observacion_ultima_vertida_h:48},
 criterios:{T_max_C:70,delta_T_C:20,profundidad_superficie_m:.025,alcance:'Docente'},series:{tiempos_h:[0,24,48],maxima_global_C:[18,60,50],por_vertida:[serie]},sondas:[{vertida_id:1,tipo:'nucleo',centro_m:[0,0,1],tiempos_h:[0,24,48],temperatura_C:[18,58,45]},{vertida_id:1,tipo:'borde',centro_m:[1,0,1],tiempos_h:[0,24,48],temperatura_C:[18,25,20]}],colocaciones:[{vertida_id:1,inicio_h:0,incluida_en_horizonte:true,anterior_id:null,intervalo_h:null,previa_media_C:null,previa_maxima_C:null,previa_nucleo_C:null,interfaz_media_C:null,contactos:[]}],juntas:'No evaluadas',muestreo:'Registros guardados'}};}
function entorno(resultado){const nodos={},$=id=>nodos[id]??(nodos[id]=new Elemento());$('tiempo').value='1';$('ejeanalisis').value='obra';$('metricacomparacion').value='maxima';
 const c={AnalisisTermico:A,$,resultado,frames:[[18],[58],[45]],seleccionVoxel:null,referenciaEscenario:null,document:{createElement:()=>new Elemento()},
  opcion:(sel,valor,texto)=>{const o=new Elemento();o.value=valor;o.textContent=texto;sel.append(o);},sessionStorage:{getItem:()=>null,setItem:()=>{},removeItem:()=>{}},mensaje:()=>{}};
 vm.createContext(c);vm.runInContext(fuente,c);return {c,$};}

test('el panel muestra picos, tabla, sondas y comparación usando sus funciones reales',()=>{const {c,$}=entorno(muestra());c.prepararAnalisis();c.actualizarAnalisis();
 assert.equal($('picoglobal').textContent,'60.00 °C');assert.equal($('picodelta').textContent,'40.00 K');assert.equal($('resumenvertidas').children.length,1);assert.equal($('tablacolocaciones').children.length,1);
 assert.ok($('posicionessondas').textContent.includes('Núcleo fijo'));$('fijarreferencia').onclick();assert.equal($('tablacomparacion').children.length,4);
 $('ejeanalisis').value='edad';c.actualizarAnalisis();$('metricacomparacion').value='delta';c.actualizarAnalisis();c.seleccionVoxel=0;c.actualizarAnalisis();
 assert.equal($('leyendasondas').children.length,3);$('quitarreferencia').onclick();assert.equal($('tablacomparacion').children.length,0);
});
test('la corrida antigua conserva su pico y no inventa el diferencial',()=>{const r=muestra();delete r.indicadores;for(let i=0;i<3;i++)r.fotogramas[i].Tmax_C=[18,60,50][i];const {c,$}=entorno(r);c.prepararAnalisis();c.actualizarAnalisis();assert.equal($('picoglobal').textContent,'60.00 °C');assert.equal($('picodelta').textContent,'—');assert.ok($('alcanceindicadores').textContent.includes('Resultado anterior'));});
if(process.env.MCPLAN_RESULTADO_QA)test('postproceso de la corrida real recuperada llega a todos los paneles',()=>{const r=JSON.parse(fs.readFileSync(process.env.MCPLAN_RESULTADO_QA,'utf8')),{c,$}=entorno(r);c.prepararAnalisis();c.actualizarAnalisis();assert.ok(Number.parseFloat($('picoglobal').textContent)>0);assert.equal($('tablacolocaciones').children.length,r.indicadores.colocaciones.length);$('fijarreferencia').onclick();assert.equal($('tablacomparacion').children.length,4);});
