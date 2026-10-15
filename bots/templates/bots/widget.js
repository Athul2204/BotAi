(function () {
  if (window.__botaiLoaded) return; window.__botaiLoaded = true;
  var API = "{{ api|escapejs }}", TITLE = "{{ bot.name|escapejs }}";
  var sid = localStorage.getItem('botai_sid') || Math.random().toString(36).slice(2, 12);
  localStorage.setItem('botai_sid', sid);

  var css = document.createElement('style');
  css.textContent = '#bw-btn{position:fixed;right:22px;bottom:22px;width:58px;height:58px;border-radius:50%;background:#226bca;color:#fff;border:0;font-size:26px;cursor:pointer;box-shadow:0 6px 20px rgba(0,0,0,.25);z-index:99998}' +
    '#bw-box{position:fixed;right:22px;bottom:94px;width:340px;max-width:calc(100vw - 30px);height:460px;background:#fff;border-radius:12px;box-shadow:0 10px 40px rgba(0,0,0,.25);display:none;flex-direction:column;overflow:hidden;z-index:99999;font:14px system-ui,sans-serif}' +
    '#bw-box header{background:#226bca;color:#fff;padding:14px 16px;font-weight:600}' +
    '#bw-msgs{flex:1;overflow:auto;padding:12px;background:#f5f6fa;display:flex;flex-direction:column;gap:8px}' +
    '.bw-m{max-width:80%;padding:8px 12px;border-radius:10px;line-height:1.35;white-space:pre-wrap}' +
    '.bw-u{align-self:flex-end;background:#226bca;color:#fff}.bw-b{align-self:flex-start;background:#fff;border:1px solid #e3e6ee;color:#222}' +
    '#bw-box form{display:flex;border-top:1px solid #e3e6ee}#bw-box input{flex:1;border:0;padding:12px;outline:0;font-size:14px}' +
    '#bw-box form button{border:0;background:none;color:#226bca;font-weight:600;padding:0 16px;cursor:pointer}';
  document.head.appendChild(css);

  var btn = document.createElement('button'); btn.id = 'bw-btn'; btn.innerHTML = '💬';
  var box = document.createElement('div'); box.id = 'bw-box';
  box.innerHTML = '<header></header><div id="bw-msgs"></div><form><input placeholder="Type a message…" autocomplete="off"><button>Send</button></form>';
  box.querySelector('header').textContent = TITLE;
  document.body.appendChild(btn); document.body.appendChild(box);
  var msgs = box.querySelector('#bw-msgs'), input = box.querySelector('input');

  function add(t, c) { var d = document.createElement('div'); d.className = 'bw-m ' + c; d.textContent = t; msgs.appendChild(d); msgs.scrollTop = msgs.scrollHeight; }
  btn.onclick = function () { var o = box.style.display === 'flex'; box.style.display = o ? 'none' : 'flex'; if (!o) { input.focus(); if (!msgs.children.length) add('Hi! 👋 How can I help you?', 'bw-b'); } };
  box.querySelector('form').onsubmit = function (e) {
    e.preventDefault(); var v = input.value.trim(); if (!v) return; input.value = ''; add(v, 'bw-u');
    fetch(API, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ session: sid, message: v }) })
      .then(function (r) { return r.json(); })
      .then(function (j) { if (j.error) add(j.error, 'bw-b'); (j.replies || []).forEach(function (t) { add(t, 'bw-b'); }); })
      .catch(function () { add('Cannot reach the bot right now.', 'bw-b'); });
  };
})();
