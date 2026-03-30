// socialEngine.js — stub for C's social module
// See docs/integration-guide-B-C.md for full spec

async function createPlayer(playerId, displayName, avatarUrl) {
  // TODO(C): persist to DynamoDB TABLE_PLAYERS
  console.log(`[socialEngine] createPlayer ${playerId} ${displayName} ${avatarUrl}`);
}

async function sit(conn, payload) {
  // TODO(C): claim chair, check conflicts, update playerState, broadcast player_sat
  throw new Error('socialEngine.sit: not yet implemented');
}

async function stand(conn, payload) {
  // TODO(C): release chair, update playerState, broadcast player_stood
  throw new Error('socialEngine.stand: not yet implemented');
}

async function chat(conn, payload) {
  // TODO(C): relay message to room, optionally filter/persist
  throw new Error('socialEngine.chat: not yet implemented');
}

async function addFriend(conn, payload) {
  // TODO(C): persist to DynamoDB TABLE_PLAYERS friends list
  throw new Error('socialEngine.addFriend: not yet implemented');
}

async function removeFriend(conn, payload) {
  // TODO(C): remove from DynamoDB TABLE_PLAYERS friends list
  throw new Error('socialEngine.removeFriend: not yet implemented');
}

module.exports = { createPlayer, sit, stand, chat, addFriend, removeFriend };
