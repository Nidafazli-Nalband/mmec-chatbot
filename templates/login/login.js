ready(()=>{
  const btn = qs('#btn-login'), email = qs('#email-login'), pw = qs('#pw-login'), msg = qs('#msg-login')
  btn && btn.addEventListener('click', async ()=>{
    const e = (email && email.value||'').trim(), p = (pw && pw.value||'').trim()
    if(!e || !p){ setText(msg,'Please enter email and password'); msg.style.display='block'; return }
    try{
      const res = await fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:e,password:p})})
      const j = await res.json()
      if(j && j.ok){
        // save session token
        localStorage.setItem('mmec_token', j.token)
        // prefer storing the provided name when available
        if(j.name) localStorage.setItem('mmec_name', j.name)
        localStorage.setItem('mmec_user', j.name || e)
        // persist email separately as the canonical user key
        localStorage.setItem('mmec_email', e)
        localStorage.setItem('mmec_role', j.role || 'Student')
        // redirect based on role
        if((j.role||'Student').toLowerCase().includes('admin')){
          window.location.href = '/admin?token='+encodeURIComponent(j.token)
        } else {
          window.location.href = '/student/dashboard?token='+encodeURIComponent(j.token)
        }
      } else {
        setText(msg, j && j.error ? j.error : 'Account not found'); msg.style.display='block'
      }
    }catch(err){
      setText(msg,'Server error'); msg.style.display='block'
    }
  })
})
