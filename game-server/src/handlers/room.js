const { joinRoom, leaveRoom, updatePlayerState, getPlayerState } = require('../state');
const { broadcastToRoom, sendTo } = require('../broadcast');

async function handleJoinRoom(conn, payload) {
  const { roomId, x, y, avatarUrl } = payload;
  joinRoom(conn, roomId, x, y, avatarUrl);
  broadcastToRoom(roomId, {
    type: 'player_joined',
    payload: { playerId: conn.playerId, displayName: conn.displayName, x, y, avatarUrl }
  }, conn.playerId);
}

async function handleLeaveRoom(conn, payload) {
  const state = getPlayerState(conn.playerId);
  if (!state) return;
  const { roomId } = state;
  leaveRoom(conn);
  broadcastToRoom(roomId, {
    type: 'player_left',
    payload: { playerId: conn.playerId }
  });
}

async function handleMove(conn, payload) {
  const { direction } = payload;
  const state = getPlayerState(conn.playerId);
  if (!state) return;
  state.direction = direction;
  updatePlayerState(conn.playerId, { direction });
  broadcastToRoom(state.roomId, {
    type: 'player_moved',
    payload: { playerId: conn.playerId, direction }
  }, conn.playerId);
}

module.exports = { handleJoinRoom, handleLeaveRoom, handleMove };
