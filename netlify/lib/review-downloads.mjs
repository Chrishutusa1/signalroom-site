const escape = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

// Only expose files already referenced by this version of the gallery.
// Historical assets may still exist in the manifest for rollback.
export function addDownloadLibrary(body, episode, manifest) {
 const prefix=`/review/${episode}/files/`, files=new Set();
 for(const match of body.matchAll(/(?:href|src|poster)="([^"]+)"/g)) {
  const value=match[1].replaceAll('&amp;','&');
  if(!value.startsWith(prefix))continue;
  let key;try{key=decodeURIComponent(value.slice(prefix.length).split(/[?#]/)[0]);}catch{continue;}
  if(manifest.files[key])files.add(key);
 }
 if(!files.size)return body;
 const list=[...files].sort().map(key=>{
  const size=manifest.files[key].size;
  const label=size>=1e9?`${(size/1e9).toFixed(2)} GB`:size>=1e6?`${(size/1e6).toFixed(1)} MB`:`${Math.ceil(size/1000)} KB`;
  const url=prefix+key.split('/').map(encodeURIComponent).join('/');
  return `<li><a href="${escape(url)}?download=1" download="${escape(key.split('/').pop())}">${escape(key)}</a> <small>${label}</small></li>`;
 }).join('');
 const section=`<section id="review-download-library" style="grid-column:1/-1;width:100%;box-sizing:border-box;max-width:1280px;margin:24px auto;padding:24px;overflow-wrap:anywhere"><h2>Download files</h2><p class="review-download-help">Use Save as… to choose a filename and location. If your browser does not support it, use Download; your browser’s download settings control the destination.</p><details><summary>All ${files.size} files used on this page</summary><ul>${list}</ul></details></section>`;
 return body.replace('</main>',section+'</main>');
}

// Serialised into the existing nonce-protected review-page script.
export function initReviewDownloads() {
 const prefix=location.pathname.match(/^\/review\/([a-z0-9-]+)\//)?.[0]+'files/';
 for(const link of document.querySelectorAll('a[href]')) {
  const url=new URL(link.href,location.href);
  if(url.origin!==location.origin||!url.pathname.startsWith(prefix)||link.dataset.downloadReady)continue;
  link.dataset.downloadReady='true';
  const filename=decodeURIComponent(url.pathname.split('/').pop());
  url.searchParams.set('download','1');
  let download=link;
  if(!link.hasAttribute('download')) {
   download=document.createElement('a');download.textContent='Download';
   download.style.margin='0 8px';download.dataset.downloadReady='true';link.after(download);
  }
  download.href=url.href;download.download=filename;
  if(typeof window.showSaveFilePicker!=='function')continue;
  const button=document.createElement('button');button.type='button';button.textContent='Save as…';
  button.className='review-save-as';button.setAttribute('aria-label','Save '+filename+' as');
  button.style.cssText='width:auto;margin:4px 8px;padding:7px 12px;font:inherit;font-size:14px;border:1px solid #a593bd;border-radius:6px;background:#251936;color:#fff;cursor:pointer';
  const status=document.createElement('span');status.setAttribute('role','status');status.style.fontSize='14px';
  const cancel=document.createElement('button');cancel.type='button';cancel.textContent='Cancel';cancel.hidden=true;
  cancel.style.cssText='width:auto;margin:4px;padding:6px 10px;font:inherit;font-size:14px';
  download.after(button,status,cancel);
  button.addEventListener('click',async()=>{
   let writable,reader;const controller=new AbortController();let bytes=0;
   button.disabled=true;status.textContent='Choose a save location…';
   cancel.onclick=()=>controller.abort();
   try {
    // Keep the picker first: it requires the user's click activation.
    const handle=await window.showSaveFilePicker({suggestedName:filename,id:'signal-room-review'});
    status.textContent='Starting download…';cancel.hidden=false;
    const response=await fetch(url.href,{credentials:'same-origin',signal:controller.signal});
    if(!response.ok||!response.body)throw Error('Download unavailable. Reopen your review share link and try again.');
    const total=Number(response.headers.get('content-length'));
    writable=await handle.createWritable();reader=response.body.getReader();
    while(true){const {done,value}=await reader.read();if(done)break;await writable.write(value);bytes+=value.byteLength;status.textContent=total?`Saving… ${Math.min(100,Math.round(bytes/total*100))}%`:`Saving… ${(bytes/1e6).toFixed(1)} MB`;}
    if(total&&bytes!==total)throw Error('The download was incomplete. Please try again.');
    await writable.close();writable=null;status.textContent='Saved to your selected location.';
   } catch(error) {
    await reader?.cancel().catch(()=>{});await writable?.abort().catch(()=>{});
    status.textContent=error.name==='AbortError'?'Save cancelled.':(error.name==='SecurityError'||error.name==='NotAllowedError')?'This browser cannot open Save as. Use Download and your browser’s save-location setting.':error.message;
   } finally {button.disabled=false;cancel.hidden=true;}
  });
 }
}
