"""App local para anonimizar documentos (.txt, .docx y .pdf).

Uso:  python app.py   ->  abre el navegador en http://127.0.0.1:18765
Empaquetada: doble clic en Anonimizador.exe (no necesita Python instalado).
Todo ocurre en tu computador: no se envía nada a internet.
La app se cierra sola unos minutos después de cerrar la pestaña, o con el botón «Cerrar».
"""
import base64
import json
import socket
import sys
import threading
import time
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from anonimizador import TIPOS, anonimizar, leer_docx

try:  # El soporte de PDF necesita PyMuPDF; sin él la app sigue funcionando con .txt y .docx.
    from pdf_anon import anonimizar_pdf, leer_pdf
    HAY_PDF = True
except ImportError:
    HAY_PDF = False

PUERTO = 18765  # poco común; si está ocupado se usa otro libre
VERSION = "4"  # súbela en cada entrega: una versión nueva cierra la vieja si está abierta
_FIRMA_BASE = "anonimizador-local-ok"
FIRMA = f"{_FIRMA_BASE} v{VERSION}"
SIN_LATIDO_SEG = 300  # si la pestaña lleva 5 minutos cerrada, la app se apaga

PAGINA = r"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Anonimizador local</title>
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Crect x='2' y='2' width='60' height='60' rx='14' fill='%231F63B5'/%3E%3Crect x='16' y='10' width='32' height='44' rx='4' fill='white'/%3E%3Crect x='21' y='25' width='16' height='5' fill='%2313233A'/%3E%3Crect x='21' y='41' width='12' height='5' fill='%2313233A'/%3E%3C/svg%3E">
<style>
:root{--bg:#F2F5F9;--card:#FFFFFF;--ink:#13233A;--mute:#5F6F84;--line:#DCE3EC;--acc:#1F63B5;--acc2:#E8F0FB;
 --ok:#1D7A4E;--ok2:#E7F5EE;--warn:#9A5B00;--warn2:#FFF4E2;--bad:#A8323A;--bad2:#FDEDEE;--mark:#FFE7A3;--sombra:0 1px 3px rgba(19,35,58,.08)}
@media (prefers-color-scheme:dark){:root{--bg:#0F1724;--card:#172234;--ink:#E6EDF6;--mute:#9AABC0;--line:#2A3950;--acc:#6EA8F0;
 --acc2:#1D2E48;--ok:#5CC796;--ok2:#163328;--warn:#F0B35A;--warn2:#3A2C14;--bad:#F08A92;--bad2:#3A1C20;--mark:#5C4A12}}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.5 "Segoe UI",system-ui,Arial,sans-serif}
main{max-width:1080px;margin:0 auto;padding:20px 16px 48px;display:grid;gap:18px}
header{display:flex;align-items:flex-start;gap:14px;flex-wrap:wrap}.titulo{flex:1 1 300px}
.titulo .privado{display:inline-block;margin-top:8px}
.logo{width:46px;height:46px;flex:none}
header h1{margin:0;font-size:24px;line-height:1.2}header p{margin:2px 0 0;color:var(--mute);font-size:15px}
.sello{margin-left:auto;display:flex;gap:10px;align-items:center;flex-wrap:wrap}
.privado{background:var(--ok2);color:var(--ok);border-radius:999px;padding:6px 12px;font-size:14px;font-weight:600}
.card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:20px;box-shadow:var(--sombra);display:grid;gap:14px}
.paso{display:flex;align-items:center;gap:10px;margin:0;font-size:19px}
.num{display:inline-grid;place-items:center;width:30px;height:30px;border-radius:50%;background:var(--acc);color:#fff;font-size:15px;font-weight:700;flex:none}
.ayuda{color:var(--mute);font-size:15px;margin:0}
button{font:600 16px "Segoe UI",system-ui,Arial;border-radius:12px;padding:12px 18px;cursor:pointer;border:1.5px solid var(--acc);background:var(--card);color:var(--acc)}
button.prim{background:var(--acc);color:#fff}button:disabled{opacity:.55;cursor:not-allowed}
button:focus-visible,.zona:focus-within,.chip:focus-within,summary:focus-visible{outline:3px solid #8DB8F2;outline-offset:2px}
.enlace{border:0;background:none;padding:0;color:var(--acc);font-weight:600;text-decoration:underline;font-size:15px}
.salir{border-color:var(--line);color:var(--mute);padding:8px 14px;font-size:14px}
.zona{border:2.5px dashed var(--line);border-radius:14px;padding:30px 16px;text-align:center;cursor:pointer;display:grid;gap:6px;justify-items:center;transition:.15s}
.zona:hover,.zona.encima{border-color:var(--acc);background:var(--acc2)}
.zona .grande{font-size:42px;line-height:1}.zona b{font-size:18px}
.zona input{position:absolute;opacity:0;width:1px;height:1px}
.archivo{display:flex;align-items:center;gap:12px;background:var(--acc2);border-radius:12px;padding:12px 14px}
.archivo .grande{font-size:30px}.archivo div{flex:1;min-width:0}.archivo b{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
textarea{width:100%;min-height:180px;font:15px/1.45 Consolas,monospace;border:1.5px solid var(--line);border-radius:12px;padding:12px;color:var(--ink);background:var(--card);resize:vertical}
input[type=text]{width:100%;border:1.5px solid var(--line);border-radius:10px;padding:10px 12px;font:inherit;color:var(--ink);background:var(--card)}
.chips{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:10px}
.chip{position:relative;display:flex;align-items:center;gap:10px;border:1.5px solid var(--line);border-radius:12px;padding:10px 12px;cursor:pointer;user-select:none;font-size:15px}
.chip input{position:absolute;opacity:0}.chip .ico{font-size:20px}
.chip .marca{margin-left:auto;width:20px;height:20px;border-radius:6px;border:2px solid var(--line);display:grid;place-items:center;font-size:13px;color:#fff}
.chip:has(input:checked){border-color:var(--acc);background:var(--acc2)}
.chip:has(input:checked) .marca{background:var(--acc);border-color:var(--acc)}
.chip:has(input:checked) .marca::after{content:"✓"}
.fila{display:flex;gap:10px;flex-wrap:wrap;align-items:center}
details{border:1px solid var(--line);border-radius:12px;padding:4px 14px}
summary{cursor:pointer;font-weight:600;padding:8px 0;color:var(--mute)}
details[open]{padding-bottom:14px}details .campo{display:grid;gap:6px;margin-top:10px}
.check{display:flex;gap:10px;align-items:flex-start;margin-top:12px;font-size:15px}.check input{width:20px;height:20px;margin-top:2px;flex:none}
.accion{display:flex;justify-content:center}
.accion button{font-size:19px;padding:16px 36px;min-width:min(100%,340px)}
.giro{display:inline-block;width:18px;height:18px;border:3px solid rgba(255,255,255,.4);border-top-color:#fff;border-radius:50%;animation:g 0.8s linear infinite;vertical-align:-3px;margin-right:8px}
@keyframes g{to{transform:rotate(360deg)}}
.aviso{border-radius:12px;padding:12px 14px;font-size:15px}
.aviso.ok{background:var(--ok2);color:var(--ok)}.aviso.warn{background:var(--warn2);color:var(--warn)}.aviso.bad{background:var(--bad2);color:var(--bad)}
.aviso b{display:block;font-size:17px;margin-bottom:2px}
.conteos{display:flex;flex-wrap:wrap;gap:8px}
.conteo{background:var(--acc2);border-radius:999px;padding:5px 12px;font-size:14px}
.pestanas{display:flex;gap:4px;border-bottom:1.5px solid var(--line)}
.pestanas button{border:0;border-bottom:3px solid transparent;border-radius:0;padding:10px 14px;background:none;color:var(--mute)}
.pestanas button[aria-selected=true]{color:var(--acc);border-bottom-color:var(--acc)}
iframe{width:100%;height:72vh;border:1px solid var(--line);border-radius:12px;background:#fff}
.vista{white-space:pre-wrap;word-wrap:break-word;font:15px/1.6 Consolas,monospace;border:1px solid var(--line);border-radius:12px;padding:16px;max-height:72vh;overflow:auto;margin:0}
mark{background:var(--mark);color:inherit;border-radius:4px;padding:0 3px}
.pie{color:var(--mute);font-size:14px;text-align:center}
[hidden]{display:none!important}
@media(max-width:600px){header h1{font-size:21px}.sello{margin-left:0}.accion button{width:100%}}
</style></head><body><main>

<header>
 <svg class="logo" viewBox="0 0 64 64" aria-hidden="true"><rect x="2" y="2" width="60" height="60" rx="14" fill="#1F63B5"/>
  <rect x="16" y="10" width="32" height="44" rx="4" fill="#fff"/><rect x="21" y="18" width="22" height="3" rx="1.5" fill="#AAB9CD"/>
  <rect x="21" y="25" width="16" height="5" rx="1.5" fill="#13233A"/><rect x="21" y="34" width="22" height="3" rx="1.5" fill="#AAB9CD"/>
  <rect x="21" y="41" width="12" height="5" rx="1.5" fill="#13233A"/></svg>
 <div class="titulo"><h1>Anonimizador de documentos</h1><p>Oculta nombres, firmas, cédulas, cuentas y direcciones antes de compartir un documento.</p>
  <span class="privado" title="Nada sale de este computador">🔒 Todo ocurre en este equipo, sin internet</span></div>
 <div class="sello"><button class="salir" id="salir">Cerrar la app</button></div>
</header>
<div class="aviso bad" id="cerrada" hidden><b>La app se cerró</b>Para volver a usarla, haz doble clic en su icono.</div>

<section class="card" aria-labelledby="t1">
 <h2 class="paso" id="t1"><span class="num">1</span>Elige el documento</h2>
 <label class="zona" id="zona">
  <input type="file" id="archivo" accept=".pdf,.docx,.txt">
  <span class="grande">📄</span><b>Arrastra aquí tu PDF, Word o texto</b>
  <span class="ayuda">o haz clic para buscarlo en tu equipo</span>
 </label>
 <div class="archivo" id="elegido" hidden><span class="grande" id="iconoArchivo">📕</span>
  <div><b id="nombreArchivo"></b><span class="ayuda" id="detalleArchivo"></span></div>
  <button class="enlace" id="cambiar">Cambiar</button></div>
 <div class="fila"><button class="enlace" id="verPegar">✏️ Prefiero pegar un texto</button></div>
 <textarea id="entrada" hidden placeholder="Pega aquí el texto que quieres anonimizar"></textarea>
</section>

<section class="card" aria-labelledby="t2">
 <h2 class="paso" id="t2"><span class="num">2</span>¿Qué quieres ocultar?</h2>
 <div class="chips" id="tipos"></div>
 <div class="fila"><button class="enlace" id="todo">Marcar todo</button><button class="enlace" id="nada">Desmarcar todo</button></div>
 <details><summary>Opciones avanzadas</summary>
  <div class="campo"><label for="nombres">Nombres que la app debe ocultar sí o sí <span class="ayuda">(separados por coma)</span></label>
   <input type="text" id="nombres" placeholder="Ej.: Marta Lucía Gómez Rivas, Carlos Peña"></div>
  <div class="campo"><label for="excluir">Palabras que NO se deben ocultar <span class="ayuda">(separadas por coma)</span></label>
   <input type="text" id="excluir" placeholder="Ej.: Bogotá, Ministerio de Salud"></div>
  <label class="check"><input type="checkbox" id="todasImagenes"><span><b>Borrar todas las imágenes del PDF</b><br>
   <span class="ayuda">Úsalo si una firma o un sello no se borró: se ocultan todas las imágenes (también logos y fotos).</span></span></label>
 </details>
</section>

<div class="accion"><button class="prim" id="go" disabled>🔒 Anonimizar documento</button></div>
<div class="aviso bad" id="error" hidden></div>

<section class="card" id="resultado" hidden aria-labelledby="t3" tabindex="-1">
 <h2 class="paso" id="t3"><span class="num">3</span>Revisa y descarga</h2>
 <div class="aviso ok" id="resumen"></div>
 <div class="conteos" id="conteos"></div>
 <div class="aviso warn" id="noubicados" hidden></div>
 <div class="fila">
  <button class="prim" id="bajarpdf" hidden>⬇️ Descargar PDF anonimizado</button>
  <button id="bajar">⬇️ Descargar texto</button>
  <button id="copiar">📋 Copiar texto</button>
  <button id="bajarmapa" title="Sirve para recuperar los datos reales después. Contiene la información sensible.">🗝️ Guardar mapa (privado)</button>
 </div>
 <div class="pestanas" role="tablist">
  <button role="tab" id="tabPdf" aria-selected="true">Vista previa del PDF</button>
  <button role="tab" id="tabTexto" aria-selected="false">Texto anonimizado</button>
 </div>
 <iframe id="vistaPdf" title="Vista previa del PDF anonimizado"></iframe>
 <pre class="vista" id="vistaTexto" hidden></pre>
 <p class="ayuda">Lo resaltado en amarillo es lo que se ocultó. <b>Revisa todo el documento antes de compartirlo:</b> la app no es infalible.
  El «mapa» guarda los datos reales: no lo compartas.</p>
</section>

<p class="pie">¿Una firma no se borró? Abre «Opciones avanzadas» y activa «Borrar todas las imágenes del PDF».<br>Versión __VERSION__</p>
</main>
<script>
const TIPOS=__TIPOS__, HAY_PDF=__HAY_PDF__;
const ORDEN=['PERSONA','FIRMA','CEDULA','DIRECCION','CUENTA','TELEFONO','CORREO','NIT','RADICADO','VALOR'];
const CORTO={PERSONA:'Nombres',FIRMA:'Firmas',CEDULA:'Cédulas',DIRECCION:'Direcciones',CUENTA:'Cuentas y tarjetas',
 TELEFONO:'Teléfonos',CORREO:'Correos',NIT:'NIT',RADICADO:'Radicados',VALOR:'Valores en pesos',IMAGEN:'Imágenes'};
const ICONO={PERSONA:'👤',FIRMA:'✍️',CEDULA:'🪪',DIRECCION:'🏠',CUENTA:'🏦',TELEFONO:'📞',CORREO:'✉️',NIT:'🏢',
 RADICADO:'📁',VALOR:'💲',IMAGEN:'🖼️'};
const $=id=>document.getElementById(id);
let doc=null; // {tipo:'pdf'|'texto', nombre, b64?, texto?}
let res=null, urlPdf=null;

// Paso 2: botones de tipos
for(const k of ORDEN.filter(k=>k in TIPOS).concat(Object.keys(TIPOS).filter(k=>!ORDEN.includes(k)))){
 $('tipos').insertAdjacentHTML('beforeend',`<label class="chip" title="${TIPOS[k]}"><input type="checkbox" value="${k}" checked>
  <span class="ico">${ICONO[k]||'•'}</span><span>${CORTO[k]||TIPOS[k]}</span><span class="marca"></span></label>`)}
const marcar=v=>$('tipos').querySelectorAll('input').forEach(i=>i.checked=v);
$('todo').onclick=()=>marcar(true);$('nada').onclick=()=>marcar(false);

// Paso 1: elegir archivo (clic o arrastrar)
const aBase64=f=>new Promise((ok,mal)=>{const r=new FileReader();r.onload=()=>ok(r.result.split(',')[1]);r.onerror=mal;r.readAsDataURL(f)});
const tam=n=>n>1048576?(n/1048576).toFixed(1)+' MB':Math.max(1,Math.round(n/1024))+' KB';
async function pedir(ruta,cuerpo){
 const r=await fetch(ruta,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(cuerpo)});
 const j=await r.json();if(j.error)throw new Error(j.error);return j}
function mostrarError(t){$('error').hidden=!t;$('error').innerHTML=t?'<b>No se pudo completar</b>'+esc(t):''}
function esc(s){return s.replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]))}
function actualizar(){$('go').disabled=!(doc&&(doc.tipo==='pdf'||doc.texto.trim()))}
function limpiarResultado(){res=null;$('resultado').hidden=true;if(urlPdf){URL.revokeObjectURL(urlPdf);urlPdf=null}}

async function elegir(f){
 if(!f)return;mostrarError('');limpiarResultado();
 const ext=f.name.toLowerCase().split('.').pop(), nombre=f.name.replace(/\.[^.]+$/,'');
 if(!['pdf','docx','txt'].includes(ext)){mostrarError('Ese tipo de archivo no se puede abrir. Usa un PDF, un Word (.docx) o un .txt.');return}
 $('nombreArchivo').textContent=f.name;$('detalleArchivo').textContent='Leyendo…';
 $('iconoArchivo').textContent={pdf:'📕',docx:'📘',txt:'📄'}[ext];
 $('zona').hidden=true;$('elegido').hidden=false;$('entrada').hidden=true;
 try{
  if(ext==='pdf'){
   if(!HAY_PDF)throw new Error('Esta copia de la app no tiene soporte de PDF.');
   const b64=await aBase64(f);await pedir('/pdf/texto',{archivo:b64}); // valida: con contraseña o escaneado
   doc={tipo:'pdf',nombre,b64};
  }else if(ext==='docx'){doc={tipo:'texto',nombre,texto:(await pedir('/docx',{archivo:await aBase64(f)})).texto}}
  else{doc={tipo:'texto',nombre,texto:await f.text()}}
  $('detalleArchivo').textContent=tam(f.size)+' · listo para anonimizar';
 }catch(e){doc=null;quitar();mostrarError(e.message)}
 actualizar();
}
function quitar(){doc=null;$('archivo').value='';$('zona').hidden=false;$('elegido').hidden=true;limpiarResultado();actualizar()}
$('archivo').onchange=e=>elegir(e.target.files[0]);
$('cambiar').onclick=()=>{quitar();$('archivo').click()};
const zona=$('zona');
['dragenter','dragover'].forEach(t=>zona.addEventListener(t,e=>{e.preventDefault();zona.classList.add('encima')}));
['dragleave','drop'].forEach(t=>zona.addEventListener(t,e=>{e.preventDefault();zona.classList.remove('encima')}));
zona.addEventListener('drop',e=>elegir(e.dataTransfer.files[0]));
window.addEventListener('dragover',e=>e.preventDefault());window.addEventListener('drop',e=>e.preventDefault());
$('verPegar').onclick=()=>{quitar();$('entrada').hidden=false;$('entrada').focus()};
$('entrada').oninput=()=>{doc={tipo:'texto',nombre:'texto',texto:$('entrada').value};limpiarResultado();actualizar()};

// Anonimizar
const lista=id=>$(id).value.split(',').map(x=>x.trim()).filter(Boolean);
$('go').onclick=async()=>{
 const tipos=[...$('tipos').querySelectorAll('input:checked')].map(i=>i.value);
 const todas=$('todasImagenes').checked;
 if(!tipos.length&&!todas){mostrarError('Marca al menos un tipo de dato para ocultar.');return}
 const op={tipos,nombres:lista('nombres'),excluir:lista('excluir')};
 mostrarError('');limpiarResultado();
 $('go').disabled=true;$('go').innerHTML='<span class="giro"></span>Anonimizando…';
 try{
  res=doc.tipo==='pdf'?await pedir('/pdf/anonimizar',{...op,archivo:doc.b64,todas_imagenes:todas})
                      :await pedir('/anonimizar',{...op,texto:doc.texto});
  mostrarResultado();
 }catch(e){mostrarError(e.message)}
 finally{$('go').innerHTML='🔒 Anonimizar documento';actualizar()}
};
function mostrarResultado(){
 const inf=res.informe, total=Object.values(inf).reduce((a,b)=>a+b,0);
 $('resumen').className='aviso '+(total?'ok':'warn');
 $('resumen').innerHTML=total?`<b>✅ Listo: se ocultaron ${total} dato${total>1?'s':''}</b>Revisa la vista previa y descarga el resultado.`
  :'<b>No se encontró ningún dato para ocultar</b>Revisa el documento de todos modos, o agrega nombres en «Opciones avanzadas».';
 $('conteos').innerHTML=Object.keys(inf).map(k=>`<span class="conteo">${ICONO[k]||''} ${CORTO[k]||k}: <b>${inf[k]}</b></span>`).join('');
 const nu=res.no_ubicados||[];
 $('noubicados').hidden=!nu.length;
 $('noubicados').innerHTML=nu.length?'<b>⚠️ Revisa esto a mano en el PDF</b>Estos datos se detectaron pero no se pudieron borrar dentro del PDF: '+nu.map(x=>esc(x[1])).join(' · '):'';
 $('vistaTexto').innerHTML=esc(res.texto).replace(/\[[A-Z]+_\d+\]/g,'<mark>$&</mark>');
 const esPdf=!!res.pdf;
 $('bajarpdf').hidden=!esPdf;$('tabPdf').hidden=!esPdf;
 if(esPdf){const s=atob(res.pdf),b=new Uint8Array(s.length);for(let i=0;i<s.length;i++)b[i]=s.charCodeAt(i);
  urlPdf=URL.createObjectURL(new Blob([b],{type:'application/pdf'}));$('vistaPdf').src=urlPdf}
 pestana(esPdf?'pdf':'texto');
 $('resultado').hidden=false;$('resultado').scrollIntoView({behavior:'smooth'});$('resultado').focus({preventScroll:true});
}
function pestana(c){const p=c==='pdf';$('tabPdf').setAttribute('aria-selected',p);$('tabTexto').setAttribute('aria-selected',!p);
 $('vistaPdf').hidden=!p;$('vistaTexto').hidden=p}
$('tabPdf').onclick=()=>pestana('pdf');$('tabTexto').onclick=()=>pestana('texto');

// Descargas
function descargar(nombre,url){const a=document.createElement('a');a.href=url;a.download=nombre;a.click()}
const deTexto=(contenido,tipo)=>URL.createObjectURL(new Blob([contenido],{type:tipo}));
$('bajarpdf').onclick=()=>descargar(doc.nombre+'_anonimizado.pdf',urlPdf);
$('bajar').onclick=()=>descargar(doc.nombre+'_anonimizado.txt',deTexto(res.texto,'text/plain;charset=utf-8'));
$('bajarmapa').onclick=()=>descargar(doc.nombre+'_mapa_NO_COMPARTIR.json',deTexto(JSON.stringify(res.mapa,null,2),'application/json'));
$('copiar').onclick=async()=>{await navigator.clipboard.writeText(res.texto);const b=$('copiar'),t=b.textContent;b.textContent='✅ Copiado';setTimeout(()=>b.textContent=t,1500)};

// Mantener viva la app mientras la pestaña esté abierta
const latir=()=>fetch('/ping').catch(()=>{$('cerrada').hidden=false});
latir();setInterval(latir,20000);
$('salir').onclick=async()=>{try{await fetch('/salir',{method:'POST'})}catch(e){}
 document.body.innerHTML='<main><section class="card"><h1>Listo, la app se cerró.</h1><p class="ayuda">Ya puedes cerrar esta pestaña.</p></section></main>'};
</script></body></html>"""

ultimo_latido = time.monotonic()
servidor_activo = None  # para las pruebas


def _b64(d):
    return base64.b64decode(d["archivo"])


def _opciones(d):
    return d.get("tipos"), d.get("nombres", []), d.get("excluir", [])


class Servidor(ThreadingHTTPServer):
    """Servidor con el puerto en uso exclusivo.

    http.server activa SO_REUSEADDR y en Windows eso deja que dos copias usen el mismo
    puerto a la vez. Aquí se pide el puerto en exclusiva: si ya está en uso, falla.
    """
    allow_reuse_address = False
    daemon_threads = True

    def server_bind(self):
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


class Manejador(BaseHTTPRequestHandler):
    def _responder(self, codigo, contenido, tipo):
        cuerpo = contenido.encode("utf-8") if isinstance(contenido, str) else contenido
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(cuerpo)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(cuerpo)

    def _json(self, codigo, datos):
        self._responder(codigo, json.dumps(datos, ensure_ascii=False), "application/json; charset=utf-8")

    def do_GET(self):
        global ultimo_latido
        if self.path == "/":
            pagina = PAGINA.replace("__TIPOS__", json.dumps(TIPOS, ensure_ascii=False)) \
                .replace("__HAY_PDF__", "true" if HAY_PDF else "false").replace("__VERSION__", VERSION)
            self._responder(200, pagina, "text/html; charset=utf-8")
        elif self.path == "/ping":
            ultimo_latido = time.monotonic()
            self._responder(200, FIRMA, "text/plain; charset=utf-8")
        else:
            self._responder(404, "No encontrado", "text/plain; charset=utf-8")

    def do_POST(self):
        # Solo se aceptan peticiones de la propia página (evita que otra web abierta use la app).
        origen = self.headers.get("Origin")
        if origen and origen not in (f"http://127.0.0.1:{self.server.server_port}",
                                     f"http://localhost:{self.server.server_port}"):
            self._responder(403, "Prohibido", "text/plain; charset=utf-8")
            return
        n = int(self.headers.get("Content-Length", 0))
        cuerpo = self.rfile.read(n)
        try:
            if self.path == "/salir":
                self._responder(200, "ok", "text/plain; charset=utf-8")
                threading.Thread(target=self.server.shutdown, daemon=True).start()
                return
            d = json.loads(cuerpo.decode("utf-8"))
            if self.path == "/anonimizar":
                texto, mapa, informe = anonimizar(d["texto"], *_opciones(d))
                self._json(200, {"texto": texto, "mapa": mapa, "informe": informe})
            elif self.path == "/docx":
                self._json(200, {"texto": leer_docx(_b64(d))})
            elif self.path == "/pdf/texto" and HAY_PDF:
                self._json(200, {"texto": leer_pdf(_b64(d))})
            elif self.path == "/pdf/anonimizar" and HAY_PDF:
                pdf, texto, mapa, informe, no_ubicados = anonimizar_pdf(
                    _b64(d), *_opciones(d), todas_las_imagenes=bool(d.get("todas_imagenes")))
                self._json(200, {"texto": texto, "mapa": mapa, "informe": informe,
                                 "pdf": base64.b64encode(pdf).decode("ascii"), "no_ubicados": no_ubicados})
            else:
                self._responder(404, "No encontrado", "text/plain; charset=utf-8")
        except ValueError as e:  # mensajes pensados para el usuario (PDF escaneado, con contraseña...)
            self._json(400, {"error": str(e)})
        except Exception as e:  # archivo dañado o de otro formato
            self._json(400, {"error": f"No pude procesar el archivo: {e}"})

    def log_message(self, *a):
        pass


def _quien_esta(puerto):
    """Qué corre en ese puerto: "misma" (esta versión), "vieja" (otra versión de la app) u "otro"."""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{puerto}/ping", timeout=2) as r:
            firma = r.read().decode()
    except Exception:
        return "otro"
    if firma == FIRMA:
        return "misma"
    return "vieja" if firma.startswith(_FIRMA_BASE) else "otro"


def _cerrar_version_vieja(puerto):
    """Pide a una versión anterior que se cierre y espera a que libere el puerto (máx. 8 s)."""
    try:
        origen = f"http://127.0.0.1:{puerto}"
        urllib.request.urlopen(urllib.request.Request(origen + "/salir", b"", {"Origin": origen}), timeout=3)
    except Exception:
        pass
    for _ in range(40):
        time.sleep(0.2)
        try:
            return Servidor(("127.0.0.1", puerto), Manejador)
        except OSError:
            continue
    return None


def _vigilar(servidor):
    """Apaga la app cuando la pestaña lleva un rato cerrada (la versión .exe no tiene ventana)."""
    while True:
        time.sleep(15)
        if time.monotonic() - ultimo_latido > SIN_LATIDO_SEG:
            servidor.shutdown()
            return


def _avisar(mensaje):
    if sys.stdout:
        print(mensaje)
    elif sys.platform == "win32":  # .exe sin consola: mostrar una ventana de aviso
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, mensaje, "Anonimizador local", 0x10)


def main():
    try:
        servidor = Servidor(("127.0.0.1", PUERTO), Manejador)  # solo este computador
    except OSError:
        quien = _quien_esta(PUERTO)
        if quien == "misma":  # doble clic dos veces: se muestra la que ya está abierta
            webbrowser.open(f"http://127.0.0.1:{PUERTO}")
            return
        # Una versión anterior abierta se cierra para que se use la nueva.
        servidor = _cerrar_version_vieja(PUERTO) if quien == "vieja" else None
        if servidor is None:
            servidor = Servidor(("127.0.0.1", 0), Manejador)  # puerto ocupado por otro programa
    global servidor_activo
    servidor_activo = servidor
    url = f"http://127.0.0.1:{servidor.server_port}"
    if sys.stdout:
        print(f"Anonimizador local en {url}  (Ctrl+C o el botón «Cerrar la app» para salir)")
    threading.Thread(target=_vigilar, args=(servidor,), daemon=True).start()
    threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        servidor.server_close()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        _avisar(f"No se pudo iniciar el anonimizador:\n{e}")
        raise
