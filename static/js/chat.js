
const chatForm = document.getElementById('chat-form');
const chatBox = document.getElementById('chatbox');
const input = document.getElementById('chat-input');

function addMsg(text, who='bot'){
  const div = document.createElement('div');
  div.className = `msg ${who}`;
  div.innerText = text;
  chatBox.appendChild(div);
  chatBox.scrollTop = chatBox.scrollHeight;
}

if(chatForm){
  chatForm.addEventListener('submit', async (e)=>{
    e.preventDefault();
    const msg = input.value.trim();
    if(!msg) return;
    addMsg(msg, 'me');
    input.value='';
    try{
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: msg })
      });
      const data = await res.json();
      addMsg(data.reply || '...');
    }catch(e){
      addMsg('Network error, please try again.');
    }
  });
}
