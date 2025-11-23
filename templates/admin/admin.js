ready(()=>{
	const uploadForm = qs('#upload-form'), fileInput = qs('#file'), target = qs('#target'), uploadResult = qs('#upload-result')
	const btnList = qs('#btn-list'), filesList = qs('#files-list')
	const btnToggle = qs('#btn-toggle-ai'), aiStatus = qs('#ai-status')
	const logout = qs('#logout-admin')

	// New elements
	const studentsList = qs('#students-list')
	const btnRefreshStudents = qs('#btn-refresh-students')
	const updateStudentForm = qs('#update-student-form')
	const studentEmail = qs('#student-email')
	const studentMarks = qs('#student-marks')
	const btnUpdateStudent = qs('#btn-update-student')
	const updateResult = qs('#update-result')
	const btnViewHistory = qs('#btn-view-history')
	const historyList = qs('#history-list')

	logout && logout.addEventListener('click',(e)=>{ e.preventDefault(); localStorage.removeItem('mmec_token'); localStorage.removeItem('mmec_user'); localStorage.removeItem('mmec_role'); window.location.href='../splash/splash.html' })

	// Upload form
	uploadForm && uploadForm.addEventListener('submit', async (ev)=>{
		ev.preventDefault();
		if(!fileInput.files || fileInput.files.length===0){ uploadResult.textContent='Choose a file'; return }
		const f = fileInput.files[0]
		const form = new FormData(); form.append('file', f); if(target && target.value) form.append('target', target.value)
		const token = localStorage.getItem('mmec_token')
		try{
			const res = await fetch('/api/admin/upload',{method:'POST',headers: token ? {'X-Session-Token': token} : {}, body: form})
			const j = await res.json()
			if(j && j.ok){ uploadResult.textContent = 'Uploaded: '+(j.file || JSON.stringify(j.files||j)) } else { uploadResult.textContent = 'Upload failed: '+(j && j.error)
			}
		}catch(err){ uploadResult.textContent = 'Error uploading file' }
	})

	// List files
	btnList && btnList.addEventListener('click', async ()=>{
		filesList.textContent = 'Loading...'
		const token = localStorage.getItem('mmec_token')
		try{
			const res = await fetch('/api/admin/upload', { headers: token? {'X-Session-Token': token} : {}})
			const j = await res.json()
			if(j && j.ok){ filesList.innerHTML = j.files.map(f=>`<div>${f}</div>`).join('') } else filesList.textContent = 'Failed to list files'
		}catch(e){ filesList.textContent = 'Error' }
	})

	// Toggle AI
	btnToggle && btnToggle.addEventListener('click', async ()=>{
		const token = localStorage.getItem('mmec_token')
		try{
			const res = await fetch('/api/admin/toggle_ai', {method:'POST', headers: token? {'X-Session-Token': token, 'Content-Type':'application/json'} : {'Content-Type':'application/json'}})
			const j = await res.json()
			if(j && j.ok){ aiStatus.textContent = 'AI allowed: '+String(j.allow_external_queries) } else aiStatus.textContent = 'Failed to toggle'
		}catch(e){ aiStatus.textContent='Error toggling' }
	})

	// Refresh students list
	btnRefreshStudents && btnRefreshStudents.addEventListener('click', loadStudents)

	// Update student
	btnUpdateStudent && btnUpdateStudent.addEventListener('click', async ()=>{
		const email = studentEmail.value.trim()
		const marks = studentMarks.value.trim()
		if(!email){ updateResult.textContent = 'Enter student email'; return }
		const token = localStorage.getItem('mmec_token')
		try{
			const res = await fetch('/api/admin/update_student', {method:'POST', headers: token? {'X-Session-Token': token, 'Content-Type':'application/json'} : {'Content-Type':'application/json'}, body: JSON.stringify({email, marks})})
			const j = await res.json()
			if(j && j.ok){ updateResult.textContent = 'Updated successfully' } else { updateResult.textContent = 'Update failed: '+(j && j.error) }
		}catch(e){ updateResult.textContent = 'Error updating' }
	})

	// View student logins
	btnViewHistory && btnViewHistory.addEventListener('click', async ()=>{
		historyList.textContent = 'Loading...'
		const token = localStorage.getItem('mmec_token')
		try{
			const res = await fetch('/api/admin/students', { headers: token? {'X-Session-Token': token} : {}})
			const j = await res.json()
			if(j && j.ok){ historyList.innerHTML = j.students.map(s=>`<div>${s.username} - Last Login: ${new Date(s.last_login).toLocaleString()}</div>`).join('') } else historyList.textContent = 'Failed to load student logins'
		}catch(e){ historyList.textContent = 'Error' }
	})

	// Load students on page load
	loadStudents()

	async function loadStudents(){
		studentsList.textContent = 'Loading...'
		const token = localStorage.getItem('mmec_token')
		try{
			const res = await fetch('/api/admin/students', { headers: token? {'X-Session-Token': token} : {}})
			const j = await res.json()
			if(j && j.ok){ studentsList.innerHTML = j.students.map(s=>`<div>${s.name} (${s.email}) - Marks: ${s.marks || 'N/A'}, Notes: ${s.notes || 'N/A'}</div>`).join('') } else studentsList.textContent = 'Failed to load students'
		}catch(e){ studentsList.textContent = 'Error' }
	}
})
