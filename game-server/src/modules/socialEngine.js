// socialEngine.js — stub for C's social module

async function createPlayer(playerId, displayName, avatarUrl) {
  // Stub: store player record (would write to DynamoDB Players table)
  console.log(`[socialEngine] createPlayer ${playerId} ${displayName} ${avatarUrl}`);
}

async function addFriend(conn, payload) {
  throw new Error('socialEngine: not yet implemented');
}

async function removeFriend(conn, payload) {
  throw new Error('socialEngine: not yet implemented');
}

module.exports = { createPlayer, addFriend, removeFriend };
