with open('public/main.js', encoding='utf-8') as f:
    content = f.read()

# Locate and replace the init function block
marker_start = 'function init() {'
marker_end = '  setInterval(checkIndexStatus, 30000);\n}'

start_idx = content.find(marker_start)
end_idx = content.find(marker_end, start_idx) + len(marker_end)

if start_idx == -1:
    print('ERROR: init function not found')
else:
    new_init = '''function init() {
  // Restore session
  const saved = sessionStorage.getItem('dpu_role');
  if (saved === 'admin' || saved === 'faculty') {
    authRole = saved;
  } else if (saved === 'student') {
    authRole = 'student';
    const savedErpId = sessionStorage.getItem('dpu_erp_id');
    if (savedErpId && MOCK_STUDENT_METADATA[savedErpId]) {
      const selectEl = document.getElementById('student-erp-id');
      if (selectEl) { selectEl.value = savedErpId; selectEl.disabled = true; }
    }
  }

  applyAuthState();
  checkIndexStatus();

  // Personalized welcome message
  const savedErpId2 = sessionStorage.getItem('dpu_erp_id');
  const studentName = savedErpId2 && MOCK_STUDENT_METADATA[savedErpId2]
    ? MOCK_STUDENT_METADATA[savedErpId2].name.split(' ')[0]
    : null;

  const welcomeText = (studentName ? 'Hello, ' + studentName : 'Hello') +
    '! I am the DPU EduBot, your AI learning assistant for Dr. D.Y. Patil Centre for Online Learning.\\n\\n' +
    'I can help you with:\\n' +
    '- Exam schedules and hall tickets\\n' +
    '- Fee payment and refund queries\\n' +
    '- LMS access, session recordings, assignments\\n' +
    '- Book dispatch and support tickets\\n\\n' +
    (studentName
      ? 'Select your batch above and ask me anything about your account or DPU programs.'
      : 'Please select your batch above. You can also click Sign In to log in and see your personal account details.');

  appendMessage('assistant', welcomeText);

  // Poll index status every 30s
  setInterval(checkIndexStatus, 30000);
}'''

    content = content[:start_idx] + new_init + content[end_idx:]
    with open('public/main.js', 'w', encoding='utf-8') as f:
        f.write(content)
    print('OK: init function updated')
