ready(()=>{
  const btn = qs('#btn-register'), name = qs('#name-register'), email = qs('#email-register'), mobile = qs('#mobile-register'), pw = qs('#pw-register'), question = qs('#question-register'), answer = qs('#answer-register'), msg = qs('#msg-register')
  btn && btn.addEventListener('click', async ()=>{
    const n = (name && name.value||'').trim(), e = (email && email.value||'').trim(), m = (mobile && mobile.value||'').trim(), p = (pw && pw.value||'').trim(), q = (question && question.value||'').trim(), a = (answer && answer.value||'').trim()
    if(!n || !e || !m || !p || !q || !a){ setText(msg,'Please fill all fields'); msg.style.display='block'; return }
    if(p.length < 6){ setText(msg,'Password must be at least 6 characters'); msg.style.display='block'; return }
    try{
      const res = await fetch('/api/register',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:n,email:e,mobile:m,password:p,security_question:q,answer:a})})
      const j = await res.json()
      if(res.status===201 || (j && j.ok)){
        // registered - auto login
        setText(msg,'Registration successful. Signing you in...'); msg.style.color='green'; msg.style.display='block'
        try{
          const loginRes = await fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:e,password:p})})
          const loginJson = await loginRes.json()
          if(loginJson && loginJson.ok){
            localStorage.setItem('mmec_token', loginJson.token)
            // store the registered name for display
            localStorage.setItem('mmec_name', n)
            localStorage.setItem('mmec_user', n)
            // store email separately
            localStorage.setItem('mmec_email', e)
            localStorage.setItem('mmec_role', loginJson.role || 'Student')
            // redirect to dashboard
            setTimeout(()=> window.location.href = '/student/dashboard?token='+encodeURIComponent(loginJson.token), 700)
          } else {
            setTimeout(()=> location.href='/login', 800)
          }
        }catch(err){ setTimeout(()=> location.href='/login', 800) }
      } else if(j && j.error==='user_exists'){
        setText(msg,'User already exists. Please login.'); msg.style.display='block'
      } else {
        setText(msg, j && j.error ? j.error : 'Registration failed'); msg.style.display='block'
      }
    }catch(err){ setText(msg,'Server error'); msg.style.display='block' }
  })
})
