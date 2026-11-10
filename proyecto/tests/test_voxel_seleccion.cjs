// Ejecutar con node --test proyecto/tests/test_voxel_seleccion.cjs
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const html=fs.readFileSync(path.join(__dirname,'../visor_e08/index.html'),'utf8');
const script=html.split('<script>')[1].split('</script>')[0];
new vm.Script(script);
const funciones=script.slice(script.indexOf('function puntoEnPoligono'),script.indexOf('function prepararCanvas'));

function escenario(){
  const controles={tiempo:{value:'0'},corte:{value:'1'},limpiarvoxel:{},voxeltemperatura:{},voxeldetalle:{},voxelinstante:{}};
  const c={$:id=>controles[id],seleccionVoxel:0,frames:[[21],[22.5],[NaN]],poligonosPantalla:[],
    visibles:()=>new Set([2]),dibujar:()=>{},resultado:{indices:[[1,2,3]],vertida_id:[2],
      origen_m:[-1,-2,0],pasos_m:[.5,.5,.05],fotogramas:[
        {tiempo_h:6,fecha_hora:'2026-11-27T10:00'},
        {tiempo_h:8,fecha_hora:'2026-11-27T12:00'},
        {tiempo_h:0,fecha_hora:'2026-11-27T04:00'}]}};
  vm.createContext(c);vm.runInContext(funciones,c);return {c,controles};
}
const cuadrado=(voxel,tamano=10)=>({voxel,p:[[0,0,0],[tamano,0,0],[tamano,tamano,0],[0,tamano,0]]});

test('un clic elige la cara que realmente se dibujó encima',()=>{
  const {c}=escenario(),fondo=cuadrado(0),frente=cuadrado(1,5);
  assert.equal(c.caraEnPunto([fondo,frente],2,2),frente);
  assert.equal(c.caraEnPunto([fondo,frente],8,8),fondo);
  assert.equal(c.caraEnPunto([fondo,frente],12,12),null);
});
test('la temperatura sigue el mismo voxel y usa sus coordenadas de centro',()=>{
  const {c,controles}=escenario();c.actualizarVoxel();
  assert.equal(controles.voxeltemperatura.textContent,'21.00 °C');
  assert.ok(controles.voxeldetalle.textContent.includes('-0.250, -0.750, 0.175'));
  assert.ok(controles.voxeldetalle.textContent.includes('V2'));
  controles.tiempo.value='1';c.actualizarVoxel();
  assert.equal(controles.voxeltemperatura.textContent,'22.50 °C');
  assert.ok(controles.voxelinstante.textContent.includes('12:00'));
  assert.equal(c.seleccionVoxel,0);
  controles.tiempo.value='2';c.actualizarVoxel();
  assert.equal(controles.voxeltemperatura.textContent,'Todavía no vertido');
});
test('selección bajo moldaje y bloqueo de triángulos IFC sin voxel',()=>{
  const {c,controles}=escenario();c.seleccionVoxel=null;
  c.poligonosPantalla=[{...cuadrado(0),moldaje:true}];c.seleccionarEnVista(2,2);
  assert.equal(c.seleccionVoxel,0);
  c.poligonosPantalla.push(cuadrado(undefined));c.seleccionarEnVista(2,2);
  assert.equal(c.seleccionVoxel,0);
  assert.ok(controles.voxeldetalle.textContent.includes('cambia Mostrar'));
});
test('clic consulta; arrastrar gira sin seleccionar; cancelar no selecciona',()=>{
  const {c}=escenario(),clics=[];
  c.arrastre=null;c.yaw=0;c.pitch=0;c.requestAnimationFrame=()=>{};
  c.canvas={setPointerCapture:()=>{},getBoundingClientRect:()=>({left:100,top:200})};
  c.seleccionarEnVista=(x,y)=>clics.push([x,y]);
  vm.runInContext(script.slice(script.indexOf('canvas.onpointerdown='),script.indexOf("canvas.addEventListener('wheel'")),c);
  const e={clientX:110,clientY:220,pointerId:1,button:0};
  c.canvas.onpointerdown(e);c.canvas.onpointerup(e);
  assert.deepEqual(clics,[[10,20]]);
  c.canvas.onpointerdown(e);c.canvas.onpointermove({...e,clientX:130});c.canvas.onpointerup({...e,clientX:130});
  assert.equal(clics.length,1);assert.notEqual(c.yaw,0);
  c.canvas.onpointerdown(e);c.canvas.onpointercancel();c.canvas.onpointerup(e);
  assert.equal(clics.length,1);
});
test('quitar selección limpia el panel sin cambiar los datos',()=>{
  const {c,controles}=escenario();c.seleccionVoxel=null;c.actualizarVoxel();
  assert.equal(controles.voxeltemperatura.textContent,'— °C');
  assert.equal(controles.limpiarvoxel.disabled,true);
  assert.deepEqual(c.frames,[[21],[22.5],[NaN]]);
});
