const elSignals = document.getElementById('signals');
const elConn = document.getElementById('conn');
const btnPush = document.getElementById('btn-push');

function fmt(n, digits = 2) {
  if (n === null || n === undefined) return '';
  return Number(n).toFixed(digits);
}

function upsertRow(sig) {
  const id = `${sig.timestamp}-${sig.symbol}`;
  let tr = document.getElementById(id);
  const votePairs = Object.entries(sig.strategy_votes || {}).map(([k, v]) => `${k}:${v}`).join(' ');
  const chipClass = sig.action === 'BUY' ? 'chip buy' : (sig.action === 'SELL' ? 'chip sell' : 'chip hold');
  const actionLabel = `<span class="${chipClass}">${sig.action}</span>`;
  if (!tr) {
    tr = document.createElement('tr');
    tr.id = id;
    tr.innerHTML = `
      <td class="time"></td>
      <td class="symbol"></td>
      <td class="action"></td>
      <td class="price"></td>
      <td class="qty"></td>
      <td class="pct"></td>
      <td class="tp"></td>
      <td class="sl"></td>
      <td class="conf"></td>
      <td class="votes"></td>
    `;
    elSignals.prepend(tr);
  }
  tr.querySelector('.time').textContent = new Date(sig.timestamp).toLocaleString();
  tr.querySelector('.symbol').textContent = sig.symbol;
  tr.querySelector('.action').innerHTML = actionLabel;
  tr.querySelector('.price').textContent = fmt(sig.entry_price, 4);
  tr.querySelector('.qty').textContent = sig.quantity || 0;
  tr.querySelector('.pct').textContent = `${fmt(sig.position_percent, 2)}%`;
  tr.querySelector('.tp').textContent = sig.take_profit_price ? fmt(sig.take_profit_price, 4) : '';
  tr.querySelector('.sl').textContent = sig.stop_loss_price ? fmt(sig.stop_loss_price, 4) : '';
  tr.querySelector('.conf').textContent = `${sig.confidence || 0}%`;
  tr.querySelector('.votes').textContent = votePairs;
}

function connectSSE() {
  const src = new EventSource('/events');
  src.onopen = () => { elConn.textContent = 'verbunden'; };
  src.onerror = () => { elConn.textContent = 'getrennt (reconnect...)'; };
  src.onmessage = (ev) => {
    try {
      const msg = JSON.parse(ev.data);
      if (msg.type === 'heartbeat') return;
      if (msg.type === 'signals') {
        (msg.data || []).forEach(upsertRow);
      } else if (msg.type === 'signal') {
        upsertRow(msg.data);
      }
    } catch (e) {
      console.error('bad message', e);
    }
  };
}

async function urlBase64ToUint8Array(base64String) {
  const padding = '='.repeat((4 - base64String.length % 4) % 4);
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
  const rawData = atob(base64);
  const outputArray = new Uint8Array(rawData.length);
  for (let i = 0; i < rawData.length; ++i) outputArray[i] = rawData.charCodeAt(i);
  return outputArray;
}

async function enablePush() {
  try {
    if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
      alert('Push wird nicht unterstützt.');
      return;
    }
    const reg = await navigator.serviceWorker.register('/sw.js');
    const resp = await fetch('/vapid');
    const { publicKey } = await resp.json();
    const sub = await reg.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: await urlBase64ToUint8Array(publicKey)
    });
    await fetch('/subscribe', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(sub) });
    btnPush.textContent = 'Benachrichtigungen aktiv';
    btnPush.disabled = true;
  } catch (e) {
    console.error(e);
    alert('Aktivierung der Push-Benachrichtigungen fehlgeschlagen.');
  }
}

btnPush.addEventListener('click', enablePush);
connectSSE();

