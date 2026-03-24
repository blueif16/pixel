const { getPlayerState, updatePlayerState } = require('../state');
const { broadcastToRoom, sendTo } = require('../broadcast');

async function handleSit(conn, payload) {
  const { chairId } = payload;
  const state = getPlayerState(conn.playerId);
  if (!state) return;
  updatePlayerState(conn.playerId, { pose: 'sitting', seatPosition: chairId });
  broadcastToRoom(state.roomId, {
    type: 'player_sat',
    payload: { playerId: conn.playerId, chairId }
  });
}

async function handleStand(conn, payload) {
  const state = getPlayerState(conn.playerId);
  if (!state) return;
  updatePlayerState(conn.playerId, { pose: 'standing', seatPosition: null });
  broadcastToRoom(state.roomId, {
    type: 'player_stood',
    payload: { playerId: conn.playerId }
  });
}

async function handleChat(conn, payload) {
  const { message } = payload;
  const state = getPlayerState(conn.playerId);
  if (!state) return;
  broadcastToRoom(state.roomId, {
    type: 'player_chat',
    payload: { playerId: conn.playerId, displayName: conn.displayName, message }
  });
}

async function handleAddFriend(conn, payload) {
  const socialEngine = require('../modules/socialEngine');
  return socialEngine.addFriend(conn, payload);
}

async function handleRemoveFriend(conn, payload) {
  const socialEngine = require('../modules/socialEngine');
  return socialEngine.removeFriend(conn, payload);
}

module.exports = { handleSit, handleStand, handleChat, handleAddFriend, handleRemoveFriend };
