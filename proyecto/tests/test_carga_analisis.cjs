// El HTML debe funcionar aunque un servidor anterior no publique /analisis.js.
const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const carpeta=path.join(__dirname,'../visor_e08');
const html=fs.readFileSync(path.join(carpeta,'index.html'),'utf8').replaceAll('\r\n','\n');
const inicio='// BEGIN ANALISIS_TERMICO_GENERADO\n',fin='// END ANALISIS_TERMICO_GENERADO\n';
test('la biblioteca viaja en el HTML y coincide con su fuente',()=>{
 assert.ok(!html.includes('<script src="/analisis.js">'));
 const biblioteca=html.split(inicio)[1]?.split(fin)[0];
 assert.ok(biblioteca,'Falta la biblioteca dentro del HTML');
 assert.equal(biblioteca,fs.readFileSync(path.join(carpeta,'analisis.js'),'utf8').replaceAll('\r\n','\n').trimEnd()+'\n');
 const c={};vm.createContext(c);vm.runInContext(biblioteca,c);
 assert.equal(typeof c.AnalisisTermico.graficar,'function');
 assert.equal(typeof c.AnalisisTermico.referenciaCompacta,'function');
});
test('el script completo es válido después de incluir la biblioteca',()=>{
 new vm.Script(html.split('<script>')[1].split('</script>')[0]);
});
