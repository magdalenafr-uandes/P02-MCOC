/* Preparación de indicadores y gráficos. Los resultados térmicos provienen de Python. */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.AnalisisTermico=api;})(typeof globalThis!=='undefined'?globalThis:this,function(){
'use strict';
const finito=v=>typeof v==='number'&&Number.isFinite(v);
const colores=['#81c9bd','#eabf66','#aeb2ff','#f39cb4','#90d389','#80c9ed'];
function pico(valores,tiempos){let valor=null,t=null;for(let i=0;i<valores.length;i++)if(finito(valores[i])&&(valor===null||valores[i]>valor)){valor=valores[i];t=tiempos[i];}return {valor_C:valor,tiempo_h:t};}
function firma(r){return JSON.stringify({ifc:r.ifc_sha256,pasos:r.pasos_m||r.paso_m,clima:r.caso_ejecutado?.ambiente,hormigones:r.caso_ejecutado?.hormigones});}
function advertenciasComparacion(actual,referencia){const a=actual.indicadores,b=referencia.indicadores,m=[];
 if(actual.ifc_sha256!==referencia.ifc_sha256)m.push('La geometría IFC es distinta.');
 if(JSON.stringify(actual.pasos_m)!==JSON.stringify(referencia.pasos_m))m.push('La resolución de malla es distinta.');
 if(a?.resumen.duracion_h!==b?.resumen.duracion_h)m.push('Los horizontes de observación son distintos.');
 if(a?.resumen.observacion_ultima_vertida_h!==b?.resumen.observacion_ultima_vertida_h)m.push('La última vertida tiene distinta edad al finalizar: revisar también sus curvas por edad.');
 if(JSON.stringify(actual.contexto)!==JSON.stringify(referencia.contexto))m.push('Cambian material, clima, fecha o protecciones: el efecto no se puede atribuir solo al intervalo.');
 return m;}
function contexto(r){const c=r.caso_ejecutado||{};return {hormigones:c.hormigones,ambiente:c.ambiente,clima:c.clima,inicio:c.simulacion?.inicio,base:c.base,suelo:c.suelo,
 protecciones:c.protecciones,vertidas:Object.fromEntries(Object.entries(c.vertidas||{}).map(([id,v])=>[id,Object.fromEntries(Object.entries(v).filter(([k])=>!['inicio','inicio_h'].includes(k)))]))};}
function referenciaCompacta(r,nombre){if(r?.indicadores?.version!==1||!r.indicadores.resumen?.pico||!r.indicadores.resumen?.diferencial_maximo||!Array.isArray(r.indicadores.series?.tiempos_h)||!Array.isArray(r.indicadores.series.maxima_global_C)||!Array.isArray(r.indicadores.series.por_vertida))throw Error('El archivo no contiene los indicadores nuevos. Ejecuta de nuevo ese caso con esta versión.');
 return {nombre,ifc_sha256:r.ifc_sha256,pasos_m:r.pasos_m||[r.paso_m,r.paso_m,r.paso_m],contexto:r.contexto||contexto(r),indicadores:r.indicadores};}
function filasComparacion(actual,referencia){const a=actual.indicadores?.resumen,b=referencia.indicadores?.resumen;if(!a||!b)return [];
 return [ ['Temperatura máxima','°C',b.pico.valor_C,a.pico.valor_C],['Diferencial máximo por vertida','K',b.diferencial_maximo.valor_C,a.diferencial_maximo.valor_C],
 ['Ventana de colocaciones','h',b.ventana_colocaciones_h,a.ventana_colocaciones_h],['Edad final de la última vertida','h',b.observacion_ultima_vertida_h,a.observacion_ultima_vertida_h] ].map(([nombre,unidad,ref,valor])=>({nombre,unidad,referencia:ref,actual:valor,cambio:finito(ref)&&finito(valor)?valor-ref:null}));}
function seriesPorVertida(indicadores,clave,porEdad=false){return (indicadores?.series.por_vertida||[]).map((v,i)=>({nombre:'V'+v.vertida_id,color:colores[i%colores.length],
 puntos:indicadores.series.tiempos_h.map((t,k)=>[porEdad?t-v.inicio_h:t,v[clave][k]]).filter(p=>p[0]>=0)}));}
function seriesSondas(indicadores,vid,porEdad=false){const inicio=indicadores?.series.por_vertida.find(v=>String(v.vertida_id)===String(vid))?.inicio_h||0;
 return (indicadores?.sondas||[]).filter(s=>String(s.vertida_id)===String(vid)).map(s=>({nombre:s.tipo==='nucleo'?'Núcleo fijo':'Borde fijo',color:s.tipo==='nucleo'?'#f5b46b':'#79b8ff',
 puntos:s.tiempos_h.map((t,i)=>[porEdad?t-inicio:t,s.temperatura_C[i]]).filter(p=>p[0]>=0),sonda:s}));}
function serieComparacion(indicadores,metrica){const s=indicadores.series;return s.tiempos_h.map((t,i)=>{if(metrica!=='delta')return [t,s.maxima_global_C[i]];const valores=s.por_vertida.map(v=>v.delta_C[i]).filter(finito);return [t,valores.length?Math.max(...valores):null];});}
function graficar(canvas,series,{cursor=null,umbral=null,unidad='°C',edad=false,eventos=[]}={}){
 const rect=canvas.getBoundingClientRect(),w=rect.width,h=rect.height,dpr=Math.min(globalThis.devicePixelRatio||1,2);
 canvas.width=Math.max(1,Math.round(w*dpr));canvas.height=Math.max(1,Math.round(h*dpr));const c=canvas.getContext('2d');c.setTransform(dpr,0,0,dpr,0,0);c.clearRect(0,0,w,h);
 const puntos=series.flatMap(s=>s.puntos).filter(p=>finito(p[0])&&finito(p[1]));c.font='12px system-ui';c.fillStyle='#aec0cb';
 if(!puntos.length){c.fillText('Sin datos para este gráfico.',16,30);return;}
 const x0=52,y0=20,x1=w-18,y1=h-34;
 let xmin=Math.min(0,...puntos.map(p=>p[0])),xmax=Math.max(1,...puntos.map(p=>p[0]));
 let ymin=Math.min(...puntos.map(p=>p[1]),...(finito(umbral)?[umbral]:[])),ymax=Math.max(...puntos.map(p=>p[1]),...(finito(umbral)?[umbral]:[]));
 const margen=Math.max(1,(ymax-ymin)*.12);ymin-=margen;ymax+=margen;
 const x=t=>x0+(t-xmin)/(xmax-xmin)*(x1-x0),y=T=>y1-(T-ymin)/(ymax-ymin)*(y1-y0);
 c.lineWidth=1;for(let i=0;i<=4;i++){const T=ymin+(ymax-ymin)*i/4;c.strokeStyle='#304957';c.beginPath();c.moveTo(x0,y(T));c.lineTo(x1,y(T));c.stroke();c.fillStyle='#aec0cb';c.fillText(T.toFixed(1),5,y(T)+4);}
 for(let i=0;i<=4;i++){const t=xmin+(xmax-xmin)*i/4;c.fillText(t.toFixed(0),x(t)-8,h-16);}
 c.fillText(unidad,5,12);c.fillText(edad?'Edad de la vertida [h]':'Horas desde inicio de obra',Math.max(x0,w-190),h-2);
 if(finito(umbral)){c.strokeStyle='#ff9b8b';c.setLineDash([5,4]);c.beginPath();c.moveTo(x0,y(umbral));c.lineTo(x1,y(umbral));c.stroke();c.setLineDash([]);}
 if(!edad)for(const e of eventos){if(e.inicio_h<xmin||e.inicio_h>xmax)continue;c.strokeStyle='#49616c';c.setLineDash([2,4]);c.beginPath();c.moveTo(x(e.inicio_h),y0);c.lineTo(x(e.inicio_h),y1);c.stroke();c.setLineDash([]);}
 c.save();c.beginPath();c.rect(x0,y0,x1-x0,y1-y0);c.clip();
 for(const s of series){c.strokeStyle=s.color;c.lineWidth=2;c.beginPath();let conectado=false;for(const p of s.puntos){if(!finito(p[1])||!finito(p[0])){conectado=false;continue;}if(conectado)c.lineTo(x(p[0]),y(p[1]));else c.moveTo(x(p[0]),y(p[1]));conectado=true;}c.stroke();}
 if(finito(cursor)&&cursor>=xmin&&cursor<=xmax){c.strokeStyle='#f3c77c';c.lineWidth=1;c.beginPath();c.moveTo(x(cursor),y0);c.lineTo(x(cursor),y1);c.stroke();}c.restore();
}
return {pico,finito,referenciaCompacta,filasComparacion,advertenciasComparacion,seriesPorVertida,seriesSondas,serieComparacion,graficar,firma,contexto,colores};
});
