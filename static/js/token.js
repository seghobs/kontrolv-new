(() => {
 const el=id=>document.getElementById(id);
 let flowId=null,timer=null,busy=false;
 const names={approval:'Instagram uygulamasından onay',whatsapp:'WhatsApp',totp:'Doğrulama uygulaması',sms:'SMS',backup:'Yedek kod',email:'E-posta kodu'};
 const stop=()=>{if(timer)clearTimeout(timer);timer=null;};
 const error=message=>{el('errorMessage').style.display='block';el('errorText').textContent=message;};
 async function api(path,data){
  const response=await fetch('/api/luma-login'+path,data===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json','X-CSRFToken':document.querySelector('meta[name="csrf-token"]').content},body:JSON.stringify(data)});
  const value=await response.json();if(!response.ok||!value.success)throw new Error(value.message||'Giriş adımı tamamlanamadı.');return value;
 }
 function render(flow){
  stop();flowId=flow.id;el('loginFlow').hidden=false;el('flowMessage').textContent=flow.message||'';
  el('flowDevice').textContent=flow.device?'Kayıtlı cihaz: '+flow.device:'';el('loginMethods').replaceChildren();
  el('verifyForm').hidden=flow.stage!=='code';el('showMethods').hidden=flow.stage!=='approval';
  el('cancelLogin').hidden=['done','failed','cancelled'].includes(flow.stage);el('submitBtn').disabled=!['done','failed','cancelled'].includes(flow.stage);
  if(flow.stage==='method')for(const method of flow.methods||[]){const button=document.createElement('button');button.type='button';button.className='btn btn-primary me-2 mb-2';button.textContent=names[method]||method;button.addEventListener('click',()=>step('select',{method}));el('loginMethods').append(button);}
  if(flow.stage==='approval')timer=setTimeout(()=>step('poll'),3000);
  if(flow.stage==='failed'){error(flow.message||'Giriş tamamlanamadı.');el('flowMessage').textContent='';}
  if(flow.stage==='done'){
   el('successMessage').style.display='block';
   el('successText').textContent='Oturum kaydedildi. Yönetim paneline yönlendiriliyorsunuz…';
   el('submitBtn').disabled=true;
   timer=setTimeout(()=>window.location.assign('/admin'),1200);
  }
 }
 async function step(action,extra={}){
  if(busy||!flowId)return;busy=true;stop();el('errorMessage').style.display='none';
  try{render((await api('/'+flowId+'/step',{action,...extra})).flow);}catch(exc){error(exc.message);el('submitBtn').disabled=false;}finally{busy=false;}
 }
 el('loginForm').addEventListener('submit',async event=>{
  event.preventDefault();if(busy)return;busy=true;stop();el('errorMessage').style.display='none';el('successMessage').style.display='none';el('loadingMessage').style.display='block';el('submitBtn').disabled=true;
  let password=el('sifre').value;
  try{const profile=el('deviceProfile').value;const data={username:el('kullanici_adi').value.trim(),password,profile,fresh:el('freshLogin').checked,new_device:el('newDevice').checked};if(profile==='custom')data.custom_profile=JSON.parse(el('customProfile').value);const value=await api('/start',data);if(value.flow&&value.flow.id)el('newDevice').checked=false;render(value.flow);data.password='';}
  catch(exc){error(exc.message);el('submitBtn').disabled=false;}finally{password='';el('sifre').value='';busy=false;el('loadingMessage').style.display='none';}
 });
 el('verifyForm').addEventListener('submit',event=>{event.preventDefault();const code=el('verificationCode').value.trim();el('verificationCode').value='';step('code',{code});});
 el('showMethods').addEventListener('click',()=>step('methods'));el('cancelLogin').addEventListener('click',()=>step('cancel'));
 el('deviceProfile').addEventListener('change',()=>{el('customProfileBox').hidden=el('deviceProfile').value!=='custom';});
 el('recoverLogin').addEventListener('click',async()=>{if(busy)return;busy=true;stop();try{render((await api('/active?username='+encodeURIComponent(el('kullanici_adi').value.trim()))).flow);}catch(exc){error(exc.message);}finally{busy=false;}});
 const username=new URLSearchParams(location.search).get('username');if(username)el('kullanici_adi').value=username;
 window.addEventListener('pagehide',stop);
})();
