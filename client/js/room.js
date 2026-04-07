import {
  ROOM, TILESET, MANIFEST, ROOM_TEMPLATES, templateIdx,
  tileImages, furnitureImages, isLive, ws, authState, gameState, selectedChar,
  moveInterval, gameLoop, furnDrag,
  setROOM, setTemplateIdx, setPlayer, setWalkIdx, setSpriteSheet, setIsLive,
  setTileCanvasCache, setWs, setCurrentRoomId, setMoveInterval, setGameLoop
} from './state.js';
import { log, showScreen, loadImage } from './utils.js';
import { sizeCanvas } from './canvas.js';
import { startLoop } from './render.js';
import { fetchCharacters } from './characters.js';
import { connectWS } from './network.js';
import { handleCanvasClickGame, initGameLoop } from './game.js';
import { furnDragStart, furnDragMove, furnDragEnd } from './furniture.js';

export async function loadTemplate(id) {
  const resp = await fetch(`/rooms/${id}.json`);
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
  const room = await resp.json();
  setROOM(room);

  const usedTiles = new Set();
  for (const row of room.tileMap) for (const t of row) usedTiles.add(t);
  await Promise.all([...usedTiles].map(tileId => {
    if (tileImages[tileId]) return;
    const def = TILESET[tileId];
    if (!def) return;
    return loadImage(def.sprite).then(img => { tileImages[tileId] = img; }).catch(() => {});
  }));

  const usedFurn = new Set((room.furniture || []).map(f => f.itemId));
  await Promise.all([...usedFurn].map(itemId => {
    if (furnitureImages[itemId]) return;
    const def = MANIFEST.furniture?.[itemId];
    if (!def) return;
    return loadImage(def.sprite).then(img => { furnitureImages[itemId] = img; }).catch(() => {});
  }));

  setTileCanvasCache(null);
}

export async function switchTemplate(delta) {
  const newIdx = ((templateIdx + delta) % ROOM_TEMPLATES.length + ROOM_TEMPLATES.length) % ROOM_TEMPLATES.length;
  setTemplateIdx(newIdx);
  const t = ROOM_TEMPLATES[newIdx];
  try {
    await loadTemplate(t.id);
  } catch (e) {
    log(`Failed to load room template: ${e.message}`, 'error');
    return;
  }
  const sp = ROOM.spawnPoint || { x: 6, y: 6 };
  setPlayer({ x: sp.x, y: sp.y, direction: 'down', pose: 'idle' });
  setWalkIdx(0);
  sizeCanvas();
  document.getElementById('template-label').textContent = `${t.name}  [${newIdx + 1}/${ROOM_TEMPLATES.length}]`;
  log(`Room: ${t.name}`, 'ok');
}

export async function enterRoom(img) {
  setSpriteSheet(img);
  setIsLive(false);

  // Inject "★ My Room" if the player has a previously decorated room
  const myRoomData = JSON.parse(localStorage.getItem('pixelMyRoom') || 'null');
  if (myRoomData && myRoomData.count > 0 && !ROOM_TEMPLATES.some(t => t._isMyRoom)) {
    const baseName = ROOM_TEMPLATES.find(t => t.id === myRoomData.template)?.name || myRoomData.template;
    ROOM_TEMPLATES.unshift({ id: myRoomData.template, name: `★ My Room (${baseName})`, _isMyRoom: true });
  }

  const saved = localStorage.getItem('pixelRoomTemplate');
  const idx = ROOM_TEMPLATES.findIndex(t => t.id === saved);
  setTemplateIdx(idx >= 0 ? idx : 0);

  if (ROOM_TEMPLATES[templateIdx].id !== 'default') {
    try { await loadTemplate(ROOM_TEMPLATES[templateIdx].id); }
    catch (e) { setTemplateIdx(0); log(`Room load failed, using default`, 'error'); }
  }

  const t = ROOM_TEMPLATES[templateIdx];
  document.getElementById('template-prev').classList.add('visible');
  document.getElementById('template-next').classList.add('visible');
  document.getElementById('template-label').classList.add('visible');
  document.getElementById('template-label').textContent = `${t.name}  [${templateIdx + 1}/${ROOM_TEMPLATES.length}]`;
  log(`Rooms: ${ROOM_TEMPLATES.map((r,i) => (i===templateIdx?'▶ ':'')+r.name).join(' · ')}`, 'ok');

  const sp = ROOM.spawnPoint || { x: 6, y: 6 };
  setPlayer({ x: sp.x, y: sp.y, direction: 'down', pose: 'idle' });
  setWalkIdx(0);
  document.getElementById('room-label').textContent = 'PICK YOUR ROOM';
  document.getElementById('room-label').className = 'room-label';
  document.getElementById('enter-btn').style.display = '';
  document.getElementById('live-toolbar').classList.remove('visible');
  showScreen('room-screen');
  sizeCanvas(); startLoop();
  log(`arrows: prev.visible=${document.getElementById('template-prev').classList.contains('visible')} left=${document.getElementById('template-prev').style.left}`, 'ok');
}

export function exitRoom() {
  if (ws) { ws.close(); setWs(null); }
  if (moveInterval) { clearInterval(moveInterval); setMoveInterval(null); }
  if (gameLoop) { cancelAnimationFrame(gameLoop); setGameLoop(null); }
  setIsLive(false);
  showScreen('select-screen');
  fetchCharacters();
}

export function enterGame() {
  localStorage.setItem('pixelRoomTemplate', ROOM_TEMPLATES[templateIdx].id);

  document.getElementById('template-prev').classList.remove('visible');
  document.getElementById('template-next').classList.remove('visible');
  document.getElementById('template-label').classList.remove('visible');

  setIsLive(true);
  document.getElementById('enter-btn').style.display = 'none';
  document.getElementById('live-toolbar').classList.add('visible');
  document.getElementById('room-label').textContent = 'LIVE';
  document.getElementById('room-label').className = 'room-label live';
  gameState.avatarUrl = selectedChar?.url || gameState.avatarUrl || '';
  log('Live mode', 'ok');

  const joinAndShow = (socket) => {
    setCurrentRoomId(authState.playerId);
    const chosenTemplate = ROOM_TEMPLATES[templateIdx].id;
    socket.send(JSON.stringify({ type: 'join_room', payload: { roomId: authState.playerId, avatarUrl: gameState.avatarUrl, template: chosenTemplate } }));
    socket.send(JSON.stringify({ type: 'get_online_players', payload: {} }));
    setTimeout(() => {
      showScreen('game-screen');
      const cvs = document.getElementById('game-canvas');
      cvs.addEventListener('mousedown', (e) => { if (furnDragStart(e, cvs)) e.preventDefault(); });
      document.addEventListener('mousemove', (e) => furnDragMove(e));
      document.addEventListener('mouseup', (e) => { if (furnDrag) furnDragEnd(e, cvs); });
      cvs.addEventListener('click', handleCanvasClickGame);
      initGameLoop();
    }, 300);
  };

  // Always establish a fresh connection when entering the game
  if (ws) { try { ws.close(); } catch(e) {} setWs(null); }
  if (authState.jwt) {
    connectWS(joinAndShow);
  }
}
